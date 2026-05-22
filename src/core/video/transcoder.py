"""
src/core/video/transcoder.py

Core business logic for transcoding arbitrary video containers to H.265/HEVC
while preserving non-video streams.
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path

from core.video.encoder_profile_builder import EncoderParams, EncoderProfileBuilder
from core.video.models import EncoderType
from utils.ffmpeg_runner import FFmpegResult, run_ffmpeg
from utils.ffprobe_runner import probe_file

logger = logging.getLogger(__name__)

_VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".m4v", ".ts", ".m2ts"}


class TranscodeStatus(Enum):
    SUCCESS = auto()
    SKIPPED = auto()
    FAILED = auto()


@dataclass(frozen=True)
class TranscodeResult:
    status: TranscodeStatus
    source: Path
    target: Path
    message: str
    encoder_used: str = ""
    ffmpeg_result: FFmpegResult | None = None

    @property
    def succeeded(self) -> bool:
        return self.status == TranscodeStatus.SUCCESS

    @property
    def skipped(self) -> bool:
        return self.status == TranscodeStatus.SKIPPED

    @property
    def failed(self) -> bool:
        return self.status == TranscodeStatus.FAILED


@dataclass
class BatchTranscodeSummary:
    results: list[TranscodeResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def succeeded(self) -> list[TranscodeResult]:
        return [r for r in self.results if r.succeeded]

    @property
    def skipped(self) -> list[TranscodeResult]:
        return [r for r in self.results if r.skipped]

    @property
    def failed(self) -> list[TranscodeResult]:
        return [r for r in self.results if r.failed]


@dataclass(frozen=True)
class TranscodeOptions:
    profile: str = "brrip"
    overwrite: bool = False
    recursive: bool = False
    skip_if_hevc: bool = True
    force_software: bool = False
    preferred_encoder: str | None = None
    hw_fallback_on_error: bool = True


def _format_bytes(byte_count: int) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    size = float(max(0, byte_count))
    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{byte_count} B"


def _required_space_for_transcode(source: Path) -> int:
    # Conservative estimate: output may temporarily be near source size.
    source_size = source.stat().st_size
    return int(source_size * 1.20) + (512 * 1024 * 1024)


def _resolve_output_path(source: Path, output_root: Path | None = None) -> Path:
    output_name = f"{source.stem}.h265.mkv"
    if output_root is None:
        return source.with_name(output_name)
    return output_root / output_name


def _resolve_batch_output_path(source: Path, directory: Path, output_root: Path | None = None) -> Path:
    if output_root is None:
        return _resolve_output_path(source)

    relative_parent = source.relative_to(directory).parent
    output_name = f"{source.stem}.h265.mkv"
    return output_root / relative_parent / output_name


def _video_codec_name(source: Path) -> str | None:
    probe = probe_file(source)
    if probe.failed:
        return None

    video = probe.first_video()
    if not video:
        return None

    codec = video.get("codec_name")
    if isinstance(codec, str):
        return codec.lower()
    return None


def _build_ffmpeg_args(source: Path, target: Path, params: EncoderParams) -> list[str]:
    return [
        "-y",
        "-i",
        str(source),
        "-map",
        "0",
        *params.base_args,
        "-c:a",
        "copy",
        "-c:s",
        "copy",
        "-c:d",
        "copy",
        "-c:t",
        "copy",
        "-map_metadata",
        "0",
        "-map_chapters",
        "0",
        str(target),
    ]


def _build_encoder_params(opts: TranscodeOptions) -> EncoderParams:
    builder = EncoderProfileBuilder(
        profile=opts.profile,
        force_software=opts.force_software,
        preferred_encoder=opts.preferred_encoder,
    )
    return builder.build()


def transcode_to_h265(source: Path, target: Path | None = None, opts: TranscodeOptions | None = None) -> TranscodeResult:
    opts = opts or TranscodeOptions()
    target_path = target or _resolve_output_path(source)

    if not source.exists():
        return TranscodeResult(
            status=TranscodeStatus.FAILED,
            source=source,
            target=target_path,
            message=f"Source file not found: {source}",
        )

    if source.suffix.lower() not in _VIDEO_EXTENSIONS:
        return TranscodeResult(
            status=TranscodeStatus.SKIPPED,
            source=source,
            target=target_path,
            message=f"Unsupported extension: {source.suffix}",
        )

    codec_name = _video_codec_name(source)
    if opts.skip_if_hevc and codec_name in {"hevc", "h265"}:
        return TranscodeResult(
            status=TranscodeStatus.SKIPPED,
            source=source,
            target=target_path,
            message="Already HEVC/H.265 — skipping.",
        )

    if target_path.exists() and not opts.overwrite:
        return TranscodeResult(
            status=TranscodeStatus.SKIPPED,
            source=source,
            target=target_path,
            message=f"Target already exists: {target_path}",
        )

    target_path.parent.mkdir(parents=True, exist_ok=True)

    required_bytes = _required_space_for_transcode(source)
    free_bytes = shutil.disk_usage(target_path.parent).free
    if free_bytes < required_bytes:
        return TranscodeResult(
            status=TranscodeStatus.FAILED,
            source=source,
            target=target_path,
            message=(
                "Insufficient free disk space for transcode: "
                f"required about {_format_bytes(required_bytes)}, "
                f"available {_format_bytes(free_bytes)}."
            ),
        )

    params = _build_encoder_params(opts)
    ffmpeg_args = _build_ffmpeg_args(source, target_path, params)
    ffmpeg_result = run_ffmpeg(ffmpeg_args)

    if ffmpeg_result.success:
        return TranscodeResult(
            status=TranscodeStatus.SUCCESS,
            source=source,
            target=target_path,
            message=f"Transcoded to H.265 successfully: {target_path.name}",
            encoder_used=params.encoder,
            ffmpeg_result=ffmpeg_result,
        )

    if opts.hw_fallback_on_error and params.encoder_type != EncoderType.SOFTWARE:
        logger.warning("Hardware transcode failed for %s, retrying with software encoder", source)
        software_opts = TranscodeOptions(
            profile=opts.profile,
            overwrite=True,
            recursive=opts.recursive,
            skip_if_hevc=False,
            force_software=True,
            preferred_encoder="software",
            hw_fallback_on_error=False,
        )
        software_params = _build_encoder_params(software_opts)
        software_result = run_ffmpeg(_build_ffmpeg_args(source, target_path, software_params))
        if software_result.success:
            return TranscodeResult(
                status=TranscodeStatus.SUCCESS,
                source=source,
                target=target_path,
                message=f"Transcoded to H.265 (software fallback): {target_path.name}",
                encoder_used=software_params.encoder,
                ffmpeg_result=software_result,
            )

        ffmpeg_result = software_result

    if target_path.exists():
        target_path.unlink(missing_ok=True)

    return TranscodeResult(
        status=TranscodeStatus.FAILED,
        source=source,
        target=target_path,
        message=(f"ffmpeg failed (exit {ffmpeg_result.return_code}). See logs for details."),
        encoder_used=params.encoder,
        ffmpeg_result=ffmpeg_result,
    )


def batch_transcode_to_h265(
    directory: Path,
    output_root: Path | None = None,
    opts: TranscodeOptions | None = None,
) -> BatchTranscodeSummary:
    opts = opts or TranscodeOptions()
    summary = BatchTranscodeSummary()

    if not directory.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")

    pattern = "**/*" if opts.recursive else "*"
    files = [
        p
        for p in sorted(directory.glob(pattern))
        if p.is_file() and p.suffix.lower() in _VIDEO_EXTENSIONS
    ]

    for source in files:
        target = _resolve_batch_output_path(source, directory, output_root=output_root)
        result = transcode_to_h265(source, target, opts=opts)
        summary.results.append(result)

    return summary
