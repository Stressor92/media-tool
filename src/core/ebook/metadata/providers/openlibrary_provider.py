from __future__ import annotations

import logging
import re
from typing import Any

import requests

from core.ebook.models import BookMetadata
from core.ebook.metadata.providers.provider import MetadataProvider

logger = logging.getLogger(__name__)


class OpenLibraryProvider(MetadataProvider):
    """Metadata provider backed by the Open Library API."""

    BASE_URL = "https://openlibrary.org"

    def __init__(self, timeout: int = 10, session: requests.Session | None = None) -> None:
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": "media-tool/1.0 (ebook management)"})

    def search_by_isbn(self, isbn: str) -> BookMetadata | None:
        try:
            response = self.session.get(f"{self.BASE_URL}/isbn/{isbn}.json", timeout=self.timeout)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                return None
            return self._parse_book_data(payload)
        except requests.RequestException as exc:
            logger.error("Open Library ISBN lookup failed", extra={"isbn": isbn, "error": str(exc)})
            return None

    def search_by_title(
        self,
        title: str,
        author: str | None = None,
        limit: int = 5,
    ) -> list[BookMetadata]:
        try:
            params: dict[str, str | int] = {"title": title, "limit": limit}
            if author:
                params["author"] = author
            response = self.session.get(f"{self.BASE_URL}/search.json", params=params, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
            docs = payload.get("docs", []) if isinstance(payload, dict) else []
            if not isinstance(docs, list):
                return []

            results: list[BookMetadata] = []
            for doc in docs[:limit]:
                if not isinstance(doc, dict):
                    continue
                parsed = self._parse_search_result(doc)
                if parsed is not None:
                    results.append(parsed)
            return results
        except requests.RequestException as exc:
            logger.error("Open Library title search failed", extra={"title": title, "error": str(exc)})
            return []

    def get_provider_name(self) -> str:
        return "openlibrary"

    def _parse_book_data(self, data: dict[str, Any]) -> BookMetadata:
        authors: list[str] = []
        for author_ref in data.get("authors", []):
            if not isinstance(author_ref, dict):
                continue
            author_key = author_ref.get("key")
            if isinstance(author_key, str) and author_key:
                author_name = self._fetch_author_name(author_key)
                if author_name:
                    authors.append(author_name)

        subjects = data.get("subjects", [])
        genres = [str(subject) for subject in subjects[:5] if isinstance(subject, str)] if isinstance(subjects, list) else []
        publisher = self._first_string(data.get("publishers"))
        metadata = BookMetadata(
            title=str(data.get("title", "Unknown") or "Unknown"),
            author=authors[0] if authors else "Unknown",
            description=self._get_description(data),
            language="en",
            genres=genres,
            publisher=publisher,
            published_year=self._extract_year(data.get("publish_date")),
            isbn=self._first_string(data.get("isbn_10")),
            isbn13=self._first_string(data.get("isbn_13")),
            authors=authors,
            page_count=data.get("number_of_pages") if isinstance(data.get("number_of_pages"), int) else None,
            source=self.get_provider_name(),
        )
        return metadata.with_calculated_completeness()

    def _parse_search_result(self, doc: dict[str, Any]) -> BookMetadata | None:
        title = doc.get("title")
        if not isinstance(title, str) or not title.strip():
            return None

        author_names = doc.get("author_name", [])
        authors = [str(author_name) for author_name in author_names if isinstance(author_name, str)] if isinstance(author_names, list) else []
        language_codes = doc.get("language", [])
        language = "en"
        if isinstance(language_codes, list):
            for code in language_codes:
                if isinstance(code, str) and code:
                    language = code
                    break

        metadata = BookMetadata(
            title=title,
            author=authors[0] if authors else "Unknown",
            language=language,
            publisher=self._first_string(doc.get("publisher")),
            published_year=doc.get("first_publish_year") if isinstance(doc.get("first_publish_year"), int) else None,
            isbn=self._first_string(doc.get("isbn")),
            authors=authors,
            source=self.get_provider_name(),
        )
        return metadata.with_calculated_completeness()

    def _fetch_author_name(self, author_key: str) -> str | None:
        try:
            response = self.session.get(f"{self.BASE_URL}{author_key}.json", timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
            name = payload.get("name") if isinstance(payload, dict) else None
            return name if isinstance(name, str) and name else None
        except requests.RequestException:
            return None

    @staticmethod
    def _get_description(data: dict[str, Any]) -> str | None:
        description = data.get("description")
        if isinstance(description, str):
            return description
        if isinstance(description, dict):
            value = description.get("value")
            return value if isinstance(value, str) else None
        return None

    @staticmethod
    def _extract_year(value: object) -> int | None:
        if not isinstance(value, str):
            return None
        match = re.search(r"\b(\d{4})\b", value)
        return int(match.group(1)) if match else None

    @staticmethod
    def _first_string(value: object) -> str | None:
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item:
                    return item
        return None