"""
tests/integration/test_subtitle_download_workflow.py

Integration tests for subtitle download workflow.
Tests the complete pipeline from video file to embedded subtitles.
"""

from unittest.mock import Mock, patch

import pytest

from core.subtitles.opensubtitles_provider import OpenSubtitlesProvider
from core.subtitles.subtitle_downloader import SubtitleDownloadManager
from core.subtitles.subtitle_provider import SubtitleMatch
from tests.integration.conftest import create_test_video
from utils.ffmpeg_runner import FFmpegMuxer


class TestSubtitleDownloadWorkflow:
    """Integration tests for subtitle download and embedding."""

    @pytest.fixture
    def mock_provider(self):
        """Create mocked subtitle provider."""
        provider = Mock(spec=OpenSubtitlesProvider)

        # Mock search results
        match = SubtitleMatch(
            id="12345",
            language="en",
            movie_name="Test Movie",
            release_name="Test.Movie.2020.1080p.BluRay.x264",
            download_url="12345",
            rating=8.5,
            download_count=1500,
            uploader="TestUploader",
            hearing_impaired=False,
            format="srt",
            provider="opensubtitles",
        )
        provider.search.return_value = [match]
        provider.get_best_match.return_value = match
        provider.download.return_value = None  # Will be set in test

        return provider

    @pytest.fixture
    def ffmpeg_runner(self):
        """Create FFmpeg runner."""
        return FFmpegMuxer()

    @pytest.fixture
    def manager(self, mock_provider, ffmpeg_runner):
        """Create subtitle download manager."""
        return SubtitleDownloadManager(mock_provider, ffmpeg_runner)

    def test_full_download_and_embed_workflow(self, tmp_path, manager, mock_provider):
        """Test complete workflow: search → download → embed."""

        # Create test video
        video_file = create_test_video(tmp_path / "test_movie.mkv", resolution="1920x1080", duration=60)

        # Mock download to create a subtitle file
        subtitle_content = """1
00:00:01,000 --> 00:00:04,000
Test subtitle text

2
00:00:05,000 --> 00:00:08,000
More subtitle text
"""

        subtitle_path = tmp_path / "test_movie.en.srt"
        subtitle_path.write_text(subtitle_content)

        def mock_download(match, output_path):
            output_path.write_text(subtitle_content)
            return output_path

        mock_provider.download.side_effect = mock_download

        # Mock embedding to succeed
        with patch.object(manager.ffmpeg, "add_subtitle_to_mkv") as mock_embed:
            mock_embed.return_value = Mock(success=True)

            # Run workflow
            result = manager.process(video_file, languages=["en"], auto_select=True, embed=True)

            # Verify success
            assert result.success
            assert "Embedded" in result.message
            assert result.subtitle_info.language == "en"

            # Verify provider was called correctly
            mock_provider.search.assert_called_once()
            mock_provider.download.assert_called_once()

            # Verify embedding was called
            mock_embed.assert_called_once()

    def test_download_external_subtitle_only(self, tmp_path, manager, mock_provider):
        """Test downloading subtitle without embedding."""

        # Create test video
        video_file = create_test_video(tmp_path / "test_movie.mkv", resolution="1920x1080", duration=30)

        # Mock download
        subtitle_content = "1\n00:00:01,000 --> 00:00:04,000\nTest subtitle\n"
        subtitle_path = tmp_path / "test_movie.en.srt"

        def mock_download(match, output_path):
            output_path.write_text(subtitle_content)
            return output_path

        mock_provider.download.side_effect = mock_download

        # Run workflow without embedding
        result = manager.process(video_file, languages=["en"], auto_select=True, embed=False)

        # Verify success
        assert result.success
        assert result.subtitle_path == subtitle_path
        assert subtitle_path.exists()
        assert subtitle_path.read_text() == subtitle_content

    def test_no_subtitles_found(self, tmp_path, manager, mock_provider):
        """Test handling when no subtitles are found."""

        # Create test video
        video_file = create_test_video(tmp_path / "test_movie.mkv", resolution="1920x1080", duration=30)

        # Mock no results
        mock_provider.search.return_value = []

        # Run workflow
        result = manager.process(video_file, languages=["en"])

        # Verify failure with suggestion
        assert not result.success
        assert "No subtitles found" in result.message
        assert result.fallback_suggestion == "whisper"

    def test_skip_existing_subtitles(self, tmp_path, manager, mock_provider):
        """Test skipping files that already have subtitles."""

        # Create test video
        video_file = create_test_video(tmp_path / "test_movie.mkv", resolution="1920x1080", duration=30)

        # Mock ffprobe to show existing subtitle track
        with patch("core.subtitles.subtitle_downloader.probe_file") as mock_probe:
            mock_probe_result = Mock()
            mock_probe_result.streams = [
                {"codec_type": "video"},
                {"codec_type": "audio"},
                {"codec_type": "subtitle"},  # Existing subtitle
            ]
            mock_probe.return_value = mock_probe_result

            # Run workflow
            result = manager.process(video_file, languages=["en"], overwrite=False)

            # Should skip
            assert not result.success
            assert "already exist" in result.message

            # Provider should not be called
            mock_provider.search.assert_not_called()

    def test_overwrite_existing_subtitles(self, tmp_path, manager, mock_provider):
        """Test overwriting existing subtitles."""

        # Create test video
        video_file = create_test_video(tmp_path / "test_movie.mkv", resolution="1920x1080", duration=30)

        # Mock ffprobe existing subtitle track but allow overwrite
        with patch("core.subtitles.subtitle_downloader.probe_file") as mock_probe:
            mock_probe_result = Mock()
            mock_probe_result.streams = [{"codec_type": "video"}, {"codec_type": "audio"}, {"codec_type": "subtitle"}]
            mock_probe.return_value = mock_probe_result

            # Mock download
            subtitle_path = tmp_path / "test_movie.en.srt"
            mock_provider.download.return_value = subtitle_path

            # Run workflow with overwrite
            result = manager.process(video_file, languages=["en"], overwrite=True)

            # Should proceed
            mock_provider.search.assert_called_once()
            mock_provider.download.assert_called_once()

    def test_process_non_mkv_file(self, tmp_path, manager):
        """Test process rejects non-MKV files."""
        video_file = create_test_video(tmp_path / "test_movie.mp4", resolution="1920x1080", duration=30)

        with pytest.raises(ValueError, match="Not an MKV file"):
            manager.process(video_file, languages=["en"])
