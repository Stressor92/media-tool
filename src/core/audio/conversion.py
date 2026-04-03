"""
src/core/audio/conversion.py

Audio format conversion using ffmpeg.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from src.statistics import get_collector
from src.statistics.event_types import EventType

from utils.audio_processor import AudioConversionResult, convert_audio_format

logger = logging.getLogger(__name__)

SUPPORTED_FORMATS = frozenset({"mp3", "flac", "m4a", "aac", "opus", "ogg"})


def convert_audio(
    input_file: Path,
    output_file: Path,
    format: str,
    quality: str | None = None,
    preserve_metadata: bool = True,
    overwrite: bool = False,
) -> AudioConversionResult:
    """
    Convert an audio file to a different format.

    Args:
        input_file: Source audio file.
        output_file: Destination file path.
        format: Target format (mp3, flac, m4a, aac, opus, ogg).
        quality: Quality setting (format-specific).
        preserve_metadata: Whether to copy metadata.
        overwrite: Whether to overwrite existing files.

    Returns:
        AudioConversionResult with conversion details.

    Raises:
        ValueError: If format is not supported.
    """
    if format.lower() not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported format '{format}'. Supported: {', '.join(sorted(SUPPORTED_FORMATS))}")

    logger.info("Converting %s to %s (%s)", input_file.name, output_file.name, format.upper())

    start = time.perf_counter()
    result = convert_audio_format(
        input_file=input_file,
        output_file=output_file,
        codec=format.lower(),
        quality=quality,
        preserve_metadata=preserve_metadata,
        overwrite=overwrite,
    )
    duration = time.perf_counter() - start

    if result.success:
        try:
            get_collector().record(EventType.AUDIO_CONVERTED, duration_seconds=duration)
        except Exception:
            logger.debug("Stats recording failed", exc_info=True)

    return result
