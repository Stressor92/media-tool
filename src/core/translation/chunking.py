# src/core/translation/chunking.py
"""
Context-aware chunking for subtitle translation.

Problem: translating one segment at a time loses sentence context, harming
grammar, pronoun resolution, and flow.

Solution: group consecutive segments into "chunks" that are sent to the
translator together, then redistribute the translated text back to the
original segment positions.

Design principles:
  - max N segments per chunk (default 4)
  - max M characters combined (default 250)
  - break on sentence-end punctuation (. ! ?) when possible
  - safe fallback: if line count after translation doesn't match, distribute
    by proportion of original text lengths
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from core.translation.models import SubtitleSegment

# Sentence-ending punctuation
_SENTENCE_END_RE = re.compile(r"[.!?]\s*$")


@dataclass
class SubtitleChunk:
    """A group of consecutive subtitle segments sent for translation together."""
    segment_indices: list[int]          # Positions in the original segments list
    combined_text: str                  # Segments joined by "\n"
    original_texts: list[str] = field(default_factory=list)  # Individual segment texts


def build_chunks(
    segments: list[SubtitleSegment],
    max_segments: int = 4,
    max_chars: int = 250,
) -> list[SubtitleChunk]:
    """
    Group *segments* into translation chunks.

    A new chunk is started when:
    - adding the next segment would exceed *max_segments*, or
    - adding the next segment would exceed *max_chars* total, or
    - the current segment ends with sentence-ending punctuation (.!?)

    Parameters
    ----------
    segments:     Full list of subtitle segments.
    max_segments: Maximum number of segments per chunk.
    max_chars:    Maximum combined character count per chunk.

    Returns
    -------
    List of SubtitleChunk objects covering all segments in order.
    """
    chunks: list[SubtitleChunk] = []
    current_indices: list[int] = []
    current_texts: list[str] = []
    current_chars = 0

    for idx, seg in enumerate(segments):
        text = seg.text.strip()
        text_len = len(text)

        # Check if we should start a new chunk
        should_break = (
            len(current_texts) >= max_segments
            or (current_chars + text_len + 1 > max_chars and current_texts)
        )

        if should_break:
            chunks.append(_make_chunk(current_indices, current_texts))
            current_indices = []
            current_texts = []
            current_chars = 0

        current_indices.append(idx)
        current_texts.append(text)
        current_chars += text_len + 1  # +1 for separator

        # End chunk at sentence boundary if we already have ≥2 segments
        if len(current_texts) >= 2 and _SENTENCE_END_RE.search(text):
            chunks.append(_make_chunk(current_indices, current_texts))
            current_indices = []
            current_texts = []
            current_chars = 0

    if current_texts:
        chunks.append(_make_chunk(current_indices, current_texts))

    return chunks


def split_translated_chunk(
    chunk: SubtitleChunk,
    translated_text: str,
) -> list[str]:
    """
    Redistribute *translated_text* back into one string per original segment.

    Strategy:
    1. Split on newlines → if count matches, use directly.
    2. Otherwise fall back to proportional distribution by character count
       of original texts.

    Returns a list of translated strings, one per segment in the chunk.
    """
    n = len(chunk.segment_indices)
    lines = [l.strip() for l in translated_text.split("\n") if l.strip()]

    if len(lines) == n:
        return lines

    # Fallback: proportional split
    return _proportional_split(translated_text, chunk.original_texts)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_chunk(indices: list[int], texts: list[str]) -> SubtitleChunk:
    return SubtitleChunk(
        segment_indices=list(indices),
        combined_text="\n".join(texts),
        original_texts=list(texts),
    )


def _proportional_split(translated: str, originals: list[str]) -> list[str]:
    """
    Distribute *translated* proportionally across *originals*.

    The translated text is split into words; each original segment receives
    a number of words proportional to its character length.
    """
    if not originals:
        return [translated]

    total_original = sum(len(t) for t in originals) or 1
    words = translated.split()
    total_words = len(words)

    result: list[str] = []
    word_pos = 0

    for i, orig in enumerate(originals):
        if i == len(originals) - 1:
            # Last segment gets all remaining words
            result.append(" ".join(words[word_pos:]))
        else:
            share = len(orig) / total_original
            n_words = max(1, round(total_words * share))
            result.append(" ".join(words[word_pos: word_pos + n_words]))
            word_pos += n_words

    return result
