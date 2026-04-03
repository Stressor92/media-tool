from __future__ import annotations

from pathlib import Path

from src.statistics.stats_models import StatsSnapshot
from src.statistics.stats_persistence import StatsPersistence


def test_load_missing_file_returns_empty_snapshot(tmp_path: Path) -> None:
    persistence = StatsPersistence(data_dir=tmp_path)
    snapshot = persistence.load()
    assert isinstance(snapshot, StatsSnapshot)
    assert snapshot.totals.files_processed == 0


def test_save_is_atomic_and_removes_tmp_file(tmp_path: Path) -> None:
    persistence = StatsPersistence(data_dir=tmp_path)
    snapshot = StatsSnapshot()
    snapshot.video.converted = 4

    persistence.save(snapshot)

    assert (tmp_path / "stats.json").exists()
    assert not (tmp_path / "stats.json.tmp").exists()


def test_corrupt_json_creates_backup_and_returns_empty(tmp_path: Path) -> None:
    stats_file = tmp_path / "stats.json"
    stats_file.write_text("{broken json", encoding="utf-8")

    persistence = StatsPersistence(data_dir=tmp_path)
    snapshot = persistence.load()

    assert snapshot.totals.files_processed == 0
    assert (tmp_path / "stats.json.bak").exists()


def test_unknown_keys_are_ignored(tmp_path: Path) -> None:
    stats_file = tmp_path / "stats.json"
    stats_file.write_text(
        '{"version": 1, "totals": {"files_processed": 2, "unknown": 1}, "unknown_root": true}',
        encoding="utf-8",
    )

    persistence = StatsPersistence(data_dir=tmp_path)
    snapshot = persistence.load()

    assert snapshot.totals.files_processed == 2
