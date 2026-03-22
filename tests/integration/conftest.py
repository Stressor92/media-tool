"""
Shared fixtures and helpers for integration tests.

Integration tests use real ffmpeg execution and generate test media.
"""

import json
import subprocess
from pathlib import Path
from typing import Dict, Any

import pytest


def run_ffmpeg(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run ffmpeg command and return completed process."""
    cmd = ["ffmpeg", "-y"] + args  # -y to overwrite without prompting
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def run_ffprobe(file_path: Path):
    """Run ffprobe on a file and return a ProbeResult object."""
    from utils.ffprobe_runner import probe_file
    return probe_file(file_path)


def create_test_video(
    output_path: Path,
    duration: int = 2,
    resolution: str = "320x240",
    language: str = "und",
    audio_freq: int = 44100
) -> Path:
    """
    Create a small test video file using ffmpeg test sources.

    Args:
        output_path: Where to save the video
        duration: Duration in seconds
        resolution: Video resolution (e.g., "320x240")
        language: Audio language code
        audio_freq: Audio frequency

    Returns:
        Path to created file
    """
    cmd = [
        "-f", "lavfi",
        "-i", f"testsrc=duration={duration}:size={resolution}:rate=10",
        "-f", "lavfi",
        "-i", f"sine=frequency=1000:duration={duration}:sample_rate={audio_freq}",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-shortest",
        "-metadata:s:a:0", f"language={language}",
        str(output_path)
    ]

    result = run_ffmpeg(cmd)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to create test video: {result.stderr}")

    return output_path


def create_test_audio(
    output_path: Path,
    duration: int = 2,
    language: str = "und",
    freq: int = 1000,
    sample_rate: int = 44100
) -> Path:
    """
    Create a small test audio file.

    Args:
        output_path: Where to save the audio
        duration: Duration in seconds
        language: Language code
        freq: Sine wave frequency
        sample_rate: Audio sample rate

    Returns:
        Path to created file
    """
    # Choose codec based on file extension
    ext = output_path.suffix.lower()
    if ext == ".mp3":
        codec = "mp3"
    elif ext == ".flac":
        codec = "flac"
    else:
        codec = "aac"  # default

    cmd = [
        "-f", "lavfi",
        "-i", f"sine=frequency={freq}:duration={duration}:sample_rate={sample_rate}",
        "-c:a", codec,
        "-metadata:s:a:0", f"language={language}",
        str(output_path)
    ]

    result = run_ffmpeg(cmd)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to create test audio: {result.stderr}")

    return output_path


def get_stream_info(file_path: Path) -> Dict[str, Any]:
    """Get stream information from a media file."""
    return run_ffprobe(file_path)


def assert_video_streams(file_path: Path, expected_count: int = 1):
    """Assert that file has expected number of video streams."""
    info = get_stream_info(file_path)
    video_streams = [s for s in info.streams if s["codec_type"] == "video"]
    assert len(video_streams) == expected_count, f"Expected {expected_count} video streams, got {len(video_streams)}"


def assert_audio_streams(file_path: Path, expected_count: int = 1):
    """Assert that file has expected number of audio streams."""
    info = get_stream_info(file_path)
    audio_streams = [s for s in info.streams if s["codec_type"] == "audio"]
    assert len(audio_streams) == expected_count, f"Expected {expected_count} audio streams, got {len(audio_streams)}"


def assert_audio_languages(file_path: Path, expected_languages: list[str]):
    """Assert that audio streams have expected languages."""
    info = get_stream_info(file_path)
    audio_streams = [s for s in info.streams if s["codec_type"] == "audio"]
    actual_languages = [s.get("tags", {}).get("language", "und") for s in audio_streams]
    assert actual_languages == expected_languages, f"Expected languages {expected_languages}, got {actual_languages}"


def assert_resolution(file_path: Path, expected_width: int, expected_height: int):
    """Assert that video has expected resolution."""
    info = get_stream_info(file_path)
    video_streams = [s for s in info.streams if s["codec_type"] == "video"]
    assert len(video_streams) > 0, "No video streams found"

    stream = video_streams[0]
    width = stream["width"]
    height = stream["height"]
    assert width == expected_width, f"Expected width {expected_width}, got {width}"
    assert height == expected_height, f"Expected height {expected_height}, got {height}"


def assert_container_format(file_path: Path, expected_format: str):
    """Assert that file has expected container format."""
    info = get_stream_info(file_path)
    format_name = info.format["format_name"]
    assert expected_format in format_name, f"Expected format {expected_format}, got {format_name}"


@pytest.fixture
def ffmpeg_available():
    """Skip tests if ffmpeg is not available."""
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True)
        if result.returncode != 0:
            pytest.skip("ffmpeg not available")
    except FileNotFoundError:
        pytest.skip("ffmpeg not available")