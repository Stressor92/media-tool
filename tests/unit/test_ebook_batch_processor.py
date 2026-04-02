from __future__ import annotations

from pathlib import Path
from typing import cast

from core.ebook.models import ProcessingResult
from core.ebook.workflow.batch_processor import BatchProcessor
from core.ebook.workflow.ebook_processor import EbookProcessor
from core.ebook.workflow.workflow_config import WorkflowConfig


class _Processor:
    def enrich(self, ebook_path: Path, **kwargs) -> ProcessingResult:
        return ProcessingResult(ebook_path=ebook_path, success=True, identified=True)


def test_batch_processor_enrich_batch(tmp_path: Path) -> None:
    files = [tmp_path / "a.epub", tmp_path / "b.epub"]
    for item in files:
        item.write_text("x", encoding="utf-8")

    batch = BatchProcessor(cast(EbookProcessor, _Processor()))
    results = batch.enrich_batch(files, WorkflowConfig())

    assert len(results) == 2
    assert all(result.success for result in results)
