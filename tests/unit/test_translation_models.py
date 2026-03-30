# tests/unit/test_translation_models.py
import pytest
from pathlib import Path

from core.translation.models import LanguagePair, SubtitleFormat, SubtitleSegment


def test_language_pair_str() -> None:
    assert str(LanguagePair.en_to_de()) == "en→de"


def test_language_pair_de_to_en_str() -> None:
    assert str(LanguagePair.de_to_en()) == "de→en"


def test_subtitle_format_from_path_srt() -> None:
    assert SubtitleFormat.from_path(Path("movie.srt")) == SubtitleFormat.SRT


def test_subtitle_format_from_path_ass() -> None:
    assert SubtitleFormat.from_path(Path("movie.ass")) == SubtitleFormat.ASS


def test_subtitle_format_from_path_ssa() -> None:
    assert SubtitleFormat.from_path(Path("movie.ssa")) == SubtitleFormat.SSA


def test_subtitle_format_from_path_vtt() -> None:
    assert SubtitleFormat.from_path(Path("movie.vtt")) == SubtitleFormat.VTT


def test_subtitle_format_from_path_unknown() -> None:
    assert SubtitleFormat.from_path(Path("movie.xyz")) == SubtitleFormat.UNKNOWN


def test_segment_defaults() -> None:
    seg = SubtitleSegment(index=1, start="00:00:01,000", end="00:00:03,000", text="Hello")
    assert seg.raw_tags == ""


def test_language_pair_frozen() -> None:
    pair = LanguagePair.en_to_de()
    with pytest.raises((AttributeError, TypeError)):
        pair.source = "fr"  # type: ignore[misc]
