# Phase 23 Task 1 — Design Note: t-Copula Tail-Dependence Calibration + Management Actions

**Verdict: PASS** (design note + tested helper module + numerical pre-study). EDUCATIONAL ONLY.

## 1. Problem

The AIC-selected copula aggregation (Phases 18-22) repeatedly pins the Student-t df at the
grid cap, collapsing to a Gaussian with ZERO asymptotic upper-tail dependence, while realised
capital-loss co-movement is strongly positive in the tail (MR-010 residual). Phase 22 Task 4:
copula SCR rel err vs nested 0.14583332565245183; var-covar understatement
0.40479539899136663. Management actions are entirely unmodelled (ERM gap).

## 2. Method A — df by tail-dependence matching (Task 2)

lambda_U(nu, rho) = 2 * t_{nu+1}(-sqrt((nu+1)(1-rho)/(1+rho)))  (Demarta-McNeil 2005)

Estimate empirical pairwise lambda_U on realised losses (threshold estimator, pseudo-obs);
invert for nu per pair (bisection on the df interval; bounds DISCLOSED when hit); pool by the
MEDIAN pair df. Implemented and tested in `par_model_v2/projection/tail_dependence.py` (21 tests).

### Pre-study (numerical feasibility)

- Truth: t-copula df=4, rho=0.6, closed-form lambda_U=0.314373, n=150,000, seed=42
- df recovery by threshold: {"0.97": {"pooled_df": 2.851, "capped_share": 0.0, "lambda_hat": 0.381111}, "0.98": {"pooled_df": 3.014, "capped_share": 0.0, "lambda_hat": 0.37}, "0.99": {"pooled_df": 3.219, "capped_share": 0.0, "lambda_hat": 0.356667}}
- Gaussian control (rising-df signature): {"0.99": 7.473, "0.995": 9.496, "0.999": 13.201}
- Conclusion: df-by-tail-dependence matching recovers a heavy-tail df (true 4) to the right order of magnitude across thresholds, while a Gaussian control shows the documented RISING-df signature (finite-threshold bias decays as q->1). Feasible for Task 2; threshold sensitivity MUST be reported with the calibrated df.

## 3. Method B — management-action rule (Task 3)

Dynamic reversionary-bonus participation cut under solvency stress:
`cut_factor = clip((CR - CR_floor) / (CR_trigger - CR_floor), 0, 1)` on the participating
bonus share, CR = asset/liability coverage proxy at the outer node. Objective, verifiable,
monotone — per Solvency II Art. 23. Enters nested conditional liability AND proxy basis;
seven-driver OOS re-validation at the Phase 22 gates.

## 4. Gap analysis (standards vs current model)

### Solvency II Del. Reg. Art. 23; ERM management-action-risk (standing prompt)

- **Requirement:** Future management actions may be allowed for only if objective, realistic, verifiable and consistent with current practice; their effect must be quantified.
- **Current state:** NO management actions anywhere in the nested ground truth or proxy: reversionary-bonus participation is STATIC; the liability does not respond to solvency stress.
- **Gap:** Management-action risk is listed as an ERM coverage requirement in the standing prompt but is unmodelled; nested tail capital is overstated relative to a realistic with-management-action basis.
- **Phase 23 design:** Task 3: dynamic reversionary-bonus participation cut: cut_factor(t)=clip((CR(t)-CR_floor)/(CR_trigger-CR_floor),0,1) applied to the participating bonus share, where CR is an asset/liability coverage-ratio proxy at the outer node; enters the nested conditional liability AND the proxy basis; OOS re-validation gate R^2>=0.95, VaR rel err<=10%.

### SOA ASOP 56 §3.1.3/§3.4

- **Requirement:** Model structure and assumptions (incl. policyholder/management behaviour) appropriate to the intended purpose; assumptions documented and supportable.
- **Current state:** Dynamic LAPSE behaviour modelled (Phase 18); management behaviour not modelled.
- **Gap:** Asymmetry: policyholder options are modelled, insurer options are not — biases the guarantee cost (TVOG) and tail capital upward.
- **Phase 23 design:** Document the action rule as an explicit assumption (assumption_change ChangeRecord); educational trigger/floor parameters with disclosed placeholders; sensitivity to trigger level reported.

### IA TAS M §3.2/§3.6

- **Requirement:** Material model limitations disclosed; validation evidence reproducible.
- **Current state:** Gaussian-copula aggregation disclosed as zero-tail-dependence limitation (MR-010 residual); management-action omission NOT yet on the risk register.
- **Gap:** Risk register lacks an explicit management-action-omission entry.
- **Phase 23 design:** Task 3 governance: open MR-013 (management-action omission) at IN_PROGRESS, MITIGATED on PASS evidence; seed/threshold/config recorded for reproducibility.

### Solvency II Del. Reg. Art. 234; IFoA Life Aggregation & Simulation WP

- **Requirement:** Diversification dependence assumptions must be empirically justified, including tail behaviour.
- **Current state:** Copula-on-realised-losses selected by AIC; Student-t df repeatedly pinned at grid cap -> Gaussian-equivalent; lambda_U effectively 0 while realised tail co-movement is strongly positive.
- **Gap:** AIC on full-sample pseudo-observations is dominated by the body of the distribution; the TAIL is not the selection criterion.
- **Phase 23 design:** Task 2: calibrate df by TAIL-DEPENDENCE MATCHING (par_model_v2/projection/tail_dependence.py): empirical pairwise lambda_U on realised losses at q in {0.95,0.975,0.99}; invert lambda_U(nu,rho) per pair; pooled MEDIAN df; report capped-share + threshold sensitivity; benchmark t(df_matched) vs gaussian vs nested; acceptance: t-copula rel err <= gaussian baseline OR <=25%, with lambda_U disclosed.

## 5. Acceptance criteria

**Task 2:**

- Empirical pairwise lambda_U on realised seven-driver standalone losses at >=3 thresholds
- Pooled df by median pairwise inversion; capped-share disclosed; threshold sensitivity table
- t(df_matched) copula SCR vs gaussian vs nested: rel err <= gaussian baseline or <= 25%
- No gate-shopping: selection criterion (tail matching) fixed BEFORE seeing benchmark errors
- MR-010 refresh + methodology_change ChangeRecord OWNER_REVIEW

**Task 3:**

- Action rule monotone: bonus cut non-decreasing as coverage ratio falls; no action above trigger
- Nested-with-actions capital <= nested-without-actions capital (sanity, documented)
- Seven-driver OOS re-validation: R^2 >= 0.95, VaR rel err <= 10% (Phase 22 gates)
- MR-013 opened; assumption_change ChangeRecord; trigger/floor sensitivity reported

## 6. Limitations

- Finite-threshold lambda_U estimators are sampling-noisy and biased upward under the Gaussian null (rising-df signature is the diagnostic, demonstrated in the pre-study).
- A single pooled df imposes exchangeable tail strength across all 21 driver pairs; pairwise capped-share is the disclosure.
- Management-action parameters (trigger/floor/cut depth) are educational placeholders pending credentialled practice data + APS X2 review.

## 7. Standards

- SOA ASOP 56 §3.1.3/§3.4/§3.5
- SOA ASOP 25 §3.3
- IA TAS M §3.2/§3.6
- Solvency II Delegated Reg. Art. 23 (future management actions)
- Solvency II Delegated Reg. Art. 234 (empirically justified diversification)
- Solvency II Delegated Reg. Art. 236
- IFoA Life Aggregation & Simulation working party
- Demarta-McNeil 2005
- McNeil-Frey-Embrechts 2015 ch.7
- Schmidt-Stadtmueller 2006

*Generated by scripts/build_phase23_task1_design_note.py — educational model; production sign-off withheld.*
