from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime
from typing import Any

from .event_types import EventType, StatEvent

logger = logging.getLogger(__name__)


class StatsCollector:
    def __init__(self) -> None:
        self._events: list[StatEvent] = []
        self._lock = threading.Lock()
        self._session_start: datetime | None = None

    def start_session(self) -> None:
        self._session_start = datetime.now(UTC)
        self.record(EventType.SESSION_START)

    def record(self, event_type: EventType, duration_seconds: float = 0.0, **metadata: Any) -> None:
        try:
            event = StatEvent(
                type=event_type,
                timestamp=datetime.now(UTC).isoformat(),
                duration_seconds=max(0.0, float(duration_seconds)),
                metadata=dict(metadata),
            )
            with self._lock:
                self._events.append(event)
        except Exception:
            logger.debug("Stats event recording failed", exc_info=True)

    def end_session(self) -> list[StatEvent]:
        duration_seconds = 0.0
        if self._session_start is not None:
            duration_seconds = max(0.0, (datetime.now(UTC) - self._session_start).total_seconds())

        self.record(EventType.SESSION_END, duration_seconds=duration_seconds)

        with self._lock:
            events = list(self._events)
            self._events.clear()
        self._session_start = None
        return events

    def get_events(self) -> list[StatEvent]:
        with self._lock:
            return list(self._events)
