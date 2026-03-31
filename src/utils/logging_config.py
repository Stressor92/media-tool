"""Central logging configuration for media-tool CLI applications."""

from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, MutableMapping

from rich.logging import RichHandler


class JsonFormatter(logging.Formatter):
    """Serialize log records as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        context = getattr(record, "context", None)
        if isinstance(context, dict) and context:
            payload["context"] = {
                str(key): context[key]
                for key in sorted(context.keys(), key=str)
            }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True)


class ContextFormatter(logging.Formatter):
    """Append structured context to human-readable log lines."""

    def format(self, record: logging.LogRecord) -> str:
        rendered = super().format(record)
        context = getattr(record, "context", None)
        if not isinstance(context, dict) or not context:
            return rendered

        parts = [f"{key}={context[key]}" for key in sorted(context.keys(), key=str)]
        return f"{rendered} | {' '.join(parts)}"


class ContextAdapter(logging.LoggerAdapter):
    """Logger adapter that merges base context with per-call context."""

    def process(
        self, msg: object, kwargs: MutableMapping[str, Any]
    ) -> tuple[object, MutableMapping[str, Any]]:
        extra = kwargs.get("extra")
        merged: dict[str, Any] = {}

        base_ctx = self.extra.get("context") if isinstance(self.extra, dict) else None
        if isinstance(base_ctx, dict):
            merged.update(base_ctx)

        if isinstance(extra, dict):
            call_ctx = extra.get("context")
            if isinstance(call_ctx, dict):
                merged.update(call_ctx)

        kwargs["extra"] = {"context": merged} if merged else {}
        return msg, kwargs


def get_logger(name: str, **base_context: object) -> logging.Logger | ContextAdapter:
    """Return a logger with optional structured base context."""
    logger = logging.getLogger(name)
    if not base_context:
        return logger
    return ContextAdapter(logger, {"context": dict(base_context)})


def _resolve_level(*, verbose: bool, debug: bool, quiet: bool) -> int:
    if quiet:
        return logging.WARNING
    if debug:
        return logging.DEBUG
    if verbose:
        return logging.INFO
    return logging.WARNING


def setup_logging(
    *,
    verbose: bool = False,
    debug: bool = False,
    quiet: bool = False,
    log_file: Path | None = None,
    log_json: bool = False,
) -> None:
    """Configure root logging handlers for console and optional file output."""

    level = _resolve_level(verbose=verbose, debug=debug, quiet=quiet)
    root = logging.getLogger()

    # Reset handlers to make repeated CLI entry calls deterministic.
    for handler in list(root.handlers):
        root.removeHandler(handler)

    root.setLevel(level)

    console_handler = RichHandler(
        rich_tracebacks=True,
        show_path=False,
        show_time=False,
    )
    console_handler.setLevel(level)
    console_handler.setFormatter(
        ContextFormatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root.addHandler(console_handler)

    if log_file is not None:
        log_path = log_file
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            filename=log_path,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        if log_json:
            file_handler.setFormatter(JsonFormatter())
        else:
            file_handler.setFormatter(
                ContextFormatter(
                    "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
            )
        root.addHandler(file_handler)

    # Keep noisy third-party libraries at INFO unless debug mode is enabled.
    if not debug:
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)
