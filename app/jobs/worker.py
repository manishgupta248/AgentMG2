"""
JobWorker — background thread that polls the jobs table for queued
work and executes it via call_tool(), keeping job execution on the
exact same validated/audited/permission-gated path as any other tool
call.

Approval note: jobs currently use AutoApprovalHandler, meaning a
queued job for a MODIFY/DELETE tool will auto-approve without a human
in the loop. This matches the "batch approval" gap already flagged
back in M2 — proper handling (e.g. requiring approval AT ENQUEUE TIME,
before the job ever starts running in the background) is deferred to
M12/M13 alongside the rest of the pipeline/workflow approval story.
For now, only enqueue jobs for tools you're comfortable auto-approving,
or READ-only tools.
"""

from __future__ import annotations

import threading
import time

from app.core.executor import call_tool
from app.core.approval import AutoApprovalHandler
from app.core.logging_setup import logger
from app.jobs.queue import _claim_next_queued_job, _mark_job_finished

DEFAULT_POLL_INTERVAL_SECONDS = 2.0


class JobWorker:
    def __init__(self, poll_interval: float = DEFAULT_POLL_INTERVAL_SECONDS):
        self.poll_interval = poll_interval
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            logger.warning("JobWorker.start() called but worker is already running.")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="JobWorker")
        self._thread.start()
        logger.info("JobWorker started. poll_interval={}s", self.poll_interval)

    def stop(self, timeout: float = 5.0) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
        logger.info("JobWorker stopped.")

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                job = _claim_next_queued_job()
                if job is None:
                    time.sleep(self.poll_interval)
                    continue
                self._execute_job(job)
            except Exception:
                logger.exception("JobWorker loop encountered an unexpected error (continuing).")
                time.sleep(self.poll_interval)

    def _execute_job(self, job: dict) -> None:
        job_id = job["id"]
        payload = job["payload"] or {}

        if job["job_type"] != "tool_call":
            _mark_job_finished(job_id, "failed", error=f"Unknown job_type: {job['job_type']}")
            logger.warning("Job {} has unknown job_type '{}'.", job_id, job["job_type"])
            return

        tool_name = payload.get("tool_name")
        tool_kwargs = payload.get("tool_kwargs", {})

        logger.info("JobWorker executing job {}: tool={}", job_id, tool_name)
        try:
            result = call_tool(tool_name, tool_kwargs, approval_handler=AutoApprovalHandler())
            _mark_job_finished(job_id, "succeeded", result=result.data)
            logger.info("Job {} succeeded.", job_id)
        except Exception as e:
            _mark_job_finished(job_id, "failed", error=str(e))
            logger.warning("Job {} failed: {}", job_id, e)


__all__ = ["JobWorker", "DEFAULT_POLL_INTERVAL_SECONDS"]