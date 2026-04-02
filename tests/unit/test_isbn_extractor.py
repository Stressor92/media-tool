from __future__ import annotations

from pathlib import Path

from core.ebook.identification.isbn_extractor import ISBNExtractor


class FakeEpubReader:
    def __init__(self, metadata: dict[str, str | None]) -> None:
        self._metadata = metadata

    def get_metadata(self, epub_path: Path) -> dict[str, str | None]:
        del epub_path
        return self._metadata


class FakePdfReader:
    def __init__(self, metadata: dict[str, str | None], text: str) -> None:
        self._metadata = metadata
        self._text = text

    def get_metadata(self, file_path: Path) -> dict[str, str | None]:
        del file_path
        return self._metadata

    def extract_text(self, file_path: Path, max_pages: int = 3) -> str:
        del file_path, max_pages
        return self._text


def test_extract_prefers_epub_identifier_and_normalizes_to_isbn13(tmp_path: Path) -> None:
    extractor = ISBNExtractor(FakeEpubReader({"identifier": "0-306-40615-2"}))

    isbn = extractor.extract(tmp_path / "book.epub")

    assert isbn == "9780306406157"


def test_extract_falls_back_to_description_scan(tmp_path: Path) -> None:
    extractor = ISBNExtractor(FakeEpubReader({"description": "ISBN-13: 978-0-306-40615-7"}))

    isbn = extractor.extract(tmp_path / "book.epub")

    assert isbn == "9780306406157"


def test_extract_reads_pdf_text_when_metadata_has_no_isbn(tmp_path: Path) -> None:
    extractor = ISBNExtractor(
        FakeEpubReader({}),
        pdf_reader=FakePdfReader({}, "Some intro text ISBN 9780306406157 end"),
    )

    isbn = extractor.extract(tmp_path / "book.pdf")

    assert isbn == "9780306406157"


def test_extract_returns_none_for_unsupported_extension(tmp_path: Path) -> None:
    extractor = ISBNExtractor(FakeEpubReader({}))

    assert extractor.extract(tmp_path / "book.mobi") is None
