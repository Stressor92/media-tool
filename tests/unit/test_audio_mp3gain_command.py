from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from cli.main import app
from core.audio.mp3gain_normalizer import MP3GainFileResult, MP3GainStatus

runner = CliRunner()


def test_audio_mp3gain_directory_success(tmp_path: Path) -> None:
    music_dir = tmp_path / "music"
    music_dir.mkdir()
    mp3_file = music_dir / "track.mp3"
    mp3_file.touch()

    results = [
        MP3GainFileResult(path=mp3_file, status=MP3GainStatus.UPDATED),
    ]

    with patch("core.audio.mp3gain_normalizer.MP3GainNormalizer.normalize_path", return_value=results):
        cli_result = runner.invoke(app, ["audio", "mp3gain", str(music_dir), "--no-recursive"])

    assert cli_result.exit_code == 0
    assert "Updated: 1" in cli_result.stdout
    assert "Failed: 0" in cli_result.stdout


def test_audio_mp3gain_failure_returns_exit_1(tmp_path: Path) -> None:
    mp3_file = tmp_path / "track.mp3"
    mp3_file.touch()

    results = [
        MP3GainFileResult(
            path=mp3_file,
            status=MP3GainStatus.FAILED,
            error="mp3gain Fehler (Code 1): failed",
        )
    ]

    with patch("core.audio.mp3gain_normalizer.MP3GainNormalizer.normalize_path", return_value=results):
        cli_result = runner.invoke(app, ["audio", "mp3gain", str(mp3_file)])

    assert cli_result.exit_code == 1
    assert "Failed: 1" in cli_result.stdout


def test_audio_mp3gain_no_files_returns_exit_0(tmp_path: Path) -> None:
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    with patch("core.audio.mp3gain_normalizer.MP3GainNormalizer.normalize_path", return_value=[]):
        cli_result = runner.invoke(app, ["audio", "mp3gain", str(empty_dir)])

    assert cli_result.exit_code == 0
    assert "No MP3 files found" in cli_result.stdout
