"""
src/cli/convert_cmd.py

CLI interface for the MP4 → MKV conversion workflow.
Responsibility: parse user input, call core functions, render output via Rich.

Rules:
- No ffmpeg logic here
- No file system traversal logic here
- Only orchestration + user-facing output
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich import box
from rich.console import Console
from rich.table import Table
from rich.text import Text

from core.video import (
    BatchConversionSummary,
    ConversionStatus,
    batch_convert_directory,
    convert_mp4_to_mkv,
    resolve_output_path,
)

app = typer.Typer(help="Convert MP4 files to MKV with proper audio metadata.")
console = Console()
err_console = Console(stderr=True, style="bold red")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _status_text(status: ConversionStatus) -> Text:
    """Map a ConversionStatus to a coloured Rich Text label."""
    mapping = {
        ConversionStatus.SUCCESS: Text("✔  OK", style="bold green"),
        ConversionStatus.SKIPPED: Text("⏭  Skipped", style="yellow"),
        ConversionStatus.FAILED: Text("✘  Failed", style="bold red"),
    }
    return mapping[status]


def _print_summary(summary: BatchConversionSummary) -> None:
    """Render a Rich table summarising the batch conversion results."""
    table = Table(
        title="Conversion Summary",
        box=box.ROUNDED,
        show_lines=True,
        expand=True,
    )
    table.add_column("File", style="cyan", no_wrap=True)
    table.add_column("Status", justify="center")
    table.add_column("Message")

    for result in summary.results:
        table.add_row(
            result.source.name,
            _status_text(result.status),
            result.message,
        )

    console.print(table)

    # Footer counters
    console.print(
        f"\n[bold]Total:[/bold] {summary.total}  "
        f"[green]Success: {len(summary.succeeded)}[/green]  "
        f"[yellow]Skipped: {len(summary.skipped)}[/yellow]  "
        f"[red]Failed:  {len(summary.failed)}[/red]"
    )


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command("batch")
def batch_command(
    directory: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help="Directory to scan for .mp4 files.",
    ),
    output_dir: Path | None = typer.Option(
        None,
        "--output-dir",
        "-o",
        help=(
            "Root directory for output subfolders. Defaults to the source directory (files placed next to originals)."
        ),
    ),
    language: str = typer.Option(
        "deu",
        "--language",
        "-l",
        help="ISO 639-2/B language code for the first audio stream (e.g. deu, eng).",
    ),
    audio_title: str = typer.Option(
        "Deutsch",
        "--audio-title",
        help="Human-readable title embedded in the first audio stream metadata.",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Re-convert even when the target MKV already exists.",
    ),
    recursive: bool = typer.Option(
        False,
        "--recursive",
        "-r",
        help="Also scan subdirectories for .mp4 files.",
    ),
) -> None:
    """
    Batch-convert all .mp4 files in DIRECTORY to MKV.

    Each output is placed in its own subfolder:
      <output-dir>/<BaseName>/<BaseName>.mkv
    """
    console.rule("[bold cyan]media-tool · batch convert[/bold cyan]")
    console.print(f"[dim]Scanning:[/dim] {directory}")

    if output_dir:
        console.print(f"[dim]Output root:[/dim] {output_dir}")

    try:
        summary = batch_convert_directory(
            directory=directory,
            output_root=output_dir,
            audio_language=language,
            audio_title=audio_title,
            overwrite=overwrite,
            recursive=recursive,
        )
    except NotADirectoryError as exc:
        err_console.print(str(exc))
        raise typer.Exit(code=1)

    if summary.total == 0:
        console.print("[yellow]No .mp4 files found.[/yellow]")
        raise typer.Exit(code=0)

    _print_summary(summary)

    # Non-zero exit code when any conversion failed
    if summary.failed:
        raise typer.Exit(code=1)


@app.command("single")
def single_command(
    source: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Path to the source .mp4 file.",
    ),
    target: Path | None = typer.Option(
        None,
        "--target",
        "-t",
        help=("Explicit output path for the .mkv file. Defaults to <source_parent>/<stem>/<stem>.mkv"),
    ),
    language: str = typer.Option(
        "deu",
        "--language",
        "-l",
        help="ISO 639-2/B language code for the first audio stream.",
    ),
    audio_title: str = typer.Option(
        "Deutsch",
        "--audio-title",
        help="Human-readable title for the first audio stream.",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Re-convert even when the target MKV already exists.",
    ),
) -> None:
    """
    Convert a single .mp4 file to MKV.
    """
    console.rule("[bold cyan]media-tool · single convert[/bold cyan]")

    resolved_target = target or resolve_output_path(source)

    console.print(f"[dim]Source:[/dim] {source}")
    console.print(f"[dim]Target:[/dim] {resolved_target}")

    result = convert_mp4_to_mkv(
        source=source,
        target=resolved_target,
        audio_language=language,
        audio_title=audio_title,
        overwrite=overwrite,
    )

    if result.succeeded:
        console.print(f"\n[bold green]✔  {result.message}[/bold green]")
    elif result.skipped:
        console.print(f"\n[yellow]⏭  {result.message}[/yellow]")
    else:
        err_console.print(f"\n✘  {result.message}")
        if result.ffmpeg_result:
            # Show last 20 lines of stderr for quick debugging
            stderr_tail = "\n".join(result.ffmpeg_result.stderr.splitlines()[-20:])
            console.print(
                f"\n[dim]ffmpeg stderr (tail):[/dim]\n{stderr_tail}",
                highlight=False,
            )
        raise typer.Exit(code=1)
