# Deep Dive — ESG Calibration & Live Market Data (MR-001)

**Document ID:** `DEEP-DIVE-ESG-CALIBRATION-2026`
**Date:** 2026-06-23
**Subsystem:** `par_model_v2/calibration/*`, `par_model_v2/stochastic/*`
**Blocking model risk:** MR-001 (placeholder parameters) · Production gate **G-02** (HW1F calibrated to market, not placeholders)
**Companion docs:** `INDUSTRY_BENCHMARK_REVIEW.md`, `DESIGN_ASSET_ESG_COUPLING.md`

---

## 1. Why this subsystem first

Calibration is the single highest-leverage Tier-1 action. Every downstream number — TVOG, VaR/TVaR,
SCR, dynamic-lapse response — inherits its credibility from the ESG parameters. Today those parameters
are **placeholders calibrated to synthetic fixtures**, which is the root cause of the "not cleared for
production" status. Fixing it unblocks G-02 and removes the MR-001 critical risk.

**Good news from the code review:** the hard part is already built. The calibration *machinery* is
implemented and tested; what is missing is narrow and mechanical — concrete **live data adapters** and
calibration of the **non-rate drivers**. This deep dive pinpoints exactly what to add and where.

---

## 2. What already exists (and works)

| Component | Location | Status |
|---|---|---|
| Abstract market-data interface | `calibration/market_data_source.py:67` `SwaptionMarketDataSource(ABC)` | ✅ clean extension point |
| Live loader (fetch→validate→inputs+lineage) | `market_data_source.py:162` `LiveSwaptionDataLoader.load()` | ✅ complete, source-agnostic |
| Input validation | `market_data_source.py:212` `_validate()` (≥8 active quotes, positive vols, curve sanity, r0 bounds) | ✅ ASOP 56 §3.4 |
| HW1F calibrator (L-BFGS-B) | `calibration_framework.py:685` `HullWhiteCalibrator.calibrate()` | ✅ **fully implemented**, lazy-scipy |
| Semi-analytic swaption vol | `calibration_framework.py:628` `swaption_model_normal_vol()` | ✅ |
| Goodness-of-fit (RMSE/max-err bps) | `calibration_framework.py:757` `goodness_of_fit_table()` | ✅ |
| G-02 production gate logic | `market_data_source.py:251` `evaluate_g02_gate()` (not-placeholder AND RMSE ≤ 25 bps) | ✅ |
| GBM equity calibrator | `calibration_framework.py:804` `GBMCalibrator.compute_historical_volatility()` | 🟡 historical σ only |
| CIR++ credit calibrator | `calibration/phase18_cir_calibration.py` (OLS on OAS) | 🟡 single-path OLS |
| G2++ swaption pricer | `stochastic/g2pp_swaption.py` (Brigo-Mercurio, Gauss-Legendre) | 🟡 pricer, not wired to surface calibration |
| Data lineage record | `market_data_source.py:44` `DataLineageRecord` + `ParameterSnapshot` | ✅ attachable to sign-off |

**Key correction to the in-code narrative.** The module docstring at
`calibration_framework.py:45` still says *"calibrate() raises NotImplementedError until Phase 4."*
That note is **stale** — `HullWhiteCalibrator.calibrate()` is implemented (lines 685–755) and returns
`is_placeholder=False`. Fix the docstring so reviewers do not mis-scope the work (see §6, fix F0).

---

## 3. The actual gap

Only three things stand between the current state and a passing G-02:

1. **No concrete *live* `SwaptionMarketDataSource`.** The only implementation is
   `FileBasedSwaptionSource` (`market_data_source.py:93`), which reads educational JSON fixtures and
   stamps `checksum_sha256 = "educational_fixture_no_checksum"` (line 139). The abstract methods
   (`fetch_swaption_quotes`, `fetch_spot_curve`, `fetch_initial_short_rate`, `fetch_calibration_date`,
   `fetch_regulatory_rate_cap`, `build_lineage_record`) need a real-feed implementation. The header
   says it plainly: *"File-based fixtures are educational proxies. Replace with credentialled live-API
   fetches and re-run sign-off workflow before regulatory use."* (`market_data_source.py:21`).

2. **Non-rate drivers are not calibrated to market.** Equity (GBM) has only historical-σ
   (`GBMCalibrator`, no implied-vol surface fit); credit (CIR++) is single-path OLS rather than
   MLE/Kalman; **FX has no calibrator at all** (parameters are placeholders in `esg_process.py`).
   G-02 today only checks HW1F — the gate set must be extended to cover every priced driver.

3. **No closed calibration→sign-off→snapshot loop run on real data.** `DataLineageRecord` and the
   GovernanceStore `ChangeRecord` workflow exist, but no run has produced a non-placeholder
   `ParameterSnapshot` from credentialled data with an Assumption-Owner sign-off
   (`calibration_framework.py:58`).

Everything else (optimiser, validation, GoF, gate, lineage) is reusable as-is.

---

## 4. Benchmark context (Prophet / AXIS / Moody's ESG)

| Dimension | Commercial standard | This model | Action |
|---|---|---|---|
| Rate calibration | Full swaption/cap surface, multi-curve, smile | ATM normal-vol grid, single curve, HW1F (G2++ pricer ready) | Wire G2++ surface fit; add smile later |
| Equity calibration | Historical *and* option-implied vol; term structure | Historical σ only | Add implied-vol source + fit |
| Credit | Hazard-rate / intensity calibrated to CDS/OAS term structure | CIR++ OLS, single path | Upgrade to MLE/Kalman, term structure |
| FX | Calibrated vol + correlation, CIP-consistent | Placeholder | Add FX calibrator + martingale (CIP) test |
| Data governance | Vendor feed, lineage, dated snapshots | Lineage *scaffold* present, fixtures only | Implement live adapter + sign-off loop |
| Vendor benchmark | Moody's/B&H deliver pre-calibrated, validated economies | DIY calibration | Optional: ingest a vendor scenario file via `ESGAdapter` |

A pragmatic shortcut worth noting: `esg_adapter.py:159` `ESGAdapter.load()` already ingests an external
scenario table against a fixed schema. A firm could **bypass DIY calibration entirely** by feeding a
vendor (Moody's/Conning) scenario file through that adapter — a legitimate, common industry pattern and
a fast route to market-consistent scenarios while the in-house calibrators mature.

---

## 5. Concrete, code-level fixes (prioritised)

> Each fix names the file, the insertion point, and the acceptance check. They are ordered so that each
> builds on the last and so G-02 can flip to PASS at fix **F3**.

### F0 — Correct the stale calibration status note *(5 min, do first)*
- **File:** `calibration_framework.py:38-47`.
- **Change:** Replace the "calibrate() raises NotImplementedError until Phase 4" text with the true
  state: HW1F implemented; remaining work is live data adapters + non-rate drivers.
- **Why:** Prevents reviewers and future contributors from re-implementing what exists.

### F1 — Implement a live `SwaptionMarketDataSource` *(the core unblock)*
- **File:** new `calibration/live_market_data_source.py`.
- **Implement:** subclass `SwaptionMarketDataSource` (abstract methods at `market_data_source.py:67-90`)
  for CNY and HKD. Pull ATM swaption normal vols, the spot/zero curve, and r0 from the firm's market-data
  service (or a dated, checksummed snapshot file with a *real* SHA-256, not the educational sentinel at
  line 139).
- **Reuse:** feed instances straight into `LiveSwaptionDataLoader(source).load()` — no loader changes
  needed; `_validate()` (line 212) already enforces ≥8 quotes, positive vols, curve and r0 sanity.
- **Acceptance:** `build_lineage_record()` returns a real checksum and provider/as-of metadata;
  `load()` succeeds for both markets.

### F2 — Run HW1F calibration on live inputs and persist a signed snapshot
- **Flow:** `LiveSwaptionDataLoader(source).load()` → `HullWhiteCalibrator(inputs).calibrate()`
  (`calibration_framework.py:685`) → `CalibrationResult` with `is_placeholder=False` and `swaption_rmse_bps`.
- **Persist:** write a `ParameterSnapshot` + `DataLineageRecord`, and open a GovernanceStore
  `ChangeRecord` (DRAFT→PEER_REVIEW→OWNER_REVIEW→APPROVED) per `calibration_framework.py:58`.
- **Acceptance:** RMSE ≤ 25 bps (HW1F achievable threshold, `market_data_source.py:261`); snapshot
  archived; ChangeRecord at OWNER_REVIEW or APPROVED.

### F3 — Flip G-02 to PASS, on real evidence
- **File:** call `evaluate_g02_gate(...)` (`market_data_source.py:251`) with the live
  `is_placeholder=False` and RMSE for **both** CNY and HKD.
- **Acceptance:** `ProductionGateStatus.status == "PASS"` with lineage evidence; MR-001 downgraded.

### F4 — Equity (GBM) market calibration
- **File:** `calibration_framework.py:804` `GBMCalibrator` — extend beyond `compute_historical_volatility()`.
- **Add:** an implied-vol source (CSI 300 / HSI listed options) and a fit of `equity_vol` to ATM implied
  vol (P-measure σ from history, Q-measure σ from implied). Calibrate the rate-equity correlation
  (`esg_process.py:1047`) from joint history.
- **Acceptance:** Q-measure equity martingale test passes (closes `ESG-LIM-08-09`,
  `ESG_MODEL_LIMITATIONS_AND_UPGRADE_PATH.md`); historical-vs-implied σ documented.

### F5 — Credit (CIR++) upgrade and FX calibrator
- **Credit:** replace single-path OLS (`phase18_cir_calibration.py`) with MLE or Kalman-filter estimation
  on the OAS term structure; check the Feller condition post-fit.
- **FX:** add an `FXCalibrator` (currently absent) fitting lognormal vol + rate-FX correlation; add a
  covered-interest-parity (CIP) martingale check for Q-measure FX.
- **Acceptance:** each priced driver has a non-placeholder snapshot and a measure-appropriate validation.

### F6 — Extend the gate set beyond HW1F
- **File:** generalise `evaluate_g02_gate` (or add sibling gates) so G-02 requires **every priced
  driver** non-placeholder, not just rates. Today a green G-02 with placeholder equity/credit/FX would
  overstate readiness.
- **Acceptance:** a single "calibration readiness" gate aggregates per-driver placeholder + GoF status.

### F7 — Vendor-scenario fast path (optional, parallel)
- **File:** document and test ingesting an external (Moody's/Conning) scenario file via
  `ESGAdapter.load()` (`esg_adapter.py:202`).
- **Acceptance:** an end-to-end TVOG run on vendor scenarios, with measure and schema validated; gives a
  market-consistent route while in-house calibrators mature.

---

## 6. Validation & evidence to attach (per ASOP 56 / IA TAS-M)

- **Calibration report** per driver: instruments used, as-of date, optimiser, GoF (RMSE/max-error bps),
  parameter bounds, warm start. The HW1F path already emits this via `goodness_of_fit_table()` and
  `CalibrationResult.notes`.
- **Backtest on real history** (closes G-09): drive `calibration/backtesting.py` (Kupiec PoF) with the
  *real* P-measure series rather than the synthetic 12-month fixture.
- **Market-consistency** (Q-measure): existing ZCB-martingale validator for rates; add equity and FX
  martingale checks (F4/F5) to close `ESG-LIM-08-09`.
- **Lineage + sign-off:** every snapshot carries a `DataLineageRecord` (real checksum) and an
  Assumption-Owner `ChangeRecord`.

---

## 7. Effort and sequencing

| Fix | Effort | Unblocks |
|---|---|---|
| F0 docstring | trivial | reviewer clarity |
| F1 live source | **medium** (depends on data-feed access) | F2, F3 |
| F2 calibrate + snapshot | small (machinery exists) | F3 |
| F3 G-02 PASS | trivial | MR-001 downgrade |
| F4 equity | medium | Q-equity martingale, ESG-LIM-08-09 |
| F5 credit+FX | medium | full driver coverage |
| F6 gate set | small | honest readiness signal |
| F7 vendor path | small–medium | fast market-consistent scenarios |

**Critical path to G-02:** F1 → F2 → F3. The rest (F4–F6) is required for *full* market consistency
across all drivers and to avoid an over-stated gate.

---

## 8. Takeaway

This subsystem is **far closer to production than the "placeholder" label suggests**: the optimiser,
validation, GoF, gate logic, and lineage scaffold are all built and tested. The remaining work is a
**concrete live data adapter (F1)** plus **calibration of the non-rate drivers (F4–F5)** and an
**honest, all-driver gate (F6)**. With data-feed access, the critical path to flipping G-02 and
downgrading MR-001 is small. The optional vendor-scenario path (F7) can deliver market-consistent
scenarios immediately while the in-house calibrators are finished.
