"""
tests/unit/test_audio_processor.py

Unit tests for audio processing extensions.

Uses standard mock fixtures from conftest.py for consistent mocking.
"""

from pathlib import Path
from unittest.mock import patch

from utils.audio_processor import AudioExtractionResult, extract_for_speech
from utils.ffmpeg_runner import FFmpegResult


class TestAudioExtractionResult:
    """Test AudioExtractionResult dataclass."""

    def test_result_creation(self):
        """Test creating an AudioExtractionResult."""
        result = AudioExtractionResult(
            success=True,
            input_file=Path("test_input.mkv"),
            output_file=Path("test.wav"),
            ffmpeg_result=None,
            duration_seconds=60.0,
            sample_rate=16000,
            channels=1,
        )

        assert result.success
        assert result.output_file == Path("test.wav")
        assert result.wav_path == Path("test.wav")
        assert result.duration_seconds == 60.0
        assert result.duration == 60.0
        assert result.sample_rate == 16000
        assert result.channels == 1


def test_extract_for_speech_success(tmp_path):
    """Test successful audio extraction for speech.

    Uses mocked FFmpeg and FFprobe for fast, isolated testing.
    """
    from utils.ffprobe_runner import ProbeResult

    video_path = tmp_path / "test.mkv"
    output_wav = tmp_path / "test.wav"
    video_path.touch()
    output_wav.touch()  # Pre-create output to simulate success

    with patch("utils.audio_processor.run_ffmpeg") as mock_ffmpeg:
        # Mock successful FFmpeg execution
        mock_ffmpeg.return_value = FFmpegResult(
            success=True,
            return_code=0,
            command=["ffmpeg"],
            stderr_bytes=b"",
            stdout_bytes=b"",
        )

        with patch("utils.ffprobe_runner.probe_file") as mock_probe:
            # Mock FFprobe returning audio info
            mock_probe.return_value = ProbeResult(
                success=True,
                return_code=0,
                data={"format": {"duration": "60.0"}},
                stderr="",
            )

            result = extract_for_speech(video_path, output_wav_path=output_wav)

    assert result.success
    assert result.output_file == output_wav
    assert result.duration == 60.0
    mock_ffmpeg.assert_called()


def test_extract_for_speech_failure(tmp_path):
    """Test failed audio extraction.

    Verifies error handling when FFmpeg fails.
    """
    video_path = tmp_path / "test.mkv"
    video_path.touch()

    with patch("utils.audio_processor.run_ffmpeg") as mock_ffmpeg:
        # Configure mock to return failure
        mock_ffmpeg.return_value = FFmpegResult(
            success=False,
            return_code=1,
            command=["ffmpeg"],
            stderr_bytes=b"FFmpeg error: Invalid file format",
            stdout_bytes=b"",
        )

        result = extract_for_speech(video_path)

    assert not result.success
    assert "FFmpeg error" in result.error_message or "Invalid" in result.error_message
