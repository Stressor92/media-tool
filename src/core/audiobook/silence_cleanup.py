"""
src/core/audiobook/silence_cleanup.py

Audiobook silence cleanup utilities.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from utils.ffmpeg_runner import FFmpegResult, run_ffmpeg
from utils.progress import ProgressEvent, emit_progress

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SilenceCleanupResult:
    """Result of long-silence cleanup on a single file."""

    success: bool
    input_file: Path
    output_file: Path
    ffmpeg_result: FFmpegResult


def remove_long_silence(
    input_file: Path,
    output_file: Path,
    min_silence_seconds: float = 10.0,
    silence_threshold_db: float = -50.0,
    overwrite: bool = False,
) -> SilenceCleanupResult:
    """Remove long silent sections from an audiobook file using ffmpeg silenceremove."""
    if min_silence_seconds <= 0:
        raise ValueError("min_silence_seconds must be > 0")

    if not input_file.exists() or not input_file.is_file():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    output_file.parent.mkdir(parents=True, exist_ok=True)

    args = []
    args.extend(["-y" if overwrite else "-n"])
    args.extend(["-i", str(input_file)])
    args.extend(
        [
            "-af",
            (
                f"silenceremove=start_periods=1:start_duration={min_silence_seconds}:"
                f"start_threshold={silence_threshold_db}dB:"
                f"stop_periods=-1:stop_duration={min_silence_seconds}:"
                f"stop_threshold={silence_threshold_db}dB"
            ),
        ]
    )
    args.extend(["-map_metadata", "0"])
    args.extend(["-c:a", "aac"])
    args.append(str(output_file))

    ffmpeg_result = run_ffmpeg(args)

    return SilenceCleanupResult(
        success=ffmpeg_result.success,
        input_file=input_file,
        output_file=output_file,
        ffmpeg_result=ffmpeg_result,
    )


def remove_long_silence_in_library(
    input_dir: Path,
    output_dir: Path,
    min_silence_seconds: float = 10.0,
    silence_threshold_db: float = -50.0,
    recursive: bool = True,
    overwrite: bool = False,
    progress_callback: Callable[[ProgressEvent], None] | None = None,
) -> dict[str, int]:
    """Apply long-silence cleanup to all audiobook files in a directory."""
    if not input_dir.is_dir():
        raise NotADirectoryError(f"Input directory not found: {input_dir}")

    extensions = {".mp3", ".flac", ".m4a", ".m4b", ".aac", ".ogg", ".wma"}
    audio_files: list[Path] = []
    for ext in extensions:
        if recursive:
            audio_files.extend(input_dir.rglob(f"*{ext}"))
        else:
            audio_files.extend(input_dir.glob(f"*{ext}"))

    counts = {"processed": 0, "cleaned": 0, "skipped": 0, "errors": 0}
    total = len(audio_files)

    for index, input_file in enumerate(audio_files, start=1):
        emit_progress(
            progress_callback,
            ProgressEvent("remove-silence", index, total, input_file.name, "start", str(input_file)),
        )
        try:
            relative_path = input_file.relative_to(input_dir)
            output_file = output_dir / relative_path

            if output_file.exists() and not overwrite:
                counts["skipped"] += 1
                emit_progress(
                    progress_callback,
                    ProgressEvent(
                        "remove-silence",
                        index,
                        total,
                        input_file.name,
                        "skipped",
                        f"Target exists: {output_file.name}",
                    ),
                )
                continue

            result = remove_long_silence(
                input_file=input_file,
                output_file=output_file,
                min_silence_seconds=min_silence_seconds,
                silence_threshold_db=silence_threshold_db,
                overwrite=overwrite,
            )

            if result.success:
                counts["cleaned"] += 1
                emit_progress(
                    progress_callback,
                    ProgressEvent(
                        "remove-silence",
                        index,
                        total,
                        input_file.name,
                        "success",
                        f"Removed silence > {min_silence_seconds:.1f}s",
                    ),
                )
            else:
                counts["errors"] += 1
                emit_progress(
                    progress_callback,
                    ProgressEvent(
                        "remove-silence",
                        index,
                        total,
                        input_file.name,
                        "failed",
                        "ffmpeg cleanup failed",
                    ),
                )

            counts["processed"] += 1

        except Exception as exc:
            logger.error("Error while removing silence from %s: %s", input_file, exc)
            counts["errors"] += 1
            emit_progress(
                progress_callback,
                ProgressEvent("remove-silence", index, total, input_file.name, "failed", str(exc)),
            )

    return counts
