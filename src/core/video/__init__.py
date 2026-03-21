"""
src/core/video/

Core business logic for video processing.
"""

from .converter import (
    BatchConversionSummary,
    ConversionResult,
    ConversionStatus,
    batch_convert_directory,
    convert_mp4_to_mkv,
    resolve_output_path,
)
from .inspector import (
    VIDEO_EXTENSIONS,
    VideoInfo,
    export_to_csv,
    inspect_file,
    scan_directory,
)
from .merger import (
    MergeResult,
    MergeStatus,
    derive_output_name,
    detect_language_files,
    merge_directory,
    merge_dual_audio,
)
from .upscaler import (
    BatchUpscaleSummary,
    UpscaleOptions,
    UpscaleResult,
    UpscaleStatus,
    batch_upscale_directory,
    upscale_dvd,
)

__all__ = [
    # Converter
    "BatchConversionSummary",
    "ConversionResult",
    "ConversionStatus",
    "batch_convert_directory",
    "convert_mp4_to_mkv",
    "resolve_output_path",
    # Inspector
    "VIDEO_EXTENSIONS",
    "VideoInfo",
    "export_to_csv",
    "inspect_file",
    "scan_directory",
    # Merger
    "MergeResult",
    "MergeStatus",
    "derive_output_name",
    "detect_language_files",
    "merge_directory",
    "merge_dual_audio",
    # Upscaler
    "BatchUpscaleSummary",
    "UpscaleOptions",
    "UpscaleResult",
    "UpscaleStatus",
    "batch_upscale_directory",
    "upscale_dvd",
]