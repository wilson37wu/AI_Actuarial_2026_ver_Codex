#!/usr/bin/env python3
"""Multi-agent coordination lock for the shared actuarial-model repo.

Implements the lock protocol in AGENT_COORDINATION.md as a small, dependency-free
helper both Codex and Claude call. The lock lives in ``.agent_lock.json`` at the
repo root and is committed/pushed to ``main``; the push is the atomic
compare-and-set (GitHub accepts exactly one ref update, so a racing acquirer is
rejected and yields).

Run this from inside the git checkout you intend to push from:
  * Codex     -> your normal checkout.
  * Claude    -> a FRESH /tmp clone (never the virtiofs-mounted worktree).

Subcommands
-----------
  preflight  fetch + rebase onto origin/main, then read the lock. Exit 0 = free
             to proceed (no held lock, or the lock is already yours, or it is
             stale); exit 10 = HELD by the other agent -> the caller must YIELD.
  acquire    preflight, then write+commit+push your lock. Exit 0 = acquired;
             exit 10 = lost the race / held by other -> YIELD; exit >0 = error.
  release    set owner=null, commit, push. Exit 0 = released.
  status     print the current lock as JSON (no network write). Exit 0.

Usage
-----
  python scripts/agent_lock.py preflight --owner claude
  python scripts/agent_lock.py acquire   --owner claude --task "Phase 29 Task 3"
  python scripts/agent_lock.py release   --owner claude
  python scripts/agent_lock.py status

Exit codes: 0 ok / proceed; 10 yield (other agent holds it); 1 usage/IO error;
2 git error.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

LOCK_FILE = ".agent_lock.json"
DEFAULT_TTL_MIN = 120
PUSH_RETRIES = 3
YIELD_EXIT = 10
VALID_OWNERS = ("codex", "claude")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _git(*args: str, check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], check=check,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None, text=True)


def _repo_root() -> Path:
    try:
        out = _git("rev-parse", "--show-toplevel").stdout.strip()
        return Path(out)
    except subprocess.CalledProcessError:
        print("ERROR: not inside a git repository", file=sys.stderr)
        sys.exit(1)


def _integrate() -> None:
    """fetch + rebase onto origin/main (raise on failure)."""
    _git("fetch", "origin", capture=False)
    # rebase current HEAD onto origin/main; abort cleanly if it conflicts.
    r = _git("rebase", "origin/main", check=False)
    if r.returncode != 0:
        _git("rebase", "--abort", check=False)
        print("ERROR: rebase onto origin/main failed (manual integration needed)",
              file=sys.stderr)
        print(r.stderr or "", file=sys.stderr)
        sys.exit(2)


def _read_lock(root: Path) -> dict:
    p = root / LOCK_FILE
    if not p.exists():
        return {"owner": None}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {"owner": None}


def _is_held(lock: dict) -> bool:
    if not lock or lock.get("owner") in (None, "", "null"):
        return False
    try:
        started = _parse_iso(lock["started_at"])
        ttl = int(lock.get("ttl_minutes", DEFAULT_TTL_MIN))
    except (KeyError, ValueError):
        return False
    return _now() < started + timedelta(minutes=ttl)


def _write_commit_push(root: Path, lock: dict, message: str) -> bool:
    """Write the lock, commit, and push to main. Return True on success,
    False if the push was rejected (lost the CAS race)."""
    (root / LOCK_FILE).write_text(
        json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    _git("add", LOCK_FILE)
    # commit may be a no-op if nothing changed; tolerate that.
    c = _git("commit", "-m", message, check=False)
    if c.returncode != 0 and "nothing to commit" not in (c.stdout + c.stderr):
        # still try to push whatever HEAD is
        pass
    p = _git("push", "origin", "HEAD:main", check=False)
    if p.returncode == 0:
        return True
    # rejected -> re-integrate and report the race to the caller
    _git("fetch", "origin", capture=False)
    _git("rebase", "origin/main", check=False)
    return False


def cmd_status(root: Path) -> int:
    print(json.dumps(_read_lock(root), indent=2))
    return 0


def cmd_preflight(root: Path, owner: str) -> int:
    _integrate()
    lock = _read_lock(root)
    if _is_held(lock) and lock.get("owner") != owner:
        print(json.dumps({"decision": "YIELD", "held_by": lock.get("owner"),
                          "task": lock.get("task"),
                          "started_at": lock.get("started_at")}))
        return YIELD_EXIT
    print(json.dumps({"decision": "PROCEED",
                      "current_owner": lock.get("owner")}))
    return 0


def cmd_acquire(root: Path, owner: str, task: str, ttl: int, note: str) -> int:
    _integrate()
    lock = _read_lock(root)
    if _is_held(lock) and lock.get("owner") != owner:
        print(json.dumps({"decision": "YIELD", "held_by": lock.get("owner")}))
        return YIELD_EXIT
    new = {
        "owner": owner,
        "cycle_id": _now().strftime("%Y-%m-%dT%H:%MZ-") + uuid.uuid4().hex[:4],
        "started_at": _iso(_now()),
        "ttl_minutes": int(ttl),
        "task": task,
        "note": note,
    }
    for attempt in range(1, PUSH_RETRIES + 1):
        if _write_commit_push(root, new, f"chore(lock): acquire [{owner}] {task}"):
            print(json.dumps({"decision": "ACQUIRED", **new}))
            return 0
        # lost the race: re-check who holds it now
        lock = _read_lock(root)
        if _is_held(lock) and lock.get("owner") != owner:
            print(json.dumps({"decision": "YIELD", "held_by": lock.get("owner"),
                              "after_race": True}))
            return YIELD_EXIT
        print(f"acquire: push race, retry {attempt}/{PUSH_RETRIES}",
              file=sys.stderr)
    print("ERROR: could not acquire lock after retries", file=sys.stderr)
    return 2


def cmd_release(root: Path, owner: str) -> int:
    _integrate()
    lock = _read_lock(root)
    if lock.get("owner") not in (owner, None, "", "null"):
        print(f"WARNING: lock owned by {lock.get('owner')}, not {owner}; "
              "releasing anyway per protocol", file=sys.stderr)
    released = {"owner": None, "released_at": _iso(_now()),
                "released_by": owner, "ttl_minutes": DEFAULT_TTL_MIN}
    for attempt in range(1, PUSH_RETRIES + 1):
        if _write_commit_push(root, released, f"chore(lock): release [{owner}]"):
            print(json.dumps({"decision": "RELEASED", **released}))
            return 0
        print(f"release: push race, retry {attempt}/{PUSH_RETRIES}",
              file=sys.stderr)
    print("ERROR: could not push release after retries", file=sys.stderr)
    return 2


def main() -> int:
    ap = argparse.ArgumentParser(description="Multi-agent coordination lock.")
    ap.add_argument("command",
                    choices=["preflight", "acquire", "release", "status"])
    ap.add_argument("--owner", choices=VALID_OWNERS,
                    help="this agent's name (required except for status)")
    ap.add_argument("--task", default="", help="the in_progress task name")
    ap.add_argument("--ttl", type=int, default=DEFAULT_TTL_MIN,
                    help="lock TTL in minutes (default 120)")
    ap.add_argument("--note", default="", help="optional free-text note")
    a = ap.parse_args()
    root = _repo_root()
    if a.command == "status":
        return cmd_status(root)
    if not a.owner:
        print("ERROR: --owner is required for this command", file=sys.stderr)
        return 1
    if a.command == "preflight":
        return cmd_preflight(root, a.owner)
    if a.command == "acquire":
        return cmd_acquire(root, a.owner, a.task, a.ttl, a.note)
    if a.command == "release":
        return cmd_release(root, a.owner)
    return 1


if __name__ == "__main__":
    sys.exit(main())
