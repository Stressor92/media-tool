# src/core/translation/translator_factory.py
from __future__ import annotations

from pathlib import Path

from core.translation.translator_protocol import TranslatorBackend, TranslatorProtocol


def create_translator(
    backend: str | TranslatorBackend = TranslatorBackend.OPUS_MT,
    model_size: str = "big",
    device: str = "auto",
    model_cache_dir: Path | None = None,
) -> TranslatorProtocol:
    """
    Creates the configured translator.

    Args:
        backend:         "opus-mt" (default) or "argos" (fallback)
        model_size:      "standard" or "big" (opus-mt only)
        device:          "auto" | "cuda" | "cpu"
        model_cache_dir: Custom model cache path (overrides default)

    Returns:
        An instance implementing TranslatorProtocol.
    """
    backend_enum = TranslatorBackend(backend)

    if backend_enum == TranslatorBackend.OPUS_MT:
        from core.translation.opus_mt_translator import OpusMtTranslator

        return OpusMtTranslator(
            model_cache_dir=model_cache_dir,
            device=device,
            model_size=model_size,
        )

    if backend_enum == TranslatorBackend.ARGOS:
        from core.translation.argos_translator import ArgosTranslator

        return ArgosTranslator()

    raise ValueError(f"Unknown backend: {backend!r}")
