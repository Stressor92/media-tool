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
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .ffprobe_runner import probe_file

logger = logging.getLogger(__name__)


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
    bits_per_sample: Optional[int]

    # Metadata tags
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    album_artist: Optional[str] = None
    genre: Optional[str] = None
    year: Optional[int] = None
    track_number: Optional[int] = None
    track_total: Optional[int] = None
    disc_number: Optional[int] = None
    disc_total: Optional[int] = None
    composer: Optional[str] = None
    comment: Optional[str] = None

    # Audiobook specific
    narrator: Optional[str] = None
    series: Optional[str] = None
    series_part: Optional[int] = None

    @property
    def duration_minutes(self) -> float:
        """Duration in minutes."""
        return self.duration_seconds / 60

    @property
    def is_audiobook(self) -> bool:
        """Check if this appears to be an audiobook based on metadata."""
        return bool(
            self.narrator or
            self.series or
            "audiobook" in (self.genre or "").lower() or
            "spoken" in (self.comment or "").lower()
        )

    @property
    def is_music(self) -> bool:
        """Check if this appears to be music based on metadata."""
        return bool(self.artist and self.album and not self.is_audiobook)


def extract_audio_metadata(filepath: Path) -> AudioMetadata | None:
    """
    Extract comprehensive audio metadata from a file.

    Args:
        filepath: Path to the audio file.

    Returns:
        AudioMetadata object or None if extraction failed.
    """
    probe = probe_file(filepath)
    if probe.failed:
        logger.warning("Failed to probe %s: %s", filepath, probe.stderr)
        return None

    # Get first audio stream
    audio_streams = probe.audio_streams()
    if not audio_streams:
        logger.warning("No audio streams found in %s", filepath)
        return None

    stream = audio_streams[0]
    format_info = probe.format

    # Extract basic metadata
    try:
        duration = float(format_info.get("duration", 0))
        bit_rate = int(format_info.get("bit_rate", 0))
        file_size = int(format_info.get("size", 0))
    except (ValueError, TypeError):
        logger.warning("Invalid format metadata in %s", filepath)
        return None

    # Extract stream metadata
    codec_name = stream.get("codec_name", "unknown")
    sample_rate = int(stream.get("sample_rate", 0))
    channels = int(stream.get("channels", 0))
    channel_layout = stream.get("channel_layout", "")
    bits_per_sample = stream.get("bits_per_sample")
    if bits_per_sample:
        bits_per_sample = int(bits_per_sample)

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
        duration_seconds=duration,
        bit_rate=bit_rate,
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


def scan_audio_directory(
    directory: Path,
    extensions: frozenset[str] = frozenset({".mp3", ".flac", ".m4a", ".aac", ".ogg", ".wma"}),
    recursive: bool = True
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
    audio_files = []

    for ext in extensions:
        audio_files.extend(directory.glob(f"{pattern}{ext}"))

    metadata_list = []
    for filepath in audio_files:
        metadata = extract_audio_metadata(filepath)
        if metadata:
            metadata_list.append(metadata)

    return metadata_list