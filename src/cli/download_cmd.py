"""CLI commands for yt-dlp based media downloading."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from core.download.download_manager import DownloadManager
from core.download.models import DownloadRequest, DownloadStatus, MediaType
from utils.config import get_config
from utils.url_validator import is_valid_url

app = typer.Typer(help="Download media from supported platforms with yt-dlp.")

_URL = Annotated[str, typer.Argument(help="Media URL (YouTube, SoundCloud, etc.).")]
_DRY = Annotated[bool, typer.Option("--dry-run", help="Fetch metadata only; do not download.")]
_OVR = Annotated[bool, typer.Option("--overwrite", help="Overwrite existing files.")]
_YT_CLIENT = Annotated[
    str | None,
    typer.Option("--youtube-client", help="yt-dlp YouTube player client (for example: mweb, web, ios)."),
]
_YT_PO_TOKEN = Annotated[
    str | None,
    typer.Option(
        "--youtube-po-token",
        "--po-token",
        help="Manual YouTube PO token. Use full form 'mweb.gvs+TOKEN' or just TOKEN (defaults to mweb.gvs+TOKEN).",
    ),
]
_YT_VISITOR = Annotated[
    str | None,
    typer.Option("--youtube-visitor-data", help="Optional YouTube visitor data for advanced troubleshooting."),
]
_YT_FETCH_POT = Annotated[
    str | None,
    typer.Option("--youtube-fetch-pot", help="PO-token fetch policy for yt-dlp plugins: auto, never, or always."),
]
_YT_POT_PROVIDER = Annotated[
    bool,
    typer.Option(
        "--youtube-use-po-token-provider",
        "--po-token-provider",
        help="Enable the recommended mweb + automatic PO-token provider flow for harder YouTube cases.",
    ),
]


def _resolve_subtitle_languages(raw: str) -> tuple[str, ...]:
    values = [item.strip().lower() for item in raw.split(",") if item.strip()]
    return tuple(values) if values else ("de", "en")


def _require_url(url: str) -> None:
    if not is_valid_url(url):
        typer.echo(f"Invalid URL: {url}", err=True)
        raise typer.Exit(code=2)


def _validate_cookie_inputs(cookies_from_browser: str | None, cookies_file: Path | None) -> None:
    if cookies_from_browser and cookies_file is not None:
        typer.echo("Use either --cookies-from-browser or --cookies-file, not both.", err=True)
        raise typer.Exit(code=2)


def _validate_youtube_inputs(youtube_fetch_pot: str | None) -> None:
    if youtube_fetch_pot is None:
        return
    if youtube_fetch_pot not in {"auto", "never", "always"}:
        typer.echo("--youtube-fetch-pot must be one of: auto, never, always.", err=True)
        raise typer.Exit(code=2)


@app.command("video")
def download_video(
    url: _URL,
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Output directory.")] = None,
    resolution: Annotated[int | None, typer.Option(help="Max resolution (480/720/1080/2160).")] = None,
    lang: Annotated[str | None, typer.Option(help="Preferred language.")] = None,
    subtitles: Annotated[bool | None, typer.Option(help="Embed subtitles.")] = None,
    thumbnail: Annotated[bool | None, typer.Option(help="Embed thumbnail.")] = None,
    subtitle_languages: Annotated[str | None, typer.Option(help="Comma-separated subtitle languages (de,en).")] = None,
    sponsorblock: Annotated[bool, typer.Option(help="Remove sponsor segments.")] = True,
    cookies_from_browser: Annotated[
        str | None,
        typer.Option("--cookies-from-browser", help="Browser cookie source (chrome/firefox)."),
    ] = None,
    cookies_file: Annotated[
        Path | None,
        typer.Option(
            "--cookies-file",
            help="Path to an exported cookie file (Netscape format). For YouTube, use a fresh private/incognito export.",
        ),
    ] = None,
    youtube_client: _YT_CLIENT = None,
    youtube_po_token: _YT_PO_TOKEN = None,
    youtube_visitor_data: _YT_VISITOR = None,
    youtube_fetch_pot: _YT_FETCH_POT = None,
    youtube_use_po_token_provider: _YT_POT_PROVIDER = False,
    dry_run: _DRY = False,
    overwrite: _OVR = False,
) -> None:
    """Download a single video."""
    _require_url(url)
    _validate_cookie_inputs(cookies_from_browser, cookies_file)
    _validate_youtube_inputs(youtube_fetch_pot)
    cfg = get_config().download
    request = DownloadRequest(
        url=url,
        media_type=MediaType.VIDEO,
        output_dir=output or Path(cfg.default_output_video),
        preferred_language=lang or cfg.preferred_language,
        subtitle_languages=(
            _resolve_subtitle_languages(subtitle_languages)
            if subtitle_languages is not None
            else tuple(cfg.subtitle_languages)
        ),
        embed_subtitles=cfg.embed_subtitles if subtitles is None else subtitles,
        embed_thumbnail=cfg.embed_thumbnail if thumbnail is None else thumbnail,
        max_resolution=resolution if resolution is not None else cfg.max_resolution,
        cookies_from_browser=cookies_from_browser,
        cookies_file=cookies_file,
        youtube_player_client=youtube_client,
        youtube_po_token=youtube_po_token,
        youtube_visitor_data=youtube_visitor_data,
        youtube_fetch_pot=youtube_fetch_pot,
        youtube_use_po_token_provider=youtube_use_po_token_provider,
        sponsorblock_remove=tuple(cfg.sponsorblock_remove) if sponsorblock else (),
        dry_run=dry_run,
        overwrite=overwrite,
    )
    _run(request)


@app.command("music")
def download_music(
    url: _URL,
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Output directory.")] = None,
    fmt: Annotated[str | None, typer.Option("--format", help="Audio format: mp3/flac/m4a/opus.")] = None,
    quality: Annotated[str | None, typer.Option(help="Audio quality (e.g. 320k).")] = None,
    cookies_from_browser: Annotated[
        str | None,
        typer.Option("--cookies-from-browser", help="Browser cookie source (chrome/firefox)."),
    ] = None,
    cookies_file: Annotated[
        Path | None,
        typer.Option(
            "--cookies-file",
            help="Path to an exported cookie file (Netscape format). For YouTube, use a fresh private/incognito export.",
        ),
    ] = None,
    youtube_client: _YT_CLIENT = None,
    youtube_po_token: _YT_PO_TOKEN = None,
    youtube_visitor_data: _YT_VISITOR = None,
    youtube_fetch_pot: _YT_FETCH_POT = None,
    youtube_use_po_token_provider: _YT_POT_PROVIDER = False,
    dry_run: _DRY = False,
    overwrite: _OVR = False,
) -> None:
    """Download music/audio."""
    _require_url(url)
    _validate_cookie_inputs(cookies_from_browser, cookies_file)
    _validate_youtube_inputs(youtube_fetch_pot)
    cfg = get_config().download
    request = DownloadRequest(
        url=url,
        media_type=MediaType.MUSIC,
        output_dir=output or Path(cfg.default_output_music),
        audio_format=fmt or cfg.audio_format,
        audio_quality=quality or cfg.audio_quality,
        cookies_from_browser=cookies_from_browser,
        cookies_file=cookies_file,
        youtube_player_client=youtube_client,
        youtube_po_token=youtube_po_token,
        youtube_visitor_data=youtube_visitor_data,
        youtube_fetch_pot=youtube_fetch_pot,
        youtube_use_po_token_provider=youtube_use_po_token_provider,
        embed_thumbnail=cfg.embed_thumbnail,
        sponsorblock_remove=tuple(cfg.sponsorblock_remove),
        dry_run=dry_run,
        overwrite=overwrite,
    )
    _run(request)


@app.command("series")
def download_series(
    url: _URL,
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Output directory.")] = None,
    resolution: Annotated[int | None, typer.Option(help="Max resolution.")] = None,
    fmt: Annotated[
        str | None,
        typer.Option("--format", help="Optional audio-only output format: mp3/flac/m4a/opus."),
    ] = None,
    quality: Annotated[
        str | None,
        typer.Option(help="Audio quality when --format is used (e.g. 320k)."),
    ] = None,
    lang: Annotated[str | None, typer.Option(help="Preferred language.")] = None,
    subtitles: Annotated[bool | None, typer.Option(help="Embed subtitles.")] = None,
    subtitle_languages: Annotated[str | None, typer.Option(help="Comma-separated subtitle languages (de,en).")] = None,
    cookies_from_browser: Annotated[
        str | None,
        typer.Option("--cookies-from-browser", help="Browser cookie source (chrome/firefox)."),
    ] = None,
    cookies_file: Annotated[
        Path | None,
        typer.Option(
            "--cookies-file",
            help="Path to an exported cookie file (Netscape format). For YouTube, use a fresh private/incognito export.",
        ),
    ] = None,
    youtube_client: _YT_CLIENT = None,
    youtube_po_token: _YT_PO_TOKEN = None,
    youtube_visitor_data: _YT_VISITOR = None,
    youtube_fetch_pot: _YT_FETCH_POT = None,
    youtube_use_po_token_provider: _YT_POT_PROVIDER = False,
    dry_run: _DRY = False,
    overwrite: _OVR = False,
) -> None:
    """Download playlist/series with season/episode path template."""
    _require_url(url)
    _validate_cookie_inputs(cookies_from_browser, cookies_file)
    _validate_youtube_inputs(youtube_fetch_pot)
    cfg = get_config().download
    request = DownloadRequest(
        url=url,
        media_type=MediaType.SERIES,
        output_dir=output or Path(cfg.default_output_series),
        preferred_language=lang or cfg.preferred_language,
        subtitle_languages=(
            _resolve_subtitle_languages(subtitle_languages)
            if subtitle_languages is not None
            else tuple(cfg.subtitle_languages)
        ),
        embed_subtitles=cfg.embed_subtitles if subtitles is None else subtitles,
        embed_thumbnail=cfg.embed_thumbnail,
        max_resolution=resolution if resolution is not None else cfg.max_resolution,
        audio_format=fmt or cfg.audio_format,
        audio_quality=quality or cfg.audio_quality,
        extract_audio=fmt is not None or quality is not None,
        cookies_from_browser=cookies_from_browser,
        cookies_file=cookies_file,
        youtube_player_client=youtube_client,
        youtube_po_token=youtube_po_token,
        youtube_visitor_data=youtube_visitor_data,
        youtube_fetch_pot=youtube_fetch_pot,
        youtube_use_po_token_provider=youtube_use_po_token_provider,
        sponsorblock_remove=tuple(cfg.sponsorblock_remove),
        dry_run=dry_run,
        overwrite=overwrite,
    )
    _run(request)


def _run(request: DownloadRequest) -> None:
    manager = DownloadManager()
    result = manager.download(request)

    if result.status == DownloadStatus.SUCCESS:
        typer.echo(f"Saved: {result.output_path}")
        return

    if result.status == DownloadStatus.SKIPPED:
        typer.echo(f"Skipped ({result.skipped_reason}): {result.track_info}")
        return

    typer.echo(f"Download failed: {result.error_message}", err=True)
    raise typer.Exit(code=1)
