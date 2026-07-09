# Cycle Status — 2026-07-09 — #8 Path-Wise vs Current TVOG Bridge (RB + TB)

**Agent:** Claude Cowork (scheduled `actuarial-model-daily-improvement`)
**Item:** §4.1 #8 — stochastic bonus declaration, path-wise RB/TB (Limitation #4)
**Outcome:** DONE — pushed to `main`, lock released. Completes §4.1 #1–#8.

## What was built

Carries the Phase-25 path-wise **reversionary-bonus** declaration pre-study
(an SCR/VaR study in `pathwise_bonus_dynamics.py`) into a **TVOG** framing and
**extends it to the terminal bonus (TB)**, delivering the roadmap DoD:
a *path-wise TVOG vs current TVOG bridge, quantified and documented*.

- `par_model_v2/projection/pathwise_tvog_bridge.py` — the bridge engine.
  Risk-neutral (Q) representative participating fund; assets = GBM with
  drift = `rf`, so `E^Q[disc·A_T] = A_0` (Q-martingale, verified as a gate).
  Four declaration bases on COMMON random numbers: `without` / **`horizon`**
  (the CURRENT governed convention — RB/TB cut frozen at `CR_0`, Phase 24
  Task 3) / **`pathwise`** (RB re-declared each inner step on `CR_t`, TB
  re-declared at maturity on terminal `CR_T`) / `max_cut` (PRE floor).
  Two costs per basis: **hard guarantee** `E^Q[disc·max(L_T^RB − A_T, 0)]`
  and **declared benefit** `E^Q[disc·max(L_T^RB·(1+TB_decl) − A_T, 0)]`.
  The current→path-wise bridge is an EXACT additive decomposition
  (`Δ_total = Δ_healthy_nodes + Δ_stressed_nodes`, partition by `CR_0` vs
  the rule trigger). Reuses the governed `ManagementActionRule` and the
  Phase-25 `retained_bonus_rate`.
- `scripts/build_pathwise_tvog_bridge.py` → `docs/validation/PATHWISE_TVOG_BRIDGE.json`
  (schema `pathwise-tvog-bridge-1.0`, stable `content_digest 2a3963f6…`,
  UNSIGNED banner, use-restriction block).
- `docs/PATHWISE_TVOG_BRIDGE_CARD.md` — the evidence card; pointers added to
  `docs/PATHWISE_DECLARATION_CARD.md` and `docs/MODEL_STABILITY_AND_LIMITATIONS.md`
  (new §3.9).

## Result (default fund; TVOG per 100 initial liability)

| Measure | Current (horizon) | Path-wise | Δ total | Δ % of current |
|---|---:|---:|---:|---:|
| Hard guarantee | 26.009 | 23.932 | −2.077 | **−7.99%** |
| Declared benefit (incl. TB) | 30.191 | 26.753 | −3.439 | **−11.39%** |

Path-wise RB/TB declaration **reduces** the mean TVOG (it cuts over-declared
bonuses stranded on deteriorating paths). The declared-benefit reduction
exceeds the RB-only guarantee reduction — the TB extension contributes the
−3.4pp gap. Martingale ratio 1.0011 (PASS); elementwise bounds PASS; bridge
identity residual < 1e-9. Disclosed: this MEAN-cost fall mirrors the Phase-25
path-wise **SCR** (a 99.5% tail) *rising* — complementary, not conflicting.

## Verification

- NEW `tests/test_pathwise_tvog_bridge.py` — **26/26 GREEN** (unittest,
  numpy-only): config validation, martingale + discount gates, common-random
  bounds, exact additive bridge identity (both measures), current→path-wise
  reconciliation, basis mean ordering, TB-extension magnitude, determinism
  (seed → digest), JSON/markdown serialisation, use-restriction disclosure.
- Regression GREEN via the minimal pytest shim —
  `test_phase23_task3_management_actions` 29/29 +
  `test_phase25_task1_design_note` 29/29 (58); `test_dynamic_lapse_elasticity_tvog`
  21/21 (unittest). `test_phase25_task2_pathwise_declaration` is PRE-EXISTING
  scipy-blocked (transitive `from scipy import stats`); scipy + pytest are
  unavailable in the network-restricted sandbox.

## Governance

Purely additive DIAGNOSTIC. Governed portfolio TVOG / aggregation headline
UNTOUCHED (the module imports no `run_model`). **Owner-gated follow-on:**
re-baselining the governed headline onto a path-wise RB/TB declaration basis
(full cutover into the production nested TVOG engine). EDUCATIONAL / UNSIGNED —
placeholder fund + rule parameters; APS X2 review pending.

**Next OPEN:** §4.1 #9 — independent-review readiness pack (APS X2 / TAS M
§3.6.5 evidence bundle).
