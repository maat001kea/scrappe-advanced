"""
Advanced Browser Fingerprint Spoofing

Mimics real browser behavior to bypass anti-bot detection:
- WebRTC spoofing
- Canvas fingerprint randomization
- WebGL parameter spoofing
- Audio fingerprint spoofing
- Navigator properties spoofing
- Screen resolution randomization
- Timezone spoofing
- Font fingerprint spoofing
- Hardware concurrency spoofing
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

try:
    from playwright.async_api import async_playwright, Browser, BrowserContext, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


logger = logging.getLogger(__name__)


# Real browser fingerprints database (simplified)
REAL_BROWSER_FINGERPRINTS = [
    {
        "vendor": "Google Inc.",
        "renderer": "WebKit WebGL",
        "version": "WebGL 2.0",
        "shading_language_version": "WebGL GLSL ES 3.00",
        "max_texture_size": 16384,
        "max_viewport_dims": [16384, 16384],
        "unmasked_vendor_webgl": "Google Inc. (NVIDIA)",
        "unmasked_renderer_webgl": "NVIDIA GeForce RTX 3080"
    },
    {
        "vendor": "Google Inc.",
        "renderer": "WebKit WebGL",
        "version": "WebGL 2.0",
        "shading_language_version": "WebGL GLSL ES 3.00",
        "max_texture_size": 16384,
        "max_viewport_dims": [16384, 16384],
        "unmasked_vendor_webgl": "Google Inc. (Intel)",
        "unmasked_renderer_webgl": "Intel(R) UHD Graphics 630"
    },
    {
        "vendor": "Google Inc.",
        "renderer": "WebKit WebGL",
        "version": "WebGL 2.0",
        "shading_language_version": "WebGL GLSL ES 3.00",
        "max_texture_size": 16384,
        "max_viewport_dims": [16384, 16384],
        "unmasked_vendor_webgl": "Google Inc. (AMD)",
        "unmasked_renderer_webgl": "AMD Radeon RX 580 Series"
    }
]


REAL_SCREEN_RESOLUTIONS = [
    (1920, 1080),
    (2560, 1440),
    (3840, 2160),
    (1366, 768),
    (1536, 864),
    (1440, 900),
    (1600, 900),
    (1280, 720),
    (1920, 1200)
]


REAL_TIMEZONES = [
    "America/New_York",
    "America/Los_Angeles",
    "America/Chicago",
    "Europe/London",
    "Europe/Paris",
    "Europe/Berlin",
    "Asia/Tokyo",
    "Asia/Shanghai",
    "Australia/Sydney"
]


REAL_LANGUAGES = [
    "en-US",
    "en-GB",
    "es-ES",
    "fr-FR",
    "de-DE",
    "it-IT",
    "pt-BR",
    "zh-CN",
    "ja-JP",
    "ko-KR"
]


@dataclass
class StealthConfig:
    """Configuration for stealth/fingerprint spoofing"""
    # Randomization settings
    randomize_fingerprint: bool = True
    randomize_screen: bool = True
    randomize_timezone: bool = True
    randomize_language: bool = True
    randomize_canvas: bool = True
    randomize_webgl: bool = True
    randomize_webrtc: bool = True
    randomize_audio: bool = True
    
    # Browser behavior settings
    human_like_mouse: bool = True
    human_like_typing: bool = True
    random_delays: bool = True
    
    # Navigator spoofing
    spoof_hardware_concurrency: bool = True
    spoof_device_memory: bool = True
    spoof_max_touch_points: bool = True
    
    # Extra protection
    block_webgl_debug_renderer_info: bool = True
    block_webrtc: bool = False  # Some sites need WebRTC
    
    # Playwright settings
    headless: bool = False  # Headless is more detectable
    viewport: Optional[tuple[int, int]] = None
    
    # Extra headers
    extra_headers: Dict[str, str] = field(default_factory=dict)


class BrowserFingerprinter:
    """
    Advanced browser fingerprint randomizer
    
    Randomizes browser fingerprints to avoid detection while maintaining
    realistic values that match real browsers.
    """
    
    def __init__(self, config: Optional[StealthConfig] = None):
        self.config = config or StealthConfig()
        self._current_fingerprint = self._generate_fingerprint()
    
    def _generate_fingerprint(self) -> Dict[str, Any]:
        """Generate a realistic browser fingerprint"""
        fingerprint = {
            "screen": self._randomize_screen() if self.config.randomize_screen else (1920, 1080),
            "timezone": self._randomize_timezone() if self.config.randomize_timezone else "America/New_York",
            "language": self._randomize_language() if self.config.randomize_language else "en-US",
            "webgl": self._randomize_webgl() if self.config.randomize_webgl else REAL_BROWSER_FINGERPRINTS[0],
            "canvas": self._randomize_canvas() if self.config.randomize_canvas else {},
            "audio": self._randomize_audio() if self.config.randomize_audio else {},
            "hardware_concurrency": self._randomize_hardware() if self.config.spoof_hardware_concurrency else 8,
            "device_memory": self._randomize_memory() if self.config.spoof_device_memory else 8,
            "max_touch_points": self._randomize_touch_points() if self.config.spoof_max_touch_points else 0,
            "webrtc": self._randomize_webrtc() if self.config.randomize_webrtc else {},
            "plugins": self._randomize_plugins(),
            "fonts": self._randomize_fonts()
        }
        return fingerprint
    
    def _randomize_screen(self) -> tuple[int, int]:
        """Randomize screen resolution"""
        return random.choice(REAL_SCREEN_RESOLUTIONS)
    
    def _randomize_timezone(self) -> str:
        """Randomize timezone"""
        return random.choice(REAL_TIMEZONES)
    
    def _randomize_language(self) -> str:
        """Randomize language"""
        return random.choice(REAL_LANGUAGES)
    
    def _randomize_webgl(self) -> Dict[str, Any]:
        """Randomize WebGL parameters"""
        return random.choice(REAL_BROWSER_FINGERPRINTS).copy()
    
    def _randomize_canvas(self) -> Dict[str, Any]:
        """Randomize canvas fingerprint (add noise)"""
        # Add slight noise to canvas operations
        noise_level = random.uniform(0.0001, 0.001)
        return {
            "noise_level": noise_level,
            "text_metrics_noise": random.uniform(-0.5, 0.5),
            "image_smoothing": random.choice([True, False])
        }
    
    def _randomize_audio(self) -> Dict[str, Any]:
        """Randomize audio fingerprint"""
        # Audio fingerprinting through AudioContext
        return {
            "sample_rate": random.choice([44100, 48000]),
            "channel_count": random.choice([1, 2]),
            "noise_level": random.uniform(0.00001, 0.0001)
        }
    
    def _randomize_hardware(self) -> int:
        """Randomize CPU core count"""
        return random.choice([4, 6, 8, 12, 16])
    
    def _randomize_memory(self) -> int:
        """Randomize device memory in GB"""
        return random.choice([4, 8, 16, 32])
    
    def _randomize_touch_points(self) -> int:
        """Randomize max touch points (0 = desktop, >0 = mobile)"""
        # 30% chance of being mobile
        if random.random() < 0.3:
            return random.choice([5, 10])
        return 0
    
    def _randomize_webrtc(self) -> Dict[str, Any]:
        """Randomize WebRTC fingerprint"""
        return {
            "local_ip": self._randomize_ip(),
            "public_ip": self._randomize_ip(),
            "candidate_type": random.choice(["host", "srflx", "relay"])
        }
    
    def _randomize_ip(self) -> str:
        """Generate random IP (for WebRTC spoofing)"""
        return f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"
    
    def _randomize_plugins(self) -> List[str]:
        """Randomize installed plugins"""
        all_plugins = [
            "Chrome PDF Plugin",
            "Chrome PDF Viewer",
            "Native Client",
            "Adobe Flash Player"
        ]
        # Randomly select 2-3 plugins
        return random.sample(all_plugins, k=random.randint(2, 3))
    
    def _randomize_fonts(self) -> List[str]:
        """Randomize available fonts"""
        common_fonts = [
            "Arial", "Times New Roman", "Courier New", "Verdana", "Georgia",
            "Palatino", "Garamond", "Bookman", "Comic Sans MS", "Trebuchet MS",
            "Arial Black", "Impact", "Lucida Console", "Tahoma", "Lucida Sans Unicode"
        ]
        # Randomly select 10-15 fonts
        return random.sample(common_fonts, k=random.randint(10, min(15, len(common_fonts))))
    
    def regenerate_fingerprint(self):
        """Generate a new fingerprint"""
        self._current_fingerprint = self._generate_fingerprint()
    
    def get_fingerprint(self) -> Dict[str, Any]:
        """Get current fingerprint"""
        return self._current_fingerprint
    
    def generate_stealth_script(self) -> str:
        """Generate JavaScript to inject for stealth"""
        fp = self._current_fingerprint
        
        script = """
        (function() {
            // Canvas fingerprint randomization
            const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
            HTMLCanvasElement.prototype.toDataURL = function(type) {
                const context = this.getContext('2d');
                if (context) {
                    const imageData = context.getImageData(0, 0, this.width, this.height);
                    for (let i = 0; i < imageData.data.length; i += 4) {
                        imageData.data[i] += Math.floor(Math.random() * 3 - 1.5);
                        imageData.data[i + 1] += Math.floor(Math.random() * 3 - 1.5);
                        imageData.data[i + 2] += Math.floor(Math.random() * 3 - 1.5);
                    }
                    context.putImageData(imageData, 0, 0);
                }
                return originalToDataURL.apply(this, arguments);
            };
            
            // WebGL parameter spoofing
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (WebGLRenderingContext.prototype.UNMASKED_VENDOR_WEBGL === parameter) {
                    return '%(webgl_vendor)s';
                }
                if (WebGLRenderingContext.prototype.UNMASKED_RENDERER_WEBGL === parameter) {
                    return '%(webgl_renderer)s';
                }
                return getParameter.apply(this, arguments);
            };
            
            // Navigator property spoofing
            Object.defineProperty(navigator, 'hardwareConcurrency', {
                get: () => %(hardware_concurrency)d
            });
            
            Object.defineProperty(navigator, 'deviceMemory', {
                get: () => %(device_memory)d
            });
            
            Object.defineProperty(navigator, 'maxTouchPoints', {
                get: () => %(max_touch_points)d
            });
            
            // Plugins spoofing
            Object.defineProperty(navigator, 'plugins', {
                get: () => %(plugins)s
            });
            
            // Timezone spoofing
            const originalTimezoneOffset = Date.prototype.getTimezoneOffset;
            Date.prototype.getTimezoneOffset = function() {
                return %(timezone_offset)d;
            };
            
            // Screen resolution spoofing
            Object.defineProperty(screen, 'width', {
                get: () => %(screen_width)d
            });
            Object.defineProperty(screen, 'height', {
                get: () => %(screen_height)d
            });
            Object.defineProperty(screen, 'availWidth', {
                get: () => %(screen_width)d
            });
            Object.defineProperty(screen, 'availHeight', {
                get: () => %(screen_height)d
            });
            
            // Languages spoofing
            Object.defineProperty(navigator, 'languages', {
                get: () => %(languages)s
            });
            
            console.log('[Stealth] Fingerprint spoofing active');
        })();
        """ % {
            'webgl_vendor': fp['webgl'].get('unmasked_vendor_webgl', 'Google Inc.'),
            'webgl_renderer': fp['webgl'].get('unmasked_renderer_webgl', 'GPU'),
            'hardware_concurrency': fp['hardware_concurrency'],
            'device_memory': fp['device_memory'],
            'max_touch_points': fp['max_touch_points'],
            'plugins': json.dumps(fp['plugins']),
            'timezone_offset': random.randint(-720, 720),  # Minutes offset
            'screen_width': fp['screen'][0],
            'screen_height': fp['screen'][1],
            'languages': json.dumps([fp['language']])
        }
        
        return script


@asynccontextmanager
async def stealth_context(
    playwright,
    config: Optional[StealthConfig] = None
) -> BrowserContext:
    """
    Context manager for creating a stealth browser context
    
    Args:
        playwright: Playwright instance
        config: Stealth configuration
    
    Yields:
        BrowserContext with stealth features enabled
    """
    if not PLAYWRIGHT_AVAILABLE:
        raise ImportError("Playwright is required for stealth context")
    
    config = config or StealthConfig()
    fingerprinter = BrowserFingerprinter(config)
    
    # Create browser
    browser = await playwright.chromium.launch(
        headless=config.headless,
        args=[
            '--disable-blink-features=AutomationControlled',
            '--disable-dev-shm-usage',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-web-security',
            '--disable-features=IsolateOrigins,site-per-process'
        ]
    )
    
    # Create context with spoofed viewport
    fp = fingerprinter.get_fingerprint()
    context = await browser.new_context(
        viewport={'width': fp['screen'][0], 'height': fp['screen'][1]},
        user_agent=fingerprinter._randomize_user_agent(),
        locale=fp['language'],
        timezone_id=fp['timezone'],
        permissions=['geolocation'],
        geolocation={'latitude': random.uniform(-90, 90), 'longitude': random.uniform(-180, 180)},
        extra_http_headers=config.extra_headers
    )
    
    # Inject stealth script
    stealth_script = fingerprinter.generate_stealth_script()
    await context.add_init_script(stealth_script)
    
    # Additional stealth measures
    await context.add_init_script("""
        // Remove webdriver property
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        
        // Chrome object
        window.chrome = {
            runtime: {}
        };
        
        // Permissions
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
    """)
    
    try:
        yield context
    finally:
        await context.close()
        await browser.close()


