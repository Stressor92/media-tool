# tests/unit/test_format_roundtrips.py
"""Roundtrip tests: write → read → content preserved."""
from pathlib import Path
from typing import Any

import pytest

from core.translation.formats import ass, lrc, sbv, scc, srt, stl, ttml, vtt
from core.translation.models import SubtitleDocument, SubtitleFormat, SubtitleSegment


def _base_doc(fmt: SubtitleFormat) -> SubtitleDocument:
    segs = [
        SubtitleSegment(1, "00:00:01,000", "00:00:03,000", "Hello World"),
        SubtitleSegment(2, "00:00:04,000", "00:00:06,000", "Second line"),
    ]
    return SubtitleDocument(segs, fmt)


@pytest.mark.parametrize("module,fmt,ext", [
    (srt,  SubtitleFormat.SRT,  ".srt"),
    (vtt,  SubtitleFormat.VTT,  ".vtt"),
    (ttml, SubtitleFormat.TTML, ".ttml"),
    (lrc,  SubtitleFormat.LRC,  ".lrc"),
    (sbv,  SubtitleFormat.SBV,  ".sbv"),
    (ass,  SubtitleFormat.ASS,  ".ass"),
])
def test_roundtrip(module: Any, fmt: SubtitleFormat, ext: str, tmp_path: Path) -> None:
    doc = _base_doc(fmt)
    out = tmp_path / f"test{ext}"

    module.write(doc, out)
    assert out.exists()

    parsed = module.read(out)
    assert len(parsed.segments) == len(doc.segments)
    assert parsed.segments[0].text == "Hello World"
    assert parsed.segments[1].text == "Second line"


def test_ttml_preserves_language(tmp_path: Path) -> None:
    doc = _base_doc(SubtitleFormat.TTML)
    doc.language = "de"
    out = tmp_path / "test.ttml"
    ttml.write(doc, out)
    parsed = ttml.read(out)
    assert parsed.language == "de"


def test_lrc_metadata_preserved(tmp_path: Path) -> None:
    doc = _base_doc(SubtitleFormat.LRC)
    doc.metadata = {"ti": "My Song", "ar": "Artist"}
    out = tmp_path / "test.lrc"
    lrc.write(doc, out)
    parsed = lrc.read(out)
    assert parsed.metadata.get("ti") == "My Song"
    assert parsed.metadata.get("ar") == "Artist"


def test_srt_multiline(tmp_path: Path) -> None:
    doc = SubtitleDocument(
        [SubtitleSegment(1, "00:00:01,000", "00:00:03,000", "Line one\nLine two")],
        SubtitleFormat.SRT,
    )
    out = tmp_path / "multi.srt"
    srt.write(doc, out)
    parsed = srt.read(out)
    assert "Line one" in parsed.segments[0].text
    assert "Line two" in parsed.segments[0].text


def test_vtt_header_present(tmp_path: Path) -> None:
    doc = _base_doc(SubtitleFormat.VTT)
    out = tmp_path / "test.vtt"
    vtt.write(doc, out)
    content = out.read_text()
    assert content.startswith("WEBVTT")


def test_ttml_xml_declaration(tmp_path: Path) -> None:
    doc = _base_doc(SubtitleFormat.TTML)
    out = tmp_path / "test.ttml"
    ttml.write(doc, out)
    content = out.read_text(encoding="utf-8")
    assert "<?xml" in content


def test_ass_header_present(tmp_path: Path) -> None:
    doc = _base_doc(SubtitleFormat.ASS)
    out = tmp_path / "test.ass"
    ass.write(doc, out)
    content = out.read_text()
    assert "[Script Info]" in content
    assert "[Events]" in content


def test_ass_style_roundtrip(tmp_path: Path) -> None:
    from core.translation.models import StyleInfo
    doc = _base_doc(SubtitleFormat.ASS)
    doc.styles = [StyleInfo(name="Custom", bold=True, font_size=24)]
    out = tmp_path / "styled.ass"
    ass.write(doc, out)
    parsed = ass.read(out)
    assert len(parsed.styles) >= 1
    assert parsed.styles[0].name == "Custom"


def test_sbv_time_format(tmp_path: Path) -> None:
    doc = _base_doc(SubtitleFormat.SBV)
    out = tmp_path / "test.sbv"
    sbv.write(doc, out)
    content = out.read_text()
    # SBV time looks like 0:00:01.000,0:00:03.000
    assert "0:00:01.000,0:00:03.000" in content


def test_stl_write_read(tmp_path: Path) -> None:
    doc = _base_doc(SubtitleFormat.STL)
    out = tmp_path / "test.stl"
    stl.write(doc, out)
    assert out.exists()
    parsed = stl.read(out)
    assert len(parsed.segments) == 2
    assert "Hello World" in parsed.segments[0].text


def test_scc_write_creates_header(tmp_path: Path) -> None:
    doc = _base_doc(SubtitleFormat.SCC)
    out = tmp_path / "test.scc"
    scc.write(doc, out)
    content = out.read_text()
    assert "Scenarist_SCC" in content


def test_scc_read_basic(tmp_path: Path) -> None:
    scc_content = (
        "Scenarist_SCC V1.0\n\n"
        "00:00:02;00\t1420 48 65 6c 6c 6f 142f\n"
    )
    f = tmp_path / "test.scc"
    f.write_text(scc_content)
    doc = scc.read(f)
    assert doc.source_format == SubtitleFormat.SCC


def test_lrc_no_metadata(tmp_path: Path) -> None:
    doc = _base_doc(SubtitleFormat.LRC)
    out = tmp_path / "test.lrc"
    lrc.write(doc, out)
    parsed = lrc.read(out)
    assert len(parsed.segments) == 2


def test_sbv_read_empty(tmp_path: Path) -> None:
    f = tmp_path / "empty.sbv"
    f.write_text("")
    doc = sbv.read(f)
    assert doc.segments == []
