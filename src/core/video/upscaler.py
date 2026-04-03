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
- Deinterlace (optional yadif/bwdif), soft deband (gradfun pre-scale), colour correction (eq), unsharp mask
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
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any

from src.backup import get_backup_manager
from src.backup.models import MediaType
from src.statistics import get_collector
from src.statistics.event_types import EventType

from core.video.encoder_profile_builder import EncoderProfileBuilder
from core.video.hardware_detector import HardwareDetector
from utils.ffmpeg_runner import FFmpegResult, run_ffmpeg
from utils.ffprobe_runner import probe_cropdetect, probe_file
from utils.progress import ProgressEvent, emit_progress

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants — all tunable via UpscaleOptions
# ---------------------------------------------------------------------------

ANIME_KEYWORDS = re.compile(
    r"anime|ova|episode|ep\d{1,3}|crunchyroll|funimation|" r"subbed|simulcast|dubbed",
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

    target_width: int = 1280
    target_height: int = 720
    crf: int = 21
    preset: str = "medium"
    codec: str = "libx265"
    # Hardware encoder options
    use_hardware: bool = True  # Enable hardware encoding if available
    preferred_encoder: str | None = None  # "nvenc", "amf", "qsv", or None for auto
    hw_fallback_on_error: bool = True  # Retry with software if HW fails

    # Filter chain tweaks
    gradfun_strength: float = 4.0
    eq_contrast: float = 1.02
    eq_brightness: float = 0.0
    eq_saturation: float = 1.02
    unsharp_luma: float = 0.15  # luma amount (5x5 matrix) — gentler default, DVD edges can't support more

    # Deinterlacing — enable for PAL TV recordings and interlaced DVD sources
    # yadif: fast field-aware deinterlace; bwdif: slower but higher quality
    deinterlace: bool = False
    deinterlace_mode: str = "yadif"  # "yadif" or "bwdif"

    # Cropdetect settings
    crop_skip_seconds: int = 5
    crop_sample_seconds: int = 10

    # Force-disable cropdetect regardless of anime detection (used by anime preset)
    force_disable_crop: bool = False

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


def _compute_dar(video_stream: dict[str, Any]) -> float | None:
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

    Order: [deinterlace →] [crop →] gradfun → scale → eq → unsharp → format

    gradfun debands on the original bit depth before upscaling, which is more
    effective than debanding at the higher output resolution. Deinterlacing must
    come first so all subsequent filters see progressive frames.

    Args:
        dar:         Display aspect ratio (used to compute output width).
        crop_filter: Optional crop=W:H:X:Y string, or None.
        opts:        UpscaleOptions for tuning parameters.
    """
    filters: list[str] = []

    # Deinterlace first — PAL TV recordings and many DVD ISOs are interlaced.
    # mode=1 = send frame, field-aware (yadif); bwdif is higher quality but slower.
    if opts.deinterlace:
        filters.append(f"{opts.deinterlace_mode}=mode=1")

    if crop_filter:
        filters.append(crop_filter)

    # Soft deband *before* scaling — operates on original bit-depth artifacts.
    filters.append(f"gradfun={opts.gradfun_strength:.1f}")

    # Scale to the configured HD target profile.
    filters.append(f"scale={opts.target_width}:{opts.target_height}:flags=lanczos")

    # Colour correction
    filters.append(f"eq=contrast={opts.eq_contrast}:brightness={opts.eq_brightness}:saturation={opts.eq_saturation}")

    # Very light sharpening (luma only) — keep low to avoid ringing on soft DVD edges.
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
    stem = source.stem.strip()
    return source.parent / stem / f"{stem} - {OUTPUT_SUFFIX}.mkv"


def _build_encoder_args(opts: UpscaleOptions, source_name: str) -> tuple[list[str], str]:
    """
    Build encoder-specific ffmpeg arguments.

    Attempts to use hardware encoders if available and enabled.
    Falls back to software encoding if requested or if hardware is unavailable.

    Args:
        opts: Upscale options
        source_name: Source filename (for logging)

    Returns:
        Tuple of (ffmpeg_args_list, encoder_type_str)
    """
    if not opts.use_hardware:
        # Software encoding explicitly requested
        logger.debug(f"{source_name} — Hardware encoding disabled, using libx265")
        return (
            ["-c:v", "libx265", "-crf", str(opts.crf), "-preset", opts.preset, "-pix_fmt", "yuv420p"],
            "software",
        )

    try:
        # Detect available hardware and build profile-specific args
        hw_caps = HardwareDetector.detect()
        builder = EncoderProfileBuilder(
            profile="dvd-hq",  # TODO: use opts profile when available
            hw_caps=hw_caps,
            force_software=False,
            preferred_encoder=opts.preferred_encoder,
        )
        params = builder.build()

        # Override CRF/preset if user customized them (compatibility mode)
        if opts.crf != 21 or opts.preset != "medium":
            logger.debug(
                f"{source_name} — Custom CRF/preset overrides hardware params (CRF={opts.crf}, preset={opts.preset})"
            )

        logger.info(f"{source_name} — Using {params.encoder_type.value} encoder")
        return (params.base_args, params.encoder_type.value)

    except Exception as e:
        logger.warning(f"{source_name} — Hardware detection failed: {e}, using software fallback")
        return (
            ["-c:v", "libx265", "-crf", str(opts.crf), "-preset", opts.preset, "-pix_fmt", "yuv420p"],
            "software",
        )


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
    width = int(video.get("width", 0))
    codec = video.get("codec_name", "unknown")

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
    if not is_anime and not opts.force_disable_crop:
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

    # Build encoder args (hardware-aware)
    encoder_args, encoder_type = _build_encoder_args(opts, source.name)

    ffmpeg_args = [
        "-y",
        "-i",
        str(source),
        "-map",
        "0",
        "-vf",
        vf,
    ]
    ffmpeg_args.extend(encoder_args)
    ffmpeg_args.extend(
        [
            "-c:a",
            "copy",
            "-c:s",
            "copy",
            "-map_metadata",
            "0",
            "-map_chapters",
            "0",
            str(resolved_target),
        ]
    )

    logger.info(
        "Starting upscale: %s → %s  [CRF=%d, %s, preset=%s]",
        source.name,
        resolved_target.name,
        opts.crf,
        opts.codec,
        opts.preset,
    )
    logger.info(
        "Encoder: %s (hardware: %s)",
        encoder_type,
        "yes" if opts.use_hardware else "no",
    )

    backup_entry = None
    try:
        backup_entry = get_backup_manager().create(source, operation="upscale", media_type=MediaType.VIDEO)
    except Exception:
        logger.debug("Backup creation failed", exc_info=True)

    start = time.monotonic()
    ffmpeg_result = run_ffmpeg(ffmpeg_args)
    elapsed = round(time.monotonic() - start, 1)

    # If hardware encoding failed and fallback is enabled, retry with software
    if not ffmpeg_result.success and opts.use_hardware and opts.hw_fallback_on_error and encoder_type != "software":
        logger.warning(
            "%s — Hardware encoder (%s) failed, retrying with libx265 software encoder",
            source.name,
            encoder_type,
        )
        resolved_target.unlink(missing_ok=True)  # Clean up partial output
        sw_encoder_args, _ = _build_encoder_args(UpscaleOptions(**{**vars(opts), "use_hardware": False}), source.name)
        ffmpeg_args_sw = ffmpeg_args[:6] + ffmpeg_args[6:8] + sw_encoder_args + ffmpeg_args[6 + len(encoder_args) :]
        ffmpeg_result = run_ffmpeg(ffmpeg_args_sw)
        elapsed = round(time.monotonic() - start, 1)

    if ffmpeg_result.success and resolved_target.exists():
        if backup_entry is not None:
            try:
                validation = get_backup_manager().validate(backup_entry, resolved_target)
                if validation.passed:
                    get_backup_manager().cleanup(backup_entry)
                else:
                    get_backup_manager().rollback(backup_entry)
            except Exception:
                logger.debug("Backup validation/cleanup failed", exc_info=True)

        size_after = round(resolved_target.stat().st_size / 1_073_741_824, 3)
        try:
            get_collector().record(
                EventType.VIDEO_UPSCALED,
                duration_seconds=elapsed,
                input_resolution=f"{height}p",
                output_resolution=f"{opts.target_height}p",
                profile="dvd-hq",
                encoder=encoder_type,
                file_size_before_mb=round(size_before * 1024, 3),
                file_size_after_mb=round(size_after * 1024, 3),
            )
        except Exception:
            logger.debug("Stats recording failed", exc_info=True)

        logger.info(
            "%s — Done in %.1fs. %.3fGB → %.3fGB (Δ %.3fGB)",
            source.name,
            elapsed,
            size_before,
            size_after,
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

    if backup_entry is not None:
        try:
            get_backup_manager().rollback(backup_entry)
        except Exception:
            logger.debug("Backup rollback failed", exc_info=True)

    return UpscaleResult(
        status=UpscaleStatus.FAILED,
        source=source,
        target=resolved_target,
        message=(f"ffmpeg failed (exit {ffmpeg_result.return_code}) after {elapsed:.1f}s."),
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
    progress_callback: Callable[[ProgressEvent], None] | None = None,
    dry_run: bool = False,
) -> BatchUpscaleSummary:
    """
    Upscale all MKV files in a directory that are below the target resolution.

    Args:
        directory: Directory to scan for .mkv files.
        opts:      Upscale configuration. Uses defaults if None.
        recursive: Also scan subdirectories.
        dry_run:   Report which files would be processed without writing output files.

    Returns:
        BatchUpscaleSummary with all individual UpscaleResult objects.
    """
    if not directory.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")

    pattern = "**/*.mkv" if recursive else "*.mkv"
    mkv_files = sorted(directory.glob(pattern))

    summary = BatchUpscaleSummary()
    total = len(mkv_files)

    for index, source in enumerate(mkv_files, start=1):
        emit_progress(
            progress_callback,
            ProgressEvent(
                stage="upscale",
                current=index,
                total=total,
                item_name=source.name,
                status="start",
                message=str(source),
            ),
        )
        if dry_run:
            simulated_target = _resolve_output_path(source)
            result = UpscaleResult(
                status=UpscaleStatus.SKIPPED,
                source=source,
                target=simulated_target,
                message=f"Dry run: would process {source.name}",
            )
        else:
            result = upscale_dvd(source, opts=opts)
        summary.results.append(result)
        emit_progress(
            progress_callback,
            ProgressEvent(
                stage="upscale",
                current=index,
                total=total,
                item_name=source.name,
                status="success" if result.succeeded else "skipped" if result.skipped else "failed",
                message=result.message,
            ),
        )

    return summary
