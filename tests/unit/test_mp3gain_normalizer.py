from __future__ import annotations

from pathlib import Path

from core.audio.mp3gain_normalizer import MP3GainNormalizer, MP3GainStatus
from utils.mp3gain_runner import MP3GainResult


def _success_result(args: list[str]) -> MP3GainResult:
    return MP3GainResult(
        success=True,
        return_code=0,
        command=["mp3gain", *args],
        stderr_bytes=b"",
        stdout_bytes=b"",
    )


def test_normalize_path_missing_returns_failed(tmp_path: Path) -> None:
    result = MP3GainNormalizer(runner=_success_result).normalize_path(tmp_path / "missing.mp3")

    assert len(result) == 1
    assert result[0].status == MP3GainStatus.FAILED
    assert "nicht gefunden" in (result[0].error or "")


def test_normalize_path_skips_non_mp3_file(tmp_path: Path) -> None:
    text_file = tmp_path / "notes.txt"
    text_file.write_text("n/a", encoding="utf-8")

    result = MP3GainNormalizer(runner=_success_result).normalize_path(text_file)

    assert len(result) == 1
    assert result[0].status == MP3GainStatus.SKIPPED
    assert "MP3" in (result[0].error or "")


def test_normalize_directory_track_mode_uses_track_args(tmp_path: Path) -> None:
    track_a = tmp_path / "a.mp3"
    track_b = tmp_path / "b.MP3"
    other = tmp_path / "cover.jpg"
    track_a.touch()
    track_b.touch()
    other.touch()

    calls: list[list[str]] = []

    def _runner(args: list[str]) -> MP3GainResult:
        calls.append(args)
        return _success_result(args)

    results = MP3GainNormalizer(runner=_runner).normalize_path(
        tmp_path,
        recursive=False,
        album_mode=False,
        target_db=91.0,
        prevent_clipping=True,
    )

    updated = [item for item in results if item.status == MP3GainStatus.UPDATED]
    skipped = [item for item in results if item.status == MP3GainStatus.SKIPPED]
    assert len(updated) == 2
    assert len(skipped) == 1
    assert calls and calls[0][0] == "-r"
    assert "-k" in calls[0]
    assert "-d" in calls[0]
    assert "2.0" in calls[0]


def test_normalize_directory_album_mode_groups_per_folder(tmp_path: Path) -> None:
    album_one = tmp_path / "Album One"
    album_two = tmp_path / "Album Two"
    album_one.mkdir()
    album_two.mkdir()
    (album_one / "track1.mp3").touch()
    (album_two / "track1.mp3").touch()

    calls: list[list[str]] = []

    def _runner(args: list[str]) -> MP3GainResult:
        calls.append(args)
        return _success_result(args)

    results = MP3GainNormalizer(runner=_runner).normalize_path(tmp_path, recursive=True, album_mode=True)

    assert len([item for item in results if item.status == MP3GainStatus.UPDATED]) == 2
    assert len(calls) == 2
    assert all(call[0] == "-a" for call in calls)


def test_failed_batch_is_retried_per_file(tmp_path: Path) -> None:
    first = tmp_path / "first.mp3"
    second = tmp_path / "second.mp3"
    first.touch()
    second.touch()

    calls: list[list[str]] = []

    def _flaky_runner(args: list[str]) -> MP3GainResult:
        calls.append(args)
        mp3_args = [item for item in args if item.lower().endswith(".mp3")]
        if len(mp3_args) > 1:
            return MP3GainResult(
                success=False,
                return_code=1,
                command=["mp3gain", *args],
                stderr_bytes=b"batch failed",
                stdout_bytes=b"",
            )
        return _success_result(args)

    results = MP3GainNormalizer(runner=_flaky_runner).normalize_path(tmp_path, recursive=False)

    assert len(calls) == 3
    assert len([item for item in results if item.status == MP3GainStatus.UPDATED]) == 2


def test_single_file_fails_when_runner_reports_cant_open_with_exit_zero(tmp_path: Path) -> None:
    file_path = tmp_path / "broken.mp3"
    file_path.touch()

    def _runner(_args: list[str]) -> MP3GainResult:
        return MP3GainResult(
            success=True,
            return_code=0,
            command=["mp3gain"],
            stderr_bytes=b"Can't open broken.mp3 for reading",
            stdout_bytes=b"",
        )

    results = MP3GainNormalizer(runner=_runner).normalize_path(file_path)

    assert len(results) == 1
    assert results[0].status == MP3GainStatus.FAILED
    assert "Can't open" in (results[0].error or "")


def test_windows_cp1252_unencodable_path_is_reported_as_failed(tmp_path: Path) -> None:
    unicode_file = tmp_path / "音楽.mp3"
    unicode_file.touch()

    normalizer = MP3GainNormalizer(runner=_success_result)
    original = MP3GainNormalizer._supports_mp3gain_path

    try:
        MP3GainNormalizer._supports_mp3gain_path = staticmethod(lambda _path: False)
        results = normalizer.normalize_path(unicode_file)
    finally:
        MP3GainNormalizer._supports_mp3gain_path = original

    assert len(results) == 1
    assert results[0].status == MP3GainStatus.FAILED
    assert "MP3Gain" in (results[0].error or "")
