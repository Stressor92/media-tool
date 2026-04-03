from __future__ import annotations

import logging
import time
from collections.abc import Sequence

from src.statistics import get_collector
from src.statistics.event_types import EventType

from core.ebook.identification.confidence_scorer import ConfidenceScorer
from core.ebook.metadata.providers.provider import MetadataProvider
from core.ebook.models import BookIdentity, BookMetadata
from utils.fuzzy_matcher import FuzzyMatcher

logger = logging.getLogger(__name__)


class MetadataService:
    """Orchestrate metadata retrieval across multiple providers."""

    def __init__(self, providers: Sequence[MetadataProvider], fuzzy_matcher: FuzzyMatcher) -> None:
        self.providers = providers
        self.fuzzy_matcher = fuzzy_matcher

    def fetch_metadata(self, book_identity: BookIdentity) -> BookMetadata | None:
        """Fetch the best metadata match for one identified book."""
        start = time.perf_counter()
        if book_identity.isbn:
            for provider in self.providers:
                metadata = provider.search_by_isbn(book_identity.isbn)
                if metadata is not None:
                    try:
                        get_collector().record(
                            EventType.EBOOK_ENRICHED,
                            duration_seconds=time.perf_counter() - start,
                            provider=provider.get_provider_name(),
                        )
                    except Exception:
                        logger.debug("Stats recording failed", exc_info=True)
                    logger.info(
                        "Book metadata found via ISBN",
                        extra={"provider": provider.get_provider_name(), "isbn": book_identity.isbn},
                    )
                    return metadata.with_calculated_completeness()

        all_results: list[BookMetadata] = []
        author = book_identity.author if book_identity.author != "Unknown" else None
        for provider in self.providers:
            all_results.extend(provider.search_by_title(book_identity.title, author=author, limit=3))

        if not all_results and author is not None:
            for provider in self.providers:
                all_results.extend(provider.search_by_title(book_identity.title, author=None, limit=3))

        if not all_results:
            logger.info(
                "No ebook metadata found",
                extra={"context": {"title": book_identity.title, "author": book_identity.author}},
            )
            return None

        selected = self._select_best_match(book_identity, all_results)
        if selected is not None:
            try:
                get_collector().record(
                    EventType.EBOOK_ENRICHED,
                    duration_seconds=time.perf_counter() - start,
                    provider=selected.source,
                )
            except Exception:
                logger.debug("Stats recording failed", exc_info=True)
        return selected

    def _select_best_match(self, identity: BookIdentity, candidates: list[BookMetadata]) -> BookMetadata | None:
        if not candidates:
            return None

        scored_candidates: list[tuple[float, BookMetadata]] = []
        for candidate in candidates:
            title_score = self.fuzzy_matcher.similarity(identity.title, candidate.title)
            author_score = 0.0
            if identity.author != "Unknown":
                author_score = self.fuzzy_matcher.similarity(identity.author, candidate.author)
            score = ConfidenceScorer.score_metadata_match(identity, candidate, title_score, author_score)
            scored_candidates.append((score, candidate.with_calculated_completeness()))

        scored_candidates.sort(key=lambda item: item[0], reverse=True)
        best_score, best_candidate = scored_candidates[0]
        logger.info(
            "Best ebook metadata match selected",
            extra={"title": best_candidate.title, "provider": best_candidate.source, "score": round(best_score, 2)},
        )
        return best_candidate
