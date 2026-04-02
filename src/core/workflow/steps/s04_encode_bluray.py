"""
src/core/workflow/steps/s04_encode_bluray.py

Step 4 – Blu-ray-Quellen nach H.265 recodieren.

Precondition: MKV-Dateien mit height ≥ 720, codec ≠ hevc/av1,
              und Dateiname enthält 'BluRay'/'BDRip'/'Remux'
              ODER Videobitrate > 15 Mbit/s.
Run:          FFmpeg re-encode → H.265 CRF 18, preset slow, Audio copy.
PostCheck:    Output-Codec == hevc.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from core.workflow.models import StepResult, StepStatus, WorkflowContext
from core.workflow.step import BaseStep
from utils.ffprobe_runner import probe_file

logger = logging.getLogger(__name__)

_BLURAY_PATTERN = re.compile(r"blu.?ray|bdrip|brrip|remux", re.IGNORECASE)
_BITRATE_THRESHOLD = 15_000_000  # 15 Mbit/s


def _is_bluray_candidate(path: Path, video: dict[str, object]) -> bool:
    if _BLURAY_PATTERN.search(path.stem):
        return True
    codec = str(video.get("codec_name", ""))
    if codec in ("hevc", "av1"):  # bereits effizient komprimiert
        return False
    bitrate = int(str(video.get("bit_rate", 0) or 0))
    height = int(str(video.get("height", 0)))
    return height >= 720 and bitrate > _BITRATE_THRESHOLD


class EncodeBlurayStep(BaseStep):
    name = "04_encode_bluray"

    def precondition(self, ctx: WorkflowContext) -> bool:
        candidates: list[Path] = []
        for f in ctx.working_files:
            if f.suffix.lower() != ".mkv":
                continue
            probe = probe_file(f)
            video = probe.first_video()
            if video and _is_bluray_candidate(f, video):
                candidates.append(f)
        ctx.metadata["bluray_candidates"] = candidates
        return len(candidates) > 0

    def run(self, ctx: WorkflowContext) -> StepResult:
        from utils.ffmpeg_runner import run_ffmpeg

        candidates: list[Path] = ctx.metadata["bluray_candidates"]
        outputs: list[Path] = []
        originals: list[Path] = []

        for source in candidates:
            out = source.with_stem(source.stem + " [h265]")
            if not ctx.dry_run:
                args = [
                    "-y",
                    "-i",
                    str(source),
                    "-map",
                    "0",
                    "-c:v",
                    "libx265",
                    "-crf",
                    "18",
                    "-preset",
                    "slow",
                    "-c:a",
                    "copy",
                    "-c:s",
                    "copy",
                    "-map_metadata",
                    "0",
                    "-map_chapters",
                    "0",
                    str(out),
                ]
                result = run_ffmpeg(args)
                if not result.success:
                    logger.warning("H.265-Encode fehlgeschlagen: %s", source.name)
                    continue
            outputs.append(out)
            originals.append(source)

        ctx.working_files = [f for f in ctx.working_files if f not in originals] + outputs

        return StepResult(
            step_name=self.name,
            status=StepStatus.SUCCESS,
            message=f"{len(outputs)} Blu-ray-Dateien nach H.265 kodiert.",
            output_files=outputs,
            deleted_files=originals if not ctx.dry_run else [],
        )

    def post_check(self, ctx: WorkflowContext, result: StepResult) -> bool:
        for out in result.output_files:
            if not out.exists():
                return False
            probe = probe_file(out)
            video = probe.first_video()
            if video and str(video.get("codec_name")) not in ("hevc", "libx265"):
                logger.error("%s: kein HEVC-Codec nach Encode", out.name)
                return False
        return True
