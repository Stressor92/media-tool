"""Jellyfin-oriented movie folder parsing and trailer filename helpers."""

from __future__ import annotations

import re


class JellyfinNaming:
    """Utility methods for parsing and generating Jellyfin-compatible names."""

    _movie_pattern = re.compile(r"^(.+?)\s*\((\d{4})\)$")

    @classmethod
    def parse_movie_folder_name(cls, folder_name: str) -> tuple[str, int | None]:
        """Parse a folder like 'Movie Name (2023)' into title and optional year."""
        match = cls._movie_pattern.match(folder_name.strip())
        if match is None:
            return folder_name.strip(), None

        title, year_text = match.groups()
        return title.strip(), int(year_text)

    @classmethod
    def get_trailer_filename(
        cls,
        movie_name: str,
        year: int | None = None,
        language: str | None = None,
    ) -> str:
        """Build trailer filename using Jellyfin trailer naming conventions."""
        base = cls.sanitize_filename(movie_name)
        if year is not None:
            base = f"{base} ({year})"

        suffix = "-trailer"
        if language:
            suffix = f"{suffix}-{language.lower()}"

        return f"{base}{suffix}.mp4"

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Replace characters that are invalid on common filesystems."""
        invalid_chars = '<>:"/\\|?*'
        cleaned = filename
        for char in invalid_chars:
            cleaned = cleaned.replace(char, "_")
        return cleaned.strip()
