# Vine / Pair-Copula Dependence Upgrade - Design Card (Phase 29)

**Verdict: PASS**. EDUCATIONAL ONLY.

## What changes

Phase 29 selects a truncated credit-root C-vine / pair-copula prototype. The implementation must keep standalone margins, Sigma and homogeneous df frozen, and must evaluate an explicit `frozen_t_boundary` leg before any candidate vine result.

## Why

- Skew-t residual remained **6,114.9**: the upper-tail scalar pinned near zero.
- Grouped-t residual widened to **10,491.5**: per-block df diluted cross-block co-movement.
- Grouped-t moved SCR down (**35,604.4** point; bootstrap mean **35,372.5**) and is disclosed but not adopted into the governed headline.
- MR-016 remains OPEN; mitigation path is conditional pair dependence via a governed vine prototype.

## Pre-registered envelope

- Structure: truncated credit-root C-vine
- Root: credit
- First tree: credit-liquidity, credit-fx, credit-rate, credit-equity, credit-lapse, credit-mortality
- Second tree: liquidity-fx | credit, liquidity-rate | credit, fx-equity | credit, liquidity-lapse | credit, liquidity-mortality | credit
- Max trees: 2
- Pair families: gaussian, student_t, survival_clayton, survival_gumbel

## Gates

- Frozen-t component **39,975.654628** reproduced before vine computation; boundary tolerance **1e-9**.
- Sigma frozen to **1e-12** and homogeneous df **2.9451** preserved within **1e-4**.
- Leakage-free fit/holdout selection; retain frozen single-df t and grouped-t comparison variants.
- Bootstrap at least **200 x 20,000**; SE <= **5%**.
- MR-016 may be mitigated only if residual materially shrinks and nested **46,638.9** is inside the candidate CI; otherwise MR-016 stays open and MR-017 may be opened for remaining vine-form limitations.

## Out of scope

- No unrestricted R-vine search in this phase.
- No capital figure is adopted in Task 1.
- Production sign-off remains withheld pending credentialled data and independent APS X2 review.

*Generated for Phase 29 Task 1. Educational model; production sign-off withheld.*
