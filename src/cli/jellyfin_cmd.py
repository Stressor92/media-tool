# src/cli/jellyfin_cmd.py
"""
CLI commands for managing and syncing the Jellyfin media library.
"""
from __future__ import annotations

import csv
import time
from typing import TYPE_CHECKING, Annotated, Optional

import typer

if TYPE_CHECKING:
    from core.jellyfin.library_manager import LibraryManager
    from core.jellyfin.models import ItemType, MetadataIssue

app = typer.Typer(help="Manage and sync the Jellyfin media library.")


def _get_manager() -> "LibraryManager":
    """Creates a LibraryManager from configuration."""
    from utils.config import get_config
    from core.jellyfin.client import JellyfinClient
    from core.jellyfin.library_manager import LibraryManager

    jf = get_config().jellyfin
    if not jf.api_key:
        typer.echo(
            "No Jellyfin API key configured. Please add [jellyfin] to media-tool.toml.",
            err=True,
        )
        raise typer.Exit(1)
    client = JellyfinClient(jf.base_url, jf.api_key)
    return LibraryManager(client)


# ── media-tool jellyfin ping ────────────────────────────────────────────


@app.command("ping")
def ping() -> None:
    """Check whether Jellyfin is reachable and the API key is valid."""
    manager = _get_manager()
    if manager.ping():
        info = manager.get_server_info()
        typer.echo(f"Jellyfin {info.get('Version', '?')} reachable.")
        typer.echo(f"  Server: {info.get('ServerName', '?')}")
    else:
        typer.echo("Jellyfin not reachable.", err=True)
        raise typer.Exit(1)


# ── media-tool jellyfin refresh ─────────────────────────────────────────


@app.command("refresh")
def refresh(
    library: Annotated[
        Optional[str],
        typer.Option("--library", "-l", help="Library name or ID"),
    ] = None,
    item_id: Annotated[
        Optional[str],
        typer.Option("--item", help="Refresh a single item by ID"),
    ] = None,
    wait: Annotated[
        bool, typer.Option("--wait", help="Block until the scan finishes")
    ] = False,
    timeout: Annotated[int, typer.Option(help="Timeout in seconds")] = 300,
) -> None:
    """
    Trigger a library refresh.

    Examples:

      media-tool jellyfin refresh

      media-tool jellyfin refresh --library Movies

      media-tool jellyfin refresh --item abc123

      media-tool jellyfin refresh --wait
    """
    manager = _get_manager()

    if item_id:
        result = manager.refresh_item(item_id)
        prefix = "Item"
    elif library:
        libs = {lib.name: lib for lib in manager.get_libraries()}
        if library not in libs:
            typer.echo(
                f"Library '{library}' not found. Available: {list(libs)}", err=True
            )
            raise typer.Exit(1)
        result = manager.refresh_library(libs[library].id)
        prefix = f"Library '{library}'"
    else:
        result = manager.refresh_all()
        prefix = "Full library"

    if result.triggered:
        typer.echo(f"{prefix} — refresh triggered.")
        if wait:
            typer.echo("Waiting for scan to complete …")
            status = manager.wait_for_scan(timeout)
            typer.echo(f"  Scan: {status.state.name}")
    else:
        typer.echo(f"Refresh failed: {result.error}", err=True)
        raise typer.Exit(1)


# ── media-tool jellyfin scan-status ─────────────────────────────────────


@app.command("scan-status")
def scan_status(
    watch: Annotated[
        bool,
        typer.Option("--watch", "-w", help="Live updates"),
    ] = False,
    interval: Annotated[int, typer.Option(help="Poll interval in seconds")] = 5,
) -> None:
    """
    Show the current scan status.

    Examples:

      media-tool jellyfin scan-status

      media-tool jellyfin scan-status --watch
    """
    from core.jellyfin.models import ScanState

    manager = _get_manager()

    def _show() -> bool:
        status = manager.get_scan_status()
        icons = {
            ScanState.RUNNING: "[RUNNING]",
            ScanState.IDLE: "[IDLE]",
            ScanState.COMPLETED: "[COMPLETED]",
            ScanState.FAILED: "[FAILED]",
        }
        icon = icons.get(status.state, "?")
        prog = f" {status.progress:.1f}%" if status.progress is not None else ""
        typer.echo(f"{icon}{prog}  [{status.task_name or 'Scan'}]")
        return status.state == ScanState.RUNNING

    if watch:
        while _show():
            time.sleep(interval)
    else:
        _show()


# ── media-tool jellyfin libraries ─────────────────────────────────────


@app.command("libraries")
def libraries() -> None:
    """List all configured libraries."""
    manager = _get_manager()
    libs = manager.get_libraries()
    if not libs:
        typer.echo("No libraries found.")
        return
    typer.echo(f"\n{'Name':<20} {'Type':<12} {'Items':>6}  Paths")
    typer.echo("-" * 70)
    for lib in libs:
        paths = ", ".join(lib.locations[:2])
        typer.echo(f"{lib.name:<20} {lib.item_type:<12} {lib.item_count:>6}  {paths}")


# ── media-tool jellyfin inspect ─────────────────────────────────────────


@app.command("inspect")
def inspect(
    library: Annotated[Optional[str], typer.Option("-l", help="Library name")] = None,
    kind: Annotated[
        str, typer.Option(help="What to check: movies | series | all")
    ] = "all",
    auto_fix: Annotated[
        bool,
        typer.Option("--fix", help="Automatically repair fixable issues"),
    ] = False,
    export: Annotated[
        Optional[str], typer.Option("--export", help="Save results as CSV")
    ] = None,
) -> None:
    """
    Analyse the library for metadata problems.

    Examples:

      media-tool jellyfin inspect

      media-tool jellyfin inspect --fix

      media-tool jellyfin inspect -l Movies --export issues.csv
    """
    from collections import defaultdict
    from core.jellyfin.metadata_inspector import MetadataInspector
    from core.jellyfin.metadata_fixer import MetadataFixer
    from core.jellyfin.client import JellyfinClient
    from utils.config import get_config

    manager = _get_manager()
    inspector = MetadataInspector(manager)

    lib_id: Optional[str] = None
    if library:
        libs = {lib.name: lib for lib in manager.get_libraries()}
        if library in libs:
            lib_id = libs[library].id

    typer.echo("Analysing library …")
    if kind == "movies":
        issues = inspector.inspect_movies(lib_id)
    elif kind == "series":
        issues = inspector.inspect_series(lib_id)
    else:
        issues = inspector.inspect_all(lib_id)

    if not issues:
        typer.echo("No metadata problems found.")
        return

    by_kind: dict[str, list[MetadataIssue]] = defaultdict(list)
    for issue in issues:
        by_kind[issue.kind.value].append(issue)

    total_auto = sum(1 for i in issues if i.auto_fixable)
    typer.echo(f"\n{len(issues)} problems found ({total_auto} automatically fixable)\n")

    for kind_name, kind_issues in sorted(by_kind.items()):
        typer.echo(f"  [{kind_name}] ({len(kind_issues)}x)")
        for issue in kind_issues[:5]:
            fix_icon = "[auto]" if issue.auto_fixable else "[manual]"
            typer.echo(f"    {fix_icon} {issue.description}")
        if len(kind_issues) > 5:
            typer.echo(f"    … and {len(kind_issues) - 5} more.")

    if export:
        _export_issues_csv(issues, export)
        typer.echo(f"\nExported to: {export}")

    if auto_fix:
        jf = get_config().jellyfin
        client = JellyfinClient(jf.base_url, jf.api_key or "")
        fixer = MetadataFixer(manager, client)
        typer.echo(f"\nFixing {total_auto} issues automatically …")
        results = fixer.fix_all_auto(issues)
        ok = sum(1 for r in results if r.success)
        err = sum(1 for r in results if not r.success)
        typer.echo(f"  {ok} fixed · {err} failed")


# ── media-tool jellyfin fix-series ──────────────────────────────────────


@app.command("fix-series")
def fix_series(
    episode_id: Annotated[
        str, typer.Argument(help="Jellyfin item ID of the episode")
    ],
    series_id: Annotated[
        str, typer.Argument(help="Jellyfin item ID of the correct series")
    ],
) -> None:
    """
    Reassign a mismatched episode to the correct series.

    Find Jellyfin item IDs with:

      media-tool jellyfin search "Series Name"
    """
    from core.jellyfin.metadata_fixer import MetadataFixer
    from core.jellyfin.client import JellyfinClient
    from utils.config import get_config

    manager = _get_manager()
    jf = get_config().jellyfin
    client = JellyfinClient(jf.base_url, jf.api_key or "")
    fixer = MetadataFixer(manager, client)

    result = fixer.reassign_series(episode_id, series_id)
    if result.success:
        typer.echo(result.applied_fix)
    else:
        typer.echo(result.error, err=True)
        raise typer.Exit(1)


# ── media-tool jellyfin search ──────────────────────────────────────────


@app.command("search")
def search(
    query: Annotated[str, typer.Argument(help="Search term")],
    item_type: Annotated[
        str, typer.Option("--type", help="movie | series | episode | all")
    ] = "all",
    limit: Annotated[int, typer.Option()] = 10,
) -> None:
    """
    Search items in the Jellyfin library.
    Outputs name, ID, and path — useful for fix-series.
    """
    from core.jellyfin.models import ItemType

    manager = _get_manager()
    types: list[ItemType] | None = None
    if item_type != "all":
        mapping = {
            "movie": ItemType.MOVIE,
            "series": ItemType.SERIES,
            "episode": ItemType.EPISODE,
        }
        if item_type in mapping:
            types = [mapping[item_type]]

    items = manager.search_items(query, types, limit)
    if not items:
        typer.echo("No results found.")
        return

    typer.echo(f"\n{'Name':<35} {'Type':<10} {'Year':>5}  ID")
    typer.echo("-" * 75)
    for item in items:
        year = str(item.year) if item.year else "-"
        typer.echo(
            f"{item.name:<35} {item.item_type.value:<10} {year:>5}  {item.id}"
        )


# ── Helpers ──────────────────────────────────────────────────────────────


def _export_issues_csv(issues: list[MetadataIssue], path: str) -> None:
    fieldnames = [
        "item_id",
        "item_name",
        "type",
        "issue",
        "description",
        "auto_fixable",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for issue in issues:
            writer.writerow(
                {
                    "item_id": issue.item.id,
                    "item_name": issue.item.name,
                    "type": issue.item.item_type.value,
                    "issue": issue.kind.value,
                    "description": issue.description,
                    "auto_fixable": issue.auto_fixable,
                }
            )
