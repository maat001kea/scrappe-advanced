import asyncio

import pytest

from scraper.network.rate_limiter import RateLimiter


@pytest.mark.asyncio
async def test_rate_limiter_fast_path() -> None:
    limiter = RateLimiter(rate_per_minute=60_000)
    await asyncio.wait_for(limiter.acquire(), timeout=0.1)


def test_rate_limiter_invalid_rate() -> None:
    with pytest.raises(ValueError):
        RateLimiter(rate_per_minute=0)
