"""Repo-hygiene CI meta-gate (W87) - the documented junk/probe artifact patterns
stay git-ignored, so "junk never gets committed" is enforced in CI rather than
by convention.

Background
----------
AGENT_COORDINATION.md section 6 ("Repo hygiene") states: *"Junk never gets
committed - see .gitignore (probes, *.tmp, __pycache__, office .~lock.*, stage
dirs, stray C:\\tmp artifacts)."* Two agents (Codex, Claude Cowork) develop this
repo on staggered schedules and both leave scratch/probe/interrupted-write
artifacts on the working mount (e.g. .w59_probe.tmp, _sync_probe.txt,
_perm_test_wt, .phase22_task2_stage/). That promise has so far been kept only by
convention - nothing FAILS if a future .gitignore edit silently drops a family
and a probe slips into a commit.

This module is a pure-Python meta-gate that asserts, via `git check-ignore`, that
a representative path from every documented junk family is ignored, and - as
teeth - that real tracked source files are NOT ignored (so the gate is not
vacuously green because check-ignore returns 0 for everything). It complements
W84/W85 (jsdom-free guard wrappers) and W86 (guard-coverage meta-gate): those
police the offline-UI guard surface; this polices repo hygiene. Different target,
same "enforce-in-CI-not-by-convention" pattern.

Why git check-ignore (not re-implement gitignore matching)
----------------------------------------------------------
`git check-ignore -q -- <path>` returns 0 if the path WOULD be ignored, 1 if not,
and operates on the path string alone - the file need not exist - so the gate
mutates nothing and needs no fixture files. It uses git's own matcher, so it
cannot drift from real commit behaviour the way a hand-rolled fnmatch would.

Auto-admissibility
------------------
Test-tooling only: Python standard library + a read-only `git check-ignore`
subprocess; no network, no writes, no node. It ships nothing the model/UI
computes and changes NO governed byte, model figure, or contract version. SKIPs
(never fails) when git is absent or the tree is not a work tree, mirroring
W84/W85's skip-when-node-absent. The pure-structural .gitignore assertion needs
no git and always runs.
"""
import os
import subprocess

import pytest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
_GITIGNORE = os.path.join(_REPO, ".gitignore")

# A representative path for every junk/probe family documented in
# AGENT_COORDINATION.md section 6 and enumerated in .gitignore. Each MUST be
# git-ignored. Synthetic basenames (the "_xyz"/"zzz" suffixes) keep them clear of
# any genuinely tracked path so the check reflects ignore rules, not index state.
_IGNORED_SAMPLES = {
    "scratch_xyz.tmp": "scratch / interrupted-write (*.tmp)",
    "par_model_v2/zzz.tmp": "*.tmp in a subdirectory",
    "_probe_write_xyz.tmp": "generic probe (_*probe*)",
    "_sync_probe_xyz.txt": "mount-sync probe (_sync_probe*.txt)",
    ".w99_probe.tmp": "timestamped write/probe snapshot (.w<n>_*.tmp)",
    "_perm_test_xyz": "write-permission probe (_perm_test*)",
    "_wtest_xyz": "write test (_wtest*)",
    "_writeprobe_xyz.tmp": "write probe (_writeprobe*)",
    "__pycache__/zzz.pyc": "python bytecode cache dir (__pycache__/)",
    "zzz.pyc": "python bytecode (*.py[cod])",
    ".pytest_cache/v/cache/lastfailed": "pytest cache (.pytest_cache/)",
    "node_modules/zzz/index.js": "node dependencies (node_modules/)",
    ".~lock.zzz.json#": "office / editor lock file (.~lock.*#)",
    ".phasezz_stage/zzz": "per-phase staging dir (.phase*_stage/)",
    "C:/tmp/zzz": "stray Windows-style path (C:/)",
    "zzz.bak": "editor / pre-edit backup (*.bak)",
    "model_inputs.json": "user run input (regenerated; never committed)",
}

# Real tracked source files that MUST NOT be ignored. These are the gate's teeth:
# if `git check-ignore` ever returned 0 indiscriminately (or .gitignore grew an
# over-broad rule swallowing source), these flip and the gate fails.
_NOT_IGNORED_SAMPLES = (
    "README.md",
    "scripts/run_model.py",
    "offline_home.html",
    "ui_data.json",
    "tests/test_nojsdom_guards_are_collected.py",
)

# Core hygiene patterns that must literally appear in .gitignore. Catches a
# gutted .gitignore even on a host where check-ignore misbehaves, and pins the
# linkage to AGENT_COORDINATION.md section 6.
_REQUIRED_PATTERNS = (
    "*.tmp",
    "_*probe*",
    "_perm_test*",
    "_wtest*",
    "__pycache__/",
    "*.py[cod]",
    ".pytest_cache/",
    "node_modules/",
    ".~lock.*#",
    ".phase*_stage/",
    "C:/",
    "*.bak",
)


def _git(*args):
    return subprocess.run(
        ["git", "-C", _REPO, *args],
        capture_output=True,
        text=True,
    )


def _require_git_worktree():
    """SKIP (not fail) when git is unavailable or _REPO is not a work tree, so
    this gate is a no-op in lanes without git rather than a false red."""
    try:
        res = _git("rev-parse", "--is-inside-work-tree")
    except (FileNotFoundError, OSError):
        pytest.skip("git executable not available")
    if res.returncode != 0 or res.stdout.strip() != "true":
        pytest.skip("not inside a git work tree (e.g. exported tarball)")


def _check_ignore_rc(relpath):
    # git check-ignore -q: exit 0 = ignored, 1 = NOT ignored, 128 = error.
    return _git("check-ignore", "-q", "--", relpath).returncode


def test_gitignore_file_present():
    # Anchor: never vacuously green because .gitignore vanished.
    assert os.path.isfile(_GITIGNORE), "missing %s" % _GITIGNORE


def test_documented_junk_patterns_are_ignored():
    # THE invariant: a sample from every documented junk/probe family is ignored.
    _require_git_worktree()
    leaked = []
    for path, family in sorted(_IGNORED_SAMPLES.items()):
        if _check_ignore_rc(path) != 0:
            leaked.append("%s  [%s]" % (path, family))
    assert not leaked, (
        "These documented junk/probe families are NOT git-ignored (a commit "
        "could leak them); restore the rule in .gitignore (see "
        "AGENT_COORDINATION.md section 6):\n  " + "\n  ".join(leaked)
    )


def test_real_source_files_are_not_ignored():
    # Teeth: prove the gate discriminates. If check-ignore returned 0 for
    # everything, or an over-broad rule swallowed source, these would be flagged.
    _require_git_worktree()
    swallowed = []
    for path in _NOT_IGNORED_SAMPLES:
        abs_path = os.path.join(_REPO, path)
        if not os.path.isfile(abs_path):
            continue  # tolerate a renamed reference; other anchors keep teeth
        if _check_ignore_rc(path) != 1:
            swallowed.append(path)
    assert not swallowed, (
        "Tracked source file(s) match a .gitignore rule - it is too broad and "
        "would hide real files from commits: %s" % swallowed
    )


def test_check_ignore_has_teeth_both_ways():
    # Non-vacuousness in one place: at least one sample is ignored AND at least
    # one real file is not, so a degenerate check-ignore (always-0 or always-1)
    # cannot pass this module.
    _require_git_worktree()
    assert _check_ignore_rc("scratch_xyz.tmp") == 0, "expected *.tmp to be ignored"
    assert _check_ignore_rc("README.md") == 1, "expected README.md NOT ignored"


def test_gitignore_lists_core_hygiene_patterns():
    # Pure-structural (no git needed): the core hygiene patterns literally exist
    # in .gitignore. Backstop for hosts where check-ignore is unavailable.
    with open(_GITIGNORE, "r", encoding="utf-8", errors="replace") as fh:
        body = fh.read()
    lines = {ln.strip() for ln in body.splitlines()}
    missing = [p for p in _REQUIRED_PATTERNS if p not in lines]
    assert not missing, (
        ".gitignore is missing core hygiene pattern line(s) documented in "
        "AGENT_COORDINATION.md section 6: %s" % missing
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([os.path.abspath(__file__), "-v"]))
