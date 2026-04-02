from __future__ import annotations

from pathlib import Path

from core.ebook.models import ProcessingResult
from core.ebook.workflow.ebook_processor import EbookProcessor
from core.ebook.workflow.workflow_config import WorkflowConfig


class BatchProcessor:
    """Run ebook workflows over batches of files/directories."""

    def __init__(self, processor: EbookProcessor) -> None:
        self.processor = processor

    def enrich_batch(self, files: list[Path], config: WorkflowConfig) -> list[ProcessingResult]:
        return [
            self.processor.enrich(
                ebook_path=file_path,
                fetch_metadata=config.fetch_metadata,
                fetch_cover=config.fetch_cover,
                normalize=config.normalize,
                embed_metadata=config.embed_metadata,
                embed_cover=config.embed_cover,
                dry_run=config.dry_run,
            )
            for file_path in files
        ]
