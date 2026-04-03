from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


class MediaType(StrEnum):
    VIDEO = "video"
    AUDIO = "audio"
    EBOOK = "ebook"
    AUDIOBOOK = "audiobook"


class BackupStatus(StrEnum):
    PENDING = "pending"
    VALIDATED = "validated"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CLEANED = "cleaned"
    EXPIRED = "expired"
    KEPT = "kept"


class RetentionPolicy(StrEnum):
    AUTO_CLEANUP = "auto_cleanup"
    KEEP = "keep"
    MANUAL = "manual"


@dataclass
class CheckResult:
    name: str
    passed: bool
    expected: str
    actual: str
    message: str | None = None


@dataclass
class ValidationResult:
    passed: bool
    checks: list[CheckResult] = field(default_factory=list)
    duration_ms: float = 0.0


@dataclass
class BackupEntry:
    id: str
    operation: str
    media_type: MediaType
    timestamp: str = field(default_factory=_iso_now)
    original_path: str = ""
    backup_path: str = ""
    original_hash: str = ""
    backup_size_bytes: int = 0
    status: BackupStatus = BackupStatus.PENDING
    retention_policy: RetentionPolicy = RetentionPolicy.AUTO_CLEANUP
    expires_at: str | None = None
    validation_result: ValidationResult | None = None
    error: str | None = None
    output_path: str | None = None


@dataclass
class BackupIndexSnapshot:
    version: int = 1
    created_at: str = field(default_factory=_iso_now)
    last_updated: str = field(default_factory=_iso_now)
    total_size_bytes: int = 0
    entries: list[BackupEntry] = field(default_factory=list)


@dataclass
class StorageUsage:
    total_size_bytes: int = 0
    by_status: dict[str, int] = field(default_factory=dict)


class BackupError(RuntimeError):
    """Base class for backup-related errors."""


class StorageQuotaError(BackupError):
    """Raised when backup storage quota cannot satisfy requested space."""


class RollbackError(BackupError):
    """Raised when rollback fails."""


class CorruptBackupError(RollbackError):
    """Raised when backup integrity checks fail during restore."""
