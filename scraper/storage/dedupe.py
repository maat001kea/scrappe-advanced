from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Set


@dataclass(slots=True)
class DedupeState:
    state_file: Path
    seen: Set[str]

    @classmethod
    def load(cls, path: str) -> "DedupeState":
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists():
            return cls(state_file=p, seen=set())
        raw = json.loads(p.read_text(encoding="utf-8") or "{}")
        seen = set(raw.get("seen", []))
        return cls(state_file=p, seen=seen)

    def key_for_url(self, url: str) -> str:
        return hashlib.sha256(url.encode("utf-8")).hexdigest()

    def is_new_url(self, url: str) -> bool:
        key = self.key_for_url(url)
        if key in self.seen:
            return False
        self.seen.add(key)
        return True

    def save(self) -> None:
        tmp = self.state_file.with_suffix(self.state_file.suffix + ".tmp")
        tmp.write_text(json.dumps({"seen": sorted(self.seen)}), encoding="utf-8")
        tmp.replace(self.state_file)
