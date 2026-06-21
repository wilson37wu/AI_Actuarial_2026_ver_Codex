# Owner Decision Pack - Dependence (Phase 31 Task 2)

**Pack** `PHASE31_OWNER_DECISION_PACK` v1.0.0 | classification EDUCATIONAL | model parameter changes: NONE | assembly gate: **PASS** (16 checks)

## 1. Purpose

Give the model owner everything needed to decide how to dispose of the quantified dependence-form residual 3,637.3 between the governed frozen single-df t headline 39,975.7 and the nested path-wise reference 46,638.9, after the Phase 30 binding stop-rule ended dependence-FORM escalation. Three options are presented neutrally; the choice rests solely with the model owner.

## 2. How to read this pack

- Section 'evidence_pack' holds every governed and disclosed figure with its status; nothing in it is a proposal.
- Section 'figure_provenance' states the frozen archived source of each figure; no figure was recomputed at assembly time.
- Section 'owner_options' lists the three pre-registered options in fixed order O1/O2/O3 with their acceptance criteria; the ordering is registry order, not preference order.
- Section 'signoff_workflow' is the six-step decision process; the owner decides at step 4 using the blank 'decision_record_template'.
- The glossary defines every technical term used, so the pack can be read without access to the model repository.

## 3. Evidence

- Governed headline (frozen single-df t): **39,975.654628** (df 2.9451; move through P27-P30: 0.0000%) - GOVERNED - unchanged by every escalation P27->P30
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
- Escalation history:

  - Phase 26 (frozen single-df t (path-wise re-aggregation)): residual 6,120.2 - baseline quantified residual
  - Phase 27 (skew-t copula): residual 6,114.9 - no material closure vs frozen-t; not adopted
  - Phase 28 (grouped-t / heterogeneous tail): residual 10,491.5 - residual WIDENED; rejected
  - Phase 29 (truncated 2-tree credit-root C-vine): residual 3,637.3 - first POSITIVE result; nested still outside 95% CI; DISCLOSED, not adopted
  - Phase 30 (tree-3 C-vine deepening): residual 3,637.3 - all four pre-registered third-tree pairs fitted zero strength; BIT-IDENTICAL to 2-tree vine; binding stop-rule APPLIED

## 4. Figure provenance (frozen archived constants)

- **governed_headline**: par_model_v2.projection.vine_copula_upgrade.FROZEN_T_COMPONENT_SCR_REFERENCE (frozen at Phase 26; re-affirmed bit-for-bit every phase through P30)
- **vine2_point**: par_model_v2.projection.dependence_roadmap.VINE2_COMPONENT_SCR_POINT (Phase 29 Task 2 archived run)
- **vine2_bootstrap**: par_model_v2.projection.dependence_roadmap.VINE2_COMPONENT_SCR_BOOTSTRAP_MEAN / VINE2_BOOTSTRAP_CI95 (Phase 29 Task 4 archived bootstrap)
- **tree3_bootstrap**: par_model_v2.projection.vine_tree3_tail_diagnostics.P30T3_TREE3_COMPONENT_MEAN / P30T3_TREE3_CI_LO / P30T3_TREE3_CI_HI (Phase 30 Task 3 archived bootstrap)
- **nested_reference**: par_model_v2.projection.vine_copula_upgrade.NESTED_PATHWISE_SCR_REFERENCE (Phase 24 archived nested run)
- **residual_ladder**: par_model_v2.projection.grouped_t_upgrade.COPULA_FORM_RESIDUAL_ABS (P26 frozen-t), vine_copula_upgrade.GROUPED_T_COPULA_FORM_RESIDUAL_ABS (P28), vine_copula_upgrade.SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS (P27), dependence_roadmap.VINE2_COPULA_FORM_RESIDUAL_POINT (P29/P30)
- **gap_decomposition**: par_model_v2.projection.dependence_roadmap.VINE2_GAP_TOTAL_POINT / VINE2_COPULA_FORM_RESIDUAL_POINT (Phase 29 Task 4 archived decomposition)

## 5. The three options (registry order, not preference order)

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

## 6. Sign-off workflow

1. **preparer (model development)** - assemble the evidence pack EXACTLY per evidence_pack_registry(); bit-for-bit consistency gate against the frozen archived references [ASOP 56 s3.1.3 (understanding the model); IFoA MPN s4 (documentation sufficient for a technically competent third party)]
2. **independent peer reviewer** - review pack completeness, figure provenance and the neutral presentation of all three options (no recommendation embedded) [ASOP 56 s3.4 (reliance on others); IFoA MPN s4.3 (independent review proportionate to materiality)]
3. **model owner** - owner review meeting: walk through governed headline, disclosed candidates, residual ladder, stop-rule record and the three options with their pre-registered acceptance criteria [ASOP 56 s3.5 (evaluation and mitigation of model risk); IFoA MPN s4.4 (communication of limitations to the decision maker)]
4. **model owner** - record the decision (O1/O2/O3) and its rationale in a governance ChangeRecord; the decision is NOT made by the model developer or any agent [ASOP 56 s3.6 (documentation of decisions); IFoA MPN s4.5 (clear ownership of the decision)]
5. **preparer (model development)** - execute the selected option's acceptance criteria; update MR-016/MR-017 dispositions accordingly [ASOP 56 s3.5; IFoA MPN s4.6 (follow-up actions)]
6. **preparer (model development)** - propagate any NEW disclosure surface to the offline UI (additive contract bump only) and archive the pack [IFoA MPN s4 (audit trail); ASOP 41 (actuarial communications)]

## 7. Decision record (blank - for the owner at step 4)

```json
{
 "decision_option_id": "",
 "rationale": "",
 "decided_by": "",
 "decided_at": "",
 "peer_reviewer": "",
 "follow_up_change_record_id": "",
 "instructions": "To be completed by the model owner at workflow step 4. Select exactly one of O1/O2/O3, record the rationale, and open a governance ChangeRecord referencing this pack."
}
```

## 8. Glossary

- **component SCR**: the 99.5th-percentile one-year loss for the modelled risk aggregation component, before diversification with other balance-sheet components
- **governed headline**: the component SCR figure currently approved for use - the frozen single-df t-copula read-out 39,975.7; it has not moved through any escalation P27->P30
- **copula-form residual**: the absolute difference between a copula candidate's component SCR and the nested path-wise reference, holding margins and calibration fixed - it isolates the dependence-FORM effect
- **nested path-wise reference**: a full nested stochastic re-simulation that applies the governed management-action rule inside every joint scenario (46,638.9); ONE run exists, so its own sampling error is unquantified
- **bootstrap CI95**: the 95% confidence interval for a candidate's component SCR obtained by resampling the joint scenario set
- **C-vine copula**: a vine copula built from a cascade of bivariate copulas around root nodes; 'truncated 2-tree' means only the first two trees carry fitted dependence
- **binding stop-rule**: the pre-registered Phase 30 rule that ENDS dependence-form escalation once an added vine tree fits zero strength while the nested reference stays outside the candidate's 95% CI
- **MR-016**: model-risk register item: quantified copula-form residual (dependence form) - OPEN, disclosed
- **MR-017**: model-risk register item: vine-form limitations (truncation; nested outside 95% CI) - OPEN, disclosed

## 9. Limitations

- the nested reference is a SINGLE run; its sampling error is unquantified (the subject of option O3)
- acceptance criteria constrain but cannot bind the owner; variations re-open the design note via a new ChangeRecord
- the residual ladder compares copula FORMS on a fixed margin/calibration basis; margin-side model risk is tracked separately

## 10. Standards

- IFoA Model Practice Note (MPN) section 4 (documentation, independent review, communication)
- SOA ASOP 56 sections 3.1.3, 3.4, 3.5, 3.6 (model risk, reliance, documentation of decisions)
- SOA ASOP 41 (actuarial communications)
- Solvency II Delegated Regulation Article 124 (validation standards)

## 11. Assembly gate

- ok: **True** (16 checks)
- task1_gate_ok_on_assembled_pack: True
- task1_gate_n_checks_21: True
- evidence_bit_for_bit: True
- options_bit_for_bit: True
- workflow_bit_for_bit: True
- option_order_is_registry_order: True
- no_steering_language: True
- decision_fields_blank: True
- no_recommended_key: True
- all_required_sections: True
- glossary_complete: True
- provenance_covers_headline_figures: True
- standards_cited: True
- purpose_states_residual: True
- pack_identity: True
- educational_no_param_changes: True

*Generated by scripts/build_phase31_task2_assemble_owner_pack.py.*
