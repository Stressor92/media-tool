"""
src/cli/merge_cmd.py

CLI interface for the dual-audio merge workflow (DE + EN → single MKV).
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

import typer
from rich import box
from rich.console import Console
from rich.table import Table
from rich.text import Text

from core.video import convert_mp4_to_mkv, derive_output_name, merge_directory, merge_dual_audio

app = typer.Typer(help="Merge German + English MP4 files into one dual-audio MKV.")
console = Console()
err_console = Console(stderr=True, style="bold red")


_LANG_SUFFIX_PATTERN = re.compile(
    r"(?:[-_ \(\[](?P<lang>de|german|deutsch|en|english|jp|jpn|japanese|nihongo)[\)\]_ ]?)$",
    re.IGNORECASE,
)


def _detect_lang_and_basename(file_path: Path) -> tuple[str | None, str]:
    """Return (lang, base_name) from a file stem based on known suffix patterns."""
    stem = file_path.stem
    match = _LANG_SUFFIX_PATTERN.search(stem)
    if not match:
        return None, stem

    lang_raw = match.group("lang").lower()
    if lang_raw in {"de", "german", "deutsch"}:
        lang = "deu"
    elif lang_raw in {"jp", "jpn", "japanese", "nihongo"}:
        lang = "jpn"
    else:
        lang = "eng"
    # Only trim separators, not title punctuation like closing ')' in years.
    base = _LANG_SUFFIX_PATTERN.sub("", stem).strip(" -_")
    return lang, (base or stem)


def _status_text(status: str) -> Text:
    if status == "merged":
        return Text("✔ merged", style="bold green")
    if status == "single":
        return Text("✔ single->mkv", style="green")
    if status == "skipped":
        return Text("⏭ skipped", style="yellow")
    return Text("✘ failed", style="bold red")


@app.command("auto")
def auto_command(
    directory: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help=(
            "Directory containing the two language-specific MP4 files. "
            "Language is detected from filename suffixes: -de/_de/(de) and -en/_en/(en)."
        ),
    ),
    overwrite: bool = typer.Option(False, "--overwrite", help="Re-merge even if the target MKV already exists."),
) -> None:
    """
    Auto-detect DE/EN MP4 files in DIRECTORY and merge them into one MKV.

    Expected filenames (examples):
      Movie Title-de.mp4 + Movie Title-en.mp4
      Movie Title_de.mp4 + Movie Title_en.mp4
      Movie Title (de).mp4 + Movie Title (en).mp4
    """
    console.rule("[bold cyan]media-tool · merge auto[/bold cyan]")
    console.print(f"[dim]Directory:[/dim] {directory}")

    result = merge_directory(directory, overwrite=overwrite)

    if result.succeeded:
        console.print(f"\n[bold green]✔  {result.message}[/bold green]")
        console.print(f"[dim]  German :[/dim] {result.german_source.name if result.german_source else '?'}")
        console.print(f"[dim]  English:[/dim] {result.english_source.name if result.english_source else '?'}")
        console.print(f"[dim]  Output :[/dim] {result.target.name}")
    elif result.skipped:
        console.print(f"\n[yellow]⏭  {result.message}[/yellow]")
    else:
        err_console.print(f"\n✘  {result.message}")
        if result.ffmpeg_result:
            stderr_tail = "\n".join(result.ffmpeg_result.stderr.splitlines()[-20:])
            console.print(f"\n[dim]ffmpeg stderr (tail):[/dim]\n{stderr_tail}", highlight=False)
        raise typer.Exit(code=1)


@app.command("batch")
def batch_command(
    directory: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help=(
            "Directory with many MP4 files. "
            "If <title>-de + <title>-en exist, create one dual-audio MKV. "
            "If only one file exists for a title, remux it to MKV as German audio."
        ),
    ),
    output_dir: Path | None = typer.Option(
        None,
        "--output-dir",
        "-o",
        file_okay=False,
        dir_okay=True,
        writable=True,
        help="Optional output directory for generated MKV files (e.g. another drive).",
    ),
    overwrite: bool = typer.Option(False, "--overwrite", help="Re-process even if target MKV already exists."),
) -> None:
    """
    Batch mode for folders with many MP4 files.

    Rules per detected title group:
      1) DE + EN present  -> merge to one dual-audio MKV
      2) exactly one file -> convert to MKV and tag audio as German (deu)
      3) other cases      -> skip and report
    """
    console.rule("[bold cyan]media-tool · merge batch[/bold cyan]")
    console.print(f"[dim]Directory:[/dim] {directory}")
    output_root = output_dir or directory
    output_root.mkdir(parents=True, exist_ok=True)
    if output_dir is not None:
        console.print(f"[dim]Output:[/dim] {output_root}")

    mp4_files = sorted(directory.glob("*.mp4"))
    if not mp4_files:
        console.print("[yellow]No .mp4 files found.[/yellow]")
        raise typer.Exit(code=0)

    groups: dict[str, dict[str, list[Path]]] = defaultdict(lambda: {"deu": [], "eng": [], "jpn": [], "other": []})
    for file_path in mp4_files:
        lang, base = _detect_lang_and_basename(file_path)
        if lang == "deu":
            groups[base]["deu"].append(file_path)
        elif lang == "eng":
            groups[base]["eng"].append(file_path)
        elif lang == "jpn":
            groups[base]["jpn"].append(file_path)
        else:
            groups[base]["other"].append(file_path)

    table = Table(title="Merge Batch Summary", box=box.ROUNDED, show_lines=True, expand=True)
    table.add_column("Title", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Source(s)")
    table.add_column("Target")
    table.add_column("Message")

    success_count = 0
    failed_count = 0
    skipped_count = 0

    for title in sorted(groups):
        group = groups[title]
        de_files = sorted(group["deu"])
        en_files = sorted(group["eng"])
        jp_files = sorted(group["jpn"])
        other_files = sorted(group["other"])
        target = output_root / title / f"{title}.mkv"

        if de_files and en_files:
            # Deterministic selection if duplicates exist.
            de_file = de_files[0]
            en_file = en_files[0]
            result = merge_dual_audio(de_file, en_file, target, overwrite=overwrite)
            status = "merged" if result.succeeded else ("skipped" if result.skipped else "failed")
            source_text = f"{de_file.name} + {en_file.name}"
            message = result.message
        elif de_files and jp_files:
            # Merge German + Japanese audio.
            de_file = de_files[0]
            jp_file = jp_files[0]
            result = merge_dual_audio(de_file, jp_file, target, overwrite=overwrite)
            status = "merged" if result.succeeded else ("skipped" if result.skipped else "failed")
            source_text = f"{de_file.name} + {jp_file.name}"
            message = result.message
        else:
            candidates = de_files + jp_files + en_files + other_files
            if len(candidates) == 1:
                source = candidates[0]
                # Determine audio language and title based on detected language
                lang, _ = _detect_lang_and_basename(source)
                audio_lang = "jpn" if lang == "jpn" else ("eng" if lang == "eng" else "deu")
                audio_title = "Japanisch" if lang == "jpn" else ("English" if lang == "eng" else "Deutsch")
                conv = convert_mp4_to_mkv(
                    source=source,
                    target=target,
                    audio_language=audio_lang,
                    audio_title=audio_title,
                    overwrite=overwrite,
                )
                status = "single" if conv.succeeded else ("skipped" if conv.skipped else "failed")
                source_text = source.name
                message = conv.message
            else:
                status = "skipped"
                source_text = ", ".join(f.name for f in candidates) if candidates else "-"
                message = "No clear DE/EN or DE/JP pair and not a single-file group."

        if status in {"merged", "single"}:
            success_count += 1
        elif status == "failed":
            failed_count += 1
        else:
            skipped_count += 1

        table.add_row(title, _status_text(status), source_text, target.name, message)

    console.print(table)
    console.print(
        f"\n[bold]Groups:[/bold] {len(groups)}  "
        f"[green]Processed: {success_count}[/green]  "
        f"[yellow]Skipped: {skipped_count}[/yellow]  "
        f"[red]Failed: {failed_count}[/red]"
    )

    if failed_count > 0:
        raise typer.Exit(code=1)


@app.command("manual")
def manual_command(
    german: Path = typer.Argument(
        ..., exists=True, file_okay=True, dir_okay=False, help="Path to the German-audio MP4 file."
    ),
    english: Path = typer.Argument(
        ..., exists=True, file_okay=True, dir_okay=False, help="Path to the English-audio MP4 file."
    ),
    target: Path | None = typer.Option(
        None,
        "--target",
        "-t",
        help="Output .mkv path. Defaults to <german_parent>/<clean_title>.mkv",
    ),
    overwrite: bool = typer.Option(False, "--overwrite", help="Re-merge even if the target MKV already exists."),
) -> None:
    """
    Merge two explicitly specified MP4 files into one dual-audio MKV.
    """
    console.rule("[bold cyan]media-tool · merge manual[/bold cyan]")

    resolved_target = target or (german.parent / f"{derive_output_name(german)}.mkv")

    console.print(f"[dim]German :[/dim] {german}")
    console.print(f"[dim]English:[/dim] {english}")
    console.print(f"[dim]Target :[/dim] {resolved_target}")

    result = merge_dual_audio(german, english, resolved_target, overwrite=overwrite)

    if result.succeeded:
        console.print(f"\n[bold green]✔  {result.message}[/bold green]")
    elif result.skipped:
        console.print(f"\n[yellow]⏭  {result.message}[/yellow]")
    else:
        err_console.print(f"\n✘  {result.message}")
        if result.ffmpeg_result:
            stderr_tail = "\n".join(result.ffmpeg_result.stderr.splitlines()[-20:])
            console.print(f"\n[dim]ffmpeg stderr (tail):[/dim]\n{stderr_tail}", highlight=False)
        raise typer.Exit(code=1)
