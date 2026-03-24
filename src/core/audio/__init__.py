"""
src/core/audio/

Core business logic for music processing.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .metadata import extract_audio_metadata_enhanced, AudioMetadataEnhanced
from .metadata_extractor import AudioFileMetadata, MetadataExtractor
from .library_scanner import LibraryScanner
from .csv_exporter import CSVExporter, CSVExportError
from .conversion import convert_audio
from .organization import organize_music
from .enhancement import (
    AudioEnhancementResult,
    enhance_audio_quality,
    improve_audio_file,
    improve_audio_library,
    normalize_audio,
    remove_silence,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .audio_tagger import AudioTagger

try:
    from .audio_tagger import AudioTagger
except ImportError:
    logger.debug("AudioTagger unavailable because optional tagging dependencies are not installed")

__all__ = [
    "extract_audio_metadata_enhanced",
    "AudioMetadataEnhanced",
    "AudioFileMetadata",
    "MetadataExtractor",
    "LibraryScanner",
    "CSVExporter",
    "CSVExportError",
    "convert_audio",
    "organize_music",
    "AudioEnhancementResult",
    "enhance_audio_quality",
    "improve_audio_file",
    "improve_audio_library",
    "normalize_audio",
    "remove_silence",
]

if "AudioTagger" in globals():
    __all__.append("AudioTagger")