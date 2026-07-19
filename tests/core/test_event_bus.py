"""
Regression tests for the EventBus and its integration into call_tool().
"""

import pytest

from app.events.bus import EventBus, Event
from app.core.registry import autodiscover_tools
from app.core.executor import call_tool
from app.core.approval import AutoApprovalHandler
from app.core.exceptions import ToolExecutionError, ToolValidationError


def test_publish_calls_all_subscribers_in_order():
    bus = EventBus()
    received = []
    bus.subscribe("test.event", lambda e: received.append(("a", e.payload)))
    bus.subscribe("test.event", lambda e: received.append(("b", e.payload)))

    bus.publish("test.event", {"x": 1})

    assert received == [("a", {"x": 1}), ("b", {"x": 1})]


def test_publish_with_no_subscribers_does_not_raise():
    bus = EventBus()
    event = bus.publish("nobody.listening", {"x": 1})
    assert event.name == "nobody.listening"


def test_broken_subscriber_does_not_break_publisher_or_other_subscribers():
    """
    A bad notification handler must never crash the tool call that
    triggered it, and must not prevent other subscribers from running.
    """
    bus = EventBus()
    received = []

    def _broken_handler(event: Event):
        raise RuntimeError("simulated notification failure")

    def _good_handler(event: Event):
        received.append(event.payload)

    bus.subscribe("test.event", _broken_handler)
    bus.subscribe("test.event", _good_handler)

    # Must not raise, despite the broken handler
    bus.publish("test.event", {"x": 1})

    assert received == [{"x": 1}]


def test_unsubscribe_stops_further_delivery():
    bus = EventBus()
    received = []

    def handler(event: Event):
        received.append(event.payload)

    bus.subscribe("test.event", handler)
    bus.publish("test.event", {"n": 1})
    bus.unsubscribe("test.event", handler)
    bus.publish("test.event", {"n": 2})

    assert received == [{"n": 1}]


def test_call_tool_publishes_event_on_success(isolated_db, monkeypatch):
    from app.core import database
    from app.events.bus import event_bus

    monkeypatch.setattr(database.settings, "db_path", isolated_db)
    autodiscover_tools()

    received = []
    handler = lambda e: received.append(e)
    event_bus.subscribe("tool.executed", handler)
    try:
        call_tool("ping", {})
        assert len(received) == 1
        assert received[-1].payload["tool_name"] == "ping"
        assert received[-1].payload["status"] == "success"
    finally:
        event_bus.unsubscribe("tool.executed", handler)


def test_call_tool_publishes_event_on_validation_failure(isolated_db, monkeypatch):
    """A tool call that FAILS validation must still publish tool.executed
    with status=failure — subsystems need to know about failures too."""
    from app.core import database
    from app.events.bus import event_bus

    monkeypatch.setattr(database.settings, "db_path", isolated_db)
    autodiscover_tools()

    received = []
    handler = lambda e: received.append(e)
    event_bus.subscribe("tool.executed", handler)
    try:
        with pytest.raises(ToolValidationError):
            call_tool("echo", {})  # missing required 'text'

        assert len(received) == 1
        assert received[-1].payload["tool_name"] == "echo"
        assert received[-1].payload["status"] == "failure"
    finally:
        event_bus.unsubscribe("tool.executed", handler)


def test_call_tool_publishes_event_on_execution_failure(isolated_db, monkeypatch):
    """A tool that raises during actual execution must still publish
    tool.executed with status=failure."""
    from app.core import database
    from app.core.registry import tool as tool_decorator
    from app.core.types import PermissionLevel
    from pydantic import BaseModel
    from app.events.bus import event_bus

    monkeypatch.setattr(database.settings, "db_path", isolated_db)

    class _BoomInput(BaseModel):
        model_config = {"extra": "forbid"}

    @tool_decorator("_test_boom", permission=PermissionLevel.READ, description="test", input_schema=_BoomInput)
    def _test_boom():
        raise ValueError("simulated execution failure")

    received = []
    handler = lambda e: received.append(e)
    event_bus.subscribe("tool.executed", handler)
    try:
        with pytest.raises(ToolExecutionError):
            call_tool("_test_boom", {}, approval_handler=AutoApprovalHandler())

        assert len(received) == 1
        assert received[-1].payload["tool_name"] == "_test_boom"
        assert received[-1].payload["status"] == "failure"
    finally:
        event_bus.unsubscribe("tool.executed", handler)