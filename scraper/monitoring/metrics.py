from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from prometheus_client import Counter, Gauge, Histogram


REQUESTS_TOTAL = Counter(
    "scraper_requests_total",
    "Total number of fetch attempts",
    ["target", "method"],
)

REQUESTS_SUCCEEDED = Counter(
    "scraper_requests_succeeded_total",
    "Total number of successful fetches",
    ["target", "method"],
)

REQUESTS_FAILED = Counter(
    "scraper_requests_failed_total",
    "Total number of failed fetches",
    ["target", "method", "reason"],
)

REQUEST_LATENCY = Histogram(
    "scraper_request_latency_seconds",
    "Latency in seconds for fetches",
    ["target", "method"],
    buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 20, 40),
)

PROXIES_TOTAL = Gauge(
    "scraper_proxies_total",
    "Number of proxies known to the pool",
)

PROXIES_HEALTHY = Gauge(
    "scraper_proxies_healthy",
    "Number of proxies currently considered healthy",
)

ENGINE_QUEUE = Gauge(
    "scraper_engine_queue_size",
    "Current number of queued tasks",
)

ENGINE_IN_FLIGHT = Gauge(
    "scraper_engine_in_flight",
    "Current number of in-flight tasks",
)

ENGINE_SUCCEEDED = Gauge(
    "scraper_engine_succeeded",
    "Total number of succeeded tasks",
)

ENGINE_FAILED = Gauge(
    "scraper_engine_failed",
    "Total number of failed tasks",
)

ENGINE_WORKERS_ACTIVE = Gauge(
    "scraper_engine_workers_active",
    "Current active worker count",
)

ENGINE_WORKERS_MAX = Gauge(
    "scraper_engine_workers_max",
    "Configured max worker count",
)


@dataclass(slots=True)
class Metrics:
    def observe_fetch(
        self,
        *,
        target: str,
        method: str,
        success: bool,
        latency_seconds: float,
        failure_reason: Optional[str] = None,
    ) -> None:
        REQUESTS_TOTAL.labels(target=target, method=method).inc()
        REQUEST_LATENCY.labels(target=target, method=method).observe(latency_seconds)
        if success:
            REQUESTS_SUCCEEDED.labels(target=target, method=method).inc()
        else:
            REQUESTS_FAILED.labels(
                target=target,
                method=method,
                reason=failure_reason or "unknown",
            ).inc()

    def set_proxy_counts(self, total: int, healthy: int) -> None:
        PROXIES_TOTAL.set(total)
        PROXIES_HEALTHY.set(healthy)

    def set_engine_status(
        self,
        *,
        queued: int,
        in_flight: int,
        succeeded: int,
        failed: int,
        workers_active: int,
        workers_max: int,
    ) -> None:
        ENGINE_QUEUE.set(queued)
        ENGINE_IN_FLIGHT.set(in_flight)
        ENGINE_SUCCEEDED.set(succeeded)
        ENGINE_FAILED.set(failed)
        ENGINE_WORKERS_ACTIVE.set(workers_active)
        ENGINE_WORKERS_MAX.set(workers_max)

# Alias for backward compatibility
MetricsCollector = Metrics
