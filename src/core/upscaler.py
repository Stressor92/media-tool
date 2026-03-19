"""
src/core/upscaler.py

Core business logic for upscaling DVD-quality video to 720p H.265.

Mirrors: DVD_h265_720p_improvment.ps1

Features:
- Skips files already at >= 720p
- Anime detection (disables cropdetect)
- SAR-aware DAR calculation
- Plausibility-filtered cropdetect
- Lanczos scale to 720p with correct DAR
- Soft deband (gradfun), colour correction (eq), unsharp mask
- H.265 CRF encode, copy audio + subtitles
- Per-file duration + size delta tracking

Rules:
- No print() / no CLI imports
- Returns structured results with logging
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path

from utils.ffmpeg_runner import FFmpegResult, run_ffmpeg
from utils.ffprobe_runner import probe_cropdetect, probe_file

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants — all tunable via UpscaleOptions
# ---------------------------------------------------------------------------

ANIME_KEYWORDS = re.compile(
    r"anime|ova|episode|ep\d{1,3}|crunchyroll|funimation|"
    r"subbed|simulcast|dubbed",
    re.IGNORECASE,
)

OUTPUT_SUFFIX = "[DVD]"


# ---------------------------------------------------------------------------
# Options model
# ---------------------------------------------------------------------------


@dataclass
class UpscaleOptions:
    """
    Configurable parameters for the DVD upscale pipeline.

    All defaults mirror the original PowerShell script.
    """

    target_height: int = 720
    crf: int = 21
    preset: str = "medium"
    codec: str = "libx265"

    # Filter chain tweaks
    gradfun_strength: float = 4.0
    eq_contrast: float = 1.02
    eq_brightness: float = 0.0
    eq_saturation: float = 1.02
    unsharp_luma: float = 0.25       # luma amount (5x5 matrix)

    # Cropdetect settings
    crop_skip_seconds: int = 5
    crop_sample_seconds: int = 10

    # Skip behaviour
    overwrite: bool = False


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------


class UpscaleStatus(Enum):
    SUCCESS = auto()
    SKIPPED = auto()
    FAILED = auto()


@dataclass(frozen=True)
class UpscaleResult:
    """Immutable result object for a single upscale operation."""

    status: UpscaleStatus
    source: Path
    target: Path
    message: str
    duration_seconds: float = 0.0
    size_before_gb: float = 0.0
    size_after_gb: float = 0.0
    ffmpeg_result: FFmpegResult | None = None

    @property
    def succeeded(self) -> bool:
        return self.status == UpscaleStatus.SUCCESS

    @property
    def skipped(self) -> bool:
        return self.status == UpscaleStatus.SKIPPED

    @property
    def failed(self) -> bool:
        return self.status == UpscaleStatus.FAILED

    @property
    def size_delta_gb(self) -> float:
        return round(self.size_before_gb - self.size_after_gb, 3)


@dataclass
class BatchUpscaleSummary:
    results: list[UpscaleResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def succeeded(self) -> list[UpscaleResult]:
        return [r for r in self.results if r.succeeded]

    @property
    def skipped(self) -> list[UpscaleResult]:
        return [r for r in self.results if r.skipped]

    @property
    def failed(self) -> list[UpscaleResult]:
        return [r for r in self.results if r.failed]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _is_anime(name: str) -> bool:
    """Return True if the filename matches known anime naming patterns."""
    return bool(ANIME_KEYWORDS.search(name))


def _compute_dar(video_stream: dict) -> float | None:
    """
    Compute the Display Aspect Ratio from a video stream probe dict.

    Takes Sample Aspect Ratio (SAR) into account for anamorphic sources.

    Args:
        video_stream: The first video stream dict from ffprobe output.

    Returns:
        DAR as a float, or None if it cannot be determined.
    """
    try:
        width = float(video_stream["width"])
        height = float(video_stream["height"])
    except (KeyError, ValueError, TypeError):
        return None

    sar_str = video_stream.get("sample_aspect_ratio", "")
    sar = 1.0
    if sar_str and ":" in sar_str:
        parts = sar_str.split(":")
        try:
            num, den = float(parts[0]), float(parts[1])
            if den != 0:
                sar = num / den
        except ValueError:
            pass

    if height == 0:
        return None

    return (width * sar) / height


def _is_crop_plausible(iw: int, ih: int, cw: int, ch: int) -> bool:
    """
    Validate whether detected crop values look like real letterbox/pillarbox.

    Rejects crops that are too small or represent full-frame identity crops,
    to avoid accidentally cropping content that doesn't need it.

    Args:
        iw, ih: Input width and height.
        cw, ch: Detected crop width and height.
    """
    if cw < 320 or ch < 200:
        return False

    w_ratio = cw / iw
    h_ratio = ch / ih

    # Letterbox: full width, reduced height (black bars top/bottom)
    is_letterbox = (w_ratio >= 0.94) and (h_ratio < 0.995)
    # Pillarbox: full height, reduced width (black bars left/right)
    is_pillarbox = (h_ratio >= 0.94) and (w_ratio < 0.995)

    # Accept exactly one type — reject ambiguous or identity crops
    return is_letterbox != is_pillarbox


def _build_filter_chain(
    dar: float,
    crop_filter: str | None,
    opts: UpscaleOptions,
) -> str:
    """
    Build the ffmpeg -vf filter chain for DVD upscaling.

    Order: [crop →] scale → gradfun → eq → unsharp → format

    Args:
        dar:         Display aspect ratio (used to compute output width).
        crop_filter: Optional crop=W:H:X:Y string, or None.
        opts:        UpscaleOptions for tuning parameters.
    """
    filters: list[str] = []

    if crop_filter:
        filters.append(crop_filter)

    # Scale to target height, compute width from DAR (must be even)
    h = opts.target_height
    filters.append(f"scale=trunc({h}*dar/2)*2:{h}:flags=lanczos")

    # Soft deband
    filters.append(f"gradfun={opts.gradfun_strength:.1f}")

    # Colour correction
    filters.append(
        f"eq=contrast={opts.eq_contrast}:"
        f"brightness={opts.eq_brightness}:"
        f"saturation={opts.eq_saturation}"
    )

    # Very light sharpening (luma only)
    filters.append(f"unsharp=5:5:{opts.unsharp_luma}:5:5:0.0")

    # Ensure clean YUV 4:2:0 output
    filters.append("format=yuv420p")

    return ",".join(filters)


def _resolve_output_path(source: Path) -> Path:
    """
    Derive the output path for a given source file.

    Convention: <source_dir>/<stem>/<stem> - [DVD].mkv

    Args:
        source: Input MKV file.
    """
    stem = source.stem
    return source.parent / stem / f"{stem} - {OUTPUT_SUFFIX}.mkv"


# ---------------------------------------------------------------------------
# Single-file upscale
# ---------------------------------------------------------------------------


def upscale_dvd(
    source: Path,
    target: Path | None = None,
    opts: UpscaleOptions | None = None,
) -> UpscaleResult:
    """
    Upscale a DVD-quality MKV to 720p H.265 with full filter chain.

    Skips files that are already at or above the target height.
    Skips files whose output name ends with [DVD] to prevent re-processing.

    Args:
        source: Input MKV file.
        target: Explicit output path. Defaults to <stem>/<stem> - [DVD].mkv.
        opts:   Upscale configuration. Uses defaults if None.

    Returns:
        UpscaleResult describing the outcome.
    """
    if opts is None:
        opts = UpscaleOptions()

    resolved_target = target or _resolve_output_path(source)

    if not source.exists():
        return UpscaleResult(
            status=UpscaleStatus.FAILED,
            source=source,
            target=resolved_target,
            message=f"Source file not found: {source}",
        )

    # Don't re-process already-upscaled files
    if source.stem.endswith(f"- {OUTPUT_SUFFIX}"):
        return UpscaleResult(
            status=UpscaleStatus.SKIPPED,
            source=source,
            target=resolved_target,
            message="Already an upscaled [DVD] file — skipping.",
        )

    if resolved_target.exists() and not opts.overwrite:
        return UpscaleResult(
            status=UpscaleStatus.SKIPPED,
            source=source,
            target=resolved_target,
            message=f"Target already exists: {resolved_target.name}",
        )

    # --- Probe source -------------------------------------------------
    probe = probe_file(source)
    if probe.failed:
        return UpscaleResult(
            status=UpscaleStatus.FAILED,
            source=source,
            target=resolved_target,
            message=f"ffprobe failed: {probe.stderr[:200]}",
        )

    video = probe.first_video()
    if not video:
        return UpscaleResult(
            status=UpscaleStatus.FAILED,
            source=source,
            target=resolved_target,
            message="No video stream found in source file.",
        )

    height = int(video.get("height", 0))
    width  = int(video.get("width",  0))
    codec  = video.get("codec_name", "unknown")

    logger.info("%s — %dx%d %s", source.name, width, height, codec)

    if height >= opts.target_height:
        return UpscaleResult(
            status=UpscaleStatus.SKIPPED,
            source=source,
            target=resolved_target,
            message=f"Already {height}p (≥ {opts.target_height}p) — skipping.",
        )

    # --- Anime detection -----------------------------------------------
    is_anime = _is_anime(source.stem)
    if is_anime:
        logger.info("%s — Anime detected: cropdetect disabled.", source.name)

    # --- DAR calculation -----------------------------------------------
    dar = _compute_dar(video)
    if dar is None:
        return UpscaleResult(
            status=UpscaleStatus.FAILED,
            source=source,
            target=resolved_target,
            message="Could not compute display aspect ratio.",
        )
    logger.info("%s — DAR=%.4f", source.name, dar)

    # --- Crop detection ------------------------------------------------
    crop_filter: str | None = None
    if not is_anime:
        raw_crop = probe_cropdetect(
            source,
            skip_seconds=opts.crop_skip_seconds,
            sample_seconds=opts.crop_sample_seconds,
        )
        if raw_crop:
            # Parse crop=W:H:X:Y
            parts = raw_crop.replace("crop=", "").split(":")
            if len(parts) == 4:
                cw, ch, cx, cy = (int(p) for p in parts)
                if _is_crop_plausible(width, height, cw, ch):
                    crop_filter = raw_crop
                    logger.info("%s — Crop accepted: %s", source.name, crop_filter)
                else:
                    logger.info("%s — Crop ignored (not plausible): %s", source.name, raw_crop)

    # --- Build filter chain --------------------------------------------
    vf = _build_filter_chain(dar, crop_filter, opts)
    logger.info("%s — Filter chain: %s", source.name, vf)

    # --- Prepare output ------------------------------------------------
    resolved_target.parent.mkdir(parents=True, exist_ok=True)

    size_before = round(source.stat().st_size / 1_073_741_824, 3)

    ffmpeg_args = [
        "-y",
        "-i", str(source),
        "-map", "0",
        "-vf", vf,
        "-c:v", opts.codec,
        "-crf", str(opts.crf),
        "-preset", opts.preset,
        "-c:a", "copy",
        "-c:s", "copy",
        "-map_metadata", "0",
        "-map_chapters", "0",
        str(resolved_target),
    ]

    logger.info(
        "Starting upscale: %s → %s  [CRF=%d, %s, preset=%s]",
        source.name, resolved_target.name, opts.crf, opts.codec, opts.preset,
    )

    start = time.monotonic()
    ffmpeg_result = run_ffmpeg(ffmpeg_args)
    elapsed = round(time.monotonic() - start, 1)

    if ffmpeg_result.success and resolved_target.exists():
        size_after = round(resolved_target.stat().st_size / 1_073_741_824, 3)
        logger.info(
            "%s — Done in %.1fs. %.3fGB → %.3fGB (Δ %.3fGB)",
            source.name, elapsed, size_before, size_after,
            size_before - size_after,
        )
        return UpscaleResult(
            status=UpscaleStatus.SUCCESS,
            source=source,
            target=resolved_target,
            message=f"Upscaled successfully: {resolved_target.name}",
            duration_seconds=elapsed,
            size_before_gb=size_before,
            size_after_gb=size_after,
            ffmpeg_result=ffmpeg_result,
        )

    # Cleanup on failure
    resolved_target.unlink(missing_ok=True)

    return UpscaleResult(
        status=UpscaleStatus.FAILED,
        source=source,
        target=resolved_target,
        message=(
            f"ffmpeg failed (exit {ffmpeg_result.return_code}) "
            f"after {elapsed:.1f}s."
        ),
        duration_seconds=elapsed,
        size_before_gb=size_before,
        ffmpeg_result=ffmpeg_result,
    )


# ---------------------------------------------------------------------------
# Batch upscale
# ---------------------------------------------------------------------------


def batch_upscale_directory(
    directory: Path,
    opts: UpscaleOptions | None = None,
    recursive: bool = False,
) -> BatchUpscaleSummary:
    """
    Upscale all MKV files in a directory that are below the target resolution.

    Args:
        directory: Directory to scan for .mkv files.
        opts:      Upscale configuration. Uses defaults if None.
        recursive: Also scan subdirectories.

    Returns:
        BatchUpscaleSummary with all individual UpscaleResult objects.
    """
    if not directory.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")

    pattern = "**/*.mkv" if recursive else "*.mkv"
    mkv_files = sorted(directory.glob(pattern))

    summary = BatchUpscaleSummary()

    for source in mkv_files:
        result = upscale_dvd(source, opts=opts)
        summary.results.append(result)

    return summary
