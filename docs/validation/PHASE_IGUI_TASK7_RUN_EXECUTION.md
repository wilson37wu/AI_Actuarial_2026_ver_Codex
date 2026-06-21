# PHASE_IGUI_TASK7_RUN_EXECUTION (v1.0.0)

**Task:** Phase IGUI Task 7 - end-to-end run + results handoff (Phase IGUI MVP)  
**Domain:** D6_run_and_handoff  
**Generated:** 2026-06-15T05:23:09.163258+00:00

## Acceptance gate

- gate ok: **True** (19/19 checks)
- new third-party runtime deps: **0** (engine runs behind the run_model.py subprocess)
- outbound network calls: **0**
- localhost self-test ok: **True**
- RESULTS UI (ui_app.html) byte-unchanged: **True** (sha256 `6dca35b3520297263dd06086a1ced18cf831efb3fab6a6e8a9cde744500d7e65`)
- governed headline carried bit-for-bit: **39,975.654628199336**

## End-to-end flow

```
gated model_inputs.json (run_gate CLEARED, Task 6) -> scripts/run_model.py -> docs/validation/RUN_MODEL_AGGREGATION_REPORT.json + RUN_MODEL_SUMMARY.json -> offline RESULTS UI (ui_app.html) user_run contract
```

## Live smoke run (this build)

- ok: **True** (stage `run_complete`)
- nested SCR (smoke): `76988.8069665521`
- selected copula (smoke): `gaussian`
- reproducibility digest carried into output: `sha256:64682554635eda0561a118a57d8b8600e02fb4c2ca8f67e145ce9c97773efa81`
- DISCLOSURE: a smoke run is a fast diagnostic, **not** a governed capital figure

## Gate-guard

A run is **refused** (nothing spawned) unless the Task-6 run gate is **CLEARED** and its reproducibility digest re-verifies against the live inputs. A missing / blocked / tampered gate writes no artifact.

## Stop-rule (Phase 30) + owner-gating

- dependence copula structure echoed read-only as **`single_t_grouped_FROZEN`** (never altered here)
- MR-016/MR-017 dependence decision remains entirely with the owner

## New localhost runner routes

- `GET /run-execution`
- `POST /execute`

## Gate checks

- PASS execution_module_present
- PASS run_model_present
- PASS execution_module_stdlib_only
- PASS run_gui_serves_run_execution
- PASS run_gui_has_execute_endpoint
- PASS run_gui_still_localhost
- PASS run_gui_prior_pages_intact
- PASS ui_app_byte_unchanged
- PASS run_page_self_contained
- PASS run_page_carries_headline
- PASS run_page_blocks_run_by_default
- PASS missing_gate_refused
- PASS cleared_gate_accepted
- PASS tampered_inputs_refused
- PASS live_run_ok
- PASS live_run_headline
- PASS digest_carried_into_output
- PASS handoff_user_run_shaped
- PASS blocked_gate_runs_nothing
