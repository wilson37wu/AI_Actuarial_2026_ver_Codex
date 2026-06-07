# Seven-Driver Economic-Capital Aggregation Card

**Phase:** 21 - FX + Liquidity Drivers and Six/Seven-Driver Economic Capital (Task 4)

**Status:** EDUCATIONAL. ChangeRecord at OWNER_REVIEW; production sign-off withheld
pending UI propagation (Task 5), credentialled liquidity exposure/coupling calibration,
and independent (APS X2) review.

## Scope

All seven documented drivers aggregated at 99.5%/1y: G2++ rates, GBM equity, CIR++
credit spread, OU dynamic lapse, OU mortality trend, lognormal FX (CIP-exact analytic
conditioning), and the Task 3 G-LIQ-calibrated CIR++ liquidity premium (CIR-affine-exact
analytic forced-sale haircut conditioning, baseline-centred).

## Headline numbers (seed 42, n_outer 160, n_inner 24)

| Measure | Value |
|---|---|
| Standalone sum | 62407.6 |
| Var-covar (7x7 ESG) | 28996.2 |
| Copula (gaussian) | 41592.6 |
| Nested benchmark | 48694.0 |
| Var-covar understatement | 40.5% |
| Copula vs nested rel err | 14.6% |
| Liquidity standalone SCR | 63.3 |
| Tail convergence | CONVERGED |
| Sobol-RQMC variance-reduction | 3.6x |

## Key findings

1. MR-010 re-confirmed under seven drivers: raw ESG factor correlations in the
   var-covar formula understate the nested diversified capital by 40.5%; the
   copula-on-realised-losses re-aggregation remains the governed mitigation.
2. MR-012 driver-omission residual CLOSED at aggregation level — no documented
   driver remains outside the correlated aggregation.
3. The calibrated liquidity premium's strong mean reversion (half-life ~0.74y)
   makes 1-in-200 one-year liquidity translation risk SMALL on a hold-to-maturity
   book (63 standalone) — an honest finding, verified affine-exact, not a
   wiring defect.

## Limitations / model-use restrictions

Educational placeholders: liquidity exposure notional, 7x7 liquidity couplings.
Single systemic liquidity factor (no asset-class segmentation / funding ladder).
Nested benchmark n_outer is small for a 99.5% metric — nested bootstrap CI is wide
and disclosed; convergence evidence carried by the copula-simulated study.
Not for pricing, reserving, or regulatory capital.

*Standards: SOA ASOP 56 3.1.3/3.4/3.5; ASOP 25 3.3; IA TAS M 3.2/3.5/3.6/3.7;
Solvency II Del. Reg. Art. 234; EIOPA VA methodology; L'Ecuyer 2018.*
