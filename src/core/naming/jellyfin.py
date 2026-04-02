"""
src/core/naming/jellyfin.py

Jellyfin-compatible file and folder naming conventions.
"""

from __future__ import annotations

import re
from pathlib import Path


def _sanitize_filename(name: str) -> str:
    """Sanitize filename by removing/replacing invalid characters."""
    # Replace invalid characters with safe alternatives
    name = name.replace("<", "").replace(">", "").replace(":", " -")
    name = name.replace('"', "").replace("|", "").replace("?", "")
    name = name.replace("*", "").replace("\\", "").replace("/", "")
    return name.strip()


def format_movie_name(title: str, year: int | str | None) -> str:
    """
    Format a movie name according to Jellyfin standards.

    Args:
        title: Movie title.
        year: Release year.

    Returns:
        Formatted name: "Movie Name (Year)"

    Example:
        format_movie_name("The Matrix", 1999) -> "The Matrix (1999)"
    """
    title = _sanitize_filename(title).strip()

    if year:
        year_str = str(year).strip()
        # Ensure year is 4 digits
        if re.match(r"^\d{4}$", year_str):
            return f"{title} ({year_str})"
        else:
            # Try to extract year
            match = re.search(r"(\d{4})", year_str)
            if match:
                return f"{title} ({match.group(1)})"

    return title


def format_series_episode(
    series_name: str, season: int | str, episode: int | str, episode_title: str | None = None
) -> str:
    """
    Format a TV episode name according to Jellyfin standards.

    Args:
        series_name: TV series name.
        season: Season number.
        episode: Episode number.
        episode_title: Optional episode title.

    Returns:
        Formatted name: "Series Name - S01E01" or "Series Name - S01E01 - Episode Title"

    Example:
        format_series_episode("Breaking Bad", 1, 1, "Pilot")
        -> "Breaking Bad - S01E01 - Pilot"
    """
    series_name = _sanitize_filename(series_name).strip()

    # Format season and episode
    try:
        season_num = int(season)
        episode_num = int(episode)
        season_str = f"S{season_num:02d}"
        episode_str = f"E{episode_num:02d}"
    except (ValueError, TypeError):
        season_str = str(season).strip()
        episode_str = str(episode).strip()

    base_name = f"{series_name} - {season_str}{episode_str}"

    if episode_title:
        episode_title = _sanitize_filename(episode_title).strip()
        return f"{base_name} - {episode_title}"

    return base_name


def generate_movie_folder_path(title: str, year: int | str | None, base_dir: Path) -> Path:
    """
    Generate the full folder path for a movie.

    Args:
        title: Movie title.
        year: Release year.
        base_dir: Base movies directory.

    Returns:
        Path: base_dir/Movie Name (Year)/

    Example:
        generate_movie_folder_path("Inception", 2010, Path("/movies"))
        -> Path("/movies/Inception (2010)")
    """
    folder_name = format_movie_name(title, year)
    return base_dir / folder_name


def generate_movie_file_path(
    title: str, year: int | str | None, extension: str, base_dir: Path, suffix: str | None = None
) -> Path:
    """
    Generate the full file path for a movie.

    Args:
        title: Movie title.
        year: Release year.
        extension: File extension (e.g., "mkv").
        base_dir: Base movies directory.
        suffix: Optional suffix for the filename.

    Returns:
        Path: base_dir/Movie Name (Year)/Movie Name (Year).mkv

    Example:
        generate_movie_file_path("Inception", 2010, "mkv", Path("/movies"))
        -> Path("/movies/Inception (2010)/Inception (2010).mkv")
    """
    folder_path = generate_movie_folder_path(title, year, base_dir)
    file_name = format_movie_name(title, year)

    if suffix:
        file_name = f"{file_name} {suffix}"

    return folder_path / f"{file_name}.{extension}"


def generate_series_folder_path(series_name: str, base_dir: Path) -> Path:
    """
    Generate the folder path for a TV series.

    Args:
        series_name: TV series name.
        base_dir: Base TV shows directory.

    Returns:
        Path: base_dir/Series Name/

    Example:
        generate_series_folder_path("Breaking Bad", Path("/tv"))
        -> Path("/tv/Breaking Bad")
    """
    series_name = _sanitize_filename(series_name).strip()
    return base_dir / series_name


def generate_season_folder_path(series_name: str, season: int | str, base_dir: Path) -> Path:
    """
    Generate the folder path for a TV season.

    Args:
        series_name: TV series name.
        season: Season number.
        base_dir: Base TV shows directory.

    Returns:
        Path: base_dir/Series Name/Season 01/

    Example:
        generate_season_folder_path("Breaking Bad", 1, Path("/tv"))
        -> Path("/tv/Breaking Bad/Season 01")
    """
    series_path = generate_series_folder_path(series_name, base_dir)

    try:
        season_num = int(season)
        season_folder = f"Season {season_num:02d}"
    except (ValueError, TypeError):
        season_folder = f"Season {season}"

    return series_path / season_folder


def generate_episode_file_path(
    series_name: str,
    season: int | str,
    episode: int | str,
    extension: str,
    base_dir: Path,
    episode_title: str | None = None,
) -> Path:
    """
    Generate the full file path for a TV episode.

    Args:
        series_name: TV series name.
        season: Season number.
        episode: Episode number.
        extension: File extension (e.g., "mkv").
        base_dir: Base TV shows directory.
        episode_title: Optional episode title.

    Returns:
        Path: base_dir/Series Name/Season 01/Series Name - S01E01.mkv

    Example:
        generate_episode_file_path("Breaking Bad", 1, 1, "mkv", Path("/tv"))
        -> Path("/tv/Breaking Bad/Season 01/Breaking Bad - S01E01.mkv")
    """
    season_path = generate_season_folder_path(series_name, season, base_dir)
    file_name = format_series_episode(series_name, season, episode, episode_title)

    return season_path / f"{file_name}.{extension}"
