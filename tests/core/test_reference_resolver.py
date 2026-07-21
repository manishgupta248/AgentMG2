"""
Regression tests for the $stepN reference resolver.
"""

import pytest

from app.router.reference_resolver import is_step_reference, resolve_reference, resolve_kwargs
from app.core.exceptions import WorkflowError


def test_is_step_reference_recognizes_simple_reference():
    assert is_step_reference("$step0") is True


def test_is_step_reference_recognizes_nested_reference():
    assert is_step_reference("$step2.messages.0.subject") is True


def test_is_step_reference_rejects_non_reference_strings():
    assert is_step_reference("just a normal string") is False
    assert is_step_reference("step0") is False  # missing $
    assert is_step_reference("$step") is False  # missing index


def test_is_step_reference_rejects_non_strings():
    assert is_step_reference(42) is False
    assert is_step_reference(None) is False
    assert is_step_reference({"a": 1}) is False


def test_resolve_simple_whole_step_reference():
    step_results = {0: {"a": 1}}
    assert resolve_reference("$step0", step_results) == {"a": 1}


def test_resolve_dict_key_path():
    step_results = {0: {"subject": "Hello"}}
    assert resolve_reference("$step0.subject", step_results) == "Hello"


def test_resolve_list_index_path():
    step_results = {0: [10, 20, 30]}
    assert resolve_reference("$step0.1", step_results) == 20


def test_resolve_deeply_nested_mixed_path():
    step_results = {0: {"messages": [{"id": "abc"}, {"id": "def"}]}}
    assert resolve_reference("$step0.messages.1.id", step_results) == "def"


def test_resolve_raises_for_missing_step():
    with pytest.raises(WorkflowError, match=r"step 3"):
        resolve_reference("$step3", {0: {}})


def test_resolve_raises_for_missing_dict_key_naming_exact_segment():
    """CRITICAL regression: must raise loudly naming the failed segment,
    never silently return the literal unresolved string."""
    with pytest.raises(WorkflowError) as exc_info:
        resolve_reference("$step0.does_not_exist", {0: {"real_key": 1}})
    assert "does_not_exist" in str(exc_info.value)


def test_resolve_raises_for_out_of_range_list_index():
    with pytest.raises(WorkflowError, match="out of range"):
        resolve_reference("$step0.5", {0: [1, 2]})


def test_resolve_raises_for_invalid_list_index_segment():
    with pytest.raises(WorkflowError, match="not a valid list index"):
        resolve_reference("$step0.notanumber", {0: [1, 2]})


def test_resolve_raises_when_indexing_into_scalar():
    with pytest.raises(WorkflowError, match="cannot index"):
        resolve_reference("$step0.subject", {0: 42})


def test_resolve_kwargs_mixes_literal_and_reference_values():
    step_results = {0: {"id": 99}}
    kwargs = {"literal": "unchanged", "ref": "$step0.id", "number": 5}
    resolved = resolve_kwargs(kwargs, step_results)
    assert resolved == {"literal": "unchanged", "ref": 99, "number": 5}


def test_resolve_kwargs_resolves_references_nested_inside_lists():
    step_results = {0: {"id": 99}}
    kwargs = {"items": ["literal", "$step0.id"]}
    resolved = resolve_kwargs(kwargs, step_results)
    assert resolved == {"items": ["literal", 99]}


def test_resolve_kwargs_resolves_references_nested_inside_dicts():
    step_results = {0: {"id": 99}}
    kwargs = {"nested": {"target_id": "$step0.id"}}
    resolved = resolve_kwargs(kwargs, step_results)
    assert resolved == {"nested": {"target_id": 99}}


def test_resolve_kwargs_never_silently_passes_through_unresolved_reference():
    """CRITICAL regression for the exact prior-build bug: an unresolved
    reference must raise, not end up as a literal string value that
    could get written into real data (e.g. a spreadsheet)."""
    step_results = {0: {"real_key": 1}}
    kwargs = {"target": "$step0.wrong_key"}
    with pytest.raises(WorkflowError):
        resolve_kwargs(kwargs, step_results)