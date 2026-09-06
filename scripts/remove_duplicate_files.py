from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass
from pathlib import Path

from mutagen import File as mutagen_file

DEFAULT_ROOT = Path(r"D:\Musik")
SUPPORTED_EXTENSIONS = {".mp3", ".flac", ".m4a", ".aac", ".ogg", ".wav", ".wma"}

MAX_SIZE_DIFF_BYTES = 128 * 1024
MAX_SIZE_DIFF_RATIO = 0.02
MAX_DURATION_DIFF_SECONDS = 1.0
MAX_DURATION_DIFF_RATIO = 0.01
MIN_COMMON_TOKENS = 1

COPY_SUFFIX_RE = re.compile(
    r"(?:\s*[\(\[](?P<index>\d+)[\)\]])$|(?:\s*[-_]?\s*(?:copy|kopie))$",
    re.IGNORECASE,
)
TOKEN_SPLIT_RE = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class SongInfo:
    path: Path
    extension: str
    size_bytes: int
    duration_seconds: float | None
    codec: str | None
    sample_rate_hz: int | None
    channels: int | None
    normalized_name: str
    tokens: frozenset[str]
    copy_like_name: bool
    copy_index: int | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Find and remove likely duplicate songs using fuzzy name + metadata checks."
    )
    parser.add_argument(
        "root",
        nargs="?",
        default=str(DEFAULT_ROOT),
        help="Root folder to scan recursively (default: D:\\Musik)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Only print matches, do not delete files")
    return parser.parse_args()


def normalize_name(stem: str) -> str:
    normalized = stem.lower().strip()
    while True:
        stripped = COPY_SUFFIX_RE.sub("", normalized).strip()
        if stripped == normalized:
            return normalized
        normalized = stripped


def tokenize(name: str) -> frozenset[str]:
    tokens = {token for token in TOKEN_SPLIT_RE.split(name.lower()) if len(token) > 1}
    return frozenset(tokens)


def parse_copy_index(stem: str) -> int | None:
    match = COPY_SUFFIX_RE.search(stem)
    if not match:
        return None
    value = match.groupdict().get("index")
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def normalize_codec_name(codec: str | None) -> str | None:
    if not codec:
        return None
    normalized = codec.strip().lower().replace(" ", "")
    return normalized or None


def read_audio_technical_details(path: Path) -> tuple[float | None, str | None, int | None, int | None]:
    try:
        audio = mutagen_file(path)
    except Exception:
        return None, None, None, None
    if audio is None:
        return None, None, None, None

    info = getattr(audio, "info", None)

    duration = getattr(info, "length", None)
    parsed_duration = float(duration) if isinstance(duration, int | float) and duration > 0 else None

    sample_rate = getattr(info, "sample_rate", None)
    parsed_sample_rate = int(sample_rate) if isinstance(sample_rate, int) and sample_rate > 0 else None

    channels = getattr(info, "channels", None)
    parsed_channels = int(channels) if isinstance(channels, int) and channels > 0 else None

    codec = normalize_codec_name(getattr(info, "codec", None))
    if codec is None:
        mime_types = getattr(audio, "mime", None)
        if isinstance(mime_types, list) and mime_types:
            mime_codec = mime_types[0].split("/", 1)[-1].split(";", 1)[0]
            codec = normalize_codec_name(mime_codec)

    return parsed_duration, codec, parsed_sample_rate, parsed_channels


def build_song_info(path: Path) -> SongInfo:
    stem = path.stem
    copy_index = parse_copy_index(stem)
    normalized_name = normalize_name(stem)
    tokens = tokenize(normalized_name)
    duration_seconds, codec, sample_rate_hz, channels = read_audio_technical_details(path)

    return SongInfo(
        path=path,
        extension=path.suffix.lower(),
        size_bytes=path.stat().st_size,
        duration_seconds=duration_seconds,
        codec=codec,
        sample_rate_hz=sample_rate_hz,
        channels=channels,
        normalized_name=normalized_name,
        tokens=tokens,
        copy_like_name=copy_index is not None or COPY_SUFFIX_RE.search(stem) is not None,
        copy_index=copy_index,
    )


def has_similar_name(first: SongInfo, second: SongInfo) -> bool:
    common = first.tokens & second.tokens
    if len(common) >= MIN_COMMON_TOKENS:
        return True

    return first.normalized_name == second.normalized_name


def has_similar_size(first: SongInfo, second: SongInfo) -> bool:
    absolute_diff = abs(first.size_bytes - second.size_bytes)
    if absolute_diff <= MAX_SIZE_DIFF_BYTES:
        return True
    largest = max(first.size_bytes, second.size_bytes)
    return (absolute_diff / largest) <= MAX_SIZE_DIFF_RATIO


def has_similar_duration(first: SongInfo, second: SongInfo) -> bool:
    if first.duration_seconds is None or second.duration_seconds is None:
        return False

    absolute_diff = abs(first.duration_seconds - second.duration_seconds)
    if absolute_diff <= MAX_DURATION_DIFF_SECONDS:
        return True
    largest = max(first.duration_seconds, second.duration_seconds)
    return (absolute_diff / largest) <= MAX_DURATION_DIFF_RATIO


def has_same_codec(first: SongInfo, second: SongInfo) -> bool:
    if first.codec is None or second.codec is None:
        return False
    return first.codec == second.codec


def has_same_sample_rate(first: SongInfo, second: SongInfo) -> bool:
    if first.sample_rate_hz is None or second.sample_rate_hz is None:
        return False
    return first.sample_rate_hz == second.sample_rate_hz


def has_same_channel_count(first: SongInfo, second: SongInfo) -> bool:
    if first.channels is None or second.channels is None:
        return False
    return first.channels == second.channels


def is_likely_duplicate(first: SongInfo, second: SongInfo) -> bool:
    return (
        first.extension == second.extension
        and has_similar_name(first, second)
        and has_similar_size(first, second)
        and has_similar_duration(first, second)
        and has_same_codec(first, second)
        and has_same_sample_rate(first, second)
        and has_same_channel_count(first, second)
    )


def choose_deletion_target(first: SongInfo, second: SongInfo) -> SongInfo | None:
    if first.copy_like_name and not second.copy_like_name:
        return first
    if second.copy_like_name and not first.copy_like_name:
        return second

    if first.copy_like_name and second.copy_like_name:
        first_idx = first.copy_index if first.copy_index is not None else -1
        second_idx = second.copy_index if second.copy_index is not None else -1
        if first_idx != second_idx:
            return first if first_idx > second_idx else second

    if first.normalized_name == second.normalized_name:
        if len(first.path.stem) != len(second.path.stem):
            return first if len(first.path.stem) > len(second.path.stem) else second
    return None


def collect_audio_files(folder: str, file_names: list[str]) -> list[SongInfo]:
    songs: list[SongInfo] = []
    for file_name in file_names:
        path = Path(folder) / file_name
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        if not path.is_file():
            continue
        try:
            songs.append(build_song_info(path))
        except OSError as exc:
            print(f"SKIP unreadable file: {path} ({exc})")
    return songs


def scan_and_remove_duplicates(root: Path, dry_run: bool) -> tuple[int, int, int]:
    compared_pairs = 0
    matched_pairs = 0
    deleted_files = 0

    for folder, _dirs, file_names in os.walk(root):
        songs = collect_audio_files(folder, file_names)
        if len(songs) < 2:
            continue

        deleted_paths: set[Path] = set()
        for idx, first in enumerate(songs):
            if first.path in deleted_paths:
                continue

            for second in songs[idx + 1 :]:
                if second.path in deleted_paths:
                    continue

                compared_pairs += 1
                if not is_likely_duplicate(first, second):
                    continue

                matched_pairs += 1
                to_delete = choose_deletion_target(first, second)
                if to_delete is None:
                    print(f"MATCH but ambiguous, skipped: {first.path.name} <-> {second.path.name}")
                    continue

                print(
                    "DUPLICATE:"
                    f" {first.path.name} <-> {second.path.name}"
                    f" | size={first.size_bytes}/{second.size_bytes}"
                    f" | duration={first.duration_seconds:.2f}/{second.duration_seconds:.2f}s"
                    f" | codec={first.codec}/{second.codec}"
                    f" | rate={first.sample_rate_hz}/{second.sample_rate_hz}Hz"
                    f" | channels={first.channels}/{second.channels}"
                )

                if dry_run:
                    print(f"DRY-RUN delete: {to_delete.path}")
                    deleted_paths.add(to_delete.path)
                    deleted_files += 1
                    continue

                try:
                    to_delete.path.unlink()
                    print(f"Deleted: {to_delete.path}")
                    deleted_paths.add(to_delete.path)
                    deleted_files += 1
                except OSError as exc:
                    print(f"ERROR deleting {to_delete.path}: {exc}")

    return compared_pairs, matched_pairs, deleted_files


def main() -> None:
    args = parse_args()
    root = Path(args.root).expanduser()

    if not root.exists() or not root.is_dir():
        print(f"ERROR: root folder not found: {root}")
        return

    compared_pairs, matched_pairs, deleted_files = scan_and_remove_duplicates(root, args.dry_run)

    print("\n------------------")
    print(f"Compared pairs: {compared_pairs}")
    print(f"Potential duplicate pairs: {matched_pairs}")
    print(f"Deleted files: {deleted_files}")


if __name__ == "__main__":
    main()
