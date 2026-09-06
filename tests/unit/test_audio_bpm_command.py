from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from cli.main import app
from core.audio.bpm_tagger import BPMTaggingResult, BPMTaggingStatus

runner = CliRunner()


def test_audio_tag_bpm_directory_success(tmp_path: Path) -> None:
    music_dir = tmp_path / "music"
    music_dir.mkdir()
    mp3_file = music_dir / "track.mp3"
    mp3_file.touch()

    results = [
        BPMTaggingResult(path=mp3_file, status=BPMTaggingStatus.UPDATED, bpm=128),
    ]

    with patch("core.audio.bpm_tagger.BPMTagger.tag_directory", return_value=results):
        cli_result = runner.invoke(app, ["audio", "tag-bpm", str(music_dir), "--no-recursive"])

    assert cli_result.exit_code == 0
    assert "Updated: 1" in cli_result.stdout
    assert "Failed: 0" in cli_result.stdout


def test_audio_tag_bpm_file_failure_returns_exit_1(tmp_path: Path) -> None:
    mp3_file = tmp_path / "track.mp3"
    mp3_file.touch()

    results = BPMTaggingResult(
        path=mp3_file,
        status=BPMTaggingStatus.FAILED,
        error="BPM-Analyse fehlgeschlagen",
    )

    with patch("core.audio.bpm_tagger.BPMTagger.tag_file", return_value=results):
        cli_result = runner.invoke(app, ["audio", "tag-bpm", str(mp3_file)])

    assert cli_result.exit_code == 1
    assert "Failed: 1" in cli_result.stdout


def test_audio_tag_bpm_dry_run_uses_preview_wording(tmp_path: Path) -> None:
    mp3_file = tmp_path / "track.mp3"
    mp3_file.touch()

    results = BPMTaggingResult(path=mp3_file, status=BPMTaggingStatus.UPDATED, bpm=110)

    with patch("core.audio.bpm_tagger.BPMTagger.tag_file", return_value=results):
        cli_result = runner.invoke(app, ["audio", "tag-bpm", str(mp3_file), "--dry-run"])

    assert cli_result.exit_code == 0
    assert "Would set BPM 110" in cli_result.stdout
