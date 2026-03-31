from __future__ import annotations

import logging
from importlib import import_module
from pathlib import Path
from typing import Any, Callable, cast

from core.audio.metadata_providers.provider import TrackMetadata

logger = logging.getLogger(__name__)


class MutagenTagger:
    """Wrapper for Mutagen tagging library."""

    @staticmethod
    def write_metadata(
        audio_path: str | Path,
        metadata: TrackMetadata,
        force: bool = False,
    ) -> bool:
        """Write metadata to an audio file."""
        audio_file_path = Path(audio_path)
        if not audio_file_path.exists():
            logger.error("Audio path does not exist: %s", audio_file_path)
            return False

        try:
            mutagen_module = import_module("mutagen")
            mutagen_file = cast(Callable[..., Any], getattr(mutagen_module, "File"))
            audio = mutagen_file(audio_file_path, easy=True)
            if audio is None:
                logger.error("Unsupported format: %s", audio_file_path)
                return False

            if metadata.title and (force or not audio.get("title")):
                audio["title"] = metadata.title
            if metadata.artist and (force or not audio.get("artist")):
                audio["artist"] = metadata.artist
            if metadata.album and (force or not audio.get("album")):
                audio["album"] = metadata.album
            if metadata.album_artist and (force or not audio.get("albumartist")):
                audio["albumartist"] = metadata.album_artist
            if metadata.year is not None and (force or not audio.get("date")):
                audio["date"] = str(metadata.year)
            if metadata.track_number is not None and (force or not audio.get("tracknumber")):
                audio["tracknumber"] = str(metadata.track_number)
            if metadata.genre and (force or not audio.get("genre")):
                audio["genre"] = metadata.genre

            audio.save()
            logger.info("Tagged metadata for %s", audio_file_path)
            return True

        except Exception as exc:
            logger.error("Failed tagging %s: %s", audio_file_path, exc)
            return False
