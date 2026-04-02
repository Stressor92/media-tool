# src/core/translation/translation_cache.py
"""
In-memory (+ optional JSON file) translation cache.

Avoids re-translating identical text segments across multiple files or
repeated runs.  Keyed on (source_lang, target_lang, source_text).

Usage
-----
    cache = TranslationCache()
    if (hit := cache.get("en", "de", "Hello")) is not None:
        return hit
    translation = translator.translate(...)
    cache.put("en", "de", "Hello", translation)
    cache.save()       # persist to disk (optional)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# JSON structure: {"en→de": {"Hello": "Hallo", ...}, ...}
_CacheStore = dict[str, dict[str, str]]


class TranslationCache:
    """
    Thread-unsafe in-memory cache with optional JSON persistence.

    Parameters
    ----------
    cache_file:
        Path to a JSON file for persistence between runs.
        If None (default), data is in-memory only.
    """

    def __init__(self, cache_file: Path | None = None) -> None:
        self._cache_file = cache_file
        self._store: _CacheStore = {}
        self._hits = 0
        self._misses = 0

        if cache_file and cache_file.exists():
            self._load(cache_file)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get(self, source_lang: str, target_lang: str, text: str) -> str | None:
        """Return cached translation or None."""
        bucket = self._store.get(self._key(source_lang, target_lang))
        if bucket:
            hit = bucket.get(text)
            if hit is not None:
                self._hits += 1
                return hit
        self._misses += 1
        return None

    def put(self, source_lang: str, target_lang: str, text: str, translation: str) -> None:
        """Store a translation in the cache."""
        k = self._key(source_lang, target_lang)
        if k not in self._store:
            self._store[k] = {}
        self._store[k][text] = translation

    def save(self) -> None:
        """Write cache to disk (no-op if no cache_file was configured)."""
        if not self._cache_file:
            return
        self._cache_file.parent.mkdir(parents=True, exist_ok=True)
        self._cache_file.write_text(
            json.dumps(self._store, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.debug("Translation cache saved: %s entries", self.size)

    def clear(self) -> None:
        """Remove all cached entries (in-memory only)."""
        self._store.clear()
        self._hits = 0
        self._misses = 0

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    @property
    def size(self) -> int:
        return sum(len(v) for v in self._store.values())

    @property
    def hits(self) -> int:
        return self._hits

    @property
    def misses(self) -> int:
        return self._misses

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total else 0.0

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _key(source_lang: str, target_lang: str) -> str:
        return f"{source_lang}→{target_lang}"

    def _load(self, path: Path) -> None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self._store = data
                logger.debug("Translation cache loaded: %s entries from %s", self.size, path)
        except Exception as exc:
            logger.warning("Could not load translation cache from %s: %s", path, exc)
