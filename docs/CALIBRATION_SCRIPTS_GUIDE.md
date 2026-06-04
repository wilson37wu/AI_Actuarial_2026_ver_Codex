# Calibration Scripts Guide — Phase 12

**Module:** `scripts/calibration/`
**Phase:** 12 — Governance, Calibration, and Educational Packaging
**Standards:** SOA ASOP 56 §3.4, SOA ASOP 25 §3.3, IA TAS M §3.5

---

## Overview

The calibration scripts package provides four standalone modules and one
orchestrator that together demonstrate end-to-end parameter calibration
for every ESG and liability component of the Phase 12 educational model.

All market data inputs are **illustrative placeholders**. In production,
replace the synthetic data in each script with live feeds and ensure
Assumption Owner sign-off per IA TAS M §3.5 before use.

---

## Scripts

| Script | Module | Key Classes / Functions |
|--------|--------|------------------------|
| `calibrate_curves.py` | Yield curve / HW1F | `HullWhiteCalibrator`, `calibrate_all_curves()` |
| `calibrate_equity.py` | Regional equity GBM | `GBMCalibrator`, `calibrate_all_equity()` |
| `calibrate_credit.py` | Credit spreads / private assets | `fit_nelson_siegel()`, `calibrate_credit_spreads()` |
| `calibrate_liabilities.py` | HK PAR liability assumptions | `build_mortality_table()`, `calibrate_lapse_curve()`, `calibrate_bonus_assumptions()` |
| `run_all_calibrations.py` | Orchestrator | `run_all()` |

---

## Quick Start

```bash
# Install dependencies (NumPy, SciPy, pandas already in requirements.txt)
pip install -r requirements.txt

# Run individual modules
python scripts/calibration/calibrate_curves.py
python scripts/calibration/calibrate_equity.py
python scripts/calibration/calibrate_credit.py
python scripts/calibration/calibrate_liabilities.py

# Run all modules and write reports
python scripts/calibration/run_all_calibrations.py --output-dir outputs/calibration
```

---

## 1. Yield Curve Calibration (`calibrate_curves.py`)

**Markets:** USD, EUR, HKD, CNY, JPY

**Method:** Hull-White 1-Factor (HW1F) swaption calibration.
Minimises the weighted sum of squared normal-vol (Bachelier) errors across
an ATM swaption grid using L-BFGS-B (scipy.optimize.minimize).

```
L(a, σ_r) = Σᵢ wᵢ × [σ_model(a, σ_r, Tᵢ, Sᵢ) − σ_market,i]²
```

**Key parameters calibrated:**
- `a` — mean-reversion speed
- `σ_r` — short rate volatility

**Input data (production):** ATM payer swaption implied vols (normal / Bachelier
convention) from Bloomberg / Refinitiv for each tenor grid, reviewed by
the Rates Desk.

**SOA ASOP 56 §3.4 references:**
- Calibration loss function is documented in `docs/PARAMETER_CALIBRATION_METHODOLOGY.md §5`
- Convergence tolerance and bounds are explicit in `HullWhiteCalibrationInputs`

**IA TAS M §3.5 requirement:**
- Calibrated parameters require Assumption Owner sign-off before use in reserves
- Parameter snapshot is written to JSON for audit trail

---

## 2. Equity GBM Calibration (`calibrate_equity.py`)

**Markets:** US (S&P 500), EU (Euro Stoxx), HK/CN (HSI/CSI), JP (TOPIX), Asia ex-JP (MSCI)

**Method:** GBM calibration blending realised historical volatility with
option-implied ATM vol.

**Credibility weighting (SOA ASOP 25 §3.3):**
```
σ_S = 0.60 × σ_implied + 0.40 × σ_historical
ERP = raw_ERP − 0.70%  (survivorship-bias adjustment per §6.4)
```

**Key parameters calibrated:**
- `σ_S` — equity volatility
- `ERP` — equity risk premium (P-measure)
- `δ` — dividend yield
- `ρ` — rate–equity correlation

**Input data (production):** Daily log-returns from approved data vendor
(e.g., Bloomberg equity history), minimum 5 years, reviewed by the
Investment Team.

---

## 3. Credit Spread Calibration (`calibrate_credit.py`)

**Asset classes:** IG (AAA–BBB), HY (BB–CCC), private credit, PE, infrastructure

**Method:** Nelson-Siegel functional form fitted to OAS term structures
using scipy `least_squares` (TRF method):
```
OAS(T) = b₀ + b₁·[(1−e^(−T/τ))/(T/τ)] + b₂·[(1−e^(−T/τ))/(T/τ) − e^(−T/τ)]
```

**Private asset illiquidity premia** are tabulated assumptions subject to
annual governance review by the Investment Risk Committee.

**Stress scenarios (ERM):**
- CS01: Moderate spread widening (+50/+150 bps IG/HY)
- CS02: Severe spread widening GFC-like (+200/+600 bps)
- CS03: IG downgrade wave (20% BBB → HY migration)

---

## 4. Liability Assumption Calibration (`calibrate_liabilities.py`)

**Products:** HK cash dividend PAR, HK reversionary bonus PAR

### 4a. Mortality

- **Base table:** HKML 2016 ultimate insured lives (IA Hong Kong)
- **Improvement scale:** 1.5% p.a. from 2016 (illustrative CMI-style)
- **Credibility blend (SOA ASOP 25 §3.3):** 60% company A/E / 40% industry
- **Company A/E input:** Replace 90% placeholder with actual experience study

### 4b. Voluntary Lapse

Exponential decay model:
```
L(t) = (L₀ − L_floor) × exp(−k × t) + L_floor
```
Fitted to synthetic HK market duration-lapse observations.
Shock scenarios per **IA(HK) GL16**: 1.5x and 2.5x base.

### 4c. Bonus / Dividend Declaration

Supportable range derived from deterministic asset-share projection:
```
Net accumulation = Investment return − Expense ratio − Mortality drag
Effective max = max_supportable − Regulatory margin
```
**IA(HK) GL16** bonus supportability evidence produced for both products.

---

## Outputs

Running `run_all_calibrations.py --output-dir outputs/calibration` produces:

```
outputs/calibration/
    curve_calibration.json          ← HW1F parameters for 5 markets
    equity_calibration.json         ← GBM parameters for 5 markets
    credit_calibration.json         ← NS spread curves + private asset assumptions
    liability_calibration.json      ← Mortality, lapse, bonus assumptions
    combined_calibration_snapshot.json  ← Governance-ready combined snapshot
    CALIBRATION_SUMMARY.md          ← Human-readable summary report
```

---

## Governance Checklist

Before using calibrated parameters in production:

- [ ] Replace all synthetic market data with live vendor data
- [ ] Run full calibration cycle and review fit diagnostics
- [ ] Assumption Owner reviews and signs CALIBRATION_SUMMARY.md
- [ ] Model Validator reviews combined_calibration_snapshot.json
- [ ] Record effective date and next review date in snapshot
- [ ] Update `docs/ASSUMPTIONS_REGISTER.md` with parameter changes
- [ ] Create git tag: `calibration-YYYY-MM-DD`

---

## Standards Cross-Reference

| Standard | Requirement | Where Addressed |
|----------|-------------|-----------------|
| SOA ASOP 56 §3.4 | Calibration methodology documented | All four scripts, this guide |
| SOA ASOP 56 §3.5 | Fit diagnostics and validation | RMSE/max-error tables in each script |
| SOA ASOP 25 §3.3 | Credibility weighting | `calibrate_equity.py`, `calibrate_liabilities.py` |
| IA TAS M §3.5 | Assumption sign-off | Governance checklist above |
| IA(HK) GL16 | Bonus supportability | `calibrate_liabilities.py §3` |
| ERM | Stress scenario coverage | `calibrate_credit.py §5` |
