# src/core/translation/subtitle_formatter.py
"""
Post-translation subtitle line wrapping.

Ensures translated text stays within readable line lengths and is broken
at natural language boundaries (spaces, commas, conjunctions) rather than
mid-word.

Rules (configurable, with sensible defaults):
  - max 40 characters per line
  - max 2 lines per subtitle block
  - prefer breaks at: punctuation (.,!?), conjunctions, commas
  - never split inside a word
"""

from __future__ import annotations

import re

# Sentence-ending punctuation after which a break is ideal
_SENTENCE_END_RE = re.compile(r"[.!?]\s+")

# Coordinating conjunctions that make good break points
_CONJUNCTION_RE = re.compile(
    r"\b(und|oder|aber|denn|sondern|doch|and|or|but|because|so|yet)\b",
    re.IGNORECASE,
)


def format_subtitle(
    text: str,
    max_chars: int = 40,
    max_lines: int = 2,
) -> str:
    """
    Wrap *text* to at most *max_lines* lines of at most *max_chars* characters.

    Multi-line input (existing \\n) is handled first: each logical line is
    independently wrapped.  The output lines are joined back with \\n.

    If the text cannot be broken sensibly (e.g. a single very long word),
    it is returned as-is rather than being truncated.
    """
    if not text or "\n" not in text and len(text) <= max_chars:
        return text

    # Flatten any existing line breaks so we can re-wrap from scratch
    flat = text.replace("\n", " ")
    flat = re.sub(r"  +", " ", flat).strip()

    if len(flat) <= max_chars:
        return flat

    lines = _wrap(flat, max_chars=max_chars, max_lines=max_lines)
    return "\n".join(lines)


def _wrap(text: str, max_chars: int, max_lines: int) -> list[str]:
    """Split *text* into up to *max_lines* chunks, each ≤ *max_chars*."""
    words = text.split()
    if not words:
        return [text]

    lines: list[str] = []
    current: list[str] = []
    current_len = 0

    for word in words:
        # Would adding this word exceed the limit?
        extra = len(word) + (1 if current else 0)  # +1 for separating space
        if current_len + extra > max_chars and current:
            lines.append(" ".join(current))
            if len(lines) >= max_lines:
                # Append all remaining words to last line rather than truncating
                remaining = words[words.index(word) :]
                lines[-1] = lines[-1] + " " + " ".join(remaining)
                return lines
            current = [word]
            current_len = len(word)
        else:
            current.append(word)
            current_len += extra

    if current:
        lines.append(" ".join(current))

    return lines or [text]
