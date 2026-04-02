# tests/unit/test_style_mapper.py

from core.translation.models import SubtitleDocument, SubtitleFormat, SubtitleSegment
from core.translation.style_mapper import (
    adapt_styles_for_target,
    ass_tags_to_html,
    html_to_ass_tags,
    strip_all_tags,
)

# ── ass_tags_to_html ──────────────────────────────────────────────────────


def test_ass_italic_to_html() -> None:
    assert ass_tags_to_html(r"{\i1}Hello{\i0}") == "<i>Hello</i>"


def test_ass_bold_to_html() -> None:
    assert ass_tags_to_html(r"{\b1}Bold{\b0}") == "<b>Bold</b>"


def test_ass_underline_to_html() -> None:
    assert ass_tags_to_html(r"{\u1}Under{\u0}") == "<u>Under</u>"


def test_ass_unknown_tags_removed() -> None:
    result = ass_tags_to_html(r"{\pos(100,200)}Text")
    assert "{" not in result
    assert "Text" in result


def test_ass_multiple_tags() -> None:
    result = ass_tags_to_html(r"{\i1}{\b1}Both{\b0}{\i0}")
    assert "<i>" in result
    assert "<b>" in result


# ── html_to_ass_tags ──────────────────────────────────────────────────────


def test_html_italic_to_ass() -> None:
    assert html_to_ass_tags("<i>Hello</i>") == r"{\i1}Hello{\i0}"


def test_html_bold_to_ass() -> None:
    assert html_to_ass_tags("<b>Bold</b>") == r"{\b1}Bold{\b0}"


def test_html_passthrough_non_markup() -> None:
    assert html_to_ass_tags("Plain text") == "Plain text"


# ── strip_all_tags ────────────────────────────────────────────────────────


def test_strip_removes_ass_and_html() -> None:
    result = strip_all_tags(r"{\i1}Hello{\i0} <b>World</b>")
    assert result == "Hello World"


def test_strip_leaves_plain_text_unchanged() -> None:
    assert strip_all_tags("No tags here") == "No tags here"


def test_strip_removes_html_only() -> None:
    assert strip_all_tags("<i>italic</i>") == "italic"


# ── adapt_styles_for_target ───────────────────────────────────────────────


def _make_doc(fmt: SubtitleFormat, text: str) -> SubtitleDocument:
    return SubtitleDocument(
        [SubtitleSegment(1, "00:00:01,000", "00:00:02,000", text)],
        fmt,
    )


def test_adapt_ass_to_srt_converts_tags() -> None:
    doc = _make_doc(SubtitleFormat.ASS, r"{\i1}Hello{\i0}")
    adapted = adapt_styles_for_target(doc, SubtitleFormat.SRT)
    assert adapted.segments[0].text == "<i>Hello</i>"


def test_adapt_srt_to_ass_converts_tags() -> None:
    doc = _make_doc(SubtitleFormat.SRT, "<b>Hello</b>")
    adapted = adapt_styles_for_target(doc, SubtitleFormat.ASS)
    assert r"{\b1}" in adapted.segments[0].text


def test_adapt_srt_to_lrc_strips_tags() -> None:
    doc = _make_doc(SubtitleFormat.SRT, "<i>italic</i>")
    adapted = adapt_styles_for_target(doc, SubtitleFormat.LRC)
    assert adapted.segments[0].text == "italic"


def test_adapt_srt_to_sbv_strips_tags() -> None:
    doc = _make_doc(SubtitleFormat.SRT, "<b>bold</b>")
    adapted = adapt_styles_for_target(doc, SubtitleFormat.SBV)
    assert adapted.segments[0].text == "bold"


def test_adapt_srt_to_scc_strips_tags() -> None:
    doc = _make_doc(SubtitleFormat.SRT, "<u>under</u>")
    adapted = adapt_styles_for_target(doc, SubtitleFormat.SCC)
    assert adapted.segments[0].text == "under"


def test_adapt_not_in_place() -> None:
    doc = _make_doc(SubtitleFormat.ASS, r"{\i1}Hello{\i0}")
    adapted = adapt_styles_for_target(doc, SubtitleFormat.SRT)
    # Original unchanged
    assert doc.segments[0].text == r"{\i1}Hello{\i0}"
    assert adapted.segments[0].text == "<i>Hello</i>"


def test_adapt_adds_default_style_for_ass_target() -> None:
    doc = _make_doc(SubtitleFormat.SRT, "plain")
    assert not doc.styles
    adapted = adapt_styles_for_target(doc, SubtitleFormat.ASS)
    assert len(adapted.styles) == 1
    assert adapted.styles[0].name == "Default"


def test_adapt_same_format_no_change() -> None:
    doc = _make_doc(SubtitleFormat.SRT, "<i>italic</i>")
    adapted = adapt_styles_for_target(doc, SubtitleFormat.SRT)
    assert adapted.segments[0].text == "<i>italic</i>"
