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

**Phase 14: Production Residual Closure and Model Sophistication** ⭐ NEXT  
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
3. Remediate MR-009 — migrate `examples/guided_examples.py` to the current
   RiskFreeCurve/FixedIncomeInstrument/TVOG APIs; bring `tests/test_guided_examples.py` green.
4. Re-run G-06 IA TAS M §3.6 suite re-scoring VR-B01/B02/B03/S05 against the
   Phase 13 Task 5 out-of-sample backtest evidence; target ≥ 90% PASS.
5. ESG sophistication: add an optional stochastic-volatility (Heston) or
   jump-diffusion equity process behind a feature flag, with Q-measure martingale
   tests (Phase 8 upgrade path). (SOA ESG standards; IA TAS M §3.6)
6. Nested-stochastic / LSMC TVOG proxy for capital metrics, with convergence and
   reproducibility diagnostics; document model-use restrictions.

**Current milestone:** Phase 14 in progress | 76/80 tasks done | Phase 14 Task 2 COMPLETE (G-03 cleared educational; MR-002 → MITIGATED; GBM equity calibrated to educational-proxy CNY/HK daily history — CNY σ_S=0.216/ERP=3.27%/ρ=-0.197, HK σ_S=0.252/ERP=1.71%/ρ=-0.149; APPROVED ChangeRecord + 2 PARAM_CHANGE entries; 18 new tests PASS). **All 12 educational deployment gates now cleared.** Also fixed a prior-cycle defect that made GOVERNANCE_STORE.json unloadable (added SignOffStatus.IMPLEMENTED + RiskRating.VERY_LOW/VERY_HIGH) and made two Phase 13 Task 6 tests state-tolerant. Production residuals remaining: credentialled live market-data feeds (G-02/G-03/G-09 proxies), MR-009 (guided_examples API migration), and a genuine human APS X2 reviewer. Next: Phase 14 Task 3 (MR-009 — migrate examples/guided_examples.py).

---

## Key Points for Sustained Autonomous Operation

✅ **State file is the contract:** Always read from `.claude-dev/MODEL_DEV_STATE.json` first  
✅ **Incremental work:** One task per cycle, thoroughly documented  
✅ **Human oversight:** Email drafts keep you informed  
✅ **Self-documenting:** Commit messages + MODEL_DEV_LOG.md = audit trail  
✅ **Resumable:** If manual intervention needed, edit state file and next cycle continues  
✅ **Industry-focused:** Each task includes SOA/IA alignment notes  

---

## Final Setup Checklist

Before enabling this task:

- [ ] `.claude-dev/MODEL_DEV_STATE.json` created with your repo URL
- [ ] Repository URL verified (https://github.com/wilson37wu/AI_Actuarial_2026_ver_Codex)
- [ ] Email address updated in this prompt
- [ ] Git credentials configured (name, email, token/SSH)
- [ ] Task frequency set to cron: `0 */12 * * *` (every 12 hours)
- [ ] Autonomous mode enabled in Claude Code
- [ ] Gmail connector enabled in Claude Code
- [ ] Test run executed — verify state file updated, commit created, draft sent
- [ ] MODEL_DEV_LOG.md created in repo root
- [ ] This prompt saved to `.claude-dev/model-dev-task.md`

---

**Ready to automate. Let Claude build your model, 12 hours at a time.**
