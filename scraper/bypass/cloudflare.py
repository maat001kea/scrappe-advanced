"""
Cloudflare Turnstile and Challenge Solver

Automatically bypasses Cloudflare challenges:
- Turnstile widget solving
- JS challenge bypass
- "Just a moment" page handling
- Cookie persistence
- Challenge completion waiting
"""

from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

try:
    from playwright.async_api import Page, BrowserContext
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


logger = logging.getLogger(__name__)


@dataclass
class CloudflareConfig:
    """Configuration for Cloudflare solver"""
    # Turnstile settings
    turnstile_api_key: Optional[str] = None
    turnstile_site_key: Optional[str] = None
    turnstile_timeout: int = 30  # seconds
    
    # Challenge handling
    max_wait_time: int = 120  # seconds
    poll_interval: float = 2.0  # seconds
    
    # Retry settings
    max_retries: int = 3
    retry_delay: float = 5.0  # seconds
    
    # User simulation
    human_like_waiting: bool = True
    random_mouse_movements: bool = True
    
    # Cookie persistence
    save_cookies: bool = True
    cookie_file: str = "cf_cookies.json"


class CloudflareSolver:
    """
    Automatic Cloudflare challenge and Turnstile solver
    
    Handles:
    - "Just a moment" challenges
    - Turnstile verification
    - JavaScript challenges
    - Cookie management
    """
    
    # Cloudflare challenge indicators
    CHALLENGE_SELECTORS = [
        "#challenge-form",
        ".cf-challenge",
        "#turnstile-wrapper",
        ".cf-turnstile",
        "[data-sitekey]",
        "div[id^='turnstile']"
    ]
    
    def __init__(self, config: Optional[CloudflareConfig] = None):
        self.config = config or CloudflareConfig()
        self._cookies: Dict[str, Any] = {}
    
    async def solve_turnstile(
        self,
        page: Page,
        site_key: Optional[str] = None,
        wait_for_selector: Optional[str] = None
    ) -> bool:
        """
        Solve Cloudflare Turnstile challenge
        
        Args:
            page: Playwright page
            site_key: Turnstile site key (optional, auto-detected if not provided)
            wait_for_selector: Selector to wait for after solving
        
        Returns:
            True if solved successfully, False otherwise
        """
        if not PLAYWRIGHT_AVAILABLE:
            logger.error("Playwright is required for Turnstile solving")
            return False
        
        try:
            # Wait for Turnstile widget to appear
            await page.wait_for_selector("[data-sitekey]", timeout=10000)
            
            # Get site key if not provided
            if not site_key:
                element = await page.query_selector("[data-sitekey]")
                if element:
                    site_key = await element.get_attribute("data-sitekey")
            
            logger.info(f"Detected Turnstile widget with site key: {site_key}")
            
            # Try to auto-solve (click the checkbox)
            await self._auto_solve_turnstile(page)
            
            # Wait for verification
            await asyncio.sleep(random.uniform(2, 5))
            
            # Check if challenge is solved
            if await self._is_challenge_solved(page):
                logger.info("Turnstile solved successfully")
                
                # Wait for specific element if requested
                if wait_for_selector:
                    await page.wait_for_selector(wait_for_selector, timeout=30000)
                
                return True
            else:
                logger.warning("Turnstile challenge appears unsolved")
                return False
        
        except Exception as e:
            logger.error(f"Error solving Turnstile: {e}")
            return False
    
    async def bypass_challenge(
        self,
        page: Page,
        url: str,
        wait_for_selector: Optional[str] = None
    ) -> bool:
        """
        Bypass Cloudflare challenge page
        
        Args:
            page: Playwright page
            url: URL to navigate to
            wait_for_selector: Selector to wait for after bypass
        
        Returns:
            True if bypassed successfully, False otherwise
        """
        if not PLAYWRIGHT_AVAILABLE:
            logger.error("Playwright is required for challenge bypass")
            return False
        
        # Navigate to URL
        await page.goto(url, wait_until="domcontentloaded")
        
        # Check if challenge is present
        if not await self._detect_challenge(page):
            logger.info("No Cloudflare challenge detected")
            return True
        
        logger.info("Cloudflare challenge detected, attempting bypass...")
        
        # Try multiple strategies
        strategies = [
            self._bypass_by_waiting,
            self._bypass_by_clicking,
            self._bypass_with_human_behavior
        ]
        
        for attempt in range(self.config.max_retries):
            for strategy in strategies:
                try:
                    result = await strategy(page)
                    if result:
                        # Check if challenge is solved
                        if await self._is_challenge_solved(page):
                            logger.info("Challenge bypassed successfully")
                            
                            # Wait for specific element if requested
                            if wait_for_selector:
                                await page.wait_for_selector(wait_for_selector, timeout=30000)
                            
                            # Save cookies
                            if self.config.save_cookies:
                                await self._save_cookies(page)
                            
                            return True
                except Exception as e:
                    logger.debug(f"Strategy failed: {e}")
                    continue
            
            # Wait before retry
            if attempt < self.config.max_retries - 1:
                await asyncio.sleep(self.config.retry_delay)
        
        logger.error("Failed to bypass Cloudflare challenge")
        return False
    
    async def _detect_challenge(self, page: Page) -> bool:
        """Detect if Cloudflare challenge is present"""
        try:
            # Check for common challenge indicators
            title = await page.title()
            challenge_keywords = [
                "Just a moment",
                "Attention Required",
                "Checking your browser",
                "DDoS protection by Cloudflare"
            ]
            
            for keyword in challenge_keywords:
                if keyword in title:
                    return True
            
            # Check for challenge DOM elements
            for selector in self.CHALLENGE_SELECTORS:
                element = await page.query_selector(selector)
                if element:
                    return True
            
            return False
        except Exception as e:
            logger.debug(f"Error detecting challenge: {e}")
            return False
    
    async def _is_challenge_solved(self, page: Page) -> bool:
        """Check if challenge is solved"""
        try:
            title = await page.title()
            
            # Check for challenge keywords in title
            challenge_keywords = [
                "Just a moment",
                "Attention Required",
                "Checking your browser"
            ]
            
            for keyword in challenge_keywords:
                if keyword in title:
                    return False
            
            # Check for challenge DOM elements
            challenge_present = False
            for selector in self.CHALLENGE_SELECTORS:
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    challenge_present = True
                    break
            
            if challenge_present:
                return False
            
            return True
        except Exception as e:
            logger.debug(f"Error checking if solved: {e}")
            return False
    
    async def _bypass_by_waiting(self, page: Page) -> bool:
        """Bypass by simply waiting for challenge to complete"""
        logger.info("Attempting bypass by waiting...")
        
        start_time = asyncio.get_event_loop().time()
        
        while asyncio.get_event_loop().time() - start_time < self.config.max_wait_time:
            await asyncio.sleep(self.config.poll_interval)
            
            if await self._is_challenge_solved(page):
                return True
        
        return False
    
    async def _bypass_by_clicking(self, page: Page) -> bool:
        """Bypass by clicking verification elements"""
        logger.info("Attempting bypass by clicking...")
        
        # Try to find and click verification button
        click_selectors = [
            "input[type='button']",
            "button",
            ".cf-challenge-button",
            "#challenge-form input[type='submit']"
        ]
        
        for selector in click_selectors:
            try:
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    await element.click()
                    await asyncio.sleep(2)
                    
                    if await self._is_challenge_solved(page):
                        return True
            except Exception as e:
                continue
        
        return False
    
    async def _bypass_with_human_behavior(self, page: Page) -> bool:
        """Bypass with simulated human behavior"""
        logger.info("Attempting bypass with human behavior simulation...")
        
        # Random mouse movements
        if self.config.random_mouse_movements:
            await self._simulate_mouse_movements(page)
        
        # Scroll page randomly
        await page.evaluate("window.scrollBy(0, Math.random() * 500)")
        await asyncio.sleep(random.uniform(0.5, 2))
        
        # Try waiting again
        return await self._bypass_by_waiting(page)
    
    async def _auto_solve_turnstile(self, page: Page):
        """Auto-solve Turnstile by clicking checkbox"""
        try:
            # Look for Turnstile checkbox
            checkbox = await page.query_selector(".cf-turnstile input[type='checkbox']")
            if checkbox:
                await checkbox.click()
                logger.debug("Clicked Turnstile checkbox")
        except Exception as e:
            logger.debug(f"Error clicking Turnstile: {e}")
    
    async def _simulate_mouse_movements(self, page: Page):
        """Simulate random mouse movements"""
        try:
            viewport = page.viewport_size
            if not viewport:
                return
            
            width, height = viewport["width"], viewport["height"]
            
            for _ in range(random.randint(3, 10)):
                x = random.randint(100, width - 100)
                y = random.randint(100, height - 100)
                
                await page.mouse.move(x, y)
                await asyncio.sleep(random.uniform(0.1, 0.5))
        except Exception as e:
            logger.debug(f"Error simulating mouse movements: {e}")
    
    async def _save_cookies(self, page: Page):
        """Save cookies for future use"""
        try:
            cookies = await page.context.cookies()
            self._cookies = {c["name"]: c["value"] for c in cookies}
            logger.debug(f"Saved {len(cookies)} cookies")
        except Exception as e:
            logger.debug(f"Error saving cookies: {e}")
    
    async def load_cookies(self, context: BrowserContext):
        """Load saved cookies into context"""
        try:
            if self._cookies:
                cookies_list = [
                    {"name": name, "value": value, "domain": ".cloudflare.com"}
                    for name, value in self._cookies.items()
                ]
                await context.add_cookies(cookies_list)
                logger.debug(f"Loaded {len(cookies_list)} cookies")
        except Exception as e:
            logger.debug(f"Error loading cookies: {e}")
