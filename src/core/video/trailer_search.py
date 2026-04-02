"""Trailer search strategy with language fallback and candidate ranking."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Protocol

from utils.ytdlp_runner import VideoInfo, YtDlpError

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TrailerSearchResult:
    """Represents a selected trailer candidate for a movie."""

    found: bool
    video_info: VideoInfo | None = None
    language: str | None = None
    search_query: str | None = None
    error: str | None = None


class SearchRunner(Protocol):
    """Structural interface for yt-dlp search operations."""

    def search(
        self,
        query: str,
        max_results: int = 5,
        timeout_seconds: int = 30,
    ) -> list[VideoInfo]: ...


class TrailerSearchService:
    """Search YouTube trailers with scoring and language fallback."""

    def __init__(self, ytdlp_runner: SearchRunner) -> None:
        self.ytdlp_runner = ytdlp_runner

    def search_trailer(
        self,
        movie_name: str,
        year: int | None = None,
        preferred_languages: tuple[str, ...] = ("en", "de"),
        max_results_per_language: int = 8,
    ) -> TrailerSearchResult:
        for language in preferred_languages:
            query = self._build_search_query(movie_name, year, language)
            try:
                candidates = self.ytdlp_runner.search(
                    query=query,
                    max_results=max_results_per_language,
                )
            except YtDlpError as exc:
                logger.warning(
                    "Trailer search failed",
                    extra={"movie_name": movie_name, "language": language, "error": str(exc)},
                )
                continue

            selected = self._select_best_trailer(candidates, movie_name, year)
            if selected is not None:
                return TrailerSearchResult(
                    found=True,
                    video_info=selected,
                    language=language,
                    search_query=query,
                )

        return TrailerSearchResult(
            found=False,
            error="No suitable trailer found in preferred languages",
        )

    @staticmethod
    def _build_search_query(movie_name: str, year: int | None, language: str) -> str:
        parts = [movie_name]
        if year is not None:
            parts.append(str(year))
        parts.extend(["official trailer", language])
        return " ".join(parts)

    def _select_best_trailer(
        self,
        candidates: list[VideoInfo],
        movie_name: str,
        year: int | None,
    ) -> VideoInfo | None:
        if not candidates:
            return None

        scored: list[tuple[int, VideoInfo]] = []
        movie_tokens = self._tokenize(movie_name)
        for candidate in candidates:
            score = self._score_candidate(candidate, movie_tokens, year)
            if score > 0:
                scored.append((score, candidate))

        if not scored:
            return None

        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[0][1]

    def _score_candidate(
        self,
        candidate: VideoInfo,
        movie_tokens: set[str],
        year: int | None,
    ) -> int:
        title_lower = candidate.title.lower()

        negative_keywords = [
            "reaction",
            "fan made",
            "teaser",
            "interview",
            "explained",
            "breakdown",
            "scene",
            "clip",
            "review",
            "music video",
            "ost",
        ]
        if any(keyword in title_lower for keyword in negative_keywords):
            return 0

        score = 0

        if "trailer" in title_lower:
            score += 20
        if "official" in title_lower:
            score += 15
        if "movie" in title_lower:
            score += 5

        title_tokens = self._tokenize(candidate.title)
        overlap = len(movie_tokens & title_tokens)
        score += overlap * 5

        if year is not None and str(year) in title_lower:
            score += 8

        uploader = (candidate.uploader or "").lower()
        if "pictures" in uploader or "studios" in uploader or "entertainment" in uploader:
            score += 4

        if candidate.view_count is not None:
            if candidate.view_count > 1_000_000:
                score += 6
            elif candidate.view_count > 100_000:
                score += 3

        return score

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())
        return {token for token in tokens if len(token) > 1}
