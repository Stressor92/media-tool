from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from utils.calibre_runner import CalibreConversionError, CalibreNotFoundError, CalibreRunner


class _Completed:
    def __init__(self, stdout: bytes = b"", stderr: bytes = b"") -> None:
        self.stdout = stdout
        self.stderr = stderr


def test_calibre_runner_raises_if_binary_missing(monkeypatch) -> None:
    monkeypatch.setattr("utils.calibre_runner.shutil.which", lambda _name: None)
    with pytest.raises(CalibreNotFoundError):
        CalibreRunner()


def test_calibre_runner_convert_success(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("utils.calibre_runner.shutil.which", lambda _name: "ebook-convert")

    calls: list[list[str]] = []

    def fake_run(cmd: list[str], capture_output: bool, check: bool, timeout: int):
        calls.append(cmd)
        return _Completed(stdout=b"ok")

    monkeypatch.setattr("utils.calibre_runner.subprocess.run", fake_run)

    source = tmp_path / "in.epub"
    target = tmp_path / "out.mobi"
    source.write_text("book", encoding="utf-8")

    runner = CalibreRunner()
    runner.convert(source, target, extra_args=["--output-profile", "kindle"])

    assert calls
    assert calls[0][0] == "ebook-convert"
    assert str(source) in calls[0]
    assert str(target) in calls[0]


def test_calibre_runner_convert_failure_translates_error(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("utils.calibre_runner.shutil.which", lambda _name: "ebook-convert")

    def fake_run(cmd: list[str], capture_output: bool, check: bool, timeout: int):
        raise subprocess.CalledProcessError(1, cmd, stderr=b"broken")

    monkeypatch.setattr("utils.calibre_runner.subprocess.run", fake_run)

    source = tmp_path / "in.epub"
    target = tmp_path / "out.mobi"
    source.write_text("book", encoding="utf-8")

    runner = CalibreRunner()
    with pytest.raises(CalibreConversionError):
        runner.convert(source, target)


def test_calibre_runner_get_metadata_empty_when_meta_binary_missing(monkeypatch, tmp_path: Path) -> None:
    def fake_which(name: str):
        return "ebook-convert" if name == "ebook-convert" else None

    monkeypatch.setattr("utils.calibre_runner.shutil.which", fake_which)
    runner = CalibreRunner()

    metadata = runner.get_metadata(tmp_path / "book.epub")
    assert metadata == {}


def test_calibre_runner_get_metadata_parses_output(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("utils.calibre_runner.shutil.which", lambda _name: "installed")

    def fake_run(cmd: list[str], capture_output: bool, check: bool, timeout: int):
        return _Completed(stdout=b"Title: Dune\nAuthor(s): Frank Herbert\n")

    monkeypatch.setattr("utils.calibre_runner.subprocess.run", fake_run)
    runner = CalibreRunner()

    metadata = runner.get_metadata(tmp_path / "book.epub")
    assert metadata.get("title") == "Dune"
    assert metadata.get("author(s)") == "Frank Herbert"


def test_calibre_runner_get_metadata_handles_subprocess_failure(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("utils.calibre_runner.shutil.which", lambda _name: "installed")

    def fake_run(cmd: list[str], capture_output: bool, check: bool, timeout: int):
        raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr("utils.calibre_runner.subprocess.run", fake_run)
    runner = CalibreRunner()

    metadata = runner.get_metadata(tmp_path / "book.epub")
    assert metadata == {}
