from __future__ import annotations

from core.ebook.models import BookIdentity, BookMetadata


class ConfidenceScorer:
    """Shared scoring helpers for ebook identification and metadata selection."""

    @staticmethod
    def score_identity(source: str, has_isbn: bool, has_title: bool, has_author: bool) -> float:
        """Compute a stable confidence score for one identification strategy."""
        if has_isbn:
            return 0.95
        if source == "metadata" and has_title and has_author:
            return 0.75
        if source == "filename" and has_title:
            return 0.4 if has_author else 0.3
        return 0.0

    @staticmethod
    def score_metadata_match(
        identity: BookIdentity,
        candidate: BookMetadata,
        title_similarity: float,
        author_similarity: float,
    ) -> float:
        """Blend text similarity and metadata richness into one ranking score."""
        completeness = candidate.calculate_completeness()
        return title_similarity * 0.6 + author_similarity * 0.3 + completeness * 0.1
