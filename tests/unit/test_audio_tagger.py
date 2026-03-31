# tests/unit/test_audio_tagger.py
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.language_detection.audio_tagger import AudioTagger
from core.language_detection.models import (
    DetectionMethod,
    LanguageDetectionResult,
    TaggingStatus,
)
from core.language_detection.pipeline import LanguageDetectionPipeline


def _mock_detection(lang: str, conf: float = 0.95) -> LanguageDetectionResult:
    return LanguageDetectionResult(
        language=lang, confidence=conf, method=DetectionMethod.WHISPER
    )


@pytest.fixture()
def mock_pipeline() -> MagicMock:
    p = MagicMock(spec=LanguageDetectionPipeline)
    p.detect.return_value = _mock_detection("ger", 0.95)
    return p


def _make_probe(lang: str) -> MagicMock:
    probe = MagicMock()
    probe.streams = [{"codec_type": "audio", "tags": {"language": lang}}]
    return probe


class TestAudioTagger:
    def test_already_labeled_track_skipped(
        self, mock_pipeline: MagicMock, tmp_path: Path
    ) -> None:
        f = tmp_path / "film.mkv"
        f.touch()
        tagger = AudioTagger(pipeline=mock_pipeline)
        with patch("core.language_detection.audio_tagger.probe_file", return_value=_make_probe("ger")):
            results = tagger.tag_file(f)
        assert results[0].status == TaggingStatus.SKIPPED
        mock_pipeline.detect.assert_not_called()

    def test_unlabeled_track_gets_tagged(
        self, mock_pipeline: MagicMock, tmp_path: Path
    ) -> None:
        f = tmp_path / "film.mkv"
        f.touch()
        tagger = AudioTagger(pipeline=mock_pipeline)
        with (
            patch("core.language_detection.audio_tagger.probe_file", return_value=_make_probe("und")),
            patch("core.language_detection.audio_tagger.run_ffmpeg") as mock_ffmpeg,
            patch("shutil.move"),
        ):
            mock_ffmpeg.return_value = MagicMock(success=True)
            results = tagger.tag_file(f, dry_run=False)

        assert results[0].status == TaggingStatus.SUCCESS
        assert results[0].detected_language == "ger"

    def test_dry_run_calls_detection_but_not_ffmpeg(
        self, mock_pipeline: MagicMock, tmp_path: Path
    ) -> None:
        f = tmp_path / "film.mkv"
        f.touch()
        tagger = AudioTagger(pipeline=mock_pipeline)
        with (
            patch("core.language_detection.audio_tagger.probe_file", return_value=_make_probe("und")),
            patch("core.language_detection.audio_tagger.run_ffmpeg") as mock_ffmpeg,
        ):
            results = tagger.tag_file(f, dry_run=True)
        mock_pipeline.detect.assert_called_once()
        mock_ffmpeg.assert_not_called()   # Kein Schreiben im Dry-Run

    def test_low_confidence_returns_failed(self, tmp_path: Path) -> None:
        f = tmp_path / "film.mkv"
        f.touch()
        low_conf_pipeline = MagicMock(spec=LanguageDetectionPipeline)
        low_conf_pipeline.detect.return_value = _mock_detection("fra", 0.40)
        tagger = AudioTagger(pipeline=low_conf_pipeline, min_confidence=0.85)
        with patch("core.language_detection.audio_tagger.probe_file", return_value=_make_probe("und")):
            results = tagger.tag_file(f)
        assert results[0].status == TaggingStatus.FAILED
        assert "Konfidenz" in (results[0].error or "")

    def test_file_not_found_returns_failed(self, tmp_path: Path) -> None:
        f = tmp_path / "missing.mkv"
        tagger = AudioTagger()
        results = tagger.tag_file(f)
        assert len(results) == 1
        assert results[0].status == TaggingStatus.FAILED
        assert "nicht gefunden" in (results[0].error or "")

    def test_force_relabels_existing_track(
        self, mock_pipeline: MagicMock, tmp_path: Path
    ) -> None:
        f = tmp_path / "film.mkv"
        f.touch()
        tagger = AudioTagger(pipeline=mock_pipeline)
        with (
            patch("core.language_detection.audio_tagger.probe_file", return_value=_make_probe("eng")),
            patch("core.language_detection.audio_tagger.run_ffmpeg") as mock_ffmpeg,
            patch("shutil.move"),
        ):
            mock_ffmpeg.return_value = MagicMock(success=True)
            results = tagger.tag_file(f, force=True)
        # With force=True, even a labeled track should be processed
        mock_pipeline.detect.assert_called_once()
        assert results[0].status == TaggingStatus.SUCCESS

    def test_empty_audio_language_treated_as_unlabeled(
        self, mock_pipeline: MagicMock, tmp_path: Path
    ) -> None:
        f = tmp_path / "film.mkv"
        f.touch()
        probe = MagicMock()
        probe.streams = [{"codec_type": "audio", "tags": {"language": ""}}]
        tagger = AudioTagger(pipeline=mock_pipeline)
        with (
            patch("core.language_detection.audio_tagger.probe_file", return_value=probe),
            patch("core.language_detection.audio_tagger.run_ffmpeg") as mock_ffmpeg,
            patch("shutil.move"),
        ):
            mock_ffmpeg.return_value = MagicMock(success=True)
            results = tagger.tag_file(f)
        mock_pipeline.detect.assert_called_once()
        assert results[0].status == TaggingStatus.SUCCESS

    def test_ffmpeg_failure_raises_runtime_error(
        self, mock_pipeline: MagicMock, tmp_path: Path
    ) -> None:
        f = tmp_path / "film.mkv"
        f.touch()
        tagger = AudioTagger(pipeline=mock_pipeline)
        failing_ffmpeg = MagicMock(success=False, stderr="ffmpeg error output")
        with (
            patch("core.language_detection.audio_tagger.probe_file", return_value=_make_probe("und")),
            patch("core.language_detection.audio_tagger.run_ffmpeg", return_value=failing_ffmpeg),
        ):
            with pytest.raises(RuntimeError, match="FFmpeg Remux"):
                tagger.tag_file(f, dry_run=False)

    def test_tag_directory_processes_mkv_files(
        self, mock_pipeline: MagicMock, tmp_path: Path
    ) -> None:
        mkv1 = tmp_path / "film1.mkv"
        mkv2 = tmp_path / "film2.mkv"
        mkv1.touch()
        mkv2.touch()
        (tmp_path / "music.mp3").touch()  # Should not be processed

        tagger = AudioTagger(pipeline=mock_pipeline)
        with (
            patch("core.language_detection.audio_tagger.probe_file", return_value=_make_probe("und")),
            patch("core.language_detection.audio_tagger.run_ffmpeg") as mock_ffmpeg,
            patch("shutil.move"),
        ):
            mock_ffmpeg.return_value = MagicMock(success=True)
            results = tagger.tag_directory(tmp_path, recursive=False)

        # Only the 2 MKV files should be processed
        assert len(results) == 2

    def test_backup_created_when_enabled(
        self, mock_pipeline: MagicMock, tmp_path: Path
    ) -> None:
        f = tmp_path / "film.mkv"
        f.write_bytes(b"fake mkv content")
        tagger = AudioTagger(pipeline=mock_pipeline, create_backup=True)
        with (
            patch("core.language_detection.audio_tagger.probe_file", return_value=_make_probe("und")),
            patch("core.language_detection.audio_tagger.run_ffmpeg") as mock_ffmpeg,
            patch("shutil.move"),
        ):
            mock_ffmpeg.return_value = MagicMock(success=True)
            tagger.tag_file(f)

        assert (tmp_path / "film.mkv.bak").exists()

    def test_und_detection_result_returns_failed(
        self, tmp_path: Path
    ) -> None:
        """Even if confidence is high but language is 'und', result should be FAILED."""
        f = tmp_path / "film.mkv"
        f.touch()
        und_pipeline = MagicMock(spec=LanguageDetectionPipeline)
        und_pipeline.detect.return_value = LanguageDetectionResult(
            language="und", confidence=0.99, method=DetectionMethod.WHISPER
        )
        tagger = AudioTagger(pipeline=und_pipeline, min_confidence=0.85)
        with patch("core.language_detection.audio_tagger.probe_file", return_value=_make_probe("und")):
            results = tagger.tag_file(f)
        assert results[0].status == TaggingStatus.FAILED
