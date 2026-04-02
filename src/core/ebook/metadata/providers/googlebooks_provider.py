from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

import requests

from core.ebook.metadata.providers.provider import MetadataProvider
from core.ebook.models import BookMetadata

logger = logging.getLogger(__name__)


class GoogleBooksProvider(MetadataProvider):
    """Metadata provider backed by the Google Books API."""

    BASE_URL = "https://www.googleapis.com/books/v1/volumes"
    RETRYABLE_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}

    def __init__(
        self,
        timeout: int = 10,
        session: requests.Session | None = None,
        api_key: str | None = None,
        max_retries: int = 2,
        backoff_seconds: float = 0.5,
        sleep_func: Callable[[float], None] | None = None,
    ) -> None:
        self.timeout = timeout
        self.session = session or requests.Session()
        self.api_key = api_key
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self.sleep_func = sleep_func or time.sleep
        self._failure_streak = 0
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
        params: dict[str, str | int] = {"q": query, "maxResults": limit}
        if self.api_key:
            params["key"] = self.api_key

        response = self._get_with_retries(
            self.BASE_URL,
            params=params,
            failure_message="Google Books lookup failed after retries",
            context={"query": query},
        )
        if response is None:
            return []

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

    def _get_with_retries(
        self,
        url: str,
        *,
        params: dict[str, str | int],
        failure_message: str,
        context: dict[str, str],
    ) -> requests.Response | None:
        total_attempts = self.max_retries + 1
        last_error: str | None = None

        for attempt in range(1, total_attempts + 1):
            try:
                response = self.session.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                self._mark_success()
                return response
            except requests.HTTPError as exc:
                status_code = exc.response.status_code if exc.response is not None else None
                last_error = self._describe_request_exception(exc)
                if status_code not in self.RETRYABLE_STATUS_CODES or attempt == total_attempts:
                    break
            except requests.RequestException as exc:
                last_error = self._describe_request_exception(exc)
                if attempt == total_attempts:
                    break

            self.sleep_func(self.backoff_seconds * (2 ** (attempt - 1)))

        self._log_failure(
            failure_message,
            context={
                **context,
                "attempts": str(total_attempts),
                "error": last_error or "unknown request failure",
            },
        )
        return None

    def _log_failure(self, message: str, *, context: dict[str, str]) -> None:
        self._failure_streak += 1
        if self._failure_streak == 1:
            logger.warning(
                f"{message}; repeated provider failures will be suppressed until recovery",
                extra={"context": context},
            )
            return
        logger.debug(message, extra={"context": {**context, "failure_streak": str(self._failure_streak)}})

    def _mark_success(self) -> None:
        self._failure_streak = 0

    @staticmethod
    def _describe_request_exception(exc: requests.RequestException) -> str:
        response = getattr(exc, "response", None)
        if response is not None and response.status_code:
            return f"HTTP {response.status_code}"
        return str(exc) or exc.__class__.__name__

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
        genres = (
            [category for category in categories if isinstance(category, str)] if isinstance(categories, list) else []
        )

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
