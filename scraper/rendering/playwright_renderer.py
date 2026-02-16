from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from pathlib import Path

from playwright.async_api import Browser, BrowserContext, async_playwright

from scraper.proxy.utils import proxy_for_playwright

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class BrowserFetchResult:
    url: str
    status_code: Optional[int]
    html: str


class PlaywrightRenderer:
    def __init__(self) -> None:
        self._playwright = None
        self._browser: Optional[Browser] = None

    async def start(self) -> None:
        if self._browser:
            return
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=True)
        logger.info("playwright_started")

    async def stop(self) -> None:
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        logger.info("playwright_stopped")

    async def fetch(
        self,
        url: str,
        headers: Dict[str, str],
        user_agent: str,
        proxy_url: Optional[str],
        storage_state_path: Optional[str],
        wait_for_selector: Optional[str],
        wait_timeout_ms: int,
    ) -> Tuple[BrowserFetchResult, float]:
        if not self._browser:
            await self.start()

        assert self._browser is not None

        context: Optional[BrowserContext] = None
        page = None
        start_ts = time.perf_counter()
        try:
            context = await self._new_context(
                user_agent=user_agent,
                headers=headers,
                proxy_url=proxy_url,
                storage_state_path=storage_state_path,
            )
            page = await context.new_page()

            response = await page.goto(url, wait_until="domcontentloaded", timeout=wait_timeout_ms)
            status = response.status if response else None

            # SPAs: give the page a chance to settle.
            try:
                await page.wait_for_load_state("networkidle", timeout=wait_timeout_ms)
            except Exception:
                pass

            if wait_for_selector:
                await page.wait_for_selector(wait_for_selector, timeout=wait_timeout_ms)

            html = await page.content()
            final_url = str(page.url)
            latency = time.perf_counter() - start_ts

            if storage_state_path:
                path = Path(storage_state_path)
                path.parent.mkdir(parents=True, exist_ok=True)
                await context.storage_state(path=str(path))

            return BrowserFetchResult(url=final_url, status_code=status, html=html), latency
        finally:
            if page is not None:
                try:
                    await page.close()
                except Exception:
                    pass
            if context is not None:
                try:
                    await context.close()
                except Exception:
                    pass

    async def _new_context(
        self,
        user_agent: str,
        headers: Dict[str, str],
        proxy_url: Optional[str],
        storage_state_path: Optional[str],
    ) -> BrowserContext:
        assert self._browser is not None

        viewport = {
            "width": random.randint(1280, 1920),
            "height": random.randint(720, 1080),
        }

        proxy = None
        if proxy_url:
            # Playwright expects {server, username, password} format.
            proxy = proxy_for_playwright(proxy_url)

        # Locale should be a BCP 47 tag (e.g. en-US). Accept-Language often contains q-values.
        accept_lang = headers.get("Accept-Language", "en-US")
        locale = accept_lang.split(",")[0].split(";")[0].strip() or "en-US"

        storage_state = None
        if storage_state_path:
            p = Path(storage_state_path)
            if p.exists():
                storage_state = str(p)

        return await self._browser.new_context(
            user_agent=user_agent,
            extra_http_headers=headers,
            viewport=viewport,
            proxy=proxy,
            locale=locale,
            storage_state=storage_state,
        )
