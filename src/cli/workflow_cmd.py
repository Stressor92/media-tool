"""
src/cli/workflow_cmd.py

CLI interface for the automated media processing workflow engine.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich import box
from rich.console import Console
from rich.table import Table

from core.workflow.models import StepStatus, WorkflowContext
from core.workflow.runner import build_movie_pipeline

app = typer.Typer(help="Automatisierte Medien-Verarbeitungspipelines.")
console = Console()
err_console = Console(stderr=True, style="bold red")

_STATUS_ICONS = {
    "SUCCESS": "[bold green]✔  OK[/bold green]",
    "SKIPPED": "[yellow]⏭  Skipped[/yellow]",
    "FAILED": "[bold red]✘  Failed[/bold red]",
    "PARTIAL": "[yellow]⚠  Partial[/yellow]",
}


@app.command("movies")
def run_movie_workflow(
    source: Annotated[
        Path,
        typer.Argument(
            help="Quellordner mit Rohmaterial (z. B. E:\\Downloads\\Movies).",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
        ),
    ],
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Zielordner (Jellyfin-Bibliothek, z. B. Y:\\Filme).",
        ),
    ],
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Nur anzeigen, nichts verändern."),
    ] = False,
    keep_going: Annotated[
        bool,
        typer.Option("--keep-going", help="Bei Fehler weiterlaufen statt abbrechen."),
    ] = False,
) -> None:
    """
    Führt die komplette Film-Pipeline aus:

    \b
    01. Sprachduplikate zusammenführen  (Film.de + Film.en → eine MKV)
    02. MP4 → MKV remux                 (lossless, Sprache 'ger' gesetzt)
    03. DVD-Rips upscalen               (H.265 720p, Profil dvd-hq)
    04. Blu-ray → H.265 recodieren      (CRF 18, preset slow)
    05. Untertitel laden / generieren   (OpenSubtitles; Whisper als Fallback TODO)
    06. Jellyfin-Bibliothek organisieren (Umbenennen + Verschieben)
    """
    output.mkdir(parents=True, exist_ok=True)

    ctx = WorkflowContext(
        source_dir=source,
        output_dir=output,
        dry_run=dry_run,
        stop_on_failure=not keep_going,
    )

    console.rule("[bold cyan]media-tool · workflow movies[/bold cyan]")
    console.print(f"[dim]Source :[/dim] {source}")
    console.print(f"[dim]Output :[/dim] {output}")
    if dry_run:
        console.print("[bold yellow]DRY-RUN – keine Änderungen werden vorgenommen.[/bold yellow]")

    pipeline = build_movie_pipeline()
    result = pipeline.run(ctx)

    # ── Summary table ────────────────────────────────────────────────────
    table = Table(
        title="Workflow-Report",
        box=box.ROUNDED,
        show_lines=True,
        expand=True,
    )
    table.add_column("Step", style="cyan", no_wrap=True)
    table.add_column("Status", justify="center")
    table.add_column("Message")

    for step in result.step_results:
        icon = _STATUS_ICONS.get(step.status.name, step.status.name)
        table.add_row(step.step_name, icon, step.message)

    console.print(table)

    if result.overall_status == StepStatus.FAILED:
        err_console.print("Pipeline mit Fehler beendet.")
        raise typer.Exit(code=1)

    console.print("[bold green]Pipeline erfolgreich abgeschlossen.[/bold green]")
