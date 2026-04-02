"""
src/cli/audiobook_cmd.py

CLI interface for audiobook processing.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich import box
from rich.console import Console
from rich.table import Table

from cli.progress_display import ConsoleProgressReporter
from core.audiobook import (
    detect_chapter_files,
    merge_audiobook_library,
    organize_audiobooks,
    scan_audiobook_library,
)

if TYPE_CHECKING:
    from core.audio.metadata import AudioMetadataEnhanced

app = typer.Typer(help="Process audiobook files.")
console = Console()
err_console = Console(stderr=True, style="bold red")


def _print_audiobook_preview(metadata_list: list[AudioMetadataEnhanced]) -> None:
    """Print a Rich table preview of audiobook metadata."""
    if not metadata_list:
        console.print("[yellow]No audiobook files found.[/yellow]")
        return

    table = Table(title="Audiobook Library Preview", box=box.ROUNDED)
    table.add_column("File", style="dim", no_wrap=True)
    table.add_column("Author", style="cyan")
    table.add_column("Book", style="green")
    table.add_column("Title", style="yellow")
    table.add_column("Duration", style="magenta", justify="right")
    table.add_column("Format", style="blue", justify="center")

    for metadata in metadata_list:
        author = metadata.narrator or metadata.artist or metadata.parsed_artist or "Unknown"
        book = metadata.album or metadata.parsed_album or "Unknown"
        title = metadata.title or metadata.parsed_title or metadata.filename
        duration = f"{metadata.duration_seconds:.0f}s" if metadata.duration_seconds else "Unknown"
        format_name = metadata.filepath.suffix.upper().lstrip(".") if metadata.filepath else "Unknown"

        table.add_row(
            metadata.filepath.name if metadata.filepath else "Unknown",
            author[:30] + "..." if len(author) > 30 else author,
            book[:30] + "..." if len(book) > 30 else book,
            title[:40] + "..." if len(title) > 40 else title,
            duration,
            format_name,
        )

    console.print(table)


@app.command("scan")
def scan_command(
    directory: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help="Directory to scan for audiobook files.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output CSV file path. Defaults to <directory>/audiobooks_list.csv",
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
    Scan DIRECTORY for audiobook files and extract metadata.
    """
    console.rule("[bold cyan]media-tool · audiobook scan[/bold cyan]")
    console.print(f"[dim]Directory:[/dim] {directory}")
    console.print(f"[dim]Recursive:[/dim] {recursive}")

    try:
        metadata_list = scan_audiobook_library(directory, recursive)
    except Exception as e:
        err_console.print(f"Error scanning directory: {e}")
        raise typer.Exit(code=1)

    if not metadata_list:
        console.print("[yellow]No audiobook files found.[/yellow]")
        return

    console.print(f"Found {len(metadata_list)} audiobook files")

    # Optional preview
    if preview:
        _print_audiobook_preview(metadata_list[:20])
        if len(metadata_list) > 20:
            console.print(f"[dim]… and {len(metadata_list) - 20} more rows in the CSV.[/dim]")

    # Export to CSV
    if output is None:
        output = directory / "audiobooks_list.csv"

    try:
        import csv

        with open(output, "w", newline="", encoding="utf-8") as csvfile:
            fieldnames = [
                "file_path",
                "filename",
                "title",
                "artist",
                "album",
                "year",
                "track_number",
                "duration",
                "bitrate",
                "format",
                "narrator",
                "series",
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for metadata in metadata_list:
                writer.writerow(
                    {
                        "file_path": str(metadata.filepath),
                        "filename": metadata.filename,
                        "title": metadata.title,
                        "artist": metadata.artist,
                        "album": metadata.album,
                        "year": metadata.year,
                        "track_number": metadata.track_number,
                        "duration": metadata.duration_seconds,
                        "bitrate": metadata.bit_rate,
                        "format": metadata.codec_name,
                        "narrator": metadata.narrator,
                        "series": metadata.series,
                    }
                )

        console.print(f"[green]✓[/green] Exported metadata to {output}")

    except Exception as e:
        err_console.print(f"Error exporting CSV: {e}")
        raise typer.Exit(code=1)


@app.command("organize")
def organize_command(
    source_dir: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help="Source directory containing audiobook files.",
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
    Organize audiobook files into Jellyfin-compatible structure.

    Structure: Audiobooks/Author/Book/Title.ext
    """
    console.rule("[bold cyan]media-tool · audiobook organize[/bold cyan]")
    console.print(f"[dim]Source:[/dim] {source_dir}")
    console.print(f"[dim]Target:[/dim] {target_dir}")
    console.print(f"[dim]Format:[/dim] {format}")

    if dry_run:
        console.print("[yellow]DRY RUN MODE - No files will be modified[/yellow]\n")

    reporter = ConsoleProgressReporter(console)

    try:
        counts = organize_audiobooks(
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


@app.command("merge")
def merge_command(
    source_dir: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help="Source directory containing chapter files.",
    ),
    target_dir: Path = typer.Argument(
        ...,
        file_okay=False,
        dir_okay=True,
        help="Target directory for merged audiobook files.",
    ),
    format: str = typer.Option(
        "m4a",
        "--format",
        "-f",
        help="Output audio format (m4a, mp3, flac, aac, ogg).",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Show what would be merged without making changes.",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        "-y",
        help="Overwrite existing merged files.",
    ),
) -> None:
    """
    Merge chapter-based audiobooks into single files.

    Detects audiobook chapters (e.g., "Book Title - Chapter 01.mp3", "Book Title - Chapter 02.mp3")
    and merges them into single audiobook files suitable for audiobook players.

    Supports various naming patterns:
    - "Book Title - Chapter 01.mp3"
    - "Book Title - Part 01.mp3"
    - "Book Title 01.mp3"
    - "01 - Book Title.mp3"
    """
    console.rule("[bold cyan]media-tool · audiobook merge[/bold cyan]")
    console.print(f"[dim]Source:[/dim] {source_dir}")
    console.print(f"[dim]Target:[/dim] {target_dir}")
    console.print(f"[dim]Format:[/dim] {format}")
    reporter = ConsoleProgressReporter(console)

    if dry_run:
        console.print("[yellow]DRY RUN MODE - No files will be modified[/yellow]\n")

        # Show what would be merged
        book_chapters = detect_chapter_files(source_dir)

        if not book_chapters:
            console.print("[yellow]No chapter files detected.[/yellow]")
            return

        table = Table(title="Audiobooks to be Merged", box=box.ROUNDED)
        table.add_column("Book Title", style="cyan", max_width=40)
        table.add_column("Chapters", justify="right")
        table.add_column("Total Size", justify="right")
        table.add_column("Output File", style="green", max_width=50)

        for book_title, chapters in book_chapters.items():
            if len(chapters) < 2:
                continue

            # Calculate total size
            total_size = sum(chapter[0].stat().st_size for chapter in chapters)
            size_mb = total_size / 1_048_576  # Convert to MB

            # Generate output filename
            safe_title = _sanitize_filename(book_title)
            output_name = f"{safe_title}.{format}"

            table.add_row(
                book_title,
                str(len(chapters)),
                f"{size_mb:.1f} MB",
                output_name,
            )

        console.print(table)
        console.print(
            f"\n[dim]Total books that would be merged: {len([b for b in book_chapters.values() if len(b) >= 2])}[/dim]"
        )
        return

    try:
        results = merge_audiobook_library(
            input_dir=source_dir,
            output_dir=target_dir,
            format=format,
            overwrite=overwrite,
            progress_callback=reporter,
        )
    except Exception as e:
        err_console.print(f"Error: {e}")
        raise typer.Exit(code=1)

    # Show results
    if results["books_merged"] > 0:
        console.print(f"\n[green]✓ Successfully merged {results['books_merged']} audiobooks[/green]")

        table = Table(title="Merged Audiobooks", box=box.ROUNDED)
        table.add_column("Book Title", style="cyan", max_width=40)
        table.add_column("Chapters", justify="right")
        table.add_column("Size", justify="right")

        for book in results["merged_books"]:
            table.add_row(
                book["title"],
                str(book["chapters"]),
                f"{book['size_mb']:.1f} MB",
            )

        console.print(table)
    else:
        console.print("[yellow]No audiobooks were merged.[/yellow]")

    if results["errors"]:
        console.print("\n[red]Errors encountered:[/red]")
        for error in results["errors"]:
            console.print(f"  • {error}")

    console.print(
        f"\n[bold]Summary:[/bold] "
        f"Books found: {results['books_found']}  "
        f"Merged: {results['books_merged']}  "
        f"Total chapters: {results['total_chapters']}"
    )

    if results["errors"]:
        raise typer.Exit(code=1)


def _sanitize_filename(name: str) -> str:
    """Sanitize filename by removing/replacing invalid characters."""
    import re

    # Replace invalid characters with underscores
    return re.sub(r'[<>:"/\\|?*]', "_", name)
