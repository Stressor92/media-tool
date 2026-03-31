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
    source_lang: Annotated[str, typer.Option("--from", help="Source language: de | en | auto")] = "en",
    target_lang: Annotated[str, typer.Option("--to", help="Target language: de | en")] = "de",
    backend: Annotated[str, typer.Option(help="Translation backend: opus-mt | argos")] = "opus-mt",
    model_size: Annotated[str, typer.Option(help="Model size: standard | big")] = "big",
    recursive: Annotated[bool, typer.Option("-r/--recursive", help="Process subdirectories recursively")] = False,
    overwrite: Annotated[bool, typer.Option(help="Overwrite existing output files")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would be done without writing files")] = False,
    chunk_size: Annotated[int, typer.Option(help="Segments per context chunk (improves grammar)")] = 4,
    no_line_wrap: Annotated[bool, typer.Option("--no-line-wrap", help="Disable automatic line wrapping")] = False,
    max_line_length: Annotated[int, typer.Option(help="Max characters per subtitle line")] = 40,
    no_tags: Annotated[bool, typer.Option("--no-tags", help="Disable HTML/ASS tag preservation")] = False,
    auto_detect: Annotated[bool, typer.Option("--auto-detect", help="Auto-detect source language (requires: pip install langdetect)")] = False,
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

    auto_src = source_lang == "auto"
    effective_src = "en" if auto_src else source_lang
    pair = LanguagePair(source=effective_src, target=target_lang)
    translator = SubtitleTranslator(
        chunk_size=chunk_size,
        preserve_tags=not no_tags,
        line_wrap=not no_line_wrap,
        max_line_length=max_line_length,
        auto_detect_language=auto_detect or auto_src,
    )
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


# Default model directory: <repo>/src/utils/translate_models
_DEFAULT_MODEL_DIR = Path(__file__).parent.parent / "utils" / "translate_models"

# Available models per direction.
# For en→de there is a tc-big model (transformer-big, BLEU ~43.7 vs ~35 standard).
# For de→en no separate big variant exists.
_ALL_MODELS: dict[str, str] = {
    "Helsinki-NLP/opus-mt-en-de":      "en→de Standard (~300 MB, BLEU ~35)",
    "gsarti/opus-mt-tc-big-en-de":     "en→de Big    (~900 MB, BLEU ~44, empfohlen)",
    "Helsinki-NLP/opus-mt-de-en":      "de→en Standard (~300 MB)",
}


@app.command("download-models")
def download_models(
    model_dir: Annotated[
        Optional[Path],
        typer.Option("--model-dir", "-d", help="Zielordner für die Modelle."),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Bereits vorhandene Modelle neu herunterladen."),
    ] = False,
) -> None:
    """
    Lade OPUS-MT Übersetzungsmodelle lokal herunter.

    Die Modelle werden automatisch vom HuggingFace Hub geladen und ins
    CTranslate2-Format konvertiert.  Danach ist keine Internetverbindung
    mehr nötig.

    Standardpfad: src/utils/translate_models/

    Modelle:
      Helsinki-NLP/opus-mt-en-de       en→de Standard (~300 MB, BLEU ~35)
      gsarti/opus-mt-tc-big-en-de      en→de Big    (~900 MB, BLEU ~44)  ← empfohlen
      Helsinki-NLP/opus-mt-de-en       de→en Standard (~300 MB)

    Beispiele:
        # Alle drei Modelle herunterladen (empfohlen beim ersten Setup)
        media-tool subtitle download-models

        # Eigener Pfad
        media-tool subtitle download-models --model-dir D:\\models\\translation
    """
    try:
        import ctranslate2
        from transformers import MarianTokenizer
    except ImportError:
        console.print(
            "[red]Fehlende Abhängigkeiten.[/red]\n"
            "Bitte installieren: [bold]pip install ctranslate2 transformers sentencepiece[/bold]"
        )
        raise typer.Exit(1)

    # Helsinki-NLP models on HuggingFace are in MarianMT (transformers) format
    # → use TransformersConverter, NOT OpusMTConverter (which expects native Marian format)
    TransformersConverter = ctranslate2.converters.TransformersConverter

    target_dir = model_dir or _DEFAULT_MODEL_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"[bold]Zielordner:[/bold] {target_dir}")
    console.print(f"[bold]Modelle:[/bold] {len(_ALL_MODELS)}\n")

    errors: list[str] = []
    for model_name, description in _ALL_MODELS.items():
        model_dir_path = target_dir / model_name.replace("/", "--")

        # A model is considered "present" only when conversion produced model.bin
        model_ready = (model_dir_path / "model.bin").exists()
        if model_ready and not force:
            console.print(f"  [dim]–[/dim] {description} [dim](bereits vorhanden)[/dim]")
            continue

        console.print(f"  [cyan]↓[/cyan] {description} …")
        try:
            # Remove any leftover partial directory so converter can start fresh
            if model_dir_path.exists():
                import shutil
                shutil.rmtree(model_dir_path)
            converter = TransformersConverter(model_name, low_cpu_mem_usage=True)
            converter.convert(str(model_dir_path))
            # Tokenizer (vocab files) neben dem Modell speichern
            MarianTokenizer.from_pretrained(model_name).save_pretrained(str(model_dir_path))
            console.print(f"  [green]✓[/green] {description} → {model_dir_path.name}")
        except Exception as exc:
            console.print(f"  [red]✗[/red] {model_name}: {exc}")
            errors.append(model_name)
            if model_dir_path.exists():
                import shutil
                shutil.rmtree(model_dir_path, ignore_errors=True)

    console.print()
    if errors:
        console.print(f"[red]Fehler bei {len(errors)} Modell(en): {', '.join(errors)}[/red]")
        raise typer.Exit(1)
    else:
        console.print(f"[green bold]Alle Modelle bereit in:[/green bold] {target_dir}")


@app.command("convert")
def convert_subtitle(
    path: Annotated[Path, typer.Argument(help="Subtitle file or directory")],
    to: Annotated[str, typer.Option(help="Target format: srt | ass | vtt | ttml | scc | stl | lrc | sbv")],
    output: Annotated[Optional[Path], typer.Option("-o", help="Output file or directory")] = None,
    recursive: Annotated[bool, typer.Option("-r/--recursive", help="Process subdirectories recursively")] = False,
    overwrite: Annotated[bool, typer.Option(help="Overwrite existing output files")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would be done without writing files")] = False,
) -> None:
    """
    Convert subtitles between all supported formats.

    Examples:
        media-tool subtitle convert movie.srt --to vtt
        media-tool subtitle convert broadcast.stl --to srt
        media-tool subtitle convert "C:\\Subs" -r --to srt
        media-tool subtitle convert captions.scc --to ttml -o output.ttml
    """
    from core.translation.converter import ConversionStatus, SubtitleConverter
    from core.translation.models import SubtitleFormat

    try:
        target_fmt = SubtitleFormat(to.lower())
    except ValueError:
        valid = [f.value for f in SubtitleFormat if f.is_text_based]
        typer.echo(f"❌ Unknown format '{to}'. Valid: {valid}", err=True)
        raise typer.Exit(1)

    subtitle_exts = {".srt", ".ass", ".ssa", ".vtt", ".ttml", ".dfxp",
                     ".scc", ".stl", ".lrc", ".sbv"}

    files: list[Path] = []
    if path.is_file():
        files = [path]
    elif path.is_dir():
        pattern = "**/*" if recursive else "*"
        files = [f for f in path.glob(pattern) if f.suffix.lower() in subtitle_exts]

    if not files:
        typer.echo("ℹ️  No subtitle files found.")
        return

    converter = SubtitleConverter()
    success = skipped = failed = 0

    for f in files:
        if output and output.is_dir():
            out: Optional[Path] = output / f.with_suffix(f".{to}").name
        else:
            out = output
        result = converter.convert(f, target_fmt, output_path=out,
                                   overwrite=overwrite, dry_run=dry_run)
        match result.status:
            case ConversionStatus.SUCCESS:
                out_name = result.output_path.name if result.output_path else "?"
                typer.echo(f"✅  {f.name} → {out_name} ({result.segments_converted} segments)")
                success += 1
            case ConversionStatus.SKIPPED:
                typer.echo(f"⏭️   {f.name} ({result.error_message})")
                skipped += 1
            case ConversionStatus.FAILED:
                typer.echo(f"❌  {f.name}: {result.error_message}", err=True)
                failed += 1

    typer.echo(f"\n{success} converted · {skipped} skipped · {failed} failed")
    if failed:
        raise typer.Exit(1)


@app.command("formats")
def list_formats() -> None:
    """Show all supported subtitle formats with read/write status."""
    from core.translation.format_registry import FormatRegistry
    from core.translation.models import SubtitleFormat

    read_fmts  = set(FormatRegistry.supported_read_formats())
    write_fmts = set(FormatRegistry.supported_write_formats())

    typer.echo("\n── Supported Subtitle Formats ──────────────────────────")
    typer.echo(f"  {'Format':<12} {'Read':<8} {'Write':<10} Description")
    typer.echo("  " + "─" * 55)

    descriptions = {
        SubtitleFormat.SRT:  "SubRip – universal standard",
        SubtitleFormat.ASS:  "Advanced SubStation Alpha – Anime, styling",
        SubtitleFormat.VTT:  "WebVTT – HTML5 / browser",
        SubtitleFormat.TTML: "TTML/DFXP – broadcast (Netflix, ARD)",
        SubtitleFormat.SCC:  "SCC – US-TV closed captions (CEA-608)",
        SubtitleFormat.STL:  "EBU STL – European broadcast TV",
        SubtitleFormat.LRC:  "LRC – music/karaoke lyric sync",
        SubtitleFormat.SBV:  "SBV – YouTube auto-captions",
        SubtitleFormat.SUB:  "VobSub – DVD bitmap (read + OCR only)",
        SubtitleFormat.SUP:  "PGS/SUP – Blu-ray bitmap (read + OCR only)",
    }

    for fmt in SubtitleFormat:
        if fmt in (SubtitleFormat.UNKNOWN, SubtitleFormat.SSA, SubtitleFormat.DFXP):
            continue
        r = "✅" if fmt in read_fmts else "❌"
        w = "✅" if fmt in write_fmts else "❌"
        desc = descriptions.get(fmt, "")
        typer.echo(f"  {fmt.value:<12} {r:<8} {w:<10} {desc}")
    typer.echo("")


if __name__ == "__main__":
    app()