from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

from utils.config import get_config

if TYPE_CHECKING:
    from core.metadata.metadata_pipeline import MetadataPipeline

app = typer.Typer(help="Fetch movie metadata and artwork from TMDB.")


def _make_pipeline(
    api_key: str,
    interactive: bool,
    overwrite: bool,
    dry_run: bool,
    artwork_raw: str,
    language: str,
    preferred_artwork_language: str,
) -> MetadataPipeline:
    from core.metadata.artwork_downloader import ArtworkDownloader
    from core.metadata.match_selector import MatchSelector, SelectionMode
    from core.metadata.metadata_pipeline import MetadataPipeline
    from core.metadata.models import ArtworkType
    from core.metadata.tmdb_client import TmdbClient
    from core.metadata.tmdb_provider import TmdbProvider

    artwork_map: dict[str, ArtworkType] = {
        "poster": ArtworkType.POSTER,
        "fanart": ArtworkType.FANART,
        "banner": ArtworkType.BANNER,
        "thumb": ArtworkType.THUMB,
        "logo": ArtworkType.LOGO,
        "disc": ArtworkType.DISC,
    }

    if artwork_raw.strip().lower() == "all":
        artwork_types = list(artwork_map.values())
    else:
        artwork_types = [
            artwork_map[item.strip().lower()] for item in artwork_raw.split(",") if item.strip().lower() in artwork_map
        ]
        if not artwork_types:
            artwork_types = [ArtworkType.POSTER, ArtworkType.FANART]

    client = TmdbClient(api_key=api_key, language=language)
    provider = TmdbProvider(client)
    selector = MatchSelector(SelectionMode.INTERACTIVE if interactive else SelectionMode.AUTO)
    downloader = ArtworkDownloader(
        preferred_language=preferred_artwork_language,
        types=artwork_types,
        overwrite=overwrite,
    )

    return MetadataPipeline(
        provider=provider,
        selector=selector,
        downloader=downloader,
        artwork_types=artwork_types,
        overwrite=overwrite,
        dry_run=dry_run,
    )


@app.command("fetch")
def fetch(
    path: Annotated[Path, typer.Argument(help="Movie file or directory")],
    interactive: Annotated[
        bool,
        typer.Option("-i", "--interactive", help="Manually select from TMDB results"),
    ] = False,
    overwrite: Annotated[bool, typer.Option("--overwrite", help="Overwrite existing NFO/artwork")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview only, write no files")] = False,
    artwork: Annotated[
        str,
        typer.Option("--artwork", help="poster,fanart,banner,thumb,logo,disc or all"),
    ] = "poster,fanart",
    language: Annotated[str, typer.Option("--language", help="TMDB language, e.g. de-DE")] = "de-DE",
    api_key: Annotated[str | None, typer.Option(envvar="TMDB_API_KEY", help="TMDB API key")] = None,
) -> None:
    from core.metadata.models import MetadataStatus

    config = get_config()
    configured_key = config.api.tmdb_api_key
    key = api_key or configured_key

    if not key:
        typer.echo(
            "No TMDB API key found. Set TMDB_API_KEY or api.tmdb_api_key in media-tool.toml.",
            err=True,
        )
        raise typer.Exit(1)

    preferred_artwork_language = config.metadata.preferred_artwork_lang
    pipeline = _make_pipeline(
        api_key=key,
        interactive=interactive,
        overwrite=overwrite,
        dry_run=dry_run,
        artwork_raw=artwork,
        language=language,
        preferred_artwork_language=preferred_artwork_language,
    )

    if path.is_file():
        results = [pipeline.process_file(path)]
    elif path.is_dir():
        results = pipeline.process_directory(path, recursive=True)
    else:
        typer.echo(f"Invalid input path: {path}", err=True)
        raise typer.Exit(1)

    ok = 0
    skipped = 0
    failed = 0
    not_found = 0

    for result in results:
        if result.status == MetadataStatus.SUCCESS:
            typer.echo(f"OK {result.source_path.name}: NFO + {len(result.artwork_files)} artwork files")
            ok += 1
        elif result.status == MetadataStatus.SKIPPED:
            typer.echo(f"SKIP {result.source_path.name}: {result.skipped_reason}")
            skipped += 1
        elif result.status == MetadataStatus.NOT_FOUND:
            typer.echo(f"NOT_FOUND {result.source_path.name}: no TMDB match", err=True)
            not_found += 1
        else:
            typer.echo(f"FAIL {result.source_path.name}: {result.error}", err=True)
            failed += 1

    typer.echo(f"\n{ok} processed, {skipped} skipped, {not_found} not found, {failed} failed")

    if dry_run:
        typer.echo("Dry run mode: no files were written.")

    if failed or not_found:
        raise typer.Exit(1)


@app.command("search")
def search_cmd(
    title: Annotated[str, typer.Argument(help="Movie title")],
    year: Annotated[int | None, typer.Option(help="Release year filter")] = None,
    limit: Annotated[int, typer.Option(help="Max result count")] = 8,
    language: Annotated[str, typer.Option("--language", help="TMDB language, e.g. de-DE")] = "de-DE",
    api_key: Annotated[str | None, typer.Option(envvar="TMDB_API_KEY", help="TMDB API key")] = None,
) -> None:
    from core.metadata.tmdb_client import TmdbClient
    from core.metadata.tmdb_provider import TmdbProvider

    config = get_config()
    key = api_key or config.api.tmdb_api_key
    if not key:
        typer.echo("No TMDB API key found.", err=True)
        raise typer.Exit(1)

    provider = TmdbProvider(TmdbClient(api_key=key, language=language))
    results = provider.search(title=title, year=year, limit=limit)
    if not results:
        typer.echo("No results.")
        return

    typer.echo(f"\n{'#':<4} {'Title':<45} {'Year':<6} {'Rating':<7} TMDB-ID")
    typer.echo("-" * 78)
    for index, result in enumerate(results, start=1):
        result_year = str(result.year) if result.year else "-"
        typer.echo(f"{index:<4} {result.title:<45} {result_year:<6} {result.vote_average:<7.1f} {result.tmdb_id}")
