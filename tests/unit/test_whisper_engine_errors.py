"""Error-path tests aligned with the current WhisperEngine API."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from core.video.whisper_engine import WhisperConfig, WhisperEngine, WhisperModel


def _engine(language: str = "en") -> WhisperEngine:
    return WhisperEngine(WhisperConfig(model=WhisperModel.BASE, language=language))


class TestWhisperEngineErrorPaths:
    def test_transcribe_missing_audio_file(self) -> None:
        result = _engine().transcribe(Path("missing.wav"))
        assert result.success is False
        assert result.error_message is not None
        assert "not found" in result.error_message.lower()

    @patch("core.video.whisper_engine.WhisperEngine._get_audio_duration")
    def test_transcribe_duration_probe_failure(self, mock_duration: MagicMock) -> None:
        mock_duration.side_effect = RuntimeError("probe failed")
        with patch.object(Path, "exists", return_value=True):
            result = _engine().transcribe(Path("audio.wav"))

        assert result.success is False
        assert result.error_message is not None
        assert "failed to get wav duration" in result.error_message.lower()

    @patch("core.video.whisper_engine.WhisperEngine._run_whisper")
    @patch("core.video.whisper_engine.WhisperEngine._get_audio_duration")
    def test_transcribe_timeout(self, mock_duration: MagicMock, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_duration.return_value = 60.0
        mock_run.side_effect = TimeoutError("took too long")
        wav_path = tmp_path / "audio.wav"
        wav_path.touch()

        result = _engine().transcribe(wav_path)

        assert result.success is False
        assert result.error_message is not None
        assert "timeout" in result.error_message.lower()
        assert result.hallucination_warnings
        assert result.hallucination_warnings[0].type == "timeout"

    @patch("core.video.whisper_engine.WhisperEngine._run_whisper")
    @patch("core.video.whisper_engine.WhisperEngine._get_audio_duration")
    def test_transcribe_generic_failure(self, mock_duration: MagicMock, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_duration.return_value = 60.0
        mock_run.side_effect = RuntimeError("decoder crashed")
        wav_path = tmp_path / "audio.wav"
        wav_path.touch()

        result = _engine().transcribe(wav_path)

        assert result.success is False
        assert result.error_message is not None
        assert "decoder crashed" in result.error_message.lower()

    @patch("core.video.whisper_engine.WhisperEngine._run_whisper")
    @patch("core.video.whisper_engine.WhisperEngine._get_audio_duration")
    def test_transcribe_too_long_audio(self, mock_duration: MagicMock, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_duration.return_value = 90000.0
        wav_path = tmp_path / "audio.wav"
        wav_path.touch()

        result = _engine().transcribe(wav_path)

        assert result.success is False
        assert result.error_message is not None
        assert "too long" in result.error_message.lower()
        mock_run.assert_not_called()

    @patch("core.video.whisper_engine.WhisperEngine._run_whisper")
    @patch("core.video.whisper_engine.WhisperEngine._get_audio_duration")
    def test_transcribe_detects_missing_output_as_warning(
        self, mock_duration: MagicMock, _mock_run: MagicMock, tmp_path: Path
    ) -> None:
        mock_duration.return_value = 60.0
        wav_path = tmp_path / "audio.wav"
        wav_path.touch()
        output_path = tmp_path / "missing.srt"

        result = _engine().transcribe(wav_path, output_path)

        assert result.success is True
        assert result.hallucination_warnings
        assert result.hallucination_warnings[0].type == "timeout"
