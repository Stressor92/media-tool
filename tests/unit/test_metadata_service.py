from __future__ import annotations

from core.ebook.metadata.metadata_service import MetadataService
from core.ebook.metadata.providers.provider import MetadataProvider
from core.ebook.models import BookIdentity, BookMetadata
from utils.fuzzy_matcher import FuzzyMatcher


class FakeProvider(MetadataProvider):
    def __init__(self, name: str, isbn_result: BookMetadata | None, title_results: list[BookMetadata]) -> None:
        self._name = name
        self._isbn_result = isbn_result
        self._title_results = title_results

    def search_by_isbn(self, isbn: str) -> BookMetadata | None:
        del isbn
        return self._isbn_result

    def search_by_title(self, title: str, author: str | None = None, limit: int = 5) -> list[BookMetadata]:
        del title, author, limit
        return self._title_results

    def get_provider_name(self) -> str:
        return self._name


def test_fetch_metadata_prefers_isbn_lookup() -> None:
    isbn_match = BookMetadata(title="Dune", author="Frank Herbert", isbn13="9780441172719", source="openlibrary")
    providers = [
        FakeProvider("openlibrary", isbn_match, []),
        FakeProvider("googlebooks", None, []),
    ]
    service = MetadataService(providers, FuzzyMatcher())

    result = service.fetch_metadata(BookIdentity(title="Dune", author="Frank Herbert", isbn="9780441172719"))

    assert result is not None
    assert result.source == "openlibrary"
    assert result.isbn13 == "9780441172719"


def test_fetch_metadata_selects_best_fuzzy_match() -> None:
    weaker = BookMetadata(title="Dunes of Mars", author="Someone Else", source="googlebooks")
    stronger = BookMetadata(
        title="Dune",
        author="Frank Herbert",
        description="A long enough description to count toward completeness scoring.",
        isbn13="9780441172719",
        source="openlibrary",
    )
    service = MetadataService(
        [
            FakeProvider("googlebooks", None, [weaker]),
            FakeProvider("openlibrary", None, [stronger]),
        ],
        FuzzyMatcher(),
    )

    result = service.fetch_metadata(BookIdentity(title="Dune", author="Frank Herbert"))

    assert result is not None
    assert result.title == "Dune"
    assert result.source == "openlibrary"


def test_fetch_metadata_returns_none_when_no_provider_matches() -> None:
    service = MetadataService([FakeProvider("empty", None, [])], FuzzyMatcher())

    result = service.fetch_metadata(BookIdentity(title="Unknown", author="Unknown"))

    assert result is None
