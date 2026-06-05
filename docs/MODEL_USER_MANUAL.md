# PAR Model User Manual

**Document version:** 1.0  
**Date:** 2026-05-31  
**Audience:** model users, actuaries, reviewers, and reporting analysts  
**Scope:** how to supply inputs, run the model, and extract outputs  
**Out of scope:** model development, automation setup, code contribution workflow

> **Use restriction:** this model is still labelled as an educational and
> development model. Do not use outputs for regulatory reporting, pricing,
> capital allocation, external disclosure, or assumption sign-off until the
> production gates in `docs/MODEL_RISK_CARD.md` are cleared.

---

## 1. What This Model Does

The repository contains a participating endowment actuarial model with:

- deterministic monthly liability, asset, and asset-share projection;
- stochastic economic scenario generation;
- TVOG calculation under Q-measure scenarios;
- VaR / ES reporting from P-measure loss distributions;
- input validation and governance/audit trail support.

The main user-facing code is here:

| Purpose | Location |
| --- | --- |
| Deterministic projection engine | `par_model_v2/projection/monthly_projection.py` |
| Demo run script | `scripts/run_monthly_projection.py` |
| Stochastic ESG generator | `par_model_v2/stochastic/esg_process.py` |
| Starter risk-free curves | `par_model_v2/stochastic/fixtures/risk_free_curves.json` |
| TVOG engine | `par_model_v2/projection/tvog.py` |
| VaR / ES engine | `par_model_v2/risk/risk_metrics.py` |
| Input validators | `par_model_v2/validation/data_validator.py` |
| Governance audit trail | `par_model_v2/governance/audit_trail.py` |

---

## 2. Environment Setup

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt -r requirements-dev.txt
```

Then verify the environment:

```powershell
python -m compileall -q par_model_v2 tests scripts
python -m pytest tests\test_monthly_projection.py tests\test_esg_process.py -q
```

If `python` is not on PATH, use the Python executable for your environment.
The model requires `numpy`, `pandas`, and `scipy` for normal runtime.

---

## 3. Input Data and Information Requirements

### 3.1 Required Policy Information

For a direct model run, create a `ParEndowmentProduct` from
`par_model_v2.projection.monthly_projection`.

Required fields:

| Field | Meaning | Current rule |
| --- | --- | --- |
| `term_years` | Policy term in years | must be `5`, `10`, or `20` |
| `issue_age` | Issue age | validator expects age 18 to 65 |
| `gender` | Policyholder gender | `M` or `F` |
| `sum_assured` | Guaranteed death/maturity benefit | positive CNY amount |
| `annual_premium` | Annual premium | positive CNY amount |

Optional fields:

| Field | Default | Meaning |
| --- | ---: | --- |
| `rb_rate_annual` | `0.030` | annual reversionary bonus rate |
| `terminal_bonus_pct` | `0.50` | terminal bonus as percentage of asset-share proxy |
| `surrender_value_pct` | `0.90` | surrender value percentage of asset-share proxy |
| `initial_rb_accum` | `0.0` | initial accumulated reversionary bonus |

Portfolio model-point validation expects these columns:

| Column | Required | Notes |
| --- | --- | --- |
| `age` | yes | issue age |
| `gender` | yes | `M`, `F`, or case-insensitive variants |
| `term_years` | yes | `5`, `10`, or `20` |
| `sum_assured` | yes | validator range: 1,000 to 10,000,000 |
| `premium` | yes | annual premium; positive |
| `policy_id` | optional | if present, must be unique |
| `policy_year` | optional | in-force duration check, if supplied |

Validator location:

```python
from par_model_v2.validation.data_validator import ModelPointValidator
```

### 3.2 Required Asset Information

Asset inputs are passed as `AssetPosition` objects.

| Field | Meaning |
| --- | --- |
| `asset_class` | `"Govt"`, `"Credit_A"` or other credit label, `"Equity"`, or `"Cash"` |
| `market_value` | starting market value |
| `book_value` | starting book value |
| `duration_years` | asset duration |
| `annual_yield` | coupon, dividend, or cash yield |
| `annual_capital_growth` | equity growth assumption; usually zero for bonds/cash |
| `average_maturity_years` | maturity/amortisation term for fixed income |
| `credit_rating` | optional rating label |

The demo asset portfolio is located in:

```text
scripts/run_monthly_projection.py
```

### 3.3 Projection Assumptions

`run_full_projection(...)` accepts these major run assumptions:

| Parameter | Default | Meaning |
| --- | ---: | --- |
| `discount_rate_annual` | `0.035` | deterministic discount rate |
| `acquisition_expense_pct` | `0.08` | acquisition expense as percentage of annual premium |
| `renewal_expense_pct` | `0.04` | renewal expense as percentage of monthly premium |
| `renewal_expense_fixed_monthly` | `12.50` | fixed monthly renewal expense |
| `policyholder_share` | `0.70` | policyholder share of distributable surplus |
| `shareholder_share` | `0.30` | shareholder share of distributable surplus |

Important: the current default `0.035` discount rate is documented as a
production issue elsewhere in the docs because it may exceed regulatory caps.
For controlled user examples, pass the discount rate explicitly.

### 3.4 ESG Scenario Inputs

For stochastic runs, use `ScenarioSet.generate(...)`.

Required inputs:

| Parameter | Meaning |
| --- | --- |
| `n` | number of scenarios |
| `T_months` | projection horizon in months |
| `measure` | `Measure.P` for real-world ALM/risk, `Measure.Q` for TVOG |

Optional but important inputs:

| Parameter | Meaning |
| --- | --- |
| `hw_params` | Hull-White 1F parameter object |
| `gbm_params` | equity GBM parameter object |
| `initial_curve` | `RiskFreeCurve`; use starter curves or a governed market curve |
| `seed` | random seed for reproducibility |
| `base_currency` | scenario reporting currency |
| `valuation_date` | scenario as-of date |

Starter curves are available for `USD`, `EUR`, `HKD`, `CNY`, and `JPY`:

```python
from par_model_v2.stochastic import starter_risk_free_curve

curve = starter_risk_free_curve("HKD", valuation_date="2026-05-30")
```

Fixture location:

```text
par_model_v2/stochastic/fixtures/risk_free_curves.json
```

---

## 4. Run Process

### 4.1 Run the Built-In Demonstration

From the repository root:

```powershell
python scripts\run_monthly_projection.py
```

This projects 5-year, 10-year, and 20-year sample policies and prints:

- summary metrics;
- first-year liability cashflows;
- maturity-month liability cashflows;
- asset cashflows by class;
- asset-share projection.

This script is the quickest way to confirm the deterministic model works.

### 4.2 Run One Deterministic Policy Projection

```python
from par_model_v2.projection import (
    AssetPosition,
    ParEndowmentProduct,
    run_full_projection,
)

product = ParEndowmentProduct(
    term_years=10,
    issue_age=35,
    gender="M",
    sum_assured=100_000.0,
    annual_premium=5_000.0,
)

fund_positions = [
    AssetPosition("Govt", 9_000.0, 8_800.0, duration_years=8.5,
                  annual_yield=0.032, average_maturity_years=8.5),
    AssetPosition("Credit_A", 5_750.0, 5_700.0, duration_years=6.2,
                  annual_yield=0.038, average_maturity_years=6.2,
                  credit_rating="A"),
    AssetPosition("Equity", 7_000.0, 7_000.0,
                  annual_yield=0.025, annual_capital_growth=0.060),
    AssetPosition("Cash", 1_250.0, 1_250.0, annual_yield=0.020),
]

result = run_full_projection(
    product=product,
    fund_positions=fund_positions,
    discount_rate_annual=0.030,
    acquisition_expense_pct=0.08,
    renewal_expense_pct=0.04,
    renewal_expense_fixed_monthly=12.50,
    policyholder_share=0.70,
    shareholder_share=0.30,
)

print(result.summary())
```

### 4.3 Validate Model-Point Inputs Before a Portfolio Run

```python
import pandas as pd
from par_model_v2.validation.data_validator import ModelPointValidator

model_points = pd.DataFrame([
    {
        "policy_id": "P001",
        "age": 35,
        "gender": "M",
        "term_years": 10,
        "sum_assured": 100_000.0,
        "premium": 5_000.0,
    }
])

report = ModelPointValidator().validate(model_points)
if not report.passed:
    raise ValueError(report.summary())
```

For portfolio use, map each row to `ParEndowmentProduct`, run
`run_full_projection(...)`, then aggregate `result.summary()` and DataFrames.

### 4.4 Generate Scenarios

```python
from par_model_v2.stochastic import (
    HullWhiteParams,
    Measure,
    ScenarioSet,
    starter_risk_free_curve,
)

curve = starter_risk_free_curve("CNY", valuation_date="2026-05-30")
hw_params = HullWhiteParams(
    initial_short_rate=curve.instantaneous_forward(0.0),
    short_rate_floor=None,
)

q_scenarios = ScenarioSet.generate(
    n=1_000,
    T_months=120,
    measure=Measure.Q,
    hw_params=hw_params,
    initial_curve=curve,
    base_currency="CNY",
    valuation_date="2026-05-30",
    seed=42,
)

print(q_scenarios.summary_stats().head())
```

Use `Measure.Q` for TVOG and `Measure.P` for VaR/ES or ALM-style risk views.

### 4.5 Compute TVOG

```python
from par_model_v2.projection.tvog import TVOGEngine

tvog_result = TVOGEngine(
    product=product,
    scenarios=q_scenarios,
    deterministic_discount_rate=0.030,
).compute()

print(tvog_result.summary())
```

TVOG requires Q-measure scenarios. The engine rejects P-measure scenarios.

### 4.6 Compute VaR / ES

```python
import numpy as np
from par_model_v2.risk.risk_metrics import LossDistribution, RiskMetrics

# Replace this toy array with real per-scenario losses from your reporting process.
losses = np.array([1000.0, 2500.0, -500.0, 4200.0, 1800.0])

loss_distribution = LossDistribution.from_array(
    losses,
    label="Example per-policy loss distribution",
    measure="P",
    currency="CNY",
    unit="per policy",
)

risk_report = RiskMetrics(loss_distribution).full_report(method="empirical")
print(risk_report.to_dataframe())
```

VaR / ES requires P-measure losses. The risk engine rejects Q-measure loss
distributions for ERM reporting.

---

## 5. Output Extraction

### 5.1 Deterministic Projection Outputs

`run_full_projection(...)` returns `FullProjectionResult`.

Use:

```python
summary = result.summary()
liability_df = result.liability.cashflows
asset_df = result.assets.cashflows
asset_summary_df = result.assets.by_class_summary
asset_share_df = result.asset_share.projection
```

Key summary fields:

| Field | Meaning |
| --- | --- |
| `pv_premiums` | present value of premiums |
| `pv_guaranteed_benefits` | PV of guaranteed death and maturity benefits |
| `pv_non_guaranteed_benefits` | PV of non-guaranteed benefits |
| `pv_expenses` | PV of expenses |
| `pv_net_liability` | positive value means liability to policyholders |
| `asset_share_at_maturity` | final asset share |
| `total_shareholder_dist` | total shareholder distribution |
| `total_policyholder_dist` | total policyholder distribution |
| `pv_asset_income` | PV of asset income |

Important DataFrame locations:

| Output | Object path | Useful columns |
| --- | --- | --- |
| Liability cashflows | `result.liability.cashflows` | `month`, `premium`, `death_benefit_guar`, `maturity_benefit_guar`, `surrender_benefit`, `pv_net_cashflow` |
| Asset cashflows | `result.assets.cashflows` | `month`, `Govt_coupon`, `Credit_coupon`, `Equity_dividend`, `Cash_interest`, `running_fund_mv` |
| Asset income summary | `result.assets.by_class_summary` | `asset_class`, `total_coupon_div`, `pv_income` |
| Asset share | `result.asset_share.projection` | `month`, `asset_share_bom`, `investment_return`, `shareholder_dist`, `policyholder_dist`, `asset_share_eom` |

Export example:

```python
from pathlib import Path
import pandas as pd

out = Path("outputs")
out.mkdir(exist_ok=True)

pd.Series(result.summary()).to_csv(out / "projection_summary.csv")
result.liability.cashflows.to_csv(out / "liability_cashflows.csv", index=False)
result.assets.cashflows.to_csv(out / "asset_cashflows.csv", index=False)
result.assets.by_class_summary.to_csv(out / "asset_income_summary.csv", index=False)
result.asset_share.projection.to_csv(out / "asset_share_projection.csv", index=False)
```

### 5.2 Scenario Outputs

`ScenarioSet.generate(...)` returns `ScenarioSet`.

Use:

```python
scenario_df = q_scenarios.data
scenario_stats = q_scenarios.summary_stats()
one_path = q_scenarios.path(1)
traceability = q_scenarios.consumer_traceability("reporting")
wide_view = q_scenarios.consumer_wide_view("reporting")
```

Scenario data columns:

| Column | Meaning |
| --- | --- |
| `scenario_id` | 1-based scenario identifier |
| `month` | month index, starting at 0 |
| `r_short` | annualized short rate |
| `zcb_1y` | one-year zero-coupon bond price proxy |
| `zcb_10y` | ten-year zero-coupon bond price proxy |
| `equity_index` | equity index level |
| `equity_return_1m` | one-month equity return |
| `measure` | `P` or `Q` |

Export example:

```python
q_scenarios.data.to_csv(out / "q_scenarios.csv", index=False)
q_scenarios.summary_stats().to_csv(out / "q_scenario_summary_stats.csv")
```

### 5.3 TVOG Outputs

`TVOGEngine.compute()` returns `TVOGResult`.

Use:

```python
tvog_summary = tvog_result.summary()
scenario_pvs = tvog_result.scenario_pvs
```

Key fields:

| Field | Meaning |
| --- | --- |
| `tvog` | mean stochastic guaranteed PV minus deterministic guaranteed PV |
| `pv_guaranteed_stochastic_mean` | average Q-measure scenario PV |
| `pv_guaranteed_deterministic` | deterministic guaranteed PV |
| `pv_p5`, `pv_p95` | scenario PV distribution percentiles |
| `n_scenarios` | number of scenarios used |
| `is_negative_tvog` | flag for negative TVOG review |

Export example:

```python
pd.Series(tvog_result.summary()).to_csv(out / "tvog_summary.csv")
pd.DataFrame({"scenario_pv": tvog_result.scenario_pvs}).to_csv(
    out / "tvog_scenario_pvs.csv",
    index=False,
)
```

### 5.4 Risk Outputs

`RiskMetrics.full_report()` returns `RiskReport`.

Use:

```python
risk_df = risk_report.to_dataframe()
loss_summary = risk_report.loss_summary
```

Export example:

```python
risk_report.to_dataframe().to_csv(out / "risk_var_es_report.csv", index=False)
risk_report.loss_summary.to_csv(out / "risk_loss_summary.csv")
```

---

## 6. Suggested User Workflow

1. Confirm intended use: deterministic liability view, TVOG, ALM/risk, or
   reporting pack.
2. Prepare model points with required policy fields.
3. Prepare asset positions and key run assumptions.
4. Validate input tables using validators in
   `par_model_v2/validation/data_validator.py`.
5. Run deterministic projection first and inspect `result.summary()`.
6. If stochastic output is needed, generate scenarios with the correct measure:
   `Measure.Q` for TVOG, `Measure.P` for VaR/ES.
7. Extract outputs to CSV using the object paths in Section 5.
8. Archive run assumptions, scenario seed, curve source, model version, and
   exported outputs together.

---

## 7. Minimum Run Metadata to Retain

For each user run, retain:

| Item | Why it matters |
| --- | --- |
| run date/time | reporting and audit trail |
| model version or Git commit | reproducibility |
| product fields | liability basis |
| asset position file or object snapshot | asset basis |
| discount rate and expenses | material assumptions |
| policyholder/shareholder split | surplus distribution basis |
| ESG measure | prevents P/Q misuse |
| scenario count and seed | stochastic reproducibility |
| risk-free curve ID and source ID | market input traceability |
| output export folder | audit retrieval |

When governance is needed, pass a `GovernanceStore` to `run_full_projection` or
`TVOGEngine.compute` and persist the resulting audit trail.

---

## 8. Troubleshooting

| Symptom | Likely cause | What to check |
| --- | --- | --- |
| `term_years` error | unsupported product term | use only `5`, `10`, or `20` |
| TVOG rejects scenarios | wrong measure | regenerate with `Measure.Q` |
| RiskMetrics rejects losses | wrong measure | use `measure="P"` |
| missing package error | Python environment incomplete | install `requirements.txt` |
| stale or surprising output | old assumptions or seed | record model version, seed, and curve ID |
| negative TVOG | possible parameter/measure issue | verify Q-measure, scenario count, curve, and rates |

---

## 9. Related User Documents

| Document | Use |
| --- | --- |
| `docs/MODEL_USAGE_GUIDE.md` | broader background and assumptions reference |
| `docs/ASSUMPTIONS_REGISTER.md` | assumption table catalogue |
| `docs/ESG_PROCESS_DOCUMENTATION.md` | stochastic process and measure rules |
| `docs/ESG_STARTER_CURVE_FIXTURES.md` | starter curve governance and limitations |
| `docs/MODEL_RISK_CARD.md` | limitations, production gates, and restrictions |
| `docs/GOVERNANCE_FRAMEWORK.md` | model governance expectations |

