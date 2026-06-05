# Model Limitation Card — Correlated Risk Aggregation (Rates + Equity Guarantee)

**Module:** `par_model_v2/projection/multi_driver_risk_aggregation.py`
**Phase:** 15 — Multi-Risk Economic Capital and Proxy-Model Validation (Task 3)
**Classification:** EDUCATIONAL ONLY — NOT a regulatory capital model
**Status:** OWNER_REVIEW — independent APS X2 review pending; production sign-off withheld
**Standards:** SOA ASOP 56 §3.1.3/§3.5; SOA ASOP 25 §3.3; IA TAS M §3.2/§3.6; IFoA proxy-model working party

## What this adds

Aggregates **standalone** rate and equity-guarantee economic capital and benchmarks the
variance-covariance formula result against the **fully-diversified two-driver nested**
capital from Task 1. Closes the Phase 15 requirement to demonstrate correlated risk
aggregation and quantify diversification benefit.

Method, on one shared set of correlated outer `(r_H, S_H)` states (common random numbers):

1. **Standalone rate capital** — full residual liability with the equity guarantee switched
   OFF (`EquityGuaranteeSpec(guarantee_rate=0.0)`); only the rate-driven guaranteed-benefit
   leg remains. SCR-proxy = VaR(99.5%) − mean.
2. **Standalone equity-guarantee capital** — the equity-guarantee leg isolated by
   common-random-number subtraction (`L_full − L_rate`), so the two standalones are computed
   on identical inner paths and sum to the full liability by construction.
3. **Variance-covariance aggregation** — `SCR_agg = √(SCR_r² + SCR_e² + 2ρ·SCR_r·SCR_e)`
   using the governed ESG `rate_equity_correlation` ρ and the validated 2×2 ESG correlation
   matrix (`phase8_rate_equity_fx_correlation_matrix`, `CorrelationMatrixValidator`).
4. **Fully-diversified nested capital** — VaR/ES on the joint two-driver liability
   `L(r_H, S_H)` (both drivers stochastic together) as the diversification reference.

## Validation evidence (seed = 42, 10y / age 40M / SA 100k, 99.5%, N_outer = 1,000, n_inner = 256)

| Quantity | SCR-proxy |
|---|--:|
| Standalone rate | 21,285.45 |
| Standalone equity guarantee | 23,191.31 |
| Undiversified sum (SCR_r + SCR_e) | 44,476.76 |
| Variance-covariance formula (ESG ρ = −0.15) | 29,031.30 |
| **Fully-diversified nested (ground truth)** | **43,250.62** |

| Diversification metric | Value |
|---|--:|
| Benefit, formula (sum − formula) | 15,445.47 |
| Benefit, nested (sum − nested) | 1,226.15 |
| Formula − nested gap | −14,219.32 |
| Formula vs nested rel. error | 32.88% |
| Empirical component loss correlation | +0.546 |

**Verdict:** PASS — correlation matrix valid, both formula and nested capital sit below the
undiversified sum (non-negative diversification benefit), and the formula-vs-nested rel.
error (32.9%) is within the 35% review tolerance. Reproducibility digest
`55ca305d…` (bit-identical on re-run).

## Key model-risk finding

The variance-covariance formula fed with the **raw ESG driver correlation (ρ = −0.15)**
materially **understates** the diversified tail capital (29,031 vs nested 43,251, −33%). The
economic reason: the equity maturity guarantee (a put) and the rate-driven guaranteed-benefit
leg both *gain* value in the same direction under a joint down-rate / down-equity stress, so
their realised **loss correlation is +0.55** — strongly positive — not the −0.15 factor
correlation. The factor correlation describes how the *drivers* co-move; the capital tail
depends on how the *losses* co-move, which the non-linear guarantee payoffs invert in sign and
amplify. A production capital model must aggregate on the **capital-loss correlation** (or use
the nested run directly), not the raw ESG factor correlation.

## Limitations / model-use restrictions

- The variance-covariance formula is a second-moment / elliptical approximation and misses the
  non-linear, asymmetric guarantee interactions evidenced by the 33% formula-vs-nested gap.
- Aggregation uses the **ESG factor correlation**, which is *not* a calibrated capital-module
  correlation; the empirical loss correlation (+0.55) is reported for transparency but not used
  in the headline formula (the task brief specifies the ESG correlation matrix).
- Only two risk drivers are in the tail. Lapse, mortality trend, credit spread, FX, liquidity,
  and management-action risks remain outside this aggregation.
- HW1F / GBM parameters are educational placeholders; the equity-guarantee specification is a
  stylised GMMB put.
- SCR-proxy = VaR − mean at the horizon; not deflated to t=0 and not a regulatory SCR.
- Credentialled calibration data and independent APS X2 review are required before any
  production use; status is OWNER_REVIEW.

**Reproduce:** `PYTHONPATH=. python3 scripts/build_phase15_task3_evidence.py`
→ `docs/validation/PHASE15_RISK_AGGREGATION_REPORT.{json,md}`
