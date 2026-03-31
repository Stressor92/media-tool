from __future__ import annotations

from pathlib import Path


def ensure_image_file(path: Path) -> bool:
    """Lightweight validation to ensure an image file exists and is non-empty."""
    return path.exists() and path.is_file() and path.stat().st_size > 0
