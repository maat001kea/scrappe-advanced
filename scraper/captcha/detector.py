from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Optional


@dataclass(frozen=True, slots=True)
class CaptchaSignal:
    kind: str
    evidence: str


_DEFAULT_PATTERNS = [
    ("recaptcha", re.compile(r"g-recaptcha|recaptcha", re.IGNORECASE)),
    ("hcaptcha", re.compile(r"hcaptcha|h-captcha", re.IGNORECASE)),
    ("captcha", re.compile(r"\bcaptcha\b", re.IGNORECASE)),
    ("cloudflare", re.compile(r"cloudflare|cf-chl|challenge-platform", re.IGNORECASE)),
    ("cloudflare_text", re.compile(r"just a moment|checking your browser|attention required", re.IGNORECASE)),
    ("datadome", re.compile(r"datadome|geo\.captcha-delivery|ddos-guard", re.IGNORECASE)),
    ("perimeterx", re.compile(r"perimeterx|px-captcha|px-block", re.IGNORECASE)),
    ("akamai", re.compile(r"akamai|bm-verify|akamai bot manager|abck", re.IGNORECASE)),
    ("imperva", re.compile(r"incapsula|imperva|visid_incap", re.IGNORECASE)),
    ("human_check", re.compile(r"verify you are human|are you human|are you a robot|unusual traffic", re.IGNORECASE)),
]


class CaptchaDetector:
    def __init__(self, extra_patterns: Iterable[str] = ()) -> None:
        self._patterns = list(_DEFAULT_PATTERNS)
        for pat in extra_patterns:
            pat = (pat or "").strip()
            if not pat:
                continue
            self._patterns.append(("custom", re.compile(pat, re.IGNORECASE)))

    def detect(self, html: str) -> Optional[CaptchaSignal]:
        if not html:
            return None
        sample = html[:200_000]  # avoid regex on huge pages
        for kind, regex in self._patterns:
            match = regex.search(sample)
            if match:
                return CaptchaSignal(kind=kind, evidence=match.group(0)[:200])
        return None
