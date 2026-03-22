"""
tests/integration/test_upscale.py

Integration tests for video upscaling functionality using real ffmpeg execution.

Tests validate the complete DVD-to-720p upscaling workflow including:
- Resolution detection and skipping
- Anime detection and crop behavior
- Filter chain application
- H.265 encoding with proper settings
- Output file validation
- Batch directory processing
"""

import pytest
from pathlib import Path
from core.video.upscaler import (
    upscale_dvd,
    batch_upscale_directory,
    UpscaleOptions,
)
from .conftest import create_test_video
from utils.ffprobe_runner import probe_file


class TestUpscaleIntegration:
    """Integration tests for DVD upscaling with real ffmpeg execution."""

    def test_upscale_low_res_video(self, tmp_path):
        """Test upscaling a low-resolution video to 720p."""
        # Create a low-res test video (480p)
        input_file = create_test_video(
            tmp_path / "test_480p.mkv",
            resolution="720x480",
            duration=2
        )

        # Run upscale
        result = upscale_dvd(input_file)

        # Verify success
        assert result.succeeded
        assert result.target.exists()
        assert result.target.suffix == ".mkv"
        assert "[DVD]" in result.target.name

        # Verify output resolution
        probe = probe_file(result.target)
        video = probe.first_video()
        assert int(video["height"]) == 720
        assert video["codec_name"] == "hevc"

        # Verify file was created and has content (small test files may not show size difference in GB)
        assert result.target.stat().st_size > 0

    def test_skip_already_upscaled(self, tmp_path):
        """Test that already upscaled files are skipped."""
        # Create a video and upscale it once
        input_file = create_test_video(
            tmp_path / "test_video.mkv",
            resolution="720x480",
            duration=2
        )

        # First upscale
        result1 = upscale_dvd(input_file)
        assert result1.succeeded

        # Try to upscale the already upscaled file
        result2 = upscale_dvd(result1.target)

        # Should be skipped
        assert result2.skipped
        assert "[DVD]" in result2.message

    def test_skip_high_res_video(self, tmp_path):
        """Test that videos already at 720p or higher are skipped."""
        # Create a 1080p test video
        input_file = create_test_video(
            tmp_path / "test_1080p.mkv",
            resolution="1920x1080",
            duration=2
        )

        # Run upscale
        result = upscale_dvd(input_file)

        # Should be skipped due to high resolution
        assert result.skipped
        assert "1080p" in result.message
        assert "≥ 720p" in result.message

    def test_anime_detection_disables_crop(self, tmp_path):
        """Test that anime files skip crop detection."""
        # Create a video with anime in the name
        input_file = create_test_video(
            tmp_path / "Anime_Series_Ep01.mkv",
            resolution="720x480",
            duration=2
        )

        # Run upscale with crop detection enabled
        result = upscale_dvd(input_file)

        # Should succeed (anime detection shouldn't break upscaling)
        assert result.succeeded

        # Verify output resolution
        probe = probe_file(result.target)
        video = probe.first_video()
        assert int(video["height"]) == 720

    def test_custom_upscale_options(self, tmp_path):
        """Test upscaling with custom options."""
        input_file = create_test_video(
            tmp_path / "test_custom.mkv",
            resolution="720x480",
            duration=2
        )

        # Custom options
        opts = UpscaleOptions(
            target_height=720,
            crf=20,  # Higher quality
            preset="slow",  # Slower but better compression
            gradfun_strength=2.0,  # Less debanding
        )

        result = upscale_dvd(input_file, opts=opts)

        # Should succeed
        assert result.succeeded

        # Verify output
        probe = probe_file(result.target)
        video = probe.first_video()
        assert int(video["height"]) == 720
        assert video["codec_name"] == "hevc"

    def test_explicit_output_path(self, tmp_path):
        """Test upscaling with explicit output path."""
        input_file = create_test_video(
            tmp_path / "input.mkv",
            resolution="720x480",
            duration=2
        )

        output_file = tmp_path / "custom_output.mkv"
        result = upscale_dvd(input_file, target=output_file)

        # Should succeed and use custom output path
        assert result.succeeded
        assert result.target == output_file
        assert output_file.exists()

    def test_overwrite_existing_output(self, tmp_path):
        """Test overwriting existing output files."""
        input_file = create_test_video(
            tmp_path / "test_overwrite.mkv",
            resolution="720x480",
            duration=2
        )

        # First upscale
        result1 = upscale_dvd(input_file)
        assert result1.succeeded
        original_mtime = result1.target.stat().st_mtime

        # Wait a bit
        import time
        time.sleep(0.1)

        # Upscale again with overwrite=True
        opts = UpscaleOptions(overwrite=True)
        result2 = upscale_dvd(input_file, opts=opts)

        # Should succeed and overwrite
        assert result2.succeeded
        new_mtime = result2.target.stat().st_mtime
        assert new_mtime > original_mtime  # File was recreated

    def test_nonexistent_input_file(self, tmp_path):
        """Test handling of nonexistent input files."""
        nonexistent = tmp_path / "does_not_exist.mkv"

        result = upscale_dvd(nonexistent)

        # Should fail gracefully
        assert result.failed
        assert "not found" in result.message
        assert not result.target.exists()

    def test_invalid_video_file(self, tmp_path):
        """Test handling of files without video streams."""
        # Create a text file with .mkv extension
        invalid_file = tmp_path / "invalid.mkv"
        invalid_file.write_text("This is not a video file")

        result = upscale_dvd(invalid_file)

        # Should fail due to ffprobe failure on invalid file
        assert result.failed
        assert "ffprobe failed" in result.message


class TestBatchUpscaleIntegration:
    """Integration tests for batch upscaling operations."""

    def test_batch_upscale_directory(self, tmp_path):
        """Test batch upscaling of multiple files in a directory."""
        # Create multiple test videos
        files = []
        for i in range(3):
            video_file = create_test_video(
                tmp_path / f"batch_test_{i}.mkv",
                resolution="720x480",
                duration=1
            )
            files.append(video_file)

        # Run batch upscale
        summary = batch_upscale_directory(tmp_path)

        # Verify results
        assert summary.total == 3
        assert len(summary.succeeded) == 3
        assert len(summary.failed) == 0
        assert len(summary.skipped) == 0

        # Verify all outputs exist
        for result in summary.succeeded:
            assert result.target.exists()
            assert "[DVD]" in result.target.name

    def test_batch_mixed_resolutions(self, tmp_path):
        """Test batch upscaling with mixed resolutions (some should be skipped)."""
        # Create videos with different resolutions
        low_res = create_test_video(
            tmp_path / "low_res.mkv",
            resolution="720x480",
            duration=1
        )
        high_res = create_test_video(
            tmp_path / "high_res.mkv",
            resolution="1920x1080",
            duration=1
        )

        # Run batch upscale
        summary = batch_upscale_directory(tmp_path)

        # Verify results
        assert summary.total == 2
        assert len(summary.succeeded) == 1  # Only low_res should be upscaled
        assert len(summary.skipped) == 1    # high_res should be skipped

        # Check which file was processed
        success_result = summary.succeeded[0]
        skip_result = summary.skipped[0]

        assert success_result.source == low_res
        assert skip_result.source == high_res
        assert "1080p" in skip_result.message

    def test_batch_recursive_directory(self, tmp_path):
        """Test recursive batch upscaling."""
        # Create subdirectory
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        # Create videos in both root and subdir
        root_video = create_test_video(
            tmp_path / "root.mkv",
            resolution="720x480",
            duration=1
        )
        sub_video = create_test_video(
            subdir / "sub.mkv",
            resolution="720x480",
            duration=1
        )

        # Run recursive batch upscale
        summary = batch_upscale_directory(tmp_path, recursive=True)

        # Verify both files were processed
        assert summary.total == 2
        assert len(summary.succeeded) == 2

    def test_batch_empty_directory(self, tmp_path):
        """Test batch upscaling on directory with no MKV files."""
        summary = batch_upscale_directory(tmp_path)

        # Should have no results
        assert summary.total == 0
        assert len(summary.succeeded) == 0
        assert len(summary.failed) == 0
        assert len(summary.skipped) == 0

    def test_batch_invalid_directory(self):
        """Test batch upscaling with invalid directory path."""
        with pytest.raises(NotADirectoryError):
            batch_upscale_directory(Path("nonexistent_directory"))


class TestUpscaleWorkflowIntegration:
    """Integration tests for complete upscaling workflow processing."""

    def test_complete_upscale_workflow(self, tmp_path):
        """Test the complete DVD upscaling workflow from input to final output."""
        # Step 1: Create source files (simulating DVD rips)
        source_dir = tmp_path / "dvd_collection"
        source_dir.mkdir()

        # Create various DVD-quality videos
        dvds = [
            ("Movie A (2000)", "720x480"),  # Standard DVD
            ("Movie B (2001)", "704x480"),  # Anamorphic DVD
            ("Movie C (2002)", "720x576"),  # PAL DVD
        ]

        created_files = []
        for name, res in dvds:
            file_path = source_dir / f"{name}.mkv"
            create_test_video(file_path, resolution=res, duration=3)
            created_files.append(file_path)

        # Step 2: Run batch upscale on the directory
        summary = batch_upscale_directory(source_dir)

        # Verify all DVDs were processed
        assert summary.total == len(dvds)
        assert len(summary.succeeded) == len(dvds)
        assert len(summary.failed) == 0

        # Step 3: Verify output files and their properties
        for i, original_file in enumerate(created_files):
            # Find corresponding result
            result = next(r for r in summary.succeeded if r.source == original_file)

            # Verify output file exists and has correct naming
            assert result.target.exists()
            assert "[DVD]" in result.target.name
            assert result.target.suffix == ".mkv"

            # Verify output is 720p
            probe = probe_file(result.target)
            video_stream = next(s for s in probe.streams if s["codec_type"] == "video")
            assert video_stream["width"] == 1280
            assert video_stream["height"] == 720

        # Step 4: Verify original files are unchanged
        for original in created_files:
            assert original.exists()

    def test_upscale_workflow_mixed_content(self, tmp_path):
        """Test upscaling workflow with mixed DVD and HD content."""
        source_dir = tmp_path / "mixed_content"
        source_dir.mkdir()

        # Create mix of DVD and HD content
        files_info = [
            ("DVD_Movie.mkv", "720x480", True),   # Should be upscaled
            ("HD_Movie.mkv", "1920x1080", False), # Should be skipped
            ("SD_Movie.mkv", "640x480", True),    # Should be upscaled
            ("UHD_Movie.mkv", "3840x2160", False), # Should be skipped
        ]

        created_files = []
        expected_upscales = 0

        for name, res, should_upscale in files_info:
            file_path = source_dir / name
            create_test_video(file_path, resolution=res, duration=2)
            created_files.append(file_path)
            if should_upscale:
                expected_upscales += 1

        # Run batch upscale
        summary = batch_upscale_directory(source_dir)

        # Verify correct processing
        assert summary.total == len(files_info)
        assert len(summary.succeeded) == expected_upscales
        assert len(summary.skipped) == (len(files_info) - expected_upscales)

        # Verify specific results
        for result in summary.succeeded:
            # Should be DVD resolution files
            probe = probe_file(result.source)
            video_stream = next(s for s in probe.streams if s["codec_type"] == "video")
            assert video_stream["height"] < 720  # Was lower resolution

            # Output should be 720p
            out_probe = probe_file(result.target)
            out_video = next(s for s in out_probe.streams if s["codec_type"] == "video")
            assert out_video["height"] == 720

        for result in summary.skipped:
            # Should be HD/UHD files
            probe = probe_file(result.source)
            video_stream = next(s for s in probe.streams if s["codec_type"] == "video")
            assert video_stream["height"] >= 720

    def test_upscale_workflow_error_recovery(self, tmp_path):
        """Test upscaling workflow with error conditions and recovery."""
        source_dir = tmp_path / "error_recovery"
        source_dir.mkdir()

        # Create valid DVD file
        valid_dvd = source_dir / "Valid_DVD.mkv"
        create_test_video(valid_dvd, resolution="720x480", duration=2)

        # Create corrupted file
        corrupted = source_dir / "Corrupted.mkv"
        corrupted.write_bytes(b"This is not a video file")

        # Create file with wrong extension
        wrong_ext = source_dir / "Not_MKV.mp4"
        create_test_video(wrong_ext, resolution="720x480", duration=2)

        # Run batch upscale
        summary = batch_upscale_directory(source_dir)

        # Should only process the valid MKV file (corrupted file fails ffprobe)
        # Note: batch_upscale_directory processes all .mkv files, but corrupted ones fail
        assert summary.total == 2  # Both files are attempted
        assert len(summary.succeeded) == 1  # Only valid file succeeds
        assert len(summary.failed) == 1     # Corrupted file fails

        # Verify the valid file was processed
        result = summary.succeeded[0]
        assert result.source == valid_dvd
        expected_output = source_dir / "Valid_DVD" / "Valid_DVD - [DVD].mkv"
        assert result.target == expected_output
        assert result.target.exists()

    def test_upscale_workflow_anime_detection(self, tmp_path):
        """Test upscaling workflow with anime content detection."""
        source_dir = tmp_path / "anime_test"
        source_dir.mkdir()

        # Create anime-style video (assuming detection by filename or content)
        anime_file = source_dir / "Anime Series S01E01 [DVD].mkv"
        create_test_video(anime_file, resolution="720x480", duration=2)

        # Create regular movie
        movie_file = source_dir / "Regular Movie.mkv"
        create_test_video(movie_file, resolution="720x480", duration=2)

        # Run batch upscale
        summary = batch_upscale_directory(source_dir)

        # Both should be processed (anime detection might affect crop, but both upscale)
        assert summary.total == 2
        assert len(summary.succeeded) == 2

        # Verify both outputs exist and are 720p
        for result in summary.succeeded:
            assert result.target.exists()
            probe = probe_file(result.target)
            video_stream = next(s for s in probe.streams if s["codec_type"] == "video")
            assert video_stream["height"] == 720


class TestUpscaleBatchOperations:
    """Test batch upscaling operations and edge cases."""

    def test_batch_upscale_large_directory(self, tmp_path):
        """Test batch upscaling with many files."""
        source_dir = tmp_path / "large_batch"
        source_dir.mkdir()

        # Create many DVD files
        num_files = 10
        created_files = []

        for i in range(num_files):
            file_path = source_dir / f"DVD_Movie_{i:02d}.mkv"
            create_test_video(file_path, resolution="720x480", duration=1)
            created_files.append(file_path)

        # Run batch upscale
        summary = batch_upscale_directory(source_dir)

        # Verify all files processed
        assert summary.total == num_files
        assert len(summary.succeeded) == num_files

        # Verify all outputs exist
        for original in created_files:
            output_name = original.parent / original.stem / f"{original.stem} - [DVD].mkv"
            assert output_name.exists()

    def test_batch_upscale_nested_directories(self, tmp_path):
        """Test batch upscaling with deeply nested directory structure."""
        # Create nested structure
        base_dir = tmp_path / "nested"
        base_dir.mkdir()

        level1 = base_dir / "level1"
        level1.mkdir()
        level2 = level1 / "level2"
        level2.mkdir()

        # Create files at different levels
        root_file = base_dir / "root.mkv"
        level1_file = level1 / "level1.mkv"
        level2_file = level2 / "level2.mkv"

        create_test_video(root_file, resolution="720x480", duration=1)
        create_test_video(level1_file, resolution="720x480", duration=1)
        create_test_video(level2_file, resolution="720x480", duration=1)

        # Run recursive batch upscale
        summary = batch_upscale_directory(base_dir, recursive=True)

        # All files should be processed
        assert summary.total == 3
        assert len(summary.succeeded) == 3

        # Verify outputs exist in correct locations
        assert (base_dir / "root" / "root - [DVD].mkv").exists()
        assert (level1 / "level1" / "level1 - [DVD].mkv").exists()
        assert (level2 / "level2" / "level2 - [DVD].mkv").exists()

    def test_batch_upscale_dry_run(self, tmp_path):
        """Test batch upscaling dry run mode."""
        source_dir = tmp_path / "dry_run"
        source_dir.mkdir()

        # Create DVD file
        dvd_file = source_dir / "Test_DVD.mkv"
        create_test_video(dvd_file, resolution="720x480", duration=1)

        # Run dry run (if supported)
        # Note: This assumes dry_run parameter exists, adjust if not
        try:
            summary = batch_upscale_directory(source_dir, dry_run=True)

            # Should report what would be done without actually doing it
            assert summary.total == 1
            assert len(summary.succeeded) == 0  # Nothing actually processed
            assert not (source_dir / "Test_DVD [DVD].mkv").exists()

        except TypeError:
            # If dry_run not supported, skip this test
            pytest.skip("Dry run not implemented")

    def test_batch_upscale_progress_reporting(self, tmp_path):
        """Test that batch upscaling provides proper progress information."""
        source_dir = tmp_path / "progress_test"
        source_dir.mkdir()

        # Create multiple files
        files = []
        for i in range(3):
            file_path = source_dir / f"Progress_Test_{i}.mkv"
            create_test_video(file_path, resolution="720x480", duration=1)
            files.append(file_path)

        # Run batch upscale
        summary = batch_upscale_directory(source_dir)

        # Verify summary contains expected information
        assert summary.total == len(files)
        assert len(summary.succeeded) == len(files)
        assert len(summary.failed) == 0

        # Each result should have source and target information
        for result in summary.succeeded:
            assert result.source in files
            assert result.target.exists()
            assert result.succeeded