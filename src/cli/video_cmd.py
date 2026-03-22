"""
src/cli/video_cmd.py

CLI interface for video processing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from core.video import (
    convert_mp4_to_mkv,
    scan_directory,
    merge_directory,
    upscale_dvd,
)

app = typer.Typer(help="Process video files.")
console = Console()
err_console = Console(stderr=True, style="bold red")


@app.command("convert")
def convert_command(
    input_file: Path = typer.Argument(
        ..., exists=True, file_okay=True, dir_okay=False, readable=True,
        help="Input video file to convert.",
    ),
    output_file: Path = typer.Argument(
        ..., file_okay=True, dir_okay=False,
        help="Output video file path.",
    ),
    language: Optional[str] = typer.Option(
        None, "--language", "-l",
        help="Set language metadata for audio/subtitle tracks (e.g., 'de', 'en').",
    ),
    audio_title: Optional[str] = typer.Option(
        None, "--audio-title", "-a",
        help="Set title for audio tracks.",
    ),
    subtitle_title: Optional[str] = typer.Option(
        None, "--subtitle-title", "-s",
        help="Set title for subtitle tracks.",
    ),
    default_audio: Optional[int] = typer.Option(
        None, "--default-audio", "-d",
        help="Set default audio track (1-based index).",
    ),
    remove_tracks: Optional[str] = typer.Option(
        None, "--remove-tracks", "-r",
        help="Remove specific tracks (e.g., 'a:2,s:1' for audio track 2 and subtitle track 1).",
    ),
    overwrite: bool = typer.Option(
        False, "--overwrite", "-y",
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
        ..., exists=True, file_okay=False, dir_okay=True, readable=True,
        help="Directory to scan for video files.",
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o",
        help="Output CSV file path. Defaults to <directory>/video_list.csv",
    ),
    recursive: bool = typer.Option(
        True, "--recursive/--no-recursive", "-r",
        help="Scan subdirectories (default: on).",
    ),
    preview: bool = typer.Option(
        False, "--preview", "-p",
        help="Print a Rich table preview of the first 20 results in the terminal.",
    ),
) -> None:
    """
    Scan media library and export metadata to CSV.
    """
    console.rule("[bold cyan]media-tool · video inspect[/bold cyan]")
    console.print(f"[dim]Directory:[/dim] {directory}")
    console.print(f"[dim]Recursive:[/dim] {recursive}")

    try:
        videos = scan_directory(
            directory=directory,
            recursive=recursive,
        )
    except Exception as e:
        err_console.print(f"Error: {e}")
        raise typer.Exit(code=1)

    if not videos:
        console.print("[yellow]No video files found.[/yellow]")
        return

    console.print(f"\n[green]✓[/green] Found {len(videos)} video files")

    # Count by type
    movies = sum(1 for v in videos if not any(x in v.file_name.lower() for x in ['s01', 's02', 'season']))
    tv_shows = len(videos) - movies
    other = 0  # Could be refined

    console.print(f"[dim]Movies:[/dim] {movies}")
    console.print(f"[dim]TV Shows:[/dim] {tv_shows}")
    console.print(f"[dim]Other:[/dim] {other}")

    # Export to CSV if requested
    if output:
        try:
            from core.video import export_to_csv
            export_to_csv(videos, output)
            console.print(f"[dim]Exported to:[/dim] {output}")
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
        ..., exists=True, file_okay=False, dir_okay=True, readable=True,
        help="Directory containing video files to merge.",
    ),
    output_file: Path = typer.Argument(
        ..., file_okay=True, dir_okay=False,
        help="Output merged video file path.",
    ),
    pattern: Optional[str] = typer.Option(
        None, "--pattern", "-p",
        help="File pattern to match (default: auto-detect German/English pairs).",
    ),
    language: Optional[str] = typer.Option(
        None, "--language", "-l",
        help="Set language metadata for merged tracks.",
    ),
    overwrite: bool = typer.Option(
        False, "--overwrite", "-y",
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
        console.print(f"[dim]German source:[/dim] {result.german_source.name}")
        console.print(f"[dim]English source:[/dim] {result.english_source.name}")
    else:
        err_console.print(f"\n[red]✘  Merge failed:[/red] {result.message}")
        if result.ffmpeg_result and result.ffmpeg_result.stderr:
            stderr_tail = "\n".join(result.ffmpeg_result.stderr.splitlines()[-20:])
            console.print(f"\n[dim]ffmpeg stderr (tail):[/dim]\n{stderr_tail}", highlight=False)
        raise typer.Exit(code=1)


@app.command("subtitle")
def subtitle_command(
    input_file: Path = typer.Argument(
        ..., exists=True, file_okay=True, dir_okay=False, readable=True,
        help="Input video file to generate subtitles for.",
    ),
    language: str = typer.Option(
        "en", "--language", "-l",
        help="Language code for transcription (e.g., 'en', 'de').",
    ),
    model: str = typer.Option(
        "large-v3", "--model", "-m",
        help="Whisper model to use (tiny, base, small, medium, large-v3).",
    ),
    output_file: Optional[Path] = typer.Option(
        None, "--output", "-o",
        help="Output MKV file path (default: input with _subtitled suffix).",
    ),
    overwrite: bool = typer.Option(
        False, "--overwrite", "-y",
        help="Overwrite output file if it exists.",
    ),
    skip_hallucination_check: bool = typer.Option(
        False, "--skip-hallucination-check",
        help="Skip hallucination detection (not recommended).",
    ),
) -> None:
    """
    Generate subtitles for a video file using Whisper AI.

    Extracts audio, transcribes with Whisper, and muxes subtitles into MKV.
    Supports hallucination detection and multiple Whisper backends.
    """
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
        from core.video import SubtitleGenerator, WhisperModel, WhisperConfig

        # Create config
        config = WhisperConfig(
            model=WhisperModel(model),
            language=language,
        )

        # Create generator
        generator = SubtitleGenerator(config=config)

        # Generate subtitles
        result = generator.generate_subtitles(
            video_path=input_file,
            output_mkv_path=output_file,
            overwrite=overwrite,
            detect_hallucinations=not skip_hallucination_check,
        )

        if result.success:
            console.print(f"\n[green]✓[/green] Subtitles generated and muxed to {output_file}")
            console.print(f"[dim]Processing time:[/dim] {result.processing_time:.1f}s")
            console.print(f"[dim]Audio duration:[/dim] {result.audio_duration:.1f}s")

            if result.hallucination_warnings:
                console.print(f"\n[yellow]⚠️  Hallucination warnings:[/yellow]")
                for warning in result.hallucination_warnings:
                    console.print(f"  - {warning}")
        else:
            err_console.print(f"\n[red]✘  Subtitle generation failed:[/red] {result.error_message}")
            if result.hallucination_warnings:
                console.print(f"\n[yellow]Warnings:[/yellow]")
                for warning in result.hallucination_warnings:
                    console.print(f"  - {warning}")
            raise typer.Exit(code=1)

    except Exception as e:
        err_console.print(f"Error: {e}")
        raise typer.Exit(code=1)


@app.command("upscale")
def upscale_command(
    input_file: Path = typer.Argument(
        ..., exists=True, file_okay=True, dir_okay=False, readable=True,
        help="Input video file to upscale.",
    ),
    output_file: Path = typer.Argument(
        ..., file_okay=True, dir_okay=False,
        help="Output upscaled video file path.",
    ),
    target_height: int = typer.Option(
        720, "--height", "-h",
        help="Target height in pixels (default: 720 for 720p).",
    ),
    video_codec: str = typer.Option(
        "libx264", "--codec", "-c",
        help="Video codec to use (default: libx264).",
    ),
    preset: str = typer.Option(
        "medium", "--preset", "-p",
        help="Encoding preset (ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow).",
    ),
    crf: int = typer.Option(
        20, "--crf",
        help="Constant Rate Factor (0-51, lower = higher quality, default: 20).",
    ),
    overwrite: bool = typer.Option(
        False, "--overwrite", "-y",
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
            video_codec=video_codec,
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
        console.print(f"[dim]Size change:[/dim] {result.size_before_gb:.2f}GB → {result.size_after_gb:.2f}GB ({result.size_delta_gb:+.2f}GB)")
    elif result.status.name == "SKIPPED":
        console.print(f"\n[yellow]⏭️[/yellow] Skipped: {result.message}")
    else:
        err_console.print(f"\n[red]✘  Upscaling failed:[/red] {result.message}")
        if result.ffmpeg_result and result.ffmpeg_result.stderr:
            stderr_tail = "\n".join(result.ffmpeg_result.stderr.splitlines()[-20:])
            console.print(f"\n[dim]ffmpeg stderr (tail):[/dim]\n{stderr_tail}", highlight=False)
        raise typer.Exit(code=1)