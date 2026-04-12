"""Unit tests for merge CLI helper parsing."""

from pathlib import Path

from cli.merge_cmd import _detect_lang_and_basename


def test_detect_lang_and_basename_keeps_closing_parenthesis() -> None:
    lang, base = _detect_lang_and_basename(Path("A United Kingdom (2016) - de.mp4"))

    assert lang == "deu"
    assert base == "A United Kingdom (2016)"


def test_detect_lang_and_basename_detects_english() -> None:
    lang, base = _detect_lang_and_basename(Path("Movie Name-en.mp4"))

    assert lang == "eng"
    assert base == "Movie Name"
