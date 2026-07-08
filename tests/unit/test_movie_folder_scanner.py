from __future__ import annotations

from core.video.movie_folder_scanner import MovieFolderScanner


def _make_movie_folder(tmp_path, folder_name: str = "12 Monkeys (1995)"):
    folder = tmp_path / folder_name
    folder.mkdir(parents=True)
    (folder / f"{folder_name}.mkv").write_bytes(b"video")
    return folder


def test_has_existing_trailer_detects_spaced_suffix(tmp_path) -> None:
    folder = _make_movie_folder(tmp_path)
    (folder / "12 Monkeys (1995) - trailer.mp4").write_bytes(b"trailer")

    assert MovieFolderScanner._has_existing_trailer(folder) is True


def test_has_existing_trailer_detects_compact_suffix(tmp_path) -> None:
    folder = _make_movie_folder(tmp_path)
    (folder / "12 Monkeys (1995)-trailer.mp4").write_bytes(b"trailer")

    assert MovieFolderScanner._has_existing_trailer(folder) is True


def test_has_existing_trailer_detects_spaced_bracket_suffix(tmp_path) -> None:
    folder = _make_movie_folder(tmp_path)
    (folder / "12 Monkeys (1995) - [trailer].mp4").write_bytes(b"trailer")

    assert MovieFolderScanner._has_existing_trailer(folder) is True


def test_has_existing_trailer_detects_compact_bracket_suffix(tmp_path) -> None:
    folder = _make_movie_folder(tmp_path)
    (folder / "12 Monkeys (1995)-[trailer].mp4").write_bytes(b"trailer")

    assert MovieFolderScanner._has_existing_trailer(folder) is True


def test_contains_primary_movie_file_ignores_all_trailer_suffix_variants(tmp_path) -> None:
    folder = tmp_path / "Movie Folder"
    folder.mkdir(parents=True)
    (folder / "Movie Folder - trailer.mp4").write_bytes(b"trailer")
    (folder / "Movie Folder-trailer.mp4").write_bytes(b"trailer")
    (folder / "Movie Folder - [trailer].mp4").write_bytes(b"trailer")
    (folder / "Movie Folder-[trailer].mp4").write_bytes(b"trailer")

    assert MovieFolderScanner._contains_primary_movie_file(folder) is False
