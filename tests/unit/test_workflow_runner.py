"""
tests/unit/test_workflow_runner.py

Unit tests for WorkflowRunner – fully mocked, no filesystem or FFmpeg needed.
"""

from pathlib import Path

import pytest

from core.workflow.models import StepResult, StepStatus, WorkflowContext
from core.workflow.runner import WorkflowRunner
from core.workflow.step import BaseStep

# ---------------------------------------------------------------------------
# Minimal stub steps
# ---------------------------------------------------------------------------


class _AlwaysSuccess(BaseStep):
    name = "always_success"

    def precondition(self, ctx: WorkflowContext) -> bool:
        return True

    def run(self, ctx: WorkflowContext) -> StepResult:
        return StepResult(self.name, StepStatus.SUCCESS, "ok")


class _AlwaysSkip(BaseStep):
    name = "always_skip"

    def precondition(self, ctx: WorkflowContext) -> bool:
        return False

    def run(self, ctx: WorkflowContext) -> StepResult:
        return StepResult(self.name, StepStatus.SUCCESS, "should not run")


class _AlwaysFail(BaseStep):
    name = "always_fail"

    def precondition(self, ctx: WorkflowContext) -> bool:
        return True

    def run(self, ctx: WorkflowContext) -> StepResult:
        return StepResult(self.name, StepStatus.FAILED, "boom")


class _AlwaysRaise(BaseStep):
    name = "always_raise"

    def precondition(self, ctx: WorkflowContext) -> bool:
        return True

    def run(self, ctx: WorkflowContext) -> StepResult:
        raise RuntimeError("unexpected error")


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def ctx(tmp_path: Path) -> WorkflowContext:
    return WorkflowContext(source_dir=tmp_path, output_dir=tmp_path)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_all_success(ctx: WorkflowContext) -> None:
    runner = WorkflowRunner([_AlwaysSuccess(), _AlwaysSuccess()])
    result = runner.run(ctx)
    assert result.overall_status == StepStatus.SUCCESS
    assert len(result.step_results) == 2


def test_skip_does_not_fail(ctx: WorkflowContext) -> None:
    runner = WorkflowRunner([_AlwaysSkip(), _AlwaysSuccess()])
    result = runner.run(ctx)
    assert result.overall_status == StepStatus.SUCCESS
    assert result.step_results[0].status == StepStatus.SKIPPED


def test_stop_on_failure(ctx: WorkflowContext) -> None:
    ctx.stop_on_failure = True
    runner = WorkflowRunner([_AlwaysFail(), _AlwaysSuccess()])
    result = runner.run(ctx)
    assert result.overall_status == StepStatus.FAILED
    # Second step must NOT have run
    assert len(result.step_results) == 1


def test_keep_going_on_failure(ctx: WorkflowContext) -> None:
    ctx.stop_on_failure = False
    runner = WorkflowRunner([_AlwaysFail(), _AlwaysSuccess()])
    result = runner.run(ctx)
    assert len(result.step_results) == 2
    assert result.overall_status == StepStatus.FAILED  # one step failed


def test_exception_in_run_is_caught(ctx: WorkflowContext) -> None:
    runner = WorkflowRunner([_AlwaysRaise()])
    result = runner.run(ctx)
    assert result.step_results[0].status == StepStatus.FAILED
    assert "unexpected error" in result.step_results[0].message


def test_post_check_failure_marks_step_failed(ctx: WorkflowContext) -> None:
    class BadPostCheck(_AlwaysSuccess):
        name = "bad_post"

        def post_check(self, ctx: WorkflowContext, result: StepResult) -> bool:
            return False

    runner = WorkflowRunner([BadPostCheck()])
    result = runner.run(ctx)
    assert result.step_results[0].status == StepStatus.FAILED
    assert "[post_check failed]" in result.step_results[0].message


def test_empty_pipeline(ctx: WorkflowContext) -> None:
    runner = WorkflowRunner([])
    result = runner.run(ctx)
    assert result.overall_status == StepStatus.SUCCESS
    assert result.step_results == []


def test_all_skipped_is_success(ctx: WorkflowContext) -> None:
    runner = WorkflowRunner([_AlwaysSkip(), _AlwaysSkip()])
    result = runner.run(ctx)
    assert result.overall_status == StepStatus.SUCCESS
