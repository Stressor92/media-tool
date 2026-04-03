from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from .backup_index import BackupIndex
from .models import BackupEntry, BackupStatus, RetentionPolicy, StorageQuotaError, StorageUsage

logger = logging.getLogger(__name__)


class StorageGuard:
    def __init__(self, index: BackupIndex, max_size_bytes: int) -> None:
        self._index = index
        self._max_size_bytes = max_size_bytes

    def check_quota(self, required_bytes: int) -> None:
        if required_bytes <= 0:
            return

        self._mark_expired_entries()
        usage = self.current_usage()
        if usage.total_size_bytes + required_bytes <= self._max_size_bytes:
            return

        bytes_needed = (usage.total_size_bytes + required_bytes) - self._max_size_bytes
        freed = self.evict_lru(bytes_needed)
        usage_after = self.current_usage()
        if freed <= 0 or usage_after.total_size_bytes + required_bytes > self._max_size_bytes:
            raise StorageQuotaError(
                f"Backup quota exceeded: required={required_bytes} bytes, used={usage_after.total_size_bytes} bytes, "
                f"limit={self._max_size_bytes} bytes"
            )

    def evict_lru(self, target_free_bytes: int) -> int:
        if target_free_bytes <= 0:
            return 0

        snapshot = self._index.load()
        candidates: list[BackupEntry] = []

        # Priority groups: EXPIRED -> AUTO_CLEANUP validated -> KEEP validated
        status_group = [
            (BackupStatus.EXPIRED, None),
            (BackupStatus.VALIDATED, RetentionPolicy.AUTO_CLEANUP),
            (BackupStatus.KEPT, RetentionPolicy.KEEP),
            (BackupStatus.VALIDATED, RetentionPolicy.KEEP),
        ]

        for status, policy in status_group:
            group = [
                e
                for e in snapshot.entries
                if e.status == status
                and (policy is None or e.retention_policy == policy)
                and Path(e.backup_path).exists()
            ]
            group.sort(key=lambda x: x.timestamp)
            candidates.extend(group)

        freed = 0
        changed = False
        for entry in candidates:
            if freed >= target_free_bytes:
                break
            try:
                backup_path = Path(entry.backup_path)
                size = backup_path.stat().st_size if backup_path.exists() else entry.backup_size_bytes
                backup_path.unlink(missing_ok=True)
                entry.status = BackupStatus.EXPIRED
                entry.error = None
                freed += int(size)
                changed = True
            except Exception:
                logger.warning("Failed to evict backup %s", entry.id, exc_info=True)

        if changed:
            self._index.save(snapshot)
        return freed

    def current_usage(self) -> StorageUsage:
        snapshot = self._index.load()
        usage = StorageUsage(total_size_bytes=0, by_status={})

        for entry in snapshot.entries:
            key = entry.status.value
            usage.by_status[key] = usage.by_status.get(key, 0) + 1
            if entry.status in {BackupStatus.CLEANED, BackupStatus.EXPIRED}:
                continue
            backup_path = Path(entry.backup_path)
            if backup_path.exists():
                usage.total_size_bytes += backup_path.stat().st_size
            else:
                usage.total_size_bytes += max(0, entry.backup_size_bytes)

        return usage

    def _mark_expired_entries(self) -> None:
        snapshot = self._index.load()
        now = datetime.now(UTC)
        changed = False
        for entry in snapshot.entries:
            if entry.expires_at is None:
                continue
            if entry.status not in {BackupStatus.VALIDATED, BackupStatus.KEPT}:
                continue
            try:
                if datetime.fromisoformat(entry.expires_at) <= now:
                    entry.status = BackupStatus.EXPIRED
                    changed = True
            except ValueError:
                continue

        if changed:
            self._index.save(snapshot)
