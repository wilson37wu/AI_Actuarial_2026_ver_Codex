# Phase 29 Task 1 - Design Note: Vine / Pair-Copula Dependence Upgrade

**Verdict: PASS** (design note + helper module). EDUCATIONAL ONLY.

## 0. Candidate selection

**Chosen:** truncated credit-root C-vine / pair-copula prototype (Aas et al. 2009). The first tree is rooted on credit; the second tree is conditioned on credit; the search is capped at two trees and four pair families: gaussian, student_t, survival_clayton, and survival_gumbel.

Rejected for this cycle:

- Full unrestricted R-vine: too many structure/family/parameter degrees of freedom for a single additive governed change.
- Adopt grouped-t down move: Phase 28 grouped-t diluted cross-block co-movement and moved SCR down; it is disclosed but not adopted into the governed headline.
- Credentialled-data calibration: still blocked on credentialled data and independent APS X2 review.

## 1. Problem

Phase 27 and Phase 28 are now two negative super-set results. The skew-t upper-tail scalar fitted to the standalone margins pinned near zero and left the copula-form residual at **6,114.9**. The grouped-t per-block df fit found no standalone within-carve-out tail concentration; it diluted cross-block co-movement, moved the disclosed component SCR down, and widened the residual to **10,491.5**.

MR-016 therefore cannot be treated as a single-copula parameter problem on standalone margins. The next governed escalation is a pair-copula construction that can localise conditional dependencies in the credit / FX / liquidity / action corner while preserving the frozen single-df t comparison leg.

Archived motivation:

- Nested path-wise reference: **46,638.9**
- Governed frozen-t component: **39,975.654628**
- Grouped-t point SCR: **35,604.4**
- Grouped-t bootstrap mean and CI: **35,372.5**, **[33,034.4, 38,008.5]**
- Grouped-t p=0.90 cross-block dilution: **-0.0871**
- Grouped-t df: NONFIN **37.866**, FIN **8.506**
- MR-016: **OPEN**

## 2. Method

Task 2 must implement only the envelope pre-registered here:

- Structure: `truncated_c_vine_credit_root`
- Root driver: credit
- First-tree edges: `[[2,6], [2,5], [2,0], [2,1], [2,3], [2,4]]`
- Second-tree edges: `[[6,5,2], [6,0,2], [5,1,2], [6,3,2], [6,4,2]]`
- Max trees: 2
- Family candidates: gaussian, student_t, survival_clayton, survival_gumbel

Margins, Sigma and homogeneous df stay frozen. The search uses a fit set for family/parameter selection and a disjoint holdout set for tail diagnostics. Single-df t and grouped-t comparison variants are retained on common random numbers. The `frozen_t_boundary` mode must be evaluated first and must reproduce the archived frozen-t component read-out before the candidate result is considered.

## 3. Synthetic mechanism pre-study

The helper module contains a deterministic synthetic pre-study. In this Windows shell, NumPy is unavailable, so the numerical pre-study was syntax-validated but not executed. The generated JSON therefore records static design-note evidence and the executable builder remains the source of truth for the normal Python-enabled automation environment.

The pre-study is scoped to prove only the design mechanism:

- A conditional pair-link shock can raise pre-registered credit / FX / liquidity tail-pair dependence more than unrelated holdout pairs.
- The zero-strength boundary recovers the frozen leg exactly.
- The real acceptance evidence is reserved for Tasks 2-4.

## 4. Acceptance criteria

**Task 2**

- Frozen boundary: reproduce frozen-t component **39,975.654628** before any vine computation; boundary max deviation <= **1e-9**.
- Rank invariance: Sigma max|diff| <= **1e-12**; homogeneous df remains **2.9451** within **1e-4**; standalone margins bit-identical.
- Implement only the pre-registered truncated credit-root C-vine envelope; no unrestricted structure search.
- Pair-family search limited to gaussian, student_t, survival_clayton, and survival_gumbel.
- Leakage control: family/parameter selection on fit rows only; holdout tail diagnostics reported separately.
- Retain single-df t and grouped-t comparison variants on common random numbers.
- Report candidate SCR direction vs frozen-t and grouped-t; direction disclosed, not gate-shopped.
- `code_change` ChangeRecord OWNER_REVIEW.

**Task 3**

- Vine margin bootstrap: at least **200 x 20,000**.
- HEADLINE: nested **46,638.9** inside the vine 95% CI OR residual re-decomposed with change vs grouped-t residual **10,491.5** and skew-t residual **6,114.9** quantified.
- Bootstrap SE <= **5%** of mean SCR.
- Common-random-number candidate minus frozen and candidate minus grouped-t differences reported with sign and confidence interval.
- Seeds/config/digests recorded; idempotent re-run digest-identical.
- `methodology_change` ChangeRecord OWNER_REVIEW.

**Task 4**

- Tail diagnostics: per-pair upper/lower tail dependence for first-tree and second-tree links, plus holdout pairs.
- Fit-vs-holdout overfit check: candidate must not improve fit-set tail pairs while degrading holdout residual disclosure silently.
- MR-016 remediation decision: close/mitigate only if residual materially shrinks and nested reference is inside CI; otherwise keep MR-016 OPEN and open MR-017 for remaining vine-form limitations if needed.
- MR-010/MR-014 refresh if candidate SCR moves more than **1%** from the governed frozen-t headline.
- Governance ChangeRecord OWNER_REVIEW; risk-register update idempotent.

**Task 5 plan:** Offline-UI propagation only after Tasks 2-4: additive contract **1.10.0 -> 1.11.0** with vine vs frozen vs grouped vs nested SCR, family selections, tail diagnostics, bootstrap CI, and MR-016 status.

## 5. Limitations

- This cycle is design-only; no vine capital figure is adopted.
- The synthetic pre-study demonstrates conditional-pair targeting and exact zero-strength boundary recovery, not real-data magnitude.
- A truncated credit-root C-vine may still be too simple for nested inner-path joint dynamics; failure is informative and must be disclosed.
- The family envelope is intentionally capped for governance; expanding it needs a new design note.
- Production sign-off remains blocked by credentialled data and independent APS X2 review.

## 6. Standards

- Aas, Czado, Frigessi & Bakken (2009), Pair-copula constructions of multiple dependence
- Bedford & Cooke (2002), Vines
- Solvency II Delegated Regulation Article 234
- Solvency II Delegated Regulation Article 23
- SOA ASOP 56 sections 3.1.3, 3.4, 3.5
- SOA ASOP 25 section 3.3
- IA TAS M sections 3.2, 3.6, 3.7

*Generated for Phase 29 Task 1. Educational model; production sign-off withheld.*
