# Liquidity-Premium Seventh-Driver Card -- G-LIQ

**Phase:** 21 - FX + Liquidity Drivers and Six/Seven-Driver Economic Capital (Task 3)

**Status:** EDUCATIONAL calibrated parameters; gate **PASS (6/6)**. Production sign-off
withheld pending seven-driver tail-dependent aggregation + tail diagnostics (Task 4),
UI propagation (Task 5), credentialled calibration data, and independent (APS X2) review.

## Driver

CIR++ mean-reverting square-root liquidity premium / funding spread l(t) = x(t) + shift,
dx = kappa_l (b - x) dt + sigma_l sqrt(x) dW. The SEVENTH economic-capital-proxy driver and
the LAST documented-but-omitted driver in MR-012 (rate, equity, credit, lapse, mortality,
FX, **liquidity**). Same CIR++ family and full-truncation Euler discretisation as the credit
driver — one tested scheme, one estimator, two drivers. P/Q consistent via the CIR risk
premium: b^Q = b^P + lambda_l sigma_l^2 / kappa_l (positive lambda_l raises Q premia; a
widening funding spread is the insurer's loss).

Economic interpretation: the NON-credit illiquidity-premium component of asset spreads
(EIOPA volatility-adjustment decomposition) and the funding-roll cost in stressed markets.
The forced-sale haircut helper turns a horizon liquidity path into a liability-side PV
haircut on illiquid backing assets: haircut = 1 - exp(-integral l du) (Duffie-Singleton
exponential-affine form).

## Calibration (educational-proxy HKD fixture, 240 monthly obs 2006-2025)

| Parameter | Calibrated | Note |
|---|---|---|
| kappa_l | 0.9345 /yr | half-life ~0.7 yr (target 0.60; slope-noise documented) |
| long-run premium (P) | 63 bp | target 60 bp; sample-mean robust |
| sigma_l | 0.0213 | target 0.022; residual-variance robust |
| lambda_l | 2.0000 | **CLAMPED at the plausibility cap** — anchor-implied ~2.5; disclosed |
| shift | 10 bp | CIR++ non-negativity |
| Feller ratio | 21.71 | holds |

Estimator: `LiquidityPremiumCalibrator` **delegates** to the regression-tested
homoscedastic CIR OLS (`CIRCalibrator`, Kladivko 2007; Brigo-Mercurio 2006); lambda_l
backed out from the documented risk-neutral long-run anchor (75 bp) via the CIR
risk-premium relation, clamped to [0, 2].

## G-LIQ gate (6/6 criteria)

c1 min obs (>=60); c2 kappa in [0.05, 3.0]; c3 long-run in [10, 300] bp;
c4 sigma in [0.003, 0.30]; c5 lambda in [0, 2]; c6 not-placeholder with a
PARAM_CHANGE audit entry. **All PASS.**

## Governance

ChangeRecord `07880f42a2b84174a54b6261c0fd7131` (assumption_change) **APPROVED**
(educational three-stage sign-off); 1 PARAM_CHANGE + 2 GOVERNANCE audit entries
(store audit 47->50, change 25->26, integrity verify_all True); MR-011 / MR-012
refreshed to MITIGATED — **not closed**: Task 4 aggregation pending; credentialled
data + genuine independent APS X2 review pending.

## Limitations / model-use restrictions

- Single systemic liquidity factor: no asset-class segmentation, no bid-ask
  microstructure, no funding-ladder granularity, no jump-to-illiquidity regime.
- Educational-proxy fixture (documented-target deterministic synthesis), single-path
  OLS, no standard errors; lambda_l sits AT the plausibility cap — treat the Q
  re-anchoring as an upper-bound educational setting.
- NOT a regulatory liquidity-risk model (no LCR/NSFR analogue, no cash-flow ladder).
- Capital evidence remains SIX-driver until Phase 21 Task 4 wires the liquidity
  driver into the nested/LSMC aggregation and tail diagnostics.

*Standards: SOA ASOP 56 3.1.3/3.4; SOA ASOP 25 3.3; IA TAS M 3.4/3.5/3.6;
EIOPA VA illiquidity-premium methodology; CIR (1985); Brigo-Mercurio (2006);
Lord-Koekkoek-van Dijk (2010); Duffie-Singleton (1999).*

**Files:** `par_model_v2/stochastic/liquidity_premium.py`;
`par_model_v2/calibration/liquidity_calibrator.py`;
`par_model_v2/calibration/liquidity_market_data_source.py`;
`par_model_v2/calibration/phase21_liquidity_calibration.py`;
`par_model_v2/calibration/fixtures/hkd_liquidity_premium_history_20260101.json`;
`scripts/build_phase21_task3_liquidity.py`; `tests/test_phase21_liquidity_driver.py` (37 tests);
`docs/validation/PHASE21_TASK3_LIQUIDITY_CALIBRATION_REPORT.{json,md}`.
