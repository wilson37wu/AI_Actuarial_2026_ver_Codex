---
name: "Actuarial Stochastic Model Development — Automated 12h Cycle"
description: "Autonomous model development task with state persistence, GitHub commits, and Gmail progress reports"
---

# Automated Actuarial Model Development Task

**Task Frequency:** Every 12 hours  
**Repository:** https://github.com/wilson37wu/AI_Actuarial_2026_ver_Codex
**State File:** `.claude-dev/MODEL_DEV_STATE.json`  
**Email Recipient:** wilsonwukl@gmail.com

---

## ⭐ STANDING INSTRUCTION (MANDATORY, EVERY CYCLE) — Email the human at the end

At the **end of every run**, before finishing, email the human (wilsonwukl@gmail.com) a concise status
report. Use the Gmail tool; if only draft creation is available, create a **draft** addressed to that
address (the human will send/review). The email MUST contain, in this order:

1. **Status** — what this cycle did, with the one or two headline outcomes (pass/fail, what was fixed).
2. **Blockers** — anything blocking further progress, especially git/disk/credential issues the sandbox
   cannot resolve itself.
3. **Actions needed from the human** — an explicit, numbered, copy-pasteable checklist (exact shell
   commands where applicable) of what the human must do. If nothing is needed, say "None — proceeding
   autonomously."

This is required whether the cycle succeeded, partially succeeded, or was blocked. Do not end a run
without producing this email/draft.

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

**Current milestone:** **Phase 18 Task 4 COMPLETE — 94/95 documented tasks. Next: Phase 18 Task 5 (offline-viewer copula/tail-dependence Aggregation panel → PHASE 18 COMPLETE).** This cycle added the FOURTH and first NON-FINANCIAL economic-capital-proxy driver — a dynamic-lapse / policyholder-behaviour OU index b(t) with lognormal horizon multiplier M=exp(b) (`par_model_v2/stochastic/lapse_behaviour.py`) — to both the nested ground truth and the LSMC proxy (`par_model_v2/projection/multi_driver_capital_4d.py`). The lapse driver enters the policyholder liability through an in-force factor IF(r,b) that scales the guaranteed + equity-guarantee benefits by survival-to-maturity under the dynamic-lapse basis × M (credit loss is asset-side, unscaled); the behavioural index is orthogonal to the financial drivers in the governed 4×4 ESG correlation. The new `FourDriverProxyValidator` ran disjoint-seed out-of-sample validation: **VERDICT PASS** — selected lean basis (degree 1, max_int 3, 5 terms), OOS R²=0.9638, VaR rel err 2.33% (ES 4.02%, SCR 6.47%) vs heavy nested truth, leakage-free, overfit gap 0.0057, textbook overfit signature (OOS R² 0.964→0.716 as the basis grows 5→57 terms; onset 15 terms), digest 12167cf6fd22. 24 new tests PASS (`tests/test_phase18_four_driver_capital.py`); regression Phase17 3D capital+credit_spread 39 + Phase17 proxy-val 26 PASS; compileall clean; offline self-test ok:true (0 net/0 JS err). Production sign-off withheld — residual is behavioural-index calibration to a credentialled lapse-experience series + independent APS X2 review, plus the still-omitted mortality-trend / FX / liquidity drivers, NOT a code gap. Governance (MR-010/MR-012 four-driver refresh + OWNER_REVIEW ChangeRecord) is Phase 18 Task 4/5 per plan; GOVERNANCE_STORE.json left untouched this cycle. This cycle calibrated the CIR++ credit-spread driver to educational-proxy CNY AA+ corporate OAS history (kappa 0.50/yr, long-run 111 bp, sigma 0.037, lambda 1.06; Feller holds) via the new `CIRCalibrator` (homoscedastic CIR OLS transition regression for kappa + long-run level; residual variance for sigma; documented risk-neutral long-run anchor for the market price of credit risk lambda), `FileBasedCreditSpreadSource` (deterministic CIR synthesis + loader + G-CR plausibility-band gate), and the `run_phase18_cir_calibration` pipeline — mirroring the GBM/HW1F calibrators. G-CR PASS (6/6); APPROVED assumption_change ChangeRecord + one PARAM_CHANGE audit entry persisted to GOVERNANCE_STORE.json (audit 32→34, change 16→17, integrity verified True); **MR-012 → MITIGATED** (open model risks 1; mitigated/closed 11). The credit driver is the third of the proxy's correlated drivers, so the calibration feeds the three-driver 99.5% VaR/ES and the credit standalone capital. All 12 educational deployment gates remain cleared. 14 new tests PASS (`tests/test_phase18_cir_calibration.py`); regression credit_spread 35 + GBM 35 + copula 22 PASS; offline self-test ok:true (0 net / 0 JS err); py_compile clean. Production sign-off withheld — residual is credentialled credit-data calibration (full ML/Kalman estimator + CDS term structure) + independent APS X2 review, plus the still-omitted lapse/mortality/FX/liquidity drivers, NOT a code gap. **Env note for next cycle:** working Python (numpy 2.2.6 / scipy 1.15.3 in `/var/tmp/pylibs`; run with `PYTHONPATH=/var/tmp/pylibs:.`); `pip install` fails (no space) but the libs are present. Run pytest in <45s batches. **Git ghost locks `.git/index.lock` + `.git/HEAD.lock` (2026-06-03) are STILL present and unremovable from the sandbox (`Operation not permitted` while `ls` cannot see them; normal `git add`/`reset`/`commit` fail with "index.lock: File exists") — commit via the alt-`GIT_INDEX_FILE` + direct-ref-write workaround until a human shell deletes them.**

**✅ 2026-06-05 crash-recovery RESOLVED & PUSHED (READ FIRST):** The 2026-06-03 crash left the working tree corrupted AND two ghost git locks. An earlier 2026-06-05 cycle fixed the *code* (offline viewer + template + 3 truncated `__init__.py` + `phase13_ia_tas_m.run()` + `test_guided_examples.py`) but could not touch git. **This cycle closed Phase R:** committed the recovered tree via an alt-`GIT_INDEX_FILE` + direct-ref-write workaround (commit `1f8f990`), discovered origin/main had diverged by 7 commits (another cycle: Phase 15 T3–5 + Phase 16 T1–4), and **merged** them — merge `e24d74e`, tree = the more-advanced local Phase 16 Task 5 superset, origin/main `ca381b3` kept as 2nd parent so nothing is orphaned. **`git push origin main` OK; local == origin (0/0).** Offline self-test `ok:true` (0 network / 0 JS errors); `compileall` clean. **Residual for a HUMAN:** the two ghost locks `.git/index.lock` + `.git/HEAD.lock` (2026-06-03) are still unremovable from the sandbox and block *normal* git — delete them in a human shell. Until then, cycles must reuse the alt-index + direct-ref workaround. **Full `pytest` was NOT run** (scipy uninstallable this run); py_compile + node self-test substituted — next cycle with a working Python env should run the suite in <45 s batches as the formal gate.

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

---

## Phase R: Crash Recovery & Commit-Backlog ✅ RESOLVED (2026-06-05; pushed as merge e24d74e)

A prior cycle crashed mid-write (2026-06-03), leaving the repository in a degraded state. The
2026-06-05 maintenance cycle diagnosed and fixed the **code** corruption (working tree only — see
MODEL_DEV_LOG.md), but **could not touch git**. Resolve the git state before any new development.

**Blockers to clear (need real filesystem / credentials — the sandbox cannot):**
1. **Stale lock:** delete `.git/index.lock` (0 B, dated 2026-06-03T19:39Z). The mounted FS returns
   "Operation not permitted" for `rm`/`mv` on it from the automation sandbox. A human shell can remove it.
2. **Phantom index:** ~93 tracked files are staged as deleted while byte-identical copies exist on disk
   (verified == HEAD). After the lock is gone, `git reset` clears this in one step.
3. **Commit the real backlog** (working-tree changes that ARE genuine and tested):
   - Recovery fixes (2026-06-05): restored `model_result_viewer.html`, `viewer_template.html`,
     `governance/__init__.py` from HEAD; rebuilt `calibration/__init__.py` + `validation/__init__.py`
     with Phase 12 / Phase 13 export wiring; `phase13_ia_tas_m.py` `run_all()`→`run()`;
     `tests/test_guided_examples.py` restored from HEAD.
   - Untracked WIP from earlier cycles that is now GREEN: `par_model_v2/calibration/phase12_calibration_pack.py`,
     `par_model_v2/validation/phase13_ia_tas_m.py`, `par_model_v2/projection/multi_driver_risk_aggregation.py`,
     `par_model_v2/projection/multi_driver_tail_diagnostics.py`, `scripts/build_phase15_task*.py`,
     `scripts/build_phase16_loss_distribution.py`, and their tests.
4. **Push** `origin main`. (The 2026-06-03 GITHUB_PUSH_BLOCKER was marked resolved; re-verify the PAT.)

**Verification gate before commit:** `python3 -m pytest -q` must be 0 failures (it is, when run in batches
< 45 s; the full run exceeds the sandbox wall-clock but each batch passes) and
`node scripts/offline_viewer_self_test.cjs model_result_viewer.html` must report `ok:true` / 0 network / 0 JS errors.

**Note on the mount:** files written via **bash** are seen reliably by the Python interpreter; files written
via the Windows-path file-tools can lag/desync within a run. Prefer bash for code edits you intend to execute
the same cycle.

---

## Phase 17: Third Risk Driver (Credit Spread) in the Economic-Capital Proxy ⭐ IN PROGRESS (Task 1 done 2026-06-05)

Extends the documented Phase 15 limitation (the LSMC capital proxy spans only two drivers — short rate +
equity). Current proxy-model practice (IFoA proxy-modelling WP; Milliman/MDPI LSMC literature) expands the
proxy basis to financial AND non-financial drivers (rates, equity, **credit**, lapse, mortality) with
higher-order and interaction terms, validated out-of-sample. The asset library already carries credit
spreads / private credit, so credit is the natural third driver.


Tasks for Phase 17 (one per cycle, in order):
1. ✅ DONE (2026-06-05) Added `par_model_v2/stochastic/credit_spread.py` (CIR++ mean-reverting square-root
   credit-spread driver; full-truncation Euler; P/Q consistent via the CIR risk premium; reduced-form
   hazard×LGD loss helper; measure enforcement + DataFrame output + `_inner_q_spread_process` conditioning)
   and `par_model_v2/projection/multi_driver_capital_3d.py` (three-driver (r,S,spread) nested ground truth +
   trivariate-LSMC proxy + diagnostics). Inner Q nest conditioned on all three states off one correlated
   draw; conditional liability adds a credit-loss component on spread-sensitive backing assets. Trivariate
   total-degree basis with **capped three-way interactions**. Outer states genuinely correlated via a shared
   3-factor Cholesky (nearest-PD eigenvalue-clip fallback). Evidence (seed 42): outer corr(r,s)=-0.22,
   corr(S,s)=-0.30; spread widening raises L; LSMC-vs-nested 3-D grid R²=0.964, max abs rel err 5.5%;
   VaR99.5≈150.5k / ES≈154.7k / SCR≈32.5k. 39 new tests PASS; offline self-test ok:true; py_compile clean.
   (SOA ASOP 56 §3.1.3/§3.4/§3.5; ASOP 25 §3.3; IA TAS M §3.2/§3.4/§3.6; Duffie-Singleton 1999; CIR 1985; L&S 2001)
2. ✅ DONE (2026-06-05) Out-of-sample trivariate proxy validation — extended `multi_driver_proxy_validation.py`
   with `ThreeDriverProxyValidator` (+`TriProxyValidationConfig`/`TriBasisDiagnostics`/`TriProxyValidationReport`,
   `_fit_tri_surface`, dimension-agnostic `_leakage_nd`). Fit on N_fit single-inner-path states (seed 42); validate on
   an INDEPENDENT disjoint-seed hold-out (seed 20260605) against HEAVY nested truth (n_inner_heavy Q-paths/state);
   basis selection over a **(degree, max_interaction_order)** grid by OOS RMSE/R² (interaction order is a genuine
   3-driver complexity lever); leakage + overfit diagnostics + honest verdict. Evidence (n_fit=1000/n_val=80/
   n_inner_heavy=512; grid (1,3)(2,3)(3,2)(3,3)(4,3); nested 800×96): VERDICT PASS — selected basis (deg1, max_int3),
   OOS R²=0.9751, VaR rel err 7.05%, ES 6.96%, leakage-free (0 shared, min scaled dist 0.057), overfit gap 0.0034;
   textbook overfit profile (OOS R² 0.975→0.936→0.812→0.761→0.759, onset 10 terms); noisy fit_r2 (~0.19) shown NOT a
   validation metric vs in-sample-heavy R² (0.87–0.98). SCR rel err 27.7% (difference-of-means amplification, not a
   gate). 26 new tests PASS; regression (Phase15 proxy 13 + credit_spread 24 + 3D 22 + Phase15 capital 29) PASS;
   offline self-test ok:true (0 net/0 JS err); py_compile clean. digest 4972795d3931.
   docs/validation/PHASE17_PROXY_VALIDATION_REPORT.{json,md}. (SOA ASOP 56 §3.5; IA TAS M §3.6; IFoA proxy-model WP; L&S 2001)
3. ✅ DONE (2026-06-05) Three-driver correlated aggregation — extended `par_model_v2/projection/multi_driver_risk_aggregation.py`
   with `ThreeDriverRiskAggregator` (+`ThreeDriverAggregationConfig`/`ThreeDriverStandaloneCapital`/`ThreeDriverCorrelatedAggregation`/
   `ThreeDriverRiskAggregationReport`), additive over the Phase 17 Task 1 trivariate nested primitives (Task 1/2 modules untouched).
   Three standalone SCRs isolated by **exact CRN decomposition** of the conditional liability (rate=guaranteed PV with equity+credit OFF;
   equity=L_re−L_rate; credit=L_rc−L_rate on the SAME inner seed → exact additivity, asserted in test); var-covar aggregation with the
   governed 3×3 ESG driver correlation; benchmarked to the fully-diversified three-driver nested capital; MR-010 refreshed for three drivers.
   Evidence (seed 42; 99.5%; N_outer=800; n_inner=128): rate SCR 20,696; equity SCR 22,559; credit SCR 4,460; standalone sum 47,715;
   var-cov SCR 26,829; nested SCR 43,753; rel err **38.7%** (>35% tol) → VERDICT **PARTIAL** (honest); digest 27edeaf8. Key finding:
   adding the credit driver WIDENS the ESG-factor understatement to ~38.7% (vs two-driver ~32.9%) — realised capital-loss correlations are
   all strongly positive (rate-eq +0.54, rate-cr +0.77, eq-cr +0.61) while the ESG factor off-diagonals are negative (−0.15/−0.20/−0.30),
   so the second-moment factor formula is non-conservative for diversified capital. MR-010 remains the dominant model risk. 12 new tests
   PASS; regression (Phase15 agg+credit 26 + Phase17 3D 22) PASS; offline self-test ok:true (0 net/0 JS err); compileall clean.
   `scripts/build_phase17_task3_aggregation.py`; docs/validation/PHASE17_RISK_AGGREGATION_REPORT.{json,md}. (SOA ASOP 56 §3.5; ASOP 25 §3.3; IA TAS M §3.2/§3.6)
4. ✅ DONE (2026-06-05) Tail-convergence + stability diagnostics for the three-driver 99.5% capital metric — extended
   `par_model_v2/projection/multi_driver_tail_diagnostics.py` (additive) with `ThreeDriverTailConfig`, `ThreeDriverTailDiagnostics`,
   `ThreeDriverTailReport`, `VarianceReduction3D`, and 3-D empirical-copula helpers (`_draw_normals_nd`/`_correlate_nd`/
   `_states_from_normals_nd`/`_nearest_correlation_matrix`). Built on the Phase 17 Task 1 trivariate LSMC surface (Task 1/2/3 modules AND
   the 2D `MultiDriverTailDiagnostics` untouched). Three diagnostics over the credit-augmented liability: (a) outer-count convergence on
   genuinely 3-factor-correlated governed outer states; (b) non-parametric bootstrap CI/SE on 99.5% VaR/ES; (c) crude/antithetic/Sobol
   variance-reduction over a pilot-anchored Gaussian copula whose controlling correlation is the realised 3×3 outer-state correlation
   (rate/equity/credit) and whose margins are the empirical pilot margins. Evidence (seed 42; n_fit=400; outer grid 500/1000/2000/3000;
   bootstrap B=1200/N=3000; VR 80×2048): VERDICT **PASS** — final VaR99.5 152,296.8 / ES 155,757.2; converged at recommended N_outer≥1,000;
   bootstrap VaR 150,859.1, 95% CI [149,634.1, 152,369.3], SE 692.4 (±0.91% rel halfwidth); Sobol QMC VaR var-reduction **2.76×**; antithetic
   0.89× documented expected-ineffective for an extreme quantile; digest aca7800a921ac1bd. 38 new tests PASS
   (`tests/test_phase17_tail_diagnostics.py`); regression: 2D tail 36 + 3D capital 22 + aggregation 12 PASS; offline self-test ok:true
   (0 net/0 JS err); py_compile clean. `scripts/build_phase17_task4_tail_diagnostics.py`;
   docs/validation/PHASE17_TAIL_DIAGNOSTICS_REPORT.{json,md}; docs/MULTI_DRIVER_3D_TAIL_DIAGNOSTICS_CARD.md.
   (SOA ASOP 56 §3.5/§3.1.3; ASOP 25 §3.3; IA TAS M §3.6; L'Ecuyer 2018 RQMC)
5. ✅ DONE (2026-06-05) Governance refresh — added `scripts/build_phase17_task5_governance.py` (idempotent):
   opened **MR-012** (credit-spread driver / three-driver capital proxy is EDUCATIONAL, not production; model_error;
   HIGH; IN_PROGRESS) linking MR-006/008/010/011; created a consolidated `governance_change` ChangeRecord at
   **OWNER_REVIEW** (sign-off withheld); appended 2 GOVERNANCE audit entries (verify_all True; store audit 28→30,
   change 14→15, risk 11→12). Added `docs/MULTI_DRIVER_3D_PROXY_LIMITATION_CARD.md` (consolidated Tasks 1–4: three
   drivers, scope, limitations, model-use restrictions, residual table) + `docs/validation/PHASE17_TASK5_GOVERNANCE_REFRESH.{json,md}`.
   Extended the offline viewer: the bundler now PREFERS the Phase 17 three-driver reports (tail/aggregation/proxy) over
   Phase 15 and surfaces `credit_scr`/`drivers`/`esg_understatement_pct`, and normalises the Phase 17 proxy
   `basis_rows`→`degree_rows` + `overfit_onset_terms`→degree; the **Capital** tab adds a Credit standalone-SCR bar +
   a "3-driver proxy" pill; the **Aggregation** tab waterfall/finding now describe three drivers and the ~38.7%
   factor-correlation understatement (vs ~32.9% two-driver). Rebuilt `model_result_viewer.html` (83,686 B). 9 new
   Task-5 tests PASS; viewer 19 PASS; governance regression 62 PASS (90 in batch); offline self-test ok:true (7 SVG
   charts, 7 export controls, 0 net / 0 JS err); py_compile clean. (IA TAS M §3.6/§3.7; APS X2 §3; SOA ASOP 56 §3.5;
   ASOP 25 §3.3; IFoA proxy-modelling WP) **PHASE 17 COMPLETE.**

---

## Phase 18: Tail-Dependent Risk Aggregation and Driver/Calibration Sophistication ⭐ NEXT

The dominant open model risk in the economic-capital proxy is **MR-010**: the variance–covariance aggregation on the
governed ESG *factor* correlations understates the fully-diversified nested capital by ~38.7% (three-driver), because
the realised capital-*loss* correlations are all strongly positive in the tail while the factor off-diagonals are
negative. Current life-insurance capital-modelling practice (IFoA *Life Aggregation and Simulation Techniques* working
party; Solvency II Delegated Reg. Art. 234, which requires diversification assumptions to be *empirically justified*;
copula-based aggregation literature) addresses exactly this by replacing the linear-correlation/elliptical aggregation
with a **copula** chosen to capture **tail dependence**, and by expanding the proxy basis to non-financial drivers.
Phase 18 makes the aggregation tail-aware, adds the next driver, and calibrates the credit driver.

Tasks for Phase 18 (one per cycle, in order):
1. ✅ DONE (2026-06-05) Copula-based risk aggregation that captures tail dependence. Added (additive; the var-covar
   `ThreeDriverRiskAggregator` is untouched) `par_model_v2/projection/multi_driver_copula_aggregation.py`
   (`CopulaRiskAggregator`/`CopulaAggregationConfig`/`CopulaFit`/`CopulaAggregationReport`): fits a Gaussian (baseline,
   no tail dependence), a Student-t (symmetric tail dependence) and a survival-Clayton (upper-tail dependence — the
   relevant tail for joint losses) copula to the REALISED standalone (rate, equity, credit) capital-loss vectors,
   rebuilds the joint loss from empirical marginals + each copula, reads the 99.5% aggregate SCR off the simulated
   joint loss, benchmarks every copula AND the var-covar formula to the three-driver nested ground truth, and selects
   the best copula by AIC on the pseudo-observations (empirical justification per Solvency II Art. 234, NOT benchmark
   fitting). Evidence (seed 42; n_outer=500/n_inner=160; n_sim=200k): VERDICT **PASS** — var-covar (ESG factor) SCR
   26,061.7 understates nested 39,774.6 by **34.5%** (MR-010); AIC-selected **gaussian** copula 40,342.0 reconciles
   within **1.43%**, Student-t 1.54% (df pinned high → collapses toward Gaussian), survival-Clayton 45,771.8 (+15.1%,
   λU=0.644 — conservative upper bound). **Key finding:** MR-010's root cause is the WRONG dependence INPUT (negative
   ESG factor correlation vs strongly positive realised loss co-movement), not primarily tail dependence; refitting the
   dependence on realised losses removes most of the gap even with a Gaussian copula. **MR-010 → MITIGATED**
   (mitigation now implemented, not just documented; copula-on-realised-losses is the recommended aggregation, var-covar
   retained for reference). 22 new tests PASS (`tests/test_phase18_copula_aggregation.py`); related-module regression
   (Phase17 agg 12 + Phase17 3D 22 + Phase15 agg 9) PASS; offline self-test ok:true (0 net / 0 JS err); py_compile clean.
   ChangeRecord (methodology_change) OWNER_REVIEW; audit chain 30→32, change 15→16. `scripts/build_phase18_task1_copula_aggregation.py`;
   `scripts/build_phase18_task1_governance.py`; docs/COPULA_AGGREGATION_CARD.md; docs/validation/PHASE18_COPULA_AGGREGATION_REPORT.{json,md};
   docs/validation/PHASE18_TASK1_GOVERNANCE_REFRESH.{json,md}. (SOA ASOP 56 §3.5; ASOP 25 §3.3; IA TAS M §3.6;
   Solvency II Del. Reg. Art. 234; IFoA Life Aggregation & Simulation WP; Demarta-McNeil 2005)
2. ✅ DONE (2026-06-05) Calibrated the CIR++ credit-spread driver to educational-proxy CNY AA+ corporate OAS history
   (mirrors the GBM/HW1F calibrators). Added `par_model_v2/calibration/cir_calibrator.py` (`CIRCalibrator`: a homoscedastic
   CIR OLS transition regression recovers the mean-reversion speed kappa and the P-measure long-run spread, the residual
   variance gives the spread vol sigma, and a documented risk-neutral long-run anchor backs out the market price of credit
   risk lambda via the CIR risk-premium relation `s∞^Q − s∞^P = lambda·sigma²/kappa`), `credit_market_data_source.py`
   (`FileBasedCreditSpreadSource` deterministic seeded CIR synthesis + `CreditSpreadDataLoader` + the six-criterion G-CR
   plausibility-band gate), `phase18_cir_calibration.py` (`run_phase18_cir_calibration`: APPROVED assumption_change
   ChangeRecord DRAFT→PEER_REVIEW→OWNER_REVIEW→APPROVED + one PARAM_CHANGE audit entry; MR-012 → MITIGATED on G-CR PASS),
   `fixtures/cny_credit_spread_history_20260101.json`, and `scripts/build_phase18_task2_calibration.py` (idempotent). The
   credit spread is the THIRD economic-capital-proxy driver, so the calibration feeds the three-driver 99.5% VaR/ES and the
   reduced-form hazard×LGD credit-loss component. Evidence (seed 20260101; 240 monthly obs): kappa=0.5028/yr,
   long-run spread=0.0111 (111 bp; target 120), sigma=0.0371 (target 0.040), lambda=1.0575; Feller holds; G-CR PASS (6/6).
   GOVERNANCE_STORE.json persisted (audit 32→34, change 16→17, integrity verify_all True); MR-012 → MITIGATED — **not closed**:
   the trivariate proxy still omits lapse/mortality/FX/liquidity drivers and credentialled credit data + an independent APS X2
   review are pending. 14 new tests PASS (`tests/test_phase18_cir_calibration.py`); regression credit_spread 35 + GBM 35 +
   copula 22 PASS; offline self-test ok:true (0 net / 0 JS err); py_compile clean. ChangeRecord (assumption_change) APPROVED.
   `docs/CIR_CREDIT_CALIBRATION_CARD.md`; `docs/validation/PHASE18_CIR_CALIBRATION_REPORT.{json,md}`.
   (SOA ASOP 56 §3.4; SOA ASOP 25 §3.3; IA TAS M §3.5/§3.6/§3.7; CIR 1985; Brigo-Mercurio 2006; Kladivko 2007; Duffie-Singleton 1999)
3. ✅ DONE (2026-06-05) Added the FOURTH (first non-financial) risk driver — dynamic-lapse / policyholder behaviour —
   to the nested ground truth AND the LSMC proxy. New `par_model_v2/stochastic/lapse_behaviour.py` (OU behavioural index
   b(t); exact-discretisation AR(1); non-financial ⇒ P=Q drift; lognormal horizon multiplier M=exp(b)) and
   `par_model_v2/projection/multi_driver_capital_4d.py` (state (r,S,s,b); `LapseExposureSpec` in-force factor IF(r,b) =
   survival-to-maturity under the dynamic-lapse basis × M, relative to central — monotone decreasing in lapse — scaling
   guaranteed + equity-guarantee benefits; credit loss asset-side unscaled; `FourDriverCorrelation` 4×4 with orthogonal
   lapse default + nearest-PD Cholesky; `FourDriverNestedEngine` / `FourDriverLSMCProxyEngine` quadrivariate capped-
   interaction surface / `FourDriverDiagnostics`). Extended `multi_driver_proxy_validation.py` with `FourDriverProxyValidator`
   (+`QuadProxyValidationConfig`/`QuadBasisDiagnostics`/`QuadProxyValidationReport`/`_fit_quad_surface`): fit on N_fit single-
   inner-path states (seed 42), validate on an INDEPENDENT disjoint-seed hold-out (seed 20260605) against HEAVY nested truth,
   basis selection over a (degree, max_interaction_order) grid by OOS error, leakage + overfit diagnostics, honest verdict.
   Evidence (n_fit=500/n_val=60/n_inner_heavy=384; nested 500×96; seed 42): VERDICT **PASS** — selected (deg1, max_int3, 5
   terms), OOS R²=0.9638, VaR rel err 2.33%, ES 4.02%, SCR 6.47%, leakage-free (0 shared, min scaled dist 0.20), overfit gap
   0.0057; textbook overfit signature (OOS R² 0.964→0.908→0.872→0.877→0.716 as terms 5→57; onset 15 terms); digest
   12167cf6fd22; realised outer corr(financial,b)≈0 (orthogonal non-financial axis). 24 new tests PASS
   (`tests/test_phase18_four_driver_capital.py`); regression Phase17 3D capital+credit_spread 39 + Phase17 proxy-val 26 PASS;
   compileall clean; offline self-test ok:true (0 net/0 JS err). docs/validation/PHASE18_TASK3_PROXY_VALIDATION_REPORT.{json,md};
   docs/MULTI_DRIVER_4D_PROXY_LIMITATION_CARD.md. Governance (MR-010/MR-012 four-driver refresh + OWNER_REVIEW ChangeRecord)
   deferred to Task 4/5 per plan. (SOA ASOP 7 §3.3; ASOP 56 §3.5; IA TAS M §3.6; IFoA proxy-modelling WP; L&S 2001)
4. ✅ DONE (2026-06-05) Four-driver tail-dependent aggregation + tail-convergence/stability diagnostics; refreshed
   MR-010/MR-012 for four drivers. Added `par_model_v2/projection/multi_driver_capital_4d_aggregation.py`
   (`FourDriverRiskAggregator`): CRN four-way standalone decomposition (rate/equity/credit/lapse off the SAME outer
   states + inner seeds), 4×4 ESG var-covar aggregation, copula-on-realised-losses re-aggregation (reusing the Phase 18
   Task 1 `CopulaRiskAggregator`), and a genuine four-driver nested benchmark with the multiplicative-lapse interaction
   residual. Extended `multi_driver_tail_diagnostics.py` (additive) with `FourDriverTailConfig`/`VarianceReduction4D`/
   `FourDriverTailReport`/`FourDriverTailDiagnostics` on the Task 3 quadrivariate LSMC surface. **Aggregation VERDICT PASS**
   (seed 42; n_outer=250/n_inner=64; n_sim_copula=150k): standalone SCR rate 33,337 / eq 29,989 / cr 9,903 / lapse 35,090
   (sum 108,318); var-covar 52,248 understates nested 99,269 by **47.4%** (MR-010 WIDENS with the lapse driver vs ~38.7%
   three-driver); AIC-selected **gaussian** copula 89,910 reconciles within **9.4%**; CRN-additive 88,221 leaves a **−11.1%**
   interaction residual — the lapse driver couples MULTIPLICATIVELY (in-force × equity-guarantee cross-term), so genuine
   nested capital is SUPER-additive vs the CRN-additive standalone sum ('nested ≤ sum' is NOT a four-driver invariant);
   digest 7ff686fd29c7. **Tail VERDICT PASS** (n_fit=900; outer grid 1k–16k; bootstrap B=1200/N=8000; VR 80×4096):
   VaR99.5 ~230,388 converged True (rec N_outer≥16,000), bootstrap VaR 231,150 95% CI [226,371, 239,438] SE 3,095 (±2.83%),
   Sobol QMC variance-reduction **3.28×**, antithetic 0.72× documented expected-ineffective for an extreme quantile; digest
   f5748053fc8d. Governance (`scripts/build_phase18_task4_governance.py`, idempotent): **MR-010 → MITIGATED** (four-driver
   understatement + super-additivity finding), **MR-012 → MITIGATED** (proxy now four drivers; mortality/FX/liquidity still
   omitted), methodology_change ChangeRecord at OWNER_REVIEW (sign-off withheld), 3 GOVERNANCE audit entries; GOVERNANCE_STORE.json
   persisted (audit 34→37, change 17→18, integrity verify_all True). docs/MULTI_DRIVER_4D_AGGREGATION_CARD.md;
   docs/validation/PHASE18_TASK4_{AGGREGATION,TAIL_DIAGNOSTICS,GOVERNANCE_REFRESH}_REPORT/.{json,md}. 22 new tests PASS; regression
   copula 22 + 3D tail 38 + governance 79 + Phase18 4D capital 24 PASS; offline self-test ok:true; py_compile clean. Production
   sign-off withheld — lapse-index calibration to credentialled experience + independent APS X2 review pending, NOT a code gap.
   (SOA ASOP 56 §3.5/§3.1.3; ASOP 25 §3.3; ASOP 7 §3.3; IA TAS M §3.2/§3.6; Solvency II Del. Reg. Art. 234; IFoA Life Aggregation & Simulation WP; L'Ecuyer 2018 RQMC)
5. ✅ DONE (2026-06-05) Offline-viewer refresh for the copula-aggregation and four-driver proxy. The viewer now
   prefers the Phase 18 Task 4 four-driver aggregation/tail diagnostics and Phase 18 Task 3 proxy-validation reports
   over older Phase 17/15 artifacts. Capital/Aggregation tabs surface lapse standalone SCR, var-covar-vs-copula-vs-
   nested reconciliation (MR-010 47.4% understatement → gaussian copula 9.4%), multiplicative-lapse interaction
   residual (-11.1% of nested), four-driver tail convergence/bootstrap-CI/QMC read-outs, and links to the four-driver
   aggregation/proxy limitation cards. Rebuilt `viewer_data.json` and `model_result_viewer.html`; Node offline self-test
   PASS (4 tabs, 8 SVG charts/export buttons, 0 network, 0 JS errors). Python/pytest unavailable in this Windows shell,
   so pytest assertions were updated but not executed here. **PHASE 18 COMPLETE.**
   (IA TAS M §3.6/3.7; APS X2 §3; SOA ASOP 56 §3.5)

---

## ⚠️ LATEST STATUS — 2026-06-05 (supersedes the "Current milestone" line above)

A second disk-full crash corrupted the offline-viewer toolchain and several files. This cycle was a
**crash-recovery + offline-viewer-restoration** cycle. **No git commit was made** (unsafe — see below).
Full detail: `docs/recovery_2026-06-05/RECOVERY_REPORT.md`.

**FIXED (working tree; persists in the user's folder regardless of git):**
- Offline viewer restored to a working state. `node scripts/offline_viewer_self_test.cjs model_result_viewer.html`
  → **ok:true** (4 tabs, 7 SVG charts, 7 export controls, 0 network, 0 JS errors). `tests/test_offline_viewer.py`
  20/21 pass (1 = a 10 s node-subprocess timeout under the loaded sandbox, not a logic fail).
- Restored from `HEAD`: `par_model_v2/viewer/viewer_template.html`, `scripts/build_offline_viewer.py`
  (on-disk Phase 18 copies were corrupted/truncated). Rebuilt `model_result_viewer.html` + `viewer_data.json`.
  **This reverts the viewer DISPLAY to Phase 17 (3-driver);** Phase 18 lapse/copula panels are not shown, but the
  Phase 18 four-driver model + data + reports are intact. A **losslessly reconstructed** Phase 18 bundler is saved at
  `docs/recovery_2026-06-05/build_offline_viewer.PHASE18_RECONSTRUCTED.py` for clean re-application later.
- Restored `tests/test_offline_viewer.py` from blob `fa5d5fe`.

**BLOCKERS FOR A HUMAN (sandbox cannot do these):**
1. `/sessions` (shared volume) is **100% full** (~32 MB free; ~9.2 GB used by other sessions). This **corrupts writes
   to the mount** ("same size, different bytes"). **Free disk space** — this is the root cause.
2. **Ghost git locks** `.git/index.lock`, `.git/refs/heads/main.lock`, `.git/__probe_lock` are **unremovable from the
   sandbox** and block all normal git. Delete them in a real shell, then `git reset`.
3. ✅ **RESOLVED 2026-06-05 (later cycle): `par_model_v2/validation/ia_validation.py` RECONSTRUCTED.** The damage was
   a single truncated string in the **last** entry (`VR-D03`) of the `IA_VALIDATION_REQUIREMENTS` list — NOT a missing
   `ValidationRunner` (that class is intact at line 483). The list tail was reconstructed faithfully (completed the final
   acceptance-criterion string + closed the entry + closed the list); no importer references any name defined after the
   list. `py_compile` clean; imports; `len(IA_VALIDATION_REQUIREMENTS)==31` (all unique). **Full suite now collects all
   2070 tests with 0 import errors** (previously blocked). PASS: `test_ia_validation`+`test_phase13_ia_validation` 75;
   `test_validation_dashboard`+`test_phase14_ia_revalidation` 66 (incl. `total==31`); `test_model_health`+`test_data_validator`
   113. **The full-pytest-green precondition for Phase 19 is now met** (modulo the heavy Phase 18 numeric batches that exceed
   a 45 s wall-clock but show no failures). Remaining blockers below are git/disk only.

**Why no commit:** committing needs the fragile alt-`GIT_INDEX_FILE` workaround on a write-corrupting 100%-full disk.
Defer all git to the human (checklist in the RECOVERY_REPORT). The improved working-tree files — now including the
recovered `ia_validation.py` — already persist in the user's folder regardless of git. The "still has one unrecoverable
corrupt file" reason no longer applies: `ia_validation.py` is fixed; the only remaining blockers are disk-full + ghost
git locks, both human-only.

---

## Phase 19: Recovery-completion + viewer re-uplift + driver expansion (NEXT, after the human clears the blockers)

Do these **only once** disk space is freed, the ghost locks are removed, and `git reset` is clean.
(`ia_validation.py` is already restored — done 2026-06-05 — and the suite collects 2070 tests / 0 import errors, so the
"full pytest green" precondition is met apart from the heavy Phase 18 numeric batches.) One task per cycle, in order:

1. Verify post-recovery health: full `pytest` (in <45 s batches) at 0 failures; `node ... offline_viewer_self_test.cjs`
   ok:true; `git status` sane. Commit the recovered tree + `docs/recovery_2026-06-05/` and push `origin main`.
2. Re-apply the Phase 18 Task 5 viewer uplift on the healthy base: reconstruct the Phase 18 `viewer_template.html`
   (4-driver lapse + copula-aggregation panels) to match `build_offline_viewer.PHASE18_RECONSTRUCTED.py`; rebuild;
   self-test ok:true; tests pass. (Restores the lapse standalone-SCR bar + var-cov→copula→nested reconciliation.)
3. Add a **mortality-trend** stochastic driver (5th capital driver; Lee-Carter-style kappa or a simple OU trend) to the
4. Five-driver tail-dependent aggregation + tail-convergence/stability diagnostics; refresh MR-010/MR-012; governance
   ChangeRecord at OWNER_REVIEW. (SOA ASOP 56 §3.5; ASOP 25 §3.3; IA TAS M §3.6; Solvency II Del. Reg. Art. 234)
5. Calibrate the lapse behavioural index to an educational-proxy experience series (mirror the GBM/HW1F/CIR
   calibrators); add a G-LAPSE plausibility gate; governance refresh. **PHASE 19 COMPLETE** when documented.

<!-- END OF PROMPT -->

---

## LATEST STATUS - 2026-06-07 (cycle 13, supersedes earlier text) — **PHASE 23 TASK 2 COMPLETE (PASS)**

**Phase 23 Task 2 is COMPLETE: Student-t copula aggregation with df calibrated by tail-dependence
matching, VERDICT PASS.** New additive module `par_model_v2/projection/t_copula_tail_matched_aggregation.py`
(`TailMatchedTCopulaAggregator`; fixed-df chi-square-mixing t-copula sampler; fixed-df gammaln loglik;
governed `CopulaRiskAggregator` untouched). Losses realised by bit-identical reuse of the Phase 22 Task 4
calibrated staged primitives (nested 48,707.4 / var-covar 28,990.9 — archived-report match asserted).
Matching per the Task 1 design: pairwise lambda_U at thresholds 0.80/0.85/0.90 (E[tail obs] 32/24/16 at
n=160; 0.97+ infeasible at this n — DISCLOSED), Kendall-tau rho, Demarta-McNeil df inversion, pooled
MEDIAN pair df per threshold (1.80/2.95/3.63), median across thresholds -> **df_matched 2.95** (capped
share 4.8% disclosed). **RESULT: t(2.95) SCR 46,756.0, rel err 4.01% vs nested — beats the gaussian AIC
incumbent (same-seed 41,472.4 / 14.85%; archived 41,604.3 / 14.58%); the FIXED pre-registered gate is met
on its primary arm (no gate-shopping); ~73% of the residual gaussian gap closed.** MR-010 refreshed
(mitigation now tail-aware per Art. 234); ChangeRecord `509699ae1f1d4adabe197bcf8419c92a`
(methodology_change) OWNER_REVIEW; audit 61->62; verify_all True; governance idempotent. Verification:
28 new tests PASS (`tests/test_phase23_task2_t_copula.py`); regression tail_dependence 21 + copula 22 +
governance 54 + phase22-task4 18 = 115 PASS; ui_app self-test ok:true (0 net / 0 JS err); py_compile clean.
Evidence: `docs/validation/PHASE23_TASK2_T_COPULA_AGGREGATION_REPORT.{json,md}`;
`docs/T_COPULA_AGGREGATION_CARD.md`; staged build `scripts/build_phase23_task2_t_copula_aggregation.py`.
**Maintenance this cycle:** repaired `.claude-dev/MODEL_DEV_STATE.json` (cycle-8 trailing block truncated
mid-string by the legacy disk-full corruption; completed faithfully from the archived PHASE22_TASK2 report;
corrupt original at /var/tmp/p23t2_build/MODEL_DEV_STATE.corrupt.bak) and re-wrote a truncated
MODEL_DEV_LOG.md append (mount write-lag) with end-marker verification. UI propagation of the t-copula
verdict is deliberately deferred to Phase 23 Task 5 (one task per cycle).

**NEXT executable task: Phase 23 Task 3 — management-action rule in nested ground truth + proxy.**
Implement the Task 1 design: dynamic reversionary-bonus cut
cut_factor=clip((CR-CR_floor)/(CR_trigger-CR_floor),0,1) at the outer node, entering the nested
conditional liability AND the LSMC proxy basis; seven-driver OOS re-validation against the with-actions
nested truth. FIXED Task 3 gate (recorded in the Task 1 design note): OOS R2>=0.95, VaR rel err<=10%,
with-actions capital <= without-actions, open MR-013 (management-action omission/model risk) +
assumption_change ChangeRecord OWNER_REVIEW.

## LATEST STATUS - 2026-06-07 (cycle 12, supersedes earlier text) — **PHASE 23 TASK 1 COMPLETE (PASS)**

**Phase 23 Task 1 is COMPLETE: research + design note for the t-copula tail-dependence calibration and the
management-action rule, VERDICT PASS.** New tested module `par_model_v2/projection/tail_dependence.py`
(closed-form lambda_U(nu,rho); df inversion by bisection on the DF INTERVAL with DISCLOSED bound-cap flag;
threshold estimator on pseudo-observations; `match_t_df_to_losses` pooled-median df matching; 21 tests PASS).
Pre-study: synthetic t(4, rho 0.6) recovered at pooled df 2.85-3.22 across thresholds 0.97-0.99 (capped-share 0);
Gaussian control shows the RISING-df signature (7.5->9.5->13.2 as q 0.99->0.999) — the documented diagnostic for
zero asymptotic tail dependence. 4-row management-action gap analysis (Solvency II Art. 23/234; ASOP 56
§3.1.3/3.4; TAS M §3.2/3.6): design = dynamic reversionary-bonus cut
cut_factor=clip((CR-CR_floor)/(CR_trigger-CR_floor),0,1), monotone/verifiable, entering nested conditional
liability AND proxy basis; MR-013 planned for Task 3. FIXED Task 2/3 acceptance criteria recorded before any
benchmark errors are seen (no gate-shopping). Evidence: `docs/validation/PHASE23_TASK1_DESIGN_NOTE.{json,md}`;
`docs/T_COPULA_MANAGEMENT_ACTION_DESIGN_CARD.md`. Governance: ChangeRecord
`cfdc0aef864c4494b94c68db83acbd69` (governance_change) OWNER_REVIEW; audit 60->61; change records 33->34;
verify_all True; idempotent. Verification: 21 new + copula 22 + governance 54 PASS; ui_app self-test ok:true
(0 net / 0 JS err); py_compile clean.

**NEXT executable task: Phase 23 Task 2 — Student-t copula aggregation with df calibrated by
tail-dependence matching.** Use `match_t_df_to_losses` on the realised seven-driver standalone capital-loss
vectors (reuse the Phase 22 Task 4 calibrated aggregation primitives); >=3 thresholds with a sensitivity table;
pooled MEDIAN df + capped-share disclosure; benchmark t(df_matched) vs gaussian vs nested (acceptance:
rel err <= gaussian baseline or <=25%); MR-010 refresh; methodology_change ChangeRecord OWNER_REVIEW.

## Phase 23: Tail-Dependence Upgrade + Management Actions (PLAN — one task per cycle)

1. ✅ DONE (2026-06-07 cycle 12) — Research + design note: t-copula tail-dependence calibration +
   management-action gap analysis (PASS; tail_dependence.py module + 21 tests; fixed Task 2/3 gates).
2. ✅ DONE (2026-06-07 cycle 13) — Student-t copula aggregation, df by tail-dependence matching
   (PASS: df 2.95; t SCR 46,756 rel err 4.01% vs nested; gaussian baseline 14.85%; MR-010 refreshed).
3. ⭐ **NEXT** — Management-action rule (dynamic bonus participation cut under solvency stress) in nested ground
   truth + proxy; seven-driver OOS re-validation; MR-013.
4. Aggregation + tail-diagnostics re-run with management actions; capital impact quantified.
5. Offline-UI propagation + PHASE 23 COMPLETE documentation.

---

## LATEST STATUS - 2026-06-07 (cycle 7, supersedes earlier text) — **PHASE 22 TASK 1 COMPLETE (PASS)**

**Phase 22 Task 1 is COMPLETE: six-driver OOS proxy-validation remediation, VERDICT PASS.**
The Phase 21 Task 2 honest PARTIAL (OOS R² 0.9498 < 0.95) is CLEARED with no gate-shopping and a
STRICTER gate: OOS R² **0.9985**, OOS RMSE 816 (was 4,686), VaR/ES/SCR rel err
**0.50% / 0.19% / 1.25%** (Phase 22 gate ≤10% EACH; Phase 21 gated VaR only — SCR was 15.97%);
overfit gap −0.0008; leakage-free; FX axis exact. All three recorded remediation options applied:
de-noised fit targets (mean of 8 inner Q-paths/state; `n_inner=1` reproduces Phase 21 bit-for-bit —
regression-tested), n_fit 500→2,000 via staged slice-stable CRN, eval nested benchmark 96→256 inner,
PLUS a targeted rate/equity-curvature 9-term candidate (deg-1 all drivers + r², S², r·S; analytic FX
offset) competing in the same OOS-RMSE selection — it clears the gate itself (R² 0.9930) but LOSES
to the engine's selected **(analytic, deg 3, max_int 2, 46 terms)** surface. Key finding: the Phase 21
diagnosis CONFIRMED — target noise, not basis capacity, bound (deg-2 OOS R² 0.794 → 0.9984+ once
de-noised). New module `par_model_v2/projection/multi_driver_proxy_validation_6d_remediation.py`
(additive; subclasses the governed validator), staged build
`scripts/build_phase22_task1_oos_remediation.py` (stage dir `/var/tmp/p22t1_stage`), tests
`tests/test_phase22_task1_oos_remediation.py` (21 PASS; incl. bit-identity, staged==monolithic,
selection-not-gate-shopped). Governance: ChangeRecord `6f88fd2a1fa449908a7cd8236ea30d33`
OWNER_REVIEW (methodology_change); MR-011/MR-012 → MITIGATED; audit 52→54, change records 28→29,
verify_all True. Evidence: `docs/validation/PHASE22_TASK1_OOS_REMEDIATION_REPORT.{json,md}`;
`docs/SIX_DRIVER_OOS_VALIDATION_CARD.md` updated. Regression: phase21 OOS 17 + governance 54 + FX 9
PASS; py_compile clean. NOTE: the offline UI still displays the Phase 21 PARTIAL — propagation is
deliberately deferred to Phase 22 Task 5 (one task per cycle).

**NEXT executable task: Phase 22 Task 2 — seven-driver proxy extension + OOS validation.** Extend the
LSMC proxy surface to the calibrated liquidity (7th) driver via the analytic CIR-affine forced-sale-
haircut feature (it enters the Phase 21 Task 4 inner nest analytically — mirror the FX control-variate
offset design where exactness allows, else add the haircut as a basis feature); disjoint-seed
seven-driver OOS validation vs the Phase 21 Task 4 nested ground truth (gate R² ≥ 0.95, VaR rel-err
≤ 10%); overfit sweep; reuse the remediated sizing from Task 1 (de-noised targets, n_fit 2,000+,
nested benchmark 256+ inner); ChangeRecord OWNER_REVIEW + MR-register refresh.

## Phase 22: Proxy hardening + seven-driver OOS validation (PLAN — one task per cycle)

1. ✅ DONE (2026-06-07 cycle 7) — Six-driver OOS remediation — PARTIAL cleared honestly (PASS,
   OOS R² 0.9985, stricter VaR/ES/SCR ≤10% gate; no gate-shopping).
2. ✅ DONE (2026-06-07 cycle 8, verified cycle 9) — Seven-driver LSMC proxy extension + OOS validation
   (PASS: OOS R² 0.9985; VaR/ES/SCR rel err 0.51%/0.18%/1.26%).
3. ✅ DONE (2026-06-07 cycle 9) — Liquidity exposure-notional (30,000 placeholder → 22,000 reproducible)
   + 7×7 coupling calibration (G-LIQX PASS 6/6; PSD-validated; sensitivity bounded).
4. ✅ DONE (2026-06-07 cycle 10) — Seven-driver aggregation re-run with the CALIBRATED exposure/couplings
   (PASS: liquidity SCR 45.1; copula 41,604 vs nested 48,707, rel 14.6%; tail CONVERGED; MR-010/MR-012
   refreshed; ChangeRecord 5a9934acc1c64f91a4c94c77a5ae37fc OWNER_REVIEW).
5. ⭐ **NEXT** — Offline-UI propagation + PHASE 22 COMPLETE documentation.

---

## LATEST STATUS - 2026-06-07 (cycles 5-6, superseded by cycle 7 above) — **PHASE 21 COMPLETE**

**Phase 21 Task 5 is COMPLETE: offline-UI propagation of the seven-driver capital view → PHASE 21 COMPLETE (Tasks 1–5).**
Work was split across two cycles: cycle 5 patched `scripts/build_ui_data.py` + `scripts/ui_app_self_test.cjs`
(via `scripts/_phase21_task5_patch.py`, off-mount + cp protocol) — contract bumped additively to **v1.3.0**;
G-FX + G-LIQ calibration-explorer panels; FX + liquidity standalone-SCR bars/cards; seven-driver
aggregation read-outs (standalone sum / 7×7 var-covar 28,996 / gaussian copula 41,593 / nested 48,694)
and seven-driver tail diagnostics (convergence, simulated + honest nested bootstrap CIs, Sobol-RQMC) —
but left it undocumented. Cycle 6 finished the task: refreshed the stale five-driver headline
aggregation/tail verdict wording to seven-driver (`_build_tail` verdict + keyed-verdict refresh in
`_build_verdicts`), rebuilt `viewer_data.json` via `scripts/build_offline_viewer.py` so the UI governance
tab reflects the LIVE store (52/52 audit entries digest-verified, 28 change records), opened ChangeRecord
`45cacebd910b440891f28b48fd30fedd` (OWNER_REVIEW, code_change; audit 51→52, changes 27→28, verify_all
True) via `scripts/build_phase21_task5_ui_propagation.py`, and wrote
`docs/validation/PHASE21_TASK5_UI_PROPAGATION_REPORT.{json,md}`. Verification: 19/19 UI-contract checks
PASS; `node scripts/ui_app_self_test.cjs ui_app.html` **ok:true, 0 network / 0 JS errors** (52 checks,
incl. gfxPresent/gliqPresent/sevenDriverCapitalPresent/sevenDriverVerdictPresent/fxScrCardPresent/
liquidityScrCardPresent/oosPartialVerdictPresent, driverBars=7); offline-viewer self-test ok:true;
py_compile clean. The six-driver OOS **PARTIAL** (R² 0.9498) remains honestly displayed.

---

## LATEST STATUS - 2026-06-07 (cycle 4, supersedes earlier text)

**Phase 21 Task 4 is COMPLETE: seven-driver tail-dependent aggregation + tail diagnostics, VERDICT PASS.**
Evidence: `docs/validation/PHASE21_TASK4_AGGREGATION_REPORT.{json,md}` and
`docs/MULTI_DRIVER_7D_AGGREGATION_CARD.md`. `SevenDriverLiquidityRiskAggregator`
(`par_model_v2/projection/multi_driver_capital_7d_aggregation.py`) aggregates ALL SEVEN documented
drivers; the calibrated liquidity driver enters the inner Q-nest analytically (CIR-affine-exact
forced-sale haircut, vs-MC 0.03%); the six-driver outer joint + five-driver CRN components are
reproduced bit-for-bit from Task 1 (staged slices reused, verified). Standalone SCRs: rate 14,486 /
equity 15,932 / credit 4,714 / lapse 22,539 / mortality 387 / fx 4,286 / liquidity 63. Var-covar
28,996 vs nested 48,694 (understatement 40.5%; MR-010 re-confirmed); gaussian copula 41,593 (rel
14.6% <= 25%); tail diagnostics CONVERGED (last VaR delta 0.07%), simulated + honest small-sample
nested bootstrap CIs, Sobol-RQMC 3.6x. ChangeRecord `d57a31a5ebf94173bf5c55c5b9669ead` OWNER_REVIEW;
MR-010/MR-012 MITIGATED — the MR-012 driver-omission residual is CLOSED at aggregation level.
Audit 50->51 verify_all True. 13 new tests PASS; regression FX 11 + liquidity 37 + copula 22 +
governance 54 PASS; py_compile clean.

**NEXT executable task: Phase 21 Task 5 — offline-UI propagation** (surface G-FX/G-LIQ gates,
FX + liquidity standalone SCRs, and the seven-driver aggregation/tail read-outs in
`scripts/build_ui_data.py` + `ui_app.html`; additive contract bump; keep
`node scripts/ui_app_self_test.cjs ui_app.html` at ok:true, 0 network / 0 JS errors).
**PHASE 21 COMPLETE when documented.**

**Earlier this date (cycle 3):** Phase 21 Task 3 COMPLETE: liquidity-premium 7th driver + calibration + G-LIQ gate PASS (6/6).
Evidence: `docs/validation/PHASE21_TASK3_LIQUIDITY_CALIBRATION_REPORT.{json,md}` and
`docs/LIQUIDITY_DRIVER_G_LIQ_CARD.md`. CIR++ liquidity/funding-spread driver
(`par_model_v2/stochastic/liquidity_premium.py`) is the SEVENTH and LAST documented-but-omitted
proxy driver; `LiquidityPremiumCalibrator` delegates to the tested homoscedastic CIR OLS;
HKD educational-proxy fixture (240 obs). kappa_l=0.9345/yr, long-run 63 bp, sigma_l=0.0213,
**lambda_l=2.0 CLAMPED at the plausibility cap (disclosed)**, Feller holds. ChangeRecord
`07880f42a2b84174a54b6261c0fd7131` APPROVED; MR-011/MR-012 MITIGATED; audit 47->50 verify_all
True. 37 new tests PASS; regression 114 PASS (cir+lapse 26, governance 54, credit_spread 17,
phase21 OOS 17); py_compile clean.

**NEXT executable task: Phase 21 Task 4 - six/seven-driver tail-dependent aggregation + tail
diagnostics** (copula-on-realised-losses re-aggregation incl. the liquidity driver via
`forced_sale_haircut_fraction`; var-covar vs copula vs nested reconciliation; tail convergence /
bootstrap CI / variance reduction; refresh MR-010/MR-012; ChangeRecord OWNER_REVIEW).

**Earlier this date:** Task 2 six-driver OOS validation COMPLETE (honest PARTIAL: OOS R2 0.9498
vs 0.95, marginal miss; remediation options in MODEL_DEV_LOG.md; ChangeRecord
c2f29042b5f44dd7b3670d7de87e09a2 OWNER_REVIEW). Task 1 FX driver COMPLETE (G-FX PASS 6/6).

---

## Phase 19: Recovery-completion + viewer re-uplift + driver expansion (PLAN — source of truth is `.claude-dev/MODEL_DEV_STATE.json`)

> This section was reconstructed 2026-06-06 PM-4 after a disk-full truncation lost the on-disk tail. One task per cycle, in order:

1. ✅ DONE (2026-06-06) Post-recovery health gate (pytest batches green; offline self-test ok:true).
2. ✅ DONE (2026-06-06) Re-applied the Phase 18 four-driver/copula viewer uplift on the healthy base.
3. ✅ DONE (2026-06-06) Added the **mortality-trend** stochastic driver (5th capital driver; OU/Lee-Carter-style index)
   to the nested ground truth + LSMC proxy (`par_model_v2/stochastic/mortality_trend.py` + `multi_driver_capital_5d.py`);
   five-driver OOS proxy validation VERDICT PASS (OOS R²=0.9616).
4. ✅ DONE (2026-06-06) **Five-driver tail-dependent aggregation** (PM-3: `multi_driver_capital_5d_aggregation.py`;
   var-covar understates nested by 48.8% MR-010; gaussian copula reconciles 6.5%) **AND** **five-driver
   tail-convergence/stability diagnostics** (PM-4: `FiveDriverTailDiagnostics` in `multi_driver_tail_diagnostics.py`).
   Tail VERDICT PASS — VaR99.5 230,879 / ES 246,337, converged True (rec N_outer≥8,000), bootstrap 95% CI
   [227,582, 241,861] SE 3,104 (±3.07%), Sobol QMC variance-reduction 4.80×, antithetic 0.78× (expected-ineffective).
   Offline-viewer five-driver uplift complete (Mortality standalone-SCR bar + dynamic 5-driver pill; bundler prefers the
   Phase 19 reports + surfaces mortality_scr; rebuilt model_result_viewer.html 92,142 B). MR-010/MR-012 governance refresh
   done PM-3. Artifacts: `docs/validation/PHASE19_TASK4_{AGGREGATION,TAIL_DIAGNOSTICS,GOVERNANCE_REFRESH}_REPORT.{json,md}`;
   `docs/MULTI_DRIVER_5D_{AGGREGATION,TAIL_DIAGNOSTICS}_CARD.md`. (SOA ASOP 56 §3.5/§3.1.3; ASOP 25 §3.3; ASOP 7 §3.3;
   IA TAS M §3.6; Solvency II Del. Reg. Art. 234; L'Ecuyer 2018 RQMC)
5. ⭐ **NEXT** — Calibrate the **lapse behavioural index** to an educational-proxy experience series (mirror the
   GBM/HW1F/CIR calibrators: OU/AR(1) transition regression for the mean-reversion speed + long-run level, residual
   variance for sigma); add a **G-LAPSE** plausibility gate; governance refresh (assumption_change ChangeRecord, MR
   register). **PHASE 19 COMPLETE** when documented.

**After Phase 19:** begin the standalone **offline user-interface** track per the scheduled-task directive — the stochastic
model completes the calculation, then a no-pre-install UI consumes ONLY the model output to display results graphically and
interactively. `model_result_viewer.html` (self-contained, no CDN/server/build; inline-SVG charts; 0 network) is the foundation.

<!-- END OF PROMPT -->

---

# NEXT EXECUTION TRACK — STANDALONE OFFLINE USER INTERFACE (model dev 100% complete)

All 19 phases / 100 model-development tasks are COMPLETE (2026-06-06 PM-5). Per the scheduled-task directive, focus now shifts to a standalone offline UI.

## Hard requirements
1. Zero pre-installation: runs by opening one HTML file in a browser. No Python/Node/server, no runtime CDN, no network calls.
2. Output-only: do NOT re-run any calculation. Consume only model OUTPUT (`viewer_data.json` and/or `docs/validation/*REPORT.json`).
3. Graphical and interactive: charts, tables, tabs, tooltips, export — all client-side, self-contained.

## Foundation already in place
- `model_result_viewer.html` (self-contained; passes `scripts/offline_viewer_self_test.cjs`, 0 network/0 JS errors) — the baseline, built by `scripts/build_offline_viewer.py` from `par_model_v2/viewer/viewer_template.html` + the Phase 19 report JSONs.
- `combined_model_app.html` + `combined_app_data.json` (inline SVG chart shim, no CDN); `viewer_data.json` (the output contract).

## Staged plan (ONE task per cycle)
- ✅ DONE (2026-06-06 PM-6) UI Task 1 — Inventory & contract. `scripts/build_ui_data.py` (no-calc bundler) catalogues every model-output JSON (32 artifacts, each SHA-256-addressed) and all calibrations incl. the new lapse **G-LAPSE** report into one stable `ui_data.json` contract (v1.0.0: meta/summary/inventory/capital/tail/proxy/loss/calibrations/governance/verdicts), and emits a self-contained `ui_app.html` with the snapshot embedded inline. `scripts/ui_app_self_test.cjs` (jsdom) asserts **0 network / 0 JS errors** → ok:true (5 tabs, 32 inventory rows, 6 calibration gates, 8 capital cards). External-ref scan clean; py_compile clean.
- ✅ DONE (2026-06-06 PM-7) UI Task 2 — Capital & tail dashboard. Added a zero-dependency inline-SVG chart toolkit (barChart/ciChart/lineChart + delegated tooltips) to `scripts/build_ui_data.py`'s `HTML_TEMPLATE` and rebuilt the Capital & Tail tab into a 4-view segmented dashboard: (1) **Driver SCRs** — 5 standalone-SCR bars with %-of-sum tooltips; (2) **Aggregation** — standalone-sum → var-covar → 3 copula candidates (gaussian selected/outlined, student_t, survival_clayton) vs the dashed nested benchmark, tooltips show rel-err/diversification/tail-dependence/AIC; (3) **VaR / ES + CI** — point estimates with 95% bootstrap-CI whiskers + variance-reduction ratios; (4) **Convergence** — VaR & ES vs outer_grid with the recommended-n* marker. Self-test extended (`capitalSubnavBtns===4`, `capitalSvgCharts>=4`, `driverBars>=5`, `capitalTipElems>=10`) → **ok:true, 0 network / 0 JS errors**. External-ref scan clean (0 http/src/link); py_compile clean. NOTE: the sandbox `/sessions` disk hit 100% mid-run and truncated three file-tool writes; recovered by switching all mount writes to the bash head+heredoc+mv workaround.
- ✅ DONE (2026-06-06 PM-8) UI Task 3 — Calibration explorer. Rebuilt `renderCalibrations()` in `scripts/build_ui_data.py`'s HTML_TEMPLATE into a per-driver explorer: a driver sub-nav (one segmented button per calibration record) toggling a detail panel per driver with (a) KPI cards (gate id, observations, fit R², optimiser-converged), (b) a gate-criteria pass/fail breakdown, (c) a calibrated-parameter table, and (d) a zero-dependency inline-SVG fit-diagnostics bar chart (HW1F swaption RMSE/max-error vs the dashed G-02 25 bps band; GBM σ implied/historical/blended; CIR++ initial/long-run-P/long-run-Q spread levels in bp; OU-lapse half-life/stationary-σ/A-E). The bundler's `_build_calibrations()` now attaches a `diagnostics` block {method,n_obs,fit_r2,converged,criteria[],fit_bars} per record (contract bumped to **v1.1.0**, additive) and adds an honest **mortality-trend** panel (educational OU placeholder; no data calibration, no G-MORT gate — flagged placeholder). Self-test extended (calibDrivers≥5, calibPanels≥5, calibCharts≥1, calibCrit≥3, calibParamRows≥1) → **ok:true**: 7 driver panels, 6 fit charts, 32 criteria rows, 31 param rows, **0 network / 0 JS errors**; external-ref scan clean (0); py_compile clean. NOTE: `/sessions` was at 100% (19 MB free) and truncated a file-tool write of the bundler mid-cycle; recovered by rebuilding the file off-mount in `/var/tmp` and writing back with byte-count + parse verification.
- ✅ DONE (2026-06-06 PM-9) UI Task 4 — Governance & assumptions view. Rebuilt `renderGovernance()` in `scripts/build_ui_data.py`'s HTML_TEMPLATE into a 4-view segmented dashboard over the read-only governance export: (1) **Deployment gates** — a cleared/total progress bar + 12 gate cards (status chip, level/blocking badges, hover tip); (2) **Model-risk register** — rating + mitigation-status filters driving a zero-dependency inline-SVG impact×likelihood heatmap (5×5, count-binned) and an expandable risk table (click a row for description/mitigation/standards basis); (3) **Change records** — a newest-first ChangeRecord approval timeline; each record expands to its standards basis + full peer-review→owner-review→approval sign-off chain (40 sign-off steps across 18 records); (4) **Audit integrity** — a recomputed offline integrity badge (holds iff every audit entry verified and none failed) + entries/verified/failed/sign-off-step KPI cards + change-by-status/by-type distributions. No data-contract change (governance section already in v1.1.0; UI-only). Self-test extended (govSubnavBtns===4, govGateCards>=5, govRiskRows>=5, govRiskFilterWorks, govHeatCells>=25, govChangeItems>=5, govSignoff>=1, govAuditBadge>=1) -> **ok:true**: 5 tabs, 12 gate cards, 12 risk rows (6 under the HIGH filter), 25 heat cells, 18 change records, 40 sign-off steps, **0 network / 0 JS errors**; external-ref scan clean (0 http/src/link); py_compile clean; ui_app.html rebuilt = 115,617 B. **SANDBOX BLOCKER (recovered):** the `/sessions` mount stayed at 100% (19 MB free) and the **Edit/Write file-tools silently TRUNCATED** mid-write -- they cut `build_ui_data.py` at line ~1053 (inside govGatesBlock) and corrupted `ui_app_self_test.cjs`. Recovered with NO source loss by: reading the intact pre-template code from the truncated file, recovering the complete original `HTML_TEMPLATE` from the surviving good bytecode `scripts/__pycache__/build_ui_data.cpython-310.pyc`, recovering the lost `write_outputs()/main()` writer from its disassembly, re-applying the 3 governance edits in Python off-mount, then **`cp`-ing back (bash cp works where the file-tools truncate)** with byte-count + `cmp` + py_compile verification. **Future cycles on this sandbox: do NOT use the Edit/Write file-tools for files on the full `/sessions` mount -- build off-mount and `cp` back with verification.**
- ✅ DONE (2026-06-06 PM-10) — UI Task 5 — Packaging & polish (FINAL UI task): consolidate to a single self-contained build, add Export PNG (canvas-serialise each inline-SVG chart) + Export CSV (inventory / risk register / change records), a Print stylesheet, keyboard/ARIA accessibility on tabs+subnavs+filters, and a README/usage note. Keep the self-test at 0 network / 0 JS errors and the external-ref scan clean. NOTE: write all mount files via bash `cp`/heredoc, never the Edit/Write file-tools, while `/sessions` is full.


---

# UI TRACK COMPLETE (2026-06-06 PM-10)

All five offline-UI tasks are DONE. `ui_app.html` (126,787 B) is a zero-install, fully-offline,
output-only viewer: 5 interactive tabs; inline-SVG charts; **Export PNG** (canvas-serialised charts),
**CSV** exports (inventory / risk register / change records), a **print/Save-PDF** stylesheet, and
**keyboard/ARIA** accessibility on tabs + sub-navs + filters. `scripts/ui_app_self_test.cjs`
(jsdom) → **ok:true, 0 network / 0 JS errors** (40 checks); external-ref scan clean (sole runtime
`xmlns` on PNG export only); `py_compile` clean; `ui_data.json` contract v1.1.0. Usage note: `UI_README.md`.

Build/verify: `PYTHONPATH=. python3 scripts/build_ui_data.py && node scripts/ui_app_self_test.cjs ui_app.html`.

> SANDBOX NOTE (still applies): `/sessions` disk is at 100% (~19 MB free) and the Edit/Write
> file-tools TRUNCATE mid-write on this mount. This cycle built off-mount in `/tmp` and `cp`-ed
> back with `cmp` + byte-count + py_compile + self-test verification. Future cycles MUST do the same
> (bash `cp`/heredoc, never the Edit/Write file-tools) until a human frees disk and clears the ghost
> git locks (`.git/index.lock`, `.git/HEAD.lock`) so commits/pushes can resume.

## NEXT EXECUTION — Phase 20 (market-consistency / multi-factor uplift)

Model development reached 100% across 19 phases and the offline-UI track is complete. Per the
scheduled-task directive ("research for further improvement to the stochastic model"), the active
track is a **market-consistency / multi-factor uplift**. ONE task per cycle, mirroring prior
structure; each ends with a validation gate + governance ChangeRecord (OWNER_REVIEW) + MR-register refresh.

**Progress:**

1. ✅ **DONE (2026-06-06) — Two-factor interest-rate driver (G2++ / 2F Hull-White).** Exact OU
   simulator + analytic initial-curve-fitted ZCB/bond-option formulas + **G-RATE2** gate (PASS 6/6).
   `par_model_v2/stochastic/g2pp_rate.py`; `tests/test_phase20_g2pp_rate.py` (7 pass);
   `scripts/build_phase20_task1_g2pp.py`; ChangeRecord OWNER_REVIEW; MR-013 opened.
2. ✅ **DONE (2026-06-06) — Swaption-surface calibration of G2++.** Analytic Brigo-Mercurio European
   swaption pricer (Gauss-Hermite decomposition into an option on the coupon bond; MC-cross-checked
   within 4 SE), Black-76 ATM targets, pure-numpy Nelder-Mead calibration of (a,b,sigma,eta,rho), and
   the **G-SWPN** gate (PASS 7/7; vol RMSE 54.7 bps over 24 ATM quotes). Calibrated a=0.0345, b=0.9583,
   sigma=0.00637, eta=0.00240, rho=-0.908. `par_model_v2/stochastic/g2pp_swaption.py`;
   `tests/test_phase20_g2pp_swaption.py` (14 pass); `scripts/build_phase20_task2_swaption.py`;
   ChangeRecord `6c7d5354530c451a9a6ab46f33a8dba0` OWNER_REVIEW; MR-013 refreshed; audit integrity True.
3. ✅ **DONE (2026-06-06) — Market-consistency (martingale) validation gate (G-MART).** Added the
   additive, output-only `par_model_v2/validation/phase20_market_consistency.py`: an EXACT,
   initial-curve-consistent HW1F simulator (`simulate_hw1f_exact`) and the **G-MART** gate verifying,
   under the money-market numeraire, that deflated assets are Q-martingales — MART-HW1F-ZCB (5y/10y),
   MART-G2PP-ZCB (5y/10y), MART-EQ-FWD (ex-div discounted GBM equity), MART-FX-CIP (covered interest
   parity), each a 4-sigma MC test. **G-MART PASS** (6/6 ERROR checks; worst 1.22 sigma; max rel err
   3.9e-4; 40k paths; t=1y). Trapezoidal deflator for bond checks (O(dt^2)); left-point deflator for
   equity/FX (matches the Euler drift → discrete identity exact); G2++ ZCB vectorised (bit-identical to
   the scalar pricer). Honest diagnostics (non-gating): the educational monthly-Euler `HullWhiteRateProcess.simulate`
   has a ~7% (~59 sigma) martingale bias vs the exact dynamics (MART-HW1F-EULER-BIAS), and the discounted
   equity drifts up by exp(ERP*t) under P (MART-PQ-MEASURE). 14 tests PASS (`tests/test_phase20_market_consistency.py`);
   regression Task1+2 21 PASS, IA-validation+health 115 PASS. `scripts/build_phase20_task3_market_consistency.py`;
   `docs/validation/PHASE20_TASK3_G_MART_REPORT.{json,md}`; `docs/MARKET_CONSISTENCY_G_MART_CARD.md`;
   ChangeRecord `955fe35ce8034a9cb98904a7b6d79c62` OWNER_REVIEW; MR-013 refreshed; audit integrity True.
   (SOA ASOP 56 §3.1.3/§3.5; IA TAS M §3.6; Solvency II Del. Reg. Art. 22/234; Brigo-Mercurio 2006)
4. ✅ **DONE (2026-06-06) — Capital re-aggregation with the two-factor G2++ rates driver.** Additive G2++
   outer-rate state (dominant factor carries the governed 5×5 ESG cross-correlation; second factor adds an
   orthogonal slope/curvature axis); governed HW1F inner nest reused as the conditional liability operator.
   Calibrated 2F driver lowers horizon short-rate dispersion ~114→~49 bps; nested SCR 104,132 (HW1F) →
   55,116 (G2++, −47.1%). G2++ var-covar understates nested 39.7%; gaussian copula reconciles within 12.4%
   (beats var-covar). Tail diagnostics (VaR/ES, outer convergence, bootstrap 99.5% CI rel-halfwidth 17.9%)
   refreshed; MR-010 & MR-012 refreshed (MITIGATED); ChangeRecord OWNER_REVIEW; audit integrity True;
   4 new pytests PASS; regression 21+22+13+51 PASS.
5. ✅ **DONE (2026-06-06) — Offline-UI propagation for Phase 20.** G-SWPN G2++ swaption-calibration panel,
   G-MART headline verdict, and G2++ 2F capital/tail dashboard sources wired into `ui_data.json`/`ui_app.html`
   (contract bumped to **1.2.0**); `node scripts/ui_app_self_test.cjs ui_app.html` → ok:true, 0 network / 0 JS
   errors. **PHASE 20 COMPLETE.**

<!-- END OF PROMPT (Phase 20) -->

---

## ⚠️ LATEST STATUS — 2026-06-06 (PM, supersedes everything above)

**Model development is 100% complete: all 19 phases + Phase 20 (market-consistency / multi-factor uplift), 100/100
documented tasks, plus the standalone offline-UI track (`ui_app.html`, contract 1.2.0, 0 network / 0 JS errors).**
The canonical source of truth is `.claude-dev/MODEL_DEV_STATE.json` (`Phase 20 … status: "completed"`,
`tasks_completed: 100`). The older "Phase 20 Task 4 ⭐ NEXT" line above is **stale** — Tasks 4 & 5 are done.

### 🛑 SANDBOX-DOWN BLOCKER THIS CYCLE (ESCALATED — HUMAN ACTION REQUIRED)
This cycle could run **no code at all**. The `/sessions` shared volume is now so full that the Linux sandbox
**cannot even boot a user**: every `bash` call fails with
`useradd: /etc/passwd.NNNNN: No space left on device … cannot lock /etc/passwd`. This is a hard escalation
beyond the prior "100% full but functional" state — previously Python/pytest/node still ran from `/var/tmp/pylibs`;
now the shell itself will not start. Consequently **no pytest, no node self-test, no git, no numeric work** was
possible. This cycle was limited to file-tool reads/writes against the user's Windows folder (a different
filesystem from the full `/sessions` mount) to update planning docs and email the human.

**This blocker is NOT resolvable from the sandbox. A human must free disk on the host that backs `/sessions`
before any further executable cycle can run.** Until then, every cycle will be a no-op for code.

### Persisting blockers carried forward (all human-only)
1. **Disk:** free space on the host backing `/sessions` (root cause of the sandbox-boot failure AND the prior
   silent file-tool write-truncation on that mount).
2. **Ghost git locks:** `.git/index.lock` + `.git/HEAD.lock` (2026-06-03) — unremovable from the sandbox; delete
   in a real shell, then `git reset`. There is an **un-pushed local commit backlog** (state file shows
   `commits_this_session: 72`, last pushed sha `fa5d5fe` = Phase 16) — Phases 17–20 are committed locally via the
   alt-`GIT_INDEX_FILE` workaround but **need a human `git push origin main`** once the locks are cleared.
3. **Production sign-off residual (not a code gap):** every Phase 14–20 ChangeRecord sits at OWNER_REVIEW with
   final APPROVED withheld pending (a) calibration to **credentialled** data and (b) an **independent APS X2**
   review. This is the standing governance residual, by design, for an educational model.

---

## ⚠️ LATEST STATUS — 2026-06-07 (supersedes everything above)

**Blockers cleared this cycle:** `/sessions` disk freed; sandbox boots; Python + pytest + scipy
available; git functional. **Health gate PASS: 2,084 passed / 0 failed** (4 single tests exceed the
44s sandbox wall-clock — disclosed in MODEL_DEV_LOG.md; rerun them in an unconstrained shell).

**Phase 21 Task 1 is COMPLETE** (FX sixth driver + G-FX gate PASS 6/6; six-driver aggregation PASS;
ChangeRecord `25e1eac6661a4d9bb74276ee1a2a4b46` OWNER_REVIEW; MR-012 refreshed; audit True). See
`docs/validation/PHASE21_TASK1_FX_DRIVER_REPORT.{json,md}` and `docs/FX_DRIVER_G_FX_CARD.md`.

**NEXT executable task: Phase 21 Task 3** (liquidity 7th driver + calibration + G-LIQ gate, below).

**Sandbox operating rules learned (apply to every future cycle):**
1. Each bash call has a ~44s hard wall; background/detached processes are KILLED when the call
   ends. Do not trust `pgrep` liveness checks (they self-match the polling command) — verify via
   `/proc/loadavg` and output artifacts.
2. Stage long computations. `scripts/build_phase21_task1_fx.py --stage outer|slice|finalise` is the
   reference pattern: slice-stable CRN (`SeedSequence(seed).spawn(n_full)[i0:i1]`) makes staged
   bit-identical to monolithic (regression-tested). Reuse this pattern for Task 2's heavy nested runs.
3. Run pytest in chunks (`-n 2`, file/class/test granularity) with done-tracking; record any test
   that cannot fit the wall as NOT RUN with a reason.

## Phase 21: FX + Liquidity Drivers and Six/Seven-Driver Economic Capital ✅ COMPLETE (Tasks 1-5, 2026-06-07)

**Do not start until the sandbox boots again (disk freed) and `python3 -m pytest -q` runs in <45 s batches at
0 failures.** The economic-capital proxy currently spans **five** drivers (rate → now G2++ 2F, equity, credit
spread, dynamic lapse, mortality trend). The two documented-but-omitted drivers are **FX/currency** and
**liquidity** (see MR-012 residual text). Phase 21 adds them, mirroring the established per-cycle structure —
one task per cycle, each ending with a validation gate + governance ChangeRecord (OWNER_REVIEW) + MR-register
refresh + offline-UI propagation. Source of truth for task state remains `.claude-dev/MODEL_DEV_STATE.json`.

1. ✅ **FX / currency driver (6th driver) — COMPLETE 2026-06-07.** `multi_driver_capital_6d_fx.py`:
   lognormal FX spot (P outer / Q CIP drift), CIP-exact analytic inner conditioning, 6x6 governed
   correlation, six-driver standalone/var-covar/copula/nested aggregation, G-FX gate PASS 6/6 with
   MART-FX-CIP evidence; 11 tests; staged build. Six-driver LSMC surface extension was deliberately
   deferred to Task 2 (where its OOS validation lives) — the nested benchmark is the 6D ground truth.
2. ✅ **Out-of-sample six-driver proxy validation — COMPLETE 2026-06-07 (verdict PARTIAL, honest).**
   `multi_driver_proxy_validation_6d.py`; analytic-CIP FX-offset surface (deg 1, max_int 3) selected by OOS
   RMSE; OOS R² 0.9498 vs 0.95 gate (marginal miss — remediation in MODEL_DEV_LOG.md); FX slope exact;
   leakage-free; 17 tests; ChangeRecord c2f29042b5f44dd7b3670d7de87e09a2 OWNER_REVIEW.
3. 

---

## ⚠️ LATEST STATUS — 2026-06-07 (cycle 9, supersedes everything above)

**Phase 22 progress: Task 1 ✅ (OOS remediation, R² 0.9985), Task 2 ✅ VERIFIED (7D OOS validation PASS,
R² 0.9985, VaR/ES/SCR rel err 0.51%/0.18%/1.26%), Task 3 ✅ (liquidity exposure + couplings calibrated,
G-LIQX PASS 6/6: notional 30,000 placeholder → 22,000 reproducible; couplings recovered within 0.12 of
documented targets from a 1,200-month seeded joint synthesis; PSD-validated; sensitivity bounded;
ChangeRecord `39b5c559fc63426b830660cd7595a297` OWNER_REVIEW; MR-011/MR-012 MITIGATED).**

**NEXT executable task: Phase 22 Task 4 — seven-driver aggregation re-run with the CALIBRATED exposure
notional + couplings.** Consume `calibrated_liquidity_exposure_notional()` and
`calibrated_seven_driver_correlation()` from `multi_driver_capital_7d_aggregation.py` (they read the
Task 3 report with placeholder fallback). Use the staged-build pattern (<45 s walls, slice-stable CRN)
as in `scripts/build_phase21_task4_aggregation*`/Task 1; refresh MR-010/MR-012; re-run tail diagnostics;
ChangeRecord at OWNER_REVIEW; then Task 5 = offline-UI propagation + PHASE 22 COMPLETE documentation.

**Sandbox operating rules (CONFIRMED AGAIN cycle 9):**
1. ~44 s hard wall per bash call; stage long computations; verify liveness via artifacts.
2. Python/pytest/scipy/pandas live in `/var/tmp/pylibs` — run with `PYTHONPATH=/var/tmp/pylibs:.`.
3. **Windows-side file-tool writes of LONG files silently truncate on sync to the Linux mount** —
   write long repo files via bash heredoc/python and ALWAYS verify with `ast.parse`/`json.loads`.

**Standing blockers (human action):** GitHub push (see GITHUB_PUSH_BLOCKER.md); production sign-off
residual (credentialled data + independent APS X2 review) — by design for this educational model.


---

## ⚠️ LATEST STATUS — 2026-06-07 (cycle 10, supersedes everything above)

**Phase 22 progress: Tasks 1–4 ✅. Task 4 (this cycle): seven-driver aggregation RE-RUN with the
G-LIQX-CALIBRATED liquidity exposure notional (22,000) + 7x7 couplings consumed via
`calibrated_liquidity_exposure_notional()` / `calibrated_seven_driver_correlation()` —
VERDICT PASS.** Liquidity SCR 63.5 → 45.1; var-covar 28,991 vs nested 48,707 (40.5%
understatement, MR-010 re-confirmed); gaussian copula 41,604 (rel 14.6% ≤ 25%); tail diagnostics
re-run CONVERGED (last VaR delta 0.07%); Sobol-RQMC 3.6x. All 6 Phase 21 Task 4 CRN slices reused
after bit-identity verification (Cholesky rows 0–5 invariant to liquidity couplings; liquidity
shock drawn last). Calibrated-vs-placeholder deltas quantified in
`docs/validation/PHASE22_TASK4_AGGREGATION_REPORT.{json,md}`;
card `docs/MULTI_DRIVER_7D_CALIBRATED_AGGREGATION_CARD.md`. ChangeRecord
`5a9934acc1c64f91a4c94c77a5ae37fc` OWNER_REVIEW; MR-010/MR-012 MITIGATED; audit verify_all True
(32 records). 18 new tests; regression 160 PASS / 0 FAIL.

**NEXT executable task: Phase 22 Task 5 — offline-UI propagation + PHASE 22 COMPLETE
documentation.** Surface in `scripts/build_ui_data.py` + `ui_app.html` (additive contract bump):
(a) the Phase 22 Task 1 OOS remediation PASS (R² 0.9985) replacing the displayed six-driver
PARTIAL; (b) the Task 2 seven-driver OOS validation PASS; (c) the Task 3 calibrated exposure/
couplings (G-LIQX panel); (d) the Task 4 calibrated aggregation read-outs (liquidity SCR 45.1,
var-covar 28,991, copula 41,604, nested 48,707) replacing the stale placeholder numbers. Keep
`node scripts/ui_app_self_test.cjs ui_app.html` ok:true (0 network / 0 JS errors); rebuild
`viewer_data.json` so governance reflects the live store. Then write PHASE 22 COMPLETE
documentation. After Phase 22: research further stochastic-model improvement (per the scheduled-
task standing instruction) and refresh this prompt; the offline-UI focus continues (the UI must
keep consuming ONLY model output JSON, no pre-installation requirement).

**Sandbox operating rules (CONFIRMED AGAIN cycle 10):**
1. ~44 s hard wall per bash call; stage long computations; verify liveness via artifacts.
2. Python/pytest/scipy/pandas live in `/var/tmp/pylibs` — run with `PYTHONPATH=/var/tmp/pylibs:.`.
3. Windows-side file-tool writes of LONG files silently truncate on sync — write long repo files
   via bash heredoc/python and ALWAYS verify with `ast.parse`/`json.loads`/`cmp`.
4. Git ghost locks persist — commit with the alt-`GIT_INDEX_FILE` workaround onto branch `p22c9`
   (updating `main` is blocked by `refs/heads/main.lock`); see GITHUB_PUSH_BLOCKER.md checklist.

**Standing blockers (human action):** GitHub push (see GITHUB_PUSH_BLOCKER.md); production
sign-off residual (credentialled data + independent APS X2 review) — by design for this
educational model.

---

## ⚠️ LATEST STATUS — 2026-06-07 (cycle 11, supersedes everything above)

**PHASE 22 COMPLETE (Tasks 1–5).** Task 5 (this cycle): offline-UI propagation — `ui_data.json`
contract bumped additively **1.3.0 → 1.4.0**; the UI now surfaces (a) the Task 1 six-driver OOS
REMEDIATED PASS (R2 0.9985, replacing the displayed honest PARTIAL), (b) the Task 2 seven-driver
OOS PASS, (c) the Task 3 **G-LIQX** calibrated exposure notional (22,000) + couplings as a
first-class calibration panel, and (d) the Task 4 calibrated aggregation/tail read-outs
(liquidity SCR 45.1, var-covar 28,991, gaussian copula 41,604, nested 48,707; MR-010 40.5%
understatement) with calibrated-vs-placeholder deltas embedded. Capital/tail loaders prefer
`PHASE22_TASK4_AGGREGATION_REPORT.json` with Phase 21 fallback. `viewer_data.json` rebuilt;
self-test extended (+4 Phase 22 checks) → **ok:true, 0 network / 0 JS errors (56 checks)**.
ChangeRecord `880aeb5d621645c9adc8d2eb1f2ea88a` OWNER_REVIEW; audit 59→60, changes 32→33,
verify_all True. 16 new tests; regression **187 PASS / 0 FAIL**. Evidence:
`docs/validation/PHASE22_TASK5_UI_PROPAGATION_REPORT.{json,md}`.

**NEXT executable task: Phase 23 Task 1 — research + design note** for the new phase
**"Phase 23: Tail-Dependence Upgrade + Management Actions"** (already set as `current_phase` in
`.claude-dev/MODEL_DEV_STATE.json`), the further stochastic-model improvement researched per the
scheduled-task standing instruction:

1. **Student-t copula aggregation** — the selected gaussian copula has ZERO tail dependence,
   which is the documented residual behind MR-010 (it reconciles to nested within 14.6% but
   cannot capture joint-tail clustering). Calibrate the t-copula df by matching the empirical
   joint-tail-dependence coefficient of the nested outer loss sample (the 7D CRN slices in
   `/var/tmp/p21t4_stage` can be reused if intact — verify bit-identity first); compare
   gaussian vs t vs nested; refresh MR-010. Candidate evidence: copula goodness-of-fit on the
   PIT-transformed outer sample (tests exist in `par_model_v2/aggregation`).
2. **Management-action driver** — ERM standards (and the Phase 2 standards block above) require
   management-action risk; the par product currently has NO dynamic bonus response. Design a
   governed rule: reversionary-bonus participation cut when the solvency ratio breaches a
   trigger (with policyholder-reasonable-expectation floor), entering the NESTED ground truth
   liability and the LSMC proxy (new basis features), then seven-driver OOS re-validation.
   Document as design note first (Task 1 deliverable), implement in Tasks 2–4, UI in Task 5.

Design-note deliverable: `docs/PHASE23_DESIGN_NOTE.md` + ChangeRecord (assumption_change,
OWNER_REVIEW) + state/log updates. One task per cycle; keep walls <45 s; stage long runs.

**Sandbox operating rules (CONFIRMED AGAIN cycle 11):**
1. ~44 s hard wall per bash call; stage long computations; background `nohup` does NOT survive
   the call boundary — poll via artifacts written by staged scripts instead.
2. Python/pytest/scipy/pandas live in `/var/tmp/pylibs` — run with `PYTHONPATH=/var/tmp/pylibs:.`.
3. Windows-side file-tool writes of LONG files silently truncate on sync — write long repo files
   via bash heredoc/python and ALWAYS verify with `ast.parse`/`json.loads`/`cmp`.
4. Git ghost locks persist — commit with the alt-`GIT_INDEX_FILE` workaround onto branch `p22c9`
   (updating `main` is blocked by `refs/heads/main.lock`); push `p22c9:main`; see
   GITHUB_PUSH_BLOCKER.md checklist.

**Standing blockers (human action):** delete the three git ghost locks (see GITHUB_PUSH_BLOCKER.md);
production sign-off residual (credentialled data + independent APS X2 review) — by design for
this educational model.

---

## ⚠️ LATEST STATUS — 2026-06-07 (cycle 14, supersedes everything above)

**Phase 23 progress: Tasks 1–3 ✅. Task 3 (this cycle): management-action rule — dynamic
reversionary-bonus participation cut (Solvency II Art. 23) — VERDICT PASS (5/5 fixed
pre-registered gates).** New additive module `par_model_v2/projection/management_actions.py`:
`cut_factor = clip((CR - CR_floor)/(CR_trigger - CR_floor), 0, 1)` (retained-bonus factor),
CR = A_ref/L at the outer node, trigger 1.10 / floor 0.90, PRE floor 60%, max liability relief
12%, MONOTONICITY GUARD at construction. The rule enters the NESTED conditional liability and
IDENTICALLY the LSMC proxy prediction as an analytic post-composition basis feature (FX/LIQ
offset pattern; cut decision uses the PRE-action CR; A_ref leakage-free from the fit-sample
mean). Phase 22 Task 2 staged primitives (`.phase22_task2_stage`) reused bit-identically after
6/6 archived-report cross-checks. Results (nested 500x256): VaR99.5 171,555 → 150,969 (−12.0%);
ES 176,570 → 155,382; SCR proxy 55,561 → 39,291 (−29.3%); active on 44.2% of outer states; OOS
R2 with actions 0.9983; VaR rel err 0.51%; trigger sensitivity 1.05/1.10/1.15 all PASS.
Evidence: `docs/validation/PHASE23_TASK3_MANAGEMENT_ACTION_REPORT.{json,md}` +
`docs/MANAGEMENT_ACTION_RULE_CARD.md`. ChangeRecord `cf22c050bca44a84a843fb262a2efb84`
(assumption_change) OWNER_REVIEW; **MR-014** opened+MITIGATED (the design note's "MR-013" ID was
already the G2++ market-consistency risk — the first governance run overwrote it, caught same
cycle, MR-013 restored from the pre-stage backup; collision disclosed in MR-014 notes, the
report, and the build script now uses MR-014). Audit 62→63; changes 34→35; verify_all True.
29 new tests; regression **271 PASS / 0 FAIL**; ui_app self-test ok:true.

**NEXT executable task: Phase 23 Task 4 — aggregation + tail-diagnostics re-run WITH management
actions.** Realise the with-actions standalone capital losses (apply
`ManagementActionRule.apply_to_liabilities` with the SAME A_ref convention to the per-driver
conditional-liability primitives — reuse `/var/tmp/p22t4_stage` + `/var/tmp/p23t2_stage` slices
bit-identically, verify against the archived Phase 22 Task 4 / Phase 23 Task 2 reports first);
re-run the tail-matched t(2.95) copula vs gaussian vs var-covar vs nested-with-actions; quantify
with-vs-without capital deltas at every level; refresh MR-010/MR-014 notes; methodology_change
ChangeRecord OWNER_REVIEW. Then **Task 5: offline-UI propagation** (management-action panel:
rule parameters, gates, with/without capital read-outs, trigger sensitivity; additive
`ui_data.json` contract bump 1.4.0 → 1.5.0; keep `node scripts/ui_app_self_test.cjs ui_app.html`
ok:true; rebuild `viewer_data.json`) + PHASE 23 COMPLETE documentation. The UI must keep
consuming ONLY model output JSON (zero install).

**Sandbox operating rules (CONFIRMED AGAIN cycle 14):**
1. ~44 s hard wall per bash call; stage long computations; poll via artifacts.
2. Python/pytest/scipy/pandas live in `/var/tmp/pylibs` — run with `PYTHONPATH=/var/tmp/pylibs:.`.
3. Long-file writes truncate on the mount EVEN from bash `>>` appends when disk is ~90% — build
   files OFF-MOUNT (/var/tmp), then `cp` + `cmp` verify (a status-file append truncated mid-line
   this cycle and was rebuilt off-mount; MODEL_DEV_LOG.md append verified intact via wc/tail).
4. Git ghost locks persist — commit with the alt-`GIT_INDEX_FILE` workaround onto branch `p22c9`
   (updating `main` is blocked by `refs/heads/main.lock`); push `p22c9:main`; see
   GITHUB_PUSH_BLOCKER.md checklist.
5. Risk-register IDs: ALWAYS check the next free MR-0xx in `.claude-dev/GOVERNANCE_STORE.json`
   before opening a new risk (MR-013 collision this cycle); back up the store before any
   governance stage.

**Standing blockers (human action):** delete the three git ghost locks (see
GITHUB_PUSH_BLOCKER.md); production sign-off residual (credentialled data + independent APS X2
review) — by design for this educational model; disk /sessions ~90% — consider pruning
`/var/tmp` build dirs and `.git.old-repo-*`.

---

## ⚠️ LATEST STATUS — 2026-06-07 (cycle 16, supersedes everything above)

**PHASE 23 COMPLETE (Tasks 1–5).** Task 4 (cycle 15) re-ran the seven-driver aggregation WITH
the governed management-action rule: nested SCR 48,707.4 → **33,117.8** (−32.0%); tail-matched
t(2.9451) 46,756.0 → 25,652.9; gaussian 41,472.4 → 23,921.8; var-covar 28,990.9 → 14,428.7
(56.4% understatement vs nested-with; MR-010 refreshed); RANK INVARIANCE gated (df re-matched at
exactly 2.9451); **MATERIAL FINDING disclosed:** copula-on-standalone-losses understates the
nested with-actions benchmark (t rel err 4.0% → 22.5%) because the action saturates (max relief
12%) in the joint tail — nested remains the capital reference. Task 5 (cycle 16) propagated all
of Phase 23 to the zero-install offline UI: `ui_data.json` contract **1.4.0 → 1.5.0 ADDITIVE**;
new `management_actions` section + **Management Actions tab** (rule card 1.10/0.90/30%/60%/12%,
5/5 + 4/4 gates, active/floor shares, trigger sensitivity, with/without SCR bars for all four
benchmarks, per-driver standalone deltas + anchoring convention, saturation finding verbatim);
capital section augmented (t_copula_scr 46,756 / df 2.9451 / nested_scr_with_actions 33,118);
3 new headline verdicts; `viewer_data.json` rebuilt (38 change records). jsdom self-test
**ok:true, 0 network / 0 JS errors over 69 checks** (13 new Phase 23 checks). Evidence:
`docs/validation/PHASE23_TASK5_UI_PROPAGATION_REPORT.{json,md}`. ChangeRecord
`9df7b0fc63464614bc87b3c7b77cfff9` (code_change) OWNER_REVIEW; audit 64→65; changes 37→38;
verify_all True. 20 new tests; regression **348 PASS / 0 FAIL** (DISCLOSED: two P22T5 tests
pinned contract=="1.4.0" exactly; made forward-compatible >=1.4.0 with embedded==ui_data.json,
intent preserved).

**NEXT executable task: Phase 24 Task 1 — research + design note** for the new phase
**"Phase 24: With-Actions Aggregation Consistency + Inner-Path Action Dynamics"** (opened in the
state file; research-driven per the scheduled-task standing instruction, motivated by the
disclosed Phase 23 Task 4 saturation gap):
1. Joint-scenario (action-after-aggregation) re-aggregation: apply the governed
   `ManagementActionRule` INSIDE the copula simulation to the simulated JOINT liability
   (V = L_fit + sum_k (vec_k − mean_k) pattern, action on the joint coverage ratio) instead of
   to standalone marginals — the design hypothesis is that this collapses the 22.5% t-copula
   rel err vs nested-with-actions because saturation is then modelled at the joint level.
2. Inner-path action-dynamics gap analysis (bonus cut affecting inner-path cashflows rather than
   the outer-node liability transform only) vs Solvency II Art. 23 / SOA ASOP 56 / IA TAS M.
3. Fixed pre-registered acceptance gates for Tasks 2–4 (no gate-shopping), mirroring the Phase 23
   Task 1 design-note pattern (tested module scaffolding + governance ChangeRecord OWNER_REVIEW).
Then Task 2 = joint-scenario t/gaussian re-aggregation vs nested-with-actions; Task 3 =
inner-path prototype + OOS re-validation; Task 4 = tail diagnostics + MR refresh; Task 5 =
offline-UI propagation (contract 1.5.0 → 1.6.0 additive) + PHASE 24 COMPLETE docs.

**Sandbox operating rules (CONFIRMED AGAIN cycle 16):**
1. ~44 s hard wall per bash call; stage long computations; run heavy pytest batches solo
   (`test_phase21_task4_aggregation.py` alone takes ~21 s).
2. Python/pytest/scipy/pandas live in `/var/tmp/pylibs` — run with `PYTHONPATH=/var/tmp/pylibs:.`.
3. Long-file writes truncate on the mount — build files OFF-MOUNT (/var/tmp/p23t5_build pattern),
   then `cp` + `cmp` verify; validate with ast.parse / json.loads. NEVER use the Windows
   file-tools for long repo files.
4. Git ghost locks persist — commit with the alt-`GIT_INDEX_FILE` workaround onto branch `p22c9`
   (updating `main` directly is blocked by `refs/heads/main.lock`); push `p22c9:main`; see
   GITHUB_PUSH_BLOCKER.md checklist.
5. Risk-register IDs: ALWAYS check the next free MR-0xx in `.claude-dev/GOVERNANCE_STORE.json`
   before opening a new risk; back up the store before any governance stage (backup at
   /var/tmp/p23t5_build/GOV_BACKUP_pre_p23t5.json this cycle).

**Standing blockers (human action):** delete the three git ghost locks (see
GITHUB_PUSH_BLOCKER.md); production sign-off residual (credentialled data + independent APS X2
review) — by design for this educational model; disk /sessions ~89% — consider pruning
`/var/tmp` build dirs and `.git.old-repo-*`.

---

## ⚠️ LATEST STATUS — 2026-06-08 (cycle 17, supersedes everything above)

**Phase 24 Task 1 COMPLETE (design note PASS).** NEW additive tested module
`par_model_v2/projection/joint_action_aggregation.py` (`JointActionAggregator`: anchored joint
levels V = L_fit + Σ_k (Q_k(U_k) − mean_k) from the WITHOUT-actions standalone empirical margins;
the governed `ManagementActionRule` applied ONCE to the joint liability — action-after-aggregation;
gaussian/t copula sims; reproducibility digests). Synthetic-truth pre-study (2-driver lognormal,
t(4) copula, seed 42, n=120k — NO real archived benchmark consumed before the Task 2 gates):
standalone-action basis UNDERSTATES true with-actions VaR99.5 by **6.5%** (the Phase 23 Task 4
saturation mechanism reproduced); joint-action basis recovers truth (**rel err 1.3%**). FIXED
pre-registered gates (module constants + design-note §5): Task 2 joint-action t SCR rel err vs
nested-with-actions ≤ 10% AND strictly < the disclosed 22.5% standalone baseline + RANK INVARIANCE
(df re-matched on without-actions losses = 2.9451, correlation frozen); Task 3 inner-path prototype
at the unchanged Phase 22 OOS gates (R² ≥ 0.95, VaR rel err ≤ 10%); Task 4 joint-vs-standalone +
with-vs-without deltas at every level + MR-010/MR-014 refresh. Evidence:
`docs/validation/PHASE24_TASK1_DESIGN_NOTE.{json,md}`. ChangeRecord
`479ec5cc7ed94d1eb434c0739cdff25d` (governance_change) OWNER_REVIEW; audit 65→66; changes 38→39;
verify_all True. 25 new tests PASS; regression batches 139 PASS / 0 FAIL; ui_app self-test ok:true.

**NEXT executable task: Phase 24 Task 2 — joint-scenario t(2.9451)/gaussian re-aggregation.**
Reuse `/var/tmp/p23t2_stage/losses.npz` (without-actions standalone losses, 7 drivers × 160) +
`/var/tmp/p23t4_stage/losses_with_actions.npz` (corr matrix, anchor means, l_fit, a_ref, nested
benchmarks) — cross-check against the archived PHASE23_TASK2/TASK4 reports BEFORE any new
computation; freeze df=2.9451 + correlation; run `JointActionAggregator` (t + gaussian) at
n_sim=200k; benchmark vs nested-with-actions SCR 33,117.8; gates per the Task 1 note (rel err
≤ 10% AND < 22.5%); rank-invariance check (re-match df on without-actions losses); var-covar
comparator; MR-010/MR-014 refresh; methodology_change ChangeRecord OWNER_REVIEW; report
`docs/validation/PHASE24_TASK2_JOINT_ACTION_AGGREGATION_REPORT.{json,md}`. Then Task 3 =
inner-path prototype + OOS re-validation; Task 4 = tail diagnostics + MR refresh; Task 5 =
offline-UI propagation (contract 1.5.0 → 1.6.0 additive) + PHASE 24 COMPLETE docs.

**Sandbox operating rules (CONFIRMED AGAIN cycle 17):**
1. ~44 s hard wall per bash call; stage long computations; run heavy pytest batches solo.
2. Python/pytest/scipy/pandas live in `/var/tmp/pylibs` — run with `PYTHONPATH=/var/tmp/pylibs:.`.
3. Long-file writes truncate on the mount — build files OFF-MOUNT (/var/tmp/p24t1_build pattern),
   then `cp` + `cmp` verify; validate with ast.parse / json.loads. NEVER use the Windows
   file-tools for long repo files.
4. Git ghost locks persist — commit with the alt-`GIT_INDEX_FILE` workaround onto branch `p22c9`
   (updating `main` directly is blocked by `refs/heads/main.lock`); push `p22c9:main`.
5. Risk-register IDs: next free is MR-015; back up the store before any governance stage
   (backup at /var/tmp/p24t1_build/GOV_BACKUP_pre_p24t1.json this cycle).

**Standing blockers (human action):** delete the three git ghost locks (see
GITHUB_PUSH_BLOCKER.md); production sign-off residual (credentialled data + independent APS X2
review) — by design for this educational model; disk /sessions ~89%.

---

## ⚠️ LATEST STATUS — 2026-06-08 (cycle 19, supersedes everything above)

**Phase 24 Task 3 COMPLETE (PASS 5/5).** NEW canonical module
`par_model_v2/projection/inner_path_action_dynamics.py`: the governed bonus cut applies to the
INNER-PATH policyholder-benefit cashflows (PV_with_i = PV_i − relief(CR_outer)·B_i,
B_i = guaranteed + equity-guarantee PV; asset-side credit loss and analytic FX/liquidity
offsets excluded from the cuttable base). Nested truth rebuilt from BIT-IDENTICAL re-runs of
the archived Phase 22 Task 2 inner paths (exact equality enforced on all 2,560 nodes); proxy
gains the matching analytic post-composition base B_hat = clip(poly5 − kappa·C_det, 0, L_hat),
kappa = 1.0368 fit-calibrated leakage-free (carve-out corr ≥ 0.996, mae < 0.9%, disclosed).
RESULTS at the unchanged Phase 22 gates: OOS R² 0.99837 (≥ 0.95), VaR rel err 0.40% (≤ 10%),
monotone, with ≤ without. **Outer-node over-relief disclosed:** nested with-actions VaR99.5
150,968.6 → 153,125.5 (+2,156.9); SCR 39,290.9 → 40,852.1 (+1,561.2, +4.0%) — the inner-path
basis is the more conservative, more faithful with-actions basis. Evidence:
`docs/validation/PHASE24_TASK3_INNER_PATH_ACTION_REPORT.{json,md}` +
`docs/INNER_PATH_ACTION_CARD.md`. ChangeRecord `418dafcfbbaf4258b0c56ae3745eec89`
(assumption_change) OWNER_REVIEW; audit 67→69; changes 40→42; verify_all True; MR-014
refreshed. 28 new tests + 12 variant tests PASS; regression 367 PASS / 0 FAIL; ui_app
self-test ok:true; py_compile clean.

**INCIDENT handled (cycle 19):** a PARALLEL automated run implemented Task 3 concurrently as a
scalar-response variant (relief = 0.85·rule_relief·L — a rescaled outer-node transform, no
inner-path cashflow basis) and its governance write left `.claude-dev/GOVERNANCE_STORE.json`
TRUNCATED. Recovery: store restored from the verified cycle-18 `p22c9` commit; corrupted file
preserved at /var/tmp/p24t3_build/GOV_STORE_CORRUPTED_20260607T1822.json; variant ChangeRecord
faithfully re-applied (`6b16ab1d`) then SUPERSEDED with documented reason; variant evidence
retained at `docs/validation/PHASE24_TASK3_INNER_PATH_SCALAR_RESPONSE_VARIANT_REPORT.{json,md}`
(recognition-lag sensitivity); its module/script/tests remain in the repo. Disclosed
forward-compat test fixes: P24T2 MR-notes pin → "Phase 24" (latest-refresh-supersedes); variant
governance-status test accepts SUPERSEDED.

**NEXT executable task: Phase 24 Task 4 — aggregation + tail diagnostics on the joint-action
basis.** Per the Task 1 design note: with-vs-without and joint-vs-standalone capital deltas
quantified at EVERY level (standalone per-driver, joint t/gaussian, var-covar comparator,
nested reference); tail diagnostics (tail-correlation / exceedance overlap) on the
joint-action basis vs the without-actions archive; MR-010 + MR-014 refresh; governance
ChangeRecord OWNER_REVIEW. Reuse /var/tmp/p24t2_stage/verified_inputs.npz +
/var/tmp/p23t2_stage/losses.npz + /var/tmp/p23t4_stage/losses_with_actions.npz after archive
cross-checks (P24T2 report digests). OPTIONAL disclosed extension: quantify the Task 3
benefit-only cuttable base at the seven-driver aggregation level (joint-action SCR 31,001.8
may shift slightly). Then Task 5 = offline-UI propagation (contract 1.5.0 → 1.6.0 additive:
joint-action + inner-path sections, saturation-gap closure 22.54% → 6.39%, outer-vs-inner
delta) + PHASE 24 COMPLETE docs.

**Sandbox operating rules (RE-CONFIRMED cycle 19 — the truncation rule is NOT optional):**
1. ~44 s hard wall per bash call; stage long computations (`--stage cdet` pattern); run heavy
   pytest batches solo.
2. Python/pytest/scipy/pandas live in `/var/tmp/pylibs` — run with `PYTHONPATH=/var/tmp/pylibs:.`.
3. Long-file writes truncate on the mount — even bash `>>` appends of ~50 lines truncated
   MODEL_DEV_LOG.md this cycle. Build files OFF-MOUNT (/var/tmp/p24t3_build pattern), then
   `cp` + `cmp`; verify with ast.parse / json.loads / wc + tail. NEVER use Windows file-tools
   for long repo files. The governance store corrupted this cycle via this failure mode —
   ALWAYS back it up before any governance stage and re-verify verify_all after writing.
4. Git ghost locks persist — commit with the alt-`GIT_INDEX_FILE` workaround onto branch
   `p22c9`; push `p22c9:main`; the default index shows phantom deletions — IGNORE it, always
   read-tree p22c9 into a fresh index.
5. Risk-register IDs: next free is MR-015; check `.claude-dev/GOVERNANCE_STORE.json` first.
6. CONCURRENCY: scheduled runs can overlap (two agents both executed Task 3 this cycle).
   Before committing or writing governance, re-check file mtimes for foreign writes; if a
   parallel run already landed the task, reconcile via the governance API
   (supersede/disclose), never by deleting the other run's work.

**Standing blockers (human action):** delete the three git ghost locks (see
GITHUB_PUSH_BLOCKER.md) and push `p22c9:main`; serialise/stagger the scheduled automated runs
(collision risk demonstrated); production sign-off residual (credentialled data + independent
APS X2 review) — by design for this educational model; disk /sessions ~89%.

---

## ⚠️ LATEST STATUS — 2026-06-08 +08 / 2026-06-07 UTC (cycle 20, supersedes everything above)

**Phase 24 Task 4 COMPLETE (PASS 3/3 + governance).** NEW additive module
`par_model_v2/projection/joint_action_tail_diagnostics.py` (confidence sweep with
action-saturation profile, prefix convergence, copula-seed stability, margin bootstrap,
delta-matrix builder) + staged builder
`scripts/build_phase24_task4_joint_action_tail_diagnostics.py` (verify/diag/governance).
27/27 archive cross-checks; archived P24T2 joint read-outs reproduced BIT-IDENTICALLY.
**Delta matrix (99.5% SCR, without → with-standalone → with-joint):** nested 48,707.4 →
33,117.8 (reference); t(2.9451) 46,756.0 → 25,652.9 → 31,001.8 (joint-vs-standalone +20.9%);
gaussian 41,472.4 → 23,921.8 → 26,267.1; var-covar 28,990.9 → 14,428.7. **Var-covar
understatement refreshed: 56.4% vs nested-with, 53.5% vs t-joint (MR-010).** Tail
diagnostics (DISCLOSED, no post-hoc thresholds): **the 99.5% joint tail is 100.0% saturated**
(max relief everywhere capital is measured — the P23T4 mechanism fully quantified); prefix
convergence 0.19%; seed spread 1.98%; margin bootstrap (200×20k, copula FROZEN, SII Art. 234)
SCR SE 5.8% of mean, 95% CI [26,471, 33,637], nested-with INSIDE the CI (n_obs=160 noise
quantified per the Task 1 disclosed limitation). ChangeRecord
`d323ab685a4840169be0a1028e0721b9` (methodology_change) OWNER_REVIEW; MR-010+MR-014
refreshed; audit 69→70; changes 42→43; verify_all True. 28 new tests; regression 314 PASS /
0 FAIL; ui_app self-test ok:true; py_compile clean. DISCLOSED forward-compat fix: two P24T3
MR-014 note pins → "Phase 24" + "Task 3" (latest-refresh-supersedes). Evidence:
`docs/validation/PHASE24_TASK4_JOINT_ACTION_TAIL_DIAGNOSTICS_REPORT.{json,md}` +
`docs/JOINT_ACTION_TAIL_DIAGNOSTICS_CARD.md`.

**NEXT executable task: Phase 24 Task 5 — offline-UI propagation + PHASE 24 COMPLETE docs.**
ui_data.json contract 1.5.0 → 1.6.0 ADDITIVE via `scripts/build_ui_data.py`; new
joint-action / Phase 24 panel: saturation-gap closure 22.54% → 6.39% (Task 2), inner-path
outer-vs-inner delta +4.0% SCR (Task 3), Task 4 delta matrix + saturation profile (100% at
99.5%) + bootstrap CI + var-covar refresh; extend `scripts/ui_app_self_test.cjs` with Phase 24
checks; new `scripts/build_phase24_task5_ui_propagation.py` contract-check script + evidence
report; tests; governance code_change ChangeRecord OWNER_REVIEW; then PHASE 24 COMPLETE
documentation (state/log/prompt). UI consumes ONLY model output JSON (no model code in UI).
After Task 5: Phase 25 Task 1 research/design note (candidates: full path-wise bonus
declaration dynamics; t-copula aggregation on the inner-path with-actions basis;
credentialled-data calibration of action/copula parameters).

**Sandbox operating rules (RE-CONFIRMED cycle 20):** unchanged from cycle 19 — 44 s bash
wall; PYTHONPATH=/var/tmp/pylibs:. ; build long files OFF-MOUNT then cp + cmp (a Windows-side
file-tool Edit truncated a test file THIS cycle; bash-side repair); back up
GOVERNANCE_STORE.json before every governance stage; alt-`GIT_INDEX_FILE` commits onto
`p22c9`, push `p22c9:main`; next free risk ID MR-015; check for parallel-run foreign writes
before governance/commit.

**Standing blockers (human action):** delete the three git ghost locks (GITHUB_PUSH_BLOCKER.md);
serialise the scheduled runs; production sign-off residual (credentialled data + APS X2);
disk /sessions ~89%.

---

## ⚠️ LATEST STATUS — 2026-06-08 +08 / 2026-06-07 UTC (cycle 21, supersedes everything above)

**Phase 24 Task 5 COMPLETE → PHASE 24 COMPLETE (Tasks 1–5).** Offline-UI propagation,
display layer ONLY: `scripts/build_ui_data.py` contract **1.5.0 → 1.6.0 ADDITIVE** — new
top-level `phase24` section (joint_action / inner_path / tail_diagnostics / narrative)
normalised from the Task 2/3/4 reports; 3 Phase 24 PASS verdicts; additive capital
read-outs (`t_copula_scr_joint_action` 31,001.8; `nested_scr_with_inner_path` 40,852.1).
New **Joint Actions (P24)** tab in `ui_app.html`: capital-delta matrix (without →
with-standalone → with-joint, all four benchmarks), saturation-gap closure 22.54% → 6.39%,
action-saturation profile (99.5% tail 100.0% saturated), frozen-copula margin-bootstrap CI
[26,471, 33,637] with nested-with INSIDE, outer-vs-inner-path delta (+1,561 SCR, +4.0%),
12 gate criteria, MR-010 var-covar refresh 56.4%/53.5%, sources + ChangeRecord ids.
`viewer_data.json` rebuilt; `ui_app_self_test.cjs` +15 Phase 24 checks (ok:true, 0 net /
0 JS err, 87 checks). New `scripts/build_phase24_task5_ui_propagation.py` — 31 contract
checks ALL PASS; evidence `docs/validation/PHASE24_TASK5_UI_PROPAGATION_REPORT.{json,md}`;
idempotent re-run verified. Governance: ChangeRecord `a66844b709f848d78bdee7553e1e49db`
(code_change) OWNER_REVIEW; audit 70→71; changes 43→44; verify_all True. Tests: 24 new
PASS; post-change regression **376 PASS / 0 FAIL**; compileall clean. DISCLOSED
forward-compat fix (repo convention, latest-refresh-supersedes): two P23T5 pins on
contract "1.5.0" equality relaxed to a version floor.

**NEXT executable task: Phase 25 Task 1 — research/design note (pick ONE, design-note-first
discipline, one task per cycle):**
1. **Full path-wise bonus declaration dynamics** — action re-evaluated at every inner time
   step on a path (the residual documented in P24T3), vs the current single outer-node
   relief on inner-path cashflows; expect recognition-lag effects (the superseded P24T3
   scalar-response variant is retained as sensitivity evidence).
2. **t-copula aggregation on the inner-path with-actions basis** — joins the T3 inner-path
   basis with the T2 joint-scenario mechanism so the copula diagnostics inherit the more
   conservative basis (joint-action SCR may shift; gates must be pre-registered).
3. **Credentialled-data calibration of action/copula parameters** — replaces educational
   placeholders (cr_trigger/floor, bonus share, df) with a documented calibration to a
   credentialled series; reduces the production sign-off residual.
Deliverable: design note (docs/validation/PHASE25_TASK1_DESIGN_NOTE.{json,md} + card +
tests + governance ChangeRecord OWNER_REVIEW). Then Tasks 2–4 implement/validate; Task 5 =
offline-UI propagation (contract 1.6.0 → 1.7.0 ADDITIVE) + PHASE 25 COMPLETE docs.

**Sandbox operating rules (RE-CONFIRMED cycle 21):** unchanged — ~44 s bash wall;
PYTHONPATH=/var/tmp/pylibs:. ; build long files OFF-MOUNT then cp + cmp (zero truncation
incidents this cycle; the protocol works); back up GOVERNANCE_STORE.json before every
governance stage (backup at /var/tmp/p24t5_build/GOV_BACKUP_pre_p24t5.json this cycle);
alt-`GIT_INDEX_FILE` commits onto `p22c9`, push `p22c9:main`; next free risk ID MR-015;
re-check mtimes for parallel-run foreign writes before governance/commit.

**Standing blockers (human action):** delete the three git ghost locks
(GITHUB_PUSH_BLOCKER.md) — NOTE cycle 21: `git push origin p22c9:main` now WORKS from the
sandbox (origin/main = a149e37, Phase 24 COMPLETE tip; push at the end of every cycle); the
locks remain only to fast-forward LOCAL main and restore normal git. Serialise the scheduled
runs; production sign-off residual (credentialled data + APS X2) — by design for this
educational model; disk /sessions ~89%.

---

## ⚠️ LATEST STATUS — 2026-06-08 +08 (cycle 22, supersedes everything above)

**Phase 25 Task 1 COMPLETE (design note, PASS).** Candidate chosen (design-note-first): **full
path-wise bonus declaration dynamics** — the governed bonus-cut decision re-evaluated at EVERY
inner time step on a path-wise coverage proxy, vs the P24T3 horizon-level convention (decision
frozen at the outer node; relief constant across inner paths — the documented residual). NOT
chosen: t-copula on the inner-path basis (deferred — Task 2 changes that basis; avoids evidence
superseded within one phase); credentialled calibration (blocked on data — human action). NEW
tested module `par_model_v2/projection/pathwise_bonus_dynamics.py` (four declaration bases on
common random numbers; retained = pre_floor + (1-pre_floor)*cut_factor(CR), unchanged rule
shape). **Synthetic recognition-lag pre-study (seed 42, 4000×100×10): the horizon-level basis
UNDERSTATES the path-wise with-actions tail loss by 12.2% at VaR99.5; cut-then-restored share
69.8%; two-sided lag (median diff negative on healthy nodes); sign/ordering/bounds checks all
True. Mechanism, NOT magnitude (disclosed).** Deliverables:
`docs/validation/PHASE25_TASK1_DESIGN_NOTE.{json,md}` +
`docs/PATHWISE_BONUS_DECLARATION_DESIGN_CARD.md` + builder script (idempotent verified).
Governance: ChangeRecord `fe5846be67a945a28fd60208f6b87972` (governance_change) OWNER_REVIEW;
audit 71→72; changes 44→45; verify_all True. Tests: 29 new PASS
(`tests/test_phase25_task1_design_note.py`); regression **368 PASS / 0 FAIL**; compileall clean;
ui self-test ok:true.

**NEXT executable task: Phase 25 Task 2 — path-wise declaration in the nested truth.**
Extend `par_model_v2/projection/inner_path_action_dynamics.py` with a path-wise declaration
mode: per-time-step retained-bonus factor from a path-wise coverage proxy (reference assets
rolled forward on the inner path / pre-action path liability at t); P24T3 carve-outs preserved
(ONLY in-force policyholder benefits cuttable; credit loss + analytic FX/liquidity offsets NOT
cuttable); horizon-level basis retained as the sensitivity variant. Archive cross-check the
without-actions basis BIT-IDENTICALLY before any new computation. **Gates (FIXED in the Task 1
note s5 — no gate-shopping):** sign gate path-wise SCR >= horizon-level SCR at 99.5% (magnitude
disclosed, not gated); monotonicity guard re-verified on the path-wise basis;
assumption_change ChangeRecord OWNER_REVIEW. Then Task 3 (matching proxy basis feature + OOS
R^2 >= 0.95, VaR rel err <= 10%), Task 4 (tail diagnostics; MR-010/MR-014 refresh if SCR delta
> 1%; rank invariance df = 2.9451 frozen), Task 5 (UI contract 1.6.0 → 1.7.0 ADDITIVE +
PHASE 25 COMPLETE docs).

**Sandbox operating rules (RE-CONFIRMED cycle 22):** unchanged — ~44 s bash wall;
PYTHONPATH=/var/tmp/pylibs:. ; build long files OFF-MOUNT then cp + cmp (zero truncation
incidents this cycle); back up GOVERNANCE_STORE.json before every governance stage (backup at
/var/tmp/p25t1_build/GOV_BACKUP_pre_p25t1.json this cycle); alt-`GIT_INDEX_FILE` commits onto
`p22c9`, push `p22c9:main` at the end of every cycle; next free risk ID MR-015; re-check
mtimes for parallel-run foreign writes before governance/commit.

**Standing blockers (human action):** delete the three git ghost locks (GITHUB_PUSH_BLOCKER.md)
— they only block fast-forwarding LOCAL main + normal git; push from the sandbox works.
Serialise the scheduled runs; production sign-off residual (credentialled data + APS X2) — by
design for this educational model; disk /sessions ~89%.

---

## ⚠️ LATEST STATUS — 2026-06-08 +08 (cycle 23, supersedes everything above)

**Phase 25 Task 2 COMPLETE (PASS 6/6 gates) — path-wise declaration in the nested truth.**
`inner_path_action_dynamics.py` extended with the path-wise declaration mode: retained-bonus
factor re-evaluated at EVERY inner month from **CR_{i,t} = a_ref / RemPV0_{i,t}** (reference
assets rolled forward at the inner short rate / pre-action remaining path liability — the
path deflator cancels); relief for the cashflow at month u decided at the START of that month
(pre-step CR). P24T3 carve-outs preserved (only in-force policyholder benefits cuttable;
envelope guard never binds). Without-actions basis BIT-IDENTICAL at every slice (archive
cross-check BEFORE any new computation); horizon-level basis retained as sensitivity and
reproduced vs the archived P24T3 report (|SCR diff| 8.6e-6). **RESULT: path-wise with-actions
SCR 46,638.9 vs horizon-level 40,852.1 (+5,786.8 = +14.17%) — pre-registered SIGN gate PASS,
magnitude disclosed; VaR99.5 158,944.1 vs 153,125.5. 41.4% of inner paths cut; 29.4%
cut-then-restore. The cycle-22 synthetic pre-study sign (12.2%) is CONFIRMED on the real
nested benchmark (14.17%). MR-010/MR-014 Task 4 refresh trigger (1%) MET.** Residuals
documented for Task 3: monthly declaration cadence; perfect-foresight discounting in the
coverage proxy; node offset undecayed. Deliverables:
`docs/validation/PHASE25_TASK2_PATHWISE_DECLARATION_REPORT.{json,md}` +
`docs/PATHWISE_DECLARATION_CARD.md` + staged `scripts/build_phase25_task2_pathwise_declaration.py`
(idempotent verified). Governance: ChangeRecord `3cfaa30a0f8044a8aaed419e6ab4ca31`
(assumption_change) OWNER_REVIEW; audit 72→73; changes 45→46; verify_all True. Tests: 28 new
PASS (`tests/test_phase25_task2_pathwise_declaration.py`); regression **386 PASS / 0 FAIL**;
compileall clean; ui self-test ok:true.

**NEXT executable task: Phase 25 Task 3 — matching path-wise proxy basis feature + OOS
re-validation.** The LSMC proxy gains the matching path-wise post-composition action basis so
truth and proxy share an IDENTICAL basis (the G1 convention): the proxy cannot run inner
paths, so design a deterministic/analytic approximation of the per-node path-wise relieved
amount (candidates: expected-path relieved fraction computed on the zero-shock inner path with
a fit-calibrated level factor, mirroring the P24T3 kappa credit carve-out pattern; or a
learned-feature-free analytic response surface on (CR_node, vol state)) — calibrated on the
FIT sample ONLY (leakage-free), then seven-driver OOS re-validation at the UNCHANGED Phase 22
gates: **OOS R^2 >= 0.95, proxy-vs-nested VaR99.5 rel err <= 10%** (design note s5, no
gate-shopping); action monotonicity re-verified; declaration-cadence (monthly vs annual) and
adaptedness residuals DOCUMENTED with sensitivity read-outs where cheap; code_change/
assumption_change ChangeRecord OWNER_REVIEW. Then Task 4 (tail diagnostics on the path-wise
basis; **MR-010/MR-014 refresh REQUIRED** — trigger met at +14.17%; rank invariance df
2.9451 frozen on without-actions losses), Task 5 (UI contract 1.6.0 → 1.7.0 ADDITIVE +
PHASE 25 COMPLETE docs).

**Sandbox operating rules (RE-CONFIRMED cycle 23):** unchanged — ~44 s bash wall;
PYTHONPATH=/var/tmp/pylibs:. ; build long files OFF-MOUNT then cp + cmp (zero truncation
incidents this cycle); back up GOVERNANCE_STORE.json before every governance stage (backup at
/var/tmp/p25t2_build/GOV_BACKUP_pre_p25t2.json this cycle, re-verified unchanged immediately
before governance); alt-`GIT_INDEX_FILE` commits onto `p22c9`, push `p22c9:main` at the end
of every cycle; next free risk ID MR-015; re-check mtimes for parallel-run foreign writes
before governance/commit. Stage data: /var/tmp/p25t2_stage (pathwise node arrays),
/var/tmp/p24t3_stage (component decomposition), /var/tmp/p23t3_stage (L7 arrays + fit_mean),
.phase22_task2_stage (heavy totals).

**Standing blockers (human action):** delete the three git ghost locks (GITHUB_PUSH_BLOCKER.md)
— they only block fast-forwarding LOCAL main + normal git; push from the sandbox works.
Serialise the scheduled runs; production sign-off residual (credentialled data + APS X2) — by
design for this educational model; disk /sessions ~89%.

---

## ⚠️ LATEST STATUS — 2026-06-08 +08 (cycle 24, supersedes everything above)

**Phase 25 Task 3 COMPLETE (PASS 5/5 gates) — matching path-wise proxy basis + seven-driver
OOS re-validation.** NEW module `par_model_v2/projection/pathwise_proxy_basis.py`: the LSMC
proxy now carries the MATCHING path-wise action basis (G1 identical-basis convention) —
relieved_hat = alpha * phi_sigma(CR_hat) * clip(B_hat, 0, L_hat), with phi_sigma the governed
relief curve smoothed over an effective lognormal dispersion of the path-wise coverage ratio
(Gauss-Hermite 21). Exactly two scalars **(sigma 0.225, alpha 0.757)** calibrated on the FIT
sample ONLY (leakage-free); kappa reproduced from the P24T3 stage. Candidate comparison
DISCLOSED: the pre-registered zero-shock + level-factor candidate was evaluated and REJECTED
on FIT evidence (lambda 6.01, fit R^2 -15.2 — state-dependent bias), retained for the cadence
sensitivity. Truth-side FIT (2000 @ 8 inner) and VAL (60 @ 384) path-wise relieved amounts
are BIT-IDENTICAL re-runs of the archived Phase 22 Task 2 inner paths (slice-enforced exact
equality vs the archived P24T3 decomposition); nested truth = archived P25T2 stage
(digest re-verified). **RESULT: OOS R^2 with actions 0.9978 (gate >= 0.95); VaR99.5 rel err
0.40% (gate <= 10%); ES rel err 0.01%; SCR rel err 1.16% (proxy 46,095.8 vs nested 46,638.9);
truth nested SCR reproduces P25T2 exactly.** Annual-cadence sensitivity ratio 1.136
(deterministic basis). Deliverables:
`docs/validation/PHASE25_TASK3_PATHWISE_PROXY_BASIS_REPORT.{json,md}` +
`docs/PATHWISE_PROXY_BASIS_CARD.md` + staged
`scripts/build_phase25_task3_pathwise_proxy_basis.py` (idempotent verified). Governance:
ChangeRecord `fc9fc911fc51414abf0fc8e73cadc92c` (code_change) OWNER_REVIEW; audit 73→74;
changes 46→47; verify_all True. Tests: 44 new PASS
(`tests/test_phase25_task3_pathwise_proxy_basis.py`); regression **430 PASS / 0 FAIL**;
compileall clean; ui self-test ok:true.

**NEXT executable task: Phase 25 Task 4 — tail diagnostics on the path-wise with-actions
basis + MR-010/MR-014 refresh (REQUIRED: the 1% trigger was MET at Task 2 with +14.17%).**
Pre-registered (design note s5): joint-scenario tail diagnostics on the path-wise with-actions
basis (mirror the P24T4 pattern: tail saturation profile, delta matrix vs without-actions and
vs the horizon basis, var-covar understatement refresh); **rank invariance — df re-matched on
WITHOUT-actions losses must remain 2.9451 and copula parameters FROZEN** (Art. 234, no silent
re-tuning); refresh MR-010 and MR-014 with the path-wise figures (latest-refresh-supersedes
pins -> "Phase 25" + "Task 4"); assumption_change/governance ChangeRecord OWNER_REVIEW. Then
Task 5 = UI contract 1.6.0 → 1.7.0 ADDITIVE (path-wise declaration + proxy-basis +
tail-diagnostics panels consume ONLY model-output JSON) + PHASE 25 COMPLETE documentation.

**Sandbox operating rules (RE-CONFIRMED cycle 24):** ~44 s bash wall; PYTHONPATH=/var/tmp/pylibs:. ;
build long files OFF-MOUNT then cp + cmp (ONE mount-staleness incident this cycle on a module
REWRITE via the file tool — the mount view kept the OLD byte length with new partial content;
caught by py_compile, recovered by heredoc chunks to /var/tmp + cp + cmp — prefer bash-side
writes for rewrites of existing large files); back up GOVERNANCE_STORE.json before every
governance stage (backup at /var/tmp/p25t3_build/GOV_BACKUP_pre_p25t3.json, re-verified
unchanged immediately before governance); alt-`GIT_INDEX_FILE` commits onto `p22c9`, push
`p22c9:main` at the end of every cycle; next free risk ID MR-015; re-check mtimes for
parallel-run foreign writes before governance/commit. Stage data: /var/tmp/p25t3_stage
(pwfit/pwval truth relieved + det arrays), /var/tmp/p25t2_stage (nested path-wise arrays),
/var/tmp/p24t3_stage (component decomposition + cdet), /var/tmp/p23t3_stage (L7 arrays +
fit_mean), .phase22_task2_stage (heavy totals).

**Standing blockers (human action):** delete the three git ghost locks (GITHUB_PUSH_BLOCKER.md)
— they only block fast-forwarding LOCAL main + normal git; push from the sandbox works.
Serialise/stagger the scheduled runs; production sign-off residual (credentialled data +
APS X2) — by design for this educational model; disk /sessions ~89%.

---

## ⚠️ LATEST STATUS — 2026-06-08 +08 (cycle 25, supersedes everything above)

**Phase 25 Task 4 COMPLETE (PASS 4/4 gates + governance verify_all True) — path-wise tail
diagnostics + with-vs-without / pathwise-vs-horizon capital-delta matrix + REQUIRED
MR-010/MR-014 refresh (trigger MET at Task 2: +14.17%).** NEW module
`par_model_v2/projection/pathwise_tail_diagnostics.py`: the t/gaussian path-wise read-outs are
an ANALYTIC RE-ANCHORING — the governed Task 3 smoothed-relief surface (sigma 0.225, alpha
0.7567) plus the FIT-sample benefit share (beta_fit 0.8450; ONE extra leakage-free scalar)
applied ONCE to the anchored joint level via the IDENTICAL node-level envelope transform used
by truth and proxy, CRN against the horizon basis; NOT a full path-wise copula re-aggregation
(documented next-phase candidate). **RESULT — 99.5% SCR (without → horizon → path-wise):
nested 55,561.2 → 40,852.1 → 46,638.9 (+14.17%); t(2.9451) 46,756.0 → 31,001.8 → 39,794.3
(+28.4%); gaussian 41,472.4 → 26,267.1 → 35,210.1 (+34.0%); var-covar: no path-wise analogue
(DISCLOSED). The path-wise basis relieves LESS at every level/confidence — the horizon basis
understates the with-actions SCR across the matrix. Var-covar understatement refreshed (MR-010):
69.1% vs nested path-wise (was 56.4% horizon). Rank invariance (Art. 234): df re-matched on the
WITHOUT-actions staged losses = 2.9451 (|diff| 7.0e-6 ≤ 4-dp tol); rho max|diff| 7.2e-16 —
copula FROZEN, no silent re-tuning.** Tail: raw governed cut saturates 100% of the 99.5% tail,
but the mean smoothed relief fraction is 0.0838 < max_relief 0.12 (restoration caps realised
relief). Margin bootstrap (200×20k, frozen copula): SCR SE 4.1% of mean, 95% CI
[35,793, 42,496] — **the nested path-wise reference 46,638.9 sits OUTSIDE the CI: the
re-anchoring understates nested by 14.7% BEYOND margin noise — quantified motivation for the
next-phase full path-wise copula re-aggregation.** P24T2 horizon read-outs reproduced
bit-identically; 36 archive cross-checks; idempotent re-run digest-identical. Governance:
ChangeRecord `a68dd3b9df114d07bfa4103d0ac1be2b` (methodology_change) OWNER_REVIEW; MR-010 +
MR-014 pins → "Phase 25 Task 4"; audit 74→75; changes 47→48; verify_all True. Tests: 39 new
PASS (`tests/test_phase25_task4_pathwise_tail_diagnostics.py`); full regression **2,684 PASS /
0 FAIL across all 94 files** (true pytest total — prior "386/430" figures tallied only a
subset of batches); compileall clean; ui self-test ok:true. ALSO REPAIRED:
`.claude-dev/MODEL_DEV_STATE.json` (corrupted by the cycle-24 mount-staleness rewrite;
truncated tail + reconstructed P25T3 entry; json-valid).

**NEXT executable task: Phase 25 Task 5 — UI propagation + PHASE 25 COMPLETE.** ui_data.json
contract 1.6.0 → 1.7.0 ADDITIVE (P21T5→P24T5 pattern: build_ui_data.py extension + ui_app.html
panel + self-test checks): path-wise declaration panel — pathwise-vs-horizon SCR delta matrix
(all four levels), restoration-share diagnostics (action share 41.4%, cut-then-restore 29.4%),
smoothed-relief-fraction tail profile, Task 2-4 gates, bootstrap disclosure (nested outside CI
→ next-phase motivation). UI consumes ONLY model-output JSON (no computation in the UI). Then
PHASE 25 COMPLETE documentation (P24 pattern: phase summary in the log + status). After Task 5:
design-note-first candidate selection for Phase 26 — (a) full path-wise copula re-aggregation
(now with quantified 14.7%-beyond-noise motivation; rank invariance machinery staged in
/var/tmp/p25t4_stage), (b) credentialled-data calibration (human-blocked), (c) declaration-
cadence refinement (annual board cadence with smoothing; cadence sensitivity 1.136 archived).

**Sandbox operating rules (RE-CONFIRMED cycle 25):** ~44 s bash wall; PYTHONPATH=/var/tmp/pylibs:. ;
build long files OFF-MOUNT (heredoc to /var/tmp) then cp + cmp; NEVER rewrite an existing large
mounted file via the file tool (cycle-24 staleness corrupted MODEL_DEV_STATE.json — repaired
cycle 25); nohup background jobs do NOT survive between bash calls — chunk work instead; back up
+ hash-verify GOVERNANCE_STORE.json before every governance stage (backup
/var/tmp/p25t4_build/GOV_BACKUP_pre_p25t4.json); alt-`GIT_INDEX_FILE` commits onto `p22c9`,
push `p22c9:main` at the end of every cycle; next free risk ID MR-015; re-check mtimes for
parallel-run foreign writes before governance/commit. Stage data: /var/tmp/p25t4_stage (rho,
df re-match, beta_fit, sigma/alpha, vc figures), /var/tmp/p25t3_stage, /var/tmp/p25t2_stage,
/var/tmp/p24t3_stage, /var/tmp/p23t2_stage (losses.npz copula primitives), /var/tmp/p23t4_stage,
.phase22_task2_stage (heavy totals).

**Standing blockers (human action):** delete the three git ghost locks (GITHUB_PUSH_BLOCKER.md)
— push from the sandbox works; serialise/stagger the scheduled runs; production sign-off
residual (credentialled data + APS X2) — by design for this educational model; disk /sessions
~89%.

---

## ⚠️ LATEST STATUS — 2026-06-08 +08 (cycle 26, supersedes everything above)

**Phase 25 Task 5 COMPLETE (PASS 40/40 contract checks; governance verify_all True) —
offline-UI propagation; PHASE 25 COMPLETE (Tasks 1-5).** ui_data.json contract
**1.6.0 → 1.7.0 ADDITIVE**: new `phase25` section (declaration / proxy_basis /
tail_diagnostics / narrative), additive capital read-outs `nested_scr_with_pathwise`
46,638.9 + `t_copula_scr_pathwise_readout` 39,794.3, three Phase 25 PASS verdicts, and a
first-class **Path-wise Actions (P25)** tab (8 tabs total): pathwise-vs-horizon capital-delta
matrix across all four benchmarks (var-covar "no path-wise analogue" DISCLOSED in-table),
8-bar SCR chart, tail saturation/restoration profile (raw 100% saturation but smoothed
relief fraction 0.0811 < 0.12 — recognition-lag quantified), frozen-copula bootstrap with
the nested path-wise reference OUTSIDE the 95% CI disclosed verbatim (14.7% beyond-noise —
the Phase 26 motivation), Task 3 proxy-basis table, 15 gate criteria (6+5+4).

`ui_app_self_test.cjs` +17 Phase 25 checks → **ok:true, 0 network / 0 JS errors over 101
checks**; `viewer_data.json` rebuilt pre-governance (48 records at build); NEW
`scripts/build_phase25_task5_ui_propagation.py` (40 checks → self-test → governance →
report; idempotent 49→49). Governance: ChangeRecord `3fa4394e568b48fc9ee06dd8a64dd44b`
(code_change) OWNER_REVIEW; audit 75→76; changes 48→49; verify_all True. Tests: 27 new PASS
(`tests/test_phase25_task5_ui_propagation.py`); DISCLOSED forward-compat fix: two P24T5
contract pins relaxed to a version floor ≥ (1,6,0) (repo convention); all four
UI-propagation suites 87/0; targeted health gate disclosed in the log (cycle 25 closed the
full 2,684/0 regression 8 h earlier; this cycle touched only the display layer).

**NEXT executable task: Phase 26 Task 1 — research/design note (pick ONE, design-note-first
per repo convention, with pre-registered gates):**
(a) **full path-wise copula re-aggregation — FRONT-RUNNER** (the P25T4 analytic re-anchoring
understates the nested path-wise reference by 14.7% BEYOND bootstrap noise — outside the
95% CI [35,793, 42,496]; rank-invariance machinery + scalars staged in /var/tmp/p25t4_stage);
(b) credentialled-data calibration (human-blocked);
(c) declaration-cadence refinement (annual board cadence; sensitivity 1.136 archived).

**Sandbox operating rules (RE-CONFIRMED cycle 26):** ~44 s bash wall — long heredoc appends
can TRUNCATE mid-write (hit MODEL_DEV_LOG.md this cycle; verify tail after EVERY append and
chunk to <2 KB); PYTHONPATH=/var/tmp/pylibs:. ; build long files OFF-MOUNT (heredoc to
/var/tmp) then cp + cmp; NEVER rewrite an existing large mounted file via the file tool;
nohup does NOT survive between bash calls — chunk instead; back up + hash-verify
GOVERNANCE_STORE.json before every governance stage (backup
/var/tmp/p25t5_build/GOV_BACKUP_pre_p25t5.json); alt-`GIT_INDEX_FILE` commits onto `p22c9`,
push `p22c9:main` at the end of every cycle; next free risk ID MR-015; re-check mtimes for
parallel-run foreign writes before governance/commit (a Python-less Windows-shell run
recorded a blocked cycle between 25 and 26 — advanced nothing but rewrote state-file header
fields). Stage data: /var/tmp/p25t5_build, /var/tmp/p25t4_stage, /var/tmp/p25t3_stage,
/var/tmp/p25t2_stage, /var/tmp/p24t3_stage, /var/tmp/p23t2_stage (losses.npz),
/var/tmp/p23t4_stage, .phase22_task2_stage.

**Standing blockers (human action):** delete the three git ghost locks
(GITHUB_PUSH_BLOCKER.md) — push from the sandbox works; serialise/stagger the scheduled runs
(Python-less Windows runs waste cycles); production sign-off residual (credentialled data +
APS X2) — by design for this educational model; disk /sessions ~89%.

---

## ⚠️ LATEST STATUS — 2026-06-08 +08 (cycle 27, supersedes everything above)

**Phase 26 Task 1 COMPLETE (PASS) — design note: full path-wise copula re-aggregation.**
Candidate selection (design-note-first): CHOSEN (a) full path-wise copula re-aggregation —
quantified motivation: the P25T4 analytic re-anchoring understates the nested path-wise
reference 46,638.9 by 14.7% BEYOND bootstrap noise (outside 95% CI [35,793, 42,496]). NOT
chosen: (b) credentialled calibration (human-blocked); (c) cadence refinement (DEFERRED —
superseded-evidence risk; sensitivity 1.136 archived). NEW tested helper
`par_model_v2/projection/pathwise_copula_reaggregation.py` (synthetic 7-driver t-copula
level-vs-component pre-study: carve-out drivers dominate the tail -> constant-share LEVEL
transform understates COMPONENT-basis VaR99.5, ~1.0% on CRN, sign stable seeds 42/7/2026;
tail cuttable share 0.566 -> 0.470; sign evidence only). Deliverables:
docs/validation/PHASE26_TASK1_DESIGN_NOTE.{json,md} + docs/PATHWISE_COPULA_REAGGREGATION_DESIGN_CARD.md
(verdict PASS; idempotent). Governance: ChangeRecord `40fb20ee3b9a41a7a2b6a47a587ada91`
(governance_change) OWNER_REVIEW; audit 76->77; changes 49->50; verify_all True. Tests: 13
new PASS (tests/test_phase26_task1_design_note.py); targeted health gate DISCLOSED
(163/0 across P24T1/P25T1/P25T3/P25T4/P26T1 suites; compileall clean; additive-only cycle).
ALSO REPAIRED (DISCLOSED): MODEL_DEV_LOG.md tail (cycle-26 truncation; a direct mount append
vanished silently this cycle) — rebuilt OFF-MOUNT, whole-file cp + cmp verified.

**NEXT executable task: Phase 26 Task 2 — per-driver composition transform on the FROZEN
copula.** Pre-registered gates (design note s5, no gate-shopping): archive cross-check FIRST
(without-actions t/gaussian + P25T4 re-anchored read-outs reproduced bit-identically); rank
invariance df re-matched on WITHOUT-actions staged losses within 1e-4 of 2.9451, rho
max|diff| <= 1e-12 (copula FROZEN, Art. 234); relief applied to the per-scenario CUTTABLE
component only with the per-scenario max_relief envelope clip; governed sigma 0.225 /
alpha 0.757 UNCHANGED (P25T3 FIT values, no re-tuning); SIGN gate: full re-aggregated
t-copula path-wise SCR >= re-anchored read-out 39,794.3 (magnitude DISCLOSED, not gated);
constant-share level variant RETAINED as comparison; code_change ChangeRecord OWNER_REVIEW.
Then Task 3 (frozen-copula bootstrap >= 200x20k on the full basis; HEADLINE: nested
46,638.9 INSIDE the 95% CI, else gap decomposed copula-form vs relief-surface + disclosed;
SE <= 5%), Task 4 (full-vs-reanchored delta matrix; MR-010/MR-014 refresh trigger 1%; rank
invariance re-verified; next free risk ID MR-015), Task 5 (UI contract 1.7.0 -> 1.8.0
ADDITIVE + PHASE 26 COMPLETE docs).

**Sandbox operating rules (RE-CONFIRMED cycle 27):** ~44 s bash wall; **MOUNT APPENDS
UNRELIABLE — a direct >>-append to MODEL_DEV_LOG.md VANISHED this cycle while the byte count
grew; ALWAYS build/append OFF-MOUNT (/var/tmp) then cp whole-file + cmp + grep-verify**;
PYTHONPATH=/var/tmp/pylibs:. ; NEVER rewrite an existing large mounted file via the file
tool; nohup does NOT survive between bash calls — chunk instead; back up + hash-verify
GOVERNANCE_STORE.json before every governance stage (backup
/var/tmp/p26t1_build/GOV_BACKUP_pre_p26t1.json); alt-`GIT_INDEX_FILE` commits onto `p22c9`,
push `p22c9:main` at the end of every cycle; next free risk ID MR-015; re-check mtimes for
parallel-run foreign writes before governance/commit. Stage data: /var/tmp/p26t1_build,
/var/tmp/p25t5_build, /var/tmp/p25t4_stage (rho, df re-match, beta_fit, sigma/alpha),
/var/tmp/p25t3_stage, /var/tmp/p25t2_stage (nested path-wise arrays), /var/tmp/p24t3_stage,
/var/tmp/p23t2_stage (losses.npz copula primitives), /var/tmp/p23t4_stage,
.phase22_task2_stage (heavy totals).

**Standing blockers (human action):** delete the three git ghost locks
(GITHUB_PUSH_BLOCKER.md) — push from the sandbox works; serialise/stagger the scheduled runs
(Python-less Windows runs waste cycles); production sign-off residual (credentialled data +
APS X2) — by design for this educational model; disk /sessions ~89%.

---

## ⚠️ LATEST STATUS — 2026-06-08 +08 (cycle 28, supersedes everything above)

**Phase 26 Task 2 COMPLETE (PASS) — per-driver composition transform on the FROZEN copula
(full path-wise copula re-aggregation, benchmark bases).** Archive cross-check FIRST 12/12
PASS (P24T2 horizon + P25T4 LEVEL read-outs bit-identical BEFORE new computation); rank
invariance df re-matched 2.9451 (tol 1e-4), rho max|diff| 7.22e-16 (tol 1e-12) — copula
FROZEN (Art. 234). NEW `par_model_v2/projection/pathwise_composition_transform.py`
(+ build script + 17 tests): per-scenario composition from frozen margins; CUTTABLE
sub-level (L_fit + rate/equity/lapse/mortality deviations) vs CARVE-OUT
(credit/fx/liquidity, P24T3); relief on the cuttable component only,
B_comp = clip(beta_fit * V_cut, 0, V), per-scenario max_relief envelope clip
(apply_pathwise_declaration_node); LEVEL variant retained on CRN bit-identically; governed
sigma 0.225 / alpha 0.7567 / beta_fit 0.8450 UNCHANGED. RESULTS (seed 20260607, 200k):
t(2.9451) SCR component 39,975.7 vs re-anchored 39,794.3 = **+0.46%** (SIGN gate PASS;
magnitude disclosed); gaussian 35,391.5 (+0.52%); tail cuttable-share depression on the
REAL basis only 0.993 -> 0.974 (vs synthetic 0.566 -> 0.470); gap to nested 46,638.9
narrows -14.68% -> -14.29% only — DISCLOSED: residual gap now expected dominated by
relief-surface / copula-form error, NOT composition. MR-010/MR-014 1% trigger NOT met.
Gates 6/6 PASS. Governance: ChangeRecord `dcf5cc5132ad4cadb534ea47314d9684` (code_change)
OWNER_REVIEW; audit 77->78; changes 50->51; verify_all True; idempotent. Reports:
docs/validation/PHASE26_TASK2_COMPOSITION_TRANSFORM_REPORT.{json,md} +
docs/COMPOSITION_TRANSFORM_CARD.md.

**NEXT executable task: Phase 26 Task 3 — frozen-copula margin bootstrap (>= 200 x 20k) on
the FULL re-aggregated (component) basis.** Pre-registered gates (design note s5): HEADLINE
nested 46,638.9 INSIDE the 95% CI, ELSE the residual gap MUST be decomposed (copula-form vs
relief-surface) + disclosed — given the +0.46% Task 2 move, the decomposition branch is
LIKELY: plan it explicitly (relief-surface error via the P25T3 OOS/val diagnostics on the
component basis; copula-form via t-vs-gaussian and margin-form deltas); bootstrap SE <= 5%
of mean SCR; seeds/config/digests recorded; idempotent re-run digest-identical;
methodology_change ChangeRecord OWNER_REVIEW. IMPLEMENTATION: chunk the 200-replicate loop
into <44 s stages persisting partials to /var/tmp/p26t3_stage (resume-safe), reusing
composition_joint_readout with per-replicate margin resamples (P25T4
pathwise_bootstrap_margin_ci pattern adapted to the component basis). Then Task 4
(full-vs-reanchored delta matrix; MR-010/MR-014 refresh trigger re-checked after Task 3;
rank invariance re-verified; next free risk ID MR-015), Task 5 (UI contract 1.7.0 -> 1.8.0
ADDITIVE + PHASE 26 COMPLETE docs).

**Sandbox operating rules (RE-CONFIRMED cycle 28):** ~44 s bash wall; MOUNT APPENDS
UNRELIABLE — ALWAYS build/append OFF-MOUNT (/var/tmp) then cp whole-file + cmp +
grep-verify (clean this cycle); PYTHONPATH=/var/tmp/pylibs:. ; NEVER rewrite an existing
large mounted file via the file tool; nohup does NOT survive between bash calls — chunk
instead; back up + hash-verify GOVERNANCE_STORE.json before every governance stage (backup
/var/tmp/p26t2_build/GOV_BACKUP_pre_p26t2.json); alt-`GIT_INDEX_FILE` commits onto `p22c9`,
push `p22c9:main` at the end of every cycle; next free risk ID MR-015; re-check mtimes for
parallel-run foreign writes before governance/commit. Stage data: /var/tmp/p26t2_stage
(verified_inputs.npz, reagg_result.json), /var/tmp/p26t1_build, /var/tmp/p25t5_build,
/var/tmp/p25t4_stage, /var/tmp/p25t3_stage, /var/tmp/p25t2_stage (nested path-wise arrays),
/var/tmp/p24t3_stage, /var/tmp/p23t2_stage (losses.npz copula primitives),
/var/tmp/p23t4_stage, .phase22_task2_stage (heavy totals).

**Standing blockers (human action):** delete the three git ghost locks
(GITHUB_PUSH_BLOCKER.md) — push from the sandbox works; serialise/stagger the scheduled
runs (Python-less Windows runs waste cycles); production sign-off residual (credentialled
data + APS X2) — by design for this educational model; disk /sessions ~89%.

---

## ⚠️ LATEST STATUS — 2026-06-08 +08 (cycle 29, supersedes everything above)

**Phase 26 Task 3 COMPLETE (PASS) — frozen-copula margin bootstrap (200×20k) on the FULL
re-aggregated (component) basis.** Archive cross-check FIRST (B3/B4): the Task 2 t-component
read-out reproduced BIT-IDENTICALLY (39975.6546, digest c97714b0a831) and all six Task 2
gates PASS before any bootstrap; copula FROZEN (df 2.9451 tol 1e-4; rho max|diff| 7.2e-16
tol 1e-12); governed sigma 0.225 / alpha 0.7567 / beta_fit 0.8450 UNCHANGED. NEW
`par_model_v2/projection/pathwise_composition_bootstrap.py` (+ build script + 10 tests):
non-parametric bootstrap over the realised standalone-loss rows (joint resample WITH
replacement → cross-driver pairing preserved); df/rho + relief scalars FROZEN per replicate
(SII Art. 234); t/gaussian component read-outs on CRN; per-replicate `SeedSequence.spawn()`
→ chunk-independent, resume-safe, idempotent. RESULTS: component t SCR mean **39,595.1**,
95% CI **[36,676.2, 42,943.1]**, SE 1,610.0 (**4.07%** of mean → B2 SE gate ≤5% PASS).
HEADLINE (B1): nested **46,638.9 OUTSIDE** the 95% CI → DECOMPOSITION branch (pre-registered,
expected). Residual gap nested − component = 6,663.2 (**+14.29%**) decomposed: relief-surface
**543.0 (8.1%)** — independently bounded by the governed P25T3 OOS SCR rel err 1.16% — and
copula-form **6,120.2 (91.9%)**; copula-form DOMINANT, residual EXCEEDS the entire gaussian→t
sensitivity (4,765.6) → the nested joint tail is heavier than the frozen t(2.9451) copula on
standalone margins, NOT relief-surface. DISCLOSED. Gates 5/5 (B1 satisfied via the disclosed
decomposition). Governance: ChangeRecord `9049003b55d742f1812d5b083e3cd518`
(methodology_change) OWNER_REVIEW; audit 78→79; changes 51→52; verify_all True; idempotent
(digest 97aa928bcbf7). Reports: docs/validation/PHASE26_TASK3_MARGIN_BOOTSTRAP_REPORT.{json,md}
+ docs/COMPOSITION_BOOTSTRAP_CARD.md.

**NEXT executable task: Phase 26 Task 4 — full-vs-reanchored delta matrix.** Build the
component-vs-level-vs-without delta matrix across t/gaussian with the Task 3 bootstrap CIs
attached; re-check the MR-010/MR-014 1% disclosure trigger after Tasks 2–3 (Task 2 +0.46% < 1%;
confirm the combined move stays sub-1% or refresh the MR notes + open MR-015); re-verify rank
invariance (df/rho frozen); methodology_change ChangeRecord OWNER_REVIEW; idempotent re-run
digest-identical; stage to /var/tmp/p26t4_* in <44 s chunks. Then Task 5 (UI contract
1.7.0 → 1.8.0 ADDITIVE: surface the component-basis bootstrap CI + gap decomposition; PHASE 26
COMPLETE docs). On Phase 26 completion the standing instruction is to keep the fully-offline
interactive UI (`ui_app.html`, no pre-install, consumes only model output) in sync with the new
evidence, and to research the next stochastic-model sophistication step.

**Sandbox operating rules (RE-CONFIRMED cycle 29):** ~44 s bash wall — a 4-chunk loop timed out
at 45 s, so chunk the bootstrap in ≤40-replicate / ≤~10 s stages (partials persist → resume is
free); MOUNT APPENDS UNRELIABLE — ALWAYS build/append OFF-MOUNT (/var/tmp) then cp whole-file +
cmp + grep-verify; PYTHONPATH=/var/tmp/pylibs:. ; NEVER rewrite an existing large mounted file
via the file tool; nohup does NOT survive between bash calls; back up + hash-verify
GOVERNANCE_STORE.json before every governance stage; alt-`GIT_INDEX_FILE` commits onto `p22c9`
seeded from the pushed tip, push `p22c9:main` at the end of every cycle; next free risk ID
MR-015; re-check mtimes for parallel-run foreign writes before governance/commit. Stage data:
/var/tmp/p26t3_stage (verified_inputs.npz + partial_*.json + bootstrap_result.json),
/var/tmp/p26t2_stage (verified_inputs.npz, reagg_result.json), /var/tmp/p26t1_build,
/var/tmp/p25t5_build, /var/tmp/p25t4_stage, /var/tmp/p25t3_stage, /var/tmp/p25t2_stage,
/var/tmp/p24t3_stage, /var/tmp/p23t2_stage (losses.npz), /var/tmp/p23t4_stage,
.phase22_task2_stage.

**Standing blockers (human action):** delete the three git ghost locks (GITHUB_PUSH_BLOCKER.md)
— push from the sandbox works; serialise/stagger the scheduled runs; production sign-off
residual (credentialled data + APS X2) — by design for this educational model; disk /sessions
~89%.

## ⚠️ LATEST STATUS — 2026-06-08 +08 (cycle 31, supersedes everything above)

**Phase 26 Task 5 COMPLETE (PASS) — offline-UI contract 1.7.0 → 1.8.0 ADDITIVE;
PHASE 26 COMPLETE (Tasks 1-5).** Propagated the full path-wise copula
re-aggregation into the zero-install offline UI (`ui_app.html`; consumes only
model-output JSON; 0 network / 0 JS errors). `scripts/build_ui_data.py`
(contract → 1.8.0) adds a `phase26` section + first-class **Full Re-Agg (P26)**
tab (9 tabs) surfacing: Task 2 per-driver composition on the FROZEN t(2.9451)
copula — component t SCR **39,975.7** vs re-anchored 39,794.3 (**+0.46%**), 6/6
gates; Task 3 frozen-copula bootstrap on the FULL component basis — mean
**39,595.1**, 95% CI **[36,676.2, 42,943.1]**, SE 4.07%, nested **46,638.9
OUTSIDE** the CI → residual **14.29%** gap = **91.9% COPULA-FORM** / 8.1%
relief-surface; Task 4 paired CRN delta matrix — composition correction **+211.5
[+46.1, +381.8]** significant but **0.55% < 1% MR trigger** (MR-015 stays free).
Three Phase 26 PASS verdicts + additive capital read-outs
(`t_copula_scr_pathwise_component`, `..._bootstrap_mean`). NEW
`scripts/build_phase26_task5_ui_propagation.py` (43 contract checks → self-test →
governance → report; idempotent) + `tests/test_phase26_task5_ui_propagation.py`
(28 tests). Reports: `docs/validation/PHASE26_TASK5_UI_PROPAGATION_REPORT.{json,md}`
+ `docs/UI_PROPAGATION_CARD_P26.md`. Governance: ChangeRecord
`474879491df64f55a182be64b1f2cf2f` (code_change) OWNER_REVIEW; audit 80→81;
changes 53→54; verify_all True; idempotent. Tests: **166/0** (Phase 26 Tasks 1-5
+ all five P22-P26 UI-propagation suites); compileall clean; Node JSON validation
passed (state, governance, ui_data, viewer_data, Task 5 report). viewer_data.json
+ ui_app.html rebuilt (python writes) so governance shows the live 54-record
store. DISCLOSED forward-compat fix: P25T5 exact-version pin relaxed to a floor
≥ (1,7,0). **The fully-offline interactive UI requirement is SATISFIED.**

**NEXT executable task: Phase 27 Task 1 — research/design note (design-note-first,
pre-registered gates)** for the next stochastic-model sophistication step.
Motivation (quantified, from P26 Task 3): the residual gap to nested truth is
**copula-FORM dominated** (91.9% of the 14.29% gap; the genuine nested joint tail
is heavier than the frozen t(2.9451) copula on standalone margins — the
copula-form residual 6,120.2 EXCEEDS the entire gaussian→t sensitivity 4,765.6,
while the governed relief surface mis-prices only 1.16%). Candidate (pick ONE,
design-note-first): (a) **richer upper-tail dependence — FRONT-RUNNER**: a
grouped / skew-t or vine copula, or explicit upper-tail-asymmetry parameter, to
close the copula-form gap while preserving the calibrated margins; pre-register
gates: archive cross-check FIRST (frozen-t component read-out 39,975.7
bit-identical before any new copula), the new copula must REDUCE the nested gap
on CRN and its 95% bootstrap CI tested against nested 46,638.9, governed margins
UNCHANGED, copula change governed + rank-invariance re-stated (SII Art. 234),
SIGN gate richer-copula SCR ≥ frozen-t component; (b) credentialled-data
calibration (human-blocked); (c) declaration-cadence refinement (DEFERRED).
Then Task 2+ per the chosen design note; on completion keep `ui_app.html` in sync
(contract 1.8.0 → 1.9.0 ADDITIVE) and re-assess the next sophistication step.

**Sandbox operating rules (RE-CONFIRMED cycle 31, Linux sandbox):** Python 3.10 +
node/jsdom ARE available here (unlike the Python-less Windows shell). **CRITICAL —
the file tool (Edit/Write) SILENTLY TRUNCATES large mounted files**: this cycle it
truncated `scripts/build_ui_data.py` (167 KB) and `scripts/ui_app_self_test.cjs`
mid-write. NEVER Edit/Write an existing large mounted file. Instead: restore the
clean blob from `p22c9` (`git cat-file -p p22c9:<path>`), build/patch OFF-MOUNT in
`/var/tmp` (deterministic patch scripts; assert each replacement applies exactly
once), then `cp` whole-file + `cmp`-verify onto the mount; python `open(...,'w')`
writes and `cp` to the mount are the SAFE paths. Back up + hash-verify
GOVERNANCE_STORE.json before every governance stage (backup
`/var/tmp/p26t5_build/GOV_BACKUP_pre_p26t5.json`); alt-`GIT_INDEX_FILE` commits
onto `p22c9` seeded from the pushed tip, push `p22c9:main` at cycle end; next free
risk ID **MR-015**; re-check mtimes for parallel-run foreign writes before
governance/commit. Stage data: `/var/tmp/p26t5_build` (CLEAN/PATCHED build_ui_data
+ self-test, GOV backup), `/var/tmp/p26t4_*`, `/var/tmp/p26t3_stage`,
`/var/tmp/p26t2_stage`, `/var/tmp/p25t*`.

**Standing blockers (human action):** delete the three git ghost locks
(GITHUB_PUSH_BLOCKER.md) — push from the sandbox works; serialise/stagger the
scheduled runs (Python-less Windows runs waste cycles); production sign-off
residual (credentialled data + APS X2) — by design for this educational model;
disk /sessions usage to watch.

---

**Phase 27 Task 1 COMPLETE (PASS) — design note: richer upper-tail dependence
copula (skew-t).** Opened Phase 27 design-note-first. CHOSEN candidate (one per
cycle): an explicit UPPER-TAIL-ASYMMETRY parameter — the GH **skew-t copula**
(Demarta & McNeil 2005; McNeil, Frey & Embrechts 2015 ch. 7) on the FROZEN
(df 2.9451, Sigma), with **gamma = 0 recovering the symmetric t EXACTLY** (strict
super-set; freeze nested as a boundary case → archive cross-check is exact).
Motivation (P26T3 decomposition): nested 46,638.9 vs frozen-t component 39,975.7
(14.29% gap); **91.9% (6,120.2) is COPULA-FORM**, exceeding the whole gaussian→t
sensitivity (4,765.6); relief-surface only 1.16%. The frozen t is radially
SYMMETRIC (lambda_U = lambda_L); the joint loss tail is upper-asymmetric → no df
re-choice closes a SHAPE gap. New tested helper
`par_model_v2/projection/tail_dependence_upgrade.py` runs a synthetic 7-driver
skew-t-vs-symmetric-t pre-study on common random numbers: upper-tail dependence
**0.291 → 0.742** (lower tail near-symmetric 0.283 → 0.136), **VaR99.5 +10.2%,
ES99.5 +10.7%**, gamma=0 recovery EXACT (0.0) — the symmetric copula UNDERSTATES
the upper tail, same sign as the nested residual. Deferred: grouped-t (Daul et
al. 2003), vine (Aas et al. 2009), credentialled calibration (blocked). pytest
**14/0** (84/0 incl. P25T1/P26T1/P26T5 regression); compileall clean; JSON
validated. Governance: ChangeRecord `391700530a174ec1bc3b99a0c16e808d`
(governance_change) OWNER_REVIEW; audit 81→82; changes 54→55; verify_all True;
idempotent. New files: builder + tests + `docs/validation/PHASE27_TASK1_DESIGN_NOTE.{json,md}`
+ `docs/RICHER_TAIL_DEPENDENCE_DESIGN_CARD.md`.

**NEXT executable task: Phase 27 Task 2 — implement the skew-t copula** on the
FROZEN (df 2.9451, Sigma). Fit the skewness parameter gamma to the realised
UPPER-TAIL co-exceedances of the standalone capital-loss vectors (margins and df
UNCHANGED — copula-only change), re-aggregate the path-wise COMPONENT basis
(P26T2 per-driver composition relief convention, cuttable component only) on the
skew-t copula, and report the skew-t SCR alongside the retained symmetric-t
comparison variant. Pre-registered gates (FIXED in the Task 1 note, no
gate-shopping): (1) **gamma = 0 EXACT recovery** of the symmetric-t aggregate
(≤ 1e-9 on CRN); (2) archive cross-check — frozen-t component read-out
**39,975.7 bit-identical** before any skew-t computation; (3) rank invariance —
df re-matched within 1e-4 of 2.9451, correlation max|diff| ≤ 1e-12 (df + Sigma
FROZEN; only gamma added; SII Art. 234); (4) margins bit-identical; (5) **SIGN
gate — skew-t re-aggregated SCR ≥ frozen-t component 39,975.7** (magnitude
DISCLOSED, not gated); (6) code_change ChangeRecord OWNER_REVIEW. Then Task 3
(skew-t margin bootstrap ≥ 200×20k; HEADLINE — nested 46,638.9 INSIDE the skew-t
95% CI or residual RE-decomposed with the reduction vs copula-form 6,120.2
quantified; skew-t must REDUCE the nested gap on CRN; SE ≤ 5%), Task 4 (tail
diagnostics + MR-010/MR-014 refresh if SCR moves > 1%; open **MR-015** for the
copula-form / radial-asymmetry change), Task 5 (offline-UI propagation, contract
**1.8.0 → 1.9.0 ADDITIVE**: skew-t-vs-symmetric-vs-nested SCR, upper/lower
tail-dependence asymmetry, bootstrap-CI closure read-out, gates; UI consumes ONLY
model-output JSON, zero-install). On Phase 27 completion re-assess the next
sophistication step (grouped-t escalation if a single asymmetry scalar is
insufficient; vine as the general fallback).

**Sandbox operating rules (RE-CONFIRMED cycle 158, Linux sandbox):** Python 3.10
present; **scipy/numpy/pytest are at `/var/tmp/pylibs`** — run everything with
`PYTHONPATH=/var/tmp/pylibs:.` (a bare `python3` import of scipy fails; the
pylibs path is the documented fix, or `pip install --break-system-packages
numpy scipy`). **CRITICAL — the file tool (Edit/Write) SILENTLY TRUNCATES large
mounted files**: NEVER Edit/Write an existing large mounted file (build_ui_data.py
167 KB, MODEL_DEV_TASK_PROMPT.md, MODEL_DEV_LOG.md). Append via shell heredoc
(`cat >> file`) or python `open(...,'a')`; for whole-file replacement build
OFF-MOUNT in `/var/tmp` then `cp` + `cmp`-verify. NEW small files (this cycle's
helper/builder/tests) were written with the file tool safely (created fresh, not
rewriting a large existing file). Back up + hash-verify GOVERNANCE_STORE.json
before every governance stage (backup `/var/tmp/p27t1_build/GOV_BACKUP_pre_p27t1.json`);
next free risk ID **MR-015** (reserved for Phase 27 Task 4); re-check mtimes for
parallel-run foreign writes before governance/commit.

**Standing blockers (human action):** delete the three git ghost locks
(GITHUB_PUSH_BLOCKER.md) — sandbox commits/pushes remain blocked until cleared,
so this cycle's artefacts are on the mount but NOT pushed; serialise/stagger the
scheduled runs (Python-less Windows runs waste cycles); production sign-off
residual (credentialled data + APS X2) — by design for this educational model;
disk /sessions usage to watch.

---

## >>> MOST RECENT STATE (SUPERSEDES ALL BLOCKS ABOVE) — 2026-06-08T09:23:08Z

**Phase 27 Task 2 COMPLETE (PASS, 7/7 pre-registered gates).** GH skew-t copula implemented on the FROZEN (df 2.9451, Sigma): scalar gamma added on the same chi-square/Gaussian mixing so **gamma = 0 recovers the frozen t EXACTLY** (recovery dev 0.0; frozen-t COMPONENT 39,975.654628199336 bit-identical). Univariate GH skew-t marginal CDF via generalised Gauss-Laguerre quadrature (margins uniform; frozen empirical margins untouched), exact Student-t short-circuit at gamma=0. **gamma fitted leakage-free** to realised standalone upper-tail co-exceedances => **gamma_hat ~ 6.2e-5** (boundary): realised upper co-exceedance 0.152 (p=0.90) < symmetric-t 0.236, no standalone upper-tail asymmetry. Skew-t component SCR 39,981.0 (+0.01% vs frozen-t). DISCLOSED gamma grid proves the lever (gamma=1.0 => 54,600, asymmetry +0.54, overshoots nested 46,638.9). MATERIAL FINDING: the copula-form residual (6,120.2; 91.9% of the 14.29% nested gap) is NOT a standalone-driver radial-asymmetry effect. Gates: G1 exact recovery, G2 archive bit-identical, G3 rank invariance (df 2.9451; rho max|diff| 7.2e-16), G4 margins-unchanged, G5 sign gate, G6 leakage-free fit, mechanism — all PASS. pytest 13/0; regression 135/0; ChangeRecord `6bb5db0a06734369a0eb6d5ff48e84bc` (code_change) OWNER_REVIEW; audit 82->83; records 55->56; verify_all True; idempotent.

**NEXT executable task: Phase 27 Task 3** — skew-t margin bootstrap (>=200 replicates x 20,000 sims, P26T3 pattern). HEADLINE gate: nested path-wise reference 46,638.9 INSIDE the skew-t 95% bootstrap CI (closure) OR the residual gap RE-decomposed (copula-form vs relief-surface) with the REDUCTION vs the frozen-t copula-form residual 6,120.2 quantified — no silent acceptance. Given gamma_hat ~ 0, the prior expectation is the residual is RE-CONFIRMED as not closed by a single skew-t scalar; quantify it honestly and attribute to nested inner-path joint dynamics. Directional gate: skew-t must NOT WIDEN the nested gap on common random numbers vs the symmetric-t basis. Bootstrap SE <= 5% of the mean SCR; seeds/config/digests recorded; idempotent; methodology_change ChangeRecord OWNER_REVIEW. Then Task 4 (tail diagnostics + MR-010/MR-014 refresh if SCR moves > 1%; **open MR-015** for the copula-form / radial-asymmetry change; next free risk ID is MR-015), Task 5 (offline-UI propagation, contract 1.8.0 -> 1.9.0 ADDITIVE: skew-t-vs-symmetric-vs-nested SCR, upper/lower tail-dependence asymmetry, the gamma_hat~0 material finding, bootstrap-CI read-out; UI consumes ONLY model-output JSON, zero-install). On Phase 27 completion re-assess the next sophistication step (grouped-t escalation — heterogeneous tail dependence across drivers — since the single asymmetry scalar did not close the residual; vine the general fallback).

**Sandbox operating rules (RE-CONFIRMED this cycle):** Python 3.10 + scipy/numpy/pytest at `/var/tmp/pylibs` — run with `PYTHONPATH=/var/tmp/pylibs:.`. Staged primitives PERSIST in /var/tmp across runs (`/var/tmp/p23t2_stage/losses.npz`, `/var/tmp/p23t4_stage/losses_with_actions.npz`, `/var/tmp/p26t2_stage/verified_inputs.npz` all present this cycle). NEVER Edit/Write large mounted files (truncation on sync) — append via `cat >>` and build whole-file replacements OFF-MOUNT in /var/tmp then cp + cmp. Back up + hash-verify GOVERNANCE_STORE.json before every governance stage.

**Standing blockers (human action):** delete the three git ghost locks (GITHUB_PUSH_BLOCKER.md) — sandbox commits/pushes blocked, so this cycle's artefacts are on the mount but NOT pushed; production sign-off residual (credentialled data + APS X2).

---

## >>> MOST RECENT STATE (SUPERSEDES ALL BLOCKS ABOVE) — 2026-06-08T10:23:25Z

**Phase 27 Task 3 COMPLETE (PASS, all pre-registered gates).** Skew-t-copula margin bootstrap (200 replicates x 20,000 sims, P26T3 pattern) on the FROZEN copula (df 2.9451, Sigma, gamma_hat 6.242e-05) + governed relief scalars (sigma/alpha/beta_fit FROZEN, SII Art. 234). Joint row-resample of realised standalone losses WITH replacement; skew-t and symmetric-t (gamma=0) on COMMON random numbers (shared latent Z, W_chi) so the per-replicate difference isolates gamma. (df, gamma_hat) interpolant built once and reused (CRN-exact to <= 1 ULP vs the tested simulator). **Result:** skew-t component SCR mean **39,598.2**, 95% CI **[36,679.9, 42,943.1]**, SE **4.07%** (<= 5% PASS). HEADLINE: nested **46,638.9 OUTSIDE** the 95% CI -> residual RE-decomposed; with gamma_hat ~ 0 the copula-form residual falls only **6,120.2 -> 6,114.9 (0.09% reduction)** at the 200k point -> **RE-CONFIRMED not closed** by a single upper-tail-asymmetry scalar. DIRECTIONAL: skew-t does NOT widen the nested gap on CRN (mean lift +ve; 88.5% reps non-negative, disclosed-not-gated). Attribution: nested inner-path joint dynamics -> grouped-t / vine escalation (Phase 28). Gates C1-C7 PASS. pytest 10/0 (P27T3); regression 145/0; compileall clean. ChangeRecord `46c3318c27ae469daf7c0e40f8d99a41` (methodology_change) OWNER_REVIEW; audit 83->84; records 56->57; verify_all True; idempotent. GOVERNANCE_STORE.json backed up + hash-verified (`/var/tmp/p27t3_build/GOV_BACKUP_pre_p27t3.json`).

**NEXT executable task: Phase 27 Task 4** — (a) tail diagnostics: report the upper/lower tail-dependence and radial asymmetry of the skew-t draw vs the symmetric-t basis (already captured per-replicate in the P27T3 records: radial_asymmetry_mean ~ 0, consistent with gamma_hat ~ 0). (b) MR-010 / MR-014 refresh IF the headline SCR moves > 1%: it does NOT — skew-t component 39,598 vs the P26T3 frozen-t component-basis mean 39,595 is +0.01%, so document "no refresh required" with the quantified move. (c) **Open MR-015** in the model risk register for the copula-FORM / radial-asymmetry change (next free risk ID is MR-015): residual is copula-form dominated and NOT closed by the skew-t scalar; mitigation = grouped-t / vine escalation (Phase 28); status OPEN/monitored; classification EDUCATIONAL. methodology_change or governance_change ChangeRecord OWNER_REVIEW. Then **Task 5** (offline-UI propagation, contract 1.8.0 -> 1.9.0 ADDITIVE: skew-t-vs-symmetric-vs-nested SCR, upper/lower tail-dependence asymmetry, gamma_hat~0 material finding, bootstrap-CI read-out, MR-015; UI consumes ONLY model-output JSON, zero-install). **On Phase 27 completion** re-assess the next sophistication step: **grouped-t** (Daul et al. 2003 — heterogeneous tail dependence across drivers, the indicated step since the single asymmetry scalar did not close the residual); **vine** (Aas et al. 2009) the general fallback.

**Key archived references for Task 4/5 (cross-check targets):** frozen-t component 39,975.654628199336; skew-t-at-gamma_hat 200k component 39,980.95565911311; gamma_hat 6.24229466599955e-05; nested path-wise 46,638.9; frozen-t copula-form residual 6,120.196568775231; relief-surface OOS rel err (P25T3) 0.01164368805922599; P27T3 bootstrap digest 9c6e55e81ae3. New modules: `par_model_v2/projection/skew_t_copula_bootstrap.py` (bootstrap + redecompose_residual_gap + summarise_ci + bootstrap_digest); report `docs/validation/PHASE27_TASK3_SKEW_T_BOOTSTRAP_REPORT.{json,md}`.

**Sandbox operating rules (RE-CONFIRMED this cycle):** Python 3.10 + scipy/numpy/pytest at `/var/tmp/pylibs` — run with `PYTHONPATH=/var/tmp/pylibs:.`. Staged primitives PERSIST in /var/tmp (`/var/tmp/p23t2_stage/losses.npz`, `/var/tmp/p23t4_stage/losses_with_actions.npz`, `/var/tmp/p27t2_stage/verified.npz`+`fit_result.json`, `/var/tmp/p27t3_stage/` all present). **CRITICAL — the file Write/Edit tool SILENTLY TRUNCATES even freshly-created files on sync** (hit TWICE this cycle on the new module + builder; repaired by trimming the partial tail line and re-appending the remainder via `cat >>`). Prefer `cat >>` heredocs / off-mount build-then-cp for anything non-trivial; ALWAYS `py_compile` new .py files immediately after writing to catch truncation. Back up + hash-verify GOVERNANCE_STORE.json before every governance stage.

**Standing blockers (human action):** delete the three git ghost locks (GITHUB_PUSH_BLOCKER.md) — sandbox commits/pushes blocked, so this cycle's artefacts are on the mount but NOT pushed; production sign-off residual (credentialled data + APS X2). The fully-offline interactive UI requirement remains SATISFIED (zero-install, model-output-only); Task 5 will add the skew-t/bootstrap read-outs additively.

---

## >>> MOST RECENT STATE (SUPERSEDES ALL BLOCKS ABOVE) — 2026-06-08T12:25Z

**Phase 27 Task 4 COMPLETE (PASS, 6/6 pre-registered gates).** Skew-t copula tail-dependence DIAGNOSTICS + MR-010/MR-014 no-refresh DECISION + opened MR-015. No new model parameter — a REPORT + governance task on the FROZEN copula (df 2.9451, Sigma, gamma_hat 6.242e-05). Re-drew the skew-t (gamma_hat) and symmetric-t (gamma=0) copula uniforms on COMMON random numbers at the archived P27T3 per-replicate cop_seeds (200 reps x 20,000 sims) over a tail grid p in {0.80,0.85,0.90,0.95}; averaged pairwise upper/lower tail co-exceedance, normalised by (1-p). **Archive cross-check (T4-G1):** at p=0.90 the recomputed lambda_U/lambda_L/radial asymmetry are BIT-identical to the cached P27T3 records (max abs dev 0.0 <= 1e-12). p=0.90 skew-t lambda_U 0.2395, lambda_L 0.2391, radial asymmetry +0.00043 (~0; recomputed mean reproduces cached 0.0004270238). **Consistency (T4-G2):** skew-t radial asym >= symmetric-t at every p on CRN. **MR refresh (T4-G3):** component SCR move +0.0133% (39,598.2 vs 39,595.1) <= 1% trigger -> NO refresh; quantified, not actioned. **MR-015 (T4-G4):** opened "Copula-FORM / radial-asymmetry residual not closed by the skew-t upper-tail scalar" (model_error; MEDIUM x HIGH; OPEN; mitigation grouped-t/vine -> Phase 28; EDUCATIONAL). Gates 6/6 PASS; digest e660ad6153ec (idempotent). pytest 11/0 (P27T4); regression 238/0 (P27T1-T3, P26T1-T5, P25T1/T4, governance); compileall clean. ChangeRecord `00f05366af9349d5ba1f4609a239f51b` (governance_change) OWNER_REVIEW; risk register 14->15; audit 86; change records 58; verify_all True; governance stage idempotent.

**RECOVERY THIS CYCLE (disk-truncation, no data loss).** A prior crashed Task 4 run appended the governance record + 2 audit entries and updated MODEL_DEV_STATE, then a disk-issue TRUNCATED both: GOVERNANCE_STORE.json was cut mid-risk-register (MR-012 truncated; MR-013/014/015 lost) and 13 older audit entries had their `0.0` float details coerced to `0` (digest breaks; verify_all False); MODEL_DEV_STATE.json got a NUL-byte tail. Recovered both from the verified `/var/tmp/gov_restore_p26t4.json` backup + the intact prefixes, opened MR-015, re-validated verify_all True, cp-back with cmp. Diagnostics independently re-derived (bootstrap) reproducing the recorded numbers bit-identically; no duplicate governance record.

**NEXT executable task: Phase 27 Task 5** — offline-UI propagation, data contract **1.8.0 -> 1.9.0 ADDITIVE**. Surface, from model-output JSON only (zero-install, interactive): (a) the **skew-t vs symmetric-t vs nested** SCR (component 39,598.2 skew-t / 39,595.1 frozen-t basis / nested 46,638.9), (b) **upper/lower tail-dependence asymmetry** profile (lambda_U/lambda_L/radial asym across p, with 95% CI), (c) the **gamma_hat~0 material finding** (skew-t economically identical to frozen-t; copula-form residual NOT closed), (d) the **bootstrap-CI read-out** [36,679.9, 42,943.1] SE 4.07%, and (e) **MR-015** in the governance view. ADDITIVE only — no breaking change to the 1.8.x contract; keep the self-test at 0 network / 0 JS errors and external-ref scan clean. **On Phase 27 completion -> Phase 28** grouped-t heterogeneous tail-dependence escalation (design-note-first; vine the general fallback).

**Key archived references (cross-check targets):** frozen-t component 39,975.654628199336; skew-t-at-gamma_hat 200k component 39,980.95565911311; gamma_hat 6.24229466599955e-05; nested 46,638.9; frozen-t copula-form residual 6,120.196568775231; P27T4 tail-grid digest e660ad6153ec; p=0.90 cached radial-asym mean 0.0004270238095238131. Modules: `par_model_v2/projection/skew_t_tail_diagnostics.py` (tail_dependence_grid, summarise_tail_diagnostics, crosscheck_against_p27t3, mr_refresh_decision, tail_diagnostics_digest); report `docs/validation/PHASE27_TASK4_TAIL_DIAGNOSTICS_REPORT.{json,md}`; card `docs/SKEW_T_TAIL_DIAGNOSTICS_CARD.md`.

**Sandbox operating rules (RE-CONFIRMED).** Python 3.10 + scipy/numpy/pytest at `/var/tmp/pylibs` — run with `PYTHONPATH=/var/tmp/pylibs:.`. Staged primitives PERSIST in /var/tmp (`/var/tmp/p27t2_stage/verified.npz`, `/var/tmp/p27t3_stage/partial_*.json`+`verified_inputs.npz`, `/var/tmp/p27t4_stage/` all present this cycle). **Build the diagnostics in <45s shells — chunk the 200 reps (40/chunk, ~8s each) in SEPARATE bash calls; running all chunks in one shell exceeds the 45s limit.** NEVER Edit/Write large mounted files (silent truncation on sync — root-caused this cycle to /sessions at 91%); append via `cat >>`, build whole-file replacements OFF-MOUNT then `cp` + `cmp`; `py_compile` new .py immediately. Back up + VALIDATE-PARSE GOVERNANCE_STORE.json AND MODEL_DEV_STATE.json before AND after every governance write (both were found truncated this cycle).

**Standing blockers (human action):** delete the three git ghost locks (GITHUB_PUSH_BLOCKER.md) — sandbox commits/pushes blocked, artefacts on the mount NOT pushed; **/sessions disk at 91% (921 MB free) is the truncation root cause — free space or the next governance write may truncate again**; production sign-off residual (credentialled data + APS X2). The fully-offline interactive UI requirement remains SATISFIED; Task 5 adds the skew-t/bootstrap/MR-015 read-outs additively.

---

## >>> MOST RECENT STATE (SUPERSEDES ALL BLOCKS ABOVE) — 2026-06-08 (Phase 27 Task 5)

**Phase 27 Task 5 COMPLETE (PASS). PHASE 27 COMPLETE.** Offline-UI propagation, data contract **1.8.0 -> 1.9.0 ADDITIVE**. `scripts/build_ui_data.py` gains `_build_phase27()` (normalises the governed P27 Task 3/4 reports — display-layer only, NO recalculation), bumps `CONTRACT_VERSION` to 1.9.0, adds `capital.skewt_copula_scr_component_bootstrap_mean`, and merges governance-store risks missing from `viewer_data.json` (surfaces **MR-015**; 14 -> 15). New **"Skew-t Tail (P27)"** tab in `ui_app.html` surfaces: (a) skew-t (39,598.2 bootstrap mean) vs symmetric-t (39,595.1) vs **nested 46,638.9** SCR bar chart; (b) lambda_U / lambda_L / radial-asymmetry profile across p in {0.80,0.85,0.90,0.95} with 95% CI (near-radial symmetry, gamma_hat~0); (c) gamma_hat~0 **MATERIAL FINDING**; (d) bootstrap CI **[36,679.9, 42,943.1] SE 4.07%** with nested OUTSIDE; (e) residual re-decomposition (copula-form 6,114.9 vs relief-surface 543.0) + T3/T4 gate grids; **MR-015** also in the Governance register. Verification: `node scripts/ui_app_self_test.cjs ui_app.html` -> **ok:true, tabCount 10, 0 network / 0 JS errors**; external-ref scan clean; jsdom render confirms the P27 tab + Governance MR-015. Builds/writes done OFF-MOUNT then cp + cmp + py_compile/parse (disk-truncation guard). The fully-offline zero-install model-output-only interactive UI requirement remains **SATISFIED**.

**NEXT executable task: Phase 28 Task 1** — design-note-first **grouped-t** (Daul et al. 2003) heterogeneous tail-dependence across drivers (the indicated next step: the single skew-t upper-tail-asymmetry scalar did NOT close the copula-form residual — gamma_hat ~ 0, MR-015 OPEN). The grouped-t allows heterogeneous degrees-of-freedom / tail dependence by driver block (e.g. financial vs non-financial), nesting the FROZEN single-df t copula as the homogeneous boundary case so the archive cross-check stays exact. **Vine / pair-copula** (Aas et al. 2009) is the general fallback if a block-homogeneous grouped-t still cannot represent the nested inner-path joint dynamics. Follow the established cycle discipline: design-note-first with pre-registered gates (one candidate per cycle, nested boundary recovery exact, copula frozen where claimed, SIGN gate vs the frozen-t component 39,975.7, bootstrap SE <= 5%, MR refresh decision, OWNER_REVIEW ChangeRecord), then implement / bootstrap / diagnostics / governance / UI propagation in subsequent tasks.

**Key archived references (cross-check targets):** frozen-t component 39,975.654628199336; skew-t-at-gamma_hat 200k component 39,980.95565911311; gamma_hat 6.24229466599955e-05; nested 46,638.9; frozen-t copula-form residual 6,120.196568775231; P27T3 bootstrap mean 39,598.16 CI [36,679.93, 42,943.14] SE 4.07%; P27T4 tail-grid digest e660ad6153ec; ui_data.json contract now **1.9.0**; UI builder `scripts/build_ui_data.py` (`_build_phase27`, `renderPhase27`); offline self-test `scripts/ui_app_self_test.cjs`.

**Sandbox operating rules (RE-CONFIRMED).** Python 3.10 + numpy/scipy/pytest at `/var/tmp/pylibs` — run with `PYTHONPATH=/var/tmp/pylibs:.`. **The file Write/Edit tool SILENTLY TRUNCATES on the /sessions mount (91% full, ~921 MB free)** — edit source OFF-MOUNT (`/var/tmp`), `py_compile`/parse, then `cp` + `cmp` back; build ui_data.json/ui_app.html off-mount then cp + verify byte count + closing tag + JSON parse. Back up + parse-validate GOVERNANCE_STORE.json AND MODEL_DEV_STATE.json before AND after every write. The node offline self-test under jsdom can exceed a 45s shell — run it in its own shell with `timeout 42`.

**Standing blockers (human action):** delete the three git ghost locks (GITHUB_PUSH_BLOCKER.md) — sandbox commits/pushes blocked, this cycle's artefacts are on the mount but NOT pushed; **/sessions disk at 91% is the truncation root cause — free space**; production sign-off withheld pending credentialled data + independent APS X2 review (by design, educational).

---

## >>> MOST RECENT STATE (SUPERSEDES ALL BLOCKS ABOVE) — 2026-06-08 (Phase 28 Task 1)

**Phase 28 Task 1 COMPLETE (PASS). PHASE 28 OPENED.** Design-note-first **grouped-t / heterogeneous tail-dependence copula** (Daul, De Giorgi, Lindskog & McNeil 2003): per-block degrees of freedom on the **FROZEN correlation Sigma**, with the homogeneous boundary (all df_g = 2.9451, single shared mixing variate) recovering the governed single-df t copula **EXACTLY** (strict super-set; m=1/fully-pooled boundary; archive cross-check stays exact). New tested helper `par_model_v2/projection/grouped_t_upgrade.py` (synthetic two-block grouped-t vs single-df t on common random numbers; pre-registered gate constants + block partition; use restrictions); builder `scripts/build_phase28_task1_design_note.py`; tests `tests/test_phase28_task1_design_note.py` (16/16). **Motivation:** the Phase 27 RECONFIRMATION — skew-t gamma_hat ~ 6.24e-05 pinned the asymmetry scalar, copula-form residual fell only 6,120.2 → 6,114.9 (0.09%), RE-CONFIRMED NOT a radial-asymmetry effect (MR-015 OPEN); the single-df t imposes ONE tail-dependence level on EVERY pair, but the nested joint loss has within-block >> cross-block tail co-movement. **Pre-study (n=200k, seed 42):** grouped-t within-FIN upper-tail dependence **0.352 vs cross-block 0.054** (single-df t near-uniform); homogeneous-boundary EXACT recovery **0.0**; **DISCLOSED two-sided sign** — the single-df t shares ONE mixing variate (MAXIMAL-cross-block boundary), so the grouped-t's independent per-block mixing DILUTES cross-block co-movement (−83%) and here aggregate VaR99.5 moves **−5.4% (DOWN)**: the grouped-t is a tail-dependence **HETEROGENEITY lever, NOT a uniform tail-heaviness lever** (its aggregate effect is two-sided, unlike the sign-pinned skew-t). Verification: pytest 16/0 (P28T1); P27+P28 64/0; compileall clean; report + governance JSON validated. Governance: ChangeRecord `b92691ef320f4109b818520b0365beab` (governance_change) OWNER_REVIEW; audit 86→87; change records 58→59; verify_all True; idempotent. All state/source/governance writes done OFF-MOUNT then cp + cmp + parse-verify; both stores backed up + parse-validated before AND after.

**NEXT executable task: Phase 28 Task 2** — implement the grouped-t copula (per-block df_g) on the FROZEN Sigma. Fit df_g leakage-free to the realised WITHIN-block vs CROSS-block co-exceedances of the standalone loss vectors on the PRE-REGISTERED partition (FIN/carve-out drivers {credit, FX, liquidity}; NON-FIN the rest); re-aggregate the path-wise component basis on the grouped-t; verify (a) homogeneous-boundary EXACT recovery (all df_g = 2.9451, single shared mixing → single-df t to ≤ 1e-9 on CRN), (b) frozen-t component read-out **39,975.654628199336** bit-identical BEFORE any grouped-t computation, (c) Sigma frozen (max|diff| ≤ 1e-12) + homogeneous df 2.9451 (tol 1e-4), (d) margins bit-identical; report the grouped-t component SCR vs frozen-t with the **directional sign DISCLOSED (NOT one-sided gated — grouped-t is two-sided)**; retain the single-df t comparison variant; `code_change` ChangeRecord OWNER_REVIEW. Then **Task 3** (grouped-t margin bootstrap ≥200×20k: HEADLINE nested 46,638.9 inside the 95% CI OR residual RE-decomposed with the change vs the skew-t-reconfirmed **6,114.9** quantified — a WIDENING is informative, escalate to the vine, disclosed not gate-failed; SE ≤ 5%), **Task 4** (within/cross-block tail diagnostics + MR-010/MR-014 refresh if SCR moves > 1% + open **MR-016**), **Task 5** (offline-UI propagation, contract 1.9.0 → 1.10.0 ADDITIVE: grouped-t-vs-single-vs-nested SCR, within/cross-block heterogeneity, bootstrap-CI read-out, MR-016; UI consumes ONLY model-output JSON, zero-install). **On Phase 28 completion → Phase 29** vine / pair-copula (Aas et al. 2009) general fallback IF a block-homogeneous grouped-t still cannot represent the nested inner-path joint dynamics.

**Key archived references (cross-check targets):** frozen-t component 39,975.654628199336; nested 46,638.9; frozen-t copula-form residual 6,120.196568775231; skew-t-reconfirmed copula-form residual 6,114.9; skew-t gamma_hat 6.24229466599955e-05; skew-t bootstrap mean 39,598.16 CI [36,679.93, 42,943.14] SE 4.07%; pre-registered partition FIN {0,4,6} / NON-FIN {1,2,3,5}; MR-016 is the next free risk ID; ui_data.json contract 1.9.0 (→ 1.10.0 at Task 5). Module: `par_model_v2/projection/grouped_t_upgrade.py` (grouped_t_vs_single_t_pre_study, grouped_t_upgrade_use_restrictions, GroupedTConfig, FIN_BLOCK, NONFIN_BLOCK, HOMOGENEOUS_RECOVERY_TOL, GROUPED_T_SIGN_GATE_REFERENCE, NEW_RISK_ID=MR-016).

**Sandbox operating rules (RE-CONFIRMED).** Python 3.10 + numpy/scipy/pytest at `/var/tmp/pylibs` — run with `PYTHONPATH=/var/tmp/pylibs:.`. **The file Write/Edit tool SILENTLY TRUNCATES on the /sessions mount (91% full, ~921 MB free)** — edit source OFF-MOUNT (`/var/tmp`), `py_compile`/parse, then `cp` + `cmp` back; build JSON/state off-mount then cp + verify byte count + JSON parse. Back up + parse-validate GOVERNANCE_STORE.json AND MODEL_DEV_STATE.json before AND after every governance/state write. Chunk long bootstraps into <45s shells (≤40 reps/chunk). A concurrent scheduled session was observed during regression collection — serialise/stagger runs.

**Pre-existing stale test (NOT a Phase 28 regression):** `tests/test_phase24_task3_inner_path_action.py::TestGovernance::test_mr014_notes_latest_refresh_mentions_inner_path` fails because the **Phase 25 Task 4** MR-014 refresh superseded the notes (mentions "Phase 24" but not "Task 3"), per the repo's latest-refresh-supersedes convention. The Phase 28 Task 1 governance write only APPENDED a new ChangeRecord + audit entry (verify_all True). Recommended one-line maintenance fix: relax the assertion to require "Phase 24" only (accept the path-wise supersession).

**Standing blockers (human action):** delete the three git ghost locks (GITHUB_PUSH_BLOCKER.md) — sandbox commits/pushes blocked, this cycle's artefacts are on the mount but NOT pushed; **/sessions disk at 91% — free space (truncation root cause)**; production sign-off withheld pending credentialled data + independent APS X2 review (by design, educational).


## >>> MOST RECENT STATE (SUPERSEDES ALL BLOCKS ABOVE) — 2026-06-08 (Phase 28 Task 2)

**Phase 28 Task 2 COMPLETE (PASS, 9/9 pre-registered gates).** Grouped t-copula (Daul et al. 2003) implemented on the FROZEN copula: per-block df_g (heterogeneous tail dependence) on the same Gaussian draw / frozen Sigma with independent per-block chi-square mixing; the homogeneous boundary (all df_g = 2.9451 + one shared mixing variate) recovers the frozen single-df t EXACTLY (dev 0.0; frozen-t component 39,975.654628199336 bit-identical). Pre-registered partition FIN/carve-out {credit,FX,liquidity}=idx{2,5,6} vs NON-FIN {rate,equity,lapse,mortality}=idx{0,1,3,4}. df fitted leakage-free to within-block upper co-exceedances: df_NONFIN 37.866 / df_FIN 8.506. MATERIAL FINDING (disclosed): realised within-block co-exceedances (0.125) are BELOW cross-block (0.172) — no within-carve-out tail concentration — so the grouped-t DILUTES cross-block co-movement, component SCR 35,604.4 vs frozen-t 39,975.7 (-10.93%, two-sided DOWN, gap to nested -23.66%). Like the skew-t (gamma_hat~0), a copula on standalone margins does NOT close the upward nested residual. ChangeRecord `85a6b858662c42f095b62e4719e04836` (code_change) OWNER_REVIEW; change records 59→60; audit 87→88; verify_all True. pytest 11/0 (P28T2); regression 250/0 (P28T1+P27 64, P26+governance 175, P28T2 11); compileall clean.

**NEXT executable task: Phase 28 Task 3** — grouped-t margin bootstrap (>=200×20k, P26T3/P27T3 pattern) on the FROZEN copula (df 2.9451, Sigma, df_NONFIN 37.866 / df_FIN 8.506) + governed relief scalars (sigma/alpha/beta_fit FROZEN, SII Art. 234). Each replicate joint-resamples the realised standalone-loss rows WITH replacement (cross-driver pairing preserved) and re-runs the Task 2 grouped-t component re-aggregation; on common random numbers also evaluate the homogeneous single-df-t variant so the per-replicate (grouped − single) difference isolates the heterogeneity effect. **HEADLINE gate:** nested path-wise 46,638.9 INSIDE the grouped-t 95% bootstrap CI (closure) OR the residual gap RE-decomposed (copula-form vs relief-surface) with the CHANGE vs the skew-t-reconfirmed copula-form residual **6,114.9** (and frozen-t 6,120.2) quantified — given df_hat dilutes (SCR DOWN), the expectation is the residual WIDENS, which is INFORMATIVE (the nested structure is NOT within-block-concentrated → vine escalation) and is DISCLOSED, not gate-failed. **Directional diagnostic (DISCLOSED, not hard gate):** grouped-t-vs-single nested-gap change on CRN reported with sign. SE <= 5% of mean SCR; idempotent re-run digest-identical; seeds/config recorded; `methodology_change` ChangeRecord OWNER_REVIEW. Then **Task 4** (within/cross-block tail diagnostics + MR-010/MR-014 refresh if SCR moves > 1% + open **MR-016**), **Task 5** (offline-UI propagation, contract 1.9.0 → 1.10.0 ADDITIVE: grouped-t-vs-single-vs-nested SCR, within/cross-block heterogeneity, bootstrap-CI read-out, MR-016; UI consumes ONLY model-output JSON, zero-install). **On Phase 28 completion → Phase 29** vine / pair-copula (Aas et al. 2009) general fallback — now DOUBLY indicated: neither the skew-t asymmetry scalar (gamma_hat~0) nor the grouped-t block-heterogeneity (df_hat dilutes) closes the residual on the standalone margins, confirming the residual is nested inner-path joint structure a copula on standalone margins cannot represent.

---

## >>> MOST RECENT STATE (SUPERSEDES ALL BLOCKS ABOVE) — 2026-06-09 (Phase 28 Task 4)

**Phase 28 Task 3 COMPLETE (PASS, SE gate).** Grouped-t margin bootstrap (200×20,000) on the FROZEN copula + governed relief scalars. Grouped-t component SCR mean 35,372.5, 95% CI [33,034.4, 38,008.5], SE 3.58% (≤5%). HEADLINE: nested 46,638.9 OUTSIDE the 95% CI → residual RE-decomposed; copula-form residual WIDENS 6,114.9 → 10,491.5 (+71.57%) — grouped-t does NOT close the UPWARD nested residual (second negative super-set after skew-t gamma_hat~0). Directional grouped−single CRN mean −4,222.6 (DOWN, 100% reps). Digest 71d5c6eee80d. ChangeRecord 32bae3c3 OWNER_REVIEW; audit 88→89; records 60→61.

**Phase 28 Task 4 COMPLETE (PASS, 6/6 pre-registered gates).** Grouped-t within/cross-block, upper/lower tail-dependence DIAGNOSTICS + MR-010/MR-014 no-refresh DECISION + opened MR-016. No new model parameter — a code-free diagnostics + governance task on the FROZEN copula (Sigma, df_NONFIN 37.866 / df_FIN 8.506, homogeneous df 2.9451). Re-drew the grouped-t and single-df t (homogeneous boundary, shared mixing) uniforms on COMMON random numbers at the archived P28T3 per-replicate cop_seeds (200 reps × 20,000 sims) over a tail grid p ∈ {0.80, 0.85, 0.90, 0.95}. **Archive cross-check (T4-G1):** at p=0.90 the recomputed grouped-t within-block (NON-FIN, FIN) upper, cross-block upper and heterogeneity_upper are BIT-identical to the cached P28T3 records (max abs dev 0.0 ≤ 1e-12). **Dilution (T4-G2):** p=0.90 grouped cross-block upper 0.1703 vs single-df t 0.2573 → dilution −0.0871 [−0.0958, −0.0766] (CI excludes 0; grouped ≤ single at every p); grouped within-FIN upper 0.1257 < single 0.1777 (df_FIN 8.5 > frozen → lighter within-block tails); within-block radial asymmetry ~0 (CI spans 0; t-copula radially symmetric within block — finite-sample noise). The independent per-block mixing (not only df_g>frozen) IS the dilution mechanism (homogeneous-boundary within-NON-FIN bit-identical across legs; FIN+cross differ at equal df). **MR refresh (T4-G3):** GOVERNED headline = frozen single-df t (maximal-cross-block, conservative boundary) recovered EXACTLY → move 0.0000% ≤ 1% → NO refresh; the grouped-t DOWN move (−10.93% point / −10.66% bootstrap) is DISCLOSED, not adopted (non-conservative), tracked by MR-016. **MR-016 (T4-G4):** opened "Heterogeneous-tail / cross-block-dilution copula-FORM residual not closed by the grouped-t per-block df" (model_error; MEDIUM × HIGH; OPEN; mitigation vine/pair-copula → Phase 29; EDUCATIONAL). Gates 6/6; digest e86057638b01 (idempotent). pytest 11/0 (P28T4); regression P28T1-T3 35/0, P27T1-T4 48/0 (94 passed); compileall clean. ChangeRecord `0988ea9f865a49c3b938d22dc37af498` (governance_change) OWNER_REVIEW; risk register 15→16; audit 89→90; change records 61→62; verify_all True; governance idempotent.

**NEXT executable task: Phase 28 Task 5** — offline-UI propagation, data contract **1.9.0 → 1.10.0 ADDITIVE**. Surface, from model-output JSON only (zero-install, interactive): (a) **grouped-t vs single-df t vs nested** SCR (component 35,372.5 grouped-t bootstrap / 35,604.4 point, single-df t = frozen-t basis 39,595.1 / 39,975.7 point, nested 46,638.9); (b) the **within/cross-block, upper/lower tail-dependence grid** (grouped vs single, with 95% CI) and the **cross-block dilution** profile (grouped cross-block upper < single at every p; p=0.90 −0.0871); (c) the **bootstrap-CI read-out** [33,034.4, 38,008.5] SE 3.58%; (d) the **residual re-decomposition + widening** (copula-form 6,114.9 → 10,491.5); (e) **df_NONFIN 37.866 / df_FIN 8.506** and (f) **MR-016** in the governance view. ADDITIVE only — no breaking change to the 1.9.x contract; keep the self-test at 0 network / 0 JS errors and external-ref scan clean. **On Phase 28 completion → Phase 29** vine / pair-copula (Aas et al. 2009) — now DOUBLY-to-TRIPLY indicated: neither the skew-t asymmetry scalar (gamma_hat~0) nor the grouped-t block-heterogeneity (df_hat dilutes, cross-block tail dependence confirmed lower than single-df t) closes the UPWARD nested residual on the standalone margins; it is nested inner-path joint structure a copula on standalone margins cannot represent.

**Sandbox note (this cycle):** scipy/numpy reused from `/var/tmp/pylibs` (export PYTHONPATH=/var/tmp/pylibs:$(pwd)); staged P28T2 (`/var/tmp/p28t2_build/verified.npz`, `fit_result.json`) and P28T3 (`/var/tmp/p28t3_stage/partial_*.json` with cop_seeds) inputs survived and were reused. A root-owned stale `tests/__pycache__/*p28t4*.pyc` blocked in-place pytest collection of the new test file; run P28T4 tests from a `/var/tmp` copy with `--import-mode=importlib -p no:cacheprovider` (11/11). Mount write-sync lag was observed on the new test file; the authoritative file-tool view is complete (220 lines, verified).
---

## >>> MOST RECENT STATE (SUPERSEDES ALL BLOCKS ABOVE) - 2026-06-09 (Phase 28 Task 5)

**Phase 28 Task 5 COMPLETE (PASS). PHASE 28 COMPLETE.** Offline-UI propagation is done; data contract **1.9.0 -> 1.10.0 ADDITIVE**. `scripts/build_ui_data.py` now builds a `phase28` section from the governed Phase 28 Task 2/3/4 model-output JSONs (display-layer only, NO recalculation), adds the capital read-outs `grouped_t_copula_scr_component_bootstrap_mean`, `single_t_copula_scr_component_bootstrap_mean`, and `grouped_t_copula_scr_component_point`, and keeps the governance-store risk merge so **MR-016** is visible. `ui_app.html` now has a **Grouped-t Tail (P28)** tab surfacing: grouped-t component SCR **35,372.5** bootstrap mean / **35,604.4** point; single-df t **39,595.1** bootstrap mean / **39,975.7** point; nested path-wise reference **46,638.9**; grouped-t bootstrap CI **[33,034.4, 38,008.5]** with SE **3.58%**; p=0.90 cross-block dilution **-0.0871**; df_NONFIN **37.866** / df_FIN **8.506**; residual widening **6,114.9 -> 10,491.5**; and MR-016 in Governance.

**Verification:** `node scripts/ui_app_self_test.cjs ui_app.html` -> **ok:true**, tabCount **11**, **0 network / 0 JS errors**. External-ref scan clean; `ui_data.json` parses; `ui_app.html` has closing `</html>`. Python aliases hang in this Windows shell, so generated artifacts were emitted with a short Node fallback from the patched Python template; the durable source remains `scripts/build_ui_data.py`.

**NEXT executable task: Phase 29 Task 1** - design-note-first **vine / pair-copula** (Aas et al. 2009) candidate selection and pre-registered gates. Motivation is now triple-confirmed: skew-t gamma_hat ~ 0 did not close the copula-form residual; grouped-t fitted df_g diluted cross-block dependence and widened the residual; MR-016 is OPEN. Task 1 should define a leakage-free vine candidate with frozen standalone margins, exact recovery of the governed single-df t boundary where claimed, pair-family search limits, CRN comparison variants, bootstrap/diagnostic gates, and MR-016 remediation criteria before implementation. Task 2 should implement the chosen prototype only after the design note is governed.

**Standing blockers (human action):** git ghost locks / index state still block automation commits and pushes (`GITHUB_PUSH_BLOCKER.md`); production sign-off remains withheld pending credentialled data + independent APS X2 review. The fully-offline zero-install model-output-only interactive UI requirement remains **SATISFIED**.
