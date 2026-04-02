"""Comprehensive metadata extraction for music library scanning."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from utils.audio_analyzer import AudioTechnicalMetadata, extract_audio_technical_metadata
from utils.ffprobe_runner import ProbeResult, probe_file

logger = logging.getLogger(__name__)

ProbeFileFunc = Callable[[Path], ProbeResult]


@dataclass
class AudioFileMetadata:
    """Complete metadata for a single audio file."""

    file_path: Path
    file_name: str
    file_size_mb: float
    directory: str
    extension: str
    duration_seconds: float
    artist: str | None = None
    album: str | None = None
    title: str | None = None
    album_artist: str | None = None
    track_number: str | None = None
    total_tracks: int | None = None
    disc_number: int | None = None
    year: int | None = None
    genre: str | None = None
    comment: str | None = None
    codec: str | None = None
    bitrate_kbps: int | None = None
    sample_rate_hz: int | None = None
    channels: int | None = None
    bit_depth: int | None = None
    is_lossless: bool = False
    is_tagged: bool = False
    has_cover_art: bool = False
    date_modified: datetime = field(default_factory=lambda: datetime.now(UTC))
    date_scanned: datetime = field(default_factory=lambda: datetime.now(UTC))
    error_message: str | None = None


class MetadataExtractor:
    """Extract file, tag, and technical metadata for a single audio file."""

    LOSSLESS_EXTENSIONS = {".flac", ".alac", ".ape", ".wav", ".aiff", ".aif", ".dsd", ".wv"}
    LOSSLESS_CODECS = {"flac", "alac", "ape", "pcm_s16le", "pcm_s24le", "pcm_s32le", "wavpack"}

    def __init__(self, ffprobe_runner: ProbeFileFunc | None = None):
        self._probe_file = ffprobe_runner or probe_file

    def extract(self, file_path: Path) -> AudioFileMetadata:
        """Extract all available metadata from an audio file."""
        resolved_path = file_path.resolve()
        scanned_at = datetime.now(UTC)

        try:
            stat = resolved_path.stat()
            file_size_mb = round(stat.st_size / (1024 * 1024), 2)
            date_modified = datetime.fromtimestamp(stat.st_mtime, tz=UTC)

            tag_data = self._extract_tags(resolved_path)
            technical = self._extract_technical_specs(resolved_path)
            is_tagged = any(tag_data.get(field) for field in ("artist", "album", "title"))
            is_lossless = self._is_lossless_format(resolved_path.suffix.lower(), technical.codec)

            return AudioFileMetadata(
                file_path=resolved_path,
                file_name=resolved_path.name,
                file_size_mb=file_size_mb,
                directory=str(resolved_path.parent),
                extension=resolved_path.suffix.lower().lstrip("."),
                duration_seconds=round(technical.duration_seconds, 2),
                artist=tag_data.get("artist"),
                album=tag_data.get("album"),
                title=tag_data.get("title"),
                album_artist=tag_data.get("album_artist"),
                track_number=tag_data.get("track_number"),
                total_tracks=tag_data.get("total_tracks"),
                disc_number=tag_data.get("disc_number"),
                year=tag_data.get("year"),
                genre=tag_data.get("genre"),
                comment=tag_data.get("comment"),
                codec=technical.codec,
                bitrate_kbps=technical.bitrate_kbps,
                sample_rate_hz=technical.sample_rate_hz,
                channels=technical.channels,
                bit_depth=technical.bit_depth,
                is_lossless=is_lossless,
                is_tagged=is_tagged,
                has_cover_art=bool(tag_data.get("has_cover_art", False)),
                date_modified=date_modified,
                date_scanned=scanned_at,
            )
        except Exception as exc:
            logger.error("Error extracting metadata from %s: %s", resolved_path, exc)
            return self._error_metadata(resolved_path, scanned_at, str(exc))

    def _extract_tags(self, file_path: Path) -> dict[str, Any]:
        try:
            from importlib import import_module

            mutagen_module = import_module("mutagen")
            mutagen_file = mutagen_module.File
            if not callable(mutagen_file):
                return {}
            audio_easy = mutagen_file(file_path, easy=True)
            audio_raw = mutagen_file(file_path)
        except Exception as exc:
            logger.debug("Tag extraction failed for %s: %s", file_path, exc)
            return {}

        if audio_easy is None and audio_raw is None:
            return {}

        track_number_value = self._get_tag(audio_easy, audio_raw, ["tracknumber"], ["TRCK", "trkn", "TRACKNUMBER"])
        disc_number_value = self._get_tag(audio_easy, audio_raw, ["discnumber"], ["TPOS", "disk", "DISCNUMBER"])

        track_number, total_tracks = self._parse_fraction_tag(track_number_value)
        disc_number, _ = self._parse_fraction_tag(disc_number_value)
        date_value = self._get_tag(audio_easy, audio_raw, ["date", "year"], ["TDRC", "TDOR", "\xa9day", "DATE", "YEAR"])

        try:
            has_cover_art = self._has_cover_art(audio_raw)
        except Exception as exc:
            logger.debug("Cover art detection failed for %s: %s", file_path, exc)
            has_cover_art = False

        return {
            "artist": self._get_tag(audio_easy, audio_raw, ["artist"], ["TPE1", "\xa9ART", "ARTIST"]),
            "album": self._get_tag(audio_easy, audio_raw, ["album"], ["TALB", "\xa9alb", "ALBUM"]),
            "title": self._get_tag(audio_easy, audio_raw, ["title"], ["TIT2", "\xa9nam", "TITLE"]),
            "album_artist": self._get_tag(audio_easy, audio_raw, ["albumartist"], ["TPE2", "aART", "ALBUMARTIST"]),
            "track_number": track_number,
            "total_tracks": total_tracks,
            "disc_number": self._safe_int(disc_number),
            "year": self._parse_year(date_value),
            "genre": self._get_tag(audio_easy, audio_raw, ["genre"], ["TCON", "\xa9gen", "GENRE"]),
            "comment": self._get_tag(
                audio_easy, audio_raw, ["comment", "description"], ["COMM", "\xa9cmt", "COMMENT", "DESCRIPTION"]
            ),
            "has_cover_art": has_cover_art,
        }

    def _extract_technical_specs(self, file_path: Path) -> AudioTechnicalMetadata:
        technical = extract_audio_technical_metadata(file_path, probe_func=self._probe_file)
        if technical is None:
            raise RuntimeError("Unable to extract technical audio metadata")
        return technical

    def _get_tag(
        self,
        audio_easy: Any,
        audio_raw: Any,
        easy_keys: list[str],
        raw_keys: list[str],
    ) -> str | None:
        easy_mapping = self._resolve_tag_mapping(audio_easy)
        for key in easy_keys:
            value = self._extract_mapping_value(easy_mapping, key)
            normalized = self._normalize_tag_value(value)
            if normalized:
                return normalized

        raw_tags = self._resolve_tag_mapping(audio_raw)
        for key in raw_keys:
            value = self._extract_mapping_value(raw_tags, key)
            normalized = self._normalize_tag_value(value)
            if normalized:
                return normalized

        return None

    def _extract_mapping_value(self, mapping: Any, key: str) -> Any:
        if mapping is None:
            return None
        getter = getattr(mapping, "get", None)
        if callable(getter):
            try:
                return getter(key)
            except (KeyError, ValueError, TypeError):
                return None
        return None

    def _resolve_tag_mapping(self, audio_object: Any) -> Any:
        if audio_object is None:
            return None
        if callable(getattr(audio_object, "get", None)):
            return audio_object
        tags = getattr(audio_object, "tags", None)
        if callable(getattr(tags, "get", None)):
            return tags
        return None

    def _normalize_tag_value(self, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, list | tuple):
            if not value:
                return None
            first = value[0]
            if isinstance(first, tuple):
                return "/".join(str(item) for item in first if item not in (None, 0)) or None
            return self._normalize_tag_value(first)
        if hasattr(value, "text"):
            text_value = value.text
            return self._normalize_tag_value(text_value)
        text = str(value).strip()
        return text or None

    def _parse_fraction_tag(self, value: Any) -> tuple[str | None, int | None]:
        normalized = self._normalize_tag_value(value)
        if not normalized:
            return None, None
        if "/" in normalized:
            primary, secondary = normalized.split("/", 1)
            return primary.strip() or None, self._safe_int(secondary.strip())
        return normalized, None

    def _parse_year(self, value: str | None) -> int | None:
        if not value:
            return None
        return self._safe_int(value[:4])

    def _has_cover_art(self, audio_raw: Any) -> bool:
        if audio_raw is None:
            return False

        pictures = getattr(audio_raw, "pictures", None)
        if pictures:
            return len(pictures) > 0

        tags = getattr(audio_raw, "tags", None)
        if tags is None:
            return False

        keys = []
        if hasattr(tags, "keys"):
            try:
                keys = list(tags.keys())
            except Exception:
                keys = []

        if any(str(key).startswith("APIC") for key in keys):
            return True
        if "covr" in keys:
            cover = tags.get("covr") if hasattr(tags, "get") else None
            return bool(cover)
        if "METADATA_BLOCK_PICTURE" in keys:
            return True

        return False

    def _error_metadata(self, file_path: Path, scanned_at: datetime, error_message: str) -> AudioFileMetadata:
        try:
            stat = file_path.stat()
            file_size_mb = round(stat.st_size / (1024 * 1024), 2)
            date_modified = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
        except OSError:
            file_size_mb = 0.0
            date_modified = scanned_at

        return AudioFileMetadata(
            file_path=file_path,
            file_name=file_path.name,
            file_size_mb=file_size_mb,
            directory=str(file_path.parent),
            extension=file_path.suffix.lower().lstrip("."),
            duration_seconds=0.0,
            date_modified=date_modified,
            date_scanned=scanned_at,
            error_message=error_message,
        )

    def _safe_int(self, value: str | None) -> int | None:
        if not value:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    @classmethod
    def _is_lossless_format(cls, extension: str, codec: str | None) -> bool:
        return extension in cls.LOSSLESS_EXTENSIONS or (codec or "").lower() in cls.LOSSLESS_CODECS
