from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BookIdentity:
    """Result of book identification."""

    title: str
    author: str
    isbn: str | None = None
    isbn13: str | None = None
    confidence_score: float = 0.0
    source: str = "unknown"

    def is_high_confidence(self) -> bool:
        """Return True when the identity score is strong enough for automation."""
        return self.confidence_score >= 0.8


@dataclass(frozen=True)
class BookMetadata:
    """Complete book metadata from one provider."""

    title: str
    author: str
    description: str | None = None
    language: str = "en"
    genres: list[str] = field(default_factory=list)
    publisher: str | None = None
    published_year: int | None = None
    isbn: str | None = None
    isbn13: str | None = None
    series: str | None = None
    series_index: float | None = None
    authors: list[str] = field(default_factory=list)
    page_count: int | None = None
    metadata_completeness: float = 0.0
    source: str = "unknown"

    def calculate_completeness(self) -> float:
        """Calculate a stable completeness score between 0.0 and 1.0."""
        score = 0.0
        score += 0.4

        if self.isbn or self.isbn13:
            score += 0.2
        if self.description and len(self.description.strip()) > 50:
            score += 0.15
        if self.publisher:
            score += 0.075
        if self.published_year is not None:
            score += 0.075
        if self.series:
            score += 0.05
        if self.genres:
            score += 0.05

        return round(score, 2)

    def with_calculated_completeness(self) -> BookMetadata:
        """Return a copy with metadata_completeness re-computed from current fields."""
        return BookMetadata(
            title=self.title,
            author=self.author,
            description=self.description,
            language=self.language,
            genres=list(self.genres),
            publisher=self.publisher,
            published_year=self.published_year,
            isbn=self.isbn,
            isbn13=self.isbn13,
            series=self.series,
            series_index=self.series_index,
            authors=list(self.authors),
            page_count=self.page_count,
            metadata_completeness=self.calculate_completeness(),
            source=self.source,
        )