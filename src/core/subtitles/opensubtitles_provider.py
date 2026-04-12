"""
src/core/subtitles/opensubtitles_provider.py

OpenSubtitles.org REST API client.
Provides subtitle search and download functionality.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import requests

from .subtitle_provider import (
    MovieInfo,
    SubtitleMatch,
    SubtitleProvider,
    extract_release_tokens,
    extract_title_year_from_filename,
    normalize_title_for_subtitle_search,
)

logger = logging.getLogger(__name__)


class OpenSubtitlesProvider(SubtitleProvider):
    """
    OpenSubtitles.org API v1 client

    API Details:
    - Base URL: https://api.opensubtitles.com/api/v1
    - Authentication: API Key Header (Api-Key: xxx)
    - Rate Limits: 40 requests/10 seconds (free), unlimited (VIP)
    - User-Agent required: YourApp v1.0
    """

    API_BASE = "https://api.opensubtitles.com/api/v1"
    _KNOWN_SUBTITLE_FORMATS = {
        "srt",
        "ass",
        "ssa",
        "sub",
        "vtt",
        "txt",
        "smi",
        "smil",
        "ttml",
        "dfxp",
        "stl",
        "scc",
        "sbv",
        "lrc",
    }

    def __init__(self, api_key: str, user_agent: str = "media-tool v1.0", timeout: int = 30, max_retries: int = 3):
        """
        Initialize OpenSubtitles provider.

        Args:
            api_key: OpenSubtitles API key
            user_agent: User-Agent string for API requests
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts for failed requests
        """
        normalized_key = api_key.strip()
        if not normalized_key:
            raise ValueError("OpenSubtitles API key must not be empty")

        self.api_key = normalized_key
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_retries = max_retries

        self.headers = {"Api-Key": normalized_key, "User-Agent": user_agent, "Content-Type": "application/json"}

        self.session = requests.Session()
        self.session.headers.update(self.headers)

        # Rate limiting
        self.last_request_time: float = 0.0
        self.min_request_interval: float = 0.25  # 4 requests/second max

    def search(self, movie_info: MovieInfo, languages: list[str], limit: int = 10) -> list[SubtitleMatch]:
        """
        Search for subtitle matches via OpenSubtitles API.

        Strategy:
        1. Primary: Search by file hash (most accurate)
        2. Fallback: Search by IMDB ID if available
        3. Fallback: Search by a normalized title/year derived from the file name

        API Endpoint: GET /subtitles
        Query params: moviehash, languages, imdb_id, order_by, query, year
        """

        self._rate_limit()

        params = {
            "moviehash": movie_info.file_hash,
            "languages": ",".join(languages),
            "order_by": "download_count",
            "limit": limit,
        }

        if movie_info.imdb_id:
            params["imdb_id"] = movie_info.imdb_id.replace("tt", "")

        if movie_info.tmdb_id:
            params["tmdb_id"] = movie_info.tmdb_id

        logger.debug("Searching OpenSubtitles with params: %s", params)
        matches = self._search_with_params(movie_info, params, limit)
        if matches:
            logger.info("Found %d subtitle matches for %s", len(matches), movie_info.file_path.name)
            return matches

        fallback_title = normalize_title_for_subtitle_search(movie_info.title or movie_info.file_path.stem)
        fallback_year = movie_info.year
        if fallback_year is None:
            _, fallback_year = extract_title_year_from_filename(movie_info.file_path.stem)

        if not fallback_title:
            logger.info("Found 0 subtitle matches for %s", movie_info.file_path.name)
            return []

        fallback_params = {
            "query": fallback_title,
            "languages": ",".join(languages),
            "order_by": "download_count",
            "limit": limit,
        }
        if fallback_year is not None:
            fallback_params["year"] = fallback_year

        logger.debug("Retrying OpenSubtitles search with normalized title fallback: %s", fallback_params)
        matches = self._search_with_params(movie_info, fallback_params, limit)
        logger.info("Found %d subtitle matches for %s", len(matches), movie_info.file_path.name)
        return matches

    def _search_with_params(self, movie_info: MovieInfo, params: dict[str, Any], limit: int) -> list[SubtitleMatch]:
        response = self._make_request("GET", f"{self.API_BASE}/subtitles", params=params)
        if not response:
            return []

        data = response.json()
        matches: list[SubtitleMatch] = []

        for item in data.get("data", [])[:limit]:
            attributes = item.get("attributes", {})
            files = attributes.get("files", [])
            if not files:
                continue

            feature_details = attributes.get("feature_details", {}) or {}
            file_info = files[0]
            file_name = str(file_info.get("file_name", "") or "")
            inferred_format = self._infer_subtitle_format(file_name)
            matches.append(
                SubtitleMatch(
                    id=str(file_info["file_id"]),
                    language=attributes.get("language", "und"),
                    movie_name=feature_details.get("movie_name", "Unknown"),
                    release_name=attributes.get("release", ""),
                    download_url=str(file_info["file_id"]),
                    rating=float(attributes.get("ratings", 0)),
                    download_count=int(attributes.get("download_count", 0)),
                    uploader=attributes.get("uploader", {}).get("name", "Unknown"),
                    hearing_impaired=bool(attributes.get("hearing_impaired", False)),
                    format=inferred_format,
                    provider="opensubtitles",
                    file_name=file_name,
                    duration=self._coerce_duration(
                        attributes.get("duration") or feature_details.get("duration") or feature_details.get("runtime")
                    ),
                    fps=self._coerce_float(attributes.get("fps") or attributes.get("frame_rate")),
                )
            )

        return matches

    def _infer_subtitle_format(self, file_name: str) -> str:
        """Infer a trustworthy subtitle format from the provider file name."""
        suffix = Path(file_name).suffix.lower().lstrip(".")
        if suffix in self._KNOWN_SUBTITLE_FORMATS:
            return suffix

        logger.debug(
            "OpenSubtitles returned an unusual subtitle filename %r; defaulting format to srt",
            file_name,
        )
        return "srt"

    def _coerce_float(self, value: Any) -> float | None:
        """Best-effort conversion for optional numeric metadata returned by the provider."""
        if value in (None, ""):
            return None

        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _coerce_duration(self, value: Any) -> float | None:
        """Normalize provider runtime metadata to seconds when it is available."""
        if value in (None, ""):
            return None

        numeric = self._coerce_float(value)
        if numeric is not None:
            if numeric > 100_000:
                return numeric / 1000.0
            return numeric

        if isinstance(value, str):
            raw = value.strip().lower()
            if ":" in raw:
                try:
                    parts = [float(part) for part in raw.replace(",", ".").split(":")]
                except ValueError:
                    parts = []
                if len(parts) == 3:
                    hours, minutes, seconds = parts
                    return (hours * 3600.0) + (minutes * 60.0) + seconds
                if len(parts) == 2:
                    minutes, seconds = parts
                    return (minutes * 60.0) + seconds

        return None

    def download(self, match: SubtitleMatch, output_path: Path) -> Path:
        """
        Download subtitle file.

        API Endpoint: POST /download
        Body: {"file_id": 12345}
        Response: {"link": "https://...", "remaining": 195, "reset_time": "..."}

        Note: Downloads are rate-limited (200/day for free tier)
        """

        self._rate_limit()

        logger.debug(f"Downloading subtitle file_id: {match.id}")

        response = self._make_request("POST", f"{self.API_BASE}/download", json={"file_id": int(match.id)})

        if not response:
            raise RuntimeError(f"Failed to get download link for file_id {match.id}")

        data = response.json()
        download_link = data.get("link")

        if not download_link:
            raise RuntimeError(f"No download link in response for file_id {match.id}")

        # Download the actual subtitle file
        logger.debug(f"Downloading from: {download_link}")
        subtitle_response = requests.get(download_link, timeout=self.timeout)
        subtitle_response.raise_for_status()

        output_path.write_bytes(subtitle_response.content)
        logger.info(f"Downloaded subtitle to {output_path}")

        return output_path

    def get_best_match(
        self,
        matches: list[SubtitleMatch],
        release_hint: str | None = None,
        movie_info: MovieInfo | None = None,
    ) -> SubtitleMatch | None:
        """
        Select the best subtitle using a weighted score:
        1. Release/file-name similarity to the local video file
        2. Runtime closeness (when provider metadata includes it)
        3. Provider rating and popularity
        4. Prefer non-hearing-impaired subtitles by default
        """

        if not matches:
            return None

        filtered = [m for m in matches if not m.hearing_impaired]
        if not filtered:
            filtered = matches

        ranked = sorted(
            filtered,
            key=lambda match: self._score_match(match, release_hint=release_hint, movie_info=movie_info),
            reverse=True,
        )
        return ranked[0]

    def _score_match(
        self,
        match: SubtitleMatch,
        release_hint: str | None = None,
        movie_info: MovieInfo | None = None,
    ) -> float:
        """Compute a weighted score for auto-selecting the most plausible subtitle match."""
        score = (match.rating * 20.0) + min(match.download_count / 200.0, 40.0)

        if match.hearing_impaired:
            score -= 12.0

        release_text = " ".join(part for part in (match.release_name, match.file_name) if part).strip()
        if release_hint and release_text:
            release_hint_lower = release_hint.lower()
            release_text_lower = release_text.lower()
            if release_hint_lower in release_text_lower:
                score += 60.0

            hint_tokens = extract_release_tokens(release_hint)
            release_tokens = extract_release_tokens(release_text)
            overlap = hint_tokens & release_tokens
            if overlap:
                score += min(len(overlap) * 8.0, 48.0)
                score += (len(overlap) / max(len(hint_tokens), 1)) * 25.0

        if movie_info and movie_info.duration > 0 and match.duration and match.duration > 0:
            drift_ratio = abs(movie_info.duration - match.duration) / movie_info.duration
            score += max(0.0, 35.0 - (drift_ratio * 500.0))
            if drift_ratio > 0.08:
                score -= 40.0
            if drift_ratio > 0.15:
                score -= 80.0

        return score

    def _rate_limit(self) -> None:
        """Implement client-side rate limiting."""
        now = time.time()
        elapsed = now - self.last_request_time

        if elapsed < self.min_request_interval:
            sleep_time = self.min_request_interval - elapsed
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)

        self.last_request_time = time.time()

    def _make_request(self, method: str, url: str, **kwargs: Any) -> requests.Response | None:
        """Make HTTP request with retry logic and error handling."""

        for attempt in range(self.max_retries):
            try:
                response = self.session.request(method, url, timeout=self.timeout, **kwargs)

                # Handle specific HTTP status codes
                if response.status_code == 401:
                    raise RuntimeError("Invalid OpenSubtitles API key")
                elif response.status_code == 429:
                    # Rate limit exceeded - wait longer
                    reset_time = response.headers.get("X-RateLimit-Reset")
                    if reset_time:
                        wait_time = max(float(reset_time) - time.time(), 10.0)
                        logger.warning(f"Rate limit exceeded, waiting {wait_time}s")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.warning("Rate limit exceeded, waiting 60s")
                        time.sleep(60)
                        continue
                elif response.status_code == 404:
                    logger.debug(f"No subtitles found: {url}")
                    return None
                elif response.status_code >= 400:
                    logger.error(f"API error {response.status_code}: {response.text}")
                    return None

                response.raise_for_status()
                return response

            except requests.exceptions.RequestException as e:
                logger.warning(f"Request failed (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2**attempt)  # Exponential backoff
                else:
                    logger.error(f"All retry attempts failed for {url}")
                    return None

        return None
