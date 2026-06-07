# Seven-Driver Proxy Validation Card

**Phase:** 22 Task 2 - Proxy hardening + seven-driver OOS validation

**Status:** EDUCATIONAL. ChangeRecord at OWNER_REVIEW; production sign-off
withheld pending credentialled calibration and independent APS X2 review.

## Result

Seven-driver proxy validation verdict: **PASS - seven-driver surface (analytic, deg 3, max_int 2, 46 terms) validated OOS (R2=0.9985, VaR/ES/SCR rel err 0.51%/0.18%/1.26%, liquidity offset exact, leakage-free)**. Selected surface:
analytic, degree 3, max interaction 2, 46 terms.

| Metric | Value |
|---|---:|
| OOS R2 | 0.9985 |
| OOS RMSE | 816.0 |
| VaR rel error | 0.51% |
| ES rel error | 0.18% |
| SCR rel error | 1.26% |
| Liquidity offset max error | 0.000e+00 |

## Design

The seventh driver is the calibrated CIR++ liquidity premium. It enters as an
analytic CIR-affine forced-sale haircut feature rather than a learned noisy
coefficient. FX remains a CIP-exact analytic offset. The polynomial surface is
selected on a disjoint-seed hold-out by OOS RMSE.

## Limitations

Educational only. Liquidity exposure notional and 7x7 liquidity couplings remain
placeholder assumptions until Phase 22 Task 3. The surface is valid only over
the fitted state region; no production capital use before credentialled data and
independent APS X2 review.
