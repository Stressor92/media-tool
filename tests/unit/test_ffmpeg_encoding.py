"""
tests/unit/test_ffmpeg_encoding.py

Unit tests for FFmpeg encoding/decoding with non-ASCII characters.
"""

from utils.ffmpeg_runner import FFmpegResult


class TestFFmpegResultEncoding:
    """Test FFmpegResult handles non-ASCII bytes safely."""

    def test_stderr_decoding_ascii(self):
        """Test decoding pure ASCII stderr."""
        result = FFmpegResult(
            success=False,
            return_code=1,
            command=["ffmpeg", "-i", "test.mp4"],
            stderr_bytes=b"normal ascii error message",
            stdout_bytes=b"",
        )

        assert isinstance(result.stderr, str)
        assert "normal ascii error message" in result.stderr

    def test_stderr_decoding_non_ascii(self):
        """Test decoding non-ASCII stderr with safe error handling."""
        # UTF-8 bytes with characters that might fail: ä, ö, ü
        result = FFmpegResult(
            success=False,
            return_code=1,
            command=["ffmpeg", "-i", "tëst.mp4"],
            stderr_bytes=b"Error with \xe4\xf6\xfc umlaut bytes",  # Non-UTF8 sequence
            stdout_bytes=b"",
        )

        # Should decode without raising UnicodeDecodeError
        stderr_str = result.stderr
        assert isinstance(stderr_str, str)
        assert len(stderr_str) > 0  # Should have decoded with 'replace'

    def test_stdout_decoding_ascii(self):
        """Test decoding pure ASCII stdout."""
        result = FFmpegResult(
            success=True,
            return_code=0,
            command=["ffmpeg", "-i", "test.mp4"],
            stderr_bytes=b"",
            stdout_bytes=b"frame= 100 fps=50",
        )

        assert isinstance(result.stdout, str)
        assert "frame= 100 fps=50" in result.stdout

    def test_stdout_decoding_non_ascii(self):
        """Test decoding non-ASCII stdout."""
        result = FFmpegResult(
            success=True,
            return_code=0,
            command=["ffmpeg"],
            stderr_bytes=b"",
            stdout_bytes=b"Output: \xe4\xf6\xfc",  # Non-UTF8 sequence
        )

        # Should decode without raising
        stdout_str = result.stdout
        assert isinstance(stdout_str, str)

    def test_stderr_property_called_multiple_times(self):
        """Test that stderr property can be called multiple times safely."""
        result = FFmpegResult(
            success=False,
            return_code=1,
            command=["ffmpeg"],
            stderr_bytes=b"Error: \xe4\xf6\xfc invalid chars",
            stdout_bytes=b"",
        )

        # Should be consistent across multiple calls
        stderr1 = result.stderr
        stderr2 = result.stderr

        assert stderr1 == stderr2
        assert isinstance(stderr1, str)
        assert isinstance(stderr2, str)

    def test_stdout_property_called_multiple_times(self):
        """Test that stdout property can be called multiple times safely."""
        result = FFmpegResult(
            success=True,
            return_code=0,
            command=["ffmpeg"],
            stderr_bytes=b"",
            stdout_bytes=b"Output: \xe4\xf6\xfc valid chars",
        )

        # Should be consistent across multiple calls
        stdout1 = result.stdout
        stdout2 = result.stdout

        assert stdout1 == stdout2
        assert isinstance(stdout1, str)
        assert isinstance(stdout2, str)

    def test_failed_property_still_works(self):
        """Test that failed property still works with new structure."""
        result = FFmpegResult(success=False, return_code=1, command=["ffmpeg"], stderr_bytes=b"Error", stdout_bytes=b"")

        assert result.failed is True
        assert result.success is False

    def test_success_with_empty_output(self):
        """Test successful command with no output."""
        result = FFmpegResult(success=True, return_code=0, command=["ffmpeg"], stderr_bytes=b"", stdout_bytes=b"")

        assert result.success is True
        assert result.stderr == ""
        assert result.stdout == ""

    def test_utf8_encoded_characters(self):
        """Test properly UTF-8 encoded non-ASCII characters."""
        # Properly encoded UTF-8 bytes for "Tëst"
        result = FFmpegResult(
            success=False, return_code=1, command=["ffmpeg"], stderr_bytes="Tëst Error".encode(), stdout_bytes=b""
        )

        assert "Tëst" in result.stderr
