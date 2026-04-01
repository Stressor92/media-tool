"""CLI commands for ebook workflows and configuration visibility."""

from __future__ import annotations

import typer

from utils.config import get_config

app = typer.Typer(help="Process and normalize ebook files.")


def _print_ebook_config_summary() -> None:
    config = get_config()
    ebook = config.ebook

    typer.echo("\n[ebook] active configuration")
    typer.echo(f"  preferred_format: {ebook.preferred_format}")
    typer.echo(f"  download_cover: {ebook.download_cover}")
    typer.echo(f"  metadata_providers: {', '.join(ebook.metadata_providers)}")
    typer.echo(f"  organization.structure: {ebook.organization.structure}")
    typer.echo(f"  conversion.target_format: {ebook.conversion.target_format}")


@app.callback(invoke_without_command=True)
def ebook_callback(ctx: typer.Context) -> None:
    """Show the currently active ebook configuration when entering this command group."""
    _print_ebook_config_summary()
    if ctx.invoked_subcommand is None:
        typer.echo("\nUse 'media-tool ebook config' to print this block again.")


@app.command("config")
def show_config() -> None:
    """Print the active ebook-related configuration values."""
    _print_ebook_config_summary()
