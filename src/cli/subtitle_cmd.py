"""
src/cli/subtitle_cmd.py

CLI commands for subtitle operations.
Provides download and search functionality for subtitles.
"""

from __future__ import annotations

import typer
from pathlib import Path
from typing import Annotated, Optional

from rich.console import Console

from core.subtitles.opensubtitles_provider import OpenSubtitlesProvider
from core.subtitles.subtitle_provider import MovieInfo
from core.subtitles.subtitle_downloader import SubtitleDownloadManager
from utils.config import build_missing_config_hint, get_config, has_config_file
from utils.video_hasher import VideoHasher
from utils.ffmpeg_runner import FFmpegMuxer
from utils.ffprobe_runner import probe_file

app = typer.Typer(help="Download and manage subtitles. Use 'download' to fetch from OpenSubtitles.org, 'search' to check availability.")
console = Console()


@app.command()
def download(
    path: Path = typer.Argument(..., help="MKV file or directory"),
    languages: str | None = typer.Option(None, help="Comma-separated language codes (en,de,fr). Defaults to config."),
    auto: bool = typer.Option(True, help="Auto-select best match"),
    embed: bool = typer.Option(True, help="Embed into MKV (vs external file)"),
    interactive: bool = typer.Option(False, help="Show matches and let user choose"),
    recursive: bool = typer.Option(True, help="Process directories recursively"),
    overwrite: bool = typer.Option(False, help="Overwrite existing subtitles"),
    api_key: str | None = typer.Option(None, envvar="OPENSUBTITLES_API_KEY")
) -> None:
    """
    Download subtitles from OpenSubtitles.org

    Examples:
        # Single file, auto-download English
        media-tool subtitle download movie.mkv

        # Multiple languages (priority order)
        media-tool subtitle download movie.mkv --languages en,de

        # Interactive selection
        media-tool subtitle download movie.mkv --interactive

        # Process entire directory
        media-tool subtitle download /path/to/movies
    """

    config = get_config()
    resolved_api_key = api_key or config.api.opensubtitles_api_key
    resolved_languages = languages or ",".join(config.defaults.subtitles.languages)

    if not resolved_api_key:
        console.print("[red]Error: OpenSubtitles API key required[/red]")
        console.print("Get your free key at: https://www.opensubtitles.com/api")
        if has_config_file():
            console.print("Set it in media-tool.toml under [api].opensubtitles_api_key or pass --api-key.")
        else:
            console.print(build_missing_config_hint())
        console.print("Legacy env override still works: OPENSUBTITLES_API_KEY=your_key")
        raise typer.Exit(1)

    # Setup components
    provider = OpenSubtitlesProvider(
        resolved_api_key,
        user_agent=config.api.opensubtitles_user_agent,
    )
    ffmpeg_runner = FFmpegMuxer()
    manager = SubtitleDownloadManager(provider, ffmpeg_runner)

    # Parse languages
    language_list = [lang.strip() for lang in resolved_languages.split(",") if lang.strip()]

    # Get files to process
    if path.is_file():
        files = [path]
    else:
        pattern = "**/*.mkv" if recursive else "*.mkv"
        files = list(path.glob(pattern))

    if not files:
        console.print(f"[yellow]No MKV files found in {path}[/yellow]")
        return

    console.print(f"Processing {len(files)} file(s)...")

    # Process each file
    success_count = 0
    for file in files:
        try:
            result = manager.process(
                file,
                languages=language_list,
                auto_select=not interactive,
                embed=embed,
                overwrite=overwrite
            )

            if result.success:
                console.print(f"[green]✓[/green] {file.name}: {result.message}")
                success_count += 1
            else:
                console.print(f"[red]✗[/red] {file.name}: {result.message}")

                # Suggest Whisper fallback
                if result.fallback_suggestion == "whisper":
                    console.print(f"  [yellow]→ Try: media-tool subtitle generate {file}[/yellow]")

        except Exception as e:
            console.print(f"[red]✗[/red] {file.name}: Unexpected error - {e}")

    # Summary
    console.print(f"\n[bold]Summary:[/bold] {success_count}/{len(files)} files processed successfully")


@app.command()
def search(
    path: Path = typer.Argument(..., help="MKV file to search subtitles for"),
    languages: str | None = typer.Option(None, help="Comma-separated language codes. Defaults to config."),
    limit: int = typer.Option(10, help="Max results to show"),
    api_key: str | None = typer.Option(None, envvar="OPENSUBTITLES_API_KEY")
) -> None:
    """
    Search for available subtitles (without downloading)

    Useful for checking availability before batch processing
    """

    config = get_config()
    resolved_api_key = api_key or config.api.opensubtitles_api_key
    resolved_languages = languages or ",".join(config.defaults.subtitles.languages)

    if not resolved_api_key:
        console.print("[red]Error: OpenSubtitles API key required[/red]")
        console.print("Get your free key at: https://www.opensubtitles.com/api")
        if has_config_file():
            console.print("Set it in media-tool.toml under [api].opensubtitles_api_key or pass --api-key.")
        else:
            console.print(build_missing_config_hint())
        raise typer.Exit(1)

    # Setup
    provider = OpenSubtitlesProvider(
        resolved_api_key,
        user_agent=config.api.opensubtitles_user_agent,
    )
    hasher = VideoHasher()
    ffmpeg_runner = FFmpegMuxer()
    manager = SubtitleDownloadManager(provider, ffmpeg_runner)

    # Get movie info
    try:
        file_hash = hasher.calculate_hash(path)
        file_size = path.stat().st_size

        # Get duration
        probe_result = probe_file(path)
        duration = float(probe_result.format.get("duration", 0))

        movie_info = MovieInfo(
            file_path=path,
            file_hash=file_hash,
            file_size=file_size,
            duration=duration
        )
    except Exception as e:
        console.print(f"[red]Error analyzing file: {e}[/red]")
        raise typer.Exit(1)

    # Search
    language_list = [lang.strip() for lang in resolved_languages.split(",") if lang.strip()]
    matches = provider.search(movie_info, language_list, limit)

    if not matches:
        console.print(f"[red]No subtitles found for {path.name}[/red]")
        return

    # Display results in table
    from rich.table import Table

    table = Table(title=f"Subtitles for {path.name}")
    table.add_column("Language", style="cyan")
    table.add_column("Release", style="white", max_width=40)
    table.add_column("Rating", justify="right", style="green")
    table.add_column("Downloads", justify="right", style="yellow")
    table.add_column("Uploader", style="blue", max_width=20)
    table.add_column("Format", style="magenta")

    for match in matches:
        table.add_row(
            match.language.upper(),
            match.release_name[:40],
            f"{match.rating:.1f}",
            f"{match.download_count:,}",
            match.uploader[:20],
            match.format.upper()
        )

    console.print(table)
    console.print(f"\n[yellow]Found {len(matches)} subtitle(s)[/yellow]")

    # Show best match
    best = provider.get_best_match(matches)
    if best:
        console.print(f"[green]Best match:[/green] {best.release_name} ({best.rating:.1f}★, {best.download_count:,} downloads)")


@app.command("translate")
def translate_subtitle(
    path: Annotated[Path, typer.Argument(help="SRT/ASS/VTT file or directory")],
    source_lang: Annotated[str, typer.Option("--from", help="Source language: de | en")] = "en",
    target_lang: Annotated[str, typer.Option("--to", help="Target language: de | en")] = "de",
    backend: Annotated[str, typer.Option(help="Translation backend: opus-mt | argos")] = "opus-mt",
    model_size: Annotated[str, typer.Option(help="Model size: standard | big")] = "big",
    recursive: Annotated[bool, typer.Option("-r/--recursive", help="Process subdirectories recursively")] = False,
    overwrite: Annotated[bool, typer.Option(help="Overwrite existing output files")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would be done without writing files")] = False,
) -> None:
    """
    Translate subtitle files locally using an offline AI model.

    No internet connection or API key required.
    Primary backend: Helsinki-NLP OPUS-MT via CTranslate2 (GPU-accelerated).
    Fallback backend: argostranslate (CPU-only, no CUDA needed).

    Install GPU backend:   pip install ctranslate2 transformers sentencepiece
    Install CPU fallback:  pip install argostranslate

    Examples:
        # Single file: English → German
        media-tool subtitle translate movie.en.srt --from en --to de

        # Directory: recursively translate all English SRT/ASS/VTT files
        media-tool subtitle translate "C:\\Movies" -r --from en --to de

        # Preview without writing
        media-tool subtitle translate movie.en.srt --from en --to de --dry-run

        # CPU-only fallback (no CUDA required)
        media-tool subtitle translate movie.en.srt --from en --to de --backend argos
    """
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
    else:
        console.print(f"[red]Not a valid path: {path}[/red]", style="bold red")
        raise typer.Exit(1)

    if not files:
        console.print("[yellow]No subtitle files found.[/yellow]")
        return

    if dry_run:
        console.print("[yellow]DRY RUN — no files will be written[/yellow]")

    console.print(f"Processing {len(files)} file(s): [cyan]{pair}[/cyan] via [cyan]{backend}[/cyan]")

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
                console.print(f"  [red]✗[/red] {f.name}: {result.error_message}")
                failed += 1

    console.print(
        f"\n[bold]Summary:[/bold] {success} translated · {skipped} skipped · {failed} failed"
    )
    if failed:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()