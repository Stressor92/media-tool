from __future__ import annotations

from pathlib import Path

# Compatibility shim: allow `import src.statistics...` while the real package
# lives at the source-root top level (`src/statistics`).
_REAL_PACKAGE_DIR = Path(__file__).resolve().parents[2] / "statistics"
if str(_REAL_PACKAGE_DIR) not in __path__:
    __path__.append(str(_REAL_PACKAGE_DIR))

# Pylance can't statically follow the `__path__` mutation used by this shim.
from .stats_collector import StatsCollector  # noqa: E402  # pyright: ignore[reportMissingImports]
from .stats_manager import StatsManager  # noqa: E402  # pyright: ignore[reportMissingImports]

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
