from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


@dataclass(slots=True)
class ProxySourceConfig:
    name: str
    type: str
    path: Optional[str] = None
    env_var: Optional[str] = None
    proxy_kind: str = "datacenter"
    username: Optional[str] = None
    password: Optional[str] = None


@dataclass(slots=True)
class ProxyConfig:
    enabled: bool = False
    remove_after_failures: int = 5
    min_success_rate: float = 0.2
    max_latency_seconds: float = 15.0
    selection_strategy: str = "weighted"  # weighted | thompson
    ewma_alpha: float = 0.2
    cooldown_base_seconds: float = 30.0
    cooldown_max_seconds: float = 600.0
    consecutive_failures_for_cooldown: int = 3
    perma_disable_after_cooldowns: int = 5
    min_attempts_before_disable: int = 5
    min_successes_for_latency_check: int = 3
    sources: List[ProxySourceConfig] = field(default_factory=list)


@dataclass(slots=True)
class CaptchaConfig:
    detect_only: bool = True
    retry_on_detected: bool = False
    detection_patterns: List[str] = field(default_factory=list)


@dataclass(slots=True)
class HeaderConfig:
    accept_languages: List[str] = field(default_factory=lambda: ["en-US,en;q=0.9"])
    default_accept: str = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"


@dataclass(slots=True)
class ScraperRuntimeConfig:
    # Run mode:
    # - "oneshot": run configured targets once and exit (good for local runs / batch jobs)
    # - "daemon": keep the process alive and re-run targets on an interval (good for Docker services)
    run_mode: str = "daemon"  # oneshot | daemon
    run_interval_seconds: float = 60.0
    requests_per_minute: int = 120
    max_concurrency: int = 10
    max_retries: int = 4
    timeout_seconds: int = 20
    initial_backoff_seconds: float = 1.0
    max_backoff_seconds: float = 20.0
    random_delay_min_ms: int = 100
    random_delay_max_ms: int = 700
    autoscale_enabled: bool = False
    autoscale_min_concurrency: int = 2
    autoscale_check_interval_seconds: float = 5.0
    autoscale_scale_step: int = 2
    autoscale_queue_per_worker_scale_up: int = 25
    autoscale_queue_per_worker_scale_down: int = 5


@dataclass(slots=True)
class TargetExtractConfig:
    title_selector: str = "title"
    links_selector: str = "a"
    links_attribute: str = "href"


@dataclass(slots=True)
class TargetConfig:
    name: str
    urls: List[str] = field(default_factory=list)
    render_js: bool = False
    wait_for_selector: Optional[str] = None
    wait_timeout_ms: int = 5000
    extract: TargetExtractConfig = field(default_factory=TargetExtractConfig)


@dataclass(slots=True)
class StorageConfig:
    output_dir: str = "data/output"
    backup_dir: str = "data/backups"
    dedupe_state_file: str = "data/state/dedupe.json"
    write_csv: bool = True


@dataclass(slots=True)
class MonitoringConfig:
    metrics_enabled: bool = True
    metrics_port: int = 9108
    health_host: str = "0.0.0.0"
    health_port: int = 8080
    log_file: str = "logs/scraper.log"


@dataclass(slots=True)
class AppConfig:
    scraper: ScraperRuntimeConfig = field(default_factory=ScraperRuntimeConfig)
    proxies: ProxyConfig = field(default_factory=ProxyConfig)
    captcha: CaptchaConfig = field(default_factory=CaptchaConfig)
    headers: HeaderConfig = field(default_factory=HeaderConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    targets: List[TargetConfig] = field(default_factory=list)


class ConfigError(ValueError):
    """Raised when configuration is invalid."""


def _parse_proxy_sources(raw_sources: List[Dict[str, Any]]) -> List[ProxySourceConfig]:
    return [ProxySourceConfig(**item) for item in raw_sources]


def _parse_targets(raw_targets: List[Dict[str, Any]]) -> List[TargetConfig]:
    parsed: List[TargetConfig] = []
    for target in raw_targets:
        extract_raw = target.get("extract", {})
        extract_cfg = TargetExtractConfig(**extract_raw)
        urls: List[str] = []
        if isinstance(target.get("url"), str) and target.get("url"):
            urls.append(target["url"])
        raw_urls = target.get("urls", [])
        if isinstance(raw_urls, list):
            for u in raw_urls:
                if isinstance(u, str) and u.strip():
                    urls.append(u.strip())
        urls = list(dict.fromkeys(urls))
        if not urls:
            raise ConfigError(f"Target '{target.get('name')}' must define 'url' or 'urls'.")
        parsed.append(
            TargetConfig(
                name=target["name"],
                urls=urls,
                render_js=target.get("render_js", False),
                wait_for_selector=target.get("wait_for_selector"),
                wait_timeout_ms=target.get("wait_timeout_ms", 5000),
                extract=extract_cfg,
            )
        )
    return parsed


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    proxy_raw = raw.get("proxies", {})
    proxy_cfg = ProxyConfig(
        enabled=proxy_raw.get("enabled", False),
        remove_after_failures=proxy_raw.get("remove_after_failures", 5),
        min_success_rate=proxy_raw.get("min_success_rate", 0.2),
        max_latency_seconds=proxy_raw.get("max_latency_seconds", 15.0),
        selection_strategy=proxy_raw.get("selection_strategy", "weighted"),
        ewma_alpha=proxy_raw.get("ewma_alpha", 0.2),
        cooldown_base_seconds=proxy_raw.get("cooldown_base_seconds", 30.0),
        cooldown_max_seconds=proxy_raw.get("cooldown_max_seconds", 600.0),
        consecutive_failures_for_cooldown=proxy_raw.get("consecutive_failures_for_cooldown", 3),
        perma_disable_after_cooldowns=proxy_raw.get("perma_disable_after_cooldowns", 5),
        min_attempts_before_disable=proxy_raw.get("min_attempts_before_disable", 5),
        min_successes_for_latency_check=proxy_raw.get("min_successes_for_latency_check", 3),
        sources=_parse_proxy_sources(proxy_raw.get("sources", [])),
    )

    app_cfg = AppConfig(
        scraper=ScraperRuntimeConfig(**raw.get("scraper", {})),
        proxies=proxy_cfg,
        captcha=CaptchaConfig(**raw.get("captcha", {})),
        headers=HeaderConfig(**raw.get("headers", {})),
        storage=StorageConfig(**raw.get("storage", {})),
        monitoring=MonitoringConfig(**raw.get("monitoring", {})),
        targets=_parse_targets(raw.get("targets", [])),
    )

    if not app_cfg.targets:
        raise ConfigError("At least one target must be configured under 'targets'.")

    if app_cfg.scraper.random_delay_min_ms > app_cfg.scraper.random_delay_max_ms:
        raise ConfigError("random_delay_min_ms cannot be greater than random_delay_max_ms")

    run_mode = (app_cfg.scraper.run_mode or "daemon").strip().lower()
    if run_mode not in {"oneshot", "daemon"}:
        raise ConfigError("scraper.run_mode must be one of: oneshot, daemon")

    if app_cfg.scraper.run_interval_seconds < 0:
        raise ConfigError("scraper.run_interval_seconds must be >= 0")

    if app_cfg.scraper.autoscale_min_concurrency <= 0:
        raise ConfigError("scraper.autoscale_min_concurrency must be > 0")

    if app_cfg.scraper.autoscale_min_concurrency > app_cfg.scraper.max_concurrency:
        raise ConfigError("scraper.autoscale_min_concurrency cannot be greater than max_concurrency")

    if app_cfg.scraper.autoscale_check_interval_seconds <= 0:
        raise ConfigError("scraper.autoscale_check_interval_seconds must be > 0")

    if app_cfg.scraper.autoscale_scale_step <= 0:
        raise ConfigError("scraper.autoscale_scale_step must be > 0")

    if app_cfg.scraper.autoscale_queue_per_worker_scale_up <= 0:
        raise ConfigError("scraper.autoscale_queue_per_worker_scale_up must be > 0")

    if app_cfg.scraper.autoscale_queue_per_worker_scale_down <= 0:
        raise ConfigError("scraper.autoscale_queue_per_worker_scale_down must be > 0")

    if app_cfg.scraper.autoscale_queue_per_worker_scale_down > app_cfg.scraper.autoscale_queue_per_worker_scale_up:
        raise ConfigError(
            "scraper.autoscale_queue_per_worker_scale_down cannot be greater than autoscale_queue_per_worker_scale_up"
        )

    strategy = (app_cfg.proxies.selection_strategy or "weighted").strip().lower()
    if strategy not in {"weighted", "thompson"}:
        raise ConfigError("proxies.selection_strategy must be one of: weighted, thompson")

    if app_cfg.proxies.ewma_alpha <= 0.0 or app_cfg.proxies.ewma_alpha >= 1.0:
        raise ConfigError("proxies.ewma_alpha must be between 0 and 1 (exclusive)")

    if app_cfg.proxies.cooldown_base_seconds < 0 or app_cfg.proxies.cooldown_max_seconds < 0:
        raise ConfigError("proxies cooldown seconds must be >= 0")

    if app_cfg.proxies.cooldown_max_seconds < app_cfg.proxies.cooldown_base_seconds:
        raise ConfigError("proxies.cooldown_max_seconds cannot be less than cooldown_base_seconds")

    return app_cfg

# Alias for backward compatibility
Config = AppConfig

class ProxyHarvesterConfig:
    """Configuration for proxy harvesting"""
    enabled: bool = False
    harvest_interval_hours: int = 24
    max_proxies_per_harvest: int = 1000
    validate_proxies: bool = True
    validation_timeout: int = 10
    min_success_rate: float = 0.5
    max_response_time: float = 10.0
    auto_refresh: bool = True
    refresh_interval_hours: int = 12
    save_to_file: bool = True
    proxy_file: str = "data/proxies/harvested_proxies.txt"
