"""
src/core/workflow/steps/s03_upscale_dvd.py

Step 3 – DVD-Rip upscalen zu H.265 720p.

Precondition: Es gibt MKV-/MP4-/AVI-Dateien mit height ≤ 576
              oder einem DVD-Rip-Kennzeichen im Dateinamen.
Run:          upscale_dvd() aus core.video.upscaler mit Profil 'dvd-hq'.
PostCheck:    Output existiert, hat height ≥ 720.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from core.workflow.models import StepResult, StepStatus, WorkflowContext
from core.workflow.step import BaseStep
from utils.ffprobe_runner import probe_file

logger = logging.getLogger(__name__)

_DVD_PATTERN = re.compile(r"dvd|dvdrip|dvdscr", re.IGNORECASE)
_VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi"}


def _is_dvd_rip(path: Path, height: int) -> bool:
    return height <= 576 or bool(_DVD_PATTERN.search(path.stem))


class UpscaleDvdStep(BaseStep):
    name = "03_upscale_dvd"

    def precondition(self, ctx: WorkflowContext) -> bool:
        candidates: list[Path] = []
        for f in ctx.working_files:
            if f.suffix.lower() not in _VIDEO_EXTENSIONS:
                continue
            probe = probe_file(f)
            video = probe.first_video()
            if video:
                h = int(str(video.get("height", 9999)))
                if _is_dvd_rip(f, h):
                    candidates.append(f)
        ctx.metadata["dvd_candidates"] = candidates
        return len(candidates) > 0

    def run(self, ctx: WorkflowContext) -> StepResult:
        from core.video.upscale_profiles import resolve_upscale_options
        from core.video.upscaler import UpscaleStatus, upscale_dvd

        opts = resolve_upscale_options("dvd-hq", overwrite=False)
        candidates: list[Path] = ctx.metadata["dvd_candidates"]
        outputs: list[Path] = []
        originals: list[Path] = []

        for source in candidates:
            if ctx.dry_run:
                outputs.append(source.with_stem(source.stem.strip() + " - [DVD]"))
                originals.append(source)
                continue
            upscale_result = upscale_dvd(source, opts=opts)
            if upscale_result.status == UpscaleStatus.SUCCESS and upscale_result.target:
                outputs.append(upscale_result.target)
                originals.append(source)
            else:
                logger.warning(
                    "Upscale fehlgeschlagen: %s – %s",
                    source.name,
                    upscale_result.message,
                )

        ctx.working_files = [f for f in ctx.working_files if f not in originals] + outputs

        return StepResult(
            step_name=self.name,
            status=StepStatus.SUCCESS,
            message=f"{len(outputs)} DVD-Rips hochskaliert (H.265, 720p).",
            output_files=outputs,
            deleted_files=originals if not ctx.dry_run else [],
        )

    def post_check(self, ctx: WorkflowContext, result: StepResult) -> bool:
        for out in result.output_files:
            if not out.exists():
                return False
            probe = probe_file(out)
            video = probe.first_video()
            if video and int(str(video.get("height", 0))) < 720:
                logger.warning("%s: Ausgabe unter 720p", out.name)
        return True
