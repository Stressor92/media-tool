from __future__ import annotations

from difflib import SequenceMatcher


class FuzzyMatcher:
    """Simple string similarity matcher for metadata ranking."""

    @staticmethod
    def similarity(str1: str, str2: str) -> float:
        """Return normalized similarity between two strings."""
        return SequenceMatcher(None, str1.lower().strip(), str2.lower().strip()).ratio()

    @staticmethod
    def is_similar(str1: str, str2: str, threshold: float = 0.8) -> bool:
        """Return True when similarity is above the supplied threshold."""
        return FuzzyMatcher.similarity(str1, str2) >= threshold