from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class MediaType(str, Enum):
    """Type of media to download."""

    VIDEO = "video"
    MUSIC = "music"
    SERIES = "series"


class DownloadStatus(str, Enum):
    """Status of a download operation."""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class DownloadRequest:
    """Description of a single download request."""

    url: str
    media_type: MediaType
    output_dir: Path
    preferred_language: str = "de"
    subtitle_languages: tuple[str, ...] = ("de", "en")
    embed_subtitles: bool = True
    embed_thumbnail: bool = True
    max_resolution: int = 1080
    audio_format: str = "mp3"
    audio_quality: str = "320k"
    overwrite: bool = False
    dry_run: bool = False
    cookies_from_browser: str | None = None
    cookies_file: Path | None = None
    sponsorblock_remove: tuple[str, ...] = ("sponsor",)
    extra_yt_dlp_opts: dict[str, object] = field(default_factory=dict)


@dataclass
class TrackInfo:
    """Metadata for a single track or video."""

    title: str
    uploader: str
    duration: float | None
    url: str
    playlist_index: int | None = None
    series: str | None = None
    season_number: int | None = None
    episode_number: int | None = None
    thumbnail_url: str | None = None
    formats: list[str] = field(default_factory=list)


@dataclass
class DownloadResult:
    """Result of a completed download."""

    status: DownloadStatus
    request: DownloadRequest
    output_path: Path | None = None
    track_info: TrackInfo | None = None
    error_message: str | None = None
    skipped_reason: str | None = None
