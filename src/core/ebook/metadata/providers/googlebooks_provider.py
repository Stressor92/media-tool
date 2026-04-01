from __future__ import annotations

import logging
from typing import Any

import requests

from core.ebook.models import BookMetadata
from core.ebook.metadata.providers.provider import MetadataProvider

logger = logging.getLogger(__name__)


class GoogleBooksProvider(MetadataProvider):
    """Metadata provider backed by the Google Books API."""

    BASE_URL = "https://www.googleapis.com/books/v1/volumes"

    def __init__(self, timeout: int = 10, session: requests.Session | None = None) -> None:
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": "media-tool/1.0 (ebook management)"})

    def search_by_isbn(self, isbn: str) -> BookMetadata | None:
        results = self._search(query=f"isbn:{isbn}", limit=1)
        return results[0] if results else None

    def search_by_title(
        self,
        title: str,
        author: str | None = None,
        limit: int = 5,
    ) -> list[BookMetadata]:
        query = f"intitle:{title}"
        if author:
            query = f"{query}+inauthor:{author}"
        return self._search(query=query, limit=limit)

    def get_provider_name(self) -> str:
        return "googlebooks"

    def _search(self, query: str, limit: int) -> list[BookMetadata]:
        try:
            params: dict[str, str | int] = {"q": query, "maxResults": limit}
            response = self.session.get(
                self.BASE_URL,
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            items = payload.get("items", []) if isinstance(payload, dict) else []
            if not isinstance(items, list):
                return []

            results: list[BookMetadata] = []
            for item in items[:limit]:
                if not isinstance(item, dict):
                    continue
                metadata = self._parse_item(item)
                if metadata is not None:
                    results.append(metadata)
            return results
        except requests.RequestException as exc:
            logger.error("Google Books lookup failed", extra={"query": query, "error": str(exc)})
            return []

    def _parse_item(self, item: dict[str, Any]) -> BookMetadata | None:
        volume = item.get("volumeInfo")
        if not isinstance(volume, dict):
            return None

        title = volume.get("title")
        if not isinstance(title, str) or not title.strip():
            return None

        authors = volume.get("authors", [])
        author_list = [author for author in authors if isinstance(author, str)] if isinstance(authors, list) else []
        identifiers = volume.get("industryIdentifiers", [])
        isbn10 = None
        isbn13 = None
        if isinstance(identifiers, list):
            for identifier in identifiers:
                if not isinstance(identifier, dict):
                    continue
                kind = identifier.get("type")
                value = identifier.get("identifier")
                if kind == "ISBN_10" and isinstance(value, str):
                    isbn10 = value
                if kind == "ISBN_13" and isinstance(value, str):
                    isbn13 = value

        categories = volume.get("categories", [])
        genres = [category for category in categories if isinstance(category, str)] if isinstance(categories, list) else []

        language = volume.get("language")
        normalized_language = language if isinstance(language, str) and language else "en"

        metadata = BookMetadata(
            title=title,
            author=author_list[0] if author_list else "Unknown",
            description=volume.get("description") if isinstance(volume.get("description"), str) else None,
            language=normalized_language,
            genres=genres,
            publisher=volume.get("publisher") if isinstance(volume.get("publisher"), str) else None,
            published_year=self._extract_year(volume.get("publishedDate")),
            isbn=isbn10,
            isbn13=isbn13,
            authors=author_list,
            page_count=volume.get("pageCount") if isinstance(volume.get("pageCount"), int) else None,
            source=self.get_provider_name(),
        )
        return metadata.with_calculated_completeness()

    @staticmethod
    def _extract_year(value: object) -> int | None:
        if not isinstance(value, str) or len(value) < 4:
            return None
        year = value[:4]
        return int(year) if year.isdigit() else None