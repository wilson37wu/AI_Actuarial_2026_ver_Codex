# W199 — Exhausted-backlog verification + mount-sync
## Genuinely-new finding: the second agent has NEVER run

- **Cycle:** W199 · lock `2026-07-21T12:08Z-f04f` · owner `claude`
- **Preflight:** PROCEED (owner null; released by claude 11:21:59Z)
- **Task executed:** W199 exhausted-backlog verification + mount-sync. Phase 38 Task 3 remains **OWNER-GATED** and was not executed.
- **Verdict:** FULL BATTERY GREEN · governed artifacts byte-stable · record-only

---

## 1. Headline finding — Codex has never acquired the lock (312 acquires, 41 days)

W196–W198 escalated the hourly-cron defect primarily as a **collision hazard** with the
Codex agent ("the 6h stagger is gone", "collides with the other agent's slot").
That framing is now **materially corrected**.

Definitive test — every value ever written to `.agent_lock.json` across full history:

| `"owner"` value written | occurrences |
|---|---|
| `"claude"` | 318 |
| `null` (release) | 318 |
| `"codex"` | **0** |

- **312** lock acquires between 2026-06-10T18:49Z and 2026-07-21T12:08Z. **None** by Codex.
- **1111** commits in repo history. Author breakdown: all are Claude-agent identities
  (`claude-cowork-agent` 629, `Claude Cowork` 180, `claude-cowork` 61, `claude` 36,
  `AutoDev` 52, + minor variants) or the owner (`wilson37wu` 62, `Wilson Wu` 24).
  **Zero** commits by any Codex identity.
- No commit message or author field mentions Codex except the repo name itself
  (`AI_Actuarial_2026_ver_Codex`) and this cycle's own lock message.

**Correction to the prior record.** W198 stated "no Codex commits since W178", which
implies Codex committed at some earlier point. It never did. The second agent has
not participated in this repository at any time.

### Why this changes the owner's priority ordering

- The 6h stagger and the push-lock protect against a counterparty that **has never appeared**.
  The collision risk W198 escalated as urgent is, on the evidence, **theoretical**.
- The real, realised cost of `cronExpression: "0 * * * *"` is therefore **not** a clobbering
  hazard. It is **12x wasted compute/API spend** and **12x near-duplicate cycle records** —
  W194–W199 are six consecutive near-duplicate verification passes in six hours.
- This is still a reason to fix the cron, but on **cost** grounds, not safety grounds — and it
  raises a **new owner question that has not previously been asked**: is Codex intended to run
  at all? If not, the coordination machinery (stagger, lock, yield) is pure overhead and the
  repo can run single-agent, simplifying every cycle.

**Not auto-applied.** The scheduler is owner infrastructure outside the repo, and the skill's
write-action rule limits this agent to reporting. Same call as W196/W197/W198.

---

## 2. Second finding — the ~14s/test cost in `test_agent_lock_identity` is root-caused

W198 recorded, as an unexplained operational note, that `tests/test_agent_lock_identity.py`
costs "~14s PER TEST". The cause is now isolated to a single call, with a clean control:

| Scenario (push to a **local** bare origin) | time |
|---|---|
| `git push` with `GIT_AUTHOR_EMAIL`/`GIT_COMMITTER_EMAIL` set | **21 ms** |
| `git push` with those unset (control, identical setup) | **13 799 ms** |
| `getent hosts $(hostname)` (independent probe) | rc=2 after **10 024 ms** |

`setUp` correctly blanks git config and redirects `HOME` to simulate "no identity". That forces
git to **derive** a committer ident for the push's reflog entry, which triggers an FQDN lookup.
This sandbox has no resolvable hostname, so the resolver stalls ~10s (plus git's retry) → ~13.8s
per `setUp`, ×4 tests ≈ 55s. Raw git ops are 6–21 ms; pytest collection is 319 ms. Neither is the cost.

**Recommended fix (auto-admissible, next cycle):** export `GIT_AUTHOR_NAME/EMAIL` and
`GIT_COMMITTER_NAME/EMAIL` in `setUp` for the seed/push scaffolding.
Expected: suite ~56s → ~1s (≈55x).

**Safety analysis — the fix does not weaken any assertion:**
- `_identity_present()` reads `git config user.name`/`user.email`. Env ident vars do **not**
  populate git config, so test 1's "fresh clone has no identity" precondition is preserved.
- `test_commit_failure_is_fatal_not_false_success` forces its failure with a **rejecting
  pre-commit hook** (and calls `_ensure_identity("claude")` first), not via absent identity,
  so it is unaffected.

Reported, not implemented — one task per cycle.

---

## 3. Cadence status (unchanged, still half-applied)

| field | value |
|---|---|
| `cronExpression` | `0 * * * *` ← **still hourly** |
| `description` | "...12h cadence: 02:00 & 14:00 HKT = 18:00 & 06:00 UTC..." ← corrected |
| `enabled` | true |
| `lastRunAt` | 2026-07-21T12:06:41Z (this run) |
| `nextRunAt` | 2026-07-21T13:06:01Z |
| `jitterSeconds` | 361 |

Correct value remains **`0 2,14 * * *`** (proven in W198 from host-local cron evaluation).
Today's firings: W194 07:14Z · W195 08:08Z · W196 09:07Z · W197 10:08Z · W198 11:06Z · **W199 12:06Z**.

**The predicted Codex-window collision materialised**: this cycle fired at 12:06Z, inside the
documented Codex 12:00Z slot. Per finding 1 it was uncontested — no Codex lock, no Codex commits.
Preflight returned PROCEED cleanly and the lock was taken without a race.

---

## 4. Verification battery — ALL GREEN

Engine on the pinned lock (`/tmp/engine_libs`): numpy 1.26.4 / scipy 1.13.1 / pandas 2.2.3.

| Gate | Result |
|---|---|
| C — GUI self-test | `self_test_ok: true`, `engine_ready: true` |
| C — smoke (`--n-outer 100 --n-inner 4 --no-tail --seed 42`) | nested **49657.9** · gaussian **37499.0** · var-covar **30267.9** — exact bit-match |
| D — `packaging/actuarial_gui.spec` | AST-parses |
| D — `packaging/release.workflow.yml` | YAML valid |
| D — `packaging/offline_bootstrap.py --self-test` | `ok: true` |
| D — `scripts/build_phase_pkg_task1_validate.py` | `ok: true`, 26/26 |
| Integrity — `build_offline_home_validate.py` | **177/177**, failed: [] |
| Integrity — `tests/test_offline_home_validate.py` | **4/4** |
| Integrity — `offline_home_loader_parity.cjs` (node) | **10/10**, failed: [] |
| MLMC — `tests/test_mlmc_*` | **66/66** |
| `tests/test_agent_lock_identity.py` | **4/4** (run per-test; see §2) |

**Governed artifacts byte-stable:**
- `offline_home.html` md5 `03d6538d3cae9efb83062ecbfab096e9` ✓
- `ui_data.json` `contract_version: 1.23.0` ✓
- headline `39975.654628199336` present ✓

No model-FORM change, no contract bump, no headline re-baseline, no new stochastic driver.
Run-evidence churn in `docs/validation/` reverted — the only diff was `run_timestamp` /
`duration_seconds`; every model number was identical.

---

## 5. Owner-gated, unchanged

Phase 38 Task 3 (ui_app.html native-tab cutover) · LSMC proxy · MLMC-as-default (stage 5) ·
MR-LONGEV-1 longevity driver · signed per-OS binaries. Auto-admissible backlog remains SATURATED.
