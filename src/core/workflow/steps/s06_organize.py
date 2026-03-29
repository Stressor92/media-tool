"""
src/core/workflow/steps/s06_organize.py

Step 6 – Jellyfin-konforme Umbenennung + Verschieben in Zielordner.

Precondition: ctx.working_files ist nicht leer.
Run:
  - Jellyfin-Pfad berechnen: <output_dir>/<Titel (Jahr)>/<Titel (Jahr)>.mkv
  - Datei verschieben; Zwischendateien löschen.
PostCheck:    Alle Zieldateien existieren.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from core.workflow.models import StepResult, StepStatus, WorkflowContext
from core.workflow.step import BaseStep

logger = logging.getLogger(__name__)


def _jellyfin_path(output_dir: Path, file: Path) -> Path:
    """
    Gibt den Jellyfin-konformen Zielpfad zurück:
      <output_dir>/<stem>/<stem><suffix>

    Der Ordnername entspricht immer dem Datei-Stem (inkl. Jahr falls vorhanden).
    """
    stem = file.stem
    return output_dir / stem / f"{stem}{file.suffix}"


class OrganizeStep(BaseStep):
    name = "06_organize"

    def precondition(self, ctx: WorkflowContext) -> bool:
        return len(ctx.working_files) > 0

    def run(self, ctx: WorkflowContext) -> StepResult:
        moved: list[Path] = []
        deleted: list[Path] = []

        for source in ctx.working_files:
            destination = _jellyfin_path(ctx.output_dir, source)

            if not ctx.dry_run:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), destination)
                logger.info("Verschoben: %s → %s", source.name, destination)

                if source != destination and source.exists():
                    source.unlink(missing_ok=True)
                    deleted.append(source)
            else:
                logger.info(
                    "[DRY-RUN] Würde verschieben: %s → %s", source, destination
                )

            moved.append(destination)

        ctx.working_files = moved

        return StepResult(
            step_name=self.name,
            status=StepStatus.SUCCESS,
            message=f"{len(moved)} Dateien in Zielordner verschoben.",
            output_files=moved,
            deleted_files=deleted,
        )

    def post_check(self, ctx: WorkflowContext, result: StepResult) -> bool:
        if ctx.dry_run:
            return True
        return all(f.exists() for f in result.output_files)
