"""
src/core/workflow/step.py

Abstract base class for all pipeline steps.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from core.workflow.models import StepResult, StepStatus, WorkflowContext

logger = logging.getLogger(__name__)


class BaseStep(ABC):
    """
    Basisklasse für alle Pipeline-Steps.

    Jeder Step implementiert drei Methoden:
      precondition()  – darf dieser Step überhaupt laufen?
      run()           – Kernlogik
      post_check()    – war das Ergebnis valide?
    """

    #: Eindeutiger Name – wird im Log und in Reports verwendet
    name: str = "base"

    def execute(self, ctx: WorkflowContext) -> StepResult:
        """Führt precondition → run → post_check aus."""
        logger.info("[%s] Evaluating precondition …", self.name)

        if not self.precondition(ctx):
            result = StepResult(
                step_name=self.name,
                status=StepStatus.SKIPPED,
                message="Precondition not met – step skipped.",
            )
            ctx.add_result(result)
            return result

        logger.info("[%s] Running …", self.name)
        try:
            result = self.run(ctx)
        except Exception as exc:  # noqa: BLE001
            logger.exception("[%s] Unhandled exception: %s", self.name, exc)
            result = StepResult(
                step_name=self.name,
                status=StepStatus.FAILED,
                message=str(exc),
            )
            ctx.add_result(result)
            return result

        if result.status == StepStatus.SUCCESS:
            if not self.post_check(ctx, result):
                result.status = StepStatus.FAILED
                result.message += " [post_check failed]"

        ctx.add_result(result)
        logger.info("[%s] → %s: %s", self.name, result.status.name, result.message)
        return result

    @abstractmethod
    def precondition(self, ctx: WorkflowContext) -> bool:
        """Gibt True zurück, wenn dieser Step ausgeführt werden soll."""

    @abstractmethod
    def run(self, ctx: WorkflowContext) -> StepResult:
        """Hauptlogik. Muss ein StepResult zurückgeben."""

    def post_check(self, ctx: WorkflowContext, result: StepResult) -> bool:
        """
        Optionale Nachprüfung (z. B. existiert die Output-Datei?).
        Standard: immer True.
        """
        return True
