from __future__ import annotations

import random
from pathlib import Path
from typing import List, Optional


def _gen_chrome(platform_token: str, majors: List[int]) -> List[str]:
    return [
        "Mozilla/5.0 ("
        + platform_token
        + ") AppleWebKit/537.36 (KHTML, like Gecko) Chrome/"
        + str(m)
        + ".0.0.0 Safari/537.36"
        for m in majors
    ]


def _gen_edge_windows(majors: List[int]) -> List[str]:
    # Edge UAs include both Chrome and Edg tokens.
    platform = "Windows NT 10.0; Win64; x64"
    return [
        "Mozilla/5.0 ("
        + platform
        + ") AppleWebKit/537.36 (KHTML, like Gecko) Chrome/"
        + str(m)
        + ".0.0.0 Safari/537.36 Edg/"
        + str(m)
        + ".0.0.0"
        for m in majors
    ]


def _gen_firefox(platform_token: str, majors: List[int]) -> List[str]:
    return [
        "Mozilla/5.0 ("
        + platform_token
        + "; rv:"
        + str(m)
        + ".0) Gecko/20100101 Firefox/"
        + str(m)
        + ".0"
        for m in majors
    ]


def _gen_safari_macos(versions: List[str]) -> List[str]:
    platform = "Macintosh; Intel Mac OS X 14_6"
    return [
        "Mozilla/5.0 ("
        + platform
        + ") AppleWebKit/605.1.15 (KHTML, like Gecko) Version/"
        + v
        + " Safari/605.1.15"
        for v in versions
    ]


def build_default_user_agents() -> List[str]:
    # Keep this list local and deterministic (no network).
    chrome_majors = list(range(120, 138))  # 18
    firefox_majors = list(range(120, 138))  # 18
    safari_versions = [
        "16.6",
        "17.0",
        "17.1",
        "17.2",
        "17.3",
        "17.4",
        "17.5",
        "17.6",
        "18.0",
    ]

    agents: List[str] = []

    agents.extend(_gen_chrome("Windows NT 10.0; Win64; x64", chrome_majors))
    agents.extend(_gen_chrome("Macintosh; Intel Mac OS X 14_6", chrome_majors))
    agents.extend(_gen_chrome("X11; Linux x86_64", chrome_majors))

    agents.extend(_gen_edge_windows(chrome_majors))

    agents.extend(_gen_firefox("Windows NT 10.0; Win64; x64", firefox_majors))
    agents.extend(_gen_firefox("Macintosh; Intel Mac OS X 14.6", firefox_majors))
    agents.extend(_gen_firefox("X11; Linux x86_64", firefox_majors))

    agents.extend(_gen_safari_macos(safari_versions))

    # De-duplicate while preserving order.
    agents = list(dict.fromkeys(agents))

    # Ensure we meet the "100+" requirement even after de-dupe.
    if len(agents) < 100:
        raise RuntimeError(f"User agent pool too small: {len(agents)}")

    return agents


class UserAgentPool:
    def __init__(self, extra_file: Optional[str] = None, seed: Optional[int] = None) -> None:
        self._rng = random.Random(seed)
        self._agents = build_default_user_agents()

        if extra_file:
            path = Path(extra_file)
            if path.exists():
                for line in path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        self._agents.append(line)

        self._agents = list(dict.fromkeys(self._agents))

    def random(self) -> str:
        return self._rng.choice(self._agents)

    def size(self) -> int:
        return len(self._agents)
