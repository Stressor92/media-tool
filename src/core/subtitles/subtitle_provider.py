"""
src/core/subtitles/subtitle_provider.py

Abstract base classes for subtitle providers.
Provides standardized interfaces for different subtitle sources.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SubtitleMatch:
    """Standardized representation of a subtitle match from any provider"""

    id: str  # Provider-specific identifier
    language: str  # ISO 639-1 code (en, de, fr, etc.)
    movie_name: str  # Detected movie name
    release_name: str  # Release string (BluRay.1080p.x264, etc.)
    download_url: str  # URL or ID for download
    rating: float  # Quality rating 0.0-10.0
    download_count: int  # Popularity indicator
    uploader: str  # Source/uploader name
    hearing_impaired: bool  # SDH/CC flag
    format: str  # "srt", "ass", "sub"
    provider: str  # "opensubtitles", "whisper", etc.


@dataclass
class MovieInfo:
    """Movie identification data for subtitle matching"""

    file_path: Path
    file_hash: str  # OpenSubtitles-compatible hash
    file_size: int
    duration: float  # in seconds
    # Optional metadata for better matching:
    imdb_id: str | None = None
    tmdb_id: int | None = None
    title: str | None = None
    year: int | None = None


@dataclass
class DownloadResult:
    """Result of a subtitle download operation"""

    success: bool
    message: str
    subtitle_path: Path | None = None
    subtitle_info: SubtitleMatch | None = None
    fallback_suggestion: str | None = None  # "whisper", "manual", etc.


class SubtitleProvider(ABC):
    """Abstract interface for subtitle sources"""

    @abstractmethod
    def search(self, movie_info: MovieInfo, languages: list[str], limit: int = 10) -> list[SubtitleMatch]:
        """Search for subtitle matches"""
        pass

    @abstractmethod
    def download(self, match: SubtitleMatch, output_path: Path) -> Path:
        """Download subtitle file to output_path"""
        pass

    @abstractmethod
    def get_best_match(self, matches: list[SubtitleMatch], release_hint: str | None = None) -> SubtitleMatch | None:
        """Select best match based on rating/downloads/release"""
        pass
