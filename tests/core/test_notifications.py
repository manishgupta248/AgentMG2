"""
Regression tests for the Notification Framework:
- NotificationManager dispatches to all registered channels, or a
  specified subset.
- A channel raising inside send() must not propagate to notify()'s
  caller (channels must not be able to crash whatever triggered them).
- The tool.executed -> notification wiring fires ONLY on failure,
  not on success (current M5 policy).
"""

import pytest

from app.notifications.manager import NotificationManager
from app.notifications.console_channel import ConsoleChannel
from app.events.bus import EventBus, Event
from app.notifications.event_subscriber import _on_tool_executed


class _RecordingChannel:
    def __init__(self, name: str):
        self.name = name
        self.sent = []

    def send(self, message, *, title=None, metadata=None):
        self.sent.append((message, title, metadata))
        return True


class _BrokenChannel:
    name = "broken"

    def send(self, message, *, title=None, metadata=None):
        raise RuntimeError("simulated channel failure")


def test_notify_dispatches_to_all_registered_channels():
    manager = NotificationManager()
    a = _RecordingChannel("a")
    b = _RecordingChannel("b")
    manager.register_channel(a)
    manager.register_channel(b)

    results = manager.notify("hello", title="Test")

    assert results == {"a": True, "b": True}
    assert a.sent == [("hello", "Test", None)]
    assert b.sent == [("hello", "Test", None)]


def test_notify_dispatches_to_specified_subset_only():
    manager = NotificationManager()
    a = _RecordingChannel("a")
    b = _RecordingChannel("b")
    manager.register_channel(a)
    manager.register_channel(b)

    results = manager.notify("hello", channels=["a"])

    assert results == {"a": True}
    assert a.sent == [("hello", None, None)]
    assert b.sent == []


def test_notify_handles_unknown_channel_gracefully():
    manager = NotificationManager()
    results = manager.notify("hello", channels=["does_not_exist"])
    assert results == {"does_not_exist": False}


def test_broken_channel_does_not_raise_and_others_still_receive():
    manager = NotificationManager()
    broken = _BrokenChannel()
    good = _RecordingChannel("good")
    manager.register_channel(broken)
    manager.register_channel(good)

    # Must NOT raise despite the broken channel
    results = manager.notify("hello")

    assert results["broken"] is False
    assert results["good"] is True
    assert good.sent == [("hello", None, None)]


def test_console_channel_send_returns_true(capsys):
    channel = ConsoleChannel()
    result = channel.send("test message", title="Test Title")
    assert result is True

    captured = capsys.readouterr()
    assert "test message" in captured.out
    assert "Test Title" in captured.out


def test_tool_executed_subscriber_fires_only_on_failure():
    from app.notifications.manager import notification_manager

    received = []
    channel = _RecordingChannel("test_channel")
    notification_manager.register_channel(channel)
    try:
        success_event = Event(name="tool.executed", payload={"tool_name": "ping", "status": "success", "data": {}})
        _on_tool_executed(success_event)
        assert channel.sent == []  # no notification for success

        failure_event = Event(name="tool.executed", payload={"tool_name": "echo", "status": "failure", "error": "boom"})
        _on_tool_executed(failure_event)
        assert len(channel.sent) == 1
        assert "echo" in channel.sent[0][0]
        assert "boom" in channel.sent[0][0]
    finally:
        notification_manager.unregister_channel("test_channel")