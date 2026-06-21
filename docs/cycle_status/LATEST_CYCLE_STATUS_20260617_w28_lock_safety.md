# Cycle Status — W28 (claude) — 2026-06-17

## Task
Coordination-infra hardening (decision-neutral): fix a latent **false-`ACQUIRED`** in
`scripts/agent_lock.py`. No model-form change; no governed-artifact rebuild.

## Defect found (this cycle, in STEP-0 preflight)
On a fresh `/tmp` clone with **no git identity**, `agent_lock.py acquire` reported
`{"decision":"ACQUIRED"}` while the lock **never reached origin**:
1. `git commit` failed silently ("Author identity unknown").
2. The subsequent `git push origin HEAD:main` pushed an **unchanged HEAD** → returned 0.
3. The helper read that 0 as success → false `ACQUIRED`/`RELEASED`.

Impact: both agents could believe they hold the lock simultaneously → the exact
clobbering the protocol exists to prevent.

## Fix
- **`_ensure_identity(owner)`** — sets a repo-local fallback identity
  (`<owner>-cowork-agent` / `<owner>-agent@actuarial-bot.local`) when none is
  configured; never overwrites an existing identity. Wired into `cmd_acquire` and
  `cmd_release`.
- **`_write_commit_push` guard** — verifies HEAD actually advanced **and** the
  committed `.agent_lock.json` carries the intended `owner` before pushing; a genuine
  local commit failure now **exits 2** instead of masquerading as success.
- **`AGENT_COORDINATION.md` §5** documents the self-heal + false-success guard.

## Verification
- `tests/test_agent_lock_identity.py` — 4/4 OK (stdlib `unittest`):
  self-heal sets identity; existing identity not overwritten; commit really lands on
  origin/main; rejecting pre-commit hook → `exit 2` (no false success).
  (~14.7s/test due to slow sandbox git I/O — run individually, not as one 45s batch.)
- `py_compile` OK; clone↔mount `md5` identical for `agent_lock.py` and
  `AGENT_COORDINATION.md`.

## Governed artifacts — UNCHANGED
`offline_home.html` / `ui_app.html` / `ui_data.json` not modified this cycle;
contract **1.23.0**; headline single-df t SCR **39,975.654628199336** intact.

## Frontier
**OWNER PIVOT.** Stop-rule-admissible efficiency/diagnostic pool (MR-CAL-1, MR-VR-1,
MR-VR-2) and offline-UI decision-neutral pool (a)–(g) remain EXHAUSTED. Remaining
items — MR-LONGEV-1 longevity 5th driver (parameter-adding model-FORM change),
packaging Option A/B/C, or declare-frontier-complete-and-freeze — all need owner
sign-off. MR-016/MR-017 dependence decision still owner-pending.

## Git hygiene
All git in a fresh `/tmp` clone of `origin/main`; mount `.git` untouched. The mount
file-tool corrupted `agent_lock.py` mid-write (truncated on disk) → patch was rebuilt
in the clone and `cp`'d to the mount per §5.
