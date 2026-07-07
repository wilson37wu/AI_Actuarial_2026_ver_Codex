# HW1F Live/Proxy Swaption Calibration - Parameter Card

> **UNSIGNED** - Parameters UNSIGNED pending Model Owner approval (roadmap #2, MR-001/MR-008): quote-set provenance file_fixture; no owner-approved credentialled vendor source is configured (roadmap #1). Educational/proxy data - not for regulatory submission.

- Schema: `hw1f-live-cal-1.0`
- Generated (UTC): 2026-07-07T19:28:55.243032+00:00
- Roadmap item: 4.1 #2 - Execute HW1F swaption calibration on live/proxy quote set
- Model-risk refs: MR-001, MR-008
- Inputs digest: `5489d2463424da53dad4094443910e03ff1bc134fc463b89423aa45bc66f871e`

## CNY (file_fixture, as of 2026-01-01)

| Parameter | Value |
|---|---|
| a (mean reversion) | 3.000000 |
| sigma_r (short-rate vol) | 0.033753 |
| lambda_r (mkt price of risk) | 0.000000 |
| r0 (initial short rate) | 0.020700 |

| Diagnostic | Value |
|---|---|
| Weighted SSE (bps^2) | 1.511945e+03 |
| RMSE (bps) | 8.8970 |
| Max abs error (bps) | 18.9290 |
| Converged (L-BFGS-B + Nelder-Mead polish) | True |
| Params at optimizer bound | a |
| Quotes (active/total) | 22/22 |
| Source SHA-256 | `2e15b086f5a3a2f7...` |
| Lineage approver | ModelGovernance_Phase13 |

## HKD (file_fixture, as of 2026-01-01)

| Parameter | Value |
|---|---|
| a (mean reversion) | 3.000000 |
| sigma_r (short-rate vol) | 0.041902 |
| lambda_r (mkt price of risk) | 0.000000 |
| r0 (initial short rate) | 0.045000 |

| Diagnostic | Value |
|---|---|
| Weighted SSE (bps^2) | 3.394112e+03 |
| RMSE (bps) | 13.3310 |
| Max abs error (bps) | 27.2560 |
| Converged (L-BFGS-B) | True |
| Params at optimizer bound | a |
| Quotes (active/total) | 22/22 |
| Source SHA-256 | `00cef8b6ac6b7c39...` |
| Lineage approver | ModelGovernance_Phase13 |

## Production gates

| Gate | Status | Evidence |
|---|---|---|
| G-02 | PASS | CNY: is_placeholder=False; CNY: RMSE=8.90bps <= 25.0bps; HKD: is_placeholder=False; HKD: RMSE=13.33bps <= 25.0bps |
| G-12 | PASS | CNY: source=ration/fixtures/cny_swaption_surface_20260101.json; CNY: sha256=2e15b086f5a3a2f7...; HKD: source=ration/fixtures/hkd_swaption_surface_20260101.json; HKD: sha256=00cef8b |

*Standards: SOA ASOP 56 3.4; SOA ASOP 23; IA TAS M 3.5/3.6; IFoA APS X2 4.2.*
