from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from rich.logging import RichHandler

from utils.logging_config import ContextFormatter, setup_logging


def _reset_root_logger() -> None:
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
    root.setLevel(logging.NOTSET)


def test_setup_logging_default_level_warning() -> None:
    _reset_root_logger()
    setup_logging()

    root = logging.getLogger()
    assert root.level == logging.WARNING
    assert any(isinstance(h, RichHandler) for h in root.handlers)


def test_setup_logging_verbose_sets_info() -> None:
    _reset_root_logger()
    setup_logging(verbose=True)

    root = logging.getLogger()
    assert root.level == logging.INFO


def test_setup_logging_debug_sets_debug() -> None:
    _reset_root_logger()
    setup_logging(debug=True)

    root = logging.getLogger()
    assert root.level == logging.DEBUG


def test_setup_logging_quiet_overrides_verbose_and_debug() -> None:
    _reset_root_logger()
    setup_logging(verbose=True, debug=True, quiet=True)

    root = logging.getLogger()
    assert root.level == logging.WARNING


def test_setup_logging_adds_rotating_file_handler(tmp_path: Path) -> None:
    _reset_root_logger()
    log_path = tmp_path / "logs" / "media-tool.log"

    setup_logging(log_file=log_path)

    root = logging.getLogger()
    file_handlers = [h for h in root.handlers if isinstance(h, RotatingFileHandler)]

    assert len(file_handlers) == 1
    assert log_path.parent.exists()

    root.info("test line")
    for handler in file_handlers:
        handler.flush()

    assert log_path.exists()


def test_setup_logging_json_file_formatter(tmp_path: Path) -> None:
    _reset_root_logger()
    log_path = tmp_path / "logs" / "media-tool.jsonl"

    setup_logging(log_file=log_path, log_json=True, debug=True)

    root = logging.getLogger()
    root.debug("json-message")

    for handler in root.handlers:
        if isinstance(handler, RotatingFileHandler):
            handler.flush()

    content = log_path.read_text(encoding="utf-8")
    assert '"message": "json-message"' in content
    assert '"level": "DEBUG"' in content


def test_context_formatter_renders_structured_context() -> None:
    formatter = ContextFormatter("%(levelname)s | %(message)s")
    record = logging.LogRecord(
        name="test.logger",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="provider failed",
        args=(),
        exc_info=None,
    )
    record.context = {"error": "timed out", "title": "Dune"}

    rendered = formatter.format(record)

    assert "provider failed" in rendered
    assert "error=timed out" in rendered
    assert "title=Dune" in rendered
