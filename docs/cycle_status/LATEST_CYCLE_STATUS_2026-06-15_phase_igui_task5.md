# Cycle status — Phase IGUI Task 5 (ESG / economic-scenario input domain)

**Date:** 2026-06-15 (Claude Cowork 06:00 UTC window)
**Owner/agent:** ClaudeCowork_AutoDev (lock held + released this cycle)
**Task:** Phase IGUI **Task 5 — ESG / economic-scenario inputs** (`D4_esg_economic`), stop-rule-bounded & owner-gated
**Status:** ✅ COMPLETE

## What landed
- **ESG core** `par_model_v2/viewer/igui_esg.py` (stdlib only, 596 lines): declarative spec of the *settable* ESG-provenance inputs — Market Data (valuation date, yield-curve source, equity-index ref), Scenario Set (label, documented scenario count) and Calibration Targets (10y rate, equity vol, credit spread, basis note) — with fail-loud per-field normalisation (incl. an ISO-date check) and a builder to the `model_inputs.json` `{esg}` sub-schema.
- **Stop-rule + owner-gating:** the governed ESG calibration (G2++/HW short-rate, equity GBM, credit-spread & liquidity-premium processes) and the **FROZEN** dependence structure (copula df 2.9451, grouped-t df 37.866/8.506, structure `single_t_grouped_FROZEN`) are a **READ-ONLY** echo. `esg_to_model_inputs` always re-attaches the governed values; the loader rejects any override; the copula structure is pinned and any other value — in the echo **or** smuggled as a top-level `esg` key — is rejected (**Phase 30 stop-rule guard**).
- **Runner** `scripts/run_gui.py`: serves a self-contained `/esg` page (grouped settable inputs + read-only governed basis + on-page stop-rule banner; zero external refs) and `POST /validate_esg`, `/save_esg`; merge preserves Tasks 2–4 `{currency, run_settings, portfolio, balance_sheet, assumptions}`.
- **Loader** `scripts/load_user_inputs.py`: additive `validate_esg_dict` (no openpyxl); Excel path unchanged.

## Evidence
- Task-5 gate `validate_task5_gate` **ok=True, 27/27 checks**.
- **24 new unittests** green (`tests/test_phase_igui_task5_esg.py`); IGUI Task-1 (24) + Task-2 (21) + Task-3 (24) + Task-4 (21) suites green → **114 IGUI tests total**.
- `run_gui --self-test` ok=True (localhost round-trip incl. override-neutralisation).
- `ui_app.html` **byte-unchanged** (sha256 `6dca35b3…0d7e65`); 0 external refs across the 3 gated HTML artifacts.
- Evidence pack: `docs/validation/PHASE_IGUI_TASK5_ESG.{json,md}`; self-test record `scripts/_phase_igui_task5_selftests.json`.

## Governance
- ChangeRecord `b2b6b4f8f5e04485937a0bdcc66444e8` opened **OWNER_REVIEW**; records 104→105, audit 132→133; `verify_all` True.
- Contract **1.21.0 unchanged**; 0 new third-party runtime deps; 0 outbound network calls.
- MR-016/MR-017 dependence decision remains **PENDING with the owner**; Phase 30 stop-rule honoured.

## Next
- **Task 6 — validation surfacing + governance gating before run** (`D5_validation_gating`): block the Run action until `model_inputs.json` is clean across all domains; record a governance gate + reproducibility digest per run.
