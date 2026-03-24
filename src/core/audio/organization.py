"""
src/core/audio/organization.py

Music library organization.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from .metadata import AudioMetadataEnhanced, extract_audio_metadata_enhanced
from .conversion import convert_audio

logger = logging.getLogger(__name__)


def _sanitize_filename(name: str) -> str:
    """Sanitize filename by removing/replacing invalid characters."""
    import re
    # Replace invalid characters with underscores
    return re.sub(r'[<>:"/\\|?*]', '_', name)


def _generate_music_path(metadata: AudioMetadataEnhanced, base_dir: Path) -> Path:
    """
    Generate Jellyfin-compatible path for music files.

    Structure: Music/Artist/Year - Album/Track - Title.ext
    """
    artist = metadata.artist or metadata.parsed_artist or "Unknown Artist"
    album = metadata.album or metadata.parsed_album or "Unknown Album"
    title = metadata.title or metadata.parsed_title or metadata.filename
    year = metadata.year or metadata.parsed_year

    # Sanitize
    artist = _sanitize_filename(artist)
    album = _sanitize_filename(album)
    title = _sanitize_filename(title)

    # Format album with year if available
    if year:
        album_dir = f"{year} - {album}"
    else:
        album_dir = album

    # Format track number
    track_str = ""
    if metadata.track_number or metadata.parsed_track_number:
        track_num = metadata.track_number or metadata.parsed_track_number
        track_str = f"{track_num:02d} - "

    filename = f"{track_str}{title}.flac"

    return base_dir / "Music" / artist / album_dir / filename


def organize_music(
    input_dir: Path,
    output_dir: Path,
    convert_format: Optional[str] = "flac",
    overwrite: bool = False
) -> dict[str, int]:
    """
    Organize music files into Jellyfin-compatible structure.

    Args:
        input_dir: Directory containing music files.
        output_dir: Base directory for organized files.
        convert_format: Target format for conversion (None to skip conversion).
        overwrite: Whether to overwrite existing files.

    Returns:
        Dict with counts: {"processed": int, "converted": int, "skipped": int, "errors": int}
    """
    if not input_dir.is_dir():
        raise NotADirectoryError(f"Input directory not found: {input_dir}")

    # Find audio files
    extensions = {".mp3", ".flac", ".m4a", ".aac", ".ogg", ".wma"}
    audio_files: list[Path] = []
    for ext in extensions:
        audio_files.extend(input_dir.rglob(f"*{ext}"))

    logger.info("Found %d music files in %s", len(audio_files), input_dir)

    counts = {"processed": 0, "converted": 0, "skipped": 0, "errors": 0}

    for input_file in audio_files:
        try:
            # Extract metadata
            metadata = extract_audio_metadata_enhanced(input_file)
            if not metadata:
                logger.warning("Could not extract metadata from %s", input_file)
                counts["errors"] += 1
                continue

            # Generate target path
            target_path = _generate_music_path(metadata, output_dir)

            # Check if target exists
            if target_path.exists() and not overwrite:
                logger.info("Skipping (exists): %s", target_path)
                counts["skipped"] += 1
                continue

            # Convert if needed
            if convert_format and input_file.suffix.lower() != f".{convert_format}":
                result = convert_audio(
                    input_file=input_file,
                    output_file=target_path,
                    format=convert_format,
                    preserve_metadata=True,
                    overwrite=overwrite,
                )
                if result.success:
                    logger.info("Converted and organized: %s → %s", input_file, target_path)
                    counts["converted"] += 1
                else:
                    logger.error("Conversion failed: %s", input_file)
                    counts["errors"] += 1
            else:
                # Just copy
                target_path.parent.mkdir(parents=True, exist_ok=True)
                import shutil
                shutil.copy2(input_file, target_path)
                logger.info("Organized: %s → %s", input_file, target_path)
                counts["processed"] += 1

        except Exception as e:
            logger.error("Error processing %s: %s", input_file, e)
            counts["errors"] += 1

    return counts