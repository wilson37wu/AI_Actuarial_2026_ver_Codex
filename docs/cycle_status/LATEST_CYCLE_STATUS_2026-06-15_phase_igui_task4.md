# Cycle status — Phase IGUI Task 4 (assumptions, owner-gated)

**Agent:** Claude Cowork (`auto_actuarial_stochastic_model`)
**Cycle:** 2026-06-15 ~02:08–02:30 UTC
**Lock:** acquired `claude` (cycle_id 2026-06-15T02:08Z-6e8b), released at end.
**Result:** COMPLETE — Task 4 lands; Task 5 (ESG, stop-rule-bounded) set in_progress.

## What landed
- **`par_model_v2/viewer/igui_assumptions.py`** (stdlib only): declarative, grouped
  spec of the full valuation assumption set — mortality (base table + multiplier +
  annual improvement + floor), lapse/surrender (base + dynamic-lapse beta + ITM
  threshold), expenses (per-policy / %-premium / inflation), premiums (frequency +
  indexation), discount (flat rate **or** tenor/rate yield curve), bonus & crediting
  (declaration strategy + reversionary + terminal + smoothing), management-action
  rules (relief sigma/alpha + dynamic toggle), reinsurance (type + quota share +
  retention), and SCR confidence / benefit share — with fail-loud normalisation, a
  discount-curve normaliser, the `model_inputs.json` `{assumptions}` builder, a
  self-contained page, and `validate_task4_gate` (25 checks).
- **`scripts/load_user_inputs.py`**: additive `validate_assumptions_dict` (no openpyxl)
  — bounds/enums/bool/curve validation + read-only governed-frozen echo enforcement.
- **`scripts/run_gui.py`**: serves `GET /assumptions` + `POST /validate_assumptions`,
  `/save_assumptions`; merge preserves prior `{currency, run_settings, portfolio,
  balance_sheet}`; self-test extended. Prior pages/endpoints unchanged.
- **`tests/test_phase_igui_task4_assumptions.py`**: 21 new unittests (all green).
- Evidence + governance builders; `docs/validation/PHASE_IGUI_TASK4_ASSUMPTIONS.{json,md}`.

## Owner-gating (the binding property)
The governed/frozen dependence parameters — copula df **2.9451**, grouped-t
df_nonfin **37.866**, df_fin **8.506** — are a READ-ONLY echo. The builder always
re-attaches the governed values (a tampered echo is **neutralised**), and the loader
**rejects** any direct override. A GUI payload can never change a governed model
parameter; Sigma / df / margins stay bit-frozen.

## Gates
- Task-4 gate: **ok:true, 25/25 checks**.
- IGUI suites: Task-1 (24) + Task-2 (21) + Task-3 (24) + Task-4 (21) = **90 green**.
- `run_gui --self-test`: **ok:true** (0 network beyond same-origin localhost POSTs).
- `ui_app.html` **byte-unchanged** (sha256 `6dca35b3…0d7e65`).
- Governed headline SCR **39,975.654628199336** carried bit-for-bit.
- 0 new third-party runtime deps; 0 outbound network calls; 0 external refs.
- Governance: change records **103 → 104**, audit entries **131 → 132**, integrity OK.
- Phase 30 stop-rule honoured; MR-016/MR-017 owner decision not pre-empted.

## Next
Task 5 — ESG / economic-scenario inputs (stop-rule-bounded): surface curve/equity/FX/
credit-spread calibration anchors, scenario count/horizon, P vs Q metadata; loader-side
validator round-trip; no new copula-structure candidate; governed params stay read-only.
