"""
src/core/translation/

Offline subtitle translation using local AI models (Helsinki-NLP OPUS-MT or argostranslate).
No cloud, no API key required.
"""

from core.translation.models import (
    LanguagePair,
    SubtitleDocument,
    SubtitleFormat,
    SubtitleSegment,
    TranslationRequest,
    TranslationResult,
    TranslationStatus,
)
from core.translation.subtitle_translator import SubtitleTranslator
from core.translation.translator_factory import create_translator
from core.translation.translator_protocol import TranslatorBackend, TranslatorProtocol

__all__ = [
    "LanguagePair",
    "SubtitleDocument",
    "SubtitleFormat",
    "SubtitleSegment",
    "TranslationRequest",
    "TranslationResult",
    "TranslationStatus",
    "TranslatorBackend",
    "TranslatorProtocol",
    "SubtitleTranslator",
    "create_translator",
]
