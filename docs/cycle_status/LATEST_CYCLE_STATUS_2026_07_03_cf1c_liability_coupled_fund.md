# Cycle Status — 2026-07-03 — CF-1c Liability-Coupled Asset Fund (Owner Correction)

**Item:** Owner correction: "asset balance projection is same every year
which is certainly wrong as it should grow and run off along with
liability."
**Outcome:** DONE

## Root cause
CF-1 projected each asset class as an isolated level book (income paid out,
principal rolled in-class) with no liability linkage — balances were flat by
construction.

## Fix
`project_asset_set(balance_sheet, net_liability_cf)`: monthly fund
recursion — investment income retained/reinvested, equity capital growth,
liability net CF invested (+) or funded by sales (−), constant-mix monthly
rebalance to opening weights, zero-floor with shortfall column.
`build_cashflow_projection_set` feeds the liability set's total net CF into
the fund. New totals: `asset_shortfall`, `book_runoff_month`.

## Verification
- Default book trajectory: 259M (y1) → peak 524M (y14) → −34.5M GMMB
  maturity (y15) → −146.6M endowment maturities (y20) → residual surplus
  compounds thereafter (documented).
- Tests 22/22 GREEN: per-class accounting identity (MV[m] = MV[m−1] +
  income + growth + net_investment, rtol 1e-9), constant weights,
  balances-not-level, exhaustion floors at zero with shortfall,
  standalone view, bad-input refusals; wide-format suite unchanged.

Next queued: CF-2 run integration, CF-3 GUI tab.
