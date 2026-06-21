# Cycle Status — Post-Phase-35 Finding (4)

**When:** 2026-06-14T13:08Z (Claude 06:00/18:00 window; ran in Codex's nominal slot but lock was FREE → preflight PROCEED, acquired cleanly: cycle_id `2026-06-14T13:08Z-16e4`)
**Owner:** claude
**Task (single in_progress):** Finding (4) — `tests/test_phase26_task4_delta_matrix.py` `KeyError 'distance_to_nested'`

## Preflight / sync
- All git done in a FRESH `/tmp` clone of `origin/main` (never the mounted `.git`). HEAD `b744de9` (`chore(lock): release [claude]`), i.e. current.
- Lock was free (`owner: null`, released 12:17Z by claude). `agent_lock.py preflight` → `{"decision":"PROCEED"}`; `acquire` → ACQUIRED.

## Root cause
`test_nested_reference_outside_task3_ci_disclosed` read an **old, restructured** report shape:
`rep["result"]["distance_to_nested"]{nested_reference, t_component_rel_gap}`.
The live published report `docs/validation/PHASE26_TASK4_DELTA_MATRIX_REPORT.json` (and its builder `scripts/build_phase26_task4_delta_matrix.py`) emit instead:
- `result["config"]["nested_pathwise_reference"]` = 46638.9, and
- `result["gap_to_nested"][basis][copula]` per-basis/copula relative-gap matrix.
There is no `distance_to_nested` key anywhere in the current pipeline → `KeyError`. Same frozen-test-vs-moving-repo anti-pattern as Finding (3).

## Change (test-only)
`test_nested_reference_outside_task3_ci_disclosed` rewritten to read the live keys, preserving intent (nested reference 46638.9; component/t basis point > 14% below nested truth, outside the Task 3 CI):
```python
assert rep["result"]["config"]["nested_pathwise_reference"] == pytest.approx(46638.9)
assert rep["result"]["gap_to_nested"]["component"]["t"] < -0.14
```
Semantics are identical: old `t_component_rel_gap` ≡ `gap_to_nested["component"]["t"]`; old `nested_reference` ≡ `config["nested_pathwise_reference"]`. No new convention invented; no source/data/governance figures changed.

## Verification
pytest still unavailable in sandbox (numpy now present, but `pip install pytest` fails: `Errno 28 No space left on device`; vendored pytest is pyc-only/non-importable). Verified statically:
1. `py_compile` OK on the edited test.
2. Standalone replication of both new assertions vs the live report → **PASS** (`nested_pathwise_reference` == 46638.9; `gap_to_nested.component.t` = -0.142869 < -0.14).
3. Old `distance_to_nested` key confirmed absent (regression reproduced — old test was genuinely RED).
4. No other `tests/` reference to `distance_to_nested` remains (only the new explanatory comment).

## Next
- Finding (4) backlog cleared. No further known RED tests flagged in state.
- Then per standing instruction: research further stochastic-model improvements; **begin the offline, zero-dependency user interface** (consumes only model output; renders results graphically/interactively with no install requirement).

## Owner note
Sandbox cannot run the numpy/scipy/pytest suite (no disk space to install pytest). All verification this cycle is static/standalone, consistent with the prior several cycles.
