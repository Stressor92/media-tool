from __future__ import annotations

import json
import logging
import os
import shutil
from dataclasses import asdict, fields, is_dataclass
from datetime import datetime
from pathlib import Path
from types import NoneType
from typing import Any, TypeVar, Union, get_args, get_origin, get_type_hints

from utils.config import get_config

from .stats_models import StatsSnapshot

logger = logging.getLogger(__name__)

_T = TypeVar("_T")


class StatsPersistence:
    def __init__(self, data_dir: Path | None = None) -> None:
        self._data_dir = data_dir or self._resolve_data_dir()
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._path = self._data_dir / "stats.json"

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> StatsSnapshot:
        if not self._path.exists():
            return StatsSnapshot()

        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                logger.warning("Statistics file has invalid structure; creating a clean snapshot.")
                return StatsSnapshot()
            snapshot = _from_dict(StatsSnapshot, raw)
            if not isinstance(snapshot, StatsSnapshot):
                return StatsSnapshot()
            return snapshot
        except json.JSONDecodeError:
            logger.warning("Corrupt statistics JSON detected; creating backup and resetting snapshot.")
            self._backup_corrupt_file()
            return StatsSnapshot()
        except OSError as exc:
            logger.warning("Unable to read statistics file: %s", exc)
            return StatsSnapshot()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Unexpected statistics loading error: %s", exc)
            return StatsSnapshot()

    def save(self, snapshot: StatsSnapshot) -> None:
        payload = asdict(snapshot)
        payload["last_updated"] = datetime.now().date().isoformat()

        tmp_path = self._path.with_suffix(".json.tmp")
        try:
            tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
            tmp_path.replace(self._path)
        except OSError as exc:
            logger.warning("Failed to save statistics snapshot: %s", exc)
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                logger.debug("Could not remove temporary statistics file", exc_info=True)

    def backup(self) -> Path:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_path = self._data_dir / f"stats_{timestamp}.bak.json"
        if self._path.exists():
            shutil.copy2(self._path, backup_path)
        else:
            backup_path.write_text("{}", encoding="utf-8")
        return backup_path

    @staticmethod
    def _resolve_data_dir() -> Path:
        default_dir = Path.home() / ".media-tool"
        configured_dir: Path | None = None

        try:
            config = get_config()
            statistics_table = getattr(config, "statistics", None)
            if statistics_table is not None:
                raw_data_dir = getattr(statistics_table, "data_dir", "")
                if isinstance(raw_data_dir, str) and raw_data_dir.strip():
                    configured_dir = Path(raw_data_dir).expanduser()
        except Exception:
            configured_dir = None

        env_override = os.environ.get("MEDIA_TOOL_STATS_DIR", "").strip()
        if env_override:
            return Path(env_override).expanduser()
        if configured_dir is not None:
            return configured_dir
        return default_dir

    def _backup_corrupt_file(self) -> None:
        bak_path = self._path.with_suffix(".json.bak")
        try:
            shutil.copy2(self._path, bak_path)
        except OSError:
            logger.debug("Could not create backup for corrupt statistics file", exc_info=True)


def _from_dict(cls: type[_T], data: Any) -> _T:
    if not is_dataclass(cls):
        return data

    if not isinstance(data, dict):
        return cls()

    result: dict[str, Any] = {}
    type_hints = get_type_hints(cls)
    for model_field in fields(cls):
        key = model_field.name
        if key not in data:
            continue
        annotation = type_hints.get(model_field.name, model_field.type)
        result[key] = _convert_value(data[key], annotation)

    return cls(**result)


def _convert_value(value: Any, annotation: Any) -> Any:
    origin = get_origin(annotation)

    if origin is Union:
        args = [arg for arg in get_args(annotation) if arg is not NoneType]
        if not args:
            return value
        return _convert_value(value, args[0])

    if origin is dict:
        dict_args = get_args(annotation)
        if len(dict_args) != 2 or not isinstance(value, dict):
            return {}
        _, value_type = dict_args
        converted: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                continue
            converted[key] = _convert_value(item, value_type)
        return converted

    if isinstance(annotation, type) and is_dataclass(annotation):
        return _from_dict(annotation, value)

    if isinstance(value, list):
        return value

    return value
