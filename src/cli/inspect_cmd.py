"""
src/cli/inspect_cmd.py

CLI interface for scanning a media library and exporting metadata to CSV.
"""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FuturesTimeout
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich import box
from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TaskID, TextColumn
from rich.table import Table

from core.video import VIDEO_EXTENSIONS, export_to_csv

if TYPE_CHECKING:
    from core.video.inspector import VideoInfo

app = typer.Typer(help="Scan a media library and export video metadata to CSV.")
console = Console()
err_console = Console(stderr=True, style="bold red")
logger = logging.getLogger(__name__)


@app.command("scan")
def scan_command(
    directory: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help="Root directory to scan for video files.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output CSV file path. Defaults to <directory>/media_list.csv",
    ),
    recursive: bool = typer.Option(
        True,
        "--recursive/--no-recursive",
        "-r",
        help="Scan subdirectories (default: on).",
    ),
    delimiter: str = typer.Option(
        ";",
        "--delimiter",
        help="CSV field delimiter. Default ';' is compatible with European Excel.",
    ),
    preview: bool = typer.Option(
        False,
        "--preview",
        "-p",
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

    # Collect files.  On slow NAS volumes the naïve glob("**/*") blocks
    # indefinitely on each subdirectory.  We instead:
    #   1. List the root with os.scandir() — fast (one SMB call).
    #   2. Scan each immediate subdirectory concurrently in a thread pool,
    #      with a per-directory timeout so hung SMB calls don't stall the whole scan.
    files: list[Path] = []

    def _scan_subtree(start: str) -> list[Path]:
        """Return all video files under *start* (recursive, errors silently skipped)."""
        found: list[Path] = []
        for root_s, _dirs, filenames in os.walk(start, onerror=lambda _e: None):
            for fname in filenames:
                if Path(fname).suffix.lower() in VIDEO_EXTENSIONS:
                    found.append(Path(root_s) / fname)
        return found

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        console=console,
        transient=True,
    ) as enum_progress:
        # Step 1: list the root directory (single fast SMB call)
        try:
            root_entries = list(os.scandir(str(directory)))
        except OSError as exc:
            err_console.print(f"Cannot read directory: {exc}")
            raise typer.Exit(code=1)

        for entry in root_entries:
            if entry.is_file() and Path(entry.name).suffix.lower() in VIDEO_EXTENSIONS:
                files.append(Path(entry.path))

        if recursive:
            subdirs = [Path(e.path) for e in root_entries if e.is_dir(follow_symlinks=False)]
            enum_task: TaskID = enum_progress.add_task("Scanning subdirectories…", total=len(subdirs))
            # Step 2: scan each subdirectory concurrently (16 threads, 5 min total timeout)
            # On NAS volumes with high latency, more workers overlap I/O waits efficiently.
            _ENUM_TIMEOUT = 300.0  # seconds for the entire enumeration batch
            with ThreadPoolExecutor(max_workers=16) as executor:
                future_map = {executor.submit(_scan_subtree, str(d)): d for d in subdirs}
                try:
                    for future in as_completed(future_map, timeout=_ENUM_TIMEOUT):
                        d = future_map[future]
                        enum_progress.update(
                            enum_task,
                            description=f"[cyan]{d.name[:50]}[/cyan]",
                            advance=1,
                        )
                        try:
                            files.extend(future.result())
                        except Exception:
                            pass  # errored subdirectory — skip
                except FuturesTimeout:
                    console.print(
                        f"[yellow]⚠  Some directories did not respond within "
                        f"{_ENUM_TIMEOUT:.0f}s and were skipped.[/yellow]"
                    )
    files.sort()

    if not files:
        console.print("[yellow]No video files found.[/yellow]")
        raise typer.Exit(code=0)

    console.print(f"[dim]Files found:[/dim] {len(files)}\n")

    # Inspect with progress bar
    from core.video import inspect_file

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
            info = inspect_file(f)
            results.append(info)
            if info.probe_error:
                logger.warning(
                    "probe error | %s | %s",
                    info.file_path,
                    info.probe_error_message,
                )
            else:
                logger.debug(
                    "scanned | %s | %s | %s | codec=%s | res=%s | audio=%d | subs=%d",
                    info.file_path,
                    info.size_gb,
                    info.duration,
                    info.video_codec,
                    info.resolution,
                    info.audio_track_count,
                    info.subtitle_track_count,
                )
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


def _print_preview(results: list[VideoInfo]) -> None:
    """Render a condensed Rich table preview of inspection results."""
    table = Table(
        title="Media Library Preview",
        box=box.ROUNDED,
        show_lines=False,
        expand=True,
    )
    table.add_column("File", style="cyan", no_wrap=True, max_width=40)
    table.add_column("Size", justify="right")
    table.add_column("Duration", justify="center")
    table.add_column("Codec", justify="center")
    table.add_column("Resolution", justify="center")
    table.add_column("FPS", justify="right")
    table.add_column("Audio", justify="center")
    table.add_column("Subtitles", justify="center")

    for r in results:
        audio_info = f"{r.audio_track_count} ({r.audio_languages})" if r.audio_track_count else "-"
        sub_info = f"{r.subtitle_track_count} ({r.subtitle_languages})" if r.subtitle_track_count else "-"
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
