"""
tests/unit/test_video_hasher.py

Unit tests for video hasher functionality.
"""

from pathlib import Path
import pytest

from utils.video_hasher import VideoHasher


class TestVideoHasher:
    """Test OpenSubtitles hash calculation."""

    def test_calculate_hash_known_file(self, tmp_path):
        """Test hash calculation with a known file."""
        # Create a small test file with known content
        test_file = tmp_path / "test.mp4"
        test_data = b"test video content for hashing" * 4400  # Make it larger than 128KB
        test_file.write_bytes(test_data)

        hasher = VideoHasher()
        hash_result = hasher.calculate_hash(test_file)

        # Should return a 16-character hex string
        assert len(hash_result) == 16
        assert all(c in "0123456789abcdef" for c in hash_result)

    def test_calculate_hash_file_too_small(self, tmp_path):
        """Test that files < 128KB raise ValueError."""
        small_file = tmp_path / "small.mp4"
        small_file.write_bytes(b"small")

        hasher = VideoHasher()

        with pytest.raises(ValueError, match="File too small"):
            hasher.calculate_hash(small_file)

    def test_calculate_hash_nonexistent_file(self, tmp_path):
        """Test that nonexistent files raise FileNotFoundError."""
        nonexistent = tmp_path / "does_not_exist.mp4"

        hasher = VideoHasher()

        with pytest.raises(FileNotFoundError):
            hasher.calculate_hash(nonexistent)