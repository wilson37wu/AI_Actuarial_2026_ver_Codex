#!/usr/bin/env python3
"""Phase 21 Task 1 build + governance -- FX / currency sixth capital driver + G-FX gate.

Runs the G-FX plausibility gate (incl. the reused Phase 20 MART-FX-CIP Q-measure
martingale evidence), runs the six-driver FX capital aggregation (standalone SCRs,
6x6 var-covar, copula-on-realised-losses, nested benchmark), writes the validation
report (JSON + Markdown) and a model card, opens an OWNER_REVIEW ChangeRecord,
refreshes risk MR-012, and verifies audit-chain integrity.

Run (monolithic):  PYTHONPATH=. python3 scripts/build_phase21_task1_fx.py
Run (staged, for wall-clock-limited shells; bit-identical to monolithic):
  PYTHONPATH=. python3 scripts/build_phase21_task1_fx.py --stage outer
  PYTHONPATH=. python3 scripts/build_phase21_task1_fx.py --stage slice --i0 0 --i1 32
  ... (cover [0, n_outer) in slices) ...
  PYTHONPATH=. python3 scripts/build_phase21_task1_fx.py --stage finalise
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
from par_model_v2.projection.multi_driver_capital_6d_fx import (
    SixDriverFXRiskAggregator,
    evaluate_g_fx_gate,
    six_driver_fx_use_restrictions,
)

PHASE = "Phase 21: FX + Liquidity Drivers and Six/Seven-Driver Economic Capital"
ACTOR = "AutomatedModelDev_Phase21"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
OUT_DIR = Path("docs/validation")
JSON_PATH = OUT_DIR / "PHASE21_TASK1_FX_DRIVER_REPORT.json"
MD_PATH = OUT_DIR / "PHASE21_TASK1_FX_DRIVER_REPORT.md"
CARD_PATH = Path("docs/FX_DRIVER_G_FX_CARD.md")
CHANGE_TITLE = "Phase 21 Task 1 - FX / currency sixth capital driver + G-FX plausibility gate"

AFFECTED_COMPONENTS = [
    "par_model_v2/projection/multi_driver_capital_6d_fx.py",
    "tests/test_phase21_fx_driver.py",
    "scripts/build_phase21_task1_fx.py",
    "docs/FX_DRIVER_G_FX_CARD.md",
    "docs/validation/PHASE21_TASK1_FX_DRIVER_REPORT.{json,md}",
]

STANDARD_REFERENCES = [
    "SOA ASOP 56 section 3.1.3",
    "SOA ASOP 56 section 3.4/3.5",
    "IA TAS M section 3.5/3.6",
    "Solvency II Delegated Regulation Article 188 (currency risk)",
    "Solvency II Delegated Regulation Article 234",
    "Brigo-Mercurio 2006",
]

# Aggregation evidence settings (educational; mirrors Phase 20 Task 4 scale).
AGG_N_OUTER = 160
AGG_N_INNER = 24
AGG_SEED = 42
AGG_N_SIM_COPULA = 200_000


def _has_change_record(store: GovernanceStore) -> bool:
    return any(r.title == CHANGE_TITLE for r in store.change_records)


def _refresh_mr012(store: GovernanceStore, gate: Dict[str, Any], agg: Dict[str, Any]) -> str:
    try:
        risk = store.risk_register.get("MR-012")
        risk.update_mitigation(
            MitigationStatus.IN_PROGRESS,
            notes=(
                "Phase 21 Task 1 added the FX / currency translation driver as the SIXTH "
                "economic-capital driver (lognormal spot, P real-world outer / Q CIP drift, "
                "CIP-exact analytic inner conditioning) with the G-FX plausibility gate "
                "({gstatus}, {gn}/{gt} criteria incl. the Phase 20 MART-FX-CIP Q-martingale "
                "evidence). Six-driver aggregation: FX standalone SCR {fx:.0f}; var-covar "
                "{vc:.0f} vs nested {nest:.0f} (understatement {und:.1f}%); copula ({cop}) "
                "reconciles within {coprel:.1f}%. The documented FX omission in this "
                "residual is now CLOSED; the LIQUIDITY driver remains open (Phase 21 Task 3), "
                "six-driver LSMC proxy OOS validation pending (Task 2), parameters remain "
                "educational placeholders pending credentialled calibration."
            ).format(
                gstatus="PASS" if gate["passed"] else "FAIL",
                gn=gate["n_passed"], gt=gate["n_criteria"],
                fx=agg["standalone_scr"]["fx"], vc=agg["var_covar_scr"],
                nest=agg["nested_scr"], und=100.0 * agg["esg_understatement_pct"],
                cop=agg["copula_selected"], coprel=100.0 * agg["copula_vs_nested_rel_error"],
            ),
        )
        return "refreshed"
    except KeyError:
        return "missing"


def _criteria_rows(gate: Dict[str, Any]) -> str:
    rows = []
    for c in gate["criteria"]:
        ev = "; ".join(
            "{}={}".format(k, round(v, 6) if isinstance(v, float) else v)
            for k, v in list(c["evidence"].items())[:3]
        )
        rows.append("| {} | {} | {} |".format(
            c["criterion"], "PASS" if c["passed"] else "FAIL", ev))
    return "\n".join(rows)


def _scr_rows(agg: Dict[str, Any]) -> str:
    return "\n".join(
        "| {} | {:.1f} |".format(k, v) for k, v in agg["standalone_scr"].items()
    )


def _write_card(gate: Dict[str, Any], agg: Dict[str, Any]) -> None:
    CARD_PATH.write_text(
        """# FX / Currency Sixth-Driver Card -- G-FX

**Phase:** 21 - FX + Liquidity Drivers and Six/Seven-Driver Economic Capital (Task 1)

**Status:** EDUCATIONAL placeholder parameters; gate {gstatus}. Production sign-off
withheld pending six-driver LSMC OOS validation (Task 2), liquidity driver (Task 3),
re-aggregation + tail diagnostics (Task 4), UI propagation (Task 5), credentialled
calibration, and independent (APS X2) review.

## Driver

Lognormal FX spot X(t) (base per foreign unit; educational HKD-per-USD book, X0 = {x0}).
Outer real-world paths use the P-measure drift; the Q measure uses the covered-interest-
parity drift (r_d - r_f). The sixth governed shock is Cholesky-correlated to the five
existing drivers through a 6x6 ESG matrix that embeds the governed 5x5 block unchanged.

## CIP-exact inner conditioning

The educational FX exposure is a foreign-currency asset leg. Under Q the deflated
translated foreign money-market account is a martingale (Phase 20 MART-FX-CIP):
E^Q[D_d(H+s) X(H+s) exp(r_f (H+s)) | X_H] = D_d(H) X_H exp(r_f H), so the inner
conditional PV given X_H is analytic and exact: fx_l = notional * (1 - X_H / X0)
(a translation loss when the foreign currency depreciates).

## G-FX gate ({gn}/{gt} criteria)

| Criterion | Result | Evidence (truncated) |
| --- | --- | --- |
{crit_rows}

## Six-driver aggregation evidence (n_outer={no}, n_inner={ni}, seed={seed}, 99.5% / 12m)

| Driver | Standalone SCR |
| --- | --- |
{scr_rows}

* Var-covar (6x6 ESG): {vc:.1f} (understates nested by {und:.1f}% -- MR-010 pattern)
* Copula ({cop}): {copscr:.1f} (within {coprel:.1f}% of nested -- MR-010/MR-012 mitigation)
* Nested benchmark: {nest:.1f}
* Verdict: **{verdict}**

## Limitations / use restrictions

{restrictions}

## Standards

{standards}
""".format(
            gstatus="PASS" if gate["passed"] else "FAIL", x0=gate["params"]["initial_spot_rate"],
            gn=gate["n_passed"], gt=gate["n_criteria"], crit_rows=_criteria_rows(gate),
            no=AGG_N_OUTER, ni=AGG_N_INNER, seed=AGG_SEED, scr_rows=_scr_rows(agg),
            vc=agg["var_covar_scr"], und=100.0 * agg["esg_understatement_pct"],
            cop=agg["copula_selected"], copscr=agg["copula_scr"],
            coprel=100.0 * agg["copula_vs_nested_rel_error"], nest=agg["nested_scr"],
            verdict=agg["verdict"],
            restrictions="\n".join("* " + r for r in six_driver_fx_use_restrictions()["restrictions"]),
            standards="\n".join("* " + s for s in STANDARD_REFERENCES),
        ),
        encoding="utf-8",
    )


def _markdown(report: Dict[str, Any]) -> str:
    gate = report["gate"]
    agg = report["aggregation"]
    return """# Phase 21 Task 1 -- FX / Currency Sixth Capital Driver (G-FX)

Run: {ts}

## G-FX gate: {gstatus} ({gn}/{gt})

| Criterion | Result | Evidence (truncated) |
| --- | --- | --- |
{crit_rows}

## Six-driver aggregation (verdict: {verdict})

| Driver | Standalone SCR |
| --- | --- |
{scr_rows}

* Var-covar (6x6): {vc:.1f}; nested: {nest:.1f}; understatement {und:.1f}%
* Copula ({cop}): {copscr:.1f} (rel err vs nested {coprel:.1f}%)
* Interaction residual (rel): {ir:.1f}%
* Reproducibility digest: `{digest}`

## Governance

* ChangeRecord: {rec} ({recst})
* MR-012: {mr} ({mract})
* Audit integrity: {audit}
""".format(
        ts=report["run_timestamp"], gstatus="PASS" if gate["passed"] else "FAIL",
        gn=gate["n_passed"], gt=gate["n_criteria"], crit_rows=_criteria_rows(gate),
        verdict=agg["verdict"], scr_rows=_scr_rows(agg), vc=agg["var_covar_scr"],
        nest=agg["nested_scr"], und=100.0 * agg["esg_understatement_pct"],
        cop=agg["copula_selected"], copscr=agg["copula_scr"],
        coprel=100.0 * agg["copula_vs_nested_rel_error"],
        ir=100.0 * agg["interaction_residual_rel"],
        digest=agg["reproducibility_digest"],
        rec=report["change_record_id"], recst=report["change_record_status"],
        mr=report["mr012_status"], mract=report["mr012_action"],
        audit=report["audit_integrity_ok"],
    )


def apply_governance(store: GovernanceStore, gate: Dict[str, Any], agg: Dict[str, Any]) -> Dict[str, Any]:
    mr_action = _refresh_mr012(store, gate, agg)
    added = False
    record_id = None
    record_status = None

    if not _has_change_record(store):
        rec = ChangeRecord.create(
            title=CHANGE_TITLE,
            description=(
                "Phase 21 Task 1 added the FX / currency translation driver as the sixth "
                "economic-capital driver: a lognormal FX spot (P real-world drift outer; "
                "Q covered-interest-parity drift) driven by a sixth governed shock through a "
                "6x6 ESG correlation that embeds the governed 5x5 block unchanged. The inner "
                "Q-nest conditioning on the FX state is analytic and CIP-exact (the deflated "
                "translated foreign money-market account is a Q-martingale, Phase 20 "
                "MART-FX-CIP), so no inner FX simulation noise is introduced. Six-driver "
                "standalone SCRs, 6x6 var-covar, copula-on-realised-losses and the nested "
                "benchmark are produced by an additive aggregator reusing the Phase 20 G2++ "
                "five-driver CRN components verbatim. A G-FX plausibility gate (positive "
                "spots, lognormal moments, P/Q separation, Q-CIP martingale, correlation "
                "wiring, exposure mapping) gates the driver."
            ),
            change_type="methodology_change",
            affected_components=AFFECTED_COMPONENTS,
            standard_references=STANDARD_REFERENCES,
            before_snapshot={
                "capital_drivers": "5 (G2++ rate, equity, credit, lapse, mortality)",
                "fx_driver": "documented omission (MR-012 residual)",
            },
            after_snapshot={
                "capital_drivers": "6 (+ FX translation)",
                "g_fx_status": "PASS" if gate["passed"] else "FAIL",
                "g_fx_criteria": "{}/{}".format(gate["n_passed"], gate["n_criteria"]),
                "fx_standalone_scr": agg["standalone_scr"]["fx"],
                "var_covar_scr": agg["var_covar_scr"],
                "nested_scr": agg["nested_scr"],
                "copula_selected": agg["copula_selected"],
                "copula_rel_error_vs_nested": agg["copula_vs_nested_rel_error"],
                "aggregation_verdict": agg["verdict"],
            },
            impact_assessment=(
                "Adds the FX translation tail axis to economic capital without changing any "
                "five-driver output (additive module; governed 5x5 correlation block and CRN "
                "component liabilities reused bit-for-bit). Closes the FX half of the MR-012 "
                "documented omission; liquidity remains open (Task 3)."
            ),
            quantitative_impact=(
                "G-FX {gstatus} ({gn}/{gt}); FX standalone SCR {fx:.0f}; six-driver var-covar "
                "{vc:.0f} vs nested {nest:.0f} (understatement {und:.1f}%); copula ({cop}) "
                "within {coprel:.1f}% of nested; n_outer={no}, n_inner={ni}, seed={seed}."
            ).format(
                gstatus="PASS" if gate["passed"] else "FAIL", gn=gate["n_passed"],
                gt=gate["n_criteria"], fx=agg["standalone_scr"]["fx"],
                vc=agg["var_covar_scr"], nest=agg["nested_scr"],
                und=100.0 * agg["esg_understatement_pct"], cop=agg["copula_selected"],
                coprel=100.0 * agg["copula_vs_nested_rel_error"],
                no=AGG_N_OUTER, ni=AGG_N_INNER, seed=AGG_SEED,
            ),
            author=ACTOR,
            phase=PHASE,
            peer_reviewer="APS_X2_Independent_Reviewer",
            assumption_owner="ChiefActuary",
        )
        rec.submit_for_peer_review(
            ACTOR,
            "FX sixth driver staged with G-FX gate + CIP-exact inner conditioning; "
            "credentialled calibration and six-driver OOS proxy validation required before approval.",
        )
        rec.submit_to_owner(
            ACTOR,
            "Owner review requested. Production sign-off withheld pending Phase 21 Tasks 2-5 "
            "and credentialled FX calibration.",
        )
        store.add_change_record(rec)
        added = True
        record_id = rec.record_id
        record_status = rec.status.value
        store.audit_trail.append(
            AuditEntry.governance(
                actor=ACTOR,
                phase=PHASE,
                event="ChangeRecord opened (OWNER_REVIEW) - FX sixth driver + G-FX gate",
                details={
                    "record_id": rec.record_id,
                    "gate": "G-FX",
                    "gate_passed": gate["passed"],
                    "fx_standalone_scr": agg["standalone_scr"]["fx"],
                    "nested_scr": agg["nested_scr"],
                    "affected_components": AFFECTED_COMPONENTS,
                    "mr012_action": mr_action,
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
        "mr012_action": mr_action,
        "mr012_status": store.risk_register.get("MR-012").mitigation_status.value,
        "added_change_record": added,
        "change_record_id": record_id,
        "change_record_status": record_status,
    }


STAGE_DIR = Path("/var/tmp/p21t1_stage")


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


def stage_outer() -> int:
    """Stage 1: outer states + analytic FX loss vector (fast)."""
    import numpy as np
    from par_model_v2.stochastic.esg_process import Measure

    STAGE_DIR.mkdir(parents=True, exist_ok=True)
    cfg = _cfg()
    agg = SixDriverFXRiskAggregator(_product())
    outer6 = agg._outer_states_6d(
        cfg.n_outer, cfg.capital_horizon_months, cfg.outer_measure, cfg.seed
    )
    np.savez(STAGE_DIR / "outer.npz", outer6=outer6,
             fx=agg.fx_exposure.liability_impact(outer6[:, 5]))
    print("stage outer done: {} states".format(len(outer6)))
    return 0


def stage_slice(i0: int, i1: int) -> int:
    """Stage 2: CRN component liabilities for outer rows [i0, i1)."""
    import numpy as np

    data = np.load(STAGE_DIR / "outer.npz")
    cfg = _cfg()
    agg = SixDriverFXRiskAggregator(_product())
    out = agg.component_liabilities_sliced(data["outer6"][:, :5], i0, i1, cfg)
    np.savez(STAGE_DIR / "slice_{:04d}_{:04d}.npz".format(i0, i1), **out)
    print("stage slice [{}, {}) done".format(i0, i1))
    return 0


def _assemble_precomputed():
    import numpy as np

    data = np.load(STAGE_DIR / "outer.npz")
    n = data["outer6"].shape[0]
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
    return pre


def main(precomputed=None) -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    gate = evaluate_g_fx_gate()

    cfg = _cfg()
    agg_report = SixDriverFXRiskAggregator(_product()).run_6d(
        config=cfg, precomputed=precomputed
    )
    agg = agg_report.to_dict()

    store = (
        GovernanceStore.from_json(GOV_PATH.read_text(encoding="utf-8"))
        if GOV_PATH.exists() else GovernanceStore()
    )
    gov = apply_governance(store, gate, agg)
    _write_card(gate, agg)

    if GOV_PATH.exists():
        GOV_PATH.write_text(store.to_json() + "\n", encoding="utf-8")

    report = {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": PHASE,
        "task": CHANGE_TITLE,
        "gate": gate,
        "aggregation": agg,
        "affected_components": AFFECTED_COMPONENTS,
        "standard_references": STANDARD_REFERENCES,
        "change_record_id": gov["change_record_id"],
        "change_record_status": gov["change_record_status"],
        "mr012_action": gov["mr012_action"],
        "mr012_status": gov["mr012_status"],
        "audit_integrity_ok": store.audit_trail.verify_all(),
        "change_records_total": len(store.change_records),
        "risk_register_summary": store.risk_register.summary(),
        "use_restrictions": six_driver_fx_use_restrictions(),
    }
    report["markdown"] = _markdown(report)
    JSON_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    MD_PATH.write_text(report["markdown"], encoding="utf-8")

    print("=== Phase 21 Task 1 - FX Sixth Driver + G-FX Gate ===")
    print("Gate G-FX         : {} ({}/{})".format(
        "PASS" if gate["passed"] else "FAIL", gate["n_passed"], gate["n_criteria"]))
    print("FX standalone SCR : {:.1f}".format(agg["standalone_scr"]["fx"]))
    print("Var-covar / nested: {:.1f} / {:.1f}".format(agg["var_covar_scr"], agg["nested_scr"]))
    print("Copula ({})  : {:.1f} (rel {:.1%})".format(
        agg["copula_selected"], agg["copula_scr"], agg["copula_vs_nested_rel_error"]))
    print("Verdict           : {}".format(agg["verdict"]))
    print("ChangeRecord      : {} ({})".format(gov["change_record_id"], gov["change_record_status"]))
    print("MR-012            : {} ({})".format(gov["mr012_status"], gov["mr012_action"]))
    print("Audit integrity   : {}".format(store.audit_trail.verify_all()))
    print("Report            : {}".format(JSON_PATH))
    return 0 if gate["passed"] and store.audit_trail.verify_all() else 1


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["outer", "slice", "finalise"], default=None)
    ap.add_argument("--i0", type=int, default=0)
    ap.add_argument("--i1", type=int, default=0)
    args = ap.parse_args()
    if args.stage == "outer":
        sys.exit(stage_outer())
    elif args.stage == "slice":
        sys.exit(stage_slice(args.i0, args.i1))
    elif args.stage == "finalise":
        sys.exit(main(precomputed=_assemble_precomputed()))
    sys.exit(main())
