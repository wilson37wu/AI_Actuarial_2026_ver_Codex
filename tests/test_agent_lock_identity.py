"""Regression tests for scripts/agent_lock.py commit-safety hardening.

Covers the two defects fixed in this cycle:

  1. A fresh /tmp clone inherits NO git identity, so ``git commit`` fails and
     the old helper's no-op ``push HEAD:main`` returned 0 -> a FALSE
     ``ACQUIRED``/``RELEASED`` while the lock never reached origin. We now
     self-heal the identity (``_ensure_identity``) and the commit succeeds.

  2. A genuine LOCAL commit failure (e.g. a rejecting hook) must be FATAL, not
     mistaken for the benign "nothing to commit" no-op. We verify the commit
     actually advanced HEAD and captured our owner before pushing.

Stdlib-only (no pytest required): run with
    python3 -m unittest tests.test_agent_lock_identity -v
or directly:
    python3 tests/test_agent_lock_identity.py
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LOCK_SCRIPT = REPO / "scripts" / "agent_lock.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("agent_lock_mod", LOCK_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git(cwd, *args, env=None):
    return subprocess.run(["git", *args], cwd=cwd, env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True)


class AgentLockCommitSafety(unittest.TestCase):
    def setUp(self):
        self.mod = _load_module()
        self.tmp = tempfile.mkdtemp(prefix="agentlock_test_")
        # Isolate from any ambient global/system git identity so "no identity"
        # is reproducible regardless of the host config.
        self.empty_cfg = os.path.join(self.tmp, "empty.gitconfig")
        open(self.empty_cfg, "w").close()
        self._saved_env = {k: os.environ.get(k) for k in
                           ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM", "HOME")}
        os.environ["GIT_CONFIG_GLOBAL"] = self.empty_cfg
        os.environ["GIT_CONFIG_SYSTEM"] = self.empty_cfg
        os.environ["HOME"] = self.tmp
        # Bare "origin" + working clone.
        self.origin = os.path.join(self.tmp, "origin.git")
        _git(self.tmp, "init", "--bare", self.origin)
        self.work = os.path.join(self.tmp, "work")
        os.makedirs(self.work)
        _git(self.work, "init")
        _git(self.work, "remote", "add", "origin", self.origin)
        # Seed an initial main commit (with a throwaway identity so setUp can
        # create history; then we REMOVE the identity to simulate a fresh clone).
        _git(self.work, "-c", "user.name=seed", "-c", "user.email=seed@x",
             "commit", "--allow-empty", "-m", "seed")
        _git(self.work, "push", "origin", "HEAD:main")
        _git(self.work, "config", "--unset", "user.name")
        _git(self.work, "config", "--unset", "user.email")
        self._cwd = os.getcwd()
        os.chdir(self.work)

    def tearDown(self):
        os.chdir(self._cwd)
        for k, v in self._saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _identity_present(self):
        name = _git(self.work, "config", "user.name").stdout.strip()
        email = _git(self.work, "config", "user.email").stdout.strip()
        return bool(name) and bool(email)

    def test_fresh_clone_has_no_identity_then_selfheals(self):
        self.assertFalse(self._identity_present(),
                         "precondition: clone should start with no identity")
        self.mod._ensure_identity("claude")
        self.assertTrue(self._identity_present(),
                        "_ensure_identity must set a fallback identity")

    def test_ensure_identity_does_not_overwrite_existing(self):
        _git(self.work, "config", "user.name", "Existing Person")
        _git(self.work, "config", "user.email", "existing@example.com")
        self.mod._ensure_identity("claude")
        self.assertEqual(
            _git(self.work, "config", "user.email").stdout.strip(),
            "existing@example.com")

    def test_acquire_path_actually_commits_and_pushes(self):
        # Simulate cmd_acquire's identity step on an identity-less clone, then
        # commit+push the lock; origin/main must really carry owner=claude.
        self.mod._ensure_identity("claude")
        lock = {"owner": "claude", "cycle_id": "test-1",
                "started_at": "2026-06-17T04:00:00Z", "ttl_minutes": 120,
                "task": "unit-test", "note": ""}
        ok = self.mod._write_commit_push(Path(self.work), lock, "acquire test")
        self.assertTrue(ok, "_write_commit_push should report success")
        origin_lock = _git(self.origin, "show",
                           "main:.agent_lock.json").stdout
        self.assertEqual(json.loads(origin_lock).get("owner"), "claude",
                         "origin/main must really carry the committed lock")

    def test_commit_failure_is_fatal_not_false_success(self):
        # With identity present but a rejecting pre-commit hook, the commit
        # fails for a non-"nothing to commit" reason. The helper must exit(2),
        # NOT return True off a no-op push of a stale HEAD.
        self.mod._ensure_identity("claude")
        hooks = os.path.join(self.work, ".git", "hooks")
        os.makedirs(hooks, exist_ok=True)
        hook = os.path.join(hooks, "pre-commit")
        with open(hook, "w") as fh:
            fh.write("#!/bin/sh\nexit 1\n")
        os.chmod(hook, 0o755)
        lock = {"owner": "claude", "cycle_id": "test-2",
                "started_at": "2026-06-17T04:00:00Z", "ttl_minutes": 120,
                "task": "unit-test", "note": ""}
        with self.assertRaises(SystemExit) as cm:
            self.mod._write_commit_push(Path(self.work), lock, "should fail")
        self.assertEqual(cm.exception.code, 2,
                         "genuine commit failure must be fatal (exit 2)")
        # And origin must NOT have been advanced with a bogus lock.
        origin_lock = _git(self.origin, "show",
                           "main:.agent_lock.json", env=None)
        self.assertNotEqual(origin_lock.returncode, 0,
                            "origin should have no lock file from a failed run")


if __name__ == "__main__":
    unittest.main(verbosity=2)
