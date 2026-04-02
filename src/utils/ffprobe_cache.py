# src/utils/ffprobe_cache.py
"""
Gecachte ffprobe-Ergebnisse — verhindert dass dieselbe Datei
bei jedem Audit-Lauf neu analysiert wird.

Cache-Key: SHA1(Dateipfad + Dateigröße + Änderungsdatum)
Cache-Speicherort: .media-tool-cache/ im Audit-Verzeichnis
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CACHE_DIR_NAME = ".media-tool-cache"
_CACHE_VERSION = 2


def _cache_key(path: Path) -> str:
    stat = path.stat()
    raw = f"{path}|{stat.st_size}|{stat.st_mtime}|v{_CACHE_VERSION}"
    return hashlib.sha1(raw.encode()).hexdigest()


def _cache_file(path: Path, cache_dir: Path) -> Path:
    return cache_dir / f"{_cache_key(path)}.json"


class FfprobeCache:
    """
    Paralleles ffprobe mit Disk-Cache.

    Bereits analysierte Dateien (unveränderter Inhalt) werden
    sofort aus dem Cache gelesen.
    """

    def __init__(
        self,
        cache_dir: Path | None = None,
        max_workers: int = 8,
        probe_fn: Callable[[Path], dict[str, Any]] | None = None,
    ) -> None:
        self._cache_dir = cache_dir
        self._max_workers = max_workers
        self._probe_fn = probe_fn or self._default_probe

    def probe_all(
        self,
        files: list[Path],
        root_dir: Path | None = None,
    ) -> dict[Path, dict[str, Any]]:
        """
        Probiert alle Dateien parallel.  Cache wird automatisch genutzt.

        Returns:
            Mapping von Path → ffprobe-Dict.  Dateien die nicht analysiert
            werden konnten, erhalten einen leeren Dict.
        """
        cache_dir = self._cache_dir or (root_dir / _CACHE_DIR_NAME if root_dir else None)
        if cache_dir:
            cache_dir.mkdir(exist_ok=True)

        results: dict[Path, dict[str, Any]] = {}
        to_probe: list[Path] = []

        for f in files:
            if cache_dir:
                cf = _cache_file(f, cache_dir)
                if cf.exists():
                    try:
                        results[f] = json.loads(cf.read_text(encoding="utf-8"))
                        continue
                    except (json.JSONDecodeError, OSError):
                        pass
            to_probe.append(f)

        if to_probe:
            logger.info(
                "ffprobe: %d Dateien (Cache: %d bereits bekannt) …",
                len(to_probe),
                len(results),
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            future_map = {pool.submit(self._probe_fn, f): f for f in to_probe}
            for future in concurrent.futures.as_completed(future_map):
                f = future_map[future]
                try:
                    probe = future.result()
                    results[f] = probe
                    if cache_dir:
                        _cache_file(f, cache_dir).write_text(json.dumps(probe), encoding="utf-8")
                except Exception as exc:
                    logger.warning("ffprobe fehlgeschlagen für %s: %s", f.name, exc)
                    results[f] = {}

        return results

    @staticmethod
    def _default_probe(path: Path) -> dict[str, Any]:
        from utils.ffprobe_runner import probe_file

        result = probe_file(path)
        return {"streams": result.streams, "format": result.format}
