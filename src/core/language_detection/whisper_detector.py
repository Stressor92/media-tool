# src/core/language_detection/whisper_detector.py
"""
Stufe 3: Spracherkennung via faster-whisper detect_language().

Whisper analysiert das Audio-Sample und gibt Wahrscheinlichkeiten
für alle unterstützten Sprachen zurück. Kein Transkriptions-Overhead —
nur die Spracherkennung wird ausgeführt (deutlich schneller).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from core.language_detection.models import DetectionMethod, LanguageDetectionResult

logger = logging.getLogger(__name__)

# Whisper → ISO 639-2 Mapping (Whisper nutzt ISO 639-1)
_WHISPER_TO_ISO639_2: dict[str, str] = {
    "de": "ger", "en": "eng", "fr": "fra", "es": "spa",
    "it": "ita", "pt": "por", "nl": "nld", "pl": "pol",
    "ru": "rus", "ja": "jpn", "zh": "zho", "ko": "kor",
    "ar": "ara", "tr": "tur", "sv": "swe", "da": "dan",
    "fi": "fin", "no": "nor", "cs": "ces", "hu": "hun",
}


class WhisperLanguageDetector:
    """
    Nutzt faster-whisper ausschließlich für die Spracherkennung.
    Das Modell wird beim ersten Aufruf geladen (Lazy-Loading).

    Der Unterschied zur Transkription: detect_language() läuft in
    < 1 Sekunde pro 30s Sample, da nur ein Forward-Pass des Encoders
    nötig ist — kein Beam Search / Decoder.
    """

    def __init__(
        self,
        model_size: str = "medium",   # "medium" reicht für Spracherkennung
        device: str = "auto",
        compute_type: str = "float16",
    ) -> None:
        self._model_size   = model_size
        self._device       = device
        self._compute_type = compute_type
        self._model: Any   = None

    def _ensure_model(self) -> Any:
        if self._model is not None:
            return self._model

        try:
            from faster_whisper import WhisperModel
        except ImportError as e:
            raise RuntimeError(
                "faster-whisper nicht installiert: pip install faster-whisper"
            ) from e

        device = self._device
        if device == "auto":
            try:
                import ctranslate2
                device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
            except Exception:
                device = "cpu"

        logger.info(
            "Lade Whisper '%s' [device=%s, compute=%s] …",
            self._model_size, device, self._compute_type,
        )
        self._model = WhisperModel(
            self._model_size,
            device=device,
            compute_type=self._compute_type if device == "cuda" else "int8",
        )
        return self._model

    def detect(
        self,
        audio_sample: Path,
        hint_languages: list[str] | None = None,
    ) -> LanguageDetectionResult:
        model = self._ensure_model()

        logger.debug("Whisper Spracherkennung: %s", audio_sample.name)

        # transcribe() mit beam_size=1 — minimaler Aufwand für reine Spracherkennung
        segments, info = model.transcribe(
            str(audio_sample),
            task="transcribe",
            language=None,           # Auto-Detection
            beam_size=1,             # Minimal für reine Spracherkennung
            best_of=1,
            without_timestamps=True,
        )
        # Consume segments to trigger detection (lazy generator)
        _ = list(segments)

        detected_lang_iso1 = info.language
        confidence         = info.language_probability

        detected_lang = _WHISPER_TO_ISO639_2.get(detected_lang_iso1, detected_lang_iso1)

        # Alle Scores aus info (falls verfügbar)
        raw_scores: dict[str, float] = dict(getattr(info, "all_language_probs", {}) or {})
        alternatives = tuple(
            (_WHISPER_TO_ISO639_2.get(lang, lang), prob)
            for lang, prob in sorted(raw_scores.items(), key=lambda x: -x[1])[:5]
            if lang != detected_lang_iso1
        )

        logger.info(
            "Whisper erkannt: %s (%.1f%%)", detected_lang, confidence * 100
        )

        return LanguageDetectionResult(
            language=detected_lang,
            confidence=confidence,
            method=DetectionMethod.WHISPER,
            raw_scores=raw_scores,
            alternatives=alternatives,
        )
