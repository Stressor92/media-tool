"""
src/utils/audio_processor.py

Audio processing utilities using ffmpeg.
Handles format conversion, metadata embedding, and audio organization.

Rules:
- No business logic here
- No CLI/UI concerns
- Always capture stderr
- Always validate return codes
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .audio_analyzer import AudioMetadata
from .ffmpeg_runner import FFmpegResult, run_ffmpeg

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AudioConversionResult:
    """Result of an audio conversion operation."""

    success: bool
    input_file: Path
    output_file: Path
    ffmpeg_result: FFmpegResult
    input_metadata: AudioMetadata | None = None
    output_metadata: AudioMetadata | None = None

    @property
    def failed(self) -> bool:
        return not self.success


def convert_audio_format(
    input_file: Path,
    output_file: Path,
    codec: str = "flac",
    quality: Optional[str] = None,
    preserve_metadata: bool = True,
    overwrite: bool = False
) -> AudioConversionResult:
    """
    Convert audio file to a different format.

    Args:
        input_file: Source audio file.
        output_file: Destination file path.
        codec: Target codec (flac, mp3, aac, etc.).
        quality: Quality setting (codec-specific).
        preserve_metadata: Whether to copy metadata.
        overwrite: Whether to overwrite existing files.

    Returns:
        AudioConversionResult with conversion details.
    """
    from .audio_analyzer import extract_audio_metadata

    input_metadata = extract_audio_metadata(input_file)

    args = []

    # Input file
    args.extend(["-i", str(input_file)])

    # Codec settings
    if codec == "flac":
        args.extend(["-c:a", "flac"])
        if quality:
            args.extend(["-compression_level", quality])
    elif codec == "mp3":
        args.extend(["-c:a", "libmp3lame"])
        if quality:
            args.extend(["-q:a", quality])  # 0-9, lower is better
        else:
            args.extend(["-q:a", "0"])  # Highest quality
    elif codec == "aac":
        args.extend(["-c:a", "aac"])
        if quality:
            args.extend(["-b:a", quality])  # Bitrate like "192k"
        else:
            args.extend(["-b:a", "256k"])
    elif codec == "opus":
        args.extend(["-c:a", "libopus"])
        if quality:
            args.extend(["-b:a", quality])
        else:
            args.extend(["-b:a", "128k"])
    else:
        args.extend(["-c:a", codec])

    # Metadata handling
    if preserve_metadata:
        args.extend(["-map_metadata", "0"])
        args.extend(["-map", "0:a"])

    # Output options
    if overwrite:
        args.insert(0, "-y")
    else:
        args.insert(0, "-n")

    args.append(str(output_file))

    ffmpeg_result = run_ffmpeg(args)

    output_metadata = None
    if ffmpeg_result.success and output_file.exists():
        output_metadata = extract_audio_metadata(output_file)

    return AudioConversionResult(
        success=ffmpeg_result.success,
        input_file=input_file,
        output_file=output_file,
        ffmpeg_result=ffmpeg_result,
        input_metadata=input_metadata,
        output_metadata=output_metadata,
    )


def embed_audio_metadata(
    input_file: Path,
    output_file: Path,
    metadata: dict[str, str],
    overwrite: bool = False
) -> AudioConversionResult:
    """
    Embed metadata into an audio file.

    Args:
        input_file: Source audio file.
        output_file: Destination file path.
        metadata: Dictionary of metadata tags to embed.
        overwrite: Whether to overwrite existing files.

    Returns:
        AudioConversionResult with operation details.
    """
    from .audio_analyzer import extract_audio_metadata

    input_metadata = extract_audio_metadata(input_file)

    args = []

    # Input file
    args.extend(["-i", str(input_file)])

    # Copy audio stream
    args.extend(["-c:a", "copy"])

    # Add metadata
    for key, value in metadata.items():
        args.extend(["-metadata", f"{key}={value}"])

    # Output options
    if overwrite:
        args.insert(0, "-y")
    else:
        args.insert(0, "-n")

    args.append(str(output_file))

    ffmpeg_result = run_ffmpeg(args)

    output_metadata = None
    if ffmpeg_result.success and output_file.exists():
        output_metadata = extract_audio_metadata(output_file)

    return AudioConversionResult(
        success=ffmpeg_result.success,
        input_file=input_file,
        output_file=output_file,
        ffmpeg_result=ffmpeg_result,
        input_metadata=input_metadata,
        output_metadata=output_metadata,
    )


def generate_jellyfin_audio_path(metadata: AudioMetadata, base_dir: Path) -> Path:
    """
    Generate a Jellyfin-compatible path for audio files.

    Args:
        metadata: Audio metadata.
        base_dir: Base directory for the library.

    Returns:
        Proper path following Jellyfin conventions.
    """
    if metadata.is_audiobook:
        # Audiobooks: Author/Series/Book Name/file.ext
        author = metadata.narrator or metadata.artist or "Unknown Author"
        series = metadata.series or ""
        title = metadata.title or metadata.filename

        if series:
            return base_dir / "Audiobooks" / author / series / f"{title}.flac"
        else:
            return base_dir / "Audiobooks" / author / f"{title}.flac"

    elif metadata.is_music:
        # Music: Artist/Album/Track - Title.ext
        artist = metadata.album_artist or metadata.artist or "Unknown Artist"
        album = metadata.album or "Unknown Album"

        track_str = ""
        if metadata.track_number:
            track_str = f"{metadata.track_number:02d} - "

        title = metadata.title or metadata.filename
        filename = f"{track_str}{title}.flac"

        return base_dir / "Music" / artist / album / filename

    else:
        # Fallback for unidentified audio
        return base_dir / "Unknown" / metadata.filename