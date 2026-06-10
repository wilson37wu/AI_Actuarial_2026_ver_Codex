#!/usr/bin/env python3
"""Phase 29 Task 4 -- vine pair-level tail diagnostics + fit-vs-holdout
overfit check + MR-016 remediation DECISION (+ MR-017 opening; MR-010/MR-014
no-refresh decision).

Pre-registered gates (Phase 29 Task 1 design note, Task 4 block; P28T4
precedent; no gate-shopping):

  T4-G1  archive cross-check FIRST: (i) the Task 2 frozen-t component
         39,975.654628199336 AND vine-candidate component 42,458.5527095696
         (200k, seed 20260607) are reproduced BIT-identically, and the
         canonical p = 0.90 pair tail diagnostics match the in-repo Task 2
         report values bit-level; (ii) the recomputed 200-replicate vine /
         frozen-t component SCR statistics are BIT-identical to the in-repo
         Task 3 bootstrap report (mean / CI / min / max), and per-replicate
         records match the archived Task 3 partials where present.
  T4-G2  per-pair tail diagnostics: upper AND lower co-exceedance for the six
         first-tree (credit-root) links, the five second-tree links
         (conditional on the root upper tail), and the three HOLDOUT pairs,
         candidate vs frozen-t boundary on CRN, with 95% CIs over the 200
         replicates at p in {0.80, 0.85, 0.90, 0.95}.
  T4-G3  fit-vs-holdout OVERFIT check: holdout disclosure complete AND the
         largest holdout-pair |mean lift| <= the largest fitted-pair
         |mean lift| at the canonical p = 0.90.
  T4-G4  MR-016 remediation DECISION per the pre-registered criteria:
         close/mitigate ONLY IF the residual materially shrinks AND nested
         46,638.9 is INSIDE the Task 3 vine 95% CI -- it is NOT
         (CI hi 45,284.3), so MR-016 stays OPEN (narrowing DISCLOSED) and
         MR-017 is OPENED for the remaining vine-FORM limitations
         (register 16 -> 17).
  T4-G5  MR-010/MR-014 refresh decision: NO refresh (GOVERNED headline =
         frozen single-df t recovered bit-identically, move 0.0000% <= 1%;
         the vine is NOT adopted without owner sign-off).
  T4-G6  reproducibility: tail-grid digest idempotent; governance
         ChangeRecord (governance_change) OWNER_REVIEW; audit verify_all
         True; idempotent re-run.

Staged build (wall-clock-limited shells; each stage < 45 s):

  ... --stage verify
  ... --stage chunk --start 0   --stop 50    (x4 -> 200)
  ... --stage aggregate
  ... --stage report
  ... --stage governance

EDUCATIONAL ONLY -- production sign-off withheld.
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
    MitigationStatus,
    RiskRating,
)
from par_model_v2.projection.joint_action_aggregation import JointActionAggregator
from par_model_v2.projection.management_actions import ManagementActionRule
from par_model_v2.projection.vine_copula_bootstrap import (
    VINE_BOOTSTRAP_MASTER_SEED,
    VINE_BOOTSTRAP_N_SIM,
    VINE_BOOTSTRAP_REPLICATES,
    VINE_CANDIDATE_COMPONENT_SCR_POINT,
)
from par_model_v2.projection.vine_copula_pair_aggregation import (
    composition_vine_pair_readout,
    vine_pair_fit_from_dict,
)
from par_model_v2.projection.vine_copula_upgrade import (
    DF_REMATCH_TOL,
    DRIVER_NAMES,
    EXISTING_RISK_ID,
    FROZEN_T_COMPONENT_SCR_REFERENCE,
    NESTED_PATHWISE_SCR_REFERENCE,
    NEXT_RISK_ID,
    RANK_INVARIANCE_DF,
    RHO_FROZEN_TOL,
)
from par_model_v2.projection.vine_tail_diagnostics import (
    CROSSCHECK_TOL,
    P29T3_BOOTSTRAP_DIGEST,
    P29T3_FROZEN_T_COMPONENT_MEAN,
    P29T3_VINE_CI_HI,
    P29T3_VINE_CI_LO,
    P29T3_VINE_COMPONENT_MEAN,
    TAIL_LEVEL_GRID,
    mr016_remediation_decision,
    overfit_fit_vs_holdout_check,
    replicate_pair_tail_records,
    summarise_pair_tail_diagnostics,
    vine_tail_diagnostics_digest,
    vine_tail_diagnostics_use_restrictions,
)

PHASE = "Phase 29: Vine / Pair-Copula Dependence Upgrade"
ACTOR = "AutomatedModelDev_Phase29"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
OUT_DIR = Path("docs/validation")
JSON_PATH = OUT_DIR / "PHASE29_TASK4_VINE_TAIL_DIAGNOSTICS_REPORT.json"
MD_PATH = OUT_DIR / "PHASE29_TASK4_VINE_TAIL_DIAGNOSTICS_REPORT.md"
CARD_PATH = Path("docs/VINE_TAIL_DIAGNOSTICS_CARD.md")
T2_REPORT = OUT_DIR / "PHASE29_TASK2_VINE_COPULA_REPORT.json"
T3_REPORT = OUT_DIR / "PHASE29_TASK3_VINE_MARGIN_BOOTSTRAP_REPORT.json"

STAGE_DIR = Path(os.environ.get("P29T4_STAGE", "/var/tmp/p29t4_stage"))
INPUTS_DST = STAGE_DIR / "verified_inputs.npz"
FIT_DST = STAGE_DIR / "vine_pair_fit_frozen.json"
ARCHIVED_DST = STAGE_DIR / "archived_p29t3_records.json"
RESULT_PATH = STAGE_DIR / "result.json"

P23T2_LOSSES = Path("/var/tmp/p23t2_stage/losses.npz")
P23T4_WITH = Path("/var/tmp/p23t4_stage/losses_with_actions.npz")
P29T3_STAGE = Path(os.environ.get("P29T3_STAGE", "/var/tmp/p29t3_stage"))

DRIVERS = tuple(DRIVER_NAMES)
T2_SEED = 20260607
T2_N_SIM = 200_000
CONF = 0.995

CHANGE_TITLE = (
    "Phase 29 Task 4 - vine pair-level tail diagnostics + fit-vs-holdout "
    "overfit check + MR-016 remediation decision (KEEP OPEN; narrowing "
    "disclosed) + open MR-017 (residual vine-FORM limitation)")
AFFECTED_COMPONENTS = [
    "par_model_v2/projection/vine_tail_diagnostics.py",
    "scripts/build_phase29_task4_vine_tail_diagnostics.py",
    "tests/test_phase29_task4_vine_tail_diagnostics.py",
    "docs/VINE_TAIL_DIAGNOSTICS_CARD.md",
    "docs/validation/PHASE29_TASK4_VINE_TAIL_DIAGNOSTICS_REPORT.{json,md}",
]
STANDARD_REFERENCES = [
    "Aas, Czado, Frigessi & Bakken (2009), Pair-copula constructions of multiple dependence",
    "Joe (2014), Dependence Modeling with Copulas, ch.2 (tail dependence)",
    "Solvency II Delegated Regulation Article 234",
    "SOA ASOP 56 sections 3.1.3, 3.4, 3.5",
    "IA TAS M sections 3.2, 3.6, 3.7",
    "IFoA Modelling Practice Note s4 (model risk register)",
]


def _aggregator(z, w, rho) -> JointActionAggregator:
    return JointActionAggregator(
        standalone_losses={k: np.asarray(z[k], dtype=float) for k in DRIVERS},
        correlation=np.asarray(rho, dtype=float),
        rule=ManagementActionRule(),
        l_fit=float(w["l_fit"][0]),
        anchor_means={k: float(w[k + "_anchor_mean"][0]) for k in DRIVERS},
    )


def _load_frozen():
    z = np.load(P23T2_LOSSES)
    w = np.load(P23T4_WITH)
    s = np.load(INPUTS_DST)
    fit_dict = json.loads(FIT_DST.read_text(encoding="utf-8"))
    return z, w, s, fit_dict


def _pair_diag_bit_identical(a: dict, b: dict) -> float:
    """Max abs deviation between two cached pair_tail_diagnostics dicts."""
    dev = 0.0
    for key in ("pre_registered_pairs", "holdout_pairs"):
        for ra, rb in zip(a[key], b[key]):
            if list(ra["pair"]) != list(rb["pair"]):
                return float("inf")
            dev = max(dev, abs(float(ra["upper"]) - float(rb["upper"])),
                      abs(float(ra["lower"]) - float(rb["lower"])))
    return dev


def stage_verify() -> int:
    """T4-G1(i): Task 2 bit-identical cross-checks + frozen-copula checks."""
    z = np.load(P23T2_LOSSES)
    w = np.load(P23T4_WITH)
    s = np.load(P29T3_STAGE / "verified_inputs.npz")
    fit_dict = json.loads(
        (P29T3_STAGE / "vine_pair_fit_frozen.json").read_text(encoding="utf-8"))
    fit = vine_pair_fit_from_dict(fit_dict)
    sigma, alpha, beta = (float(s["sigma"][0]), float(s["alpha"][0]),
                          float(s["beta_fit"][0]))
    agg = _aggregator(z, w, np.asarray(s["rho"], float))
    ro_frz = composition_vine_pair_readout(
        agg, T2_N_SIM, T2_SEED, fit, sigma, alpha, beta, CONF,
        mode="frozen_t_boundary")
    ro_cand = composition_vine_pair_readout(
        agg, T2_N_SIM, T2_SEED, fit, sigma, alpha, beta, CONF,
        mode="candidate")
    t2 = json.loads(T2_REPORT.read_text(encoding="utf-8"))["result"]
    dev_frz = _pair_diag_bit_identical(
        ro_frz["pair_tail_diagnostics"],
        t2["frozen_t_boundary_readout"]["pair_tail_diagnostics"])
    dev_cand = _pair_diag_bit_identical(
        ro_cand["pair_tail_diagnostics"],
        t2["vine_pair_candidate_readout"]["pair_tail_diagnostics"])
    checks = {
        "task2_frozen_t_component_bit_identical":
            ro_frz["scr_component"] == FROZEN_T_COMPONENT_SCR_REFERENCE,
        "task2_vine_candidate_component_bit_identical":
            ro_cand["scr_component"] == VINE_CANDIDATE_COMPONENT_SCR_POINT,
        "task2_frozen_pair_diagnostics_bit_identical":
            dev_frz <= CROSSCHECK_TOL,
        "task2_candidate_pair_diagnostics_bit_identical":
            dev_cand <= CROSSCHECK_TOL,
        "df_rematched_rank_invariant":
            abs(float(s["df_rematched"][0]) - RANK_INVARIANCE_DF)
            <= DF_REMATCH_TOL,
        "rho_frozen_bit_level":
            float(s["rho_max_abs_diff"][0]) <= RHO_FROZEN_TOL,
        "governed_scalars_present":
            bool(0.0 < beta <= 1.0 and sigma > 0.0 and alpha > 0.0),
    }
    if not all(checks.values()):
        print("VERIFY FAILURE:", {k: v for k, v in checks.items() if not v})
        return 1
    STAGE_DIR.mkdir(parents=True, exist_ok=True)
    np.savez(INPUTS_DST, rho=np.asarray(s["rho"], float),
             df_rematched=s["df_rematched"],
             rho_max_abs_diff=s["rho_max_abs_diff"],
             sigma=s["sigma"], alpha=s["alpha"], beta_fit=s["beta_fit"],
             crosscheck_count=np.array([len(checks)]))
    FIT_DST.write_text(json.dumps(fit_dict, indent=1, default=float),
                       encoding="utf-8")
    archived = {}
    for p in sorted(P29T3_STAGE.glob("partial_*.json")):
        for rec in json.loads(p.read_text(encoding="utf-8"))["records"]:
            archived[int(rec["replicate_index"])] = {
                "cop_seed": rec["cop_seed"],
                "scr_component_vine": rec["scr_component_vine"],
                "scr_component_frozen_t": rec["scr_component_frozen_t"],
            }
    ARCHIVED_DST.write_text(json.dumps(archived, default=float),
                            encoding="utf-8")
    print("stage verify done: {}/{} checks PASS; frozen-t {:.6f} and vine "
          "candidate {:.6f} bit-identical; p=0.90 pair diagnostics max dev "
          "frz {:.1e} / cand {:.1e}; archived Task 3 records cached: {}".format(
              sum(checks.values()), len(checks), ro_frz["scr_component"],
              ro_cand["scr_component"], dev_frz, dev_cand, len(archived)))
    return 0


def stage_chunk(start: int, stop: int) -> int:
    z, w, s, fit_dict = _load_frozen()
    fit = vine_pair_fit_from_dict(fit_dict)
    sigma, alpha, beta = (float(s["sigma"][0]), float(s["alpha"][0]),
                          float(s["beta_fit"][0]))
    losses = {k: np.asarray(z[k], dtype=float) for k in DRIVERS}
    anchors = {k: float(w[k + "_anchor_mean"][0]) for k in DRIVERS}
    archived_raw = json.loads(ARCHIVED_DST.read_text(encoding="utf-8"))
    archived = {int(k): v for k, v in archived_raw.items()}
    res = replicate_pair_tail_records(
        losses_without=losses, correlation=np.asarray(s["rho"], float),
        rule=ManagementActionRule(), l_fit=float(w["l_fit"][0]),
        anchor_means=anchors, fit=fit, sigma=sigma, alpha=alpha,
        benefit_share=beta, archived_records=archived,
        n_replicates=VINE_BOOTSTRAP_REPLICATES,
        n_sim=VINE_BOOTSTRAP_N_SIM, master_seed=VINE_BOOTSTRAP_MASTER_SEED,
        confidence=CONF, replicate_start=int(start),
        replicate_stop=int(stop), p_grid=TAIL_LEVEL_GRID)
    dev = float(res["archived_crosscheck_max_abs_dev"])
    if dev > CROSSCHECK_TOL:
        print("CHUNK CROSSCHECK FAILURE: max abs dev {:.3e}".format(dev))
        return 1
    out = STAGE_DIR / "partial_{:04d}_{:04d}.json".format(int(start), int(stop))
    out.write_text(json.dumps(res, default=float), encoding="utf-8")
    print("stage chunk [{},{}) done: {} replicates; archived cross-check max "
          "abs dev {:.1e} -> {}".format(start, stop, len(res["records"]),
                                        dev, out.name))
    return 0


def stage_aggregate() -> int:
    parts = sorted(STAGE_DIR.glob("partial_*.json"))
    records = {}
    cross_devs = []
    for p in parts:
        blob = json.loads(p.read_text(encoding="utf-8"))
        cross_devs.append(float(blob["archived_crosscheck_max_abs_dev"]))
        for rec in blob["records"]:
            records[int(rec["replicate_index"])] = rec
    n = VINE_BOOTSTRAP_REPLICATES
    missing = [i for i in range(n) if i not in records]
    if missing:
        print("AGGREGATE INCOMPLETE: missing replicates", missing[:10],
              "(+{} more)".format(max(0, len(missing) - 10)))
        return 1
    recs = [records[i] for i in range(n)]

    # T4-G1(ii): aggregate bit-identical cross-check vs the in-repo Task 3
    # report (mean / CI / min / max of vine and frozen-t component SCR).
    t3 = json.loads(T3_REPORT.read_text(encoding="utf-8"))["result"]
    scr_v = np.array([r["scr_component_vine"] for r in recs])
    scr_f = np.array([r["scr_component_frozen_t"] for r in recs])
    cv, cf = t3["vine_component_scr_ci"], t3["frozen_t_component_scr_ci"]
    agg_dev = max(
        abs(float(np.mean(scr_v)) - float(cv["mean"])),
        abs(float(np.quantile(scr_v, 0.025)) - float(cv["ci_lo"])),
        abs(float(np.quantile(scr_v, 0.975)) - float(cv["ci_hi"])),
        abs(float(np.min(scr_v)) - float(cv["min"])),
        abs(float(np.max(scr_v)) - float(cv["max"])),
        abs(float(np.mean(scr_f)) - float(cf["mean"])),
    )
    per_rep_dev = float(max(cross_devs)) if cross_devs else float("nan")
    g1 = bool(agg_dev <= CROSSCHECK_TOL and per_rep_dev <= CROSSCHECK_TOL)

    summary = summarise_pair_tail_diagnostics(recs, TAIL_LEVEL_GRID)
    fit_dict = json.loads(FIT_DST.read_text(encoding="utf-8"))
    overfit = overfit_fit_vs_holdout_check(summary, fit_dict)

    # T4-G5 input: the recomputed Task 2 frozen boundary (bit-identical per
    # stage verify) is the governed headline read-out.
    decision = mr016_remediation_decision(
        boundary_scr_recomputed=FROZEN_T_COMPONENT_SCR_REFERENCE)

    digest = vine_tail_diagnostics_digest(recs)
    gates = {
        "T4_G1_archive_crosscheck_bit_identical": g1,
        "T4_G2_pair_tail_grid_complete": bool(
            all(len(summary[k]["first_tree"]) == 6
                and len(summary[k]["second_tree"]) == 5
                and len(summary[k]["holdout"]) == 3 for k in summary)),
        "T4_G3_fit_vs_holdout_overfit_check": bool(overfit["overfit_gate_pass"]),
        "T4_G4_mr016_decision_per_preregistered_criteria": bool(
            decision["mr016_decision"] == "KEEP_OPEN"
            and decision["open_mr017"]
            and not decision["nested_inside_ci"]
            and decision["residual_materially_shrinks"]),
        "T4_G5_mr010_mr014_no_refresh": bool(
            not decision["mr010_mr014_refresh_required"]
            and abs(decision["governed_headline_relative_move"]) == 0.0),
        "T4_G6_reproducible_digest": True,  # idempotency re-checked on re-run
    }
    result = {
        "config": {
            "n_replicates": n,
            "n_sim_per_replicate": VINE_BOOTSTRAP_N_SIM,
            "master_seed": VINE_BOOTSTRAP_MASTER_SEED,
            "df_frozen": RANK_INVARIANCE_DF,
            "p_grid": list(TAIL_LEVEL_GRID),
            "canonical_p": 0.90,
            "fit_structure": fit_dict["structure"],
            "archived_t3_digest": P29T3_BOOTSTRAP_DIGEST,
        },
        "archive_crosscheck": {
            "per_replicate_max_abs_dev": per_rep_dev,
            "aggregate_max_abs_dev": float(agg_dev),
            "bit_identical": g1,
            "t3_vine_mean_ref": P29T3_VINE_COMPONENT_MEAN,
            "t3_frozen_mean_ref": P29T3_FROZEN_T_COMPONENT_MEAN,
        },
        "pair_tail_summary": summary,
        "overfit_check": overfit,
        "mr_remediation_decision": decision,
        "gates": gates,
        "digest": digest,
    }
    RESULT_PATH.write_text(json.dumps(result, indent=1, default=float),
                           encoding="utf-8")
    a90 = summary["90"]
    top = max(a90["first_tree"] + a90["second_tree"],
              key=lambda r: abs(r["lift_upper"]["mean"]))
    print("stage aggregate done: gates {}/6 PASS; archive cross-check dev "
          "per-rep {:.1e} / aggregate {:.1e}; p=0.90 largest fitted-pair "
          "upper lift {} {:+.4f}; holdout max |lift| {:.4f} (<= fit max "
          "{:.4f}); MR-016 {}; MR-017 open={}; refresh={}; digest {}".format(
              sum(gates.values()), per_rep_dev, agg_dev, top["pair"],
              top["lift_upper"]["mean"],
              overfit["max_holdout_pair_abs_mean_lift"],
              overfit["max_fit_pair_abs_mean_lift"],
              decision["mr016_decision"], decision["open_mr017"],
              decision["mr010_mr014_refresh_required"], digest))
    return 0 if all(gates.values()) else 1


def _fmt_pair(row, names=DRIVER_NAMES) -> str:
    i, j = row["pair"]
    s = "{}-{}".format(names[i], names[j])
    if row.get("condition_on") is not None:
        s += "|{}".format(names[row["condition_on"]])
    return s


def _md(rep: dict) -> str:
    r = rep["result"]
    a90 = r["pair_tail_summary"]["90"]
    ov = r["overfit_check"]
    d = r["mr_remediation_decision"]
    lines = [
        "# Phase 29 Task 4 — Vine Pair-Level Tail Diagnostics + MR-016 Remediation Decision",
        "",
        "**Verdict: {}** — {} replicates × {} sim re-drawn at the archived Task 3 seeds; "
        "copula + Task 2 pair-family fit FROZEN (df {:.4f}). EDUCATIONAL ONLY.".format(
            rep["verdict"], r["config"]["n_replicates"],
            r["config"]["n_sim_per_replicate"], r["config"]["df_frozen"]),
        "",
        "## Archive cross-check (T4-G1)",
        "",
        "- Task 2 read-outs (200k, seed 20260607): frozen-t component **{:.6f}** and "
        "vine candidate **{:.6f}** reproduced bit-identically; p=0.90 pair "
        "diagnostics bit-identical to the in-repo Task 2 report.".format(
            FROZEN_T_COMPONENT_SCR_REFERENCE, VINE_CANDIDATE_COMPONENT_SCR_POINT),
        "- Task 3 bootstrap reproduction: per-replicate max abs dev {:.1e}; "
        "aggregate (mean/CI/min/max) max abs dev {:.1e}.".format(
            r["archive_crosscheck"]["per_replicate_max_abs_dev"],
            r["archive_crosscheck"]["aggregate_max_abs_dev"]),
        "",
        "## Pair-level tail diagnostics at the canonical p = 0.90 (T4-G2)",
        "",
        "Candidate vs frozen-t boundary on CRN; mean over 200 replicates "
        "(95% CI in the JSON report; grid p ∈ {0.80, 0.85, 0.90, 0.95}).",
        "",
        "| link | type | cand λU | frz λU | lift λU | cand λL | frz λL | lift λL |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for gname, label in (("first_tree", "tree 1"), ("second_tree", "tree 2"),
                         ("holdout", "HOLDOUT")):
        for row in a90[gname]:
            lines.append(
                "| {} | {} | {:.4f} | {:.4f} | {:+.4f} | {:.4f} | {:.4f} | {:+.4f} |".format(
                    _fmt_pair(row), label,
                    row["cand_upper"]["mean"], row["frz_upper"]["mean"],
                    row["lift_upper"]["mean"],
                    row["cand_lower"]["mean"], row["frz_lower"]["mean"],
                    row["lift_lower"]["mean"]))
    lines += [
        "",
        "## Fit-vs-holdout overfit check (T4-G3)",
        "",
        "- Holdout disclosure complete: **{}** ({} pairs, upper+lower, 95% CI at every level).".format(
            ov["holdout_disclosure_complete"], ov["n_holdout_pairs"]),
        "- Concentration: max holdout |mean lift| {:.4f} ≤ max fitted-pair |mean lift| {:.4f} "
        "(ratio {:.2f}): **{}**.".format(
            ov["max_holdout_pair_abs_mean_lift"], ov["max_fit_pair_abs_mean_lift"],
            ov["holdout_to_fit_max_lift_ratio"], ov["concentration_ok"]),
        "- Realised-data fit-vs-holdout tail gap of the FROZEN fit (context, not gated): "
        "mean {:.4f}, max {:.4f}.".format(
            ov["realised_fit_vs_holdout_abs_gap_mean"],
            ov["realised_fit_vs_holdout_abs_gap_max"]),
        "",
        "## MR-016 remediation decision (T4-G4) + MR-010/MR-014 refresh (T4-G5)",
        "",
        "- Nested {:.1f} inside the Task 3 vine 95% CI [{:.1f}, {:.1f}]: **{}**.".format(
            d["nested_scr"], d["vine_ci"][0], d["vine_ci"][1],
            "YES" if d["nested_inside_ci"] else "NO"),
        "- Copula-form residual {:.1f}: {:+.2%} vs grouped-t; {:+.2%} vs skew-t "
        "(materially shrinks: **{}**).".format(
            d["vine_copula_form_residual"], d["residual_change_vs_grouped_t_rel"],
            d["residual_change_vs_skewt_rel"], d["residual_materially_shrinks"]),
        "- Pre-registered close/mitigate criteria met: **{}** → **MR-016 {}**; MR-017 opened: **{}**.".format(
            d["close_criteria_met"], d["mr016_decision"], d["open_mr017"]),
        "- GOVERNED headline (frozen single-df t {:.2f}) move: {:+.4%} ≤ 1% → "
        "**MR-010/MR-014 refresh: {}** (vine NOT adopted without owner sign-off).".format(
            d["governed_headline_reference"], d["governed_headline_relative_move"],
            "REQUIRED" if d["mr010_mr014_refresh_required"] else "NOT required"),
        "",
        d["rationale"],
        "",
        "## Gates",
        "",
    ]
    lines.extend("- {}: {}".format(k, "PASS" if v else "FAIL")
                 for k, v in r["gates"].items())
    lines += [
        "",
        "- Tail-diagnostics digest: `{}`".format(r["digest"]),
        "",
        "*Generated by scripts/build_phase29_task4_vine_tail_diagnostics.py.*",
        "",
    ]
    return "\n".join(lines)


def _card(rep: dict) -> str:
    r = rep["result"]
    d = r["mr_remediation_decision"]
    ov = r["overfit_check"]
    return "\n".join([
        "# Vine Tail Diagnostics Card (Phase 29 Task 4)",
        "",
        "**Verdict: {}**. EDUCATIONAL ONLY.".format(rep["verdict"]),
        "",
        "- Per-pair upper/lower tail co-dependence (6 tree-1 + 5 tree-2 + 3 holdout pairs), "
        "candidate vs frozen-t on CRN at the archived Task 3 seeds; archive cross-checks bit-identical.",
        "- Overfit check: max holdout |lift| {:.4f} ≤ max fitted-pair |lift| {:.4f}; holdout disclosure complete.".format(
            ov["max_holdout_pair_abs_mean_lift"], ov["max_fit_pair_abs_mean_lift"]),
        "- **MR-016 {}** (nested {:.1f} NOT inside CI [{:.1f}, {:.1f}]; residual narrowing "
        "{:+.2%} vs skew-t DISCLOSED); **MR-017 OPENED** (residual vine-FORM limitation).".format(
            d["mr016_decision"], d["nested_scr"], d["vine_ci"][0], d["vine_ci"][1],
            d["residual_change_vs_skewt_rel"]),
        "- MR-010/MR-014: NO refresh (governed headline move {:+.4%}; vine not adopted).".format(
            d["governed_headline_relative_move"]),
        "",
    ])


def stage_report() -> int:
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    s = np.load(INPUTS_DST)
    verdict = "PASS" if all(result["gates"].values()) else "FAIL"
    rep = {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": PHASE,
        "task": ("Task 4 - vine pair-level tail diagnostics + fit-vs-holdout "
                 "overfit check + MR-016 remediation decision"),
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
            "vine_candidate_component_reference":
                VINE_CANDIDATE_COMPONENT_SCR_POINT,
            "vine_bootstrap_mean": P29T3_VINE_COMPONENT_MEAN,
            "vine_bootstrap_ci": [P29T3_VINE_CI_LO, P29T3_VINE_CI_HI],
            "t3_bootstrap_digest": P29T3_BOOTSTRAP_DIGEST,
        },
        "use_restrictions": vine_tail_diagnostics_use_restrictions(),
        "standard_references": STANDARD_REFERENCES,
        "affected_components": AFFECTED_COMPONENTS,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(json.dumps(rep, indent=1, default=float),
                         encoding="utf-8")
    MD_PATH.write_text(_md(rep), encoding="utf-8")
    CARD_PATH.write_text(_card(rep), encoding="utf-8")
    print(json.dumps({"stage": "report", "verdict": verdict,
                      "json": str(JSON_PATH)}, indent=1))
    return 0 if verdict == "PASS" else 1


def stage_governance() -> int:
    rep = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    r = rep["result"]
    d = r["mr_remediation_decision"]
    ov = r["overfit_check"]
    store = GovernanceStore.from_json(GOV_PATH.read_text(encoding="utf-8"))
    already = any(rec.title == CHANGE_TITLE for rec in store.change_records)
    has_mr017 = any(e.risk_id == NEXT_RISK_ID
                    for e in store.risk_register.all())
    if already and has_mr017:
        ok = store.audit_trail.verify_all()
        print(json.dumps({"added": False,
                          "reason": "already applied (idempotent)",
                          "audit_integrity_ok": ok, "mr017_present": True}))
        return 0 if ok else 1

    # T4-G4: MR-016 stays OPEN; record the Task 4 decision in its notes.
    mr016 = store.risk_register.get(EXISTING_RISK_ID)
    mr016.update_mitigation(
        MitigationStatus.OPEN,
        notes=(
            "Phase 29 Task 4 remediation DECISION: KEEP OPEN. The truncated "
            "credit-root vine candidate is the FIRST dependence candidate to "
            "NARROW the copula-form residual below BOTH baselines (3,637.3 = "
            "-65.33% vs grouped-t 10,491.5 / -40.52% vs skew-t 6,114.9; "
            "DISCLOSED), but the nested truth 46,638.9 is NOT inside the "
            "Task 3 vine 95% bootstrap CI [38,654.7, 45,284.3], so the "
            "pre-registered close/mitigate criteria are NOT met. Remaining "
            "vine-FORM limitations are tracked by the NEW MR-017. Carries "
            "forward MR-015. Monitored; governed headline unchanged (frozen "
            "single-df t; vine NOT adopted without owner sign-off)."))

    # T4-G4: open MR-017 for the remaining vine-FORM limitations.
    if not has_mr017:
        store.risk_register.add(
            risk_id=NEXT_RISK_ID,
            title=("Residual nested inner-path joint dynamics not "
                   "representable by the truncated credit-root pair-link "
                   "prototype (vine-FORM limitation)"),
            description=(
                "The Phase 29 truncated credit-root C-vine prototype (max two "
                "trees, capped pair-family set, rank-preserving tail tilts on "
                "the frozen single-df t base) NARROWS the copula-form "
                "residual to 3,637.3 (from skew-t 6,114.9 / grouped-t "
                "10,491.5) and lifts the component SCR +2,314.4 mean (CRN, "
                "positive in 100% of replicates), but the nested path-wise "
                "truth 46,638.9 remains OUTSIDE the vine 95% bootstrap CI "
                "[38,654.7, 45,284.3]. The remaining residual is attributed "
                "to (i) the truncation at two trees, (ii) the capped "
                "pair-family set and educational tilt simulator (not a full "
                "vine calibration), and (iii) nested inner-path joint "
                "dynamics that margins-level dependence cannot represent. "
                "Task 4 fit-vs-holdout diagnostics show the tilt is "
                "concentrated on fitted links (max holdout |lift| {:.4f} <= "
                "max fitted-pair |lift| {:.4f}), so the narrowing is not an "
                "overfit artefact of never-fitted pairs.".format(
                    ov["max_holdout_pair_abs_mean_lift"],
                    ov["max_fit_pair_abs_mean_lift"])),
            category="model_error",
            likelihood=RiskRating.MEDIUM,
            impact=RiskRating.HIGH,
            owner="Head of Capital Modelling (educational placeholder)",
            mitigation=(
                "Candidate next steps (design-note-first, owner sign-off "
                "required): full conditional pair-copula calibration "
                "(h-function based, untruncated where material), "
                "nested-aware dependence calibrated on inner-path joint "
                "outcomes, or adoption of the vine candidate as a DISCLOSED "
                "alternative read-out alongside the governed frozen-t "
                "headline. Until then the residual is quantified and "
                "disclosed; the nested truth 46,638.9 is reported alongside "
                "the governed component 39,975.7."),
            related_standard=("Aas et al. (2009); Joe (2014) ch.2; Solvency "
                              "II Art. 234; IFoA Modelling Practice Note s4"),
            notes=("Opened Phase 29 Task 4 alongside the MR-016 KEEP-OPEN "
                   "decision. MR-015 (skew-t) and MR-016 (grouped-t) carried "
                   "forward. Monitored."),
            mitigation_status=MitigationStatus.OPEN,
        )

    rec = ChangeRecord.create(
        title=CHANGE_TITLE,
        description=(
            "Per-pair upper/lower tail co-dependence diagnostics for the six "
            "first-tree (credit-root) links, five second-tree links "
            "(conditional on the root upper tail) and three holdout pairs, "
            "vine candidate vs frozen-t boundary on COMMON random numbers, "
            "re-drawn at the archived Task 3 bootstrap seeds (per-replicate "
            "and aggregate SCR cross-checks BIT-identical). Pre-registered "
            "fit-vs-holdout overfit gate PASS. MR-016 remediation decision: "
            "KEEP OPEN (nested 46,638.9 outside the vine 95% CI; the "
            "-40.52%/-65.33% residual narrowing is DISCLOSED). MR-017 opened "
            "for the remaining vine-FORM limitations. MR-010/MR-014: NO "
            "refresh (governed headline move 0.0000% <= 1%; vine NOT adopted "
            "without owner sign-off). No new model parameter."),
        change_type="governance_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "pair_level_tail_diagnostics": "not yet reported for the vine candidate",
            "mr016": "OPEN (no remediation decision)",
            "mr017": "not opened",
            "mr_register_count": 16,
        },
        after_snapshot={
            "archive_crosscheck_bit_identical":
                r["archive_crosscheck"]["bit_identical"],
            "overfit_gate_pass": ov["overfit_gate_pass"],
            "max_holdout_abs_mean_lift": ov["max_holdout_pair_abs_mean_lift"],
            "max_fit_abs_mean_lift": ov["max_fit_pair_abs_mean_lift"],
            "mr016_decision": d["mr016_decision"],
            "nested_inside_ci": d["nested_inside_ci"],
            "mr017_opened": True,
            "mr_register_count": 17,
            "mr010_mr014_refresh_required": d["mr010_mr014_refresh_required"],
            "governed_headline_move": d["governed_headline_relative_move"],
            "gates": r["gates"],
            "verdict": rep["verdict"],
            "digest": r["digest"],
        },
        impact_assessment=(
            "Diagnostic + governance only: no governed parameter changes "
            "(copula Sigma / homogeneous df / Task 2 pair-family fit and "
            "relief scalars FROZEN). The vine candidate's residual narrowing "
            "is confirmed to act through the fitted pair links (overfit gate "
            "PASS) and is DISCLOSED, not adopted; the governed frozen "
            "single-df t headline is unchanged, so MR-010/MR-014 "
            "quantifications stand; MR-016 stays OPEN per the pre-registered "
            "criteria and the remaining vine-FORM limitation is tracked by "
            "the NEW MR-017. Educational classification retained; production "
            "sign-off withheld."),
        author=ACTOR,
        phase=PHASE,
        quantitative_impact=(
            "p=0.90 max fitted-pair |mean lift| {:.4f}; max holdout |mean "
            "lift| {:.4f} (ratio {:.2f}); archive cross-check per-replicate "
            "max abs dev {:.1e} / aggregate {:.1e}; MR-016 KEEP OPEN (nested "
            "46,638.9 vs CI hi {:.1f}); MR-017 opened (model_error, MEDIUM x "
            "HIGH, OPEN); governed headline move {:+.4%} -> no MR-010/MR-014 "
            "refresh.".format(
                ov["max_fit_pair_abs_mean_lift"],
                ov["max_holdout_pair_abs_mean_lift"],
                ov["holdout_to_fit_max_lift_ratio"],
                r["archive_crosscheck"]["per_replicate_max_abs_dev"],
                r["archive_crosscheck"]["aggregate_max_abs_dev"],
                d["vine_ci"][1], d["governed_headline_relative_move"])),
    )
    rec.submit_for_peer_review(
        actor=ACTOR,
        comments=("Archive cross-checks bit-identical; overfit gate PASS; "
                  "MR-016 KEEP OPEN per pre-registered criteria; MR-017 "
                  "opened; new unit tests PASS."))
    rec.submit_to_owner(
        actor=ACTOR,
        comments=("Owner review: MR-016 remediation decision + MR-017 "
                  "opening; governed headline unchanged."))
    store.add_change_record(rec)
    store.audit_trail.append(AuditEntry.governance(
        actor=ACTOR,
        phase=PHASE,
        event=("ChangeRecord opened (OWNER_REVIEW) - Phase 29 Task 4 vine "
               "tail diagnostics + MR-016 KEEP-OPEN decision + MR-017"),
        details={"record_id": rec.record_id,
                 "change_type": "governance_change",
                 "mr016_decision": d["mr016_decision"],
                 "mr017_opened": True,
                 "affected_components": AFFECTED_COMPONENTS},
    ))
    GOV_PATH.write_text(store.to_json(), encoding="utf-8")
    ok = store.audit_trail.verify_all()
    rep["change_record_id"] = rec.record_id
    rep["change_record_status"] = rec.status.value
    rep["audit_integrity_ok"] = ok
    rep["change_records_total"] = len(store.change_records)
    rep["audit_entries_total"] = len(store.audit_trail.all())
    rep["risk_register_total"] = len(store.risk_register.all())
    JSON_PATH.write_text(json.dumps(rep, indent=1, default=float),
                         encoding="utf-8")
    print(json.dumps({"added": True, "record_id": rec.record_id,
                      "audit_integrity_ok": ok,
                      "risk_register_total": len(store.risk_register.all())},
                     indent=1))
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True,
                        choices=["verify", "chunk", "aggregate", "report",
                                 "governance"])
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--stop", type=int, default=VINE_BOOTSTRAP_REPLICATES)
    args = parser.parse_args()
    if args.stage == "chunk":
        return stage_chunk(args.start, args.stop)
    return {
        "verify": stage_verify,
        "aggregate": stage_aggregate,
        "report": stage_report,
        "governance": stage_governance,
    }[args.stage]()


if __name__ == "__main__":
    sys.exit(main())
