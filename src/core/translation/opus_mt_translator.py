# src/core/translation/opus_mt_translator.py
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Model names on HuggingFace Hub
# Note: For de→en no tc-big variant exists; standard model is used for both sizes.
# For en→de there is a tc-big model by gsarti (transformer-big, BLEU ~43.7 vs ~35 standard).
_MODEL_MAP: dict[tuple[str, str], dict[str, str]] = {
    ("de", "en"): {
        "standard": "Helsinki-NLP/opus-mt-de-en",
        "big":      "Helsinki-NLP/opus-mt-de-en",  # no tc-big variant exists
    },
    ("en", "de"): {
        "standard": "Helsinki-NLP/opus-mt-en-de",
        "big":      "gsarti/opus-mt-tc-big-en-de",  # transformer-big, BLEU ~43.7 vs ~35
    },
}

_SUPPORTED_PAIRS = set(_MODEL_MAP.keys())


class OpusMtTranslator:
    """
    Translation backend based on Helsinki-NLP OPUS-MT models,
    executed via ctranslate2 for maximum GPU performance.

    Lazy-loading: The model is loaded on first translate_batch() call
    and kept in memory (singleton per language pair).
    """

    def __init__(
        self,
        model_cache_dir: Path | None = None,
        device: str = "auto",    # "auto" | "cuda" | "cpu"
        model_size: str = "big",
        inter_threads: int = 4,
    ) -> None:
        # Default: <repo>/src/utils/translate_models  (same folder used by 'subtitle download-models')
        _repo_model_dir = Path(__file__).parent.parent.parent / "utils" / "translate_models"
        self._cache_dir     = model_cache_dir or _repo_model_dir
        self._device        = device
        self._model_size    = model_size
        self._inter_threads = inter_threads
        self._loaded_models: dict[tuple[str, str], Any] = {}

    def _get_model(self, source_lang: str, target_lang: str) -> Any:
        key = (source_lang, target_lang)
        if key not in self._loaded_models:
            self._loaded_models[key] = self._load_model(source_lang, target_lang)
        return self._loaded_models[key]

    def _load_model(self, source_lang: str, target_lang: str) -> Any:
        """
        Loads tokenizer + CTranslate2 model.
        Converts automatically from HuggingFace format on first run.
        """
        try:
            import ctranslate2
            from transformers import MarianTokenizer
        except ImportError as e:
            raise RuntimeError(
                "opus-mt backend requires: pip install ctranslate2 transformers sentencepiece"
            ) from e

        key        = (source_lang, target_lang)
        model_name = _MODEL_MAP[key][self._model_size]
        model_dir  = self._cache_dir / model_name.replace("/", "--")

        if not model_dir.exists():
            logger.info("Converting %s to CTranslate2 format …", model_name)
            model_dir.mkdir(parents=True, exist_ok=True)
            # Helsinki-NLP models on HuggingFace use MarianMT (transformers) format
            converter = ctranslate2.converters.TransformersConverter(model_name, low_cpu_mem_usage=True)
            converter.convert(str(model_dir))
            # Save tokenizer vocab alongside the model
            from transformers import MarianTokenizer as _MT
            _MT.from_pretrained(model_name).save_pretrained(str(model_dir))

        resolved_device = self._device
        if resolved_device == "auto":
            resolved_device = "cuda" if self._is_cuda_available() else "cpu"

        logger.info("Loading model: %s [device=%s]", model_name, resolved_device)
        tokenizer = MarianTokenizer.from_pretrained(str(model_dir))
        translator = ctranslate2.Translator(
            str(model_dir),
            device=resolved_device,
            inter_threads=self._inter_threads,
        )
        return (translator, tokenizer)

    @staticmethod
    def _is_cuda_available() -> bool:
        try:
            import ctranslate2
            return int(ctranslate2.get_cuda_device_count()) > 0
        except Exception:
            return False

    def translate_batch(
        self,
        texts: list[str],
        source_lang: str,
        target_lang: str,
    ) -> list[str]:
        if not texts:
            return []

        translator, tokenizer = self._get_model(source_lang, target_lang)

        # Filter out empty strings, remember their positions
        indices_empty = {i for i, t in enumerate(texts) if not t.strip()}
        active_texts  = [t for i, t in enumerate(texts) if i not in indices_empty]

        if not active_texts:
            return texts[:]

        # Tokenize
        tokenized = tokenizer(active_texts, return_tensors=None, padding=False)
        input_tokens = [
            tokenizer.convert_ids_to_tokens(ids)
            for ids in tokenized["input_ids"]
        ]

        # Inference
        results = translator.translate_batch(input_tokens)

        # Detokenize
        translated_active = [
            tokenizer.decode(
                tokenizer.convert_tokens_to_ids(r.hypotheses[0]),
                skip_special_tokens=True,
            )
            for r in results
        ]

        # Merge results with empty-string placeholders
        output: list[str] = []
        active_iter = iter(translated_active)
        for i in range(len(texts)):
            output.append("" if i in indices_empty else next(active_iter))

        return output

    def is_language_pair_supported(self, source_lang: str, target_lang: str) -> bool:
        return (source_lang, target_lang) in _SUPPORTED_PAIRS
