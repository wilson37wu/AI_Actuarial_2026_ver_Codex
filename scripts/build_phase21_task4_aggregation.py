#!/usr/bin/env python3
"""Phase 21 Task 4 build + governance -- seven-driver tail-dependent aggregation
+ tail diagnostics.

Runs the seven-driver (G2++ rate, equity, credit, lapse, mortality, FX,
liquidity) capital aggregation: standalone SCRs, 7x7 var-covar,
copula-on-realised-losses re-aggregation (gaussian / student-t /
survival-Clayton, AIC-selected), the nested benchmark, and the tail
diagnostics (copula-simulated convergence, bootstrap CIs incl. the honest
small-sample nested CI, and the crude-vs-Sobol-RQMC variance-reduction
study).  Writes the validation report (JSON + Markdown) and a model card,
opens an OWNER_REVIEW ChangeRecord, refreshes risks MR-010 and MR-012, and
verifies audit-chain integrity.

CRN reuse: the seven-driver outer joint reproduces the Phase 21 Task 1
six-driver construction bit-for-bit at the same seed, so the Task 1 staged
five-driver component liabilities (/var/tmp/p21t1_stage) are reused verbatim
when present and verified; otherwise the slices are recomputed with the
identical protocol.

Run (monolithic):  PYTHONPATH=. python3 scripts/build_phase21_task4_aggregation.py
Run (staged, for wall-clock-limited shells; bit-identical to monolithic):
  PYTHONPATH=. python3 scripts/build_phase21_task4_aggregation.py --stage outer
  PYTHONPATH=. python3 scripts/build_phase21_task4_aggregation.py --stage slice --i0 0 --i1 32
  ... (cover [0, n_outer) in slices) ...
  PYTHONPATH=. python3 scripts/build_phase21_task4_aggregation.py --stage finalise
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from par_model_v2.governance.audit_trail import (
    AuditEntry,
    ChangeRecord,
    GovernanceStore,
    MitigationStatus,
)
from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.multi_driver_capital_5d_aggregation import (
    FiveDriverAggregationConfig,
)
from par_model_v2.projection.multi_driver_capital_7d_aggregation import (
    SevenDriverLiquidityRiskAggregator,
    seven_driver_use_restrictions,
)

PHASE = "Phase 21: FX + Liquidity Drivers and Six/Seven-Driver Economic Capital"
ACTOR = "AutomatedModelDev_Phase21"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
OUT_DIR = Path("docs/validation")
JSON_PATH = OUT_DIR / "PHASE21_TASK4_AGGREGATION_REPORT.json"
MD_PATH = OUT_DIR / "PHASE21_TASK4_AGGREGATION_REPORT.md"
CARD_PATH = Path("docs/MULTI_DRIVER_7D_AGGREGATION_CARD.md")
CHANGE_TITLE = (
    "Phase 21 Task 4 - seven-driver tail-dependent aggregation + tail diagnostics"
)

AFFECTED_COMPONENTS = [
    "par_model_v2/projection/multi_driver_capital_7d_aggregation.py",
    "tests/test_phase21_task4_aggregation.py",
    "scripts/build_phase21_task4_aggregation.py",
    "docs/MULTI_DRIVER_7D_AGGREGATION_CARD.md",
    "docs/validation/PHASE21_TASK4_AGGREGATION_REPORT.{json,md}",
]

STANDARD_REFERENCES = [
    "SOA ASOP 56 section 3.1.3/3.4/3.5",
    "SOA ASOP 25 section 3.3",
    "IA TAS M section 3.2/3.5/3.6",
    "Solvency II Delegated Regulation Article 234 (aggregation)",
    "EIOPA volatility-adjustment methodology (illiquidity premium)",
    "Duffie-Singleton 1999; Brigo-Mercurio 2006; L'Ecuyer 2018 (RQMC)",
]

# Aggregation evidence settings — MUST match Phase 21 Task 1 so the staged
# five-driver CRN component liabilities are reusable bit-for-bit.
AGG_N_OUTER = 160
AGG_N_INNER = 24
AGG_SEED = 42
AGG_N_SIM_COPULA = 200_000

STAGE_DIR = Path("/var/tmp/p21t4_stage")
TASK1_STAGE_DIR = Path("/var/tmp/p21t1_stage")


def _product() -> ParEndowmentProduct:
    return ParEndowmentProduct(
        issue_age=45, gender="M", sum_assured=100000.0,
        annual_premium=5000.0, term_years=20,
    )


def _cfg() -> FiveDriverAggregationConfig:
    return FiveDriverAggregationConfig(
        n_outer=AGG_N_OUTER, n_inner=AGG_N_INNER, seed=AGG_SEED,
        capital_horizon_months=12, n_sim_copula=AGG_N_SIM_COPULA,
    )


# ---------------------------------------------------------------------------
# Governance
# ---------------------------------------------------------------------------

def _has_change_record(store: GovernanceStore) -> bool:
    return any(r.title == CHANGE_TITLE for r in store.change_records)


def _refresh_mr010(store: GovernanceStore, agg: Dict[str, Any]) -> str:
    try:
        risk = store.risk_register.get("MR-010")
        risk.update_mitigation(
            MitigationStatus.MITIGATED,
            notes=(
                "Phase 21 Task 4 re-confirmed the MR-010 finding under SEVEN drivers: the "
                "7x7 var-covar formula with raw ESG factor correlations gives {vc:.0f} vs the "
                "nested benchmark {nest:.0f} (understatement {und:.1f}%), because factor "
                "correlations are not capital-loss correlations in the tail. The "
                "copula-on-realised-losses re-aggregation ({cop}) reconciles within "
                "{coprel:.1f}% and remains the governed mitigation. Tail diagnostics: "
                "copula-simulated VaR convergence {conv} (last delta {dlt:.2%} vs 1% tol), "
                "simulated 95% CI rel-halfwidth {shw:.1%}, nested small-sample CI "
                "rel-halfwidth {nhw:.1%} (disclosed), Sobol-RQMC variance-reduction "
                "ratio {qmc:.1f}x."
            ).format(
                vc=agg["var_covar_scr"], nest=agg["nested_scr"],
                und=100.0 * agg["esg_understatement_pct"],
                cop=agg["copula_selected"],
                coprel=100.0 * agg["copula_vs_nested_rel_error"],
                conv="CONVERGED" if agg["tail_diagnostics"]["converged"] else "NOT converged",
                dlt=agg["tail_diagnostics"]["successive_var_rel_deltas"][-1],
                shw=agg["tail_diagnostics"]["simulated_bootstrap"]["var_ci_rel_halfwidth"],
                nhw=agg["tail_diagnostics"]["nested_bootstrap"]["var_ci_rel_halfwidth"],
                qmc=agg["tail_diagnostics"]["variance_reduction"]["qmc_variance_reduction_ratio"],
            ),
        )
        return "refreshed"
    except KeyError:
        return "missing"


def _refresh_mr012(store: GovernanceStore, agg: Dict[str, Any]) -> str:
    try:
        risk = store.risk_register.get("MR-012")
        risk.update_mitigation(
            MitigationStatus.MITIGATED,
            notes=(
                "Phase 21 Task 4 CLOSED the driver-omission residual at the aggregation "
                "level: all SEVEN documented drivers (G2++ rate, equity, credit spread, "
                "dynamic lapse, mortality trend, FX, liquidity) now enter the correlated "
                "economic-capital aggregation. The liquidity driver uses the Task 3 "
                "G-LIQ-calibrated CIR++ parameters with an ANALYTIC, CIR-affine-exact "
                "forced-sale haircut conditioning (verified vs Monte Carlo within 0.03%); "
                "liquidity standalone SCR {liq:.0f} vs rate {rate:.0f} / equity {eq:.0f} — "
                "small because the calibrated mean reversion (half-life ~0.74y) pulls the "
                "premium back over the ~19y workout horizon (documented finding). REMAINING "
                "residual is calibration quality, not coverage: liquidity exposure notional "
                "+ 7x7 liquidity couplings are educational placeholders pending "
                "credentialled data and independent APS X2 review."
            ).format(
                liq=agg["standalone_scr"]["liquidity"],
                rate=agg["standalone_scr"]["rate"],
                eq=agg["standalone_scr"]["equity"],
            ),
        )
        return "refreshed"
    except KeyError:
        return "missing"


def apply_governance(store: GovernanceStore, agg: Dict[str, Any]) -> Dict[str, Any]:
    mr010_action = _refresh_mr010(store, agg)
    mr012_action = _refresh_mr012(store, agg)
    added = False
    record_id = None
    record_status = None

    if not _has_change_record(store):
        td = agg["tail_diagnostics"]
        rec = ChangeRecord.create(
            title=CHANGE_TITLE,
            description=(
                "Phase 21 Task 4 aggregated all seven documented economic risk drivers "
                "(G2++ two-factor rates, GBM equity, CIR++ credit spread, OU dynamic lapse, "
                "OU mortality trend, lognormal FX, calibrated CIR++ liquidity premium) into "
                "the 99.5% one-year economic-capital view. The liquidity state enters the "
                "inner Q-nest ANALYTICALLY via the CIR-affine-exact forced-sale haircut "
                "(Duffie-Singleton form; baseline-centred), so no inner simulation noise is "
                "added. Aggregation: seven standalone SCRs, 7x7 var-covar on the governed "
                "ESG correlation (6x6 block inherited unchanged), copula-on-realised-losses "
                "re-aggregation with AIC selection, nested benchmark, plus tail diagnostics "
                "(copula-simulated VaR/ES convergence over a CRN prefix grid, bootstrap CIs "
                "for both the simulated aggregate and the honest small-sample nested vector, "
                "and a crude-vs-scrambled-Sobol RQMC variance-reduction study)."
            ),
            change_type="methodology_change",
            affected_components=AFFECTED_COMPONENTS,
            standard_references=STANDARD_REFERENCES,
            before_snapshot={
                "aggregated_drivers": "6 (FX added Task 1); liquidity calibrated but not aggregated",
                "mr012": "liquidity omission open at aggregation level",
            },
            after_snapshot={
                "aggregated_drivers": "7 (+ liquidity, analytic CIR-affine haircut)",
                "standalone_scr": agg["standalone_scr"],
                "var_covar_scr": agg["var_covar_scr"],
                "nested_scr": agg["nested_scr"],
                "copula_selected": agg["copula_selected"],
                "copula_rel_error_vs_nested": agg["copula_vs_nested_rel_error"],
                "tail_converged": td["converged"],
                "qmc_variance_reduction": td["variance_reduction"]["qmc_variance_reduction_ratio"],
                "aggregation_verdict": agg["verdict"],
            },
            impact_assessment=(
                "Completes driver coverage of the economic-capital proxy (MR-012 closure at "
                "aggregation level) without changing any six-driver output: the module is "
                "additive and the six-driver outer joint plus five-driver CRN component "
                "liabilities are reproduced bit-for-bit (regression-tested). MR-010 finding "
                "re-confirmed and re-quantified under seven drivers."
            ),
            quantitative_impact=(
                "Standalone sum {ss:.0f}; var-covar {vc:.0f} vs nested {nest:.0f} "
                "(understatement {und:.1f}%); copula ({cop}) within {coprel:.1f}%; liquidity "
                "standalone SCR {liq:.0f}; tail convergence {conv} (last VaR delta {dlt:.2%}); "
                "Sobol-RQMC ratio {qmc:.1f}x; n_outer={no}, n_inner={ni}, seed={seed}, "
                "n_sim_copula={ns}."
            ).format(
                ss=agg["standalone_scr_sum"], vc=agg["var_covar_scr"],
                nest=agg["nested_scr"], und=100.0 * agg["esg_understatement_pct"],
                cop=agg["copula_selected"],
                coprel=100.0 * agg["copula_vs_nested_rel_error"],
                liq=agg["standalone_scr"]["liquidity"],
                conv="CONVERGED" if td["converged"] else "NOT converged",
                dlt=td["successive_var_rel_deltas"][-1],
                qmc=td["variance_reduction"]["qmc_variance_reduction_ratio"],
                no=AGG_N_OUTER, ni=AGG_N_INNER, seed=AGG_SEED, ns=AGG_N_SIM_COPULA,
            ),
            author=ACTOR,
            phase=PHASE,
            peer_reviewer="APS_X2_Independent_Reviewer",
            assumption_owner="ChiefActuary",
        )
        rec.submit_for_peer_review(
            ACTOR,
            "Seven-driver aggregation staged with analytic liquidity conditioning, copula "
            "re-aggregation and tail diagnostics; credentialled exposure/coupling calibration "
            "required before approval.",
        )
        rec.submit_to_owner(
            ACTOR,
            "Owner review requested. Production sign-off withheld pending Phase 21 Task 5 "
            "(UI propagation), credentialled liquidity exposure calibration, and APS X2 review.",
        )
        store.add_change_record(rec)
        added = True
        record_id = rec.record_id
        record_status = rec.status.value
        store.audit_trail.append(
            AuditEntry.governance(
                actor=ACTOR,
                phase=PHASE,
                event="ChangeRecord opened (OWNER_REVIEW) - seven-driver aggregation + tail diagnostics",
                details={
                    "record_id": rec.record_id,
                    "liquidity_standalone_scr": agg["standalone_scr"]["liquidity"],
                    "var_covar_scr": agg["var_covar_scr"],
                    "nested_scr": agg["nested_scr"],
                    "copula_selected": agg["copula_selected"],
                    "tail_converged": agg["tail_diagnostics"]["converged"],
                    "affected_components": AFFECTED_COMPONENTS,
                    "mr010_action": mr010_action,
                    "mr012_action": mr012_action,
                },
            )
        )
    else:
        for rec in store.change_records:
            if rec.title == CHANGE_TITLE:
                record_id = rec.record_id
                record_status = rec.status.value
                break

    return {
        "mr010_action": mr010_action,
        "mr010_status": store.risk_register.get("MR-010").mitigation_status.value,
        "mr012_action": mr012_action,
        "mr012_status": store.risk_register.get("MR-012").mitigation_status.value,
        "added_change_record": added,
        "change_record_id": record_id,
        "change_record_status": record_status,
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _scr_rows(agg: Dict[str, Any]) -> str:
    return "\n".join(
        "| {} | {:.1f} |".format(k, v) for k, v in agg["standalone_scr"].items()
    )


def _markdown(report: Dict[str, Any]) -> str:
    agg = report["aggregation"]
    td = agg["tail_diagnostics"]
    sb = td["simulated_bootstrap"]
    nb = td["nested_bootstrap"]
    vr = td["variance_reduction"]
    return """# Phase 21 Task 4 — Seven-Driver Tail-Dependent Aggregation + Tail Diagnostics

**Run:** {ts}
**Verdict:** {verdict}
**ChangeRecord:** `{crid}` ({crstatus})
**MR-010:** {mr010} | **MR-012:** {mr012}

## Standalone SCRs (99.5%, 1y)

| Driver | SCR |
|---|---|
{scr_rows}
| **Sum** | **{ss:.1f}** |

## Reconciliation

| Measure | SCR | vs nested |
|---|---|---|
| Var-covar (7x7 ESG) | {vc:.1f} | {und:+.1f}% understatement |
| Copula ({cop}) | {copscr:.1f} | {coprel:.1f}% rel err |
| Nested benchmark | {nest:.1f} | — |

Interaction residual (CRN sum vs nested): {ir:.1f}%.

## Tail diagnostics

* Copula-simulated VaR convergence over n_sim grid {grid}: last successive
  delta {dlt:.2%} (tol {tol:.0%}) → **{conv}**.
* Simulated bootstrap 95% CI: VaR [{svlo:.0f}, {svhi:.0f}] (SE {svse:.0f},
  rel-halfwidth {shw:.1%}); ES [{selo:.0f}, {sehi:.0f}].
* Nested small-sample bootstrap (n_outer={no}): VaR [{nvlo:.0f}, {nvhi:.0f}]
  (rel-halfwidth {nhw:.1%}) — wide by construction, disclosed.
* Variance reduction: scrambled-Sobol RQMC vs crude MC ratio **{qmc:.1f}x**
  (n={vrn}, {vrr} replications).

## Liquidity driver (7th)

Calibrated CIR++ (Task 3 G-LIQ): kappa={kap:.4f}/yr, long-run {lr:.0f}bp,
sigma={sig:.4f}, lambda_l={lam:.2f}. Exposure notional {notional:.0f}
(educational placeholder). Inner conditioning is ANALYTIC and
CIR-affine-exact; liquidity standalone SCR {liq:.1f} — small under the
calibrated mean reversion (documented finding, not a wiring defect).

## Notes

{notes}

## Use restrictions

EDUCATIONAL ONLY — see report JSON `use_restrictions`.

*Standards: {standards}*
""".format(
        ts=report["run_timestamp"], verdict=agg["verdict"],
        crid=report["change_record_id"], crstatus=report["change_record_status"],
        mr010=report["mr010_status"], mr012=report["mr012_status"],
        scr_rows=_scr_rows(agg), ss=agg["standalone_scr_sum"],
        vc=agg["var_covar_scr"], und=100.0 * agg["esg_understatement_pct"],
        cop=agg["copula_selected"], copscr=agg["copula_scr"],
        coprel=100.0 * agg["copula_vs_nested_rel_error"],
        nest=agg["nested_scr"], ir=100.0 * agg["interaction_residual_rel"],
        grid=td["n_sim_grid"], dlt=td["successive_var_rel_deltas"][-1],
        tol=td["convergence_tolerance"],
        conv="CONVERGED" if td["converged"] else "NOT CONVERGED",
        svlo=sb["var_ci"][0], svhi=sb["var_ci"][1], svse=sb["var_se"],
        shw=sb["var_ci_rel_halfwidth"], selo=sb["es_ci"][0], sehi=sb["es_ci"][1],
        no=nb["n_outer"], nvlo=nb["var_ci"][0], nvhi=nb["var_ci"][1],
        nhw=nb["var_ci_rel_halfwidth"],
        qmc=vr["qmc_variance_reduction_ratio"], vrn=vr["n_per_replication"],
        vrr=vr["replications"],
        kap=agg["liquidity_params"]["kappa"],
        lr=1e4 * agg["liquidity_params"]["long_run_premium_p"],
        sig=agg["liquidity_params"]["sigma"],
        lam=agg["liquidity_params"]["lambda_l"],
        notional=agg["liquidity_exposure_notional"],
        liq=agg["standalone_scr"]["liquidity"],
        notes="\n".join("* " + n for n in agg["notes"]),
        standards="; ".join(STANDARD_REFERENCES),
    )


def _write_card(agg: Dict[str, Any]) -> None:
    td = agg["tail_diagnostics"]
    CARD_PATH.write_text(
        """# Seven-Driver Economic-Capital Aggregation Card

**Phase:** 21 - FX + Liquidity Drivers and Six/Seven-Driver Economic Capital (Task 4)

**Status:** EDUCATIONAL. ChangeRecord at OWNER_REVIEW; production sign-off withheld
pending UI propagation (Task 5), credentialled liquidity exposure/coupling calibration,
and independent (APS X2) review.

## Scope

All seven documented drivers aggregated at 99.5%/1y: G2++ rates, GBM equity, CIR++
credit spread, OU dynamic lapse, OU mortality trend, lognormal FX (CIP-exact analytic
conditioning), and the Task 3 G-LIQ-calibrated CIR++ liquidity premium (CIR-affine-exact
analytic forced-sale haircut conditioning, baseline-centred).

## Headline numbers (seed {seed}, n_outer {no}, n_inner {ni})

| Measure | Value |
|---|---|
| Standalone sum | {ss:.1f} |
| Var-covar (7x7 ESG) | {vc:.1f} |
| Copula ({cop}) | {copscr:.1f} |
| Nested benchmark | {nest:.1f} |
| Var-covar understatement | {und:.1f}% |
| Copula vs nested rel err | {coprel:.1f}% |
| Liquidity standalone SCR | {liq:.1f} |
| Tail convergence | {conv} |
| Sobol-RQMC variance-reduction | {qmc:.1f}x |

## Key findings

1. MR-010 re-confirmed under seven drivers: raw ESG factor correlations in the
   var-covar formula understate the nested diversified capital by {und:.1f}%; the
   copula-on-realised-losses re-aggregation remains the governed mitigation.
2. MR-012 driver-omission residual CLOSED at aggregation level — no documented
   driver remains outside the correlated aggregation.
3. The calibrated liquidity premium's strong mean reversion (half-life ~0.74y)
   makes 1-in-200 one-year liquidity translation risk SMALL on a hold-to-maturity
   book ({liq:.0f} standalone) — an honest finding, verified affine-exact, not a
   wiring defect.

## Limitations / model-use restrictions

Educational placeholders: liquidity exposure notional, 7x7 liquidity couplings.
Single systemic liquidity factor (no asset-class segmentation / funding ladder).
Nested benchmark n_outer is small for a 99.5% metric — nested bootstrap CI is wide
and disclosed; convergence evidence carried by the copula-simulated study.
Not for pricing, reserving, or regulatory capital.

*Standards: SOA ASOP 56 3.1.3/3.4/3.5; ASOP 25 3.3; IA TAS M 3.2/3.5/3.6/3.7;
Solvency II Del. Reg. Art. 234; EIOPA VA methodology; L'Ecuyer 2018.*
""".format(
            seed=AGG_SEED, no=AGG_N_OUTER, ni=AGG_N_INNER,
            ss=agg["standalone_scr_sum"], vc=agg["var_covar_scr"],
            cop=agg["copula_selected"], copscr=agg["copula_scr"],
            nest=agg["nested_scr"], und=100.0 * agg["esg_understatement_pct"],
            coprel=100.0 * agg["copula_vs_nested_rel_error"],
            liq=agg["standalone_scr"]["liquidity"],
            conv="CONVERGED" if td["converged"] else "NOT CONVERGED",
            qmc=td["variance_reduction"]["qmc_variance_reduction_ratio"],
        ),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Staged execution
# ---------------------------------------------------------------------------

def stage_outer() -> int:
    """Stage 1: 7D outer states + analytic FX and liquidity loss vectors."""
    import numpy as np

    STAGE_DIR.mkdir(parents=True, exist_ok=True)
    cfg = _cfg()
    agg = SevenDriverLiquidityRiskAggregator(_product())
    outer7 = agg._outer_states_7d(
        cfg.n_outer, cfg.capital_horizon_months, cfg.outer_measure, cfg.seed
    )
    tau = agg._liquidity_tau_years(cfg.capital_horizon_months)
    np.savez(
        STAGE_DIR / "outer.npz",
        outer7=outer7,
        fx=agg.fx_exposure.liability_impact(outer7[:, 5]),
        liquidity=agg.liquidity_exposure.liability_impact(
            outer7[:, 6], agg.liquidity_params, tau
        ),
    )
    print("stage outer done: {} states".format(len(outer7)))
    return 0


def stage_slice(i0: int, i1: int) -> int:
    """Stage 2: CRN five-driver component liabilities for rows [i0, i1)."""
    import numpy as np

    data = np.load(STAGE_DIR / "outer.npz")
    cfg = _cfg()
    agg = SevenDriverLiquidityRiskAggregator(_product())
    out = agg.component_liabilities_sliced(data["outer7"][:, :5], i0, i1, cfg)
    np.savez(STAGE_DIR / "slice_{:04d}_{:04d}.npz".format(i0, i1), **out)
    print("stage slice [{}, {}) done".format(i0, i1))
    return 0


def _try_reuse_task1_slices() -> bool:
    """Reuse Task 1's staged slices when the outer joints verifiably match."""
    import numpy as np

    t1_outer = TASK1_STAGE_DIR / "outer.npz"
    if not t1_outer.exists():
        return False
    here = np.load(STAGE_DIR / "outer.npz")
    there = np.load(t1_outer)
    if "outer6" not in there.files:
        return False
    if not np.array_equal(here["outer7"][:, :5], there["outer6"][:, :5]):
        return False
    copied = 0
    for f in sorted(TASK1_STAGE_DIR.glob("slice_*.npz")):
        dst = STAGE_DIR / f.name
        if not dst.exists():
            dst.write_bytes(f.read_bytes())
            copied += 1
    print("reused {} Task 1 CRN slices (outer joint verified bit-identical)".format(copied))
    return True


def _assemble_precomputed():
    import numpy as np

    data = np.load(STAGE_DIR / "outer.npz")
    n = data["outer7"].shape[0]
    slices = sorted(STAGE_DIR.glob("slice_*.npz"))
    keys = ("rate", "equity", "credit", "lapse", "mortality", "full5")
    pre = {k: np.full(n, np.nan) for k in keys}
    for f in slices:
        i0, i1 = (int(x) for x in f.stem.split("_")[1:3])
        part = np.load(f)
        for k in keys:
            pre[k][i0:i1] = part[k]
    if any(np.isnan(pre[k]).any() for k in keys):
        raise RuntimeError("staged slices do not cover [0, n_outer); rerun missing slices")
    pre["fx"] = data["fx"]
    pre["liquidity"] = data["liquidity"]
    return pre


def main(precomputed=None) -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    cfg = _cfg()
    agg_report = SevenDriverLiquidityRiskAggregator(_product()).run_7d(
        config=cfg, precomputed=precomputed
    )
    agg = agg_report.to_dict()

    store = (
        GovernanceStore.from_json(GOV_PATH.read_text(encoding="utf-8"))
        if GOV_PATH.exists() else GovernanceStore()
    )
    gov = apply_governance(store, agg)
    _write_card(agg)

    if GOV_PATH.exists():
        GOV_PATH.write_text(store.to_json() + "\n", encoding="utf-8")

    report = {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": PHASE,
        "task": CHANGE_TITLE,
        "aggregation": agg,
        "affected_components": AFFECTED_COMPONENTS,
        "standard_references": STANDARD_REFERENCES,
        "change_record_id": gov["change_record_id"],
        "change_record_status": gov["change_record_status"],
        "mr010_action": gov["mr010_action"],
        "mr010_status": gov["mr010_status"],
        "mr012_action": gov["mr012_action"],
        "mr012_status": gov["mr012_status"],
        "audit_integrity_ok": store.audit_trail.verify_all(),
        "change_records_total": len(store.change_records),
        "risk_register_summary": store.risk_register.summary(),
        "use_restrictions": seven_driver_use_restrictions(),
    }
    report["markdown"] = _markdown(report)
    JSON_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    MD_PATH.write_text(report["markdown"], encoding="utf-8")

    td = agg["tail_diagnostics"]
    print("=== Phase 21 Task 4 - Seven-Driver Aggregation + Tail Diagnostics ===")
    print("Standalone SCRs   : " + ", ".join(
        "{}={:.1f}".format(k, v) for k, v in agg["standalone_scr"].items()))
    print("Var-covar / nested: {:.1f} / {:.1f} (understatement {:.1f}%)".format(
        agg["var_covar_scr"], agg["nested_scr"], 100.0 * agg["esg_understatement_pct"]))
    print("Copula ({}) : {:.1f} (rel {:.1%})".format(
        agg["copula_selected"], agg["copula_scr"], agg["copula_vs_nested_rel_error"]))
    print("Tail convergence  : {} (last delta {:.2%})".format(
        "CONVERGED" if td["converged"] else "NOT CONVERGED",
        td["successive_var_rel_deltas"][-1]))
    print("Sobol-RQMC ratio  : {:.1f}x".format(
        td["variance_reduction"]["qmc_variance_reduction_ratio"]))
    print("Verdict           : {}".format(agg["verdict"]))
    print("ChangeRecord      : {} ({})".format(gov["change_record_id"], gov["change_record_status"]))
    print("MR-010 / MR-012   : {} ({}) / {} ({})".format(
        gov["mr010_status"], gov["mr010_action"],
        gov["mr012_status"], gov["mr012_action"]))
    print("Audit integrity   : {}".format(store.audit_trail.verify_all()))
    print("Report            : {}".format(JSON_PATH))
    return 0 if agg["verdict"] == "PASS" and store.audit_trail.verify_all() else 1


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["outer", "slice", "finalise"], default=None)
    ap.add_argument("--i0", type=int, default=0)
    ap.add_argument("--i1", type=int, default=0)
    args = ap.parse_args()
    if args.stage == "outer":
        rc = stage_outer()
        _try_reuse_task1_slices()
        sys.exit(rc)
    elif args.stage == "slice":
        sys.exit(stage_slice(args.i0, args.i1))
    elif args.stage == "finalise":
        sys.exit(main(precomputed=_assemble_precomputed()))
    sys.exit(main())
