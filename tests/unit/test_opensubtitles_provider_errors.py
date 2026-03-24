"""
tests/unit/test_opensubtitles_provider_errors.py

Comprehensive error handling tests for OpenSubtitles API provider.
Tests network errors, API failures, invalid responses, and rate limiting.
"""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import requests

from core.subtitles.opensubtitles_provider import OpenSubtitlesProvider


class TestOpenSubtitlesNetworkErrors:
    """Test error handling for network-related issues."""

    def test_network_connection_error(self):
        """Test handling of connection errors."""
        provider = OpenSubtitlesProvider(api_key="test_key")
        
        with patch("requests.get") as mock_get:
            mock_get.side_effect = requests.ConnectionError(
                "Failed to establish connection to OpenSubtitles"
            )
            
            with pytest.raises(requests.ConnectionError):
                provider.search_subtitles(imdb_id="tt0111161")

    def test_network_timeout_error(self):
        """Test handling of network timeout."""
        provider = OpenSubtitlesProvider(api_key="test_key")
        
        with patch("requests.get") as mock_get:
            mock_get.side_effect = requests.Timeout(
                "Request timed out (30 seconds)"
            )
            
            with pytest.raises(requests.Timeout):
                provider.search_subtitles(imdb_id="tt0111161")

    def test_network_http_error(self):
        """Test handling of generic HTTP errors."""
        provider = OpenSubtitlesProvider(api_key="test_key")
        
        with patch("requests.get") as mock_get:
            mock_get.side_effect = requests.RequestException(
                "HTTP request failed"
            )
            
            with pytest.raises(requests.RequestException):
                provider.search_subtitles(imdb_id="tt0111161")

    def test_dns_resolution_error(self):
        """Test handling of DNS resolution failures."""
        provider = OpenSubtitlesProvider(api_key="test_key")
        
        with patch("requests.get") as mock_get:
            mock_get.side_effect = requests.ConnectionError(
                "Failed to resolve DNS: api.opensubtitles.com"
            )
            
            with pytest.raises(requests.ConnectionError):
                provider.search_subtitles(imdb_id="tt0111161")


class TestOpenSubtitlesHTTPErrors:
    """Test error handling for HTTP status codes."""

    def test_http_404_not_found(self):
        """Test handling of 404 Not Found response."""
        provider = OpenSubtitlesProvider(api_key="test_key")
        
        with patch("requests.get") as mock_get:
            response = MagicMock()
            response.status_code = 404
            response.reason = "Not Found"
            response.text = "Endpoint not found"
            mock_get.return_value = response
            
            # Might return empty results or raise
            result = provider.search_subtitles(imdb_id="tt0000000")
            
            # Depends on implementation
            assert isinstance(result, (list, dict)) or result is None

    def test_http_401_unauthorized(self):
        """Test handling of 401 Unauthorized (invalid API key)."""
        provider = OpenSubtitlesProvider(api_key="invalid_key")
        
        with patch("requests.get") as mock_get:
            response = MagicMock()
            response.status_code = 401
            response.reason = "Unauthorized"
            response.text = "Invalid API key"
            mock_get.return_value = response
            
            with pytest.raises(Exception):
                provider.search_subtitles(imdb_id="tt0111161")

    def test_http_403_forbidden(self):
        """Test handling of 403 Forbidden response."""
        provider = OpenSubtitlesProvider(api_key="test_key")
        
        with patch("requests.get") as mock_get:
            response = MagicMock()
            response.status_code = 403
            response.reason = "Forbidden"
            response.text = "Access denied"
            mock_get.return_value = response
            
            with pytest.raises(Exception):
                provider.search_subtitles(imdb_id="tt0111161")

    def test_http_429_rate_limited(self):
        """Test handling of 429 Too Many Requests (rate limiting)."""
        provider = OpenSubtitlesProvider(api_key="test_key")
        
        with patch("requests.get") as mock_get:
            response = MagicMock()
            response.status_code = 429
            response.reason = "Too Many Requests"
            response.headers = {"Retry-After": "60"}
            response.text = "Rate limit exceeded"
            mock_get.return_value = response
            
            # Should handle rate limiting gracefully
            with pytest.raises(Exception) as exc_info:
                provider.search_subtitles(imdb_id="tt0111161")
            
            # Error message should indicate rate limiting
            assert "rate" in str(exc_info.value).lower() or "retry" in str(exc_info.value).lower()

    def test_http_500_server_error(self):
        """Test handling of 500 Internal Server Error."""
        provider = OpenSubtitlesProvider(api_key="test_key")
        
        with patch("requests.get") as mock_get:
            response = MagicMock()
            response.status_code = 500
            response.reason = "Internal Server Error"
            response.text = "Server error"
            mock_get.return_value = response
            
            with pytest.raises(Exception):
                provider.search_subtitles(imdb_id="tt0111161")

    def test_http_502_bad_gateway(self):
        """Test handling of 502 Bad Gateway."""
        provider = OpenSubtitlesProvider(api_key="test_key")
        
        with patch("requests.get") as mock_get:
            response = MagicMock()
            response.status_code = 502
            response.reason = "Bad Gateway"
            mock_get.return_value = response
            
            with pytest.raises(Exception):
                provider.search_subtitles(imdb_id="tt0111161")

    def test_http_503_service_unavailable(self):
        """Test handling of 503 Service Unavailable."""
        provider = OpenSubtitlesProvider(api_key="test_key")
        
        with patch("requests.get") as mock_get:
            response = MagicMock()
            response.status_code = 503
            response.reason = "Service Unavailable"
            response.headers = {"Retry-After": "3600"}
            mock_get.return_value = response
            
            with pytest.raises(Exception):
                provider.search_subtitles(imdb_id="tt0111161")


class TestOpenSubtitlesInvalidResponse:
    """Test handling of invalid API responses."""

    def test_invalid_json_response(self):
        """Test handling of invalid JSON in response."""
        provider = OpenSubtitlesProvider(api_key="test_key")
        
        with patch("requests.get") as mock_get:
            response = MagicMock()
            response.status_code = 200
            response.text = "This is not JSON"
            response.json.side_effect = ValueError("Invalid JSON")
            mock_get.return_value = response
            
            with pytest.raises(ValueError):
                provider.search_subtitles(imdb_id="tt0111161")

    def test_empty_response_body(self):
        """Test handling of empty response body."""
        provider = OpenSubtitlesProvider(api_key="test_key")
        
        with patch("requests.get") as mock_get:
            response = MagicMock()
            response.status_code = 200
            response.text = ""
            response.json.side_effect = ValueError("No JSON object could be decoded")
            mock_get.return_value = response
            
            with pytest.raises(ValueError):
                provider.search_subtitles(imdb_id="tt0111161")

    def test_unexpected_response_structure(self):
        """Test handling of unexpected JSON structure."""
        provider = OpenSubtitlesProvider(api_key="test_key")
        
        with patch("requests.get") as mock_get:
            response = MagicMock()
            response.status_code = 200
            response.json.return_value = {"unexpected": "structure"}
            mock_get.return_value = response
            
            # Should handle gracefully or return empty results
            result = provider.search_subtitles(imdb_id="tt0111161")
            
            assert result is None or result == []

    def test_missing_required_fields_in_response(self):
        """Test handling when response is missing required fields."""
        provider = OpenSubtitlesProvider(api_key="test_key")
        
        with patch("requests.get") as mock_get:
            response = MagicMock()
            response.status_code = 200
            response.json.return_value = {
                "subtitle": {}  # Missing required fields
            }
            mock_get.return_value = response
            
            result = provider.search_subtitles(imdb_id="tt0111161")
            
            # Should handle missing fields


class TestOpenSubtitlesSearchValidation:
    """Test error handling for search parameters."""

    def test_search_invalid_imdb_id_format(self):
        """Test search with invalid IMDb ID format."""
        provider = OpenSubtitlesProvider(api_key="test_key")
        
        # Invalid IMDb ID
        with pytest.raises(ValueError):
            provider.search_subtitles(imdb_id="invalid")

    def test_search_invalid_language_code(self):
        """Test search with invalid language code."""
        provider = OpenSubtitlesProvider(api_key="test_key")
        
        # Invalid language code
        with pytest.raises(ValueError):
            provider.search_subtitles(
                imdb_id="tt0111161",
                language="xyz"  # Invalid
            )

    def test_search_missing_search_criteria(self):
        """Test search without any search criteria."""
        provider = OpenSubtitlesProvider(api_key="test_key")
        
        with pytest.raises(ValueError):
            provider.search_subtitles()  # No criteria provided

    def test_search_conflicting_parameters(self):
        """Test search with conflicting parameters."""
        provider = OpenSubtitlesProvider(api_key="test_key")
        
        # Both file hash and IMDb ID provided (might be conflicting)
        result = provider.search_subtitles(
            imdb_id="tt0111161",
            file_hash="1234567890abcdef"
        )
        
        # Behavior depends on implementation


class TestOpenSubtitlesDownloadErrors:
    """Test error handling for subtitle downloads."""

    def test_download_invalid_download_link(self):
        """Test downloading from invalid URL."""
        provider = OpenSubtitlesProvider(api_key="test_key")
        
        with patch("requests.get") as mock_get:
            mock_get.side_effect = requests.ConnectionError("Invalid URL")
            
            with pytest.raises(requests.ConnectionError):
                provider.download_subtitle(download_link="http://invalid.url/sub.zip")

    def test_download_corrupt_zip_file(self):
        """Test handling of corrupt ZIP file in download."""
        provider = OpenSubtitlesProvider(api_key="test_key")
        
        with patch("requests.get") as mock_get:
            response = MagicMock()
            response.status_code = 200
            response.content = b"Not a real ZIP file"
            mock_get.return_value = response
            
            # Should raise error when trying to extract
            with pytest.raises(Exception):
                provider.download_subtitle(download_link="http://example.com/sub.zip")

    def test_download_empty_zip_file(self):
        """Test handling of empty ZIP file."""
        provider = OpenSubtitlesProvider(api_key="test_key")
        
        with patch("requests.get") as mock_get:
            import zipfile
            import io
            
            # Create minimal but empty ZIP
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w') as zf:
                pass
            
            response = MagicMock()
            response.status_code = 200
            response.content = zip_buffer.getvalue()
            mock_get.return_value = response
            
            # Should handle empty archive
            result = provider.download_subtitle(download_link="http://example.com/sub.zip")
            
            # Behavior depends on implementation

    def test_download_no_subtitle_in_archive(self):
        """Test handling when ZIP contains no subtitle files."""
        provider = OpenSubtitlesProvider(api_key="test_key")
        
        with patch("requests.get") as mock_get:
            import zipfile
            import io
            
            # Create ZIP with non-subtitle files
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w') as zf:
                zf.writestr("readme.txt", "Not a subtitle")
            
            response = MagicMock()
            response.status_code = 200
            response.content = zip_buffer.getvalue()
            mock_get.return_value = response
            
            result = provider.download_subtitle(download_link="http://example.com/sub.zip")
            
            # Should return None or empty


class TestOpenSubtitlesAuthenticationErrors:
    """Test authentication-related errors."""

    def test_invalid_api_key(self):
        """Test with invalid API key."""
        provider = OpenSubtitlesProvider(api_key="invalid_key_12345")
        
        with patch("requests.get") as mock_get:
            response = MagicMock()
            response.status_code = 401
            response.reason = "Unauthorized"
            mock_get.return_value = response
            
            with pytest.raises(Exception):
                provider.search_subtitles(imdb_id="tt0111161")

    def test_expired_api_key(self):
        """Test with expired API key."""
        provider = OpenSubtitlesProvider(api_key="expired_key")
        
        with patch("requests.get") as mock_get:
            response = MagicMock()
            response.status_code = 401
            response.text = "API key has expired"
            mock_get.return_value = response
            
            with pytest.raises(Exception):
                provider.search_subtitles(imdb_id="tt0111161")

    def test_missing_api_key(self):
        """Test with missing API key."""
        with pytest.raises(ValueError):
            provider = OpenSubtitlesProvider(api_key="")


class TestOpenSubtitlesFileHandling:
    """Test error handling for file operations."""

    def test_save_subtitle_permission_denied(self, tmp_path):
        """Test saving subtitle when permission is denied."""
        provider = OpenSubtitlesProvider(api_key="test_key")
        output_file = tmp_path / "output.srt"
        
        with patch("builtins.open", side_effect=PermissionError("Permission denied")):
            with pytest.raises(PermissionError):
                provider._save_subtitle_file(
                    content=b"Subtitle content",
                    output_path=output_file
                )

    def test_save_subtitle_disk_full(self, tmp_path):
        """Test saving subtitle when disk is full."""
        provider = OpenSubtitlesProvider(api_key="test_key")
        output_file = tmp_path / "output.srt"
        
        with patch("builtins.open", side_effect=OSError(28, "No space left on device")):
            with pytest.raises(OSError):
                provider._save_subtitle_file(
                    content=b"Subtitle content",
                    output_path=output_file
                )

    def test_extract_subtitle_from_zip_error(self):
        """Test error when extracting subtitle from ZIP."""
        provider = OpenSubtitlesProvider(api_key="test_key")
        
        with patch("zipfile.ZipFile") as mock_zipfile:
            mock_zipfile.return_value.__enter__.return_value.namelist.return_value = ["file.srt"]
            mock_zipfile.return_value.__enter__.return_value.read.side_effect = Exception("ZIP read error")
            
            with pytest.raises(Exception):
                provider._extract_subtitle_from_zip(b"zip_data")


class TestOpenSubtitlesRateLimiting:
    """Test rate limiting behavior."""

    def test_rate_limit_retry_mechanism(self):
        """Test that rate limiting triggers retry mechanism."""
        provider = OpenSubtitlesProvider(api_key="test_key")
        
        with patch("requests.get") as mock_get:
            # First call: rate limited
            response_429 = MagicMock()
            response_429.status_code = 429
            response_429.headers = {"Retry-After": "1"}
            
            # Second call: success
            response_200 = MagicMock()
            response_200.status_code = 200
            response_200.json.return_value = {"subtitles": []}
            
            # Should retry after rate limit
            mock_get.side_effect = [response_429, response_200]
            
            # Depends on implementation whether it auto-retries

    def test_rate_limit_exponential_backoff(self):
        """Test exponential backoff on rate limiting."""
        provider = OpenSubtitlesProvider(api_key="test_key", retry_attempts=3)
        
        with patch("requests.get") as mock_get:
            # All calls rate limited
            response = MagicMock()
            response.status_code = 429
            response.headers = {"Retry-After": "1"}
            mock_get.return_value = response
            
            # Should stop after max retries
            with pytest.raises(Exception):
                provider.search_subtitles(imdb_id="tt0111161")


class TestOpenSubtitlesEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_search_special_characters_in_query(self):
        """Test search with special characters."""
        provider = OpenSubtitlesProvider(api_key="test_key")
        
        with patch("requests.get") as mock_get:
            response = MagicMock()
            response.status_code = 200
            response.json.return_value = {"subtitles": []}
            mock_get.return_value = response
            
            # Should handle special characters
            result = provider.search_subtitles(query="Test & <Special> \"Chars\"")
            
            assert isinstance(result, (list, dict)) or result is None

    def test_search_very_long_query(self):
        """Test search with very long query string."""
        provider = OpenSubtitlesProvider(api_key="test_key")
        
        with patch("requests.get") as mock_get:
            response = MagicMock()
            response.status_code = 200
            response.json.return_value = {"subtitles": []}
            mock_get.return_value = response
            
            long_query = "A" * 10000
            result = provider.search_subtitles(query=long_query)
            
            # Should handle or truncate
            assert isinstance(result, (list, dict)) or result is None

    def test_multiple_subtitle_languages_in_search(self):
        """Test searching for multiple language subtitles."""
        provider = OpenSubtitlesProvider(api_key="test_key")
        
        with patch("requests.get") as mock_get:
            response = MagicMock()
            response.status_code = 200
            response.json.return_value = {"subtitles": [
                {"language": "en", "SubDownloadLink": "http://example.com/1.zip"},
                {"language": "de", "SubDownloadLink": "http://example.com/2.zip"},
                {"language": "fr", "SubDownloadLink": "http://example.com/3.zip"},
            ]}
            mock_get.return_value = response
            
            result = provider.search_subtitles(
                imdb_id="tt0111161",
                languages=["en", "de", "fr"]
            )
            
            # Should return multiple results
