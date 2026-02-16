from __future__ import annotations

import random
from typing import Dict, List

from scraper.config import HeaderConfig


class HeaderFactory:
    def __init__(self, config: HeaderConfig) -> None:
        self._cfg = config

    def build(self, user_agent: str) -> Dict[str, str]:
        accept_language = random.choice(self._cfg.accept_languages)
        # Keep headers stable and standards-compliant. Avoid "stealth" tricks; prefer compatibility.
        return {
            "User-Agent": user_agent,
            "Accept": self._cfg.default_accept,
            "Accept-Language": accept_language,
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "DNT": "1",
        }

    @staticmethod
    def merge(base: Dict[str, str], extra: Dict[str, str]) -> Dict[str, str]:
        merged = dict(base)
        merged.update(extra)
        return merged
