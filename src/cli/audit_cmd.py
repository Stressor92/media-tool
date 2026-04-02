# src/cli/audit_cmd.py
from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(help="Medien-Bibliothek auf Probleme prüfen.")


@app.command("run")
def run_audit(
    directory: Annotated[Path, typer.Argument(help="Zu prüfendes Verzeichnis")],
    checks: Annotated[
        str | None,
        typer.Option(
            "--checks",
            help="Kommagetrennte Check-IDs (z. B. A01,B01) oder 'all'",
        ),
    ] = "all",
    severity: Annotated[
        str,
        typer.Option(
            "--min-severity",
            help="Mindest-Schwere: critical | high | medium | low | info",
        ),
    ] = "low",
    details: Annotated[
        bool,
        typer.Option("--details", "-d", help="Detaillierte Ausgabe"),
    ] = False,
    export_csv: Annotated[Path | None, typer.Option("--csv", help="CSV-Report ausgeben")] = None,
    export_json: Annotated[Path | None, typer.Option("--json", help="JSON-Report ausgeben")] = None,
    workers: Annotated[int, typer.Option("--workers", help="ffprobe-Threads")] = 8,
    no_cache: Annotated[bool, typer.Option("--no-cache", help="ffprobe-Cache deaktivieren")] = False,
) -> None:
    """
    Führt einen vollständigen Bibliotheks-Audit durch.

    \b
    Beispiele:
      media-tool audit "Y:\\\\Media"
      media-tool audit "Y:\\\\Media" --details
      media-tool audit "Y:\\\\Media" --checks A01,A04,B01 --min-severity high
      media-tool audit "Y:\\\\Media" --csv report.csv --json report.json
    """
    from core.audit.auditor import LibraryAuditor
    from core.audit.check_registry import CheckRegistry
    from core.audit.models import CheckSeverity
    from core.audit.reporter import AuditReporter
    from utils.ffprobe_cache import FfprobeCache

    if not directory.is_dir():
        typer.echo(f"❌ Kein gültiger Ordner: {directory}", err=True)
        raise typer.Exit(1)

    check_ids = checks.split(",") if (checks is not None and checks != "all") else None
    selected_checks = CheckRegistry.get_checks(
        ids=check_ids,
        root_dir=directory,
    )

    try:
        min_sev = CheckSeverity[severity.upper()]
    except KeyError:
        typer.echo(f"❌ Unbekannte Severity: {severity}", err=True)
        raise typer.Exit(1)

    cache = FfprobeCache(
        cache_dir=None if no_cache else None,
        max_workers=workers,
    )
    auditor = LibraryAuditor(checks=selected_checks, ffprobe_cache=cache)

    typer.echo(f"🔍  Analysiere '{directory}' mit {len(selected_checks)} Checks …")
    report = auditor.audit(directory)

    # Severity-Filter nachträglich anwenden
    for cr in report.check_results:
        cr.findings = [f for f in cr.findings if f.severity.value <= min_sev.value]

    reporter = AuditReporter()
    if details:
        typer.echo(reporter.render_details(report))
    else:
        typer.echo(reporter.render_summary(report))

    if export_csv:
        reporter.export_csv(report, export_csv)
        typer.echo(f"\n📄  CSV: {export_csv}")
    if export_json:
        reporter.export_json(report, export_json)
        typer.echo(f"📄  JSON: {export_json}")

    if report.critical_count > 0 or report.high_count > 0:
        raise typer.Exit(1)


@app.command("checks")
def list_checks() -> None:
    """Zeigt alle verfügbaren Checks mit ID und Beschreibung."""
    from core.audit.check_registry import CheckRegistry

    typer.echo(f"\n{'ID':<6} {'Name':<45} Schwere")
    typer.echo("─" * 65)
    for check in CheckRegistry.all_checks():
        typer.echo(f"  {check.check_id:<6} {check.check_name:<45}")
