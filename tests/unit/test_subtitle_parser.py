# tests/unit/test_subtitle_parser.py
from core.translation.subtitle_parser import parse_srt, parse_vtt, parse_ass

SRT_SAMPLE = """\
1
00:00:01,000 --> 00:00:03,500
Hello World

2
00:00:04,000 --> 00:00:06,000
This is a test.

"""

VTT_SAMPLE = """\
WEBVTT

00:00:01.000 --> 00:00:03.500
Hello World

00:00:04.000 --> 00:00:06.000
Second line.

"""

ASS_SAMPLE = """\
[Script Info]
Title: Test

[Events]
Format: Layer, Start, End, Style, Actor, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:03.50,Default,,0,0,0,,{\\i1}Hello{\\i0}
Dialogue: 0,0:00:04.00,0:00:06.00,Default,,0,0,0,,World
"""


class TestSrtParser:
    def test_segment_count(self) -> None:
        segs = parse_srt(SRT_SAMPLE)
        assert len(segs) == 2

    def test_first_segment_index(self) -> None:
        seg = parse_srt(SRT_SAMPLE)[0]
        assert seg.index == 1

    def test_first_segment_start(self) -> None:
        seg = parse_srt(SRT_SAMPLE)[0]
        assert seg.start == "00:00:01,000"

    def test_first_segment_end(self) -> None:
        seg = parse_srt(SRT_SAMPLE)[0]
        assert seg.end == "00:00:03,500"

    def test_first_segment_text(self) -> None:
        seg = parse_srt(SRT_SAMPLE)[0]
        assert seg.text == "Hello World"

    def test_second_segment_text(self) -> None:
        seg = parse_srt(SRT_SAMPLE)[1]
        assert seg.text == "This is a test."

    def test_empty_input(self) -> None:
        assert parse_srt("") == []


class TestVttParser:
    def test_segment_count(self) -> None:
        segs = parse_vtt(VTT_SAMPLE)
        assert len(segs) == 2

    def test_time_converted_to_srt_format(self) -> None:
        seg = parse_vtt(VTT_SAMPLE)[0]
        assert "," in seg.start   # VTT "." → SRT ","

    def test_first_segment_text(self) -> None:
        segs = parse_vtt(VTT_SAMPLE)
        assert segs[0].text == "Hello World"

    def test_indices_start_at_1(self) -> None:
        segs = parse_vtt(VTT_SAMPLE)
        assert segs[0].index == 1


class TestAssParser:
    def test_segment_count(self) -> None:
        segs, _ = parse_ass(ASS_SAMPLE)
        assert len(segs) == 2

    def test_tags_stripped_from_text(self) -> None:
        segs, _ = parse_ass(ASS_SAMPLE)
        assert "{" not in segs[0].text
        assert "Hello" in segs[0].text

    def test_second_segment_text(self) -> None:
        segs, _ = parse_ass(ASS_SAMPLE)
        assert segs[1].text == "World"

    def test_metadata_extracted(self) -> None:
        _, meta = parse_ass(ASS_SAMPLE)
        assert meta.get("title") == "Test"

    def test_raw_tags_preserved(self) -> None:
        segs, _ = parse_ass(ASS_SAMPLE)
        assert "{" in segs[0].raw_tags
