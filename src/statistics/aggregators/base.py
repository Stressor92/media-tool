from __future__ import annotations

from abc import ABC, abstractmethod

from ..event_types import StatEvent
from ..stats_models import DailyEntry, StatsSnapshot


class BaseAggregator(ABC):
    @abstractmethod
    def accepts(self, event: StatEvent) -> bool:
        """Return True if this aggregator handles the given event type."""

    @abstractmethod
    def apply(self, event: StatEvent, snapshot: StatsSnapshot) -> StatsSnapshot:
        """Apply event updates to snapshot and return the modified snapshot."""


def ensure_daily_entry(snapshot: StatsSnapshot, date_key: str) -> DailyEntry:
    if date_key not in snapshot.history:
        snapshot.history[date_key] = DailyEntry()
    return snapshot.history[date_key]
