# Calibration Backtest Report 2026

**Generated:** 2026-06-04T08:28:08.184593+00:00
**Market:** CNY
**Run ID (full):** backtest-f09fe151a3cb
**Run ID (out-of-sample):** backtest-f818199660c6
**Observations:** 12 annual points (in-sample 7, out-of-sample 5)
**Dataset basis:** LIVE realised CNY market history (educational proxy feed) — out-of-sample validated
**Gate G-09:** PASS

> Calibration uses the in-sample window only; the out-of-sample holdout below is a
> genuine out-of-sample test (its realised losses never entered calibration).

---

## 1. Data Lineage (IA TAS M §3.6)

- Source type: educational_historical_proxy
- Source detail: ChinaBond 1Y CGB year-end yield + CSI 300 calendar-year total return (educational proxy series, vendor feed not yet credentialled)
- Lineage ID: LIN_BT_CNY_20260101; fixture version 1.0.0; approved_by ModelGovernance_Phase13
- SHA-256: 05f21d4bb1e826cd9ff24c0adecdcff8...
- **Production restriction:** educational proxy series; replace with credentialled
  ChinaBond / CSI / Wind extracts before regulatory or capital-adequacy use.

## 2. Calibrated Parameters (from in-sample history)

- HW1F: a=0.8453, sigma_r=0.0095 (0.95% p.a.), r0=0.0420
- GBM: sigma_S=0.2976 (29.8% p.a.), ERP=0.1204, dividend_yield=0.0250, rho=0.2409

## 3. Full-Series Backtest (12 obs)

- Rate 10th-90th coverage: 75.0% (min 70%)
- Equity 10th-90th coverage: 91.7% (min 70%)
- VaR95 breach rate: 0.0%
- VaR99 breach rate: 0.0% (max 5%)
- Kupiec POF p-values: 95%=0.267, 99%=0.623
- Mean ES95 / ES99: 192,591 / 233,983
- Q-measure martingale control: PASS
- Governance trigger: MONITOR

## 4. Out-of-Sample Holdout Backtest (5 obs)

- Rate coverage: 100.0%
- Equity coverage: 100.0%
- VaR95 breach rate: 0.0%
- VaR99 breach rate: 0.0%
- Kupiec POF p-values: 95%=0.474, 99%=0.751
- Recalibration trigger: MONITOR

## 5. Tail Loss Analysis (full series)

- Mean VaR95 / ES95: 161,767 / 192,591
- Mean VaR99 / ES99: 211,373 / 233,983
- Max realised excess above VaR95 / VaR99: 0 / 0

## 6. Gate G-09 Verification

**Status: PASS**

n_obs=12, live_file=True; rate_cov=75.0%; equity_cov=91.7%; kupiec95_p=0.267; var99_breach=0.0%; report_populated=True; audit_entry_id=1eca50b2b5004bffafab9c4bf786f0be

| # | Criterion | Threshold | Result |
|---|-----------|-----------|--------|
| 1 | >=10 annual obs from live file | >=10 | 12 |
| 2 | Rate coverage | >=70% | 75.0% |
| 3 | Equity coverage | >=70% | 91.7% |
| 4 | Kupiec VaR95 p-value | >0.05 | 0.267 |
| 5 | VaR99 breach rate | <=5% | 0.0% |
| 6 | Annual report populated | not scaffold | yes |
| 7 | Governance audit entry | present | 1eca50b2b5004bffafab9c4bf786f0be |

## 7. Governance Interpretation

- SOA ASOP 56 §3.5: scenario adequacy now evidenced against realised history, not
  self-generated synthetic data; rate/equity coverage and VaR/ES breach tracked.
- IA TAS M §3.6: backtest detail, Kupiec statistics, and martingale control recorded;
  VALIDATION AuditEntry 1eca50b2b5004bffafab9c4bf786f0be written to the GovernanceStore.
- IA TAS M §3.6 requirements advanced: VR-B01 (asset backtest), VR-B03 (VaR/ES
  exception backtest), VR-S05 (HW1F stability), and VR-B02 (liability shortfall proxy).
- ERM tail view: Expected Shortfall reported alongside VaR so severe low-frequency
  loss years are not hidden by percentile thresholds.

## 8. Recommendation

No recalibration trigger on live history. Continue annual monitoring and replace the educational proxy feed with a credentialled CNY market extract.

## 9. Machine Summary

```json
{
  "run_timestamp": "2026-06-04T08:28:08.184593+00:00",
  "market": "CNY",
  "lineage": {
    "lineage_id": "LIN_BT_CNY_20260101",
    "market": "CNY",
    "as_of_date": "2026-01-01",
    "source_type": "educational_historical_proxy",
    "source_detail": "ChinaBond 1Y CGB year-end yield + CSI 300 calendar-year total return (educational proxy series, vendor feed not yet credentialled)",
    "fixture_version": "1.0.0",
    "approved_by": "ModelGovernance_Phase13",
    "approval_timestamp": "2026-01-01T00:00:00Z",
    "sha256_checksum": "05f21d4bb1e826cd9ff24c0adecdcff82509b7a82f4999cbda60848e625066fc",
    "produced_at": "2026-06-04T08:28:08.185220+00:00"
  },
  "calibration": {
    "a": 0.84527860920907,
    "sigma_r": 0.009513236142594271,
    "r0": 0.042,
    "sigma_S": 0.297584345786439,
    "erp": 0.12041428571428572,
    "rho": 0.24086209320404586,
    "dividend_yield": 0.025,
    "is_placeholder": false,
    "notes": "Calibrated from 7 in-sample realised annual observations (Phase 13 Task 5, G-09 out-of-sample backtest)."
  },
  "full_backtest": {
    "run_id": "backtest-f09fe151a3cb",
    "rate_coverage_pct": 0.75,
    "equity_coverage_pct": 0.9166666666666666,
    "var95_exception_rate": 0.0,
    "var99_exception_rate": 0.0,
    "es95_mean": 192591.24322132464,
    "es99_mean": 233983.20987463024,
    "kupiec_pvalue_95": 0.26720505975226005,
    "kupiec_pvalue_99": 0.6233349482036092,
    "martingale_all_pass": true,
    "requires_recalibration": false,
    "audit_entry_id": "1eca50b2b5004bffafab9c4bf786f0be",
    "created_at": "2026-06-04T08:28:23.729811+00:00"
  },
  "out_of_sample_backtest": {
    "run_id": "backtest-f818199660c6",
    "rate_coverage_pct": 1.0,
    "equity_coverage_pct": 1.0,
    "var95_exception_rate": 0.0,
    "var99_exception_rate": 0.0,
    "es95_mean": 215985.37482456552,
    "es99_mean": 260448.5824375567,
    "kupiec_pvalue_95": 0.47387195607914057,
    "kupiec_pvalue_99": 0.7512264183056867,
    "martingale_all_pass": true,
    "requires_recalibration": false,
    "audit_entry_id": null,
    "created_at": "2026-06-04T08:28:33.048263+00:00"
  },
  "gate_g09": {
    "gate_id": "G-09",
    "gate_description": "Backtesting against live CNY market data: >=10 annual observations, rate/equity coverage >=70%, Kupiec VaR95 p>0.05, VaR99 breach <=5%, populated annual report, governance audit entry (SOA ASOP 56 \u00a73.5; IA TAS M \u00a73.6)",
    "status": "PASS",
    "evidence": "n_obs=12, live_file=True; rate_cov=75.0%; equity_cov=91.7%; kupiec95_p=0.267; var99_breach=0.0%; report_populated=True; audit_entry_id=1eca50b2b5004bffafab9c4bf786f0be",
    "evaluated_at": "2026-06-04T08:28:33.048453+00:00"
  },
  "annual_report_path": "docs/CALIBRATION_BACKTEST_REPORT_2026.md",
  "audit_entry_id": "1eca50b2b5004bffafab9c4bf786f0be",
  "observations": {
    "full": 12,
    "in_sample": 7,
    "out_of_sample": 5
  }
}
```
