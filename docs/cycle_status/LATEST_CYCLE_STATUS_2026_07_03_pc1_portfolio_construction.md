# Cycle Status — 2026-07-03 — PC-1 Flexible Portfolio Construction

**Item:** Owner directive: construct asset inputs (type, mix, SAA) and
liability inputs (product templates, e.g. short/long-term par) flexibly,
integrated in the GUI.
**Outcome:** DONE

## What landed
- `par_model_v2/projection/portfolio_construction.py`: asset-strategy and
  product-catalogue schemas + fail-loud validators (weights sum to 1,
  kind-specific parameter bounds, duplicate guards, term ranges, CD/vested-
  bonus rule, illiquid-share engine rule), `derive_balance_sheet` (incl.
  run-engine fields backing_asset_mv / illiquid_share), `resolve_portfolio`
  (catalogue -> family + mechanics), `asset_mechanics_from_strategy`.
- CF engine: rows carry catalogue mechanics (CD rate, RB rate, TB, SV%);
  output classes are per catalogue product; asset fund mechanics/weights
  come from the SAA. Legacy inputs unchanged (regression suites green).
- `/portfolio` GUI page (three editable tables, live weight sum, add/remove
  rows) + `/portfolio-defaults`, `/validate_construction`,
  `/save_construction` endpoints; save merge-writes model_inputs.json,
  re-validates through the governed loader, and resets the run gate.
- Page registered in the node JS-syntax guard.

## Verification
- 17 new tests; 130 GREEN across PC/CF/GUI suites (2 pre-existing
  owner-gated sha-baseline failures confirmed identical on unmodified main).
- LIVE e2e: save_construction (4 products, 5-class SAA) → Save & RUN
  (gate cleared, engine smoke succeeded, nested_scr rendered) →
  /cashflow-data splits liabilities by PAR_CD_SHORT / PAR_CD_LONG /
  PAR_RB_LONG / GMMB_STD.
- Mid-cycle fix: derived balance sheet initially lacked backing_asset_mv /
  illiquid_share required by the liquidity-exposure engine — added, plus a
  validation rule that at least one weighted SAA class is illiquid.

Next queued: PC-2 (new mechanic families), CF-2 (attach CF set to runs).
