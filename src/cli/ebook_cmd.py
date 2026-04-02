"""CLI commands for ebook workflows and configuration visibility."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

from core.ebook.audit import LibraryAuditor
from core.ebook.conversion import CalibreNotFoundError, CalibreRunner, ConversionProfiles, FormatConverter
from core.ebook.cover import (
    CoverProvider,
    CoverSelector,
    CoverService,
    GoogleBooksCoverProvider,
    OpenLibraryCoverProvider,
)
from core.ebook.deduplication import DuplicateFinder, VersionComparator
from core.ebook.identification import BookIdentifier, ISBNExtractor
from core.ebook.metadata import MetadataService
from core.ebook.metadata.providers import GoogleBooksProvider, OpenLibraryProvider
from core.ebook.metadata.providers.provider import MetadataProvider
from core.ebook.models import AuditReport, EbookFormat, ProcessingResult
from core.ebook.normalization import EbookNormalizer, EpubValidator, MetadataEmbedder, TocGenerator
from core.ebook.organization import LibraryOrganizer, NamingService
from core.ebook.workflow import EbookProcessor
from utils.config import get_config
from utils.epub_reader import EpubReader
from utils.epub_writer import EpubWriter
from utils.fuzzy_matcher import FuzzyMatcher
from utils.pdf_reader import PdfReader

app = typer.Typer(help="Process and normalize ebook files.")
console = Console()


@dataclass(frozen=True)
class EbookServiceBundle:
    identifier: BookIdentifier
    metadata_service: MetadataService
    cover_service: CoverService
    normalizer: EbookNormalizer
    isbn_extractor: ISBNExtractor
    fuzzy_matcher: FuzzyMatcher


def _print_ebook_config_summary() -> None:
    config = get_config()
    ebook = config.ebook

    typer.echo("\n[ebook] active configuration")
    typer.echo(f"  preferred_format: {ebook.preferred_format}")
    typer.echo(f"  download_cover: {ebook.download_cover}")
    typer.echo(f"  metadata_providers: {', '.join(ebook.metadata_providers)}")
    typer.echo(f"  organization.structure: {ebook.organization.structure}")
    typer.echo(f"  conversion.target_format: {ebook.conversion.target_format}")


def _build_services() -> EbookServiceBundle:
    config = get_config()
    googlebooks_api_key = config.api.googlebooks_api_key

    epub_reader = EpubReader()
    pdf_reader = PdfReader()
    isbn_extractor = ISBNExtractor(epub_reader=epub_reader, pdf_reader=pdf_reader)
    fuzzy_matcher = FuzzyMatcher()
    identifier = BookIdentifier(isbn_extractor=isbn_extractor, epub_reader=epub_reader)

    metadata_providers: list[MetadataProvider] = []
    for provider_name in config.ebook.metadata_providers:
        if provider_name == "openlibrary":
            metadata_providers.append(OpenLibraryProvider())
        elif provider_name == "googlebooks":
            metadata_providers.append(GoogleBooksProvider(api_key=googlebooks_api_key))
    if not metadata_providers:
        metadata_providers = [OpenLibraryProvider(), GoogleBooksProvider(api_key=googlebooks_api_key)]
    metadata_service = MetadataService(metadata_providers, fuzzy_matcher)

    cover_provider_map: dict[str, type[CoverProvider]] = {
        "openlibrary": OpenLibraryCoverProvider,
        "googlebooks": GoogleBooksCoverProvider,
    }
    cover_providers: list[CoverProvider] = []
    for provider_name in config.ebook.metadata_providers:
        cover_provider_cls = cover_provider_map.get(provider_name)
        if cover_provider_cls is not None:
            cover_providers.append(cover_provider_cls())
    if not cover_providers:
        cover_providers = [OpenLibraryCoverProvider(), GoogleBooksCoverProvider()]

    epub_writer = EpubWriter()
    cover_service = CoverService(cover_providers, CoverSelector(), epub_writer)
    normalizer = EbookNormalizer(
        metadata_embedder=MetadataEmbedder(epub_writer),
        cover_service=cover_service,
        toc_generator=TocGenerator(epub_writer),
        epub_validator=EpubValidator(epub_reader),
    )

    return EbookServiceBundle(
        identifier=identifier,
        metadata_service=metadata_service,
        cover_service=cover_service,
        normalizer=normalizer,
        isbn_extractor=isbn_extractor,
        fuzzy_matcher=fuzzy_matcher,
    )


def _collect_ebooks(path: Path, recursive: bool = True) -> list[Path]:
    extensions = {".epub", ".mobi", ".azw3", ".azw", ".pdf"}
    if path.is_file():
        return [path] if path.suffix.lower() in extensions else []
    pattern = "**/*" if recursive else "*"
    return sorted([item for item in path.glob(pattern) if item.is_file() and item.suffix.lower() in extensions])


def _display_processing_results(results: list[ProcessingResult]) -> None:
    table = Table(title="Processing Results")
    table.add_column("File", style="cyan")
    table.add_column("Operations", justify="right")
    table.add_column("Status")

    for result in results:
        status = "[green]OK[/green]" if result.success else "[red]FAIL[/red]"
        table.add_row(result.ebook_path.name, str(result.operations_completed), status)

    console.print(table)
    successful = len([item for item in results if item.success])
    console.print(f"Successful: {successful}/{len(results)}")


def _display_issue_table(title: str, paths: list[Path]) -> None:
    if not paths:
        return
    table = Table(title=title)
    table.add_column("File", style="yellow")
    table.add_column("Directory", style="dim")
    for item in paths[:20]:
        table.add_row(item.name, str(item.parent))
    console.print(table)
    if len(paths) > 20:
        console.print(f"... and {len(paths) - 20} more")


def _display_format_distribution(report: AuditReport) -> None:
    if not report.format_distribution:
        return
    table = Table(title="Format Distribution")
    table.add_column("Format")
    table.add_column("Count", justify="right")
    for suffix, count in sorted(report.format_distribution.items()):
        table.add_row(suffix, str(count))
    console.print(table)


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


@app.command("identify")
def identify(path: Path = typer.Argument(..., help="E-book file to identify")) -> None:
    """Identify one ebook and display title, author, ISBN, confidence, and source."""
    if not path.exists() or not path.is_file():
        console.print(f"[red]File not found:[/red] {path}")
        raise typer.Exit(1)

    bundle = _build_services()
    identity = bundle.identifier.identify(path)

    table = Table(title=f"Book Identity: {path.name}")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("Title", identity.title)
    table.add_row("Author", identity.author)
    table.add_row("ISBN", identity.isbn or "Not found")
    table.add_row("Confidence", f"{identity.confidence_score:.0%}")
    table.add_row("Source", identity.source)
    console.print(table)


@app.command("enrich")
def enrich(
    path: Path = typer.Argument(..., help="E-book file or directory"),
    metadata: bool = typer.Option(True, "--metadata/--no-metadata", help="Fetch metadata"),
    cover: bool = typer.Option(True, "--cover/--no-cover", help="Download cover"),
    normalize: bool = typer.Option(True, "--normalize/--no-normalize", help="Normalize EPUB structure"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", help="Scan directories recursively"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Simulate without changing files"),
) -> None:
    """Run enrichment workflow: identify, fetch metadata/cover, and normalize."""
    if not path.exists():
        console.print(f"[red]Path not found:[/red] {path}")
        raise typer.Exit(1)

    files = _collect_ebooks(path, recursive=recursive)
    if not files:
        console.print("[yellow]No supported e-book files found[/yellow]")
        return

    bundle = _build_services()
    processor = EbookProcessor(
        book_identifier=bundle.identifier,
        metadata_service=bundle.metadata_service,
        cover_service=bundle.cover_service,
        normalizer=bundle.normalizer,
    )

    results: list[ProcessingResult] = []
    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), console=console
    ) as progress:
        task = progress.add_task("Enriching books...", total=len(files))
        for file_path in files:
            results.append(
                processor.enrich(
                    ebook_path=file_path,
                    fetch_metadata=metadata,
                    fetch_cover=cover,
                    normalize=normalize,
                    dry_run=dry_run,
                )
            )
            progress.advance(task)

    _display_processing_results(results)


@app.command("organize")
def organize(
    source: Path = typer.Argument(..., help="Source file or directory"),
    library: Path = typer.Argument(..., help="Library root target"),
    copy: bool = typer.Option(False, "--copy", help="Copy files instead of moving"),
    metadata: bool = typer.Option(True, "--metadata/--no-metadata", help="Fetch metadata for better naming"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", help="Scan directories recursively"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Simulate without changing files"),
) -> None:
    """Organize books into Jellyfin-compatible Author/Series/Book structure."""
    if not source.exists():
        console.print(f"[red]Source not found:[/red] {source}")
        raise typer.Exit(1)

    bundle = _build_services()
    organizer = LibraryOrganizer(NamingService(), dry_run=dry_run)
    processor = EbookProcessor(
        book_identifier=bundle.identifier,
        metadata_service=bundle.metadata_service,
        cover_service=bundle.cover_service,
        normalizer=bundle.normalizer,
        organizer=organizer,
    )

    results = processor.organize_library(
        source_path=source,
        library_root=library,
        fetch_metadata=metadata,
        copy_instead_of_move=copy,
        dry_run=dry_run,
        recursive=recursive,
    )
    _display_processing_results(results)


@app.command("audit")
def audit(
    library: Path = typer.Argument(..., help="Library directory"),
    output: Path | None = typer.Option(None, "--output", help="Write summary to file"),
    covers: bool = typer.Option(True, "--covers/--no-covers", help="Check cover availability"),
    series: bool = typer.Option(True, "--series/--no-series", help="Analyze series completeness"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", help="Scan directories recursively"),
) -> None:
    """Audit library for metadata, cover, format, and series quality issues."""
    if not library.exists() or not library.is_dir():
        console.print(f"[red]Library not found:[/red] {library}")
        raise typer.Exit(1)

    bundle = _build_services()
    auditor = LibraryAuditor(
        book_identifier=bundle.identifier,
        metadata_service=bundle.metadata_service,
        isbn_extractor=bundle.isbn_extractor,
        epub_reader=EpubReader(),
    )

    with console.status("Auditing library..."):
        report = auditor.audit(library, recursive=recursive, check_covers=covers, check_series=series)

    console.print("\n" + report.summary())
    _display_format_distribution(report)
    _display_issue_table("Missing Metadata", report.missing_metadata)
    _display_issue_table("Missing Cover", report.missing_cover)
    _display_issue_table("Missing ISBN", report.missing_isbn)
    _display_issue_table("Broken Files", report.broken_files)

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report.summary(), encoding="utf-8")
        console.print(f"[green]Saved report:[/green] {output}")


@app.command("deduplicate")
def deduplicate(
    library: Path = typer.Argument(..., help="Library directory"),
    delete: bool = typer.Option(False, "--delete", help="Delete non-best duplicates"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show duplicates without deleting"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", help="Scan directories recursively"),
) -> None:
    """Find duplicate groups and optionally remove lower-quality versions."""
    if not library.exists() or not library.is_dir():
        console.print(f"[red]Library not found:[/red] {library}")
        raise typer.Exit(1)

    bundle = _build_services()
    finder = DuplicateFinder(
        isbn_extractor=bundle.isbn_extractor,
        book_identifier=bundle.identifier,
        version_comparator=VersionComparator(),
        fuzzy_matcher=bundle.fuzzy_matcher,
    )

    duplicates = finder.find_duplicates(library, recursive=recursive)
    if not duplicates:
        console.print("[green]No duplicates found[/green]")
        return

    for index, group in enumerate(duplicates, 1):
        table = Table(title=f"Duplicate Group {index}")
        table.add_column("File")
        table.add_column("Status")
        table.add_column("Confidence", justify="right")
        for file_path in group.books:
            keep = file_path == group.best_version
            table.add_row(file_path.name, "KEEP" if keep else "REMOVE", f"{group.match_confidence:.0%}")
        console.print(table)
        console.print(f"Reason: {group.reason}")

    if delete and not dry_run:
        if not typer.confirm("Delete non-best duplicate files?"):
            return
        deleted = 0
        for group in duplicates:
            for file_path in group.books:
                if file_path == group.best_version:
                    continue
                try:
                    file_path.unlink(missing_ok=False)
                    deleted += 1
                except OSError as exc:
                    console.print(f"[red]Delete failed:[/red] {file_path} ({exc})")
        console.print(f"[green]Deleted {deleted} duplicate files[/green]")


@app.command("convert")
def convert(
    path: Path = typer.Argument(..., help="File or directory"),
    format: str = typer.Argument(..., help="Target format: epub, mobi, azw3"),
    profile: str | None = typer.Option(None, "--profile", help="Profile name such as kindle_high"),
    output: Path | None = typer.Option(None, "--output", help="Optional output directory"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", help="Scan directories recursively"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Simulate conversion operations"),
) -> None:
    """Convert ebook formats using Calibre with optional quality profiles."""
    if not path.exists():
        console.print(f"[red]Path not found:[/red] {path}")
        raise typer.Exit(1)

    target_format = EbookFormat.from_extension(format)
    if target_format is None or target_format not in {EbookFormat.EPUB, EbookFormat.MOBI, EbookFormat.AZW3}:
        console.print("[red]Invalid target format. Use epub, mobi, or azw3.[/red]")
        raise typer.Exit(1)

    try:
        calibre = CalibreRunner()
    except CalibreNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)

    converter = FormatConverter(calibre_runner=calibre, dry_run=dry_run)
    selected_profile = ConversionProfiles.get_profile(profile) if profile else None
    if profile and selected_profile is None:
        console.print(f"[red]Unknown profile:[/red] {profile}")
        raise typer.Exit(1)

    files = _collect_ebooks(path, recursive=recursive)
    if not files:
        console.print("[yellow]No supported files found[/yellow]")
        return

    results = []
    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), console=console
    ) as progress:
        task = progress.add_task("Converting books...", total=len(files))
        for file_path in files:
            results.append(
                converter.convert(
                    input_path=file_path,
                    output_format=target_format,
                    profile=selected_profile,
                    output_dir=output,
                    create_backup=True,
                )
            )
            progress.advance(task)

    successful = len([item for item in results if item.success])
    failed = len(results) - successful
    console.print(f"[green]Conversion complete:[/green] {successful} succeeded, {failed} failed")
