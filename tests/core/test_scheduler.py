"""Regression tests for the Scheduler."""

import time

import pytest

from app.core.registry import autodiscover_tools
from app.core.executor import call_tool
from app.core.approval import AutoApprovalHandler
from app.scheduler.scheduler import (
    create_scheduled_job, get_scheduled_job, list_scheduled_jobs,
    set_scheduled_job_enabled, delete_scheduled_job, _due_scheduled_jobs,
    _advance_next_run, _parse_interval_seconds, SchedulerLoop,
)
from app.jobs.queue import list_jobs
from app.jobs.worker import JobWorker


def test_parse_interval_seconds_valid():
    assert _parse_interval_seconds("every:60") == 60


def test_parse_interval_seconds_invalid_format_raises():
    with pytest.raises(ValueError):
        _parse_interval_seconds("daily")


def test_create_scheduled_job_rejects_malformed_schedule_expr(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)

    with pytest.raises(ValueError):
        create_scheduled_job("bad", "tool_call", {}, "not_a_valid_expr")


def test_create_and_get_scheduled_job(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)

    sid = create_scheduled_job("test_job", "tool_call", {"tool_name": "ping", "tool_kwargs": {}}, "every:60")
    job = get_scheduled_job(sid)

    assert job["name"] == "test_job"
    assert job["enabled"] is True
    assert job["schedule_expr"] == "every:60"


def test_new_scheduled_job_is_immediately_due(isolated_db, monkeypatch):
    """next_run_at defaults to 'now' on creation, so a brand new job
    should show up as due right away."""
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)

    sid = create_scheduled_job("test_job", "tool_call", {"tool_name": "ping", "tool_kwargs": {}}, "every:60")
    due = _due_scheduled_jobs()

    assert any(j["id"] == sid for j in due)


def test_disabled_job_is_never_due(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)

    sid = create_scheduled_job("test_job", "tool_call", {"tool_name": "ping", "tool_kwargs": {}}, "every:60", enabled=False)
    due = _due_scheduled_jobs()

    assert not any(j["id"] == sid for j in due)


def test_advance_next_run_pushes_next_run_into_the_future(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)

    sid = create_scheduled_job("test_job", "tool_call", {"tool_name": "ping", "tool_kwargs": {}}, "every:60")
    before = get_scheduled_job(sid)

    _advance_next_run(sid, "every:60")
    after = get_scheduled_job(sid)

    assert after["last_run_at"] is not None
    assert after["next_run_at"] > before["next_run_at"] if before["next_run_at"] else True

    # After advancing, it should no longer be immediately due
    due = _due_scheduled_jobs()
    assert not any(j["id"] == sid for j in due)


def test_set_scheduled_job_enabled_toggles_correctly(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)

    sid = create_scheduled_job("test_job", "tool_call", {"tool_name": "ping", "tool_kwargs": {}}, "every:60")
    assert set_scheduled_job_enabled(sid, False) is True
    assert get_scheduled_job(sid)["enabled"] is False

    assert set_scheduled_job_enabled(sid, True) is True
    assert get_scheduled_job(sid)["enabled"] is True


def test_set_scheduled_job_enabled_returns_false_for_nonexistent(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)

    assert set_scheduled_job_enabled(99999, True) is False


def test_delete_scheduled_job_removes_it(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)

    sid = create_scheduled_job("test_job", "tool_call", {"tool_name": "ping", "tool_kwargs": {}}, "every:60")
    assert delete_scheduled_job(sid) is True
    assert get_scheduled_job(sid) is None
    assert delete_scheduled_job(sid) is False  # already gone


def test_scheduler_loop_triggers_due_job_and_enqueues(isolated_db, monkeypatch):
    """End-to-end: SchedulerLoop should enqueue a real job via the Job
    Queue when a scheduled job is due."""
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)
    autodiscover_tools()

    create_scheduled_job("test_job", "tool_call", {"tool_name": "ping", "tool_kwargs": {}}, "every:9999")  # long interval, only triggers once

    scheduler = SchedulerLoop(check_interval=0.2)
    worker = JobWorker(poll_interval=0.2)
    scheduler.start()
    worker.start()
    try:
        time.sleep(1.5)  # enough for at least one check cycle
        jobs = list_jobs(limit=10)
        ping_jobs = [j for j in jobs if j["payload"]["tool_name"] == "ping"]
        assert len(ping_jobs) >= 1
        assert any(j["status"] == "succeeded" for j in ping_jobs)
    finally:
        scheduler.stop()
        worker.stop()


def test_schedule_create_tool_requires_explicit_approval(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)
    autodiscover_tools()

    with pytest.raises(RuntimeError, match="require an explicit approval_handler"):
        call_tool("schedule_create", {"name": "x", "tool_name": "ping", "schedule_expr": "every:60"})


def test_schedule_create_tool_succeeds_with_approval(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)
    autodiscover_tools()

    result = call_tool(
        "schedule_create",
        {"name": "x", "tool_name": "ping", "schedule_expr": "every:60"},
        approval_handler=AutoApprovalHandler(),
    )
    assert result.success is True
    assert "scheduled_id" in result.data