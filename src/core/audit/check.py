# src/core/audit/check.py
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from core.audit.models import AuditFinding, CheckResult


class BaseCheck(ABC):
    """
    Basisklasse für alle Audit-Checks.

    Jede Unterklasse implementiert ``run()`` und gibt eine Liste von
    ``AuditFinding``-Objekten zurück.  ``execute()`` kümmert sich um
    Timing und Fehlerbehandlung.
    """

    #: Eindeutige ID z. B. "A01"
    check_id: str = "XX"
    #: Menschenlesbarer Name
    check_name: str = "Base Check"

    def execute(
        self,
        files: list[Path],
        probes: dict[Path, dict[str, Any]],
    ) -> CheckResult:
        start = time.monotonic()
        try:
            findings = self.run(files, probes)
        except Exception as exc:
            return CheckResult(
                check_id=self.check_id,
                findings=[],
                files_checked=len(files),
                duration_seconds=round(time.monotonic() - start, 2),
                error=str(exc),
            )
        return CheckResult(
            check_id=self.check_id,
            findings=findings,
            files_checked=len(files),
            duration_seconds=round(time.monotonic() - start, 2),
        )

    @abstractmethod
    def run(
        self,
        files: list[Path],
        probes: dict[Path, dict[str, Any]],
    ) -> list[AuditFinding]: ...
