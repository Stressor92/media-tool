"""Progress event primitives for long-running batch workflows."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class ProgressEvent:
    """UI-agnostic progress payload emitted by core batch operations."""

    stage: str
    current: int
    total: int
    item_name: str
    status: str
    message: str = ""


ProgressCallback = Callable[[ProgressEvent], None]


def emit_progress(callback: ProgressCallback | None, event: ProgressEvent) -> None:
    """Emit a progress event when a callback is registered."""
    if callback is not None:
        callback(event)
