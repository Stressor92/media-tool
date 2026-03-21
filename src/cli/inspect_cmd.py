"""
src/cli/inspect_cmd.py

CLI interface for scanning a media library and exporting metadata to CSV.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn
from rich.table import Table
from rich import box

from core.video import VIDEO_EXTENSIONS, export_to_csv, inspect_file, scan_directory

app = typer.Typer(help="Scan a media library and export video metadata to CSV.")
console = Console()
err_console = Console(stderr=True, style="bold red")


@app.command("scan")
def scan_command(
    directory: Path = typer.Argument(
        ..., exists=True, file_okay=False, dir_okay=True, readable=True,
        help="Root directory to scan for video files.",
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o",
        help="Output CSV file path. Defaults to <directory>/media_list.csv",
    ),
    recursive: bool = typer.Option(
        True, "--recursive/--no-recursive", "-r",
        help="Scan subdirectories (default: on).",
    ),
    delimiter: str = typer.Option(
        ";", "--delimiter",
        help="CSV field delimiter. Default ';' is compatible with European Excel.",
    ),
    preview: bool = typer.Option(
        False, "--preview", "-p",
        help="Print a Rich table preview of the first 20 results in the terminal.",
    ),
) -> None:
    """
    Scan DIRECTORY for .mp4, .mkv, and .avi files, extract metadata via ffprobe,
    and export a CSV report.

    The CSV is Excel-compatible (UTF-8 BOM, semicolon delimiter).
    """
    console.rule("[bold cyan]media-tool · inspect scan[/bold cyan]")
    console.print(f"[dim]Directory :[/dim] {directory}")

    resolved_output = output or directory / "media_list.csv"
    console.print(f"[dim]CSV output :[/dim] {resolved_output}")

    # Collect files first for the progress bar
    pattern = "**/*" if recursive else "*"
    files = sorted(
        f for f in directory.glob(pattern)
        if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS
    )

    if not files:
        console.print("[yellow]No video files found.[/yellow]")
        raise typer.Exit(code=0)

    console.print(f"[dim]Files found:[/dim] {len(files)}\n")

    # Inspect with progress bar
    from core.video import inspect_file, VideoInfo
    results: list[VideoInfo] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Analysing files…", total=len(files))
        for f in files:
            progress.update(task, description=f"[cyan]{f.name[:50]}[/cyan]")
            results.append(inspect_file(f))
            progress.advance(task)

    # Export
    export_to_csv(results, resolved_output, delimiter=delimiter)

    errors = [r for r in results if r.probe_error]
    console.print(
        f"\n[bold green]✔  CSV saved:[/bold green] {resolved_output}\n"
        f"   Total: {len(results)}  |  "
        f"[green]OK: {len(results) - len(errors)}[/green]  |  "
        f"[red]Errors: {len(errors)}[/red]"
    )

    # Optional in-terminal preview table
    if preview:
        _print_preview(results[:20])
        if len(results) > 20:
            console.print(f"[dim]… and {len(results) - 20} more rows in the CSV.[/dim]")

    if errors:
        console.print("\n[yellow]Files with probe errors:[/yellow]")
        for r in errors:
            console.print(f"  [red]✘[/red] {r.file_name}: {r.probe_error_message[:80]}")


def _print_preview(results: list) -> None:
    """Render a condensed Rich table preview of inspection results."""
    table = Table(
        title="Media Library Preview",
        box=box.ROUNDED,
        show_lines=False,
        expand=True,
    )
    table.add_column("File",         style="cyan",  no_wrap=True, max_width=40)
    table.add_column("Size",         justify="right")
    table.add_column("Duration",     justify="center")
    table.add_column("Codec",        justify="center")
    table.add_column("Resolution",   justify="center")
    table.add_column("FPS",          justify="right")
    table.add_column("Audio",        justify="center")
    table.add_column("Subtitles",    justify="center")

    for r in results:
        audio_info = f"{r.audio_track_count} ({r.audio_languages})" if r.audio_track_count else "-"
        sub_info   = f"{r.subtitle_track_count} ({r.subtitle_languages})" if r.subtitle_track_count else "-"
        table.add_row(
            r.file_name,
            f"{r.size_gb:.2f} GB",
            r.duration,
            r.video_codec,
            r.resolution,
            r.fps,
            audio_info,
            sub_info,
        )

    console.print(table)
