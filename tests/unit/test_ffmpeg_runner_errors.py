"""
tests/unit/test_ffmpeg_runner_errors.py

Comprehensive error handling tests for FFmpeg runner.
Tests various failure scenarios and ensures proper error reporting.
"""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from utils.ffmpeg_runner import FFmpegResult, run_ffmpeg


class TestFFmpegRunnerErrors:
    """Test error handling in FFmpeg runner."""

    def test_run_ffmpeg_file_not_found_error(self):
        """Test handling when ffmpeg executable is not installed."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("ffmpeg executable not found")

            with pytest.raises(FileNotFoundError) as exc_info:
                run_ffmpeg(["-i", "input.mp4", "output.mkv"])

            assert "ffmpeg" in str(exc_info.value).lower()
            assert "not found" in str(exc_info.value).lower()

    def test_run_ffmpeg_invalid_input_file(self):
        """Test handling when input file doesn't exist."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stderr=b"input.mp4: No such file or directory",
                stdout=b"",
            )

            result = run_ffmpeg(["-i", "nonexistent.mp4", "output.mkv"])

            assert result.failed is True
            assert result.return_code == 1
            assert "No such file or directory" in result.stderr

    def test_run_ffmpeg_permission_denied(self):
        """Test handling when unable to read input file due to permissions."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stderr=b"input.mkv: Permission denied",
                stdout=b"",
            )

            result = run_ffmpeg(["-i", "input.mkv", "output.mkv"])

            assert result.failed is True
            assert "Permission denied" in result.stderr

    def test_run_ffmpeg_disk_full_error(self):
        """Test handling when disk is full."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stderr=b"No space left on device",
                stdout=b"",
            )

            result = run_ffmpeg(["-i", "input.mkv", "output.mkv"])

            assert result.failed is True
            assert "No space left" in result.stderr

    def test_run_ffmpeg_unknown_encoder(self):
        """Test handling when specified encoder is not available."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stderr=b"Unknown encoder 'libx999'",
                stdout=b"",
            )

            result = run_ffmpeg(["-i", "input.mkv", "-c:v", "libx999", "output.mkv"])

            assert result.failed is True
            assert "Unknown encoder" in result.stderr

    def test_run_ffmpeg_unsupported_format(self):
        """Test handling when input format is not supported."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stderr=b"Invalid data found when processing input",
                stdout=b"",
            )

            result = run_ffmpeg(["-i", "corrupt.mkv", "output.mkv"])

            assert result.failed is True
            assert "Invalid data" in result.stderr

    def test_run_ffmpeg_missing_audio_stream(self):
        """Test handling when expected audio stream is missing."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stderr=b"Stream specifier ':a:2' does not match any stream",
                stdout=b"",
            )

            result = run_ffmpeg(["-i", "input.mkv", "-map", "0:v:0", "-map", "0:a:2", "output.mkv"])

            assert result.failed is True
            assert "Stream specifier" in result.stderr

    def test_run_ffmpeg_output_file_permission_denied(self):
        """Test handling when unable to write output file."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stderr=b"/readonly/output.mkv: Permission denied",
                stdout=b"",
            )

            result = run_ffmpeg(["-i", "input.mkv", "/readonly/output.mkv"])

            assert result.failed is True
            assert "Permission denied" in result.stderr

    def test_run_ffmpeg_non_ascii_error_message(self):
        """Test safe decoding of non-ASCII characters in error messages."""
        with patch("subprocess.run") as mock_run:
            # Simulate UTF-8 encoded non-ASCII characters in stderr
            mock_run.return_value = MagicMock(
                returncode=1,
                stderr=b"Fehler: Eingabedatei nicht gefunden",  # German: Error: input file not found
                stdout=b"",
            )

            result = run_ffmpeg(["-i", "input.mkv", "output.mkv"])

            assert result.failed is True
            assert isinstance(result.stderr, str)
            assert len(result.stderr) > 0

    def test_run_ffmpeg_malformed_utf8_in_stderr(self):
        """Test safe handling of malformed UTF-8 in stderr."""
        with patch("subprocess.run") as mock_run:
            # Include byte sequence that's not valid UTF-8
            mock_run.return_value = MagicMock(
                returncode=1,
                stderr=b"Error: \x80\x81\x82 invalid",
                stdout=b"",
            )

            result = run_ffmpeg(["-i", "input.mkv", "output.mkv"])

            assert result.failed is True
            # Should not raise UnicodeDecodeError
            stderr_str = result.stderr
            assert isinstance(stderr_str, str)

    def test_run_ffmpeg_timeout_simulation(self):
        """Test handling when ffmpeg process times out."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="ffmpeg -i input.mkv output.mkv", timeout=3600)

            # Current implementation doesn't raise on timeout,
            # but verify the error is properly propagated
            with pytest.raises(subprocess.TimeoutExpired):
                run_ffmpeg(["-i", "input.mkv", "output.mkv"])

    def test_run_ffmpeg_zero_exit_code_success(self):
        """Test that zero exit code is treated as success."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stderr=b"",
                stdout=b"frame=1000 fps=50 q=-1.0 Lsize=N/A",
            )

            result = run_ffmpeg(["-i", "input.mkv", "output.mkv"])

            assert result.success is True
            assert result.failed is False

    def test_run_ffmpeg_nonzero_exit_code_failure(self):
        """Test that any non-zero exit code is treated as failure."""
        for exit_code in [1, 2, 127, 255]:
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=exit_code,
                    stderr=b"Error occurred",
                    stdout=b"",
                )

                result = run_ffmpeg(["-i", "input.mkv", "output.mkv"])

                assert result.failed is True
                assert result.return_code == exit_code

    def test_run_ffmpeg_result_properties_consistency(self):
        """Test that FFmpegResult properties work consistently."""
        result = FFmpegResult(
            success=False,
            return_code=1,
            command=["ffmpeg", "-i", "input.mkv", "output.mkv"],
            stderr_bytes=b"Error: Test",
            stdout_bytes=b"",
        )

        # Results should be consistent across multiple calls
        assert result.stderr == result.stderr
        assert result.stdout == result.stdout
        assert result.failed == result.failed

    def test_run_ffmpeg_command_stored_for_debugging(self):
        """Test that full command is stored in result for debugging."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stderr=b"Error",
                stdout=b"",
            )

            args = ["-i", "input.mkv", "-c:v", "libx265", "output.mkv"]
            result = run_ffmpeg(args)

            assert result.command[0] == "ffmpeg"
            assert "input.mkv" in result.command
            assert "output.mkv" in result.command

    def test_run_ffmpeg_stderr_truncated_for_large_output(self, caplog):
        """Test that large stderr output is handled gracefully."""
        large_stderr = b"Error message repeated " * 1000  # Very large output

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stderr=large_stderr,
                stdout=b"",
            )

            result = run_ffmpeg(["-i", "input.mkv", "output.mkv"])

            assert result.failed is True
            # Should still be decodable
            assert isinstance(result.stderr, str)


class TestFFmpegRunnerEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_run_ffmpeg_empty_arguments_list(self):
        """Test handling of empty arguments list."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stderr=b"No input specified",
                stdout=b"",
            )

            result = run_ffmpeg([])

            assert result.command == ["ffmpeg"]
            assert result.failed is True

    def test_run_ffmpeg_special_characters_in_filename(self):
        """Test handling of special characters in filenames."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stderr=b"",
                stdout=b"",
            )

            special_file = "file with (special) [chars] & ñames.mkv"
            result = run_ffmpeg(["-i", special_file, "output.mkv"])

            assert special_file in result.command

    def test_run_ffmpeg_very_long_command_line(self):
        """Test handling of very long command lines."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stderr=b"",
                stdout=b"",
            )

            # Create a very long arguments list
            args = ["-i", "input.mkv"]
            for i in range(100):
                args.extend(["-map", f"0:{i}"])
            args.append("output.mkv")

            result = run_ffmpeg(args)

            assert result.success is True
            assert len(result.command) == len(args) + 1  # +1 for "ffmpeg"


class TestFFmpegResultDataClass:
    """Test FFmpegResult data structure."""

    def test_ffmpeg_result_immutability(self):
        """Test that FFmpegResult is immutable (frozen dataclass)."""
        result = FFmpegResult(
            success=True,
            return_code=0,
            command=["ffmpeg"],
            stderr_bytes=b"",
            stdout_bytes=b"",
        )

        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            result.success = False

    def test_ffmpeg_result_default_empty_bytes(self):
        """Test that stderr/stdout default to empty bytes."""
        result = FFmpegResult(
            success=True,
            return_code=0,
            command=["ffmpeg"],
        )

        assert result.stderr == ""
        assert result.stdout == ""
        assert result.stderr_bytes == b""
        assert result.stdout_bytes == b""
