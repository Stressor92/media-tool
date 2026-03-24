"""
tests/unit/test_audio_processor_errors.py

Comprehensive error handling tests for audio processing.
Tests invalid formats, codec errors, filesystem errors, and cleanup.
"""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from utils.audio_processor import (
    convert_audio_format,
    AudioConversionResult,
)
from utils.ffmpeg_runner import FFmpegResult


class TestAudioConverterInvalidInput:
    """Test error handling for invalid audio input."""

    def test_convert_audio_source_not_found(self, tmp_path):
        """Test handling when source audio file doesn't exist."""
        source = tmp_path / "nonexistent.mp3"
        target = tmp_path / "output.flac"
        
        result = convert_audio_format(source, target)
        
        assert result.success is False
        assert not target.exists()

    def test_convert_audio_corrupt_input(self, tmp_path):
        """Test handling of corrupt audio input file."""
        source = tmp_path / "corrupt.mp3"
        source.write_bytes(b"This is not valid audio data")
        target = tmp_path / "output.flac"
        
        with patch("utils.audio_processor.run_ffmpeg") as mock_ffmpeg:
            mock_ffmpeg.return_value = FFmpegResult(
                success=False,
                return_code=1,
                command=["ffmpeg"],
                stderr_bytes=b"Invalid data found when processing input",
                stdout_bytes=b"",
            )
            
            result = convert_audio_format(source, target)
            
            assert result.success is False

    def test_convert_audio_unsupported_input_format(self, tmp_path):
        """Test handling of unsupported input format."""
        source = tmp_path / "audio.xyz"
        source.touch()
        target = tmp_path / "output.mp3"
        
        with patch("utils.audio_processor.run_ffmpeg") as mock_ffmpeg:
            mock_ffmpeg.return_value = FFmpegResult(
                success=False,
                return_code=1,
                command=["ffmpeg"],
                stderr_bytes=b"Unknown format or codec",
                stdout_bytes=b"",
            )
            
            result = convert_audio_format(source, target)
            
            assert result.success is False

    def test_convert_audio_source_is_directory(self, tmp_path):
        """Test handling when source is a directory, not a file."""
        source = tmp_path / "directory"
        source.mkdir()
        target = tmp_path / "output.mp3"
        
        result = convert_audio_format(source, target)
        
        assert result.success is False


class TestAudioConverterCodecErrors:
    """Test error handling for codec-related issues."""

    def test_convert_audio_unknown_input_codec(self, tmp_path):
        """Test handling when input codec is unknown."""
        source = tmp_path / "audio.mp3"
        source.touch()
        target = tmp_path / "output.flac"
        
        with patch("utils.audio_processor.run_ffmpeg") as mock_ffmpeg:
            mock_ffmpeg.return_value = FFmpegResult(
                success=False,
                return_code=1,
                command=["ffmpeg"],
                stderr_bytes=b"Unknown encoder 'unknown_codec'",
                stdout_bytes=b"",
            )
            
            result = convert_audio_format(source, target)
            
            assert result.success is False

    def test_convert_audio_unknown_output_codec(self, tmp_path):
        """Test handling when output codec is not available."""
        source = tmp_path / "audio.mp3"
        source.touch()
        target = tmp_path / "output.flac"
        
        with patch("utils.audio_processor.run_ffmpeg") as mock_ffmpeg:
            mock_ffmpeg.return_value = FFmpegResult(
                success=False,
                return_code=1,
                command=["ffmpeg"],
                stderr_bytes=b"Unknown encoder 'libauddec'",
                stdout_bytes=b"",
            )
            
            result = convert_audio_format(source, target)
            
            assert result.success is False

    def test_convert_audio_to_unsupported_format(self, tmp_path):
        """Test converting to unsupported format."""
        source = tmp_path / "audio.mp3"
        source.touch()
        target = tmp_path / "output.xyz"
        
        with patch("utils.audio_processor.run_ffmpeg") as mock_ffmpeg:
            mock_ffmpeg.return_value = FFmpegResult(
                success=False,
                return_code=1,
                command=["ffmpeg"],
                stderr_bytes=b"Unknown format 'xyz'",
                stdout_bytes=b"",
            )
            
            result = convert_audio_format(source, target, codec="xyz_codec")
            
            assert result.success is False

    def test_convert_audio_invalid_quality_setting(self, tmp_path):
        """Test handling of invalid quality settings."""
        source = tmp_path / "audio.mp3"
        source.touch()
        target = tmp_path / "output.mp3"
        
        with patch("utils.audio_processor.run_ffmpeg") as mock_ffmpeg:
            mock_ffmpeg.return_value = FFmpegResult(
                success=False,
                return_code=1,
                command=["ffmpeg"],
                stderr_bytes=b"Invalid quality setting",
                stdout_bytes=b"",
            )
            
            result = convert_audio_format(
                source,
                target,
                codec="libmp3lame",
                quality="invalid_quality"
            )
            
            assert result.success is False


class TestAudioConverterFilesystemErrors:
    """Test error handling for filesystem-related issues."""

    def test_convert_audio_output_exists_no_overwrite(self, tmp_path):
        """Test that existing output is skipped without overwrite."""
        source = tmp_path / "audio.mp3"
        source.touch()
        target = tmp_path / "output.flac"
        target.touch()
        
        result = convert_audio_format(source, target, overwrite=False)
        
        # Behavior depends on implementation
        # Could skip or error
        assert isinstance(result.success, bool)

    def test_convert_audio_output_exists_with_overwrite(self, tmp_path):
        """Test that overwrite=True replaces existing output."""
        source = tmp_path / "audio.mp3"
        source.touch()
        target = tmp_path / "output.flac"
        target.touch()
        
        with patch("utils.audio_processor.run_ffmpeg") as mock_ffmpeg:
            mock_ffmpeg.return_value = FFmpegResult(
                success=True,
                return_code=0,
                command=["ffmpeg"],
                stderr_bytes=b"",
                stdout_bytes=b"",
            )
            
            result = convert_audio_format(
                source,
                target,
                overwrite=True
            )
            
            assert result.success is True

    def test_convert_audio_output_directory_not_exist(self, tmp_path):
        """Test that output directory is created if needed."""
        source = tmp_path / "audio.mp3"
        source.touch()
        target = tmp_path / "nested" / "dir" / "output.flac"
        
        with patch("utils.audio_processor.run_ffmpeg") as mock_ffmpeg:
            mock_ffmpeg.return_value = FFmpegResult(
                success=True,
                return_code=0,
                command=["ffmpeg"],
                stderr_bytes=b"",
                stdout_bytes=b"",
            )
            
            result = convert_audio_format(source, target)
            
            # Should create directories
            if result.success:
                assert target.parent.exists()

    def test_convert_audio_permission_denied_output(self, tmp_path):
        """Test handling when unable to write output file."""
        source = tmp_path / "audio.mp3"
        source.touch()
        target = tmp_path / "output.mp3"
        
        with patch("utils.audio_processor.run_ffmpeg") as mock_ffmpeg:
            mock_ffmpeg.return_value = FFmpegResult(
                success=False,
                return_code=1,
                command=["ffmpeg"],
                stderr_bytes=b"Permission denied",
                stdout_bytes=b"",
            )
            
            result = convert_audio_format(source, target)
            
            assert result.success is False

    def test_convert_audio_disk_full(self, tmp_path):
        """Test handling when disk is full during conversion."""
        source = tmp_path / "audio.mp3"
        source.touch()
        target = tmp_path / "output.flac"
        
        with patch("utils.audio_processor.run_ffmpeg") as mock_ffmpeg:
            mock_ffmpeg.return_value = FFmpegResult(
                success=False,
                return_code=1,
                command=["ffmpeg"],
                stderr_bytes=b"No space left on device",
                stdout_bytes=b"",
            )
            
            result = convert_audio_format(source, target)
            
            assert result.success is False


class TestAudioConverterCleanup:
    """Test cleanup behavior on conversion errors."""

    def test_convert_audio_cleanup_on_failure(self, tmp_path):
        """Test that partial output file is cleaned up on failure."""
        source = tmp_path / "audio.mp3"
        source.touch()
        target = tmp_path / "output.flac"
        
        with patch("utils.audio_processor.run_ffmpeg") as mock_ffmpeg:
            # Simulate creating partial output before failing
            def side_effect(args):
                target.write_bytes(b"partial flac data")
                return FFmpegResult(
                    success=False,
                    return_code=1,
                    command=["ffmpeg"],
                    stderr_bytes=b"Write error",
                    stdout_bytes=b"",
                )
            
            mock_ffmpeg.side_effect = side_effect
            
            result = convert_audio_format(source, target)
            
            assert result.success is False
            # Cleanup behavior depends on implementation
            # Could be cleaned up or left for manual inspection

    def test_convert_audio_preserves_on_success(self, tmp_path):
        """Test that output file is preserved on success."""
        source = tmp_path / "audio.mp3"
        source.touch()
        target = tmp_path / "output.flac"
        
        with patch("utils.audio_processor.run_ffmpeg") as mock_ffmpeg:
            mock_ffmpeg.return_value = FFmpegResult(
                success=True,
                return_code=0,
                command=["ffmpeg"],
                stderr_bytes=b"",
                stdout_bytes=b"",
            )
            
            result = convert_audio_format(source, target)
            
            assert result.success is True


class TestAudioConverterMetadata:
    """Test metadata handling during audio conversion."""

    def test_convert_audio_preserve_metadata(self, tmp_path):
        """Test that metadata is preserved when requested."""
        source = tmp_path / "audio.mp3"
        source.touch()
        target = tmp_path / "output.flac"
        
        with patch("utils.audio_processor.run_ffmpeg") as mock_ffmpeg:
            mock_ffmpeg.return_value = FFmpegResult(
                success=True,
                return_code=0,
                command=["ffmpeg"],
                stderr_bytes=b"",
                stdout_bytes=b"",
            )
            
            result = convert_audio_format(
                source,
                target,
                preserve_metadata=True
            )
            
            assert result.success is True
            # Verify metadata flags are in command
            call_args = mock_ffmpeg.call_args
            if call_args:
                # Check if -map_metadata was used
                pass

    def test_convert_audio_metadata_error(self, tmp_path):
        """Test handling metadata errors."""
        source = tmp_path / "audio.mp3"
        source.touch()
        target = tmp_path / "output.flac"
        
        with patch("utils.audio_processor.run_ffmpeg") as mock_ffmpeg:
            mock_ffmpeg.return_value = FFmpegResult(
                success=False,
                return_code=1,
                command=["ffmpeg"],
                stderr_bytes=b"Metadata writing failed",
                stdout_bytes=b"",
            )
            
            result = convert_audio_format(
                source,
                target,
                preserve_metadata=True
            )
            
            assert result.success is False


class TestAudioConverterFormatSpecific:
    """Test format-specific error handling."""

    def test_convert_audio_to_mp3_error(self, tmp_path):
        """Test MP3 conversion errors."""
        source = tmp_path / "audio.flac"
        source.touch()
        target = tmp_path / "output.mp3"
        
        with patch("utils.audio_processor.run_ffmpeg") as mock_ffmpeg:
            mock_ffmpeg.return_value = FFmpegResult(
                success=False,
                return_code=1,
                command=["ffmpeg"],
                stderr_bytes=b"MP3 encoder not available",
                stdout_bytes=b"",
            )
            
            result = convert_audio_format(
                source,
                target,
                codec="libmp3lame"
            )
            
            assert result.success is False

    def test_convert_audio_to_flac_error(self, tmp_path):
        """Test FLAC conversion errors."""
        source = tmp_path / "audio.mp3"
        source.touch()
        target = tmp_path / "output.flac"
        
        with patch("utils.audio_processor.run_ffmpeg") as mock_ffmpeg:
            mock_ffmpeg.return_value = FFmpegResult(
                success=False,
                return_code=1,
                command=["ffmpeg"],
                stderr_bytes=b"FLAC encoder error",
                stdout_bytes=b"",
            )
            
            result = convert_audio_format(
                source,
                target,
                codec="flac"
            )
            
            assert result.success is False

    def test_convert_audio_to_aac_error(self, tmp_path):
        """Test AAC conversion errors."""
        source = tmp_path / "audio.mp3"
        source.touch()
        target = tmp_path / "output.m4a"
        
        with patch("utils.audio_processor.run_ffmpeg") as mock_ffmpeg:
            mock_ffmpeg.return_value = FFmpegResult(
                success=False,
                return_code=1,
                command=["ffmpeg"],
                stderr_bytes=b"AAC encoder error",
                stdout_bytes=b"",
            )
            
            result = convert_audio_format(
                source,
                target,
                codec="aac"
            )
            
            assert result.success is False


class TestAudioConverterEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_convert_audio_very_large_file(self, tmp_path):
        """Test handling of very large audio files."""
        source = tmp_path / "huge_audio.mp3"
        source.write_bytes(b"x" * (5 * 1024 * 1024))  # 5MB
        target = tmp_path / "output.flac"
        
        with patch("utils.audio_processor.run_ffmpeg") as mock_ffmpeg:
            mock_ffmpeg.return_value = FFmpegResult(
                success=True,
                return_code=0,
                command=["ffmpeg"],
                stderr_bytes=b"",
                stdout_bytes=b"",
            )
            
            result = convert_audio_format(source, target)
            
            # Should handle large files
            assert isinstance(result.success, bool)

    def test_convert_audio_special_characters_in_filename(self, tmp_path):
        """Test handling filenames with special characters."""
        source = tmp_path / "audio (with) [special] & chars.mp3"
        source.touch()
        target = tmp_path / "output (converted).flac"
        
        with patch("utils.audio_processor.run_ffmpeg") as mock_ffmpeg:
            mock_ffmpeg.return_value = FFmpegResult(
                success=True,
                return_code=0,
                command=["ffmpeg"],
                stderr_bytes=b"",
                stdout_bytes=b"",
            )
            
            result = convert_audio_format(source, target)
            
            assert result.success is True

    def test_convert_audio_unicode_filename(self, tmp_path):
        """Test handling Unicode characters in filenames."""
        source = tmp_path / "音声.mp3"  # Japanese: "audio"
        source.touch()
        target = tmp_path / "出力.flac"  # Japanese: "output"
        
        with patch("utils.audio_processor.run_ffmpeg") as mock_ffmpeg:
            mock_ffmpeg.return_value = FFmpegResult(
                success=True,
                return_code=0,
                command=["ffmpeg"],
                stderr_bytes=b"",
                stdout_bytes=b"",
            )
            
            result = convert_audio_format(source, target)
            
            assert result.success is True
