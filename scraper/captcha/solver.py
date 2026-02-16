"""
Advanced CAPTCHA Solver Module

Supports:
1. API-based solving (2captcha, anti-captcha, capmonster, etc.)
2. OCR-based solving (Tesseract, EasyOCR)
3. Automatic fallback between methods
4. Rate limiting for API calls
5. Cost tracking
"""

from __future__ import annotations

import asyncio
import base64
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List
import httpx
from io import BytesIO

# Optional imports for OCR
try:
    import pytesseract
    from PIL import Image
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False


logger = logging.getLogger(__name__)


class SolverType(Enum):
    """Supported CAPTCHA solver types"""
    TWO_CAPTCHA = "2captcha"
    ANI_CAPTCHA = "anti-captcha"
    CAPMONSTER = "capmonster"
    DEATHBYCAPTCHA = "deathbycaptcha"
    OCR_TESSERACT = "ocr_tesseract"
    OCR_EASYOCR = "ocr_easyocr"


@dataclass
class CaptchaImage:
    """Represents a CAPTCHA image"""
    image_data: bytes
    format: str = "PNG"
    is_base64: bool = False

    def to_base64(self) -> str:
        """Convert to base64 string"""
        if self.is_base64:
            return self.image_data.decode() if isinstance(self.image_data, bytes) else self.image_data
        return base64.b64encode(self.image_data).decode()

    def to_pil_image(self):
        """Convert to PIL Image for OCR"""
        if self.is_base64:
            img_data = base64.b64decode(self.image_data)
        else:
            img_data = self.image_data
        return Image.open(BytesIO(img_data))


@dataclass
class SolveResult:
    """Result of CAPTCHA solving attempt"""
    success: bool
    solution: Optional[str] = None
    solver_used: Optional[str] = None
    time_taken: float = 0.0
    cost: float = 0.0
    error: Optional[str] = None
    attempts: int = 0


@dataclass
class SolverConfig:
    """Configuration for CAPTCHA solver"""
    # API-based solver settings
    api_key: Optional[str] = None
    api_url: str = "http://2captcha.com"
    api_timeout: int = 120  # seconds
    api_poll_interval: int = 5  # seconds
    
    # OCR settings
    ocr_enabled: bool = True
    ocr_language: str = "eng"
    ocr_preprocess: bool = True  # Enhance image before OCR
    
    # Strategy settings
    preferred_solver: SolverType = SolverType.TWO_CAPTCHA
    fallback_to_ocr: bool = True
    max_retries: int = 3
    max_cost_per_batch: float = 10.0  # USD
    
    # Rate limiting
    rate_limit_per_minute: int = 20
    
    def __post_init__(self):
        if not self.api_key and self.preferred_solver != SolverType.OCR_TESSERACT:
            logger.warning("No API key provided, falling back to OCR")
            self.preferred_solver = SolverType.OCR_TESSERACT


class CaptchaSolver:
    """
    Advanced CAPTCHA solver with multiple backends
    
    Automatically selects best solver based on:
    - Configuration preferences
    - API key availability
    - OCR availability
    - Cost constraints
    """
    
    def __init__(self, config: SolverConfig):
        self.config = config
        self._api_client: Optional[httpx.AsyncClient] = None
        self._request_times: List[float] = []
        self._total_cost: float = 0.0
        self._stats: Dict[str, Any] = {
            "total_solves": 0,
            "successful_solves": 0,
            "failed_solves": 0,
            "solver_breakdown": {}
        }
    
    async def __aenter__(self):
        """Async context manager entry"""
        self._api_client = httpx.AsyncClient(timeout=self.config.api_timeout)
        return self
    
    async def __aexit__(self, *args):
        """Async context manager exit"""
        if self._api_client:
            await self._api_client.aclose()
    
    async def solve(
        self,
        captcha: CaptchaImage,
        solver_type: Optional[SolverType] = None
    ) -> SolveResult:
        """
        Solve CAPTCHA using preferred or specified solver
        
        Args:
            captcha: CAPTCHA image to solve
            solver_type: Force specific solver, None for auto-select
        
        Returns:
            SolveResult with solution or error
        """
        start_time = time.time()
        
        # Rate limiting check
        await self._check_rate_limit()
        
        # Determine solver strategy
        solvers_to_try = self._get_solver_order(solver_type)
        
        for i, solver_type in enumerate(solvers_to_try):
            if i >= self.config.max_retries:
                break
            
            try:
                logger.info(f"Attempting solve with {solver_type.value} (attempt {i+1})")
                
                if solver_type in [SolverType.TWO_CAPTCHA, 
                                   SolverType.ANI_CAPTCHA,
                                   SolverType.CAPMONSTER,
                                   SolverType.DEATHBYCAPTCHA]:
                    result = await self._solve_with_api(captcha, solver_type)
                elif solver_type == SolverType.OCR_TESSERACT:
                    result = await self._solve_with_ocr_tesseract(captcha)
                else:
                    result = SolveResult(
                        success=False,
                        error=f"Solver {solver_type.value} not implemented yet"
                    )
                
                result.time_taken = time.time() - start_time
                result.attempts = i + 1
                
                if result.success:
                    self._update_stats(True, solver_type.value, result.cost)
                    logger.info(f"CAPTCHA solved successfully with {solver_type.value}")
                    return result
                else:
                    logger.warning(f"Solve failed with {solver_type.value}: {result.error}")
                    
            except Exception as e:
                logger.error(f"Exception during solve with {solver_type.value}: {e}")
                
        # All solvers failed
        self._update_stats(False, "none", 0)
        return SolveResult(
            success=False,
            time_taken=time.time() - start_time,
            attempts=len(solvers_to_try),
            error="All solvers failed"
        )
    
    async def solve_from_url(
        self,
        image_url: str,
        solver_type: Optional[SolverType] = None
    ) -> SolveResult:
        """Solve CAPTCHA from image URL"""
        async with httpx.AsyncClient() as client:
            response = await client.get(image_url)
            response.raise_for_status()
            captcha = CaptchaImage(image_data=response.content)
            return await self.solve(captcha, solver_type)
    
    async def solve_from_base64(
        self,
        base64_data: str,
        solver_type: Optional[SolverType] = None
    ) -> SolveResult:
        """Solve CAPTCHA from base64 string"""
        image_data = base64.b64decode(base64_data)
        captcha = CaptchaImage(image_data=image_data, is_base64=False)
        return await self.solve(captcha, solver_type)
    
    def _get_solver_order(self, preferred: Optional[SolverType]) -> List[SolverType]:
        """Get ordered list of solvers to try"""
        if preferred:
            solvers = [preferred]
        else:
            solvers = [self.config.preferred_solver]
        
        # Add fallbacks
        if self.config.fallback_to_ocr:
            if SolverType.OCR_TESSERACT not in solvers:
                solvers.append(SolverType.OCR_TESSERACT)
        
        return solvers
    
    async def _solve_with_api(
        self,
        captcha: CaptchaImage,
        solver_type: SolverType
    ) -> SolveResult:
        """Solve using API-based service (2captcha, anti-captcha, etc.)"""
        if not self._api_client:
            self._api_client = httpx.AsyncClient(timeout=self.config.api_timeout)
        
        if not self.config.api_key:
            return SolveResult(
                success=False,
                error="No API key configured"
            )
        
        # Cost check
        if self._total_cost >= self.config.max_cost_per_batch:
            return SolveResult(
                success=False,
                error="Cost limit reached"
            )
        
        try:
            if solver_type == SolverType.TWO_CAPTCHA:
                return await self._solve_2captcha(captcha)
            elif solver_type == SolverType.ANI_CAPTCHA:
                return await self._solve_anti_captcha(captcha)
            elif solver_type == SolverType.CAPMONSTER:
                return await self._solve_capmonster(captcha)
            else:
                return SolveResult(
                    success=False,
                    error=f"API solver {solver_type.value} not implemented"
                )
        except Exception as e:
            return SolveResult(
                success=False,
                error=str(e)
            )
    
    async def _solve_2captcha(self, captcha: CaptchaImage) -> SolveResult:
        """Solve using 2captcha API"""
        base64_img = captcha.to_base64()
        
        # Submit CAPTCHA
        submit_data = {
            "key": self.config.api_key,
            "method": "base64",
            "body": base64_img,
            "json": 1
        }
        
        response = await self._api_client.post(
            f"{self.config.api_url}/in.php",
            data=submit_data
        )
        result = response.json()
        
        if result["status"] != 1:
            return SolveResult(
                success=False,
                error=result.get("request", "Unknown error")
            )
        
        captcha_id = result["request"]
        
        # Poll for result
        start_poll = time.time()
        while time.time() - start_poll < self.config.api_timeout:
            await asyncio.sleep(self.config.api_poll_interval)
            
            poll_data = {
                "key": self.config.api_key,
                "action": "get",
                "id": captcha_id,
                "json": 1
            }
            
            response = await self._api_client.get(
                f"{self.config.api_url}/res.php",
                params=poll_data
            )
            result = response.json()
            
            if result["status"] == 1:
                solution = result["request"]
                # 2captcha costs ~$0.0007 per normal CAPTCHA
                cost = 0.0007
                self._total_cost += cost
                
                return SolveResult(
                    success=True,
                    solution=solution,
                    solver_used="2captcha",
                    cost=cost
                )
            elif result["request"] == "CAPCHA_NOT_READY":
                continue
            else:
                return SolveResult(
                    success=False,
                    error=result.get("request", "Unknown error")
                )
        
        return SolveResult(
            success=False,
            error="Timeout waiting for solution"
        )
    
    async def _solve_anti_captcha(self, captcha: CaptchaImage) -> SolveResult:
        """Solve using Anti-Captcha API"""
        base64_img = captcha.to_base64()
        
        # Create task
        create_task_data = {
            "clientKey": self.config.api_key,
            "task": {
                "type": "ImageToTextTask",
                "body": base64_img,
                "phrase": False,
                "case": False,
                "numeric": 0,
                "math": False,
                "minLength": 0,
                "maxLength": 0
            }
        }
        
        response = await self._api_client.post(
            "https://api.anti-captcha.com/createTask",
            json=create_task_data
        )
        result = response.json()
        
        if result["errorId"] != 0:
            return SolveResult(
                success=False,
                error=result.get("errorDescription", "Unknown error")
            )
        
        task_id = result["taskId"]
        
        # Get task result
        start_poll = time.time()
        while time.time() - start_poll < self.config.api_timeout:
            await asyncio.sleep(self.config.api_poll_interval)
            
            get_task_data = {
                "clientKey": self.config.api_key,
                "taskId": task_id
            }
            
            response = await self._api_client.post(
                "https://api.anti-captcha.com/getTaskResult",
                json=get_task_data
            )
            result = response.json()
            
            if result["status"] == "ready":
                solution = result["solution"]["text"]
                # Anti-captcha costs ~$0.0005 per normal CAPTCHA
                cost = 0.0005
                self._total_cost += cost
                
                return SolveResult(
                    success=True,
                    solution=solution,
                    solver_used="anti-captcha",
                    cost=cost
                )
            elif result["status"] == "processing":
                continue
            else:
                return SolveResult(
                    success=False,
                    error=result.get("errorDescription", "Unknown error")
                )
        
        return SolveResult(
            success=False,
            error="Timeout waiting for solution"
        )
    
    async def _solve_capmonster(self, captcha: CaptchaImage) -> SolveResult:
        """Solve using CapMonster API (compatible with 2captcha)"""
        # CapMonster is compatible with 2captcha API
        # Just different endpoint URL
        original_url = self.config.api_url
        self.config.api_url = "https://api.capmonster.cloud"
        
        try:
            result = await self._solve_2captcha(captcha)
            if result.success:
                result.solver_used = "capmonster"
            return result
        finally:
            self.config.api_url = original_url
    
    async def _solve_with_ocr_tesseract(self, captcha: CaptchaImage) -> SolveResult:
        """Solve using Tesseract OCR"""
        if not TESSERACT_AVAILABLE:
            return SolveResult(
                success=False,
                error="Tesseract not installed. Install with: apt-get install tesseract-ocr && pip install pytesseract"
            )
        
        try:
            image = captcha.to_pil_image()
            
            # Preprocessing if enabled
            if self.config.ocr_preprocess:
                image = self._preprocess_image(image)
            
            # OCR with Tesseract
            config = f'--oem 3 --psm 6 -l {self.config.ocr_language}'
            solution = pytesseract.image_to_string(image, config=config).strip()
            
            # Clean up common OCR artifacts
            solution = solution.replace(" ", "").replace("\n", "").replace("\t", "")
            
            if not solution:
                return SolveResult(
                    success=False,
                    error="OCR produced empty result"
                )
            
            return SolveResult(
                success=True,
                solution=solution,
                solver_used="ocr_tesseract",
                cost=0.0  # OCR is free!
            )
        
        except Exception as e:
            return SolveResult(
                success=False,
                error=f"OCR failed: {str(e)}"
            )
    
    def _preprocess_image(self, image):
        """Preprocess image for better OCR results"""
        from PIL import Image, ImageEnhance, ImageFilter
        
        # Convert to grayscale
        if image.mode != 'L':
            image = image.convert('L')
        
        # Increase contrast
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(2.0)
        
        # Apply slight blur to reduce noise
        image = image.filter(ImageFilter.MedianFilter())
        
        # Binarize (threshold)
        image = image.point(lambda x: 0 if x < 128 else 255, '1')
        
        return image
    
    async def _check_rate_limit(self):
        """Check and enforce rate limiting"""
        now = time.time()
        # Remove old entries (older than 1 minute)
        self._request_times = [t for t in self._request_times if now - t < 60]
        
        if len(self._request_times) >= self.config.rate_limit_per_minute:
            wait_time = 60 - (now - self._request_times[0])
            if wait_time > 0:
                logger.info(f"Rate limit reached, waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
        
        self._request_times.append(now)
    
    def _update_stats(self, success: bool, solver: str, cost: float):
        """Update solving statistics"""
        self._stats["total_solves"] += 1
        if success:
            self._stats["successful_solves"] += 1
        else:
            self._stats["failed_solves"] += 1
        
        if solver not in self._stats["solver_breakdown"]:
            self._stats["solver_breakdown"][solver] = {
                "attempts": 0,
                "successes": 0,
                "failures": 0,
                "total_cost": 0.0
            }
        
        breakdown = self._stats["solver_breakdown"][solver]
        breakdown["attempts"] += 1
        if success:
            breakdown["successes"] += 1
        else:
            breakdown["failures"] += 1
        breakdown["total_cost"] += cost
    
    def get_stats(self) -> Dict[str, Any]:
        """Get solver statistics"""
        return {
            **self._stats,
            "total_cost": self._total_cost,
            "success_rate": (
                self._stats["successful_solves"] / self._stats["total_solves"]
                if self._stats["total_solves"] > 0 else 0
            )
        }
    
    def reset_stats(self):
        """Reset all statistics"""
        self._stats = {
            "total_solves": 0,
            "successful_solves": 0,
            "failed_solves": 0,
            "solver_breakdown": {}
        }
        self._total_cost = 0.0
