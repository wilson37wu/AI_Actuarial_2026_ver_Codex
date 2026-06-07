# Phase 22 Task 3 — Liquidity Exposure-Notional + 7x7 Coupling Calibration (G-LIQX)

**Run:** 2026-06-07 08:25:03 UTC
**Market:** HKD (documented-targets educational fixture)
**Gate G-LIQX:** PASS ✅

## What this replaces

The LAST liquidity placeholders: the `LiquidityExposureSpec` notional
(placeholder 30,000) and the six `SevenDriverCorrelation` liquidity couplings
(placeholders 0.05, -0.20, 0.35, 0.10, 0.0, 0.10) flagged in MR-011/MR-012.

## Exposure notional (reproducible)

`exposure_notional = backing_asset_mv x illiquid_share x forced_sale_fraction`
= 100,000 x 0.55 x 0.40 = **22,000**
(GMMB backing-portfolio anchor; HK par-fund illiquid allocation; Solvency II
Art. 142 mass-lapse 40% forced-sale analogue.)

## Couplings (CIR transition-residual estimator, 1200 monthly joint obs)

| Coupling | Target | Estimated | Error |
|---|---|---|---|
| liq_rate | -0.1000 | -0.0794 | +0.0206 |
| liq_equity | -0.3000 | -0.2935 | +0.0065 |
| liq_spread | +0.5000 | +0.4579 | -0.0421 |
| liq_lapse | +0.1500 | +0.1081 | -0.0419 |
| liq_mortality | +0.0000 | +0.0160 | +0.0160 |
| liq_fx | +0.1500 | +0.1070 | -0.0430 |

Tolerance +/-0.12; 7x7 PSD validator: **PASS** (no repair allowed).

## Var-covar SCR sensitivity (standalone SCRs from Phase 21 Task 4)

- Placeholder config: 28,996 -> calibrated config: 28,991 (-0.02%)
- Notional grid (monotone=False; net liquidity cross-term -766 — the
  liquidity driver is **net-diversifying** at this scale, so var-covar SCR can
  legitimately fall as the notional rises): 0.5x -> 28991, 1.0x -> 28991, 1.5x -> 28990
- Max coupling-perturbation effect (+/-0.10 on liq_spread/liq_equity): 0.01%
- Full nested + copula re-aggregation with these values is **Phase 22 Task 4**.

## G-LIQX criteria

| Criterion | Outcome |
|---|---|
| c1_lineage_checksum_ok | PASS |
| c2_exposure_reproducible_in_band | PASS |
| c3_couplings_recovered_within_tol | PASS |
| c4_correlation7_psd_validator_pass | PASS |
| c5_sensitivity_bounded | PASS |
| c6_not_placeholder_with_audit | PASS |

**Evidence:** HKD: n=1200, notional=22000, couplings={'liq_rate': -0.0794, 'liq_equity': -0.2935, 'liq_spread': 0.4579, 'liq_lapse': 0.1081, 'liq_mortality': 0.016, 'liq_fx': 0.107}

## Governance

- ChangeRecord `39b5c559fc63426b830660cd7595a297` — status **OWNER_REVIEW** (assumption_change)
- PARAM_CHANGE audit entries: a7e9a48281af43e9b5b42e17988721aa
- MR-011: **MITIGATED** | MR-012: **MITIGATED** | audit integrity: **True**

## Model-use restrictions

EDUCATIONAL ONLY. Documented-targets fixture, not credentialled joint market
data; seeded-synthesis estimator recovery, not market joint estimation;
automation-driven sign-off stops at OWNER_REVIEW. Production use requires a
credentialled joint dataset and an independent APS X2 review.

*Standards: SOA ASOP 56 3.1.3/3.4; SOA ASOP 25 3.3; IA TAS M 3.4/3.5/3.6;
Solvency II Delegated Reg. Art. 142/234; Dick-Nielsen, Feldhutter & Lando
(2012); Amihud (2002); Pastor & Stambaugh (2003).*
