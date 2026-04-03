from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


def _iso_date_today() -> str:
    return datetime.now(UTC).date().isoformat()


@dataclass
class VideoStats:
    converted: int = 0
    upscaled: int = 0
    merged: int = 0
    total_processing_time_seconds: float = 0.0
    input_resolutions: dict[str, int] = field(default_factory=dict)
    output_resolutions: dict[str, int] = field(default_factory=dict)


@dataclass
class AudioStats:
    converted: int = 0
    normalized: int = 0
    tagged: int = 0
    total_processing_time_seconds: float = 0.0


@dataclass
class SubtitleStats:
    downloaded: int = 0
    generated: int = 0
    translated: int = 0
    by_language: dict[str, int] = field(default_factory=dict)
    total_processing_time_seconds: float = 0.0


@dataclass
class EbookStats:
    processed: int = 0
    converted: int = 0
    metadata_enriched: int = 0
    covers_added: int = 0
    deduplicated: int = 0


@dataclass
class SystemStats:
    runs: int = 0
    errors: int = 0
    total_runtime_seconds: float = 0.0


@dataclass
class TotalsStats:
    files_processed: int = 0
    total_runtime_seconds: float = 0.0


@dataclass
class DailyEntry:
    files_processed: int = 0
    runtime_seconds: float = 0.0
    errors: int = 0


@dataclass
class StatsSnapshot:
    version: int = 1
    created_at: str = field(default_factory=_iso_date_today)
    last_updated: str = field(default_factory=_iso_date_today)
    totals: TotalsStats = field(default_factory=TotalsStats)
    video: VideoStats = field(default_factory=VideoStats)
    audio: AudioStats = field(default_factory=AudioStats)
    subtitles: SubtitleStats = field(default_factory=SubtitleStats)
    ebooks: EbookStats = field(default_factory=EbookStats)
    system: SystemStats = field(default_factory=SystemStats)
    history: dict[str, DailyEntry] = field(default_factory=dict)
