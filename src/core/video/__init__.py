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
from .movie_folder_scanner import (
    MovieFolder,
    MovieFolderScanner,
)
from .subtitle_generator import (
    GenerationResult,
    SubtitleGenerator,
)
from .subtitle_processor import (
    SubtitleTimingProcessor,
)
from .trailer_downloader import (
    TrailerDownloadResult,
    TrailerDownloadService,
)
from .trailer_search import (
    TrailerSearchResult,
    TrailerSearchService,
)
from .upscale_profiles import (
    BUILTIN_PROFILES,
    UpscaleProfile,
    get_profile,
    resolve_upscale_options,
)
from .upscaler import (
    BatchUpscaleSummary,
    UpscaleOptions,
    UpscaleResult,
    UpscaleStatus,
    batch_upscale_directory,
    upscale_dvd,
)
from .whisper_engine import (
    HallucinationDetector,
    HallucinationWarning,
    TranscriptionResult,
    WhisperConfig,
    WhisperEngine,
    WhisperModel,
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
    # Upscale profiles
    "BUILTIN_PROFILES",
    "UpscaleProfile",
    "get_profile",
    "resolve_upscale_options",
    # Whisper Engine
    "HallucinationDetector",
    "HallucinationWarning",
    "TranscriptionResult",
    "WhisperConfig",
    "WhisperEngine",
    "WhisperModel",
    # Subtitle Generator
    "GenerationResult",
    "SubtitleGenerator",
    # Subtitle Processor
    "SubtitleTimingProcessor",
    # Trailer workflow
    "MovieFolder",
    "MovieFolderScanner",
    "TrailerSearchResult",
    "TrailerSearchService",
    "TrailerDownloadResult",
    "TrailerDownloadService",
]
