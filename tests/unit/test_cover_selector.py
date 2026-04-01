from __future__ import annotations

from core.ebook.cover.cover_selector import CoverSelector
from core.ebook.cover.providers.provider import CoverImage


def _cover(width: int, height: int, image_format: str = "jpeg", source: str = "test") -> CoverImage:
    return CoverImage(b"bytes", width, height, image_format, source, "https://example.com/cover.jpg")


def test_select_best_prefers_resolution_and_aspect_ratio() -> None:
    selector = CoverSelector()
    best = selector.select_best([
        _cover(500, 500, "png"),
        _cover(900, 1400, "jpeg"),
        _cover(700, 1200, "jpeg"),
    ])

    assert best is not None
    assert best.width == 900
    assert best.height == 1400


def test_select_best_returns_none_when_resolution_too_low() -> None:
    selector = CoverSelector()

    assert selector.select_best([_cover(100, 150)], min_resolution=500_000) is None