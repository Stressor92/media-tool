from __future__ import annotations

from abc import ABC, abstractmethod

from core.ebook.models import BookMetadata


class MetadataProvider(ABC):
    """Abstract base for metadata sources."""

    @abstractmethod
    def search_by_isbn(self, isbn: str) -> BookMetadata | None:
        """Search for one book by ISBN."""
        ...

    @abstractmethod
    def search_by_title(
        self,
        title: str,
        author: str | None = None,
        limit: int = 5,
    ) -> list[BookMetadata]:
        """Search for candidate books by title and optional author."""
        ...

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return a stable provider identifier."""
        ...
