# Phase 24 Task 1 — Design Note: Joint-Scenario Action-After-Aggregation + Inner-Path Action Dynamics

**Verdict: PASS** (design note + tested helper module + synthetic-truth pre-study). EDUCATIONAL ONLY.

## 1. Problem

Phase 23 Task 4 disclosed a MATERIAL FINDING: aggregating standalone WITH-ACTIONS losses with the tail-matched t(2.9451) copula understates the nested with-actions benchmark by 22.5% (vs 4.0% without actions). The governed action SATURATES (max liability relief 12%) in the joint tail where the total liability is largest, while each standalone tail sits in the steeper partial-cut band - applying the rule to marginals before aggregation double-counts relief exactly where capital is measured. Separately, the action remains an outer-node liability transform; inner-path bonus dynamics (cut affecting projected cashflows) are unmodelled.

Archived Phase 23 Task 4 motivation figures (NOT consumed by gates): {"nested_scr_with_actions": 33117.7704, "t_matched_scr_with_actions": 25652.9228, "t_matched_rel_error_with_actions": 0.225403, "gaussian_rel_error_with_actions": 0.277674, "var_covar_understatement_with_actions": 0.56432, "df_matched": 2.9451, "source": "docs/validation/PHASE23_TASK4_AGGREGATION_WITH_ACTIONS_REPORT.json"}

## 2. Method A — joint-scenario (action-after-aggregation) re-aggregation (Task 2)

Aggregate the WITHOUT-actions dependence structure first, then apply the governed rule ONCE to the anchored simulated JOINT liability: V = L_fit + sum_k (Q_k(U_k) - mean_k); W = rule.apply_to_liabilities(V, A_ref). Q_k = empirical margins of the Phase 23 Task 2 staged WITHOUT-actions standalone losses; U from t(df_matched) and Gaussian copulas on the governed correlation; L_fit/A_ref identical (leakage-free) to the Phase 23 Task 3/4 convention. Implemented and unit-tested in par_model_v2/projection/joint_action_aggregation.py (JointActionAggregator).

**Hypothesis:** Saturation is then modelled at the joint level, so the t-copula joint-action SCR rel err vs nested-with-actions collapses from the disclosed 22.5% to <= 10%.

### Pre-study (synthetic-truth saturation mechanism)

- Truth: two lognormal margins, t(4) copula, rho=0.6, n_truth=120,000, seed=42
- True with-actions VaR99.5: 150,599; truth active share 35.5%
- Standalone-action basis VaR99.5: 140,790 (UNDERSTATES truth by 6.5%)
- Joint-action basis VaR99.5: 148,643 (rel err 1.3%)
- understatement_sign_ok=True; joint_recovers_truth=True; digest=ff4de2b86464

The pre-study uses a SYNTHETIC two-driver lognormal/t(4)-copula ground truth so that no real archived nested benchmark is consumed before the Task 2 gates: it demonstrates the saturation MECHANISM (standalone-action basis understates true with-actions VaR99.5 by 6.5%) and that action-after-aggregation recovers the truth (rel err 1.3%).

## 3. Method B — inner-path action dynamics prototype (Task 3)

Prototype inner-path action dynamics: the bonus cut applies to the inner-path projected bonus cashflows (declared-rate path responds to the coverage ratio at the outer node), not only to the outer-node conditional-liability transform. Nested ground truth extended; the LSMC proxy gains the matching analytic post-composition basis feature; seven-driver OOS re-validation at the unchanged Phase 22 gates.

**Scope note:** Full path-wise dynamic declaration (action re-evaluated at every inner time step) is OUT of Phase 24 scope; the prototype relaxes the outer-node approximation one step (horizon-level cashflow response) and documents the residual.

## 4. Gap analysis (standards vs current model)

### Solvency II Del. Reg. Art. 23 (management actions)

- **Requirement:** Effect of management actions quantified consistently with how they would be exercised: the insurer cuts the bonus ONCE on its TOTAL solvency position, not once per risk driver.
- **Current state:** Phase 23 Task 4 applies the rule per standalone marginal, then aggregates; nested-with-actions applies it to the full conditional liability (correct reference).
- **Gap:** Copula diagnostic basis is inconsistent with how the action is exercised; understates capital by 22.5% vs the nested reference (disclosed).
- **Phase 24 design:** Task 2 joint-scenario re-aggregation: rule applied INSIDE the copula simulation to the joint liability; gate rel err <= 10% AND strictly below the 22.5% baseline.

### SOA ASOP 56 §3.1.3/§3.4 (model structure; assumptions supportable)

- **Requirement:** Model structure appropriate to the intended purpose, including the level at which management behaviour enters the model.
- **Current state:** Action is an outer-node deterministic transform of the conditional liability; inner-path cashflows (bonus declarations) do not respond.
- **Gap:** Liability relief is instantaneous at the horizon; no recognition lag or cashflow path response - TVOG interaction unmeasured.
- **Phase 24 design:** Task 3 inner-path prototype: horizon-level bonus-cashflow response in the nested truth + matching proxy basis feature; OOS re-validation R^2 >= 0.95, VaR rel err <= 10%.

### IA TAS M §3.2/§3.6 (limitations disclosed; evidence reproducible)

- **Requirement:** Material limitations of the aggregation basis disclosed; validation evidence reproducible with recorded config.
- **Current state:** Saturation finding disclosed verbatim in the Task 4 report, MR-010/MR-014 notes, and the offline UI.
- **Gap:** Risk-register notes describe the gap but no quantified joint-basis remediation exists yet.
- **Phase 24 design:** Task 4: joint-vs-standalone and with-vs-without capital deltas at every level; MR-010/MR-014 refreshed with the joint-basis figures; seeds/config/digests recorded.

### Solvency II Del. Reg. Art. 234; IFoA Aggregation WP (tail dependence)

- **Requirement:** Dependence assumptions empirically justified INCLUDING tail behaviour, on the basis actually used for capital.
- **Current state:** df=2.9451 tail-matched on WITHOUT-actions losses (Phase 23 Task 2); Task 4 showed rank invariance under the standalone with-actions transform.
- **Gap:** Joint-action basis must not silently re-tune the copula: df re-matched on the without-actions losses must remain 2.9451 (the action is a liability transform, not a dependence change).
- **Phase 24 design:** Task 2 rank-invariance gate: df re-matched on the without-actions staged losses unchanged at 2.9451; copula params frozen before the joint-action read-out.

## 5. Acceptance criteria (FIXED, pre-registered — no gate-shopping)

**Task 2:**

- t(df_matched) JOINT-action SCR rel err vs nested-with-actions <= 10%
- AND strictly below the disclosed Phase 23 Task 4 standalone-action rel err (22.5%)
- Rank invariance: df re-matched on WITHOUT-actions staged losses unchanged at 2.9451; correlation matrix frozen
- Gaussian joint-action and var-covar comparators reported alongside; nested-with-actions remains the reference
- Staged primitives reused bit-identically with archive cross-checks BEFORE any new computation
- No gate-shopping: these gates fixed in this Task 1 note before any real-data joint-action benchmark
- MR-010 + MR-014 refresh; methodology_change ChangeRecord OWNER_REVIEW

**Task 3:**

- Inner-path prototype: bonus cut enters horizon-level inner cashflows in the nested truth AND the proxy basis identically
- Seven-driver OOS re-validation: R^2 >= 0.95, VaR rel err <= 10% (unchanged Phase 22 gates)
- Action monotonicity preserved (construction guard re-verified on the inner-path basis)
- Outer-node vs inner-path capital delta disclosed; residual (full path-wise declaration) documented
- assumption_change ChangeRecord OWNER_REVIEW

**Task 4:**

- Joint-action tail diagnostics: with-vs-without and joint-vs-standalone deltas at VaR/ES/SCR for nested, t, gaussian, var-covar
- Var-covar understatement refreshed on the joint-action basis; MR-010/MR-014 notes refreshed
- Reproducibility: seeds, config, digests recorded; methodology_change ChangeRecord OWNER_REVIEW

**Task 5 plan:** Offline-UI propagation (ui_data.json contract 1.5.0 -> 1.6.0 ADDITIVE; joint-action panel) + PHASE 24 COMPLETE documentation; UI consumes ONLY model output JSON.

## 6. Limitations

- Joint anchoring V = L_fit + sum_k (Q_k - mean_k) is a first-order level approximation; cross-driver non-linearities beyond the action are not represented.
- Empirical margins from n_outer=160 realised losses are sampling-noisy; the joint read-out inherits this (disclosed; nested remains the reference).
- The synthetic pre-study proves the mechanism, not the magnitude, of the real-data improvement.
- Action parameters remain educational placeholders pending credentialled practice data + independent APS X2 review.

## 7. Standards

- Solvency II Delegated Reg. Art. 23 (future management actions: objective, realistic, verifiable; effect quantified)
- Solvency II Delegated Reg. Art. 234 (empirically justified diversification incl. tail behaviour)
- SOA ASOP 56 §3.1.3/§3.4/§3.5
- SOA ASOP 25 §3.3
- IA TAS M §3.2/§3.6
- IFoA Life Aggregation & Simulation working party
- McNeil-Frey-Embrechts 2015 ch.7
- Demarta-McNeil 2005

*Generated by scripts/build_phase24_task1_design_note.py — educational model; production sign-off withheld.*
