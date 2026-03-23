"""
Shared pytest fixtures for all tests.

Provides mocks for ffmpeg and other external dependencies,
ensuring tests remain isolated and fast.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

import pytest

from utils.ffmpeg_runner import FFmpegResult
from utils.ffprobe_runner import ProbeResult
from core.video.whisper_engine import TranscriptionResult, HallucinationWarning, WhisperEngine
from tests.fixtures.media_generator import TestMediaGenerator


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
        stderr_bytes=b"",
        stdout_bytes=b"",
    )


@pytest.fixture
def mock_ffmpeg_failure():
    """Mock ffmpeg that simulates failed conversion."""
    return FFmpegResult(
        success=False,
        return_code=1,
        command=["ffmpeg", "-i", "test.mp4"],
        stderr_bytes=b"Error: Unknown encoder 'libx265'",
        stdout_bytes=b"",
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
            stderr_bytes=b"",
            stdout_bytes=b"",
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
            stderr_bytes=b"",
            stdout_bytes=b"",
        )
        yield mock_ffmpeg


# ============================================================================
# STANDARD MOCK FIXTURES - Use these for consistent unit test mocking
# ============================================================================


@pytest.fixture
def mock_ffmpeg_runner():
    """Standard FFmpeg runner mock with realistic default returns.
    
    Returns a Mock object configured with sensible defaults
    for successful FFmpeg execution.
    
    Usage:
        def test_convert(mock_ffmpeg_runner):
            converter = VideoConverter(ffmpeg_runner=mock_ffmpeg_runner)
            result = converter.convert(input_path, output_path)
    """
    mock = Mock()
    
    # Default: successful conversion
    mock.run.return_value = FFmpegResult(
        success=True,
        return_code=0,
        command=["ffmpeg", "-i", "input.mkv", "output.mkv"],
        stderr_bytes=b"frame=   100 fps= 50 q=-1.0 Lsize=N/A time=00:02:00 bitrate=N/A speed=N/A\n",
        stdout_bytes=b"",
    )
    
    return mock


@pytest.fixture
def mock_ffmpeg_runner_failure():
    """FFmpeg runner mock configured to simulate failure.
    
    Usage:
        def test_convert_error(mock_ffmpeg_runner_failure):
            converter = VideoConverter(ffmpeg_runner=mock_ffmpeg_runner_failure)
            with pytest.raises(Exception):
                converter.convert(input_path, output_path)
    """
    mock = Mock()
    
    # Default: failed conversion
    mock.run.return_value = FFmpegResult(
        success=False,
        return_code=1,
        command=["ffmpeg", "-i", "input.mkv", "output.mkv"],
        stderr_bytes=b"Unknown encoder 'libx265'",
        stdout_bytes=b"",
    )
    
    return mock


@pytest.fixture
def mock_ffprobe_runner():
    """Standard FFprobe runner mock with realistic video/audio data.
    
    Returns a Mock object configured like FFprobeRunner with sensible defaults
    for 1080p video with stereo audio.
    
    Usage:
        def test_inspect(mock_ffprobe_runner):
            inspector = VideoInspector(ffprobe_runner=mock_ffprobe_runner)
            info = inspector.inspect(video_path)
    """
    mock = Mock()
    
    # Default: 1080p video with stereo audio
    mock.probe_file.return_value = ProbeResult(
        success=True,
        return_code=0,
        data={
            "streams": [
                {
                    "index": 0,
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                    "r_frame_rate": "24/1",
                    "avg_frame_rate": "24/1",
                    "duration": "120.5",
                    "nb_frames": "2892",
                    "bit_rate": "5000000",
                    "tags": {
                        "DURATION": "00:02:00.500000000"
                    }
                },
                {
                    "index": 1,
                    "codec_type": "audio",
                    "codec_name": "aac",
                    "channels": 2,
                    "sample_rate": "48000",
                    "duration": "120.5",
                    "bit_rate": "128000",
                    "tags": {
                        "language": "eng",
                        "DURATION": "00:02:00.640000000"
                    }
                }
            ],
            "format": {
                "filename": "input.mkv",
                "format_name": "matroska,webm",
                "duration": "120.5",
                "size": "104857600",
                "bit_rate": "6991744",
                "tags": {
                    "encoder": "libebml v1.3.10 + libmatroska v1.7.1",
                    "creation_time": "2024-01-15T12:00:00.000000Z"
                }
            }
        },
        stderr="",
    )
    
    return mock


@pytest.fixture
def mock_ffprobe_runner_720p():
    """FFprobe runner mock with 720p video data."""
    mock = Mock()
    
    mock.probe_file.return_value = ProbeResult(
        success=True,
        return_code=0,
        data={
            "streams": [
                {
                    "index": 0,
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1280,
                    "height": 720,
                    "r_frame_rate": "30/1",
                    "avg_frame_rate": "30/1",
                    "duration": "60.0",
                    "bit_rate": "2500000",
                    "tags": {"DURATION": "00:01:00.000000000"}
                }
            ],
            "format": {
                "format_name": "matroska,webm",
                "duration": "60.0",
                "size": "20971520",
            }
        },
        stderr="",
    )
    
    return mock


@pytest.fixture
def mock_ffprobe_runner_failure():
    """FFprobe runner mock configured to simulate failure."""
    mock = Mock()
    
    mock.probe_file.return_value = ProbeResult(
        success=False,
        return_code=1,
        data={},
        stderr="No such file or directory",
    )
    
    return mock


@pytest.fixture
def mock_whisper_engine():
    """Standard Whisper engine mock with realistic transcription data.
    
    Usage:
        def test_transcribe(mock_whisper_engine):
            from core.video.whisper_engine import WhisperEngine
            
            engine = WhisperEngine()
            # The mock will be used via dependency injection or patching
    """
    mock = Mock(spec=WhisperEngine)
    
    # Default: successful transcription
    mock.transcribe.return_value = TranscriptionResult(
        success=True,
        srt_path=Path("output.srt"),
        wav_duration=120.5,
        estimated_duration=120.5,
        hallucination_warnings=[],
        error_message=None,
        processing_time=15.3,
    )
    
    return mock


@pytest.fixture
def mock_whisper_engine_with_warnings():
    """Whisper engine mock with hallucination warnings."""
    mock = Mock(spec=WhisperEngine)
    
    mock.transcribe.return_value = TranscriptionResult(
        success=True,
        srt_path=Path("output.srt"),
        wav_duration=120.5,
        estimated_duration=120.5,
        hallucination_warnings=[
            HallucinationWarning(
                type="known_pattern",
                message="Thank you for watching",
                confidence=0.95,
                details={"count": 1}
            )
        ],
        error_message=None,
        processing_time=15.3,
    )
    
    return mock


@pytest.fixture
def mock_whisper_engine_failure():
    """Whisper engine mock configured to simulate transcription failure."""
    mock = Mock(spec=WhisperEngine)
    
    mock.transcribe.return_value = TranscriptionResult(
        success=False,
        srt_path=None,
        wav_duration=0.0,
        estimated_duration=0.0,
        hallucination_warnings=[],
        error_message="WAV file duration too short: 5.0s",
        processing_time=0.0,
    )
    
    return mock


@pytest.fixture
def patch_ffmpeg_run():
    """Patch utils.ffmpeg_runner.run_ffmpeg globally across tests.
    
    Use this when you need to patch FFmpeg's run_ffmpeg function
    in the utils module itself.
    
    Usage:
        def test_something(patch_ffmpeg_run):
            # patch_ffmpeg_run is the mock object
            result = some_function_that_calls_run_ffmpeg()
            patch_ffmpeg_run.assert_called_once()
    """
    with patch("utils.ffmpeg_runner.run_ffmpeg") as mock_run:
        # Default to success
        mock_run.return_value = FFmpegResult(
            success=True,
            return_code=0,
            command=["ffmpeg"],
            stderr_bytes=b"",
            stdout_bytes=b"",
        )
        yield mock_run


@pytest.fixture
def patch_ffprobe_probe():
    """Patch utils.ffprobe_runner.probe_file globally across tests."""
    with patch("utils.ffprobe_runner.probe_file") as mock_probe:
        # Default to success with 1080p video
        mock_probe.return_value = ProbeResult(
            success=True,
            return_code=0,
            data={
                "streams": [
                    {
                        "index": 0,
                        "codec_type": "video",
                        "width": 1920,
                        "height": 1080,
                        "duration": "120.0"
                    }
                ],
                "format": {"duration": "120.0"}
            },
            stderr="",
        )
        yield mock_probe


@pytest.fixture
def patch_subprocess_run():
    """Patch subprocess.run for tests that call external commands.
    
    Use this when you need to mock subprocess.run directly.
    """
    with patch("subprocess.run") as mock_run:
        # Default to success
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=b"",
            stderr=b"",
            args=["some", "command"]
        )
        yield mock_run

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


# ============================================================================
# Valid Media Fixtures (using FFmpeg)
# ============================================================================


@pytest.fixture(scope="session")
def media_generator():
    """Singleton media generator for test session."""
    return TestMediaGenerator()


@pytest.fixture
def test_video_720p(tmp_path, media_generator):
    """Generate valid 720p MKV video with audio for testing."""
    video_path = tmp_path / "test_720p.mkv"
    return media_generator.create_test_video(
        video_path, duration=5.0, resolution=(1280, 720), with_audio=True
    )


@pytest.fixture
def test_video_1080p(tmp_path, media_generator):
    """Generate valid 1080p MKV video with audio for testing."""
    video_path = tmp_path / "test_1080p.mkv"
    return media_generator.create_test_video(
        video_path, duration=5.0, resolution=(1920, 1080), with_audio=True
    )


@pytest.fixture
def test_video_short(tmp_path, media_generator):
    """Generate short video for quick tests."""
    video_path = tmp_path / "test_short.mkv"
    return media_generator.create_test_video(
        video_path, duration=2.0, resolution=(1280, 720), with_audio=True
    )


@pytest.fixture
def test_video_with_subtitles(tmp_path, media_generator):
    """Generate video with embedded subtitles."""
    video_path = tmp_path / "test_with_subs.mkv"
    return media_generator.create_test_video(
        video_path,
        duration=5.0,
        resolution=(1280, 720),
        with_audio=True,
        with_subtitles=True,
    )


@pytest.fixture
def test_audio_wav(tmp_path, media_generator):
    """Generate valid WAV audio file."""
    audio_path = tmp_path / "test.wav"
    return media_generator.create_test_audio(audio_path, duration=10.0)


@pytest.fixture
def test_audio_mp3(tmp_path, media_generator):
    """Generate valid MP3 audio file."""
    audio_path = tmp_path / "test.mp3"
    return media_generator.create_test_audio(audio_path, duration=10.0)


@pytest.fixture
def large_binary_file(tmp_path, media_generator):
    """Generate 128KB binary file for hash testing."""
    file_path = tmp_path / "large_file.bin"
    return media_generator.create_large_file(file_path, size_bytes=131072)


@pytest.fixture
def test_srt_file(tmp_path, media_generator):
    """Generate valid SRT subtitle file."""
    srt_path = tmp_path / "test.srt"
    return media_generator.create_srt_file(srt_path, num_subtitles=3)


# ============================================================================
# PYTEST HOOKS - Auto-mark integration tests
# ============================================================================

def pytest_collection_modifyitems(config, items):
    """Auto-mark tests in tests/integration/ directory as integration tests.
    
    This allows running unit tests with: pytest -m "not integration"
    And integration tests separately: pytest -m integration
    """
    for item in items:
        # Check if test file is in integration directory
        if "integration" in str(item.fspath):
            # Only mark if not already marked
            if not any(marker.name == "integration" for marker in item.iter_markers()):
                item.add_marker(pytest.mark.integration)


