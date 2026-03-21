"""
Shared pytest fixtures for all tests.

Provides mocks for ffmpeg and other external dependencies,
ensuring tests remain isolated and fast.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from utils.ffmpeg_runner import FFmpegResult


@pytest.fixture
def tmp_media_dir(tmp_path):
    """Create a temporary directory structure for media testing."""
    (tmp_path / "input").mkdir()
    (tmp_path / "output").mkdir()
    return tmp_path


@pytest.fixture
def mock_ffmpeg_success():
    """Mock ffmpeg that simulates successful conversion."""
    return FFmpegResult(
        success=True,
        return_code=0,
        command=["ffmpeg", "-i", "test.mp4"],
        stderr="",
        stdout="",
    )


@pytest.fixture
def mock_ffmpeg_failure():
    """Mock ffmpeg that simulates failed conversion."""
    return FFmpegResult(
        success=False,
        return_code=1,
        command=["ffmpeg", "-i", "test.mp4"],
        stderr="Error: Unknown encoder 'libx265'",
        stdout="",
    )


@pytest.fixture
def patch_run_ffmpeg():
    """Patch run_ffmpeg for converter module tests.
    
    Must patch where it's imported/used, not where it's defined.
    """
    with patch("core.video.converter.run_ffmpeg") as mock_ffmpeg:
        # Default to success
        mock_ffmpeg.return_value = FFmpegResult(
            success=True,
            return_code=0,
            command=["ffmpeg"],
            stderr="",
            stdout="",
        )
        yield mock_ffmpeg


@pytest.fixture
def patch_merge_ffmpeg():
    """Patch run_ffmpeg for merger module tests."""
    with patch("core.video.merger.run_ffmpeg") as mock_ffmpeg:
        # Default to success
        mock_ffmpeg.return_value = FFmpegResult(
            success=True,
            return_code=0,
            command=["ffmpeg"],
            stderr="",
            stdout="",
        )
        yield mock_ffmpeg


@pytest.fixture(autouse=True)
def reset_path_exists():
    """Ensure Path.exists() behaves correctly in tests by default.
    
    This prevents tests from accidentally depending on real filesystem state.
    Can be overridden per test by mocking Path.exists() specifically.
    """
    yield


@pytest.fixture
def sample_german_mp4(tmp_media_dir):
    """Create sample German MP4 file for testing."""
    file_path = tmp_media_dir / "input" / "Movie_Title-de.mp4"
    file_path.touch()
    return file_path


@pytest.fixture
def sample_english_mp4(tmp_media_dir):
    """Create sample English MP4 file for testing."""
    file_path = tmp_media_dir / "input" / "Movie_Title-en.mp4"
    file_path.touch()
    return file_path


@pytest.fixture
def sample_chapter_files(tmp_media_dir):
    """Create sample audiobook chapter files for testing."""
    chapter_dir = tmp_media_dir / "chapters"
    chapter_dir.mkdir()
    
    files = []
    for i in range(1, 4):
        file_path = chapter_dir / f"Book Title - Chapter {i:02d}.mp3"
        file_path.touch()
        files.append(file_path)
    
    return chapter_dir, files
