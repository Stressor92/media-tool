"""Unit tests for merge CLI helper parsing."""

from pathlib import Path
from types import SimpleNamespace

from cli.merge_cmd import (
    _detect_audio_language_from_metadata,
    _detect_lang_and_basename,
    _language_filename_suffix,
    _parse_series_episode,
)


def test_detect_lang_and_basename_keeps_closing_parenthesis() -> None:
    lang, base = _detect_lang_and_basename(Path("A United Kingdom (2016) - de.mp4"))

    assert lang == "deu"
    assert base == "A United Kingdom (2016)"


def test_detect_lang_and_basename_detects_english() -> None:
    lang, base = _detect_lang_and_basename(Path("Movie Name-en.mp4"))

    assert lang == "eng"
    assert base == "Movie Name"


def test_detect_lang_and_basename_detects_spanish() -> None:
    lang, base = _detect_lang_and_basename(Path("Movie Name - spa.mp4"))

    assert lang == "spa"
    assert base == "Movie Name"


def test_detect_lang_and_basename_detects_en_with_de_sub_marker() -> None:
    lang, base = _detect_lang_and_basename(Path("Please Like Me - S04E01 - [en][de-sub].mp4"))

    assert lang == "eng"
    assert base == "Please Like Me - S04E01"


def test_detect_lang_and_basename_ignores_subtitle_only_marker_for_audio_language() -> None:
    lang, base = _detect_lang_and_basename(Path("Please Like Me - S04E01 - [de-sub].mp4"))

    assert lang is None
    assert base == "Please Like Me - S04E01"


def test_detect_lang_and_basename_trims_trailing_whitespace() -> None:
    lang, base = _detect_lang_and_basename(Path("Die Firma (1993) .mp4"))

    assert lang is None
    assert base == "Die Firma (1993)"


def test_parse_series_episode_normalizes_standard_episode() -> None:
    series, season, episode = _parse_series_episode("My Show - S1E2")

    assert series == "My Show"
    assert season == 1
    assert episode == "S01E02"


def test_parse_series_episode_keeps_exact_episode_number_for_s01e01() -> None:
    series, season, episode = _parse_series_episode("My Show - S01E01")

    assert series == "My Show"
    assert season == 1
    assert episode == "S01E01"


def test_parse_series_episode_normalizes_compact_episode() -> None:
    series, season, episode = _parse_series_episode("My Show - S0102")

    assert series == "My Show"
    assert season == 1
    assert episode == "S01E02"


def test_parse_series_episode_trims_non_episode_input() -> None:
    series, season, episode = _parse_series_episode("Die Firma (1993) ")

    assert series is None
    assert season is None
    assert episode == "Die Firma (1993)"


def test_detect_audio_language_from_metadata_prefers_stream_tag(monkeypatch) -> None:
    fake_probe = SimpleNamespace(
        failed=False,
        audio_streams=lambda: [{"codec_type": "audio", "tags": {"language": "es"}}],
    )
    monkeypatch.setattr("cli.merge_cmd.probe_file", lambda _path: fake_probe)

    detected = _detect_audio_language_from_metadata(Path("dummy.mp4"))

    assert detected == "spa"


def test_language_filename_suffix_for_spanish() -> None:
    assert _language_filename_suffix("spa") == "spa"
