from __future__ import annotations

import csv
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from src.statistics import get_manager
from src.statistics.stats_persistence import StatsPersistence

app = typer.Typer(help="Show, export and manage media-tool statistics.")
console = Console()
err_console = Console(stderr=True, style="bold red")


def _format_duration(seconds: float) -> str:
    total = int(max(0.0, seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


@app.command("show")
def show_stats() -> None:
    manager = get_manager()
    snapshot = manager.get_snapshot()

    error_rate = 0.0
    if snapshot.system.runs > 0:
        error_rate = (snapshot.system.errors / snapshot.system.runs) * 100.0

    avg_video_seconds = 0.0
    video_count = snapshot.video.converted + snapshot.video.upscaled + snapshot.video.merged
    if video_count > 0:
        avg_video_seconds = snapshot.video.total_processing_time_seconds / video_count

    avg_runtime = 0.0
    if snapshot.system.runs > 0:
        avg_runtime = snapshot.system.total_runtime_seconds / snapshot.system.runs

    today = snapshot.last_updated
    today_entry = snapshot.history.get(today)

    console.print("\n[bold cyan]Media Tool Statistics[/bold cyan]")
    console.print("[dim]" + "=" * 52 + "[/dim]")

    console.print("\n[bold]Video[/bold]")
    console.print(
        f"  Converted: {snapshot.video.converted}  Upscaled: {snapshot.video.upscaled}  Merged: {snapshot.video.merged}"
    )
    console.print(
        f"  Total time: {_format_duration(snapshot.video.total_processing_time_seconds)}  Avg/file: {_format_duration(avg_video_seconds)}"
    )

    console.print("\n[bold]Audio[/bold]")
    console.print(
        f"  Converted: {snapshot.audio.converted}  Normalized: {snapshot.audio.normalized}  Tagged: {snapshot.audio.tagged}"
    )
    console.print(f"  Total time: {_format_duration(snapshot.audio.total_processing_time_seconds)}")

    console.print("\n[bold]Subtitles[/bold]")
    console.print(
        f"  Downloaded: {snapshot.subtitles.downloaded}  Generated: {snapshot.subtitles.generated}  Translated: {snapshot.subtitles.translated}"
    )
    if snapshot.subtitles.by_language:
        langs = " · ".join(f"{k} ({v})" for k, v in sorted(snapshot.subtitles.by_language.items()))
        console.print(f"  Languages: {langs}")

    console.print("\n[bold]Ebooks[/bold]")
    console.print(
        f"  Processed: {snapshot.ebooks.processed}  Converted: {snapshot.ebooks.converted}  Enriched: {snapshot.ebooks.metadata_enriched}"
    )

    console.print("\n[bold]System[/bold]")
    console.print(
        f"  Sessions: {snapshot.system.runs}  Errors: {snapshot.system.errors}  Error rate: {error_rate:.1f}%"
    )
    console.print(
        f"  Avg runtime: {_format_duration(avg_runtime)}  Total runtime: {_format_duration(snapshot.system.total_runtime_seconds)}"
    )

    if today_entry is not None:
        console.print(f"\n[bold]Today ({today})[/bold]")
        console.print(
            f"  Files: {today_entry.files_processed}  Runtime: {_format_duration(today_entry.runtime_seconds)}  Errors: {today_entry.errors}"
        )

    if snapshot.totals.files_processed >= 1000:
        console.print("\n[bold green]Milestone reached: 1,000+ files processed![/bold green]")


@app.command("history")
def history(days: int = typer.Option(7, "--days", min=1, max=3650)) -> None:
    snapshot = get_manager().get_snapshot()
    table = Table(title=f"Last {days} Days", show_header=True)
    table.add_column("Date")
    table.add_column("Files", justify="right")
    table.add_column("Runtime", justify="right")
    table.add_column("Errors", justify="right")

    items = sorted(snapshot.history.items(), key=lambda kv: kv[0], reverse=True)[:days]
    for day, entry in items:
        table.add_row(day, str(entry.files_processed), _format_duration(entry.runtime_seconds), str(entry.errors))

    if not items:
        console.print("No history available yet.")
        return

    console.print(table)


@app.command("export")
def export_stats(
    output: Path = typer.Option(..., "--output", "-o"),
    format: str = typer.Option("json", "--format", "-f"),
) -> None:
    manager = get_manager()
    snapshot = manager.get_snapshot()
    fmt = format.lower()

    output.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "json":
        payload = manager.get_snapshot()
        from dataclasses import asdict

        output.write_text(json.dumps(asdict(payload), indent=2, sort_keys=True), encoding="utf-8")
        console.print(f"Exported JSON to {output}")
        return

    if fmt == "csv":
        with output.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["section", "metric", "value"])
            writer.writerow(["totals", "files_processed", snapshot.totals.files_processed])
            writer.writerow(["totals", "total_runtime_seconds", snapshot.totals.total_runtime_seconds])
            writer.writerow(["video", "converted", snapshot.video.converted])
            writer.writerow(["video", "upscaled", snapshot.video.upscaled])
            writer.writerow(["video", "merged", snapshot.video.merged])
            writer.writerow(["audio", "converted", snapshot.audio.converted])
            writer.writerow(["audio", "normalized", snapshot.audio.normalized])
            writer.writerow(["audio", "tagged", snapshot.audio.tagged])
            writer.writerow(["subtitles", "downloaded", snapshot.subtitles.downloaded])
            writer.writerow(["subtitles", "generated", snapshot.subtitles.generated])
            writer.writerow(["subtitles", "translated", snapshot.subtitles.translated])
            writer.writerow(["ebooks", "processed", snapshot.ebooks.processed])
            writer.writerow(["ebooks", "converted", snapshot.ebooks.converted])
            writer.writerow(["ebooks", "metadata_enriched", snapshot.ebooks.metadata_enriched])
            writer.writerow(["ebooks", "covers_added", snapshot.ebooks.covers_added])
            writer.writerow(["ebooks", "deduplicated", snapshot.ebooks.deduplicated])
            writer.writerow(["system", "runs", snapshot.system.runs])
            writer.writerow(["system", "errors", snapshot.system.errors])
            writer.writerow(["system", "total_runtime_seconds", snapshot.system.total_runtime_seconds])
        console.print(f"Exported CSV to {output}")
        return

    raise typer.BadParameter("format must be json or csv")


@app.command("reset")
def reset_stats(confirm: bool = typer.Option(False, "--confirm", help="Confirm full stats reset.")) -> None:
    manager = get_manager()
    try:
        manager.reset(confirm=confirm)
    except ValueError as exc:
        err_console.print(str(exc))
        raise typer.Exit(code=1)

    console.print("Statistics reset completed.")


@app.command("doctor")
def doctor() -> None:
    persistence = StatsPersistence()
    path = persistence.path

    if not path.exists():
        console.print("Statistics file does not exist yet; this is not an error.")
        return

    issues: list[str] = []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            issues.append("Top-level JSON must be an object")
        elif not isinstance(raw.get("version", 1), int):
            issues.append("Field 'version' should be an integer")
    except json.JSONDecodeError as exc:
        issues.append(f"Invalid JSON: {exc}")
    except OSError as exc:
        issues.append(f"I/O error: {exc}")

    if not issues:
        console.print("Statistics doctor: no problems found.")
        return

    err_console.print("Statistics doctor found issues:")
    for issue in issues:
        err_console.print(f"- {issue}")
    raise typer.Exit(code=1)
