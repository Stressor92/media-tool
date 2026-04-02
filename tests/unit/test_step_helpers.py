"""
tests/unit/test_step_helpers.py

Unit tests for pure helper functions in concrete step modules.
No filesystem access, no FFmpeg, no network.
"""

from pathlib import Path

from core.workflow.steps.s01_merge_language_dupes import _group_language_dupes
from core.workflow.steps.s04_encode_bluray import _is_bluray_candidate
from core.workflow.steps.s06_organize import _jellyfin_path

# ---------------------------------------------------------------------------
# s01 – _group_language_dupes
# ---------------------------------------------------------------------------


def test_group_language_dupes_finds_pair(tmp_path: Path) -> None:
    files = [
        tmp_path / "Inception.de.mkv",
        tmp_path / "Inception.en.mkv",
        tmp_path / "The.Matrix.mkv",  # Einzeldatei → kein Duplikat
    ]
    groups = _group_language_dupes(files)
    assert len(groups) == 1
    _title, group_files = groups[0]
    assert len(group_files) == 2


def test_group_language_dupes_no_duplicates(tmp_path: Path) -> None:
    files = [tmp_path / "Solo.Film.mkv"]
    assert _group_language_dupes(files) == []


def test_group_language_dupes_multiple_groups(tmp_path: Path) -> None:
    files = [
        tmp_path / "Film.A.de.mkv",
        tmp_path / "Film.A.en.mkv",
        tmp_path / "Film.B.ger.mkv",
        tmp_path / "Film.B.eng.mkv",
    ]
    groups = _group_language_dupes(files)
    assert len(groups) == 2


def test_group_language_dupes_empty_list() -> None:
    assert _group_language_dupes([]) == []


# ---------------------------------------------------------------------------
# s04 – _is_bluray_candidate
# ---------------------------------------------------------------------------


def test_is_bluray_candidate_by_name(tmp_path: Path) -> None:
    path = tmp_path / "Film.BluRay.mkv"
    assert _is_bluray_candidate(path, {"codec_name": "h264", "height": 1080}) is True


def test_is_bluray_candidate_by_bitrate(tmp_path: Path) -> None:
    path = tmp_path / "Film.mkv"
    assert _is_bluray_candidate(path, {"codec_name": "h264", "height": 1080, "bit_rate": 20_000_000}) is True


def test_is_bluray_candidate_hevc_already_compressed(tmp_path: Path) -> None:
    # No BluRay indicator in filename – codec check kicks in and rejects it
    path = tmp_path / "Film.mkv"
    assert _is_bluray_candidate(path, {"codec_name": "hevc", "height": 1080}) is False


def test_is_bluray_candidate_low_bitrate(tmp_path: Path) -> None:
    path = tmp_path / "Film.mkv"
    assert _is_bluray_candidate(path, {"codec_name": "h264", "height": 1080, "bit_rate": 5_000_000}) is False


# ---------------------------------------------------------------------------
# s06 – _jellyfin_path
# ---------------------------------------------------------------------------


def test_jellyfin_path_with_year(tmp_path: Path) -> None:
    source = Path("Inception (2010).mkv")
    dest = _jellyfin_path(tmp_path, source)
    assert dest == tmp_path / "Inception (2010)" / "Inception (2010).mkv"


def test_jellyfin_path_without_year(tmp_path: Path) -> None:
    source = Path("Unknown Film.mkv")
    dest = _jellyfin_path(tmp_path, source)
    assert dest.parent.name == "Unknown Film"
    assert dest.name == "Unknown Film.mkv"


def test_jellyfin_path_preserves_suffix(tmp_path: Path) -> None:
    source = Path("Film (2020).avi")
    dest = _jellyfin_path(tmp_path, source)
    assert dest.suffix == ".avi"
