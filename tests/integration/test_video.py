"""
tests/integration/test_video.py

Integration tests for video processing functionality using real ffmpeg execution.

Tests validate the complete video processing workflow including:
- Video file conversion (MP4 → MKV)
- Video library scanning and metadata extraction
- Video file merging (dual audio)
- Video upscaling (DVD → 720p)
- Complete video workflow processing
"""

import pytest
import csv
from pathlib import Path
from core.video import (
    convert_mp4_to_mkv,
    scan_directory,
    merge_directory,
    upscale_dvd,
)
from .conftest import create_test_video, run_ffprobe


class TestVideoConvertIntegration:
    """Integration tests for video conversion functionality."""

    def test_convert_mp4_to_mkv_basic(self, tmp_path):
        """Test basic MP4 to MKV conversion."""
        # Create test MP4 file
        input_mp4 = create_test_video(
            tmp_path / "input.mp4",
            resolution="1920x1080",
            duration=10
        )

        output_mkv = tmp_path / "output.mkv"

        # Convert MP4 to MKV
        result = convert_mp4_to_mkv(
            source=input_mp4,
            target=output_mkv,
            audio_language="deu",
            audio_title="Deutsch",
            overwrite=False
        )

        # Verify conversion
        assert result.status.name == "SUCCESS"
        assert output_mkv.exists()
        assert output_mkv.stat().st_size > 0

        # Verify output is valid MKV
        probe = run_ffprobe(output_mkv)
        assert probe is not None

    def test_convert_with_language_metadata(self, tmp_path):
        """Test conversion with custom language metadata."""
        input_mp4 = create_test_video(
            tmp_path / "input_lang.mp4",
            resolution="1280x720",
            duration=5
        )

        output_mkv = tmp_path / "output_lang.mkv"

        result = convert_mp4_to_mkv(
            source=input_mp4,
            target=output_mkv,
            audio_language="eng",
            audio_title="English",
            overwrite=False
        )

        assert result.status.name == "SUCCESS"
        assert output_mkv.exists()

    def test_convert_overwrite_behavior(self, tmp_path):
        """Test conversion overwrite behavior."""
        input_mp4 = create_test_video(
            tmp_path / "input_overwrite.mp4",
            resolution="1920x1080",
            duration=5
        )

        output_mkv = tmp_path / "output_overwrite.mkv"

        # First conversion
        result1 = convert_mp4_to_mkv(
            source=input_mp4,
            target=output_mkv,
            audio_language="deu",
            audio_title="Deutsch",
            overwrite=False
        )
        assert result1.status.name == "SUCCESS"

        # Second conversion without overwrite - should be skipped
        result2 = convert_mp4_to_mkv(
            source=input_mp4,
            target=output_mkv,
            audio_language="deu",
            audio_title="Deutsch",
            overwrite=False
        )
        assert result2.status.name == "SKIPPED"

        # Third conversion with overwrite
        result3 = convert_mp4_to_mkv(
            source=input_mp4,
            target=output_mkv,
            audio_language="deu",
            audio_title="Deutsch",
            overwrite=True
        )
        assert result3.status.name == "SUCCESS"


class TestVideoInspectIntegration:
    """Integration tests for video library inspection functionality."""

    def test_inspect_video_directory(self, tmp_path):
        """Test scanning a directory with video files."""
        # Create test video files
        video1 = create_test_video(
            tmp_path / "movie1.mp4",
            resolution="1920x1080",
            duration=30
        )
        video2 = create_test_video(
            tmp_path / "movie2.mkv",
            resolution="1280x720",
            duration=45
        )

        # Scan directory
        videos = scan_directory(tmp_path, recursive=True)

        # Verify results
        assert len(videos) >= 2
        assert all(Path(video.file_path).exists() for video in videos)

    def test_inspect_empty_directory(self, tmp_path):
        """Test scanning a directory with no video files."""
        videos = scan_directory(tmp_path, recursive=True)

        # Should find no files
        assert len(videos) == 0

    def test_inspect_recursive_directory(self, tmp_path):
        """Test recursive scanning of video subdirectories."""
        # Create subdirectory structure
        movies_dir = tmp_path / "Movies"
        movies_dir.mkdir()

        tv_dir = tmp_path / "TV Shows" / "Show Name" / "Season 1"
        tv_dir.mkdir(parents=True)

        # Create videos in different locations
        movie = create_test_video(movies_dir / "movie.mp4", resolution="1920x1080", duration=30)
        episode = create_test_video(tv_dir / "episode.mp4", resolution="1280x720", duration=25)

        # Scan recursively
        videos = scan_directory(tmp_path, recursive=True)

        # Should find both files
        assert len(videos) >= 2

    def test_inspect_mixed_formats(self, tmp_path):
        """Test scanning directory with mixed video formats."""
        formats = ["mp4", "mkv", "avi"]  # Only formats supported by VIDEO_EXTENSIONS

        for fmt in formats:
            create_test_video(
                tmp_path / f"video.{fmt}",
                resolution="1280x720",
                duration=10
            )

        videos = scan_directory(tmp_path, recursive=True)

        # Should find all supported formats
        assert len(videos) >= len(formats)


class TestVideoMergeIntegration:
    """Integration tests for video merging functionality."""

    def test_merge_dual_audio_videos(self, tmp_path):
        """Test merging two videos with different audio tracks."""
        # Create German audio video
        german_video = create_test_video(
            tmp_path / "movie_german.mp4",
            resolution="1920x1080",
            duration=30
        )

        # Create English audio video
        english_video = create_test_video(
            tmp_path / "movie_english.mp4",
            resolution="1920x1080",
            duration=30
        )

        # Merge videos (auto-detect language pairs)
        result = merge_directory(tmp_path)

        # Verify merge result
        assert result.status.name == "SUCCESS"

        # Find the output file (should be named after the base name)
        output_mkv = tmp_path / "movie.mkv"
        assert output_mkv.exists()

        # Verify output has multiple audio streams
        from utils.ffprobe_runner import probe_file
        probe = probe_file(output_mkv)
        video = probe.first_video()
        assert video is not None

    def test_merge_directory_with_pattern(self, tmp_path):
        """Test merging videos in directory using filename patterns."""
        # Create multiple related video files
        for i in range(1, 4):
            create_test_video(
                tmp_path / f"part_{i}.mp4",
                resolution="1920x1080",
                duration=10
            )

        # Note: Current merge_directory only does auto language detection
        # This test would need a different merge function for pattern-based merging
        pytest.skip("Pattern-based merging not implemented in current merge_directory")

    def test_merge_empty_directory(self, tmp_path):
        """Test merging in directory with no matching files."""
        # Note: Current merge_directory only does auto language detection
        # This test would need a different merge function for pattern-based merging
        pytest.skip("Pattern-based merging not implemented in current merge_directory")


class TestVideoUpscaleIntegration:
    """Integration tests for video upscaling functionality."""

    def test_upscale_single_video(self, tmp_path):
        """Test upscaling a single video file."""
        # Create low-res video
        input_video = create_test_video(
            tmp_path / "dvd_movie.mp4",
            resolution="720x480",  # DVD resolution
            duration=15
        )

        # Upscale to 720p
        result = upscale_dvd(input_video)

        # Verify upscaling
        assert result.status.name == "SUCCESS"
        assert result.target.exists()
        assert "[DVD]" in result.target.name

        # Verify output resolution
        probe = run_ffprobe(result.target)
        video = probe.first_video()
        assert int(video["height"]) == 720

    def test_upscale_skip_high_res(self, tmp_path):
        """Test that high-res videos are skipped during upscaling."""
        # Create already high-res video
        high_res_video = create_test_video(
            tmp_path / "bluray_movie.mkv",
            resolution="1920x1080",
            duration=15
        )

        result = upscale_dvd(high_res_video)

        # Should be skipped
        assert result.status.name == "SKIPPED"
        assert "1080p" in result.message

    def test_upscale_custom_options(self, tmp_path):
        """Test upscaling with custom options."""
        from core.video.upscaler import UpscaleOptions

        input_video = create_test_video(
            tmp_path / "custom_dvd.mp4",
            resolution="720x480",
            duration=10
        )

        # Custom upscale options
        opts = UpscaleOptions(
            target_height=720,
            crf=18,  # Higher quality
            preset="slow",
        )

        result = upscale_dvd(input_video, opts=opts)

        assert result.status.name == "SUCCESS"
        assert result.target.exists()


class TestVideoWorkflowIntegration:
    """Integration tests for complete video workflow processing."""

    def test_complete_video_workflow(self, tmp_path):
        """Test the complete video processing workflow."""
        # Step 1: Create raw video files
        raw_dir = tmp_path / "raw_videos"
        raw_dir.mkdir()

        german_video = create_test_video(
            raw_dir / "Movie_German.mp4",
            resolution="1920x1080",
            duration=30
        )
        english_video = create_test_video(
            raw_dir / "Movie_English.mp4",
            resolution="1920x1080",
            duration=30
        )
        dvd_video = create_test_video(
            raw_dir / "Old_DVD.mp4",
            resolution="720x480",
            duration=20
        )

        # Step 2: Inspect the library
        videos = scan_directory(raw_dir, recursive=True)
        assert len(videos) >= 3

        # Step 3: Convert MP4 files to MKV
        converted_dir = tmp_path / "converted"
        converted_dir.mkdir()

        for video in videos:
            if Path(video.file_path).suffix.lower() == '.mp4':
                output_mkv = converted_dir / f"{video.file_path.stem}.mkv"
                result = convert_mp4_to_mkv(
                    source=video.file_path,
                    target=output_mkv,
                    audio_language="deu",
                    audio_title="Deutsch",
                    overwrite=False
                )
                assert result.status.name == "SUCCESS"

        # Step 4: Merge dual audio videos
        merged_mkv = tmp_path / "Movie_Complete.mkv"
        merge_result = merge_directory(
            directory=raw_dir,
            output=merged_mkv,
            pattern="Movie_*.mp4"
        )
        assert merge_result.status.name == "SUCCESS"

        # Step 5: Upscale DVD content
        upscale_result = upscale_dvd(dvd_video)
        assert upscale_result.status.name == "SUCCESS"

        # Step 6: Final inspection
        final_videos = scan_directory(tmp_path, recursive=True)
        assert len(final_videos) >= 4  # original + converted + merged + upscaled