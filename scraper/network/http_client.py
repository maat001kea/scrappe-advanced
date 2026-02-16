from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import requests

from scraper.proxy.utils import normalize_proxy_url

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class HttpResponse:
    status_code: int
    text: str
    headers: Dict[str, str]
    url: str


class RequestsFetcher:
    def __init__(self) -> None:
        self._session = requests.Session()

    def fetch(
        self,
        url: str,
        headers: Dict[str, str],
        proxy_url: Optional[str],
        timeout_seconds: int,
    ) -> Tuple[HttpResponse, float]:
        proxies = None
        if proxy_url:
            proxy_url = normalize_proxy_url(proxy_url)
            proxies = {
                "http": proxy_url,
                "https": proxy_url,
            }

        start = time.perf_counter()
        resp = self._session.get(
            url,
            headers=headers,
            proxies=proxies,
            timeout=timeout_seconds,
            allow_redirects=True,
        )
        latency = time.perf_counter() - start

        return (
            HttpResponse(
                status_code=resp.status_code,
                text=resp.text,
                headers=dict(resp.headers),
                url=str(resp.url),
            ),
            latency,
        )
