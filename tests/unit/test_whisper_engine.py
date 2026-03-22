"""
tests/unit/test_whisper_engine.py

Unit tests for WhisperEngine and related components.
"""

import tempfile
import wave
from pathlib import Path
from unittest.mock import patch


from src.core.video import (
    HallucinationDetector,
    WhisperConfig,
    WhisperEngine,
    WhisperModel,
)


class TestHallucinationDetector:
    """Test hallucination detection logic."""

    def test_detect_known_patterns(self):
        """Test detection of known hallucination patterns."""
        detector = HallucinationDetector()

        # Test with known pattern
        srt_content = """
1
00:00:00,000 --> 00:00:05,000
Thank you for watching!

2
00:00:05,000 --> 00:00:10,000
Please subscribe to my channel.
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
            f.write(srt_content)
            srt_path = Path(f.name)

        try:
            warnings = detector.detect(srt_path, 10.0)
            assert len(warnings) == 2  # thank you and subscribe patterns
            assert all(w.type == "known_pattern" for w in warnings)
        finally:
            srt_path.unlink()

    def test_detect_repeated_text(self):
        """Test detection of repeated identical text."""
        detector = HallucinationDetector()

        srt_content = """
1
00:00:00,000 --> 00:00:05,000
This is a test.

2
00:00:05,000 --> 00:00:10,000
This is a test.

3
00:00:10,000 --> 00:00:15,000
This is a test.

4
00:00:15,000 --> 00:00:20,000
This is a test.

5
00:00:20,000 --> 00:00:25,000
This is a test.

6
00:00:25,000 --> 00:00:30,000
This is a test.
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
            f.write(srt_content)
            srt_path = Path(f.name)

        try:
            warnings = detector.detect(srt_path, 25.0)
            repeated_warnings = [w for w in warnings if w.type == "repeated_text"]
            assert len(repeated_warnings) == 1
            assert "this is a test" in repeated_warnings[0].message.lower()
        finally:
            srt_path.unlink()

    def test_detect_oversized_output(self):
        """Test detection of oversized SRT files."""
        detector = HallucinationDetector()

        # Create a very large SRT for short audio
        srt_content = "\n".join([f"{i}\n00:00:00,000 --> 00:00:01,000\nLine {i}\n" for i in range(1000)])

        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
            f.write(srt_content)
            srt_path = Path(f.name)

        try:
            warnings = detector.detect(srt_path, 10.0)  # 10 second audio
            oversized_warnings = [w for w in warnings if w.type == "oversized_output"]
            assert len(oversized_warnings) == 1
        finally:
            srt_path.unlink()


class TestWhisperEngine:
    """Test WhisperEngine transcription logic."""

    def create_test_wav(self, duration_seconds: float = 5.0) -> Path:
        """Create a minimal test WAV file."""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            wav_path = Path(f.name)

        # Create a simple WAV file
        with wave.open(str(wav_path), 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            # Write minimal data
            frames = b'\x00\x00' * int(16000 * duration_seconds)
            wav.writeframes(frames)

        return wav_path

    def test_transcribe_missing_wav(self):
        """Test transcribe with missing WAV file."""
        engine = WhisperEngine()
        result = engine.transcribe(Path("nonexistent.wav"))
        assert not result.success
        assert "not found" in result.error_message

    def test_transcribe_short_wav(self):
        """Test transcribe with too short WAV."""
        engine = WhisperEngine()
        wav_path = self.create_test_wav(5.0)  # 5 seconds

        try:
            result = engine.transcribe(wav_path)
            assert not result.success
            assert "too short" in result.error_message
        finally:
            wav_path.unlink()

    @patch('core.video.whisper_engine.WhisperEngine._run_whisper')
    @patch('core.video.whisper_engine.WhisperEngine._get_audio_duration')
    def test_transcribe_success(self, mock_duration, mock_run):
        """Test successful transcription."""
        mock_duration.return_value = 60.0  # 1 minute

        engine = WhisperEngine()
        wav_path = self.create_test_wav(60.0)

        try:
            with tempfile.NamedTemporaryFile(suffix='.srt', delete=False) as srt_file:
                srt_path = Path(srt_file.name)

            result = engine.transcribe(wav_path, srt_path)

            assert result.success
            assert result.srt_path == srt_path
            assert result.wav_duration == 60.0
            mock_run.assert_called_once()
        finally:
            wav_path.unlink()
            if srt_path.exists():
                srt_path.unlink()

    @patch('core.video.whisper_engine.WhisperEngine._run_whisper')
    @patch('core.video.whisper_engine.WhisperEngine._get_audio_duration')
    def test_transcribe_with_hallucinations(self, mock_duration, mock_run):
        """Test transcription with hallucination detection."""
        mock_duration.return_value = 60.0

        engine = WhisperEngine()
        wav_path = self.create_test_wav(60.0)

        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as srt_file:
                # Write SRT with known hallucination pattern
                srt_file.write("""1
00:00:00,000 --> 00:00:05,000
Thank you for watching!
""")
                srt_file.flush()
                srt_path = Path(srt_file.name)

            result = engine.transcribe(wav_path, srt_path)

            assert result.success
            assert len(result.hallucination_warnings) > 0
            assert any(w.type == "known_pattern" for w in result.hallucination_warnings)
        finally:
            wav_path.unlink()
            srt_path.unlink()

    def test_get_local_model_path(self):
        """Test local model path resolution."""
        config = WhisperConfig(model=WhisperModel.LARGE)
        engine = WhisperEngine(config)

        # Test with non-existent model
        path = engine._get_local_model_path()
        assert isinstance(path, Path)
        # Should return full path to model file
        assert str(path).endswith("ggml-large-v3.bin")

    def test_seconds_to_srt_time(self):
        """Test SRT timestamp formatting."""
        result = WhisperEngine._seconds_to_srt_time(3661.5)  # 1h 1m 1.5s
        assert result == "01:01:01,500"