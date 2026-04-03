from __future__ import annotations

import hashlib
import logging
import shutil
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from src.statistics import get_collector
from src.statistics.event_types import EventType

from utils.config import get_config

from .backup_index import BackupIndex
from .models import (
    BackupEntry,
    BackupError,
    BackupStatus,
    MediaType,
    RetentionPolicy,
    ValidationResult,
)
from .rollback_engine import RollbackEngine
from .storage_guard import StorageGuard
from .validators.audio_validator import AudioValidator
from .validators.audiobook_validator import AudiobookValidator
from .validators.base_validator import AbstractValidator
from .validators.ebook_validator import EbookValidator
from .validators.video_validator import VideoValidator

logger = logging.getLogger(__name__)


class BackupManager:
    def __init__(self, backup_dir: Path | None = None) -> None:
        config = get_config()
        cfg = getattr(config, "backup", None)

        configured_dir = Path.home() / ".media-tool" / "backups"
        if cfg is not None and isinstance(cfg.backup_dir, str) and cfg.backup_dir.strip():
            configured_dir = Path(cfg.backup_dir).expanduser()

        self._backup_dir = backup_dir or configured_dir
        self._backup_dir.mkdir(parents=True, exist_ok=True)

        max_size_gb = float(getattr(cfg, "max_size_gb", 50.0) if cfg is not None else 50.0)
        self._max_size_bytes = int(max_size_gb * 1024 * 1024 * 1024)

        self._index = BackupIndex(self._backup_dir)
        self._storage_guard = StorageGuard(self._index, self._max_size_bytes)
        self._rollback_engine = RollbackEngine()

        self._after_days = int(getattr(getattr(cfg, "auto_cleanup", None), "after_days", 0) if cfg is not None else 0)

        validation_cfg = getattr(cfg, "validation", None) if cfg is not None else None
        self._validators: dict[MediaType, AbstractValidator] = {
            MediaType.VIDEO: VideoValidator(
                duration_tolerance=float(getattr(validation_cfg, "video_duration_tolerance", 0.05)),
                require_audio_tracks=bool(getattr(validation_cfg, "require_audio_tracks", True)),
            ),
            MediaType.AUDIO: AudioValidator(
                duration_tolerance=float(getattr(validation_cfg, "audio_duration_tolerance", 0.03)),
                min_audio_bitrate_kbps=int(getattr(validation_cfg, "min_audio_bitrate_kbps", 0)),
            ),
            MediaType.EBOOK: EbookValidator(
                require_epub_metadata=bool(getattr(validation_cfg, "require_epub_metadata", True)),
                require_cover=bool(getattr(validation_cfg, "require_cover", True)),
                require_isbn_if_present=bool(getattr(validation_cfg, "require_isbn_if_present", False)),
            ),
            MediaType.AUDIOBOOK: AudiobookValidator(
                duration_tolerance=float(getattr(validation_cfg, "audiobook_duration_tolerance", 0.05)),
                require_chapters=bool(getattr(validation_cfg, "require_chapters", True)),
            ),
        }

    @property
    def index(self) -> BackupIndex:
        return self._index

    @property
    def backup_dir(self) -> Path:
        return self._backup_dir

    def create(self, original_path: Path, operation: str, media_type: MediaType) -> BackupEntry:
        if not original_path.exists() or not original_path.is_file():
            raise BackupError(f"Original path is not a file: {original_path}")

        required = original_path.stat().st_size
        self._storage_guard.check_quota(required)

        entry_id = str(uuid.uuid4())
        backup_path = self._backup_dir / f"{entry_id}{original_path.suffix}"
        original_hash = self._sha256(original_path)

        shutil.copy2(original_path, backup_path)
        backup_size = backup_path.stat().st_size

        expires_at: str | None = None
        retention = RetentionPolicy.AUTO_CLEANUP
        if self._after_days < 0:
            retention = RetentionPolicy.KEEP
        elif self._after_days > 0:
            expires_at = (datetime.now(UTC) + timedelta(days=self._after_days)).isoformat()

        entry = BackupEntry(
            id=entry_id,
            operation=operation,
            media_type=media_type,
            timestamp=datetime.now(UTC).isoformat(),
            original_path=str(original_path.resolve()),
            backup_path=str(backup_path.resolve()),
            original_hash=original_hash,
            backup_size_bytes=backup_size,
            status=BackupStatus.PENDING,
            retention_policy=retention,
            expires_at=expires_at,
        )
        self._index.upsert_entry(entry)
        self._record_stats_event("backup_created", backup_id=entry.id, media_type=entry.media_type.value)
        return entry

    def validate(self, entry: BackupEntry, output_path: Path) -> ValidationResult:
        validator = self._validators[entry.media_type]
        result = validator.validate(Path(entry.original_path), output_path)
        entry.validation_result = result
        entry.output_path = str(output_path.resolve())
        entry.status = BackupStatus.VALIDATED if result.passed else BackupStatus.FAILED
        entry.error = None if result.passed else "Validation failed"

        if result.passed and self._after_days == 0 and entry.retention_policy == RetentionPolicy.AUTO_CLEANUP:
            entry.expires_at = datetime.now(UTC).isoformat()

        self._index.upsert_entry(entry)
        return result

    def cleanup(self, entry: BackupEntry) -> None:
        if entry.status != BackupStatus.VALIDATED:
            return
        if entry.retention_policy != RetentionPolicy.AUTO_CLEANUP:
            return

        should_cleanup = self._after_days == 0
        if self._after_days > 0 and entry.expires_at is not None:
            try:
                should_cleanup = datetime.fromisoformat(entry.expires_at) <= datetime.now(UTC)
            except ValueError:
                should_cleanup = False

        if not should_cleanup:
            return

        try:
            Path(entry.backup_path).unlink(missing_ok=True)
            entry.status = BackupStatus.CLEANED
            self._index.upsert_entry(entry)
            self._record_stats_event("backup_cleaned", backup_id=entry.id, media_type=entry.media_type.value)
        except Exception:
            logger.warning("Backup cleanup failed for %s", entry.id, exc_info=True)

    def rollback(self, entry: BackupEntry) -> None:
        self._rollback_engine.restore(entry)
        entry.status = BackupStatus.ROLLED_BACK
        self._index.upsert_entry(entry)
        self._record_stats_event("backup_rolled_back", backup_id=entry.id, media_type=entry.media_type.value)

    def list_pending(self) -> list[BackupEntry]:
        snapshot = self._index.load()
        return [
            entry
            for entry in snapshot.entries
            if entry.status in {BackupStatus.PENDING, BackupStatus.VALIDATED, BackupStatus.FAILED}
        ]

    def purge_expired(self) -> int:
        snapshot = self._index.load()
        now = datetime.now(UTC)
        deleted = 0
        changed = False

        for entry in snapshot.entries:
            is_expired = entry.status == BackupStatus.EXPIRED
            if not is_expired and entry.expires_at:
                try:
                    is_expired = datetime.fromisoformat(entry.expires_at) <= now
                except ValueError:
                    is_expired = False

            if not is_expired:
                continue

            backup_path = Path(entry.backup_path)
            if backup_path.exists():
                backup_path.unlink(missing_ok=True)
            entry.status = BackupStatus.EXPIRED
            deleted += 1
            changed = True

        if changed:
            self._index.save(snapshot)
        return deleted

    def purge(self, status: BackupStatus | None = None) -> int:
        snapshot = self._index.load()
        deleted = 0
        changed = False
        for entry in snapshot.entries:
            if status is not None and entry.status != status:
                continue
            backup_path = Path(entry.backup_path)
            if backup_path.exists():
                backup_path.unlink(missing_ok=True)
            entry.status = BackupStatus.CLEANED
            deleted += 1
            changed = True

        if changed:
            self._index.save(snapshot)
        return deleted

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        return f"sha256:{digest.hexdigest()}"

    @staticmethod
    def _record_stats_event(event_name: str, **metadata: str) -> None:
        try:
            event_map = {
                "backup_created": EventType.BACKUP_CREATED,
                "backup_cleaned": EventType.BACKUP_CLEANED,
                "backup_rolled_back": EventType.BACKUP_ROLLED_BACK,
            }
            get_collector().record(event_map[event_name], duration_seconds=0.0, **metadata)
        except Exception:
            logger.debug("Backup stats event recording failed", exc_info=True)
