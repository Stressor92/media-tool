"""
Integration tests for video conversion functionality.

Tests MP4 → MKV conversion with real ffmpeg execution.
"""


from core.video.converter import convert_mp4_to_mkv


class TestVideoConversion:
    """Test MP4 to MKV conversion with real ffmpeg."""

    def test_convert_mp4_to_mkv_basic(self, tmp_path, ffmpeg_available):
        """Test basic MP4 to MKV conversion."""
        # Create test MP4 file
        from tests.integration.conftest import create_test_video

        input_mp4 = tmp_path / "input.mp4"
        create_test_video(input_mp4, duration=2, resolution="320x240")

        # Convert to MKV
        output_mkv = tmp_path / "output.mkv"
        result = convert_mp4_to_mkv(
            source=input_mp4,
            target=output_mkv,
            audio_language="deu"
        )

        # Verify conversion succeeded
        assert result.succeeded
        assert output_mkv.exists()

        # Verify output is valid MKV
        from tests.integration.conftest import assert_container_format, assert_video_streams, assert_audio_streams
        assert_container_format(output_mkv, "matroska")
        assert_video_streams(output_mkv, 1)
        assert_audio_streams(output_mkv, 1)

    def test_convert_preserves_streams(self, tmp_path, ffmpeg_available):
        """Test that conversion preserves all streams."""
        from tests.integration.conftest import create_test_video

        input_mp4 = tmp_path / "input.mp4"
        create_test_video(input_mp4, duration=2)

        output_mkv = tmp_path / "output.mkv"
        result = convert_mp4_to_mkv(input_mp4, output_mkv)

        assert result.succeeded

        # Check that input and output have same stream counts
        from tests.integration.conftest import get_stream_info
        input_info = get_stream_info(input_mp4)
        output_info = get_stream_info(output_mkv)

        input_video = len([s for s in input_info["streams"] if s["codec_type"] == "video"])
        input_audio = len([s for s in input_info["streams"] if s["codec_type"] == "audio"])
        output_video = len([s for s in output_info["streams"] if s["codec_type"] == "video"])
        output_audio = len([s for s in output_info["streams"] if s["codec_type"] == "audio"])

        assert input_video == output_video
        assert input_audio == output_audio

    def test_convert_with_custom_audio_language(self, tmp_path, ffmpeg_available):
        """Test conversion with custom audio language metadata."""
        from tests.integration.conftest import create_test_video, assert_audio_languages

        input_mp4 = tmp_path / "input.mp4"
        create_test_video(input_mp4, language="eng")

        output_mkv = tmp_path / "output.mkv"
        result = convert_mp4_to_mkv(
            source=input_mp4,
            target=output_mkv,
            audio_language="deu",
            audio_title="Deutsch"
        )

        assert result.succeeded
        assert_audio_languages(output_mkv, ["deu"])

    def test_convert_overwrite_behavior(self, tmp_path, ffmpeg_available):
        """Test overwrite behavior when target exists."""
        from tests.integration.conftest import create_test_video

        input_mp4 = tmp_path / "input.mp4"
        create_test_video(input_mp4)

        output_mkv = tmp_path / "output.mkv"
        # Create existing file
        output_mkv.write_text("existing content")

        # Without overwrite, should skip
        result = convert_mp4_to_mkv(input_mp4, output_mkv, overwrite=False)
        assert result.skipped
        assert output_mkv.read_bytes() == b"existing content"

        # With overwrite, should convert
        result = convert_mp4_to_mkv(input_mp4, output_mkv, overwrite=True)
        assert result.succeeded
        assert output_mkv.read_bytes() != b"existing content"

    def test_convert_invalid_input(self, tmp_path, ffmpeg_available):
        """Test conversion with invalid input file."""
        output_mkv = tmp_path / "output.mkv"
        nonexistent_input = tmp_path / "nonexistent.mp4"

        result = convert_mp4_to_mkv(nonexistent_input, output_mkv)

        assert result.failed
        assert not output_mkv.exists()
        assert "not found" in result.message.lower()


class TestBatchConversion:
    """Test batch conversion functionality."""

    def test_batch_convert_directory(self, tmp_path, ffmpeg_available):
        """Test converting multiple MP4 files in a directory."""
        from tests.integration.conftest import create_test_video
        from core.video.converter import batch_convert_directory

        # Create test directory with multiple MP4 files
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        files = []
        for i in range(3):
            mp4_file = input_dir / f"video{i}.mp4"
            create_test_video(mp4_file, duration=1)
            files.append(mp4_file)

        # Convert directory
        summary = batch_convert_directory(input_dir)

        # Verify results
        assert summary.total == 3
        assert summary.succeeded == summary.results
        assert len(summary.failed) == 0

        # Check output files exist
        for original in files:
            output_mkv = input_dir / original.stem / f"{original.stem}.mkv"
            assert output_mkv.exists()
            from tests.integration.conftest import assert_container_format
            assert_container_format(output_mkv, "matroska")

    def test_batch_convert_recursive_directory(self, tmp_path, ffmpeg_available):
        """Test recursive batch conversion in nested directories."""
        from tests.integration.conftest import create_test_video
        from core.video.converter import batch_convert_directory

        # Create nested directory structure
        root_dir = tmp_path / "media"
        root_dir.mkdir()

        sub_dir = root_dir / "subdir"
        sub_dir.mkdir()

        # Create MP4 files in different levels
        root_mp4 = root_dir / "root_video.mp4"
        sub_mp4 = sub_dir / "sub_video.mp4"

        create_test_video(root_mp4, duration=1)
        create_test_video(sub_mp4, duration=1)

        # Convert recursively
        summary = batch_convert_directory(root_dir, recursive=True)

        # Verify both files were converted
        assert summary.total == 2
        assert len(summary.succeeded) == 2
        assert len(summary.failed) == 0

    def test_batch_convert_mixed_files(self, tmp_path, ffmpeg_available):
        """Test batch conversion with mixed file types (only MP4 should be converted)."""
        from tests.integration.conftest import create_test_video
        from core.video.converter import batch_convert_directory

        # Create directory with MP4 and non-MP4 files
        input_dir = tmp_path / "mixed"
        input_dir.mkdir()

        # MP4 files (should be converted)
        mp4_1 = input_dir / "video1.mp4"
        mp4_2 = input_dir / "video2.mp4"
        create_test_video(mp4_1, duration=1)
        create_test_video(mp4_2, duration=1)

        # Non-MP4 files (should be ignored)
        mkv_file = input_dir / "video.mkv"
        mkv_file.write_text("Not an MP4 file")

        avi_file = input_dir / "video.avi"
        avi_file.write_text("Not an MP4 file")

        # Convert directory
        summary = batch_convert_directory(input_dir)

        # Only MP4 files should be processed
        assert summary.total == 2
        assert len(summary.succeeded) == 2

    def test_batch_convert_empty_directory(self, tmp_path, ffmpeg_available):
        """Test batch conversion on directory with no MP4 files."""
        from core.video.converter import batch_convert_directory

        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        summary = batch_convert_directory(empty_dir)

        # Should have no results
        assert summary.total == 0
        assert len(summary.succeeded) == 0
        assert len(summary.failed) == 0

    def test_batch_convert_with_custom_options(self, tmp_path, ffmpeg_available):
        """Test batch conversion with custom language and title options."""
        from tests.integration.conftest import create_test_video, assert_audio_languages
        from core.video.converter import batch_convert_directory

        input_dir = tmp_path / "custom"
        input_dir.mkdir()

        # Create MP4 files
        mp4_1 = input_dir / "video1.mp4"
        mp4_2 = input_dir / "video2.mp4"
        create_test_video(mp4_1, duration=1, language="eng")
        create_test_video(mp4_2, duration=1, language="eng")

        # Convert with custom options
        summary = batch_convert_directory(
            input_dir,
            audio_language="deu",
            audio_title="Deutsch"
        )

        assert summary.total == 2
        assert len(summary.succeeded) == 2

        # Check that output files have correct language metadata
        for result in summary.succeeded:
            assert_audio_languages(result.target, ["deu"])

    def test_batch_convert_overwrite_handling(self, tmp_path, ffmpeg_available):
        """Test batch conversion overwrite behavior."""
        from tests.integration.conftest import create_test_video
        from core.video.converter import batch_convert_directory

        input_dir = tmp_path / "overwrite_test"
        input_dir.mkdir()

        # Create MP4 file
        mp4_file = input_dir / "video.mp4"
        create_test_video(mp4_file, duration=1)

        # First batch conversion
        summary1 = batch_convert_directory(input_dir, overwrite=False)
        assert summary1.total == 1
        assert len(summary1.succeeded) == 1

        # Second batch conversion (should skip existing)
        summary2 = batch_convert_directory(input_dir, overwrite=False)
        assert summary2.total == 1
        assert len(summary2.succeeded) == 0  # All skipped

        # Third batch conversion with overwrite
        summary3 = batch_convert_directory(input_dir, overwrite=True)
        assert summary3.total == 1
        assert len(summary3.succeeded) == 1  # Should succeed with overwrite

    def test_batch_convert_recursive(self, tmp_path, ffmpeg_available):
        """Test recursive batch conversion."""
        from tests.integration.conftest import create_test_video
        from core.video.converter import batch_convert_directory

        # Create nested directory structure
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        subdir = input_dir / "subdir"
        subdir.mkdir()

        # Create files in both directories
        file1 = input_dir / "video1.mp4"
        file2 = subdir / "video2.mp4"
        create_test_video(file1, duration=1)
        create_test_video(file2, duration=1)

        # Convert with recursive=True
        summary = batch_convert_directory(input_dir, recursive=True)

        assert summary.total == 2
        assert len(summary.succeeded) == 2

    def test_batch_convert_empty_directory_results_collection(self, tmp_path, ffmpeg_available):
        """Test batch conversion on empty directory with results collection assertions."""
        from core.video.converter import batch_convert_directory

        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        summary = batch_convert_directory(empty_dir)

        assert summary.total == 0
        assert len(summary.results) == 0