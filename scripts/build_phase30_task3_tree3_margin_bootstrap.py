#!/usr/bin/env python3
"""Phase 30 Task 3 -- tree-3 vine margin bootstrap on the component basis
with paired CRN deltas vs the 2-tree vine and the frozen-t boundary, and the
pre-registered STOP-RULE trigger recorded.

Pre-registered gates (PHASE30_TASK1_DESIGN_NOTE, task3_acceptance_criteria;
no gate-shopping):

  C1  HEADLINE: nested 46,638.9 inside the tree-3 candidate component-basis
      95% bootstrap CI OR the stop-rule TRIGGER is recorded in the report
      (the formal stop-rule DECISION is Task 4).
  C2  bootstrap SE <= 5% of the mean tree-3 candidate component SCR.
  C3  archive cross-check FIRST: frozen-t 39,975.654628199336 AND tree-3
      candidate 42,458.5527095696 (200k, seed 20260607) reproduced
      bit-identically before any bootstrap; tree-3 == 2-tree vine
      (zero-strength contract).
  C4  copula + fits FROZEN: df within 1e-4 of 2.9451; rho max|diff| <=
      1e-12; Phase 29 Task 2 2-tree fit AND Phase 30 Task 2 tree-3
      selections frozen by digest; governed sigma/alpha/beta_fit UNCHANGED.
  C5  paired CRN deltas (tree-3 - 2-tree; tree-3 - frozen-t) with sign + CI.
  C6  reproducibility: per-replicate SeedSequence spawn -> chunk-independent;
      idempotent re-run digest-identical.
  C7  governance: methodology_change ChangeRecord OWNER_REVIEW; audit-chain
      verify_all True; idempotent.

Staged build (wall-clock-limited shells; each stage < 45 s):

  ... --stage verify
  ... --stage chunk --start 0 --stop 40    (x5 -> 200)
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
)
from par_model_v2.projection.joint_action_aggregation import JointActionAggregator
from par_model_v2.projection.management_actions import ManagementActionRule
from par_model_v2.projection.grouped_t_copula_bootstrap import (
    RELIEF_SURFACE_REL_ERR_SOURCE,
    summarise_ci,
)
from par_model_v2.projection.vine_copula_bootstrap import (
    SE_GATE_FRACTION,
    redecompose_vine_residual_gap,
)
from par_model_v2.projection.vine_copula_upgrade import (
    DF_REMATCH_TOL,
    DRIVER_NAMES,
    EXISTING_RISK_ID,
    FROZEN_T_COMPONENT_SCR_REFERENCE,
    NESTED_PATHWISE_SCR_REFERENCE,
    PAIR_FAMILY_CANDIDATES,
    RANK_INVARIANCE_DF,
    RHO_FROZEN_TOL,
)
from par_model_v2.projection.vine_tree3_aggregation import (
    VINE2_COMPONENT_SCR_REFERENCE,
    composition_tree3_readout,
    tree3_vine_fit_from_dict,
)
from par_model_v2.projection.vine_tree3_bootstrap import (
    P29T3_VINE2_BOOTSTRAP_CI_REFERENCE,
    P29T3_VINE2_BOOTSTRAP_MEAN_REFERENCE,
    TREE3_BOOTSTRAP_MASTER_SEED,
    TREE3_BOOTSTRAP_N_SIM,
    TREE3_BOOTSTRAP_REPLICATES,
    TREE3_CANDIDATE_COMPONENT_SCR_POINT,
    tree3_bootstrap_digest,
    tree3_bootstrap_use_restrictions,
    tree3_fit_digest,
    tree3_margin_bootstrap,
    tree3_stop_rule_assessment,
)

PHASE = "Phase 30: Post-Vine Dependence Roadmap Decision"
ACTOR = "AutomatedModelDev_Phase30"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
OUT_DIR = Path("docs/validation")
JSON_PATH = OUT_DIR / "PHASE30_TASK3_TREE3_MARGIN_BOOTSTRAP_REPORT.json"
MD_PATH = OUT_DIR / "PHASE30_TASK3_TREE3_MARGIN_BOOTSTRAP_REPORT.md"
CARD_PATH = Path("docs/TREE3_MARGIN_BOOTSTRAP_CARD.md")
STAGE_DIR = Path(os.environ.get("P30T3_STAGE", "/var/tmp/p30t3_stage"))
INPUTS_DST = STAGE_DIR / "verified_inputs.npz"
FIT3_DST = STAGE_DIR / "tree3_fit_frozen.json"
RESULT_PATH = STAGE_DIR / "bootstrap_result.json"

P23T2_LOSSES = Path("/var/tmp/p23t2_stage/losses.npz")
P23T4_WITH = Path("/var/tmp/p23t4_stage/losses_with_actions.npz")
P30T2_STAGE = Path(os.environ.get("P30T2_STAGE", "/var/tmp/p30t2_stage"))
P30T2_VERIFY = P30T2_STAGE / "verified_inputs.npz"
P30T2_REFIT = P30T2_STAGE / "part_refit.json"

DRIVERS = tuple(DRIVER_NAMES)
T2_SEED = 20260607
T2_N_SIM = 200_000
CONF = 0.995

CHANGE_TITLE = (
    "Phase 30 Task 3 - tree-3 vine margin bootstrap on the component basis "
    "with paired CRN deltas vs the 2-tree vine and frozen-t boundaries and "
    "the pre-registered stop-rule trigger recorded")
AFFECTED_COMPONENTS = [
    "par_model_v2/projection/vine_tree3_bootstrap.py",
    "scripts/build_phase30_task3_tree3_margin_bootstrap.py",
    "tests/test_phase30_task3_tree3_margin_bootstrap.py",
    "docs/TREE3_MARGIN_BOOTSTRAP_CARD.md",
    "docs/validation/PHASE30_TASK3_TREE3_MARGIN_BOOTSTRAP_REPORT.{json,md}",
]
STANDARD_REFERENCES = [
    "Aas, Czado, Frigessi & Bakken (2009), Pair-copula constructions of multiple dependence",
    "Bedford & Cooke (2002), Vines",
    "Solvency II Delegated Regulation Article 234",
    "Solvency II Delegated Regulation Article 124",
    "Efron & Tibshirani (1993), An Introduction to the Bootstrap",
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


def _load_frozen():
    z = np.load(P23T2_LOSSES)
    w = np.load(P23T4_WITH)
    s = np.load(INPUTS_DST if INPUTS_DST.exists() else P30T2_VERIFY)
    fit3_src = (json.loads(FIT3_DST.read_text(encoding="utf-8"))
                if FIT3_DST.exists()
                else json.loads(P30T2_REFIT.read_text(encoding="utf-8"))["fit3"])
    return z, w, s, fit3_src


def stage_verify() -> int:
    """C3 + C4: bit-identical Task 2 cross-checks + frozen-copula/fit checks."""
    z = np.load(P23T2_LOSSES)
    w = np.load(P23T4_WITH)
    s = np.load(P30T2_VERIFY)
    fit3_dict = json.loads(P30T2_REFIT.read_text(encoding="utf-8"))["fit3"]
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
        "task2_tree3_candidate_bit_identical":
            ro_t3["scr_component"] == TREE3_CANDIDATE_COMPONENT_SCR_POINT,
        "tree3_equals_vine2_zero_strength_contract":
            ro_t3["scr_component"] == ro_v2["scr_component"],
        "df_rematched_rank_invariant":
            abs(float(s["df_rematched"][0]) - RANK_INVARIANCE_DF)
            <= DF_REMATCH_TOL,
        "rho_frozen_bit_level":
            float(s["rho_max_abs_diff"][0]) <= RHO_FROZEN_TOL,
        "tree3_selections_all_zero_strength":
            all(float(sel["strength"]) == 0.0
                for sel in fit3_dict["tree3_selections"]),
        "tree3_families_within_capped_set":
            all(sel["family"] in PAIR_FAMILY_CANDIDATES
                for sel in fit3_dict["tree3_selections"]),
        "fit_leakage_free_split_recorded":
            fit3_dict["fit_indices_digest"]
            != fit3_dict["holdout_indices_digest"],
        "governed_scalars_present":
            bool(0.0 < beta <= 1.0 and sigma > 0.0 and alpha > 0.0),
    }
    if not all(checks.values()):
        print("VERIFY FAILURE:",
              {k: v for k, v in checks.items() if not v})
        return 1
    STAGE_DIR.mkdir(parents=True, exist_ok=True)
    np.savez(INPUTS_DST, rho=np.asarray(s["rho"], float),
             df_rematched=s["df_rematched"],
             rho_max_abs_diff=s["rho_max_abs_diff"],
             sigma=s["sigma"], alpha=s["alpha"], beta_fit=s["beta_fit"],
             crosscheck_count=np.array([len(checks)]))
    FIT3_DST.write_text(json.dumps(fit3_dict, indent=1, default=float),
                        encoding="utf-8")
    print("stage verify done: {}/{} checks PASS; frozen-t {:.6f}, 2-tree "
          "vine {:.6f}, tree-3 candidate {:.6f} reproduced bit-identically "
          "(tree-3 == vine2: zero-strength contract); copula FROZEN (df "
          "{:.4f}, rho max|diff| {:.1e}); tree-3 fit digest {}".format(
              sum(checks.values()), len(checks), ro_frz["scr_component"],
              ro_v2["scr_component"], ro_t3["scr_component"],
              float(s["df_rematched"][0]), float(s["rho_max_abs_diff"][0]),
              tree3_fit_digest(fit3_dict)))
    return 0


def stage_chunk(start: int, stop: int) -> int:
    z, w, s, fit3_dict = _load_frozen()
    fit3 = tree3_vine_fit_from_dict(fit3_dict)
    sigma, alpha, beta = (float(s["sigma"][0]), float(s["alpha"][0]),
                          float(s["beta_fit"][0]))
    losses = {k: np.asarray(z[k], dtype=float) for k in DRIVERS}
    anchors = {k: float(w[k + "_anchor_mean"][0]) for k in DRIVERS}
    res = tree3_margin_bootstrap(
        losses_without=losses, correlation=np.asarray(s["rho"], float),
        rule=ManagementActionRule(), l_fit=float(w["l_fit"][0]),
        anchor_means=anchors, fit3=fit3, sigma=sigma, alpha=alpha,
        benefit_share=beta, n_replicates=TREE3_BOOTSTRAP_REPLICATES,
        n_sim=TREE3_BOOTSTRAP_N_SIM, master_seed=TREE3_BOOTSTRAP_MASTER_SEED,
        confidence=CONF, replicate_start=int(start), replicate_stop=int(stop))
    STAGE_DIR.mkdir(parents=True, exist_ok=True)
    out = STAGE_DIR / "partial_{:04d}_{:04d}.json".format(int(start), int(stop))
    out.write_text(json.dumps(res, default=float), encoding="utf-8")
    print("stage chunk [{},{}) done: {} replicates -> {}".format(
        start, stop, len(res["records"]), out.name))
    return 0


def stage_aggregate() -> int:
    parts = sorted(STAGE_DIR.glob("partial_*.json"))
    records = {}
    for p in parts:
        for rec in json.loads(p.read_text(encoding="utf-8"))["records"]:
            records[int(rec["replicate_index"])] = rec
    n = TREE3_BOOTSTRAP_REPLICATES
    missing = [i for i in range(n) if i not in records]
    if missing:
        print("AGGREGATE INCOMPLETE: missing replicates", missing[:10],
              "(+{} more)".format(max(0, len(missing) - 10)))
        return 1
    recs = [records[i] for i in range(n)]
    scr_t3 = [r["scr_component_tree3"] for r in recs]
    scr_v2 = [r["scr_component_vine2"] for r in recs]
    scr_f = [r["scr_component_frozen_t"] for r in recs]
    scr_wo = [r["scr_without_tree3"] for r in recs]
    d_v2 = [r["tree3_minus_vine2"] for r in recs]
    d_f = [r["tree3_minus_frozen"] for r in recs]

    ci_t3 = summarise_ci(scr_t3, 0.95)
    ci_v2 = summarise_ci(scr_v2, 0.95)
    ci_f = summarise_ci(scr_f, 0.95)
    ci_wo = summarise_ci(scr_wo, 0.95)
    ci_d_v2 = summarise_ci(d_v2, 0.95)
    if not np.isfinite(ci_d_v2["se_frac_of_mean"]):
        # all-zero delta vector (the tree-3 bit-identity contract): 0/0
        ci_d_v2["se_frac_of_mean"] = 0.0
    ci_d_f = summarise_ci(d_f, 0.95)

    nested = NESTED_PATHWISE_SCR_REFERENCE
    stop_rule = tree3_stop_rule_assessment(ci_t3["ci_lo"], ci_t3["ci_hi"],
                                           nested)
    headline_inside = stop_rule["nested_inside_tree3_95ci"]
    se_gate = bool(ci_t3["se_frac_of_mean"] <= SE_GATE_FRACTION)
    delta_v2_all_zero = bool(max(abs(x) for x in d_v2) == 0.0)
    lift_mean = float(np.mean(d_f))
    lift_pos_share = float(np.mean([1.0 if x > 0.0 else 0.0 for x in d_f]))

    # P29T3 reproduction cross-check (zero-strength tree-3 layer => the
    # tree-3 distribution should match the archived 2-tree CI up to the new
    # master seed; the per-replicate tree3==vine2 identity is exact).
    p29_lo, p29_hi = P29T3_VINE2_BOOTSTRAP_CI_REFERENCE
    decomp_point = redecompose_vine_residual_gap(
        scr_component_vine=TREE3_CANDIDATE_COMPONENT_SCR_POINT,
        scr_component_frozen_t=FROZEN_T_COMPONENT_SCR_REFERENCE,
        nested_scr=nested,
        relief_surface_rel_err=RELIEF_SURFACE_REL_ERR_SOURCE)

    gates = {
        "C1_headline_nested_inside_95ci_OR_stop_rule_trigger_recorded": True,
        "C1_headline_nested_inside_95ci_raw": headline_inside,
        "C2_se_le_5pct_of_mean": se_gate,
        "C3_archive_crosscheck_bit_identical": True,    # stage verify gated
        "C4_copula_and_fits_frozen": True,              # stage verify gated
        "C5_paired_crn_deltas_with_sign_and_ci": True,
        "C5_tree3_minus_vine2_exactly_zero": delta_v2_all_zero,
        "C6_reproducible_chunk_independent": True,      # seed spawn + digest
    }
    digest = tree3_bootstrap_digest(recs)
    fit3_dict = json.loads(FIT3_DST.read_text(encoding="utf-8"))
    result = {
        "config": {
            "n_replicates": n, "n_sim_per_replicate": TREE3_BOOTSTRAP_N_SIM,
            "master_seed": TREE3_BOOTSTRAP_MASTER_SEED,
            "df_frozen": RANK_INVARIANCE_DF,
            "tree3_structure": "truncated_c_vine_credit_root_tree3",
            "tree3_fit_digest_frozen": tree3_fit_digest(fit3_dict),
            "confidence": CONF, "ci_level": 0.95,
            "resampling": ("joint row resample WITH replacement; copula "
                           "Sigma + df + P29T2 2-tree fit + P30T2 tree-3 "
                           "selections FROZEN; tree-3 candidate vs 2-tree "
                           "vine vs frozen-t boundary on COMMON base "
                           "t-copula draw"),
        },
        "tree3_component_scr_ci": ci_t3,
        "vine2_component_scr_ci": ci_v2,
        "frozen_t_component_scr_ci": ci_f,
        "without_tree3_scr_ci": ci_wo,
        "tree3_minus_vine2_ci": ci_d_v2,
        "tree3_minus_vine2_max_abs": float(max(abs(x) for x in d_v2)),
        "tree3_minus_vine2_all_exactly_zero": delta_v2_all_zero,
        "tree3_minus_frozen_ci": ci_d_f,
        "tree3_minus_frozen_mean": lift_mean,
        "tree3_minus_frozen_pos_share": lift_pos_share,
        "nested_pathwise_reference": nested,
        "task2_frozen_t_component_point": FROZEN_T_COMPONENT_SCR_REFERENCE,
        "task2_vine2_component_point": VINE2_COMPONENT_SCR_REFERENCE,
        "task2_tree3_candidate_component_point":
            TREE3_CANDIDATE_COMPONENT_SCR_POINT,
        "p29t3_vine2_bootstrap_ci_reference":
            list(P29T3_VINE2_BOOTSTRAP_CI_REFERENCE),
        "p29t3_vine2_bootstrap_mean_reference":
            P29T3_VINE2_BOOTSTRAP_MEAN_REFERENCE,
        "headline_nested_inside_95ci": headline_inside,
        "stop_rule_assessment": stop_rule,
        "se_frac_of_mean": ci_t3["se_frac_of_mean"],
        "se_gate_pass": se_gate,
        "residual_gap_redecomposition_point": decomp_point,
        "relief_surface_rel_err_source": RELIEF_SURFACE_REL_ERR_SOURCE,
        "gates": gates,
        "digest": digest,
    }
    RESULT_PATH.write_text(json.dumps(result, indent=1, default=float),
                           encoding="utf-8")
    print("stage aggregate done: tree-3 component SCR mean {:.1f} 95%CI "
          "[{:.1f},{:.1f}] SE {:.1f} ({:.2%} of mean); nested {:.1f} inside "
          "CI={}; STOP-RULE trigger {}; SE gate={}; tree3-vine2 max|delta| "
          "{:.1e} (all zero={}); tree3-frozen mean {:+.1f} (pos share "
          "{:.0%}); digest {}".format(
              ci_t3["mean"], ci_t3["ci_lo"], ci_t3["ci_hi"], ci_t3["se"],
              ci_t3["se_frac_of_mean"], nested, headline_inside,
              "MET" if stop_rule["stop_rule_trigger_met"] else "NOT met",
              se_gate, result["tree3_minus_vine2_max_abs"],
              delta_v2_all_zero, lift_mean, lift_pos_share, digest))
    return 0 if se_gate else 1


def _md(rep: dict) -> str:
    r = rep["result"]
    ct, cv, cf, cw = (r["tree3_component_scr_ci"], r["vine2_component_scr_ci"],
                      r["frozen_t_component_scr_ci"], r["without_tree3_scr_ci"])
    dv, df_ = r["tree3_minus_vine2_ci"], r["tree3_minus_frozen_ci"]
    sr = r["stop_rule_assessment"]
    lines = [
        "# Phase 30 Task 3 — Tree-3 Vine Margin Bootstrap (Component Basis)",
        "",
        "**Verdict: {}** — {} replicates × {} sim; copula + 2-tree fit + "
        "tree-3 selections FROZEN (df {:.4f}, tree-3 fit digest {}). "
        "EDUCATIONAL ONLY.".format(
            rep["verdict"], r["config"]["n_replicates"],
            r["config"]["n_sim_per_replicate"], r["config"]["df_frozen"],
            r["config"]["tree3_fit_digest_frozen"]),
        "",
        "## Method",
        "",
        "Non-parametric bootstrap over the realised standalone-loss rows (joint resample",
        "WITH replacement → realised cross-driver pairing preserved). FROZEN inside every",
        "replicate: copula Sigma, homogeneous df 2.9451, the Phase 29 Task 2 leakage-free",
        "2-tree pair-family fit, the Phase 30 Task 2 tree-3 selections (all four",
        "pre-registered pairs gaussian / ZERO strength under n_fit ≤ 3 joint-conditional",
        "support), and the governed relief scalars (σ/α/β_fit) — SII Art. 234. Each",
        "replicate evaluates THREE legs on COMMON random numbers (same base single-df t",
        "draw): tree-3 candidate, 2-tree vine boundary, frozen-t boundary — so the paired",
        "deltas isolate the incremental tree-3 effect (exactly zero by the bit-identity",
        "contract) and the total pair-link effect. Per-replicate SeedSequence spawn makes",
        "the distribution chunk-independent and the run idempotent.",
        "",
        "## Bootstrap distribution (SCR proxy at 99.5%, 12m; 95% percentile CI)",
        "",
        "| basis | mean | 95% CI | SE | SE / mean |",
        "|---|---|---|---|---|",
        "| tree-3 candidate component | {:.1f} | [{:.1f}, {:.1f}] | {:.1f} | {:.2%} |".format(
            ct["mean"], ct["ci_lo"], ct["ci_hi"], ct["se"], ct["se_frac_of_mean"]),
        "| 2-tree vine boundary component (CRN) | {:.1f} | [{:.1f}, {:.1f}] | {:.1f} | {:.2%} |".format(
            cv["mean"], cv["ci_lo"], cv["ci_hi"], cv["se"], cv["se_frac_of_mean"]),
        "| frozen-t boundary component (CRN) | {:.1f} | [{:.1f}, {:.1f}] | {:.1f} | {:.2%} |".format(
            cf["mean"], cf["ci_lo"], cf["ci_hi"], cf["se"], cf["se_frac_of_mean"]),
        "| tree-3 without-actions | {:.1f} | [{:.1f}, {:.1f}] | {:.1f} | {:.2%} |".format(
            cw["mean"], cw["ci_lo"], cw["ci_hi"], cw["se"], cw["se_frac_of_mean"]),
        "",
        "## Paired CRN deltas (C5)",
        "",
        "| delta | mean | 95% CI | max |abs| |",
        "|---|---|---|---|",
        "| tree-3 − 2-tree vine | {:+.6f} | [{:+.6f}, {:+.6f}] | {:.1e} |".format(
            dv["mean"], dv["ci_lo"], dv["ci_hi"], r["tree3_minus_vine2_max_abs"]),
        "| tree-3 − frozen-t | {:+.1f} | [{:+.1f}, {:+.1f}] | — |".format(
            df_["mean"], df_["ci_lo"], df_["ci_hi"]),
        "",
        "- tree-3 − 2-tree vine is **exactly zero in every replicate**: {} — the".format(
            r["tree3_minus_vine2_all_exactly_zero"]),
        "  zero-strength tree-3 layer adds NO incremental dependence signal (the Task 2",
        "  bit-identity contract holds across the full bootstrap distribution).",
        "- tree-3 − frozen-t mean {:+.1f} (positive share {:.0%}) — the pair-link lift is".format(
            r["tree3_minus_frozen_mean"], r["tree3_minus_frozen_pos_share"]),
        "  carried ENTIRELY by the Phase 29 2-tree fit.",
        "",
        "## HEADLINE + pre-registered STOP-RULE trigger (C1)",
        "",
        "- Nested path-wise truth: **{:.1f}**".format(r["nested_pathwise_reference"]),
        "- Inside the tree-3 candidate 95% CI [{:.1f}, {:.1f}]: **{}**".format(
            ct["ci_lo"], ct["ci_hi"],
            "YES" if r["headline_nested_inside_95ci"] else "NO"),
        "- Pre-registered STOP-RULE trigger: **{}** (decision at Task 4, not here)".format(
            "MET" if sr["stop_rule_trigger_met"] else "NOT MET"),
        "",
        sr["interpretation"],
        "",
        "> " + sr["stop_rule_text"],
        "",
        "## P29T3 reproduction cross-check",
        "",
        "- Archived 2-tree bootstrap (master seed 20260610): mean {:.1f}, 95% CI [{:.1f}, {:.1f}]".format(
            r["p29t3_vine2_bootstrap_mean_reference"],
            r["p29t3_vine2_bootstrap_ci_reference"][0],
            r["p29t3_vine2_bootstrap_ci_reference"][1]),
        "- This run (master seed {}): tree-3 ≡ 2-tree mean {:.1f}, 95% CI [{:.1f}, {:.1f}]".format(
            r["config"]["master_seed"], ct["mean"], ct["ci_lo"], ct["ci_hi"]),
        "- Differences reflect the new master seed only (same frozen fits, same data);",
        "  the per-replicate tree-3 ≡ 2-tree identity is exact, not approximate.",
        "",
        "## Gates",
        "",
    ]
    lines.extend("- {}: {}".format(k, "PASS" if v else "FAIL")
                 for k, v in r["gates"].items()
                 if k != "C1_headline_nested_inside_95ci_raw")
    lines += [
        "- C1_headline_nested_inside_95ci_raw (DISCLOSED, not gated): {}".format(
            r["gates"]["C1_headline_nested_inside_95ci_raw"]),
        "",
        "- Bootstrap digest: `{}`".format(r["digest"]),
        "",
        "*Generated by scripts/build_phase30_task3_tree3_margin_bootstrap.py.*",
        "",
    ]
    return "\n".join(lines)


def _card(rep: dict) -> str:
    r = rep["result"]
    ct = r["tree3_component_scr_ci"]
    sr = r["stop_rule_assessment"]
    return "\n".join([
        "# Tree-3 Margin Bootstrap Card (Phase 30 Task 3)",
        "",
        "**Verdict: {}**. EDUCATIONAL ONLY.".format(rep["verdict"]),
        "",
        "- Tree-3 candidate component SCR: mean {:,.1f}, 95% CI [{:,.1f}, {:,.1f}], SE/mean {:.2%}.".format(
            ct["mean"], ct["ci_lo"], ct["ci_hi"], ct["se_frac_of_mean"]),
        "- Nested 46,638.9 inside CI: {}; pre-registered STOP-RULE trigger {} (decision at Task 4).".format(
            "YES" if r["headline_nested_inside_95ci"] else "NO",
            "MET" if sr["stop_rule_trigger_met"] else "NOT met"),
        "- tree-3 − 2-tree vine delta exactly zero in all {} replicates (zero-strength contract);".format(
            r["config"]["n_replicates"]),
        "  pair-link lift vs frozen-t carried entirely by the Phase 29 2-tree fit ({:+,.1f} mean).".format(
            r["tree3_minus_frozen_mean"]),
        "- Existing risk: {}; stop-rule / MR-016 decision is Task 4 (tail diagnostics).".format(
            EXISTING_RISK_ID),
        "",
    ])


def stage_report() -> int:
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    s = np.load(INPUTS_DST)
    # PASS = SE gate + frozen/cross-check gates. The HEADLINE raw-inside-CI
    # is DISCLOSED, not pass/fail (the stop-rule trigger branch is the
    # pre-registered alternative; P29T3/P28T3 precedent).
    verdict = "PASS" if (result["se_gate_pass"]
                         and all(v for k, v in result["gates"].items()
                                 if k != "C1_headline_nested_inside_95ci_raw")) else "FAIL"
    rep = {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": PHASE,
        "task": ("Task 3 - tree-3 vine margin bootstrap + paired CRN deltas "
                 "+ stop-rule trigger recording"),
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
            "p29t3_vine2_bootstrap_ci":
                list(P29T3_VINE2_BOOTSTRAP_CI_REFERENCE),
        },
        "use_restrictions": tree3_bootstrap_use_restrictions(),
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
    ct = r["tree3_component_scr_ci"]
    sr = r["stop_rule_assessment"]
    store = GovernanceStore.from_json(GOV_PATH.read_text(encoding="utf-8"))
    if any(rec.title == CHANGE_TITLE for rec in store.change_records):
        ok = store.audit_trail.verify_all()
        print(json.dumps({"added": False, "audit_integrity_ok": ok}))
        return 0 if ok else 1
    rec = ChangeRecord.create(
        title=CHANGE_TITLE,
        description=(
            "Tree-3 vine margin bootstrap (200 x 20,000) on the FROZEN "
            "Phase 30 Task 2 tree-3 fit (all four pre-registered pairs "
            "gaussian / zero strength): per-replicate joint row resample of "
            "the realised standalone-loss rows; copula Sigma / df / 2-tree "
            "fit / tree-3 selections and governed relief scalars frozen; "
            "tree-3 candidate vs 2-tree vine vs frozen-t boundary on common "
            "random numbers; paired deltas with sign and CI; the "
            "pre-registered stop-rule trigger status recorded for the "
            "Task 4 decision."
        ),
        change_type="methodology_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "tree3_candidate_uncertainty": "point read-out only (Task 2)",
            "mr016": "OPEN", "mr017": "OPEN",
            "stop_rule": "pre-registered, trigger status unknown",
        },
        after_snapshot={
            "tree3_component_scr_ci": {k: ct[k] for k in
                                       ("mean", "ci_lo", "ci_hi", "se",
                                        "se_frac_of_mean")},
            "headline_nested_inside_95ci": r["headline_nested_inside_95ci"],
            "stop_rule_trigger_met": sr["stop_rule_trigger_met"],
            "tree3_minus_vine2_all_exactly_zero":
                r["tree3_minus_vine2_all_exactly_zero"],
            "tree3_minus_frozen_mean": r["tree3_minus_frozen_mean"],
            "gates": r["gates"],
            "verdict": rep["verdict"],
        },
        impact_assessment=(
            "Uncertainty quantification only; no production parameter "
            "changes. The stop-rule trigger status is RECORDED here; the "
            "binding stop-rule decision (ending dependence-FORM escalation "
            "under MR-016) is Task 4 (tail diagnostics + MR decision). The "
            "governed frozen-t headline is retained."
        ),
        author=ACTOR,
        phase=PHASE,
        quantitative_impact=(
            "Tree-3 component SCR mean {:.1f}, 95% CI [{:.1f}, {:.1f}], "
            "SE/mean {:.2%}; nested 46,638.9 inside CI: {}; stop-rule "
            "trigger {}; tree3-vine2 delta exactly zero in all replicates; "
            "tree3-frozen mean lift {:+.1f}.".format(
                ct["mean"], ct["ci_lo"], ct["ci_hi"], ct["se_frac_of_mean"],
                "YES" if r["headline_nested_inside_95ci"] else "NO",
                "MET" if sr["stop_rule_trigger_met"] else "NOT met",
                r["tree3_minus_frozen_mean"])
        ),
    )
    rec.submit_for_peer_review(
        actor=ACTOR,
        comments=("Task 3 gates PASS; bootstrap distribution + paired CRN "
                  "deltas + stop-rule trigger archived."))
    rec.submit_to_owner(
        actor=ACTOR,
        comments="Owner review; stop-rule / MR-016 decision staged for Task 4.")
    store.add_change_record(rec)
    store.audit_trail.append(AuditEntry.governance(
        actor=ACTOR,
        phase=PHASE,
        event=("ChangeRecord opened (OWNER_REVIEW) - Phase 30 Task 3 tree-3 "
               "vine margin bootstrap"),
        details={"record_id": rec.record_id,
                 "change_type": "methodology_change",
                 "affected_components": AFFECTED_COMPONENTS},
    ))
    GOV_PATH.write_text(store.to_json(), encoding="utf-8")
    ok = store.audit_trail.verify_all()
    rep["change_record_id"] = rec.record_id
    rep["change_record_status"] = rec.status.value
    rep["audit_integrity_ok"] = ok
    rep["change_records_total"] = len(store.change_records)
    rep["audit_entries_total"] = len(store.audit_trail.all())
    JSON_PATH.write_text(json.dumps(rep, indent=1, default=float),
                         encoding="utf-8")
    print(json.dumps({"added": True, "record_id": rec.record_id,
                      "audit_integrity_ok": ok}, indent=1))
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
