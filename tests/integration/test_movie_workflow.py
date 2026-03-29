"""
tests/integration/test_movie_workflow.py

Integration tests for the full movie pipeline.

Requires: MEDIA_TOOL_INTEGRATION_TESTS=1 (opt-in, same gate as other integration tests).
Dry-run tests need no network and no FFmpeg – they run unconditionally.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.workflow.models import StepStatus, WorkflowContext
from core.workflow.runner import build_movie_pipeline


@pytest.mark.integration
class TestMovieWorkflowDryRun:
    """Dry-Run tests – no network, no FFmpeg invocations."""

    def test_empty_source_dir_all_steps_skipped(self, tmp_path: Path) -> None:
        src = tmp_path / "source"
        out = tmp_path / "output"
        src.mkdir()
        out.mkdir()

        ctx = WorkflowContext(
            source_dir=src,
            output_dir=out,
            dry_run=True,
        )

        result = build_movie_pipeline().run(ctx)

        # No media → every step's precondition is False → all SKIPPED
        assert all(r.status == StepStatus.SKIPPED for r in result.step_results)
        # Overall is still SUCCESS because no step FAILED
        assert result.overall_status == StepStatus.SUCCESS

    def test_dry_run_creates_no_files(self, tmp_path: Path) -> None:
        src = tmp_path / "source"
        out = tmp_path / "output"
        src.mkdir()
        out.mkdir()
        # A zero-byte MP4 that will never be read in dry_run mode
        (src / "Movie (2020).mp4").touch()

        ctx = WorkflowContext(source_dir=src, output_dir=out, dry_run=True)
        build_movie_pipeline().run(ctx)

        # Output directory must stay empty – nothing was written
        assert list(out.rglob("*")) == []

    def test_pipeline_result_has_six_step_results(self, tmp_path: Path) -> None:
        src = tmp_path / "source"
        out = tmp_path / "output"
        src.mkdir()
        out.mkdir()

        ctx = WorkflowContext(source_dir=src, output_dir=out, dry_run=True)
        result = build_movie_pipeline().run(ctx)

        assert len(result.step_results) == 6

    def test_stop_on_failure_default_is_true(self, tmp_path: Path) -> None:
        ctx = WorkflowContext(source_dir=tmp_path, output_dir=tmp_path)
        assert ctx.stop_on_failure is True

    def test_context_working_files_empty_at_start(self, tmp_path: Path) -> None:
        ctx = WorkflowContext(source_dir=tmp_path, output_dir=tmp_path, dry_run=True)
        build_movie_pipeline().run(ctx)
        # After empty source dir run, working_files should still be empty
        assert ctx.working_files == []
