# src/core/language_detection/__init__.py
"""
Language detection pipeline for unlabeled audio tracks.
Supports heuristic (filename/metadata), and Whisper (speech recognition) detection.
"""
from core.language_detection.audio_tagger import AudioTagger
from core.language_detection.detector_protocol import DetectorProtocol
from core.language_detection.heuristic_detector import HeuristicDetector
from core.language_detection.models import (
    BatchTaggingResult,
    DetectionMethod,
    DetectionRequest,
    LanguageDetectionResult,
    TaggingResult,
    TaggingStatus,
)
from core.language_detection.pipeline import LanguageDetectionPipeline
from core.language_detection.whisper_detector import WhisperLanguageDetector

__all__ = [
    "AudioTagger",
    "BatchTaggingResult",
    "DetectionMethod",
    "DetectionRequest",
    "DetectorProtocol",
    "HeuristicDetector",
    "LanguageDetectionPipeline",
    "LanguageDetectionResult",
    "TaggingResult",
    "TaggingStatus",
    "WhisperLanguageDetector",
]
