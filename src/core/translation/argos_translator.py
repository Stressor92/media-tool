# src/core/translation/argos_translator.py
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_SUPPORTED_PAIRS = {("de", "en"), ("en", "de")}


class ArgosTranslator:
    """
    Fallback backend via argostranslate.
    No CUDA required, fully portable.
    Significantly slower than OpusMT (~10–30 seg/s on CPU).
    """

    def __init__(self) -> None:
        self._initialized = False

    def _ensure_initialized(self, source_lang: str, target_lang: str) -> None:
        if self._initialized:
            return
        try:
            import argostranslate.package
            import argostranslate.translate
        except ImportError as e:
            raise RuntimeError(
                "argos backend requires: pip install argostranslate"
            ) from e

        installed = argostranslate.translate.get_installed_languages()
        codes = {lang.code for lang in installed}

        if source_lang not in codes or target_lang not in codes:
            logger.info("Downloading argostranslate package %s→%s …", source_lang, target_lang)
            argostranslate.package.update_package_index()
            available = argostranslate.package.get_available_packages()
            pkg = next(
                (p for p in available if p.from_code == source_lang and p.to_code == target_lang),
                None,
            )
            if pkg is None:
                raise RuntimeError(f"No argostranslate package for {source_lang}→{target_lang}")
            argostranslate.package.install_from_path(pkg.download())

        self._initialized = True

    def translate_batch(
        self,
        texts: list[str],
        source_lang: str,
        target_lang: str,
    ) -> list[str]:
        import argostranslate.translate

        self._ensure_initialized(source_lang, target_lang)

        installed = argostranslate.translate.get_installed_languages()
        src_lang_obj = next(l for l in installed if l.code == source_lang)
        tgt_lang_obj = next(l for l in installed if l.code == target_lang)
        translation = src_lang_obj.get_translation(tgt_lang_obj)

        return [
            translation.translate(t) if t.strip() else t
            for t in texts
        ]

    def is_language_pair_supported(self, source_lang: str, target_lang: str) -> bool:
        return (source_lang, target_lang) in _SUPPORTED_PAIRS
