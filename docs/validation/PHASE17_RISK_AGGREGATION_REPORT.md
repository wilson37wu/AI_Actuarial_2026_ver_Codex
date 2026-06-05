# Phase 17 Task 3 — Three-Driver Correlated Risk Aggregation

**Classification:** EDUCATIONAL ONLY — placeholder parameters; not a regulatory capital model.

**Verdict:** PARTIAL - three-driver aggregation evidence generated with review items

Drivers: short_rate, equity_guarantee, credit_spread.  Run `td-riskagg-400f7963`; reproducibility digest `27edeaf8c3ddf67f`.

## Standalone capital (99.5%, CRN-isolated)

| Component | mean L | VaR | ES | SCR (VaR−mean) |
|---|--:|--:|--:|--:|
| Rate (guaranteed benefit) | 84251.8 | 104947.6 | 105968.5 | 20695.8 |
| Equity guarantee | 23172.0 | 45731.1 | 51069.5 | 22559.0 |
| Credit loss | 10500.7 | 14960.3 | 15484.4 | 4459.7 |
| **Standalone sum** | | | | **47714.5** |

## Aggregation

- Var-covar SCR (governed 3×3 ESG correlation): **26828.5**
- Full three-driver nested SCR (diversified benchmark): **43752.9**
- Diversification benefit — formula: 20886.0; nested: 3961.6
- Formula-vs-nested rel. error: 38.7% (tol 35%)

### MR-010 (three-driver refresh)

The raw ESG-factor formula understates the diversified nested capital by **38.7%**.  ESG driver correlation matrix (rate, equity, credit): [[1.0, -0.15, -0.2], [-0.15, 1.0, -0.3], [-0.2, -0.3, 1.0]].  Realised capital-loss correlation: [[0.9999999999999998, 0.5385945441624796, 0.7666078287668839], [0.5385945441624798, 1.0, 0.6050915377419434], [0.7666078287668839, 0.6050915377419434, 0.9999999999999999]].  Equity-guarantee and credit losses co-move positively in stress even though the underlying equity/spread factor correlation is negative — so the second-moment formula on factor correlations is non-conservative for diversified capital.

## Standards

SOA ASOP 56 §3.5, SOA ASOP 56 §3.1.3, SOA ASOP 25 §3.3, IA TAS M §3.6, IA TAS M §3.2, IFoA proxy-model working party.
