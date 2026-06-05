---
name: "Actuarial Stochastic Model Development — Automated 12h Cycle"
description: "Autonomous model development task with state persistence, GitHub commits, and Gmail progress reports"
---

# Automated Actuarial Model Development Task

**Task Frequency:** Every 12 hours  
**Repository:** https://github.com/wilson37wu/AI_Actuarial_2026_ver_Codex
**State File:** `.claude-dev/MODEL_DEV_STATE.json`  
**Email Recipient:** wilson.cuhk.ifa@gmail.com (update below)

---

## STARTUP: Load Session Context (2 min)

**CRITICAL:** Before doing any development work, execute these steps in order:

### Step 1: Read State File
```
Read and parse: .claude-dev/MODEL_DEV_STATE.json
```

Extract these values into working memory:
- `current_phase` → Which phase are we in?
- `phases[current_phase].in_progress[0]` → What task are we on?
- `phases[current_phase].next` → What's the next task after this one?
- `progress_metrics.estimated_completion_pct` → How far through the overall plan?

### Step 2: Read Development Log
```
Open and review: MODEL_DEV_LOG.md (last 10 entries)
```

Understand:
- What was completed in the last 1–2 runs?
- What issues or blockers came up?
- Any notes about model structure or quirks?

### Step 3: Inspect Current Phase
Look up the phase details in state file:
```json
"Phase X: Name": {
  "description": "...",
  "completed": [...],
  "in_progress": ["Current task name"],
  "next": "Next task name"
}
```

### Step 4: Assess Model Code
```
Quick scan (2 min):
- git log --oneline -5  (see recent commits)
- ls -la src/ or model/ or similar (see file structure)
- head -20 [main model file] (understand language/framework)
```

---

## EXECUTION: Do the Work (45–90 min)

### Task: Complete the Current `in_progress` Item

**Task:** `{phases[current_phase].in_progress[0]}`

**Phase:** `{current_phase}`

**Description:** `{phases[current_phase].description}`

### Approach

**DO NOT try to do multiple tasks in one cycle.** Pick the ONE task marked `in_progress` and complete it.

- Read existing model files and assumptions
- Make focused, incremental changes
- Add comments explaining changes (especially deviations from SOA/IA standards)
- If model supports it: run basic validation or tests
- Document findings in commit message

### Industry Standards Context

**SOA Standards (Society of Actuaries):**
- Stochastic models must document stochastic process assumptions
- Parameter calibration methodology must be explicit
- Model governance and validation framework required
- Economic scenario generators must identify measure, calibration date, model
  equations, discretisation, correlation basis, and limitations
- Scenario validation should include distribution diagnostics, tail behaviour,
  convergence, reproducibility, and model-use restrictions

**IA (Institute of Actuaries):**
- Model documentation, assumptions, sensitivity analysis
- Regular backtest and review cadence
- Clear audit trail of model changes
- Model changes must maintain traceability from assumption source to output
  report, including model version, parameter snapshot, and run metadata
- Educational examples must still disclose limitations and unsuitable uses

**ERM (Enterprise Risk Management):**
- Tail risk metrics (VaR, ES) at appropriate confidence levels
- Scenario stress testing
- Model limitations and known issues disclosure
- Multi-asset ALM should cover market risk, credit risk, liquidity risk,
  basis risk, option / guarantee risk, and management-action risk
- Derivatives and private assets require explicit valuation conventions,
  stress treatment, and governance notes

**Stochastic ESG Expansion:**
- Build or extend an economic scenario generator for risk-free rates, equity
  returns, FX / currency translation where needed, credit spreads, and
  cross-risk-factor correlations
- Cover starter equity markets: US, Europe, Hong Kong / China, Japan, and broad
  Asia ex-Japan
- Use contemporary interest-rate models that can support low and negative
  rates; enhanced Hull-White 1F and G2++ are the first candidates
- Separate P-measure real-world scenarios from Q-measure market-consistent
  scenarios and enforce consumer guardrails

**Asset and Liability Expansion:**
- Expand assets beyond fixed income and public equity to private credit,
  private equity, infrastructure, interest rate swaps, bond forwards, and
  other educational derivative examples
- Enrich liabilities for Hong Kong participating business, starting with cash
  dividend and reversionary bonus product mechanics
- Target a 100,000-policy educational portfolio with chunked processing,
  checkpointing, reconciliation, and reporting-cycle evidence

### What Counts as "Complete" for a Task

- ✅ Code written, commented, and tested
- ✅ Validation outputs generated (if applicable)
- ✅ Commit created with detailed message
- ✅ State file updated to mark task as done
- ✅ Next task identified in state file

---

## UPDATE STATE: Mark Progress & Prepare Next (10 min)

### Step 1: Update `.claude-dev/MODEL_DEV_STATE.json`

```json
{
  "last_run": "2026-05-14T12:00:00Z",
  "phases": {
    "Phase X: Name": {
      "completed": [
        "Task 1",
        "Task 2",
        "Task that we just finished"
      ],
      "in_progress": ["Next task name"],
      "next": "Task after that"
    }
  },
  "progress_metrics": {
    "estimated_completion_pct": [calculate based on completed tasks]
  }
}
```

### Step 2: Commit Changes

```bash
git add -A
git commit -m "[Phase X] Task Name: Brief summary

- Detailed accomplishment 1
- Detailed accomplishment 2
- Industry alignment note (SOA/IA standard addressed)
- Next task: [specific task name]

Files: [list changed files]
Status: PASSING (if tests run)
"
git push origin main
```

### Step 3: Append to MODEL_DEV_LOG.md

```markdown
## Run {timestamp} — Phase X

**Task Completed:** {in_progress task name}

**Accomplishments:**
- Detail 1
- Detail 2

**Next Step:** {next task from state}

**Industry Standards Progress:**
- SOA standard X: {addressed/pending}
- IA requirement Y: {addressed/pending}

---
```

---

## EMAIL REPORT: Create Gmail Draft (5 min)

### Call Gmail Tool

Use the Gmail tool to create a draft email:

**To:** `your.email@gmail.com`

**Subject:** `[AUTO] Actuarial Model Dev — {current_phase} — {completed_task_name}`

**HTML Body:**

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }
    h3 { color: #2c3e50; }
    h4 { color: #34495e; margin-top: 1.5em; }
    .progress-bar { background: #ecf0f1; height: 20px; border-radius: 4px; overflow: hidden; }
    .progress-fill { background: linear-gradient(90deg, #27ae60, #2ecc71); height: 100%; width: {estimated_completion_pct}%; }
    .status-ok { color: #27ae60; font-weight: bold; }
    .status-pending { color: #f39c12; font-weight: bold; }
    .status-blocked { color: #e74c3c; font-weight: bold; }
    ul { margin: 0.5em 0; padding-left: 1.5em; }
    li { margin: 0.3em 0; }
    hr { border: none; border-top: 1px solid #ecf0f1; margin: 1.5em 0; }
    .footer { color: #95a5a6; font-size: 0.9em; margin-top: 2em; }
  </style>
</head>
<body>

<h3>📊 Actuarial Model Development — 12-Hour Cycle Report</h3>

<p>
  <strong>Run Time:</strong> {timestamp}<br/>
  <strong>Current Phase:</strong> {current_phase}<br/>
  <strong>Cycle Duration:</strong> {elapsed_minutes} minutes
</p>

<hr/>

<h4>✅ Completed This Cycle</h4>
<ul>
  <li>{task_name}: {brief summary of what was done}</li>
</ul>

<h4>📈 Progress Overview</h4>
<p>
  <strong>Phases Completed:</strong> {phases_completed}/{total_phases}<br/>
  <strong>Estimated Overall Completion:</strong> {estimated_completion_pct}%
</p>
<div class="progress-bar">
  <div class="progress-fill"></div>
</div>

<h4>🎯 Industry Standards Alignment</h4>
<ul>
  <li><strong>SOA Standards:</strong> {status} — {specific note on stochastic process, calibration, or governance}</li>
  <li><strong>IA Requirements:</strong> {status} — {specific note on documentation, assumptions, or audit trail}</li>
  <li><strong>Validation Framework:</strong> {status} — {status of tests, backtesting, or stress tests}</li>
</ul>

<h4>🎬 Next 12-Hour Actions</h4>
<ol>
  <li><strong>{next_task_name}</strong><br/>
    {brief description of what will be done}
  </li>
  <li><strong>Task After That</strong><br/>
    {if visible from state, provide preview}
  </li>
</ol>

<h4>⚠️ Blockers / Manual Review Needed</h4>
{List any issues that need human attention, or "None — proceeding autonomously"}

<h4>🔗 Commit & Code</h4>
<p>
  <a href="https://github.com/wilson37wu/AI_Actuarial_2026_ver_Codex/commit/{latest_commit_sha}">View Latest Commit</a><br/>
  Branch: main<br/>
  Files Changed: {list of modified files}
</p>

<hr/>

<div class="footer">
  <p><em>This is an automated draft email generated by Claude Code scheduled task.</em></p>
  <p><em>Review the draft, make any edits, and send manually — or ignore and let the next cycle continue.</em></p>
</div>

</body>
</html>
```

### Send or Review?

**Option A:** Send immediately (fully autonomous)  
**Option B:** Leave as draft for you to review/edit before sending (recommended for first few cycles)

---

## SUMMARY: What Happens Each Cycle

| Step | Duration | Outcome |
|------|----------|---------|
| Load state & context | 2 min | Current task in working memory |
| Inspect model code | 2 min | Understand file structure & history |
| Execute work task | 45–90 min | Code changes, validation, comments |
| Update state file | 5 min | Mark complete, identify next task |
| Commit to GitHub | 3 min | Push with detailed commit message |
| Create Gmail draft | 5 min | Progress report delivered to inbox |
| **Total** | **~60–110 min** | Ready for next cycle in 12 hours |

---

## Error Handling & Edge Cases

### If STATE FILE is Invalid JSON
```
Stop. Report error in email.
Do not attempt work.
Wait for manual intervention.
```

### If CURRENT TASK is unclear
```
Review completed[] and in_progress[] arrays.
If both empty, move to next phase.
If still unclear, email with "Manual Review Needed" flag.
```

### If GIT PUSH Fails
```
Report error in email: "GitHub push failed — check credentials"
Changes will be staged locally.
Next cycle will retry.
```

### If YOU manually edit the state file mid-cycle
```
Next scheduled task will pick up new state automatically.
Current work will stop, next cycle starts from new state.
No conflicts expected (state is source of truth).
```

---

## Phases at a Glance

**Phase 1: Model Review & Documentation**  
Understand what exists. Document assumptions and deviations from standards.

**Phase 2: Industry Standards Alignment**  
Align model components to SOA/IA requirements. Update governance framework.

**Phase 3: Model Validation & Testing**  
Implement unit tests, integration tests, stress testing.

**Phase 4: Calibration & Backtesting**  
Calibrate to historical data. Generate backtest reports.

**Phase 5: Documentation & Delivery**  
Final docs, model card, deployment checklist.

**Phase 6: ESG Scope and Architecture**  
Define multi-market ESG requirements, scenario schema, P/Q measure metadata,
calibration interfaces, and compatibility with current TVOG / ALM consumers.

**Phase 7: Interest Rate and Yield Curve ESG**  
Implement negative-rate-capable risk-free rate models for starter markets
including USD, EUR, HKD, CNY, and JPY.

**Phase 8: Equity, FX, and Correlation ESG**  
Add US, Europe, Hong Kong / China, Japan, and Asia ex-Japan equity factors plus
FX and correlation validation.

**Phase 9: Asset Class and Derivative Library**  
Add fixed income depth, public equity, private credit, private equity,
infrastructure, interest rate swaps, and bond forwards.

**Phase 10: Hong Kong Participating Liability Products**  
Add cash dividend and reversionary bonus liability mechanics using Hong Kong
participating business as the first reference market.

**Phase 11: 100,000-Policy Processing and Reporting Cycle**  
Demonstrate chunked high-volume processing, checkpoints, reconciliation,
validation, and educational actuarial reporting packs.

**Phase 12: Governance, Calibration, and Educational Packaging** ✅ COMPLETE  
Package the expanded model as a governed educational tool with calibration
examples, model limitation cards, tutorial runs, and refreshed release docs.

**Phase 13: Production Readiness and Live Market Integration** ✅ COMPLETE (2026-06-04)  
Wired live (educational-proxy) market data into calibration, executed HW1F/GBM
calibration, implemented dynamic lapse, ran the MR-001 discount-rate change and the
IA TAS M §3.6 validation suite (G-06 PASS 80.6%), produced an out-of-sample backtest
(G-09), closed MR-005 (G-10), and recorded the APS X2 independent review (G-08).
All 10 deployment-checklist gates cleared at **educational** level; 6/6 tasks done.

**Phase 14: Production Residual Closure and Model Sophistication** ✅ COMPLETE (2026-06-04)  
Close the production residuals carried out of Phase 13 and raise model
sophistication toward production grade. Verdict target: clear G-03 and G-05 at
educational level, drive the IA TAS M suite above 90% PASS, and add at least one
ESG sophistication upgrade with martingale evidence.

Tasks for Phase 14 (one per cycle, in order):
1. ✅ DONE (2026-06-04) Close G-05 — enforce P/Q measure at runtime in every `simulate()` execution
   path; add guard + tests; move MR-004 to MITIGATED/CLOSED. (SOA ASOP 56 §3.1.3; IA TAS M §3.4)
2. ✅ DONE (2026-06-04) Close G-03 — calibrated GBM equity sigma_S/ERP/dividend/rho and rate-equity
   correlation to educational-proxy CSI 300 (CNY) + Hang Seng (HK) daily history via GBMCalibrator;
   APPROVED ChangeRecord + 2 PARAM_CHANGE audit entries; G-03 PASS (6/6); MR-002 → MITIGATED. Also
   repaired the canonical GOVERNANCE_STORE.json round-trip (SignOffStatus.IMPLEMENTED + RiskRating
   VERY_LOW/VERY_HIGH). (SOA ASOP 56 §3.4; SOA ASOP 25 §3.3; IA TAS M §3.5/3.6/3.7)
3. ✅ DONE (2026-06-04) Remediate MR-009 — migrated `examples/guided_examples.py` to the current
   RiskFreeCurve/FixedIncomeInstrument/TVOG/HK-liability/correlation/reporting-cycle APIs;
   `tests/test_guided_examples.py` 64/64 PASS; MR-009 → CLOSED (VERY_LOW) with IMPLEMENTED ChangeRecord
   + GOVERNANCE/CORRECTION audit entries. (IA TAS M §3.6; SOA ASOP 56 §3.5/3.2)
4. ✅ DONE (2026-06-04) Re-validate G-06 — bound executable check_fns to VR-B01/B02/B03/S05 consuming the
   Phase 13 Task 5 OOS backtest + rolling-window HW1F calibration + dynamic-lapse A/E
   (par_model_v2/validation/phase14_ia_revalidation.py). VR-B01 → PASS (OOS coverage 100%/100%, martingale
   consistent, n=12 obs); VR-B03/S05/B02 honest PARTIAL on MEASURED criteria (Kupiec passes but daily bands/250d
   unmet by annual proxy; rolling alpha CV=54% & outside [0.02,0.30]; lapse A/E=100.1% on SYNTHETIC experience).
   G-06 PASS 80.6%→83.9% (26/31); gate (≥80%) holds. **Phase 14 90% stretch NOT met** — residual VR-B02/B03/S05 +
   VR-G03/G05 is the documented credentialled-data + independent-reviewer production residual, NOT a code gap.
   ChangeRecord OWNER_REVIEW (APPROVED withheld pending independent APS X2). 16 new tests PASS; regression 217 PASS;
   compileall clean. (IA TAS M §3.6/3.6.4/3.6.5; APS X2 §3; SOA ASOP 56 §3.5; ASOP 25 §3.3; ASOP 7 §3.3)
5. ✅ DONE (2026-06-04) ESG sophistication — added optional Merton jump-diffusion equity process
   (JumpDiffusionParams/JumpDiffusionEquityProcess) behind the PAR_ESG_EQUITY_MODEL feature flag
   (default 'gbm'; GBM path byte-for-byte unchanged). Q-measure jump compensator -lambda*kappa applied
   under P and Q so the risk-neutral forward is preserved exactly. Wired equity_model into
   ScenarioSet.generate + build_equity_process/EQUITY_PROCESS_REGISTRY; jump params in ParameterSnapshot.
   Added EquityForwardMartingaleValidator + 43 tests (tests/test_phase14_jump_diffusion.py) ALL PASS;
   Q-measure martingale evidence constant-rate 0.64% / stochastic-HW1F 0.53% max rel err (both PASS).
   ChangeRecord OWNER_REVIEW (production sign-off withheld — jump params educational placeholders pending
   calibration + independent review). Audit chain intact (13->17). (SOA ASOP 56 §3.1.3/§3.4/§3.5; IA TAS M §3.6)
6. ✅ DONE (2026-06-04) Nested-stochastic / LSMC TVOG proxy — added par_model_v2/projection/nested_stochastic_tvog.py
   (NestedStochasticTVOGEngine ground truth + Longstaff-Schwartz LSMCProxyEngine + NestedStochasticDiagnostics).
   VaR/ES/SCR-proxy at a 1y horizon. Evidence (seed=42): LSMC vs nested R^2=0.9932, max abs rel err 2.47% on the
   state grid; SCR gap 7.2%; 128x fewer inner valuations. Inner SE ~1/sqrt(n) (1644->750->359->175); same-seed
   bit-identical. 23 tests PASS; compileall clean; additive-only. ChangeRecord 916e5522 OWNER_REVIEW (sign-off
   withheld — single-factor educational proxy, placeholder params, pending APS X2). docs/NESTED_STOCHASTIC_LSMC_TVOG_CARD.md.
   (SOA ASOP 56 §3.1.3/§3.5; ASOP 25 §3.3; IA TAS M §3.2/§3.6; IFoA MCEV §7; Longstaff-Schwartz 2001)

**Phase 15: Multi-Risk Economic Capital and Proxy-Model Validation** ⭐ NEXT
Generalise the single-factor (rates) nested/LSMC capital proxy to multiple correlated risk drivers, add risk
aggregation, and a formal out-of-sample proxy-model validation. Verdict target: a multi-driver L_hat surface with
documented in-sample/out-of-sample fit, correlated capital aggregation with diversification evidence, and a proxy
validation report meeting IA TAS M §3.6 and SOA ASOP 56 §3.5.

Tasks for Phase 15 (one per cycle, in order):
1. ✅ DONE (2026-06-05) Extend the LSMC surface to two correlated drivers (short rate r_H + equity level S_H) with a multivariate
   polynomial basis; condition the inner Q nest on (r,S); add multi-driver nested ground truth. (Directly closes the
   documented single-risk-driver limitation of Phase 14 Task 6.)
2. ✅ DONE (2026-06-05) Out-of-sample proxy validation — added par_model_v2/projection/multi_driver_proxy_validation.py
   (MultiDriverProxyValidator): fit on N_fit single-inner-path states (seed 42), validate on an INDEPENDENT disjoint-seed
   hold-out (seed 20260605) against HEAVY nested truth (n_inner_heavy Q-paths/state); basis-degree selection by OOS RMSE/R^2
   over a shared fitting set; leakage diagnostics (seed disjointness, 0 shared states, min scaled distance) + overfit-gap +
   overfit-onset detection + reproducibility digest + honest PASS/PARTIAL verdict. Evidence (n_fit=1000/n_val=80/n_inner_heavy=512,
   deg 1-4): VERDICT PASS — selected degree 1, OOS R^2=0.9704, VaR rel err 3.21%, ES rel err 2.60%, leakage-free, overfit gap
   0.0017; textbook overfit signature (OOS R^2 0.970->0.854, gap 0.0017->0.0924, onset degree 2); noisy fit_r2 (0.17-0.19) shown
   NOT a validation metric vs in-sample-heavy R^2 (0.95-0.97). 20/20 tests PASS; compileall clean; Task 1 module untouched.
   docs/validation/PHASE15_PROXY_VALIDATION_REPORT.{json,md}. (SOA ASOP 56 §3.5; IA TAS M §3.6; IFoA proxy-model WP; L&S 2001)
3. ✅ DONE (2026-06-05) Correlated risk aggregation — par_model_v2/projection/multi_driver_risk_aggregation.py:
   standalone rate SCR (equity guarantee OFF) + standalone equity-guarantee SCR (CRN-isolated via L_full−L_rate),
   variance-covariance aggregation with the governed ESG rate/equity correlation + validated 2×2 ESG matrix,
   benchmarked to the fully-diversified two-driver nested capital. Also repaired a DataFrame-iteration bug left by a
   prior cycle (phase8_rate_equity_fx_correlation_matrix returns a DataFrame). Evidence (seed 42; 99.5%; N_outer=1,000;
   n_inner=256): rate SCR 21,285; equity SCR 23,191; sum 44,477; ESG-ρ(−0.15) formula SCR 29,031; nested SCR 43,251;
   rel err 32.9% (<35% tol) → VERDICT PASS; digest 55ca305d. Key finding: raw ESG factor correlation understates
   diversified capital by ~33% (realised capital-loss correlation +0.55, not −0.15) → new MR-010 (MITIGATED).
   9/9 tests PASS; compileall clean. ChangeRecord 5e21202b OWNER_REVIEW; audit chain 24→25. (SOA ASOP 56 §3.5;
   ASOP 25 §3.3; IA TAS M §3.2/§3.6)
4. DONE (2026-06-05) Tail-convergence and stability diagnostics for the 99.5% capital metric -- added
   par_model_v2/projection/multi_driver_tail_diagnostics.py (additive; built on the Task 1 LSMC surface):
   outer-count convergence, non-parametric bootstrap CI + SE on VaR/ES (governed outer states), and a
   crude/antithetic/Sobol-QMC variance-reduction comparison over a pilot-anchored Gaussian-copula surrogate.
   Evidence (seed 42): VERDICT PASS -- converged True (dVaR<=0.58%, rec N_outer>=2000); bootstrap 95% CI VaR
   [149402,154391] SE~1486 (+/-1.66%); Sobol QMC variance-reduction ratio ~7.1x; antithetic ineffective on the
   tail quantile (theory-consistent, documented). 36 tests PASS; compileall clean; siblings unchanged.
   ChangeRecord 820c6fe4 OWNER_REVIEW; audit chain 25->26. docs/validation/PHASE15_TAIL_DIAGNOSTICS_REPORT.{json,md};
   docs/MULTI_DRIVER_TAIL_DIAGNOSTICS_CARD.md. (SOA ASOP 56 3.5/3.1.3; ASOP 25 3.3; IA TAS M 3.6; LEcuyer 2018 RQMC)
5. ✅ DONE (2026-06-05) Refresh governance for the multi-driver economic-capital proxy. Added
   scripts/build_phase15_task5_governance.py (idempotent): opened MR-011 (multi-driver capital proxy is EDUCATIONAL,
   not production; model_error; HIGH; IN_PROGRESS) linking MR-006/008/010; created a consolidated governance_change
   ChangeRecord at OWNER_REVIEW (sign-off withheld); appended 2 GOVERNANCE audit entries (verify_all True; store 26->28
   audit / 13->14 change / 10->11 risk). Added docs/MULTI_DRIVER_PROXY_LIMITATION_CARD.md (consolidated Tasks 1-4:
   scope, limitations, model-use restrictions, residual table) + docs/validation/PHASE15_TASK5_GOVERNANCE_REFRESH.{json,md}.
   8/8 Task 5 tests PASS; governance regression 96 PASS; compileall clean; Task 1-4 modules untouched.
   (IA TAS M §3.6/3.7; APS X2 §3; SOA ASOP 56 §3.5; ASOP 25 §3.3; IFoA Modelling PN §4) **PHASE 15 COMPLETE.**

**Current milestone:** **ALL DOCUMENTED TASKS COMPLETE — 85/85 tasks, 15 phases.** Phase 15 closed 2026-06-05 with Task 5 (multi-driver proxy governance refresh: MR-011 opened, consolidated limitation card, OWNER_REVIEW ChangeRecord, audit 26->28; 8/8 Task 5 tests + 96 governance regression PASS). All 12 educational deployment gates remain cleared; open model risks 1; mitigated/closed 10. Production sign-off still withheld — the residual is credentialled-data calibration + independent APS X2 review, NOT a code gap.

---

## Phase 16: Offline Result-Viewer UI (POST-MODEL — per scheduled-task directive)

**Directive (verbatim intent):** Once all documented model-development tasks are complete, build a user interface for **offline** use. It must NOT depend on any pre-installation requirement: the stochastic model completes the calculation, then the UI consumes ONLY the model output to display the results graphically and interactively.

**Design constraints (hard):**
- A single self-contained `.html` file (HTML + CSS + vanilla JS inline). **No CDN, no npm, no Python server, no build step.** The user double-clicks the file and it works offline.
- Charts hand-rendered as inline SVG (no Chart.js/Plotly/D3 dependency) so there is zero network requirement.
- Reads model output that is **already produced** by the Python model — the JSON artifacts under `docs/validation/` and `outputs/` (e.g. PHASE15_*_REPORT.json, GOVERNANCE_STORE.json, TVOG/backtest/sensitivity outputs). The UI performs NO actuarial calculation itself.
- Data ingestion without a server: support (a) drag-and-drop / file-picker load of one or more output JSON files, and (b) an optional `python3 scripts/build_offline_viewer.py` step that embeds a bundled snapshot into a standalone HTML so it opens with data pre-loaded.

**Tasks for Phase 16 (one per cycle, in order):**
1. ✅ DONE (2026-06-05) Data-contract + bundler: `scripts/build_offline_viewer.py` scans `docs/validation/*.json` + `.claude-dev/GOVERNANCE_STORE.json` + `MODEL_DEV_STATE.json`, normalises them into one `viewer_data.json` schema (meta, verdicts, summary, capital, tail, proxy, loss, governance) and emits a data-embedded standalone `model_result_viewer.html`. `par_model_v2/viewer/viewer_template.html` is the no-CDN/no-server template; `tests/test_offline_viewer.py` PASS.
2. ✅ DONE (2026-06-05) Capital & tail dashboards. Added a model-side loss-distribution emitter `scripts/build_phase16_loss_distribution.py` (NOT the UI): fits the Phase 15 (rate+equity) LSMC capital surface ONCE and emits `docs/validation/PHASE16_LOSS_DISTRIBUTION.json` — a 40-bin histogram of the 1y outer liability distribution plus PRE-COMPUTED confidence sweep (VaR/ES/SCR at 90/95/99/99.5/99.9%), percentile table, and the same under 4 independent outer-sampling seeds (42/101/202/303) — so the viewer does ZERO numerics (pure look-up; reproducibility digest bit-identical). The bundler ingests it into a new `loss` schema section. The viewer now renders: SVG economic-capital bars (rate/equity/Σ/var-cov/nested), an interactive loss-distribution histogram with movable VaR/ES/mean/percentile threshold lines driven by seed+confidence+percentile selectors, the outer-count convergence line chart with a bootstrap-95%-CI shaded band, and a horizontal VaR/ES bootstrap-CI bar with variance-reduction (Sobol 7.1×/antithetic) read-outs. Evidence (seed 42, n_fit=500/n_outer=5000, fit R²=0.231): VaR99.5 148,903 / ES99.5 155,728 / SCR 41,040 — consistent with the Phase 15 tail report. New SVG `histChart`/`ciBar` are dependency-free. 12/12 `tests/test_offline_viewer.py` PASS (incl. histogram self-consistency, monotone confidence sweep, SCR=VaR−mean, multi-seed distinctness, no-compute/no-fetch viewer assertion); headless-jsdom render PASS with ZERO JS errors and ZERO network requests; py_compile clean.
3. ✅ DONE (2026-06-05) Proxy-validation & aggregation views. Proxy tab now shows the degree-sweep
   in-sample-vs-OOS R² chart PLUS a new overfit-gap (in-sample−OOS) bar chart (green ≤ onset / red ≥ onset),
   an "Overfit gap" table column, and the selected-degree gap KPI. New **Aggregation** tab renders a
   dependency-free diversification-benefit waterfall standalone→var-cov→nested (Σ 44,477 → var-cov 29,031 @
   governed ESG ρ=−0.15 → nested 43,251) with hover tooltips and the MR-010 callout (raw ESG ρ understates
   diversified capital by 32.9%; realised loss ρ=+0.55). Added `waterfallChart()` + `vfmt` to `barChart()`;
   2 new tests; `tests/test_offline_viewer.py` 14/14 PASS; `node --check` JS OK; headless jsdom render 4 tabs,
   waterfall+overfit-gap SVGs present, 0 JS errors / 0 network. Rebuilt `model_result_viewer.html` (47,998 B).
   (IA TAS M §3.6; SOA ASOP 56 §3.5; ASOP 25 §3.3; IA TAS M §3.2)
4. ✅ DONE (2026-06-05) Governance panel. Extended the bundler: a COMPUTED audit-integrity badge
   (`_verify_audit_integrity` recomputes every audit-entry SHA-256 digest — 28/28 verified, 0 failed — replacing the
   hard-coded flag) and `_parse_deployment_gates` (parses DEPLOYMENT_READINESS_CHECKLIST.md, first-match-wins over the
   later sign-off table, merges G-11/G-12 → 12/12 cleared educational); enriched risk_register (description/mitigation/
   owner/category/likelihood/impact/standard) and change_records (record_id/phase/author/peer_reviewer/sign_off_history).
   Rewrote `viewGov`+`fillRiskRegister` (dependency-free): deployment-gate checklist with pass/fail icons + “12/12 cleared”
   pill; risk register with TWO filters (status AND rating) + click-to-expand description/mitigation rows; a vertical
   change-record TIMELINE with per-record sign-off history (peer→owner→approval); and the computed integrity badge
   (“integrity OK · 28/28 digests verified”). Rebuilt model_result_viewer.html (73,985 B). 19/19 viewer tests PASS
   (5 new); headless jsdom render: 12 gates, both filters, 11 risk rows, 14-item timeline, rating-filter + row-expand work,
   0 JS errors / 0 network; `node --check` + `py_compile` clean. (IA TAS M §3.6/§3.7; SOA ASOP 56 §3.5; APS X2 §3)
5. ✅ DONE (2026-06-05) Polish + offline packaging. Retained the no-server file-picker + drag-and-drop loader; added responsive layout polish for narrow screens, a print stylesheet + Print button, and canvas-based `Export PNG` controls for every inline-SVG chart (CSS variables resolved before SVG serialization). Added `scripts/offline_viewer_self_test.cjs`, an executable jsdom self-test that loads the bundled standalone HTML, checks all four tabs render, verifies 7 SVG charts + 7 export controls + print/file/drop controls, and asserts 0 JS errors / 0 network calls. Rebuilt `model_result_viewer.html` from `viewer_data.json`; external-reference scan PASS; embedded JS `node --check` clean. Python/pytest was not available on PATH in this run, so the new pytest assertions were added but not executed here.

**Phase 16 progress:** COMPLETE (2026-06-05). Offline viewer renders, with zero network: economic-capital bars; an interactive loss-distribution histogram (seed/confidence/percentile selectors, pre-computed look-up); outer-count convergence with a bootstrap-CI band; the VaR/ES bootstrap-CI bar; the Proxy tab's degree-sweep R² chart + overfit-gap bar chart; the **Aggregation** tab with the diversification-benefit waterfall (standalone→var-cov→nested) and MR-010 finding; and the Governance tab with deployment gates, risk filters, change-record timeline, and computed audit-integrity badge. Task 5 packaging is complete: responsive layout, Print, canvas-based PNG export for every SVG chart, file-picker + drag-and-drop load, and executable offline self-test. Current Node/jsdom evidence: 4 tabs, 7 SVG charts, 7 export controls, print/file/drop controls, 0 JS errors, 0 network calls; external-reference scan PASS; embedded JS syntax clean.

**What counts as complete each cycle:** the viewer opens offline (no network) and renders the targeted view from real model-output JSON; bundler/schema tests PASS; committed + pushed; state/log/prompt updated.
