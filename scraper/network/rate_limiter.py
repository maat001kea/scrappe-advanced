from __future__ import annotations

import asyncio
import time


class RateLimiter:
    """A simple async rate limiter using a token-bucket style refill."""

    def __init__(self, rate_per_minute: int) -> None:
        if rate_per_minute <= 0:
            raise ValueError("rate_per_minute must be > 0")
        self._capacity = float(rate_per_minute)
        self._tokens = float(rate_per_minute)
        self._refill_per_second = float(rate_per_minute) / 60.0
        self._last = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: float = 1.0) -> None:
        if tokens <= 0:
            return

        while True:
            async with self._lock:
                now = time.monotonic()
                elapsed = now - self._last
                self._last = now

                self._tokens = min(self._capacity, self._tokens + elapsed * self._refill_per_second)
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return

                missing = tokens - self._tokens
                sleep_for = missing / self._refill_per_second

            await asyncio.sleep(sleep_for)
