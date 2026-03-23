"""
Unit tests for src/core/video/merger.py

Test video merging logic including:
- Language detection in filenames
- Output name derivation
- Merge result objects
- Merge operation with mocked ffmpeg
"""

from __future__ import annotations


import pytest

from core.video.merger import (
    MergeResult,
    MergeStatus,
    derive_output_name,
    detect_language_files,
    merge_dual_audio,
    merge_directory,
)
from utils.ffmpeg_runner import FFmpegResult


# ---------------------------------------------------------------------------
# Tests for detect_language_files()
# ---------------------------------------------------------------------------


class TestDetectLanguageFiles:
    """Test language detection in filenames."""

    def test_detect_german_and_english(self, tmp_media_dir):
        """Should detect standard German and English file suffixes."""
        german_file = tmp_media_dir / "input" / "Movie-de.mp4"
        english_file = tmp_media_dir / "input" / "Movie-en.mp4"
        german_file.touch()
        english_file.touch()
        
        de, en = detect_language_files(tmp_media_dir / "input")
        assert de == german_file
        assert en == english_file

    def test_detect_underscore_separator(self, tmp_media_dir):
        """Should detect language suffix with underscore."""
        german_file = tmp_media_dir / "input" / "Film_de.mp4"
        english_file = tmp_media_dir / "input" / "Film_en.mp4"
        german_file.touch()
        english_file.touch()
        
        de, en = detect_language_files(tmp_media_dir / "input")
        assert de == german_file
        assert en == english_file

    def test_detect_parentheses_separator(self, tmp_media_dir):
        """Should detect language suffix in parentheses."""
        german_file = tmp_media_dir / "input" / "Movie(de).mp4"
        english_file = tmp_media_dir / "input" / "Movie(en).mp4"
        german_file.touch()
        english_file.touch()
        
        de, en = detect_language_files(tmp_media_dir / "input")
        assert de == german_file
        assert en == english_file

    def test_detect_square_brackets_separator(self, tmp_media_dir):
        """Should detect language suffix in square brackets."""
        german_file = tmp_media_dir / "input" / "Film[de].mp4"
        english_file = tmp_media_dir / "input" / "Film[en].mp4"
        german_file.touch()
        english_file.touch()
        
        de, en = detect_language_files(tmp_media_dir / "input")
        assert de == german_file
        assert en == english_file

    def test_detect_case_insensitive(self, tmp_media_dir):
        """Should detect language codes case-insensitively."""
        german_file = tmp_media_dir / "input" / "Film-DE.mp4"
        english_file = tmp_media_dir / "input" / "Film-EN.mp4"
        german_file.touch()
        english_file.touch()
        
        de, en = detect_language_files(tmp_media_dir / "input")
        assert de == german_file
        assert en == english_file

    def test_detect_missing_english(self, tmp_media_dir):
        """Should return None for missing English file."""
        german_file = tmp_media_dir / "input" / "Movie-de.mp4"
        german_file.touch()
        
        de, en = detect_language_files(tmp_media_dir / "input")
        assert de == german_file
        assert en is None

    def test_detect_missing_german(self, tmp_media_dir):
        """Should return None for missing German file."""
        english_file = tmp_media_dir / "input" / "Movie-en.mp4"
        english_file.touch()
        
        de, en = detect_language_files(tmp_media_dir / "input")
        assert de is None
        assert en == english_file

    def test_detect_both_missing(self, tmp_media_dir):
        """Should return None for both when no matching files exist."""
        de, en = detect_language_files(tmp_media_dir / "input")
        assert de is None
        assert en is None

    def test_detect_ignores_non_mp4(self, tmp_media_dir):
        """Should ignore non-MP4 files."""
        (tmp_media_dir / "input" / "file-de.mkv").touch()
        (tmp_media_dir / "input" / "file-en.avi").touch()
        
        de, en = detect_language_files(tmp_media_dir / "input")
        assert de is None
        assert en is None

    def test_detect_with_mixed_files(self, tmp_media_dir):
        """Should find MP4s among other file types."""
        german_file = tmp_media_dir / "input" / "Movie-de.mp4"
        english_file = tmp_media_dir / "input" / "Movie-en.mp4"
        (tmp_media_dir / "input" / "other-de.mkv").touch()
        (tmp_media_dir / "input" / "subtitle.srt").touch()
        german_file.touch()
        english_file.touch()
        
        de, en = detect_language_files(tmp_media_dir / "input")
        assert de == german_file
        assert en == english_file


# ---------------------------------------------------------------------------
# Tests for derive_output_name()
# ---------------------------------------------------------------------------


class TestDeriveOutputName:
    """Test output name derivation by removing language suffix."""

    def test_derive_removes_dash_de_suffix(self, tmp_media_dir):
        """Should remove '-de' suffix."""
        file_path = tmp_media_dir / "Movie-de.mp4"
        assert derive_output_name(file_path) == "Movie"

    def test_derive_removes_underscore_de_suffix(self, tmp_media_dir):
        """Should remove '_de' suffix."""
        file_path = tmp_media_dir / "Movie_de.mp4"
        assert derive_output_name(file_path) == "Movie"

    def test_derive_removes_parentheses_de_suffix(self, tmp_media_dir):
        """Should remove '(de)' suffix."""
        file_path = tmp_media_dir / "Movie(de).mp4"
        assert derive_output_name(file_path) == "Movie"

    def test_derive_removes_square_bracket_de_suffix(self, tmp_media_dir):
        """Should NOT remove [de] suffix (not in regex pattern)."""
        file_path = tmp_media_dir / "Movie[de].mp4"
        # Square brackets are not in the regex pattern, so they remain
        assert derive_output_name(file_path) == "Movie[de]"

    def test_derive_case_insensitive(self, tmp_media_dir):
        """Should remove suffix case-insensitively."""
        file_path = tmp_media_dir / "Movie-DE.mp4"
        assert derive_output_name(file_path) == "Movie"

    def test_derive_with_year_in_title(self, tmp_media_dir):
        """Should preserve year in title when removing language."""
        file_path = tmp_media_dir / "Movie (2022)-de.mp4"
        assert "2022" in derive_output_name(file_path)
        assert "-de" not in derive_output_name(file_path).lower()

    def test_derive_with_multiple_parts(self, tmp_media_dir):
        """Should handle titles with multiple words."""
        file_path = tmp_media_dir / "The Matrix Reloaded-de.mp4"
        assert derive_output_name(file_path) == "The Matrix Reloaded"

    def test_derive_no_language_suffix(self, tmp_media_dir):
        """Should return stem unchanged if no language suffix."""
        file_path = tmp_media_dir / "NoLanguage.mp4"
        assert derive_output_name(file_path) == "NoLanguage"

    def test_derive_strips_whitespace(self, tmp_media_dir):
        """Should strip trailing whitespace after removal."""
        file_path = tmp_media_dir / "Movie  -de.mp4"
        result = derive_output_name(file_path)
        assert result == "Movie"


# ---------------------------------------------------------------------------
# Tests for MergeResult model
# ---------------------------------------------------------------------------


class TestMergeResult:
    """Test MergeResult immutable data object."""

    def test_merge_result_success_property(self, tmp_media_dir):
        """Should correctly identify successful merge."""
        german = tmp_media_dir / "a-de.mp4"
        english = tmp_media_dir / "a-en.mp4"
        target = tmp_media_dir / "a.mkv"
        
        result = MergeResult(
            status=MergeStatus.SUCCESS,
            german_source=german,
            english_source=english,
            target=target,
            message="Success",
        )
        
        assert result.succeeded is True
        assert result.failed is False
        assert result.skipped is False

    def test_merge_result_failed_property(self, tmp_media_dir):
        """Should correctly identify failed merge."""
        target = tmp_media_dir / "a.mkv"
        
        result = MergeResult(
            status=MergeStatus.FAILED,
            german_source=None,
            english_source=None,
            target=target,
            message="Error",
        )
        
        assert result.failed is True
        assert result.succeeded is False
        assert result.skipped is False

    def test_merge_result_skipped_property(self, tmp_media_dir):
        """Should correctly identify skipped merge."""
        target = tmp_media_dir / "a.mkv"
        
        result = MergeResult(
            status=MergeStatus.SKIPPED,
            german_source=None,
            english_source=None,
            target=target,
            message="Already exists",
        )
        
        assert result.skipped is True
        assert result.succeeded is False
        assert result.failed is False

    def test_merge_result_immutable(self, tmp_media_dir):
        """MergeResult should be immutable."""
        result = MergeResult(
            status=MergeStatus.SUCCESS,
            german_source=None,
            english_source=None,
            target=tmp_media_dir / "out.mkv",
            message="Test",
        )
        
        with pytest.raises(Exception):  # FrozenInstanceError
            result.message = "Changed"


# ---------------------------------------------------------------------------
# Tests for merge_dual_audio() with mocking
# ---------------------------------------------------------------------------


class TestMergeDualAudio:
    """Test dual-audio merge operation with mocked ffmpeg."""

    def test_merge_success(self, tmp_media_dir, patch_merge_ffmpeg):
        """Should return SUCCESS when ffmpeg succeeds."""
        german = tmp_media_dir / "input" / "Movie-de.mp4"
        english = tmp_media_dir / "input" / "Movie-en.mp4"
        target = tmp_media_dir / "output" / "Movie.mkv"
        german.touch()
        english.touch()
        
        patch_merge_ffmpeg.return_value = FFmpegResult(
            success=True,
            return_code=0,
            command=["ffmpeg"],
            stderr_bytes=b"",
            stdout_bytes=b"",
        )
        
        result = merge_dual_audio(german, english, target)
        
        assert result.succeeded
        assert result.status == MergeStatus.SUCCESS
        assert result.target == target

    def test_merge_failure(self, tmp_media_dir, patch_merge_ffmpeg):
        """Should return FAILED when ffmpeg fails."""
        german = tmp_media_dir / "input" / "Movie-de.mp4"
        english = tmp_media_dir / "input" / "Movie-en.mp4"
        target = tmp_media_dir / "output" / "Movie.mkv"
        german.touch()
        english.touch()
        
        patch_merge_ffmpeg.return_value = FFmpegResult(
            success=False,
            return_code=1,
            command=["ffmpeg"],
            stderr_bytes=b"Error: codec not found",
            stdout_bytes=b"",
        )
        
        result = merge_dual_audio(german, english, target)
        
        assert result.failed
        assert result.status == MergeStatus.FAILED

    def test_merge_skip_existing_target(self, tmp_media_dir, patch_merge_ffmpeg):
        """Should skip merge when target exists and overwrite=False."""
        german = tmp_media_dir / "input" / "Movie-de.mp4"
        english = tmp_media_dir / "input" / "Movie-en.mp4"
        target = tmp_media_dir / "output" / "Movie.mkv"
        german.touch()
        english.touch()
        target.touch()  # Target already exists
        
        result = merge_dual_audio(german, english, target, overwrite=False)
        
        assert result.skipped
        assert result.status == MergeStatus.SKIPPED
        # Should not have called ffmpeg
        patch_merge_ffmpeg.assert_not_called()

    def test_merge_overwrite_existing_target(self, tmp_media_dir, patch_merge_ffmpeg):
        """Should overwrite target when overwrite=True."""
        german = tmp_media_dir / "input" / "Movie-de.mp4"
        english = tmp_media_dir / "input" / "Movie-en.mp4"
        target = tmp_media_dir / "output" / "Movie.mkv"
        german.touch()
        english.touch()
        target.touch()  # Target already exists
        
        patch_merge_ffmpeg.return_value = FFmpegResult(
            success=True,
            return_code=0,
            command=["ffmpeg"],
            stderr_bytes=b"",
            stdout_bytes=b"",
        )
        
        result = merge_dual_audio(german, english, target, overwrite=True)
        
        assert result.succeeded
        # Should have called ffmpeg with -y flag
        patch_merge_ffmpeg.assert_called_once()
        call_args = patch_merge_ffmpeg.call_args[0][0]
        assert "-y" in call_args

    def test_merge_includes_language_metadata(self, tmp_media_dir, patch_merge_ffmpeg):
        """Should include language metadata in ffmpeg command."""
        german = tmp_media_dir / "input" / "Movie-de.mp4"
        english = tmp_media_dir / "input" / "Movie-en.mp4"
        target = tmp_media_dir / "output" / "Movie.mkv"
        german.touch()
        english.touch()
        
        patch_merge_ffmpeg.return_value = FFmpegResult(
            success=True,
            return_code=0,
            command=["ffmpeg"],
            stderr_bytes=b"",
            stdout_bytes=b"",
        )
        
        merge_dual_audio(german, english, target)
        
        # Check ffmpeg was called with language metadata
        patch_merge_ffmpeg.assert_called_once()
        call_args = patch_merge_ffmpeg.call_args[0][0]
        
        # Should map audio tracks
        assert "-map" in call_args
        # Should set language metadata
        assert "language=deu" in " ".join(call_args)
        assert "language=eng" in " ".join(call_args)

    def test_merge_message_content(self, tmp_media_dir, patch_merge_ffmpeg):
        """Should include descriptive message in result."""
        german = tmp_media_dir / "input" / "Movie-de.mp4"
        english = tmp_media_dir / "input" / "Movie-en.mp4"
        target = tmp_media_dir / "output" / "Movie.mkv"
        german.touch()
        english.touch()
        
        patch_merge_ffmpeg.return_value = FFmpegResult(
            success=True,
            return_code=0,
            command=["ffmpeg"],
            stderr_bytes=b"",
            stdout_bytes=b"",
        )
        
        result = merge_dual_audio(german, english, target)
        
        assert result.message  # Should have a message
        assert len(result.message) > 0


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestMergeIntegration:
    """Integration tests for merge workflow."""

    def test_detect_and_merge_workflow(self, tmp_media_dir, patch_merge_ffmpeg):
        """Test complete workflow: detect files, derive name, merge."""
        # Setup
        german = tmp_media_dir / "input" / "Movie(2020)-de.mp4"
        english = tmp_media_dir / "input" / "Movie(2020)-en.mp4"
        german.touch()
        english.touch()
        
        patch_merge_ffmpeg.return_value = FFmpegResult(
            success=True,
            return_code=0,
            command=["ffmpeg"],
            stderr_bytes=b"",
            stdout_bytes=b"",
        )
        
        # Detect
        detected_de, detected_en = detect_language_files(tmp_media_dir / "input")
        assert detected_de is not None
        assert detected_en is not None
        
        # Derive output name
        output_name = derive_output_name(detected_de)
        assert "2020" in output_name
        assert "-de" not in output_name
        
        # Merge
        target = tmp_media_dir / "output" / f"{output_name}.mkv"
        result = merge_dual_audio(detected_de, detected_en, target)
        
        assert result.succeeded
        assert result.german_source == german
        assert result.english_source == english


# ---------------------------------------------------------------------------
# Tests for merge_directory()
# ---------------------------------------------------------------------------


class TestMergeDirectory:
    """Test directory-level merge operations."""

    def test_merge_directory_success(self, tmp_media_dir, patch_merge_ffmpeg):
        """Should successfully merge detected language files."""
        german = tmp_media_dir / "input" / "Movie-de.mp4"
        english = tmp_media_dir / "input" / "Movie-en.mp4"
        german.touch()
        english.touch()
        
        patch_merge_ffmpeg.return_value = FFmpegResult(
            success=True,
            return_code=0,
            command=["ffmpeg"],
            stderr_bytes=b"",
            stdout_bytes=b"",
        )
        
        result = merge_directory(tmp_media_dir / "input")
        
        assert result.succeeded
        assert result.german_source == german
        assert result.english_source == english
        assert result.target.name == "Movie.mkv"
        assert "Merged successfully" in result.message

    def test_merge_directory_missing_german(self, tmp_media_dir):
        """Should fail when German file is missing."""
        english = tmp_media_dir / "input" / "Movie-en.mp4"
        english.touch()
        
        result = merge_directory(tmp_media_dir / "input")
        
        assert result.failed
        assert result.german_source is None
        assert result.english_source == english
        assert "Could not detect both language versions" in result.message

    def test_merge_directory_missing_english(self, tmp_media_dir):
        """Should fail when English file is missing."""
        german = tmp_media_dir / "input" / "Movie-de.mp4"
        german.touch()
        
        result = merge_directory(tmp_media_dir / "input")
        
        assert result.failed
        assert result.german_source == german
        assert result.english_source is None
        assert "Could not detect both language versions" in result.message

    def test_merge_directory_no_mp4_files(self, tmp_media_dir):
        """Should fail when no MP4 files exist."""
        result = merge_directory(tmp_media_dir / "input")
        
        assert result.failed
        assert result.german_source is None
        assert result.english_source is None
        assert "Found MP4 files: (none)" in result.message

    def test_merge_directory_non_mp4_files(self, tmp_media_dir):
        """Should fail when only non-MP4 files exist."""
        avi_file = tmp_media_dir / "input" / "Movie.avi"
        avi_file.touch()
        
        result = merge_directory(tmp_media_dir / "input")
        
        assert result.failed
        assert "Found MP4 files: (none)" in result.message

    def test_merge_directory_with_year_in_name(self, tmp_media_dir, patch_merge_ffmpeg):
        """Should derive correct output name from German file with year."""
        german = tmp_media_dir / "input" / "Film(2022)-de.mp4"
        english = tmp_media_dir / "input" / "Film(2022)-en.mp4"
        german.touch()
        english.touch()
        
        patch_merge_ffmpeg.return_value = FFmpegResult(
            success=True,
            return_code=0,
            command=["ffmpeg"],
            stderr_bytes=b"",
            stdout_bytes=b"",
        )
        
        result = merge_directory(tmp_media_dir / "input")
        
        assert result.succeeded
        assert result.target.name == "Film(2022).mkv"

    def test_merge_directory_overwrite_parameter(self, tmp_media_dir, patch_merge_ffmpeg):
        """Should pass overwrite parameter to merge_dual_audio."""
        german = tmp_media_dir / "input" / "Movie-de.mp4"
        english = tmp_media_dir / "input" / "Movie-en.mp4"
        german.touch()
        english.touch()
        
        patch_merge_ffmpeg.return_value = FFmpegResult(
            success=True,
            return_code=0,
            command=["ffmpeg"],
            stderr_bytes=b"",
            stdout_bytes=b"",
        )
        
        result = merge_directory(tmp_media_dir / "input", overwrite=True)
        
        assert result.succeeded
        # Check that ffmpeg was called with overwrite flag
        patch_merge_ffmpeg.assert_called_once()
        call_args = patch_merge_ffmpeg.call_args[0][0]
        assert "-y" in call_args

    def test_merge_directory_not_a_directory(self, tmp_path):
        """Should raise NotADirectoryError for invalid path."""
        file_path = tmp_path / "not_a_dir.txt"
        file_path.touch()
        
        with pytest.raises(NotADirectoryError, match="Not a directory"):
            merge_directory(file_path)

    def test_merge_directory_case_insensitive_detection(self, tmp_media_dir, patch_merge_ffmpeg):
        """Should work with mixed case language suffixes."""
        german = tmp_media_dir / "input" / "Movie-DE.mp4"
        english = tmp_media_dir / "input" / "Movie-EN.mp4"
        german.touch()
        english.touch()
        
        patch_merge_ffmpeg.return_value = FFmpegResult(
            success=True,
            return_code=0,
            command=["ffmpeg"],
            stderr_bytes=b"",
            stdout_bytes=b"",
        )
        
        result = merge_directory(tmp_media_dir / "input")
        
        assert result.succeeded
        assert result.german_source == german
        assert result.english_source == english
