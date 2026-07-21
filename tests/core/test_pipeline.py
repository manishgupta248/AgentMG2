"""
Regression tests for Pipeline definition and run_pipeline execution.
"""

import pytest

from app.core.registry import autodiscover_tools
from app.core.approval import AutoApprovalHandler
from app.core.exceptions import WorkflowError
from app.router.pipeline import Pipeline, PipelineStep, register_pipeline, get_pipeline, run_pipeline


def test_register_and_get_pipeline():
    pipeline = Pipeline(name="_test_pipeline_1", steps=[PipelineStep(tool_name="ping")])
    register_pipeline(pipeline)
    assert get_pipeline("_test_pipeline_1") is pipeline


def test_run_pipeline_raises_for_unregistered_pipeline(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)
    autodiscover_tools()

    with pytest.raises(WorkflowError, match="not registered"):
        run_pipeline("_definitely_not_a_real_pipeline")


def test_run_pipeline_executes_single_step(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)
    autodiscover_tools()

    register_pipeline(Pipeline(name="_test_single_step", steps=[PipelineStep(tool_name="ping")]))
    results = run_pipeline("_test_single_step", approval_handler=AutoApprovalHandler())

    assert len(results) == 1
    assert results[0].success is True


def test_run_pipeline_chains_step_results_via_reference(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)
    autodiscover_tools()

    register_pipeline(Pipeline(
        name="_test_chained_pipeline",
        steps=[
            PipelineStep(tool_name="kb_add", tool_kwargs={"kind": "note", "content": "chain test"}),
            PipelineStep(tool_name="kb_get", tool_kwargs={"entry_id": "$step0.id"}),
        ],
    ))

    results = run_pipeline("_test_chained_pipeline", approval_handler=AutoApprovalHandler())

    assert results[0].success is True
    assert results[1].success is True
    assert results[1].data["content"] == "chain test"


def test_run_pipeline_raises_on_unresolvable_reference_before_executing_that_step(isolated_db, monkeypatch):
    """A step referencing a nonexistent field from a prior step must
    fail loudly rather than passing the literal string through to the
    tool call."""
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)
    autodiscover_tools()

    register_pipeline(Pipeline(
        name="_test_bad_reference_pipeline",
        steps=[
            PipelineStep(tool_name="kb_add", tool_kwargs={"kind": "note", "content": "test"}),
            PipelineStep(tool_name="kb_get", tool_kwargs={"entry_id": "$step0.nonexistent_field"}),
        ],
    ))

    with pytest.raises(WorkflowError):
        run_pipeline("_test_bad_reference_pipeline", approval_handler=AutoApprovalHandler())


def test_run_pipeline_stops_at_first_failing_step(isolated_db, monkeypatch):
    """If step 0 fails, step 1 must never execute."""
    from app.core import database
    from app.core.exceptions import ToolNotFoundError
    monkeypatch.setattr(database.settings, "db_path", isolated_db)
    autodiscover_tools()

    register_pipeline(Pipeline(
        name="_test_failing_pipeline",
        steps=[
            PipelineStep(tool_name="_this_tool_does_not_exist", tool_kwargs={}),
            PipelineStep(tool_name="ping", tool_kwargs={}),
        ],
    ))

    with pytest.raises(ToolNotFoundError):
        run_pipeline("_test_failing_pipeline", approval_handler=AutoApprovalHandler())