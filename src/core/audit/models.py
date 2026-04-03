# src/core/audit/models.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, StrEnum
from pathlib import Path
from typing import Any


class CheckSeverity(Enum):
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    INFO = 5


class FindingKind(StrEnum):
    # Subtitel
    MISSING_DE_SUBTITLE = "missing_de_subtitle"
    MISSING_EN_SUBTITLE = "missing_en_subtitle"
    NO_SUBTITLES = "no_subtitles"
    # Audio
    UNLABELED_AUDIO = "unlabeled_audio"
    MISSING_DE_AUDIO = "missing_de_audio"
    # Serien
    EPISODE_GAP = "episode_gap"
    BAD_EPISODE_NAMING = "bad_episode_naming"
    # Dateiqualität
    BROKEN_FILE = "broken_file"
    WRONG_CONTAINER = "wrong_container"
    INEFFICIENT_CODEC = "inefficient_codec"
    SUSPICIOUS_SIZE = "suspicious_size"
    LOW_BITRATE = "low_bitrate"
    NONSTANDARD_RESOLUTION = "nonstandard_resolution"
    # Benennung
    BAD_MOVIE_NAMING = "bad_movie_naming"
    DUPLICATE_MOVIE = "duplicate_movie"
    FILE_IN_ROOT = "file_in_root"
    EMPTY_FOLDER = "empty_folder"
    SPECIAL_CHARS = "special_chars"
    NAME_TOO_LONG = "name_too_long"


@dataclass
class AuditFinding:
    """Einzelner Fund eines Checks."""

    kind: FindingKind
    severity: CheckSeverity
    path: Path
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    suggested_command: str | None = None


@dataclass
class CheckResult:
    check_id: str
    findings: list[AuditFinding]
    files_checked: int
    duration_seconds: float = 0.0
    error: str | None = None

    @property
    def passed(self) -> bool:
        return len(self.findings) == 0


@dataclass
class AuditReport:
    """Vollständiger Bericht eines Audit-Laufs."""

    root_dir: Path
    total_files: int
    check_results: list[CheckResult] = field(default_factory=list)
    duration_seconds: float = 0.0

    @property
    def all_findings(self) -> list[AuditFinding]:
        return [f for r in self.check_results for f in r.findings]

    @property
    def by_severity(self) -> dict[CheckSeverity, list[AuditFinding]]:
        result: dict[CheckSeverity, list[AuditFinding]] = {}
        for f in self.all_findings:
            result.setdefault(f.severity, []).append(f)
        return result

    @property
    def by_kind(self) -> dict[FindingKind, list[AuditFinding]]:
        result: dict[FindingKind, list[AuditFinding]] = {}
        for f in self.all_findings:
            result.setdefault(f.kind, []).append(f)
        return result

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.all_findings if f.severity == CheckSeverity.CRITICAL)

    @property
    def high_count(self) -> int:
        return sum(1 for f in self.all_findings if f.severity == CheckSeverity.HIGH)
