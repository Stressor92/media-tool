from __future__ import annotations

from unittest.mock import MagicMock

from core.ebook.metadata.providers.googlebooks_provider import GoogleBooksProvider


def test_search_by_isbn_returns_first_google_books_match() -> None:
    session = MagicMock()
    response = MagicMock()
    response.json.return_value = {
        "items": [
            {
                "volumeInfo": {
                    "title": "Dune",
                    "authors": ["Frank Herbert"],
                    "description": "Epic science fiction novel with a long enough summary.",
                    "language": "en",
                    "publisher": "Ace",
                    "publishedDate": "1965-08-01",
                    "pageCount": 412,
                    "categories": ["Science Fiction"],
                    "industryIdentifiers": [
                        {"type": "ISBN_10", "identifier": "0441172717"},
                        {"type": "ISBN_13", "identifier": "9780441172719"},
                    ],
                }
            }
        ]
    }
    session.get.return_value = response

    provider = GoogleBooksProvider(session=session)
    result = provider.search_by_isbn("9780441172719")

    assert result is not None
    assert result.title == "Dune"
    assert result.isbn13 == "9780441172719"
    assert result.publisher == "Ace"


def test_search_by_title_returns_empty_on_invalid_payload() -> None:
    session = MagicMock()
    response = MagicMock()
    response.json.return_value = {"items": {"not": "a list"}}
    session.get.return_value = response

    provider = GoogleBooksProvider(session=session)

    assert provider.search_by_title("Dune") == []