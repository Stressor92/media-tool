# tests/integration/test_converter_integration.py
"""
Integration tests: all conversion paths through real files.
Requires: MEDIA_TOOL_INTEGRATION_TESTS=1
"""

from pathlib import Path

import pytest

from core.translation.converter import ConversionStatus, SubtitleConverter
from core.translation.models import SubtitleFormat

_SRT = """\
1
00:00:01,000 --> 00:00:03,500
Hello World

2
00:00:04,000 --> 00:00:06,000
<i>This is italic.</i>

"""


@pytest.mark.integration
@pytest.mark.parametrize(
    "target",
    [
        SubtitleFormat.VTT,
        SubtitleFormat.TTML,
        SubtitleFormat.ASS,
        SubtitleFormat.SBV,
        SubtitleFormat.LRC,
        SubtitleFormat.SCC,
        SubtitleFormat.STL,
    ],
)
def test_srt_to_all_formats(target: SubtitleFormat, tmp_path: Path) -> None:
    src = tmp_path / "test.srt"
    src.write_text(_SRT)
    c = SubtitleConverter()
    result = c.convert(src, target)
    assert result.status == ConversionStatus.SUCCESS
    assert result.output_path is not None
    assert result.output_path.exists()
    assert result.segments_converted == 2


@pytest.mark.integration
def test_ttml_to_srt_roundtrip(tmp_path: Path) -> None:
    src = tmp_path / "test.srt"
    src.write_text(_SRT)
    c = SubtitleConverter()

    ttml_out = tmp_path / "test.ttml"
    c.convert(src, SubtitleFormat.TTML, output_path=ttml_out)

    srt_out = tmp_path / "from_ttml.srt"
    result = c.convert(ttml_out, SubtitleFormat.SRT, output_path=srt_out)

    assert result.status == ConversionStatus.SUCCESS
    content = srt_out.read_text()
    assert "Hello World" in content


@pytest.mark.integration
def test_sbv_youtube_roundtrip(tmp_path: Path) -> None:
    src = tmp_path / "captions.srt"
    src.write_text(_SRT)
    c = SubtitleConverter()
    sbv_out = tmp_path / "captions.sbv"
    c.convert(src, SubtitleFormat.SBV, output_path=sbv_out)
    back = tmp_path / "back.srt"
    result = c.convert(sbv_out, SubtitleFormat.SRT, output_path=back)
    assert result.status == ConversionStatus.SUCCESS
    assert "Hello World" in back.read_text()


@pytest.mark.integration
def test_ass_roundtrip(tmp_path: Path) -> None:
    src = tmp_path / "test.srt"
    src.write_text(_SRT)
    c = SubtitleConverter()
    ass_out = tmp_path / "test.ass"
    c.convert(src, SubtitleFormat.ASS, output_path=ass_out)
    back = tmp_path / "back.srt"
    result = c.convert(ass_out, SubtitleFormat.SRT, output_path=back)
    assert result.status == ConversionStatus.SUCCESS
    assert "Hello World" in back.read_text()


@pytest.mark.integration
def test_stl_roundtrip(tmp_path: Path) -> None:
    src = tmp_path / "test.srt"
    src.write_text(_SRT)
    c = SubtitleConverter()
    stl_out = tmp_path / "test.stl"
    c.convert(src, SubtitleFormat.STL, output_path=stl_out)
    back = tmp_path / "stl_back.srt"
    result = c.convert(stl_out, SubtitleFormat.SRT, output_path=back)
    assert result.status == ConversionStatus.SUCCESS
    assert "Hello World" in back.read_text()


@pytest.mark.integration
def test_lrc_roundtrip_text_preserved(tmp_path: Path) -> None:
    src = tmp_path / "test.srt"
    src.write_text(_SRT)
    c = SubtitleConverter()
    lrc_out = tmp_path / "test.lrc"
    c.convert(src, SubtitleFormat.LRC, output_path=lrc_out)
    back = tmp_path / "lrc_back.srt"
    result = c.convert(lrc_out, SubtitleFormat.SRT, output_path=back)
    assert result.status == ConversionStatus.SUCCESS
    assert "Hello World" in back.read_text()


@pytest.mark.integration
def test_batch_srt_to_vtt(tmp_path: Path) -> None:
    srts = []
    for i in range(4):
        f = tmp_path / f"sub{i}.srt"
        f.write_text(_SRT)
        srts.append(f)
    c = SubtitleConverter()
    results = c.convert_batch(srts, SubtitleFormat.VTT, output_dir=tmp_path)
    assert len(results) == 4
    assert all(r.status == ConversionStatus.SUCCESS for r in results)
