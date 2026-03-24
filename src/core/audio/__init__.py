"""
src/core/audio/

Core business logic for music processing.
"""

from .metadata import extract_audio_metadata_enhanced, AudioMetadataEnhanced
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
from .audio_tagger import AudioTagger

__all__ = [
    "extract_audio_metadata_enhanced",
    "AudioMetadataEnhanced",
    "convert_audio",
    "organize_music",
    "AudioEnhancementResult",
    "enhance_audio_quality",
    "improve_audio_file",
    "improve_audio_library",
    "normalize_audio",
    "remove_silence",
    "AudioTagger",
]