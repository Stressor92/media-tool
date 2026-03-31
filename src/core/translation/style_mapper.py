# src/core/translation/style_mapper.py
"""
Converts style/tag information between subtitle formats.
Lossy conversions are logged.
"""
from __future__ import annotations

import copy
import logging
import re

from core.translation.models import StyleInfo, SubtitleDocument, SubtitleFormat

logger = logging.getLogger(__name__)

# ASS inline tags → HTML tags (simple open/close pairs only)
_ASS_TO_HTML: dict[str, str] = {
    r"{\i1}": "<i>",
    r"{\i0}": "</i>",
    r"{\b1}": "<b>",
    r"{\b0}": "</b>",
    r"{\u1}": "<u>",
    r"{\u0}": "</u>",
}

_ASS_TAG_RE  = re.compile(r"\{[^}]*\}")
_HTML_TAG_RE = re.compile(r"<[^>]+>")

_FORMATS_WITHOUT_MARKUP = frozenset({
    SubtitleFormat.SCC,
    SubtitleFormat.STL,
    SubtitleFormat.LRC,
    SubtitleFormat.SBV,
})


def ass_tags_to_html(text: str) -> str:
    for ass_tag, html_tag in _ASS_TO_HTML.items():
        text = text.replace(ass_tag, html_tag)
    return _ASS_TAG_RE.sub("", text)


def html_to_ass_tags(text: str) -> str:
    mapping = {v: k for k, v in _ASS_TO_HTML.items()}
    for html_tag, ass_tag in mapping.items():
        text = text.replace(html_tag, ass_tag)
    return text


def strip_all_tags(text: str) -> str:
    """Remove all markup tags (for formats without styling support)."""
    text = _ASS_TAG_RE.sub("", text)
    text = _HTML_TAG_RE.sub("", text)
    return text


def adapt_styles_for_target(
    doc: SubtitleDocument,
    target_format: SubtitleFormat,
) -> SubtitleDocument:
    """
    Adapt segment texts and styles to the target format.
    Returns a new SubtitleDocument (not in-place).
    """
    adapted = copy.deepcopy(doc)

    source_is_ass = doc.source_format in (SubtitleFormat.ASS, SubtitleFormat.SSA)
    source_is_html = doc.source_format in (SubtitleFormat.SRT, SubtitleFormat.VTT, SubtitleFormat.TTML)

    for seg in adapted.segments:
        if source_is_ass and target_format in (
            SubtitleFormat.SRT, SubtitleFormat.VTT, SubtitleFormat.TTML
        ):
            seg.text = ass_tags_to_html(seg.text)
        elif source_is_html and target_format == SubtitleFormat.ASS:
            seg.text = html_to_ass_tags(seg.text)
        elif target_format in _FORMATS_WITHOUT_MARKUP:
            seg.text = strip_all_tags(seg.text)

    if not adapted.styles and target_format == SubtitleFormat.ASS:
        adapted.styles = [StyleInfo()]

    return adapted
