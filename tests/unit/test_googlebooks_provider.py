from __future__ import annotations

import logging
from unittest.mock import MagicMock

import requests

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


def test_search_by_title_includes_api_key_when_configured() -> None:
    session = MagicMock()
    response = MagicMock()
    response.json.return_value = {"items": []}
    session.get.return_value = response

    provider = GoogleBooksProvider(session=session, api_key="google-key")

    provider.search_by_title("Dune")

    assert session.get.call_args.kwargs["params"]["key"] == "google-key"


def test_googlebooks_retries_and_logs_real_exception(caplog) -> None:
    session = MagicMock()
    session.get.side_effect = [
        requests.ConnectionError("first failure"),
        requests.ConnectionError("second failure"),
        requests.ConnectionError("final failure"),
    ]

    provider = GoogleBooksProvider(session=session, max_retries=2, backoff_seconds=0.0)

    with caplog.at_level(logging.WARNING):
        results = provider.search_by_title("Dune")

    assert results == []
    assert session.get.call_count == 3
    assert "Google Books lookup failed after retries" in caplog.text
    assert caplog.records[0].context["error"] == "final failure"
