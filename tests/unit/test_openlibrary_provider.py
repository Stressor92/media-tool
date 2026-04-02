from __future__ import annotations

import logging
from unittest.mock import MagicMock

import requests

from core.ebook.metadata.providers.openlibrary_provider import OpenLibraryProvider


def test_search_by_isbn_parses_book_payload_and_author_lookup() -> None:
    session = MagicMock()
    isbn_response = MagicMock()
    isbn_response.status_code = 200
    isbn_response.json.return_value = {
        "title": "Dune",
        "authors": [{"key": "/authors/OL1A"}],
        "description": {"value": "Epic science fiction novel with enough detail to count."},
        "publishers": ["Chilton Books"],
        "publish_date": "1965",
        "subjects": ["Science Fiction", "Classic"],
        "number_of_pages": 412,
    }
    author_response = MagicMock()
    author_response.json.return_value = {"name": "Frank Herbert"}
    session.get.side_effect = [isbn_response, author_response]

    provider = OpenLibraryProvider(session=session)
    result = provider.search_by_isbn("9780441172719")

    assert result is not None
    assert result.title == "Dune"
    assert result.author == "Frank Herbert"
    assert result.publisher == "Chilton Books"
    assert result.metadata_completeness > 0.5


def test_search_by_title_filters_invalid_docs() -> None:
    session = MagicMock()
    response = MagicMock()
    response.json.return_value = {
        "docs": [
            {"title": "Dune", "author_name": ["Frank Herbert"], "language": ["en"], "isbn": ["9780441172719"]},
            {"author_name": ["Missing title"]},
        ]
    }
    session.get.return_value = response

    provider = OpenLibraryProvider(session=session)
    results = provider.search_by_title("Dune", author="Frank Herbert")

    assert len(results) == 1
    assert results[0].title == "Dune"
    assert results[0].author == "Frank Herbert"


def test_search_by_title_retries_and_logs_real_exception(caplog) -> None:
    session = MagicMock()
    session.get.side_effect = [
        requests.ReadTimeout("first timeout"),
        requests.ReadTimeout("second timeout"),
        requests.ReadTimeout("final timeout"),
    ]

    provider = OpenLibraryProvider(session=session, max_retries=2, backoff_seconds=0.0)

    with caplog.at_level(logging.WARNING):
        results = provider.search_by_title("Dune")

    assert results == []
    assert session.get.call_count == 3
    assert "Open Library title search failed after retries" in caplog.text
    assert caplog.records[0].context["error"] == "final timeout"


def test_repeated_openlibrary_failures_only_warn_once(caplog) -> None:
    session = MagicMock()
    session.get.side_effect = requests.ReadTimeout("still timing out")

    provider = OpenLibraryProvider(session=session, max_retries=0, backoff_seconds=0.0)

    with caplog.at_level(logging.WARNING):
        provider.search_by_title("Dune")
        provider.search_by_title("Dune Messiah")

    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warnings) == 1
