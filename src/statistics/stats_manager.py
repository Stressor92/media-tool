from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any

from .aggregators.audio_stats import AudioStatsAggregator
from .aggregators.base import BaseAggregator
from .aggregators.ebook_stats import EbookStatsAggregator
from .aggregators.subtitle_stats import SubtitleStatsAggregator
from .aggregators.system_stats import SystemStatsAggregator
from .aggregators.video_stats import VideoStatsAggregator
from .event_types import EventType, StatEvent
from .stats_collector import StatsCollector
from .stats_models import StatsSnapshot
from .stats_persistence import StatsPersistence

logger = logging.getLogger(__name__)


class StatsManager:
    """
    Singleton-like manager for statistics lifecycle and aggregation.
    """

    def __init__(self, persistence: StatsPersistence | None = None) -> None:
        self._persistence = persistence or StatsPersistence()
        self._snapshot: StatsSnapshot | None = None
        self._collector: StatsCollector | None = None
        self._aggregators: list[BaseAggregator] = self._load_aggregators()

    def load(self) -> None:
        self._snapshot = self._persistence.load()

    def aggregate(self, events: list[StatEvent]) -> None:
        snapshot = self.get_snapshot()
        for event in events:
            handled = False
            for aggregator in self._aggregators:
                if aggregator.accepts(event):
                    snapshot = aggregator.apply(event, snapshot)
                    handled = True
            if not handled:
                logger.debug("Unknown statistics event type ignored: %s", event.type)
        self._snapshot = snapshot

    def save(self) -> None:
        snapshot = self.get_snapshot()
        self._persistence.save(snapshot)

    def get_snapshot(self) -> StatsSnapshot:
        if self._snapshot is None:
            self.load()
        if self._snapshot is None:
            self._snapshot = StatsSnapshot()
        return self._snapshot

    def reset(self, confirm: bool = False) -> None:
        if not confirm:
            raise ValueError("Reset requires confirm=True")
        self._persistence.backup()
        current = self.get_snapshot()
        self._snapshot = replace(StatsSnapshot(), created_at=current.created_at)
        self.save()

    def record(self, event_type: EventType, duration_seconds: float = 0.0, **metadata: Any) -> None:
        try:
            collector = self._collector
            if collector is None:
                from . import get_collector

                collector = get_collector()
            collector.record(event_type, duration_seconds=duration_seconds, **metadata)
        except Exception:
            logger.debug("Stats manager could not record event", exc_info=True)

    def set_collector(self, collector: StatsCollector) -> None:
        self._collector = collector

    def _load_aggregators(self) -> list[BaseAggregator]:
        return [
            VideoStatsAggregator(),
            AudioStatsAggregator(),
            SubtitleStatsAggregator(),
            EbookStatsAggregator(),
            SystemStatsAggregator(),
        ]
