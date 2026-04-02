from __future__ import annotations

import re


class NamingService:
    """Naming helpers for filesystem-safe, deterministic ebook paths."""

    @staticmethod
    def sanitize_filename(name: str, max_length: int = 200) -> str:
        cleaned = re.sub(r"[<>:\"/\\|?*]", "", name)
        cleaned = re.sub(r"\s+", " ", cleaned)
        cleaned = cleaned.strip(" .")

        if len(cleaned) > max_length:
            trimmed = cleaned[:max_length]
            if " " in trimmed:
                trimmed = trimmed.rsplit(" ", 1)[0]
            cleaned = trimmed

        return cleaned or "Unknown"

    @staticmethod
    def format_series_name(series: str, index: float | None) -> str:
        if index is None:
            return series
        if index == int(index):
            return f"{series} #{int(index)}"
        return f"{series} #{index}"
