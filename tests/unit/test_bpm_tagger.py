from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from core.audio.bpm_tagger import BPMTagger, BPMTaggingStatus


def test_tag_file_missing_returns_failed(tmp_path: Path) -> None:
    result = BPMTagger(analyzer=lambda _path: 120.0).tag_file(tmp_path / "missing.mp3")

    assert result.status == BPMTaggingStatus.FAILED
    assert "nicht gefunden" in (result.error or "")


def test_tag_file_skips_non_mp3_input(tmp_path: Path) -> None:
    wav_file = tmp_path / "track.wav"
    wav_file.touch()

    result = BPMTagger(analyzer=lambda _path: 120.0).tag_file(wav_file)

    assert result.status == BPMTaggingStatus.SKIPPED
    assert "MP3" in (result.error or "")


def test_tag_file_skips_when_bpm_exists_without_overwrite(tmp_path: Path) -> None:
    mp3_file = tmp_path / "track.mp3"
    mp3_file.touch()
    tagger = BPMTagger(analyzer=lambda _path: 130.0)

    with (
        patch.object(BPMTagger, "_read_existing_bpm", return_value=122),
        patch.object(BPMTagger, "_write_bpm_tag") as mock_write,
    ):
        result = tagger.tag_file(mp3_file, overwrite=False)

    assert result.status == BPMTaggingStatus.SKIPPED
    assert result.existing_bpm == 122
    mock_write.assert_not_called()


def test_tag_file_overwrites_existing_bpm_when_requested(tmp_path: Path) -> None:
    mp3_file = tmp_path / "track.mp3"
    mp3_file.touch()
    tagger = BPMTagger(analyzer=lambda _path: 127.6)

    with (
        patch.object(BPMTagger, "_read_existing_bpm", return_value=90),
        patch.object(BPMTagger, "_write_bpm_tag") as mock_write,
    ):
        result = tagger.tag_file(mp3_file, overwrite=True)

    assert result.status == BPMTaggingStatus.UPDATED
    assert result.bpm == 128
    assert result.existing_bpm == 90
    mock_write.assert_called_once_with(mp3_file, 128)


def test_tag_file_fails_when_bpm_not_reliable(tmp_path: Path) -> None:
    mp3_file = tmp_path / "track.mp3"
    mp3_file.touch()
    tagger = BPMTagger(analyzer=lambda _path: None)

    with patch.object(BPMTagger, "_read_existing_bpm", return_value=None):
        result = tagger.tag_file(mp3_file)

    assert result.status == BPMTaggingStatus.FAILED
    assert "ermittelt" in (result.error or "").lower()


def test_tag_directory_processes_only_mp3_files_recursively(tmp_path: Path) -> None:
    root_mp3 = tmp_path / "root.mp3"
    root_mp3.touch()
    subdir = tmp_path / "nested"
    subdir.mkdir()
    sub_mp3 = subdir / "sub.MP3"
    sub_mp3.touch()
    (subdir / "skip.flac").touch()

    tagger = BPMTagger(analyzer=lambda _path: 100.0)
    with (
        patch.object(BPMTagger, "_read_existing_bpm", return_value=None),
        patch.object(BPMTagger, "_write_bpm_tag"),
    ):
        results = tagger.tag_directory(tmp_path, recursive=True)

    assert len(results) == 2
    assert all(result.status == BPMTaggingStatus.UPDATED for result in results)


def test_normalize_bpm_value_maps_half_tempo_into_range() -> None:
    assert BPMTagger._normalize_bpm_value(30.0) == 60
    assert BPMTagger._normalize_bpm_value(240.0) == 120


def test_load_audio_for_bpm_uses_ffmpeg_fallback_on_direct_load_error(tmp_path: Path) -> None:
    mp3_file = tmp_path / "broken_decode.mp3"
    mp3_file.touch()

    class FakeLibrosa:
        def __init__(self) -> None:
            self.load_calls = 0

        def load(self, path: str, **kwargs):
            self.load_calls += 1
            if path.endswith(".mp3"):
                raise RuntimeError("Unspecified internal error")
            return [0.1, 0.2, 0.3], 22050

    fake_librosa = FakeLibrosa()

    def _ffmpeg_success(args: list[str]) -> SimpleNamespace:
        output_path = Path(args[-1])
        output_path.touch()
        return SimpleNamespace(failed=False, stderr="")

    tagger = BPMTagger(analyzer=lambda _path: 120.0)
    with patch("core.audio.bpm_tagger.run_ffmpeg", side_effect=_ffmpeg_success) as mock_ffmpeg:
        audio, sample_rate = tagger._load_audio_for_bpm(fake_librosa, mp3_file)

    assert sample_rate == 22050
    assert len(audio) == 3
    assert fake_librosa.load_calls == 3
    mock_ffmpeg.assert_called_once()


def test_load_audio_for_bpm_retries_with_offset_zero_when_initial_window_empty(tmp_path: Path) -> None:
    mp3_file = tmp_path / "short_track.mp3"
    mp3_file.touch()

    load_calls: list[float] = []

    class FakeLibrosa:
        def load(self, _path: str, **kwargs):
            load_calls.append(float(kwargs.get("offset", 0.0)))
            if kwargs.get("offset") == 15.0:
                return [], 22050
            return [0.2, 0.1], 22050

    tagger = BPMTagger(analyzer=lambda _path: 120.0)
    audio, sample_rate = tagger._load_audio_for_bpm(FakeLibrosa(), mp3_file)

    assert sample_rate == 22050
    assert len(audio) == 2
    assert load_calls == [15.0, 0.0]
