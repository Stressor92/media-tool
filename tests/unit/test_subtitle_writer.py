# tests/unit/test_subtitle_writer.py
from pathlib import Path

from core.translation.models import SubtitleDocument, SubtitleFormat, SubtitleSegment
from core.translation.subtitle_writer import write_subtitle_file
from core.translation.subtitle_parser import parse_srt


def _make_doc(texts: list[str]) -> SubtitleDocument:
    segs = [
        SubtitleSegment(i + 1, f"00:00:0{i},000", f"00:00:0{i + 1},000", t)
        for i, t in enumerate(texts)
    ]
    return SubtitleDocument(segs, SubtitleFormat.SRT)


def test_srt_roundtrip(tmp_path: Path) -> None:
    doc = _make_doc(["Hallo Welt", "Zweite Zeile"])
    out = tmp_path / "out.srt"
    write_subtitle_file(doc, out)

    parsed = parse_srt(out.read_text())
    assert len(parsed) == 2
    assert parsed[0].text == "Hallo Welt"
    assert parsed[1].text == "Zweite Zeile"


def test_output_dir_created(tmp_path: Path) -> None:
    doc = _make_doc(["Test"])
    out = tmp_path / "subdir" / "nested" / "out.srt"
    write_subtitle_file(doc, out)
    assert out.exists()


def test_vtt_output_contains_webvtt_header(tmp_path: Path) -> None:
    doc = _make_doc(["Hello"])
    doc.source_format = SubtitleFormat.SRT  # override to test explicit format
    out = tmp_path / "out.vtt"
    write_subtitle_file(doc, out, output_format=SubtitleFormat.VTT)
    content = out.read_text()
    assert content.startswith("WEBVTT")


def test_vtt_uses_dot_as_millisecond_separator(tmp_path: Path) -> None:
    doc = _make_doc(["Hello"])
    out = tmp_path / "out.vtt"
    write_subtitle_file(doc, out, output_format=SubtitleFormat.VTT)
    content = out.read_text()
    # VTT uses "." not ","
    assert "00:00:00.000" in content or "," not in content.split("-->")[0]


def test_unknown_format_falls_back_to_srt(tmp_path: Path) -> None:
    segs = [SubtitleSegment(1, "00:00:01,000", "00:00:02,000", "Test")]
    doc = SubtitleDocument(segs, SubtitleFormat.UNKNOWN)
    out = tmp_path / "out.srt"
    write_subtitle_file(doc, out)
    assert out.exists()
    content = out.read_text()
    assert "Test" in content
