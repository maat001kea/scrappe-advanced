from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(slots=True)
class ScrapeTask:
    url: str
    target_name: str
    render_js: bool = False
    wait_for_selector: Optional[str] = None
    wait_timeout_ms: int = 5000
    attempt: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ScrapeResult:
    task: ScrapeTask
    success: bool
    status_code: Optional[int]
    latency_seconds: float
    html: Optional[str] = None
    extracted: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    used_proxy: Optional[str] = None
