# Phase 31 Task 1 - Design Note: Owner Decision Package (Dependence)

**Verdict: PASS** | classification EDUCATIONAL | change type `governance_change` | model parameter changes: NONE

## 1. Context

Phase 30 applied the BINDING STOP-RULE: the tree-3 vine candidate fitted zero third-tree strength (bit-identical to the 2-tree vine) and the nested path-wise reference 46,638.9 stayed outside the 95% bootstrap CI, so dependence-FORM escalation under MR-016 ENDS. Phase 31 is pre-registered roadmap option C: hand the owner a complete, neutral decision package. This note FREEZES the pack contents, the three options with acceptance criteria, and the sign-off workflow before the pack is assembled (Task 2).

## 2. Pre-registered evidence pack contents

- Governed headline (frozen single-df t): **39,975.654628** (df 2.9451; move through P27-P30: 0.0000%)
- Disclosed 2-tree vine: point 42,458.5527; bootstrap mean 41,917.6; CI95 [38,654.7, 45,284.3] - NOT adopted
- Tree-3 candidate: BIT-IDENTICAL point 42,458.5527; bootstrap mean 41,751.9; CI95 [38,593.7, 44,556.4] - NOT adopted
- Nested reference: 46,638.9 (inside vine2 CI: False; inside tree-3 CI: False). ONE nested run only; its own sampling error is unquantified - the motivation for option O3.
- Residual ladder (copula-form residual, abs):

  - grouped-t (P28): 10,491.5
  - frozen single-df t (P26): 6,120.2
  - skew-t (P27): 6,114.9
  - 2-tree / tree-3 vine (P29/P30): 3,637.3

- Gap decomposition: total 4,180.3; copula-form part 3,637.3
- Risk register: MR-016 OPEN - quantified copula-form residual disclosed; MR-017 OPEN - vine-form limitations (truncation)
- Stop-rule record: {"trigger": "nested path-wise reference outside the tree-3 candidate 95% bootstrap CI at Phase 30 Task 4", "trigger_met": true, "applied": true, "effect": "dependence-FORM escalation under MR-016 ENDS", "mr016_disposition": "KEEP OPEN (quantified residual disclosed)", "mr017_disposition": "KEEP OPEN (vine-form limitations)", "governed_headline_move_pct": 0.0, "tree3_zero_strength": true, "tree3_bit_identical_to_vine2": true}
- Escalation history:

  - Phase 26 (frozen single-df t (path-wise re-aggregation)): residual 6,120.2 - baseline quantified residual
  - Phase 27 (skew-t copula): residual 6,114.9 - no material closure vs frozen-t; not adopted
  - Phase 28 (grouped-t / heterogeneous tail): residual 10,491.5 - residual WIDENED; rejected
  - Phase 29 (truncated 2-tree credit-root C-vine): residual 3,637.3 - first POSITIVE result; nested still outside 95% CI; DISCLOSED, not adopted
  - Phase 30 (tree-3 C-vine deepening): residual 3,637.3 - all four pre-registered third-tree pairs fitted zero strength; BIT-IDENTICAL to 2-tree vine; binding stop-rule APPLIED

## 3. The three owner options (pre-registered)

### O1_adopt_disclosed_vine_readout

- Adopt the disclosed 2-tree vine read-out (42,458.6) as the governed component-SCR headline, replacing the frozen single-df t (39,975.7).
- Capital effect (abs): 2,482.9; governance risk: HIGH - adopts a candidate whose 95% CI excludes the nested reference; escalation path open: False
- Acceptance criteria:

  - explicit owner sign-off recorded in a governance ChangeRecord (model_change) BEFORE any headline switch
  - a written MR-017 mitigation plan for the residual vine-form limitations (truncation; nested outside 95% CI)
  - full re-run of the UI/state propagation chain so every disclosure surface shows the new governed basis
  - risk-register update: MR-016 re-pointed at the REMAINING residual 3,637.3, not closed

### O2_accept_residual_with_monitoring

- Keep the frozen single-df t headline; formally ACCEPT the quantified copula-form residual 3,637.3 as a documented model limitation.
- Capital effect (abs): 0.0; governance risk: MEDIUM - residual persists but is quantified, disclosed and monitored; escalation path open: False
- Acceptance criteria:

  - a documented residual TOLERANCE (absolute and as % of the governed headline) signed by the owner
  - a pre-registered MONITORING TRIGGER (re-open MR-016 escalation if a future recalibration moves the residual beyond tolerance)
  - annual re-affirmation entry in the risk register (MR-016/MR-017 stay OPEN with ACCEPTED disposition)

### O3_fund_second_independent_nested_run

- Fund former roadmap option B: a SECOND, independent nested path-wise run (fresh seeds, independent implementation checks) to quantify the sampling error of the nested reference 46,638.9 - the only escalation path the Phase 30 binding stop-rule left open.
- Capital effect (abs): 0.0; governance risk: LOW - adds information only; no model change; escalation path open: True
- Acceptance criteria:

  - pre-registered design note BEFORE the run (seeds, scenario count, acceptance gates) - no peeking at the existing nested figure when fixing gates
  - the run is INDEPENDENT: new random seeds and an independent reviewer of the run configuration (ASOP 56 s3.5 reliance)
  - decision rule fixed in advance: if the two nested runs bracket the vine CI differently, the owner package is re-issued with the pooled estimate; copula-FORM escalation stays ENDED either way

## 4. Sign-off workflow (IFoA MPN s4 / ASOP 56)

1. **preparer (model development)** - assemble the evidence pack EXACTLY per evidence_pack_registry(); bit-for-bit consistency gate against the frozen archived references [ASOP 56 s3.1.3 (understanding the model); IFoA MPN s4 (documentation sufficient for a technically competent third party)]
2. **independent peer reviewer** - review pack completeness, figure provenance and the neutral presentation of all three options (no recommendation embedded) [ASOP 56 s3.4 (reliance on others); IFoA MPN s4.3 (independent review proportionate to materiality)]
3. **model owner** - owner review meeting: walk through governed headline, disclosed candidates, residual ladder, stop-rule record and the three options with their pre-registered acceptance criteria [ASOP 56 s3.5 (evaluation and mitigation of model risk); IFoA MPN s4.4 (communication of limitations to the decision maker)]
4. **model owner** - record the decision (O1/O2/O3) and its rationale in a governance ChangeRecord; the decision is NOT made by the model developer or any agent [ASOP 56 s3.6 (documentation of decisions); IFoA MPN s4.5 (clear ownership of the decision)]
5. **preparer (model development)** - execute the selected option's acceptance criteria; update MR-016/MR-017 dispositions accordingly [ASOP 56 s3.5; IFoA MPN s4.6 (follow-up actions)]
6. **preparer (model development)** - propagate any NEW disclosure surface to the offline UI (additive contract bump only) and archive the pack [IFoA MPN s4 (audit trail); ASOP 41 (actuarial communications)]

## 5. Validation gate

- ok: **True** (21 checks)
- headline_matches_frozen_t: True
- headline_move_zero: True
- vine2_point_matches: True
- tree3_bit_identical: True
- no_candidate_adopted: True
- nested_matches: True
- nested_outside_both_cis: True
- residual_ladder_descending: True
- residual_ladder_endpoints: True
- mr_status_open: True
- stop_rule_applied: True
- history_complete_p26_p30: True
- exactly_three_options: True
- each_option_has_criteria: True
- single_escalation_path_is_o3: True
- o2_zero_capital_effect: True
- workflow_ordered: True
- workflow_has_owner_decision: True
- workflow_has_independent_review: True
- every_step_has_standards: True
- no_parameter_changes: True

## 6. Task 2 acceptance criteria (frozen now)

- assembled pack reproduces every registered figure bit-for-bit (validate_owner_package ok:true re-run against the assembled pack)
- pack presents all three options NEUTRALLY - no recommendation, no default option
- pack is self-contained: a technically competent third party can follow it without repo access (IFoA MPN s4)
- governance ChangeRecord (governance_change) OWNER_REVIEW; audit integrity verify_all true

**Task 3 plan:** Owner-facing summary; offline-UI propagation ONLY IF a new disclosure surface is added (additive contract bump). After Phase 31 the standing directive applies: focus shifts to the zero-install offline user interface.

## 7. Limitations

- the nested reference is a SINGLE run; its sampling error is unquantified (motivates option O3)
- acceptance criteria constrain but cannot bind the owner; the owner may request variations, which would re-open this note via a new ChangeRecord
- the residual ladder compares copula FORMS on a fixed margin/calibration basis; margin-side model risk is tracked separately

## 8. Standards

- IFoA Model Practice Note (MPN) section 4 (documentation, independent review, communication)
- SOA ASOP 56 sections 3.1.3, 3.4, 3.5, 3.6 (model risk, reliance, documentation of decisions)
- SOA ASOP 41 (actuarial communications)
- Solvency II Delegated Regulation Article 124 (validation standards)
- Solvency II Delegated Regulation Article 234 (aggregation including tail behaviour)

*Generated by scripts/build_phase31_task1_owner_decision_design_note.py.*
