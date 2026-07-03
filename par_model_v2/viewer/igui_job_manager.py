"""GUI-1 - Background run-job manager for the Input & Run GUI.

Roadmap 4.0 item GUI-1 (owner directive 2026-07-03): the Task-7 ``POST
/execute`` endpoint runs the engine INSIDE the HTTP request, so the browser
blocks for the whole run with no progress visibility and a dropped connection
loses the result.  This module supplies the asynchronous alternative:

  * ``JobManager.submit(...)``   -> returns a ``job_id`` immediately; the run
                                    executes on a daemon worker thread;
  * ``JobManager.status(id)``    -> queued / running / succeeded / failed +
                                    elapsed seconds + progress lines + (when
                                    finished) the full engine result;
  * ``JobManager.list_jobs()``   -> newest-first summaries (GUI-4 seed);
  * every terminal job is persisted to ``<persist_dir>/job_<id>.json`` so a
    server restart does not erase the run record (SHA-256 audit trail of the
    engine output stays with the run_output artifacts themselves).

Discipline (matches the Phase IGUI stack): STANDARD LIBRARY ONLY, no model
parameter change, no touch of the governed RESULTS UI.  Single-flight: the
engine writes shared ``run_output/`` artifacts, so ONE run at a time; a second
submit while a job is active is refused with the active job id.

The runner callable is injected (``runner(smoke: bool) -> dict``), keeping
this module engine-agnostic and unit-testable without spawning the model.
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

_ACTIVE_STATES = ("queued", "running")
_TERMINAL_STATES = ("succeeded", "failed")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobManager:
    """Thread-safe, single-flight background executor for GUI model runs."""

    def __init__(self, runner: Callable[[bool], Dict[str, Any]],
                 persist_dir: Optional[str] = None,
                 max_history: int = 100) -> None:
        self._runner = runner
        self._persist_dir = persist_dir
        self._max_history = int(max_history)
        self._lock = threading.Lock()
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._order: List[str] = []

    # -- submission ----------------------------------------------------------

    def submit(self, smoke: bool = True) -> Dict[str, Any]:
        with self._lock:
            active = self._active_job_id_locked()
            if active is not None:
                return {"ok": False,
                        "error": "a run is already in progress; one run at a time "
                                 "(shared run_output artifacts)",
                        "active_job_id": active}
            job_id = "{}-{}".format(
                datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
                uuid.uuid4().hex[:8])
            self._jobs[job_id] = {
                "job_id": job_id,
                "state": "queued",
                "smoke": bool(smoke),
                "submitted_at": _utc_now(),
                "started_at": None,
                "finished_at": None,
                "started_monotonic": None,
                "finished_monotonic": None,
                "progress": ["job {} queued".format(job_id)],
                "result": None,
                "error": None,
            }
            self._order.append(job_id)
            self._trim_locked()
        worker = threading.Thread(target=self._work, args=(job_id, bool(smoke)),
                                  name="igui-job-{}".format(job_id), daemon=True)
        worker.start()
        return {"ok": True, "job_id": job_id, "state": "queued"}

    def _active_job_id_locked(self) -> Optional[str]:
        for jid in reversed(self._order):
            if self._jobs[jid]["state"] in _ACTIVE_STATES:
                return jid
        return None

    def _trim_locked(self) -> None:
        while len(self._order) > self._max_history:
            oldest = self._order[0]
            if self._jobs[oldest]["state"] in _ACTIVE_STATES:
                break  # never evict an active job
            self._order.pop(0)
            self._jobs.pop(oldest, None)

    # -- worker ---------------------------------------------------------------

    def _work(self, job_id: str, smoke: bool) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:  # evicted before start (should not happen)
                return
            job["state"] = "running"
            job["started_at"] = _utc_now()
            job["started_monotonic"] = time.monotonic()
            job["progress"].append("engine run started (smoke={})".format(smoke))
        try:
            result = self._runner(smoke)
            ok = bool(isinstance(result, dict) and result.get("ok"))
            with self._lock:
                job["result"] = result
                job["state"] = "succeeded" if ok else "failed"
                if not ok:
                    job["error"] = (result or {}).get("stage") or "run failed"
                engine_progress = (result or {}).get("progress")
                if isinstance(engine_progress, list) and engine_progress:
                    job["progress"] = list(engine_progress)
                job["progress"].append(
                    "job {} {}".format(job_id, job["state"]))
        except Exception as exc:  # runner must never kill the server
            with self._lock:
                job["state"] = "failed"
                job["error"] = str(exc)
                job["progress"].append("job {} failed: {}".format(job_id, exc))
        finally:
            with self._lock:
                job["finished_at"] = _utc_now()
                job["finished_monotonic"] = time.monotonic()
                snapshot = self._snapshot_locked(job_id)
            self._persist(snapshot)

    # -- inspection -----------------------------------------------------------

    def status(self, job_id: str) -> Dict[str, Any]:
        with self._lock:
            if job_id not in self._jobs:
                return {"ok": False, "error": "unknown job_id", "job_id": job_id}
            snap = self._snapshot_locked(job_id)
        snap["ok"] = True
        return snap

    def list_jobs(self) -> Dict[str, Any]:
        with self._lock:
            summaries = []
            for jid in reversed(self._order):
                s = self._snapshot_locked(jid)
                summaries.append({k: s.get(k) for k in (
                    "job_id", "state", "smoke", "submitted_at", "started_at",
                    "finished_at", "elapsed_seconds", "error")})
        return {"ok": True, "jobs": summaries}

    def _snapshot_locked(self, job_id: str) -> Dict[str, Any]:
        job = self._jobs[job_id]
        snap = {k: v for k, v in job.items()
                if k not in ("started_monotonic", "finished_monotonic")}
        snap["progress"] = list(job["progress"])
        start = job["started_monotonic"]
        end = job["finished_monotonic"]
        if start is None:
            snap["elapsed_seconds"] = 0.0
        else:
            snap["elapsed_seconds"] = round((end or time.monotonic()) - start, 3)
        if job["state"] == "running":
            snap["progress"] = snap["progress"] + [
                "engine executing... elapsed {:.0f}s".format(snap["elapsed_seconds"])]
        return snap

    # -- persistence ----------------------------------------------------------

    def _persist(self, snapshot: Dict[str, Any]) -> None:
        if not self._persist_dir:
            return
        try:
            os.makedirs(self._persist_dir, exist_ok=True)
            path = os.path.join(self._persist_dir,
                                "job_{}.json".format(snapshot["job_id"]))
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(snapshot, fh, indent=1, default=str)
            with open(path, "r", encoding="utf-8") as fh:
                json.load(fh)  # re-parse guard (house rule: never ship corrupt JSON)
        except OSError:
            pass  # persistence is best-effort; the in-memory record remains
