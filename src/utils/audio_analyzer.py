"""
src/utils/audio_analyzer.py

Audio file analysis utilities using ffprobe.
Extracts comprehensive metadata for music and audiobook files.

Rules:
- No business logic here
- No CLI/UI concerns
- Always validate return codes
- Always capture stderr
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .ffprobe_runner import ProbeResult, probe_file

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AudioTechnicalMetadata:
    """Technical audio metadata derived from ffprobe."""

    duration_seconds: float = 0.0
    codec: str | None = None
    bitrate_kbps: int | None = None
    sample_rate_hz: int | None = None
    channels: int | None = None
    bit_depth: int | None = None


ProbeFileFunc = Callable[[Path], ProbeResult]


@dataclass(frozen=True)
class AudioMetadata:
    """Comprehensive audio file metadata."""

    # Basic file info
    filepath: Path
    filename: str
    file_size_bytes: int
    duration_seconds: float
    bit_rate: int

    # Audio stream info
    codec_name: str
    sample_rate: int
    channels: int
    channel_layout: str
    bits_per_sample: int | None

    # Metadata tags
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    album_artist: str | None = None
    genre: str | None = None
    year: int | None = None
    track_number: int | None = None
    track_total: int | None = None
    disc_number: int | None = None
    disc_total: int | None = None
    composer: str | None = None
    comment: str | None = None

    # Audiobook specific
    narrator: str | None = None
    series: str | None = None
    series_part: int | None = None

    @property
    def duration_minutes(self) -> float:
        """Duration in minutes."""
        return self.duration_seconds / 60

    @property
    def is_audiobook(self) -> bool:
        """Check if this appears to be an audiobook based on metadata."""
        return bool(
            self.narrator
            or self.series
            or "audiobook" in (self.genre or "").lower()
            or "spoken" in (self.comment or "").lower()
        )

    @property
    def is_music(self) -> bool:
        """Check if this appears to be music based on metadata."""
        return bool(self.artist and self.album and not self.is_audiobook)


def extract_audio_technical_metadata(
    filepath: Path,
    probe_func: ProbeFileFunc = probe_file,
) -> AudioTechnicalMetadata | None:
    """Extract technical audio metadata from ffprobe output."""
    probe = probe_func(filepath)
    if probe.failed:
        logger.warning("Failed to probe %s: %s", filepath, probe.stderr)
        return None

    audio_streams = probe.audio_streams()
    if not audio_streams:
        logger.warning("No audio streams found in %s", filepath)
        return None

    stream = audio_streams[0]
    format_info = probe.format

    duration = _safe_float(
        format_info.get("duration") or stream.get("duration"),
        default=0.0,
    )
    stream_bit_rate = _safe_int(stream.get("bit_rate"))
    format_bit_rate = _safe_int(format_info.get("bit_rate"))
    bit_rate = stream_bit_rate or format_bit_rate
    sample_rate = _safe_int(stream.get("sample_rate"))
    channels = _safe_int(stream.get("channels"))
    bit_depth = _safe_int(stream.get("bits_per_sample")) or _safe_int(stream.get("bits_per_raw_sample"))

    return AudioTechnicalMetadata(
        duration_seconds=duration,
        codec=str(stream.get("codec_name")) if stream.get("codec_name") else None,
        bitrate_kbps=int(bit_rate / 1000) if bit_rate is not None else None,
        sample_rate_hz=sample_rate,
        channels=channels,
        bit_depth=bit_depth,
    )


def extract_audio_metadata(filepath: Path) -> AudioMetadata | None:
    """
    Extract comprehensive audio metadata from a file.

    Args:
        filepath: Path to the audio file.

    Returns:
        AudioMetadata object or None if extraction failed.
    """
    technical = extract_audio_technical_metadata(filepath)
    if technical is None:
        return None

    probe = probe_file(filepath)

    # Get first audio stream
    audio_streams = probe.audio_streams()
    if not audio_streams:
        logger.warning("No audio streams found in %s", filepath)
        return None

    stream = audio_streams[0]
    format_info = probe.format

    # Extract basic metadata
    try:
        file_size = int(format_info.get("size", 0))
    except (ValueError, TypeError):
        logger.warning("Invalid format metadata in %s", filepath)
        return None

    # Extract stream metadata
    codec_name = technical.codec or "unknown"
    sample_rate = technical.sample_rate_hz or 0
    channels = technical.channels or 0
    channel_layout = stream.get("channel_layout", "")
    bits_per_sample = technical.bit_depth

    # Extract tags
    tags = stream.get("tags", {}) or format_info.get("tags", {})

    def safe_int(value: str | None) -> int | None:
        if not value:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    def extract_track_info(track_str: str | None) -> tuple[int | None, int | None]:
        """Extract track number and total from strings like '3/12' or '03'."""
        if not track_str:
            return None, None
        if "/" in track_str:
            parts = track_str.split("/", 1)
            return safe_int(parts[0]), safe_int(parts[1])
        return safe_int(track_str), None

    track_num, track_total = extract_track_info(tags.get("track"))
    disc_num, disc_total = extract_track_info(tags.get("disc"))

    return AudioMetadata(
        filepath=filepath,
        filename=filepath.name,
        file_size_bytes=file_size,
        duration_seconds=technical.duration_seconds,
        bit_rate=(technical.bitrate_kbps or 0) * 1000,
        codec_name=codec_name,
        sample_rate=sample_rate,
        channels=channels,
        channel_layout=channel_layout,
        bits_per_sample=bits_per_sample,
        title=tags.get("title"),
        artist=tags.get("artist"),
        album=tags.get("album"),
        album_artist=tags.get("album_artist"),
        genre=tags.get("genre"),
        year=safe_int(tags.get("date") or tags.get("year")),
        track_number=track_num,
        track_total=track_total,
        disc_number=disc_num,
        disc_total=disc_total,
        composer=tags.get("composer"),
        comment=tags.get("comment"),
        narrator=tags.get("narrator"),
        series=tags.get("series"),
        series_part=safe_int(tags.get("series_part") or tags.get("part")),
    )


def _safe_int(value: object, default: int | None = None) -> int | None:
    if value is None:
        return default
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def _safe_float(value: object, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return default


def scan_audio_directory(
    directory: Path,
    extensions: frozenset[str] = frozenset({".mp3", ".flac", ".m4a", ".aac", ".ogg", ".wma"}),
    recursive: bool = True,
) -> list[AudioMetadata]:
    """
    Scan a directory for audio files and extract metadata.

    Args:
        directory: Directory to scan.
        extensions: File extensions to consider.
        recursive: Whether to scan subdirectories.

    Returns:
        List of AudioMetadata objects.
    """
    if not directory.is_dir():
        return []

    pattern = "**/*" if recursive else "*"
    audio_files: list[Path] = []

    for ext in extensions:
        audio_files.extend(directory.glob(f"{pattern}{ext}"))

    metadata_list = []
    for filepath in audio_files:
        metadata = extract_audio_metadata(filepath)
        if metadata:
            metadata_list.append(metadata)

    return metadata_list
