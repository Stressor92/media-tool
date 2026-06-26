from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core.audiobook.organization import (
    _generate_audiobook_path,
    organize_audiobooks,
    organize_audiobooks_from_subfolders,
)


def test_generate_audiobook_path_uses_requested_extension(tmp_path):
    metadata = MagicMock(
        narrator="Narrator",
        artist="Artist",
        parsed_artist=None,
        album="Book",
        parsed_album=None,
        series=None,
        year=2021,
        language="deu",
        title="Chapter 1",
        parsed_title=None,
        filename="chapter01.mp3",
    )

    target = _generate_audiobook_path(metadata, tmp_path, "m4b")

    assert target.suffix == ".m4b"
    assert target.parent.name == "Narrator-Book-2021-de"


def test_organize_uses_convert_format_for_output_extension(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    input_file = source_dir / "track01.mp3"
    input_file.touch()

    output_dir = tmp_path / "out"

    metadata = MagicMock(
        narrator="Narrator",
        artist="Artist",
        parsed_artist=None,
        album="Book",
        parsed_album=None,
        series=None,
        year=2022,
        language="eng",
        title="Track 01",
        parsed_title=None,
        filename="track01.mp3",
    )

    with (
        patch("core.audiobook.organization.extract_audio_metadata_enhanced", return_value=metadata),
        patch("core.audiobook.organization.convert_audio") as mock_convert,
    ):
        mock_convert.return_value = SimpleNamespace(success=True)

        result = organize_audiobooks(source_dir, output_dir, convert_format="m4b")

        assert result["converted"] == 1
        call_kwargs = mock_convert.call_args.kwargs
        assert call_kwargs["output_file"].suffix == ".m4b"
        assert "Narrator-Book-2022-en" in str(call_kwargs["output_file"])


def test_collect_from_subfolders_scans_recursively(tmp_path):
    source_root = tmp_path / "root"
    nested = source_root / "A" / "B"
    nested.mkdir(parents=True)
    input_file = nested / "track01.mp3"
    input_file.touch()

    output_dir = tmp_path / "out"

    metadata = MagicMock(
        narrator="Author",
        artist="Artist",
        parsed_artist=None,
        album="Titel",
        parsed_album=None,
        series=None,
        year=2020,
        language=None,
        title="Track 01",
        parsed_title=None,
        filename="track01.mp3",
    )

    with (
        patch("core.audiobook.organization.extract_audio_metadata_enhanced", return_value=metadata),
        patch("core.audiobook.organization.convert_audio") as mock_convert,
    ):
        mock_convert.return_value = SimpleNamespace(success=True)

        result = organize_audiobooks_from_subfolders(source_root, output_dir, convert_format="m4b")

        assert result["converted"] == 1
        call_kwargs = mock_convert.call_args.kwargs
        assert "Author-Titel-2020-de" in str(call_kwargs["output_file"])
