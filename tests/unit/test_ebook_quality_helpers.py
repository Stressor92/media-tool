from __future__ import annotations

from pathlib import Path

from core.ebook.audit.quality_checker import QualityChecker
from core.ebook.audit.series_analyzer import SeriesAnalyzer
from core.ebook.models import BookIdentity, BookMetadata


def test_quality_checker_format_and_identity() -> None:
    checker = QualityChecker()

    assert checker.check_format(Path("x.pdf")) is not None
    assert checker.check_format(Path("x.epub")) is None

    low = BookIdentity(title="A", author="Unknown", confidence_score=0.2)
    assert checker.check_identity(low) == "Low identification confidence"

    good = BookIdentity(title="A", author="B", confidence_score=0.9)
    assert checker.check_identity(good) is None

    assert checker.metadata_completeness(None) == 0.0
    meta = BookMetadata(title="A", author="B", source="test")
    assert checker.metadata_completeness(meta) > 0.0


def test_series_analyzer_gaps_and_incomplete() -> None:
    analyzer = SeriesAnalyzer()
    grouped = analyzer.group(
        [
            ("Saga", 1.0),
            ("Saga", 3.0),
            ("Short", 1.0),
        ]
    )

    gaps = analyzer.find_gaps(grouped)
    incomplete = analyzer.find_incomplete(grouped)

    assert "Saga: Missing #2 to #2" in gaps
    assert "Short (1 books)" in incomplete
