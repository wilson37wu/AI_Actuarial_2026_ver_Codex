# Phase 25 Task 1 — Design Note: Full Path-Wise Bonus Declaration Dynamics

**Verdict: PASS** (design note + tested helper module + synthetic recognition-lag pre-study). EDUCATIONAL ONLY.

## 0. Candidate selection (design-note-first discipline)

**Chosen:** full path-wise bonus declaration dynamics (P24T3 documented residual).

- t-copula on the inner-path basis: DEFERRED to a later phase: Task 2 of THIS phase changes the with-actions basis (horizon-level -> path-wise); running the copula re-aggregation on the inner-path basis now would produce evidence superseded within one phase. Sequencing the basis refinement first avoids duplicated copula benchmarks.
- Credentialled-data calibration: BLOCKED on credentialled management-practice data (standing human-action blocker); not executable from the sandbox. Remains the production sign-off residual by design.

## 1. Problem

Phase 24 Task 3 moved the governed bonus-cut rule into the inner-path benefit cashflows, but the DECISION remains horizon-level: the pre-action outer-node coverage ratio fixes ONE retained-bonus factor that is constant across all inner paths and all time steps of that node (documented residual). A real par-fund board re-declares the reversionary bonus at every declaration date on the fund's CURRENT solvency position: after a cut, recovering paths see the bonus (partially) restored; after a healthy start, deteriorating paths see a cut the horizon-level basis never applies. The horizon-level approximation therefore mis-states the with-actions liability in both directions (recognition lag), and the sign at the capital-relevant 99.5% tail is an UNDERSTATEMENT: stressed nodes keep maximum relief for the whole projection while the path-wise truth restores bonus on recovering paths.

Archived Phase 24 Task 3 motivation figures (NOT consumed by gates): {"nested_scr_without": 55561.1889, "nested_scr_with_outer_node": 39290.8985, "nested_scr_with_inner_path": 40852.0541, "active_share_nested": 0.442, "floor_share_nested": 0.08}

## 2. Method — path-wise declaration (Tasks 2-3)

Extend par_model_v2/projection/inner_path_action_dynamics.py with a path-wise declaration mode: at each inner time step t, the retained-bonus factor is re-evaluated as retained(CR_t) where CR_t is a path-wise coverage proxy (reference assets rolled forward on the inner path / pre-action path liability at t), using the UNCHANGED governed ManagementActionRule shape (trigger/floor/PRE floor; same monotonicity guard). Only in-force policyholder benefits remain cuttable (P24T3 carve-outs preserved: credit loss + analytic FX/liquidity offsets are NOT cuttable). The horizon-level basis is RETAINED as the comparison/sensitivity variant (P24T3 convention), exactly as the superseded scalar-response variant was retained in Phase 24. The LSMC proxy gains the matching path-wise post-composition basis feature so truth and proxy share an IDENTICAL action basis (G1 convention), then seven-driver OOS re-validation at the unchanged Phase 22 gates.

**Hypothesis:** Path-wise declaration relieves LESS capital than the horizon-level basis at the 99.5% tail (bonus restoration on recovering paths), so the path-wise with-actions SCR is HIGHER than the P24T3 inner-path horizon-level reference (40,852.1); the synthetic pre-study sign carries over.

## 3. Pre-study (synthetic recognition-lag mechanism)

- Synthetic fund: lognormal assets mu=0.05, sigma=0.15; g=0.02, target bonus=0.02; n_outer=4,000, n_inner=100, n_steps=10, seed=42
- VaR99.5 conditional net loss: without 21.38; horizon-level 12.36; path-wise 14.07; max-cut bound 12.36 (per 100 initial liability)
- Horizon-level UNDERSTATES the path-wise tail loss by 12.2% at VaR99.5
- Path-wise action share 82.0%; cut-then-RESTORED share 69.8% (restoration is a real dynamic)
- Median path-wise minus horizon-level diff -1.51 (healthy nodes: path-wise cuts MORE — the lag effect is two-sided)
- understatement_sign_ok=True; relief_ordering_ok=True; bounds_ok=True; digest=cbc0ab270b75e4a376763911471bbeb91a37d294c0c14a976ea8f2365943eb2e

The pre-study uses a SYNTHETIC single-fund participating product (reversionary bonus attaching to the liability, common-random-number asset paths) so that no real archived nested benchmark is consumed before the Task 2 gates: it demonstrates the recognition-lag MECHANISM (horizon-level basis understates the path-wise with-actions tail loss by 12.2% at VaR99.5 on the synthetic fund; bonus cut-then-restoration occurs on 69.8% of inner paths; on healthy nodes the median path-wise minus horizon-level difference is -1.51 per 100 of initial liability, i.e. the lag effect is two-sided), not the magnitude of the real-data effect.

## 4. Gap analysis (standards vs current model)

### Solvency II Del. Reg. Art. 23 (management actions)

- **Requirement:** Management actions allowed for only if consistent with how they would actually be exercised: bonus declarations are made at every declaration date on the then-current solvency position, including restorations.
- **Current state:** P24T3 inner-path basis: cut enters the inner cashflows but the decision is frozen at the outer node; no restoration on recovering paths, no cut on deteriorating paths from healthy nodes.
- **Gap:** Declaration timing is inconsistent with exercise practice; synthetic pre-study sign: horizon-level basis UNDERSTATES the with-actions tail loss.
- **Phase 25 design:** Task 2 path-wise declaration in the nested truth; gates pre-registered in this note (s5); horizon-level basis retained as sensitivity evidence.

### SOA ASOP 56 §3.1.3/§3.4 (model structure; assumptions supportable)

- **Requirement:** Model structure appropriate to purpose, including the TIME LEVEL at which management behaviour enters the model.
- **Current state:** Action decision is per-outer-node (annual horizon); inner-path declared rate cannot respond to the path.
- **Gap:** Recognition lag unmodelled; TVOG interaction of declaration dynamics unmeasured.
- **Phase 25 design:** Task 3: matching path-wise proxy basis feature + OOS re-validation R^2 >= 0.95, VaR rel err <= 10% (unchanged Phase 22 gates); TVOG read-out disclosed.

### IA TAS M §3.2/§3.6 (limitations disclosed; evidence reproducible)

- **Requirement:** Material limitations disclosed; validation evidence reproducible with recorded config.
- **Current state:** P24T3 residual disclosed verbatim in the report, the risk register and the offline UI; no quantification exists.
- **Gap:** Residual is described but not quantified; materiality unknown.
- **Phase 25 design:** Task 4: pathwise-vs-horizon and with-vs-without capital deltas at VaR/ES/SCR for all four benchmarks; MR-010/MR-014 refresh if the SCR delta exceeds the 1% disclosure threshold; seeds/config/digests recorded.

### Solvency II Del. Reg. Art. 234; IFoA Aggregation WP (tail dependence)

- **Requirement:** Dependence assumptions justified on the basis actually used for capital; copula must not silently re-tune when the action basis changes.
- **Current state:** df=2.9451 tail-matched on WITHOUT-actions losses (P23T2); P24T2 joint-action mechanism validated on the outer-node basis.
- **Gap:** If the path-wise basis becomes the with-actions reference, the joint-action copula read-outs must be re-anchored WITHOUT re-tuning the dependence parameters.
- **Phase 25 design:** Task 4 rank-invariance check: df re-matched on the without-actions staged losses unchanged at 2.9451; copula parameters frozen; the t-copula-on-new-basis full re-aggregation is the documented NEXT-phase candidate.

## 5. Acceptance criteria (FIXED, pre-registered — no gate-shopping)

**Task 2:**

- Path-wise declaration in the nested truth: retained-bonus factor re-evaluated at every inner time step from a path-wise coverage proxy; UNCHANGED governed rule shape (trigger/floor/PRE; monotonicity guard re-verified on the path-wise basis)
- P24T3 carve-outs preserved: only in-force policyholder benefits cuttable (credit loss + analytic FX/liquidity offsets NOT cuttable)
- Sign gate (pre-registered): path-wise with-actions SCR >= horizon-level inner-path with-actions SCR at 99.5% (bonus restoration relieves LESS in the tail); magnitude DISCLOSED, not gated
- Horizon-level basis retained and reported alongside as the sensitivity variant; without-actions basis unchanged bit-identically (archive cross-check BEFORE any new computation)
- No gate-shopping: these gates fixed in this Task 1 note before any real-data path-wise benchmark
- assumption_change ChangeRecord OWNER_REVIEW

**Task 3:**

- Identical path-wise action basis in nested truth AND proxy (matching post-composition basis feature)
- Seven-driver OOS re-validation: R^2 >= 0.95, VaR rel err <= 10% (unchanged Phase 22 gates)
- Action monotonicity preserved (construction guard re-verified on the path-wise basis)
- Pathwise-vs-horizon capital delta disclosed at VaR/ES/SCR; residual (declaration frequency vs inner step size; board discretion smoothing) documented
- code_change/assumption_change ChangeRecord OWNER_REVIEW

**Task 4:**

- Tail diagnostics on the path-wise basis: with-vs-without and pathwise-vs-horizon deltas at VaR/ES/SCR for nested, t, gaussian, var-covar
- MR-010/MR-014 refreshed if |pathwise - horizon| SCR delta > 1% of the horizon-basis SCR (disclosure trigger, not a pass/fail gate)
- Rank invariance: df re-matched on WITHOUT-actions staged losses unchanged at 2.9451; copula parameters frozen (no silent re-tuning)
- Reproducibility: seeds, config, digests recorded; methodology_change ChangeRecord OWNER_REVIEW

**Task 5 plan:** Offline-UI propagation (ui_data.json contract 1.6.0 -> 1.7.0 ADDITIVE; path-wise declaration panel: pathwise-vs-horizon delta matrix, restoration-share diagnostics, gates) + PHASE 25 COMPLETE documentation; UI consumes ONLY model output JSON.

## 6. Limitations

- The synthetic pre-study proves the mechanism and its SIGN, not the magnitude, of the real-data effect (single fund, lognormal assets, bonus attaching to liability).
- Path-wise coverage proxy on the inner paths is itself an approximation (reference assets rolled forward analytically; no inner rebalancing).
- Declaration frequency is tied to the inner step size; real boards declare annually with smoothing/discretion - documented residual for the design.
- Action parameters remain educational placeholders pending credentialled practice data + independent APS X2 review.

## 7. Standards

- Solvency II Delegated Reg. Art. 23 (future management actions: objective, realistic, verifiable; consistent with how they would be exercised over time)
- Solvency II Delegated Reg. Art. 234 (empirically justified diversification incl. tail behaviour)
- SOA ASOP 56 §3.1.3/§3.4/§3.5
- SOA ASOP 25 §3.3
- IA TAS M §3.2/§3.6
- IFoA Life Aggregation & Simulation working party
- CFO Forum MCEV Principle 7 (TVOG; dynamic management actions)

*Generated by scripts/build_phase25_task1_design_note.py — educational model; production sign-off withheld.*
