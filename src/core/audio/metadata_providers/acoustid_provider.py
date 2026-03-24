from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import acoustid
import musicbrainzngs

from core.audio.metadata_providers.provider import MetadataProvider, TrackMatch, TrackMetadata
from utils.chromaprint_runner import ChromaprintRunner


class AcoustIDProvider(MetadataProvider):
    """Provider backed by AcoustID + MusicBrainz."""

    def __init__(self, acoustid_api_key: str):
        self.acoustid_api_key = acoustid_api_key
        musicbrainzngs.set_useragent("media-tool", "1.0", "https://example.com")

    def lookup_by_fingerprint(self, fingerprint: str, duration: float) -> List[TrackMatch]:
        if not self.acoustid_api_key:
            raise ValueError("AcoustID API key is required")

        try:
            result = acoustid.lookup(self.acoustid_api_key, fingerprint, duration)
        except acoustid.AcoustidError as exc:
            raise RuntimeError("AcoustID lookup failed") from exc

        matches: list[TrackMatch] = []
        status = result.get("status")
        if status != "ok":
            return matches

        for recording in result.get("results", []):
            for track in recording.get("recordings", []):
                track_id = track.get("id")
                title = track.get("title")
                artist_credit = track.get("artists", [])
                artist_name = ", ".join(a.get("name", "") for a in artist_credit if a.get("name"))
                album = ""  # Will fill from MusicBrainz if available
                confidence = float(track.get("score", 0.0))

                mb_metadata = None
                if track_id:
                    mb_metadata = self.lookup_by_id(track_id)

                if mb_metadata:
                    metadata = mb_metadata
                else:
                    metadata = TrackMetadata(
                        title=title or "",
                        artist=artist_name,
                        album=album,
                        musicbrainz_id=track_id,
                        acoustid_id=result.get("id"),
                        confidence_score=confidence,
                    )

                matches.append(TrackMatch(metadata=metadata, confidence=confidence, source="acoustid"))

        return sorted(matches, key=lambda m: m.confidence, reverse=True)

    def lookup_by_id(self, track_id: str) -> Optional[TrackMetadata]:
        if not track_id:
            return None

        try:
            rec = musicbrainzngs.get_recording_by_id(track_id, includes=["artists", "releases"])
        except musicbrainzngs.ResponseError:
            return None

        recording = rec.get("recording")
        if not recording:
            return None

        title = recording.get("title", "")
        artist_credit = recording.get("artist-credit", [])
        artist_name = ", ".join(a.get("artist", {}).get("name", "") for a in artist_credit if a.get("artist"))

        album = ""
        disc_number = None
        track_number = None

        releases = recording.get("release-list", [])
        if releases:
            release = releases[0]
            album = release.get("title", "")
            track_offset = release.get("medium-list", [])
            if track_offset and isinstance(track_offset, list):
                medium0 = track_offset[0]
                track_list = medium0.get("track-list", [])
                if track_list:
                    track_item = track_list[0]
                    track_number = int(track_item.get("number", 0)) if track_item.get("number") else None
                    disc_number = int(medium0.get("position", 0)) if medium0.get("position") else None

        return TrackMetadata(
            title=title,
            artist=artist_name,
            album=album,
            musicbrainz_id=track_id,
            disc_number=disc_number,
            track_number=track_number,
            confidence_score=1.0,
        )

    @classmethod
    def from_audio_file(cls, file_path: str, acoustid_api_key: str) -> List[TrackMatch]:
        if not acoustid_api_key:
            raise ValueError("AcoustID API key is required")

        runner = ChromaprintRunner()
        fp_result = runner.calculate_fingerprint(Path(file_path))

        if not fp_result.success:
            raise RuntimeError(f"Chromaprint failed: {fp_result.error_message}")

        return cls(acoustid_api_key).lookup_by_fingerprint(fp_result.fingerprint, fp_result.duration)
