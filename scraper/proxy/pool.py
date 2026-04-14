from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Dict, List, Optional

from scraper.config import ProxyConfig
from scraper.errors import ProxyPoolEmpty
from scraper.proxy.models import ProxyEntry, ProxyStats
from scraper.proxy.sources import build_sources
from scraper.proxy.utils import apply_proxy_auth, normalize_proxy_url, redact_proxy_url


logger = logging.getLogger(__name__)


class ProxyPool:
    """Proxy pool with basic health scoring.

    Notes:
    - This pool is designed to be safe-by-default and transparent.
    - It does not attempt to bypass access controls. Use only with permission.
    """

    def __init__(self, config: ProxyConfig) -> None:
        self._cfg = config
        self._lock = asyncio.Lock()
        self._entries: Dict[str, ProxyEntry] = {}
        self.reload()

    async def reload(self) -> None:
        async with self._lock:
            sources = build_sources(self._cfg.sources)
            new_urls: List[tuple[str, str, str]] = []
            for src_cfg, src in sources:
                for url in src.load():
                    url = url.strip()
                    if not url:
                        continue
                    proxy_url = normalize_proxy_url(url)
                    proxy_url = apply_proxy_auth(
                        proxy_url,
                        username=src_cfg.username,
                        password=src_cfg.password,
                    )
                    new_urls.append((proxy_url, src_cfg.name, src_cfg.proxy_kind))

            for url, source_name, kind in new_urls:
                if url in self._entries:
                    continue
                self._entries[url] = ProxyEntry(
                    url=url,
                    source=source_name,
                    kind=kind,
                    stats=ProxyStats(),
                    disabled=False,
                )

            if not self._entries:
                logger.warning("proxy_pool_empty")

    def enabled(self) -> bool:
        return bool(self._cfg.enabled)

    async def all(self) -> List[ProxyEntry]:
        async with self._lock:
            return list(self._entries.values())

    async def healthy(self) -> List[ProxyEntry]:
        async with self._lock:
            now = time.monotonic()
            return [
                p
                for p in self._entries.values()
                if (not p.disabled) and (now >= p.disabled_until_mono)
            ]

    def selection_strategy(self) -> str:
        return (self._cfg.selection_strategy or "weighted").strip().lower()

    @staticmethod
    def _expected_success(entry: ProxyEntry) -> float:
        alpha = max(0.1, float(entry.stats.beta_alpha))
        beta = max(0.1, float(entry.stats.beta_beta))
        return alpha / (alpha + beta)

    def _score(self, entry: ProxyEntry) -> float:
        # Prefer high success-rate, low latency, and low failure streak. Add tiny jitter to avoid hot-spotting.
        attempts = entry.stats.attempts()
        # Laplace smoothing keeps brand new proxies in the mix without letting them dominate.
        weighted_sr = (entry.stats.success + 1) / (attempts + 2) if attempts >= 0 else 0.5
        if self.selection_strategy() == "thompson":
            alpha = max(0.1, float(entry.stats.beta_alpha))
            beta = max(0.1, float(entry.stats.beta_beta))
            success_pred = random.betavariate(alpha, beta)
        else:
            success_pred = weighted_sr

        latency = max(0.2, entry.stats.effective_latency())
        in_flight = max(0, entry.in_flight)
        fail_streak = max(0, entry.stats.consecutive_failures)

        base = success_pred / (latency**1.15)
        base = base / (1.0 + (0.75 * fail_streak))
        base = base / (1.0 + (0.50 * in_flight))

        return max(0.0001, base) + random.uniform(0.0, 0.01)

    def _deterministic_score(self, entry: ProxyEntry) -> float:
        attempts = entry.stats.attempts()
        weighted_sr = (entry.stats.success + 1) / (attempts + 2) if attempts >= 0 else 0.5
        if self.selection_strategy() == "thompson":
            success_pred = self._expected_success(entry)
        else:
            success_pred = weighted_sr

        latency = max(0.2, entry.stats.effective_latency())
        in_flight = max(0, entry.in_flight)
        fail_streak = max(0, entry.stats.consecutive_failures)

        base = success_pred / (latency**1.15)
        base = base / (1.0 + (0.75 * fail_streak))
        base = base / (1.0 + (0.50 * in_flight))
        return max(0.0001, base)

    async def get(self) -> Optional[ProxyEntry]:
        return await self.acquire()

    async def acquire(self) -> Optional[ProxyEntry]:
        if not self._cfg.enabled:
            return None

        async with self._lock:
            now = time.monotonic()
            candidates = [
                p
                for p in self._entries.values()
                if (not p.disabled) and (now >= p.disabled_until_mono)
            ]
            if not candidates:
                raise ProxyPoolEmpty("Proxy usage enabled but no healthy proxies are available")

            scored = [(self._score(p), p) for p in candidates]
            scored.sort(key=lambda x: x[0], reverse=True)

            # Take top-K then weighted random pick to spread load while still preferring good proxies.
            top = scored[: min(20, len(scored))]
            weights = [s for s, _ in top]
            total = sum(weights)
            r = random.uniform(0.0, total)
            upto = 0.0
            chosen = top[-1][1]
            for score, entry in top:
                upto += score
                if upto >= r:
                    chosen = entry
                    break

            chosen.in_flight += 1
            return chosen

    async def report_success(self, proxy_url: str, latency_seconds: float) -> None:
        async with self._lock:
            entry = self._entries.get(proxy_url)
            if not entry:
                return
            entry.in_flight = max(0, entry.in_flight - 1)
            entry.stats.record_success(latency_seconds, ewma_alpha=self._cfg.ewma_alpha)
            # Successful usage should gradually restore confidence.
            entry.cooldown_level = max(0, entry.cooldown_level - 1)
            self._maybe_disable(entry)

    async def report_failure(self, proxy_url: str, *, reason: str = "unknown", blocked: bool = False) -> None:
        async with self._lock:
            entry = self._entries.get(proxy_url)
            if not entry:
                return
            entry.in_flight = max(0, entry.in_flight - 1)
            entry.stats.record_failure(reason=reason, blocked=blocked)
            self._maybe_disable(entry, reason=reason)

    async def top_summaries(self, limit: int = 10) -> List[Dict[str, object]]:
        async with self._lock:
            now = time.monotonic()
            entries = list(self._entries.values())
            entries.sort(key=self._deterministic_score, reverse=True)
            out: List[Dict[str, object]] = []
            for e in entries[: max(0, limit)]:
                cooldown_left = max(0.0, e.disabled_until_mono - now)
                out.append(
                    {
                        "proxy": redact_proxy_url(e.url),
                        "source": e.source,
                        "kind": e.kind,
                        "attempts": e.stats.attempts(),
                        "success_rate": round(e.stats.success_rate(), 4),
                        "predicted_success": round(self._expected_success(e), 4),
                        "latency_seconds": round(e.stats.effective_latency(), 3),
                        "in_flight": e.in_flight,
                        "cooldown_level": e.cooldown_level,
                        "cooldown_seconds_left": round(cooldown_left, 3) if cooldown_left > 0 else 0.0,
                        "blocked": e.stats.blocked,
                        "consecutive_failures": e.stats.consecutive_failures,
                        "disabled": e.disabled,
                        "disabled_reason": e.disabled_reason,
                    }
                )
            return out

    def _maybe_disable(self, entry: ProxyEntry, reason: str = "unknown") -> None:
        # Disable rules are conservative; you can tune them via config.
        if entry.disabled:
            return

        if reason == "proxy_auth":
            self._perma_disable(entry, reason="proxy_auth")
            return

        if entry.stats.consecutive_failures >= self._cfg.consecutive_failures_for_cooldown:
            self._cooldown(entry, reason="consecutive_failures")
            return

        if (
            entry.stats.success >= self._cfg.min_successes_for_latency_check
            and entry.stats.effective_latency() > self._cfg.max_latency_seconds
        ):
            self._cooldown(entry, reason="high_latency")
            return

        attempts = entry.stats.attempts()
        if (
            attempts >= self._cfg.min_attempts_before_disable
            and entry.stats.failure >= self._cfg.remove_after_failures
            and entry.stats.success_rate() < self._cfg.min_success_rate
        ):
            self._perma_disable(entry, reason="low_success_rate")
            return

        if self._cfg.perma_disable_after_cooldowns > 0 and (
            entry.cooldown_level >= self._cfg.perma_disable_after_cooldowns
        ):
            self._perma_disable(entry, reason="too_many_cooldowns")
            return

    def _cooldown(self, entry: ProxyEntry, *, reason: str) -> None:
        now = time.monotonic()
        entry.cooldown_level += 1
        entry.disabled_reason = reason

        base = max(1.0, float(self._cfg.cooldown_base_seconds))
        cooldown = base * (2 ** max(0, entry.cooldown_level - 1))
        cooldown = min(cooldown, float(self._cfg.cooldown_max_seconds))
        cooldown = cooldown * random.uniform(0.9, 1.1)

        entry.disabled_until_mono = now + cooldown

        logger.info(
            "proxy_cooldown",
            extra={
                "proxy": entry.url,
                "source": entry.source,
                "kind": entry.kind,
                "reason": reason,
                "cooldown_seconds": round(cooldown, 3),
                "cooldown_level": entry.cooldown_level,
                "success_rate": round(entry.stats.success_rate(), 4),
                "latency_seconds": round(entry.stats.effective_latency(), 3),
                "attempts": entry.stats.attempts(),
                "consecutive_failures": entry.stats.consecutive_failures,
                "blocked": entry.stats.blocked,
            },
        )

    def _perma_disable(self, entry: ProxyEntry, *, reason: str) -> None:
        entry.disabled = True
        entry.disabled_reason = reason
        logger.info(
            "proxy_disabled",
            extra={
                "proxy": entry.url,
                "source": entry.source,
                "kind": entry.kind,
                "reason": reason,
                "success_rate": round(entry.stats.success_rate(), 4),
                "latency_seconds": round(entry.stats.effective_latency(), 3),
                "attempts": entry.stats.attempts(),
                "failures": entry.stats.failure,
                "blocked": entry.stats.blocked,
                "cooldown_level": entry.cooldown_level,
            },
        )
