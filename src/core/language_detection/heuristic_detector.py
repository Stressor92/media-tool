# src/core/language_detection/heuristic_detector.py
"""
Stufe 1: Spracherkennung aus Metadaten, Dateinamen und Ordnerstruktur.
Extrem schnell (< 1ms), hohe Konfidenz bei eindeutigen Mustern.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from core.language_detection.models import DetectionMethod, LanguageDetectionResult

# Muster → (ISO 639-2, Konfidenz)
_FILENAME_PATTERNS: list[tuple[re.Pattern[str], str, float]] = [
    (re.compile(r"[.\[( _-](german|deutsch|ger|deu)[.\])\-_ ]", re.I), "ger", 0.97),
    (re.compile(r"[.\[( _-](english|eng)[.\])\-_ ]", re.I), "eng", 0.97),
    (re.compile(r"[.\[( _-](french|fre|fra)[.\])\-_ ]", re.I), "fra", 0.97),
    (re.compile(r"[.\[( _-](spanish|spa|esp)[.\])\-_ ]", re.I), "spa", 0.97),
    (re.compile(r"[.\[( _-](italian|ita)[.\])\-_ ]", re.I), "ita", 0.97),
    (re.compile(r"[.\[( _-](japanese|jpn|jap)[.\])\-_ ]", re.I), "jpn", 0.97),
    # Doppelsprachigkeit (z. B. "[DE-EN]")
    (re.compile(r"\[DE\]", re.I), "ger", 0.95),
    (re.compile(r"\[EN\]", re.I), "eng", 0.95),
    (re.compile(r"\.de\.", re.I), "ger", 0.90),
    (re.compile(r"\.en\.", re.I), "eng", 0.90),
]

# Containersprachen → ISO 639-2 Mapping
_CONTAINER_LANG_MAP: dict[str, str] = {
    "german": "ger",
    "deutsch": "ger",
    "de": "ger",
    "deu": "ger",
    "ger": "ger",
    "english": "eng",
    "en": "eng",
    "eng": "eng",
    "french": "fra",
    "fr": "fra",
    "fre": "fra",
    "fra": "fra",
    "spanish": "spa",
    "es": "spa",
    "spa": "spa",
    "italian": "ita",
    "it": "ita",
    "ita": "ita",
    "japanese": "jpn",
    "ja": "jpn",
    "jpn": "jpn",
}


class HeuristicDetector:
    """Stufe-1-Erkennung ohne Audio-Analyse."""

    def detect_from_path(
        self,
        video_path: Path,
        stream_index: int = 0,
        probe: Mapping[str, Any] | None = None,
    ) -> LanguageDetectionResult | None:
        """
        Versucht die Sprache aus Pfad, Dateiname und Container-Tags zu lesen.
        Gibt None zurück wenn keine eindeutige Erkennung möglich.
        """
        # 1. Container-Metadaten (ffprobe-Ergebnis)
        if probe:
            result = self._from_container_tags(probe, stream_index)
            if result:
                return result

        # 2. Dateiname
        result = self._from_filename(video_path)
        if result:
            return result

        # 3. Ordnerpfad (z. B. "German Audio/" oder "[DE]" im Pfad)
        return self._from_directory(video_path)

    def _from_container_tags(self, probe: Mapping[str, Any], stream_index: int) -> LanguageDetectionResult | None:
        raw_streams = probe.get("streams", [])
        if not isinstance(raw_streams, list):
            return None

        streams: list[dict[str, Any]] = [
            s for s in raw_streams if isinstance(s, dict) and s.get("codec_type") == "audio"
        ]
        if stream_index >= len(streams):
            return None

        stream = streams[stream_index]
        raw_lang = (stream.get("tags", {}) or {}).get("language", "").lower().strip()

        if raw_lang and raw_lang not in {"und", "unknown", ""}:
            normalized = _CONTAINER_LANG_MAP.get(raw_lang, raw_lang[:3])
            return LanguageDetectionResult(
                language=normalized,
                confidence=0.99,  # Direktes Container-Tag ist sehr verlässlich
                method=DetectionMethod.HEURISTIC,
                stream_index=stream_index,
            )
        return None

    def _from_filename(self, path: Path) -> LanguageDetectionResult | None:
        name = path.name
        for pattern, lang, conf in _FILENAME_PATTERNS:
            if pattern.search(name):
                return LanguageDetectionResult(
                    language=lang,
                    confidence=conf,
                    method=DetectionMethod.HEURISTIC,
                )
        return None

    def _from_directory(self, path: Path) -> LanguageDetectionResult | None:
        full_path = str(path).lower()
        for pattern, lang, conf in _FILENAME_PATTERNS:
            if pattern.search(full_path):
                return LanguageDetectionResult(
                    language=lang,
                    confidence=conf * 0.85,  # Pfad ist weniger verlässlich als Dateiname
                    method=DetectionMethod.HEURISTIC,
                )
        return None

    def detect(
        self,
        audio_sample: Path,
        hint_languages: list[str] | None = None,
    ) -> LanguageDetectionResult:
        # Fallback für Protocol-Kompatibilität — Heuristik braucht kein Audio
        return LanguageDetectionResult(language="und", confidence=0.0, method=DetectionMethod.UNKNOWN)
