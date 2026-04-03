"""
src/cli/video_cmd.py

CLI interface for video processing.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich import box
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

from core.video import (
    TrailerDownloadResult,
    TrailerDownloadService,
    TrailerSearchService,
    convert_mp4_to_mkv,
    merge_directory,
    scan_directory,
    upscale_dvd,
)
from core.video.movie_folder_scanner import MovieFolderScanner
from utils.config import get_config
from utils.ffprobe_runner import ProbeResult
from utils.ytdlp_runner import YtDlpNotFoundError, YtDlpRunner

app = typer.Typer(help="Process video files.")
console = Console()
err_console = Console(stderr=True, style="bold red")


@app.command("convert")
def convert_command(
    input_file: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Input video file to convert.",
    ),
    output_file: Path = typer.Argument(
        ...,
        file_okay=True,
        dir_okay=False,
        help="Output video file path.",
    ),
    language: str | None = typer.Option(
        None,
        "--language",
        "-l",
        help="Set language metadata for audio/subtitle tracks (e.g., 'de', 'en').",
    ),
    audio_title: str | None = typer.Option(
        None,
        "--audio-title",
        "-a",
        help="Set title for audio tracks.",
    ),
    subtitle_title: str | None = typer.Option(
        None,
        "--subtitle-title",
        "-s",
        help="Set title for subtitle tracks.",
    ),
    default_audio: int | None = typer.Option(
        None,
        "--default-audio",
        "-d",
        help="Set default audio track (1-based index).",
    ),
    remove_tracks: str | None = typer.Option(
        None,
        "--remove-tracks",
        "-r",
        help="Remove specific tracks (e.g., 'a:2,s:1' for audio track 2 and subtitle track 1).",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        "-y",
        help="Overwrite output file if it exists.",
    ),
) -> None:
    """
    Convert video files (MP4 → MKV, etc.).

    Lossless container conversion using ffmpeg. Preserves all streams (audio, subtitles, metadata).
    """
    console.rule("[bold cyan]media-tool · video convert[/bold cyan]")
    console.print(f"[dim]Input :[/dim] {input_file}")
    console.print(f"[dim]Output:[/dim] {output_file}")

    if language:
        console.print(f"[dim]Language:[/dim] {language}")
    if audio_title:
        console.print(f"[dim]Audio title:[/dim] {audio_title}")
    if subtitle_title:
        console.print(f"[dim]Subtitle title:[/dim] {subtitle_title}")
    if default_audio:
        console.print(f"[dim]Default audio track:[/dim] {default_audio}")
    if remove_tracks:
        console.print(f"[dim]Remove tracks:[/dim] {remove_tracks}")

    try:
        result = convert_mp4_to_mkv(
            source=input_file,
            target=output_file,
            audio_language=language or "deu",
            audio_title=audio_title or "Deutsch",
            overwrite=overwrite,
        )
    except Exception as e:
        err_console.print(f"Error: {e}")
        raise typer.Exit(code=1)

    if result.status.name == "SUCCESS":
        console.print(f"\n[green]✓[/green] Successfully converted to {output_file}")
    elif result.status.name == "SKIPPED":
        console.print(f"\n[yellow]⏭️[/yellow] Skipped: {result.message}")
    else:
        err_console.print(f"\n[red]✘  Conversion failed:[/red] {result.message}")
        if result.ffmpeg_result and result.ffmpeg_result.stderr:
            stderr_tail = "\n".join(result.ffmpeg_result.stderr.splitlines()[-20:])
            console.print(f"\n[dim]ffmpeg stderr (tail):[/dim]\n{stderr_tail}", highlight=False)
        raise typer.Exit(code=1)


@app.command("inspect")
def inspect_command(
    directory: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help="Directory to scan for video files.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output CSV file path. Defaults to <directory>/video_list.csv",
    ),
    recursive: bool = typer.Option(
        True,
        "--recursive/--no-recursive",
        "-r",
        help="Scan subdirectories (default: on).",
    ),
    preview: bool = typer.Option(
        False,
        "--preview",
        "-p",
        help="Print a Rich table preview of the first 20 results in the terminal.",
    ),
) -> None:
    """
    Scan media library and export metadata to CSV.
    """
    progress_state = {"last_reported": 0}

    def report_progress(current: int, total: int, current_file: Path) -> None:
        should_report = current == 1 or current == total or current - progress_state["last_reported"] >= 25
        if not should_report:
            return

        progress_state["last_reported"] = current
        console.print(f"[dim]Progress:[/dim] {current}/{total} · {current_file.name}")

    console.rule("[bold cyan]media-tool · video inspect[/bold cyan]")
    console.print(f"[dim]Directory:[/dim] {directory}")
    console.print(f"[dim]Recursive:[/dim] {recursive}")
    console.print("[dim]Scanning library and probing video files...[/dim]")

    try:
        videos = scan_directory(
            directory=directory,
            recursive=recursive,
            progress_callback=report_progress,
        )
    except Exception as e:
        err_console.print(f"Error: {e}")
        raise typer.Exit(code=1)

    if not videos:
        console.print("[yellow]No video files found.[/yellow]")
        return

    console.print(f"\n[green]✓[/green] Found {len(videos)} video files")

    # Count by type
    movies = sum(1 for v in videos if not any(x in v.file_name.lower() for x in ["s01", "s02", "season"]))
    tv_shows = len(videos) - movies
    other = 0  # Could be refined

    console.print(f"[dim]Movies:[/dim] {movies}")
    console.print(f"[dim]TV Shows:[/dim] {tv_shows}")
    console.print(f"[dim]Other:[/dim] {other}")

    # Always export CSV. If --output is omitted, use <directory>/video_list.csv.
    csv_output = output or (directory / "video_list.csv")
    try:
        from core.video import export_to_csv

        export_to_csv(videos, csv_output)
        console.print(f"[dim]Exported to:[/dim] {csv_output}")
    except Exception as e:
        err_console.print(f"Error exporting CSV: {e}")
        raise typer.Exit(code=1)

    # Preview if requested
    if preview:
        from rich.table import Table

        table = Table(title="Video Library Preview", box=box.ROUNDED)
        table.add_column("File", style="dim", no_wrap=True, max_width=30)
        table.add_column("Size (GB)", justify="right")
        table.add_column("Duration", justify="center")
        table.add_column("Resolution", justify="center")
        table.add_column("Codec", justify="center")

        for video in videos[:20]:  # Show first 20
            table.add_row(
                video.file_name,
                f"{video.size_gb:.2f}",
                video.duration,
                video.resolution,
                video.video_codec,
            )

        console.print(table)
        if len(videos) > 20:
            console.print(f"[dim]… and {len(videos) - 20} more files.[/dim]")


@app.command("merge")
def merge_command(
    input_dir: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help="Directory containing video files to merge.",
    ),
    output_file: Path = typer.Argument(
        ...,
        file_okay=True,
        dir_okay=False,
        help="Output merged video file path.",
    ),
    pattern: str | None = typer.Option(
        None,
        "--pattern",
        "-p",
        help="File pattern to match (default: auto-detect German/English pairs).",
    ),
    language: str | None = typer.Option(
        None,
        "--language",
        "-l",
        help="Set language metadata for merged tracks.",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        "-y",
        help="Overwrite output file if it exists.",
    ),
) -> None:
    """
    Merge multiple video files into a single MKV.

    Example: Combine German + English MP4 files into dual-audio MKV.
    """
    console.rule("[bold cyan]media-tool · video merge[/bold cyan]")
    console.print(f"[dim]Input dir:[/dim] {input_dir}")
    console.print(f"[dim]Output:[/dim] {output_file}")

    if pattern:
        console.print(f"[dim]Pattern:[/dim] {pattern}")
    if language:
        console.print(f"[dim]Language:[/dim] {language}")

    try:
        result = merge_directory(
            directory=input_dir,
            overwrite=overwrite,
        )
    except Exception as e:
        err_console.print(f"Error: {e}")
        raise typer.Exit(code=1)

    if result.status.name == "SUCCESS":
        console.print(f"\n[green]✓[/green] Successfully merged to {result.target}")
        if result.german_source is not None:
            console.print(f"[dim]German source:[/dim] {result.german_source.name}")
        if result.english_source is not None:
            console.print(f"[dim]English source:[/dim] {result.english_source.name}")
    else:
        err_console.print(f"\n[red]✘  Merge failed:[/red] {result.message}")
        if result.ffmpeg_result and result.ffmpeg_result.stderr:
            stderr_tail = "\n".join(result.ffmpeg_result.stderr.splitlines()[-20:])
            console.print(f"\n[dim]ffmpeg stderr (tail):[/dim]\n{stderr_tail}", highlight=False)
        raise typer.Exit(code=1)


@app.command("subtitle")
def subtitle_command(
    input_path: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=True,
        readable=True,
        help="Input video file or directory of MKV files to generate subtitles for.",
    ),
    language: str = typer.Option(
        "en",
        "--language",
        "-l",
        help="Language code for transcription (e.g., 'en', 'de').",
    ),
    model: str = typer.Option(
        "large-v3",
        "--model",
        "-m",
        help="Whisper model to use (tiny, base, small, medium, large-v3).",
    ),
    output_file: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output MKV file path (single-file mode only; default: input with _subtitled suffix).",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        "-y",
        help="Overwrite output file if it exists.",
    ),
    recursive: bool = typer.Option(
        False,
        "--recursive",
        "-r",
        help="Process subdirectories recursively (directory mode only).",
    ),
    skip_hallucination_check: bool = typer.Option(
        False,
        "--skip-hallucination-check",
        help="Skip hallucination detection (not recommended).",
    ),
) -> None:
    """
    Generate subtitles for a video file or all MKV files in a directory.

    Extracts audio, transcribes with Whisper, and muxes subtitles into MKV.
    Supports hallucination detection and multiple Whisper backends.

    Examples:
        media-tool video subtitle movie.mkv
        media-tool video subtitle "Season 01/"
        media-tool video subtitle "Series/" --recursive
    """
    if input_path.is_dir():
        _subtitle_batch(
            directory=input_path,
            language=language,
            model=model,
            overwrite=overwrite,
            recursive=recursive,
            skip_hallucination_check=skip_hallucination_check,
        )
    else:
        _subtitle_single(
            input_file=input_path,
            language=language,
            model=model,
            output_file=output_file,
            overwrite=overwrite,
            skip_hallucination_check=skip_hallucination_check,
        )


def _subtitle_single(
    input_file: Path,
    language: str,
    model: str,
    output_file: Path | None,
    overwrite: bool,
    skip_hallucination_check: bool,
) -> bool:
    """Generate subtitles for a single file.  Returns True on success."""
    console.rule("[bold cyan]media-tool · video subtitle[/bold cyan]")
    console.print(f"[dim]Input file:[/dim] {input_file}")
    console.print(f"[dim]Language:[/dim] {language}")
    console.print(f"[dim]Model:[/dim] {model}")

    if output_file:
        console.print(f"[dim]Output:[/dim] {output_file}")
    else:
        output_file = input_file.with_stem(f"{input_file.stem}_subtitled").with_suffix(".mkv")
        console.print(f"[dim]Output (auto):[/dim] {output_file}")

    try:
        from core.video import SubtitleGenerator, WhisperConfig, WhisperModel

        config = WhisperConfig(model=WhisperModel(model), language=language)
        generator = SubtitleGenerator(config=config)

        def _progress(message: str, fraction: float) -> None:
            pct = int(fraction * 100)
            console.print(f"  [dim][{pct:3d}%][/dim] {message}")

        result = generator.generate_subtitles(
            video_path=input_file,
            output_mkv_path=output_file,
            overwrite=overwrite,
            detect_hallucinations=not skip_hallucination_check,
            progress_callback=_progress,
        )

        if result.success:
            console.print(f"\n[green]✓[/green] Subtitles generated and muxed to {output_file}")
            console.print(f"[dim]Processing time:[/dim] {result.processing_time:.1f}s")
            if result.audio_duration:
                console.print(f"[dim]Audio duration:[/dim] {result.audio_duration:.1f}s")
            if result.hallucination_warnings:
                console.print("\n[yellow]⚠️  Hallucination warnings:[/yellow]")
                for warning in result.hallucination_warnings:
                    console.print(f"  - {warning}")
            return True
        else:
            err_console.print(f"\n[red]✘  Subtitle generation failed:[/red] {result.error_message}")
            if result.steps_completed:
                completed = [s for s in result.steps_completed if not s.startswith("backup")]
                console.print(f"[dim]Completed steps:[/dim] {' → '.join(completed)}")
            if result.hallucination_warnings:
                console.print("\n[yellow]Warnings:[/yellow]")
                for warning in result.hallucination_warnings:
                    console.print(f"  - {warning}")
            console.print("[dim]Tip: run with --debug and --log-file=subtitle.log for full details[/dim]")
            return False

    except Exception as e:
        err_console.print(f"Error: {e}")
        return False


def _subtitle_batch(
    directory: Path,
    language: str,
    model: str,
    overwrite: bool,
    recursive: bool,
    skip_hallucination_check: bool,
) -> None:
    """Process all MKV files in a directory."""
    pattern = "**/*.mkv" if recursive else "*.mkv"
    files = sorted(directory.glob(pattern))

    # Skip already-subtitled output files
    files = [f for f in files if not f.stem.endswith("_subtitled")]

    if not files:
        console.print(f"[yellow]No MKV files found in {directory}[/yellow]")
        raise typer.Exit(code=0)

    console.rule("[bold cyan]media-tool · video subtitle (batch)[/bold cyan]")
    console.print(f"[dim]Directory:[/dim]  {directory}")
    console.print(f"[dim]Files found:[/dim] {len(files)}")
    console.print(f"[dim]Language:[/dim]   {language}   [dim]Model:[/dim] {model}\n")

    succeeded: list[Path] = []
    failed: list[tuple[Path, str]] = []

    for i, mkv in enumerate(files, 1):
        console.print(f"\n[bold]({i}/{len(files)})[/bold] {mkv.name}")
        output_file = mkv.with_stem(f"{mkv.stem}_subtitled").with_suffix(".mkv")

        if output_file.exists() and not overwrite:
            console.print(f"  [dim]Skipping — output already exists:[/dim] {output_file.name}")
            succeeded.append(mkv)
            continue

        ok = _subtitle_single(
            input_file=mkv,
            language=language,
            model=model,
            output_file=output_file,
            overwrite=overwrite,
            skip_hallucination_check=skip_hallucination_check,
        )
        if ok:
            succeeded.append(mkv)
        else:
            failed.append((mkv, "see output above"))

    # Batch summary
    console.rule()
    console.print(f"\n[bold]Batch complete:[/bold] {len(succeeded)}/{len(files)} succeeded")
    if failed:
        console.print(f"[red]Failed ({len(failed)}):[/red]")
        for path, _reason in failed:
            console.print(f"  ✘ {path.name}")
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# subtitle-auto — check & generate only when needed
# ---------------------------------------------------------------------------


def _has_english_audio(probe: ProbeResult) -> bool:
    """Return True if the file has at least one English audio stream."""
    for s in probe.audio_streams():
        tags = s.get("tags") or {}
        lang = tags.get("language", "").lower()
        if lang in ("en", "eng"):
            return True
    return False


def _has_english_subtitles(probe: ProbeResult) -> bool:
    """Return True if the file already has at least one English subtitle track."""
    for s in probe.subtitle_streams():
        tags = s.get("tags") or {}
        lang = tags.get("language", "").lower()
        if lang in ("en", "eng"):
            return True
    return False


@app.command("subtitle-auto")
def subtitle_auto_command(
    input_path: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=True,
        readable=True,
        help="MKV file or directory to process.",
    ),
    model: str = typer.Option(
        "large-v3",
        "--model",
        "-m",
        help="Whisper model to use (tiny, base, small, medium, large-v3).",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        "-y",
        help="Re-generate even if English subtitles already exist.",
    ),
    recursive: bool = typer.Option(
        False,
        "--recursive",
        "-r",
        help="Process subdirectories recursively (directory mode only).",
    ),
    skip_hallucination_check: bool = typer.Option(
        False,
        "--skip-hallucination-check",
        help="Skip hallucination detection (not recommended).",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Only show what would be done, without actually transcribing.",
    ),
) -> None:
    """
    Auto-generate English subtitles only where needed.

    For each MKV file this command checks:
      1. Does the file have an English audio track?
      2. Does the file already have English subtitles?

    Subtitles are generated only when (1) is true and (2) is false.
    Files with no English audio are skipped entirely.

    Examples:
        media-tool video subtitle-auto "Season 01/"
        media-tool video subtitle-auto movie.mkv
        media-tool video subtitle-auto "Series/" --recursive --dry-run
    """
    from utils.ffprobe_runner import probe_file

    if input_path.is_file():
        files = [input_path]
    else:
        pattern = "**/*.mkv" if recursive else "*.mkv"
        files = sorted(input_path.glob(pattern))
        files = [f for f in files if not f.stem.endswith("_subtitled")]

    if not files:
        console.print(f"[yellow]No MKV files found in {input_path}[/yellow]")
        raise typer.Exit(code=0)

    console.rule("[bold cyan]media-tool · video subtitle-auto[/bold cyan]")
    if input_path.is_dir():
        console.print(f"[dim]Directory:[/dim]  {input_path}")
    console.print(f"[dim]Files found:[/dim] {len(files)}   [dim]Model:[/dim] {model}")
    if dry_run:
        console.print("[yellow]DRY RUN — no files will be changed[/yellow]")
    console.print()

    # ---- categorise every file ----
    to_generate: list[Path] = []
    skipped_has_subs: list[Path] = []
    skipped_no_eng_audio: list[Path] = []

    for mkv in files:
        probe = probe_file(mkv)
        if probe.failed:
            console.print(f"  [red]✘[/red] {mkv.name}  [dim](probe failed — skipping)[/dim]")
            skipped_no_eng_audio.append(mkv)
            continue

        has_audio = _has_english_audio(probe)
        has_subs = _has_english_subtitles(probe)

        if not has_audio:
            console.print(f"  [dim]–[/dim] {mkv.name}  [dim](no English audio, skipping)[/dim]")
            skipped_no_eng_audio.append(mkv)
        elif has_subs and not overwrite:
            console.print(f"  [green]✓[/green] {mkv.name}  [dim](English subtitles already present)[/dim]")
            skipped_has_subs.append(mkv)
        else:
            marker = " [dim](would generate)[/dim]" if dry_run else ""
            console.print(f"  [yellow]→[/yellow] {mkv.name}{marker}")
            to_generate.append(mkv)

    # ---- summary before we start ----
    console.print(
        f"\n[bold]Will generate:[/bold] {len(to_generate)}   "
        f"[dim]Already done:[/dim] {len(skipped_has_subs)}   "
        f"[dim]No English audio:[/dim] {len(skipped_no_eng_audio)}"
    )

    if dry_run or not to_generate:
        raise typer.Exit(code=0)

    # ---- generate ----
    console.print()
    succeeded: list[Path] = []
    failed: list[Path] = []

    for i, mkv in enumerate(to_generate, 1):
        console.print(f"\n[bold]({i}/{len(to_generate)})[/bold] {mkv.name}")
        output_file = mkv.with_stem(f"{mkv.stem}_subtitled").with_suffix(".mkv")
        ok = _subtitle_single(
            input_file=mkv,
            language="en",
            model=model,
            output_file=output_file,
            overwrite=overwrite,
            skip_hallucination_check=skip_hallucination_check,
        )
        if ok:
            succeeded.append(mkv)
        else:
            failed.append(mkv)

    console.rule()
    console.print(f"\n[bold]Done:[/bold] {len(succeeded)} generated, {len(failed)} failed")
    if failed:
        console.print("[red]Failed:[/red]")
        for p in failed:
            console.print(f"  ✘ {p.name}")
        raise typer.Exit(code=1)


def _render_trailer_results(results: list[TrailerDownloadResult]) -> None:
    """Render a compact trailer download summary table."""
    table = Table(title="Trailer Download Results", box=box.ROUNDED)
    table.add_column("Movie", style="cyan")
    table.add_column("Status")
    table.add_column("Language", justify="center")
    table.add_column("Trailer File", overflow="fold")
    table.add_column("Details", overflow="fold")

    for result in results:
        status = "[green]✓ downloaded[/green]" if result.success else "[red]✘ failed[/red]"
        if result.dry_run and result.success:
            status = "[yellow]◌ dry-run[/yellow]"
        if result.skipped:
            status = "[dim]⏭ skipped[/dim]"

        trailer_file = result.trailer_path.name if result.trailer_path is not None else "-"
        details = result.selected_title or result.error or "-"

        table.add_row(
            result.movie_name,
            status,
            result.language or "-",
            trailer_file,
            details,
        )

    console.print(table)


@app.command("download-trailers")
def download_trailers_command(
    library_path: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help="Jellyfin movie library root path.",
    ),
    languages: str = typer.Option(
        "en,de",
        "--languages",
        "-l",
        help="Comma-separated language preference order (e.g., en,de).",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview trailer matches without downloading files.",
    ),
    skip_existing: bool = typer.Option(
        True,
        "--skip-existing/--include-existing",
        help="Skip movie folders that already contain trailer files.",
    ),
    max_downloads: int = typer.Option(
        0,
        "--max-downloads",
        "-m",
        help="Maximum number of movie folders to process (0 means no limit).",
    ),
) -> None:
    """Download YouTube trailers for Jellyfin movie folders."""
    language_list = tuple(lang.strip().lower() for lang in languages.split(",") if lang.strip())
    if not language_list:
        err_console.print("Error: at least one language must be provided")
        raise typer.Exit(code=1)

    config = get_config()
    ytdlp_binary = config.tools.yt_dlp if config.tools and config.tools.yt_dlp else "yt-dlp"

    console.rule("[bold cyan]media-tool · video download-trailers[/bold cyan]")
    console.print(f"[dim]Library:[/dim] {library_path}")
    console.print(f"[dim]Languages:[/dim] {', '.join(language_list)}")
    console.print(f"[dim]Skip existing:[/dim] {skip_existing}")
    if max_downloads > 0:
        console.print(f"[dim]Max folders:[/dim] {max_downloads}")
    if dry_run:
        console.print("[yellow]DRY RUN — no trailer files will be written[/yellow]")

    try:
        ytdlp_runner = YtDlpRunner(ytdlp_binary=ytdlp_binary)
    except YtDlpNotFoundError as exc:
        err_console.print(f"Error: {exc}")
        err_console.print("Install yt-dlp or configure tools.yt_dlp in media-tool.toml")
        raise typer.Exit(code=1)
    except Exception as exc:
        err_console.print(f"Error initializing yt-dlp: {exc}")
        raise typer.Exit(code=1)

    search_service = TrailerSearchService(ytdlp_runner=ytdlp_runner)
    downloader = TrailerDownloadService(
        ytdlp_runner=ytdlp_runner,
        search_service=search_service,
        scanner=MovieFolderScanner(),
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        transient=True,
        console=console,
    ) as progress:
        task_id = progress.add_task("Scanning and downloading trailers", total=1)

        def _progress_callback(current: int, total: int, current_movie: str) -> None:
            progress.update(
                task_id,
                total=max(1, total),
                completed=min(current, max(1, total)),
                description=f"Processing: {current_movie}",
            )

        try:
            results = downloader.process_library(
                library_path=library_path,
                preferred_languages=language_list,
                dry_run=dry_run,
                skip_existing=skip_existing,
                max_downloads=max_downloads,
                progress_callback=_progress_callback,
            )
        except Exception as exc:
            err_console.print(f"Error: {exc}")
            raise typer.Exit(code=1)

    if not results:
        console.print("[yellow]No matching movie folders found.[/yellow]")
        raise typer.Exit(code=0)

    _render_trailer_results(results)

    success_count = sum(1 for result in results if result.success)
    failure_count = len(results) - success_count
    console.print(f"\n[bold]Summary:[/bold] {success_count}/{len(results)} successful · {failure_count} failed")

    if failure_count > 0 and not dry_run:
        raise typer.Exit(code=1)


@app.command("upscale")
def upscale_command(
    input_file: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Input video file to upscale.",
    ),
    output_file: Path = typer.Argument(
        ...,
        file_okay=True,
        dir_okay=False,
        help="Output upscaled video file path.",
    ),
    target_height: int = typer.Option(
        720,
        "--height",
        "-h",
        help="Target height in pixels (default: 720 for 720p).",
    ),
    video_codec: str = typer.Option(
        "libx264",
        "--codec",
        "-c",
        help="Video codec to use (default: libx264).",
    ),
    preset: str = typer.Option(
        "medium",
        "--preset",
        "-p",
        help="Encoding preset (ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow).",
    ),
    crf: int = typer.Option(
        20,
        "--crf",
        help="Constant Rate Factor (0-51, lower = higher quality, default: 20).",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        "-y",
        help="Overwrite output file if it exists.",
    ),
) -> None:
    """
    Upscale DVD-quality video to higher resolution.

    Enhances low-resolution content (e.g., 480p → 720p) with H.265/HEVC encoding.
    """
    console.rule("[bold cyan]media-tool · video upscale[/bold cyan]")
    console.print(f"[dim]Input :[/dim] {input_file}")
    console.print(f"[dim]Output:[/dim] {output_file}")
    console.print(f"[dim]Target height:[/dim] {target_height}p")
    console.print(f"[dim]Codec:[/dim] {video_codec}")
    console.print(f"[dim]Preset:[/dim] {preset}")
    console.print(f"[dim]CRF:[/dim] {crf}")

    try:
        from core.video import UpscaleOptions

        opts = UpscaleOptions(
            target_height=target_height,
            codec=video_codec,
            preset=preset,
            crf=crf,
            overwrite=overwrite,
        )
        result = upscale_dvd(
            source=input_file,
            target=output_file,
            opts=opts,
        )
    except Exception as e:
        err_console.print(f"Error: {e}")
        raise typer.Exit(code=1)

    if result.status.name == "SUCCESS":
        console.print(f"\n[green]✓[/green] Successfully upscaled to {result.target}")
        console.print(f"[dim]Duration:[/dim] {result.duration_seconds:.1f}s")
        console.print(
            f"[dim]Size change:[/dim] {result.size_before_gb:.2f}GB → {result.size_after_gb:.2f}GB ({result.size_delta_gb:+.2f}GB)"
        )
    elif result.status.name == "SKIPPED":
        console.print(f"\n[yellow]⏭️[/yellow] Skipped: {result.message}")
    else:
        err_console.print(f"\n[red]✘  Upscaling failed:[/red] {result.message}")
        if result.ffmpeg_result and result.ffmpeg_result.stderr:
            stderr_tail = "\n".join(result.ffmpeg_result.stderr.splitlines()[-20:])
            console.print(f"\n[dim]ffmpeg stderr (tail):[/dim]\n{stderr_tail}", highlight=False)
        raise typer.Exit(code=1)


@app.command("subtitle-translate")
def subtitle_translate_command(
    path: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=True,
        readable=True,
        help="SRT/ASS/VTT file or directory to translate.",
    ),
    source_lang: str = typer.Option(
        "en",
        "--from",
        "-s",
        help="Source language code (en, de).",
    ),
    target_lang: str = typer.Option(
        "de",
        "--to",
        "-t",
        help="Target language code (en, de).",
    ),
    backend: str = typer.Option(
        "opus-mt",
        "--backend",
        help="Translation backend: opus-mt (GPU, recommended) | argos (CPU fallback).",
    ),
    model_size: str = typer.Option(
        "big",
        "--model-size",
        help="Model size: standard (~300 MB) | big (~900 MB, higher quality).",
    ),
    recursive: bool = typer.Option(
        False,
        "--recursive",
        "-r",
        help="Process subdirectories recursively (directory mode only).",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        "-y",
        help="Overwrite existing output files.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be done without writing files.",
    ),
) -> None:
    """
    Translate subtitle files locally with an offline AI model.

    No internet or API key required.
    Primary: Helsinki-NLP OPUS-MT via CTranslate2 (GPU).
    Fallback: argostranslate (CPU, no CUDA needed).

    Examples:
        media-tool video subtitle-translate movie.en.srt --from en --to de
        media-tool video subtitle-translate "Season 01/" -r --from en --to de
        media-tool video subtitle-translate movie.en.srt --from en --to de --dry-run
    """
    # Delegate to the shared implementation in subtitle_cmd

    # Invoke by re-using the core logic directly
    from core.translation.models import LanguagePair, TranslationStatus
    from core.translation.subtitle_translator import SubtitleTranslator

    pair = LanguagePair(source=source_lang, target=target_lang)
    translator = SubtitleTranslator()
    subtitle_exts = {".srt", ".ass", ".ssa", ".vtt"}

    files: list[Path] = []
    if path.is_file():
        files = [path]
    elif path.is_dir():
        pattern = "**/*" if recursive else "*"
        files = [f for f in path.glob(pattern) if f.suffix.lower() in subtitle_exts]

    if not files:
        console.print("[yellow]No subtitle files found.[/yellow]")
        raise typer.Exit(code=0)

    if dry_run:
        console.print("[yellow]DRY RUN — no files will be written[/yellow]")

    console.rule("[bold cyan]media-tool · video subtitle-translate[/bold cyan]")
    console.print(f"[dim]Files:[/dim] {len(files)}   [dim]Direction:[/dim] {pair}   [dim]Backend:[/dim] {backend}")

    success = skipped = failed = 0
    for f in files:
        result = translator.translate_file(
            source_path=f,
            language_pair=pair,
            backend=backend,
            model_size=model_size,
            overwrite=overwrite,
            dry_run=dry_run,
        )
        match result.status:
            case TranslationStatus.SUCCESS:
                console.print(f"  [green]✓[/green] {f.name} → {result.output_path.name if result.output_path else '?'}")
                success += 1
            case TranslationStatus.SKIPPED:
                reason = "(dry run)" if dry_run else "(already exists)"
                console.print(f"  [dim]–[/dim] {f.name} {reason}")
                skipped += 1
            case TranslationStatus.FAILED:
                err_console.print(f"  [red]✗[/red] {f.name}: {result.error_message}")
                failed += 1

    console.rule()
    console.print(f"\n[bold]Summary:[/bold] {success} translated · {skipped} skipped · {failed} failed")
    if failed:
        raise typer.Exit(code=1)


@app.command("subtitle-translate-mkv")
def subtitle_translate_mkv_command(
    path: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=True,
        readable=True,
        help="MKV file or directory containing MKV files.",
    ),
    source_lang: str = typer.Option(
        "en",
        "--from",
        "-s",
        help="Source subtitle language code to extract (en, de).",
    ),
    target_lang: str = typer.Option(
        "de",
        "--to",
        "-t",
        help="Target translation language code (en, de).",
    ),
    backend: str = typer.Option(
        "opus-mt",
        "--backend",
        help="Translation backend: opus-mt (GPU) | argos (CPU fallback).",
    ),
    model_size: str = typer.Option(
        "big",
        "--model-size",
        help="Model size: standard (~300 MB) | big (~900 MB).",
    ),
    recursive: bool = typer.Option(
        False,
        "--recursive",
        "-r",
        help="Process subdirectories recursively.",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        "-y",
        help="Overwrite existing output files.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be done without writing files.",
    ),
    chunk_size: int = typer.Option(
        4,
        "--chunk-size",
        help="Segments per context chunk (improves grammar/pronouns).",
    ),
    no_line_wrap: bool = typer.Option(
        False,
        "--no-line-wrap",
        help="Disable post-translation line wrapping.",
    ),
    max_line_length: int = typer.Option(
        40,
        "--max-line-length",
        help="Max characters per subtitle line.",
    ),
) -> None:
    """
    Extract, translate, and re-mux subtitle track(s) in MKV file(s).

    Finds the subtitle track matching --from language, translates it offline
    with Helsinki-NLP OPUS-MT or argostranslate, then adds the translated
    track back into the MKV (no re-encode, copy streams).

    Examples:
        media-tool video subtitle-translate-mkv movie.mkv --from en --to de
        media-tool video subtitle-translate-mkv "Season 01/" -r --from en --to de
        media-tool video subtitle-translate-mkv movie.mkv --dry-run
    """
    from core.video.subtitle_pipeline import translate_mkv_subtitles

    mkv_files: list[Path] = []
    if path.is_file():
        mkv_files = [path]
    elif path.is_dir():
        pattern = "**/*.mkv" if recursive else "*.mkv"
        mkv_files = list(path.glob(pattern))

    if not mkv_files:
        console.print("[yellow]No MKV files found.[/yellow]")
        raise typer.Exit(code=0)

    if dry_run:
        console.print("[yellow]DRY RUN — no files will be changed[/yellow]")

    console.rule("[bold cyan]media-tool · video subtitle-translate-mkv[/bold cyan]")
    console.print(
        f"[dim]Files:[/dim] {len(mkv_files)}   "
        f"[dim]Direction:[/dim] {source_lang}→{target_lang}   "
        f"[dim]Backend:[/dim] {backend}"
    )

    success = skipped = failed = 0
    for mkv in mkv_files:
        console.print(f"\n  Processing [bold]{mkv.name}[/bold] …")
        result = translate_mkv_subtitles(
            video_path=mkv,
            source_lang=source_lang,
            target_lang=target_lang,
            backend=backend,
            model_size=model_size,
            overwrite=overwrite,
            dry_run=dry_run,
            chunk_size=chunk_size,
            line_wrap=not no_line_wrap,
            max_line_length=max_line_length,
        )
        if result.success:
            console.print(f"  [green]✓[/green] {mkv.name} → {result.output_path}")
            success += 1
        elif dry_run:
            console.print(f"  [yellow]–[/yellow] {mkv.name} (dry run)")
            skipped += 1
        else:
            err_console.print(f"  [red]✗[/red] {mkv.name}: {result.error_message}")
            failed += 1

    console.rule()
    console.print(f"\n[bold]Summary:[/bold] {success} done · {skipped} skipped · {failed} failed")
    if failed:
        raise typer.Exit(code=1)
