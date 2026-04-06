from __future__ import annotations

import functools
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any, ParamSpec, TypeVar

# Compatibility shim: allow `import src.backup...` while the real package
# lives at the source-root top level (`src/backup`).
_REAL_PACKAGE_DIR = Path(__file__).resolve().parents[2] / "backup"
if str(_REAL_PACKAGE_DIR) not in __path__:
    __path__.append(str(_REAL_PACKAGE_DIR))

from .backup_manager import BackupManager  # noqa: E402
from .models import BackupEntry, BackupStatus, MediaType  # noqa: E402

logger = logging.getLogger(__name__)

_P = ParamSpec("_P")
_R = TypeVar("_R")

_manager: BackupManager | None = None


def init(manager: BackupManager | None = None) -> None:
    global _manager
    _manager = manager or BackupManager()


def get_backup_manager() -> BackupManager:
    global _manager
    if _manager is None:
        _manager = BackupManager()
    return _manager


def with_backup(media_type: MediaType, operation: str) -> Callable[[Callable[_P, _R]], Callable[_P, _R]]:
    def decorator(func: Callable[_P, _R]) -> Callable[_P, _R]:
        @functools.wraps(func)
        def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
            manager = get_backup_manager()

            input_path = _guess_path(kwargs, args, ["input_path", "source", "file_path", "input_file"])
            output_path = _guess_path(kwargs, args, ["output_path", "target", "output_file"])

            entry: BackupEntry | None = None
            if input_path is not None and input_path.exists() and input_path.is_file():
                try:
                    entry = manager.create(input_path, operation=operation, media_type=media_type)
                except Exception:
                    logger.warning("Backup creation failed before operation", exc_info=True)

            result = func(*args, **kwargs)

            if entry is not None and output_path is not None:
                try:
                    validation = manager.validate(entry, output_path)
                    if validation.passed:
                        manager.cleanup(entry)
                except Exception:
                    logger.warning("Backup validation/cleanup failed", exc_info=True)
            return result

        return wrapper

    return decorator


def _guess_path(kwargs: dict[str, Any], args: tuple[Any, ...], candidates: list[str]) -> Path | None:
    for name in candidates:
        value = kwargs.get(name)
        if isinstance(value, Path):
            return value
    for arg in args:
        if isinstance(arg, Path):
            return arg
    return None


__all__ = [
    "BackupManager",
    "BackupStatus",
    "MediaType",
    "get_backup_manager",
    "init",
    "with_backup",
]
