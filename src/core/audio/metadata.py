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

    # Parse filename
    parsed = _parse_filename_metadata(basic.filename)

    # Initialize enhanced data
    enhanced_data = basic.__dict__.copy()
    enhanced_data.update({
        'parsed_artist': parsed.get('artist'),
        'parsed_album': parsed.get('album'),
        'parsed_title': parsed.get('title'),
        'parsed_track_number': parsed.get('track'),
        'parsed_year': parsed.get('year'),
        'musicbrainz_id': None,
        'release_id': None,
        'artist_id': None,
        'metadata_confidence': 0.0
    })

    # Try MusicBrainz if we have artist and title
    search_artist = enhanced_data['artist'] or enhanced_data['parsed_artist']
    search_title = enhanced_data['title'] or enhanced_data['parsed_title']
    search_album = enhanced_data['album'] or enhanced_data['parsed_album']

    if search_artist and search_title:
        mb_data = _query_musicbrainz(search_artist, search_title, search_album)
        if mb_data:
            enhanced_data['musicbrainz_id'] = mb_data.get('musicbrainz_id')
            enhanced_data['release_id'] = mb_data.get('release_id')
            enhanced_data['artist_id'] = mb_data.get('artist_id')

            # Update metadata with MusicBrainz data if not present
            if not enhanced_data['title'] and mb_data.get('title'):
                enhanced_data['title'] = mb_data['title']
            if not enhanced_data['artist'] and mb_data.get('artist'):
                enhanced_data['artist'] = mb_data['artist']
            if not enhanced_data['album'] and mb_data.get('album'):
                enhanced_data['album'] = mb_data['album']
            if not enhanced_data['year'] and mb_data.get('year'):
                enhanced_data['year'] = mb_data['year']

            enhanced_data['metadata_confidence'] = 0.9  # High confidence from MusicBrainz
        else:
            # Fallback to parsed data
            if not enhanced_data['title'] and enhanced_data['parsed_title']:
                enhanced_data['title'] = enhanced_data['parsed_title']
            if not enhanced_data['artist'] and enhanced_data['parsed_artist']:
                enhanced_data['artist'] = enhanced_data['parsed_artist']
            if not enhanced_data['album'] and enhanced_data['parsed_album']:
                enhanced_data['album'] = enhanced_data['parsed_album']
            if not enhanced_data['track_number'] and enhanced_data['parsed_track_number']:
                enhanced_data['track_number'] = enhanced_data['parsed_track_number']
            if not enhanced_data['year'] and enhanced_data['parsed_year']:
                enhanced_data['year'] = enhanced_data['parsed_year']

            enhanced_data['metadata_confidence'] = 0.5  # Medium confidence from parsing

    return AudioMetadataEnhanced(**enhanced_data)