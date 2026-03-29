"""
src/core/workflow/models.py

Data models shared across the workflow engine:
WorkflowContext, StepResult, StepStatus, WorkflowResult.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any


class StepStatus(Enum):
    SUCCESS = auto()   # Step erfolgreich abgeschlossen
    SKIPPED = auto()   # Precondition nicht erfüllt → kein Fehler
    FAILED  = auto()   # Fehler – Runner bricht ab oder fährt fort je nach Config
    PARTIAL = auto()   # Teilweise erfolgreich (z. B. ein Film von drei)


@dataclass
class StepResult:
    step_name: str
    status: StepStatus
    message: str
    output_files: list[Path] = field(default_factory=list)
    deleted_files: list[Path] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowContext:
    """
    Gemeinsamer Zustand, der durch alle Steps weitergereicht wird.
    Steps lesen und schreiben hier ihre Ergebnisse rein –
    nachfolgende Steps können darauf aufbauen.
    """

    source_dir: Path                # Eingangsordner (z. B. E:\Downloads\Movies)
    output_dir: Path                # Zielordner     (z. B. Y:\Movies)
    dry_run: bool = False
    stop_on_failure: bool = True    # Pipeline abbrechen bei erstem Fehler

    # Wird während des Laufs befüllt
    working_files: list[Path] = field(default_factory=list)
    completed_steps: list[StepResult] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_result(self, result: StepResult) -> None:
        self.completed_steps.append(result)

    def last_result(self) -> StepResult | None:
        return self.completed_steps[-1] if self.completed_steps else None


@dataclass
class WorkflowResult:
    context: WorkflowContext
    overall_status: StepStatus
    step_results: list[StepResult] = field(default_factory=list)

    @property
    def succeeded(self) -> bool:
        return self.overall_status == StepStatus.SUCCESS

    @property
    def failed_steps(self) -> list[StepResult]:
        return [r for r in self.step_results if r.status == StepStatus.FAILED]

    @property
    def skipped_steps(self) -> list[StepResult]:
        return [r for r in self.step_results if r.status == StepStatus.SKIPPED]
