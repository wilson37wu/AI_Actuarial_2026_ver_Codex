# Phase 30 Task 1 - Design Note: Post-Vine Dependence Roadmap Decision

**Verdict: PASS** - selected option: **A_tree3_vine_deepening**. EDUCATIONAL ONLY.

## 1. Problem

Phase 29 closed with the first POSITIVE dependence result: the truncated 2-tree credit-root C-vine narrowed the copula-form residual to 3,637.3 (-65.33% vs grouped-t 10,491.5; -40.52% vs skew-t 6,114.9) and lifted the disclosed component SCR to 42,458.6 (bootstrap mean 41,917.6), but the nested path-wise reference 46,638.9 stayed OUTSIDE the 95% CI [38,654.7, 45,284.3]. MR-016 remains OPEN and MR-017 tracks the residual vine-FORM limitations - by construction, dependence the 2-tree truncation cannot represent. The roadmap decision is which escalation, if any, is justified next.

## 2. Headroom analysis (archived Phase 29 constants)

- Needed bootstrap-mean lift for nested to enter the CI: 1,354.6 (+3.23%) = 37.2% of the point residual 3,637.3.
- Max addressable share of the total gap by ANY dependence option: 87.0% (relief-surface part 543.0 is NOT dependence-addressable).

## 3. Option study

### A_tree3_vine_deepening

- ONE additional governed C-vine tree (the four pre-registered third-tree conditional pairs), same four pair families, frozen margins/Sigma/df, vine2 AND frozen-t boundary legs reproduced bit-identically before any candidate run.
- Expected residual closure (max abs): 3,637.3; cost: 4 cycle(s); governance risk: LOW: additive, disclosed, frozen-headline preserved.

### B_nested_aware_calibration

- Calibrate dependence parameters directly against the nested path-wise reference.
- Expected residual closure (max abs): 3,637.3; cost: 6 cycle(s); governance risk: HIGH: circular calibration to the validation benchmark.
- NOT selected: leakage/circularity without a new nested run; deferred as post-stop owner-approved escalation

### C_owner_adoption_package

- Decision package: adopt the disclosed vine read-out, or accept residual with MR-016 OPEN.
- Expected residual closure (max abs): 0.0; cost: 1 cycle(s); governance risk: NONE: no model change.
- NOT selected: zero residual closure; scheduled REGARDLESS as the post-Phase-30 owner package

### D_stop_rule

- Stop dependence-form escalation; redirect to credentialled-data priority (human-blocked).
- Expected residual closure (max abs): 0.0; cost: 0 cycle(s); governance risk: NONE.
- NOT selected: zero closure as a primary action; embedded as the pre-registered conditional stop-rule

## 4. Decision rule (pre-registered)

- R1: exclude options with zero expected residual closure as PRIMARY actions (C, D) - they are scheduled/embedded, not lost.
- R2: exclude options that re-use the only independent nested benchmark for calibration (B) unless the owner funds a second nested run.
- R3: the remaining option (A) is selected ONLY if the synthetic pre-study demonstrates boundary recovery, a positive truncation gap, holdout closure share >= 0.5, and tree-3 targeting above holdout drift.

**Stop-rule:** STOP-RULE (pre-registered): if the Phase 30 tree-3 vine still leaves the nested reference 46,638.9 outside its 95% bootstrap CI at Task 4, dependence-FORM escalation under MR-016 ENDS. No further copula-structure candidates may be opened without owner sign-off; Phase 31 becomes the owner decision package (option C), with option B available only as an owner-approved escalation funding a second independent nested run.

**Post-Phase-30 commitment:** Phase 31 is the owner decision package (option C) REGARDLESS of outcome: adopt-the-disclosed-read-out vs accept-residual vs fund option B with a second independent nested run.

## 5. Pre-registered tree-3 structure

- fx-rate | credit, liquidity
- rate-lapse | credit, liquidity
- lapse-mortality | credit, liquidity
- equity-liquidity | credit, fx
- Families: ['gaussian', 'student_t', 'survival_clayton', 'survival_gumbel']; max trees: 3
- Envelope checks: {"max_vine_trees_p30": 3, "third_tree_edge_count": 4, "third_tree_edges_ok": true, "third_tree_edges_unique": true, "first_second_tree_unchanged": true, "pair_families_unchanged": true, "ui_contract": ["1.11.0", "1.12.0"], "envelope_ok": true}

## 6. Synthetic tree-3 truncation pre-study

- n_scen=200,000; seed=30; tree3_strength(truth)=1.1
- Holdout VaR99.5: truth 278.51; 2-tree truncated 265.69; tree-3 fitted 276.68
- Truncation gap +4.83%; leakage-free holdout closure share 85.7% (fitted s3=1.0)
- Joint triple-tail lift +0.864 vs holdout pair drift 0.0372
- 2-tree boundary exact recovery: 0.0e+00; digest 5a2abc2ff92ca2c11c497c096845a724ed24a7aa96d8f4e339c67ce6a17ab7de

The synthetic pre-study is not a calibration. It demonstrates that (i) joint-conditional (tree-3) tail dependence leaves a positive VaR99.5 gap against a 2-tree truncation, (ii) a single governed tree-3 strength fitted leakage-free on a fit half closes a quantified share of that gap on the holdout half, and (iii) zero tree-3 strength recovers the 2-tree leg exactly. Real-data magnitude is reserved for Tasks 2-4.

## 7. Acceptance criteria (fixed before implementation)

**Task 2:**

- Dual boundary: reproduce frozen-t component 39,975.654628 AND archived 2-tree vine candidate 42,458.552710 bit-identically before any tree-3 computation; boundary max deviation <= 1e-09.
- Rank invariance: Sigma max|diff| <= 1e-12; homogeneous df remains 2.9451 within 0.0001; standalone margins bit-identical.
- Implement ONLY the four pre-registered third-tree conditional pairs; first/second-tree fits FROZEN from Phase 29 Task 2.
- Pair-family search limited to ['gaussian', 'student_t', 'survival_clayton', 'survival_gumbel']; no new families or rotations.
- Leakage control: tree-3 family/parameter selection on fit rows only; holdout diagnostics disclosed.
- Retain single-df t, grouped-t and 2-tree vine comparison variants on common random numbers.
- code_change ChangeRecord OWNER_REVIEW.

**Task 3:**

- Tree-3 vine margin bootstrap: >= 200 replicates x 20,000 sims; SE <= 5% of mean.
- HEADLINE: nested 46,638.9 inside the tree-3 vine 95% CI OR the stop-rule TRIGGERS (recorded in the report; no gate-shopping).
- Paired CRN deltas (tree-3 minus 2-tree vine; tree-3 minus frozen-t) with sign and CI.
- Seeds/config/digests recorded; idempotent re-run digest-identical.
- methodology_change ChangeRecord OWNER_REVIEW.

**Task 4:**

- Per-pair tail diagnostics including the four tree-3 conditional pairs; holdout pairs disclosed with CIs.
- Overfit check: holdout-to-fit max-lift ratio disclosed (P29 reference 0.049); concentration gate as P29 T4.
- MR decision: mitigate MR-016/MR-017 ONLY if nested is inside the CI AND the residual shrinks below 3,637.3; otherwise KEEP OPEN and APPLY THE STOP-RULE.
- MR-010/MR-014 refresh only if the governed headline moves > 1% (it must not: headline stays frozen-t).
- governance_change ChangeRecord OWNER_REVIEW; risk-register update idempotent.

**Task 5 plan:** Offline-UI propagation only after Tasks 2-4: additive contract 1.11.0 -> 1.12.0 with tree-3 vs 2-tree vs frozen vs nested SCR, tree-3 pair diagnostics, stop-rule status, and MR-016/MR-017 decisions.

## 8. Limitations

- This cycle is design-only; no capital figure changes.
- The synthetic pre-study demonstrates mechanism and leakage-free closure on synthetic data, not real-data magnitude.
- A tree-3 C-vine may STILL not bring the nested reference inside the CI; the pre-registered stop-rule makes that outcome terminal for dependence-form escalation.
- Production sign-off remains blocked by credentialled data and independent APS X2 review.

## 9. Standards

- Aas, Czado, Frigessi & Bakken (2009), Pair-copula constructions of multiple dependence
- Bedford & Cooke (2002), Vines - a new graphical model for dependent random variables
- Solvency II Delegated Regulation Article 234 (aggregation including tail behaviour)
- Solvency II Delegated Regulation Article 124 (validation standards: independence of validation data)
- SOA ASOP 56 sections 3.1.3, 3.4, 3.5
- SOA ASOP 25 section 3.3
- IA TAS M sections 3.2, 3.6, 3.7
- McNeil, Frey & Embrechts (2015), Quantitative Risk Management ch. 7

*Generated by scripts/build_phase30_task1_dependence_roadmap.py.*
