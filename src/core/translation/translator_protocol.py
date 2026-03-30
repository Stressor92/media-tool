# src/core/translation/translator_protocol.py
from __future__ import annotations

from enum import Enum
from typing import Protocol, runtime_checkable


class TranslatorBackend(str, Enum):
    OPUS_MT = "opus-mt"
    ARGOS   = "argos"


@runtime_checkable
class TranslatorProtocol(Protocol):
    """
    Minimal interface for all translation backends.
    Both methods must be thread-safe.
    """

    def translate_batch(
        self,
        texts: list[str],
        source_lang: str,
        target_lang: str,
    ) -> list[str]:
        """
        Translates a list of texts.
        Input and output have exactly the same length.
        Empty strings are returned unchanged.
        """
        ...

    def is_language_pair_supported(
        self, source_lang: str, target_lang: str
    ) -> bool:
        """True if this backend supports the language pair."""
        ...
