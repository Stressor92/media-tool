from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from cli.main import app
from tests.ebook_test_support import create_minimal_epub
from utils.config import reset_config_cache


runner = CliRunner()


def test_ebook_identify_command_outputs_identity(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "media-tool.toml"
    config_path.write_text(
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
    monkeypatch.setenv("MEDIA_TOOL_CONFIG", str(config_path))
    reset_config_cache()

    ebook = tmp_path / "book.epub"
    create_minimal_epub(ebook, title="Dune", author="Frank Herbert")

    result = runner.invoke(app, ["ebook", "identify", str(ebook)])

    assert result.exit_code == 0
    assert "Book Identity" in result.stdout
    assert "Dune" in result.stdout
    assert "Frank Herbert" in result.stdout
