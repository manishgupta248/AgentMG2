"""
Regression tests for the Intent Router — Tier 1 regex matching,
normalization, and compound-request detection.
"""

import pytest

from app.router.normalize import normalize_text
from app.router.compound_detector import is_compound_request
from app.router.router import resolve_intent
from app.core.exceptions import IntentResolutionError


# --- Normalization ---

def test_normalize_converts_smart_quotes():
    assert normalize_text("it\u2019s a test") == "it's a test"


def test_normalize_converts_smart_double_quotes():
    assert normalize_text("\u201chello\u201d") == '"hello"'


def test_normalize_collapses_extra_whitespace():
    assert normalize_text("  hello    world  ") == "hello world"


def test_normalize_converts_nbsp():
    assert normalize_text("hello\u00a0world") == "hello world"


def test_normalize_is_idempotent():
    text = "already normal text"
    assert normalize_text(normalize_text(text)) == text


# --- Compound detection ---

@pytest.mark.parametrize("text", [
    "ping the server and then email me",
    "do this then do that",
    "check email after that update the sheet",
    "read the file followed by summarizing it",
    "do X and also do Y",
])
def test_compound_markers_detected(text):
    assert is_compound_request(text) is True


@pytest.mark.parametrize("text", [
    "ping the server",
    "echo hello world",
    "remember to buy milk",
    "what time is it",
])
def test_non_compound_text_not_flagged(text):
    assert is_compound_request(text) is False


# --- Tier 1 / resolve_intent integration ---

def test_resolve_intent_matches_ping():
    tool_name, kwargs = resolve_intent("ping")
    assert tool_name == "ping"
    assert kwargs == {}


def test_resolve_intent_matches_echo_with_correct_text():
    tool_name, kwargs = resolve_intent("echo hello there")
    assert tool_name == "echo"
    assert kwargs == {"text": "hello there"}


def test_resolve_intent_echo_capture_group_not_greedy_across_boundary():
    """
    Regression for the exact prior-build regex-greediness bug: a bare
    .* before an optional capture group could eat characters meant for
    that group. Our echo pattern captures everything after 'echo ' as
    text — verify it doesn't truncate or over-capture with trailing
    punctuation/numbers present.
    """
    tool_name, kwargs = resolve_intent("echo the number is 42 and that's final")
    assert kwargs["text"] == "the number is 42 and that's final"


def test_resolve_intent_matches_remember():
    tool_name, kwargs = resolve_intent("remember that the gate code is 1234")
    assert tool_name == "kb_add"
    assert kwargs == {"kind": "note", "content": "the gate code is 1234"}


def test_resolve_intent_matches_note_without_that():
    tool_name, kwargs = resolve_intent("note the gate code is 1234")
    assert tool_name == "kb_add"
    assert kwargs["content"] == "the gate code is 1234"


def test_resolve_intent_matches_kb_search():
    tool_name, kwargs = resolve_intent("search notes for renewal")
    assert tool_name == "kb_search"
    assert kwargs == {"query": "renewal"}


def test_resolve_intent_matches_calendar_list():
    tool_name, kwargs = resolve_intent("what's on my calendar")
    assert tool_name == "calendar_list_events"


def test_resolve_intent_normalizes_before_matching():
    """Smart quote + extra whitespace should not prevent a match."""
    tool_name, kwargs = resolve_intent("  echo   it\u2019s   working  ")
    assert tool_name == "echo"
    assert kwargs["text"] == "it's working"


def test_resolve_intent_raises_for_compound_request():
    with pytest.raises(IntentResolutionError, match="multi-step"):
        resolve_intent("ping the server and then email me the result")


def test_resolve_intent_raises_for_unrecognized_text():
    with pytest.raises(IntentResolutionError):
        resolve_intent("this matches absolutely nothing we have defined")


def test_resolve_intent_case_insensitive():
    tool_name, kwargs = resolve_intent("ECHO Hello World")
    assert tool_name == "echo"
    assert kwargs["text"] == "Hello World"