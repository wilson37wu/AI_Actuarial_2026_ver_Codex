# Six-Driver OOS Proxy-Validation Card (FX included)

**Phase:** 21 - FX + Liquidity Drivers and Six/Seven-Driver Economic Capital (Task 2)

**Status:** EDUCATIONAL. Verdict **PARTIAL**. Production sign-off withheld pending the
liquidity driver (Task 3), re-aggregation + tail diagnostics (Task 4), UI propagation
(Task 5), credentialled calibration, and independent (APS X2) review.

## What was validated

The six-driver (G2++ rate, equity, credit spread, dynamic lapse, mortality trend,
FX translation) LSMC capital surface, out-of-sample against heavy nested truth on an
independent disjoint-seed hold-out, with basis selection by OOS error over a
(degree, max_interaction_order) grid swept in TWO fx modes:

* **analytic** -- the CIP-exact FX leg fx_l(X_H) = notional * (1 - X_H/X0) enters as a
  known offset (control variate); the polynomial spans the five stochastic-valuation
  drivers (production-sensible structure exploitation).
* **learned** -- a fully hexavariate basis must estimate the FX axis from noisy
  single-path fitting targets (standard error ~ sigma_noise / (sqrt(n_fit) * sd(X_H))).

## Selected surface

fx_mode = **analytic**, degree 1, max_interaction_order 3 (6 terms);
OOS R^2 = 0.9498; VaR rel err = 5.99%; overfit gap = -0.0018;
FX-axis slope recovered within 0.00% of the CIP-exact theoretical slope.

## Honest findings

* FX-mode head-to-head (best OOS RMSE): analytic offset 4686.04 vs learned hexavariate 4757.11 — the control-variate design dominates the fully-learned FX axis at this educational scale.
* Proxy and nested capital are evaluated on the SAME eval outer states (seed 141), so the comparison isolates pure surface error; the nested benchmark uses 96 heavy inner Q-paths per state.
* FX-axis recovery: surface partial-FX slope -3846.15 vs CIP-exact theoretical -3846.15 (rel err 0.00%).
* verdict drivers: OOS R^2 0.9498 < 0.95

## Limitations / use restrictions

* Basis selection minimises OOS error over the swept (degree, max_interaction_order) grid only; the true optimum may lie outside the grid. Valid only over the fitted 6-D interquartile state region — extrapolation is unsupported.
* The FX leg is a single linear translation exposure with CIP-exact conditioning — real books carry optioned / partially hedged FX with smile and regime (peg) dynamics outside this surface. Liquidity risk remains outside the proxy (Phase 21 Task 3). The five-driver inner nest is the governed HW1F nest conditioned at the realised G2++ r_H (Phase 20 residual). Parameters are illustrative placeholders; capital magnitudes are NOT calibrated.

## Standards

* SOA ASOP 7 section 3.3
* SOA ASOP 25 section 3.3
* SOA ASOP 56 section 3.1.3/3.5
* IA TAS M section 3.2/3.6
* IFoA proxy-modelling working party
* Longstaff & Schwartz (2001)
* Solvency II Delegated Regulation Article 188/234

---

## Phase 22 Task 1 update (2026-06-07) — REMEDIATED, verdict PASS

The Phase 21 Task 2 honest PARTIAL (OOS R² 0.9498 < 0.95) is **CLEARED** by the recorded
remediation options, with NO gate-shopping (same disjoint-seed hold-out, selection still by
OOS RMSE, and a STRICTER Phase 22 gate adding ES + SCR rel err ≤ 10% to the VaR criterion):

1. **De-noised fitting targets** — 8 inner Q-paths/state (was 1), identical SeedSequence
   protocol (n_inner=1 reproduces Phase 21 bit-for-bit; regression-tested).
2. **4× training states** — n_fit 500 → 2,000 via the staged slice-stable CRN protocol.
3. **De-noised eval benchmark** — nested_n_inner 96 → 256.
4. **Targeted rate/equity-curvature candidate** (deg-1 all drivers + r², S², r·S; 9 terms,
   analytic FX offset) competed in the same selection — it clears the gate itself
   (OOS R² 0.9930) but LOSES by OOS RMSE to the engine's (analytic, deg 3, max_int 2) surface.

**Final selected surface:** fx_mode=analytic, degree 3, max_interaction_order 2 (46 terms);
OOS R² **0.9985**; OOS RMSE 816 (was 4,686); VaR/ES/SCR rel err **0.50% / 0.19% / 1.25%**
(SCR was 15.97%); overfit gap −0.0008; FX-axis slope recovered exactly (0.00%).

**Key finding:** the Phase 21 conclusion "training nested budget, not basis capacity, binds"
is CONFIRMED — with de-noised targets the deg-2/3 bases that previously overfitted
catastrophically (deg-2 OOS R² 0.794) now generalise (0.9984+), and the selected surface
moved from deg-1 to deg-3.

Evidence: `docs/validation/PHASE22_TASK1_OOS_REMEDIATION_REPORT.{json,md}`.
ChangeRecord `6f88fd2a1fa449908a7cd8236ea30d33` (OWNER_REVIEW); MR-011/MR-012 refreshed →
MITIGATED. Production sign-off remains withheld pending Phase 22 Tasks 2–5, credentialled
calibration, and independent APS X2 review.
