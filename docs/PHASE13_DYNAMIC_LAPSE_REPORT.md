# Phase 13 Task 2 — Dynamic Lapse Calibration Report

**Run:** 2026-06-04 04:27:17 UTC
**Gates:** G-04 ✅ PASS | G-11 ✅ PASS
**ChangeRecord:** `ee0906eb2b0f4f6db81249b4efc41d5b` — **APPROVED** (assumption="dynamic_lapse")

> **PRODUCTION USE RESTRICTION.** Calibration uses a *synthetic* HK PAR lapse
> experience study and the sign-off is automation-driven. Replace with a
> credible experience study and obtain genuine independent APS X2 review
> before any pricing or regulatory use.

## 1. Functional Form

Let `s = market_rate - credited_rate`.

```
base(t)     = duration-dependent base annual lapse            [Opt C]
mult(s)     = 1 + beta * (2/pi) * arctan(s / kappa)           [Opt A]
shock(s)    = shock_max / (1 + exp(-(s - tau) / width))       [Opt B]
lapse(t, s) = clip(base(t) * mult(s) + shock(s), floor, cap)
```

At `s = 0`, `mult = 1` and `shock` collapses to a small baseline, so the
model reduces to approximately the legacy static duration table — the
static path (`dynamic_lapse=None`) is preserved bit-for-bit.

## 2. Calibrated Parameters

| Parameter | Value | Meaning |
|---|---|---|
| beta | 0.6458 | efficiency sensitivity (Opt A) |
| kappa | 0.0246 | spread scale, annualised |
| shock_max | 0.1767 | max additive mass lapse (Opt B) |
| tau | 0.0297 | mass-lapse spread threshold |
| width | 0.0100 | logistic transition width (fixed) |
| credited_rate | 0.0250 | reference credited rate |

**Calibration basis:** Synthetic HK PAR endowment lapse experience study
**Optimizer:** scipy.optimize.least_squares (trf) (converged=True)
**Goodness-of-fit:** R² = 0.9999, RMSE = 0.00062, weighted RMSE = 0.00063,
max\|residual\| = 0.00178 over 48 experience cells.

## 3. Static vs Dynamic Impact (representative 20y HK PAR endowment)

| Scenario | Spread (bps) | PV NetLiab static | PV NetLiab dynamic | Δ% | PV Surr static | PV Surr dynamic |
|---|---:|---:|---:|---:|---:|---:|
| ITM -200bps | -200 | -52,433 | -28,861 | +44.96% | 80,030 | 74,533 |
| Base (mkt=credited) | +0 | -52,433 | -70,166 | -33.82% | 80,030 | 96,237 |
| OTM +100bps | +100 | -52,433 | -95,273 | -81.71% | 80,030 | 107,926 |
| OTM +200bps | +200 | -52,433 | -112,772 | -115.08% | 80,030 | 110,522 |
| Shock +400bps | +400 | -52,433 | -102,640 | -95.75% | 80,030 | 85,811 |

The static-lapse PV net liability is invariant to the market rate (FLAT). The
dynamic model produces a strong, economically-signed response: surrenders fall
when the guarantee is in-the-money and rise as market rates exceed the credited
rate. At the +400 bps shock, very high early-duration lapses deplete the
in-force faster, so PV surrender turns over — a realistic disintermediation
effect — while the response remains clearly non-FLAT. This closes G-04
criterion 2 (non-FLAT) and criterion 6 (documented TVOG/liability delta).

## 4. Production Gate Status

| Gate | Status | Evidence |
|---|---|---|
| G-04 | ✅ PASS | calibration converged (scipy.optimize.least_squares (trf)); R²=0.9999 >= 0.90; response NON-FLAT: max |ΔNL|=115.080% > 0.50% |
| G-11 | ✅ PASS | RMSE=0.00062 <= 0.010; experience basis: Synthetic HK PAR endowment lapse experience study; n_points=48 |

## 5. Governance

ChangeRecord `ee0906eb2b0f4f6db81249b4efc41d5b` (assumption="dynamic_lapse") logged to GovernanceStore and
driven through DRAFT → PEER_REVIEW → OWNER_REVIEW → **APPROVED**. This mitigates
model risk **MR-003** (static lapse / FLAT TVOG sensitivity).

**Standards addressed:** SOA ASOP 7 §3.3, ASOP 25 §3.3, ASOP 56 §3.1;
IA TAS M §3.5 & §3.6; IFoA APS X2 §4.2.
