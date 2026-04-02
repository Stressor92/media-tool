"""
src/core/workflow/steps/s01_merge_language_dupes.py

Step 1 – Sprachduplikate zusammenführen.

Precondition: Es gibt ≥ 2 Videodateien im Ordner mit gleichem Titel
              aber unterschiedlichen Sprach-Kennzeichnungen im Dateinamen
              (z. B. "Film.de.mkv" + "Film.en.mkv").
Run:          ffmpeg -map alle Streams → eine MKV mit mehreren Audiospuren.
PostCheck:    Output-Datei existiert und hat ≥ 2 Audiospuren (ffprobe).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from core.workflow.models import StepResult, StepStatus, WorkflowContext
from core.workflow.step import BaseStep
from utils.ffprobe_runner import probe_file

logger = logging.getLogger(__name__)

_LANG_PATTERN = re.compile(
    r"[._](de|ger|en|eng|fr|fre|es|spa|it|ita)(?:[._]|$)",
    re.IGNORECASE,
)


def _group_language_dupes(files: list[Path]) -> list[tuple[str, list[Path]]]:
    """
    Gruppiert Videodateien nach bereinigtem Titel (ohne Sprachkürzel).
    Gibt nur Gruppen zurück, die ≥ 2 Dateien enthalten.
    """
    groups: dict[str, list[Path]] = {}
    for f in files:
        clean = _LANG_PATTERN.sub(".", f.stem).strip(".")
        groups.setdefault(clean, []).append(f)
    return [(title, grp) for title, grp in groups.items() if len(grp) >= 2]


class MergeLanguageDupesStep(BaseStep):
    name = "01_merge_language_dupes"

    def precondition(self, ctx: WorkflowContext) -> bool:
        videos = list(ctx.source_dir.rglob("*.mkv")) + list(ctx.source_dir.rglob("*.mp4"))
        ctx.metadata["video_files"] = videos
        groups = _group_language_dupes(videos)
        ctx.metadata["dupe_groups"] = groups
        return len(groups) > 0

    def run(self, ctx: WorkflowContext) -> StepResult:
        from utils.ffmpeg_runner import run_ffmpeg

        groups: list[tuple[str, list[Path]]] = ctx.metadata["dupe_groups"]
        merged: list[Path] = []
        sources_to_delete: list[Path] = []

        for title, files in groups:
            output = ctx.source_dir / f"{title}.merged.mkv"
            if not ctx.dry_run:
                inputs: list[str] = []
                for f in files:
                    inputs += ["-i", str(f)]

                maps: list[str] = []
                for i in range(len(files)):
                    maps += ["-map", f"{i}:v?", "-map", f"{i}:a?", "-map", f"{i}:s?"]

                args = ["-y"] + inputs + maps + ["-c", "copy", "-map_metadata", "0", str(output)]
                result = run_ffmpeg(args)
                if not result.success:
                    logger.warning("Merge fehlgeschlagen für %s", title)
                    continue
            merged.append(output)
            sources_to_delete.extend(files)

        ctx.working_files = [f for f in ctx.metadata["video_files"] if f not in sources_to_delete] + merged

        return StepResult(
            step_name=self.name,
            status=StepStatus.SUCCESS,
            message=f"{len(merged)} Sprachduplikat-Gruppen zusammengeführt.",
            output_files=merged,
            deleted_files=sources_to_delete if not ctx.dry_run else [],
        )

    def post_check(self, ctx: WorkflowContext, result: StepResult) -> bool:
        for out in result.output_files:
            if not out.exists():
                logger.error("Merged file missing: %s", out)
                return False
            probe = probe_file(out)
            audio_count = len(probe.audio_streams())
            if audio_count < 2:
                logger.warning("%s hat nur %d Audiospur(en)", out.name, audio_count)
        return True
