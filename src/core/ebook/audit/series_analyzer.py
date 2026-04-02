from __future__ import annotations

from collections import defaultdict


class SeriesAnalyzer:
    """Analyze series indexes for gaps and likely incomplete collections."""

    def group(self, entries: list[tuple[str, float | None]]) -> dict[str, list[float]]:
        grouped: dict[str, list[float]] = defaultdict(list)
        for series_name, index in entries:
            if not series_name:
                continue
            if index is not None and index > 0:
                grouped[series_name].append(index)
        return dict(grouped)

    def find_gaps(self, grouped_indices: dict[str, list[float]]) -> list[str]:
        gaps: list[str] = []
        for series_name, raw_indices in grouped_indices.items():
            whole_numbers = sorted({int(i) for i in raw_indices if i >= 1 and float(i).is_integer()})
            if len(whole_numbers) < 2:
                continue
            for left, right in zip(whole_numbers, whole_numbers[1:], strict=False):
                if right - left > 1:
                    gaps.append(f"{series_name}: Missing #{left + 1} to #{right - 1}")
        return gaps

    def find_incomplete(self, grouped_indices: dict[str, list[float]]) -> list[str]:
        return [
            f"{series_name} ({len(indices)} books)"
            for series_name, indices in grouped_indices.items()
            if 1 <= len(indices) <= 2
        ]
