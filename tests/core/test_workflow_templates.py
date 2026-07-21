"""
Regression tests for Workflow Templates.
"""

import pytest

from app.core.registry import autodiscover_tools
from app.core.executor import call_tool
from app.core.approval import AutoApprovalHandler
from app.core.exceptions import WorkflowError
from app.workflows.templates import WorkflowTemplate, register_template, run_workflow, get_template


def test_register_and_get_template():
    t = WorkflowTemplate(name="_test_tmpl_1", description="test", step_definitions=[{"tool_name": "ping", "tool_kwargs": {}}])
    register_template(t)
    assert get_template("_test_tmpl_1") is t


def test_run_workflow_raises_for_unregistered_template(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)
    autodiscover_tools()

    with pytest.raises(WorkflowError, match="not registered"):
        run_workflow("_definitely_not_a_real_template", {})


def test_run_workflow_substitutes_param_in_string():
    from app.workflows.templates import _substitute_params
    result = _substitute_params("Hello {{name}}!", {"name": "World"})
    assert result == "Hello World!"


def test_run_workflow_substitutes_param_preserving_type_for_full_match():
    """A value that IS entirely one {{param}} should preserve the
    param's original type (e.g. int), not stringify it."""
    from app.workflows.templates import _substitute_params
    result = _substitute_params("{{count}}", {"count": 42})
    assert result == 42
    assert isinstance(result, int)


def test_run_workflow_substitutes_params_nested_in_dict_and_list():
    from app.workflows.templates import _substitute_params
    value = {"a": "{{x}}", "b": ["literal", "{{y}}"]}
    result = _substitute_params(value, {"x": 1, "y": "hello"})
    assert result == {"a": 1, "b": ["literal", "hello"]}


def test_run_workflow_raises_for_undefined_param_reference():
    from app.workflows.templates import _substitute_params
    with pytest.raises(WorkflowError, match="undefined_param"):
        _substitute_params("{{undefined_param}}", {})


def test_run_workflow_raises_for_missing_required_params(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)
    autodiscover_tools()

    register_template(WorkflowTemplate(
        name="_test_requires_param",
        description="test",
        step_definitions=[{"tool_name": "echo", "tool_kwargs": {"text": "{{msg}}"}}],
        required_params=["msg"],
    ))

    with pytest.raises(WorkflowError, match="Missing required parameter"):
        run_workflow("_test_requires_param", {})


def test_run_workflow_executes_full_template_with_param_and_step_chaining(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)
    autodiscover_tools()

    register_template(WorkflowTemplate(
        name="_test_full_workflow",
        description="test",
        step_definitions=[
            {"tool_name": "kb_add", "tool_kwargs": {"kind": "note", "content": "About {{topic}}"}},
            {"tool_name": "kb_get", "tool_kwargs": {"entry_id": "$step0.id"}},
        ],
        required_params=["topic"],
    ))

    results = run_workflow("_test_full_workflow", {"topic": "testing"}, approval_handler=AutoApprovalHandler())

    assert results[0].success is True
    assert results[1].success is True
    assert results[1].data["content"] == "About testing"


def test_workflow_run_tool_requires_explicit_approval(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)
    autodiscover_tools()

    register_template(WorkflowTemplate(
        name="_test_approval_workflow",
        description="test",
        step_definitions=[{"tool_name": "ping", "tool_kwargs": {}}],
    ))

    with pytest.raises(RuntimeError, match="require an explicit approval_handler"):
        call_tool("workflow_run", {"template_name": "_test_approval_workflow", "params": {}})


def test_workflow_list_tool_returns_registered_templates(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)
    autodiscover_tools()

    register_template(WorkflowTemplate(name="_test_list_workflow", description="a test workflow", step_definitions=[{"tool_name": "ping", "tool_kwargs": {}}]))

    result = call_tool("workflow_list", {})
    names = [t["name"] for t in result.data]
    assert "_test_list_workflow" in names