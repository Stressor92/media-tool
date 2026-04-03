# tests/unit/test_subtitle_translator.py
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.translation.models import LanguagePair, TranslationStatus
from core.translation.subtitle_translator import SubtitleTranslator

SRT_CONTENT = """\
1
00:00:01,000 --> 00:00:03,000
Hello World

2
00:00:04,000 --> 00:00:06,000
How are you?

"""


@pytest.fixture()
def srt_file(tmp_path: Path) -> Path:
    f = tmp_path / "movie.en.srt"
    f.write_text(SRT_CONTENT)
    return f


@pytest.fixture()
def mock_translator() -> MagicMock:
    t = MagicMock()
    t.translate_batch.side_effect = lambda texts, **_: [f"[DE] {x}" for x in texts]
    t.is_language_pair_supported.return_value = True
    return t


def test_translate_file_success(srt_file: Path, mock_translator: MagicMock) -> None:
    st = SubtitleTranslator(translator=mock_translator)
    result = st.translate_file(
        source_path=srt_file,
        language_pair=LanguagePair.en_to_de(),
    )
    assert result.status == TranslationStatus.SUCCESS
    assert result.output_path is not None
    assert result.output_path.exists()
    assert result.segments_translated == 2
    mock_translator.translate_batch.assert_called_once()


def test_dry_run_creates_no_file(srt_file: Path, mock_translator: MagicMock) -> None:
    st = SubtitleTranslator(translator=mock_translator)
    result = st.translate_file(
        source_path=srt_file,
        language_pair=LanguagePair.en_to_de(),
        dry_run=True,
    )
    assert result.status == TranslationStatus.SKIPPED
    mock_translator.translate_batch.assert_not_called()


def test_skips_existing_without_overwrite(srt_file: Path, mock_translator: MagicMock, tmp_path: Path) -> None:
    out = tmp_path / "movie.de.srt"
    out.write_text("already exists")
    st = SubtitleTranslator(translator=mock_translator)
    result = st.translate_file(
        source_path=srt_file,
        language_pair=LanguagePair.en_to_de(),
        output_path=out,
        overwrite=False,
    )
    assert result.status == TranslationStatus.SKIPPED


def test_overwrite_replaces_existing(srt_file: Path, mock_translator: MagicMock, tmp_path: Path) -> None:
    out = tmp_path / "movie.de.srt"
    out.write_text("old content")
    st = SubtitleTranslator(translator=mock_translator)
    result = st.translate_file(
        source_path=srt_file,
        language_pair=LanguagePair.en_to_de(),
        output_path=out,
        overwrite=True,
    )
    assert result.status == TranslationStatus.SUCCESS
    assert "old content" not in out.read_text()


def test_output_path_convention(srt_file: Path, mock_translator: MagicMock) -> None:
    st = SubtitleTranslator(translator=mock_translator)
    result = st.translate_file(srt_file, LanguagePair.en_to_de())
    assert result.output_path is not None
    assert result.output_path.name == "movie.de.srt"


def test_missing_file_returns_failed(tmp_path: Path, mock_translator: MagicMock) -> None:
    st = SubtitleTranslator(translator=mock_translator)
    result = st.translate_file(
        source_path=tmp_path / "does_not_exist.srt",
        language_pair=LanguagePair.en_to_de(),
    )
    assert result.status == TranslationStatus.FAILED


def test_tag_preservation(tmp_path: Path, mock_translator: MagicMock) -> None:
    """HTML tags must be preserved after translation."""
    f = tmp_path / "tagged.en.srt"
    f.write_text("1\n00:00:01,000 --> 00:00:02,000\n<i>Hello</i>\n\n")
    # Mock returns text without tags — tags must be restored by translator
    mock_translator.translate_batch.side_effect = lambda texts, **_: ["Hallo" for _ in texts]
    st = SubtitleTranslator(translator=mock_translator)
    result = st.translate_file(f, LanguagePair.en_to_de())
    assert result.status == TranslationStatus.SUCCESS
    assert result.output_path is not None
    content = result.output_path.read_text()
    assert "<i>" in content


def test_translated_content_written_to_file(srt_file: Path, mock_translator: MagicMock) -> None:
    st = SubtitleTranslator(translator=mock_translator)
    result = st.translate_file(srt_file, LanguagePair.en_to_de())
    assert result.output_path is not None
    content = result.output_path.read_text()
    assert "[DE]" in content
