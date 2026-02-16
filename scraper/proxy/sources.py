from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, List

from scraper.config import ProxySourceConfig


class ProxySource:
    def load(self) -> List[str]:
        raise NotImplementedError


class FileProxySource(ProxySource):
    def __init__(self, path: str) -> None:
        self._path = Path(path)

    def load(self) -> List[str]:
        if not self._path.exists():
            return []
        proxies: List[str] = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            proxies.append(line)
        return proxies


class EnvProxySource(ProxySource):
    def __init__(self, env_var: str) -> None:
        self._env_var = env_var

    def load(self) -> List[str]:
        raw = os.getenv(self._env_var, "").strip()
        if not raw:
            return []
        parts = [p.strip() for p in raw.split(",")]
        return [p for p in parts if p]


def build_sources(configs: Iterable[ProxySourceConfig]) -> List[tuple[ProxySourceConfig, ProxySource]]:
    built: List[tuple[ProxySourceConfig, ProxySource]] = []
    for cfg in configs:
        if cfg.type == "file":
            if not cfg.path:
                continue
            built.append((cfg, FileProxySource(cfg.path)))
        elif cfg.type == "env":
            if not cfg.env_var:
                continue
            built.append((cfg, EnvProxySource(cfg.env_var)))
        else:
            # Unknown source type: ignore to keep config extensible.
            continue
    return built
