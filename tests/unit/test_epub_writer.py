from __future__ import annotations

from pathlib import Path
import zipfile

from tests.ebook_test_support import create_image_bytes, create_minimal_epub
from utils.epub_reader import EpubReader
from utils.epub_writer import EpubWriter


def test_update_metadata_updates_epub_opf_fields(tmp_path: Path) -> None:
    epub_path = tmp_path / "book.epub"
    create_minimal_epub(epub_path)

    writer = EpubWriter()
    success = writer.update_metadata(
        epub_path,
        {
            "title": "Updated Title",
            "creator": "Updated Author",
            "publisher": "Ace",
            "description": "A complete updated description",
        },
    )

    assert success is True
    metadata = EpubReader().get_metadata(epub_path)
    assert metadata["title"] == "Updated Title"
    assert metadata["author"] == "Updated Author"
    assert metadata["publisher"] == "Ace"


def test_add_cover_and_navigation_write_expected_files(tmp_path: Path) -> None:
    epub_path = tmp_path / "book.epub"
    create_minimal_epub(epub_path)
    writer = EpubWriter()

    assert writer.add_cover(epub_path, create_image_bytes(900, 1400)) is True
    assert writer.ensure_navigation(epub_path) is True

    with zipfile.ZipFile(epub_path, "r") as archive:
        names = set(archive.namelist())
        assert "OEBPS/images/cover.jpg" in names
        assert "OEBPS/nav.xhtml" in names