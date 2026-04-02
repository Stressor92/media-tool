"""
tests/unit/test_opensubtitles_provider.py

Unit tests for OpenSubtitles provider.
Uses mocked API responses to avoid real network calls.
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests

from core.subtitles.opensubtitles_provider import OpenSubtitlesProvider
from core.subtitles.subtitle_provider import MovieInfo, SubtitleMatch


class TestOpenSubtitlesProvider:
    """Test OpenSubtitles API client."""

    @pytest.fixture
    def provider(self):
        """Create provider with test API key."""
        return OpenSubtitlesProvider("test_api_key")

    @pytest.fixture
    def movie_info(self):
        """Create test movie info."""
        return MovieInfo(
            file_path=Path("/test/movie.mkv"), file_hash="8e245d9679d31e12", file_size=1000000, duration=3600.0
        )

    def test_init(self, provider):
        """Test provider initialization."""
        assert provider.api_key == "test_api_key"
        assert provider.user_agent == "media-tool v1.0"
        assert "Api-Key" in provider.headers

    @patch.object(OpenSubtitlesProvider, "_make_request")
    def test_search_success(self, mock_make_request, provider, movie_info):
        """Test successful subtitle search."""
        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": [
                {
                    "attributes": {
                        "language": "en",
                        "feature_details": {"movie_name": "Test Movie"},
                        "release": "Test.Movie.2020.1080p.BluRay.x264",
                        "ratings": 8.5,
                        "download_count": 1500,
                        "uploader": {"name": "TestUploader"},
                        "hearing_impaired": False,
                        "files": [{"file_id": 12345, "file_name": "test.srt"}],
                    }
                }
            ]
        }
        mock_make_request.return_value = mock_response

        matches = provider.search(movie_info, ["en"])

        assert len(matches) == 1
        match = matches[0]
        assert isinstance(match, SubtitleMatch)
        assert match.language == "en"
        assert match.movie_name == "Test Movie"
        assert match.rating == 8.5
        assert match.download_count == 1500
        assert match.provider == "opensubtitles"

    @patch.object(OpenSubtitlesProvider, "_make_request")
    def test_search_no_results(self, mock_make_request, provider, movie_info):
        """Test search with no results."""
        mock_response = Mock()
        mock_response.json.return_value = {"data": []}
        mock_make_request.return_value = mock_response

        matches = provider.search(movie_info, ["en"])

        assert len(matches) == 0

    @patch.object(OpenSubtitlesProvider, "_make_request")
    @patch("requests.get")
    def test_download_success(self, mock_get, mock_make_request, provider, tmp_path):
        """Test successful subtitle download."""
        # Mock download endpoint response
        mock_post_response = Mock()
        mock_post_response.json.return_value = {"link": "https://example.com/download/test.srt", "remaining": 195}
        mock_make_request.return_value = mock_post_response

        # Mock actual file download
        mock_file_response = Mock()
        mock_file_response.content = b"test subtitle content"
        mock_file_response.raise_for_status.return_value = None
        mock_get.return_value = mock_file_response

        match = SubtitleMatch(
            id="12345",
            language="en",
            movie_name="Test",
            release_name="Test",
            download_url="12345",
            rating=8.0,
            download_count=100,
            uploader="Test",
            hearing_impaired=False,
            format="srt",
            provider="opensubtitles",
        )

        output_path = tmp_path / "test.srt"
        result_path = provider.download(match, output_path)

        assert result_path == output_path
        assert output_path.read_bytes() == b"test subtitle content"

    def test_get_best_match(self, provider):
        """Test best match selection."""
        matches = [
            SubtitleMatch(
                id="1",
                language="en",
                movie_name="Test",
                release_name="BluRay.1080p",
                download_url="",
                rating=7.0,
                download_count=1000,
                uploader="A",
                hearing_impaired=False,
                format="srt",
                provider="opensubtitles",
            ),
            SubtitleMatch(
                id="2",
                language="en",
                movie_name="Test",
                release_name="WEB-DL.720p",
                download_url="",
                rating=8.5,
                download_count=500,
                uploader="B",
                hearing_impaired=False,
                format="srt",
                provider="opensubtitles",
            ),
        ]

        best = provider.get_best_match(matches)
        assert best.id == "2"  # Higher rating wins

    def test_get_best_match_with_release_hint(self, provider):
        """Test best match with release name hint."""
        matches = [
            SubtitleMatch(
                id="1",
                language="en",
                movie_name="Test",
                release_name="WEB-DL.720p",
                download_url="",
                rating=8.5,
                download_count=1000,
                uploader="A",
                hearing_impaired=False,
                format="srt",
                provider="opensubtitles",
            ),
            SubtitleMatch(
                id="2",
                language="en",
                movie_name="Test",
                release_name="BluRay.1080p",
                download_url="",
                rating=7.0,
                download_count=500,
                uploader="B",
                hearing_impaired=False,
                format="srt",
                provider="opensubtitles",
            ),
        ]

        best = provider.get_best_match(matches, "BluRay")
        assert best.id == "2"  # Exact release match wins despite lower rating

    def test_get_best_match_all_hearing_impaired(self, provider):
        """Test selection when all matches are hearing impaired."""
        matches = [
            SubtitleMatch(
                id="1",
                language="en",
                movie_name="Test",
                release_name="HearingImpaired",
                download_url="",
                rating=5.0,
                download_count=50,
                uploader="A",
                hearing_impaired=True,
                format="srt",
                provider="opensubtitles",
            ),
            SubtitleMatch(
                id="2",
                language="en",
                movie_name="Test",
                release_name="HearingImpaired",
                download_url="",
                rating=6.0,
                download_count=30,
                uploader="B",
                hearing_impaired=True,
                format="srt",
                provider="opensubtitles",
            ),
        ]

        best = provider.get_best_match(matches)
        assert best.id == "2"  # Highest rating among HI set

    @patch.object(OpenSubtitlesProvider, "_make_request")
    def test_download_missing_link(self, mock_make_request, provider, tmp_path):
        """Test download raises if API response misses link."""
        mock_post_response = Mock()
        mock_post_response.json.return_value = {"remaining": 190}
        mock_make_request.return_value = mock_post_response

        match = SubtitleMatch(
            id="12345",
            language="en",
            movie_name="Test",
            release_name="Test",
            download_url="12345",
            rating=8.0,
            download_count=100,
            uploader="Test",
            hearing_impaired=False,
            format="srt",
            provider="opensubtitles",
        )

        with pytest.raises(RuntimeError, match="No download link"):
            provider.download(match, tmp_path / "test.srt")

    @patch.object(OpenSubtitlesProvider, "_make_request")
    @patch("requests.get")
    def test_download_http_error(self, mock_get, mock_make_request, provider, tmp_path):
        """Test download raises when content fetch fails."""
        mock_post_response = Mock()
        mock_post_response.json.return_value = {"link": "https://example.com/test.srt"}
        mock_post_response.raise_for_status.return_value = None
        mock_make_request.return_value = mock_post_response

        mock_file_response = Mock()
        mock_file_response.raise_for_status.side_effect = requests.exceptions.HTTPError("Bad Request")
        mock_get.return_value = mock_file_response

        match = SubtitleMatch(
            id="12345",
            language="en",
            movie_name="Test",
            release_name="Test",
            download_url="12345",
            rating=8.0,
            download_count=100,
            uploader="Test",
            hearing_impaired=False,
            format="srt",
            provider="opensubtitles",
        )

        with pytest.raises(requests.exceptions.HTTPError):
            provider.download(match, tmp_path / "test.srt")

    @patch("requests.Session.get")
    def test_search_missing_file_entry(self, mock_get, provider, movie_info):
        """Test search skips items with missing files."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": [
                {
                    "attributes": {
                        "language": "en",
                        "feature_details": {"movie_name": "Test"},
                        "release": "Test",
                        "files": [],
                    }
                }
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        matches = provider.search(movie_info, ["en"])

        assert matches == []
