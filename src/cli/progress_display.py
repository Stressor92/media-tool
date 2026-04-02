"""Shared console progress rendering for batch CLI commands."""

from __future__ import annotations

from rich.console import Console

from utils.progress import ProgressEvent


class ConsoleProgressReporter:
    """Render durable per-item progress lines for long-running batch work."""

    def __init__(self, console: Console) -> None:
        self.console = console

    def __call__(self, event: ProgressEvent) -> None:
        if event.status == "info":
            self.console.print(f"[bold blue]{event.stage}[/bold blue] {event.message}")
            return

        total = event.total if event.total > 0 else "?"
        left = max(event.total - event.current, 0) if event.total > 0 else "?"
        prefix = f"[{event.current}/{total} | {left} left]"

        if event.status == "start":
            message = event.message or event.item_name
            self.console.print(f"[cyan]{prefix}[/cyan] Starting {event.stage}: {message}")
            return

        icon_map = {
            "success": "[bold green]OK[/bold green]",
            "skipped": "[yellow]SKIP[/yellow]",
            "failed": "[bold red]FAIL[/bold red]",
        }
        status = icon_map.get(event.status, event.status.upper())
        suffix = f" - {event.message}" if event.message else ""
        self.console.print(f"{status} [cyan]{prefix}[/cyan] {event.item_name}{suffix}")
