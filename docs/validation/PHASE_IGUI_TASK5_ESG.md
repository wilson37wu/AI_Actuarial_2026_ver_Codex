# PHASE_IGUI_TASK5_ESG (v1.0.0)

**Task:** Phase IGUI Task 5 - ESG / economic scenarios (stop-rule-bounded, owner-gated)  
**Domain:** D4_esg_economic  
**Generated:** 2026-06-15T03:17:07.799914+00:00

## Acceptance gate

- gate ok: **True** (27 checks)
- new third-party runtime deps: **0**
- outbound network calls: **0**
- localhost self-test ok: **True**
- RESULTS UI (ui_app.html) byte-unchanged: **True** (sha256 `6dca35b3520297263dd06086a1ced18cf831efb3fab6a6e8a9cde744500d7e65`)
- governed headline carried bit-for-bit: **39,975.654628199336**

## Stop-rule (Phase 30) + owner-gating (read-only echo)

- dependence copula structure pinned to **`single_t_grouped_FROZEN`** (loader rejects any other)
- `rate_model` = G2++ two-factor / HW one-factor (educational governed) (read-only echo; override rejected by loader)
- `rate.mean_reversion_x` = 0.1 (read-only echo; override rejected by loader)
- `rate.mean_reversion_y` = 0.35 (read-only echo; override rejected by loader)
- `rate.vol_x` = 0.01 (read-only echo; override rejected by loader)
- `rate.vol_y` = 0.006 (read-only echo; override rejected by loader)
- `rate.long_run_rate_p` = 0.025 (read-only echo; override rejected by loader)
- `equity.equity_vol` = 0.22 (read-only echo; override rejected by loader)
- `equity.dividend_yield` = 0.025 (read-only echo; override rejected by loader)
- `equity.equity_risk_premium` = 0.045 (read-only echo; override rejected by loader)
- `equity.rate_equity_correlation` = -0.15 (read-only echo; override rejected by loader)
- `credit.mean_reversion_speed` = 0.3 (read-only echo; override rejected by loader)
- `credit.long_run_spread_p` = 0.015 (read-only echo; override rejected by loader)
- `liquidity.mean_reversion_speed` = 0.6 (read-only echo; override rejected by loader)
- `liquidity.long_run_premium_p` = 0.006 (read-only echo; override rejected by loader)
- `dependence.copula_structure` = single_t_grouped_FROZEN (read-only echo; override rejected by loader)
- `dependence.copula_df_single_t` = 2.9451 (read-only echo; override rejected by loader)
- `dependence.grouped_t_df_nonfin` = 37.866 (read-only echo; override rejected by loader)
- `dependence.grouped_t_df_fin` = 8.506 (read-only echo; override rejected by loader)

## Settable provenance groups surfaced

- Market Data
- Scenario Set
- Calibration Targets

## New localhost runner routes

- `GET /esg`
- `POST /validate_esg`
- `POST /save_esg`

## Gate checks

- PASS esg_module_present
- PASS run_gui_present
- PASS loader_present
- PASS esg_module_stdlib_only
- PASS run_gui_serves_esg
- PASS run_gui_has_esg_endpoints
- PASS run_gui_still_localhost
- PASS run_gui_prior_pages_intact
- PASS loader_has_esg_validator
- PASS schema_version_lockstep
- PASS defaults_normalise_clean
- PASS fragment_has_esg
- PASS fragment_passes_loader_validator
- PASS loader_frozen_lockstep
- PASS frozen_echo_is_governed
- PASS frozen_override_rejected
- PASS new_copula_structure_rejected
- PASS stop_rule_guard_blocks_smuggled_structure
- PASS out_of_bounds_caught
- PASS bad_date_rejected
- PASS page_self_contained
- PASS page_carries_headline
- PASS page_shows_frozen_readonly
- PASS page_shows_stop_rule
- PASS page_groups_present
- PASS ui_app_byte_unchanged
- PASS no_external_refs_in_results_ui
