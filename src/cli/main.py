"""
src/cli/main.py

Root CLI entry point for media-tool.
Mounts all sub-command groups. This is the only place where sub-apps are wired together.
"""

from __future__ import annotations

import logging

import typer
from rich.logging import RichHandler

from cli.convert_cmd import app as convert_app
from cli.upscale_cmd import app as upscale_app
from cli.inspect_cmd import app as inspect_app
from cli.merge_cmd import app as merge_app
from cli.audio_cmd import app as audio_app
from cli.video_cmd import app as video_app
from cli.audiobook_cmd import app as audiobook_app
from cli.subtitle_cmd import app as subtitle_app

# ---------------------------------------------------------------------------
# Logging bootstrap
# ---------------------------------------------------------------------------
# Configure once at the root. Individual modules use module-level loggers.
# Level is overridden below by --verbose flag.

logging.basicConfig(
    level=logging.WARNING,
    format="%(message)s",
    handlers=[RichHandler(rich_tracebacks=True, show_path=False)],
)

root_logger = logging.getLogger()

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


# ---------------------------------------------------------------------------
# Global options callback
# ---------------------------------------------------------------------------


@app.callback()
def global_options(
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Enable verbose/debug logging output.",
        is_eager=True,
    ),
) -> None:
    """media-tool — modular media processing for Jellyfin."""
    if verbose:
        root_logger.setLevel(logging.DEBUG)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    app()


if __name__ == "__main__":
    main()
