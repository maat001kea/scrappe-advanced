from pathlib import Path

import pytest
import asyncio

from scraper.config import ProxyConfig, ProxySourceConfig
from scraper.errors import ProxyPoolEmpty
from scraper.proxy.pool import ProxyPool


@pytest.mark.asyncio
async def test_proxy_pool_disables_bad_proxy(tmp_path: Path) -> None:
    proxy_file = tmp_path / "proxies.txt"
    proxy_file.write_text("http://127.0.0.1:8080\n", encoding="utf-8")

    cfg = ProxyConfig(
        enabled=True,
        remove_after_failures=2,
        min_success_rate=0.5,
        max_latency_seconds=15.0,
        consecutive_failures_for_cooldown=2,
        cooldown_base_seconds=999.0,
        sources=[
            ProxySourceConfig(
                name="file",
                type="file",
                path=str(proxy_file),
                proxy_kind="datacenter",
            )
        ],
    )

    pool = ProxyPool(cfg)
    await pool.initialize()
    p = await pool.get()
    assert p is not None

    await pool.report_failure(p.url)
    await pool.report_failure(p.url)

    healthy = await pool.healthy()
    assert len(healthy) == 0
    with pytest.raises(ProxyPoolEmpty):
        await pool.get()
