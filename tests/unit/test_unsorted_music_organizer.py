from __future__ import annotations

from pathlib import Path

from core.audio.unsorted_music_organizer import organize_unsorted_music


def _create_audio_files(directory: Path, names: list[str], payload: bytes = b"x") -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name in names:
        (directory / name).write_bytes(payload)


def test_existing_artist_folder_is_used_even_below_threshold(tmp_path: Path, monkeypatch) -> None:
    source_dir = tmp_path / "Unsortiert"
    artists_root = tmp_path / "Interpreten"
    _create_audio_files(source_dir, ["song1.mp3"])
    (artists_root / "Artist One").mkdir(parents=True)

    monkeypatch.setattr(
        "core.audio.unsorted_music_organizer.extract_artist_album",
        lambda _: ("Artist One", None),
    )

    summary = organize_unsorted_music(source_dir, artists_root, min_artist_tracks=5, min_album_tracks=5)

    assert summary.moved_tracks == 1
    assert (artists_root / "Artist One" / "song1.mp3").exists()


def test_artist_folder_created_when_threshold_reached(tmp_path: Path, monkeypatch) -> None:
    source_dir = tmp_path / "Unsortiert"
    artists_root = tmp_path / "Interpreten"
    names = [f"track{i}.mp3" for i in range(1, 6)]
    _create_audio_files(source_dir, names)

    monkeypatch.setattr(
        "core.audio.unsorted_music_organizer.extract_artist_album",
        lambda _: ("Artist Two", None),
    )

    summary = organize_unsorted_music(source_dir, artists_root, min_artist_tracks=5, min_album_tracks=5)

    assert summary.moved_tracks == 5
    assert summary.moved_to_artist == 5
    for name in names:
        assert (artists_root / "Artist Two" / name).exists()


def test_album_folder_created_when_album_threshold_reached(tmp_path: Path, monkeypatch) -> None:
    source_dir = tmp_path / "Unsortiert"
    artists_root = tmp_path / "Interpreten"
    names = [f"album-track-{i}.mp3" for i in range(1, 6)]
    _create_audio_files(source_dir, names)

    monkeypatch.setattr(
        "core.audio.unsorted_music_organizer.extract_artist_album",
        lambda _: ("Artist Three", "Album Three"),
    )

    summary = organize_unsorted_music(source_dir, artists_root, min_artist_tracks=5, min_album_tracks=5)

    assert summary.moved_tracks == 5
    assert summary.moved_to_album == 5
    for name in names:
        assert (artists_root / "Artist Three" / "Album Three" / name).exists()


def test_existing_album_folder_is_used_below_album_threshold(tmp_path: Path, monkeypatch) -> None:
    source_dir = tmp_path / "Unsortiert"
    artists_root = tmp_path / "Interpreten"
    _create_audio_files(source_dir, ["single.mp3"])
    (artists_root / "Artist Four" / "Album Four").mkdir(parents=True)

    monkeypatch.setattr(
        "core.audio.unsorted_music_organizer.extract_artist_album",
        lambda _: ("Artist Four", "Album Four"),
    )

    summary = organize_unsorted_music(source_dir, artists_root, min_artist_tracks=5, min_album_tracks=5)

    assert summary.moved_tracks == 1
    assert (artists_root / "Artist Four" / "Album Four" / "single.mp3").exists()


def test_tracks_are_skipped_if_artist_threshold_not_met_and_no_folder_exists(tmp_path: Path, monkeypatch) -> None:
    source_dir = tmp_path / "Unsortiert"
    artists_root = tmp_path / "Interpreten"
    _create_audio_files(source_dir, ["lonely.mp3"])

    monkeypatch.setattr(
        "core.audio.unsorted_music_organizer.extract_artist_album",
        lambda _: ("Artist Five", None),
    )

    summary = organize_unsorted_music(source_dir, artists_root, min_artist_tracks=5, min_album_tracks=5)

    assert summary.moved_tracks == 0
    assert summary.skipped_no_target == 1
    assert (source_dir / "lonely.mp3").exists()


def test_name_collision_gets_incremented_filename(tmp_path: Path, monkeypatch) -> None:
    source_dir = tmp_path / "Unsortiert"
    artists_root = tmp_path / "Interpreten"
    _create_audio_files(source_dir, ["duplicate.mp3"], payload=b"123456")
    target_artist = artists_root / "Artist Six"
    target_artist.mkdir(parents=True)
    (target_artist / "duplicate.mp3").write_bytes(b"not-the-same-size")

    monkeypatch.setattr(
        "core.audio.unsorted_music_organizer.extract_artist_album",
        lambda _: ("Artist Six", None),
    )

    summary = organize_unsorted_music(source_dir, artists_root, min_artist_tracks=5, min_album_tracks=5)

    assert summary.moved_tracks == 1
    assert (target_artist / "duplicate (1).mp3").exists()


def test_identical_target_duplicate_is_skipped(tmp_path: Path, monkeypatch) -> None:
    source_dir = tmp_path / "Unsortiert"
    artists_root = tmp_path / "Interpreten"
    payload = b"same-bytes"
    _create_audio_files(source_dir, ["same.mp3"], payload=payload)
    target_artist = artists_root / "Artist Seven"
    target_artist.mkdir(parents=True)
    (target_artist / "same.mp3").write_bytes(payload)

    monkeypatch.setattr(
        "core.audio.unsorted_music_organizer.extract_artist_album",
        lambda _: ("Artist Seven", None),
    )

    summary = organize_unsorted_music(source_dir, artists_root, min_artist_tracks=5, min_album_tracks=5)

    assert summary.moved_tracks == 0
    assert summary.skipped_duplicate_target == 1
    assert (source_dir / "same.mp3").exists()
