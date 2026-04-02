"""
src/cli/audio_cmd.py

CLI interface for music processing.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich import box
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from cli.progress_display import ConsoleProgressReporter
from core.audio import (
    AudioFileMetadata,
    CSVExporter,
    CSVExportError,
    LibraryScanner,
    MetadataExtractor,
    convert_audio,
    improve_audio_file,
    improve_audio_library,
    organize_music,
)
from utils.config import build_missing_config_hint, get_config, has_config_file

app = typer.Typer(help="Process music files.")
console = Console()
err_console = Console(stderr=True, style="bold red")


@app.command("scan")
def scan_command(
    directory: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help="Directory to scan for audio files.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output CSV file path. Defaults to <directory>/music_library.csv",
    ),
    max_workers: int = typer.Option(
        4,
        "--max-workers",
        min=1,
        max=16,
        help="Parallel worker count for metadata extraction.",
    ),
    include_errors: bool = typer.Option(
        True,
        "--include-errors/--exclude-errors",
        help="Include unreadable files with error details in the CSV.",
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
    Scan DIRECTORY for audio files and generate a detailed CSV report.
    """
    console.rule("[bold cyan]media-tool · audio scan[/bold cyan]")
    console.print(f"[dim]Directory :[/dim] {directory}")

    resolved_output = output or directory / "music_library.csv"
    console.print(f"[dim]CSV output :[/dim] {resolved_output}")
    console.print(f"[dim]Workers   :[/dim] {max_workers}")

    extractor = MetadataExtractor()
    scanner = LibraryScanner(metadata_extractor=extractor, max_workers=max_workers)
    exporter = CSVExporter()

    progress_task_id: int | None = None

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        progress_task_id = progress.add_task("Processing files...", total=None)

        def update_progress(current: int, total: int) -> None:
            if progress_task_id is None:
                return
            progress.update(
                progress_task_id,
                description=f"Processing files ({current}/{total})...",
                completed=current,
                total=total,
            )

        metadata_list = scanner.scan(directory, progress_callback=update_progress, recursive=recursive)

    if not metadata_list:
        console.print("[yellow]No audio files found.[/yellow]")
        raise typer.Exit(code=0)

    successful = len([item for item in metadata_list if not item.error_message])
    errors = len(metadata_list) - successful

    console.print("\n[green]✓ Scan complete[/green]")
    console.print(f"  Total files: {len(metadata_list)}")
    console.print(f"  Successful: {successful}")
    if errors:
        console.print(f"  [yellow]Errors: {errors}[/yellow]")

    _print_library_statistics(metadata_list)

    console.print("\n[cyan]Exporting to CSV...[/cyan]")
    try:
        rows_written = exporter.export(metadata_list, resolved_output, include_errors=include_errors)
    except CSVExportError as exc:
        err_console.print(f"Export failed: {exc}")
        raise typer.Exit(code=1)

    console.print(f"[bold green]✔  Exported {rows_written} rows to {resolved_output}[/bold green]")

    # Optional preview
    if preview:
        _print_audio_preview(metadata_list[:20])
        if len(metadata_list) > 20:
            console.print(f"[dim]… and {len(metadata_list) - 20} more rows in the CSV.[/dim]")


@app.command("organize")
def organize_command(
    source_dir: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help="Source directory containing music files.",
    ),
    target_dir: Path = typer.Argument(
        ...,
        file_okay=False,
        dir_okay=True,
        help="Target directory for organized files.",
    ),
    format: str = typer.Option(
        "flac",
        "--format",
        "-f",
        help="Target audio format (mp3, flac, m4a, aac, opus, ogg).",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Show what would be done without making changes.",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Overwrite existing files in target directory.",
    ),
) -> None:
    """
    Organize music files into Jellyfin-compatible structure.

    Structure: Music/Artist/Year - Album/Track - Title.ext
    """
    console.rule("[bold cyan]media-tool · audio organize[/bold cyan]")
    console.print(f"[dim]Source:[/dim] {source_dir}")
    console.print(f"[dim]Target:[/dim] {target_dir}")
    console.print(f"[dim]Format:[/dim] {format}")

    if dry_run:
        console.print("[yellow]DRY RUN MODE - No files will be modified[/yellow]\n")

    reporter = ConsoleProgressReporter(console)

    try:
        counts = organize_music(
            input_dir=source_dir,
            output_dir=target_dir,
            convert_format=format if not dry_run else None,
            overwrite=overwrite,
            progress_callback=reporter,
        )
    except ValueError as e:
        err_console.print(f"Error: {e}")
        raise typer.Exit(code=1)

    console.print(
        f"\n[bold]Summary:[/bold] "
        f"Processed: {counts['processed']}  "
        f"Converted: {counts['converted']}  "
        f"Skipped: {counts['skipped']}  "
        f"Errors: {counts['errors']}"
    )

    if counts["errors"] > 0:
        raise typer.Exit(code=1)


@app.command("convert")
def convert_command(
    input_file: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Input audio file.",
    ),
    output_file: Path = typer.Argument(
        ...,
        file_okay=True,
        dir_okay=False,
        help="Output audio file path.",
    ),
    format: str = typer.Option(
        "flac",
        "--format",
        "-f",
        help="Target audio format (mp3, flac, m4a, aac, opus, ogg).",
    ),
    quality: str | None = typer.Option(
        None,
        "--quality",
        "-q",
        help="Quality setting (format-specific, e.g. '0' for MP3, '256k' for AAC).",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Overwrite output file if it exists.",
    ),
) -> None:
    """
    Convert a single audio file to a different format.
    """
    console.rule("[bold cyan]media-tool · audio convert[/bold cyan]")
    console.print(f"[dim]Input :[/dim] {input_file}")
    console.print(f"[dim]Output:[/dim] {output_file}")
    console.print(f"[dim]Format:[/dim] {format}")

    try:
        result = convert_audio(
            input_file=input_file,
            output_file=output_file,
            format=format,
            quality=quality,
            preserve_metadata=True,
            overwrite=overwrite,
        )
    except ValueError as e:
        err_console.print(f"Error: {e}")
        raise typer.Exit(code=1)

    if result.success:
        console.print(f"\n[bold green]✔  Converted successfully:[/bold green] {output_file}")
    else:
        err_console.print(f"\n[red]✘  Conversion failed:[/red] {input_file}")
        if result.ffmpeg_result:
            stderr_tail = "\n".join(result.ffmpeg_result.stderr.splitlines()[-20:])
            console.print(f"\n[dim]ffmpeg stderr (tail):[/dim]\n{stderr_tail}", highlight=False)
        raise typer.Exit(code=1)


@app.command("improve")
def improve_command(
    input_file: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Input audio file to improve.",
    ),
    output_file: Path = typer.Argument(
        ...,
        file_okay=True,
        dir_okay=False,
        help="Output improved audio file path.",
    ),
    no_silence_removal: bool = typer.Option(
        False,
        "--no-silence-removal",
        help="Skip silence removal from start/end.",
    ),
    no_normalization: bool = typer.Option(
        False,
        "--no-normalization",
        help="Skip volume normalization.",
    ),
    no_enhancement: bool = typer.Option(
        False,
        "--no-enhancement",
        help="Skip quality enhancement.",
    ),
    silence_threshold: float = typer.Option(
        -50.0,
        "--silence-threshold",
        help="Silence threshold in dB (default: -50.0).",
    ),
    target_level: float = typer.Option(
        -16.0,
        "--target-level",
        help="Target volume level in dB (default: -16.0).",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Overwrite output file if it exists.",
    ),
) -> None:
    """
    Improve a single audio file with silence removal, volume normalization, and quality enhancement.
    """
    console.rule("[bold cyan]media-tool · audio improve[/bold cyan]")
    console.print(f"[dim]Input :[/dim] {input_file}")
    console.print(f"[dim]Output:[/dim] {output_file}")

    result = improve_audio_file(
        input_file=input_file,
        output_file=output_file,
        remove_silence_flag=not no_silence_removal,
        normalize_volume=not no_normalization,
        enhance_quality=not no_enhancement,
        silence_threshold=silence_threshold,
        target_level=target_level,
        overwrite=overwrite,
    )

    if result.success:
        operations = ", ".join(result.operations_performed) if result.operations_performed else "none"
        console.print(f"\n[bold green]✔  Improved successfully:[/bold green] {output_file}")
        console.print(f"[dim]Operations:[/dim] {operations}")
    else:
        err_console.print(f"\n[red]✘  Improvement failed:[/red] {input_file}")
        if result.ffmpeg_result:
            stderr_tail = "\n".join(result.ffmpeg_result.stderr.splitlines()[-20:])
            console.print(f"\n[dim]ffmpeg stderr (tail):[/dim]\n{stderr_tail}", highlight=False)
        raise typer.Exit(code=1)


@app.command("improve-library")
def improve_library_command(
    input_dir: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help="Input directory containing audio files to improve.",
    ),
    output_dir: Path = typer.Argument(
        ...,
        file_okay=False,
        dir_okay=True,
        help="Output directory for improved audio files.",
    ),
    no_silence_removal: bool = typer.Option(
        False,
        "--no-silence-removal",
        help="Skip silence removal from start/end.",
    ),
    no_normalization: bool = typer.Option(
        False,
        "--no-normalization",
        help="Skip volume normalization.",
    ),
    no_enhancement: bool = typer.Option(
        False,
        "--no-enhancement",
        help="Skip quality enhancement.",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Overwrite existing files in output directory.",
    ),
) -> None:
    """
    Improve an entire audio library with silence removal, volume normalization, and quality enhancement.

    Processes all audio files in the input directory and saves improved versions
    to the output directory, preserving the directory structure.
    """
    console.rule("[bold cyan]media-tool · audio improve-library[/bold cyan]")
    console.print(f"[dim]Input dir :[/dim] {input_dir}")
    console.print(f"[dim]Output dir:[/dim] {output_dir}")
    reporter = ConsoleProgressReporter(console)

    try:
        counts = improve_audio_library(
            input_dir=input_dir,
            output_dir=output_dir,
            remove_silence_flag=not no_silence_removal,
            normalize_volume=not no_normalization,
            enhance_quality=not no_enhancement,
            overwrite=overwrite,
            progress_callback=reporter,
        )
    except ValueError as e:
        err_console.print(f"Error: {e}")
        raise typer.Exit(code=1)

    console.print(
        f"\n[bold]Summary:[/bold] "
        f"Processed: {counts['processed']}  "
        f"Improved: {counts['improved']}  "
        f"Skipped: {counts['skipped']}  "
        f"Errors: {counts['errors']}"
    )

    if counts["errors"] > 0:
        raise typer.Exit(code=1)


@app.command("identify")
def identify_command(
    input_file: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Input audio file for metadata identification.",
    ),
    acoustid_api_key: str | None = typer.Option(
        None,
        "--acoustid-api-key",
        "-k",
        help="AcoustID API key. Defaults to config if available.",
    ),
) -> None:
    """Identify a single audio file using AcoustID + MusicBrainz."""
    from core.audio import AudioTagger

    resolved_api_key = acoustid_api_key or get_config().api.acoustid_api_key
    if not resolved_api_key:
        err_console.print("Error: AcoustID API key required.")
        if has_config_file():
            err_console.print("Set [api].acoustid_api_key in media-tool.toml or pass --acoustid-api-key.")
        else:
            err_console.print(build_missing_config_hint())
        raise typer.Exit(code=1)

    console.rule("[bold cyan]media-tool · audio identify[/bold cyan]")
    console.print(f"[dim]Input :[/dim] {input_file}")
    console.print("[dim]Resolving via AcoustID/MusicBrainz...[/dim]")

    tagger = AudioTagger(acoustid_api_key=resolved_api_key)
    try:
        matches = tagger.identify(str(input_file))
    except Exception as e:
        err_console.print(f"Error: {e}")
        raise typer.Exit(code=1)

    if not matches:
        console.print("[yellow]No matches found.[/yellow]")
        raise typer.Exit(code=0)

    table = Table(title="AcoustID Matches", box=box.MINIMAL_DOUBLE_HEAD)
    table.add_column("Rank", justify="right")
    table.add_column("Title")
    table.add_column("Artist")
    table.add_column("Album")
    table.add_column("Confidence", justify="right")

    for idx, match in enumerate(matches, 1):
        data = match.metadata
        table.add_row(
            str(idx),
            data.title or "-",
            data.artist or "-",
            data.album or "-",
            f"{match.confidence:.2f}",
        )

    console.print(table)


@app.command("auto-tag")
def auto_tag_command(
    input_file: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Input audio file to auto-tag using AcoustID metadata.",
    ),
    acoustid_api_key: str | None = typer.Option(
        None,
        "--acoustid-api-key",
        "-k",
        help="AcoustID API key. Defaults to config if available.",
    ),
    min_confidence: float = typer.Option(
        0.70,
        "--min-confidence",
        "-c",
        help="Minimum confidence threshold to apply tags.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing tags if present.",
    ),
) -> None:
    """Auto-tag a file with metadata from AcoustID + MusicBrainz."""
    from core.audio import AudioTagger

    config = get_config()
    resolved_api_key = acoustid_api_key or config.api.acoustid_api_key
    resolved_min_confidence = min_confidence if min_confidence != 0.70 else config.defaults.audio.min_confidence

    if not resolved_api_key:
        err_console.print("Error: AcoustID API key required.")
        if has_config_file():
            err_console.print("Set [api].acoustid_api_key in media-tool.toml or pass --acoustid-api-key.")
        else:
            err_console.print(build_missing_config_hint())
        raise typer.Exit(code=1)

    console.rule("[bold cyan]media-tool · audio auto-tag[/bold cyan]")
    console.print(f"[dim]Input :[/dim] {input_file}")

    tagger = AudioTagger(acoustid_api_key=resolved_api_key)
    try:
        metadata = tagger.auto_tag(str(input_file), force=force, min_confidence=resolved_min_confidence)
    except Exception as e:
        err_console.print(f"Error: {e}")
        raise typer.Exit(code=1)

    if not metadata:
        console.print(
            f"[yellow]No metadata applied. Confidence threshold {resolved_min_confidence} not reached.[/yellow]"
        )
        raise typer.Exit(code=0)

    console.print(f"[bold green]✔  Metadata applied to {input_file}[/bold green]")
    console.print(f"[dim]Title:[/dim] {metadata.title}")
    console.print(f"[dim]Artist:[/dim] {metadata.artist}")
    console.print(f"[dim]Album:[/dim] {metadata.album}")


@app.command("workflow")
def workflow_command(
    input_dir: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help="Input directory containing mixed music library.",
    ),
    output_dir: Path = typer.Argument(
        ...,
        file_okay=False,
        dir_okay=True,
        help="Output directory for processed music library.",
    ),
    format: str = typer.Option(
        "flac",
        "--format",
        "-f",
        help="Target audio format (mp3, flac, m4a, aac, opus, ogg).",
    ),
    improve_audio: bool = typer.Option(
        True,
        "--improve/--no-improve",
        help="Apply audio improvements (silence removal, normalization, enhancement).",
    ),
    scan_only: bool = typer.Option(
        False,
        "--scan-only",
        help="Only scan and analyze, don't process files.",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Overwrite existing files.",
    ),
) -> None:
    """
    Complete music library processing workflow.

    This command provides a comprehensive solution for mixed music libraries:
    1. Scan and analyze all audio files with metadata extraction
    2. Improve audio quality (remove silence, normalize volume, enhance quality)
    3. Organize files into proper directory structure
    4. Convert to consistent format

    Perfect for libraries with mixed sources (CD rips, downloads, different naming).
    """
    console.rule("[bold cyan]media-tool · audio workflow[/bold cyan]")
    console.print(f"[dim]Input dir :[/dim] {input_dir}")
    console.print(f"[dim]Output dir:[/dim] {output_dir}")
    console.print(f"[dim]Format    :[/dim] {format}")
    console.print(f"[dim]Improve   :[/dim] {'Yes' if improve_audio else 'No'}")

    if scan_only:
        console.print("[yellow]SCAN-ONLY MODE - No files will be modified[/yellow]\n")

    reporter = ConsoleProgressReporter(console)

    try:
        from core.audio.workflow import process_audio_library_workflow

        results = process_audio_library_workflow(
            input_dir=input_dir,
            output_dir=output_dir,
            format=format,
            improve=improve_audio,
            scan_only=scan_only,
            overwrite=overwrite,
            progress_callback=reporter,
        )
    except Exception as e:
        err_console.print(f"Error: {e}")
        raise typer.Exit(code=1)

    console.print(
        f"\n[bold]Summary:[/bold] "
        f"Scanned: {results['statistics']['total_files']}  "
        f"Improved: {results['statistics']['improved_files']}  "
        f"Organized: {results['statistics']['organized_files']}  "
        f"Converted: {results['statistics']['converted_files']}  "
        f"Errors: {results['statistics']['errors']}"
    )

    if results["statistics"]["errors"] > 0:
        raise typer.Exit(code=1)


@app.command("detect-language")
def detect_language_command(
    path: Path = typer.Argument(help="MKV-Datei oder Ordner"),
    recursive: bool = typer.Option(False, "-r", "--recursive", help="Unterordner rekursiv durchsuchen"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Nur anzeigen, nichts schreiben"),
    force: bool = typer.Option(False, "--force", help="Auch bereits gesetzte Sprachkürzel überschreiben"),
    min_confidence: float = typer.Option(0.85, "--min-confidence", help="Mindest-Konfidenz (0.0–1.0)"),
    whisper_model: str = typer.Option("medium", "--whisper-model", help="Whisper-Modell: tiny/base/medium/large-v3"),
    force_whisper: bool = typer.Option(False, "--force-whisper", help="Heuristik überspringen, direkt Whisper"),
    backup: bool = typer.Option(False, "--backup", help="Backup der Originaldatei erstellen (.bak)"),
) -> None:
    """
    Erkennt Sprache unlabeled Audio-Spuren und schreibt das Ergebnis
    als Metadaten-Tag in die MKV-Datei (lossless, kein Re-Encoding).

    \b
    Beispiele:
      media-tool audio detect-language movie.mkv
      media-tool audio detect-language "Y:\\Movies" -r --dry-run
      media-tool audio detect-language movie.mkv --force-whisper --whisper-model large-v3
      media-tool audio detect-language movie.mkv --backup
    """
    from core.language_detection.audio_tagger import AudioTagger
    from core.language_detection.models import TaggingStatus
    from core.language_detection.pipeline import LanguageDetectionPipeline

    if not path.exists():
        err_console.print(f"Kein gültiger Pfad: {path}")
        raise typer.Exit(1)

    pipeline = LanguageDetectionPipeline(
        min_confidence=min_confidence,
        whisper_model_size=whisper_model,
    )
    tagger = AudioTagger(
        pipeline=pipeline,
        min_confidence=min_confidence,
        create_backup=backup,
    )

    if path.is_file():
        results = tagger.tag_file(path, dry_run=dry_run, force=force)
    else:
        results = tagger.tag_directory(path, recursive=recursive, dry_run=dry_run)

    success = skipped = failed = 0
    for r in results:
        match r.status:
            case TaggingStatus.SUCCESS:
                conf_str = f"{r.confidence:.0%}" if r.confidence else ""
                typer.echo(
                    f"✅  {r.path.name} Spur {r.stream_index}: "
                    f"{r.previous_language or 'und'} → {r.detected_language} "
                    f"({r.method.value} {conf_str})"
                )
                success += 1
            case TaggingStatus.SKIPPED:
                typer.echo(
                    f"⏭️   {r.path.name} Spur {r.stream_index}: " f"bereits '{r.detected_language}' — übersprungen"
                )
                skipped += 1
            case TaggingStatus.FAILED:
                typer.echo(
                    f"❌  {r.path.name} Spur {r.stream_index}: {r.error}",
                    err=True,
                )
                failed += 1

    typer.echo(f"\n{success} gesetzt · {skipped} übersprungen · {failed} fehlgeschlagen")
    if dry_run:
        typer.echo("ℹ️   Dry-Run — keine Änderungen geschrieben.")
    if failed:
        raise typer.Exit(1)


def _print_library_statistics(metadata_list: list[AudioFileMetadata]) -> None:
    """Print summary statistics for a completed library scan."""
    from collections import Counter

    successful_results = [item for item in metadata_list if not item.error_message]
    if not successful_results:
        return

    total_size_gb = sum(item.file_size_mb for item in successful_results) / 1024
    total_duration_hours = sum(item.duration_seconds for item in successful_results) / 3600
    format_counter = Counter(item.extension for item in successful_results)
    lossless_count = sum(1 for item in successful_results if item.is_lossless)
    tagged_count = sum(1 for item in successful_results if item.is_tagged)

    console.print("\n[bold]Library Statistics:[/bold]")
    console.print(f"  Total size: {total_size_gb:.2f} GB")
    console.print(f"  Total duration: {total_duration_hours:.1f} hours")
    console.print(f"  Lossless: {lossless_count} ({(lossless_count / len(successful_results)) * 100:.1f}%)")
    console.print(f"  Tagged: {tagged_count} ({(tagged_count / len(successful_results)) * 100:.1f}%)")

    table = Table(title="Format Breakdown", box=box.ROUNDED)
    table.add_column("Format", style="cyan")
    table.add_column("Count", justify="right", style="yellow")
    table.add_column("Percentage", justify="right", style="green")

    for extension, count in format_counter.most_common(10):
        percentage = (count / len(successful_results)) * 100
        table.add_row(extension, str(count), f"{percentage:.1f}%")

    console.print(table)


def _print_audio_preview(metadata_list: list[AudioFileMetadata]) -> None:
    """Print a Rich table preview of library scan metadata."""
    table = Table(
        title="Audio Library Preview",
        box=box.ROUNDED,
        show_lines=False,
        expand=True,
    )
    table.add_column("File", style="cyan", no_wrap=True, max_width=30)
    table.add_column("Duration", justify="right")
    table.add_column("Codec", justify="center")
    table.add_column("Bitrate", justify="right")
    table.add_column("Tagged", justify="center")
    table.add_column("Title", max_width=25)
    table.add_column("Artist", max_width=20)
    table.add_column("Album", max_width=20)

    for meta in metadata_list:
        table.add_row(
            meta.file_name,
            f"{meta.duration_seconds / 60:.1f}m",
            (meta.codec or "?").upper(),
            f"{meta.bitrate_kbps}k" if meta.bitrate_kbps else "?",
            "Yes" if meta.is_tagged else "No",
            meta.title or "-",
            meta.artist or "-",
            meta.album or "-",
        )

    console.print(table)
