from __future__ import annotations

import asyncio
import logging
import random
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Deque, Dict, List

import requests
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from scraper.captcha.detector import CaptchaDetector
from scraper.config import AppConfig, TargetConfig
from scraper.errors import FetchAttemptError, ProxyPoolEmpty
from scraper.extractors.basic import extract_basic
from scraper.models import ScrapeResult, ScrapeTask
from scraper.monitoring.metrics import Metrics
from scraper.network.backoff import compute_backoff_seconds
from scraper.network.headers import HeaderFactory
from scraper.network.http_client import RequestsFetcher
from scraper.network.rate_limiter import RateLimiter
from scraper.network.user_agents import UserAgentPool
from scraper.proxy.pool import ProxyPool
from scraper.rendering.playwright_renderer import PlaywrightRenderer
from scraper.storage.writer import StorageManager


logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class EngineStatus:
    queued: int = 0
    in_flight: int = 0
    succeeded: int = 0
    failed: int = 0
    workers_active: int = 0
    workers_max: int = 0


@dataclass(slots=True)
class _Worker:
    worker_id: int
    stop: asyncio.Event
    task: asyncio.Task


class ScraperEngine:
    def __init__(
        self,
        cfg: AppConfig,
        *,
        proxy_pool: ProxyPool,
        captcha_detector: CaptchaDetector,
        ua_pool: UserAgentPool,
        header_factory: HeaderFactory,
        requests_fetcher: RequestsFetcher,
        renderer: PlaywrightRenderer,
        storage: StorageManager,
        metrics: Metrics,
    ) -> None:
        self._cfg = cfg
        self._proxy_pool = proxy_pool
        self._captcha_detector = captcha_detector
        self._ua_pool = ua_pool
        self._header_factory = header_factory
        self._requests_fetcher = requests_fetcher
        self._renderer = renderer
        self._storage = storage
        self._metrics = metrics

        self._status = EngineStatus()
        self._status_lock = asyncio.Lock()

        self._targets_by_name: Dict[str, TargetConfig] = {t.name: t for t in cfg.targets}
        self._recent_errors: Deque[Dict[str, object]] = deque(maxlen=50)

        self._workers: List[_Worker] = []
        self._worker_seq = 0

    def status_snapshot(self) -> Dict[str, object]:
        return {
            "queued": self._status.queued,
            "in_flight": self._status.in_flight,
            "succeeded": self._status.succeeded,
            "failed": self._status.failed,
            "workers_active": self._status.workers_active,
            "workers_max": self._status.workers_max,
        }

    def recent_errors(self, limit: int = 20) -> List[Dict[str, object]]:
        if limit <= 0:
            return []
        items = list(self._recent_errors)
        return items[-limit:]

    async def run(self) -> None:
        queue: asyncio.Queue[ScrapeTask] = asyncio.Queue()

        for target in self._cfg.targets:
            self._storage.backup_if_exists(target.name)
            for url in target.urls:
                await queue.put(
                    ScrapeTask(
                        url=url,
                        target_name=target.name,
                        render_js=target.render_js,
                        wait_for_selector=target.wait_for_selector,
                        wait_timeout_ms=target.wait_timeout_ms,
                        attempt=1,
                    )
                )

        max_workers = max(1, int(self._cfg.scraper.max_concurrency))
        autoscale = bool(self._cfg.scraper.autoscale_enabled)

        async with self._status_lock:
            self._status.queued = queue.qsize()
            self._status.workers_max = max_workers

        rate_limiter = RateLimiter(self._cfg.scraper.requests_per_minute)

        scaler_stop = asyncio.Event()
        scaler_task: asyncio.Task | None = None

        if autoscale:
            min_workers = max(1, int(self._cfg.scraper.autoscale_min_concurrency))
            min_workers = min(min_workers, max_workers)
            for _ in range(min_workers):
                await self._start_worker(queue, rate_limiter)
            scaler_task = asyncio.create_task(
                self._autoscale_loop(
                    queue=queue,
                    rate_limiter=rate_limiter,
                    stop_event=scaler_stop,
                    min_workers=min_workers,
                    max_workers=max_workers,
                )
            )
        else:
            for _ in range(max_workers):
                await self._start_worker(queue, rate_limiter)

        await queue.join()

        scaler_stop.set()
        if scaler_task:
            await asyncio.gather(scaler_task, return_exceptions=True)

        # Graceful shutdown after work is done.
        for w in self._workers:
            w.stop.set()
        await asyncio.gather(*[w.task for w in self._workers], return_exceptions=True)
        self._workers.clear()

        await self._refresh_workers_active()
        self._storage.flush()

    async def _start_worker(
        self, queue: asyncio.Queue[ScrapeTask], rate_limiter: RateLimiter
    ) -> None:
        worker_id = self._worker_seq
        self._worker_seq += 1
        stop = asyncio.Event()
        task = asyncio.create_task(self._worker_loop(worker_id, queue, rate_limiter, stop))
        self._workers.append(_Worker(worker_id=worker_id, stop=stop, task=task))
        await self._refresh_workers_active()

    async def _stop_one_worker(self) -> None:
        for w in reversed(self._workers):
            if not w.stop.is_set() and not w.task.done():
                w.stop.set()
                break
        await self._refresh_workers_active()

    async def _refresh_workers_active(self) -> None:
        active = sum(1 for w in self._workers if (not w.stop.is_set()) and (not w.task.done()))
        async with self._status_lock:
            self._status.workers_active = active

    async def _autoscale_loop(
        self,
        *,
        queue: asyncio.Queue[ScrapeTask],
        rate_limiter: RateLimiter,
        stop_event: asyncio.Event,
        min_workers: int,
        max_workers: int,
    ) -> None:
        interval = float(self._cfg.scraper.autoscale_check_interval_seconds)
        step = int(self._cfg.scraper.autoscale_scale_step)
        up_per_worker = int(self._cfg.scraper.autoscale_queue_per_worker_scale_up)
        down_per_worker = int(self._cfg.scraper.autoscale_queue_per_worker_scale_down)

        while not stop_event.is_set():
            await asyncio.sleep(interval)

            # Drop completed worker handles.
            self._workers = [w for w in self._workers if not w.task.done()]
            await self._refresh_workers_active()

            active = sum(1 for w in self._workers if (not w.stop.is_set()) and (not w.task.done()))
            if active <= 0:
                # Never fully stop.
                await self._start_worker(queue, rate_limiter)
                continue

            qsize = queue.qsize()

            should_scale_up = qsize > (active * up_per_worker)
            should_scale_down = qsize < (max(0, (active - 1) * down_per_worker))

            if should_scale_up and active < max_workers:
                to_add = min(step, max_workers - active)
                for _ in range(to_add):
                    await self._start_worker(queue, rate_limiter)
                continue

            if should_scale_down and active > min_workers:
                to_remove = min(step, active - min_workers)
                for _ in range(to_remove):
                    await self._stop_one_worker()

    async def _worker_loop(
        self,
        worker_id: int,
        queue: asyncio.Queue[ScrapeTask],
        rate_limiter: RateLimiter,
        stop_event: asyncio.Event,
    ) -> None:
        while True:
            if stop_event.is_set():
                return

            try:
                task = await asyncio.wait_for(queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            try:
                async with self._status_lock:
                    self._status.queued = queue.qsize()
                    self._status.in_flight += 1

                await rate_limiter.acquire(1.0)

                delay = random.uniform(
                    self._cfg.scraper.random_delay_min_ms / 1000.0,
                    self._cfg.scraper.random_delay_max_ms / 1000.0,
                )
                await asyncio.sleep(delay)

                await self._process_task(task)

                async with self._status_lock:
                    self._status.succeeded += 1
            except Exception as exc:
                async with self._status_lock:
                    self._status.failed += 1

                await self._handle_failure(exc, task, queue)
            finally:
                async with self._status_lock:
                    self._status.in_flight = max(0, self._status.in_flight - 1)
                    self._status.queued = queue.qsize()
                queue.task_done()

    async def _process_task(self, task: ScrapeTask) -> None:
        target_cfg = self._targets_by_name[task.target_name]

        user_agent = self._ua_pool.random()
        headers = self._header_factory.build(user_agent)

        proxy_url = None
        if self._proxy_pool.enabled():
            try:
                proxy_entry = await self._proxy_pool.acquire()
            except ProxyPoolEmpty as exc:
                raise FetchAttemptError(
                    target=task.target_name,
                    url=task.url,
                    method="proxy",
                    attempt=task.attempt,
                    reason="proxy_pool_empty",
                    message=str(exc),
                    retryable=False,
                ) from exc
            proxy_url = proxy_entry.url if proxy_entry else None

        method = "playwright" if task.render_js else "requests"

        status_code: int | None = None
        latency: float = 0.0
        final_url: str | None = None
        html: str = ""
        response_headers: Dict[str, str] = {}

        if task.render_js:
            safe_target = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in task.target_name)
            storage_state_path = f"data/state/playwright_{safe_target}.json"

            start = time.perf_counter()
            try:
                fetch_result, latency = await self._renderer.fetch(
                    task.url,
                    headers=headers,
                    user_agent=user_agent,
                    proxy_url=proxy_url,
                    storage_state_path=storage_state_path,
                    wait_for_selector=task.wait_for_selector,
                    wait_timeout_ms=task.wait_timeout_ms,
                )
            except PlaywrightTimeoutError as exc:
                latency = time.perf_counter() - start
                if proxy_url:
                    await self._proxy_pool.report_failure(proxy_url, reason="pw_timeout")
                raise FetchAttemptError(
                    target=task.target_name,
                    url=task.url,
                    method=method,
                    attempt=task.attempt,
                    reason="pw_timeout",
                    message=str(exc),
                    retryable=True,
                    latency_seconds=latency,
                    proxy=proxy_url,
                    underlying=exc,
                ) from exc
            except Exception as exc:
                latency = time.perf_counter() - start
                if proxy_url:
                    await self._proxy_pool.report_failure(proxy_url, reason="pw_error")
                raise FetchAttemptError(
                    target=task.target_name,
                    url=task.url,
                    method=method,
                    attempt=task.attempt,
                    reason="pw_error",
                    message=str(exc),
                    retryable=True,
                    latency_seconds=latency,
                    proxy=proxy_url,
                    underlying=exc,
                ) from exc

            final_url = fetch_result.url
            status_code = fetch_result.status_code
            html = fetch_result.html
        else:
            start = time.perf_counter()
            try:
                resp, latency = await asyncio.to_thread(
                    self._requests_fetcher.fetch,
                    task.url,
                    headers,
                    proxy_url,
                    self._cfg.scraper.timeout_seconds,
                )
            except requests.exceptions.Timeout as exc:
                latency = time.perf_counter() - start
                if proxy_url:
                    await self._proxy_pool.report_failure(proxy_url, reason="timeout")
                raise FetchAttemptError(
                    target=task.target_name,
                    url=task.url,
                    method=method,
                    attempt=task.attempt,
                    reason="timeout",
                    message=str(exc),
                    retryable=True,
                    latency_seconds=latency,
                    proxy=proxy_url,
                    underlying=exc,
                ) from exc
            except requests.exceptions.ProxyError as exc:
                latency = time.perf_counter() - start
                if proxy_url:
                    await self._proxy_pool.report_failure(proxy_url, reason="proxy_error")
                raise FetchAttemptError(
                    target=task.target_name,
                    url=task.url,
                    method=method,
                    attempt=task.attempt,
                    reason="proxy_error",
                    message=str(exc),
                    retryable=True,
                    latency_seconds=latency,
                    proxy=proxy_url,
                    underlying=exc,
                ) from exc
            except requests.exceptions.ConnectionError as exc:
                latency = time.perf_counter() - start
                if proxy_url:
                    await self._proxy_pool.report_failure(proxy_url, reason="connection_error")
                raise FetchAttemptError(
                    target=task.target_name,
                    url=task.url,
                    method=method,
                    attempt=task.attempt,
                    reason="connection_error",
                    message=str(exc),
                    retryable=True,
                    latency_seconds=latency,
                    proxy=proxy_url,
                    underlying=exc,
                ) from exc
            except requests.exceptions.RequestException as exc:
                latency = time.perf_counter() - start
                if proxy_url:
                    await self._proxy_pool.report_failure(proxy_url, reason="request_error")
                raise FetchAttemptError(
                    target=task.target_name,
                    url=task.url,
                    method=method,
                    attempt=task.attempt,
                    reason="request_error",
                    message=str(exc),
                    retryable=True,
                    latency_seconds=latency,
                    proxy=proxy_url,
                    underlying=exc,
                ) from exc

            final_url = resp.url
            status_code = resp.status_code
            html = resp.text
            response_headers = resp.headers

        signal = self._captcha_detector.detect(html)
        if signal:
            if proxy_url:
                await self._proxy_pool.report_failure(proxy_url, reason="captcha_detected", blocked=True)

            artifact_path = await self._storage.write_text_artifact(
                target=task.target_name,
                kind="captcha",
                content=html,
                suffix=".html",
            )

            raise FetchAttemptError(
                target=task.target_name,
                url=task.url,
                method=method,
                attempt=task.attempt,
                reason="captcha_detected",
                message=f"captcha_detected kind={signal.kind} evidence={signal.evidence}",
                retryable=bool(self._cfg.captcha.retry_on_detected and self._proxy_pool.enabled()),
                latency_seconds=latency,
                status_code=status_code,
                proxy=proxy_url,
                extra={
                    "captcha_kind": signal.kind,
                    "evidence": signal.evidence,
                    "final_url": final_url or "",
                    "artifact_path": artifact_path,
                },
            )

        if status_code is None:
            if proxy_url:
                await self._proxy_pool.report_failure(proxy_url, reason="no_status")
            raise FetchAttemptError(
                target=task.target_name,
                url=task.url,
                method=method,
                attempt=task.attempt,
                reason="no_status",
                message="no status code returned",
                retryable=True,
                latency_seconds=latency,
                proxy=proxy_url,
                extra={"final_url": final_url or ""},
            )

        retry_after = self._retry_after_seconds(response_headers)

        if status_code == 407:
            if proxy_url:
                await self._proxy_pool.report_failure(proxy_url, reason="proxy_auth")
            raise FetchAttemptError(
                target=task.target_name,
                url=task.url,
                method=method,
                attempt=task.attempt,
                reason="proxy_auth",
                message="proxy authentication required (HTTP 407)",
                retryable=False,
                latency_seconds=latency,
                status_code=status_code,
                proxy=proxy_url,
                extra={"final_url": final_url or ""},
            )

        if status_code == 429:
            if proxy_url:
                await self._proxy_pool.report_failure(proxy_url, reason="http_429", blocked=True)
            raise FetchAttemptError(
                target=task.target_name,
                url=task.url,
                method=method,
                attempt=task.attempt,
                reason="http_429",
                message="rate limited (HTTP 429)",
                retryable=True,
                latency_seconds=latency,
                status_code=status_code,
                proxy=proxy_url,
                retry_after_seconds=retry_after,
                extra={"final_url": final_url or ""},
            )

        if status_code in (401, 403):
            if proxy_url:
                await self._proxy_pool.report_failure(proxy_url, reason=f"http_{status_code}", blocked=True)
            raise FetchAttemptError(
                target=task.target_name,
                url=task.url,
                method=method,
                attempt=task.attempt,
                reason=f"http_{status_code}",
                message=f"access denied (HTTP {status_code})",
                retryable=bool(self._proxy_pool.enabled()),
                latency_seconds=latency,
                status_code=status_code,
                proxy=proxy_url,
                extra={"final_url": final_url or ""},
            )

        if 500 <= status_code <= 599:
            if proxy_url:
                await self._proxy_pool.report_success(proxy_url, latency)
            raise FetchAttemptError(
                target=task.target_name,
                url=task.url,
                method=method,
                attempt=task.attempt,
                reason="http_5xx",
                message=f"server error (HTTP {status_code})",
                retryable=True,
                latency_seconds=latency,
                status_code=status_code,
                proxy=proxy_url,
                extra={"final_url": final_url or ""},
            )

        if 400 <= status_code <= 499:
            if proxy_url:
                await self._proxy_pool.report_success(proxy_url, latency)
            raise FetchAttemptError(
                target=task.target_name,
                url=task.url,
                method=method,
                attempt=task.attempt,
                reason="http_4xx",
                message=f"client error (HTTP {status_code})",
                retryable=False,
                latency_seconds=latency,
                status_code=status_code,
                proxy=proxy_url,
                extra={"final_url": final_url or ""},
            )

        if proxy_url:
            await self._proxy_pool.report_success(proxy_url, latency)

        extracted = extract_basic(html, target_cfg.extract)
        extracted["final_url"] = final_url

        result = ScrapeResult(
            task=task,
            success=True,
            status_code=status_code,
            latency_seconds=latency,
            html=None,
            extracted=extracted,
            error=None,
            used_proxy=proxy_url,
        )

        await self._storage.persist(result)

        self._metrics.observe_fetch(
            target=task.target_name,
            method=method,
            success=True,
            latency_seconds=latency,
        )

        logger.info(
            "fetch_success",
            extra={
                "target": task.target_name,
                "url": task.url,
                "final_url": final_url,
                "status_code": status_code,
                "latency_seconds": latency,
                "method": method,
                "proxy": proxy_url,
                "attempt": task.attempt,
            },
        )

    @staticmethod
    def _retry_after_seconds(headers: Dict[str, str]) -> float | None:
        raw = (headers.get("Retry-After") or "").strip()
        if not raw:
            return None
        try:
            value = float(raw)
        except ValueError:
            return None
        return max(0.0, value)

    async def _handle_failure(
        self, exc: Exception, task: ScrapeTask, queue: asyncio.Queue[ScrapeTask]
    ) -> None:
        if isinstance(exc, FetchAttemptError):
            err = exc
        else:
            err = FetchAttemptError(
                target=task.target_name,
                url=task.url,
                method="playwright" if task.render_js else "requests",
                attempt=task.attempt,
                reason=exc.__class__.__name__,
                message=str(exc),
                retryable=False,
                underlying=exc,
            )

        self._recent_errors.append(
            {
                "timestamp": _utc_now_iso(),
                "target": err.target,
                "reason": err.reason,
                "status_code": err.status_code,
                "proxy": err.proxy,
                "error": str(err),
            }
        )

        logger.warning(
            "fetch_failed",
            extra={
                "target": err.target,
                "url": err.url,
                "method": err.method,
                "attempt": err.attempt,
                "reason": err.reason,
                "status_code": err.status_code,
                "latency_seconds": err.latency_seconds,
                "proxy": err.proxy,
                "retryable": err.retryable,
                "retry_after_seconds": err.retry_after_seconds,
                "error": str(err),
                "extra": err.extra,
            },
        )

        await self._storage.persist_error(
            target=err.target,
            url=err.url,
            method=err.method,
            attempt=err.attempt,
            error_type=err.reason,
            error_message=str(err),
            retryable=err.retryable,
            status_code=err.status_code,
            latency_seconds=err.latency_seconds,
            proxy=err.proxy,
            extra=dict(err.extra),
        )

        self._metrics.observe_fetch(
            target=err.target,
            method=err.method,
            success=False,
            latency_seconds=err.latency_seconds,
            failure_reason=err.reason,
        )

        max_attempts = 1 + self._cfg.scraper.max_retries
        if not err.retryable or task.attempt >= max_attempts:
            return

        backoff = None
        if err.retry_after_seconds is not None:
            backoff = min(err.retry_after_seconds, float(self._cfg.scraper.max_backoff_seconds))
        if backoff is None:
            backoff = compute_backoff_seconds(
                task.attempt,
                initial=self._cfg.scraper.initial_backoff_seconds,
                maximum=self._cfg.scraper.max_backoff_seconds,
            )

        await asyncio.sleep(backoff)
        await queue.put(
            ScrapeTask(
                url=task.url,
                target_name=task.target_name,
                render_js=task.render_js,
                wait_for_selector=task.wait_for_selector,
                wait_timeout_ms=task.wait_timeout_ms,
                attempt=task.attempt + 1,
                metadata=dict(task.metadata),
            )
        )
