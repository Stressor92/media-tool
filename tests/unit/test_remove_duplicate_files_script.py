from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "remove_duplicate_files.py"
SPEC = importlib.util.spec_from_file_location("remove_duplicate_files", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _song(
    *,
    name: str,
    extension: str = ".mp3",
    size_bytes: int = 10_000_000,
    duration_seconds: float = 180.0,
    codec: str = "mpeg",
    sample_rate_hz: int = 44100,
    channels: int = 2,
    copy_like_name: bool = False,
    copy_index: int | None = None,
):
    normalized_name = MODULE.normalize_name(name)
    return MODULE.SongInfo(
        path=Path(r"C:/tmp") / f"{name}{extension}",
        extension=extension,
        size_bytes=size_bytes,
        duration_seconds=duration_seconds,
        codec=codec,
        sample_rate_hz=sample_rate_hz,
        channels=channels,
        normalized_name=normalized_name,
        tokens=MODULE.tokenize(normalized_name),
        copy_like_name=copy_like_name,
        copy_index=copy_index,
    )


def test_has_similar_name_accepts_partial_overlap() -> None:
    first = _song(name="Metallica - Nothing Else Matters")
    second = _song(name="Nothing Else Matters Live")

    assert MODULE.has_similar_name(first, second) is True


def test_has_similar_name_accepts_single_shared_token() -> None:
    first = _song(name="Great Song Original")
    second = _song(name="Song Demo")

    assert MODULE.has_similar_name(first, second) is True


def test_has_similar_name_rejects_low_overlap() -> None:
    first = _song(name="Metallica - One")
    second = _song(name="Beatles - Yesterday")

    assert MODULE.has_similar_name(first, second) is False


def test_is_likely_duplicate_uses_extension_size_and_duration() -> None:
    first = _song(name="Song Title")
    second = _song(name="Song Title (1)", size_bytes=10_040_000, duration_seconds=180.5)

    assert MODULE.is_likely_duplicate(first, second) is True

    different_format = _song(name="Song Title (copy)", extension=".flac")
    assert MODULE.is_likely_duplicate(first, different_format) is False


def test_is_likely_duplicate_requires_same_codec_sample_rate_and_channels() -> None:
    first = _song(name="Song Title")

    different_codec = _song(name="Song Title (1)", codec="aac")
    assert MODULE.is_likely_duplicate(first, different_codec) is False

    different_sample_rate = _song(name="Song Title (2)", sample_rate_hz=48000)
    assert MODULE.is_likely_duplicate(first, different_sample_rate) is False

    different_channels = _song(name="Song Title (3)", channels=1)
    assert MODULE.is_likely_duplicate(first, different_channels) is False


def test_choose_deletion_target_prefers_copy_variant() -> None:
    original = _song(name="Song Title")
    duplicate = _song(name="Song Title (2)", copy_like_name=True, copy_index=2)

    result = MODULE.choose_deletion_target(original, duplicate)

    assert result is duplicate


def test_choose_deletion_target_skips_ambiguous_match() -> None:
    first = _song(name="Song Title Remaster")
    second = _song(name="Song Title 2020")

    result = MODULE.choose_deletion_target(first, second)

    assert result is None
