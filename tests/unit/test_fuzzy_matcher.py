from __future__ import annotations

from utils.fuzzy_matcher import FuzzyMatcher


def test_similarity_is_case_insensitive() -> None:
    assert FuzzyMatcher.similarity("Dune", "dune") == 1.0


def test_is_similar_uses_threshold() -> None:
    assert FuzzyMatcher.is_similar("The Hobbit", "Hobbit, The", threshold=0.4) is True
    assert FuzzyMatcher.is_similar("The Hobbit", "Neuromancer", threshold=0.8) is False