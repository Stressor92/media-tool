from __future__ import annotations

from unittest.mock import MagicMock

import requests

from core.ebook.cover.providers.googlebooks_cover import GoogleBooksCoverProvider
from tests.ebook_test_support import create_image_bytes


def test_get_cover_by_isbn_uses_google_books_image_links() -> None:
    session = MagicMock()
    search_response = MagicMock()
    search_response.status_code = 200
    search_response.json.return_value = {
        "items": [{"volumeInfo": {"imageLinks": {"thumbnail": "https://books.google.test/cover.jpg"}}}]
    }
    cover_response = MagicMock()
    cover_response.status_code = 200
    cover_response.content = create_image_bytes(1000, 1500)
    session.get.side_effect = [search_response, cover_response]

    provider = GoogleBooksCoverProvider(session=session)
    result = provider.get_cover_by_isbn("9780306406157")

    assert result is not None
    assert result.width == 1000
    assert result.source == "googlebooks"


def test_search_covers_returns_empty_on_request_error() -> None:
    session = MagicMock()
    session.get.side_effect = requests.RequestException("boom")

    provider = GoogleBooksCoverProvider(session=session)

    assert provider.search_covers("Dune") == []
