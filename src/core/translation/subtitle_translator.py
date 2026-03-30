# src/core/translation/subtitle_translator.py
"""
Orchestrates: Parse → Translate → Write.
Single public entry point for the rest of the project.
"""
from __future__ import annotations

import logging
import re
import time
from pathlib import Path

from core.translation.models import (
    LanguagePair,
    SubtitleDocument,
    SubtitleFormat,
    SubtitleSegment,
    TranslationRequest,
    TranslationResult,
    TranslationStatus,
)
from core.translation.subtitle_parser import parse_subtitle_file
from core.translation.subtitle_writer import write_subtitle_file
from core.translation.translator_factory import create_translator
from core.translation.translator_protocol import TranslatorProtocol

logger = logging.getLogger(__name__)

# HTML-like tags in subtitles (<i>, <b>, <u>, <font …>)
_TAG_RE = re.compile(r"(<[^>]+>)")

# Known language suffixes in stem names
_LANG_SUFFIX_RE = re.compile(r"\.(de|en|ger|eng)$", re.IGNORECASE)


def _strip_tags(text: str) -> tuple[str, list[tuple[int, str]]]:
    """Removes tags and remembers their positions for roundtrip."""
    tags: list[tuple[int, str]] = []
    for m in _TAG_RE.finditer(text):
        tags.append((m.start(), m.group()))
    clean = _TAG_RE.sub("", text)
    return clean, tags


def _restore_tags(translated: str, tags: list[tuple[int, str]]) -> str:
    """Re-inserts tags after translation at approximately the right position."""
    if not tags:
        return translated
    prefix_tags = [t for pos, t in tags if pos == 0]
    suffix_tags = [t for pos, t in tags if pos != 0]
    return "".join(prefix_tags) + translated + "".join(suffix_tags)


class SubtitleTranslator:
    """
    Main orchestrator for subtitle translations.

    Supports:
    - Individual files (.srt, .ass, .vtt)
    - Batch processing of multiple files
    """

    def __init__(self, translator: TranslatorProtocol | None = None) -> None:
        self._translator = translator

    def _get_translator(self, request: TranslationRequest) -> TranslatorProtocol:
        if self._translator is not None:
            return self._translator
        return create_translator(
            backend=request.backend,
            model_size=request.model_size,
        )

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
        Translates a single subtitle file.

        Output path convention:
          movie.de.srt  → movie.en.srt
          subtitle.srt  → subtitle.en.srt  (language is appended)
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

        resolved_output = output_path or self._default_output_path(
            source_path, language_pair
        )

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
        request = TranslationRequest(
            document=doc,
            language_pair=language_pair,
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

        return self._translate_and_write(request, resolved_output)

    def _translate_and_write(
        self,
        request: TranslationRequest,
        output_path: Path,
    ) -> TranslationResult:
        start = time.monotonic()
        translator = self._get_translator(request)
        doc = request.document
        pair = request.language_pair

        # Extract texts, strip tags
        raw_texts: list[str] = []
        tag_maps: list[list[tuple[int, str]]] = []

        for seg in doc.segments:
            clean, tags = _strip_tags(seg.text)
            raw_texts.append(clean)
            tag_maps.append(tags)

        # Batch translation
        logger.info(
            "Translating %d segments [%s] via %s …",
            len(raw_texts), pair, request.backend,
        )
        translated_texts = translator.translate_batch(
            raw_texts,
            source_lang=pair.source,
            target_lang=pair.target,
        )

        # Assemble new document
        new_segments: list[SubtitleSegment] = []
        for seg, translated, tags in zip(doc.segments, translated_texts, tag_maps):
            new_segments.append(SubtitleSegment(
                index=seg.index,
                start=seg.start,
                end=seg.end,
                text=_restore_tags(translated, tags),
                raw_tags=seg.raw_tags,
            ))

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
            "Translation complete: %d segments in %.1fs → %s",
            len(new_segments), elapsed, output_path.name,
        )

        return TranslationResult(
            status=TranslationStatus.SUCCESS,
            request=request,
            translated_document=translated_doc,
            output_path=output_path,
            segments_translated=len(new_segments),
            duration_seconds=elapsed,
        )

    @staticmethod
    def _default_output_path(source: Path, pair: LanguagePair) -> Path:
        """
        movie.en.srt  →  movie.de.srt
        movie.srt     →  movie.de.srt
        """
        clean_stem = _LANG_SUFFIX_RE.sub("", source.stem)
        return source.parent / f"{clean_stem}.{pair.target}{source.suffix}"
