# PHASE_IGUI_TASK6_VALIDATION_GATING (v1.0.0)

**Task:** Phase IGUI Task 6 - validation surfacing + governance gating before run  
**Domain:** D5_validation_gating  
**Generated:** 2026-06-15T04:17:43.500215+00:00

## Acceptance gate

- gate ok: **True** (27/27 checks)
- new third-party runtime deps: **0**
- outbound network calls: **0**
- localhost self-test ok: **True**
- RESULTS UI (ui_app.html) byte-unchanged: **True** (sha256 `6dca35b3520297263dd06086a1ced18cf831efb3fab6a6e8a9cde744500d7e65`)
- governed headline carried bit-for-bit: **39,975.654628199336**

## What the gate does

The Run action is **BLOCKED** until the assembled `model_inputs.json` is present and clean across **all** input domains:

- **Run controls (Task 2)** (`run_controls`)
- **Model points / in-force (Task 3)** (`model_points`)
- **Assumptions (Task 4)** (`assumptions`)
- **Economic scenarios / ESG (Task 5)** (`esg`)

Validation is surfaced through the REAL loader (`validate_assembled_inputs`), so the GUI shows exactly what would be rejected. On clearing, a governance run-gate + a run-level reproducibility digest are recorded before any run. Execution + results handoff are Task 7.

## Stop-rule (Phase 30) + owner-gating

- dependence copula structure echoed read-only as **`single_t_grouped_FROZEN`** (never altered here)
- MR-016/MR-017 dependence decision remains entirely with the owner

## Example cleared run-gate (deterministic digest)

```json
{
 "decision": "CLEARED",
 "run_permitted": true,
 "reproducibility_digest": "sha256:64682554635eda0561a118a57d8b8600e02fb4c2ca8f67e145ce9c97773efa81",
 "frozen_copula_structure": "single_t_grouped_FROZEN",
 "governed_headline": "39,975.654628199336",
 "n_blocking_issues": 0
}
```

## New localhost runner routes

- `GET /run-gate`
- `POST /preflight`
- `POST /run`

## Gate checks

- PASS gating_module_present
- PASS run_gui_present
- PASS loader_present
- PASS gating_module_stdlib_only
- PASS run_gui_serves_run_gate
- PASS run_gui_has_gate_endpoints
- PASS run_gui_still_localhost
- PASS run_gui_prior_pages_intact
- PASS loader_has_aggregate_validator
- PASS schema_version_lockstep
- PASS ui_app_byte_unchanged
- PASS clean_inputs_clear
- PASS clean_gate_decision_cleared
- PASS gate_has_digest
- PASS gate_echoes_frozen_structure
- PASS gate_carries_headline
- PASS incomplete_inputs_blocked
- PASS incomplete_gate_decision_blocked
- PASS invalid_field_blocked
- PASS digest_deterministic
- PASS digest_sensitive_to_inputs
- PASS digest_ignores_timestamp
- PASS loader_validate_assembled_present
- PASS page_self_contained
- PASS page_carries_headline
- PASS page_shows_frozen_structure
- PASS page_blocks_run_by_default
