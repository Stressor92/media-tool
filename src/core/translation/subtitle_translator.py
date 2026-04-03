# src/core/translation/subtitle_translator.py
"""
Orchestrates the full translation pipeline:

  Parse → TagProcessor.extract → ChunkBuilder → Translator
        → ChunkSplitter → TagProcessor.restore → Formatter → Write

Single public entry point for the rest of the project.
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from importlib import import_module
from importlib.util import find_spec
from pathlib import Path
from typing import Any, cast

from src.statistics import get_collector
from src.statistics.event_types import EventType

from core.translation.chunking import SubtitleChunk, build_chunks, split_translated_chunk
from core.translation.models import (
    LanguagePair,
    SubtitleDocument,
    SubtitleFormat,
    SubtitleSegment,
    TranslationRequest,
    TranslationResult,
    TranslationStatus,
)
from core.translation.subtitle_formatter import format_subtitle
from core.translation.subtitle_parser import parse_subtitle_file
from core.translation.subtitle_writer import write_subtitle_file
from core.translation.tag_processor import TagMapping, TagProcessor
from core.translation.translation_cache import TranslationCache
from core.translation.translator_factory import create_translator
from core.translation.translator_protocol import TranslatorProtocol

logger = logging.getLogger(__name__)

# Known language suffixes in stem names  (movie.en.srt -> "en")
_LANG_SUFFIX_RE = re.compile(r"\.(de|en|ger|eng)$", re.IGNORECASE)


class SubtitleTranslator:
    """
    Main orchestrator for subtitle translations.

    Supports:
    - Individual files (.srt, .ass, .vtt)
    - Batch processing of multiple files

    v2 features:
    - Context-aware chunking (better grammar / pronoun resolution)
    - Placeholder-based tag preservation (HTML + ASS tags)
    - Post-translation line wrapping
    - In-memory + optional JSON translation cache
    - Optional auto language detection (langdetect)
    """

    def __init__(
        self,
        translator: TranslatorProtocol | None = None,
        cache: TranslationCache | None = None,
        chunk_size: int = 4,
        max_chars_per_chunk: int = 250,
        preserve_tags: bool = True,
        line_wrap: bool = True,
        max_line_length: int = 40,
        max_lines: int = 2,
        auto_detect_language: bool = False,
    ) -> None:
        self._translator = translator
        self._cache = cache or TranslationCache()
        self._tag_processor = TagProcessor()
        self._chunk_size = chunk_size
        self._max_chars_per_chunk = max_chars_per_chunk
        self._preserve_tags = preserve_tags
        self._line_wrap = line_wrap
        self._max_line_length = max_line_length
        self._max_lines = max_lines
        self._auto_detect_language = auto_detect_language

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def translate_file(
        self,
        source_path: Path,
        language_pair: LanguagePair,
        output_path: Path | None = None,
        backend: str = "opus-mt",
        model_size: str = "big",
        overwrite: bool = False,
        dry_run: bool = False,
    ) -> TranslationResult:
        """
        Translate a single subtitle file.

        Output path convention:
          movie.de.srt  -> movie.en.srt
          subtitle.srt  -> subtitle.en.srt  (language suffix appended)
        """
        if not source_path.exists():
            return TranslationResult(
                status=TranslationStatus.FAILED,
                request=TranslationRequest(
                    document=SubtitleDocument([], SubtitleFormat.UNKNOWN),
                    language_pair=language_pair,
                ),
                error_message=f"File not found: {source_path}",
            )

        resolved_output = output_path or self._default_output_path(source_path, language_pair)

        if resolved_output.exists() and not overwrite:
            return TranslationResult(
                status=TranslationStatus.SKIPPED,
                request=TranslationRequest(
                    document=SubtitleDocument([], SubtitleFormat.UNKNOWN),
                    language_pair=language_pair,
                ),
                output_path=resolved_output,
                error_message="Output file already exists (use --overwrite to overwrite).",
            )

        doc = parse_subtitle_file(source_path)

        effective_pair = language_pair
        if self._auto_detect_language:
            detected = self._detect_language(doc.segments[:10])
            if detected and detected != language_pair.source:
                logger.warning(
                    "Auto-detected language '%s' differs from '--from %s'; using detected.",
                    detected,
                    language_pair.source,
                )
                effective_pair = LanguagePair(source=detected, target=language_pair.target)

        request = TranslationRequest(
            document=doc,
            language_pair=effective_pair,
            backend=backend,
            model_size=model_size,
        )

        if dry_run:
            return TranslationResult(
                status=TranslationStatus.SKIPPED,
                request=request,
                output_path=resolved_output,
                segments_translated=len(doc.segments),
                error_message="dry_run",
            )

        result = self._translate_and_write(request, resolved_output)
        if result.status == TranslationStatus.SUCCESS:
            try:
                get_collector().record(
                    EventType.SUBTITLE_TRANSLATED,
                    duration_seconds=result.duration_seconds,
                    source_language=effective_pair.source,
                    target_language=effective_pair.target,
                    backend=backend,
                )
            except Exception:
                logger.debug("Stats recording failed", exc_info=True)
        return result

    # ------------------------------------------------------------------
    # Core pipeline
    # ------------------------------------------------------------------

    def _translate_and_write(
        self,
        request: TranslationRequest,
        output_path: Path,
    ) -> TranslationResult:
        start = time.monotonic()
        translator = self._get_translator(request)
        doc = request.document
        pair = request.language_pair

        chunks = build_chunks(
            doc.segments,
            max_segments=self._chunk_size,
            max_chars=self._max_chars_per_chunk,
        )
        logger.info(
            "Translating %d segments in %d chunks [%s] via %s ...",
            len(doc.segments),
            len(chunks),
            pair,
            request.backend,
        )

        translated_by_index: dict[int, str] = {}
        for chunk in chunks:
            translated_by_index.update(self._translate_chunk(chunk, pair, translator))

        new_segments: list[SubtitleSegment] = []
        for idx, seg in enumerate(doc.segments):
            translated = translated_by_index.get(idx, seg.text)
            if self._line_wrap:
                translated = format_subtitle(
                    translated,
                    max_chars=self._max_line_length,
                    max_lines=self._max_lines,
                )
            new_segments.append(
                SubtitleSegment(
                    index=seg.index,
                    start=seg.start,
                    end=seg.end,
                    text=translated,
                    raw_tags=seg.raw_tags,
                )
            )

        translated_doc = SubtitleDocument(
            segments=new_segments,
            source_format=doc.source_format,
            source_path=output_path,
            language=pair.target,
            metadata=doc.metadata,
        )

        write_subtitle_file(translated_doc, output_path)
        elapsed = round(time.monotonic() - start, 1)

        logger.info(
            "Translation complete: %d segments in %.1fs -> %s",
            len(new_segments),
            elapsed,
            output_path.name,
        )

        return TranslationResult(
            status=TranslationStatus.SUCCESS,
            request=request,
            translated_document=translated_doc,
            output_path=output_path,
            segments_translated=len(new_segments),
            duration_seconds=elapsed,
        )

    def _translate_chunk(
        self,
        chunk: SubtitleChunk,
        pair: LanguagePair,
        translator: TranslatorProtocol,
    ) -> dict[int, str]:
        """
        Translate one chunk and return a mapping of segment_index -> translated_text.

        Steps:
          1. Extract tags -> placeholders (per-segment)
          2. Check cache per segment
          3. Send uncached segments (joined) to translator
          4. Split translated result back into per-segment strings
          5. Restore tags in each segment
          6. Store new translations in cache
        """
        tp = self._tag_processor

        clean_texts: list[str] = []
        tag_mappings_per_seg: list[list[TagMapping]] = []

        for orig_text in chunk.original_texts:
            if self._preserve_tags:
                result = tp.extract(orig_text)
                clean_texts.append(result.clean_text)
                tag_mappings_per_seg.append(result.mappings)
            else:
                clean_texts.append(orig_text)
                tag_mappings_per_seg.append([])

        translated_clean: list[str | None] = [self._cache.get(pair.source, pair.target, t) for t in clean_texts]

        uncached_indices = [i for i, v in enumerate(translated_clean) if v is None]
        uncached_texts = [clean_texts[i] for i in uncached_indices]

        if uncached_texts:
            combined = "\n".join(uncached_texts)
            [combined_translated] = translator.translate_batch(
                [combined],
                source_lang=pair.source,
                target_lang=pair.target,
            )
            mock_chunk = SubtitleChunk(
                segment_indices=uncached_indices,
                combined_text=combined,
                original_texts=uncached_texts,
            )
            per_segment = split_translated_chunk(mock_chunk, combined_translated)

            for local_i, seg_translation in zip(uncached_indices, per_segment, strict=False):
                translated_clean[local_i] = seg_translation
                self._cache.put(pair.source, pair.target, clean_texts[local_i], seg_translation)

        result_map: dict[int, str] = {}
        for local_i, global_i in enumerate(chunk.segment_indices):
            text = translated_clean[local_i] or clean_texts[local_i]
            if self._preserve_tags and tag_mappings_per_seg[local_i]:
                text = tp.restore(text, tag_mappings_per_seg[local_i])
            result_map[global_i] = text

        return result_map

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_translator(self, request: TranslationRequest) -> TranslatorProtocol:
        if self._translator is not None:
            return self._translator
        return create_translator(
            backend=request.backend,
            model_size=request.model_size,
        )

    @staticmethod
    def _detect_language(segments: list[SubtitleSegment]) -> str | None:
        """
        Use langdetect to detect the language of the first N segments.
        Returns an ISO 639-1 code, or None if detection fails / langdetect not installed.
        """
        try:
            if find_spec("langdetect") is None:
                return None

            module = import_module("langdetect")
            detect = cast(Callable[[str], Any], getattr(module, "detect", None))
            if detect is None:
                return None

            sample = " ".join(s.text for s in segments if s.text)
            if not sample.strip():
                return None
            return str(detect(sample))
        except Exception:
            return None

    @staticmethod
    def _default_output_path(source: Path, pair: LanguagePair) -> Path:
        """
        movie.en.srt  ->  movie.de.srt
        movie.srt     ->  movie.de.srt
        """
        clean_stem = _LANG_SUFFIX_RE.sub("", source.stem)
        return source.parent / f"{clean_stem}.{pair.target}{source.suffix}"
