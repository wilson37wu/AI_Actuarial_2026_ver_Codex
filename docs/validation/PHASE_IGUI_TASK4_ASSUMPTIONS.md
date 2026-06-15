# PHASE_IGUI_TASK4_ASSUMPTIONS (v1.0.0)

**Task:** Phase IGUI Task 4 - assumptions (owner-gated)  
**Domain:** D3_assumptions  
**Generated:** 2026-06-15T02:20:08.279263+00:00

## Acceptance gate

- gate ok: **True** (25 checks)
- new third-party runtime deps: **0**
- outbound network calls: **0**
- localhost self-test ok: **True**
- RESULTS UI (ui_app.html) byte-unchanged: **True** (sha256 `6dca35b3520297263dd06086a1ced18cf831efb3fab6a6e8a9cde744500d7e65`)
- governed headline carried bit-for-bit: **39,975.654628199336**

## Owner-gating (governed/frozen, read-only)

- `copula_df_single_t` = 2.9451 (read-only echo; override rejected by loader)
- `grouped_t_df_nonfin` = 37.866 (read-only echo; override rejected by loader)
- `grouped_t_df_fin` = 8.506 (read-only echo; override rejected by loader)

## Assumption groups surfaced

- Mortality
- Lapse & Surrender
- Expenses
- Premiums
- Discount / Yield
- Bonus & Crediting
- Management Action
- Reinsurance
- Risk

## New localhost runner routes

- `GET /assumptions`
- `POST /validate_assumptions`
- `POST /save_assumptions`

## Gate checks

- PASS assumptions_module_present
- PASS run_gui_present
- PASS loader_present
- PASS assumptions_module_stdlib_only
- PASS run_gui_serves_assumptions
- PASS run_gui_has_assumption_endpoints
- PASS run_gui_still_localhost
- PASS run_gui_prior_pages_intact
- PASS loader_has_assumptions_validator
- PASS schema_version_lockstep
- PASS defaults_normalise_clean
- PASS fragment_has_assumptions
- PASS fragment_passes_loader_validator
- PASS frozen_echo_is_governed
- PASS frozen_override_rejected
- PASS out_of_bounds_caught
- PASS bad_choice_rejected
- PASS bad_curve_tenor_rejected
- PASS default_curve_ok
- PASS page_self_contained
- PASS page_carries_headline
- PASS page_shows_frozen_readonly
- PASS page_groups_present
- PASS ui_app_byte_unchanged
- PASS no_external_refs_in_results_ui
