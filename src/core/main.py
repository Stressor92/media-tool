"""
src/cli/main.py

Root CLI entry point for media-tool.
Mounts all sub-command groups. This is the only place where sub-apps are wired together.
"""

from __future__ import annotations

import logging
import sys

import typer
from rich.logging import RichHandler

from cli.convert_cmd import app as convert_app
from cli.inspect_cmd import app as inspect_app
from cli.merge_cmd   import app as merge_app
from cli.upscale_cmd import app as upscale_app

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

app.add_typer(convert_app, name="convert", help="Convert MP4 files to MKV (lossless).")
app.add_typer(merge_app,   name="merge",   help="Merge DE+EN MP4 files into dual-audio MKV.")
app.add_typer(upscale_app, name="upscale", help="Upscale DVD-quality video to H.265 720p.")
app.add_typer(inspect_app, name="inspect", help="Scan media library and export metadata CSV.")


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
