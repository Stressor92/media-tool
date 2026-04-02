# tests/unit/test_heuristic_detector.py
from __future__ import annotations

from pathlib import Path

from core.language_detection.heuristic_detector import HeuristicDetector
from core.language_detection.models import DetectionMethod

detector = HeuristicDetector()


class TestHeuristicDetector:
    def test_german_from_filename(self, tmp_path: Path) -> None:
        f = tmp_path / "Film.German.mkv"
        result = detector.detect_from_path(f)
        assert result is not None
        assert result.language == "ger"
        assert result.confidence >= 0.90

    def test_english_from_bracket(self, tmp_path: Path) -> None:
        f = tmp_path / "Film [EN].mkv"
        result = detector.detect_from_path(f)
        assert result is not None
        assert result.language == "eng"

    def test_de_dot_pattern(self, tmp_path: Path) -> None:
        f = tmp_path / "Film.de.mkv"
        result = detector.detect_from_path(f)
        assert result is not None
        assert result.language == "ger"

    def test_no_language_hint_returns_none(self, tmp_path: Path) -> None:
        f = tmp_path / "completely_unknown_film.mkv"
        result = detector.detect_from_path(f)
        assert result is None

    def test_container_tag_highest_confidence(self, tmp_path: Path) -> None:
        f = tmp_path / "film.mkv"
        probe = {"streams": [{"codec_type": "audio", "tags": {"language": "ger"}}]}
        result = detector.detect_from_path(f, stream_index=0, probe=probe)
        assert result is not None
        assert result.language == "ger"
        assert result.confidence >= 0.99

    def test_und_container_tag_ignored(self, tmp_path: Path) -> None:
        f = tmp_path / "film.mkv"
        probe = {"streams": [{"codec_type": "audio", "tags": {"language": "und"}}]}
        result = detector._from_container_tags(probe, 0)
        assert result is None

    def test_normalizes_full_language_name(self, tmp_path: Path) -> None:
        f = tmp_path / "film.mkv"
        probe = {"streams": [{"codec_type": "audio", "tags": {"language": "german"}}]}
        result = detector.detect_from_path(f, probe=probe)
        assert result is not None
        assert result.language == "ger"

    def test_english_container_tag(self, tmp_path: Path) -> None:
        f = tmp_path / "film.mkv"
        probe = {"streams": [{"codec_type": "audio", "tags": {"language": "english"}}]}
        result = detector.detect_from_path(f, probe=probe)
        assert result is not None
        assert result.language == "eng"

    def test_de_bracket(self, tmp_path: Path) -> None:
        f = tmp_path / "Film [DE].mkv"
        result = detector.detect_from_path(f)
        assert result is not None
        assert result.language == "ger"

    def test_method_is_heuristic(self, tmp_path: Path) -> None:
        f = tmp_path / "Film.German.mkv"
        result = detector.detect_from_path(f)
        assert result is not None
        assert result.method == DetectionMethod.HEURISTIC

    def test_directory_path_detected_lower_confidence(self, tmp_path: Path) -> None:
        # Use a directory name with delimiter patterns the regex recognizes (.german.)
        german_dir = tmp_path / "Film.German.Dub"
        german_dir.mkdir()
        f = german_dir / "unknownfilm.mkv"
        result = detector.detect_from_path(f)
        # The directory path contains ".german." which should match _from_directory
        # with reduced confidence (filename confidence × 0.85)
        assert result is not None
        assert result.language == "ger"
        assert result.confidence < 0.97  # directory confidence is reduced

    def test_stream_index_out_of_range_returns_none(self, tmp_path: Path) -> None:
        f = tmp_path / "film.mkv"
        probe = {"streams": [{"codec_type": "audio", "tags": {"language": "eng"}}]}
        result = detector._from_container_tags(probe, stream_index=5)
        assert result is None

    def test_missing_tags_dict_handled(self, tmp_path: Path) -> None:
        f = tmp_path / "film.mkv"
        probe = {
            "streams": [
                {"codec_type": "audio"}  # no tags key at all
            ]
        }
        result = detector._from_container_tags(probe, 0)
        assert result is None

    def test_non_audio_streams_ignored(self, tmp_path: Path) -> None:
        f = tmp_path / "film.mkv"
        probe = {
            "streams": [
                {"codec_type": "video", "tags": {"language": "ger"}},
                {"codec_type": "audio", "tags": {"language": "und"}},
            ]
        }
        result = detector._from_container_tags(probe, 0)
        # First audio stream is "und" → should return None
        assert result is None

    def test_detect_protocol_fallback(self, tmp_path: Path) -> None:
        f = tmp_path / "sample.wav"
        result = detector.detect(f)
        assert result.language == "und"
        assert result.confidence == 0.0
