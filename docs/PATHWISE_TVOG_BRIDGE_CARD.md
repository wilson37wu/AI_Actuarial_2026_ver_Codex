# Path-Wise vs Current (Horizon-Level) TVOG Bridge — RB + TB Declaration

**Roadmap:** §4.1 item #8 (Limitation #4 — stochastic bonus declaration).
**Status:** DONE — bridge quantified and documented. **EDUCATIONAL / UNSIGNED.**
**Content digest:** `2a3963f6…` (stable, seed 42; ex-timestamp).

## What this delivers

The roadmap item asks to *"make RB/TB declaration fully path-wise (extend
PATHWISE_DECLARATION work into the TVOG main path)"* with a *"path-wise TVOG
vs current TVOG bridge quantified and documented."* This cycle:

1. Carries the Phase 25 path-wise **reversionary-bonus (RB)** declaration work
   (`pathwise_bonus_dynamics.py`, an SCR/VaR pre-study) into a **TVOG** framing.
2. **Extends it to the terminal bonus (TB)** — TB is now re-declared at
   maturity on the terminal coverage ratio, so *both* RB and TB declaration
   timing feed the cost.
3. Produces the **bridge**: an exact, additive reconciliation from the
   **current** (horizon-level) TVOG to the **path-wise** TVOG.

Module `par_model_v2/projection/pathwise_tvog_bridge.py`; evidence
`docs/validation/PATHWISE_TVOG_BRIDGE.json`; builder
`scripts/build_pathwise_tvog_bridge.py`; tests
`tests/test_pathwise_tvog_bridge.py` (26/26 GREEN).

## Method

Single representative participating fund, **risk-neutral (Q)**: assets follow a
GBM with drift = risk-free `rf`, so `E^Q[disc·A_T] = A_0` — verified as a gate
(**martingale ratio 1.0011, PASS**). The liability accrues the guaranteed rate
plus the *declared* RB each step; at maturity a *declared* TB uplifts the
benefit. Two shortfall costs are valued per basis:

- **Hard guarantee** `E^Q[disc·max(L_T^RB − A_T, 0)]` — guaranteed accrual +
  *vested* RB; RB declaration flows in.
- **Declared benefit** `E^Q[disc·max(L_T^RB·(1+TB_decl) − A_T, 0)]` —
  guaranteed accrual + declared RB + *declared* TB; TB declaration timing bites.

Four bases share common random numbers: `without` (full bonus), **`horizon`**
(the CURRENT convention — cut frozen at `CR_0`), **`pathwise`** (RB re-declared
each step; TB re-declared at maturity), `max_cut` (PRE floor). Elementwise
`max_cut ≤ {horizon, pathwise} ≤ without` holds per node (**bounds gate PASS**).

## Result (default fund; TVOG per 100 initial liability)

| Basis | TVOG guarantee | TVOG declared |
|---|---:|---:|
| without | 27.845 | 32.794 |
| **horizon (current)** | **26.009** | **30.191** |
| **pathwise** | **23.932** | **26.753** |
| max_cut | 22.166 | 24.648 |

**Bridge (exact additive; partitioned by `CR_0` vs trigger 1.10; healthy-node
share 51.6%):**

| Measure | Current (horizon) | Δ healthy nodes | Δ stressed nodes | Path-wise | Δ total | Δ % of current |
|---|---:|---:|---:|---:|---:|---:|
| Hard guarantee | 26.009 | −1.419 | −0.658 | 23.932 | **−2.077** | **−7.99%** |
| Declared benefit | 30.191 | −2.358 | −1.080 | 26.753 | **−3.439** | **−11.39%** |

Identity `Δ_total = Δ_healthy + Δ_stressed` holds to < 1e-9 (residual 0 for the
declared leg, −3e-15 for the guarantee leg).

## Reading the bridge

- **Moving to path-wise RB/TB declaration REDUCES the TVOG** by ~8% (hard
  guarantee) to ~11% (declared benefit). The frozen `horizon` basis leaves
  bonuses *over-declared* on paths that deteriorate after `t=0`; the path-wise
  basis cuts them, lowering the funded shortfall.
- **The TB extension is material:** the declared-benefit reduction (−11.4%)
  exceeds the RB-only guarantee reduction (−8.0%) — the extra −3.4pp is the
  terminal-bonus declaration responsiveness the item asked for.
- **Both régimes contribute:** ~68% of the reduction comes from *healthy*
  starting nodes (where the horizon basis never cuts, so path-wise cutting is
  pure added responsiveness) and ~32% from *stressed* nodes.
- Path-wise cut share 89.9%; cut-then-restore share 66.5%.

## Relation to the Phase 25 SCR pre-study (disclosed)

The Phase 25 pre-study reported path-wise **SCR** (a 99.5% *tail*) *above* the
horizon SCR — restoration lifts the tail. A **TVOG** is a risk-neutral *mean*
cost, and path-wise re-declaration trims over-declared bonuses on the average
deteriorating path, so the **mean-cost bridge moves opposite to the tail**.
The two views are complementary, not conflicting: path-wise declaration lowers
the expected cost of guarantees while (per the pre-study) fattening the extreme
tail via bonus restoration on late-recovering paths.

## Scope / governance

- **Governed headline UNTOUCHED.** This is an additive representative-fund
  diagnostic. The governed portfolio TVOG / aggregation figures are not
  recomputed and not changed.
- **Owner-gated follow-on:** re-baselining the governed headline onto a
  path-wise RB/TB declaration basis (the full cutover into the production
  nested TVOG engine).
- **EDUCATIONAL / UNSIGNED:** placeholder fund + `ManagementActionRule`
  parameters; automation-driven sign-off; APS X2 review pending.

*Standards: SOA ASOP 56 §3.1, ASOP 7 §3.3; IA TAS M §3.2, §3.6; IFoA MCEV
Principles §7. See `PATHWISE_DECLARATION_CARD.md` (Phase 25 SCR basis) and
`PATHWISE_BONUS_DECLARATION_DESIGN_CARD.md`.*
