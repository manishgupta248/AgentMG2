"""
Regression tests for the Job Queue and JobWorker.
"""

import time

import pytest

from app.core.registry import autodiscover_tools
from app.core.executor import call_tool
from app.core.approval import AutoApprovalHandler
from app.jobs.queue import enqueue_job, get_job, list_jobs, _claim_next_queued_job, _mark_job_finished
from app.jobs.worker import JobWorker


def test_enqueue_and_get_job(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)

    job_id = enqueue_job("tool_call", {"tool_name": "ping", "tool_kwargs": {}})
    job = get_job(job_id)

    assert job is not None
    assert job["status"] == "queued"
    assert job["job_type"] == "tool_call"
    assert job["payload"]["tool_name"] == "ping"


def test_get_nonexistent_job_returns_none(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)

    assert get_job(99999) is None


def test_claim_next_queued_job_flips_status_to_running(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)

    job_id = enqueue_job("tool_call", {"tool_name": "ping", "tool_kwargs": {}})
    claimed = _claim_next_queued_job()

    assert claimed is not None
    assert claimed["id"] == job_id
    assert claimed["status"] == "running"
    assert claimed["started_at"] is not None


def test_claim_next_queued_job_returns_none_when_empty(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)

    assert _claim_next_queued_job() is None


def test_claim_next_queued_job_processes_in_fifo_order(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)

    id1 = enqueue_job("tool_call", {"tool_name": "a", "tool_kwargs": {}})
    id2 = enqueue_job("tool_call", {"tool_name": "b", "tool_kwargs": {}})

    first_claimed = _claim_next_queued_job()
    assert first_claimed["id"] == id1

    second_claimed = _claim_next_queued_job()
    assert second_claimed["id"] == id2


def test_mark_job_finished_success(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)

    job_id = enqueue_job("tool_call", {"tool_name": "ping", "tool_kwargs": {}})
    _claim_next_queued_job()
    _mark_job_finished(job_id, "succeeded", result={"ok": True})

    job = get_job(job_id)
    assert job["status"] == "succeeded"
    assert job["result"] == {"ok": True}
    assert job["finished_at"] is not None


def test_mark_job_finished_failure(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)

    job_id = enqueue_job("tool_call", {"tool_name": "ping", "tool_kwargs": {}})
    _claim_next_queued_job()
    _mark_job_finished(job_id, "failed", error="something broke")

    job = get_job(job_id)
    assert job["status"] == "failed"
    assert job["error"] == "something broke"


def test_list_jobs_filters_by_status(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)

    id1 = enqueue_job("tool_call", {"tool_name": "a", "tool_kwargs": {}})
    id2 = enqueue_job("tool_call", {"tool_name": "b", "tool_kwargs": {}})
    _claim_next_queued_job()  # claims id1, flips to running

    queued = list_jobs(status="queued")
    running = list_jobs(status="running")

    assert any(j["id"] == id2 for j in queued)
    assert any(j["id"] == id1 for j in running)


def test_job_worker_executes_queued_job_end_to_end(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)
    autodiscover_tools()

    worker = JobWorker(poll_interval=0.1)
    worker.start()
    try:
        job_id = enqueue_job("tool_call", {"tool_name": "echo", "tool_kwargs": {"text": "worker test"}})

        # Poll for completion (test-side, generous timeout)
        for _ in range(50):
            job = get_job(job_id)
            if job["status"] in ("succeeded", "failed"):
                break
            time.sleep(0.1)

        assert job["status"] == "succeeded"
        assert job["result"] == {"echoed": "worker test"}
    finally:
        worker.stop()


def test_job_worker_marks_unknown_tool_as_failed(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)
    autodiscover_tools()

    worker = JobWorker(poll_interval=0.1)
    worker.start()
    try:
        job_id = enqueue_job("tool_call", {"tool_name": "definitely_not_real", "tool_kwargs": {}})

        for _ in range(50):
            job = get_job(job_id)
            if job["status"] in ("succeeded", "failed"):
                break
            time.sleep(0.1)

        assert job["status"] == "failed"
        assert "not registered" in job["error"]
    finally:
        worker.stop()


def test_job_worker_marks_unknown_job_type_as_failed(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)
    autodiscover_tools()

    worker = JobWorker(poll_interval=0.1)
    worker.start()
    try:
        job_id = enqueue_job("some_unsupported_job_type", {})

        for _ in range(50):
            job = get_job(job_id)
            if job["status"] in ("succeeded", "failed"):
                break
            time.sleep(0.1)

        assert job["status"] == "failed"
        assert "Unknown job_type" in job["error"]
    finally:
        worker.stop()


def test_job_enqueue_tool_no_collision_with_call_tool_tool_name(isolated_db, monkeypatch):
    """
    Permanent regression test for the real-world collision scenario
    manually verified in M10 Step 2: job_enqueue's OWN 'tool_name'
    input field must not collide with call_tool()'s framework-level
    tool_name parameter.
    """
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)
    autodiscover_tools()

    result = call_tool(
        "job_enqueue",
        {"tool_name": "ping", "tool_kwargs": {}},
        approval_handler=AutoApprovalHandler(),
    )
    assert result.success is True
    assert "job_id" in result.data

    job = get_job(result.data["job_id"])
    assert job["payload"]["tool_name"] == "ping"