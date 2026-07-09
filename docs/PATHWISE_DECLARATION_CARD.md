# Path-Wise Declaration Card (Phase 25 Task 2)

**What:** the governed reversionary-bonus cut is re-declared at EVERY inner
month from a path-wise coverage proxy; bonus restoration on recovering paths
and cuts on deteriorating paths are both captured (two-sided recognition
lag).

**Verdict:** PASS. Path-wise with-actions SCR 46638.9 vs horizon-level
40852.1 (delta +5786.8, +14.17% - sign gate PASS, magnitude disclosed).
Without-actions basis unchanged bit-identically.

**Carve-outs preserved:** only in-force policyholder benefits cuttable;
credit-loss and analytic FX/liquidity offsets are NOT cuttable.

**Diagnostics:** 41.4% of inner paths see a cut; 29.4% cut-then-
restore; mean initial path-wise CR 1.344.

**Residuals (Task 3):** monthly (not annual) declaration cadence;
perfect-foresight discounting in the coverage proxy; node offset undecayed.

**EDUCATIONAL MODEL** - parameters are placeholders; NOT for production
capital decisions. See PHASE25_TASK2_PATHWISE_DECLARATION_REPORT.md.

---

## Update — TVOG bridge (roadmap §4.1 #8, 2026-07-09)

The path-wise declaration work above (an SCR/VaR pre-study, RB only) is now
carried into a **TVOG** framing and **extended to the terminal bonus (TB)**.
The current→path-wise **TVOG bridge** is quantified in
`PATHWISE_TVOG_BRIDGE_CARD.md` (evidence
`docs/validation/PATHWISE_TVOG_BRIDGE.json`): on the risk-neutral
representative fund, path-wise RB+TB declaration **reduces** the TVOG by −7.99%
(hard guarantee) / −11.39% (declared benefit) vs the current horizon-level
convention — the mean-cost mirror of this card's tail-SCR result (path-wise
mean cost falls while the path-wise 99.5% tail rises; disclosed and
reconciled). Governed headline untouched; full cutover OWNER-GATED.
