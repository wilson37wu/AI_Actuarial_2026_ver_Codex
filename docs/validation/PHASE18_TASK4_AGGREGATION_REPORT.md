# Phase 18 Task 4 - Four-Driver Tail-Dependent Risk Aggregation

**Drivers:** short_rate, equity_guarantee, credit_spread, lapse_behaviour

**Verdict:** PASS - four-driver copula aggregation (selected: gaussian) reconciles to nested capital within 9.4% vs var-covar 47.4%; MR-010 four-driver mitigation confirmed

Run `fd-riskagg-ff75c8b4` | 31.3 s | digest `7ff686fd29c7`

## 1. Standalone capital (CRN-isolated)

| Driver | SCR |
|--------|----:|
| Rate | 33,336.7 |
| Equity guarantee | 29,988.9 |
| Credit spread | 9,902.6 |
| Lapse behaviour | 35,089.6 |
| **Sum (no diversification)** | **108,317.8** |

## 2. Aggregation vs genuine four-driver nested capital

| Method | Aggregate SCR | Rel. error vs nested |
|--------|--------------:|---------------------:|
| Var-covar (4x4 ESG factor) | 52,248.1 | 47.4% |
| Copula (gaussian, realised losses) | 89,909.9 | 9.4% |
| **Nested ground truth** | **99,268.7** | - |

ESG-factor var-covar understates nested capital by **47.4%** (MR-010).
Copula-on-realised-losses reconciles within **9.4%**.

## 3. CRN additive-decomposition residual (multiplicative lapse term)

- CRN additive-sum SCR: 88,221.3
- Genuine nested SCR:   99,268.7
- Interaction residual: -11,047.4 (-11.1% of nested) - the multiplicative in-force x equity-guarantee cross-term the additive split omits.

## Notes

- Standalone rate capital is the guaranteed-benefit component (equity, credit, and behavioural lapse all OFF).
- Equity / credit standalone capital isolated by common-random-number subtraction (eq-guarantee / reduced-form credit-loss).
- Lapse standalone capital is (IF(r,b)-1)*guaranteed_pv - the marginal behavioural in-force effect; lapse is NON-FINANCIAL and orthogonal in the 4x4 ESG matrix.
- Var-covar aggregation uses the governed 4x4 ESG driver correlation, NOT a fitted capital-factor correlation.
- MR-010 (four-driver refresh): the raw ESG-factor var-covar formula understates the diversified nested capital by 47.4% because the realised capital-loss vectors co-move positively in the tail while several ESG factor off-diagonals are negative.
- Copula-on-realised-losses (selected: gaussian) reconciles to nested capital within 9.4% - the implemented MR-010 mitigation, now extended to four drivers.
- Four-driver finding: the CRN additive decomposition leaves a -11.1%-of-nested interaction residual because the lapse driver scales the benefits MULTIPLICATIVELY (the IF x equity-guarantee cross-term), unlike the exactly additive three-driver split. A positive residual means the genuine nested capital is SUPER-additive vs the CRN-additive standalone sum, so 'nested <= standalone sum' is NOT a valid invariant for four drivers.
