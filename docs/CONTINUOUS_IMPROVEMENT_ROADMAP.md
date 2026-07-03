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

**This track takes priority over items 2–12 below until GUI-4 is DONE.** One phase per cycle. It does NOT constitute sign-off for the separately owner-gated Phase 38 Task 3 (`ui_app.html` native-tab cutover / sha256 re-baseline), which stays gated.

| # | Item | Definition of done | Status |
|---|------|--------------------|--------|
| GUI-1 | Run-console server skeleton + core stochastic run: background job execution with progress endpoint, results rendered in GUI. Discovery: the Phase IGUI stack already provided input pages, validation gate, launchers, and a synchronous run; GUI-1 delivered the missing async layer (JobManager, /execute-async, /jobs/<id>, /jobs, polling run page) on the existing stdlib-only server (kept over Flask/FastAPI: zero new deps, same architecture class - local web server) | User can launch, configure, run, watch progress, and read results with zero .py editing | DONE(2026-07-03, see §5) |
| GUI-2 | Sensitivities & stress in GUI: predefined stress suite + parameter sensitivity toggles, results compared against base run | Stress results in GUI with base-vs-stress deltas | OPEN |
| GUI-3 | Calibration runs in GUI: trigger HW1F/GBM calibration via live market-data pipeline (roadmap #1), fit diagnostics (SSE, convergence, parameter card) displayed; UNSIGNED flag surfaced | Calibration runnable + diagnosable from GUI | OPEN |
| GUI-4 | Run history & compare: persisted run registry (id, timestamp, inputs hash, seed, headline outputs), list/open past runs, side-by-side diff of two runs | Reproducible run registry browsable in GUI | OPEN |

Standing constraints: runs executed through the GUI must keep the existing governance trail (seed policy, parameter snapshots, SHA-256 audit) — the GUI is a front-end to the governed engine, never a bypass. Governed headline figures remain untouched except where an item explicitly covers them.

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
| 2026-07-03 | GUI-1 async run console: igui_job_manager.py + /execute-async + /jobs endpoints + polling run page; 9 new tests GREEN; live async end-to-end smoke succeeded (real engine headline, /my-results refreshed); 7 pre-existing ui_app sha-baseline failures on main documented (owner-gated Phase 38) | DONE | (this cycle's AUTO commit) |
| 2026-07-03 | Owner directive registered: GUI run-console track (GUI-1..GUI-4) prioritised above general backlog; architecture = local web server | Directive cycle (no code) | (this commit) |
| 2026-07-03 | Roadmap created; sync tooling (`scripts/cowork_sync_push.sh`) added; scheduled task registered | Setup cycle | — |
| 2026-07-03 | #1 Live market-data pipeline: `live_market_data_pipeline.py` (CNYYieldCurveLoader, CSI300IndexLoader, SnapshotCache), 2 fixtures, 12 tests GREEN; live tier UNSIGNED pending owner source approval | DONE | (this cycle's AUTO commit) |

## 6. Standing Rules

- Never force-push `main`; never bypass the agent lock.
- Governed headline figures (TVOG, aggregation reports) change only with an explicit item covering them.
- Secrets (GitHub PAT at `.git/gh_token`) are never committed, logged, or echoed.
- If two consecutive cycles yield (lock contention with Codex), report to Model Owner instead of retrying harder.
