from __future__ import annotations

from pathlib import Path

from core.ebook.models import BookIdentity, BookMetadata


class QualityChecker:
    """Lightweight file and metadata quality checks used by library auditing."""

    SUPPORTED_EXTENSIONS = {".epub", ".mobi", ".azw3", ".azw", ".pdf"}

    def check_format(self, ebook_path: Path) -> str | None:
        suffix = ebook_path.suffix.lower()
        if suffix not in self.SUPPORTED_EXTENSIONS:
            return f"Unsupported format: {suffix}"
        if suffix == ".pdf":
            return "PDF is supported but lower-priority for reflowed readers"
        return None

    def check_identity(self, identity: BookIdentity) -> str | None:
        if identity.confidence_score < 0.5:
            return "Low identification confidence"
        if identity.author.strip().lower() == "unknown":
            return "Unknown author"
        return None

    def metadata_completeness(self, metadata: BookMetadata | None) -> float:
        if metadata is None:
            return 0.0
        return metadata.calculate_completeness()
