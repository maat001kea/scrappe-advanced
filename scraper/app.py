from __future__ import annotations

import asyncio
import logging
import os
import signal
from pathlib import Path

from scraper.captcha.detector import CaptchaDetector
from scraper.config import load_config
from scraper.engine import ScraperEngine
from scraper.logging_setup import configure_logging
from scraper.monitoring.metrics import Metrics
from scraper.monitoring.server import MonitoringServer
from scraper.network.headers import HeaderFactory
from scraper.network.http_client import RequestsFetcher
from scraper.network.user_agents import UserAgentPool
from scraper.proxy.pool import ProxyPool
from scraper.rendering.playwright_renderer import PlaywrightRenderer
from scraper.storage.writer import StorageManager


logger = logging.getLogger(__name__)


async def _wait_for_stop(stop: asyncio.Event, timeout: float | None) -> bool:
    if timeout is None:
        await stop.wait()
        return True
    try:
        await asyncio.wait_for(stop.wait(), timeout=timeout)
        return True
    except asyncio.TimeoutError:
        return False


async def main() -> None:
    config_path = Path(os.getenv("SCRAPER_CONFIG", "config.yml"))
    cfg = load_config(config_path)

    configure_logging(cfg.monitoring.log_file)
    logger.info("scraper_starting", extra={"config": str(config_path)})

    metrics = Metrics()

    proxy_pool = ProxyPool(cfg.proxies)
    captcha_detector = CaptchaDetector(cfg.captcha.detection_patterns)

    ua_pool = UserAgentPool(seed=1337)
    header_factory = HeaderFactory(cfg.headers)

    fetcher = RequestsFetcher()
    renderer = PlaywrightRenderer()
    storage = StorageManager(cfg.storage)

    engine = ScraperEngine(
        cfg,
        proxy_pool=proxy_pool,
        captcha_detector=captcha_detector,
        ua_pool=ua_pool,
        header_factory=header_factory,
        requests_fetcher=fetcher,
        renderer=renderer,
        storage=storage,
        metrics=metrics,
    )

    async def status_provider() -> dict[str, object]:
        snap = engine.status_snapshot()
        proxies_total = len(await proxy_pool.all())
        proxies_healthy = len(await proxy_pool.healthy())

        metrics.set_proxy_counts(proxies_total, proxies_healthy)
        metrics.set_engine_status(
            queued=int(snap.get("queued", 0) or 0),
            in_flight=int(snap.get("in_flight", 0) or 0),
            succeeded=int(snap.get("succeeded", 0) or 0),
            failed=int(snap.get("failed", 0) or 0),
            workers_active=int(snap.get("workers_active", 0) or 0),
            workers_max=int(snap.get("workers_max", 0) or 0),
        )

        return {
            **snap,
            "proxies_total": proxies_total,
            "proxies_healthy": proxies_healthy,
            "proxies_strategy": proxy_pool.selection_strategy(),
            "proxies_top": await proxy_pool.top_summaries(limit=10),
            "recent_errors": engine.recent_errors(limit=20),
            "user_agents": ua_pool.size(),
        }

    server = MonitoringServer(
        host=cfg.monitoring.health_host,
        health_port=cfg.monitoring.health_port,
        metrics_port=cfg.monitoring.metrics_port,
        metrics_enabled=cfg.monitoring.metrics_enabled,
        status_provider=status_provider,
    )

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            # Windows / limited runtimes. Docker (Linux) supports signal handlers.
            pass

    await server.start()

    try:
        run_mode = (cfg.scraper.run_mode or "daemon").strip().lower()
        if run_mode == "oneshot":
            await engine.run()
            return

        interval = float(cfg.scraper.run_interval_seconds)
        while not stop.is_set():
            try:
                await engine.run()
            except Exception:
                logger.exception("engine_run_crashed")
                # Avoid a tight crash-loop.
                await _wait_for_stop(stop, timeout=min(30.0, max(1.0, interval)))
                continue

            if interval <= 0:
                continue
            # Sleep, but wake up early on SIGTERM/SIGINT.
            await _wait_for_stop(stop, timeout=interval)
    finally:
        await server.stop()
        await renderer.stop()
        storage.flush()
        logger.info("scraper_stopped")


if __name__ == "__main__":
    asyncio.run(main())
