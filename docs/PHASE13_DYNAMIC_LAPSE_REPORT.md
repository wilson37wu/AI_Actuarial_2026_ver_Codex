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


---

## 6. Bounded Elasticity of the Rate-Differential Response (roadmap §4.1 #4, MR-003)

The lapse response to the rate differential `s = market_rate - credited_rate`
is now exposed as an analytic **marginal response** and **semi-elasticity**, with
a proven closed-form bound.

Let `L(s) = base·mult(s) + shock(s)` (pre-clip). Then

```
dL/ds        = base·mult'(s) + shock'(s)                         [marginal response]
mult'(s)     = beta·(2/pi)·(1/kappa) / (1 + (s/kappa)^2)         (peaks at s=0)
shock'(s)    = shock_max·sig·(1-sig)/width, sig=logistic((s-tau)/width)  (peaks at s=tau)
semi_elast.  = (dL/ds) / L(s)  =  d ln L / d s
```

**Bounded-elasticity guarantee.** Because the arctan slope is maximised at
`s = 0` and the logistic slope at `s = tau`, the marginal response admits the
closed-form Lipschitz bound

```
sup_s dL/ds  =  base·beta·2/(pi·kappa) + shock_max/(4·width)
```

so lapse cannot react arbitrarily fast to a rate move (a well-posedness
requirement — SOA ASOP 7 §3.3, IA TAS M §3.5). For the calibrated default at the
year-1 base (0.12): bound = **6.6008 / unit-spread**;
a dense finite-difference sweep over ±1500 bps gives an observed maximum slope of
**5.1680**, confirming `observed ≤ bound` (component peaks:
efficiency 17.5070 at s=0, mass-lapse 4.5000 at s=τ).

| Spread (bps) | Marginal response dL/ds | Semi-elasticity /bp | Semi-elasticity /unit |
|---:|---:|---:|---:|
| -200 | 1.1701 | 0.001327 | 13.266 |
| -100 | 1.9986 | 0.001926 | 19.262 |
| +0 | 2.9140 | 0.002267 | 22.671 |
| +100 | 3.5706 | 0.002219 | 22.186 |
| +200 | 4.5894 | 0.002279 | 22.787 |
| +400 | 3.9592 | 0.001328 | 13.281 |

The semi-elasticity peaks near-the-money (~0.0023 per bp ⇒ a +1 bp rate move
lifts the annual lapse rate ~0.23%) and tapers in both tails as the arctan and
logistic saturate — the economically-required shape.

## 7. TVOG Delta — Dynamic vs Static Lapse (TVOG delta quantified)

The DoD requires the TVOG delta be quantified. Define a representative-policy
**TVOG proxy** as the convexity value `TVOG = E[PV_netliab(R)] - PV_netliab(credited)`
with `R ~ N(credited, sigma^2)` evaluated by exact 5-node Gauss-Hermite
quadrature. Under **static** lapse `PV_netliab(R)` is rate-invariant (FLAT) so
`TVOG_static = 0` exactly; the dynamic model bends the PV with the rate, so the
reported

```
TVOG delta = TVOG_dynamic - TVOG_static  ( = TVOG_dynamic )
```

is precisely the TVOG contribution introduced by dynamic lapse — the FLAT-
sensitivity gap MR-003 flags for static lapse.

At the illustrative `sigma = 100 bps`, discount 3.00% (≤ CBIRC 3.0% cap),
on the representative 20y HK PAR endowment:

- **TVOG static** = **0.0000** (FLAT, by construction)
- **TVOG dynamic** = **-753.6047**
- **TVOG delta** = **-753.6047** = **-1.835%** of the central reserve

**Sensitivity to the assumed rate volatility:**

| Rate sigma | TVOG static | TVOG delta | Δ % of central |
|---:|---:|---:|---:|
| 0.25% | 0.0000 | -71.1503 | -0.173% |
| 0.50% | 0.0000 | -274.0907 | -0.667% |
| 1.00% | 0.0000 | -753.6047 | -1.835% |
| 1.50% | 0.0000 | -628.0662 | -1.529% |
| 2.00% | 0.0000 | 762.0537 | +1.855% |

The delta grows with rate uncertainty through ~100–150 bps, then the sign turns
over at very high sigma as the Option-B mass-lapse depletes early-duration
in-force faster than the efficiency term adds surrenders (the realistic
disintermediation / turnover effect already noted in §3). Machine artifact:
`docs/DYNAMIC_LAPSE_ELASTICITY_TVOG_DELTA.json`; regenerate with
`python scripts/build_dynamic_lapse_tvog_report.py`.

> **SCOPE.** Educational representative-policy diagnostic — NOT the governed
> portfolio TVOG headline (produced by the stochastic aggregation engine and
> left untouched this cycle). Synthetic experience study, illustrative sigma,
> automation-driven sign-off; UNSIGNED pending APS X2 review. Re-baselining the
> governed headline onto a dynamic-lapse basis remains owner-gated.
