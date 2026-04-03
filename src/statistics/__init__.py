from __future__ import annotations

from .stats_collector import StatsCollector
from .stats_manager import StatsManager

_manager: StatsManager | None = None
_collector: StatsCollector | None = None


def init(manager: StatsManager | None = None) -> None:
    global _manager, _collector
    _manager = manager or StatsManager()
    _collector = StatsCollector()
    _manager.set_collector(_collector)


def get_manager() -> StatsManager:
    if _manager is None:
        raise RuntimeError("Statistics not initialized. Call statistics.init() first.")
    return _manager


def get_collector() -> StatsCollector:
    if _collector is None:
        raise RuntimeError("Statistics not initialized. Call statistics.init() first.")
    return _collector
