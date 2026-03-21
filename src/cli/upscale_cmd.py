"""
src/cli/upscale_cmd.py

CLI interface for the DVD upscale workflow (H.265 720p re-encode).
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from rich import box

from core.video import (
    BatchUpscaleSummary,
    UpscaleOptions,
    UpscaleStatus,
    batch_upscale_directory,
    upscale_dvd,
)

app = typer.Typer(help="Upscale DVD-quality video to 720p H.265.")
console = Console()
err_console = Console(stderr=True, style="bold red")


def _print_summary(summary: BatchUpscaleSummary) -> None:
    table = Table(title="Upscale Summary", box=box.ROUNDED, show_lines=True, expand=True)
    table.add_column("File", style="cyan", no_wrap=True)
    table.add_column("Status", justify="center")
    table.add_column("Before", justify="right")
    table.add_column("After",  justify="right")
    table.add_column("Δ",      justify="right")
    table.add_column("Time",   justify="right")
    table.add_column("Message")

    for r in summary.results:
        status_map = {
            UpscaleStatus.SUCCESS: "[bold green]✔  OK[/bold green]",
            UpscaleStatus.SKIPPED: "[yellow]⏭  Skipped[/yellow]",
            UpscaleStatus.FAILED:  "[bold red]✘  Failed[/bold red]",
        }
        table.add_row(
            r.source.name,
            status_map[r.status],
            f"{r.size_before_gb:.3f} GB" if r.size_before_gb else "-",
            f"{r.size_after_gb:.3f} GB"  if r.size_after_gb  else "-",
            f"{r.size_delta_gb:+.3f} GB" if r.succeeded       else "-",
            f"{r.duration_seconds:.0f}s"  if r.duration_seconds else "-",
            r.message,
        )

    console.print(table)
    console.print(
        f"\n[bold]Total:[/bold] {summary.total}  "
        f"[green]OK: {len(summary.succeeded)}[/green]  "
        f"[yellow]Skipped: {len(summary.skipped)}[/yellow]  "
        f"[red]Failed: {len(summary.failed)}[/red]"
    )


@app.command("batch")
def batch_command(
    directory: Path = typer.Argument(
        ..., exists=True, file_okay=False, dir_okay=True, readable=True,
        help="Directory to scan for .mkv files.",
    ),
    crf: int = typer.Option(21, "--crf", help="H.265 CRF quality value (lower = better, 18–28 recommended)."),
    preset: str = typer.Option("medium", "--preset", help="H.265 encoding preset (ultrafast…veryslow)."),
    overwrite: bool = typer.Option(False, "--overwrite", help="Re-encode even if output already exists."),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Also scan subdirectories."),
    target_height: int = typer.Option(720, "--height", help="Target output height in pixels."),
) -> None:
    """
    Batch-upscale all DVD-quality MKV files in DIRECTORY to H.265 720p.

    Files already at or above the target height are automatically skipped.
    Anime files are detected automatically (cropdetect disabled for them).
    """
    console.rule("[bold cyan]media-tool · upscale batch[/bold cyan]")
    console.print(f"[dim]Directory:[/dim] {directory}")

    opts = UpscaleOptions(
        crf=crf,
        preset=preset,
        overwrite=overwrite,
        target_height=target_height,
    )

    try:
        summary = batch_upscale_directory(directory, opts=opts, recursive=recursive)
    except NotADirectoryError as exc:
        err_console.print(str(exc))
        raise typer.Exit(code=1)

    if summary.total == 0:
        console.print("[yellow]No .mkv files found.[/yellow]")
        raise typer.Exit(code=0)

    _print_summary(summary)

    if summary.failed:
        raise typer.Exit(code=1)


@app.command("single")
def single_command(
    source: Path = typer.Argument(
        ..., exists=True, file_okay=True, dir_okay=False, readable=True,
        help="Path to the source .mkv file.",
    ),
    crf: int = typer.Option(21, "--crf"),
    preset: str = typer.Option("medium", "--preset"),
    overwrite: bool = typer.Option(False, "--overwrite"),
    target_height: int = typer.Option(720, "--height"),
) -> None:
    """Upscale a single MKV file to H.265 720p."""
    console.rule("[bold cyan]media-tool · upscale single[/bold cyan]")
    console.print(f"[dim]Source:[/dim] {source}")

    opts = UpscaleOptions(
        crf=crf, preset=preset, overwrite=overwrite, target_height=target_height
    )
    result = upscale_dvd(source, opts=opts)

    if result.succeeded:
        console.print(f"\n[bold green]✔  {result.message}[/bold green]")
        console.print(
            f"[dim]  Size:[/dim] {result.size_before_gb:.3f} GB → "
            f"{result.size_after_gb:.3f} GB  "
            f"([green]{result.size_delta_gb:+.3f} GB[/green])"
        )
        console.print(f"[dim]  Time:[/dim] {result.duration_seconds:.0f}s")
    elif result.skipped:
        console.print(f"\n[yellow]⏭  {result.message}[/yellow]")
    else:
        err_console.print(f"\n✘  {result.message}")
        if result.ffmpeg_result:
            stderr_tail = "\n".join(result.ffmpeg_result.stderr.splitlines()[-20:])
            console.print(f"\n[dim]ffmpeg stderr (tail):[/dim]\n{stderr_tail}", highlight=False)
        raise typer.Exit(code=1)
