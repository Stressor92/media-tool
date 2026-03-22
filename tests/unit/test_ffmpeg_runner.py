"""
tests/unit/test_ffmpeg_runner.py

Unit tests for FFmpeg runner extensions.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch


from src.utils.ffmpeg_runner import FFmpegMuxer


class TestFFmpegMuxer:
    """Test FFmpegMuxer functionality."""

    def create_test_files(self):
        """Create test MKV and SRT files."""
        with tempfile.NamedTemporaryFile(suffix='.mkv', delete=False) as mkv_file:
            mkv_file.write(b'dummy mkv content')
            mkv_path = Path(mkv_file.name)

        with tempfile.NamedTemporaryFile(suffix='.srt', delete=False) as srt_file:
            srt_file.write(b'1\n00:00:00,000 --> 00:00:05,000\nTest subtitle\n')
            srt_path = Path(srt_file.name)

        return mkv_path, srt_path

    @patch('src.utils.ffmpeg_runner.run_ffmpeg')
    def test_add_subtitle_to_mkv_success(self, mock_run_ffmpeg):
        """Test successful subtitle muxing."""
        mock_run_ffmpeg.return_value = MagicMock(success=True)

        muxer = FFmpegMuxer()
        mkv_path, srt_path = self.create_test_files()

        try:
            result = muxer.add_subtitle_to_mkv(mkv_path, srt_path)

            assert result.success
            assert result.output_file == mkv_path
            mock_run_ffmpeg.assert_called_once()
        finally:
            mkv_path.unlink()
            srt_path.unlink()

    def test_add_subtitle_to_mkv_missing_mkv(self):
        """Test muxing with missing MKV file."""
        muxer = FFmpegMuxer()
        srt_path = Path("test.srt")
        srt_path.touch()

        try:
            result = muxer.add_subtitle_to_mkv(Path("nonexistent.mkv"), srt_path)

            assert not result.success
            assert "does not exist" in result.error_message
        finally:
            srt_path.unlink()

    def test_add_subtitle_to_mkv_missing_srt(self):
        """Test muxing with missing SRT file."""
        muxer = FFmpegMuxer()
        mkv_path = Path("test.mkv")
        mkv_path.touch()

        try:
            result = muxer.add_subtitle_to_mkv(mkv_path, Path("nonexistent.srt"))

            assert not result.success
            assert "does not exist" in result.error_message
        finally:
            mkv_path.unlink()

    @patch('src.utils.ffmpeg_runner.run_ffmpeg')
    def test_add_subtitle_to_mkv_ffmpeg_fail(self, mock_run_ffmpeg):
        """Test muxing when FFmpeg fails."""
        mock_run_ffmpeg.return_value = MagicMock(success=False, stderr="FFmpeg error")

        muxer = FFmpegMuxer()
        mkv_path, srt_path = self.create_test_files()

        try:
            result = muxer.add_subtitle_to_mkv(mkv_path, srt_path)

            assert not result.success
            assert "FFmpeg error" in result.error_message
        finally:
            mkv_path.unlink()
            srt_path.unlink()

    @patch('src.utils.ffmpeg_runner.run_ffmpeg')
    def test_add_subtitle_to_mkv_size_check(self, mock_run_ffmpeg):
        """Test muxing with size validation."""
        mock_run_ffmpeg.return_value = MagicMock(success=True)

        muxer = FFmpegMuxer()
        mkv_path, srt_path = self.create_test_files()

        # Make original file very small to trigger size check
        mkv_path.write_bytes(b'x' * 100)

        try:
            result = muxer.add_subtitle_to_mkv(mkv_path, srt_path)

            # Should fail size validation
            assert not result.success
            assert "size out of expected range" in result.error_message
        finally:
            mkv_path.unlink()
            srt_path.unlink()