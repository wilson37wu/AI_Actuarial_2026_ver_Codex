# PHASE_IGUI_TASK2_RUN_CONTROLS (v1.0.0)

**Task:** Phase IGUI Task 2 - run controls + stdlib local-runner scaffolding  
**Architecture:** L2_stdlib_local_runner (stdlib http.server, 127.0.0.1, offline)  
**Generated:** 2026-06-15T00:20:36.983349+00:00

## Acceptance gate

- gate ok: **True** (21 checks)
- new third-party runtime deps: **0**
- outbound network calls: **0**
- localhost self-test ok: **True**
- RESULTS UI (ui_app.html) byte-unchanged: **True** (sha256 `6dca35b3520297263dd06086a1ced18cf831efb3fab6a6e8a9cde744500d7e65`)
- governed headline carried bit-for-bit: **39,975.654628199336**

### Gate checks

- PASS run_gui_present
- PASS core_module_present
- PASS loader_present
- PASS orchestrator_present
- PASS run_gui_stdlib_only
- PASS core_module_stdlib_only
- PASS run_gui_binds_localhost
- PASS loader_has_dict_validator
- PASS schema_version_lockstep
- PASS loader_scale_enum_lockstep
- PASS loader_thousands_enum_lockstep
- PASS defaults_normalise_clean
- PASS digest_deterministic
- PASS model_inputs_has_run_settings
- PASS form_carries_headline
- PASS form_has_all_fields
- PASS form_zero_external_refs
- PASS ui_app_byte_unchanged
- PASS live_zero_external_refs
- PASS governance_risk_register_frozen
- PASS governance_change_records_floor

## Run controls collected (D1_run_controls)

valuation_date, currency_code, currency_symbol, scale, thousands, market_label, n_outer, n_inner, n_sim, bootstrap_replicates, horizon_months, step_months, seed, output_label

## Example model_inputs.json fragment (loader-validated, errors=0)

```json
{
 "schema_version": "1.0.0",
 "generated_at": "1970-01-01T00:00:00+00:00",
 "source": "igui_run_gui (Phase IGUI Task 2 run controls)",
 "currency": {
  "code": "HKD",
  "symbol": "HK$",
  "scale": "units",
  "thousands": "comma",
  "market_label": "HK_2026_baseline",
  "valuation_date": "2026-06-30"
 },
 "run_settings": {
  "n_outer": 160,
  "n_inner": 24,
  "n_sim": 200000,
  "bootstrap_replicates": 1000,
  "horizon_months": 12,
  "step_months": 1,
  "seed": 42,
  "output_label": "igui_run",
  "reproducibility_digest": "sha256:b4947eed5ac052754f66bc74ad1b1766c8d2c178c039a7b6a56ddefc4d286f7a"
 }
}
```

Validation through `scripts/load_user_inputs.validate_run_controls_dict` (no openpyxl needed) returned 0 issue(s); a payload must validate clean before the runner writes model_inputs.json. The Excel template path is unchanged. NO model parameter change; the Phase 30 stop-rule is honoured and the MR-016/MR-017 owner decision is not pre-empted.
