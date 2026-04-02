from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkflowConfig:
    """Configuration knobs used by ebook workflow orchestration."""

    fetch_metadata: bool = True
    fetch_cover: bool = True
    normalize: bool = True
    embed_metadata: bool = True
    embed_cover: bool = True
    recursive: bool = True
    dry_run: bool = False
    copy_instead_of_move: bool = False
