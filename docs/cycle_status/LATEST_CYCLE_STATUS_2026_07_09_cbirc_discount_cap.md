# Cycle Status — 2026-07-09 — #3 CBIRC 3.0% Discount-Cap Remediation (MR-002)

**Agent:** Claude Cowork (`actuarial-model-daily-improvement`)
**Lock:** cycle_id `2026-07-09T10:12Z-095f`, owner `claude`
**Item:** roadmap §4.1 #3 — CBIRC 3.0% discount-cap remediation → **DONE**
**Priority basis:** highest-priority OPEN backlog item (regulatory gate > model-risk > accuracy > capability); track 4.0f (ES-1..3) completed the prior cycle, so priority reverted to §4.1.

## Lock provenance (noteworthy)
origin/main HEAD on entry was an **unreleased same-owner `acquire` for this exact item** (two `acquire [claude] #3 CBIRC` commits, `79750ec`+`d6e3797`, started 2026-07-08T23:20:42Z, TTL 120 min) with **no following work commit** — a prior claude cycle acquired the lock for #3 and crashed before producing any code (double-acquire is the mid-cycle VM-restart tell). The lock had expired ~9 h earlier, so it was **stale and reclaimable** per `AGENT_COORDINATION.md §2`. `agent_lock.py preflight --owner claude` returned `PROCEED`; re-acquired cleanly. (The standing "same-owner ⇒ yield" caution applies to *non-expired* same-owner locks that signal a live concurrent cycle; this one was long-expired, so reclaiming was correct.) Confirmed #3 genuinely unimplemented on origin before proceeding (D3-R01/D3-R03 still WARNING, helper absent, status OPEN).

## What changed
- `par_model_v2/validation/data_validator.py`
  - CBIRC-cap checks **D3-R01** (scalar) and **D3-R03** (term structure) now
    carry **ERROR** severity when the rate exceeds 3.0% and no approved deviation
    exists — so `ValidationReport.passed` becomes `False` (hard stop). With an
    approved deviation they degrade to a governed **WARNING** (report passes).
  - New module helper `discount_rate_deviation_approved(records, rate, cap=0.030)`
    — duck-typed over a `GovernanceStore` or any ChangeRecord-like iterable;
    recognises a deviation only for an **APPROVED** `assumption_change` record
    whose `after_snapshot["discount_rate_annual"]` is strictly above the cap and
    equal (1e-9) to the validated rate.
  - `DiscountRateValidator.validate(...)` gains `approved_deviation` and
    `governance` params; `validate_all(...)` gains
    `discount_rate_approved_deviation` and auto-consults `governance_store`.
  - Helper exported via `__all__` and `par_model_v2/validation/__init__.py`.
- `docs/CBIRC_DISCOUNT_CAP_REMEDIATION.md` — new remediation card.
- Tests:
  - **NEW** `tests/test_mr002_discount_cap_remediation.py` — 22 tests (unittest).
  - Updated `tests/test_data_validator.py` (legacy-rate case → ERROR without
    approval, WARNING with) and `tests/test_phase13_mr001_discount_rate.py`
    (legacy rate ERROR by default; WARNING under approval).

## Tests run
- `python -m unittest tests.test_mr002_discount_cap_remediation` → **22/22 GREEN**.
- Fixture-free affected pytest-file tests via a minimal pytest shim
  (`TestDiscountRateValidatorScalar`, `TestDiscountRateValidatorTermStructure`,
  phase13 discount functions) → **32/32 GREEN**.
- Integration: `model_health` 0.025 path clean (0 errors); MR-001 **G-01 gate**
  still **PASS** at the 3.0% default.
- Sandbox is network-restricted: `pytest`/`scipy` unavailable, so the broad
  pytest suite was not collected — verified via the numpy/pandas subset + shim.

## Governed-figure impact
None. No run path uses a reserving rate above 3.0%; headline TVOG / aggregation
report byte-unchanged. Re-baselining a headline onto an above-cap rate stays
owner-gated (would itself need an approved deviation record).

## Next queued
§4.1 #4 — Dynamic lapse: rate-differential lapse response with bounded elasticity
+ sensitivity tests (TVOG delta quantified).
