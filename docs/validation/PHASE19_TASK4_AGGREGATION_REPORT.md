# Phase 19 Task 4 - Five-Driver Tail-Dependent Risk Aggregation

**Drivers:** short_rate, equity_guarantee, credit_spread, lapse_behaviour, mortality_trend

**Verdict:** PASS - five-driver copula aggregation (selected: gaussian) reconciles to nested capital within 6.5% vs var-covar 48.8%; MR-010 five-driver mitigation confirmed

Run `ftd-riskagg-65094ee8` | 19.07 s | digest `50ca08d617fe`

## 1. Standalone capital (CRN-isolated)

| Driver | SCR |
|--------|----:|
| Rate | 33,329.5 |
| Equity guarantee | 30,195.6 |
| Credit spread | 9,770.7 |
| Lapse behaviour | 26,973.1 |
| Mortality trend | 413.3 |
| **Sum (no diversification)** | **100,682.3** |

## 2. Aggregation vs genuine five-driver nested capital

| Method | Aggregate SCR | Rel. error vs nested |
|--------|--------------:|---------------------:|
| Var-covar (5x5 ESG factor) | 47,292.8 | 48.8% |
| Copula (gaussian, realised losses) | 86,444.2 | 6.5% |
| **Nested ground truth** | **92,448.6** | - |

ESG-factor var-covar understates nested capital by **48.8%** (MR-010).
Copula-on-realised-losses reconciles within **6.5%**.

## 3. CRN additive-decomposition residual (multiplicative lapse x mortality)

- CRN additive-sum SCR: 84,961.8
- Genuine nested SCR:   92,448.6
- Interaction residual: -7,486.8 (-8.1% of nested) - the multiplicative in-force x (equity-guarantee + mortality-G) cross-terms the additive split omits.

## 4. Mortality-trend driver (5th, second non-financial, orthogonal)

- Mortality is non-financial (P=Q, no risk premium) and orthogonal to every financial driver in the default 5x5 matrix; standalone SCR 413.3 is SMALL vs rate/equity/credit, confirming a genuinely orthogonal second tail axis (cf the Phase 19 Task 3 nested finding).

## Notes

- Standalone rate capital is the guaranteed-benefit component (equity, credit, lapse, and mortality all OFF; central q_x basis).
- Equity / credit standalone capital isolated by common-random-number subtraction (eq-guarantee / reduced-form credit-loss).
- Lapse standalone capital is (IF(r,b)-1)*guaranteed_pv - the marginal behavioural in-force effect; lapse is NON-FINANCIAL.
- Mortality standalone capital is the marginal effect of scaling central q_x by G(m_H)=exp(theta*m_H); mortality trend is NON-FINANCIAL (P=Q) and ORTHOGONAL to every financial driver in the default 5x5 matrix.
- Var-covar aggregation uses the governed 5x5 ESG driver correlation, NOT a fitted capital-factor correlation.
- MR-010 (five-driver refresh): the raw ESG-factor var-covar formula understates the diversified nested capital by 48.8% because the realised capital-loss vectors co-move positively in the tail while several ESG factor off-diagonals are zero/negative.
- Copula-on-realised-losses (selected: gaussian) reconciles to nested capital within 6.5% - the implemented MR-010 mitigation, now extended to five drivers.
- Five-driver finding: the CRN additive decomposition leaves a -8.1%-of-nested interaction residual because BOTH the lapse driver (IF) and the mortality driver (G) scale the guaranteed benefit MULTIPLICATIVELY (the IF x equity-guarantee and IF x mortality-G cross-terms). A positive residual means the genuine nested capital is SUPER-additive vs the CRN-additive standalone sum, so 'nested <= standalone sum' is NOT a valid invariant for five drivers.
- Mortality being a SMALL orthogonal driver, the five-driver nested SCR is a small monotone increment over the four-driver figure (benefit-timing on a sum-assured endowment); the copula must not over-state this second orthogonal tail axis (MR-012 tail-aggregation governance).
