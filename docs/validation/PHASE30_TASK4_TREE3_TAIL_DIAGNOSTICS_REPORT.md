# Phase 30 Task 4 — Tree-3 Vine Tail Diagnostics + Binding Stop-Rule / MR Decision

**Verdict: PASS** — 200 replicates × 20000 sim re-drawn at the archived Task 3 seeds; copula + P29T2 2-tree fit + P30T2 tree-3 selections FROZEN (df 2.9451). EDUCATIONAL ONLY.

## Archive cross-check (T4-G1)

- Task 2 read-outs (200k, seed 20260607): frozen-t **39975.654628**, 2-tree vine **42458.552710** and tree-3 candidate **42458.552710** reproduced bit-identically (zero-strength contract: tree-3 == vine-2).
- Task 3 bootstrap reproduction: per-replicate max abs dev 0.0e+00; aggregate (mean/CI/min/max) max abs dev 0.0e+00; uniform bit-identity max |U_t3 - U_v2| = 0.0e+00 across all 200 replicates.

## Pair-level tail diagnostics at the canonical p = 0.90 (T4-G2)

Candidate vs frozen-t boundary on CRN; mean over 200 replicates (95% CI in the JSON report; grid p ∈ {0.80, 0.85, 0.90, 0.95}). Tree-3 rows are conditional on the JOINT upper tail of both pre-registered conditioners.

| link | type | cand λU | frz λU | lift λU | cand λL | frz λL | lift λL |
|---|---|---|---|---|---|---|---|
| credit-liquidity | tree 1 | 0.3172 | 0.2553 | +0.0619 | 0.2687 | 0.2541 | +0.0146 |
| credit-fx | tree 1 | 0.1539 | 0.1445 | +0.0093 | 0.1448 | 0.1432 | +0.0016 |
| rate-credit | tree 1 | 0.7761 | 0.7187 | +0.0574 | 0.7194 | 0.7182 | +0.0012 |
| equity-credit | tree 1 | 0.4901 | 0.4570 | +0.0331 | 0.4578 | 0.4554 | +0.0024 |
| credit-lapse | tree 1 | 0.2622 | 0.2314 | +0.0308 | 0.2348 | 0.2313 | +0.0035 |
| credit-mortality | tree 1 | 0.2033 | 0.1913 | +0.0120 | 0.1927 | 0.1911 | +0.0016 |
| fx-liquidity|credit | tree 2 | 0.4480 | 0.3822 | +0.0658 | 0.1585 | 0.3071 | -0.1485 |
| rate-liquidity|credit | tree 2 | 2.4778 | 1.6329 | +0.8449 | 0.0024 | 0.0036 | -0.0012 |
| equity-fx|credit | tree 2 | 0.8144 | 0.7097 | +0.1047 | 0.0932 | 0.1145 | -0.0213 |
| lapse-liquidity|credit | tree 2 | 0.9021 | 0.6186 | +0.2835 | 0.1289 | 0.2177 | -0.0888 |
| mortality-liquidity|credit | tree 2 | 0.8621 | 0.6706 | +0.1915 | 0.2269 | 0.3596 | -0.1326 |
| rate-fx|credit,liquidity | tree 3 | 1.1251 | 0.9672 | +0.1579 | 0.0164 | 0.0344 | -0.0180 |
| rate-lapse|credit,liquidity | tree 3 | 2.3619 | 1.6573 | +0.7046 | 0.0132 | 0.0312 | -0.0180 |
| lapse-mortality|credit,liquidity | tree 3 | 0.9898 | 0.8288 | +0.1610 | 0.4401 | 0.5949 | -0.1548 |
| equity-liquidity|credit,fx | tree 3 | 1.9868 | 1.6473 | +0.3395 | 0.2619 | 0.3182 | -0.0563 |
| rate-equity | HOLDOUT | 0.4783 | 0.4371 | +0.0412 | 0.4382 | 0.4362 | +0.0020 |
| lapse-mortality | HOLDOUT | 0.2234 | 0.2177 | +0.0058 | 0.2138 | 0.2170 | -0.0032 |
| rate-lapse | HOLDOUT | 0.2592 | 0.2260 | +0.0332 | 0.2293 | 0.2262 | +0.0031 |

## Fit-vs-holdout overfit check (T4-G3)

- Holdout disclosure complete: **True** (3 pairs, upper+lower, 95% CI at every level).
- Concentration: max holdout |mean lift| 0.0412 ≤ max fitted-pair |mean lift| 0.8449 (ratio 0.049; P29 reference 0.049): **True**.
- Tree-3 joint-conditional fit support (n_fit per pre-registered pair): [3, 3, 3, 1] — all four selections zero strength: **True** (the candidate tail field is exactly the 2-tree vine's).

## Binding stop-rule / MR decision (T4-G4) + MR-010/MR-014 refresh (T4-G5)

- Nested 46638.9 inside the Task 3 tree-3 95% CI [38593.7, 44556.4]: **NO**.
- Copula-form residual 3637.3 strictly below the 2-tree vine residual 3637.3: **NO** (residual UNCHANGED — bit-identity).
- Pre-registered mitigation criteria met: **False** → **MR-016 KEEP_OPEN / MR-017 KEEP_OPEN**.
- **STOP-RULE APPLIED: True** — dependence-FORM escalation under MR-016 **ENDS**; no further copula-structure candidates without owner sign-off.
- GOVERNED headline (frozen single-df t 39975.65) move: +0.0000% ≤ 1% → **MR-010/MR-014 refresh: NOT required** (nothing adopted without owner sign-off).

### Phase 31 directive

Phase 31 = OWNER DECISION PACKAGE (design-note option C): consolidated read-out of the governed frozen-t headline 39,975.7, the disclosed 2-tree vine / tree-3 candidate 42,458.6, the nested reference 46,638.9 and the quantified residual 3,637.3, for an owner adoption / escalation / accept decision. Option B (nested-aware dependence calibration) remains available ONLY as an owner-approved escalation funding a second independent nested run.

The pre-registered mitigation criteria require BOTH nested 46638.9 INSIDE the tree-3 95% bootstrap CI [38593.7, 44556.4] AND a STRICT residual improvement below the 2-tree vine residual 3637.3. Neither holds: the tree-3 candidate is bit-identical to the 2-tree vine (all four pre-registered third-tree pairs zero strength under n_fit <= 3 joint-conditional support), so the residual is UNCHANGED, and nested remains OUTSIDE the CI. MR-016 and MR-017 KEEP OPEN and the STOP-RULE IS APPLIED: dependence-FORM escalation under MR-016 ENDS (no further copula-structure candidates without owner sign-off); Phase 31 is the owner decision package. The GOVERNED headline remains the frozen single-df t 39975.7 (recovered bit-identically, move 0.0000%), so MR-010/MR-014 quantifications are unchanged.

## Gates

- T4_G1_archive_crosscheck_bit_identical: PASS
- T4_G2_pair_tail_grid_complete: PASS
- T4_G3_fit_vs_holdout_overfit_check: PASS
- T4_G4_stop_rule_mr_decision_per_preregistered_criteria: PASS
- T4_G5_mr010_mr014_no_refresh: PASS
- T4_G6_zero_strength_bit_identity_and_digest: PASS

- Tail-diagnostics digest: `9e10a3b86332`

*Generated by scripts/build_phase30_task4_tree3_tail_diagnostics.py.*
