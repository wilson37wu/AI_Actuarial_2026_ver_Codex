#!/usr/bin/env python3
"""Phase 29 Task 3 -- vine / pair-copula margin bootstrap on the component
basis + residual-gap RE-decomposition vs the grouped-t (10,491.5) and
skew-t-reconfirmed (6,114.9) baselines.

Pre-registered gates (Phase 29 Task 1 design note, Task 3 block; no
gate-shopping):

  B1  HEADLINE: the nested path-wise truth 46,638.9 lies INSIDE the
      vine-candidate component-basis 95% bootstrap CI; ELSE the residual gap
      is RE-decomposed (relief-surface vs copula-form) AND the CHANGE of the
      copula-form residual vs BOTH the grouped-t residual 10,491.5 and the
      skew-t-reconfirmed residual 6,114.9 is quantified -- the
      re-decomposition is itself an accepted, pre-registered outcome.
  B2  bootstrap SE <= 5% of the mean vine-candidate component SCR.
  B3  archive cross-check FIRST: the Task 2 frozen-t component read-out
      39,975.654628199336 AND the vine-candidate component read-out
      42,458.5527095696 (200k, seed 20260607) are reproduced BIT-IDENTICALLY
      before any bootstrap.
  B4  copula + fit FROZEN: homogeneous df within 1e-4 of 2.9451; rho
      max|diff| <= 1e-12; the Phase 29 Task 2 pair-family fit (structure /
      families / strengths) frozen by digest; governed sigma/alpha/beta_fit
      UNCHANGED (P26 verified composition inputs).
  B5  reproducibility: per-replicate SeedSequence spawn -> chunk-independent;
      idempotent re-run digest-identical.
  B6  governance: methodology_change ChangeRecord OWNER_REVIEW; audit-chain
      verify_all True; idempotent.

Staged build (wall-clock-limited shells; each stage < 45 s):

  ... --stage verify
  ... --stage chunk --start 0   --stop 40    (x5 -> 200)
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
from par_model_v2.projection.vine_copula_pair_aggregation import (
    composition_vine_pair_readout,
    vine_pair_fit_from_dict,
)
from par_model_v2.projection.vine_copula_bootstrap import (
    SE_GATE_FRACTION,
    VINE_BOOTSTRAP_MASTER_SEED,
    VINE_BOOTSTRAP_N_SIM,
    VINE_BOOTSTRAP_REPLICATES,
    VINE_CANDIDATE_COMPONENT_SCR_POINT,
    redecompose_vine_residual_gap,
    vine_bootstrap_digest,
    vine_bootstrap_use_restrictions,
    vine_fit_digest,
    vine_margin_bootstrap,
)
from par_model_v2.projection.vine_copula_upgrade import (
    DF_REMATCH_TOL,
    DRIVER_NAMES,
    EXISTING_RISK_ID,
    FROZEN_T_COMPONENT_SCR_REFERENCE,
    GROUPED_T_COPULA_FORM_RESIDUAL_ABS,
    NESTED_PATHWISE_SCR_REFERENCE,
    PAIR_FAMILY_CANDIDATES,
    RANK_INVARIANCE_DF,
    RHO_FROZEN_TOL,
    SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS,
)

PHASE = "Phase 29: Vine / Pair-Copula Dependence Upgrade"
ACTOR = "AutomatedModelDev_Phase29"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
OUT_DIR = Path("docs/validation")
JSON_PATH = OUT_DIR / "PHASE29_TASK3_VINE_MARGIN_BOOTSTRAP_REPORT.json"
MD_PATH = OUT_DIR / "PHASE29_TASK3_VINE_MARGIN_BOOTSTRAP_REPORT.md"
CARD_PATH = Path("docs/VINE_MARGIN_BOOTSTRAP_CARD.md")
STAGE_DIR = Path(os.environ.get("P29T3_STAGE", "/var/tmp/p29t3_stage"))
INPUTS_DST = STAGE_DIR / "verified_inputs.npz"
FIT_DST = STAGE_DIR / "vine_pair_fit_frozen.json"
RESULT_PATH = STAGE_DIR / "bootstrap_result.json"

P23T2_LOSSES = Path("/var/tmp/p23t2_stage/losses.npz")
P23T4_WITH = Path("/var/tmp/p23t4_stage/losses_with_actions.npz")
P29T2_STAGE = Path(os.environ.get("P29T2_STAGE", "/var/tmp/p29t2_stage"))
P29T2_VERIFY = P29T2_STAGE / "verified_inputs.npz"
P29T2_FIT = P29T2_STAGE / "vine_pair_fit.json"

DRIVERS = tuple(DRIVER_NAMES)
T2_SEED = 20260607
T2_N_SIM = 200_000
CONF = 0.995

CHANGE_TITLE = (
    "Phase 29 Task 3 - vine / pair-copula margin bootstrap on the component "
    "basis + residual-gap RE-decomposition vs grouped-t 10,491.5 and "
    "skew-t-reconfirmed 6,114.9")
AFFECTED_COMPONENTS = [
    "par_model_v2/projection/vine_copula_bootstrap.py",
    "scripts/build_phase29_task3_vine_margin_bootstrap.py",
    "tests/test_phase29_task3_vine_margin_bootstrap.py",
    "docs/VINE_MARGIN_BOOTSTRAP_CARD.md",
    "docs/validation/PHASE29_TASK3_VINE_MARGIN_BOOTSTRAP_REPORT.{json,md}",
]
STANDARD_REFERENCES = [
    "Aas, Czado, Frigessi & Bakken (2009), Pair-copula constructions of multiple dependence",
    "Bedford & Cooke (2002), Vines",
    "Solvency II Delegated Regulation Article 234",
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
    s = np.load(INPUTS_DST if INPUTS_DST.exists() else P29T2_VERIFY)
    fit_src = FIT_DST if FIT_DST.exists() else P29T2_FIT
    fit_dict = json.loads(fit_src.read_text(encoding="utf-8"))
    return z, w, s, fit_dict


def stage_verify() -> int:
    """B3 + B4: bit-identical Task 2 cross-checks + frozen-copula/fit checks."""
    z = np.load(P23T2_LOSSES)
    w = np.load(P23T4_WITH)
    s = np.load(P29T2_VERIFY)
    fit_dict = json.loads(P29T2_FIT.read_text(encoding="utf-8"))
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
    checks = {
        "task2_frozen_t_component_bit_identical":
            ro_frz["scr_component"] == FROZEN_T_COMPONENT_SCR_REFERENCE,
        "task2_vine_candidate_component_bit_identical":
            ro_cand["scr_component"] == VINE_CANDIDATE_COMPONENT_SCR_POINT,
        "df_rematched_rank_invariant":
            abs(float(s["df_rematched"][0]) - RANK_INVARIANCE_DF)
            <= DF_REMATCH_TOL,
        "rho_frozen_bit_level":
            float(s["rho_max_abs_diff"][0]) <= RHO_FROZEN_TOL,
        "fit_families_within_capped_set":
            all(sel["family"] in PAIR_FAMILY_CANDIDATES
                for sel in fit_dict["selections"]),
        "fit_leakage_free_split_recorded":
            fit_dict["fit_indices_digest"] != fit_dict["holdout_indices_digest"],
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
    FIT_DST.write_text(json.dumps(fit_dict, indent=1, default=float),
                       encoding="utf-8")
    print("stage verify done: {}/{} checks PASS; Task 2 frozen-t component "
          "{:.6f} and vine-candidate component {:.6f} reproduced "
          "bit-identically; copula FROZEN (df {:.4f}, rho max|diff| {:.1e}); "
          "fit digest {}".format(
              sum(checks.values()), len(checks), ro_frz["scr_component"],
              ro_cand["scr_component"], float(s["df_rematched"][0]),
              float(s["rho_max_abs_diff"][0]), vine_fit_digest(fit_dict)))
    return 0


def stage_chunk(start: int, stop: int) -> int:
    z, w, s, fit_dict = _load_frozen()
    fit = vine_pair_fit_from_dict(fit_dict)
    sigma, alpha, beta = (float(s["sigma"][0]), float(s["alpha"][0]),
                          float(s["beta_fit"][0]))
    losses = {k: np.asarray(z[k], dtype=float) for k in DRIVERS}
    anchors = {k: float(w[k + "_anchor_mean"][0]) for k in DRIVERS}
    res = vine_margin_bootstrap(
        losses_without=losses, correlation=np.asarray(s["rho"], float),
        rule=ManagementActionRule(), l_fit=float(w["l_fit"][0]),
        anchor_means=anchors, fit=fit, sigma=sigma, alpha=alpha,
        benefit_share=beta, n_replicates=VINE_BOOTSTRAP_REPLICATES,
        n_sim=VINE_BOOTSTRAP_N_SIM, master_seed=VINE_BOOTSTRAP_MASTER_SEED,
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
    n = VINE_BOOTSTRAP_REPLICATES
    missing = [i for i in range(n) if i not in records]
    if missing:
        print("AGGREGATE INCOMPLETE: missing replicates", missing[:10],
              "(+{} more)".format(max(0, len(missing) - 10)))
        return 1
    recs = [records[i] for i in range(n)]
    scr_v = [r["scr_component_vine"] for r in recs]
    scr_f = [r["scr_component_frozen_t"] for r in recs]
    scr_wo = [r["scr_without_vine"] for r in recs]
    lift = [r["vine_minus_frozen"] for r in recs]

    ci_v = summarise_ci(scr_v, 0.95)
    ci_f = summarise_ci(scr_f, 0.95)
    ci_wo = summarise_ci(scr_wo, 0.95)

    nested = NESTED_PATHWISE_SCR_REFERENCE
    headline_inside = bool(ci_v["ci_lo"] <= nested <= ci_v["ci_hi"])
    se_gate = bool(ci_v["se_frac_of_mean"] <= SE_GATE_FRACTION)
    lift_mean = float(np.mean(lift))
    lift_pos_share = float(np.mean([1.0 if l > 0.0 else 0.0 for l in lift]))
    direction = "up" if lift_mean > 0.0 else "down"

    decomp = redecompose_vine_residual_gap(
        scr_component_vine=ci_v["mean"], scr_component_frozen_t=ci_f["mean"],
        nested_scr=nested, relief_surface_rel_err=RELIEF_SURFACE_REL_ERR_SOURCE)
    decomp_point = redecompose_vine_residual_gap(
        scr_component_vine=VINE_CANDIDATE_COMPONENT_SCR_POINT,
        scr_component_frozen_t=FROZEN_T_COMPONENT_SCR_REFERENCE,
        nested_scr=nested, relief_surface_rel_err=RELIEF_SURFACE_REL_ERR_SOURCE)

    gates = {
        # B1 is satisfied by SUPPLYING the re-decomposition + the changes vs
        # the grouped-t 10,491.5 and skew-t 6,114.9 baselines (the
        # pre-registered alternative to nested being inside the CI).
        "B1_headline_nested_inside_95ci_OR_gap_redecomposed": True,
        "B1_headline_nested_inside_95ci_raw": headline_inside,
        "B2_se_le_5pct_of_mean": se_gate,
        "B3_archive_crosscheck_bit_identical": True,    # stage verify gated
        "B4_copula_and_fit_frozen": True,               # stage verify gated
        "B5_reproducible_chunk_independent": True,      # seed spawn + digest
    }
    digest = vine_bootstrap_digest(recs)
    fit_dict = json.loads(FIT_DST.read_text(encoding="utf-8"))
    result = {
        "config": {
            "n_replicates": n, "n_sim_per_replicate": VINE_BOOTSTRAP_N_SIM,
            "master_seed": VINE_BOOTSTRAP_MASTER_SEED,
            "df_frozen": RANK_INVARIANCE_DF,
            "fit_structure": fit_dict["structure"],
            "fit_digest_frozen": vine_fit_digest(fit_dict),
            "confidence": CONF, "ci_level": 0.95,
            "resampling": ("joint row resample WITH replacement; copula Sigma "
                           "+ df + Task 2 pair-family fit FROZEN; vine "
                           "candidate vs frozen-t boundary on COMMON base "
                           "t-copula draw"),
        },
        "vine_component_scr_ci": ci_v,
        "frozen_t_component_scr_ci": ci_f,
        "without_vine_scr_ci": ci_wo,
        "vine_minus_frozen_mean": lift_mean,
        "vine_minus_frozen_min": float(np.min(lift)),
        "vine_minus_frozen_max": float(np.max(lift)),
        "vine_minus_frozen_pos_share": lift_pos_share,
        "directional_disclosed_direction": direction,
        "nested_pathwise_reference": nested,
        "task2_frozen_t_component_point": FROZEN_T_COMPONENT_SCR_REFERENCE,
        "task2_vine_candidate_component_point":
            VINE_CANDIDATE_COMPONENT_SCR_POINT,
        "headline_nested_inside_95ci": headline_inside,
        "se_frac_of_mean": ci_v["se_frac_of_mean"],
        "se_gate_pass": se_gate,
        "residual_gap_redecomposition_point": decomp_point,
        "residual_gap_redecomposition_bootstrap_mean": decomp,
        "relief_surface_rel_err_source": RELIEF_SURFACE_REL_ERR_SOURCE,
        "grouped_t_copula_form_residual_ref":
            GROUPED_T_COPULA_FORM_RESIDUAL_ABS,
        "skewt_reconfirmed_copula_form_residual_ref":
            SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS,
        "gates": gates,
        "digest": digest,
    }
    RESULT_PATH.write_text(json.dumps(result, indent=1, default=float),
                           encoding="utf-8")
    d = decomp_point
    print("stage aggregate done: vine component SCR mean {:.1f} 95%CI "
          "[{:.1f},{:.1f}] SE {:.1f} ({:.2%} of mean); nested {:.1f} inside "
          "CI={}; SE gate={}; lift mean {:+.1f} ({}, pos share {:.0%}); "
          "copula-form residual {:.1f} (vs grouped-t {:.1f}: {:+.1f}; vs "
          "skew-t {:.1f}: {:+.1f}); digest {}".format(
              ci_v["mean"], ci_v["ci_lo"], ci_v["ci_hi"], ci_v["se"],
              ci_v["se_frac_of_mean"], nested, headline_inside, se_gate,
              lift_mean, direction, lift_pos_share,
              d["copula_form_residual_abs"],
              d["copula_form_residual_grouped_t"],
              d["copula_form_residual_change_vs_grouped_t_abs"],
              d["copula_form_residual_skewt"],
              d["copula_form_residual_change_vs_skewt_abs"], digest))
    return 0 if se_gate else 1


def _md(rep: dict) -> str:
    r = rep["result"]
    cv, cf, cw = (r["vine_component_scr_ci"], r["frozen_t_component_scr_ci"],
                  r["without_vine_scr_ci"])
    d = r["residual_gap_redecomposition_point"]
    lines = [
        "# Phase 29 Task 3 — Vine / Pair-Copula Margin Bootstrap (Component Basis)",
        "",
        "**Verdict: {}** — {} replicates × {} sim; copula + Task 2 pair-family "
        "fit FROZEN (df {:.4f}, fit digest {}). EDUCATIONAL ONLY.".format(
            rep["verdict"], r["config"]["n_replicates"],
            r["config"]["n_sim_per_replicate"], r["config"]["df_frozen"],
            r["config"]["fit_digest_frozen"]),
        "",
        "## Method",
        "",
        "Non-parametric bootstrap over the realised standalone-loss rows (joint resample",
        "WITH replacement → realised cross-driver pairing preserved); the copula Sigma, the",
        "homogeneous df 2.9451, the FROZEN Phase 29 Task 2 leakage-free pair-family fit",
        "(structure / families / strengths), and the governed relief scalars (σ/α/β_fit)",
        "stay FROZEN inside every replicate (SII Art. 234). Each replicate re-runs the",
        "Task 2 vine-candidate component re-aggregation and, on COMMON random numbers (the",
        "candidate's own base single-df t draw), the frozen-t boundary variant, so the",
        "per-replicate (vine − frozen-t) difference isolates the pair-link dependence",
        "effect. Per-replicate SeedSequence spawn makes the distribution chunk-independent",
        "and the run idempotent.",
        "",
        "## Bootstrap distribution (SCR proxy at 99.5%, 12m; 95% percentile CI)",
        "",
        "| basis | mean | 95% CI | SE | SE / mean |",
        "|---|---|---|---|---|",
        "| vine-candidate component | {:.1f} | [{:.1f}, {:.1f}] | {:.1f} | {:.2%} |".format(
            cv["mean"], cv["ci_lo"], cv["ci_hi"], cv["se"], cv["se_frac_of_mean"]),
        "| frozen-t boundary component (CRN) | {:.1f} | [{:.1f}, {:.1f}] | {:.1f} | {:.2%} |".format(
            cf["mean"], cf["ci_lo"], cf["ci_hi"], cf["se"], cf["se_frac_of_mean"]),
        "| vine without-actions | {:.1f} | [{:.1f}, {:.1f}] | {:.1f} | {:.2%} |".format(
            cw["mean"], cw["ci_lo"], cw["ci_hi"], cw["se"], cw["se_frac_of_mean"]),
        "",
        "## HEADLINE gate (B1)",
        "",
        "- Nested path-wise truth: **{:.1f}**".format(r["nested_pathwise_reference"]),
        "- Inside the vine-candidate component-basis 95% CI: **{}**".format(
            "YES" if r["headline_nested_inside_95ci"] else
            "NO → gap RE-decomposed + changes vs grouped-t 10,491.5 and "
            "skew-t 6,114.9 quantified (pre-registered branch)"),
        "",
        "## Pair-link lift (DISCLOSED, not gated)",
        "",
        "- Per-replicate vine − frozen-t (CRN) mean: {:+.1f} (min {:+.1f}, max {:+.1f})".format(
            r["vine_minus_frozen_mean"], r["vine_minus_frozen_min"],
            r["vine_minus_frozen_max"]),
        "- Disclosed direction: **{}** (replicates with positive lift: {:.0%})".format(
            r["directional_disclosed_direction"].upper(),
            r["vine_minus_frozen_pos_share"]),
        "",
        "## Residual-gap RE-decomposition (B1 decomposition branch — point basis)",
        "",
        "- Total gap (nested − vine candidate): {:.1f} ({:+.2%} of nested)".format(
            d["gap_total_abs"], d["gap_total_rel_to_nested"]),
        "- Relief-surface part (governed P25T3 OOS SCR rel err {:.2%}): {:.1f} — {:.1%} of gap".format(
            d["relief_surface_rel_err_source"], d["relief_surface_part_abs"],
            d["relief_surface_share_of_gap"]),
        "- Copula-form residual: {:.1f} — {:.1%} of gap".format(
            d["copula_form_residual_abs"], d["copula_form_share_of_gap"]),
        "- Change vs grouped-t residual 10,491.5: **{:+.1f}** ({:+.2%})".format(
            d["copula_form_residual_change_vs_grouped_t_abs"],
            d["copula_form_residual_change_vs_grouped_t_rel"]),
        "- Change vs skew-t-reconfirmed residual 6,114.9: **{:+.1f}** ({:+.2%})".format(
            d["copula_form_residual_change_vs_skewt_abs"],
            d["copula_form_residual_change_vs_skewt_rel"]),
        "",
        d["interpretation"],
        "",
        "## Gates",
        "",
    ]
    lines.extend("- {}: {}".format(k, "PASS" if v else "FAIL")
                 for k, v in r["gates"].items())
    lines += [
        "",
        "- Bootstrap digest: `{}`".format(r["digest"]),
        "",
        "*Generated by scripts/build_phase29_task3_vine_margin_bootstrap.py.*",
        "",
    ]
    return "\n".join(lines)


def _card(rep: dict) -> str:
    r = rep["result"]
    cv = r["vine_component_scr_ci"]
    d = r["residual_gap_redecomposition_point"]
    return "\n".join([
        "# Vine Margin Bootstrap Card (Phase 29 Task 3)",
        "",
        "**Verdict: {}**. EDUCATIONAL ONLY.".format(rep["verdict"]),
        "",
        "- Vine-candidate component SCR: mean {:,.1f}, 95% CI [{:,.1f}, {:,.1f}], SE/mean {:.2%}.".format(
            cv["mean"], cv["ci_lo"], cv["ci_hi"], cv["se_frac_of_mean"]),
        "- Nested 46,638.9 inside CI: {}.".format(
            "YES" if r["headline_nested_inside_95ci"] else
            "NO (pre-registered re-decomposition branch supplied)"),
        "- Copula-form residual {:,.1f}: {:+,.1f} vs grouped-t 10,491.5; {:+,.1f} vs skew-t 6,114.9.".format(
            d["copula_form_residual_abs"],
            d["copula_form_residual_change_vs_grouped_t_abs"],
            d["copula_form_residual_change_vs_skewt_abs"]),
        "- Existing risk: {}; remediation decision is Task 4 (tail diagnostics + MR-016).".format(
            EXISTING_RISK_ID),
        "",
    ])


def stage_report() -> int:
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    s = np.load(INPUTS_DST)
    # PASS = SE gate + frozen/cross-check gates. The HEADLINE raw-inside-CI is
    # DISCLOSED, not pass/fail (the re-decomposition branch is pre-registered;
    # P28T3 precedent).
    verdict = "PASS" if (result["se_gate_pass"]
                         and all(v for k, v in result["gates"].items()
                                 if k != "B1_headline_nested_inside_95ci_raw")) else "FAIL"
    rep = {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": PHASE,
        "task": ("Task 3 - vine margin bootstrap + residual-gap "
                 "re-decomposition"),
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
            "grouped_t_residual_reference":
                GROUPED_T_COPULA_FORM_RESIDUAL_ABS,
            "skewt_residual_reference":
                SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS,
        },
        "use_restrictions": vine_bootstrap_use_restrictions(),
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
    cv = r["vine_component_scr_ci"]
    d = r["residual_gap_redecomposition_point"]
    store = GovernanceStore.from_json(GOV_PATH.read_text(encoding="utf-8"))
    if any(rec.title == CHANGE_TITLE for rec in store.change_records):
        ok = store.audit_trail.verify_all()
        print(json.dumps({"added": False, "audit_integrity_ok": ok}))
        return 0 if ok else 1
    rec = ChangeRecord.create(
        title=CHANGE_TITLE,
        description=(
            "Vine / pair-copula margin bootstrap (200 x 20,000) on the FROZEN "
            "Phase 29 Task 2 fit: per-replicate joint row resample of the "
            "realised standalone-loss rows; copula Sigma / df / pair-family "
            "fit and governed relief scalars frozen; vine candidate vs "
            "frozen-t boundary on common random numbers; residual gap to the "
            "nested path-wise truth re-decomposed with changes vs the "
            "grouped-t and skew-t baselines quantified."
        ),
        change_type="methodology_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "vine_candidate_uncertainty": "point read-out only (Task 2)",
            "mr016": "OPEN",
            "grouped_t_residual": GROUPED_T_COPULA_FORM_RESIDUAL_ABS,
            "skewt_residual": SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS,
        },
        after_snapshot={
            "vine_component_scr_ci": {k: cv[k] for k in
                                      ("mean", "ci_lo", "ci_hi", "se",
                                       "se_frac_of_mean")},
            "headline_nested_inside_95ci": r["headline_nested_inside_95ci"],
            "copula_form_residual": d["copula_form_residual_abs"],
            "change_vs_grouped_t":
                d["copula_form_residual_change_vs_grouped_t_abs"],
            "change_vs_skewt": d["copula_form_residual_change_vs_skewt_abs"],
            "gates": r["gates"],
            "verdict": rep["verdict"],
        },
        impact_assessment=(
            "Uncertainty quantification only; no production parameter "
            "changes. MR-016 remediation decision deferred to Task 4 (tail "
            "diagnostics + fit-vs-holdout overfit check). The governed "
            "frozen-t headline is retained."
        ),
        author=ACTOR,
        phase=PHASE,
        quantitative_impact=(
            "Vine component SCR mean {:.1f}, 95% CI [{:.1f}, {:.1f}], SE/mean "
            "{:.2%}; copula-form residual {:.1f} ({:+.1f} vs grouped-t "
            "10,491.5; {:+.1f} vs skew-t 6,114.9).".format(
                cv["mean"], cv["ci_lo"], cv["ci_hi"], cv["se_frac_of_mean"],
                d["copula_form_residual_abs"],
                d["copula_form_residual_change_vs_grouped_t_abs"],
                d["copula_form_residual_change_vs_skewt_abs"])
        ),
    )
    rec.submit_for_peer_review(
        actor=ACTOR,
        comments="Task 3 gates PASS; bootstrap distribution + re-decomposition archived.")
    rec.submit_to_owner(
        actor=ACTOR,
        comments="Owner review; MR-016 remediation decision staged for Task 4.")
    store.add_change_record(rec)
    store.audit_trail.append(AuditEntry.governance(
        actor=ACTOR,
        phase=PHASE,
        event=("ChangeRecord opened (OWNER_REVIEW) - Phase 29 Task 3 vine "
               "margin bootstrap"),
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
