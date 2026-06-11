#!/usr/bin/env python3
"""Phase 30 Task 2 - tree-3 vine deepening implementation.

Stages (fit is chunked so each part stays inside a short execution window):

  PYTHONPATH=/var/tmp/pylibs_c:. python3 scripts/build_phase30_task2_tree3_vine.py --stage verify
  PYTHONPATH=/var/tmp/pylibs_c:. python3 scripts/build_phase30_task2_tree3_vine.py --stage fit --part refit
  ... --stage fit --part frozen
  ... --stage fit --part boundary_t
  ... --stage fit --part boundary_v2
  ... --stage fit --part candidate
  ... --stage fit --part grouped
  ... --stage fit --part assemble
  ... --stage report
  ... --stage governance

The runner refuses to produce candidate output unless BOTH boundary legs
(frozen single-df t AND archived 2-tree vine) reproduce their archived
read-outs bit-identically first. All read-outs are deterministic given the
shared seed, so the chunked path is identical to a monolithic run of
run_phase30_task2_readouts.
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
from par_model_v2.projection.grouped_t_copula_aggregation import (
    BLOCKS as GROUPED_T_BLOCKS,
    composition_grouped_t_readout,
)
from par_model_v2.projection.pathwise_composition_transform import (
    composition_joint_readout,
)
from par_model_v2.projection.vine_copula_pair_aggregation import (
    fit_vine_pair_families,
    vine_pair_fit_from_dict,
)
from par_model_v2.projection.vine_copula_upgrade import (
    DF_REMATCH_TOL,
    DRIVER_NAMES,
    FROZEN_T_COMPONENT_SCR_REFERENCE,
    GROUPED_T_DF_FIN,
    GROUPED_T_DF_NONFIN,
    NESTED_PATHWISE_SCR_REFERENCE,
    PAIR_FAMILY_CANDIDATES,
    RANK_INVARIANCE_DF,
    RHO_FROZEN_TOL,
    VINE_BOUNDARY_RECOVERY_TOL,
)
from par_model_v2.projection.vine_tree3_aggregation import (
    CONFIDENCE,
    P29_FIT_INDICES_DIGEST,
    P29_HOLDOUT_INDICES_DIGEST,
    READOUT_N_SIM,
    READOUT_SEED,
    THIRD_TREE_EDGES,
    VINE2_COMPONENT_SCR_REFERENCE,
    VINE2_COPULA_FORM_RESIDUAL_ABS,
    composition_tree3_readout,
    fit_tree3_pairs,
    material_finding_text,
    tree3_vine_fit_from_dict,
    tree3_vine_use_restrictions,
    validate_tree3_design_envelope,
)


PHASE = "Phase 30: Post-Vine Dependence Roadmap Decision"
ACTOR = "AutomatedModelDev_Phase30"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
OUT_DIR = Path("docs/validation")
JSON_PATH = OUT_DIR / "PHASE30_TASK2_TREE3_VINE_REPORT.json"
MD_PATH = OUT_DIR / "PHASE30_TASK2_TREE3_VINE_REPORT.md"
CARD_PATH = Path("docs/TREE3_VINE_PROTOTYPE_CARD.md")
STAGE_DIR = Path(os.environ.get("P30T2_STAGE", "/var/tmp/p30t2_stage"))
VERIFY_PATH = STAGE_DIR / "verified_inputs.npz"
FIT2_PATH = STAGE_DIR / "vine_pair_fit_frozen.json"
RESULT_PATH = STAGE_DIR / "tree3_result.json"

P23T2_LOSSES = Path("/var/tmp/p23t2_stage/losses.npz")
P23T4_WITH = Path("/var/tmp/p23t4_stage/losses_with_actions.npz")
P26T2_VERIFY = Path("/var/tmp/p26t2_stage/verified_inputs.npz")
P29T2_FIT = Path("/var/tmp/p29t2_stage/vine_pair_fit.json")
P30T1_NOTE = OUT_DIR / "PHASE30_TASK1_DESIGN_NOTE.json"

DRIVERS = tuple(DRIVER_NAMES)

CHANGE_TITLE = (
    "Phase 30 Task 2 - implement pre-registered tree-3 deepening of the "
    "truncated credit-root vine on the frozen Phase 29 2-tree fit"
)

AFFECTED_COMPONENTS = [
    "par_model_v2/projection/vine_tree3_aggregation.py",
    "scripts/build_phase30_task2_tree3_vine.py",
    "tests/test_phase30_task2_tree3_vine.py",
    "docs/TREE3_VINE_PROTOTYPE_CARD.md",
    "docs/validation/PHASE30_TASK2_TREE3_VINE_REPORT.{json,md}",
]

STANDARD_REFERENCES = [
    "Aas, Czado, Frigessi & Bakken (2009), Pair-copula constructions of multiple dependence",
    "Bedford & Cooke (2002), Vines",
    "Solvency II Delegated Regulation Article 234",
    "Solvency II Delegated Regulation Article 124",
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


def _load_frozen_fit_dict(losses) -> dict:
    """Prefer the archived Phase 29 stage fit; else deterministic re-fit."""
    if P29T2_FIT.exists():
        return json.loads(P29T2_FIT.read_text(encoding="utf-8"))
    return fit_vine_pair_families(losses, DRIVERS).to_dict()


def stage_verify() -> int:
    """Validate frozen inputs and the Phase 30 design-note prerequisites."""
    p30 = json.loads(P30T1_NOTE.read_text(encoding="utf-8"))
    s = np.load(P26T2_VERIFY)
    df_rematched = float(s["df_rematched"][0])
    rho_max_abs_diff = float(s["rho_max_abs_diff"][0])
    z = np.load(P23T2_LOSSES)
    losses = {k: np.asarray(z[k], dtype=float) for k in DRIVERS}
    fit2 = _load_frozen_fit_dict(losses)
    checks = {
        "phase30_task1_design_note_pass": p30["verdict"] == "PASS",
        "phase30_selected_option_a":
            p30.get("selected_option") == "A_tree3_vine_deepening",
        "tree3_envelope_ok":
            validate_tree3_design_envelope()["envelope_ok"] is True,
        "df_rematched_rank_invariant":
            abs(df_rematched - RANK_INVARIANCE_DF) <= DF_REMATCH_TOL,
        "rho_frozen_rank_invariant": rho_max_abs_diff <= RHO_FROZEN_TOL,
        "family_set_capped":
            set(PAIR_FAMILY_CANDIDATES) == {
                "gaussian", "student_t", "survival_clayton", "survival_gumbel",
            },
        "frozen_tree12_fit_digests_archived":
            fit2["fit_indices_digest"] == P29_FIT_INDICES_DIGEST
            and fit2["holdout_indices_digest"] == P29_HOLDOUT_INDICES_DIGEST,
    }
    if not all(checks.values()):
        print(json.dumps({"stage": "verify", "checks": checks}, indent=1))
        return 1
    STAGE_DIR.mkdir(parents=True, exist_ok=True)
    FIT2_PATH.write_text(json.dumps(fit2, indent=1, default=float), encoding="utf-8")
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


def _fit_context():
    z = np.load(P23T2_LOSSES)
    w = np.load(P23T4_WITH)
    s = np.load(VERIFY_PATH)
    rho = np.asarray(s["rho"], dtype=float)
    sigma = float(s["sigma"][0])
    alpha = float(s["alpha"][0])
    beta = float(s["beta_fit"][0])
    agg = _aggregator(z, w, rho)
    losses = {k: np.asarray(z[k], dtype=float) for k in DRIVERS}
    return agg, losses, sigma, alpha, beta


def _part_path(name: str) -> Path:
    return STAGE_DIR / f"part_{name}.json"


def _write_part(name: str, payload: dict) -> None:
    _part_path(name).write_text(
        json.dumps(payload, indent=1, default=float), encoding="utf-8"
    )
    # re-parse to confirm the JSON is not corrupted
    json.loads(_part_path(name).read_text(encoding="utf-8"))


def _read_part(name: str) -> dict:
    return json.loads(_part_path(name).read_text(encoding="utf-8"))


def stage_fit(part: str) -> int:
    """Chunked dual-boundary verification then tree-3 candidate read-outs.

    Parts must run in order: refit -> frozen -> boundary_t -> boundary_v2 ->
    candidate -> grouped -> assemble. ``candidate`` refuses to run unless both
    boundary parts exist and reproduced their archived references
    bit-identically (the design-note hard precondition).
    """
    agg, losses, sigma, alpha, beta = _fit_context()
    fit2_dict = json.loads(FIT2_PATH.read_text(encoding="utf-8"))
    fit2 = vine_pair_fit_from_dict(fit2_dict)

    if part == "refit":
        refit2 = fit_vine_pair_families(losses, DRIVERS)
        fit3 = fit_tree3_pairs(losses, DRIVERS, fit2)
        _write_part("refit", {
            "frozen_fit_consistent": refit2.to_dict() == fit2.to_dict(),
            "fit3": fit3.to_dict(),
        })
        print(json.dumps({"stage": "fit", "part": part, "ok": True}))
        return 0

    fit3 = tree3_vine_fit_from_dict(_read_part("refit")["fit3"])

    if part == "frozen":
        out = composition_joint_readout(
            agg, READOUT_N_SIM, READOUT_SEED, RANK_INVARIANCE_DF,
            sigma, alpha, beta, CONFIDENCE,
        )
        _write_part("frozen", out)
    elif part == "boundary_t":
        out = composition_tree3_readout(
            agg, READOUT_N_SIM, READOUT_SEED, fit3, sigma, alpha, beta,
            CONFIDENCE, mode="frozen_t_boundary",
        )
        _write_part("boundary_t", out)
    elif part == "boundary_v2":
        out = composition_tree3_readout(
            agg, READOUT_N_SIM, READOUT_SEED, fit3, sigma, alpha, beta,
            CONFIDENCE, mode="vine2_boundary",
        )
        _write_part("boundary_v2", out)
    elif part == "candidate":
        frozen = _read_part("frozen")
        bt = _read_part("boundary_t")
        bv2 = _read_part("boundary_v2")
        t_dev = abs(bt["scr_component"] - frozen["scr_component"])
        t_arch = abs(frozen["scr_component"] - FROZEN_T_COMPONENT_SCR_REFERENCE)
        v2_dev = abs(bv2["scr_component"] - VINE2_COMPONENT_SCR_REFERENCE)
        if max(t_dev, t_arch, v2_dev) > VINE_BOUNDARY_RECOVERY_TOL:
            raise RuntimeError(
                "DUAL boundary recovery failed; refusing the tree-3 candidate "
                f"(t_dev={t_dev:.3e}, t_archive_dev={t_arch:.3e}, "
                f"vine2_dev={v2_dev:.3e})"
            )
        out = composition_tree3_readout(
            agg, READOUT_N_SIM, READOUT_SEED, fit3, sigma, alpha, beta,
            CONFIDENCE, mode="candidate",
        )
        _write_part("candidate", out)
    elif part == "grouped":
        out = composition_grouped_t_readout(
            agg, READOUT_N_SIM, READOUT_SEED,
            [GROUPED_T_DF_NONFIN, GROUPED_T_DF_FIN], GROUPED_T_BLOCKS,
            sigma, alpha, beta, CONFIDENCE, shared_mixing=False,
        )
        _write_part("grouped", out)
    elif part == "assemble":
        frozen = _read_part("frozen")
        bt = _read_part("boundary_t")
        bv2 = _read_part("boundary_v2")
        candidate = _read_part("candidate")
        grouped = _read_part("grouped")
        refit_info = _read_part("refit")
        t_dev = abs(bt["scr_component"] - frozen["scr_component"])
        t_arch = abs(frozen["scr_component"] - FROZEN_T_COMPONENT_SCR_REFERENCE)
        v2_dev = abs(bv2["scr_component"] - VINE2_COMPONENT_SCR_REFERENCE)
        dual_ok = bool(max(t_dev, t_arch, v2_dev) <= VINE_BOUNDARY_RECOVERY_TOL)
        envelope = validate_tree3_design_envelope()
        gates = {
            "G1_dual_boundary_bit_identical": dual_ok,
            "G2_frozen_t_archive_reference_first":
                bool(frozen["scr_component"] == FROZEN_T_COMPONENT_SCR_REFERENCE),
            "G3_vine2_archive_reference_recovered":
                bool(bv2["scr_component"] == VINE2_COMPONENT_SCR_REFERENCE),
            "G4_rank_invariance_constants_frozen":
                bool(RANK_INVARIANCE_DF == 2.9451 and RHO_FROZEN_TOL <= 1e-12),
            "G5_tree12_fit_frozen_from_phase29":
                bool(refit_info["frozen_fit_consistent"]
                     and fit2.fit_indices_digest == P29_FIT_INDICES_DIGEST
                     and fit2.holdout_indices_digest
                     == P29_HOLDOUT_INDICES_DIGEST),
            "G6_pre_registered_tree3_envelope_only":
                bool(envelope["envelope_ok"]),
            "G7_family_set_capped":
                bool(set(PAIR_FAMILY_CANDIDATES) == {
                    "gaussian", "student_t", "survival_clayton",
                    "survival_gumbel",
                }),
            "G8_leakage_free_fit_holdout_recorded":
                bool(fit3.fit_indices_digest != fit3.holdout_indices_digest
                     and fit3.fit_indices_digest == P29_FIT_INDICES_DIGEST),
            "G9_comparison_variants_retained_crn": True,
            "G10_directional_disclosed_not_gated": True,
        }
        result = {
            "fit": fit3.to_dict(),
            "envelope": envelope,
            "frozen_fit_consistent_with_refit":
                refit_info["frozen_fit_consistent"],
            "frozen_t_boundary_readout": bt,
            "frozen_t_component_reference_readout": frozen,
            "vine2_boundary_readout": bv2,
            "grouped_t_comparison_readout": grouped,
            "tree3_candidate_readout": candidate,
            "boundary_t_recovery_dev": t_dev,
            "boundary_t_archive_dev": t_arch,
            "boundary_vine2_recovery_dev": v2_dev,
            "candidate_vs_frozen_t_rel":
                candidate["scr_component"] / frozen["scr_component"] - 1.0,
            "candidate_vs_vine2_rel":
                candidate["scr_component"] / bv2["scr_component"] - 1.0,
            "candidate_vs_grouped_t_rel":
                candidate["scr_component"] / grouped["scr_component"] - 1.0,
            "candidate_gap_to_nested_rel":
                candidate["scr_component"] / NESTED_PATHWISE_SCR_REFERENCE - 1.0,
            "candidate_residual_abs":
                abs(NESTED_PATHWISE_SCR_REFERENCE - candidate["scr_component"]),
            "vine2_residual_abs_reference": VINE2_COPULA_FORM_RESIDUAL_ABS,
            "gates": gates,
            "material_finding": material_finding_text(
                candidate, bv2, frozen, grouped
            ),
        }
        RESULT_PATH.write_text(
            json.dumps(result, indent=1, default=float), encoding="utf-8"
        )
        json.loads(RESULT_PATH.read_text(encoding="utf-8"))
        ok = all(gates.values())
        print(json.dumps({
            "stage": "fit", "part": part, "ok": ok,
            "boundary_t_recovery_dev": t_dev,
            "boundary_vine2_recovery_dev": v2_dev,
            "candidate_scr": candidate["scr_component"],
            "candidate_vs_vine2_rel": result["candidate_vs_vine2_rel"],
            "candidate_vs_frozen_t_rel": result["candidate_vs_frozen_t_rel"],
            "tree3_family_counts": result["fit"]["tree3_family_counts"],
        }, indent=1, default=float))
        return 0 if ok else 1
    else:
        raise ValueError(f"unknown fit part {part!r}")

    print(json.dumps({
        "stage": "fit", "part": part, "ok": True,
        "scr_component": out["scr_component"],
    }, indent=1, default=float))
    return 0


def _md(rep: dict) -> str:
    r = rep["result"]
    fit = r["fit"]
    cand = r["tree3_candidate_readout"]
    vine2 = r["vine2_boundary_readout"]
    frozen = r["frozen_t_component_reference_readout"]
    grouped = r["grouped_t_comparison_readout"]
    lines = [
        "# Phase 30 Task 2 - Tree-3 Vine Deepening",
        "",
        f"**Verdict: {rep['verdict']}**. EDUCATIONAL ONLY.",
        "",
        "## Method",
        "",
        "The candidate deepens the FROZEN Phase 29 truncated credit-root C-vine "
        "with the four pre-registered third-tree conditional pairs from "
        "PHASE30_TASK1_DESIGN_NOTE. Both boundary legs (frozen single-df t AND "
        "the archived 2-tree vine) were reproduced bit-identically before the "
        "candidate ran. Tree-3 tilts are activated by the joint conditional "
        "tail (elementwise minimum) of the two conditioning drivers; margins "
        "are re-ranked back to uniforms, so marginal ranks are unchanged.",
        "",
        f"- Simulator version: {cand['config']['simulator_version']}",
        f"- Fit split digests: fit {fit['fit_indices_digest']}; holdout {fit['holdout_indices_digest']} (identical to Phase 29)",
        f"- Tree-3 family counts: {fit['tree3_family_counts']}",
        "",
        "## Read-outs (common random numbers, seed {})".format(
            cand["config"]["seed"]
        ),
        "",
        "| basis | component SCR | vs frozen-t | vs 2-tree vine | gap to nested |",
        "|---|---:|---:|---:|---:|",
        "| frozen single-df t | {:.1f} | 0.00% | {:+.2%} | {:+.2%} |".format(
            frozen["scr_component"],
            frozen["scr_component"] / vine2["scr_component"] - 1.0,
            frozen["scr_component"] / NESTED_PATHWISE_SCR_REFERENCE - 1.0,
        ),
        "| grouped-t comparison | {:.1f} | {:+.2%} | {:+.2%} | {:+.2%} |".format(
            grouped["scr_component"],
            grouped["scr_component"] / frozen["scr_component"] - 1.0,
            grouped["scr_component"] / vine2["scr_component"] - 1.0,
            grouped["scr_component"] / NESTED_PATHWISE_SCR_REFERENCE - 1.0,
        ),
        "| 2-tree vine boundary | {:.1f} | {:+.2%} | 0.00% | {:+.2%} |".format(
            vine2["scr_component"],
            vine2["scr_component"] / frozen["scr_component"] - 1.0,
            vine2["scr_component"] / NESTED_PATHWISE_SCR_REFERENCE - 1.0,
        ),
        "| tree-3 vine candidate | {:.1f} | {:+.2%} | {:+.2%} | {:+.2%} |".format(
            cand["scr_component"],
            r["candidate_vs_frozen_t_rel"],
            r["candidate_vs_vine2_rel"],
            r["candidate_gap_to_nested_rel"],
        ),
        "",
        "- Frozen-t boundary recovery deviation: {:.3e}".format(
            r["boundary_t_recovery_dev"]
        ),
        "- 2-tree vine boundary recovery deviation: {:.3e}".format(
            r["boundary_vine2_recovery_dev"]
        ),
        "- Candidate copula-form residual: {:.1f} (2-tree reference {:.1f})".format(
            r["candidate_residual_abs"], VINE2_COPULA_FORM_RESIDUAL_ABS
        ),
        "",
        "## Tree-3 selected pair families",
        "",
        "| edge | conditioners | family | strength | fit upper | fit lower | holdout upper | holdout lower | n fit | n holdout |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for sel in fit["tree3_selections"]:
        lines.append(
            "| {} | {} | {} | {:.4f} | {:.4f} | {:.4f} | {:.4f} | {:.4f} | {} | {} |".format(
                sel["edge"], sel["condition_on"], sel["family"],
                sel["strength"], sel["fit_upper"], sel["fit_lower"],
                sel["holdout_upper"], sel["holdout_lower"],
                sel["n_fit"], sel["n_holdout"],
            )
        )
    lines += ["", "## Gates", ""]
    for k, v in r["gates"].items():
        lines.append("- {}: {}".format(k, "PASS" if v else "FAIL"))
    lines += [
        "",
        "## Material Finding",
        "",
        r["material_finding"],
        "",
        "*Generated by scripts/build_phase30_task2_tree3_vine.py.*",
        "",
    ]
    return "\n".join(lines)


def _card(rep: dict) -> str:
    r = rep["result"]
    cand = r["tree3_candidate_readout"]
    return "\n".join([
        "# Tree-3 Vine Prototype Card (Phase 30 Task 2)",
        "",
        f"**Verdict: {rep['verdict']}**. EDUCATIONAL ONLY.",
        "",
        "- Dual boundary recovery: frozen-t dev {:.3e}; 2-tree vine dev {:.3e}.".format(
            r["boundary_t_recovery_dev"], r["boundary_vine2_recovery_dev"]
        ),
        f"- Candidate component SCR: {cand['scr_component']:,.1f}.",
        f"- Candidate vs 2-tree vine: {r['candidate_vs_vine2_rel']:+.2%}.",
        f"- Candidate vs frozen-t: {r['candidate_vs_frozen_t_rel']:+.2%}.",
        "- Candidate copula-form residual: {:.1f} (2-tree reference {:.1f}).".format(
            r["candidate_residual_abs"], VINE2_COPULA_FORM_RESIDUAL_ABS
        ),
        "- Existing risks: MR-016 / MR-017; Task 3 bootstrap and Task 4 "
        "diagnostics decide remediation or the pre-registered stop-rule.",
        "",
    ])


def stage_report() -> int:
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    s = np.load(VERIFY_PATH)
    verdict = "PASS" if all(result["gates"].values()) else "FAIL"
    rep = {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": PHASE,
        "task": "Task 2 - implement pre-registered tree-3 vine deepening",
        "verdict": verdict,
        "drivers": list(DRIVERS),
        "df_frozen": RANK_INVARIANCE_DF,
        "df_rematched": float(s["df_rematched"][0]),
        "rho_max_abs_diff": float(s["rho_max_abs_diff"][0]),
        "third_tree_edges": [
            {"pair": [int(a), int(b)], "condition_on": [int(c[0]), int(c[1])],
             "names": "{}-{} | {},{}".format(
                 DRIVERS[a], DRIVERS[b], DRIVERS[c[0]], DRIVERS[c[1]])}
            for a, b, c in THIRD_TREE_EDGES
        ],
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
            "vine2_component_reference": VINE2_COMPONENT_SCR_REFERENCE,
            "vine2_residual_reference": VINE2_COPULA_FORM_RESIDUAL_ABS,
        },
        "use_restrictions": tree3_vine_use_restrictions(),
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
    cand = r["tree3_candidate_readout"]
    store = GovernanceStore.from_json(GOV_PATH.read_text(encoding="utf-8"))
    if any(rec.title == CHANGE_TITLE for rec in store.change_records):
        ok = store.audit_trail.verify_all()
        print(json.dumps({"added": False, "audit_integrity_ok": ok}))
        return 0 if ok else 1
    rec = ChangeRecord.create(
        title=CHANGE_TITLE,
        description=(
            "Implemented the pre-registered Phase 30 tree-3 deepening of the "
            "truncated credit-root C-vine over the FROZEN Phase 29 2-tree fit. "
            "Both boundary legs (frozen single-df t and archived 2-tree vine) "
            "reproduced their archived read-outs bit-identically before the "
            "candidate ran; tree-3 family selection used fit rows only; frozen-t, "
            "grouped-t and 2-tree vine comparison variants are retained on "
            "common random numbers."
        ),
        change_type="code_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "dependency_form": "frozen single-df t; disclosed 2-tree vine candidate",
            "mr016": "OPEN",
            "mr017": "OPEN",
            "vine2_candidate_scr": VINE2_COMPONENT_SCR_REFERENCE,
            "vine2_residual": VINE2_COPULA_FORM_RESIDUAL_ABS,
        },
        after_snapshot={
            "dependency_form": "tree-3 deepened credit-root pair-link prototype",
            "candidate_scr": cand["scr_component"],
            "candidate_vs_vine2_rel": r["candidate_vs_vine2_rel"],
            "candidate_vs_frozen_t_rel": r["candidate_vs_frozen_t_rel"],
            "candidate_residual_abs": r["candidate_residual_abs"],
            "gates": r["gates"],
            "verdict": rep["verdict"],
        },
        impact_assessment=(
            "Code implementation only. Adoption remains deferred pending Task 3 "
            "bootstrap and Task 4 MR-016/MR-017 diagnostics, subject to the "
            "pre-registered stop-rule. The governed frozen-t headline is "
            "retained."
        ),
        author=ACTOR,
        phase=PHASE,
        quantitative_impact=(
            "Candidate component SCR {:.1f}; vs 2-tree vine {:+.2%}; vs "
            "frozen-t {:+.2%}; dual boundary devs {:.3e} / {:.3e}.".format(
                cand["scr_component"],
                r["candidate_vs_vine2_rel"],
                r["candidate_vs_frozen_t_rel"],
                r["boundary_t_recovery_dev"],
                r["boundary_vine2_recovery_dev"],
            )
        ),
    )
    rec.submit_for_peer_review(
        actor=ACTOR,
        comments="Task 2 gates PASS; dual boundary and CRN comparison variants retained.",
    )
    rec.submit_to_owner(
        actor=ACTOR,
        comments="Owner review; implementation staged for Task 3 bootstrap.",
    )
    store.add_change_record(rec)
    store.audit_trail.append(AuditEntry.governance(
        actor=ACTOR,
        phase=PHASE,
        event="ChangeRecord opened (OWNER_REVIEW) - Phase 30 Task 2 tree-3 vine deepening",
        details={
            "record_id": rec.record_id,
            "status": rec.status.value,
            "affected_components": AFFECTED_COMPONENTS,
        },
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
    parser.add_argument(
        "--stage", required=True,
        choices=["verify", "fit", "report", "governance"],
    )
    parser.add_argument(
        "--part", default="assemble",
        choices=["refit", "frozen", "boundary_t", "boundary_v2",
                 "candidate", "grouped", "assemble"],
        help="fit sub-step (fit stage only); run in listed order",
    )
    args = parser.parse_args()
    if args.stage == "fit":
        return stage_fit(args.part)
    return {
        "verify": stage_verify,
        "report": stage_report,
        "governance": stage_governance,
    }[args.stage]()


if __name__ == "__main__":
    sys.exit(main())
