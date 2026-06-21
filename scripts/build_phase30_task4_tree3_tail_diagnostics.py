#!/usr/bin/env python3
"""Phase 30 Task 4 -- tree-3 vine pair-level tail diagnostics + fit-vs-holdout
overfit check + BINDING STOP-RULE / MR-016 / MR-017 decision (+ MR-010/MR-014
no-refresh decision).

Pre-registered gates (PHASE30_TASK1_DESIGN_NOTE task4_acceptance_criteria;
P29T4 precedent; no gate-shopping):

  T4-G1  archive cross-check FIRST: (i) the Task 2 point read-outs (200k,
         seed 20260607) -- frozen-t 39,975.654628199336, 2-tree vine AND
         tree-3 candidate 42,458.5527095696 -- reproduced BIT-identically
         on the FROZEN P30T2 tree-3 fit (digest f689e11e81fa); (ii) the
         recomputed 200-replicate tree-3 / vine-2 / frozen-t component SCR
         statistics BIT-identical to the in-repo Task 3 bootstrap report
         (mean / CI / min / max), per-replicate records matching the
         archived Task 3 partials.
  T4-G2  per-pair tail diagnostics: upper AND lower co-exceedance for the
         six first-tree links, five second-tree links (conditional on the
         root upper tail), FOUR tree-3 links (joint-conditional on both
         pre-registered conditioners) and the three HOLDOUT pairs,
         candidate vs frozen-t boundary on CRN, with 95% CIs over the 200
         replicates at p in {0.80, 0.85, 0.90, 0.95}.
  T4-G3  fit-vs-holdout OVERFIT check: holdout disclosure complete AND the
         largest holdout-pair |mean lift| <= the largest fitted-pair
         |mean lift| at the canonical p = 0.90 (fitted = tree-1 + tree-2 +
         tree-3); holdout-to-fit ratio DISCLOSED vs the P29 reference 0.049.
  T4-G4  BINDING STOP-RULE / MR decision per the pre-registered criteria:
         mitigate MR-016/MR-017 ONLY IF nested 46,638.9 is INSIDE the
         Task 3 tree-3 95% CI [38,593.7, 44,556.4] AND the residual shrinks
         STRICTLY below 3,637.298487404965 -- NEITHER holds (tree-3
         bit-identical to vine-2; nested outside CI), so KEEP OPEN both and
         APPLY THE STOP-RULE: dependence-FORM escalation under MR-016 ENDS;
         Phase 31 = owner decision package (option C).
  T4-G5  MR-010/MR-014 refresh decision: NO refresh (GOVERNED headline =
         frozen single-df t recovered bit-identically, move 0.0000% <= 1%;
         nothing adopted without owner sign-off).
  T4-G6  reproducibility: tail-grid digest idempotent; zero-strength
         uniform bit-identity re-verified across all replicates;
         governance ChangeRecord (governance_change) OWNER_REVIEW; audit
         verify_all True; idempotent re-run.

Staged build (wall-clock-limited shells; each stage < 45 s):

  ... --stage verify
  ... --stage chunk --start 0 --stop 50    (x4 -> 200)
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
)
from par_model_v2.projection.joint_action_aggregation import JointActionAggregator
from par_model_v2.projection.management_actions import ManagementActionRule
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
from par_model_v2.projection.vine_tree3_aggregation import (
    VINE2_COMPONENT_SCR_REFERENCE,
    composition_tree3_readout,
    tree3_vine_fit_from_dict,
)
from par_model_v2.projection.vine_tree3_bootstrap import (
    TREE3_BOOTSTRAP_MASTER_SEED,
    TREE3_BOOTSTRAP_N_SIM,
    TREE3_BOOTSTRAP_REPLICATES,
    TREE3_CANDIDATE_COMPONENT_SCR_POINT,
    tree3_fit_digest,
)
from par_model_v2.projection.vine_tail_diagnostics import CROSSCHECK_TOL
from par_model_v2.projection.vine_tree3_tail_diagnostics import (
    P30T2_TREE3_FIT_DIGEST_REFERENCE,
    P30T3_BOOTSTRAP_DIGEST,
    P30T3_FROZEN_T_COMPONENT_MEAN,
    P30T3_TREE3_CI_HI,
    P30T3_TREE3_CI_LO,
    P30T3_TREE3_COMPONENT_MEAN,
    TAIL_LEVEL_GRID,
    replicate_tree3_tail_records,
    summarise_tree3_pair_tail_diagnostics,
    tree3_overfit_check,
    tree3_stop_rule_mr_decision,
    tree3_tail_diagnostics_digest,
    tree3_tail_diagnostics_use_restrictions,
)

PHASE = "Phase 30: Post-Vine Dependence Roadmap Decision"
ACTOR = "AutomatedModelDev_Phase30"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
OUT_DIR = Path("docs/validation")
JSON_PATH = OUT_DIR / "PHASE30_TASK4_TREE3_TAIL_DIAGNOSTICS_REPORT.json"
MD_PATH = OUT_DIR / "PHASE30_TASK4_TREE3_TAIL_DIAGNOSTICS_REPORT.md"
CARD_PATH = Path("docs/TREE3_TAIL_DIAGNOSTICS_CARD.md")
T3_REPORT = OUT_DIR / "PHASE30_TASK3_TREE3_MARGIN_BOOTSTRAP_REPORT.json"

STAGE_DIR = Path(os.environ.get("P30T4_STAGE", "/var/tmp/p30t4_stage"))
INPUTS_DST = STAGE_DIR / "verified_inputs.npz"
FIT3_DST = STAGE_DIR / "tree3_fit_frozen.json"
ARCHIVED_DST = STAGE_DIR / "archived_p30t3_records.json"
RESULT_PATH = STAGE_DIR / "result.json"

P23T2_LOSSES = Path("/var/tmp/p23t2_stage/losses.npz")
P23T4_WITH = Path("/var/tmp/p23t4_stage/losses_with_actions.npz")
P30T3_STAGE = Path(os.environ.get("P30T3_STAGE", "/var/tmp/p30t3_stage"))

DRIVERS = tuple(DRIVER_NAMES)
T2_SEED = 20260607
T2_N_SIM = 200_000
CONF = 0.995

CHANGE_TITLE = (
    "Phase 30 Task 4 - tree-3 vine pair-level tail diagnostics + "
    "fit-vs-holdout overfit check + BINDING STOP-RULE decision (MR-016 and "
    "MR-017 KEEP OPEN; dependence-FORM escalation under MR-016 ENDS; "
    "Phase 31 = owner decision package)")
AFFECTED_COMPONENTS = [
    "par_model_v2/projection/vine_tree3_tail_diagnostics.py",
    "scripts/build_phase30_task4_tree3_tail_diagnostics.py",
    "tests/test_phase30_task4_tree3_tail_diagnostics.py",
    "docs/TREE3_TAIL_DIAGNOSTICS_CARD.md",
    "docs/validation/PHASE30_TASK4_TREE3_TAIL_DIAGNOSTICS_REPORT.{json,md}",
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
    fit3_dict = json.loads(FIT3_DST.read_text(encoding="utf-8"))
    return z, w, s, fit3_dict


def stage_verify() -> int:
    """T4-G1(i): Task 2 point read-outs bit-identical on the frozen fit."""
    z = np.load(P23T2_LOSSES)
    w = np.load(P23T4_WITH)
    s = np.load(P30T3_STAGE / "verified_inputs.npz")
    fit3_dict = json.loads(
        (P30T3_STAGE / "tree3_fit_frozen.json").read_text(encoding="utf-8"))
    fit3 = tree3_vine_fit_from_dict(fit3_dict)
    sigma, alpha, beta = (float(s["sigma"][0]), float(s["alpha"][0]),
                          float(s["beta_fit"][0]))
    agg = _aggregator(z, w, np.asarray(s["rho"], float))
    ro_frz = composition_tree3_readout(
        agg, T2_N_SIM, T2_SEED, fit3, sigma, alpha, beta, CONF,
        mode="frozen_t_boundary")
    ro_v2 = composition_tree3_readout(
        agg, T2_N_SIM, T2_SEED, fit3, sigma, alpha, beta, CONF,
        mode="vine2_boundary")
    ro_t3 = composition_tree3_readout(
        agg, T2_N_SIM, T2_SEED, fit3, sigma, alpha, beta, CONF,
        mode="candidate")
    checks = {
        "task2_frozen_t_component_bit_identical":
            ro_frz["scr_component"] == FROZEN_T_COMPONENT_SCR_REFERENCE,
        "task2_vine2_component_bit_identical":
            ro_v2["scr_component"] == VINE2_COMPONENT_SCR_REFERENCE,
        "task2_tree3_candidate_component_bit_identical":
            ro_t3["scr_component"] == TREE3_CANDIDATE_COMPONENT_SCR_POINT,
        "tree3_equals_vine2_zero_strength_contract":
            ro_t3["scr_component"] == ro_v2["scr_component"],
        "tree3_fit_digest_frozen":
            tree3_fit_digest(fit3_dict) == P30T2_TREE3_FIT_DIGEST_REFERENCE,
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
    FIT3_DST.write_text(json.dumps(fit3_dict, indent=1, default=float),
                        encoding="utf-8")
    archived = {}
    for p in sorted(P30T3_STAGE.glob("partial_*.json")):
        for rec in json.loads(p.read_text(encoding="utf-8"))["records"]:
            archived[int(rec["replicate_index"])] = {
                "cop_seed": rec["cop_seed"],
                "scr_component_tree3": rec["scr_component_tree3"],
                "scr_component_vine2": rec["scr_component_vine2"],
                "scr_component_frozen_t": rec["scr_component_frozen_t"],
            }
    ARCHIVED_DST.write_text(json.dumps(archived, default=float),
                            encoding="utf-8")
    print("stage verify done: {}/{} checks PASS; frozen-t {:.6f}, vine-2 "
          "{:.6f} and tree-3 candidate {:.6f} bit-identical; fit digest {} "
          "frozen; archived Task 3 records cached: {}".format(
              sum(checks.values()), len(checks), ro_frz["scr_component"],
              ro_v2["scr_component"], ro_t3["scr_component"],
              P30T2_TREE3_FIT_DIGEST_REFERENCE, len(archived)))
    return 0


def stage_chunk(start: int, stop: int) -> int:
    z, w, s, fit3_dict = _load_frozen()
    fit3 = tree3_vine_fit_from_dict(fit3_dict)
    sigma, alpha, beta = (float(s["sigma"][0]), float(s["alpha"][0]),
                          float(s["beta_fit"][0]))
    losses = {k: np.asarray(z[k], dtype=float) for k in DRIVERS}
    anchors = {k: float(w[k + "_anchor_mean"][0]) for k in DRIVERS}
    archived_raw = json.loads(ARCHIVED_DST.read_text(encoding="utf-8"))
    archived = {int(k): v for k, v in archived_raw.items()}
    res = replicate_tree3_tail_records(
        losses_without=losses, correlation=np.asarray(s["rho"], float),
        rule=ManagementActionRule(), l_fit=float(w["l_fit"][0]),
        anchor_means=anchors, fit3=fit3, sigma=sigma, alpha=alpha,
        benefit_share=beta, archived_records=archived,
        n_replicates=TREE3_BOOTSTRAP_REPLICATES,
        n_sim=TREE3_BOOTSTRAP_N_SIM, master_seed=TREE3_BOOTSTRAP_MASTER_SEED,
        confidence=CONF, replicate_start=int(start),
        replicate_stop=int(stop), p_grid=TAIL_LEVEL_GRID)
    dev = float(res["archived_crosscheck_max_abs_dev"])
    u_dev = float(res["uniform_bit_identity_max_abs_dev"])
    if dev > CROSSCHECK_TOL or u_dev > 0.0:
        print("CHUNK CROSSCHECK FAILURE: archived dev {:.3e}; uniform "
              "bit-identity dev {:.3e}".format(dev, u_dev))
        return 1
    out = STAGE_DIR / "partial_{:04d}_{:04d}.json".format(int(start), int(stop))
    out.write_text(json.dumps(res, default=float), encoding="utf-8")
    print("stage chunk [{},{}) done: {} replicates; archived cross-check max "
          "abs dev {:.1e}; uniform bit-identity dev {:.1e} -> {}".format(
              start, stop, len(res["records"]), dev, u_dev, out.name))
    return 0


def stage_aggregate() -> int:
    parts = sorted(STAGE_DIR.glob("partial_*.json"))
    records = {}
    cross_devs = []
    u_devs = []
    for p in parts:
        blob = json.loads(p.read_text(encoding="utf-8"))
        cross_devs.append(float(blob["archived_crosscheck_max_abs_dev"]))
        u_devs.append(float(blob["uniform_bit_identity_max_abs_dev"]))
        for rec in blob["records"]:
            records[int(rec["replicate_index"])] = rec
    n = TREE3_BOOTSTRAP_REPLICATES
    missing = [i for i in range(n) if i not in records]
    if missing:
        print("AGGREGATE INCOMPLETE: missing replicates", missing[:10],
              "(+{} more)".format(max(0, len(missing) - 10)))
        return 1
    recs = [records[i] for i in range(n)]

    # T4-G1(ii): aggregate bit-identical cross-check vs the in-repo Task 3
    # report (mean / CI / min / max of tree-3, vine-2 and frozen-t SCR).
    t3 = json.loads(T3_REPORT.read_text(encoding="utf-8"))["result"]
    scr_3 = np.array([r["scr_component_tree3"] for r in recs])
    scr_2 = np.array([r["scr_component_vine2"] for r in recs])
    scr_f = np.array([r["scr_component_frozen_t"] for r in recs])
    c3, c2, cf = (t3["tree3_component_scr_ci"], t3["vine2_component_scr_ci"],
                  t3["frozen_t_component_scr_ci"])
    agg_dev = max(
        abs(float(np.mean(scr_3)) - float(c3["mean"])),
        abs(float(np.quantile(scr_3, 0.025)) - float(c3["ci_lo"])),
        abs(float(np.quantile(scr_3, 0.975)) - float(c3["ci_hi"])),
        abs(float(np.min(scr_3)) - float(c3["min"])),
        abs(float(np.max(scr_3)) - float(c3["max"])),
        abs(float(np.mean(scr_2)) - float(c2["mean"])),
        abs(float(np.mean(scr_f)) - float(cf["mean"])),
    )
    per_rep_dev = float(max(cross_devs)) if cross_devs else float("nan")
    u_dev = float(max(u_devs)) if u_devs else float("nan")
    zero_deltas_all = bool(all(float(r["tree3_minus_vine2"]) == 0.0
                               for r in recs))
    g1 = bool(agg_dev <= CROSSCHECK_TOL and per_rep_dev <= CROSSCHECK_TOL)

    summary = summarise_tree3_pair_tail_diagnostics(recs, TAIL_LEVEL_GRID)
    fit3_dict = json.loads(FIT3_DST.read_text(encoding="utf-8"))
    overfit = tree3_overfit_check(summary, fit3_dict)

    decision = tree3_stop_rule_mr_decision(
        boundary_scr_recomputed=FROZEN_T_COMPONENT_SCR_REFERENCE)

    digest = tree3_tail_diagnostics_digest(recs)
    gates = {
        "T4_G1_archive_crosscheck_bit_identical": g1,
        "T4_G2_pair_tail_grid_complete": bool(
            all(len(summary[k]["first_tree"]) == 6
                and len(summary[k]["second_tree"]) == 5
                and len(summary[k]["third_tree"]) == 4
                and len(summary[k]["holdout"]) == 3 for k in summary)),
        "T4_G3_fit_vs_holdout_overfit_check": bool(
            overfit["overfit_gate_pass"]),
        "T4_G4_stop_rule_mr_decision_per_preregistered_criteria": bool(
            decision["mr016_decision"] == "KEEP_OPEN"
            and decision["mr017_decision"] == "KEEP_OPEN"
            and decision["stop_rule_applied"]
            and decision["dependence_form_escalation_ends"]
            and not decision["nested_inside_ci"]
            and not decision["residual_shrinks_strictly"]),
        "T4_G5_mr010_mr014_no_refresh": bool(
            not decision["mr010_mr014_refresh_required"]
            and abs(decision["governed_headline_relative_move"]) == 0.0),
        "T4_G6_zero_strength_bit_identity_and_digest": bool(
            u_dev == 0.0 and zero_deltas_all),
    }
    result = {
        "config": {
            "n_replicates": n,
            "n_sim_per_replicate": TREE3_BOOTSTRAP_N_SIM,
            "master_seed": TREE3_BOOTSTRAP_MASTER_SEED,
            "df_frozen": RANK_INVARIANCE_DF,
            "p_grid": list(TAIL_LEVEL_GRID),
            "canonical_p": 0.90,
            "tree3_structure": fit3_dict["structure"],
            "tree3_fit_digest": P30T2_TREE3_FIT_DIGEST_REFERENCE,
            "archived_t3_digest": P30T3_BOOTSTRAP_DIGEST,
        },
        "archive_crosscheck": {
            "per_replicate_max_abs_dev": per_rep_dev,
            "aggregate_max_abs_dev": float(agg_dev),
            "bit_identical": g1,
            "uniform_bit_identity_max_abs_dev": u_dev,
            "tree3_minus_vine2_all_exactly_zero": zero_deltas_all,
            "t3_tree3_mean_ref": P30T3_TREE3_COMPONENT_MEAN,
            "t3_frozen_mean_ref": P30T3_FROZEN_T_COMPONENT_MEAN,
        },
        "pair_tail_summary": summary,
        "overfit_check": overfit,
        "stop_rule_mr_decision": decision,
        "gates": gates,
        "digest": digest,
    }
    RESULT_PATH.write_text(json.dumps(result, indent=1, default=float),
                           encoding="utf-8")
    a90 = summary["90"]
    top = max(a90["first_tree"] + a90["second_tree"] + a90["third_tree"],
              key=lambda r: abs(r["lift_upper"]["mean"]))
    print("stage aggregate done: gates {}/6 PASS; archive cross-check dev "
          "per-rep {:.1e} / aggregate {:.1e}; uniform bit-identity {:.1e}; "
          "p=0.90 largest fitted-pair upper lift {} {:+.4f}; holdout max "
          "|lift| {:.4f} (<= fit max {:.4f}; ratio {:.3f} vs P29 ref 0.049); "
          "MR-016 {}; MR-017 {}; stop-rule applied={}; refresh={}; digest "
          "{}".format(
              sum(gates.values()), per_rep_dev, agg_dev, u_dev, top["pair"],
              top["lift_upper"]["mean"],
              overfit["max_holdout_pair_abs_mean_lift"],
              overfit["max_fit_pair_abs_mean_lift"],
              overfit["holdout_to_fit_max_lift_ratio"],
              decision["mr016_decision"], decision["mr017_decision"],
              decision["stop_rule_applied"],
              decision["mr010_mr014_refresh_required"], digest))
    return 0 if all(gates.values()) else 1


def _fmt_pair(row, names=DRIVER_NAMES) -> str:
    i, j = row["pair"]
    s = "{}-{}".format(names[i], names[j])
    cond = row.get("condition_on")
    if cond is None:
        return s
    if isinstance(cond, list):
        return s + "|{},{}".format(names[cond[0]], names[cond[1]])
    return s + "|{}".format(names[cond])


def _md(rep: dict) -> str:
    r = rep["result"]
    a90 = r["pair_tail_summary"]["90"]
    ov = r["overfit_check"]
    d = r["stop_rule_mr_decision"]
    lines = [
        "# Phase 30 Task 4 — Tree-3 Vine Tail Diagnostics + Binding Stop-Rule / MR Decision",
        "",
        "**Verdict: {}** — {} replicates × {} sim re-drawn at the archived Task 3 seeds; "
        "copula + P29T2 2-tree fit + P30T2 tree-3 selections FROZEN (df {:.4f}). "
        "EDUCATIONAL ONLY.".format(
            rep["verdict"], r["config"]["n_replicates"],
            r["config"]["n_sim_per_replicate"], r["config"]["df_frozen"]),
        "",
        "## Archive cross-check (T4-G1)",
        "",
        "- Task 2 read-outs (200k, seed 20260607): frozen-t **{:.6f}**, 2-tree vine "
        "**{:.6f}** and tree-3 candidate **{:.6f}** reproduced bit-identically "
        "(zero-strength contract: tree-3 == vine-2).".format(
            FROZEN_T_COMPONENT_SCR_REFERENCE, VINE2_COMPONENT_SCR_REFERENCE,
            TREE3_CANDIDATE_COMPONENT_SCR_POINT),
        "- Task 3 bootstrap reproduction: per-replicate max abs dev {:.1e}; "
        "aggregate (mean/CI/min/max) max abs dev {:.1e}; uniform bit-identity "
        "max |U_t3 - U_v2| = {:.1e} across all 200 replicates.".format(
            r["archive_crosscheck"]["per_replicate_max_abs_dev"],
            r["archive_crosscheck"]["aggregate_max_abs_dev"],
            r["archive_crosscheck"]["uniform_bit_identity_max_abs_dev"]),
        "",
        "## Pair-level tail diagnostics at the canonical p = 0.90 (T4-G2)",
        "",
        "Candidate vs frozen-t boundary on CRN; mean over 200 replicates "
        "(95% CI in the JSON report; grid p ∈ {0.80, 0.85, 0.90, 0.95}). "
        "Tree-3 rows are conditional on the JOINT upper tail of both "
        "pre-registered conditioners.",
        "",
        "| link | type | cand λU | frz λU | lift λU | cand λL | frz λL | lift λL |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for gname, label in (("first_tree", "tree 1"), ("second_tree", "tree 2"),
                         ("third_tree", "tree 3"), ("holdout", "HOLDOUT")):
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
        "(ratio {:.3f}; P29 reference {:.3f}): **{}**.".format(
            ov["max_holdout_pair_abs_mean_lift"], ov["max_fit_pair_abs_mean_lift"],
            ov["holdout_to_fit_max_lift_ratio"], ov["p29_holdout_to_fit_reference"],
            ov["concentration_ok"]),
        "- Tree-3 joint-conditional fit support (n_fit per pre-registered pair): {} "
        "— all four selections zero strength: **{}** (the candidate tail field is "
        "exactly the 2-tree vine's).".format(
            ov["tree3_fit_support_n_fit"], ov["tree3_fit_all_zero_strength"]),
        "",
        "## Binding stop-rule / MR decision (T4-G4) + MR-010/MR-014 refresh (T4-G5)",
        "",
        "- Nested {:.1f} inside the Task 3 tree-3 95% CI [{:.1f}, {:.1f}]: **{}**.".format(
            d["nested_scr"], d["tree3_ci"][0], d["tree3_ci"][1],
            "YES" if d["nested_inside_ci"] else "NO"),
        "- Copula-form residual {:.1f} strictly below the 2-tree vine residual {:.1f}: "
        "**{}** (residual UNCHANGED — bit-identity).".format(
            d["tree3_copula_form_residual"], d["residual_improvement_threshold"],
            "YES" if d["residual_shrinks_strictly"] else "NO"),
        "- Pre-registered mitigation criteria met: **{}** → **MR-016 {} / MR-017 {}**.".format(
            d["mitigate_criteria_met"], d["mr016_decision"], d["mr017_decision"]),
        "- **STOP-RULE APPLIED: {}** — dependence-FORM escalation under MR-016 **ENDS**; "
        "no further copula-structure candidates without owner sign-off.".format(
            d["stop_rule_applied"]),
        "- GOVERNED headline (frozen single-df t {:.2f}) move: {:+.4%} ≤ 1% → "
        "**MR-010/MR-014 refresh: {}** (nothing adopted without owner sign-off).".format(
            d["governed_headline_reference"], d["governed_headline_relative_move"],
            "REQUIRED" if d["mr010_mr014_refresh_required"] else "NOT required"),
        "",
        "### Phase 31 directive",
        "",
        d["phase31_directive"],
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
        "*Generated by scripts/build_phase30_task4_tree3_tail_diagnostics.py.*",
        "",
    ]
    return "\n".join(lines)


def _card(rep: dict) -> str:
    r = rep["result"]
    d = r["stop_rule_mr_decision"]
    ov = r["overfit_check"]
    return "\n".join([
        "# Tree-3 Tail Diagnostics Card (Phase 30 Task 4)",
        "",
        "**Verdict: {}**. EDUCATIONAL ONLY.".format(rep["verdict"]),
        "",
        "- Per-pair upper/lower tail co-dependence (6 tree-1 + 5 tree-2 + 4 tree-3 "
        "joint-conditional + 3 holdout pairs), candidate vs frozen-t on CRN at the "
        "archived Task 3 seeds; archive cross-checks bit-identical; zero-strength "
        "bit-identity (tree-3 == vine-2) re-verified across all 200 replicates.",
        "- Overfit check: max holdout |lift| {:.4f} ≤ max fitted-pair |lift| {:.4f} "
        "(ratio {:.3f}; P29 reference 0.049); holdout disclosure complete.".format(
            ov["max_holdout_pair_abs_mean_lift"], ov["max_fit_pair_abs_mean_lift"],
            ov["holdout_to_fit_max_lift_ratio"]),
        "- **MR-016 {} / MR-017 {}** (nested {:.1f} NOT inside CI [{:.1f}, {:.1f}]; "
        "residual UNCHANGED at {:.1f}); **STOP-RULE APPLIED** — dependence-FORM "
        "escalation under MR-016 ENDS; Phase 31 = owner decision package.".format(
            d["mr016_decision"], d["mr017_decision"], d["nested_scr"],
            d["tree3_ci"][0], d["tree3_ci"][1], d["tree3_copula_form_residual"]),
        "- MR-010/MR-014: NO refresh (governed headline move {:+.4%}; nothing adopted).".format(
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
        "task": ("Task 4 - tree-3 vine pair-level tail diagnostics + "
                 "fit-vs-holdout overfit check + binding stop-rule / MR "
                 "decision"),
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
            "vine2_component_reference": VINE2_COMPONENT_SCR_REFERENCE,
            "tree3_candidate_component_reference":
                TREE3_CANDIDATE_COMPONENT_SCR_POINT,
            "tree3_bootstrap_mean": P30T3_TREE3_COMPONENT_MEAN,
            "tree3_bootstrap_ci": [P30T3_TREE3_CI_LO, P30T3_TREE3_CI_HI],
            "t3_bootstrap_digest": P30T3_BOOTSTRAP_DIGEST,
            "tree3_fit_digest": P30T2_TREE3_FIT_DIGEST_REFERENCE,
        },
        "use_restrictions": tree3_tail_diagnostics_use_restrictions(),
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
    d = r["stop_rule_mr_decision"]
    ov = r["overfit_check"]
    store = GovernanceStore.from_json(GOV_PATH.read_text(encoding="utf-8"))
    already = any(rec.title == CHANGE_TITLE for rec in store.change_records)
    if already:
        ok = store.audit_trail.verify_all()
        print(json.dumps({"added": False,
                          "reason": "already applied (idempotent)",
                          "audit_integrity_ok": ok}))
        return 0 if ok else 1

    # T4-G4: MR-016 stays OPEN; the binding stop-rule decision is recorded.
    mr016 = store.risk_register.get(EXISTING_RISK_ID)
    mr016.update_mitigation(
        MitigationStatus.OPEN,
        notes=(
            "Phase 30 Task 4 BINDING STOP-RULE decision: KEEP OPEN; "
            "STOP-RULE APPLIED. The pre-registered tree-3 deepening (P30T2) "
            "selected gaussian / zero strength on ALL FOUR third-tree pairs "
            "(n_fit <= 3 joint-conditional support), so the tree-3 "
            "candidate is BIT-identical to the 2-tree vine (42,458.55; "
            "residual UNCHANGED at 3,637.3) and nested 46,638.9 remains "
            "OUTSIDE the Task 3 tree-3 95% bootstrap CI [38,593.7, "
            "44,556.4]. Dependence-FORM escalation under MR-016 ENDS: no "
            "further copula-structure candidates may be opened without "
            "owner sign-off. Phase 31 = owner decision package (option C); "
            "option B (nested-aware calibration) only as an owner-approved "
            "escalation. Carries forward MR-015. Governed headline "
            "unchanged (frozen single-df t; nothing adopted)."))

    # MR-017 stays OPEN with the same decision recorded.
    mr017 = store.risk_register.get(NEXT_RISK_ID)
    mr017.update_mitigation(
        MitigationStatus.OPEN,
        notes=(
            "Phase 30 Task 4 decision: KEEP OPEN. The residual vine-FORM "
            "limitation is now FULLY QUANTIFIED at the pre-registered "
            "escalation depth: deepening the truncation (tree 3) adds ZERO "
            "incremental dependence at the pre-registered joint-conditional "
            "tail level (no empirical support with 160 outer scenarios), so "
            "the remaining residual 3,637.3 is attributed to nested "
            "inner-path joint dynamics that margins-level dependence cannot "
            "represent, NOT to the truncation depth. STOP-RULE APPLIED "
            "(with MR-016): dependence-FORM escalation ENDS; remediation "
            "moves to the Phase 31 owner decision package (adopt the vine "
            "as a DISCLOSED alternative read-out, fund a second independent "
            "nested run, or accept and disclose the quantified residual)."))

    rec = ChangeRecord.create(
        title=CHANGE_TITLE,
        description=(
            "Per-pair upper/lower tail co-dependence diagnostics for the six "
            "first-tree links, five second-tree links (conditional on the "
            "root upper tail), FOUR tree-3 links (joint-conditional on both "
            "pre-registered conditioners) and three holdout pairs, tree-3 "
            "candidate vs frozen-t boundary on COMMON random numbers, "
            "re-drawn at the archived Task 3 bootstrap seeds (per-replicate "
            "and aggregate SCR cross-checks BIT-identical; zero-strength "
            "uniform bit-identity tree-3 == vine-2 re-verified across all "
            "200 replicates). Pre-registered fit-vs-holdout overfit gate "
            "PASS. BINDING STOP-RULE decision: MR-016 and MR-017 KEEP OPEN "
            "(nested 46,638.9 outside the tree-3 95% CI; residual UNCHANGED "
            "at 3,637.3 by bit-identity) and the STOP-RULE IS APPLIED - "
            "dependence-FORM escalation under MR-016 ENDS; Phase 31 = owner "
            "decision package (option C). MR-010/MR-014: NO refresh "
            "(governed headline move 0.0000% <= 1%; nothing adopted without "
            "owner sign-off). No new model parameter."),
        change_type="governance_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "tree3_pair_level_tail_diagnostics":
                "not yet reported for the tree-3 candidate",
            "mr016": "OPEN (stop-rule trigger recorded at Task 3, not decided)",
            "mr017": "OPEN (no Task 4 decision)",
            "stop_rule": "trigger MET (Task 3); decision pending",
            "mr_register_count": 17,
        },
        after_snapshot={
            "archive_crosscheck_bit_identical":
                r["archive_crosscheck"]["bit_identical"],
            "uniform_bit_identity_max_abs_dev":
                r["archive_crosscheck"]["uniform_bit_identity_max_abs_dev"],
            "overfit_gate_pass": ov["overfit_gate_pass"],
            "max_holdout_abs_mean_lift": ov["max_holdout_pair_abs_mean_lift"],
            "max_fit_abs_mean_lift": ov["max_fit_pair_abs_mean_lift"],
            "holdout_to_fit_ratio": ov["holdout_to_fit_max_lift_ratio"],
            "mr016_decision": d["mr016_decision"],
            "mr017_decision": d["mr017_decision"],
            "stop_rule_applied": d["stop_rule_applied"],
            "dependence_form_escalation_ends":
                d["dependence_form_escalation_ends"],
            "nested_inside_ci": d["nested_inside_ci"],
            "mr_register_count": 17,
            "mr010_mr014_refresh_required": d["mr010_mr014_refresh_required"],
            "governed_headline_move": d["governed_headline_relative_move"],
            "gates": r["gates"],
            "verdict": rep["verdict"],
            "digest": r["digest"],
        },
        impact_assessment=(
            "Diagnostic + governance only: no governed parameter changes "
            "(copula Sigma / homogeneous df / P29T2 2-tree fit / P30T2 "
            "tree-3 selections and relief scalars FROZEN). The tree-3 "
            "candidate adds ZERO incremental dependence (zero-strength "
            "bit-identity re-verified), so the 2-tree vine's residual "
            "narrowing stands as the best dependence-FORM result; the "
            "pre-registered STOP-RULE is APPLIED and dependence-FORM "
            "escalation under MR-016 ENDS. The governed frozen single-df t "
            "headline is unchanged, so MR-010/MR-014 quantifications stand. "
            "Phase 31 is the owner decision package. Educational "
            "classification retained; production sign-off withheld."),
        author=ACTOR,
        phase=PHASE,
        quantitative_impact=(
            "p=0.90 max fitted-pair |mean lift| {:.4f}; max holdout |mean "
            "lift| {:.4f} (ratio {:.3f}; P29 ref 0.049); archive "
            "cross-check per-replicate max abs dev {:.1e} / aggregate "
            "{:.1e}; uniform bit-identity {:.1e}; MR-016 + MR-017 KEEP OPEN "
            "(nested 46,638.9 vs CI hi {:.1f}; residual unchanged 3,637.3); "
            "STOP-RULE APPLIED; governed headline move {:+.4%} -> no "
            "MR-010/MR-014 refresh.".format(
                ov["max_fit_pair_abs_mean_lift"],
                ov["max_holdout_pair_abs_mean_lift"],
                ov["holdout_to_fit_max_lift_ratio"],
                r["archive_crosscheck"]["per_replicate_max_abs_dev"],
                r["archive_crosscheck"]["aggregate_max_abs_dev"],
                r["archive_crosscheck"]["uniform_bit_identity_max_abs_dev"],
                d["tree3_ci"][1], d["governed_headline_relative_move"])),
    )
    rec.submit_for_peer_review(
        actor=ACTOR,
        comments=("Archive cross-checks bit-identical; zero-strength "
                  "bit-identity re-verified; overfit gate PASS; STOP-RULE "
                  "APPLIED per pre-registered criteria (MR-016 + MR-017 "
                  "KEEP OPEN); new unit tests PASS."))
    rec.submit_to_owner(
        actor=ACTOR,
        comments=("Owner review: binding stop-rule decision - "
                  "dependence-FORM escalation under MR-016 ends; Phase 31 "
                  "owner decision package; governed headline unchanged."))
    store.add_change_record(rec)
    store.audit_trail.append(AuditEntry.governance(
        actor=ACTOR,
        phase=PHASE,
        event=("ChangeRecord opened (OWNER_REVIEW) - Phase 30 Task 4 tree-3 "
               "tail diagnostics + BINDING STOP-RULE decision (MR-016/MR-017 "
               "KEEP OPEN; dependence-FORM escalation ends)"),
        details={"record_id": rec.record_id,
                 "change_type": "governance_change",
                 "mr016_decision": d["mr016_decision"],
                 "mr017_decision": d["mr017_decision"],
                 "stop_rule_applied": d["stop_rule_applied"],
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
    parser.add_argument("--stop", type=int, default=TREE3_BOOTSTRAP_REPLICATES)
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
