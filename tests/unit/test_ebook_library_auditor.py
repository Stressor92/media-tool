from __future__ import annotations

from pathlib import Path

from core.ebook.audit.library_auditor import LibraryAuditor
from core.ebook.models import BookIdentity, BookMetadata
from tests.ebook_test_support import create_minimal_epub


class _Identifier:
    def identify(self, file_path: Path) -> BookIdentity:
        if "noisbn" in file_path.name:
            return BookIdentity(title="Book", author="Author", confidence_score=0.9)
        return BookIdentity(
            title="Book", author="Author", isbn="9780441172719", isbn13="9780441172719", confidence_score=0.9
        )


class _MetadataService:
    def fetch_metadata(self, identity: BookIdentity) -> BookMetadata | None:
        if identity.isbn is None:
            return None
        return BookMetadata(
            title=identity.title,
            author=identity.author,
            isbn=identity.isbn,
            isbn13=identity.isbn13,
            series="Saga",
            series_index=1,
            source="test",
        )


class _IsbnExtractor:
    def extract(self, file_path: Path) -> str | None:
        return None if "noisbn" in file_path.name else "9780441172719"


class _EpubReader:
    def get_metadata(self, epub_path: Path) -> dict[str, str | None]:
        return {"title": "Book", "creator": "Author"}


def test_library_auditor_collects_missing_metadata_and_isbn(tmp_path: Path) -> None:
    root = tmp_path / "library"
    root.mkdir()

    first = root / "book.epub"
    second = root / "book-noisbn.epub"
    create_minimal_epub(first, "Book", "Author")
    create_minimal_epub(second, "Book", "Author")

    auditor = LibraryAuditor(
        book_identifier=_Identifier(),
        metadata_service=_MetadataService(),
        isbn_extractor=_IsbnExtractor(),
        epub_reader=_EpubReader(),
    )

    report = auditor.audit(root)

    assert report.total_books == 2
    assert len(report.missing_metadata) == 1
    assert second in report.missing_metadata
    assert len(report.missing_isbn) == 1
    assert second in report.missing_isbn
    assert ".epub" in report.format_distribution
