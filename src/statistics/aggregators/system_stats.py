from __future__ import annotations

from datetime import datetime

from ..event_types import EventType, StatEvent
from ..stats_models import StatsSnapshot
from .base import BaseAggregator, ensure_daily_entry


class SystemStatsAggregator(BaseAggregator):
    _accepted = {EventType.SESSION_START, EventType.SESSION_END, EventType.ERROR_OCCURRED}

    def __init__(self) -> None:
        self._session_start: datetime | None = None

    def accepts(self, event: StatEvent) -> bool:
        return event.type in self._accepted

    def apply(self, event: StatEvent, snapshot: StatsSnapshot) -> StatsSnapshot:
        day_key = event.timestamp[:10]
        day = ensure_daily_entry(snapshot, day_key)

        if event.type == EventType.SESSION_START:
            snapshot.system.runs += 1
            day.runtime_seconds += event.duration_seconds
            try:
                self._session_start = datetime.fromisoformat(event.timestamp)
            except ValueError:
                self._session_start = None
            return snapshot

        if event.type == EventType.SESSION_END:
            snapshot.system.total_runtime_seconds += event.duration_seconds
            snapshot.totals.total_runtime_seconds += event.duration_seconds
            day.runtime_seconds += event.duration_seconds
            return snapshot

        snapshot.system.errors += 1
        day.errors += 1
        return snapshot
