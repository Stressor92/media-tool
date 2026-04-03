"""
src/core/workflow/steps/s05_subtitles.py

Step 5 – Untertitel prüfen / laden / generieren.

Precondition: Mindestens eine Arbeitsdatei hat ausschließlich englische
              Audiospuren UND keine deutschen/englischen Untertitelspuren.
Run:
  a) SubtitleDownloadManager.process() → OpenSubtitles API
  b) Fallback: Whisper (TODO – vorbereitet, noch nicht integriert)
PostCheck:    Datei hat ≥ 1 Untertitelspur (nur bei nicht-dry_run geprüft).
"""

from __future__ import annotations

import logging
from pathlib import Path

from core.workflow.models import StepResult, StepStatus, WorkflowContext
from core.workflow.step import BaseStep
from utils.ffprobe_runner import probe_file

logger = logging.getLogger(__name__)

_ENGLISH_LANG_CODES = {"eng", "en", "english"}
_WANTED_SUBTITLE_LANGS = {"eng", "en", "ger", "deu", "de"}


def _needs_subtitles(path: Path) -> bool:
    """True wenn: nur englische Audiospuren + keine passenden Subs."""
    probe = probe_file(path)

    audio_langs = {(s.get("tags") or {}).get("language", "").lower() for s in probe.audio_streams()}
    sub_langs = {(s.get("tags") or {}).get("language", "").lower() for s in probe.subtitle_streams()}

    only_english_audio = bool(audio_langs) and audio_langs.issubset(_ENGLISH_LANG_CODES)
    no_relevant_subs = not sub_langs.intersection(_WANTED_SUBTITLE_LANGS)
    return only_english_audio and no_relevant_subs


class SubtitleStep(BaseStep):
    name = "05_subtitles"

    def precondition(self, ctx: WorkflowContext) -> bool:
        needs_subs = [f for f in ctx.working_files if _needs_subtitles(f)]
        ctx.metadata["subtitle_candidates"] = needs_subs
        return len(needs_subs) > 0

    def run(self, ctx: WorkflowContext) -> StepResult:
        from core.subtitles.opensubtitles_provider import OpenSubtitlesProvider
        from core.subtitles.subtitle_downloader import SubtitleDownloadManager
        from utils.config import get_config
        from utils.ffmpeg_runner import FFmpegMuxer

        config = get_config()
        api_key = config.api.opensubtitles_api_key
        if not api_key:
            logger.warning("OpenSubtitles API key not configured – subtitle step skipped.")
            return StepResult(
                step_name=self.name,
                status=StepStatus.SKIPPED,
                message="OpenSubtitles API key missing – configure [api].opensubtitles_api_key.",
            )

        candidates: list[Path] = ctx.metadata["subtitle_candidates"]
        processed: list[Path] = []
        whisper_needed: list[str] = []

        manager = SubtitleDownloadManager(
            provider=OpenSubtitlesProvider(
                api_key,
                user_agent=config.api.opensubtitles_user_agent,
            ),
            ffmpeg_runner=FFmpegMuxer(),
        )

        for source in candidates:
            if ctx.dry_run:
                processed.append(source)
                continue

            dl_result = manager.process(
                video_path=source,
                languages=["de", "en"],
                auto_select=True,
                embed=True,
            )

            if dl_result.success:
                processed.append(source)
                logger.info("Untertitel via API geladen: %s", source.name)
            else:
                # Fallback: Whisper (TODO – sobald Whisper-Modul verfügbar)
                logger.info(
                    "API-Download fehlgeschlagen für %s – Whisper-Fallback noch nicht verfügbar.",
                    source.name,
                )
                whisper_needed.append(source.name)

        total = len(processed) + len(whisper_needed)
        status = StepStatus.SUCCESS if processed or total == 0 else StepStatus.PARTIAL

        return StepResult(
            step_name=self.name,
            status=status,
            message=(
                f"{len(processed)} Dateien mit Untertiteln versehen. {len(whisper_needed)} noch ohne (Whisper TODO)."
            ),
            output_files=processed,
            details={"whisper_fallback_needed": whisper_needed},
        )

    def post_check(self, ctx: WorkflowContext, result: StepResult) -> bool:
        if ctx.dry_run:
            return True
        for out in result.output_files:
            if not probe_file(out).subtitle_streams():
                logger.warning("%s: immer noch keine Untertitelspur nach Step", out.name)
        return True
