# CBIRC 3.0% Discount-Cap Remediation (MR-002 / roadmap §4.1 #3)

**Document ID:** `CBIRC-DISCOUNT-CAP-REMEDIATION`
**Created:** 2026-07-09 (Claude Cowork continuous-improvement cycle)
**Maps to:** Model-risk register `MR-002`; roadmap backlog §4.1 item #3
**Standards:** CBIRC C-ROSS reserve valuation (2023) · SOA ASOP 56 §3.5 · IA TAS M §3.5

---

## 1. Problem

The CBIRC 2023 reserve-valuation circular caps the guaranteed valuation
(reserving) discount rate for CNY participating business at **3.0%**. The model
default was already lowered from the legacy 3.5% to the 3.0% cap under **MR-001**
(`par_model_v2/projection/monthly_projection.py :: DEFAULT_RESERVING_DISCOUNT_RATE`).

The gap that remained: the input validator (`DiscountRateValidator`) flagged a
rate **above** the cap only as a **WARNING**. A warning does not fail validation
(`ValidationReport.passed` ignores warnings), so nothing stopped a run from using
an above-cap reserving rate — the "deviation record for any override" required by
the backlog item was not *enforced*.

## 2. Remediation

The CBIRC-cap checks are now a **hard ERROR** unless an **APPROVED deviation
ChangeRecord** authorises the specific override, in which case they are
downgraded to a **governed WARNING**.

| Situation | Severity | `report.passed` |
|---|---|---|
| rate ≤ 3.0% cap | check passes | `True` |
| rate > cap, **no** approved deviation | **ERROR** | **`False`** (hard stop) |
| rate > cap, **approved** deviation on record | WARNING | `True` (governed, flagged) |

Applies to both validator entry points:
- `D3-R01` — scalar reserving rate
- `D3-R03` — term-structure rates (each above-cap tenor must be authorised)

## 3. What "approved deviation" means

`discount_rate_deviation_approved(records, rate, cap=0.030)` (in
`par_model_v2/validation/data_validator.py`) returns `True` only when the
governance store holds a ChangeRecord that is:

1. **APPROVED** — fully through the IA TAS M §3.5 three-stage sign-off
   (DRAFT → PEER_REVIEW → OWNER_REVIEW → APPROVED); and
2. an **`assumption_change`**; and
3. carries `after_snapshot["discount_rate_annual"]` **strictly above the cap**
   and **equal (to 1e-9) to the rate being validated**.

The exact-rate match means every distinct above-cap override must be signed off
explicitly — an approval for one rate never licences another. The MR-001 record
(which lowered the default *to* 3.0%) has an after-snapshot equal to the cap, so
it never authorises operating above it.

`records` is duck-typed: pass a `GovernanceStore` (its `.change_records` are
used) or any iterable of ChangeRecord-like objects. This keeps the validation
layer free of a hard governance import.

## 4. Public API

```python
from par_model_v2.validation import (
    DiscountRateValidator,
    discount_rate_deviation_approved,
    validate_all,
)

# Explicit flag (caller has already established sign-off):
report = DiscountRateValidator().validate(0.035, approved_deviation=True)

# Governance-driven (validator consults the store):
report = DiscountRateValidator().validate(0.035, governance=store)

# Aggregate entry point:
full = validate_all(discount_rate=0.035,
                    discount_rate_approved_deviation=False,   # default -> ERROR
                    governance_store=store)                    # or auto-check
```

Default behaviour (`approved_deviation=False`, `governance=None`) is the safe
one: an above-cap rate is an **ERROR**.

## 5. Governed-figure impact

**None.** No governed run path uses a reserving rate above 3.0% (the default is
the 3.0% cap), so headline TVOG and the aggregation report are byte-unchanged.
The change only *strengthens* the guard on out-of-policy overrides. Re-baselining
any headline onto an above-cap rate would itself require an approved deviation
record and remains owner-gated.

## 6. Tests

- `tests/test_mr002_discount_cap_remediation.py` — 22 tests (unittest): scalar &
  term-structure severity switching, the approval helper (APPROVED vs DRAFT,
  exact-rate match, at-cap non-authorisation, wrong change-type, store input),
  `validate_all` threading, and an end-to-end real-`GovernanceStore` approval.
- `tests/test_data_validator.py` — updated: above-cap without approval is an
  ERROR that fails the report; with approval it is a governed WARNING.
- `tests/test_phase13_mr001_discount_rate.py` — updated: the legacy 3.5% rate is
  now a hard ERROR by default; a WARNING only under an approved deviation. The
  MR-001 **G-01 gate** (default 3.0%, no CBIRC warning) still PASSES.
