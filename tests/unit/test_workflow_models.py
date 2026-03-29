"""
tests/unit/test_workflow_models.py

Unit tests for core.workflow.models.
"""

from pathlib import Path

from core.workflow.models import (
    StepResult,
    StepStatus,
    WorkflowContext,
    WorkflowResult,
)


def test_context_add_result(tmp_path: Path) -> None:
    ctx = WorkflowContext(source_dir=tmp_path, output_dir=tmp_path)
    r = StepResult(step_name="test", status=StepStatus.SUCCESS, message="ok")
    ctx.add_result(r)
    assert ctx.last_result() is r
    assert len(ctx.completed_steps) == 1


def test_context_last_result_empty(tmp_path: Path) -> None:
    ctx = WorkflowContext(source_dir=tmp_path, output_dir=tmp_path)
    assert ctx.last_result() is None


def test_context_defaults(tmp_path: Path) -> None:
    ctx = WorkflowContext(source_dir=tmp_path, output_dir=tmp_path)
    assert ctx.dry_run is False
    assert ctx.stop_on_failure is True
    assert ctx.working_files == []
    assert ctx.metadata == {}


def test_workflow_result_succeeded(tmp_path: Path) -> None:
    ctx = WorkflowContext(source_dir=tmp_path, output_dir=tmp_path)
    wr = WorkflowResult(context=ctx, overall_status=StepStatus.SUCCESS)
    assert wr.succeeded is True


def test_workflow_result_failed_steps(tmp_path: Path) -> None:
    ctx = WorkflowContext(source_dir=tmp_path, output_dir=tmp_path)
    results = [
        StepResult("s1", StepStatus.SUCCESS, "ok"),
        StepResult("s2", StepStatus.FAILED, "boom"),
        StepResult("s3", StepStatus.SKIPPED, "skip"),
    ]
    wr = WorkflowResult(
        context=ctx,
        overall_status=StepStatus.FAILED,
        step_results=results,
    )
    assert len(wr.failed_steps) == 1
    assert len(wr.skipped_steps) == 1
    assert wr.failed_steps[0].step_name == "s2"
    assert not wr.succeeded


def test_step_result_default_collections(tmp_path: Path) -> None:
    r = StepResult(step_name="x", status=StepStatus.SUCCESS, message="ok")
    assert r.output_files == []
    assert r.deleted_files == []
    assert r.details == {}
