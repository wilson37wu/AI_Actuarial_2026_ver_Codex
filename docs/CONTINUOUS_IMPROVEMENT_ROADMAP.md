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
| 2026-07-03 | Roadmap created; sync tooling (`scripts/cowork_sync_push.sh`) added; scheduled task registered | Setup cycle | — |
| 2026-07-03 | #1 Live market-data pipeline: `live_market_data_pipeline.py` (CNYYieldCurveLoader, CSI300IndexLoader, SnapshotCache), 2 fixtures, 12 tests GREEN; live tier UNSIGNED pending owner source approval | DONE | (this cycle's AUTO commit) |

## 6. Standing Rules

- Never force-push `main`; never bypass the agent lock.
- Governed headline figures (TVOG, aggregation reports) change only with an explicit item covering them.
- Secrets (GitHub PAT at `.git/gh_token`) are never committed, logged, or echoed.
- If two consecutive cycles yield (lock contention with Codex), report to Model Owner instead of retrying harder.
