# tests/unit/test_translation_output_paths.py
from pathlib import Path

from core.translation.models import LanguagePair
from core.translation.subtitle_translator import SubtitleTranslator


def test_de_suffix_replaced_by_en() -> None:
    p = SubtitleTranslator._default_output_path(
        Path("/movies/film.de.srt"), LanguagePair.de_to_en()
    )
    assert p.name == "film.en.srt"


def test_en_suffix_replaced_by_de() -> None:
    p = SubtitleTranslator._default_output_path(
        Path("/movies/film.en.srt"), LanguagePair.en_to_de()
    )
    assert p.name == "film.de.srt"


def test_no_lang_suffix_appended() -> None:
    p = SubtitleTranslator._default_output_path(
        Path("/movies/film.srt"), LanguagePair.en_to_de()
    )
    assert p.name == "film.de.srt"


def test_ger_suffix_replaced() -> None:
    p = SubtitleTranslator._default_output_path(
        Path("/movies/film.ger.srt"), LanguagePair.de_to_en()
    )
    assert p.name == "film.en.srt"


def test_eng_suffix_replaced() -> None:
    p = SubtitleTranslator._default_output_path(
        Path("/movies/film.eng.srt"), LanguagePair.en_to_de()
    )
    assert p.name == "film.de.srt"


def test_parent_directory_preserved() -> None:
    p = SubtitleTranslator._default_output_path(
        Path("/movies/Season 01/ep01.en.srt"), LanguagePair.en_to_de()
    )
    assert p.parent == Path("/movies/Season 01")


def test_vtt_extension_preserved() -> None:
    p = SubtitleTranslator._default_output_path(
        Path("/movies/film.en.vtt"), LanguagePair.en_to_de()
    )
    assert p.suffix == ".vtt"
    assert p.name == "film.de.vtt"
