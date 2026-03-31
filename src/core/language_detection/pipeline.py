# src/core/language_detection/pipeline.py
from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from core.language_detection.detector_protocol import DetectorProtocol
from core.language_detection.heuristic_detector import HeuristicDetector
from core.language_detection.models import (
    DetectionMethod,
    DetectionRequest,
    LanguageDetectionResult,
)
from utils.audio_sampler import extract_audio_sample

logger = logging.getLogger(__name__)

_UNKNOWN_RESULT = LanguageDetectionResult(
    language="und",
    confidence=0.0,
    method=DetectionMethod.UNKNOWN,
)


class LanguageDetectionPipeline:
    """
    Führt die Stufenpipeline aus:
    Heuristik → [AcoustID] → Whisper

    Das Modell für Whisper wird erst geladen wenn die
    Heuristik nicht confident genug war.
    """

    def __init__(
        self,
        min_confidence: float = 0.85,
        whisper_model_size: str = "medium",
        whisper_detector: DetectorProtocol | None = None,
    ) -> None:
        self._min_confidence = min_confidence
        self._heuristic = HeuristicDetector()
        self._whisper = whisper_detector   # Lazy-init wenn None
        self._whisper_model_size = whisper_model_size

    def detect(
        self,
        request: DetectionRequest,
        probe: Mapping[str, Any] | None = None,
    ) -> LanguageDetectionResult:
        """
        Führt die Pipeline für eine einzelne Audiospur aus.
        """
        # ── Stufe 1: Heuristik ────────────────────────────────────────
        if not request.force_whisper:
            result = self._heuristic.detect_from_path(
                request.video_path,
                request.stream_index,
                probe=probe,
            )
            if result and result.confidence >= self._min_confidence:
                logger.info(
                    "Sprache via Heuristik erkannt: %s (%.0f%%)",
                    result.language, result.confidence * 100,
                )
                return result

        # ── Stufe 3: Whisper ──────────────────────────────────────────
        logger.info(
            "Heuristik nicht confident genug — starte Whisper für '%s' (Spur %d) …",
            request.video_path.name, request.stream_index,
        )
        audio_sample: Path | None = None
        try:
            audio_sample = extract_audio_sample(
                request.video_path,
                duration=request.sample_duration,
                offset=request.sample_offset,
                stream_index=request.stream_index,
            )
            whisper = self._get_whisper()
            result = whisper.detect(audio_sample)

            if result.confidence >= request.min_confidence:
                return result

            logger.warning(
                "Whisper unter Konfidenz-Schwelle: %s (%.0f%% < %.0f%%)",
                result.language, result.confidence * 100, request.min_confidence * 100,
            )
            return result   # Gib es trotzdem zurück, Tagger entscheidet

        except Exception as exc:
            logger.exception("Whisper-Erkennung fehlgeschlagen: %s", exc)
            return _UNKNOWN_RESULT
        finally:
            if audio_sample and audio_sample.exists():
                os.unlink(audio_sample)

    def _get_whisper(self) -> DetectorProtocol:
        if self._whisper is None:
            from core.language_detection.whisper_detector import WhisperLanguageDetector
            self._whisper = WhisperLanguageDetector(
                model_size=self._whisper_model_size
            )
        return self._whisper
