"""
src/cli/merge_cmd.py

CLI interface for the dual-audio merge workflow (DE + EN → single MKV).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from core.video import  merge_directory, merge_dual_audio, derive_output_name

app = typer.Typer(help="Merge German + English MP4 files into one dual-audio MKV.")
console = Console()
err_console = Console(stderr=True, style="bold red")


@app.command("auto")
def auto_command(
    directory: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help=(
            "Directory containing the two language-specific MP4 files. "
            "Language is detected from filename suffixes: -de/_de/(de) and -en/_en/(en)."
        ),
    ),
    overwrite: bool = typer.Option(
        False, "--overwrite", help="Re-merge even if the target MKV already exists."
    ),
) -> None:
    """
    Auto-detect DE/EN MP4 files in DIRECTORY and merge them into one MKV.

    Expected filenames (examples):
      Movie Title-de.mp4 + Movie Title-en.mp4
      Movie Title_de.mp4 + Movie Title_en.mp4
      Movie Title (de).mp4 + Movie Title (en).mp4
    """
    console.rule("[bold cyan]media-tool · merge auto[/bold cyan]")
    console.print(f"[dim]Directory:[/dim] {directory}")

    result = merge_directory(directory, overwrite=overwrite)

    if result.succeeded:
        console.print(f"\n[bold green]✔  {result.message}[/bold green]")
        console.print(
            f"[dim]  German :[/dim] {result.german_source.name if result.german_source else '?'}"
        )
        console.print(
            f"[dim]  English:[/dim] {result.english_source.name if result.english_source else '?'}"
        )
        console.print(f"[dim]  Output :[/dim] {result.target.name}")
    elif result.skipped:
        console.print(f"\n[yellow]⏭  {result.message}[/yellow]")
    else:
        err_console.print(f"\n✘  {result.message}")
        if result.ffmpeg_result:
            stderr_tail = "\n".join(result.ffmpeg_result.stderr.splitlines()[-20:])
            console.print(f"\n[dim]ffmpeg stderr (tail):[/dim]\n{stderr_tail}", highlight=False)
        raise typer.Exit(code=1)


@app.command("manual")
def manual_command(
    german: Path = typer.Argument(
        ..., exists=True, file_okay=True, dir_okay=False,
        help="Path to the German-audio MP4 file."
    ),
    english: Path = typer.Argument(
        ..., exists=True, file_okay=True, dir_okay=False,
        help="Path to the English-audio MP4 file."
    ),
    target: Optional[Path] = typer.Option(
        None, "--target", "-t",
        help="Output .mkv path. Defaults to <german_parent>/<clean_title>.mkv",
    ),
    overwrite: bool = typer.Option(
        False, "--overwrite", help="Re-merge even if the target MKV already exists."
    ),
) -> None:
    """
    Merge two explicitly specified MP4 files into one dual-audio MKV.
    """
    console.rule("[bold cyan]media-tool · merge manual[/bold cyan]")

    resolved_target = target or (
        german.parent / f"{derive_output_name(german)}.mkv"
    )

    console.print(f"[dim]German :[/dim] {german}")
    console.print(f"[dim]English:[/dim] {english}")
    console.print(f"[dim]Target :[/dim] {resolved_target}")

    result = merge_dual_audio(german, english, resolved_target, overwrite=overwrite)

    if result.succeeded:
        console.print(f"\n[bold green]✔  {result.message}[/bold green]")
    elif result.skipped:
        console.print(f"\n[yellow]⏭  {result.message}[/yellow]")
    else:
        err_console.print(f"\n✘  {result.message}")
        if result.ffmpeg_result:
            stderr_tail = "\n".join(result.ffmpeg_result.stderr.splitlines()[-20:])
            console.print(f"\n[dim]ffmpeg stderr (tail):[/dim]\n{stderr_tail}", highlight=False)
        raise typer.Exit(code=1)
