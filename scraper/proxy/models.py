"""Proxy data models"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum
import asyncio
import time


class ProxyKind(Enum):
    """Proxy type classification"""
    DATA_CENTER = "datacenter"
    RESIDENTIAL = "residential"
    MOBILE = "mobile"
    SHARED = "shared"


class ProxyStatus(Enum):
    """Proxy status"""
    ACTIVE = "active"
    COOLDOWN = "cooldown"
    DISABLED = "disabled"
    FAILED = "failed"


@dataclass
class ProxyStats:
    """Statistics for a proxy"""
    total_attempts: int = 0
    successful_attempts: int = 0
    failed_attempts: int = 0
    consecutive_failures: int = 0
    cooldown_count: int = 0
    last_used: Optional[datetime] = None
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate (0-1)"""
        if self.total_attempts == 0:
            return 1.0
        return self.successful_attempts / self.total_attempts
    
    def record_success(self):
        """Record a successful request"""
        self.total_attempts += 1
        self.successful_attempts += 1
        self.consecutive_failures = 0
        self.last_success = datetime.now()
        self.last_used = datetime.now()
    
    def record_failure(self):
        """Record a failed request"""
        self.total_attempts += 1
        self.failed_attempts += 1
        self.consecutive_failures += 1
        self.last_failure = datetime.now()
        self.last_used = datetime.now()


@dataclass
class ProxyEntry:
    """Single proxy entry"""
    url: str
    kind: ProxyKind = ProxyKind.DATA_CENTER
    status: ProxyStatus = ProxyStatus.ACTIVE
    stats: ProxyStats = field(default_factory=ProxyStats)
    
    # EWMA latency (Exponentially Weighted Moving Average)
    _ewma_latency: float = 0.0
    _ewma_alpha: float = 0.2
    
    # Cooldown state
    _cooldown_until: Optional[float] = None
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    
    def get_latency(self) -> float:
        """Get EWMA latency estimate"""
        return self._ewma_latency
    
    def update_latency(self, latency: float):
        """Update EWMA latency with new measurement"""
        if self._ewma_latency == 0:
            self._ewma_latency = latency
        else:
            self._ewma_latency = (
                self._ewma_alpha * latency +
                (1 - self._ewma_alpha) * self._ewma_latency
            )
    
    def is_in_cooldown(self) -> bool:
        """Check if proxy is in cooldown period"""
        if self._cooldown_until is None:
            return False
        return time.time() < self._cooldown_until
    
    def set_cooldown(self, duration_seconds: float):
        """Set proxy to cooldown"""
        self._cooldown_until = time.time() + duration_seconds
        self.stats.cooldown_count += 1
        self.status = ProxyStatus.COOLDOWN
    
    def exit_cooldown(self):
        """Exit cooldown and reactivate"""
        self._cooldown_until = None
        self.status = ProxyStatus.ACTIVE
    
    def disable(self):
        """Permanently disable proxy"""
        self.status = ProxyStatus.DISABLED
    
    def reset_consecutive_failures(self):
        """Reset consecutive failure counter"""
        self.stats.consecutive_failures = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'url': self.url,
            'kind': self.kind.value,
            'status': self.status.value,
            'stats': {
                'total_attempts': self.stats.total_attempts,
                'successful_attempts': self.stats.successful_attempts,
                'failed_attempts': self.stats.failed_attempts,
                'consecutive_failures': self.stats.consecutive_failures,
                'success_rate': self.stats.success_rate,
                'last_used': self.stats.last_used.isoformat() if self.stats.last_used else None,
                'last_success': self.stats.last_success.isoformat() if self.stats.last_success else None,
                'last_failure': self.stats.last_failure.isoformat() if self.stats.last_failure else None,
            },
            'latency': self._ewma_latency,
            'cooldown_until': self._cooldown_until
        }


# Proxy alias for compatibility
Proxy = ProxyEntry
