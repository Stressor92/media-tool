from __future__ import annotations

from pathlib import Path

import pytest
import src.statistics as statistics
from src.statistics.event_types import EventType
from src.statistics.stats_manager import StatsManager
from src.statistics.stats_persistence import StatsPersistence
from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()


@pytest.mark.not_live_integration
def test_stats_lifecycle_persist_and_reload(tmp_path: Path) -> None:
    manager = StatsManager(persistence=StatsPersistence(data_dir=tmp_path))
    manager.load()
    statistics.init(manager)

    collector = statistics.get_collector()
    collector.start_session()
    collector.record(EventType.VIDEO_CONVERTED, duration_seconds=1.0)
    collector.record(EventType.AUDIO_CONVERTED, duration_seconds=2.0)

    events = collector.end_session()
    manager.aggregate(events)
    manager.save()

    reload_manager = StatsManager(persistence=StatsPersistence(data_dir=tmp_path))
    reload_manager.load()
    snapshot = reload_manager.get_snapshot()

    assert snapshot.video.converted == 1
    assert snapshot.audio.converted == 1


@pytest.mark.not_live_integration
def test_cli_stats_show_contains_video(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MEDIA_TOOL_STATS_DIR", str(tmp_path))

    result = runner.invoke(app, ["stats", "show"])

    assert result.exit_code == 0
    assert "Video" in result.stdout


@pytest.mark.not_live_integration
def test_cli_stats_reset_clears_snapshot(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MEDIA_TOOL_STATS_DIR", str(tmp_path))

    initial = runner.invoke(app, ["stats", "show"])
    assert initial.exit_code == 0

    reset = runner.invoke(app, ["stats", "reset", "--confirm"])
    assert reset.exit_code == 0

    after = runner.invoke(app, ["stats", "show"])
    assert after.exit_code == 0
