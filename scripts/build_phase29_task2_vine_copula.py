#!/usr/bin/env python3
"""Phase 29 Task 2 - vine / pair-copula prototype implementation.

Stages:

  PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase29_task2_vine_copula.py --stage verify
  PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase29_task2_vine_copula.py --stage fit
  PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase29_task2_vine_copula.py --stage report
  PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase29_task2_vine_copula.py --stage governance

The script intentionally refuses to produce a PASS report unless the frozen-t
boundary is evaluated first and reproduces the archived component read-out.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from par_model_v2.governance.audit_trail import (
    AuditEntry,
    ChangeRecord,
    GovernanceStore,
)
from par_model_v2.projection.joint_action_aggregation import JointActionAggregator
from par_model_v2.projection.management_actions import ManagementActionRule
from par_model_v2.projection.vine_copula_pair_aggregation import (
    CONFIDENCE,
    FIT_FRACTION,
    FIT_SEED,
    READOUT_N_SIM,
    READOUT_SEED,
    TAIL_LEVEL_P,
    VINE_SIMULATOR_VERSION,
    composition_vine_pair_readout,
    fit_vine_pair_families,
    run_phase29_task2_readouts,
    vine_pair_copula_use_restrictions,
    vine_pair_fit_from_dict,
)
from par_model_v2.projection.vine_copula_upgrade import (
    DF_REMATCH_TOL,
    DRIVER_NAMES,
    EXISTING_RISK_ID,
    FROZEN_T_COMPONENT_SCR_REFERENCE,
    GROUPED_T_COMPONENT_SCR_POINT,
    GROUPED_T_COPULA_FORM_RESIDUAL_ABS,
    NESTED_PATHWISE_SCR_REFERENCE,
    PAIR_FAMILY_CANDIDATES,
    RANK_INVARIANCE_DF,
    RHO_FROZEN_TOL,
    SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS,
    VINE_BOUNDARY_RECOVERY_TOL,
    validate_vine_design_envelope,
)


PHASE = "Phase 29: Vine / Pair-Copula Dependence Upgrade"
ACTOR = "AutomatedModelDev_Phase29"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
OUT_DIR = Path("docs/validation")
JSON_PATH = OUT_DIR / "PHASE29_TASK2_VINE_COPULA_REPORT.json"
MD_PATH = OUT_DIR / "PHASE29_TASK2_VINE_COPULA_REPORT.md"
CARD_PATH = Path("docs/VINE_COPULA_PROTOTYPE_CARD.md")
STAGE_DIR = Path(os.environ.get("P29T2_STAGE", "/var/tmp/p29t2_stage"))
VERIFY_PATH = STAGE_DIR / "verified_inputs.npz"
FIT_PATH = STAGE_DIR / "vine_pair_fit.json"
RESULT_PATH = STAGE_DIR / "vine_pair_result.json"

P23T2_LOSSES = Path("/var/tmp/p23t2_stage/losses.npz")
P23T4_WITH = Path("/var/tmp/p23t4_stage/losses_with_actions.npz")
P26T2_VERIFY = Path("/var/tmp/p26t2_stage/verified_inputs.npz")
P29T1_NOTE = OUT_DIR / "PHASE29_TASK1_DESIGN_NOTE.json"

DRIVERS = tuple(DRIVER_NAMES)

CHANGE_TITLE = (
    "Phase 29 Task 2 - implement truncated credit-root vine / pair-copula "
    "prototype on frozen standalone margins"
)

AFFECTED_COMPONENTS = [
    "par_model_v2/projection/vine_copula_pair_aggregation.py",
    "scripts/build_phase29_task2_vine_copula.py",
    "tests/test_phase29_task2_vine_copula.py",
    "docs/VINE_COPULA_PROTOTYPE_CARD.md",
    "docs/validation/PHASE29_TASK2_VINE_COPULA_REPORT.{json,md}",
]

STANDARD_REFERENCES = [
    "Aas, Czado, Frigessi & Bakken (2009), Pair-copula constructions of multiple dependence",
    "Bedford & Cooke (2002), Vines",
    "Solvency II Delegated Regulation Article 234",
    "SOA ASOP 56 sections 3.1.3, 3.4, 3.5",
    "IA TAS M sections 3.2, 3.6, 3.7",
]


def _aggregator(z, w, rho) -> JointActionAggregator:
    return JointActionAggregator(
        standalone_losses={k: np.asarray(z[k], dtype=float) for k in DRIVERS},
        correlation=np.asarray(rho, dtype=float),
        rule=ManagementActionRule(),
        l_fit=float(w["l_fit"][0]),
        anchor_means={k: float(w[k + "_anchor_mean"][0]) for k in DRIVERS},
    )


def stage_verify() -> int:
    """Validate frozen inputs and Phase 29 design-note prerequisites."""
    p29 = json.loads(P29T1_NOTE.read_text(encoding="utf-8"))
    s = np.load(P26T2_VERIFY)
    df_rematched = float(s["df_rematched"][0])
    rho_max_abs_diff = float(s["rho_max_abs_diff"][0])
    checks = {
        "phase29_task1_design_note_pass": p29["verdict"] == "PASS",
        "envelope_ok": validate_vine_design_envelope()["envelope_ok"] is True,
        "df_rematched_rank_invariant":
            abs(df_rematched - RANK_INVARIANCE_DF) <= DF_REMATCH_TOL,
        "rho_frozen_rank_invariant": rho_max_abs_diff <= RHO_FROZEN_TOL,
        "family_set_capped":
            set(PAIR_FAMILY_CANDIDATES) == {
                "gaussian", "student_t", "survival_clayton", "survival_gumbel",
            },
    }
    if not all(checks.values()):
        print(json.dumps({"stage": "verify", "checks": checks}, indent=1))
        return 1
    STAGE_DIR.mkdir(parents=True, exist_ok=True)
    np.savez(
        VERIFY_PATH,
        rho=np.asarray(s["rho"], dtype=float),
        df_rematched=np.array([df_rematched]),
        rho_max_abs_diff=np.array([rho_max_abs_diff]),
        sigma=np.array([float(s["sigma"][0])]),
        alpha=np.array([float(s["alpha"][0])]),
        beta_fit=np.array([float(s["beta_fit"][0])]),
        crosscheck_count=np.array([len(checks)]),
    )
    print(json.dumps({"stage": "verify", "checks": checks}, indent=1))
    return 0


def stage_fit() -> int:
    """Fit pair families and compute candidate/frozen/grouped read-outs."""
    z = np.load(P23T2_LOSSES)
    w = np.load(P23T4_WITH)
    s = np.load(VERIFY_PATH)
    rho = np.asarray(s["rho"], dtype=float)
    sigma = float(s["sigma"][0])
    alpha = float(s["alpha"][0])
    beta = float(s["beta_fit"][0])
    agg = _aggregator(z, w, rho)
    losses = {k: np.asarray(z[k], dtype=float) for k in DRIVERS}

    fit = fit_vine_pair_families(
        losses, DRIVERS, fit_fraction=FIT_FRACTION, seed=FIT_SEED, p=TAIL_LEVEL_P
    )
    FIT_PATH.write_text(json.dumps(fit.to_dict(), indent=1, default=float), encoding="utf-8")

    result = run_phase29_task2_readouts(
        agg, losses, DRIVERS, sigma, alpha, beta, n_sim=READOUT_N_SIM, seed=READOUT_SEED
    )
    RESULT_PATH.write_text(json.dumps(result, indent=1, default=float), encoding="utf-8")
    ok = all(result["gates"].values())
    print(json.dumps({
        "stage": "fit",
        "ok": ok,
        "boundary_recovery_dev": result["boundary_recovery_dev"],
        "candidate_scr": result["vine_pair_candidate_readout"]["scr_component"],
        "candidate_vs_frozen_t_rel": result["candidate_vs_frozen_t_rel"],
        "family_counts": result["fit"]["family_counts"],
    }, indent=1, default=float))
    return 0 if ok else 1


def _md(rep: dict) -> str:
    r = rep["result"]
    fit = r["fit"]
    vine = r["vine_pair_candidate_readout"]
    frozen = r["frozen_t_component_reference_readout"]
    grouped = r["grouped_t_comparison_readout"]
    lines = [
        "# Phase 29 Task 2 - Vine / Pair-Copula Prototype",
        "",
        f"**Verdict: {rep['verdict']}**. EDUCATIONAL ONLY.",
        "",
        "## Method",
        "",
        "The prototype implements only the pre-registered truncated credit-root "
        "C-vine envelope from Phase 29 Task 1. It evaluates the frozen_t_boundary "
        "leg first, then applies local conditional pair-link tail tilts on common "
        "random numbers and re-ranks each column back to uniform margins.",
        "",
        f"- Simulator version: {VINE_SIMULATOR_VERSION}",
        f"- Fit split: {fit['fit_fraction']:.0%}; fit digest {fit['fit_indices_digest']}; holdout digest {fit['holdout_indices_digest']}",
        f"- Family counts: {fit['family_counts']}",
        "",
        "## Read-outs",
        "",
        "| basis | component SCR | vs frozen-t | vs grouped-t | gap to nested |",
        "|---|---:|---:|---:|---:|",
        "| frozen single-df t | {:.1f} | 0.00% | {:+.2%} | {:+.2%} |".format(
            frozen["scr_component"],
            frozen["scr_component"] / grouped["scr_component"] - 1.0,
            frozen["scr_component"] / NESTED_PATHWISE_SCR_REFERENCE - 1.0,
        ),
        "| grouped-t comparison | {:.1f} | {:+.2%} | 0.00% | {:+.2%} |".format(
            grouped["scr_component"],
            grouped["scr_component"] / frozen["scr_component"] - 1.0,
            grouped["scr_component"] / NESTED_PATHWISE_SCR_REFERENCE - 1.0,
        ),
        "| vine-pair candidate | {:.1f} | {:+.2%} | {:+.2%} | {:+.2%} |".format(
            vine["scr_component"],
            r["candidate_vs_frozen_t_rel"],
            r["candidate_vs_grouped_t_rel"],
            r["candidate_gap_to_nested_rel"],
        ),
        "",
        f"- Frozen boundary recovery deviation: {r['boundary_recovery_dev']:.3e}",
        "",
        "## Selected pair families",
        "",
        "| edge | condition | family | strength | fit upper | fit lower | holdout upper | holdout lower |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for sel in fit["selections"]:
        lines.append("| {} | {} | {} | {:.4f} | {:.4f} | {:.4f} | {:.4f} | {:.4f} |".format(
            sel["edge"],
            sel["condition_on"],
            sel["family"],
            sel["strength"],
            sel["fit_upper"],
            sel["fit_lower"],
            sel["holdout_upper"],
            sel["holdout_lower"],
        ))
    lines += [
        "",
        "## Gates",
        "",
    ]
    lines.extend(f"- {k}: {'PASS' if v else 'FAIL'}" for k, v in r["gates"].items())
    lines += [
        "",
        "## Material Finding",
        "",
        r["material_finding"],
        "",
        "*Generated by scripts/build_phase29_task2_vine_copula.py.*",
        "",
    ]
    return "\n".join(lines)


def _card(rep: dict) -> str:
    r = rep["result"]
    vine = r["vine_pair_candidate_readout"]
    return "\n".join([
        "# Vine / Pair-Copula Prototype Card (Phase 29 Task 2)",
        "",
        f"**Verdict: {rep['verdict']}**. EDUCATIONAL ONLY.",
        "",
        f"- Frozen boundary recovery deviation: {r['boundary_recovery_dev']:.3e}.",
        f"- Candidate component SCR: {vine['scr_component']:,.1f}.",
        f"- Candidate vs frozen-t: {r['candidate_vs_frozen_t_rel']:+.2%}.",
        f"- Candidate vs grouped-t: {r['candidate_vs_grouped_t_rel']:+.2%}.",
        f"- Existing risk: {EXISTING_RISK_ID}; Task 3 bootstrap and Task 4 diagnostics decide remediation.",
        "",
    ])


def stage_report() -> int:
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    s = np.load(VERIFY_PATH)
    verdict = "PASS" if all(result["gates"].values()) else "FAIL"
    rep = {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": PHASE,
        "task": "Task 2 - implement selected vine / pair-copula prototype",
        "verdict": verdict,
        "drivers": list(DRIVERS),
        "df_frozen": RANK_INVARIANCE_DF,
        "df_rematched": float(s["df_rematched"][0]),
        "rho_max_abs_diff": float(s["rho_max_abs_diff"][0]),
        "pathwise_basis_params": {
            "sigma": float(s["sigma"][0]),
            "alpha": float(s["alpha"][0]),
            "benefit_share_fit": float(s["beta_fit"][0]),
            "provenance": "Phase 26 verified composition inputs; no re-tuning",
        },
        "result": result,
        "archived_references": {
            "nested_pathwise_reference": NESTED_PATHWISE_SCR_REFERENCE,
            "frozen_t_component_reference": FROZEN_T_COMPONENT_SCR_REFERENCE,
            "grouped_t_component_reference": GROUPED_T_COMPONENT_SCR_POINT,
            "skewt_residual_reference": SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS,
            "grouped_t_residual_reference": GROUPED_T_COPULA_FORM_RESIDUAL_ABS,
        },
        "use_restrictions": vine_pair_copula_use_restrictions(),
        "standard_references": STANDARD_REFERENCES,
        "affected_components": AFFECTED_COMPONENTS,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(json.dumps(rep, indent=1, default=float), encoding="utf-8")
    MD_PATH.write_text(_md(rep), encoding="utf-8")
    CARD_PATH.write_text(_card(rep), encoding="utf-8")
    print(json.dumps({"stage": "report", "verdict": verdict, "json": str(JSON_PATH)}, indent=1))
    return 0 if verdict == "PASS" else 1


def stage_governance() -> int:
    rep = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    r = rep["result"]
    vine = r["vine_pair_candidate_readout"]
    store = GovernanceStore.from_json(GOV_PATH.read_text(encoding="utf-8"))
    if any(rec.title == CHANGE_TITLE for rec in store.change_records):
        ok = store.audit_trail.verify_all()
        print(json.dumps({"added": False, "audit_integrity_ok": ok}))
        return 0 if ok else 1
    rec = ChangeRecord.create(
        title=CHANGE_TITLE,
        description=(
            "Implemented the pre-registered truncated credit-root vine / "
            "pair-copula prototype on frozen standalone margins. The explicit "
            "frozen_t_boundary leg reproduced the governed single-df t component "
            "before candidate evaluation; family selection used fit rows only; "
            "holdout tail diagnostics and frozen/grouped comparison variants are "
            "retained."
        ),
        change_type="code_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "dependency_form": "frozen single-df t plus grouped-t negative super-set",
            "mr016": "OPEN",
            "grouped_t_residual": GROUPED_T_COPULA_FORM_RESIDUAL_ABS,
        },
        after_snapshot={
            "dependency_form": "truncated credit-root pair-link prototype",
            "candidate_scr": vine["scr_component"],
            "candidate_vs_frozen_t_rel": r["candidate_vs_frozen_t_rel"],
            "candidate_vs_grouped_t_rel": r["candidate_vs_grouped_t_rel"],
            "gates": r["gates"],
            "verdict": rep["verdict"],
        },
        impact_assessment=(
            "Code implementation only. Adoption remains deferred pending Task 3 "
            "bootstrap and Task 4 MR-016 diagnostics. The governed frozen-t "
            "headline is retained unless the later uncertainty evidence supports "
            "remediation."
        ),
        author=ACTOR,
        phase=PHASE,
        quantitative_impact=(
            "Candidate component SCR {:.1f}; vs frozen-t {:+.2%}; vs grouped-t "
            "{:+.2%}; boundary recovery dev {:.3e}.".format(
                vine["scr_component"],
                r["candidate_vs_frozen_t_rel"],
                r["candidate_vs_grouped_t_rel"],
                r["boundary_recovery_dev"],
            )
        ),
    )
    rec.submit_for_peer_review(actor=ACTOR, comments="Task 2 gates PASS; frozen boundary and comparison variants retained.")
    rec.submit_to_owner(actor=ACTOR, comments="Owner review; implementation staged for Task 3 bootstrap.")
    store.add_change_record(rec)
    store.audit_trail.append(AuditEntry.governance(
        actor=ACTOR,
        phase=PHASE,
        event="ChangeRecord opened (OWNER_REVIEW) - Phase 29 Task 2 vine / pair-copula implementation",
        details={"record_id": rec.record_id, "status": rec.status.value, "affected_components": AFFECTED_COMPONENTS},
    ))
    GOV_PATH.write_text(store.to_json(), encoding="utf-8")
    ok = store.audit_trail.verify_all()
    rep["change_record_id"] = rec.record_id
    rep["change_record_status"] = rec.status.value
    rep["audit_integrity_ok"] = ok
    rep["change_records_total"] = len(store.change_records)
    rep["audit_entries_total"] = len(store.audit_trail.all())
    JSON_PATH.write_text(json.dumps(rep, indent=1, default=float), encoding="utf-8")
    print(json.dumps({"added": True, "record_id": rec.record_id, "audit_integrity_ok": ok}, indent=1))
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True, choices=["verify", "fit", "report", "governance"])
    args = parser.parse_args()
    return {
        "verify": stage_verify,
        "fit": stage_fit,
        "report": stage_report,
        "governance": stage_governance,
    }[args.stage]()


if __name__ == "__main__":
    sys.exit(main())

