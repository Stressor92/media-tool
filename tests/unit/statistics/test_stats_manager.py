from __future__ import annotations

from pathlib import Path

import pytest
from src.statistics.event_types import EventType, StatEvent
from src.statistics.stats_manager import StatsManager
from src.statistics.stats_persistence import StatsPersistence


def test_aggregate_updates_multiple_domains(tmp_path: Path) -> None:
    manager = StatsManager(persistence=StatsPersistence(data_dir=tmp_path))
    manager.load()
    events = [
        StatEvent(type=EventType.VIDEO_CONVERTED, timestamp="2026-04-03T10:00:00+00:00", duration_seconds=5.0),
        StatEvent(type=EventType.AUDIO_CONVERTED, timestamp="2026-04-03T10:00:01+00:00", duration_seconds=2.0),
        StatEvent(type=EventType.SUBTITLE_TRANSLATED, timestamp="2026-04-03T10:00:02+00:00", duration_seconds=3.0),
        StatEvent(type=EventType.EBOOK_PROCESSED, timestamp="2026-04-03T10:00:03+00:00", duration_seconds=1.0),
        StatEvent(type=EventType.SESSION_START, timestamp="2026-04-03T10:00:04+00:00"),
        StatEvent(type=EventType.SESSION_END, timestamp="2026-04-03T10:00:05+00:00", duration_seconds=11.0),
    ]

    manager.aggregate(events)
    snapshot = manager.get_snapshot()

    assert snapshot.video.converted == 1
    assert snapshot.audio.converted == 1
    assert snapshot.subtitles.translated == 1
    assert snapshot.ebooks.processed == 1
    assert snapshot.system.runs == 1
    assert snapshot.system.total_runtime_seconds == 11.0


def test_reset_without_confirm_raises(tmp_path: Path) -> None:
    manager = StatsManager(persistence=StatsPersistence(data_dir=tmp_path))
    manager.load()

    with pytest.raises(ValueError):
        manager.reset(confirm=False)


def test_reset_with_confirm_creates_backup_and_clears_snapshot(tmp_path: Path) -> None:
    manager = StatsManager(persistence=StatsPersistence(data_dir=tmp_path))
    manager.load()
    manager.aggregate([StatEvent(type=EventType.VIDEO_CONVERTED, timestamp="2026-04-03T10:00:00+00:00")])
    manager.save()

    manager.reset(confirm=True)

    snapshot = manager.get_snapshot()
    assert snapshot.totals.files_processed == 0
    backups = list(tmp_path.glob("stats_*.bak.json"))
    assert backups
