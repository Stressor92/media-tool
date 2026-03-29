"""
src/core/workflow/runner.py

WorkflowRunner – executes an ordered list of BaseStep instances against a
WorkflowContext and returns a WorkflowResult.
"""

from __future__ import annotations

import logging

from core.workflow.models import StepStatus, WorkflowContext, WorkflowResult
from core.workflow.step import BaseStep

logger = logging.getLogger(__name__)


class WorkflowRunner:
    """
    Führt eine geordnete Liste von Steps gegen einen WorkflowContext aus.

    Verhalten:
    - Steps werden sequenziell ausgeführt.
    - SKIPPED-Steps werden protokolliert, aber nicht als Fehler gewertet.
    - Bei FAILED + stop_on_failure=True wird die Pipeline sofort gestoppt.
    - Am Ende wird ein WorkflowResult mit Gesamt-Status geliefert.
    """

    def __init__(self, steps: list[BaseStep]) -> None:
        self._steps = steps

    def run(self, ctx: WorkflowContext) -> WorkflowResult:
        logger.info(
            "=== Workflow started: %d steps | source=%s | output=%s ===",
            len(self._steps),
            ctx.source_dir,
            ctx.output_dir,
        )

        for step in self._steps:
            result = step.execute(ctx)

            if result.status == StepStatus.FAILED and ctx.stop_on_failure:
                logger.error(
                    "Pipeline aborted at step [%s]: %s", step.name, result.message
                )
                return WorkflowResult(
                    context=ctx,
                    overall_status=StepStatus.FAILED,
                    step_results=list(ctx.completed_steps),
                )

        overall = (
            StepStatus.FAILED
            if any(r.status == StepStatus.FAILED for r in ctx.completed_steps)
            else StepStatus.SUCCESS
        )

        logger.info("=== Workflow finished: %s ===", overall.name)
        return WorkflowResult(
            context=ctx,
            overall_status=overall,
            step_results=list(ctx.completed_steps),
        )


def build_movie_pipeline() -> WorkflowRunner:
    """
    Erstellt die Standard-Filmpipeline in der definierten Reihenfolge.

    Imports hier (nicht auf Modulebene) um zirkuläre Imports zu vermeiden.
    """
    from core.workflow.steps.s01_merge_language_dupes import MergeLanguageDupesStep
    from core.workflow.steps.s02_mp4_to_mkv import Mp4ToMkvStep
    from core.workflow.steps.s03_upscale_dvd import UpscaleDvdStep
    from core.workflow.steps.s04_encode_bluray import EncodeBlurayStep
    from core.workflow.steps.s05_subtitles import SubtitleStep
    from core.workflow.steps.s06_organize import OrganizeStep

    return WorkflowRunner(
        steps=[
            MergeLanguageDupesStep(),
            Mp4ToMkvStep(),
            UpscaleDvdStep(),
            EncodeBlurayStep(),
            SubtitleStep(),
            OrganizeStep(),
        ]
    )
