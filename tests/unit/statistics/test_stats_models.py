from __future__ import annotations

import json
from dataclasses import asdict

from src.statistics.stats_models import DailyEntry, StatsSnapshot
from src.statistics.stats_persistence import _from_dict


def test_snapshot_is_constructible_without_args() -> None:
    snapshot = StatsSnapshot()
    assert snapshot.version == 1
    assert snapshot.totals.files_processed == 0


def test_stats_snapshot_roundtrip_json() -> None:
    snapshot = StatsSnapshot()
    snapshot.video.converted = 3
    snapshot.history[snapshot.created_at] = DailyEntry(files_processed=2, runtime_seconds=4.5, errors=1)
    payload = asdict(snapshot)

    raw = json.dumps(payload)
    loaded = json.loads(raw)
    restored = _from_dict(StatsSnapshot, loaded)

    assert restored == snapshot
