# Continuous Industry-Grade Improvement Roadmap

**Document ID:** `CONT-IMPROVEMENT-ROADMAP`
**Created:** 2026-07-03
**Owner:** Model Owner (KCW) — executed by Claude Cowork scheduled task `actuarial-model-daily-improvement`
**Cadence:** Daily, 14:00 local (06:00 UTC — the Claude slot per `AGENT_COORDINATION.md`)
**Governing protocol:** `AGENT_COORDINATION.md` (lock, one task per cycle, throwaway-clone git, push to `main`)

---

## 1. Objective

Advance the PAR Endowment Stochastic ALM & TVOG model from "structurally complete, NOT production ready" toward industry-grade production quality, one governed increment per cycle. Every cycle must leave `main` with: passing tests, updated documentation, a governance note, and no regression to governed headline figures without explicit sign-off.

## 2. Cycle Contract (every scheduled run)

1. Integrate: fresh throwaway clone of `origin/main` (never git-write against the mounted `.git`).
2. Lock: `agent_lock.py preflight` → yield if held; else `acquire`.
3. Select ONE item: the highest-priority `OPEN` item in §4 backlog (or the `in_progress` item in `.claude-dev/MODEL_DEV_STATE.json` if the auto-dev state machine has one).
4. Implement + test: code, unit tests, and self-checks must be GREEN before commit.
5. Document: update the relevant `docs/` card, this roadmap's §5 log, and a uniquely named `docs/cycle_status/LATEST_CYCLE_STATUS_<date>_<id>.md`.
6. Push to `main` (fetch-rebase, retry ≤3×), release lock.
7. If blocked (owner sign-off required, data unavailable), mark item `BLOCKED(reason)` in §4, pick the next item, and surface the blocker to the Model Owner in the run summary.

## 3. Industry-Grade Quality Bar

Each improvement is judged against these standards (traceable in `docs/SOA_ASSUMPTIONS_DOCUMENT.md`, `docs/IA_VALIDATION_REQUIREMENTS.md`, `docs/GOVERNANCE_FRAMEWORK.md`):

- SOA ASOP 56 (modeling), ASOP 25 (credibility), ASOP 7 (cashflow testing)
- IA (HK) TAS M — model governance, independent review, change control
- CBIRC C-ROSS — scenario count (≥2,000), 3.0% discount cap, stress suite
- Reproducibility: seed policy, parameter snapshots, SHA-256 audit trail on every run

## 4. Prioritised Backlog

### 4.0 OWNER-DIRECTED GUI Run-Console Track (directive 2026-07-03, KCW)

Owner directive (2026-07-03, interactive session): build a comprehensive GUI so users configure and trigger calculation runs and view outputs entirely in the GUI — eliminate any need to open .py files. Owner-selected architecture: **local Python web server** (Flask/FastAPI, launched via `python -m par_model_v2.gui` + a Windows launcher script); browser GUI posts run requests, shows progress, renders results in-page.

**This track is COMPLETE (GUI-1..GUI-4 all DONE 2026-07-03); priority reverts to the general backlog (§4.1).** One phase per cycle. It does NOT constitute sign-off for the separately owner-gated Phase 38 Task 3 (`ui_app.html` native-tab cutover / sha256 re-baseline), which stays gated.

| # | Item | Definition of done | Status |
|---|------|--------------------|--------|
| GUI-1 | Run-console server skeleton + core stochastic run: background job execution with progress endpoint, results rendered in GUI. Discovery: the Phase IGUI stack already provided input pages, validation gate, launchers, and a synchronous run; GUI-1 delivered the missing async layer (JobManager, /execute-async, /jobs/<id>, /jobs, polling run page) on the existing stdlib-only server (kept over Flask/FastAPI: zero new deps, same architecture class - local web server) | User can launch, configure, run, watch progress, and read results with zero .py editing | DONE(2026-07-03, see §5) |
| GUI-2 | Sensitivities & stress in GUI: /stress console, 7-item input-level catalogue (re-validated + re-gated per stress, isolated output dirs), base-vs-stress delta table, deterministic Phase 9 asset-stress panel | Stress results in GUI with base-vs-stress deltas | DONE(2026-07-03, see §5) |
| GUI-3 | Calibration runs in GUI: trigger HW1F/GBM calibration via live market-data pipeline (roadmap #1), fit diagnostics (SSE, convergence, parameter card) displayed; UNSIGNED flag surfaced | Calibration runnable + diagnosable from GUI | DONE(2026-07-03, see §5) |
| GUI-4 | Run history & compare: persisted run registry (id, timestamp, inputs hash, seed, headline outputs), list/open past runs, side-by-side diff of two runs | Reproducible run registry browsable in GUI | DONE(2026-07-03, see §5) |
| GUI-5 | One-click Save & RUN on the Run Controls page (owner request 2026-07-03, interactive): save → optional governed-default auto-fill of missing sections → Task-6 gate → async engine run with in-page progress + results links | User kicks off the calculation from the first screen with one button | DONE(2026-07-03, see §5) |

Standing constraints: runs executed through the GUI must keep the existing governance trail (seed policy, parameter snapshots, SHA-256 audit) — the GUI is a front-end to the governed engine, never a bypass. Governed headline figures remain untouched except where an item explicitly covers them.

### 4.0c OWNER-DIRECTED Cash-Flow Projection Set Track (directive 2026-07-03, KCW)

Owner directive (2026-07-03, interactive): a NEW OUTPUT SET with liability cash flows by product class x type (premium, expense, benefits split guaranteed/non-guaranteed across death/surrender/maturity + cash dividend; >=6 buckets for CD products) and asset cash flows AND balances by asset class, monthly + yearly to 100 years. Owner-selected basis: deterministic central. Owner-selected delivery: JSON + CSV + GUI tab.

| # | Item | Definition of done | Status |
|---|------|--------------------|--------|
| CF-1 | Projection engine + artifacts: `cashflow_projection_set.py` (3 product classes, 9 liability buckets, asset CF+balances, monthly 1..1200 + yearly 1..100, JSON+6 CSVs, inputs digest, UNSIGNED declaration-scale note); conventions regression-tested against the legacy per-product engine | Engine + files + tests GREEN | DONE(2026-07-03, see §5) |
| CF-2 | Run integration: /save-run & execute_run attach the CF set to run_output + run registry; stale-set guard (inputs digest match) | CF set produced with every GUI run | OPEN |
| CF-3 | GUI tab: yearly view + monthly drill-down per product class / asset class, CSV downloads, UNSIGNED banner | CF set browsable in GUI | DONE(2026-07-03, see §5) |

### 4.0e OWNER-DIRECTED GUI Stepwise-Detail Track (directive 2026-07-07, KCW)

Owner directive (2026-07-07, interactive): enrich the GUI to output and display MORE DETAILED STEPWISE CALCULATION in general - economic scenario paths, asset return paths, asset cash flow by asset class, liability cash flow by guaranteed / non-guaranteed, etc. Delivery pattern per item: engine artifact (JSON+CSV, digest-cached, UNSIGNED note) + self-contained GUI page/section (inline-SVG, zero external refs). Diagnostic overlays only - governed headline figures untouched.

| # | Item | Definition of done | Status |
|---|------|--------------------|--------|
| GD-1 | Scenario-path detail set + /paths GUI page: real-world (P) HW1F short-rate + correlated GBM equity paths on the SAVED run seed; per-asset-class monthly-return & cumulative-index percentile fans (p5/25/50/75/95) with CF-1 class mechanics; sample-path overlays; JSON+6 CSVs digest-cached; CF-3 liability chart gains guaranteed vs non-guaranteed benefit series | Paths browsable in GUI, artifacts on disk, tests GREEN | DONE(2026-07-07, see §5) |
| GD-2 | Stepwise liability drill-down: per-model-point / per-product-class bucket-level cash-flow inspector (pick a policy/class, see month-by-month premium/expense/benefit build-up incl. gtd/non-gtd split) | Policy-level stepwise table in GUI | OPEN |
| GD-3 | Stepwise run-result decomposition: surface per-driver standalone SCR paths / TVOG build-up steps from the run artifacts in the results page (calculation waterfall view) | Waterfall of headline build-up in GUI | OPEN |
| GD-4 | Scenario-path detail bound to EXECUTED runs: persist the GD-1 set with each run (run registry attachment, like CF-2) so paths shown match the run actually executed, not just current inputs | Per-run path detail in history/compare | OPEN |

### 4.0d OWNER-DIRECTED Portfolio Construction Track (directive 2026-07-03, KCW)

Owner directive: flexible input construction - asset classes by type with mix/SAA, and liability product templates (e.g. short vs long term par) composable into the portfolio.

| # | Item | Definition of done | Status |
|---|------|--------------------|--------|
| PC-1 | Construction layer + GUI: `portfolio_construction.py` (asset strategy with SAA weights deriving the balance sheet + fund mechanics; product catalogue parameterised over the three mechanic families; composer validation incl. term ranges and the illiquid-share engine rule), CF-engine integration (per-product output classes, catalogue rates, SAA mechanics), `/portfolio` GUI page, loader-revalidated save | Construct + save + gate + run + cashflows end-to-end from composed inputs | DONE(2026-07-03, see §5) |
| PC-2 | Extend mechanic families (whole-life par, term assurance, annuity) + per-product expense/decrement overrides | New families runnable end-to-end | OPEN |

### 4.1 General backlog


Priority = (regulatory gate) > (model-risk register CRITICAL) > (accuracy) > (capability expansion). Status values: `OPEN`, `IN_PROGRESS`, `BLOCKED(reason)`, `DONE(date, commit)`.

| # | Item | Maps to | Definition of done | Status |
|---|------|---------|--------------------|--------|
| 1 | Live market-data pipeline: CNY yield curve + CSI 300 loaders with schema validation and cached snapshots | MR-006 | Loader module + fixtures + tests; `docs/ESG_CALIBRATION_DATA_INTERFACES.md` updated | DONE(2026-07-03, see §5) |
| 2 | Execute HW1F swaption calibration on live/proxy quote set; parameter card with fit diagnostics | MR-001, MR-008 | `calibrate()` runs end-to-end; SSE/convergence report; params flagged UNSIGNED pending owner approval | OPEN |
| 3 | CBIRC 3.0% discount-cap remediation: config default ≤3.0% + deviation record for any override | MR-002 | Validator ERROR (not WARNING) above cap without an approved ChangeRecord | OPEN |
| 4 | Dynamic lapse: rate-differential lapse response function with bounded elasticity + sensitivity tests | MR-003 | Model + tests + `PHASE13_DYNAMIC_LAPSE_REPORT.md` refresh; TVOG delta quantified | OPEN |
| 5 | Scenario adequacy at 2,000+ scenarios: convergence study 500→1,000→2,000→5,000 with CI bands | C-ROSS gap #6 | Convergence report; runtime benchmark; recommendation memo | OPEN |
| 6 | Backtest on real history: populate BacktestEngine with live CNY curve / CSI 300 series (item 1 dependency) | Limitation #5 | Kupiec POF + coverage tests on ≥10y history; recalibration triggers evaluated | OPEN |
| 7 | G2++ two-factor rate model promotion: wire existing G2PP cards/design into the production ESG path with curve-twist validation | MR-004 | G2++ selectable in ESG config; martingale + swaption fit evidence; HW1F kept as fallback | OPEN |
| 8 | Stochastic bonus declaration: make RB/TB declaration fully pathwise (extend PATHWISE_DECLARATION work into TVOG main path) | Limitation #4 | Pathwise TVOG vs current TVOG bridge quantified and documented | OPEN |
| 9 | Independent-review readiness pack: assemble APS X2 / TAS M §3.6.5 evidence bundle (validation reports, limitations, sign-off states) | Gate 3 | Single `docs/INDEPENDENT_REVIEW_PACK.md` index; all links resolve | OPEN |
| 10 | Performance: profile 100k-policy batch, close top hotspot (chunking / vectorisation), publish benchmark | Expansion plan §2.6 | ≥20% runtime cut on benchmark or documented finding that none is available | OPEN |
| 11 | Mortality improvement + credibility blending (ASOP 25) for qx tables | Accuracy | Blended table generator + tests + assumptions register entry | OPEN |
| 12 | Model health check expansion: add VR-H11 (calibration drift) and VR-H12 (scenario file schema hash) | Governance | Checks wired into `model_health.py` + scheduled cycle | OPEN |

Items requiring human sign-off (owner approval, regulator deviation): implement to the point of sign-off, then `BLOCKED(owner-signoff)` — never self-approve.

## 5. Cycle Log

| Date | Item | Outcome | Commit |
|------|------|---------|--------|
| 2026-07-07 | GD-1 (owner directive 2026-07-07: stepwise detail in GUI): scenario_path_detail.py engine (P-measure HW1F + correlated GBM on saved seed; per-class return/cumulative fans via CF-1 mechanics: bond carry+duration proxy, equity TR, cash carry; JSON+6 CSVs, digest-cached, UNSIGNED) + igui_path_detail.py /paths page (fan charts p5-p95/p25-p75/median + sample overlays, series picker, provenance card) + /path-data route + nav link; CF-3 liability chart now splits guaranteed vs non-guaranteed benefits (schema cf3-gui-1.1); 13 new tests, 114 GREEN across GD/CF/PC/GUI suites incl. nav + node script-syntax guards; live e2e fresh+cached verified | DONE | (this cycle's AUTO commit) |
| 2026-07-03 | PC-1c (owner report: pages not inter-accessible): shared nav bar now injected CENTRALLY (run_gui._with_nav) on all 11 console pages with active-page highlight; page-embedded duplicates removed; new regression test asserts every page carries exactly one nav with all links; 76 GREEN (4 pre-existing sha-baseline failures unchanged) | DONE | (this cycle's AUTO commit) |
| 2026-07-03 | PC-1b (owner request): GUI navigation bar on the Run Controls landing page + all-console links; /portfolio construction blocks presented as TABS (Asset strategy / Product catalogue / Portfolio composer); node JS guard green; 46 tests GREEN (2 pre-existing sha-baseline failures unchanged) | DONE | (this cycle's AUTO commit) |
| 2026-07-03 | PC-1 portfolio construction (owner directive): asset SAA (type/mix/weights -> derived balance sheet incl. run-engine fields backing_asset_mv/illiquid_share + CF fund mechanics), product catalogue over 3 mechanic families (short/long par etc.), composer + /portfolio GUI page; saves loader-revalidated, gate reset on save; CF outputs split per catalogue product; 17 new tests, 130 GREEN across suites; LIVE e2e construct->run->cashflows verified (2 pre-existing sha-baseline failures unchanged) | DONE | (this cycle's AUTO commit) |
| 2026-07-03 | CF-3 (owner request): /cashflows GUI page - inline-SVG charts (liability CF components; stacked asset balances), yearly tables per class with monthly drill-down per year, digest-cached /cashflow-data endpoint (refreshes the six CSVs), UNSIGNED banner, run-off/shortfall callouts; page added to node JS-syntax guard; 6 new tests, 85 GREEN across CF+GUI suites | DONE | (this cycle's AUTO commit) |
| 2026-07-03 | CF-1c (owner correction: asset balances were level): asset fund now COUPLED to liability net CF - income reinvested, benefits funded by sales, monthly constant-mix rebalancing, zero-floor + shortfall reporting, book_runoff_month marker; verified grow-then-run-off (peak y14 524M, -146.6M y20 maturities); 22/22 tests GREEN incl. accounting identity | DONE | (this cycle's AUTO commit) |
| 2026-07-03 | CF-1b (owner request): wide-format CF artifacts - rows = time only, classes horizontal (<class>__<measure> headers; balances use plain class labels); JSON preview follows; 2 new pivot tests + updated artifact tests, 18/18 GREEN | DONE | (this cycle's AUTO commit) |
| 2026-07-03 | CF-1 cash-flow projection set (owner directive): par_model_v2/projection/cashflow_projection_set.py - liability by product class x 9 buckets (gtd/non-gtd x death/maturity/surrender + cash dividend; CD product = 6 populated buckets), asset CF + balances by class, monthly+yearly to 100y, JSON+6 CSV artifacts with inputs digest; premium/expense/decrement conventions regression-tested vs legacy engine; 16 new tests GREEN, 98 legacy projection tests GREEN | DONE | (this cycle's AUTO commit) |
| 2026-07-03 | HOTFIX GUI-5 (owner report: button did nothing): collapsed backslash escape put raw newlines inside JS string literals -> whole page script failed to parse -> no click handler; 21 escapes fixed; NEW GUARD tests/test_igui_page_scripts_syntax.py (node --check over every inline script of all 9 GUI pages); live e2e re-verified (seed 45 smoke run succeeded, headline rendered) | DONE | (this cycle's AUTO commit) |
| 2026-07-03 | GUI-5 (owner request): Save & RUN button on Run Controls page; /save-run orchestration (save → autofill missing domains with governed defaults → gate → GUI-1 async job); gate never bypassed (engine re-verifies); 8 new tests GREEN; live e2e: one click → smoke run succeeded, headline rendered, /my-results refreshed; pre-existing sha-baseline failures unchanged | DONE | (this cycle's AUTO commit) |
| 2026-07-03 | GUI-4 run history & compare: igui_run_history.py + /history /runs /runs/<id> /compare-runs; registry from persisted GUI-1 job records (id, timestamps, inputs digest, seed, headline); durable run-plan enrichment (survives artifact overwrite); side-by-side metadata + headline-delta compare with smoke/kind/same-digest notes; 14 new tests GREEN (53 across GUI-1..4); GUI TRACK COMPLETE | DONE | (this cycle's AUTO commit) |
| 2026-07-03 | GUI-3 calibration console: igui_calibration.py + /calibration /calibration-catalogue /market-data-status /run-calibration; HW1F + GBM pipelines async via JobManager; per-market parameter card + fit diagnostics (RMSE/SSE-proxy, convergence, gates G-02/G-12/G-03); market-data provenance panel (roadmap #1); UNSIGNED surfaced everywhere; repo governance store untouched (byte-tested); new tests GREEN | DONE | (this cycle's AUTO commit) |
| 2026-07-03 | GUI-2 stress console: igui_stress.py + /stress /stress-catalogue /run-stress /asset-stress; JobManager per-job runner+meta; 13 new tests GREEN (25 with GUI-1 suite); live base-vs-stress e2e verified (conf 99.0 → SCR −13.9%); no new regressions vs main baseline | DONE | (this cycle's AUTO commit) |
| 2026-07-03 | GUI-1 async run console: igui_job_manager.py + /execute-async + /jobs endpoints + polling run page; 9 new tests GREEN; live async end-to-end smoke succeeded (real engine headline, /my-results refreshed); 7 pre-existing ui_app sha-baseline failures on main documented (owner-gated Phase 38) | DONE | (this cycle's AUTO commit) |
| 2026-07-03 | Owner directive registered: GUI run-console track (GUI-1..GUI-4) prioritised above general backlog; architecture = local web server | Directive cycle (no code) | (this commit) |
| 2026-07-03 | Roadmap created; sync tooling (`scripts/cowork_sync_push.sh`) added; scheduled task registered | Setup cycle | — |
| 2026-07-03 | #1 Live market-data pipeline: `live_market_data_pipeline.py` (CNYYieldCurveLoader, CSI300IndexLoader, SnapshotCache), 2 fixtures, 12 tests GREEN; live tier UNSIGNED pending owner source approval | DONE | (this cycle's AUTO commit) |

## 6. Standing Rules

- Never force-push `main`; never bypass the agent lock.
- Governed headline figures (TVOG, aggregation reports) change only with an explicit item covering them.
- Secrets (GitHub PAT at `.git/gh_token`) are never committed, logged, or echoed.
- If two consecutive cycles yield (lock contention with Codex), report to Model Owner instead of retrying harder.
