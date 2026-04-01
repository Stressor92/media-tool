from __future__ import annotations

from unittest.mock import MagicMock

from core.ebook.cover.providers.openlibrary_cover import OpenLibraryCoverProvider
from tests.ebook_test_support import create_image_bytes


def test_get_cover_by_isbn_returns_cover_image() -> None:
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.content = create_image_bytes(800, 1200)
    session.get.return_value = response

    provider = OpenLibraryCoverProvider(session=session)
    result = provider.get_cover_by_isbn("9780306406157")

    assert result is not None
    assert result.width == 800
    assert result.height == 1200
    assert result.source == "openlibrary"


def test_search_covers_downloads_cover_ids_from_search_results() -> None:
    session = MagicMock()
    search_response = MagicMock()
    search_response.status_code = 200
    search_response.json.return_value = {"docs": [{"cover_i": 12345}]}
    cover_response = MagicMock()
    cover_response.status_code = 200
    cover_response.content = create_image_bytes(700, 1100)
    session.get.side_effect = [search_response, cover_response]

    provider = OpenLibraryCoverProvider(session=session)
    results = provider.search_covers("Dune", author="Frank Herbert")

    assert len(results) == 1
    assert results[0].url.endswith("/id/12345-L.jpg")