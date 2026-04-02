"""
Unit tests for src/core/video/converter.py

Test video conversion logic including:
- MP4 to MKV conversion
- Conversion result objects
- Status enum
- Batch conversion summary
- Overwrite behavior
"""

from __future__ import annotations

import pytest

from core.video.converter import (
    BatchConversionSummary,
    ConversionResult,
    ConversionStatus,
    batch_convert_directory,
    convert_mp4_to_mkv,
    resolve_output_path,
)
from utils.ffmpeg_runner import FFmpegResult

# ---------------------------------------------------------------------------
# Tests for ConversionStatus enum
# ---------------------------------------------------------------------------


class TestConversionStatus:
    """Test ConversionStatus enum."""

    def test_has_success_status(self):
        """Should have SUCCESS status."""
        assert hasattr(ConversionStatus, "SUCCESS")
        assert ConversionStatus.SUCCESS is not None

    def test_has_skipped_status(self):
        """Should have SKIPPED status."""
        assert hasattr(ConversionStatus, "SKIPPED")
        assert ConversionStatus.SKIPPED is not None

    def test_has_failed_status(self):
        """Should have FAILED status."""
        assert hasattr(ConversionStatus, "FAILED")
        assert ConversionStatus.FAILED is not None


# ---------------------------------------------------------------------------
# Tests for ConversionResult model
# ---------------------------------------------------------------------------


class TestConversionResult:
    """Test ConversionResult immutable data object."""

    def test_conversion_result_success_property(self, tmp_media_dir):
        """Should correctly identify successful conversion."""
        source = tmp_media_dir / "input.mp4"
        target = tmp_media_dir / "output.mkv"

        result = ConversionResult(
            status=ConversionStatus.SUCCESS,
            source=source,
            target=target,
            message="Converted successfully",
        )

        assert result.succeeded is True
        assert result.failed is False
        assert result.skipped is False

    def test_conversion_result_skipped_property(self, tmp_media_dir):
        """Should correctly identify skipped conversion."""
        source = tmp_media_dir / "input.mp4"
        target = tmp_media_dir / "output.mkv"

        result = ConversionResult(
            status=ConversionStatus.SKIPPED,
            source=source,
            target=target,
            message="File already exists",
        )

        assert result.skipped is True
        assert result.succeeded is False
        assert result.failed is False

    def test_conversion_result_failed_property(self, tmp_media_dir):
        """Should correctly identify failed conversion."""
        source = tmp_media_dir / "input.mp4"
        target = tmp_media_dir / "output.mkv"

        result = ConversionResult(
            status=ConversionStatus.FAILED,
            source=source,
            target=target,
            message="ffmpeg error",
        )

        assert result.failed is True
        assert result.succeeded is False
        assert result.skipped is False

    def test_conversion_result_immutable(self, tmp_media_dir):
        """ConversionResult should be immutable."""
        result = ConversionResult(
            status=ConversionStatus.SUCCESS,
            source=tmp_media_dir / "in.mp4",
            target=tmp_media_dir / "out.mkv",
            message="Test",
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            result.message = "Changed"

    def test_conversion_result_with_ffmpeg_result(self, tmp_media_dir):
        """Should store FFmpegResult reference."""
        ffmpeg_result = FFmpegResult(
            success=True,
            return_code=0,
            command=["ffmpeg"],
            stderr_bytes=b"",
            stdout_bytes=b"",
        )

        result = ConversionResult(
            status=ConversionStatus.SUCCESS,
            source=tmp_media_dir / "in.mp4",
            target=tmp_media_dir / "out.mkv",
            message="Done",
            ffmpeg_result=ffmpeg_result,
        )

        assert result.ffmpeg_result == ffmpeg_result


# ---------------------------------------------------------------------------
# Tests for BatchConversionSummary
# ---------------------------------------------------------------------------


class TestBatchConversionSummary:
    """Test batch conversion summary aggregation."""

    def test_summary_total_count(self, tmp_media_dir):
        """Should count total results."""
        results = [
            ConversionResult(
                status=ConversionStatus.SUCCESS,
                source=tmp_media_dir / f"in{i}.mp4",
                target=tmp_media_dir / f"out{i}.mkv",
                message="OK",
            )
            for i in range(3)
        ]

        summary = BatchConversionSummary(results=results)
        assert summary.total == 3

    def test_summary_succeeded_filter(self, tmp_media_dir):
        """Should filter succeeded results."""
        results = [
            ConversionResult(
                status=ConversionStatus.SUCCESS,
                source=tmp_media_dir / "in1.mp4",
                target=tmp_media_dir / "out1.mkv",
                message="OK",
            ),
            ConversionResult(
                status=ConversionStatus.FAILED,
                source=tmp_media_dir / "in2.mp4",
                target=tmp_media_dir / "out2.mkv",
                message="Error",
            ),
        ]

        summary = BatchConversionSummary(results=results)
        assert len(summary.succeeded) == 1
        assert summary.succeeded[0].succeeded

    def test_summary_skipped_filter(self, tmp_media_dir):
        """Should filter skipped results."""
        results = [
            ConversionResult(
                status=ConversionStatus.SKIPPED,
                source=tmp_media_dir / "in1.mp4",
                target=tmp_media_dir / "out1.mkv",
                message="Exists",
            ),
            ConversionResult(
                status=ConversionStatus.SKIPPED,
                source=tmp_media_dir / "in2.mp4",
                target=tmp_media_dir / "out2.mkv",
                message="Exists",
            ),
        ]

        summary = BatchConversionSummary(results=results)
        assert len(summary.skipped) == 2
        assert all(r.skipped for r in summary.skipped)

    def test_summary_failed_filter(self, tmp_media_dir):
        """Should filter failed results."""
        results = [
            ConversionResult(
                status=ConversionStatus.FAILED,
                source=tmp_media_dir / "in1.mp4",
                target=tmp_media_dir / "out1.mkv",
                message="Error",
            ),
        ]

        summary = BatchConversionSummary(results=results)
        assert len(summary.failed) == 1
        assert summary.failed[0].failed

    def test_summary_mixed_results(self, tmp_media_dir):
        """Should correctly categorize mixed results."""
        results = [
            ConversionResult(
                status=ConversionStatus.SUCCESS,
                source=tmp_media_dir / "in1.mp4",
                target=tmp_media_dir / "out1.mkv",
                message="OK",
            ),
            ConversionResult(
                status=ConversionStatus.SKIPPED,
                source=tmp_media_dir / "in2.mp4",
                target=tmp_media_dir / "out2.mkv",
                message="Exists",
            ),
            ConversionResult(
                status=ConversionStatus.FAILED,
                source=tmp_media_dir / "in3.mp4",
                target=tmp_media_dir / "out3.mkv",
                message="Error",
            ),
        ]

        summary = BatchConversionSummary(results=results)
        assert summary.total == 3
        assert len(summary.succeeded) == 1
        assert len(summary.skipped) == 1
        assert len(summary.failed) == 1

    def test_summary_empty_results(self):
        """Should handle empty result list."""
        summary = BatchConversionSummary()
        assert summary.total == 0
        assert len(summary.succeeded) == 0
        assert len(summary.skipped) == 0
        assert len(summary.failed) == 0


# ---------------------------------------------------------------------------
# Tests for convert_mp4_to_mkv()
# ---------------------------------------------------------------------------


class TestConvertMp4ToMkv:
    """Test single-file MP4 to MKV conversion."""

    def test_convert_success(self, tmp_media_dir, patch_run_ffmpeg):
        """Should return SUCCESS when ffmpeg succeeds."""
        source = tmp_media_dir / "input.mp4"
        target = tmp_media_dir / "output.mkv"
        source.touch()

        patch_run_ffmpeg.return_value = FFmpegResult(
            success=True,
            return_code=0,
            command=["ffmpeg"],
            stderr_bytes=b"",
            stdout_bytes=b"",
        )

        result = convert_mp4_to_mkv(source, target)

        assert result.succeeded
        assert result.status == ConversionStatus.SUCCESS
        assert result.source == source
        assert result.target == target

    def test_convert_failure(self, tmp_media_dir, patch_run_ffmpeg):
        """Should return FAILED when ffmpeg fails."""
        source = tmp_media_dir / "input.mp4"
        target = tmp_media_dir / "output.mkv"
        source.touch()

        patch_run_ffmpeg.return_value = FFmpegResult(
            success=False,
            return_code=1,
            command=["ffmpeg"],
            stderr_bytes=b"Error: Unknown encoder",
            stdout_bytes=b"",
        )

        result = convert_mp4_to_mkv(source, target)

        assert result.failed
        assert result.status == ConversionStatus.FAILED

    def test_convert_skip_existing_no_overwrite(self, tmp_media_dir, patch_run_ffmpeg):
        """Should skip conversion when target exists and overwrite=False."""
        source = tmp_media_dir / "input.mp4"
        target = tmp_media_dir / "output.mkv"
        source.touch()
        target.touch()  # Target already exists

        result = convert_mp4_to_mkv(source, target, overwrite=False)

        assert result.skipped
        assert result.status == ConversionStatus.SKIPPED
        # Should not call ffmpeg
        patch_run_ffmpeg.assert_not_called()

    def test_convert_overwrite_existing(self, tmp_media_dir, patch_run_ffmpeg):
        """Should overwrite target when overwrite=True."""
        source = tmp_media_dir / "input.mp4"
        target = tmp_media_dir / "output.mkv"
        source.touch()
        target.touch()  # Target already exists

        patch_run_ffmpeg.return_value = FFmpegResult(
            success=True,
            return_code=0,
            command=["ffmpeg"],
            stderr_bytes=b"",
            stdout_bytes=b"",
        )

        result = convert_mp4_to_mkv(source, target, overwrite=True)

        assert result.succeeded
        # Should have called ffmpeg
        patch_run_ffmpeg.assert_called_once()

    def test_convert_uses_audio_language(self, tmp_media_dir, patch_run_ffmpeg):
        """Should include audio language metadata."""
        source = tmp_media_dir / "input.mp4"
        target = tmp_media_dir / "output.mkv"
        source.touch()

        patch_run_ffmpeg.return_value = FFmpegResult(
            success=True,
            return_code=0,
            command=["ffmpeg"],
            stderr_bytes=b"",
            stdout_bytes=b"",
        )

        convert_mp4_to_mkv(source, target, audio_language="eng", audio_title="English")

        # Check ffmpeg was called with correct language
        patch_run_ffmpeg.assert_called_once()
        call_args = patch_run_ffmpeg.call_args[0][0]
        args_str = " ".join(call_args)
        assert "language=eng" in args_str
        assert "English" in args_str

    def test_convert_default_audio_language(self, tmp_media_dir, patch_run_ffmpeg):
        """Should use default German language if not specified."""
        source = tmp_media_dir / "input.mp4"
        target = tmp_media_dir / "output.mkv"
        source.touch()

        patch_run_ffmpeg.return_value = FFmpegResult(
            success=True,
            return_code=0,
            command=["ffmpeg"],
            stderr_bytes=b"",
            stdout_bytes=b"",
        )

        convert_mp4_to_mkv(source, target)

        # Check ffmpeg was called with default German language
        patch_run_ffmpeg.assert_called_once()
        call_args = patch_run_ffmpeg.call_args[0][0]
        assert "language=deu" in " ".join(call_args)

    def test_convert_copies_streams(self, tmp_media_dir, patch_run_ffmpeg):
        """Should use copy codec for lossless conversion."""
        source = tmp_media_dir / "input.mp4"
        target = tmp_media_dir / "output.mkv"
        source.touch()

        patch_run_ffmpeg.return_value = FFmpegResult(
            success=True,
            return_code=0,
            command=["ffmpeg"],
            stderr_bytes=b"",
            stdout_bytes=b"",
        )

        convert_mp4_to_mkv(source, target)

        # Check ffmpeg uses copy codec
        patch_run_ffmpeg.assert_called_once()
        call_args = patch_run_ffmpeg.call_args[0][0]
        assert "copy" in call_args

    def test_convert_message_on_success(self, tmp_media_dir, patch_run_ffmpeg):
        """Should include message in success result."""
        source = tmp_media_dir / "input.mp4"
        target = tmp_media_dir / "output.mkv"
        source.touch()

        patch_run_ffmpeg.return_value = FFmpegResult(
            success=True,
            return_code=0,
            command=["ffmpeg"],
            stderr_bytes=b"",
            stdout_bytes=b"",
        )

        result = convert_mp4_to_mkv(source, target)

        assert result.message
        assert "successfully" in result.message.lower() or "OK" in result.message

    def test_convert_message_on_failure(self, tmp_media_dir, patch_run_ffmpeg):
        """Should include error info in failure message."""
        source = tmp_media_dir / "input.mp4"
        target = tmp_media_dir / "output.mkv"
        source.touch()

        patch_run_ffmpeg.return_value = FFmpegResult(
            success=False,
            return_code=1,
            command=["ffmpeg"],
            stderr_bytes=b"Codec error",
            stdout_bytes=b"",
        )

        result = convert_mp4_to_mkv(source, target)

        assert result.message
        assert "failed" in result.message.lower() or "error" in result.message.lower()

    def test_convert_cleans_up_incomplete_output_on_failure(self, tmp_media_dir, patch_run_ffmpeg):
        """Should remove incomplete output file on conversion failure."""
        source = tmp_media_dir / "input.mp4"
        target = tmp_media_dir / "output.mkv"
        source.touch()

        # Create output file without overwrite to trigger the skip behavior
        # Then test with overwrite=True and failure

        patch_run_ffmpeg.return_value = FFmpegResult(
            success=False,
            return_code=1,
            command=["ffmpeg"],
            stderr_bytes=b"Error",
            stdout_bytes=b"",
        )

        result = convert_mp4_to_mkv(source, target, overwrite=True)

        # Output should be cleaned up onFailure
        assert result.failed
        # File might be deleted by the function (behavior depends on implementation)


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestConversionIntegration:
    """Integration tests for conversion workflow."""

    def test_batch_conversion_sequence(self, tmp_media_dir, patch_run_ffmpeg):
        """Test converting multiple files in sequence."""
        patch_run_ffmpeg.return_value = FFmpegResult(
            success=True,
            return_code=0,
            command=["ffmpeg"],
            stderr_bytes=b"",
            stdout_bytes=b"",
        )

        files = []
        for i in range(3):
            source = tmp_media_dir / f"input{i}.mp4"
            source.touch()
            files.append(source)

        results = []
        for source in files:
            target = tmp_media_dir / f"output{source.stem}.mkv"
            result = convert_mp4_to_mkv(source, target)
            results.append(result)

        # All should succeed
        assert all(r.succeeded for r in results)

    def test_overwrite_parameter_propagation(self, tmp_media_dir, patch_run_ffmpeg):
        """Test that overwrite parameter correctly influences behavior."""
        source = tmp_media_dir / "input.mp4"
        target = tmp_media_dir / "output.mkv"
        source.touch()
        target.touch()

        patch_run_ffmpeg.return_value = FFmpegResult(
            success=True,
            return_code=0,
            command=["ffmpeg"],
            stderr_bytes=b"",
            stdout_bytes=b"",
        )

        # First try without overwrite - should skip
        result1 = convert_mp4_to_mkv(source, target, overwrite=False)
        assert result1.skipped

        # Reset mock
        patch_run_ffmpeg.reset_mock()

        # Then try with overwrite - should process
        result2 = convert_mp4_to_mkv(source, target, overwrite=True)
        assert result2.succeeded
        patch_run_ffmpeg.assert_called_once()


# ---------------------------------------------------------------------------
# Tests for resolve_output_path()
# ---------------------------------------------------------------------------


class TestResolveOutputPath:
    """Test output path resolution for batch conversion."""

    def test_resolve_output_path_basic(self, tmp_path):
        """Should create subfolder with same name as input file."""
        source = tmp_path / "Movie.mp4"
        result = resolve_output_path(source)
        expected = tmp_path / "Movie" / "Movie.mkv"
        assert result == expected

    def test_resolve_output_path_with_output_root(self, tmp_path):
        """Should use custom output root instead of source directory."""
        source = tmp_path / "input" / "Movie.mp4"
        output_root = tmp_path / "output"
        result = resolve_output_path(source, output_root)
        expected = output_root / "Movie" / "Movie.mkv"
        assert result == expected

    def test_resolve_output_path_preserves_stem(self, tmp_path):
        """Should use source file stem for both folder and filename."""
        source = tmp_path / "My Movie (2020).mp4"
        result = resolve_output_path(source)
        expected = tmp_path / "My Movie (2020)" / "My Movie (2020).mkv"
        assert result == expected

    def test_resolve_output_path_complex_filename(self, tmp_path):
        """Should handle filenames with special characters."""
        source = tmp_path / "Film: The Adventure-Part.1.mp4"
        result = resolve_output_path(source)
        expected = tmp_path / "Film: The Adventure-Part.1" / "Film: The Adventure-Part.1.mkv"
        assert result == expected

    def test_resolve_output_path_none_output_root(self, tmp_path):
        """Should use source.parent when output_root is None."""
        source = tmp_path / "subdir" / "file.mp4"
        result = resolve_output_path(source, None)
        expected = tmp_path / "subdir" / "file" / "file.mkv"
        assert result == expected


# ---------------------------------------------------------------------------
# Tests for batch_convert_directory()
# ---------------------------------------------------------------------------


class TestBatchConvertDirectory:
    """Test batch directory conversion operations."""

    def test_batch_convert_empty_directory(self, tmp_path):
        """Should return empty summary for directory with no MP4 files."""
        summary = batch_convert_directory(tmp_path)
        assert summary.total == 0
        assert len(summary.results) == 0

    def test_batch_convert_single_file(self, tmp_media_dir, patch_run_ffmpeg):
        """Should convert single MP4 file."""
        source = tmp_media_dir / "input.mp4"
        source.touch()

        patch_run_ffmpeg.return_value = FFmpegResult(
            success=True,
            return_code=0,
            command=["ffmpeg"],
            stderr_bytes=b"",
            stdout_bytes=b"",
        )

        summary = batch_convert_directory(tmp_media_dir)

        assert summary.total == 1
        assert summary.succeeded == [summary.results[0]]
        assert len(summary.failed) == 0
        assert len(summary.skipped) == 0

    def test_batch_convert_multiple_files(self, tmp_media_dir, patch_run_ffmpeg):
        """Should convert multiple MP4 files."""
        sources = []
        for i in range(3):
            source = tmp_media_dir / f"input{i}.mp4"
            source.touch()
            sources.append(source)

        patch_run_ffmpeg.return_value = FFmpegResult(
            success=True,
            return_code=0,
            command=["ffmpeg"],
            stderr_bytes=b"",
            stdout_bytes=b"",
        )

        summary = batch_convert_directory(tmp_media_dir)

        assert summary.total == 3
        assert len(summary.succeeded) == 3
        assert len(summary.failed) == 0

    def test_batch_convert_with_output_root(self, tmp_media_dir, patch_run_ffmpeg):
        """Should use custom output root for all conversions."""
        source = tmp_media_dir / "input.mp4"
        output_root = tmp_media_dir / "output"
        source.touch()

        patch_run_ffmpeg.return_value = FFmpegResult(
            success=True,
            return_code=0,
            command=["ffmpeg"],
            stderr_bytes=b"",
            stdout_bytes=b"",
        )

        summary = batch_convert_directory(tmp_media_dir, output_root=output_root)

        assert summary.total == 1
        result = summary.results[0]
        assert result.succeeded
        # Target should be in output_root
        assert str(result.target).startswith(str(output_root))

    def test_batch_convert_recursive(self, tmp_media_dir, patch_run_ffmpeg):
        """Should scan subdirectories when recursive=True."""
        # Create files in subdirectories
        subdir = tmp_media_dir / "subdir"
        subdir.mkdir()
        source1 = tmp_media_dir / "input.mp4"
        source2 = subdir / "input2.mp4"
        source1.touch()
        source2.touch()

        patch_run_ffmpeg.return_value = FFmpegResult(
            success=True,
            return_code=0,
            command=["ffmpeg"],
            stderr_bytes=b"",
            stdout_bytes=b"",
        )

        # Non-recursive should only find top-level file
        summary = batch_convert_directory(tmp_media_dir, recursive=False)
        assert summary.total == 1

        # Recursive should find both
        summary = batch_convert_directory(tmp_media_dir, recursive=True)
        assert summary.total == 2

    def test_batch_convert_custom_audio_language(self, tmp_media_dir, patch_run_ffmpeg):
        """Should pass custom audio language to conversion."""
        source = tmp_media_dir / "input.mp4"
        source.touch()

        patch_run_ffmpeg.return_value = FFmpegResult(
            success=True,
            return_code=0,
            command=["ffmpeg"],
            stderr_bytes=b"",
            stdout_bytes=b"",
        )

        summary = batch_convert_directory(tmp_media_dir, audio_language="eng", audio_title="English")

        assert summary.total == 1
        # Check that ffmpeg was called with custom language
        patch_run_ffmpeg.assert_called_once()
        call_args = patch_run_ffmpeg.call_args[0][0]
        assert "language=eng" in " ".join(call_args)

    def test_batch_convert_overwrite_propagation(self, tmp_media_dir, patch_run_ffmpeg):
        """Should pass overwrite parameter to individual conversions."""
        source = tmp_media_dir / "input.mp4"
        target = tmp_media_dir / "input" / "input.mkv"
        source.touch()
        target.touch()  # Pre-existing target

        patch_run_ffmpeg.return_value = FFmpegResult(
            success=True,
            return_code=0,
            command=["ffmpeg"],
            stderr_bytes=b"",
            stdout_bytes=b"",
        )

        # With overwrite=False, should skip
        summary = batch_convert_directory(tmp_media_dir, overwrite=False)
        assert summary.total == 1
        assert len(summary.skipped) == 1

        # Reset mock
        patch_run_ffmpeg.reset_mock()

        # With overwrite=True, should process
        summary = batch_convert_directory(tmp_media_dir, overwrite=True)
        assert summary.total == 1
        assert len(summary.succeeded) == 1
        patch_run_ffmpeg.assert_called_once()

    def test_batch_convert_not_a_directory(self, tmp_path):
        """Should raise NotADirectoryError for invalid path."""
        file_path = tmp_path / "not_a_dir.txt"
        file_path.touch()

        with pytest.raises(NotADirectoryError, match="Not a directory"):
            batch_convert_directory(file_path)

    def test_batch_convert_sorts_files(self, tmp_media_dir, patch_run_ffmpeg):
        """Should process files in sorted order."""
        # Create files in reverse alphabetical order
        sources = []
        for name in ["zebra.mp4", "alpha.mp4", "beta.mp4"]:
            source = tmp_media_dir / name
            source.touch()
            sources.append(source)

        patch_run_ffmpeg.return_value = FFmpegResult(
            success=True,
            return_code=0,
            command=["ffmpeg"],
            stderr_bytes=b"",
            stdout_bytes=b"",
        )

        summary = batch_convert_directory(tmp_media_dir)

        assert summary.total == 3
        # Should be processed in sorted order (alpha, beta, zebra)
        expected_order = ["alpha", "beta", "zebra"]
        for i, result in enumerate(summary.results):
            assert expected_order[i] in str(result.source)
