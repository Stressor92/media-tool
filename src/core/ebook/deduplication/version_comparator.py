from __future__ import annotations

from pathlib import Path


class VersionComparator:
    """Select the best ebook version from duplicate candidates."""

    FORMAT_PRIORITY: dict[str, int] = {
        ".epub": 4,
        ".azw3": 3,
        ".mobi": 2,
        ".pdf": 1,
    }

    def select_best(self, versions: list[Path]) -> Path:
        if not versions:
            raise ValueError("versions must contain at least one path")
        if len(versions) == 1:
            return versions[0]

        scored = [(self._calculate_score(path), path) for path in versions]
        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[0][1]

    def _calculate_score(self, path: Path) -> float:
        format_score = self.FORMAT_PRIORITY.get(path.suffix.lower(), 0) / 4.0

        try:
            size_mb = path.stat().st_size / (1024 * 1024)
        except OSError:
            size_mb = 0.0
        size_score = min(size_mb / 2.0, 1.0)

        stem = path.stem
        noise_penalty = 0.15 if any(token in stem.lower() for token in ["copy", "v2", "final", "new"]) else 0.0
        name_score = max(0.0, 1.0 - (len(stem) / 200.0) - noise_penalty)

        return (format_score * 0.5) + (size_score * 0.3) + (name_score * 0.2)
