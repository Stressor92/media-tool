# tests/unit/test_language_detection_pipeline.py
from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from core.language_detection.models import (
    DetectionMethod,
    DetectionRequest,
    LanguageDetectionResult,
)
from core.language_detection.pipeline import LanguageDetectionPipeline


def _mock_result(lang: str, conf: float) -> LanguageDetectionResult:
    return LanguageDetectionResult(
        language=lang, confidence=conf, method=DetectionMethod.WHISPER
    )


@pytest.fixture()
def mock_whisper() -> MagicMock:
    w = MagicMock()
    w.detect.return_value = _mock_result("ger", 0.93)
    return w


@pytest.fixture()
def pipeline(mock_whisper: MagicMock) -> LanguageDetectionPipeline:
    return LanguageDetectionPipeline(
        min_confidence=0.85,
        whisper_detector=mock_whisper,
    )


class TestPipeline:
    def test_heuristic_confident_skips_whisper(
        self, pipeline: LanguageDetectionPipeline, mock_whisper: MagicMock, tmp_path: Path
    ) -> None:
        f = tmp_path / "Film.German.mkv"
        req = DetectionRequest(video_path=f)
        result = pipeline.detect(req)
        assert result.language == "ger"
        mock_whisper.detect.assert_not_called()  # Whisper nicht gebraucht

    def test_whisper_called_when_heuristic_fails(
        self, pipeline: LanguageDetectionPipeline, mock_whisper: MagicMock, tmp_path: Path
    ) -> None:
        f = tmp_path / "completely_unnamed_file.mkv"
        f.write_bytes(b"\x00" * 100)  # Minimale Datei
        req = DetectionRequest(video_path=f)

        with patch("core.language_detection.pipeline.extract_audio_sample") as mock_sampler:
            sample = tmp_path / "sample.wav"
            sample.touch()
            mock_sampler.return_value = sample
            result = pipeline.detect(req)

        assert result.language == "ger"
        mock_whisper.detect.assert_called_once()

    def test_force_whisper_skips_heuristic(
        self, pipeline: LanguageDetectionPipeline, mock_whisper: MagicMock, tmp_path: Path
    ) -> None:
        f = tmp_path / "Film.German.mkv"
        req = DetectionRequest(video_path=f, force_whisper=True)
        with patch("core.language_detection.pipeline.extract_audio_sample") as mock_sampler:
            sample = tmp_path / "sample.wav"
            sample.touch()
            mock_sampler.return_value = sample
            pipeline.detect(req)
        mock_whisper.detect.assert_called_once()

    def test_low_confidence_result_returned_anyway(
        self, mock_whisper: MagicMock, tmp_path: Path
    ) -> None:
        mock_whisper.detect.return_value = _mock_result("fra", 0.45)
        pl = LanguageDetectionPipeline(
            min_confidence=0.85, whisper_detector=mock_whisper
        )
        f = tmp_path / "unknown.mkv"
        req = DetectionRequest(video_path=f)
        with patch("core.language_detection.pipeline.extract_audio_sample") as mock_sampler:
            sample = tmp_path / "sample.wav"
            sample.touch()
            mock_sampler.return_value = sample
            result = pl.detect(req)
        # Niedrige Konfidenz → trotzdem zurückgeben, Tagger entscheidet
        assert result.language == "fra"
        assert result.confidence < 0.85

    def test_whisper_exception_returns_unknown(
        self, mock_whisper: MagicMock, tmp_path: Path
    ) -> None:
        mock_whisper.detect.side_effect = RuntimeError("Whisper crashed")
        pl = LanguageDetectionPipeline(
            min_confidence=0.85, whisper_detector=mock_whisper
        )
        f = tmp_path / "unknown.mkv"
        req = DetectionRequest(video_path=f)
        with patch("core.language_detection.pipeline.extract_audio_sample") as mock_sampler:
            sample = tmp_path / "sample.wav"
            sample.touch()
            mock_sampler.return_value = sample
            result = pl.detect(req)
        assert result.language == "und"
        assert result.method == DetectionMethod.UNKNOWN

    def test_heuristic_uses_probe_container_tag(
        self, pipeline: LanguageDetectionPipeline, mock_whisper: MagicMock, tmp_path: Path
    ) -> None:
        f = tmp_path / "unknown.mkv"
        probe = {"streams": [{"codec_type": "audio", "tags": {"language": "eng"}}]}
        req = DetectionRequest(video_path=f)
        result = pipeline.detect(req, probe=probe)
        assert result.language == "eng"
        mock_whisper.detect.assert_not_called()

    def test_audio_sample_cleaned_up_after_whisper(
        self, pipeline: LanguageDetectionPipeline, mock_whisper: MagicMock, tmp_path: Path
    ) -> None:
        f = tmp_path / "unnamed.mkv"
        req = DetectionRequest(video_path=f)
        sample_path = tmp_path / "sample.wav"
        sample_path.touch()

        with patch("core.language_detection.pipeline.extract_audio_sample") as mock_sampler:
            mock_sampler.return_value = sample_path
            pipeline.detect(req)

        # After pipeline runs, the sample should be deleted
        assert not sample_path.exists()

    def test_lazy_whisper_model_created_on_demand(self, tmp_path: Path) -> None:
        pl = LanguageDetectionPipeline(min_confidence=0.85)
        assert pl._whisper is None  # Not created yet
        f = tmp_path / "unknown.mkv"
        req = DetectionRequest(video_path=f)

        class _FakeWhisper:
            def detect(self, audio_sample: Path, hint_languages: list[str] | None = None) -> LanguageDetectionResult:
                return _mock_result("ger", 0.95)

        with patch("core.language_detection.pipeline.extract_audio_sample") as mock_sampler:
            sample = tmp_path / "sample.wav"
            sample.touch()
            mock_sampler.return_value = sample
            with patch(
                "core.language_detection.pipeline.LanguageDetectionPipeline._get_whisper",
                return_value=_FakeWhisper(),
            ):
                result = pl.detect(req)

        assert result.language == "ger"
