"""
src/core/audio/metadata.py

Enhanced audio metadata extraction using MusicBrainz and filename parsing.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from utils.audio_analyzer import AudioMetadata, extract_audio_metadata

logger = logging.getLogger(__name__)

# Try to import musicbrainzngs, but make it optional
try:
    import musicbrainzngs
    MUSICBRAINZ_AVAILABLE = True
    musicbrainzngs.set_useragent("media-tool", "0.1.0", "https://github.com/user/media-tool")
except ImportError:
    MUSICBRAINZ_AVAILABLE = False
    logger.warning("musicbrainzngs not available, using filename parsing only")


@dataclass(frozen=True)
class AudioMetadataEnhanced(AudioMetadata):
    """Enhanced audio metadata with MusicBrainz data."""

    # MusicBrainz specific
    musicbrainz_id: Optional[str] = None
    release_id: Optional[str] = None
    artist_id: Optional[str] = None

    # Parsed from filename
    parsed_artist: Optional[str] = None
    parsed_album: Optional[str] = None
    parsed_title: Optional[str] = None
    parsed_track_number: Optional[int] = None
    parsed_year: Optional[int] = None

    # Confidence scores
    metadata_confidence: float = 0.0  # 0.0 to 1.0


def _parse_filename_metadata(filename: str) -> dict[str, str | int | None]:
    """
    Parse metadata from filename using common patterns.

    Examples:
    - "Artist - Album - 01 - Title.mp3"
    - "01 - Artist - Title.flac"
    - "Artist - Title.mp3"
    """
    # Remove extension
    name = Path(filename).stem

    # Common patterns
    patterns = [
        # Artist - Album - Track - Title
        re.compile(r'^(.+?)\s*-\s*(.+?)\s*-\s*(\d+)\s*-\s*(.+)$'),
        # Track - Artist - Title
        re.compile(r'^(\d+)\s*-\s*(.+?)\s*-\s*(.+)$'),
        # Artist - Title
        re.compile(r'^(.+?)\s*-\s*(.+)$'),
    ]

    for pattern in patterns:
        match = pattern.match(name)
        if match:
            groups = match.groups()
            if len(groups) == 4:  # Artist - Album - Track - Title
                return {
                    'artist': groups[0].strip(),
                    'album': groups[1].strip(),
                    'track': int(groups[2]),
                    'title': groups[3].strip(),
                }
            elif len(groups) == 3:  # Track - Artist - Title
                return {
                    'track': int(groups[0]),
                    'artist': groups[1].strip(),
                    'title': groups[2].strip(),
                }
            elif len(groups) == 2:  # Artist - Title
                return {
                    'artist': groups[0].strip(),
                    'title': groups[1].strip(),
                }

    return {}


def _query_musicbrainz(artist: str, title: str, album: Optional[str] = None) -> dict[str, str | None]:
    """
    Query MusicBrainz for metadata.

    Returns enhanced metadata dict.
    """
    if not MUSICBRAINZ_AVAILABLE:
        return {}

    try:
        # Search for recording
        result = musicbrainzngs.search_recordings(
            artist=artist,
            recording=title,
            release=album,
            limit=1
        )

        if result['recording-list']:
            recording = result['recording-list'][0]

            metadata = {
                'musicbrainz_id': recording.get('id'),
                'title': recording.get('title'),
                'artist': recording.get('artist-credit-phrase'),
            }

            # Get release info if available
            if 'release-list' in recording and recording['release-list']:
                release = recording['release-list'][0]
                metadata['album'] = release.get('title')
                metadata['release_id'] = release.get('id')

                # Try to get year
                if 'date' in release:
                    try:
                        metadata['year'] = int(release['date'][:4])
                    except ValueError:
                        pass

            return metadata

    except Exception as e:
        logger.warning("MusicBrainz query failed: %s", e)

    return {}


def extract_audio_metadata_enhanced(filepath: Path) -> AudioMetadataEnhanced | None:
    """
    Extract enhanced audio metadata with MusicBrainz lookup and filename parsing.

    Args:
        filepath: Path to the audio file.

    Returns:
        AudioMetadataEnhanced object or None if extraction failed.
    """
    # Get basic metadata
    basic = extract_audio_metadata(filepath)
    if not basic:
        return None

    enhanced = AudioMetadataEnhanced(**basic.__dict__)

    # Parse filename
    parsed = _parse_filename_metadata(basic.filename)
    enhanced.parsed_artist = parsed.get('artist')
    enhanced.parsed_album = parsed.get('album')
    enhanced.parsed_title = parsed.get('title')
    enhanced.parsed_track_number = parsed.get('track')
    enhanced.parsed_year = parsed.get('year')

    # Try MusicBrainz if we have artist and title
    search_artist = enhanced.artist or enhanced.parsed_artist
    search_title = enhanced.title or enhanced.parsed_title
    search_album = enhanced.album or enhanced.parsed_album

    if search_artist and search_title:
        mb_data = _query_musicbrainz(search_artist, search_title, search_album)
        if mb_data:
            enhanced.musicbrainz_id = mb_data.get('musicbrainz_id')
            enhanced.release_id = mb_data.get('release_id')
            enhanced.artist_id = mb_data.get('artist_id')

            # Update metadata with MusicBrainz data if not present
            if not enhanced.title and mb_data.get('title'):
                enhanced.title = mb_data['title']
            if not enhanced.artist and mb_data.get('artist'):
                enhanced.artist = mb_data['artist']
            if not enhanced.album and mb_data.get('album'):
                enhanced.album = mb_data['album']
            if not enhanced.year and mb_data.get('year'):
                enhanced.year = mb_data['year']

            enhanced.metadata_confidence = 0.9  # High confidence from MusicBrainz
        else:
            # Fallback to parsed data
            if not enhanced.title and enhanced.parsed_title:
                enhanced.title = enhanced.parsed_title
            if not enhanced.artist and enhanced.parsed_artist:
                enhanced.artist = enhanced.parsed_artist
            if not enhanced.album and enhanced.parsed_album:
                enhanced.album = enhanced.parsed_album
            if not enhanced.track_number and enhanced.parsed_track_number:
                enhanced.track_number = enhanced.parsed_track_number
            if not enhanced.year and enhanced.parsed_year:
                enhanced.year = enhanced.parsed_year

            enhanced.metadata_confidence = 0.5  # Medium confidence from parsing

    return enhanced