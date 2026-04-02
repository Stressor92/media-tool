from __future__ import annotations

from pathlib import Path

from core.ebook.models import EbookFormat, LibraryStructure
from core.ebook.organization.naming_service import NamingService


def test_ebook_format_from_extension_handles_dot_and_plain() -> None:
    assert EbookFormat.from_extension(".epub") is EbookFormat.EPUB
    assert EbookFormat.from_extension("mobi") is EbookFormat.MOBI
    assert EbookFormat.from_extension(".unknown") is None


def test_library_structure_series_path_and_filename() -> None:
    structure = LibraryStructure(
        root_path=Path("library"),
        author="Frank Herbert",
        series="Dune Chronicles",
        series_index=2.0,
        book_title="Dune Messiah",
        year=1969,
    )

    assert structure.folder_path == Path("library") / "Frank Herbert" / "Dune Chronicles #2" / "Dune Messiah (1969)"
    assert structure.filename == "Dune Messiah (1969)"


def test_naming_service_sanitizes_invalid_filename_chars() -> None:
    raw = 'A <Very> : "Bad" / Name \\ * ? | '
    cleaned = NamingService.sanitize_filename(raw)
    assert cleaned == "A Very Bad Name"
