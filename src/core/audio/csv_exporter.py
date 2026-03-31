"""CSV export for library scan metadata."""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from .metadata_extractor import AudioFileMetadata

logger = logging.getLogger(__name__)


class CSVExportError(RuntimeError):
    """Raised when CSV export fails."""


class CSVExporter:
    """Export audio metadata rows in a stable CSV format."""

    FIELD_ORDER = [
        "file_path", "file_name", "file_size_mb", "directory", "extension", "duration_seconds",
        "artist", "album", "title", "album_artist", "track_number", "total_tracks", "disc_number",
        "year", "genre", "comment",
        "codec", "bitrate_kbps", "sample_rate_hz", "channels", "bit_depth",
        "is_lossless", "is_tagged", "has_cover_art",
        "date_modified", "date_scanned", "error_message",
    ]

    def export(
        self,
        metadata_list: list[AudioFileMetadata],
        output_path: Path,
        include_errors: bool = True,
    ) -> int:
        """Export metadata rows to a CSV file."""
        rows = metadata_list if include_errors else [row for row in metadata_list if not row.error_message]
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with output_path.open("w", newline="", encoding="utf-8-sig") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.FIELD_ORDER, extrasaction="ignore")
                writer.writeheader()
                for metadata in rows:
                    writer.writerow(self._metadata_to_dict(metadata))
        except OSError as exc:
            logger.error("CSV export failed for %s: %s", output_path, exc)
            raise CSVExportError(f"Failed to write CSV: {exc}") from exc

        logger.info("Exported %d rows to %s", len(rows), output_path)
        return len(rows)

    def _metadata_to_dict(self, metadata: AudioFileMetadata) -> dict[str, str]:
        row: dict[str, str] = {}
        for field_name in self.FIELD_ORDER:
            value = getattr(metadata, field_name)
            row[field_name] = self._format_value(field_name, value)
        return row

    def _format_value(self, field_name: str, value: object) -> str:
        if value is None:
            return ""
        if field_name in {"file_size_mb", "duration_seconds"} and isinstance(value, float):
            return f"{value:.2f}"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, Path):
            return str(value)
        isoformat_method = getattr(value, "isoformat", None)
        if callable(isoformat_method):
            return str(isoformat_method())
        return str(value)