"""
src/cli/upscale_cmd.py

CLI interface for the DVD upscale workflow (H.265 720p re-encode).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from cli.progress_display import ConsoleProgressReporter
from rich.console import Console
from rich.table import Table
from rich import box

from core.video import (
    BUILTIN_PROFILES,
    BatchUpscaleSummary,
    UpscaleStatus,
    batch_upscale_directory,
    get_profile,
    resolve_upscale_options,
    upscale_dvd,
)

app = typer.Typer(help="Upscale DVD-quality video to H.265.")
console = Console()
err_console = Console(stderr=True, style="bold red")

# Build profile list for help text once at import time
_PROFILE_NAMES = ", ".join(sorted(BUILTIN_PROFILES))
_PROFILE_HELP = (
    f"Named upscale profile to use. Available: {_PROFILE_NAMES}. "
    "Run with --list-profiles to see full descriptions."
)


@app.command("profiles")
def list_profiles_command() -> None:
    """List all available upscale profiles and their settings."""
    table = Table(
        title="Available Upscale Profiles",
        box=box.ROUNDED,
        show_lines=True,
        expand=True,
    )
    table.add_column("Profile", style="bold cyan", no_wrap=True)
    table.add_column("Height", justify="center")
    table.add_column("CRF", justify="center")
    table.add_column("Enc. Preset", justify="center")
    table.add_column("Deinterlace", justify="center")
    table.add_column("Crop", justify="center")
    table.add_column("Description")

    for name in sorted(BUILTIN_PROFILES):
        p = BUILTIN_PROFILES[name]
        o = p.options
        crop_status = "[red]off[/red]" if o.force_disable_crop else "[green]auto[/green]"
        deint_status = f"[green]{o.deinterlace_mode}[/green]" if o.deinterlace else "[dim]off[/dim]"
        table.add_row(
            name,
            f"{o.target_height}p",
            str(o.crf),
            o.preset,
            deint_status,
            crop_status,
            p.description,
        )

    console.print(table)


def _print_summary(summary: BatchUpscaleSummary) -> None:
    table = Table(title="Upscale Summary", box=box.ROUNDED, show_lines=True, expand=True)
    table.add_column("File", style="cyan", no_wrap=True)
    table.add_column("Status", justify="center")
    table.add_column("Before", justify="right")
    table.add_column("After",  justify="right")
    table.add_column("Δ",      justify="right")
    table.add_column("Time",   justify="right")
    table.add_column("Message")

    for r in summary.results:
        status_map = {
            UpscaleStatus.SUCCESS: "[bold green]✔  OK[/bold green]",
            UpscaleStatus.SKIPPED: "[yellow]⏭  Skipped[/yellow]",
            UpscaleStatus.FAILED:  "[bold red]✘  Failed[/bold red]",
        }
        table.add_row(
            r.source.name,
            status_map[r.status],
            f"{r.size_before_gb:.3f} GB" if r.size_before_gb else "-",
            f"{r.size_after_gb:.3f} GB"  if r.size_after_gb  else "-",
            f"{r.size_delta_gb:+.3f} GB" if r.succeeded       else "-",
            f"{r.duration_seconds:.0f}s"  if r.duration_seconds else "-",
            r.message,
        )

    console.print(table)
    console.print(
        f"\n[bold]Total:[/bold] {summary.total}  "
        f"[green]OK: {len(summary.succeeded)}[/green]  "
        f"[yellow]Skipped: {len(summary.skipped)}[/yellow]  "
        f"[red]Failed: {len(summary.failed)}[/red]"
    )


@app.command("batch")
def batch_command(
    directory: Path = typer.Argument(
        ..., exists=True, file_okay=False, dir_okay=True, readable=True,
        help="Directory to scan for .mkv files.",
    ),
    profile: str = typer.Option(
        "dvd", "--profile", "-p",
        help=_PROFILE_HELP,
    ),
    crf: Optional[int] = typer.Option(
        None, "--crf",
        help="Override CRF quality value (lower = better, 14–28). Overrides profile.",
    ),
    preset: Optional[str] = typer.Option(
        None, "--preset",
        help="Override ffmpeg encoding preset (ultrafast…veryslow). Overrides profile.",
    ),
    overwrite: bool = typer.Option(False, "--overwrite", help="Re-encode even if output already exists."),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Also scan subdirectories."),
    target_height: Optional[int] = typer.Option(
        None, "--height",
        help="Override target output height in pixels. Overrides profile.",
    ),
    deinterlace: Optional[bool] = typer.Option(
        None, "--deinterlace/--no-deinterlace",
        help="Enable deinterlacing (yadif). Recommended for PAL TV recordings. Overrides profile.",
    ),
    deinterlace_mode: Optional[str] = typer.Option(
        None, "--deinterlace-mode",
        help='Deinterlace filter to use: \"yadif\" (fast) or \"bwdif\" (higher quality). Default: yadif.',
    ),
) -> None:
    """
    Batch-upscale all DVD-quality MKV files in DIRECTORY to H.265.

    Uses the named profile as the base configuration; any explicit option
    (--crf, --preset, --height) overrides the corresponding profile value.

    Files already at or above the target height are automatically skipped.
    Anime files are detected automatically (cropdetect disabled for them).
    Use the 'anime' profile to force-disable cropdetect for all files.
    """
    # Validate profile name early for a clean error message
    try:
        get_profile(profile)
    except ValueError as exc:
        err_console.print(str(exc))
        raise typer.Exit(code=1)

    console.rule("[bold cyan]media-tool · upscale batch[/bold cyan]")
    console.print(f"[dim]Directory:[/dim] {directory}")
    console.print(f"[dim]Profile  :[/dim] {profile}")

    opts = resolve_upscale_options(
        profile_name=profile,
        crf=crf,
        encoder_preset=preset,
        target_height=target_height,
        overwrite=overwrite,
        deinterlace=deinterlace,
        deinterlace_mode=deinterlace_mode,
    )
    deinterlace_info = f" · {opts.deinterlace_mode}" if opts.deinterlace else ""
    console.print(
        f"[dim]Settings :[/dim] "
        f"{opts.target_height}p \u00b7 CRF {opts.crf} \u00b7 preset {opts.preset} \u00b7 "
        f"codec {opts.codec}{deinterlace_info}"
    )
    reporter = ConsoleProgressReporter(console)

    try:
        summary = batch_upscale_directory(
            directory,
            opts=opts,
            recursive=recursive,
            progress_callback=reporter,
        )
    except NotADirectoryError as exc:
        err_console.print(str(exc))
        raise typer.Exit(code=1)

    if summary.total == 0:
        console.print("[yellow]No .mkv files found.[/yellow]")
        raise typer.Exit(code=0)

    _print_summary(summary)

    if summary.failed:
        raise typer.Exit(code=1)


@app.command("single")
def single_command(
    source: Path = typer.Argument(
        ..., exists=True, file_okay=True, dir_okay=False, readable=True,
        help="Path to the source .mkv file.",
    ),
    profile: str = typer.Option("dvd", "--profile", "-p", help=_PROFILE_HELP),
    crf: Optional[int] = typer.Option(None, "--crf"),
    preset: Optional[str] = typer.Option(None, "--preset"),
    overwrite: bool = typer.Option(False, "--overwrite"),
    target_height: Optional[int] = typer.Option(None, "--height"),
    deinterlace: Optional[bool] = typer.Option(
        None, "--deinterlace/--no-deinterlace",
        help="Enable deinterlacing (yadif). Recommended for PAL TV recordings. Overrides profile.",
    ),
    deinterlace_mode: Optional[str] = typer.Option(
        None, "--deinterlace-mode",
        help='Deinterlace filter: \"yadif\" (fast) or \"bwdif\" (higher quality). Default: yadif.',
    ),
) -> None:
    """Upscale a single MKV file to H.265 using the chosen profile."""
    try:
        get_profile(profile)
    except ValueError as exc:
        err_console.print(str(exc))
        raise typer.Exit(code=1)

    console.rule("[bold cyan]media-tool · upscale single[/bold cyan]")
    console.print(f"[dim]Source :[/dim] {source}")
    console.print(f"[dim]Profile:[/dim] {profile}")

    opts = resolve_upscale_options(
        profile_name=profile,
        crf=crf,
        encoder_preset=preset,
        target_height=target_height,
        overwrite=overwrite,        deinterlace=deinterlace,
        deinterlace_mode=deinterlace_mode,    )
    console.print(
        f"[dim]Settings:[/dim] "
        f"{opts.target_height}p · CRF {opts.crf} · preset {opts.preset} · "
        f"codec {opts.codec}"
    )

    result = upscale_dvd(source, opts=opts)

    if result.succeeded:
        console.print(f"\n[bold green]✔  {result.message}[/bold green]")
        console.print(
            f"[dim]  Size:[/dim] {result.size_before_gb:.3f} GB → "
            f"{result.size_after_gb:.3f} GB  "
            f"([green]{result.size_delta_gb:+.3f} GB[/green])"
        )
        console.print(f"[dim]  Time:[/dim] {result.duration_seconds:.0f}s")
    elif result.skipped:
        console.print(f"\n[yellow]⏭  {result.message}[/yellow]")
    else:
        err_console.print(f"\n✘  {result.message}")
        if result.ffmpeg_result:
            stderr_tail = "\n".join(result.ffmpeg_result.stderr.splitlines()[-20:])
            console.print(f"\n[dim]ffmpeg stderr (tail):[/dim]\n{stderr_tail}", highlight=False)
        raise typer.Exit(code=1)
