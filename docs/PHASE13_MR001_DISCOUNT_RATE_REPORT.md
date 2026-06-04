# Phase 13 Task 3 — MR-001 Discount-Rate Change Report

**Run:** 2026-06-04 05:28:13 UTC
**Gates:** G-01 ✅ PASS | G-07 ✅ PASS
**ChangeRecord:** `5dac3fe33735460da56c1cedbd3ce547` — **APPROVED** (assumption="discount_rate_annual")

> **PRODUCTION USE RESTRICTION.** The three-stage sign-off is automation-driven
> for this educational model. Production reserving requires a genuine Assumption
> Owner + independent peer review and a CNY sovereign discount curve bootstrapped
> from live published bond yields (cross-ref G-02 / G-12).

## 1. Change Summary

| Field | Before | After |
|---|---|---|
| `discount_rate_annual` (default) | 0.035 (3.5%) | 0.030 (3.0%) |
| Basis | Legacy model default (non-compliant) | CBIRC 2023 reserve-valuation cap |
| Affected defaults | `project_liability_cashflows`, `run_full_projection` | via `DEFAULT_RESERVING_DISCOUNT_RATE` |

The legacy 3.5% default breached the CBIRC statutory valuation cap of 3.0% and
understated reserves (critical model risk **MR-001**). The default is now the
CBIRC-compliant 3.0%.

## 2. Reserve Impact (representative HK PAR endowments)

| Product | PV NetLiab @3.5% | PV NetLiab @3.0% | Δ% | PV Guar @3.5% | PV Guar @3.0% | Δ% |
|---|---:|---:|---:|---:|---:|---:|
| 5y HK PAR endowment | 180,446 | 189,291 | +4.90% | 576,218 | 590,269 | +2.44% |
| 10y HK PAR endowment | 57,037 | 68,613 | +20.29% | 419,881 | 440,432 | +4.89% |
| 20y HK PAR endowment | -52,433 | -41,079 | +21.65% | 263,282 | 288,852 | +9.71% |

Lowering the discount rate increases the present value of long-dated guaranteed
liabilities. The effect grows with policy term (longer duration -> greater rate
sensitivity), confirming the change is regulator-protective: reserves rise and the
prior systematic understatement is removed.

## 3. Production Gate Status

| Gate | Status | Evidence |
|---|---|---|
| G-01 | ✅ PASS | default discount_rate_annual=0.030 <= cap 0.030; DiscountRateValidator: no CBIRC warning at default; reserve impact quantified over 3 products |
| G-07 | ✅ PASS | before_snapshot=0.035; after_snapshot=0.030; impact assessment present; standard refs include CBIRC + IA TAS M §3.5; status=APPROVED; 3-stage sign-off DRAFT->PEER_REVIEW->OWNER_REVIEW->APPROVED |

## 4. Governance

ChangeRecord `5dac3fe33735460da56c1cedbd3ce547` (assumption="discount_rate_annual") logged to the
GovernanceStore and driven through DRAFT → PEER_REVIEW → OWNER_REVIEW →
**APPROVED**. This operationally demonstrates the IA TAS M §3.5/§3.7 change-
control workflow on the highest-priority assumption and mitigates model risk
**MR-001** (educational; production residual = genuine independent sign-off +
live CNY curve).

**Standards addressed:** CBIRC C-ROSS Reserve Valuation (2023); SOA ASOP 25 §3.3;
SOA ASOP 56 §3.5; IA TAS M §3.5 & §3.7.
