# Economic Scenario File Format — user-supplied ESG input

**Schema ID:** `esg-user-scenarios-1.0`
**Owner directive:** 2026-07-08 (KCW, interactive session) — allow user-input
economic scenario FILES alongside the built-in HW1F + GBM scenario generator.
**Status:** format spec APPROVED-FOR-BUILD by owner conventions choices
(2026-07-08: decimal annual spot zeros; annual equity total return; tenor grid
to 30Y). Loader/GUI/engine integration tracked as roadmap items ES-1..ES-3.
User scenario files are SCENARIO INPUTS and remain **UNSIGNED** pending Model
Owner approval of the generating source; every run records the file digest.

---

## 1. Files

| File | Required | Purpose |
|---|---|---|
| `economic_scenarios.csv` | yes | the scenario table (this spec §2) |
| `economic_scenarios_manifest.json` | yes | conventions declaration + integrity digest (§3) |

Designed size: **1,000 scenarios × 100 projection years** (100,000 data rows,
~13 MB). The loader accepts any `n_scenarios` ≥ 100 declared in the manifest;
`projection_years` must be exactly 100 (engine horizon).

## 2. CSV layout — `economic_scenarios.csv`

UTF-8, comma-separated, ONE header row, no comment lines, `.` decimal point,
no thousands separators.

**Columns (15, fixed order and exact header spelling):**

```
scenario,year,3M,6M,9M,1Y,2Y,3Y,5Y,7Y,10Y,15Y,20Y,30Y,EQ_RETURN
```

| Column | Type | Meaning |
|---|---|---|
| `scenario` | int | scenario number, `1..N` contiguous, no gaps |
| `year` | int | projection year, `1..100`; each (scenario, year) pair appears exactly once |
| `3M … 30Y` (12 tenors) | decimal | **zero-coupon spot rates, annually compounded, decimals** (`0.032` = 3.2%), for the curve prevailing at the **end of projection year `year`** |
| `EQ_RETURN` | decimal | **equity TOTAL return** (price + reinvested dividends) earned **over projection year `year`** (`0.085` = +8.5%) |

Rows sorted `scenario` ascending, then `year` ascending.

Tenor grid: `3M 6M 9M 1Y 2Y 3Y 5Y 7Y 10Y 15Y 20Y 30Y`. Beyond 30Y the engine
extrapolates flat-forward, consistent with current HW1F usage.

**Bond asset class:** no bond-return column — bond asset-class returns are
DERIVED from the yield-curve columns by the engine (carry + duration
revaluation, CF-1 asset mechanics), which keeps the file free of internal
inconsistency between curves and bond returns.

Example rows (illustrative numbers):

```
scenario,year,3M,6M,9M,1Y,2Y,3Y,5Y,7Y,10Y,15Y,20Y,30Y,EQ_RETURN
1,1,0.0182,0.0190,0.0196,0.0201,0.0214,0.0225,0.0243,0.0257,0.0272,0.0288,0.0296,0.0305,0.0812
1,2,0.0175,0.0184,0.0191,0.0197,0.0211,0.0223,0.0244,0.0259,0.0276,0.0293,0.0301,0.0309,-0.0431
2,1,0.0190,0.0197,0.0203,0.0208,0.0220,0.0231,0.0249,0.0262,0.0277,0.0292,0.0300,0.0308,0.1247
```

## 3. Manifest — `economic_scenarios_manifest.json`

```json
{
  "schema": "esg-user-scenarios-1.0",
  "n_scenarios": 1000,
  "projection_years": 100,
  "basis": "risk_neutral",
  "rate_convention": {"type": "zero_coupon_spot", "compounding": "annual",
                       "units": "decimal", "day_count": "ACT/365F"},
  "equity_convention": {"type": "annual_total_return", "units": "decimal"},
  "currency": "CNY",
  "source": "<generating ESG name + version + calibration date>",
  "created_utc": "2026-07-08T00:00:00Z",
  "csv_sha256": "<sha256 hex of economic_scenarios.csv>"
}
```

`basis` is **REQUIRED** and must be `"risk_neutral"` or `"real_world"` — it
declares the probability measure of the file. Basis-appropriate use is
enforced at run time (§5).

## 4. Validation rules (ES-1 loader, fail-loud with row/column reported)

1. Header exactly as §2 (names, order, count).
2. `scenario` contiguous `1..n_scenarios`; `year` complete `1..100` per
   scenario; no duplicates; rows sorted.
3. Every cell numeric; no blanks/NaN/inf.
4. Plausibility bounds: rates in `[-0.05, 0.30]`; `EQ_RETURN` in
   `[-0.99, 3.00]`.
5. Manifest present, parseable, schema/units/compounding as declared here;
   `csv_sha256` matches the file byte-for-byte.
6. Loader echoes a summary card (p5/median/p95 of the 10Y rate and
   `EQ_RETURN` by projection year 1/10/50/100) for eyeball verification, and
   surfaces the UNSIGNED banner.

## 5. Interaction with the built-in ESG (ES-3 scope)

* Run configuration gains `scenario_source`: `"model"` (default — governed
  HW1F + GBM, bit-identical to current runs) or `"user_file"`.
* Measure guard: `risk_neutral` files are usable for valuation paths
  (TVOG/SCR inner scenarios); `real_world` files for P-measure diagnostics
  (GD-1 path fans, stress overlays). A mismatch is a validator ERROR;
  override requires an approved deviation record (C-ROSS discipline).
* Monthly engine mapping (documented at ES-3): curves are interpolated to the
  monthly grid within each year; the annual equity return is spread
  geometrically over 12 months: `(1+R)^(1/12)-1`.
* Governance trail: run artifacts record `csv_sha256`, manifest content and
  the UNSIGNED state — the file is a scenario input, never a governed
  calibration.
* C-ROSS scenario-count note: the governed stochastic run standard is ≥2,000
  scenarios; a 1,000-scenario file is accepted for diagnostics but the
  validator WARNS when a `user_file` run is used for capital figures below
  the C-ROSS count.

## 6. Roadmap items

| Item | Scope | Status |
|---|---|---|
| ES-1 | This spec + validating loader (`par_model_v2/stochastic/user_scenarios.py`) + template + tests | DONE (2026-07-08: spec + loader + 41 tests) |
| ES-2 | GUI: /scenarios upload page — validate, preview fan chart, persist with digest | DONE (2026-07-08: `igui_scenarios.py`, /scenarios + /scenario-status + validate/save routes, 19 tests) |
| ES-3 | Engine integration: `scenario_source` selector, measure guard, governance trail | OPEN |
