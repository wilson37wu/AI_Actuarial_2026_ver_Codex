# Latest Cycle Status — W87 (claude, AUTO)

**Timestamp:** 2026-06-30T01:27:10Z
**Cycle ID:** 2026-06-30T01:10Z-c0a2
**Owner:** claude (Cowork `auto_actuarial_stochastic_model`)
**Verdict:** ✅ PASS — auto-admissible test-tooling only; origin/main delta = **+1 new test file**; no model-FORM, governed-artifact, or contract change.

## One task executed
Authored **`tests/test_gitignore_covers_junk_probes.py`** — a **pure-Python** meta-gate that shells
`git check-ignore -q` (SKIP when git absent / not a work tree) to assert that **a representative path from every
documented junk/probe family** in `AGENT_COORDINATION.md` §6 is git-ignored, so the protocol's promise *"junk
never gets committed"* is enforced in CI rather than by convention. **5 passed.**

Two agents (Codex, Claude Cowork) share this repo and both strew scratch/probe/interrupted-write artifacts on the
working mount (`.w59_probe.tmp`, `_sync_probe.txt`, `_perm_test_wt`, `.phase22_task2_stage/`, …). Until now nothing
**failed** if a future `.gitignore` edit silently dropped a family and a probe slipped into a commit.

### Families covered (17 representative samples → family map)
`*.tmp` (root + subdir), `_*probe*`, `_sync_probe*.txt`, `.w<n>_*.tmp`, `_perm_test*`, `_wtest*`, `_writeprobe*`,
`__pycache__/`, `*.py[cod]`, `.pytest_cache/`, `node_modules/`, `.~lock.*#`, `.phase*_stage/`, `C:/`, `*.bak`,
`model_inputs.json`.

### Why `git check-ignore` (not a re-implemented matcher)
`git check-ignore -q -- <path>` returns 0 if the path *would* be ignored, 1 if not, and works on the path string
alone — the file need not exist — so the gate mutates nothing, needs no fixtures, and uses git's own matcher (so
it cannot drift from real commit behaviour the way a hand-rolled `fnmatch` would).

### Teeth (gate is not vacuous)
1. **Both-ways discrimination** — positive samples return 0 (ignored) **and** tracked source files (`README.md`,
   `scripts/run_model.py`, `offline_home.html`, `ui_data.json`, `tests/test_nojsdom_guards_are_collected.py`)
   return 1 (NOT ignored), so a degenerate always-0 matcher cannot pass.
2. **Regression re-verified** — in an **isolated throwaway git repo** (copied `.gitignore` + the test), deleting
   the `*.tmp` and `_*probe*` rules drove **3 of 5 tests RED** (`test_documented_junk_patterns_are_ignored`,
   `test_check_ignore_has_teeth_both_ways`, `test_gitignore_lists_core_hygiene_patterns`). The governed clone was
   never mutated (copy-out only).
3. **Pure-structural backstop** (no git needed) — core hygiene pattern lines literally present in `.gitignore`;
   catches a gutted `.gitignore` even where `check-ignore` is unavailable.

## Verification gates — all GREEN
| Gate | Result |
|---|---|
| C — offline GUI self-test | `self_test_ok:true`, `engine_ready:true` |
| C — run_model smoke (seed 42, 100×4, no-tail) | nested **49657.9** / gaussian **37499.0** / var-covar **30267.9** (bit-match) |
| D — packaging | `actuarial_gui.spec` AST-parse OK; `release.workflow.yml` valid YAML (3-OS ubuntu/windows/macos matrix; jobs build+release); `offline_bootstrap.py --self-test` ok×3; `build_phase_pkg_task1_validate` **26/26** (incl `ui_app_byte_unchanged` + `governed_headline_present`) |
| Integrity — structural | `build_offline_home_validate` **177/177**; `test_offline_home_validate` **4/4** |
| Integrity — node parity | `offline_home_loader_parity.cjs` **10/10** |
| Integrity — sibling regressions | W84+W85 wrappers + W86 meta-gate + **new W87** = **23 passed** together |
| Integrity — MLMC | **53/53** (8 + 19 + 4 + 22) |
| **New W87 meta-gate** | **5 passed** |

## Governed artifacts — byte-UNCHANGED
- `offline_home.html` md5 **03d6538d3cae9efb83062ecbfab096e9**
- `ui_data.json` contract **1.23.0**, headline **39975.654628199336**

(The Gate-C smoke re-wrote `docs/validation/RUN_MODEL_{AGGREGATION_REPORT,SUMMARY}.json` in the clone — those hold
the *WorkedExample* run, not the governed default — reverted via `git checkout`, not committed → origin/main delta
= **+1 new test file only**.) Engine lock: numpy 1.26.4 / scipy 1.13.1 / pandas 2.2.3 / pytest 9.1.1 (fresh `/tmp`
venv); PyYAML installed in the venv **only** to lint the CI recipe YAML (not an engine pin; headline unaffected).

## In-progress / owner-gated
**Phase 38 Task 3** — fold Cash Flows + Products + the Phase 37 Scenario Explorer into byte-pinned `ui_app.html`
as native tabs — remains **OWNER-GATED** (owner sha256 re-baseline across ~10 governance/gate scripts + a
`ui_data.json` contract bump, plus a jsdom-equipped env for `scripts/ui_app_self_test.cjs`). Left in_progress.
Model frontier remains frozen/owner-gated (stage-5 tail-MLMC default; MR-LONGEV-1 longevity 5th driver; LSMC SCR
proxy; signed per-OS binaries).

## Registered next — W88
**`tests/test_governed_offline_ui_byte_anchors.py`** — a pure-Python pytest meta-gate that **pins the governed
offline-UI byte anchors in CI**: `md5(offline_home.html) == 03d6538d3cae9efb83062ecbfab096e9`, `ui_data.json`
`contract_version == 1.23.0`, and headline `39975.654628199336` present in `ui_data.json`. Today these anchors are
checked only **manually** each cycle (and `build_phase_pkg` pins `ui_app.html`, a *different* file); `grep
'03d6538d' tests/ scripts/` → none, so `offline_home.html`'s exact md5 is currently unguarded in pytest. Converts
the manual byte-stability check into an automatic guard, directly serving the owner offline-UI directive *"keep
governed UI artifacts byte-stable."* Distinct from W84/W85 (guard wrappers), W86 (guard-coverage), W87 (gitignore
hygiene); stdlib only; no governed bytes; no model-FORM change.

## Coordination
Fresh `/tmp` clone (mount `.git` untouched); lock `2026-06-30T01:10Z-c0a2` acquired this cycle, released at end;
push via fetch-rebase-retry; mount synced to origin/main (`.agent_lock.json` ignored as dynamic).
