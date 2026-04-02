# src/core/audit/auditor.py
from __future__ import annotations

import logging
import time
from pathlib import Path

from core.audit.check import BaseCheck
from core.audit.check_registry import CheckRegistry
from core.audit.models import AuditReport
from utils.ffprobe_cache import FfprobeCache

logger = logging.getLogger(__name__)

_MEDIA_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".m4v", ".wmv", ".flv"}


class LibraryAuditor:
    """Orchestriert den vollständigen Audit-Lauf."""

    def __init__(
        self,
        checks: list[BaseCheck] | None = None,
        ffprobe_cache: FfprobeCache | None = None,
        max_workers: int = 8,
    ) -> None:
        self._checks = checks
        self._cache = ffprobe_cache or FfprobeCache(max_workers=max_workers)
        self._max_workers = max_workers

    def audit(
        self,
        root_dir: Path,
        recursive: bool = True,
    ) -> AuditReport:
        if not root_dir.is_dir():
            raise NotADirectoryError(f"Kein gültiger Ordner: {root_dir}")

        start = time.monotonic()
        logger.info("Audit gestartet: %s", root_dir)

        pattern = "**/*" if recursive else "*"
        files = sorted(f for f in root_dir.glob(pattern) if f.is_file() and f.suffix.lower() in _MEDIA_EXTENSIONS)
        logger.info("%d Mediendateien gefunden.", len(files))

        probes = self._cache.probe_all(files, root_dir=root_dir)

        # Resolve checks here so root-dir-aware checks get the correct path
        checks = self._checks if self._checks is not None else CheckRegistry.default_checks(root_dir)

        report = AuditReport(
            root_dir=root_dir,
            total_files=len(files),
        )

        for check in checks:
            logger.info("Führe Check '%s' aus …", check.check_name)
            result = check.execute(files, probes)
            report.check_results.append(result)
            if result.error:
                logger.warning("Check %s fehlgeschlagen: %s", check.check_id, result.error)

        report.duration_seconds = round(time.monotonic() - start, 1)
        logger.info(
            "Audit fertig in %.1fs: %d Findings.",
            report.duration_seconds,
            len(report.all_findings),
        )
        return report
