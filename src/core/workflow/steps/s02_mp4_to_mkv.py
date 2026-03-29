"""
src/core/workflow/steps/s02_mp4_to_mkv.py

Step 2 – MP4 → MKV (lossless remux).

Precondition: Es gibt ≥ 1 MP4-Datei in ctx.working_files (oder source_dir).
Run:          Lossless remux via ffmpeg, erste Audiospur als 'ger' markiert.
PostCheck:    Alle Output-MKVs existieren.
"""

from __future__ import annotations

import logging
from pathlib import Path

from core.workflow.models import StepResult, StepStatus, WorkflowContext
from core.workflow.step import BaseStep

logger = logging.getLogger(__name__)


class Mp4ToMkvStep(BaseStep):
    name = "02_mp4_to_mkv"

    def precondition(self, ctx: WorkflowContext) -> bool:
        files = ctx.working_files or list(ctx.source_dir.rglob("*.mp4"))
        mp4s = [f for f in files if f.suffix.lower() == ".mp4"]
        ctx.metadata["mp4_files"] = mp4s
        return len(mp4s) > 0

    def run(self, ctx: WorkflowContext) -> StepResult:
        from utils.ffmpeg_runner import run_ffmpeg

        mp4s: list[Path] = ctx.metadata["mp4_files"]
        outputs: list[Path] = []
        originals: list[Path] = []

        for mp4 in mp4s:
            out = mp4.with_suffix(".mkv")
            if not ctx.dry_run:
                args = [
                    "-y", "-i", str(mp4),
                    "-map", "0",
                    "-c", "copy",
                    "-metadata:s:a:0", "language=ger",
                    "-disposition:a:0", "default",
                    str(out),
                ]
                result = run_ffmpeg(args)
                if not result.success:
                    logger.warning("Konvertierung fehlgeschlagen: %s", mp4.name)
                    continue
            outputs.append(out)
            originals.append(mp4)

        ctx.working_files = [
            f for f in (ctx.working_files or []) if f not in originals
        ] + outputs

        return StepResult(
            step_name=self.name,
            status=StepStatus.SUCCESS,
            message=f"{len(outputs)} MP4-Dateien nach MKV konvertiert.",
            output_files=outputs,
            deleted_files=originals if not ctx.dry_run else [],
        )

    def post_check(self, ctx: WorkflowContext, result: StepResult) -> bool:
        return all(f.exists() for f in result.output_files)
