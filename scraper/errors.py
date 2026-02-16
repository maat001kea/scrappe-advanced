from __future__ import annotations


class ScraperError(Exception):
    """Base class for scraper exceptions."""


class CaptchaDetected(ScraperError):
    """Raised when a CAPTCHA or bot-challenge is detected."""


class ProxyPoolEmpty(ScraperError):
    """Raised when proxy usage is enabled but no usable proxies exist."""


class FetchAttemptError(ScraperError):
    """Raised when a single fetch attempt fails with classified metadata."""

    def __init__(
        self,
        *,
        target: str,
        url: str,
        method: str,
        attempt: int,
        reason: str,
        message: str,
        retryable: bool,
        latency_seconds: float = 0.0,
        status_code: int | None = None,
        proxy: str | None = None,
        retry_after_seconds: float | None = None,
        extra: dict[str, object] | None = None,
        underlying: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.target = target
        self.url = url
        self.method = method
        self.attempt = attempt
        self.reason = reason
        self.retryable = retryable
        self.latency_seconds = latency_seconds
        self.status_code = status_code
        self.proxy = proxy
        self.retry_after_seconds = retry_after_seconds
        self.extra = extra or {}
        self.underlying = underlying
