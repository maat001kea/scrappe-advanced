from __future__ import annotations
from dataclasses import dataclass
from typing import Awaitable, Callable, Dict, Optional

from aiohttp import web
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from scraper.monitoring.ui import HTML

@dataclass(slots=True)
class MonitoringServer:
    host: str
    health_port: int
    metrics_port: int
    metrics_enabled: bool

    # A callable that returns a dict with basic runtime status.
    status_provider: Callable[[], Awaitable[Dict[str, object]]]

    _health_runner: Optional[web.AppRunner] = None
    _metrics_runner: Optional[web.AppRunner] = None

    async def start(self) -> None:
        if self.metrics_enabled and self.metrics_port == self.health_port:
            app = web.Application()
            app.router.add_get("/", self._ui)
            app.router.add_get("/ui", self._ui)
            app.router.add_get("/health", self._health)
            app.router.add_get("/metrics", self._metrics)
            self._health_runner = web.AppRunner(app)
            await self._health_runner.setup()
            await web.TCPSite(self._health_runner, self.host, self.health_port).start()
            return

        health_app = web.Application()
        health_app.router.add_get("/", self._ui)
        health_app.router.add_get("/ui", self._ui)
        health_app.router.add_get("/health", self._health)
        self._health_runner = web.AppRunner(health_app)
        await self._health_runner.setup()
        await web.TCPSite(self._health_runner, self.host, self.health_port).start()

        if self.metrics_enabled:
            metrics_app = web.Application()
            metrics_app.router.add_get("/metrics", self._metrics)
            self._metrics_runner = web.AppRunner(metrics_app)
            await self._metrics_runner.setup()
            await web.TCPSite(self._metrics_runner, self.host, self.metrics_port).start()

    async def stop(self) -> None:
        if self._metrics_runner:
            await self._metrics_runner.cleanup()
            self._metrics_runner = None
        if self._health_runner:
            await self._health_runner.cleanup()
            self._health_runner = None

    async def _health(self, request: web.Request) -> web.Response:
        payload = {"ok": True, **(await self.status_provider() or {})}
        return web.json_response(payload)

    async def _metrics(self, request: web.Request) -> web.Response:
        data = generate_latest()
        return web.Response(body=data, headers={"Content-Type": CONTENT_TYPE_LATEST})

    async def _ui(self, request: web.Request) -> web.Response:
        return web.Response(text=HTML, content_type="text/html")
