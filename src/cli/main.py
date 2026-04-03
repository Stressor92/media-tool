"""
src/cli/main.py

Root CLI entry point for media-tool.
Mounts all sub-command groups. This is the only place where sub-apps are wired together.
"""

from __future__ import annotations

import atexit
from pathlib import Path

import typer
from src.statistics.stats_manager import StatsManager

from cli.audio_cmd import app as audio_app
from cli.audiobook_cmd import app as audiobook_app
from cli.audit_cmd import app as audit_app
from cli.convert_cmd import app as convert_app
from cli.download_cmd import app as download_app
from cli.ebook_cmd import app as ebook_app
from cli.inspect_cmd import app as inspect_app
from cli.jellyfin_cmd import app as jellyfin_app
from cli.merge_cmd import app as merge_app
from cli.metadata_cmd import app as metadata_app
from cli.stats_cmd import app as stats_app
from cli.subtitle_cmd import app as subtitle_app
from cli.upscale_cmd import app as upscale_app
from cli.video_cmd import app as video_app
from cli.workflow_cmd import app as workflow_app
from utils.config import get_config
from utils.logging_config import setup_logging

# ---------------------------------------------------------------------------
# Root app
# ---------------------------------------------------------------------------

app = typer.Typer(
    name="media-tool",
    help="Automate media preparation for Jellyfin / NAS storage.",
    add_completion=False,
    no_args_is_help=True,
)

app.add_typer(convert_app, name="convert", help="Convert media files (MP4 → MKV, etc.)")
app.add_typer(upscale_app, name="upscale", help="Upscale DVD-quality video to 720p H.265.")
app.add_typer(inspect_app, name="inspect", help="Scan media library and export metadata to CSV.")
app.add_typer(merge_app, name="merge", help="Merge German + English MP4 files into dual-audio MKV.")
app.add_typer(audio_app, name="audio", help="Process music files.")
app.add_typer(video_app, name="video", help="Process video files.")
app.add_typer(audiobook_app, name="audiobook", help="Process audiobook files.")
app.add_typer(subtitle_app, name="subtitle", help="Download and manage subtitles from OpenSubtitles.org.")
app.add_typer(stats_app, name="stats", help="Show and manage statistics.")
app.add_typer(download_app, name="download", help="Download music, videos, and series using yt-dlp.")
app.add_typer(workflow_app, name="workflow", help="Run automated media processing pipelines.")
app.add_typer(jellyfin_app, name="jellyfin", help="Manage and sync the Jellyfin media library.")
app.add_typer(audit_app, name="audit", help="Audit a media library for quality and naming issues.")
app.add_typer(metadata_app, name="metadata", help="Fetch movie metadata and artwork from TMDB.")
app.add_typer(ebook_app, name="ebook", help="Process ebooks and show active ebook configuration.")


# ---------------------------------------------------------------------------
# Global options callback
# ---------------------------------------------------------------------------


@app.callback()
def global_options(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable informative progress logging (INFO level).",
        is_eager=True,
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Enable detailed technical logging (DEBUG level).",
        is_eager=True,
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Show only warnings and errors.",
        is_eager=True,
    ),
    log_file: Path | None = typer.Option(
        None,
        "--log-file",
        help="Write rotating logs to file, e.g. logs/media-tool.log",
        is_eager=True,
    ),
    log_json: bool = typer.Option(
        False,
        "--log-json",
        help="Write structured JSON logs when --log-file is set.",
        is_eager=True,
    ),
) -> None:
    """media-tool — modular media processing for Jellyfin."""
    setup_logging(
        verbose=verbose,
        debug=debug,
        quiet=quiet,
        log_file=log_file,
        log_json=log_json,
    )

    try:
        config = get_config()
        if not config.statistics.enabled:
            return

        import src.statistics as statistics

        manager = StatsManager()
        manager.load()
        statistics.init(manager)
        statistics.get_collector().start_session()

        def _flush_stats() -> None:
            try:
                events = statistics.get_collector().end_session()
                manager.aggregate(events)
                manager.save()
            except Exception:
                return

        atexit.register(_flush_stats)
    except Exception:
        return


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    app()


if __name__ == "__main__":
    main()
