# Cash-Flow Projection Set (CF track, owner directive 2026-07-03)

**Module:** `par_model_v2/projection/cashflow_projection_set.py`
**Basis:** deterministic central (owner-selected 2026-07-03) — best-estimate
decrements (governed base mortality/lapse tables), governed reserving
discount cap, Phase 10 educational HK declaration mechanics (UNSIGNED).
**Grids:** monthly 1..1,200 and yearly 1..100 (100 years).
**Entry point:** `build_cashflow_projection_set(model_inputs, out_dir)` →
`CASHFLOW_PROJECTION_SET.json` + 6 CSVs.

## Liability set — by product class × cash-flow type

Buckets (per month/year, per product class): `premium`, `expense`,
`death_guaranteed`, `death_non_guaranteed`, `maturity_guaranteed`,
`maturity_non_guaranteed`, `surrender_guaranteed`,
`surrender_non_guaranteed`, `cash_dividend`, plus `total_benefit` and
`net_cashflow`.

Guaranteed vs non-guaranteed convention (ASOP 56 §3.4, documented): sum
assured + bonuses vested AT the valuation date = guaranteed; future
declarations (future RB accrual, terminal bonus, cash dividends, equity
account excess over guarantee) = non-guaranteed. Surrender values split in
proportion to the guaranteed/non-guaranteed share of the projected benefit.

Product mechanics: HKRB (annual RB vesting @2.5%, TB 35% at maturity,
surrender 90% × asset-share proxy), HKCD (annual cash dividend @1.2% SA at
anniversary — six populated buckets: premium, expense, death gtd, maturity
gtd, surrender gtd, cash dividend), GMMB (central-growth account with SA
maturity floor; account excess non-guaranteed).

Premium timing, expense loadings (8% acq yr-0 / 4%+fixed renewal) and
decrements are IDENTICAL to `monthly_projection.project_liability_cashflows`
(regression-tested), so the set is consistent with the legacy engine.

## Asset set — by asset class

Per class: cash flows (`income`, `principal_repaid`, `reinvestment`,
`net_cashflow`) and balance (`market_value`). Bonds amortise over class
average maturity and reinvest in-class (level book; income = distributable
cash flow); equity pays dividends and compounds; cash rolls at the short
rate. Class mechanics are documented defaults keyed on the loader's asset
labels.

## Governance

Diagnostic cash-flow view — governed headline figures untouched; declaration
scales UNSIGNED pending owner approval; artifacts carry an inputs SHA-256
digest for reproducibility. Track: CF-1 DONE; CF-2 run integration; CF-3
GUI tab (roadmap §4.0c).
