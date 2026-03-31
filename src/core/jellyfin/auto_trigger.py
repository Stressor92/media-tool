# src/core/jellyfin/auto_trigger.py
"""
Hook that automatically updates Jellyfin after a workflow pipeline completes.
Attach to s06_organize.py or WorkflowRunner.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from core.jellyfin.client import JellyfinClient
from core.jellyfin.library_manager import LibraryManager
from core.jellyfin.models import RefreshResult

logger = logging.getLogger(__name__)


class JellyfinAutoTrigger:
    """
    Called after a successful workflow pipeline.
    Configured via media-tool.toml [jellyfin].
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        wait_for_scan: bool = False,
        scan_timeout: int = 300,
    ) -> None:
        client = JellyfinClient(base_url, api_key)
        self._manager = LibraryManager(client)
        self._wait = wait_for_scan
        self._scan_timeout = scan_timeout

    @classmethod
    def from_config(cls) -> Optional["JellyfinAutoTrigger"]:
        """
        Creates an instance from media-tool.toml.
        Returns None if Jellyfin is not configured.
        """
        try:
            from utils.config import get_config

            cfg = get_config()
            jf = cfg.jellyfin
            if not jf.api_key:
                return None
            return cls(
                base_url=jf.base_url,
                api_key=jf.api_key,
                wait_for_scan=jf.wait_for_scan,
                scan_timeout=jf.scan_timeout,
            )
        except Exception as exc:
            logger.debug("JellyfinAutoTrigger not initialised: %s", exc)
            return None

    def on_workflow_complete(self, output_path: Path) -> RefreshResult:
        """
        Callback for WorkflowRunner after s06_organize.
        Triggers a library refresh for the affected path.
        """
        if not self._manager.ping():
            logger.warning("Jellyfin not reachable — auto-refresh skipped.")
            return RefreshResult(triggered=False, message="Server not reachable.")

        result = self._manager.refresh_path(output_path)

        if result.triggered and self._wait:
            logger.info(
                "Waiting for scan to complete (max. %ds) …", self._scan_timeout
            )
            self._manager.wait_for_scan(self._scan_timeout)

        return result
