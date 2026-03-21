"""
src/core/audio/enhancement.py

Audio enhancement functions for music library improvement.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from utils.audio_processor import AudioConversionResult
from utils.ffmpeg_runner import FFmpegResult, run_ffmpeg

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AudioEnhancementResult:
    """Result of an audio enhancement operation."""

    success: bool
    input_file: Path
    output_file: Path
    operations_performed: list[str]
    ffmpeg_result: FFmpegResult
    input_metadata: Optional[dict] = None
    output_metadata: Optional[dict] = None

    @property
    def failed(self) -> bool:
        return not self.success


def remove_silence(
    input_file: Path,
    output_file: Path,
    silence_threshold: float = -50.0,
    silence_duration: float = 0.5,
    overwrite: bool = False
) -> AudioEnhancementResult:
    """
    Remove silence from the beginning and end of an audio file.

    Args:
        input_file: Source audio file.
        output_file: Destination file path.
        silence_threshold: Silence threshold in dB (default: -50.0).
        silence_duration: Minimum silence duration in seconds (default: 0.5).
        overwrite: Whether to overwrite existing files.

    Returns:
        AudioEnhancementResult with enhancement details.
    """
    logger.info(f"Removing silence from {input_file.name}")

    args = []

    # Input file
    args.extend(["-i", str(input_file)])

    # Silence detection and removal
    # This uses ffmpeg's silencedetect filter to find silence periods
    # and then removes them
    args.extend([
        "-af",
        f"silenceremove=start_threshold={silence_threshold}dB:"
        f"start_duration={silence_duration}:"
        f"stop_threshold={silence_threshold}dB:"
        f"stop_duration={silence_duration}",
        "-c:a", "copy"  # Copy audio codec to avoid re-encoding
    ])

    # Output options
    if overwrite:
        args.insert(0, "-y")
    else:
        args.insert(0, "-n")

    args.append(str(output_file))

    ffmpeg_result = run_ffmpeg(args)

    operations = ["silence_removal"] if ffmpeg_result.success else []

    return AudioEnhancementResult(
        success=ffmpeg_result.success,
        input_file=input_file,
        output_file=output_file,
        operations_performed=operations,
        ffmpeg_result=ffmpeg_result,
    )


def normalize_audio(
    input_file: Path,
    output_file: Path,
    target_level: float = -16.0,
    compression_ratio: float = 4.0,
    attack_time: float = 0.1,
    release_time: float = 0.1,
    overwrite: bool = False
) -> AudioEnhancementResult:
    """
    Normalize audio to consistent volume levels using dynamic range compression.

    Args:
        input_file: Source audio file.
        output_file: Destination file path.
        target_level: Target RMS level in dB (default: -16.0).
        compression_ratio: Compression ratio (default: 4.0).
        attack_time: Compressor attack time in seconds (default: 0.1).
        release_time: Compressor release time in seconds (default: 0.1).
        overwrite: Whether to overwrite existing files.

    Returns:
        AudioEnhancementResult with enhancement details.
    """
    logger.info(f"Normalizing audio levels in {input_file.name}")

    args = []

    # Input file
    args.extend(["-i", str(input_file)])

    # Audio filter chain for normalization
    # Uses loudnorm filter for true peak normalization
    args.extend([
        "-af",
        f"loudnorm=I={target_level}:TP=-1.5:LRA=11",
        "-c:a", "copy"  # Copy audio codec to avoid re-encoding
    ])

    # Output options
    if overwrite:
        args.insert(0, "-y")
    else:
        args.insert(0, "-n")

    args.append(str(output_file))

    ffmpeg_result = run_ffmpeg(args)

    operations = ["volume_normalization"] if ffmpeg_result.success else []

    return AudioEnhancementResult(
        success=ffmpeg_result.success,
        input_file=input_file,
        output_file=output_file,
        operations_performed=operations,
        ffmpeg_result=ffmpeg_result,
    )


def enhance_audio_quality(
    input_file: Path,
    output_file: Path,
    apply_declick: bool = True,
    apply_decrackle: bool = True,
    apply_equalization: bool = True,
    overwrite: bool = False
) -> AudioEnhancementResult:
    """
    Apply various audio quality enhancements.

    Args:
        input_file: Source audio file.
        output_file: Destination file path.
        apply_declick: Apply declicking filter (default: True).
        apply_decrackle: Apply decrackling filter (default: True).
        apply_equalization: Apply gentle equalization (default: True).
        overwrite: Whether to overwrite existing files.

    Returns:
        AudioEnhancementResult with enhancement details.
    """
    logger.info(f"Enhancing audio quality of {input_file.name}")

    args = []
    filters = []

    # Input file
    args.extend(["-i", str(input_file)])

    # Build filter chain
    if apply_declick:
        # Remove clicks and pops (good for vinyl/CD rips)
        filters.append("declick")

    if apply_decrackle:
        # Remove crackle (good for old recordings)
        filters.append("adecrackle")

    if apply_equalization:
        # Gentle equalization to improve clarity
        # Boost bass slightly, cut harsh highs, boost presence
        filters.append("equalizer=f=60:width_type=h:width=100:g=2")  # Boost low bass
        filters.append("equalizer=f=3000:width_type=h:width=1000:g=1")  # Boost presence
        filters.append("equalizer=f=8000:width_type=h:width=2000:g=-1")  # Cut harsh highs

    if filters:
        args.extend(["-af", ",".join(filters)])

    args.extend(["-c:a", "copy"])  # Copy audio codec

    # Output options
    if overwrite:
        args.insert(0, "-y")
    else:
        args.insert(0, "-n")

    args.append(str(output_file))

    ffmpeg_result = run_ffmpeg(args)

    operations = []
    if ffmpeg_result.success:
        if apply_declick:
            operations.append("declick")
        if apply_decrackle:
            operations.append("decrackle")
        if apply_equalization:
            operations.append("equalization")

    return AudioEnhancementResult(
        success=ffmpeg_result.success,
        input_file=input_file,
        output_file=output_file,
        operations_performed=operations,
        ffmpeg_result=ffmpeg_result,
    )


def improve_audio_file(
    input_file: Path,
    output_file: Path,
    remove_silence_flag: bool = True,
    normalize_volume: bool = True,
    enhance_quality: bool = True,
    silence_threshold: float = -50.0,
    target_level: float = -16.0,
    overwrite: bool = False
) -> AudioEnhancementResult:
    """
    Apply comprehensive audio improvements to a single file.

    This combines silence removal, volume normalization, and quality enhancement
    in a single operation for efficiency.

    Args:
        input_file: Source audio file.
        output_file: Destination file path.
        remove_silence_flag: Whether to remove silence (default: True).
        normalize_volume: Whether to normalize volume (default: True).
        enhance_quality: Whether to enhance quality (default: True).
        silence_threshold: Silence threshold in dB (default: -50.0).
        target_level: Target volume level in dB (default: -16.0).
        overwrite: Whether to overwrite existing files.

    Returns:
        AudioEnhancementResult with all performed operations.
    """
    logger.info(f"Improving audio file: {input_file.name}")

    args = []
    filters = []
    operations = []

    # Input file
    args.extend(["-i", str(input_file)])

    # Build comprehensive filter chain
    if remove_silence_flag:
        filters.append(
            f"silenceremove=start_threshold={silence_threshold}dB:"
            f"start_duration=0.5:"
            f"stop_threshold={silence_threshold}dB:"
            f"stop_duration=0.5"
        )
        operations.append("silence_removal")

    if normalize_volume:
        filters.append(f"loudnorm=I={target_level}:TP=-1.5:LRA=11")
        operations.append("volume_normalization")

    if enhance_quality:
        # Quality enhancement filters
        filters.append("declick")
        filters.append("equalizer=f=60:width_type=h:width=100:g=2")
        filters.append("equalizer=f=3000:width_type=h:width=1000:g=1")
        filters.append("equalizer=f=8000:width_type=h:width=2000:g=-1")
        operations.append("quality_enhancement")

    if filters:
        args.extend(["-af", ",".join(filters)])

    args.extend(["-c:a", "copy"])  # Copy audio codec to preserve quality

    # Output options
    if overwrite:
        args.insert(0, "-y")
    else:
        args.insert(0, "-n")

    args.append(str(output_file))

    ffmpeg_result = run_ffmpeg(args)

    success = ffmpeg_result.success
    if not success:
        operations = []  # No operations succeeded if overall failure

    return AudioEnhancementResult(
        success=success,
        input_file=input_file,
        output_file=output_file,
        operations_performed=operations,
        ffmpeg_result=ffmpeg_result,
    )


def improve_audio_library(
    input_dir: Path,
    output_dir: Path,
    extensions: frozenset[str] = frozenset({".mp3", ".flac", ".m4a", ".aac", ".ogg", ".wma"}),
    remove_silence_flag: bool = True,
    normalize_volume: bool = True,
    enhance_quality: bool = True,
    overwrite: bool = False
) -> dict[str, int]:
    """
    Improve an entire audio library with comprehensive enhancements.

    Args:
        input_dir: Directory containing audio files.
        output_dir: Directory for improved files.
        extensions: File extensions to process.
        remove_silence_flag: Remove silence from start/end.
        normalize_volume: Normalize volume levels.
        enhance_quality: Apply quality enhancements.
        overwrite: Overwrite existing files.

    Returns:
        Dict with counts: {"processed": int, "improved": int, "skipped": int, "errors": int}
    """
    if not input_dir.is_dir():
        raise NotADirectoryError(f"Input directory not found: {input_dir}")

    # Find audio files
    audio_files = []
    for ext in extensions:
        audio_files.extend(input_dir.rglob(f"*{ext}"))

    logger.info(f"Found {len(audio_files)} audio files to improve")

    counts = {"processed": 0, "improved": 0, "skipped": 0, "errors": 0}

    for input_file in audio_files:
        try:
            # Create relative path for output
            relative_path = input_file.relative_to(input_dir)
            output_file = output_dir / relative_path

            # Ensure output directory exists
            output_file.parent.mkdir(parents=True, exist_ok=True)

            # Check if output exists
            if output_file.exists() and not overwrite:
                logger.info(f"Skipping (exists): {output_file}")
                counts["skipped"] += 1
                continue

            # Apply improvements
            result = improve_audio_file(
                input_file=input_file,
                output_file=output_file,
                remove_silence_flag=remove_silence_flag,
                normalize_volume=normalize_volume,
                enhance_quality=enhance_quality,
                overwrite=overwrite,
            )

            if result.success and result.operations_performed:
                logger.info(f"Improved: {output_file.name} ({', '.join(result.operations_performed)})")
                counts["improved"] += 1
            elif result.success:
                # File copied without changes
                counts["processed"] += 1
            else:
                logger.error(f"Failed to improve: {input_file}")
                counts["errors"] += 1

        except Exception as e:
            logger.error(f"Error processing {input_file}: {e}")
            counts["errors"] += 1

    return counts