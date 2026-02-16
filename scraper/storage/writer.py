from __future__ import annotations

import asyncio
import csv
import json
import logging
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from scraper.config import StorageConfig
from scraper.models import ScrapeResult
from scraper.storage.dedupe import DedupeState


logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_name(value: str) -> str:
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in value)


@dataclass(slots=True)
class StoragePaths:
    jsonl_path: Path
    csv_path: Path
    errors_jsonl_path: Path


class StorageManager:
    def __init__(self, cfg: StorageConfig) -> None:
        self._cfg = cfg
        self._output_dir = Path(cfg.output_dir)
        self._backup_dir = Path(cfg.backup_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._backup_dir.mkdir(parents=True, exist_ok=True)

        self._dedupe = DedupeState.load(cfg.dedupe_state_file)

        self._lock = asyncio.Lock()
        self._since_state_save = 0

    def paths_for_target(self, target: str) -> StoragePaths:
        safe = _safe_name(target)
        jsonl_path = self._output_dir / f"{safe}.jsonl"
        csv_path = self._output_dir / f"{safe}.csv"
        errors_jsonl_path = self._output_dir / f"{safe}_errors.jsonl"
        return StoragePaths(jsonl_path=jsonl_path, csv_path=csv_path, errors_jsonl_path=errors_jsonl_path)

    def backup_if_exists(self, target: str) -> None:
        paths = self.paths_for_target(target)
        if not paths.jsonl_path.exists():
            return
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = self._backup_dir / f"{paths.jsonl_path.stem}.{ts}.jsonl"
        shutil.copy2(paths.jsonl_path, backup_path)
        logger.info("output_backed_up", extra={"target": target, "backup": str(backup_path)})

    async def persist(self, result: ScrapeResult) -> bool:
        # Returns True if written, False if deduped/skipped.
        if not result.success or not result.task.url:
            return False

        if not self._dedupe.is_new_url(result.task.url):
            return False

        paths = self.paths_for_target(result.task.target_name)
        record: Dict[str, Any] = {
            "timestamp": _utc_now_iso(),
            "target": result.task.target_name,
            "url": result.task.url,
            "status_code": result.status_code,
            "latency_seconds": result.latency_seconds,
            "proxy": result.used_proxy,
            "extracted": result.extracted,
        }

        async with self._lock:
            paths.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
            with paths.jsonl_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

            if self._cfg.write_csv:
                self._append_csv(paths.csv_path, record)

            self._since_state_save += 1
            if self._since_state_save >= 100:
                self._dedupe.save()
                self._since_state_save = 0

        return True

    async def persist_error(
        self,
        *,
        target: str,
        url: str,
        method: str,
        attempt: int,
        error_type: str,
        error_message: str,
        retryable: bool,
        status_code: int | None,
        latency_seconds: float,
        proxy: str | None,
        extra: Dict[str, Any] | None = None,
    ) -> None:
        paths = self.paths_for_target(target)
        record: Dict[str, Any] = {
            "timestamp": _utc_now_iso(),
            "target": target,
            "url": url,
            "method": method,
            "attempt": attempt,
            "error_type": error_type,
            "error": error_message,
            "retryable": retryable,
            "status_code": status_code,
            "latency_seconds": latency_seconds,
            "proxy": proxy,
        }
        if extra:
            record["extra"] = extra

        async with self._lock:
            paths.errors_jsonl_path.parent.mkdir(parents=True, exist_ok=True)
            with paths.errors_jsonl_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    async def write_text_artifact(
        self,
        *,
        target: str,
        kind: str,
        content: str,
        suffix: str = ".html",
        max_bytes: int = 1_000_000,
    ) -> str:
        safe_target = _safe_name(target)
        safe_kind = _safe_name(kind)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        token = uuid.uuid4().hex[:8]

        artifact_dir = self._output_dir / "artifacts" / safe_kind
        artifact_dir.mkdir(parents=True, exist_ok=True)
        path = artifact_dir / f"{safe_target}_{ts}_{token}{suffix}"

        data = (content or "").encode("utf-8", errors="replace")[:max_bytes]
        async with self._lock:
            path.write_bytes(data)

        return str(path)

    def _append_csv(self, path: Path, record: Dict[str, Any]) -> None:
        extracted = record.get("extracted", {}) or {}
        row = {
            "timestamp": record.get("timestamp"),
            "target": record.get("target"),
            "url": record.get("url"),
            "status_code": record.get("status_code"),
            "latency_seconds": record.get("latency_seconds"),
            "title": extracted.get("title"),
            "links_count": extracted.get("links_count"),
        }
        write_header = not path.exists()
        with path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(row.keys()))
            if write_header:
                writer.writeheader()
            writer.writerow(row)

    def flush(self) -> None:
        self._dedupe.save()
