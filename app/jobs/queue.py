"""
Job Queue — async execution for long-running tasks, off the main
request/response path. Status tracking persisted in SQLite (jobs
table, created in M1's init_db()).

Design: a job wraps a single call_tool() invocation (tool_name +
tool_kwargs), executed by a background JobWorker thread. This keeps
the Job Queue's execution path identical to every other tool call —
same validation, same permission gating, same audit logging — rather
than having jobs bypass call_tool() and reimplement any of that.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from app.core.database import db_cursor
from app.core.logging_setup import logger
from app.core.exceptions import JobError


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def enqueue_job(job_type: str, payload: dict) -> int:
    """
    Enqueues a job. `payload` must contain at least 'tool_name' and
    'tool_kwargs' for job_type='tool_call' (the only job_type for now).
    Returns the new job's id.
    """
    now = _now_iso()
    with db_cursor() as cur:
        cur.execute(
            """
            INSERT INTO jobs (job_type, payload, status, created_at)
            VALUES (?, ?, 'queued', ?)
            """,
            (job_type, json.dumps(payload), now),
        )
        job_id = cur.lastrowid
    logger.info("Job enqueued. id={} type={}", job_id, job_type)
    return job_id


def get_job(job_id: int) -> dict | None:
    with db_cursor() as cur:
        cur.execute(
            "SELECT id, job_type, payload, status, result, error, created_at, started_at, finished_at FROM jobs WHERE id = ?",
            (job_id,),
        )
        row = cur.fetchone()
    if row is None:
        return None
    return _row_to_dict(row)


def list_jobs(status: str | None = None, limit: int = 50) -> list[dict]:
    with db_cursor() as cur:
        if status:
            cur.execute(
                "SELECT id, job_type, payload, status, result, error, created_at, started_at, finished_at FROM jobs WHERE status = ? ORDER BY id DESC LIMIT ?",
                (status, limit),
            )
        else:
            cur.execute(
                "SELECT id, job_type, payload, status, result, error, created_at, started_at, finished_at FROM jobs ORDER BY id DESC LIMIT ?",
                (limit,),
            )
        rows = cur.fetchall()
    return [_row_to_dict(row) for row in rows]


def _claim_next_queued_job() -> dict | None:
    """
    Atomically claims the oldest queued job by flipping it to 'running'.
    Uses a single UPDATE...WHERE status='queued' scoped to the specific
    id found by a prior SELECT, inside one db_cursor transaction, to
    avoid two worker threads (if ever run concurrently) claiming the
    same job.
    """
    with db_cursor() as cur:
        cur.execute("SELECT id FROM jobs WHERE status = 'queued' ORDER BY id ASC LIMIT 1")
        row = cur.fetchone()
        if row is None:
            return None
        job_id = row[0]
        cur.execute(
            "UPDATE jobs SET status = 'running', started_at = ? WHERE id = ? AND status = 'queued'",
            (_now_iso(), job_id),
        )
        if cur.rowcount == 0:
            # Another worker claimed it between the SELECT and UPDATE
            return None
    return get_job(job_id)


def _mark_job_finished(job_id: int, status: str, result=None, error: str | None = None) -> None:
    with db_cursor() as cur:
        cur.execute(
            "UPDATE jobs SET status = ?, result = ?, error = ?, finished_at = ? WHERE id = ?",
            (status, json.dumps(result, default=str) if result is not None else None, error, _now_iso(), job_id),
        )


def _row_to_dict(row) -> dict:
    job_id, job_type, payload_json, status, result_json, error, created_at, started_at, finished_at = row
    return {
        "id": job_id,
        "job_type": job_type,
        "payload": json.loads(payload_json) if payload_json else None,
        "status": status,
        "result": json.loads(result_json) if result_json else None,
        "error": error,
        "created_at": created_at,
        "started_at": started_at,
        "finished_at": finished_at,
    }


__all__ = ["enqueue_job", "get_job", "list_jobs", "_claim_next_queued_job", "_mark_job_finished"]