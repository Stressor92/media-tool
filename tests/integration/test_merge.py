"""
Integration tests for dual audio merging functionality.

Tests merging German + English MP4 files into single MKV with real ffmpeg.
"""

import pytest

from core.video.merger import merge_dual_audio, merge_directory


class TestDualAudioMerge:
    """Test dual audio merging with real ffmpeg."""

    def test_merge_dual_audio_basic(self, tmp_path, ffmpeg_available):
        """Test basic dual audio merge."""
        from tests.integration.conftest import create_test_video

        # Create German and English versions
        german_mp4 = tmp_path / "movie-de.mp4"
        english_mp4 = tmp_path / "movie-en.mp4"
        create_test_video(german_mp4, duration=2, language="deu")
        create_test_video(english_mp4, duration=2, language="eng")

        # Merge into MKV
        output_mkv = tmp_path / "movie.mkv"
        result = merge_dual_audio(german_mp4, english_mp4, output_mkv)

        # Verify merge succeeded
        assert result.succeeded
        assert output_mkv.exists()

        # Verify output has 2 audio streams
        from tests.integration.conftest import assert_container_format, assert_video_streams, assert_audio_streams, assert_audio_languages
        assert_container_format(output_mkv, "matroska")
        assert_video_streams(output_mkv, 1)
        assert_audio_streams(output_mkv, 2)
        assert_audio_languages(output_mkv, ["deu", "eng"])

    def test_merge_preserves_video_from_german(self, tmp_path, ffmpeg_available):
        """Test that video stream comes from German file."""
        from tests.integration.conftest import create_test_video, assert_resolution

        # Create files with different resolutions to verify source
        german_mp4 = tmp_path / "german.mp4"
        english_mp4 = tmp_path / "english.mp4"
        create_test_video(german_mp4, resolution="640x480", language="deu")
        create_test_video(english_mp4, resolution="320x240", language="eng")

        output_mkv = tmp_path / "output.mkv"
        result = merge_dual_audio(german_mp4, english_mp4, output_mkv)

        assert result.succeeded
        # Output should have German file's resolution (640x480)
        assert_resolution(output_mkv, 640, 480)

    def test_merge_overwrite_behavior(self, tmp_path, ffmpeg_available):
        """Test overwrite behavior in merging."""
        from tests.integration.conftest import create_test_video

        german_mp4 = tmp_path / "german.mp4"
        english_mp4 = tmp_path / "english.mp4"
        create_test_video(german_mp4, language="deu")
        create_test_video(english_mp4, language="eng")

        output_mkv = tmp_path / "output.mkv"
        # Create existing file
        output_mkv.write_text("existing")
        existing_bytes = output_mkv.read_bytes()

        # Without overwrite, should skip
        result = merge_dual_audio(german_mp4, english_mp4, output_mkv, overwrite=False)
        assert result.skipped
        assert output_mkv.read_text() == "existing"

        # With overwrite, should merge
        result = merge_dual_audio(german_mp4, english_mp4, output_mkv, overwrite=True)
        assert result.succeeded
        assert output_mkv.read_bytes() != existing_bytes

    def test_merge_missing_files(self, tmp_path, ffmpeg_available):
        """Test merge with missing input files."""
        from tests.integration.conftest import create_test_video

        german_mp4 = tmp_path / "german.mp4"
        english_mp4 = tmp_path / "english.mp4"
        create_test_video(german_mp4, language="deu")
        # Don't create english_mp4

        output_mkv = tmp_path / "output.mkv"
        result = merge_dual_audio(german_mp4, english_mp4, output_mkv)

        assert result.failed
        assert not output_mkv.exists()
        assert "not found" in result.message

    def test_merge_with_language_suffixes(self, tmp_path, ffmpeg_available):
        """Test merge with files that have language suffixes in names."""
        from tests.integration.conftest import create_test_video

        # Create files with language suffixes (like real workflow)
        german_mp4 = tmp_path / "Movie (2020)-de.mp4"
        english_mp4 = tmp_path / "Movie (2020)-en.mp4"
        create_test_video(german_mp4, language="deu")
        create_test_video(english_mp4, language="eng")

        output_mkv = tmp_path / "Movie (2020).mkv"
        result = merge_dual_audio(german_mp4, english_mp4, output_mkv)

        assert result.succeeded
        from tests.integration.conftest import assert_audio_languages
        assert_audio_languages(output_mkv, ["deu", "eng"])


class TestDirectoryMerge:
    """Test directory-level merge operations."""

    def test_merge_directory_success(self, tmp_path, ffmpeg_available):
        """Test successful directory merge."""
        from tests.integration.conftest import create_test_video

        input_dir = tmp_path / "input"
        input_dir.mkdir()

        # Create German and English files
        german_mp4 = input_dir / "Movie-de.mp4"
        english_mp4 = input_dir / "Movie-en.mp4"
        create_test_video(german_mp4, language="deu")
        create_test_video(english_mp4, language="eng")

        result = merge_directory(input_dir)

        assert result.succeeded
        output_mkv = input_dir / "Movie.mkv"
        assert output_mkv.exists()

        from tests.integration.conftest import assert_audio_streams, assert_audio_languages
        assert_audio_streams(output_mkv, 2)
        assert_audio_languages(output_mkv, ["deu", "eng"])

    def test_merge_directory_no_german_file(self, tmp_path, ffmpeg_available):
        """Test directory merge when German file is missing."""
        from tests.integration.conftest import create_test_video

        input_dir = tmp_path / "input"
        input_dir.mkdir()

        # Only create English file
        english_mp4 = input_dir / "Movie-en.mp4"
        create_test_video(english_mp4, language="eng")

        result = merge_directory(input_dir)

        assert result.failed
        assert "Could not detect both language versions" in result.message

    def test_merge_directory_case_insensitive_detection(self, tmp_path, ffmpeg_available):
        """Test directory merge with different case language suffixes."""
        from tests.integration.conftest import create_test_video

        input_dir = tmp_path / "input"
        input_dir.mkdir()

        # Create files with uppercase suffixes
        german_mp4 = input_dir / "Movie-DE.mp4"
        english_mp4 = input_dir / "Movie-EN.mp4"
        create_test_video(german_mp4, language="deu")
        create_test_video(english_mp4, language="eng")

        result = merge_directory(input_dir)

        assert result.succeeded
        from tests.integration.conftest import assert_audio_languages
        output_mkv = input_dir / "Movie.mkv"
        assert_audio_languages(output_mkv, ["deu", "eng"])

    def test_merge_directory_multiple_separators(self, tmp_path, ffmpeg_available):
        """Test directory merge with different language separators."""
        from tests.integration.conftest import create_test_video

        input_dir = tmp_path / "input"
        input_dir.mkdir()

        # Test different separator patterns
        test_cases = [
            ("Movie_de.mp4", "Movie_en.mp4"),
            ("Movie(de).mp4", "Movie(en).mp4"),
            ("Movie[de].mp4", "Movie[en].mp4"),
        ]

        for german_name, english_name in test_cases:
            # Clean up previous files
            for f in input_dir.glob("*.mp4"):
                f.unlink()
            for f in input_dir.glob("*.mkv"):
                f.unlink()

            german_mp4 = input_dir / german_name
            english_mp4 = input_dir / english_name
            create_test_video(german_mp4, language="deu")
            create_test_video(english_mp4, language="eng")

            result = merge_directory(input_dir)
            assert result.succeeded, f"Failed for {german_name}, {english_name}"

            from tests.integration.conftest import assert_audio_languages
            output_mkv = input_dir / "Movie.mkv"
            assert_audio_languages(output_mkv, ["deu", "eng"])


class TestAutoMerge:
    """Test automatic merge detection and processing."""

    def test_auto_merge_basic(self, tmp_path, ffmpeg_available):
        """Test automatic merge detection for files with -de/-en suffixes."""
        from tests.integration.conftest import create_test_video

        input_dir = tmp_path / "auto_merge"
        input_dir.mkdir()

        # Create files with standard naming pattern
        german_mp4 = input_dir / "Test Movie (2023)-de.mp4"
        english_mp4 = input_dir / "Test Movie (2023)-en.mp4"
        create_test_video(german_mp4, language="deu")
        create_test_video(english_mp4, language="eng")

        # Run auto merge
        result = merge_directory(input_dir)

        # Should find and merge the pair
        assert result.succeeded

        # Check output file
        output_mkv = input_dir / "Test Movie (2023).mkv"
        assert output_mkv.exists()

    def test_auto_merge_multiple_pairs(self, tmp_path, ffmpeg_available):
        """Test auto merge picks a valid detectable pair when multiple pairs exist."""
        from tests.integration.conftest import create_test_video, assert_audio_languages

        input_dir = tmp_path / "auto_merge_multiple"
        input_dir.mkdir()

        create_test_video(input_dir / "Alpha Movie-de.mp4", language="deu")
        create_test_video(input_dir / "Alpha Movie-en.mp4", language="eng")
        create_test_video(input_dir / "Beta Movie-de.mp4", language="deu")
        create_test_video(input_dir / "Beta Movie-en.mp4", language="eng")

        result = merge_directory(input_dir)

        assert result.succeeded
        assert result.target.exists()
        assert result.target.name in {"Alpha Movie.mkv", "Beta Movie.mkv"}
        assert_audio_languages(result.target, ["deu", "eng"])

    def test_auto_merge_no_pairs(self, tmp_path, ffmpeg_available):
        """Test auto merge fails cleanly when no detectable language pair exists."""
        from tests.integration.conftest import create_test_video

        input_dir = tmp_path / "auto_merge_none"
        input_dir.mkdir()

        create_test_video(input_dir / "Movie-fr.mp4", language="fra")
        create_test_video(input_dir / "Movie-es.mp4", language="spa")

        result = merge_directory(input_dir)

        assert result.failed
        assert "Could not detect both language versions" in result.message

    def test_auto_merge_partial_pairs(self, tmp_path, ffmpeg_available):
        """Test auto merge still succeeds when one complete pair exists among incomplete files."""
        from tests.integration.conftest import create_test_video, assert_audio_languages

        input_dir = tmp_path / "auto_merge_partial"
        input_dir.mkdir()

        create_test_video(input_dir / "Complete Movie-de.mp4", language="deu")
        create_test_video(input_dir / "Complete Movie-en.mp4", language="eng")
        create_test_video(input_dir / "Incomplete Movie-de.mp4", language="deu")

        result = merge_directory(input_dir)

        assert result.succeeded
        assert result.target.exists()
        assert_audio_languages(result.target, ["deu", "eng"])

    def test_auto_merge_different_languages(self, tmp_path, ffmpeg_available):
        """Test auto merge ignores unsupported language variants and fails without de/en pair."""
        from tests.integration.conftest import create_test_video

        input_dir = tmp_path / "auto_merge_langs"
        input_dir.mkdir()

        create_test_video(input_dir / "Movie-de.mp4", language="deu")
        create_test_video(input_dir / "Movie-fr.mp4", language="fra")

        result = merge_directory(input_dir)

        assert result.failed
        assert "Could not detect both language versions" in result.message


class TestMergeWorkflowIntegration:
    """Integration tests for complete merge workflow processing."""

    def test_complete_merge_workflow(self, tmp_path, ffmpeg_available):
        """Test the complete merge workflow from MP4 files to final MKV."""
        from tests.integration.conftest import create_test_video

        # Step 1: Create source files (simulating download directory)
        source_dir = tmp_path / "downloads"
        source_dir.mkdir()

        # Create multiple movie pairs
        movies = [
            ("Action Movie (2023)", "de", "eng"),
            ("Comedy Film (2022)", "de", "eng"),
            ("Drama Series S01E01", "de", "eng"),
        ]

        for movie_name, lang1, lang2 in movies:
            de_file = source_dir / f"{movie_name}-{lang1}.mp4"
            en_file = source_dir / f"{movie_name}-{lang2}.mp4"
            create_test_video(de_file, language=lang1, duration=2)
            create_test_video(en_file, language=lang2, duration=2)

        # Step 2: Run merge on each pair individually
        for movie_name, _, _ in movies:
            de_file = source_dir / f"{movie_name}-de.mp4"
            en_file = source_dir / f"{movie_name}-eng.mp4"
            output_mkv = source_dir / f"{movie_name}.mkv"

            result = merge_dual_audio(de_file, en_file, output_mkv)
            assert result.succeeded

        # Step 3: Verify output files
        for movie_name, _, _ in movies:
            output_mkv = source_dir / f"{movie_name}.mkv"
            assert output_mkv.exists()

            # Verify MKV has correct streams
            from tests.integration.conftest import assert_container_format, assert_video_streams, assert_audio_streams
            assert_container_format(output_mkv, "matroska")
            assert_video_streams(output_mkv, 1)
            assert_audio_streams(output_mkv, 2)

        # Step 4: Verify original MP4 files are still there (merge doesn't delete them)
        total_mp4_files = len(list(source_dir.glob("*.mp4")))
        assert total_mp4_files == len(movies) * 2  # 2 files per movie

    def test_merge_workflow_error_handling(self, tmp_path, ffmpeg_available):
        """Test merge workflow with various error conditions."""
        from tests.integration.conftest import create_test_video

        source_dir = tmp_path / "error_test"
        source_dir.mkdir()

        # Create valid pair
        valid_de = source_dir / "Valid-de.mp4"
        valid_en = source_dir / "Valid-en.mp4"
        create_test_video(valid_de, language="deu")
        create_test_video(valid_en, language="eng")

        # Create incomplete pair
        incomplete_de = source_dir / "Incomplete-de.mp4"
        create_test_video(incomplete_de, language="deu")

        # Create corrupted file
        corrupted = source_dir / "Corrupted-de.mp4"
        corrupted.write_bytes(b"This is not a video file")

        # Test valid merge
        valid_result = merge_dual_audio(valid_de, valid_en, source_dir / "Valid.mkv")
        assert valid_result.succeeded

        # Test invalid merge (missing file)
        invalid_result = merge_dual_audio(incomplete_de, source_dir / "missing.mp4", source_dir / "Invalid.mkv")
        assert invalid_result.failed