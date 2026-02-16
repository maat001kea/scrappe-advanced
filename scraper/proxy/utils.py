from __future__ import annotations

from typing import Dict
from urllib.parse import urlparse, urlunparse


def normalize_proxy_url(proxy_url: str) -> str:
    proxy_url = (proxy_url or "").strip()
    if not proxy_url:
        return proxy_url

    if "://" not in proxy_url:
        # Default to http proxy if scheme omitted.
        return f"http://{proxy_url}"

    return proxy_url


def proxy_for_playwright(proxy_url: str) -> Dict[str, str]:
    """Convert a proxy URL string into Playwright's proxy dict.

    Playwright expects: {server, username?, password?}
    """

    normalized = normalize_proxy_url(proxy_url)
    parsed = urlparse(normalized)

    server = f"{parsed.scheme}://{parsed.hostname}:{parsed.port}" if parsed.hostname and parsed.port else normalized
    out: Dict[str, str] = {"server": server}

    if parsed.username:
        out["username"] = parsed.username
    if parsed.password:
        out["password"] = parsed.password

    return out


def apply_proxy_auth(proxy_url: str, *, username: str | None, password: str | None) -> str:
    """Inject username/password into a proxy URL when the proxy list omits auth.

    If the proxy URL already contains credentials, it is returned unchanged.
    """

    if not proxy_url:
        return proxy_url
    if not username or not password:
        return proxy_url

    normalized = normalize_proxy_url(proxy_url)
    parsed = urlparse(normalized)
    if parsed.username:
        return normalized

    if not parsed.hostname:
        return normalized

    host = parsed.hostname
    port = f":{parsed.port}" if parsed.port else ""
    netloc = f"{username}:{password}@{host}{port}"
    rebuilt = urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
    return rebuilt


def redact_proxy_url(proxy_url: str) -> str:
    """Remove credentials from a proxy URL for logs/UI."""

    normalized = normalize_proxy_url(proxy_url)
    parsed = urlparse(normalized)
    if parsed.hostname and parsed.port:
        return f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"
    return normalized
