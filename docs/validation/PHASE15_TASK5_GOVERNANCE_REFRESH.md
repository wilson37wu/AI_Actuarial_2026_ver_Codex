# Phase 15 Task 5 — Multi-Driver Economic-Capital Proxy Governance Refresh

**Task:** Refresh governance for the multi-driver proxy — model-limitation card,
ChangeRecord, MR-register update; document model-use restrictions and the remaining
credentialled-data / independent-review residual. **Completes Phase 15.**

**Run:** `PYTHONPATH=. python3 scripts/build_phase15_task5_governance.py --governance`
(idempotent — re-running does not duplicate MR-011 or the ChangeRecord).

## What was done

1. **Consolidated limitation card** — `docs/MULTI_DRIVER_PROXY_LIMITATION_CARD.md`
   gathers the four Phase 15 multi-driver capital modules (Tasks 1–4) into a single
   governance reference: validated scope/evidence, limitations, model-use
   restrictions, and the residual-risk table.
2. **MR-011 opened** — *"Multi-driver economic-capital proxy is educational, not
   production capital"* (category model_error; likelihood MEDIUM × impact HIGH →
   overall **HIGH**; status **IN_PROGRESS**). Formalises the educational-only
   classification, the placeholder calibration, the omitted risk drivers, and the
   no-independent-review residual; links to MR-006 / MR-008 / MR-010.
3. **ChangeRecord (governance_change)** — *"Phase 15 Task 5 — multi-driver
   economic-capital proxy governance refresh"* created and walked DRAFT → PEER_REVIEW
   → **OWNER_REVIEW** (production sign-off withheld). Before/after snapshots and a
   no-numeric-impact assessment recorded.
4. **Audit trail** — two GOVERNANCE entries appended (MR-011 opened; ChangeRecord
   opened); append-only integrity verified (`verify_all()` → True).

## Resulting governance state

| Metric | Value |
|---|---|
| Audit entries | 28 (was 26); integrity OK |
| Change records | 14 (was 13); Task 5 record at OWNER_REVIEW |
| Risk register entries | 11 (was 10) |
| Open / In-progress / Mitigated / Closed | 1 / 4 / 4 / 2 |

## Model-use restrictions (summary)

Educational / methodology-demonstration use only. Not for regulatory capital,
pricing, reserving, or external reporting. Always report capital figures with their
proxy-error (OOS R² = 0.9704; VaR rel err 3.21%) and outer-sampling-error
(SE ≈ ±1.66%) bounds, and benchmark aggregated figures to the Task 3 nested ground
truth (the var-cov formula understates diversified capital by ~33%, MR-010).

## Residual to production

Credentialled-data calibration (MR-008), omitted risk drivers brought into the tail,
validation readiness raised to production threshold (MR-006), and an **independent
APS X2 review** — all tracked under **MR-011**. Educational classification retained;
production sign-off withheld.

## Standards

IA TAS M §3.6 (validation, model-use restrictions) / §3.7 (change log); APS X2 §3
(independent review); SOA ASOP 56 §3.5 (validation/limitations); SOA ASOP 25 §3.3;
IFoA Modelling Practice Note §4 (risk register).
