"""
tests/unit/test_audio_processor.py

Unit tests for audio processing extensions.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch


from src.utils.audio_processor import AudioExtractionResult, extract_for_speech


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
            channels=1
        )

        assert result.success
        assert result.output_file == Path("test.wav")
        assert result.wav_path == Path("test.wav")
        assert result.duration_seconds == 60.0
        assert result.duration == 60.0
        assert result.sample_rate == 16000
        assert result.channels == 1


@patch('subprocess.run')
@patch('pathlib.Path.exists')
def test_extract_for_speech_success(mock_exists, mock_run):
    """Test successful audio extraction for speech."""
    mock_exists.return_value = True
    mock_run.return_value = MagicMock(returncode=0, stdout="60.0", stderr="")

    video_path = Path("test.mkv")
    result = extract_for_speech(video_path)

    assert result.success
    assert result.wav_path.exists()
    assert result.duration == 60.0
    mock_run.assert_called()


@patch('subprocess.run')
@patch('pathlib.Path.exists')
def test_extract_for_speech_failure(mock_exists, mock_run):
    """Test failed audio extraction."""
    mock_exists.return_value = True
    mock_run.return_value = MagicMock(returncode=1, stderr="FFmpeg error")

    video_path = Path("test.mkv")
    result = extract_for_speech(video_path)

    assert not result.success
    assert "FFmpeg error" in result.error_message