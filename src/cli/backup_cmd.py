from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from src.backup import get_backup_manager
from src.backup.models import BackupStatus

app = typer.Typer(help="Backup and rollback utilities.")
console = Console()


def _format_bytes(size: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    idx = 0
    while value >= 1024.0 and idx < len(units) - 1:
        value /= 1024.0
        idx += 1
    return f"{value:.1f} {units[idx]}"


@app.command("list")
def list_backups(status: str = typer.Option("all", "--status")) -> None:
    manager = get_backup_manager()
    snapshot = manager.index.load()

    requested = status.lower().strip()
    table = Table(title="Backup Overview")
    table.add_column("ID")
    table.add_column("Type")
    table.add_column("Operation")
    table.add_column("Date")
    table.add_column("Size")
    table.add_column("Status")

    count = 0
    for entry in snapshot.entries:
        if requested != "all" and entry.status.value != requested:
            continue
        table.add_row(
            entry.id[:8],
            entry.media_type.value,
            entry.operation,
            entry.timestamp[:19].replace("T", " "),
            _format_bytes(entry.backup_size_bytes),
            entry.status.value,
        )
        count += 1

    console.print(table)
    console.print(
        f"Total: {count} entries · {_format_bytes(snapshot.total_size_bytes)} used · index: {manager.index.path}"
    )


@app.command("status")
def status_command() -> None:
    manager = get_backup_manager()
    usage = manager._storage_guard.current_usage()  # noqa: SLF001
    max_bytes = manager._max_size_bytes  # noqa: SLF001
    percent = (usage.total_size_bytes / max_bytes * 100.0) if max_bytes > 0 else 0.0

    console.print("Backup Storage")
    console.print("-" * 40)
    console.print(f"Used space: {_format_bytes(usage.total_size_bytes)} / {_format_bytes(max_bytes)} ({percent:.1f}%)")
    for key in sorted(usage.by_status):
        console.print(f"{key}: {usage.by_status[key]} entries")


@app.command("rollback")
def rollback_command(
    backup_id: str = typer.Argument(...),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    manager = get_backup_manager()
    entry = manager.index.get_entry(backup_id)
    if entry is None:
        raise typer.BadParameter(f"Backup id not found: {backup_id}")

    console.print(f"Rollback {entry.id}")
    console.print(f"  Original: {entry.original_path}")
    console.print(f"  Backup:   {entry.backup_path}")
    if dry_run:
        console.print("Dry-run: no file changes made")
        return

    manager.rollback(entry)
    console.print("Rollback completed")


@app.command("purge")
def purge_command(
    status: str = typer.Option("expired", "--status"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    manager = get_backup_manager()

    if dry_run:
        snapshot = manager.index.load()
        if status == "all":
            count = len(snapshot.entries)
        else:
            count = sum(1 for entry in snapshot.entries if entry.status.value == status)
        console.print(f"Dry-run: would purge {count} entries")
        return

    if status == "all":
        deleted = manager.purge(None)
    else:
        deleted = manager.purge(BackupStatus(status))

    console.print(f"Purged {deleted} backups")


@app.command("validate")
def validate_command(backup_id: str = typer.Argument(...)) -> None:
    manager = get_backup_manager()
    entry = manager.index.get_entry(backup_id)
    if entry is None:
        raise typer.BadParameter(f"Backup id not found: {backup_id}")
    if entry.output_path is None:
        raise typer.BadParameter("Backup entry has no output_path recorded; cannot validate")

    result = manager.validate(entry, Path(entry.output_path))
    console.print(f"Validation: {'passed' if result.passed else 'failed'}")
    for check in result.checks:
        marker = "OK" if check.passed else "FAIL"
        console.print(f"- {marker} {check.name}: expected={check.expected}, actual={check.actual}")
