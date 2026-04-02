"""
src/core/audio/

Core business logic for music processing.
"""

from __future__ import annotations

import logging

from .conversion import convert_audio
from .csv_exporter import CSVExporter, CSVExportError
from .enhancement import (
    AudioEnhancementResult,
    enhance_audio_quality,
    improve_audio_file,
    improve_audio_library,
    normalize_audio,
    remove_silence,
)
from .library_scanner import LibraryScanner
from .metadata import AudioMetadataEnhanced, extract_audio_metadata_enhanced
from .metadata_extractor import AudioFileMetadata, MetadataExtractor
from .organization import organize_music

logger = logging.getLogger(__name__)

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

try:
    from . import audio_tagger as _audio_tagger
except ImportError:
    logger.debug("AudioTagger unavailable because optional tagging dependencies are not installed")
else:
    AudioTagger = _audio_tagger.AudioTagger
    __all__.append("AudioTagger")
