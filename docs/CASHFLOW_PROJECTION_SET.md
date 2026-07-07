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

## Asset set — by asset class (liability-coupled fund)

Owner correction 2026-07-03: the asset fund is COUPLED to the liability
book. Monthly recursion: investment income (coupons/dividends/interest) is
retained and reinvested; equity additionally compounds at the capital-growth
rate; the month's net liability cash flow (premiums − expenses − benefits)
is invested when positive and funded by asset sales when negative; the fund
rebalances monthly to the opening balance-sheet class weights
(constant-mix). Balances therefore GROW during premium accumulation and RUN
OFF at maturities/claims; any post-runoff residual is surplus compounding at
investment return (`totals.book_runoff_month` marks where the book ends).
If outflows exhaust the fund, balances floor at zero and the unfunded amount
is reported (`totals.asset_shortfall`).

Per class: cash flows (`investment_income`, `capital_growth`,
`net_investment` purchase+/sale−, `net_cashflow`) and balance
(`market_value`). Accounting identity regression-tested:
MV[m] = MV[m−1] + income + growth + net_investment.

## Output orientation (owner request 2026-07-03)

CSVs carry ONLY the time dimension in rows (`month` or `year`); classes run
horizontally. Multi-measure tables flatten headers to `<class>__<measure>`
(e.g. `HKCD_PAR_2026__cash_dividend`); single-measure tables (balances) use
the plain class label as the header. Tidy (long) frames remain available
in-process via `result["frames"]` and `to_wide()` is the documented pivot.

## Governance

Diagnostic cash-flow view — governed headline figures untouched; declaration
scales UNSIGNED pending owner approval; artifacts carry an inputs SHA-256
digest for reproducibility. Track: CF-1 DONE; CF-2 run integration DONE
(2026-07-08); CF-3 GUI tab DONE (roadmap §4.0c — track COMPLETE).

## CF-2 — per-run persistence (2026-07-08)

Every successful engine run now persists its cash-flow set:
`execute_run` (step 6b, best-effort — never fails the governed run) calls
`igui_cashflows.attach_cashflow_set_for_run`, which writes the CF-1 set to
`run_output/cashflow_set_runs/<digest12>/cashflow_set/` keyed by the CF-1
inputs digest. Identical-input runs share one copy (digest-cache hit);
later runs never overwrite an earlier run's set. The digest key is the
stale-set guard, and `load_run_cashflow_set` re-verifies schema + digest
before serving. Surfaces: attachment block on the GUI-1 job record,
`cashflow_set` availability + digest in the run registry, a per-run `CFs`
button on /history, compare notes (same/differing/missing CF sets), and
`/cashflows?run=<id>` → `/cashflow-data?run=<id>` showing EXACTLY the
set persisted with that run (run-provenance banner shown). Tests:
`tests/test_cf2_run_cashflow_attachment.py`.

## PC-2 — extended families + per-product overrides (2026-07-08)

The liability set now projects six product families. New: `WL_PAR_2026`
(whole-life par; RB mechanics, endowment-at-limit convention), `TERM_2026`
(term assurance; death benefit only) and `ANNUITY_2026` (deferred annuity;
guaranteed payout). A TENTH liability bucket `annuity_guaranteed` carries
the annuity payments; the `_guaranteed` suffix auto-classifies it as
guaranteed in the CF-3 charts, the GD-2 drilldown and all rollups (JSON
`liability_buckets` lists the live bucket set; CSV wide headers gain the
column additively). Per-product expense/decrement overrides
(`portfolio_construction.OVERRIDE_PARAMS`) thread through `_decrements` /
`_premium_expense` / `_asset_share_proxy` consistently for ALL families;
absent keys reproduce the governed defaults bit-identically
(regression-tested). Tests: `tests/test_pc2_mechanic_families.py`.
