# tests/unit/test_translation_cache.py
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from core.translation.translation_cache import TranslationCache


class TestTranslationCacheMemory:
    def test_miss_returns_none(self) -> None:
        cache = TranslationCache()
        assert cache.get("en", "de", "Hello") is None

    def test_put_then_get(self) -> None:
        cache = TranslationCache()
        cache.put("en", "de", "Hello", "Hallo")
        assert cache.get("en", "de", "Hello") == "Hallo"

    def test_different_direction_is_separate(self) -> None:
        cache = TranslationCache()
        cache.put("en", "de", "Hello", "Hallo")
        assert cache.get("de", "en", "Hello") is None

    def test_size_counts_entries(self) -> None:
        cache = TranslationCache()
        cache.put("en", "de", "A", "B")
        cache.put("en", "de", "C", "D")
        assert cache.size == 2

    def test_hit_miss_counters(self) -> None:
        cache = TranslationCache()
        cache.put("en", "de", "Word", "Wort")
        cache.get("en", "de", "Word")   # hit
        cache.get("en", "de", "Other")  # miss
        assert cache.hits == 1
        assert cache.misses == 1

    def test_hit_rate(self) -> None:
        cache = TranslationCache()
        cache.put("en", "de", "Word", "Wort")
        cache.get("en", "de", "Word")
        cache.get("en", "de", "Word")
        cache.get("en", "de", "Missing")
        assert abs(cache.hit_rate - 2/3) < 0.01

    def test_clear(self) -> None:
        cache = TranslationCache()
        cache.put("en", "de", "A", "B")
        cache.clear()
        assert cache.size == 0
        assert cache.get("en", "de", "A") is None


class TestTranslationCachePersistence:
    def test_save_and_load(self, tmp_path: Path) -> None:
        cache_file = tmp_path / "cache.json"
        cache = TranslationCache(cache_file=cache_file)
        cache.put("en", "de", "Hello", "Hallo")
        cache.save()

        assert cache_file.exists()
        loaded = TranslationCache(cache_file=cache_file)
        assert loaded.get("en", "de", "Hello") == "Hallo"

    def test_save_creates_directory(self, tmp_path: Path) -> None:
        cache_file = tmp_path / "sub" / "nested" / "cache.json"
        cache = TranslationCache(cache_file=cache_file)
        cache.put("en", "de", "Test", "Test")
        cache.save()
        assert cache_file.exists()

    def test_corrupt_file_does_not_crash(self, tmp_path: Path) -> None:
        cache_file = tmp_path / "cache.json"
        cache_file.write_text("THIS IS NOT JSON!!!")
        # Should not raise; cache starts empty
        cache = TranslationCache(cache_file=cache_file)
        assert cache.size == 0

    def test_save_is_noop_without_file(self) -> None:
        # Must not raise
        cache = TranslationCache()
        cache.put("en", "de", "A", "B")
        cache.save()  # no-op
