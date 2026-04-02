from __future__ import annotations

from pathlib import Path

from core.ebook.identification.book_identifier import BookIdentifier
from core.ebook.identification.isbn_extractor import ISBNExtractor


class FakeEpubReader:
    def __init__(self, metadata: dict[str, str | None]) -> None:
        self._metadata = metadata

    def get_metadata(self, epub_path: Path) -> dict[str, str | None]:
        del epub_path
        return self._metadata


def test_identify_uses_isbn_strategy_when_available(tmp_path: Path) -> None:
    reader = FakeEpubReader({"title": "Dune", "author": "Frank Herbert", "identifier": "9780441172719"})
    identifier = BookIdentifier(ISBNExtractor(reader), reader)

    result = identifier.identify(tmp_path / "dune.epub")

    assert result.source == "isbn"
    assert result.isbn == "9780441172719"
    assert result.title == "Dune"
    assert result.is_high_confidence() is True


def test_identify_uses_metadata_when_no_isbn(tmp_path: Path) -> None:
    reader = FakeEpubReader({"title": "Neuromancer", "author": "William Gibson"})
    identifier = BookIdentifier(ISBNExtractor(reader), reader)

    result = identifier.identify(tmp_path / "neuromancer.epub")

    assert result.source == "metadata"
    assert result.title == "Neuromancer"
    assert result.author == "William Gibson"
    assert result.confidence_score == 0.75


def test_identify_falls_back_to_filename_parsing(tmp_path: Path) -> None:
    reader = FakeEpubReader({})
    identifier = BookIdentifier(ISBNExtractor(reader), reader)

    result = identifier.identify(tmp_path / "Isaac Asimov - Foundation.epub")

    assert result.source == "filename"
    assert result.title == "Foundation"
    assert result.author == "Isaac Asimov"
