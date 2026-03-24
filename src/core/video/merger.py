"""
src/core/merger.py

Core business logic for merging two language-specific MP4 files into one
MKV with dual audio tracks (German + English).

Mirrors: englisch_and_german_movie.ps1

Rules:
- No print() / no CLI imports
- Fully reusable and testable in isolation
- Returns structured results
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path

from utils.ffmpeg_runner import FFmpegResult, run_ffmpeg

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Language detection patterns
# ---------------------------------------------------------------------------

# Matches suffixes like: -de, _de, (de), [de], -en, _en, (en), [en]
# Also handles variants without closing bracket at end-of-string
_LANG_PATTERN: dict[str, re.Pattern[str]] = {
    "deu": re.compile(r"(?:[-_ \(\[](?:de|german|deutsch)[\)\]_ ]?)$", re.IGNORECASE),
    "eng": re.compile(r"(?:[-_ \(\[](?:en|english)[\)\]_ ]?)$", re.IGNORECASE),
}

# Strips the language suffix to derive the clean base name
_CLEAN_SUFFIX = re.compile(r"(?:[-_ \(\[]+(?:de|german|deutsch|en|english)[\)\]_ ]?)$", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------


class MergeStatus(Enum):
    SUCCESS = auto()
    FAILED = auto()
    SKIPPED = auto()


@dataclass(frozen=True)
class MergeResult:
    """Immutable result object for a dual-audio merge operation."""

    status: MergeStatus
    german_source: Path | None
    english_source: Path | None
    target: Path
    message: str
    ffmpeg_result: FFmpegResult | None = None

    @property
    def succeeded(self) -> bool:
        return self.status == MergeStatus.SUCCESS

    @property
    def failed(self) -> bool:
        return self.status == MergeStatus.FAILED

    @property
    def skipped(self) -> bool:
        return self.status == MergeStatus.SKIPPED


# ---------------------------------------------------------------------------
# Language detection helpers
# ---------------------------------------------------------------------------


def detect_language_files(
    directory: Path,
) -> tuple[Path | None, Path | None]:
    """
    Scan a directory for MP4 files and detect the German and English versions
    by matching standard language suffixes in the filename.

    Patterns recognised: -de, _de, (de), [de] and equivalents for "en".

    Args:
        directory: Directory to scan.

    Returns:
        Tuple of (german_file, english_file). Either may be None if not found.
    """
    mp4_files = list(directory.glob("*.mp4"))
    german: Path | None = None
    english: Path | None = None

    for f in mp4_files:
        stem = f.stem
        if _LANG_PATTERN["deu"].search(stem):
            german = f
        elif _LANG_PATTERN["eng"].search(stem):
            english = f

    return german, english


def derive_output_name(german_file: Path) -> str:
    """
    Strip the German language suffix from a filename to get the clean title.

    Example: "Talk to Me (2022)-de.mp4" → "Talk to Me (2022)"

    Args:
        german_file: Path to the German-language source file.

    Returns:
        Clean base name without language suffix.
    """
    cleaned = _CLEAN_SUFFIX.sub("", german_file.stem).strip()
    return cleaned if cleaned else german_file.stem


# ---------------------------------------------------------------------------
# Core merge function
# ---------------------------------------------------------------------------


def merge_dual_audio(
    german_file: Path,
    english_file: Path,
    target: Path,
    overwrite: bool = False,
) -> MergeResult:
    """
    Merge a German-audio MP4 and an English-audio MP4 into a single MKV
    with two audio tracks. The video stream is taken from the German file.

    Equivalent ffmpeg call:
        ffmpeg -i german.mp4 -i english.mp4
               -map 0:v:0 -map 0:a:0 -map 1:a:0
               -c:v copy -c:a copy
               -metadata:s:a:0 language=deu
               -metadata:s:a:1 language=eng
               output.mkv

    Args:
        german_file:  Path to the German-audio MP4.
        english_file: Path to the English-audio MP4.
        target:       Desired output .mkv path.
        overwrite:    Re-merge even if target already exists.

    Returns:
        MergeResult describing the outcome.
    """
    for f in (german_file, english_file):
        if not f.exists():
            return MergeResult(
                status=MergeStatus.FAILED,
                german_source=german_file,
                english_source=english_file,
                target=target,
                message=f"Source file not found: {f}",
            )

    if target.exists() and not overwrite:
        return MergeResult(
            status=MergeStatus.SKIPPED,
            german_source=german_file,
            english_source=english_file,
            target=target,
            message=f"Target already exists: {target.name}",
        )

    target.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg_args = [
        "-y",
        "-i", str(german_file),
        "-i", str(english_file),
        # Video from German file; both audio tracks
        "-map", "0:v:0",
        "-map", "0:a:0",
        "-map", "1:a:0",
        # Lossless copy — no re-encoding
        "-c:v", "copy",
        "-c:a", "copy",
        # Language tags
        "-metadata:s:a:0", "language=deu",
        "-metadata:s:a:0", "title=Deutsch",
        "-metadata:s:a:1", "language=eng",
        "-metadata:s:a:1", "title=English",
        str(target),
    ]

    logger.info(
        "Merging: %s + %s → %s",
        german_file.name,
        english_file.name,
        target.name,
    )
    ffmpeg_result = run_ffmpeg(ffmpeg_args)

    if ffmpeg_result.success:
        return MergeResult(
            status=MergeStatus.SUCCESS,
            german_source=german_file,
            english_source=english_file,
            target=target,
            message=f"Merged successfully: {target.name}",
            ffmpeg_result=ffmpeg_result,
        )

    if target.exists():
        target.unlink(missing_ok=True)

    return MergeResult(
        status=MergeStatus.FAILED,
        german_source=german_file,
        english_source=english_file,
        target=target,
        message=(
            f"ffmpeg failed (exit {ffmpeg_result.return_code}). "
            "See logs for details."
        ),
        ffmpeg_result=ffmpeg_result,
    )


def merge_directory(
    directory: Path,
    output: Path | None = None,
    pattern: str | None = None,
    overwrite: bool = False,
) -> MergeResult:
    """
    Auto-detect language files in a directory and merge them.

    Convenience wrapper around detect_language_files + merge_dual_audio.

    Args:
        directory: Directory containing the two MP4 language versions.
        overwrite: Re-merge even if the target MKV already exists.

    Returns:
        MergeResult describing the outcome.
    """
    if not directory.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")

    if pattern is not None:
        candidates = list(directory.glob(pattern))
        # For now, continue to use the existing detection logic; pattern is advisory
        logger.info("Pattern scope has %d candidate files", len(candidates))

    german, english = detect_language_files(directory)

    _dummy_target = output if output is not None else directory / "unknown.mkv"

    if not german or not english:
        found = list(directory.glob("*.mp4"))
        names = ", ".join(f.name for f in found) or "(none)"
        return MergeResult(
            status=MergeStatus.FAILED,
            german_source=german,
            english_source=english,
            target=_dummy_target,
            message=(
                "Could not detect both language versions. "
                f"Found MP4 files: {names}"
            ),
        )

    if output is not None:
        target = output
    else:
        base_name = derive_output_name(german)
        target = directory / f"{base_name}.mkv"

    return merge_dual_audio(
        german_file=german,
        english_file=english,
        target=target,
        overwrite=overwrite,
    )
