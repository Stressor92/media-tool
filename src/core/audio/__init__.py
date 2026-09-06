"""
src/core/audio/

Core business logic for music processing.
"""

from __future__ import annotations

import logging

from .bpm_tagger import BPMTagger, BPMTaggingResult, BPMTaggingStatus
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
from .genre_normalizer import (
    GenreNormalizationFileResult,
    GenreNormalizationRun,
    GenreNormalizationStatus,
    GenreNormalizer,
    GenreReportPaths,
)
from .library_scanner import LibraryScanner
from .metadata import AudioMetadataEnhanced, extract_audio_metadata_enhanced
from .metadata_extractor import AudioFileMetadata, MetadataExtractor
from .mp3gain_normalizer import MP3GainFileResult, MP3GainNormalizer, MP3GainStatus
from .organization import organize_music
from .unsorted_music_organizer import SortSummary, organize_unsorted_music

logger = logging.getLogger(__name__)

__all__ = [
    "BPMTagger",
    "BPMTaggingResult",
    "BPMTaggingStatus",
    "MP3GainNormalizer",
    "MP3GainFileResult",
    "MP3GainStatus",
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
    "GenreNormalizer",
    "GenreNormalizationStatus",
    "GenreNormalizationFileResult",
    "GenreNormalizationRun",
    "GenreReportPaths",
    "organize_unsorted_music",
    "SortSummary",
]

try:
    from . import audio_tagger as _audio_tagger
except ImportError:
    logger.debug("AudioTagger unavailable because optional tagging dependencies are not installed")
else:
    AudioTagger = _audio_tagger.AudioTagger
    __all__.append("AudioTagger")
