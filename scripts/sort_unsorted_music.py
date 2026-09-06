from __future__ import annotations

import argparse
from pathlib import Path

from core.audio.unsorted_music_organizer import organize_unsorted_music


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sortiert Tracks aus D:\\Musik\\Unsortiert nach Interpret und Album.",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=Path(r"D:\Musik\Unsortiert"),
        help="Quellordner mit unsortierter Musik.",
    )
    parser.add_argument(
        "--artists-root",
        type=Path,
        default=Path(r"D:\Musik\Interpreten"),
        help="Zielordner mit Interpreten-Ordnern.",
    )
    parser.add_argument(
        "--min-artist-tracks",
        type=int,
        default=5,
        help="Minimale Anzahl Tracks pro Interpret fuer automatische Zuordnung.",
    )
    parser.add_argument(
        "--min-album-tracks",
        type=int,
        default=5,
        help="Minimale Anzahl Tracks pro Album fuer automatische Albumordner.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Nur anzeigen, was verschoben wuerde, ohne Dateien zu bewegen.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    summary = organize_unsorted_music(
        source_dir=args.source,
        artists_root=args.artists_root,
        min_artist_tracks=args.min_artist_tracks,
        min_album_tracks=args.min_album_tracks,
        dry_run=args.dry_run,
    )

    mode = "DRY-RUN" if args.dry_run else "MOVE"
    print(f"Modus: {mode}")
    print(f"Gescannt: {summary.scanned_tracks}")
    print(f"Verschoben: {summary.moved_tracks}")
    print(f"  -> in Interpretenordner: {summary.moved_to_artist}")
    print(f"  -> in Albumordner: {summary.moved_to_album}")
    print(f"Ohne Artist-Tag uebersprungen: {summary.skipped_missing_artist}")
    print(f"Unter Schwellwert uebersprungen: {summary.skipped_no_target}")
    print(f"Doppelte im Ziel uebersprungen: {summary.skipped_duplicate_target}")
    print(f"Fehler: {summary.errors}")


if __name__ == "__main__":
    main()
