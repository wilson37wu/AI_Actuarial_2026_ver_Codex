# Phase 26 Task 1 — Design Note: Full Path-Wise Copula Re-Aggregation

**Verdict: PASS** (design note + tested helper module + synthetic composition-heterogeneity pre-study). EDUCATIONAL ONLY.

## 0. Candidate selection (design-note-first discipline)

**Chosen:** full path-wise copula re-aggregation (P25T4 documented next-phase candidate; quantified 14.7%-beyond-noise motivation).

- Credentialled-data calibration: BLOCKED on credentialled management-practice data (standing human-action blocker); not executable from the sandbox. Remains the production sign-off residual by design.
- Declaration-cadence refinement: DEFERRED: the annual-cadence sensitivity (ratio 1.136, deterministic basis) is archived; cadence evidence computed on the aggregation basis that THIS phase changes would be superseded within one phase. Sequencing the aggregation refinement first avoids duplicated cadence benchmarks.

## 1. Problem

Phase 25 Task 4 produced the t/gaussian path-wise capital read-outs by ANALYTIC RE-ANCHORING: the governed smoothed-relief surface (sigma 0.225, alpha 0.7567) plus ONE constant FIT-sample benefit share (beta_fit 0.8450) applied to the anchored joint TOTAL liability level of each copula scenario. The transform therefore sees neither the per-driver composition of the scenario nor the per-node spread of the cuttable share. The frozen-copula margin bootstrap quantified the consequence: the nested path-wise reference 46,638.9 sits OUTSIDE the re-anchoring 95% CI [35,793, 42,496] - the re-anchoring understates nested by 14.7% BEYOND margin noise. The mechanism is composition heterogeneity: the 99.5% tail of the joint loss is disproportionately driven by the heavy-tailed CARVE-OUT (non-cuttable) drivers (credit loss; analytic FX/liquidity offsets), so the constant-share level transform credits relief the governed rule cannot actually take in the tail.

Archived Phase 25 motivation figures (NOT consumed by gates): {"nested_scr_with_pathwise": 46638.9, "t_copula_reanchored_readout": 39794.3, "gaussian_reanchored_readout": 35210.1, "bootstrap_ci95": [35793.0, 42496.0], "understatement_beyond_noise_rel": 0.147}

## 2. Method — full path-wise copula re-aggregation (Tasks 2-3)

Full path-wise copula re-aggregation (Tasks 2-3): keep the copula FROZEN (df 2.9451 tail-matched on the without-actions basis, Phase 23 Task 2; correlation matrix bit-frozen) and replace the level transform with a per-driver composition transform: for each joint copula scenario, recover the per-driver loss composition from the frozen margins, split cuttable vs carve-out components per scenario, evaluate the governed smoothed-relief surface on the scenario's coverage state, and apply the relief to the scenario's CUTTABLE component only (clip at max_relief of the cuttable component - the node-level envelope preserved per scenario). Calibration scalars (sigma, alpha) remain the governed Phase 25 Task 3 FIT-sample values - leakage-free, NO re-tuning. Task 3 then re-runs the frozen-copula margin bootstrap on the FULL re-aggregated basis: the headline acceptance criterion is that the nested path-wise reference falls INSIDE the 95% CI (closure of the beyond-noise understatement), or the residual gap is decomposed (copula-form vs relief-surface error) and disclosed.

**Hypothesis:** The full re-aggregated t-copula path-wise SCR is HIGHER than the analytic re-anchored read-out 39,794.3 (composition heterogeneity can only reduce tail relief vs the constant-share level transform) and the gap to the nested reference 46,638.9 shrinks to within margin noise; the synthetic pre-study sign carries over.

## 3. Pre-study (synthetic composition-heterogeneity mechanism)

- Synthetic portfolio: 7 drivers, equicorrelated t-copula rho 0.5, df 3, lognormal margins; carve-out (non-cuttable) drivers mirror P24T3; n_scen=200,000, seed=42
- VaR99.5 per 100 mean loss: without 180.02; level basis 170.93; component basis 172.38
- Level basis UNDERSTATES the component-basis VaR99.5 by 0.8%
- Tail cuttable-share depression: mean 0.566 vs tail 0.472 (the mechanism: the tail is carve-out-driven)
- Mean relief nearly unchanged (2.11 vs 2.02): a tail re-ranking effect, not a mean shift
- understatement_sign_ok=True; ordering_ok=True; bounds_ok=True; digest=96b60bb361046ba181d3a0b0c4aae0c8c8d4a4088e9d8daf9c7f980d629b1583

The pre-study uses a SYNTHETIC seven-driver t-copula portfolio (equicorrelated rho 0.5, df 3, lognormal margins, three carve-out drivers mirroring the P24T3 non-cuttable components) so that no real archived nested benchmark is consumed before the Task 2 gates. On common random numbers, moving the relief from the constant-share level basis to the per-scenario cuttable composition raises VaR99.5 by 0.8% - the level basis UNDERSTATES with-actions capital, and the tail cuttable share is depressed (0.566 mean vs 0.472 in the tail). It demonstrates the composition-heterogeneity MECHANISM and its SIGN, not the magnitude of the real-data effect: on the real basis two further channels (per-node coverage-state heterogeneity and the benefit-share spread, both clip-binding at node level) widen the gap toward the archived 14.7%; they are quantified only at Tasks 2-3.

## 4. Gap analysis (standards vs current model)

### Solvency II Del. Reg. Art. 234; IFoA Aggregation WP (dependence on the basis used)

- **Requirement:** Diversification/dependence empirically justified ON THE BASIS ACTUALLY USED for capital, including tail behaviour; no silent re-tuning when the basis changes.
- **Current state:** Copula frozen (df 2.9451 on without-actions losses; rank invariance re-verified at P25T4), but the with-actions t/gaussian read-outs are a LEVEL transform of the joint total - the dependence between cuttable and carve-out components inside the tail is not represented.
- **Gap:** The benchmark capital read-outs on the path-wise basis are quantified as understating the nested reference by 14.7% beyond margin noise.
- **Phase 26 design:** Task 2: per-driver composition transform on the frozen copula (no re-tuning); Task 3: bootstrap closure test against the nested reference; rank-invariance re-verified each task.

### SOA ASOP 56 §3.1.3/§3.4 (model structure; approximations appropriate to purpose)

- **Requirement:** Structure of the model - including the LEVEL at which an approximation enters - appropriate to the intended purpose; material approximation error identified.
- **Current state:** Constant beta_fit benefit share applied at the joint level (disclosed first-order approximation, P25T4); per-node share spread reported but not propagated.
- **Gap:** The approximation error is quantified (14.7% beyond noise) and exceeds any reasonable materiality threshold for a benchmark read-out.
- **Phase 26 design:** Task 2 propagates the per-scenario cuttable composition; the constant-share level transform is RETAINED as the comparison variant (P24T3 convention).

### IA TAS M §3.2/§3.6 (limitations disclosed; evidence reproducible)

- **Requirement:** Material limitations disclosed with quantification where practicable; validation evidence reproducible with recorded config.
- **Current state:** P25T4/T5 disclose the understatement verbatim in the report, risk register (MR-010/MR-014) and offline UI, with the bootstrap CI.
- **Gap:** Disclosure exists; the REMEDIATION is the open item - benchmark read-outs should not stay outside their own confidence band against the truth reference.
- **Phase 26 design:** Task 3 headline gate: nested reference INSIDE the full re-aggregation 95% CI, or residual gap decomposed + disclosed; seeds/config/digests recorded; Task 4 refreshes MR-010/MR-014.

### Solvency II Del. Reg. Art. 23 (management actions consistent with practice)

- **Requirement:** Allowance for management actions consistent with how they would actually be exercised - including WHAT can be cut: carve-outs (credit loss, FX/liquidity offsets) are not relievable by a bonus cut.
- **Current state:** Nested truth respects carve-outs per node (P24T3); the benchmark level transform applies a constant cuttable share to the joint total - in the tail this credits relief on carve-out-driven losses.
- **Gap:** Benchmark relief in the tail exceeds what the governed rule can take; sign pre-registered (understatement of capital).
- **Phase 26 design:** Task 2 applies relief to the per-scenario CUTTABLE component only, with the per-scenario max_relief envelope clip.

## 5. Acceptance criteria (FIXED, pre-registered — no gate-shopping)

**Task 2:**

- Per-driver composition transform on the FROZEN copula: relief applied to the per-scenario cuttable component only; per-scenario envelope clip at max_relief of the cuttable component; governed sigma/alpha UNCHANGED (P25T3 FIT values; no re-tuning)
- Rank invariance: df re-matched on the WITHOUT-actions staged losses within 0.0001 of 2.9451; correlation matrix max|diff| <= 1e-12 (copula FROZEN, Art. 234)
- Without-actions t/gaussian read-outs and the P25T4 re-anchored read-outs reproduced bit-identically BEFORE any new computation (archive cross-check)
- Sign gate (pre-registered): full re-aggregated t-copula path-wise SCR >= the analytic re-anchored read-out 39,794.3; magnitude DISCLOSED, not gated
- Constant-share level transform RETAINED and reported alongside as the comparison variant (P24T3 convention)
- No gate-shopping: these gates fixed in this Task 1 note before any real-data full re-aggregation
- code_change ChangeRecord OWNER_REVIEW

**Task 3:**

- Frozen-copula margin bootstrap on the FULL re-aggregated basis: >= 200 replicates x 20,000 sims (P25T4 pattern)
- HEADLINE gate: nested path-wise reference 46,638.9 INSIDE the full re-aggregation 95% CI - closure of the beyond-noise understatement; if still outside, the residual gap MUST be decomposed (copula-form vs relief-surface error) and disclosed - no silent acceptance
- Bootstrap SE <= 5% of the mean SCR
- Idempotent re-run digest-identical; seeds/config recorded
- methodology_change ChangeRecord OWNER_REVIEW

**Task 4:**

- Tail diagnostics on the full re-aggregated basis: with-vs-without and full-vs-reanchored deltas at VaR/ES/SCR for nested, t, gaussian (var-covar: no path-wise analogue - DISCLOSED in-table, P25T4 convention)
- MR-010 (var-covar understatement) and MR-014 refreshed if the full re-aggregated SCR moves more than 1% from the re-anchored read-out (disclosure trigger, not pass/fail)
- Rank invariance re-verified: df 2.9451 on without-actions losses; copula parameters frozen (no silent re-tuning)
- Reproducibility: seeds, config, digests recorded; assumption_change/governance ChangeRecord OWNER_REVIEW

**Task 5 plan:** Offline-UI propagation (ui_data.json contract 1.7.0 -> 1.8.0 ADDITIVE; full re-aggregation panel: full-vs-reanchored-vs-nested SCR comparison, bootstrap CI closure read-out, composition-heterogeneity diagnostics, gates) + PHASE 26 COMPLETE documentation; UI consumes ONLY model-output JSON.

## 6. Limitations

- The synthetic pre-study proves the composition-heterogeneity mechanism and its SIGN, not the magnitude (synthetic margins; single relief surface; no per-node clip binding).
- The full re-aggregation still consumes the governed smoothed-relief surface (sigma, alpha) - a FIT-sample approximation of the path-wise truth; residual surface error is decomposed at Task 3 if the CI gate fails.
- Per-driver composition recovery from the frozen margins is exact only at the margin level used by the benchmark (node-level heterogeneity below the driver level remains aggregated).
- Declaration cadence (annual board declaration with smoothing) remains the deferred candidate; sensitivity 1.136 archived.
- Action parameters remain educational placeholders pending credentialled practice data + independent APS X2 review.

## 7. Standards

- Solvency II Delegated Reg. Art. 234 (empirically justified diversification incl. tail behaviour; dependence justified on the basis actually used for capital)
- Solvency II Delegated Reg. Art. 23 (future management actions: objective, realistic, verifiable)
- SOA ASOP 56 §3.1.3/§3.4/§3.5
- SOA ASOP 25 §3.3
- IA TAS M §3.2/§3.6
- IFoA Life Aggregation & Simulation working party
- CFO Forum MCEV Principle 7 (TVOG; dynamic management actions)

*Generated by scripts/build_phase26_task1_design_note.py — educational model; production sign-off withheld.*
