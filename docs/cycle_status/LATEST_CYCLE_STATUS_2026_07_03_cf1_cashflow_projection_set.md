# Cycle Status — 2026-07-03 — CF-1 Cash-Flow Projection Set

**Agent:** Claude Cowork (owner-triggered interactive cycle)
**Item:** CF-1 (owner directive 2026-07-03): new output set — liability CFs
by product class × type (benefit split gtd/non-gtd across
death/surrender/maturity + cash dividend), asset CFs + balances by class,
monthly + yearly to 100 years. Owner choices: deterministic central basis;
CD product class via Phase 10 mechanics; JSON+CSV now, GUI tab next.
**Outcome:** DONE

## What landed
- `par_model_v2/projection/cashflow_projection_set.py` (engine, see
  docs/CASHFLOW_PROJECTION_SET.md)
- `tests/test_cf1_cashflow_projection_set.py` — 16 tests: legacy-engine
  consistency (premium/expense arrays match project_liability_cashflows to
  1e-10), CD ≥6 populated buckets, RB gtd/non-gtd split, GMMB floor,
  net-cashflow identity, non-negativity, yearly=Σmonthly, balance=year-end,
  artifacts written + re-parse, digest deterministic/input-sensitive.
- Roadmap §4.0c CF track registered (CF-1 DONE, CF-2 run integration OPEN,
  CF-3 GUI tab OPEN); docs card added.

## Verification
16/16 new tests GREEN; 98 legacy projection/HK-participating tests GREEN;
magnitude sanity-check on the default book plausible (CD dividends ≈
policies × SA × 1.2% × anniversaries × in-force decay).

## Next queued
CF-2 — attach the set to every GUI run (run_output + registry, digest
guard), then CF-3 GUI tab.
