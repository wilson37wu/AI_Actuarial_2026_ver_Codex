# Multi-Agent Coordination Protocol

**Repository:** `AI_Actuarial_2026_ver_Codex`
**Agents sharing this repo:** OpenAI **Codex** and Claude **Cowork** (`auto_actuarial_stochastic_model`).
**Purpose:** let both agents develop this project on their own schedules **without** clobbering each other's commits, duplicating tasks, or corrupting the shared state files.

This file is the single source of truth. **Both agents MUST read and follow it at the start of every cycle.** It is intentionally simple: *stagger the schedules, take a lock, always integrate before pushing, do one task, release the lock.*

---

## 0. TL;DR cycle checklist (every run, every agent)

1. **Integrate first.** Get a clean, up-to-date `main` (fetch + rebase, or a fresh clone of `origin/main`).
2. **Preflight the lock.** Read `.agent_lock.json`. If another agent holds a **non-expired** lock → **yield** (do no work, exit cleanly).
3. **Acquire the lock.** Write your lock, commit, push. If the push is rejected (a race), re-integrate, re-check; if now locked by the other agent → yield.
4. **Do exactly ONE task** — the single `in_progress` item in `.claude-dev/MODEL_DEV_STATE.json`.
5. **Push your work** (re-integrate + push, retry on rejection).
6. **Release the lock** (clear it, commit, push).
7. If you yielded or failed, leave `main` exactly as you found it.

A helper implements steps 1–3, 6: `python scripts/agent_lock.py <preflight|acquire|release|status> --owner <codex|claude> --task "<name>"`.

---

## 1. Schedules — staggered, never overlapping

Each cycle should fit inside its window. Run the two agents **offset by 6 hours** so they never start at the same time:

| Agent | Cadence | Run times (UTC) |
|---|---|---|
| Codex | every 12h | **00:00 and 12:00** |
| Claude Cowork | every 12h | **06:00 and 18:00** |

If you change cadence, keep the offset ≥ the maximum cycle length and ≥ the lock TTL (below). Staggering is the first line of defence; the lock is the backstop for overruns/jitter.

---

## 2. The lock — `.agent_lock.json`

A small file at the repo root, the poor-man's distributed lock. Shape:

```json
{
  "owner": "claude",            // "codex" | "claude" | null (released)
  "cycle_id": "2026-06-10T18:00Z-ab12",
  "started_at": "2026-06-10T18:00:11Z",
  "ttl_minutes": 120,
  "task": "Phase 29 Task 3",
  "note": "free text"
}
```

**Rules**
- **Acquire** = write the file with your `owner` + fresh `started_at`, commit, **push**. The push is the atomic compare-and-set: if two agents race, GitHub accepts exactly one ref update; the loser's push is **rejected** → it re-integrates, sees the winner's lock, and **yields**.
- A lock is **held** if `owner != null` AND `now < started_at + ttl_minutes`.
- A lock is **stale** (an agent crashed mid-cycle) if `now ≥ started_at + ttl_minutes`. Any agent may reclaim a stale lock (overwrite it on acquire).
- **Release** = set `owner: null`, commit, push. Always release at the end of a successful cycle. (Stale-expiry covers the case where you can't.)
- Default `ttl_minutes`: **120** (must exceed your longest cycle).

**Never** do project work while you do not hold a fresh lock in your own name.

---

## 3. Integrate before you push — no exceptions

`main` is shared. Before **any** push:

```
git fetch origin
git rebase origin/main          # or: git pull --rebase origin main
# ... your commit(s) ...
git push origin HEAD:main
# if rejected:
git fetch origin && git rebase origin/main && git push origin HEAD:main   # retry (up to 3x)
```

Because each cycle does **one** task and rebases first, conflicts on code are rare. The shared **state files** (`.claude-dev/MODEL_DEV_STATE.json`, `GOVERNANCE_STORE.json`, `MODEL_DEV_LOG.md`, `MODEL_DEV_TASK_PROMPT.md`) are only ever edited by the **lock holder**, so they never conflict in practice. Per-cycle status files use unique names (`LATEST_CYCLE_STATUS_<date>_<task>.md`) and never collide.

---

## 4. One task per cycle, claimed via state

The next task is the single `in_progress` entry in `.claude-dev/MODEL_DEV_STATE.json`. The lock holder:
1. reads `in_progress`,
2. completes that ONE task,
3. moves it to `completed`, sets the next `in_progress`,
4. records the cycle.

Do **not** start a second task. This, plus the lock, is what prevents the duplicate-work seen historically (e.g. two parallel "Phase 29 Task 2" attempts).

---

## 5. Git hygiene by environment

### Claude Cowork (Windows host + Linux virtiofs sandbox) — MANDATORY
The repo is mounted read-mostly via virtiofs that **forbids deletes/renames**, so in-place `git add/commit` leaves undeletable `.git/*.lock` "ghost locks" and the local `main` ref goes stale. **Therefore Claude does ALL git in a fresh throwaway clone**, never against the mounted `.git`:

```
git clone --depth 1 "$(git -C <repo> remote get-url origin)" /tmp/cycle_clone
cd /tmp/cycle_clone
# run agent_lock.py preflight/acquire here; copy produced files in from the mount;
# commit; push; release. Discard /tmp/cycle_clone at the end.
```
Write/verify source + state files on the mount (or off-mount), then **copy** them into the clone (`cp` preserves integrity; the in-place editor has corrupted files mid-write before — always re-parse JSON after writing). Never run `git add/commit` in the mounted worktree.

### Codex (normal Linux checkout)
Operate in your checkout directly. Still: fetch-rebase before push, honour the lock, and never force-push `main`.

---

## 6. Repo hygiene
- Junk never gets committed — see `.gitignore` (probes, `*.tmp`, `__pycache__`, office `.~lock.*`, stage dirs, stray `C:\tmp` artifacts).
- Never `git push --force` to `main`.
- Never `git gc`/`prune` on the mounted Claude repo (it has historically held the only ref to in-flight commits).

---

## 7. Codex setup snippet (paste into Codex's project instructions)

> **Before doing any work on this repo, follow `AGENT_COORDINATION.md`.** Concretely:
> 1. `git fetch origin && git checkout main && git rebase origin/main`.
> 2. Run `python scripts/agent_lock.py preflight --owner codex`. If it exits non-zero ("locked by claude"), **stop this run** — do no work, make no commits.
> 3. Else `python scripts/agent_lock.py acquire --owner codex --task "<the in_progress task>"` (this commits + pushes the lock; if it reports a lost race, stop).
> 4. Do **one** task (the `in_progress` item in `.claude-dev/MODEL_DEV_STATE.json`). Update state, log, and a uniquely-named `LATEST_CYCLE_STATUS_<date>_<task>.md`.
> 5. `git fetch origin && git rebase origin/main && git push origin HEAD:main` (retry up to 3× on rejection).
> 6. `python scripts/agent_lock.py release --owner codex` (commits + pushes the release).
> 7. Run on the **00:00 / 12:00 UTC** schedule (Claude runs 06:00 / 18:00). Never force-push `main`.

---

*If anything in this protocol is ambiguous for a given run, the safe default is to **yield** (do nothing and leave `main` untouched) rather than risk a conflicting write.*
