from __future__ import annotations

from pathlib import Path

from core.download.models import DownloadRequest


class PostProcessor:
    """Placeholder post-processing facade for future file-level workflows."""

    def process(self, output_path: Path, request: DownloadRequest) -> Path:
        """Return output path unchanged until custom post-processing is added."""
        _ = request
        return output_path
