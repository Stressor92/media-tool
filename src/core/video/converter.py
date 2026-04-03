"""
src/core/converter.py

Core business logic for media conversion.
Responsibility: define WHAT to convert and HOW (strategy), delegate execution to utils.

Rules:
- No print() calls — use logging or return structured results
- No CLI/UI imports
- No hardcoded paths
- Fully reusable and testable in isolation
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path

from utils.ffmpeg_runner import FFmpegResult, run_ffmpeg

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------


class ConversionStatus(Enum):
    SUCCESS = auto()
    SKIPPED = auto()
    FAILED = auto()


@dataclass(frozen=True)
class ConversionResult:
    """
    Immutable result object for a single file conversion.
    Carries enough context for CLI/GUI layers to render feedback without
    knowing anything about the underlying ffmpeg invocation.
    """

    status: ConversionStatus
    source: Path
    target: Path
    message: str
    ffmpeg_result: FFmpegResult | None = None

    @property
    def succeeded(self) -> bool:
        return self.status == ConversionStatus.SUCCESS

    @property
    def skipped(self) -> bool:
        return self.status == ConversionStatus.SKIPPED

    @property
    def failed(self) -> bool:
        return self.status == ConversionStatus.FAILED


@dataclass
class BatchConversionSummary:
    """Aggregated result for a batch directory conversion."""

    results: list[ConversionResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def succeeded(self) -> list[ConversionResult]:
        return [r for r in self.results if r.succeeded]

    @property
    def skipped(self) -> list[ConversionResult]:
        return [r for r in self.results if r.skipped]

    @property
    def failed(self) -> list[ConversionResult]:
        return [r for r in self.results if r.failed]


# ---------------------------------------------------------------------------
# Single-file conversion
# ---------------------------------------------------------------------------


def convert_mp4_to_mkv(
    source: Path,
    target: Path,
    audio_language: str = "deu",
    audio_title: str = "Deutsch",
    overwrite: bool = False,
) -> ConversionResult:
    """
    Convert a single MP4 file to MKV (lossless stream copy).

    Mirrors the PowerShell workflow:
      ffmpeg -y -i <source> -map 0 -c copy
             -metadata:s:a:0 language=<lang>
             -metadata:s:a:0 title=<title>
             <target>

    Args:
        source:         Path to the input .mp4 file.
        target:         Path to the desired output .mkv file.
        audio_language: ISO 639-2/B language code for the first audio stream
                        (e.g. "deu", "eng", "fra"). Defaults to "deu".
        audio_title:    Human-readable title embedded in the audio stream
                        metadata. Defaults to "Deutsch".
        overwrite:      If True, re-convert even when target already exists.
                        Defaults to False (skip existing).

    Returns:
        ConversionResult describing success, skip, or failure.
    """
    if not source.exists():
        return ConversionResult(
            status=ConversionStatus.FAILED,
            source=source,
            target=target,
            message=f"Source file not found: {source}",
        )

    if target.exists() and not overwrite:
        logger.info("Skipping (already exists): %s", target)
        return ConversionResult(
            status=ConversionStatus.SKIPPED,
            source=source,
            target=target,
            message=f"Target already exists: {target}",
        )

    # Ensure output directory exists
    target.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg_args = [
        "-y",  # overwrite target without asking
        "-i",
        str(source),
        "-map",
        "0",  # preserve ALL streams
        "-c",
        "copy",  # lossless: no re-encoding
        "-metadata:s:a:0",
        f"language={audio_language}",
        "-metadata:s:a:0",
        f"title={audio_title}",
        str(target),
    ]

    logger.info("Converting: %s → %s", source.name, target)
    ffmpeg_result = run_ffmpeg(ffmpeg_args)

    if ffmpeg_result.success:
        logger.info("Conversion successful: %s", target)
        return ConversionResult(
            status=ConversionStatus.SUCCESS,
            source=source,
            target=target,
            message=f"Converted successfully: {target.name}",
            ffmpeg_result=ffmpeg_result,
        )

    # Cleanup incomplete/corrupt output on failure
    if target.exists():
        logger.warning("Removing incomplete output: %s", target)
        target.unlink(missing_ok=True)

    return ConversionResult(
        status=ConversionStatus.FAILED,
        source=source,
        target=target,
        message=(f"ffmpeg failed (exit {ffmpeg_result.return_code}). See logs for details."),
        ffmpeg_result=ffmpeg_result,
    )


# ---------------------------------------------------------------------------
# Batch conversion
# ---------------------------------------------------------------------------


def resolve_output_path(source: Path, output_root: Path | None = None) -> Path:
    """
    Derive the canonical MKV output path for a given MP4 source file.

    Replicates the PS naming convention:
      <root>/<BaseName>/<BaseName>.mkv

    If output_root is None, the subfolder is created next to the source file.

    Args:
        source:      The input .mp4 file.
        output_root: Optional base directory for output. When None, uses
                     source.parent as the root.

    Returns:
        Path: <output_root>/<stem>/<stem>.mkv
    """
    root = output_root if output_root is not None else source.parent
    stem = source.stem
    return root / stem / f"{stem}.mkv"


def batch_convert_directory(
    directory: Path,
    output_root: Path | None = None,
    audio_language: str = "deu",
    audio_title: str = "Deutsch",
    overwrite: bool = False,
    recursive: bool = False,
) -> BatchConversionSummary:
    """
    Convert all .mp4 files in a directory to MKV (lossless, stream copy).

    Each file is placed in its own subfolder following the convention:
      <output_root>/<BaseName>/<BaseName>.mkv

    Args:
        directory:      Directory to scan for .mp4 files.
        output_root:    Base directory for output subfolders. Defaults to
                        the source directory itself (mirrors PS behaviour).
        audio_language: ISO 639-2/B code for the first audio track.
        audio_title:    Human-readable title for the first audio track.
        overwrite:      Skip files whose target MKV already exists when False.
        recursive:      Scan subdirectories as well when True.

    Returns:
        BatchConversionSummary containing all individual ConversionResult objects.
    """
    if not directory.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")

    pattern = "**/*.mp4" if recursive else "*.mp4"
    mp4_files = sorted(directory.glob(pattern))

    if not mp4_files:
        logger.info("No .mp4 files found in: %s", directory)

    summary = BatchConversionSummary()

    for source in mp4_files:
        target = resolve_output_path(source, output_root)
        result = convert_mp4_to_mkv(
            source=source,
            target=target,
            audio_language=audio_language,
            audio_title=audio_title,
            overwrite=overwrite,
        )
        summary.results.append(result)

    return summary
