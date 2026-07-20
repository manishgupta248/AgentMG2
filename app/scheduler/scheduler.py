"""
Scheduler — decides WHEN recurring jobs run; the Job Queue (M10)
decides HOW they run. This module only ever enqueues jobs; it never
executes tool calls directly.

Schedule expression format (kept simple for M11): 'every:<seconds>'
e.g. 'every:60' runs every 60 seconds. A full cron-like parser can be
added later if needed; this is enough for daily summaries, periodic
backups, etc. expressed as intervals.
"""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone

from app.core.database import db_cursor
from app.core.logging_setup import logger
from app.jobs.queue import enqueue_job

DEFAULT_CHECK_INTERVAL_SECONDS = 5.0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_interval_seconds(schedule_expr: str) -> int:
    if not schedule_expr.startswith("every:"):
        raise ValueError(f"Unsupported schedule_expr format: {schedule_expr!r} (expected 'every:<seconds>')")
    return int(schedule_expr.split(":", 1)[1])


def create_scheduled_job(name: str, job_type: str, payload: dict, schedule_expr: str, enabled: bool = True) -> int:
    """Registers a new recurring job definition. Validates schedule_expr eagerly."""
    _parse_interval_seconds(schedule_expr)  # raises ValueError if malformed

    with db_cursor() as cur:
        cur.execute(
            """
            INSERT INTO scheduled_jobs (name, job_type, payload, schedule_expr, enabled, next_run_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name, job_type, json.dumps(payload), schedule_expr, 1 if enabled else 0, _now_iso()),
        )
        scheduled_id = cur.lastrowid
    logger.info("Scheduled job created. id={} name={} schedule={}", scheduled_id, name, schedule_expr)
    return scheduled_id


def get_scheduled_job(scheduled_id: int) -> dict | None:
    with db_cursor() as cur:
        cur.execute(
            "SELECT id, name, job_type, payload, schedule_expr, enabled, last_run_at, next_run_at FROM scheduled_jobs WHERE id = ?",
            (scheduled_id,),
        )
        row = cur.fetchone()
    return _row_to_dict(row) if row else None


def list_scheduled_jobs(enabled_only: bool = False) -> list[dict]:
    with db_cursor() as cur:
        if enabled_only:
            cur.execute("SELECT id, name, job_type, payload, schedule_expr, enabled, last_run_at, next_run_at FROM scheduled_jobs WHERE enabled = 1")
        else:
            cur.execute("SELECT id, name, job_type, payload, schedule_expr, enabled, last_run_at, next_run_at FROM scheduled_jobs")
        rows = cur.fetchall()
    return [_row_to_dict(r) for r in rows]


def set_scheduled_job_enabled(scheduled_id: int, enabled: bool) -> bool:
    with db_cursor() as cur:
        cur.execute("UPDATE scheduled_jobs SET enabled = ? WHERE id = ?", (1 if enabled else 0, scheduled_id))
        return cur.rowcount > 0


def delete_scheduled_job(scheduled_id: int) -> bool:
    with db_cursor() as cur:
        cur.execute("DELETE FROM scheduled_jobs WHERE id = ?", (scheduled_id,))
        return cur.rowcount > 0


def _due_scheduled_jobs() -> list[dict]:
    now = _now_iso()
    with db_cursor() as cur:
        cur.execute(
            "SELECT id, name, job_type, payload, schedule_expr, enabled, last_run_at, next_run_at "
            "FROM scheduled_jobs WHERE enabled = 1 AND (next_run_at IS NULL OR next_run_at <= ?)",
            (now,),
        )
        rows = cur.fetchall()
    return [_row_to_dict(r) for r in rows]


def _advance_next_run(scheduled_id: int, schedule_expr: str) -> None:
    interval = _parse_interval_seconds(schedule_expr)
    now = datetime.now(timezone.utc)
    next_run = now.timestamp() + interval
    next_run_iso = datetime.fromtimestamp(next_run, tz=timezone.utc).isoformat()

    with db_cursor() as cur:
        cur.execute(
            "UPDATE scheduled_jobs SET last_run_at = ?, next_run_at = ? WHERE id = ?",
            (now.isoformat(), next_run_iso, scheduled_id),
        )


def _row_to_dict(row) -> dict:
    sid, name, job_type, payload_json, schedule_expr, enabled, last_run_at, next_run_at = row
    return {
        "id": sid,
        "name": name,
        "job_type": job_type,
        "payload": json.loads(payload_json) if payload_json else None,
        "schedule_expr": schedule_expr,
        "enabled": bool(enabled),
        "last_run_at": last_run_at,
        "next_run_at": next_run_at,
    }


class SchedulerLoop:
    """Daemon thread that periodically checks for due scheduled jobs
    and enqueues them via the Job Queue. Never executes tools directly."""

    def __init__(self, check_interval: float = DEFAULT_CHECK_INTERVAL_SECONDS):
        self.check_interval = check_interval
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            logger.warning("SchedulerLoop.start() called but already running.")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="SchedulerLoop")
        self._thread.start()
        logger.info("SchedulerLoop started. check_interval={}s", self.check_interval)

    def stop(self, timeout: float = 5.0) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
        logger.info("SchedulerLoop stopped.")

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                due = _due_scheduled_jobs()
                for job_def in due:
                    self._trigger(job_def)
            except Exception:
                logger.exception("SchedulerLoop encountered an unexpected error (continuing).")
            time.sleep(self.check_interval)

    def _trigger(self, job_def: dict) -> None:
        job_id = enqueue_job(job_def["job_type"], job_def["payload"])
        _advance_next_run(job_def["id"], job_def["schedule_expr"])
        logger.info(
            "Scheduled job '{}' (id={}) triggered -> enqueued job_id={}",
            job_def["name"], job_def["id"], job_id,
        )


__all__ = [
    "create_scheduled_job", "get_scheduled_job", "list_scheduled_jobs",
    "set_scheduled_job_enabled", "delete_scheduled_job", "SchedulerLoop",
]