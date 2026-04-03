from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import (
    BackupEntry,
    BackupIndexSnapshot,
    BackupStatus,
    CheckResult,
    MediaType,
    RetentionPolicy,
    ValidationResult,
)

logger = logging.getLogger(__name__)


class BackupIndex:
    def __init__(self, backup_dir: Path) -> None:
        self._backup_dir = backup_dir
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        self._path = self._backup_dir / "backup_index.json"

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> BackupIndexSnapshot:
        if not self._path.exists():
            return BackupIndexSnapshot()

        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                return BackupIndexSnapshot()
            snapshot = BackupIndexSnapshot(
                version=int(payload.get("version", 1)),
                created_at=str(payload.get("created_at") or datetime.now(UTC).isoformat()),
                last_updated=str(payload.get("last_updated") or datetime.now(UTC).isoformat()),
                total_size_bytes=int(payload.get("total_size_bytes", 0)),
                entries=[],
            )
            for raw_entry in payload.get("entries", []):
                entry = self._parse_entry(raw_entry)
                if entry is not None:
                    snapshot.entries.append(entry)
            snapshot.total_size_bytes = sum(
                e.backup_size_bytes
                for e in snapshot.entries
                if e.status not in {BackupStatus.CLEANED, BackupStatus.EXPIRED}
            )
            return snapshot
        except Exception:
            logger.warning("Failed to load backup index", exc_info=True)
            return BackupIndexSnapshot()

    def save(self, snapshot: BackupIndexSnapshot) -> None:
        snapshot.last_updated = datetime.now(UTC).isoformat()
        snapshot.total_size_bytes = sum(
            entry.backup_size_bytes
            for entry in snapshot.entries
            if entry.status not in {BackupStatus.CLEANED, BackupStatus.EXPIRED}
        )

        tmp_path = self._path.with_suffix(".json.tmp")
        try:
            tmp_path.write_text(json.dumps(asdict(snapshot), indent=2, sort_keys=True), encoding="utf-8")
            tmp_path.replace(self._path)
        except Exception:
            logger.warning("Failed to save backup index", exc_info=True)
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                logger.debug("Could not remove backup index tmp file", exc_info=True)

    def upsert_entry(self, entry: BackupEntry) -> BackupEntry:
        snapshot = self.load()
        for i, existing in enumerate(snapshot.entries):
            if existing.id == entry.id:
                snapshot.entries[i] = entry
                self.save(snapshot)
                return entry
        snapshot.entries.append(entry)
        self.save(snapshot)
        return entry

    def get_entry(self, entry_id: str) -> BackupEntry | None:
        snapshot = self.load()
        for entry in snapshot.entries:
            if entry.id == entry_id:
                return entry
        return None

    @staticmethod
    def _parse_entry(raw_entry: Any) -> BackupEntry | None:
        if not isinstance(raw_entry, dict):
            return None
        try:
            validation_raw = raw_entry.get("validation_result")
            validation: ValidationResult | None = None
            if isinstance(validation_raw, dict):
                checks = []
                for raw_check in validation_raw.get("checks", []):
                    if isinstance(raw_check, dict):
                        checks.append(
                            CheckResult(
                                name=str(raw_check.get("name", "unknown")),
                                passed=bool(raw_check.get("passed", False)),
                                expected=str(raw_check.get("expected", "")),
                                actual=str(raw_check.get("actual", "")),
                                message=(str(raw_check["message"]) if raw_check.get("message") else None),
                            )
                        )
                validation = ValidationResult(
                    passed=bool(validation_raw.get("passed", False)),
                    checks=checks,
                    duration_ms=float(validation_raw.get("duration_ms", 0.0)),
                )

            return BackupEntry(
                id=str(raw_entry.get("id", "")),
                operation=str(raw_entry.get("operation", "")),
                media_type=MediaType(str(raw_entry.get("media_type", MediaType.VIDEO.value))),
                timestamp=str(raw_entry.get("timestamp", datetime.now(UTC).isoformat())),
                original_path=str(raw_entry.get("original_path", "")),
                backup_path=str(raw_entry.get("backup_path", "")),
                original_hash=str(raw_entry.get("original_hash", "")),
                backup_size_bytes=int(raw_entry.get("backup_size_bytes", 0)),
                status=BackupStatus(str(raw_entry.get("status", BackupStatus.PENDING.value))),
                retention_policy=RetentionPolicy(
                    str(raw_entry.get("retention_policy", RetentionPolicy.AUTO_CLEANUP.value))
                ),
                expires_at=(str(raw_entry["expires_at"]) if raw_entry.get("expires_at") else None),
                validation_result=validation,
                error=(str(raw_entry["error"]) if raw_entry.get("error") else None),
                output_path=(str(raw_entry["output_path"]) if raw_entry.get("output_path") else None),
            )
        except Exception:
            logger.debug("Skipping invalid backup index entry", exc_info=True)
            return None
