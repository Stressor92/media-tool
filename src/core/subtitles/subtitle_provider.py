"""
src/core/subtitles/subtitle_provider.py

Abstract base classes for subtitle providers.
Provides standardized interfaces for different subtitle sources.
"""

from __future__ import annotations

import re
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
    file_name: str = ""  # Provider-reported subtitle filename when available
    duration: float | None = None  # Provider-reported runtime in seconds when available
    fps: float | None = None  # Provider-reported FPS hint when available


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


_YEAR_RE = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")
_SEARCH_NOISE_RE = re.compile(
    r"\b(?:"
    r"subtitled?|dvd|bd|br|bluray|blu-ray|brrip|dvdrip|webrip|web-dl|hdtv|"
    r"director'?s?\s*cut|extended(?:\s*cut)?|final\s*cut|remastered|unrated|uncut|"
    r"special\s*edition|collector'?s?\s*edition|criterion|imax|proper|repack|"
    r"german|english|multi|dubbed|1080p|720p|2160p|4k|uhd|hdr|x264|x265|hevc|"
    r"h\.?264|h\.?265|aac|ac3|dts|truehd|atmos"
    r")\b",
    re.IGNORECASE,
)


def normalize_title_for_subtitle_search(raw: str, *, truncate_after_year: bool = True) -> str:
    """Clean noisy file/folder names for subtitle-provider title queries."""
    cleaned = Path(raw).stem

    if truncate_after_year:
        year_matches = list(_YEAR_RE.finditer(cleaned))
        if year_matches:
            cleaned = cleaned[: year_matches[-1].start()]

    cleaned = re.sub(r"\[[^\]]*\]|\([^\)]*\)", " ", cleaned)
    cleaned = cleaned.replace("_subtitled", " ").replace("-subtitled", " ")
    cleaned = _SEARCH_NOISE_RE.sub(" ", cleaned)
    cleaned = re.sub(r"[._-]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" -_[]()")


def extract_title_year_from_filename(filename: str) -> tuple[str | None, int | None]:
    """Extract a clean movie title and year from a noisy media filename."""
    stem = Path(filename).stem
    year_matches = list(_YEAR_RE.finditer(stem))
    year = int(year_matches[-1].group(1)) if year_matches else None
    title = normalize_title_for_subtitle_search(stem, truncate_after_year=True)
    return (title or None), year


def extract_release_tokens(raw: str) -> set[str]:
    """Return normalized tokens for release matching (title/year/1080p/BluRay/etc.)."""
    stem = Path(raw).stem.lower()
    tokens = re.findall(r"[a-z0-9]+", stem)
    stopwords = {"the", "a", "an", "and", "of", "der", "die", "das"}
    return {token for token in tokens if len(token) >= 2 and token not in stopwords}


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
    def get_best_match(
        self,
        matches: list[SubtitleMatch],
        release_hint: str | None = None,
        movie_info: MovieInfo | None = None,
    ) -> SubtitleMatch | None:
        """Select best match based on release similarity, runtime fit, rating, and downloads."""
        pass
