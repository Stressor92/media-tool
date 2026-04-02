from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from cli.main import app
from core.ebook.models import DuplicateGroup, ProcessingResult
from utils.config import reset_config_cache

runner = CliRunner()


def _write_config(path: Path) -> None:
    path.write_text(
        """
[ebook]
preferred_format = "epub"
download_cover = true
metadata_providers = ["openlibrary", "googlebooks"]

[ebook.organization]
structure = "{author}/{series}/{title}"

[ebook.conversion]
target_format = "epub"
""".strip(),
        encoding="utf-8",
    )


class _Bundle:
    def __init__(self) -> None:
        self.identifier = object()
        self.metadata_service = object()
        self.cover_service = object()
        self.normalizer = object()
        self.isbn_extractor = object()
        self.fuzzy_matcher = object()


def test_ebook_identify_missing_file(tmp_path: Path, monkeypatch) -> None:
    cfg = tmp_path / "media-tool.toml"
    _write_config(cfg)
    monkeypatch.setenv("MEDIA_TOOL_CONFIG", str(cfg))
    reset_config_cache()

    result = runner.invoke(app, ["ebook", "identify", str(tmp_path / "missing.epub")])
    assert result.exit_code == 1


def test_ebook_enrich_no_files(tmp_path: Path, monkeypatch) -> None:
    cfg = tmp_path / "media-tool.toml"
    _write_config(cfg)
    monkeypatch.setenv("MEDIA_TOOL_CONFIG", str(cfg))
    reset_config_cache()

    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    result = runner.invoke(app, ["ebook", "enrich", str(empty_dir)])
    assert result.exit_code == 0
    assert "No supported e-book files found" in result.stdout


def test_ebook_deduplicate_delete_mode(tmp_path: Path, monkeypatch) -> None:
    cfg = tmp_path / "media-tool.toml"
    _write_config(cfg)
    monkeypatch.setenv("MEDIA_TOOL_CONFIG", str(cfg))
    reset_config_cache()

    library = tmp_path / "library"
    library.mkdir()
    keep = library / "book.epub"
    remove = library / "book.mobi"
    keep.write_text("x", encoding="utf-8")
    remove.write_text("y", encoding="utf-8")

    monkeypatch.setattr("cli.ebook_cmd._build_services", lambda: _Bundle())

    class _Finder:
        def __init__(self, **kwargs):
            pass

        def find_duplicates(self, library_path: Path, recursive: bool = True):
            return [DuplicateGroup(books=[keep, remove], match_confidence=0.95, best_version=keep, reason="best")]

    monkeypatch.setattr("cli.ebook_cmd.DuplicateFinder", _Finder)

    result = runner.invoke(app, ["ebook", "deduplicate", str(library), "--delete"], input="y\n")
    assert result.exit_code == 0
    assert not remove.exists()


def test_ebook_convert_invalid_format(tmp_path: Path, monkeypatch) -> None:
    cfg = tmp_path / "media-tool.toml"
    _write_config(cfg)
    monkeypatch.setenv("MEDIA_TOOL_CONFIG", str(cfg))
    reset_config_cache()

    source = tmp_path / "book.epub"
    source.write_text("x", encoding="utf-8")

    result = runner.invoke(app, ["ebook", "convert", str(source), "txt"])
    assert result.exit_code == 1


def test_ebook_convert_missing_calibre(tmp_path: Path, monkeypatch) -> None:
    cfg = tmp_path / "media-tool.toml"
    _write_config(cfg)
    monkeypatch.setenv("MEDIA_TOOL_CONFIG", str(cfg))
    reset_config_cache()

    source = tmp_path / "book.epub"
    source.write_text("x", encoding="utf-8")

    class _Err(Exception):
        pass

    from core.ebook.conversion import CalibreNotFoundError

    def _raise():
        raise CalibreNotFoundError("not found")

    monkeypatch.setattr("cli.ebook_cmd.CalibreRunner", _raise)

    result = runner.invoke(app, ["ebook", "convert", str(source), "mobi"])
    assert result.exit_code == 1


def test_ebook_enrich_success_path_with_stub_processor(tmp_path: Path, monkeypatch) -> None:
    cfg = tmp_path / "media-tool.toml"
    _write_config(cfg)
    monkeypatch.setenv("MEDIA_TOOL_CONFIG", str(cfg))
    reset_config_cache()

    source = tmp_path / "book.epub"
    source.write_text("x", encoding="utf-8")

    monkeypatch.setattr("cli.ebook_cmd._build_services", lambda: _Bundle())

    class _Processor:
        def __init__(self, **kwargs):
            pass

        def enrich(self, ebook_path: Path, **kwargs):
            return ProcessingResult(ebook_path=ebook_path, success=True, identified=True)

    monkeypatch.setattr("cli.ebook_cmd.EbookProcessor", _Processor)

    result = runner.invoke(app, ["ebook", "enrich", str(source), "--dry-run"])
    assert result.exit_code == 0
    assert "Processing Results" in result.stdout


def test_ebook_organize_success_path_with_stub_processor(tmp_path: Path, monkeypatch) -> None:
    cfg = tmp_path / "media-tool.toml"
    _write_config(cfg)
    monkeypatch.setenv("MEDIA_TOOL_CONFIG", str(cfg))
    reset_config_cache()

    source = tmp_path / "source"
    source.mkdir()
    (source / "book.epub").write_text("x", encoding="utf-8")
    library = tmp_path / "library"

    monkeypatch.setattr("cli.ebook_cmd._build_services", lambda: _Bundle())

    class _Processor:
        def __init__(self, **kwargs):
            pass

        def organize_library(self, source_path: Path, library_root: Path, **kwargs):
            return [ProcessingResult(ebook_path=source_path / "book.epub", success=True, organized=True)]

    monkeypatch.setattr("cli.ebook_cmd.EbookProcessor", _Processor)

    result = runner.invoke(app, ["ebook", "organize", str(source), str(library), "--dry-run"])
    assert result.exit_code == 0
    assert "Processing Results" in result.stdout
