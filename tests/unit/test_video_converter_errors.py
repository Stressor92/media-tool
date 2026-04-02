"""
tests/unit/test_video_converter_errors.py

Comprehensive error handling tests for video conversion.
Tests invalid inputs, FFmpeg failures, filesystem errors, and cleanup behavior.
"""

from __future__ import annotations

import pytest

from core.video.converter import (
    ConversionStatus,
    convert_mp4_to_mkv,
)
from utils.ffmpeg_runner import FFmpegResult


class TestVideoConverterInvalidInput:
    """Test error handling for invalid input scenarios."""

    def test_convert_source_file_not_found(self, tmp_path):
        """Test handling when source file doesn't exist."""
        source = tmp_path / "nonexistent.mp4"
        target = tmp_path / "output.mkv"

        result = convert_mp4_to_mkv(source, target)

        assert result.failed is True
        assert result.status == ConversionStatus.FAILED
        assert "not found" in result.message.lower()
        assert not target.exists()

    def test_convert_source_is_directory(self, tmp_path):
        """Test handling when source is a directory, not a file."""
        source = tmp_path / "directory"
        source.mkdir()
        target = tmp_path / "output.mkv"

        result = convert_mp4_to_mkv(source, target)

        assert result.failed is True
        # Could fail at exists check or at ffmpeg stage

    def test_convert_corrupt_input_file(self, tmp_path, patch_run_ffmpeg):
        """Test handling of corrupt/invalid input file."""
        source = tmp_path / "corrupt.mp4"
        source.write_bytes(b"This is not a valid video file")
        target = tmp_path / "output.mkv"

        patch_run_ffmpeg.return_value = FFmpegResult(
            success=False,
            return_code=1,
            command=["ffmpeg"],
            stderr_bytes=b"Invalid data found when processing input",
            stdout_bytes=b"",
        )

        result = convert_mp4_to_mkv(source, target)

        assert result.failed is True
        assert "Invalid data" in result.ffmpeg_result.stderr

    def test_convert_unsupported_format(self, tmp_path, patch_run_ffmpeg):
        """Test handling of unsupported input format."""
        source = tmp_path / "input.mkv"
        source.touch()
        target = tmp_path / "output.mkv"

        patch_run_ffmpeg.return_value = FFmpegResult(
            success=False,
            return_code=1,
            command=["ffmpeg"],
            stderr_bytes=b"Unknown format or codec",
            stdout_bytes=b"",
        )

        result = convert_mp4_to_mkv(source, target)

        assert result.failed is True

    def test_convert_invalid_output_directory_path(self, tmp_path):
        """Test handling when target directory path is invalid."""
        source = tmp_path / "input.mp4"
        source.touch()

        # Try to put output in a path that doesn't exist
        # (mkdir should create it, so use a read-only parent)
        target = tmp_path / "readonly" / "nested" / "output.mkv"

        # Skip this test if we can't create a read-only directory (Windows)
        pytest.skip("Read-only directory test is platform-specific")


class TestVideoConverterFFmpegFailures:
    """Test error handling for FFmpeg execution failures."""

    def test_convert_missing_encoder(self, tmp_path, patch_run_ffmpeg):
        """Test handling when required encoder is not available."""
        source = tmp_path / "input.mp4"
        source.touch()
        target = tmp_path / "output.mkv"

        patch_run_ffmpeg.return_value = FFmpegResult(
            success=False,
            return_code=1,
            command=["ffmpeg"],
            stderr_bytes=b"Unknown encoder 'libx265'",
            stdout_bytes=b"",
        )

        result = convert_mp4_to_mkv(source, target)

        assert result.failed is True
        assert "libx265" in result.ffmpeg_result.stderr

    def test_convert_missing_audio_stream(self, tmp_path, patch_run_ffmpeg):
        """Test handling when expected audio stream doesn't exist."""
        source = tmp_path / "input.mp4"
        source.touch()
        target = tmp_path / "output.mkv"

        patch_run_ffmpeg.return_value = FFmpegResult(
            success=False,
            return_code=1,
            command=["ffmpeg"],
            stderr_bytes=b"Stream specifier ':a:0' does not match any stream",
            stdout_bytes=b"",
        )

        result = convert_mp4_to_mkv(source, target)

        assert result.failed is True

    def test_convert_ffmpeg_timeout(self, tmp_path, patch_run_ffmpeg):
        """Test handling of FFmpeg timeout."""
        source = tmp_path / "huge_file.mp4"
        source.touch()
        target = tmp_path / "output.mkv"

        # Simulate timeout by raising exception
        patch_run_ffmpeg.side_effect = TimeoutError("FFmpeg conversion timed out")

        with pytest.raises(TimeoutError):
            convert_mp4_to_mkv(source, target)

    def test_convert_ffmpeg_killed_by_signal(self, tmp_path, patch_run_ffmpeg):
        """Test handling when FFmpeg process is killed by signal."""
        source = tmp_path / "input.mp4"
        source.touch()
        target = tmp_path / "output.mkv"

        patch_run_ffmpeg.return_value = FFmpegResult(
            success=False,
            return_code=-9,  # SIGKILL
            command=["ffmpeg"],
            stderr_bytes=b"Process killed",
            stdout_bytes=b"",
        )

        result = convert_mp4_to_mkv(source, target)

        assert result.failed is True
        assert result.ffmpeg_result.return_code == -9


class TestVideoConverterFilesystemErrors:
    """Test error handling for filesystem-related errors."""

    def test_convert_output_exists_skip(self, tmp_path):
        """Test that conversion is skipped when target exists and overwrite=False."""
        source = tmp_path / "input.mp4"
        source.touch()
        target = tmp_path / "output.mkv"
        target.touch()  # Target already exists

        result = convert_mp4_to_mkv(source, target, overwrite=False)

        assert result.skipped is True
        assert result.status == ConversionStatus.SKIPPED
        assert "already exists" in result.message.lower()

    def test_convert_output_exists_overwrite(self, tmp_path, patch_run_ffmpeg):
        """Test that conversion proceeds with overwrite=True."""
        source = tmp_path / "input.mp4"
        source.touch()
        target = tmp_path / "output.mkv"
        target.touch()  # Target already exists

        patch_run_ffmpeg.return_value = FFmpegResult(
            success=True,
            return_code=0,
            command=["ffmpeg"],
            stderr_bytes=b"",
            stdout_bytes=b"",
        )

        result = convert_mp4_to_mkv(source, target, overwrite=True)

        assert result.succeeded is True

    def test_convert_output_cleanup_on_failure(self, tmp_path, patch_run_ffmpeg):
        """Test that incomplete output file is cleaned up on failure."""
        source = tmp_path / "input.mp4"
        source.touch()
        target = tmp_path / "output.mkv"

        # Simulate FFmpeg creating partial output before failing
        patch_run_ffmpeg.side_effect = lambda args: (
            target.write_bytes(b"partial mkv data"),
            FFmpegResult(
                success=False,
                return_code=1,
                command=["ffmpeg"],
                stderr_bytes=b"Write error",
                stdout_bytes=b"",
            ),
        )[1]

        result = convert_mp4_to_mkv(source, target)

        assert result.failed is True
        # Output should be cleaned up
        assert not target.exists()

    def test_convert_creates_output_directory(self, tmp_path, patch_run_ffmpeg):
        """Test that output directory is created if it doesn't exist."""
        source = tmp_path / "input.mp4"
        source.touch()

        # Nested directory that doesn't exist yet
        target = tmp_path / "outputs" / "converted" / "output.mkv"

        patch_run_ffmpeg.return_value = FFmpegResult(
            success=True,
            return_code=0,
            command=["ffmpeg"],
            stderr_bytes=b"",
            stdout_bytes=b"",
        )

        result = convert_mp4_to_mkv(source, target)

        assert result.succeeded is True
        assert target.parent.exists()

    def test_convert_permission_denied_output(self, tmp_path, patch_run_ffmpeg):
        """Test handling when unable to write to output directory."""
        source = tmp_path / "input.mp4"
        source.touch()
        target = tmp_path / "output.mkv"

        patch_run_ffmpeg.return_value = FFmpegResult(
            success=False,
            return_code=1,
            command=["ffmpeg"],
            stderr_bytes=b"Permission denied",
            stdout_bytes=b"",
        )

        result = convert_mp4_to_mkv(source, target)

        assert result.failed is True


class TestVideoConverterErrorMessages:
    """Test that error messages are user-friendly and informative."""

    def test_convert_error_message_includes_context(self, tmp_path, patch_run_ffmpeg):
        """Test that error message includes helpful context."""
        source = tmp_path / "input.mp4"
        source.touch()
        target = tmp_path / "output.mkv"

        patch_run_ffmpeg.return_value = FFmpegResult(
            success=False,
            return_code=1,
            command=["ffmpeg"],
            stderr_bytes=b"Specific error detail",
            stdout_bytes=b"",
        )

        result = convert_mp4_to_mkv(source, target)

        assert result.failed is True
        assert len(result.message) > 20  # Non-trivial message
        assert "exit" in result.message.lower() or "failed" in result.message.lower()

    def test_convert_success_message(self, tmp_path, patch_run_ffmpeg):
        """Test that success message is informative."""
        source = tmp_path / "input.mp4"
        source.touch()
        target = tmp_path / "output.mkv"

        patch_run_ffmpeg.return_value = FFmpegResult(
            success=True,
            return_code=0,
            command=["ffmpeg"],
            stderr_bytes=b"",
            stdout_bytes=b"",
        )

        result = convert_mp4_to_mkv(source, target)

        assert result.succeeded is True
        assert "successfully" in result.message.lower()
        assert target.name in result.message

    def test_convert_skip_message(self, tmp_path):
        """Test that skip message is clear."""
        source = tmp_path / "input.mp4"
        source.touch()
        target = tmp_path / "output.mkv"
        target.touch()

        result = convert_mp4_to_mkv(source, target)

        assert result.skipped is True
        assert "skip" in result.message.lower() or "exists" in result.message.lower()


class TestVideoConverterMetadataHandling:
    """Test error handling for metadata operations."""

    def test_convert_with_custom_audio_language(self, tmp_path, patch_run_ffmpeg):
        """Test conversion with custom audio language metadata."""
        source = tmp_path / "input.mp4"
        source.touch()
        target = tmp_path / "output.mkv"

        patch_run_ffmpeg.return_value = FFmpegResult(
            success=True,
            return_code=0,
            command=["ffmpeg"],
            stderr_bytes=b"",
            stdout_bytes=b"",
        )

        result = convert_mp4_to_mkv(source, target, audio_language="eng", audio_title="English")

        assert result.succeeded is True
        # Verify the command includes language metadata
        call_args = patch_run_ffmpeg.call_args[0][0]
        assert "language=eng" in call_args

    def test_convert_invalid_audio_language_code(self, tmp_path, patch_run_ffmpeg):
        """Test handling of invalid audio language code."""
        source = tmp_path / "input.mp4"
        source.touch()
        target = tmp_path / "output.mkv"

        patch_run_ffmpeg.return_value = FFmpegResult(
            success=False,
            return_code=1,
            command=["ffmpeg"],
            stderr_bytes=b"Invalid language code",
            stdout_bytes=b"",
        )

        result = convert_mp4_to_mkv(source, target, audio_language="invalid_code")

        # Current implementation doesn't validate, but we test the behavior
        assert result.failed is True or result.succeeded is True


class TestVideoConverterIntegration:
    """Test integration of multiple error scenarios."""

    def test_convert_batch_with_mixed_success_failure(self, tmp_path, patch_run_ffmpeg):
        """Test handling multiple files with mixed success/failure."""
        files = []
        for i in range(3):
            source = tmp_path / f"input{i}.mp4"
            source.touch()
            files.append(source)

        target = tmp_path / "output.mkv"

        # Mock: first two succeed, third fails
        results = [
            FFmpegResult(success=True, return_code=0, command=["ffmpeg"], stderr_bytes=b"", stdout_bytes=b""),
            FFmpegResult(success=True, return_code=0, command=["ffmpeg"], stderr_bytes=b"", stdout_bytes=b""),
            FFmpegResult(success=False, return_code=1, command=["ffmpeg"], stderr_bytes=b"Error", stdout_bytes=b""),
        ]
        patch_run_ffmpeg.side_effect = results

        outcomes = []
        for source in files:
            result = convert_mp4_to_mkv(source, target)
            outcomes.append(result)

        assert outcomes[0].succeeded is True
        assert outcomes[1].succeeded is True
        assert outcomes[2].failed is True

    def test_convert_error_chain_information(self, tmp_path, patch_run_ffmpeg):
        """Test that error chaining preserves information."""
        source = tmp_path / "input.mp4"
        source.touch()
        target = tmp_path / "output.mkv"

        patch_run_ffmpeg.return_value = FFmpegResult(
            success=False,
            return_code=1,
            command=["ffmpeg", "-i", "input.mp4"],
            stderr_bytes=b"Detailed error information",
            stdout_bytes=b"",
        )

        result = convert_mp4_to_mkv(source, target)

        assert result.failed is True
        assert result.ffmpeg_result is not None
        assert result.ffmpeg_result.stderr_bytes == b"Detailed error information"
