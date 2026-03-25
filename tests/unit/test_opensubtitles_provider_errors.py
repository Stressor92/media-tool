"""Error-path tests aligned with the current OpenSubtitlesProvider API."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from core.subtitles.opensubtitles_provider import OpenSubtitlesProvider
from core.subtitles.subtitle_provider import MovieInfo, SubtitleMatch


@pytest.fixture
def provider() -> OpenSubtitlesProvider:
    return OpenSubtitlesProvider(api_key="test_key")


@pytest.fixture
def movie_info() -> MovieInfo:
    return MovieInfo(
        file_path=Path("movie.mkv"),
        file_hash="8e245d9679d31e12",
        file_size=123456,
        duration=3600.0,
        imdb_id="tt0111161",
    )


class TestOpenSubtitlesProviderErrors:
    def test_empty_api_key_rejected(self) -> None:
        with pytest.raises(ValueError):
            OpenSubtitlesProvider(api_key="")

    def test_make_request_retries_then_returns_none(self, provider: OpenSubtitlesProvider) -> None:
        with patch.object(provider.session, "request", side_effect=requests.ConnectionError("offline")):
            with patch("time.sleep") as sleep_mock:
                result = provider._make_request("GET", "https://example.com")

        assert result is None
        assert sleep_mock.call_count == provider.max_retries - 1

    def test_make_request_raises_for_unauthorized(self, provider: OpenSubtitlesProvider) -> None:
        response = MagicMock(status_code=401, text="Invalid OpenSubtitles API key")
        with patch.object(provider.session, "request", return_value=response):
            with pytest.raises(RuntimeError, match="Invalid OpenSubtitles API key"):
                provider._make_request("GET", "https://example.com")

    def test_search_invalid_json_bubbles_up(
        self, provider: OpenSubtitlesProvider, movie_info: MovieInfo
    ) -> None:
        response = MagicMock()
        response.json.side_effect = ValueError("Invalid JSON")
        with patch.object(OpenSubtitlesProvider, "_make_request", return_value=response):
            with pytest.raises(ValueError, match="Invalid JSON"):
                provider.search(movie_info, ["en"])

    def test_search_missing_file_entries_returns_empty(
        self, provider: OpenSubtitlesProvider, movie_info: MovieInfo
    ) -> None:
        response = MagicMock()
        response.json.return_value = {
            "data": [{"attributes": {"language": "en", "files": []}}]
        }
        with patch.object(OpenSubtitlesProvider, "_make_request", return_value=response):
            matches = provider.search(movie_info, ["en"])

        assert matches == []

    def test_download_without_link_raises(self, provider: OpenSubtitlesProvider, tmp_path: Path) -> None:
        match = SubtitleMatch(
            id="123",
            language="en",
            movie_name="Movie",
            release_name="Movie.Release",
            download_url="123",
            rating=8.0,
            download_count=10,
            uploader="uploader",
            hearing_impaired=False,
            format="srt",
            provider="opensubtitles",
        )
        response = MagicMock()
        response.json.return_value = {"remaining": 100}
        with patch.object(OpenSubtitlesProvider, "_make_request", return_value=response):
            with pytest.raises(RuntimeError, match="No download link"):
                provider.download(match, tmp_path / "out.srt")

    def test_make_request_rate_limit_waits_and_retries(self, provider: OpenSubtitlesProvider) -> None:
        limited = MagicMock(status_code=429, headers={"X-RateLimit-Reset": str(time.time())}, text="rate")
        ok = MagicMock(status_code=200)
        ok.raise_for_status.return_value = None
        with patch.object(provider.session, "request", side_effect=[limited, ok]):
            with patch("time.sleep") as sleep_mock:
                response = provider._make_request("GET", "https://example.com")

        assert response is ok
        sleep_mock.assert_called()
