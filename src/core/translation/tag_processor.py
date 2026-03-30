# src/core/translation/tag_processor.py
"""
Placeholder-based tag preservation for subtitle translation.

Replaces HTML (<i>, <b>, <font ...>) and ASS ({\an8}, {\c&H...}) tags with
stable placeholders before translation, then restores them afterwards.

This keeps the translator from mangling or dropping inline formatting.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Matches HTML-like tags AND ASS/SSA curly-brace tags
_TAG_RE = re.compile(r"(<[^>]+>|\{[^}]+\})")

_PLACEHOLDER_PREFIX = "__T"
_PLACEHOLDER_SUFFIX = "__"


@dataclass
class TagMapping:
    """A single placeholder ↔ original tag pair."""
    placeholder: str
    original: str
    original_position: int = 0  # char offset in the source text (0 = prefix)


@dataclass
class TagProcessorResult:
    """Result of stripping tags from a text string."""
    clean_text: str
    mappings: list[TagMapping] = field(default_factory=list)


class TagProcessor:
    """
    Stateless helper.  Use extract() → translate → restore().

    Example
    -------
    >>> tp = TagProcessor()
    >>> result = tp.extract("<i>Hello</i>")
    >>> result.clean_text
    '__T0__ Hello __T1__'
    >>> translated = translate_somehow(result.clean_text)
    >>> tp.restore(translated, result.mappings)
    '<i>Hallo</i>'
    """

    def extract(self, text: str) -> TagProcessorResult:
        """
        Replace every tag in *text* with a numbered placeholder.
        Returns the cleaned text and the mapping list needed for restore().
        """
        mappings: list[TagMapping] = []
        counter = 0

        def _replace(m: re.Match[str]) -> str:
            nonlocal counter
            ph = f"{_PLACEHOLDER_PREFIX}{counter}{_PLACEHOLDER_SUFFIX}"
            mappings.append(TagMapping(
                placeholder=ph,
                original=m.group(),
                original_position=m.start(),
            ))
            counter += 1
            return f" {ph} "

        clean = _TAG_RE.sub(_replace, text)
        # Collapse multiple whitespace runs that may arise from adjacent tags
        clean = re.sub(r"  +", " ", clean).strip()
        return TagProcessorResult(clean_text=clean, mappings=mappings)

    def restore(self, translated: str, mappings: list[TagMapping]) -> str:
        """
        Replace placeholders in *translated* back with their original tags.

        If a placeholder was dropped by the translator:
        - Tags that preceded text (original_position == 0) are prepended.
        - All other orphaned tags are appended.
        """
        result = translated
        orphan_prefix: list[str] = []
        orphan_suffix: list[str] = []

        for m in mappings:
            before = result
            result = result.replace(f" {m.placeholder} ", m.original)
            if result == before:
                result = result.replace(m.placeholder, m.original)
            if result == before:
                # Placeholder was dropped by the model — use positional fallback
                if m.original_position == 0:
                    orphan_prefix.append(m.original)
                else:
                    orphan_suffix.append(m.original)

        if orphan_prefix or orphan_suffix:
            result = "".join(orphan_prefix) + result + "".join(orphan_suffix)

        return result

    def has_tags(self, text: str) -> bool:
        """Returns True if *text* contains any HTML or ASS tags."""
        return bool(_TAG_RE.search(text))
