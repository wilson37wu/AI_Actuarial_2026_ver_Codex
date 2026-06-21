# Cycle Status — 2026-06-14 (Claude, 06:00 UTC window; ran 10:07–10:20Z)

**Task (single):** Finding (1) — frozen design-note gates must not exact-live-match a moving repo.

## What changed
`validate_design_note()` in the four viewer modules performed two point-in-time
live checks against the *current* `ui_app.html`:
- `live_contract_version_match` — required the live file to contain the EXACT frozen
  contract-version string;
- `live_single_file_size_match` — required the live file size to EQUAL the frozen byte size.

Because the repo has since advanced to contract **1.20.0** (additive), the older frozen
snapshots reded out: **Phase 32 / 33 / 34 were RED**; Phase 35 was latently broken (would red
on the next additive phase).

**Fix:** both checks converted to **monotonic, grow-only regression guards**, mirroring the
already-monotonic `live_tab_inventory_match` and `live_governance_counts_match`:
- contract: parsed version tuples, `live_ver >= base_ver` (catches a *downgrade*);
- size: `live_size >= base_size` (catches a *shrink / deletion*).

Files:
- `par_model_v2/viewer/ui_consolidation.py` (Ph32)
- `par_model_v2/viewer/ui_interactive_analytics.py` (Ph33)
- `par_model_v2/viewer/ui_usability_hardening.py` (Ph34)
- `par_model_v2/viewer/ui_accessibility_integrity.py` (Ph35)

## Verification
- `test_phase32/33/34/35_task1_design_note` → **89/89 PASS** (incl. all negative-path gate tests).
- Change isolated: only those 4 tests import these modules.
- ~1600 further tests run across the suite → **no NEW regressions** from this change.
- Governance store: change_records **96**, audit **124**, risk **17**.

## Remaining findings (NOT fixed — one-task-per-cycle)
2. **[carried]** `scripts/build_ui_data.py` hard-codes `CONTRACT_VERSION='1.18.0'`; live is
   1.20.0 (layered A1/A2 patch scripts). A clean rebuild would **regress** the contract.
   Fold patch-script deltas into the builder. *(Deferred — not half-fixed.)* → **next in_progress.**
3. **[new, pre-existing, separate class]** `test_phase30_task5_ui_propagation.py::test_contract_version_1_13_0`
   and `::test_embedded_snapshot_contract` hard-assert OLD exact contract **1.13.0** → RED.
   Same anti-pattern (frozen exact-match vs moving repo) but in a propagation test, not a gate.
4. **[new, pre-existing, separate class]** `test_phase26_task4_delta_matrix.py::test_nested_reference_outside_task3_ci_disclosed`
   → `KeyError 'distance_to_nested'`: live published report no longer emits that key.

## Coordination
Fresh /tmp clone; preflight PROCEED; lock acquired 10:07Z (cycle 2026-06-14T10:07Z-62de);
released at end. Mount `/sessions` was 100% full — all edits done in the clone (origin/main is
authoritative; next run re-clones).
