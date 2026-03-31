# src/core/language_detection/detector_protocol.py
from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from core.language_detection.models import LanguageDetectionResult


@runtime_checkable
class DetectorProtocol(Protocol):
    """
    Interface für alle Erkennungs-Backends.
    Jede Implementierung bekommt einen Audio-Beispiel-Pfad (WAV)
    und gibt ein LanguageDetectionResult zurück.
    """

    def detect(
        self,
        audio_sample: Path,
        hint_languages: list[str] | None = None,
    ) -> LanguageDetectionResult:
        """
        Erkennt die Sprache einer Audio-Datei.

        Args:
            audio_sample:    Pfad zur temporären WAV-Datei (16kHz, Mono)
            hint_languages:  Bevorzugte Sprachen (reduziert Suchraum)

        Returns:
            LanguageDetectionResult mit confidence und method
        """
        ...
