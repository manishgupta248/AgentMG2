"""
Regression tests for Tier 3 LLM router. Uses mocks for the actual
LLM calls (these cost real money and are non-deterministic) — tests
focus on: catalog building reflects real schemas, JSON parsing,
hallucination guard, and Gemini-fails-fallback-to-Groq logic. Live
response QUALITY was verified manually in M14 Step 1/1b against real
Gemini calls.
"""

import json
from unittest.mock import patch, MagicMock

import pytest

from app.core.registry import autodiscover_tools
from app.router.tier3_llm import (
    _build_tool_catalog, _build_system_prompt, resolve_via_llm, LLMToolDecision,
)
from app.core.exceptions import LLMProviderError, IntentResolutionError


def test_tool_catalog_includes_real_param_names(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)
    autodiscover_tools()

    catalog = _build_tool_catalog()
    assert "echo" in catalog
    assert "text" in catalog  # echo's real param name, not a generic placeholder


def test_tool_catalog_excludes_test_only_tools(isolated_db, monkeypatch):
    from app.core import database
    from app.core.registry import tool as tool_decorator
    from app.core.types import PermissionLevel
    from pydantic import BaseModel

    monkeypatch.setattr(database.settings, "db_path", isolated_db)

    class _Input(BaseModel):
        model_config = {"extra": "forbid"}

    @tool_decorator("_test_catalog_exclusion", permission=PermissionLevel.READ, description="test", input_schema=_Input)
    def _fn():
        return {}

    autodiscover_tools()
    catalog = _build_tool_catalog()
    assert "_test_catalog_exclusion" not in catalog


def test_system_prompt_includes_current_date():
    from datetime import datetime, timezone
    prompt = _build_system_prompt()
    current_year = str(datetime.now(timezone.utc).year)
    assert current_year in prompt
    assert "do NOT guess" in prompt


def test_system_prompt_documents_return_shape_convention():
    prompt = _build_system_prompt()
    assert "RETURN SHAPE CONVENTION" in prompt


@patch("app.router.tier3_llm._try_gemini")
def test_resolve_via_llm_uses_gemini_when_it_succeeds(mock_gemini, isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)
    autodiscover_tools()

    mock_gemini.return_value = LLMToolDecision(tool_name="ping", tool_kwargs_json="{}", reasoning="test")

    tool_name, kwargs = resolve_via_llm("some request")
    assert tool_name == "ping"
    assert kwargs == {}


@patch("app.router.tier3_llm._try_groq")
@patch("app.router.tier3_llm._try_gemini")
def test_resolve_via_llm_falls_back_to_groq_when_gemini_fails(mock_gemini, mock_groq, isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)
    autodiscover_tools()

    mock_gemini.side_effect = RuntimeError("simulated Gemini failure")
    mock_groq.return_value = LLMToolDecision(tool_name="ping", tool_kwargs_json="{}", reasoning="fallback test")

    tool_name, kwargs = resolve_via_llm("some request")
    assert tool_name == "ping"
    mock_groq.assert_called_once()


@patch("app.router.tier3_llm._try_groq")
@patch("app.router.tier3_llm._try_gemini")
def test_resolve_via_llm_raises_when_both_providers_fail(mock_gemini, mock_groq, isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)
    autodiscover_tools()

    mock_gemini.side_effect = RuntimeError("gemini down")
    mock_groq.side_effect = RuntimeError("groq down")

    with pytest.raises(LLMProviderError, match="Both Gemini and Groq failed"):
        resolve_via_llm("some request")


@patch("app.router.tier3_llm._try_gemini")
def test_resolve_via_llm_raises_on_hallucinated_tool_name(mock_gemini, isolated_db, monkeypatch):
    """CRITICAL: if the LLM picks a tool that isn't actually
    registered, this must raise rather than attempting to call a
    nonexistent tool."""
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)
    autodiscover_tools()

    mock_gemini.return_value = LLMToolDecision(
        tool_name="totally_made_up_tool_that_does_not_exist",
        tool_kwargs_json="{}",
        reasoning="hallucinated",
    )

    with pytest.raises(IntentResolutionError, match="not registered"):
        resolve_via_llm("some request")


@patch("app.router.tier3_llm._try_gemini")
def test_resolve_via_llm_raises_on_invalid_json_in_kwargs(mock_gemini, isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)
    autodiscover_tools()

    mock_gemini.return_value = LLMToolDecision(
        tool_name="ping",
        tool_kwargs_json="{not valid json!!!",
        reasoning="test",
    )

    with pytest.raises(IntentResolutionError, match="invalid JSON"):
        resolve_via_llm("some request")


@patch("app.router.tier3_llm._try_gemini")
def test_resolve_via_llm_correctly_parses_nested_kwargs_json(mock_gemini, isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)
    autodiscover_tools()

    mock_gemini.return_value = LLMToolDecision(
        tool_name="kb_add",
        tool_kwargs_json=json.dumps({"kind": "note", "content": "test", "metadata": {"nested": True}}),
        reasoning="test",
    )

    tool_name, kwargs = resolve_via_llm("some request")
    assert kwargs["metadata"] == {"nested": True}