# Post-Phase-IGUI Task 1 - Design Note: Credentialled-Data Calibration-Residual Diagnostics (frozen margins)

**Verdict: PASS** - pure governance (governance_change); NO parameter change; implementation DEFERRED. Classification: EDUCATIONAL.

## 1. Candidate (pre-registered, exactly one)

- **MR-CAL-1** - Credentialled-data calibration-residual diagnostics on the frozen margins
- Touches copula structure: **False** (Phase 30 stop-rule compliant)
- No model parameter change: **True**; implementation deferred: **True**

## 2. Context

Phase 30 applied the BINDING STOP-RULE: dependence-FORM escalation under MR-016 ENDS; MR-016/MR-017 stay OPEN owner decisions; candidates are DISCLOSED, not adopted. The standing roadmap names the credentialled-data calibration priority as the live next priority. The seven standalone risk-driver margins are FROZEN, but the calibration residual of those frozen margins against a credentialled reference has never been quantified. Diagnostics-first (exactly as the dependence work was diagnostics-first): MEASURE the calibration residual before any recalibration could ever be contemplated.

Frozen cross-check references:

- Governed frozen-t component SCR: **39,975.654628**
- Nested path-wise reference: 46,638.9
- Copula-FORM residual ladder (abs):

  - grouped_t: 10,491.5
  - frozen_t: 6,120.2
  - skew_t: 6,114.9
  - vine2: 3,637.3

- Seven frozen standalone risk-driver margins: rate, equity, credit, lapse, mortality, fx, liquidity

## 3. Scope deferred to next cycle (implementation)

- Diagnostics-only module computing each frozen driver margin's calibration residual against a credentialled reference (credibility framing: the credentialled dataset is the reference, the model margin is the prior).
- Distributional GoF on the frozen margins: PIT/Rosenblatt uniformity, QQ, KS, Anderson-Darling with bootstrap CIs; SCR-relevant tail quantiles.
- Residual decomposition separating margin-calibration residual from the already-quantified copula-FORM residual, reconciled to the gap vs nested.
- A DISCLOSED report + optional ADDITIVE offline-UI surface; frozen margins stay bit-identical (NOT a recalibration).

## 4. Pre-registered acceptance gates (frozen now)

- **G1 Frozen-margin + headline invariance** - Every frozen marginal calibration parameter AND the governed frozen-t component SCR 39,975.654628199336 recovered BIT-IDENTICAL (dev <= 1e-09) BEFORE and AFTER the diagnostics run. Diagnostics must not perturb any margin or output.
- **G2 Credentialled-reference provenance** - The credentialled reference dataset is documented (source, vintage, n, credential/licence basis) and version-pinned. If no external credentialled dataset is available in-sandbox, a clearly-labelled SYNTHETIC credentialled-reference stub with the same interface is used and the report is marked EDUCATIONAL/illustrative (GBM ESG-stub precedent).
- **G3 Leakage-free goodness-of-fit** - PIT/Rosenblatt uniformity, QQ, KS and Anderson-Darling on a documented fit/holdout split; GoF statistics computed on holdout, >= 200 bootstrap replicates, SE <= 5% of the mean, SCR-relevant tail quantiles reported with CIs.
- **G4 Residual decomposition reconciliation** - calibration-residual + copula-FORM residual reconcile to the total gap vs nested 46,638.9 within a pre-stated tolerance; decomposition DISCLOSED; the governed headline does NOT move.
- **G5 Credibility quantification - report not apply** - Partial-credibility Z (Buhlmann-Straub / limited-fluctuation) and the credibility-weighted indicated margin shift are REPORTED as an information item but NOT applied. Any indicated |dSCR| > 1% of the governed headline OPENS a new model-risk entry (OPEN) rather than triggering recalibration.
- **G6 Governance + offline-UI discipline** - Idempotent run digest; governance_change / methodology_change ChangeRecord left OWNER_REVIEW; unit tests added; if an offline-UI surface is added it is an ADDITIVE contract bump only, self-tests ok:true 0 network / 0 JS errors, 0 external refs, every pre-existing key bit-identical.

## 5. Candidate sequencing (pool of three)

- Selected NOW: **MR-CAL-1** (credentialled-data calibration diagnostics)
- Next candidate: **MR-VR-1** (inner-path antithetic/CRN variance reduction for TVOG)
- Deferred candidate: **MR-LONGEV-1** (mortality-trend / longevity 5th driver - parameter-adding, owner sign-off)
- Rationale: (b) credentialled-data calibration is the live roadmap priority after the dependence stop-rule, is diagnostics-only (cleanest stop-rule compliance, no parameter change). (c) inner-path antithetic/CRN variance reduction is the recorded NEXT candidate. (a) longevity 5th-driver is a parameter-adding model-FORM change deferred to a dedicated owner-sign-off cycle.

## 6. Stop-rule compliance

No copula structure and no model parameter touched; MR-016/MR-017 untouched; governed headline frozen. Admissible under the Phase 30 binding stop-rule (bars new copula-structure candidates only).

## 7. Validation gate

- ok: **True** (14 checks)
- candidate_id: True
- no_param_change: True
- stop_rule_no_copula: True
- implementation_deferred: True
- change_type_governance: True
- seven_frozen_margins: True
- headline_frozen: True
- nested_ref: True
- residual_ladder_4: True
- six_gates: True
- gate_ids: True
- g1_invariance: True
- sequencing_present: True
- standards_cited: True

## 8. Standards

- SOA ASOP 25 (Credibility Procedures)
- SOA ASOP 56 sections 3.1.3, 3.4, 3.5, 3.6 (model risk, reliance, documentation)
- IFoA Model Practice Note (MPN) section 4 (documentation, independent review)
- Solvency II Delegated Regulation Article 124 (validation standards)
- Buhlmann & Straub (1970) credibility; limited-fluctuation (Mowbray) credibility
- Rosenblatt (1952) PIT; Anderson-Darling / Kolmogorov-Smirnov goodness-of-fit

*Generated by scripts/build_postigui_task1_design_note.py.*
