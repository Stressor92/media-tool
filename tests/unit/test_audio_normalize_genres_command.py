from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from cli.main import app
from core.audio.genre_normalizer import (
    GenreNormalizationFileResult,
    GenreNormalizationRun,
    GenreNormalizationStatus,
    GenreReportPaths,
)

runner = CliRunner()


def _build_reports(tmp_path: Path) -> GenreReportPaths:
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    return GenreReportPaths(
        changes_csv=reports_dir / "changes.csv",
        unknown_genres_csv=reports_dir / "unknown_genres.csv",
        genre_statistics_csv=reports_dir / "genre_statistics.csv",
    )


def test_audio_normalize_genres_dry_run_success(tmp_path: Path) -> None:
    music_dir = tmp_path / "music"
    music_dir.mkdir()
    track = music_dir / "track.mp3"
    track.touch()

    run_result = GenreNormalizationRun(
        results=[
            GenreNormalizationFileResult(
                path=track,
                status=GenreNormalizationStatus.UPDATED,
                original_genre="ALT ROCK",
                normalized_genre="Rock; Alternative Rock",
                unknown_genres=("OddGenre",),
            )
        ],
        reports=_build_reports(tmp_path),
    )

    with patch("core.audio.genre_normalizer.GenreNormalizer.normalize_path", return_value=run_result):
        cli_result = runner.invoke(app, ["audio", "normalize-genres", str(music_dir), "--no-recursive"])

    assert cli_result.exit_code == 0
    assert "DRY RUN MODE" in cli_result.stdout
    assert "Would set GENRE" in cli_result.stdout
    assert "Updated: 1" in cli_result.stdout
    assert "Unknown values: 1" in cli_result.stdout


def test_audio_normalize_genres_failed_file_returns_exit_1(tmp_path: Path) -> None:
    track = tmp_path / "track.mp3"
    track.touch()

    run_result = GenreNormalizationRun(
        results=[
            GenreNormalizationFileResult(
                path=track,
                status=GenreNormalizationStatus.FAILED,
                message="GENRE konnte nicht gelesen werden",
            )
        ],
        reports=_build_reports(tmp_path),
    )

    with patch("core.audio.genre_normalizer.GenreNormalizer.normalize_path", return_value=run_result):
        cli_result = runner.invoke(app, ["audio", "normalize-genres", str(track), "--apply"])

    assert cli_result.exit_code == 1
    assert "Failed: 1" in cli_result.stdout
