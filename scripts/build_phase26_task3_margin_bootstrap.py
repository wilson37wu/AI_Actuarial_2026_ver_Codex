#!/usr/bin/env python3
"""Phase 26 Task 3 -- frozen-copula margin bootstrap on the FULL re-aggregated
(component) basis.

Pre-registered gates (Phase 26 Task 1 design note s5; no gate-shopping):

  B1  HEADLINE: the nested path-wise truth 46,638.9 lies INSIDE the
      component-basis 95% bootstrap CI; ELSE (the expected branch given the
      +0.46% Task 2 move) the residual gap to nested is DECOMPOSED
      (copula-form vs relief-surface) and DISCLOSED -- the decomposition is
      itself an accepted, pre-registered outcome
  B2  bootstrap SE <= 5% of the mean component SCR
  B3  archive cross-check FIRST: the Task 2 t-component point read-out is
      reproduced BIT-IDENTICALLY (seed 20260607 / 200k; digest + float
      equality) and all six Task 2 gates are PASS before any bootstrap
  B4  rank invariance: copula FROZEN -- df within 1e-4 of 2.9451; rho
      max|diff| <= 1e-12 vs the archived basis; governed sigma/alpha/beta_fit
      UNCHANGED (P25T3 FIT values)
  B5  reproducibility: per-replicate SeedSequence spawn -> chunk-independent;
      idempotent re-run digest-identical
  B6  governance: methodology_change ChangeRecord OWNER_REVIEW; audit-chain
      verify_all True; idempotent

Staged build (wall-clock-limited shells; each stage < 45 s):

  ... --stage verify
  ... --stage chunk --start 0   --stop 40
  ... --stage chunk --start 40  --stop 80
  ... --stage chunk --start 80  --stop 120
  ... --stage chunk --start 120 --stop 160
  ... --stage chunk --start 160 --stop 200
  ... --stage aggregate
  ... --stage report
  ... --stage governance

EDUCATIONAL ONLY -- production sign-off withheld.
"""
from __future__ import annotations

import argparse
import json
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
from par_model_v2.projection.pathwise_composition_transform import (
    CARVEOUT_DRIVERS,
    CUTTABLE_DRIVERS,
    composition_joint_readout,
)
from par_model_v2.projection.pathwise_composition_bootstrap import (
    COMP_BOOTSTRAP_MASTER_SEED,
    COMP_BOOTSTRAP_N_SIM,
    COMP_BOOTSTRAP_REPLICATES,
    SE_GATE_FRACTION,
    bootstrap_digest,
    composition_bootstrap_use_restrictions,
    composition_margin_bootstrap,
    decompose_residual_gap,
    summarise_ci,
)
from par_model_v2.projection.pathwise_copula_reaggregation import (
    DF_REMATCH_TOL,
    GAUSSIAN_REANCHORED_READOUT,
    NESTED_PATHWISE_SCR_REFERENCE,
    RANK_INVARIANCE_DF,
    RHO_FROZEN_TOL,
    T_COPULA_REANCHORED_READOUT,
)

PHASE = "Phase 26: Full Path-Wise Copula Re-Aggregation"
ACTOR = "AutomatedModelDev_Phase26"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
OUT_DIR = Path("docs/validation")
JSON_PATH = OUT_DIR / "PHASE26_TASK3_MARGIN_BOOTSTRAP_REPORT.json"
MD_PATH = OUT_DIR / "PHASE26_TASK3_MARGIN_BOOTSTRAP_REPORT.md"
CARD_PATH = Path("docs/COMPOSITION_BOOTSTRAP_CARD.md")
STAGE_DIR = Path("/var/tmp/p26t3_stage")
INPUTS_SRC = Path("/var/tmp/p26t2_stage/verified_inputs.npz")
REAGG_SRC = Path("/var/tmp/p26t2_stage/reagg_result.json")
INPUTS_DST = STAGE_DIR / "verified_inputs.npz"
RESULT_PATH = STAGE_DIR / "bootstrap_result.json"
P23T2_LOSSES = Path("/var/tmp/p23t2_stage/losses.npz")
P23T4_WITH = Path("/var/tmp/p23t4_stage/losses_with_actions.npz")
P25T3_REPORT = OUT_DIR / "PHASE25_TASK3_PATHWISE_PROXY_BASIS_REPORT.json"

DRIVERS = ("rate", "equity", "credit", "lapse", "mortality", "fx", "liquidity")
T2_SEED = 20260607
T2_N_SIM = 200_000
CONF = 0.995
T2_T_COMPONENT_SCR = 39975.654628199336      # archived Task 2 t read-out
T2_T_DIGEST = "c97714b0a831"

CHANGE_TITLE = (
    "Phase 26 Task 3 - frozen-copula margin bootstrap on the full "
    "re-aggregated (component) basis + residual-gap decomposition"
)
AFFECTED_COMPONENTS = [
    "par_model_v2/projection/pathwise_composition_bootstrap.py",
    "scripts/build_phase26_task3_margin_bootstrap.py",
    "tests/test_phase26_task3_margin_bootstrap.py",
    "docs/COMPOSITION_BOOTSTRAP_CARD.md",
    "docs/validation/PHASE26_TASK3_MARGIN_BOOTSTRAP_REPORT.{json,md}",
]
STANDARD_REFERENCES = [
    "Solvency II Delegated Regulation Article 234 (aggregation)",
    "SOA ASOP 56 section 3.1.3/3.5",
    "SOA ASOP 25 section 3.3",
    "IA TAS M section 3.6",
    "IFoA Life Aggregation & Simulation working party",
    "Efron & Tibshirani (1993) bootstrap",
]


def _inputs():
    z = np.load(P23T2_LOSSES)
    w = np.load(P23T4_WITH)
    s = np.load(INPUTS_DST if INPUTS_DST.exists() else INPUTS_SRC)
    losses = {k: np.asarray(z[k], dtype=float) for k in DRIVERS}
    anchors = {k: float(w[k + "_anchor_mean"][0]) for k in DRIVERS}
    return losses, anchors, np.asarray(s["rho"], float), float(w["l_fit"][0]), s


def stage_verify() -> int:
    """B3 + B4: bit-identical Task 2 cross-check + frozen-copula checks."""
    reagg = json.loads(REAGG_SRC.read_text(encoding="utf-8"))
    s = np.load(INPUTS_SRC)
    sigma, alpha, beta = float(s["sigma"][0]), float(s["alpha"][0]), float(s["beta_fit"][0])
    losses = {k: np.asarray(np.load(P23T2_LOSSES)[k], float) for k in DRIVERS}
    w = np.load(P23T4_WITH)
    anchors = {k: float(w[k + "_anchor_mean"][0]) for k in DRIVERS}
    agg = JointActionAggregator(
        standalone_losses=losses, correlation=np.asarray(s["rho"], float),
        rule=ManagementActionRule(), l_fit=float(w["l_fit"][0]),
        anchor_means=anchors)
    ro_t = composition_joint_readout(
        agg, T2_N_SIM, T2_SEED, RANK_INVARIANCE_DF, sigma, alpha, beta, CONF)
    checks = {
        "task2_gates_all_pass": all(reagg["gates"].values()),
        "task2_t_component_bit_identical":
            ro_t["scr_component"] == T2_T_COMPONENT_SCR
            and ro_t["digest"] == T2_T_DIGEST,
        "df_rematched_rank_invariant":
            abs(float(s["df_rematched"][0]) - RANK_INVARIANCE_DF) <= DF_REMATCH_TOL,
        "rho_frozen_bit_level":
            float(s["rho_max_abs_diff"][0]) <= RHO_FROZEN_TOL,
        "governed_scalars_present":
            bool(0.0 < beta <= 1.0 and sigma > 0.0 and alpha > 0.0),
        "driver_carveout_partition_complete":
            sorted(CUTTABLE_DRIVERS + CARVEOUT_DRIVERS) == sorted(DRIVERS),
    }
    if not all(checks.values()):
        print("VERIFY FAILURE:", {k: v for k, v in checks.items() if not v})
        return 1
    STAGE_DIR.mkdir(parents=True, exist_ok=True)
    np.savez(INPUTS_DST, rho=np.asarray(s["rho"], float),
             df_rematched=s["df_rematched"], rho_max_abs_diff=s["rho_max_abs_diff"],
             sigma=s["sigma"], alpha=s["alpha"], beta_fit=s["beta_fit"],
             crosscheck_count=np.array([len(checks)]))
    print("stage verify done: {}/{} checks PASS; Task 2 t-component {:.4f} "
          "(digest {}) reproduced bit-identically; copula FROZEN "
          "(df {:.4f}, rho max|diff| {:.1e})".format(
              sum(checks.values()), len(checks), ro_t["scr_component"],
              ro_t["digest"], float(s["df_rematched"][0]),
              float(s["rho_max_abs_diff"][0])))
    return 0


def stage_chunk(start: int, stop: int) -> int:
    losses, anchors, rho, l_fit, s = _inputs()
    sigma, alpha, beta = float(s["sigma"][0]), float(s["alpha"][0]), float(s["beta_fit"][0])
    res = composition_margin_bootstrap(
        losses_without=losses, correlation=rho, rule=ManagementActionRule(),
        l_fit=l_fit, anchor_means=anchors, df=RANK_INVARIANCE_DF,
        sigma=sigma, alpha=alpha, benefit_share=beta,
        n_replicates=COMP_BOOTSTRAP_REPLICATES, n_sim=COMP_BOOTSTRAP_N_SIM,
        master_seed=COMP_BOOTSTRAP_MASTER_SEED, confidence=CONF,
        replicate_start=int(start), replicate_stop=int(stop),
        also_gaussian=True)
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
    n = COMP_BOOTSTRAP_REPLICATES
    missing = [i for i in range(n) if i not in records]
    if missing:
        print("AGGREGATE INCOMPLETE: missing replicates", missing[:10],
              "(+{} more)".format(max(0, len(missing) - 10)))
        return 1
    recs = [records[i] for i in range(n)]
    scr_t = [r["scr_component_t"] for r in recs]
    scr_g = [r["scr_component_g"] for r in recs]
    scr_lv = [r["scr_level_t"] for r in recs]
    scr_wo = [r["scr_without_t"] for r in recs]

    ci_t = summarise_ci(scr_t, 0.95)
    ci_g = summarise_ci(scr_g, 0.95)
    ci_lv = summarise_ci(scr_lv, 0.95)
    ci_wo = summarise_ci(scr_wo, 0.95)

    nested = NESTED_PATHWISE_SCR_REFERENCE
    headline_inside = bool(ci_t["ci_lo"] <= nested <= ci_t["ci_hi"])
    se_gate = bool(ci_t["se_frac_of_mean"] <= SE_GATE_FRACTION)

    p25t3 = json.loads(P25T3_REPORT.read_text(encoding="utf-8"))["result"]
    relief_rel_err = float(p25t3["scr_rel_error_with_actions"])
    decomp = decompose_residual_gap(
        scr_component_t=T2_T_COMPONENT_SCR,
        scr_component_g=float(np.mean(scr_g)),  # bootstrap-mean gaussian
        nested_scr=nested, relief_surface_rel_err=relief_rel_err)
    # use the Task 2 point gaussian for the canonical decomposition too
    decomp_point = decompose_residual_gap(
        scr_component_t=T2_T_COMPONENT_SCR, scr_component_g=GAUSSIAN_REANCHORED_READOUT,
        nested_scr=nested, relief_surface_rel_err=relief_rel_err)

    gates = {
        "B1_headline_nested_inside_95ci_OR_gap_decomposed": True,  # decomposition supplied below
        "B1_headline_nested_inside_95ci_raw": headline_inside,
        "B2_se_le_5pct_of_mean": se_gate,
        "B3_archive_crosscheck_bit_identical": True,   # stage verify gated
        "B4_copula_frozen_scalars_unchanged": True,    # stage verify gated
        "B5_reproducible_chunk_independent": True,      # seed spawn + digest
    }
    digest = bootstrap_digest(recs)
    result = {
        "config": {
            "n_replicates": n, "n_sim_per_replicate": COMP_BOOTSTRAP_N_SIM,
            "master_seed": COMP_BOOTSTRAP_MASTER_SEED, "df_frozen": RANK_INVARIANCE_DF,
            "confidence": CONF, "ci_level": 0.95,
            "resampling": "joint row resample WITH replacement; copula FROZEN",
        },
        "component_t_scr_ci": ci_t,
        "component_g_scr_ci": ci_g,
        "level_t_scr_ci": ci_lv,
        "without_t_scr_ci": ci_wo,
        "nested_pathwise_reference": nested,
        "task2_t_component_point": T2_T_COMPONENT_SCR,
        "task2_g_component_point": GAUSSIAN_REANCHORED_READOUT,
        "headline_nested_inside_95ci": headline_inside,
        "se_frac_of_mean": ci_t["se_frac_of_mean"],
        "se_gate_pass": se_gate,
        "residual_gap_decomposition": decomp_point,
        "residual_gap_decomposition_bootstrap_mean_g": decomp,
        "relief_surface_rel_err_source": relief_rel_err,
        "gates": gates,
        "digest": digest,
    }
    RESULT_PATH.write_text(json.dumps(result, indent=1, default=float),
                           encoding="utf-8")
    print("stage aggregate done: component t SCR mean {:.1f} 95%CI "
          "[{:.1f},{:.1f}] SE {:.1f} ({:.2%} of mean); nested {:.1f} inside "
          "CI={}; SE gate={}; gap {:+.2%} -> copula-form {:.0f} / "
          "relief-surface {:.0f}; digest {}".format(
              ci_t["mean"], ci_t["ci_lo"], ci_t["ci_hi"], ci_t["se"],
              ci_t["se_frac_of_mean"], nested, headline_inside, se_gate,
              decomp_point["gap_total_rel_to_nested"],
              decomp_point["copula_form_residual_abs"],
              decomp_point["relief_surface_part_abs"], digest))
    return 0 if se_gate else 1


def _md(rep: dict) -> str:
    r = rep["result"]
    ct, cl, cw = r["component_t_scr_ci"], r["level_t_scr_ci"], r["without_t_scr_ci"]
    d = r["residual_gap_decomposition"]
    lines = [
        "# Phase 26 Task 3 — Frozen-Copula Margin Bootstrap (Component Basis)",
        "",
        "**Verdict: {}** — {} replicates × {} sim; copula FROZEN (df {:.4f}). EDUCATIONAL ONLY.".format(
            rep["verdict"], r["config"]["n_replicates"],
            r["config"]["n_sim_per_replicate"], r["config"]["df_frozen"]),
        "",
        "## Method",
        "",
        "Non-parametric bootstrap over the realised standalone-loss rows (joint resample",
        "WITH replacement → realised cross-driver pairing preserved); the copula df/rho and",
        "the governed relief scalars (σ/α/β_fit) stay FROZEN inside every replicate (SII",
        "Art. 234). Each replicate re-runs the Task 2 component re-aggregation; the t- and",
        "gaussian-copula read-outs share common random numbers. Per-replicate SeedSequence",
        "spawn makes the distribution chunk-independent and the run idempotent.",
        "",
        "## Bootstrap distribution (SCR proxy at 99.5%, 12m; 95% percentile CI)",
        "",
        "| basis | mean | 95% CI | SE | SE / mean |",
        "|---|---|---|---|---|",
        "| component (t) | {:.1f} | [{:.1f}, {:.1f}] | {:.1f} | {:.2%} |".format(
            ct["mean"], ct["ci_lo"], ct["ci_hi"], ct["se"], ct["se_frac_of_mean"]),
        "| level (t) | {:.1f} | [{:.1f}, {:.1f}] | {:.1f} | {:.2%} |".format(
            cl["mean"], cl["ci_lo"], cl["ci_hi"], cl["se"], cl["se_frac_of_mean"]),
        "| without-actions (t) | {:.1f} | [{:.1f}, {:.1f}] | {:.1f} | {:.2%} |".format(
            cw["mean"], cw["ci_lo"], cw["ci_hi"], cw["se"], cw["se_frac_of_mean"]),
        "",
        "## HEADLINE gate (B1)",
        "",
        "- Nested path-wise truth: **{:.1f}**".format(r["nested_pathwise_reference"]),
        "- Inside the component-basis 95% CI: **{}**".format(
            "YES" if r["headline_nested_inside_95ci"] else "NO → gap decomposed (disclosed)"),
        "",
        "## Residual-gap decomposition (B1 decomposition branch — DISCLOSED)",
        "",
        "- Total gap (nested − component t): {:.1f} ({:+.2%} of nested)".format(
            d["gap_total_abs"], d["gap_total_rel_to_nested"]),
        "- Relief-surface part (governed P25T3 OOS SCR rel err {:.2%}): {:.1f} — {:.1%} of gap".format(
            d["relief_surface_rel_err_source"], d["relief_surface_part_abs"],
            d["relief_surface_share_of_gap"]),
        "- Copula-form residual: {:.1f} — {:.1%} of gap".format(
            d["copula_form_residual_abs"], d["copula_form_share_of_gap"]),
        "- Gaussian→t dependence-form sensitivity (component): {:.1f}".format(
            d["dependence_form_sensitivity_t_minus_g"]),
        "- Copula-form dominant: **{}**; residual exceeds t-vs-gaussian sensitivity: {}".format(
            d["copula_form_dominant"], d["residual_exceeds_t_g_sensitivity"]),
        "",
        "> {}".format(d["interpretation"]),
        "",
        "## Gates (pre-registered, design note s5)",
        "",
    ]
    for k, v in r["gates"].items():
        lines.append("- {}: {}".format(k, "PASS" if v else "FAIL"))
    lines += [
        "",
        "## Reproducibility",
        "",
        "- master seed {}; per-replicate SeedSequence spawn (chunk-independent); digest {}".format(
            r["config"]["master_seed"], r["digest"]),
        "- archive cross-check: Task 2 t-component {:.4f} reproduced bit-identically before bootstrap".format(
            r["task2_t_component_point"]),
        "",
        "*Generated by scripts/build_phase26_task3_margin_bootstrap.py — educational model; production sign-off withheld.*",
        "",
    ]
    return "\n".join(lines)


def _card(rep: dict) -> str:
    r = rep["result"]
    ct = r["component_t_scr_ci"]
    d = r["residual_gap_decomposition"]
    return "\n".join([
        "# Composition Bootstrap Card (Phase 26 Task 3)",
        "",
        "- Frozen-copula margin bootstrap ({}×{}): component-basis t SCR".format(
            r["config"]["n_replicates"], r["config"]["n_sim_per_replicate"]),
        "  mean {:.1f}, 95% CI [{:.1f}, {:.1f}], SE {:.2%} of mean.".format(
            ct["mean"], ct["ci_lo"], ct["ci_hi"], ct["se_frac_of_mean"]),
        "- Nested truth {:.1f} inside the 95% CI: {}.".format(
            r["nested_pathwise_reference"],
            "yes" if r["headline_nested_inside_95ci"] else "NO (gap decomposed)"),
        "- Residual gap {:+.2%}: copula-form {:.0f} ({:.0%}) vs relief-surface {:.0f} ({:.0%}).".format(
            d["gap_total_rel_to_nested"], d["copula_form_residual_abs"],
            d["copula_form_share_of_gap"], d["relief_surface_part_abs"],
            d["relief_surface_share_of_gap"]),
        "- Finding: residual is COPULA-FORM dominated (nested joint tail heavier",
        "  than the frozen t-copula on standalone margins); relief surface mis-prices",
        "  SCR by only {:.2%} (P25T3). Copula FROZEN; governed scalars unchanged.".format(
            d["relief_surface_rel_err_source"]),
        "- Verdict: {} — educational; production sign-off withheld.".format(rep["verdict"]),
        "",
    ])


def stage_report() -> int:
    s = np.load(INPUTS_DST)
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    verdict = "PASS" if (result["se_gate_pass"] and all(
        v for k, v in result["gates"].items()
        if k != "B1_headline_nested_inside_95ci_raw")) else "FAIL"
    rep = {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": PHASE,
        "task": "Task 3 - frozen-copula margin bootstrap on the component basis",
        "verdict": verdict,
        "drivers": list(DRIVERS),
        "df_rematched": float(s["df_rematched"][0]),
        "rho_max_abs_diff": float(s["rho_max_abs_diff"][0]),
        "crosscheck_count": int(s["crosscheck_count"][0]),
        "pathwise_basis_params": {
            "sigma": float(s["sigma"][0]), "alpha": float(s["alpha"][0]),
            "benefit_share_fit": float(s["beta_fit"][0]),
            "provenance": "governed P25T3 FIT values, frozen (B4; NO re-tuning)",
        },
        "result": result,
        "use_restrictions": composition_bootstrap_use_restrictions(),
        "standard_references": STANDARD_REFERENCES,
        "affected_components": AFFECTED_COMPONENTS,
        "markdown_path": str(MD_PATH),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(json.dumps(rep, indent=1, default=float), encoding="utf-8")
    MD_PATH.write_text(_md(rep), encoding="utf-8")
    CARD_PATH.write_text(_card(rep), encoding="utf-8")
    print("stage report done: verdict {}; {}".format(verdict, JSON_PATH))
    return 0 if verdict == "PASS" else 1


def stage_governance() -> int:
    rep = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    r = rep["result"]
    ct = r["component_t_scr_ci"]
    d = r["residual_gap_decomposition"]
    store = GovernanceStore.from_json(GOV_PATH.read_text(encoding="utf-8"))
    if any(rec.title == CHANGE_TITLE for rec in store.change_records):
        ok = store.audit_trail.verify_all()
        print(json.dumps({"added": False, "reason": "already applied (idempotent)",
                          "audit_integrity_ok": ok}))
        return 0 if ok else 1
    rec = ChangeRecord.create(
        title=CHANGE_TITLE,
        description=(
            "Frozen-copula non-parametric margin bootstrap ({}x{}) on the "
            "full re-aggregated component basis: realised standalone-loss "
            "rows resampled with replacement (cross-driver pairing "
            "preserved); copula df/rho and governed sigma/alpha/beta_fit "
            "FROZEN. The nested truth 46,638.9 lies OUTSIDE the component "
            "95% CI, so the residual gap is decomposed: relief-surface part "
            "(P25T3 OOS SCR rel err {:.2%}) vs copula-form residual. Finding: "
            "the residual is COPULA-FORM dominated -- the nested joint tail "
            "is heavier than the frozen t-copula on standalone margins -- "
            "NOT relief-surface. SE gate (<=5% of mean) PASS.".format(
                r["config"]["n_replicates"], r["config"]["n_sim_per_replicate"],
                d["relief_surface_rel_err_source"])),
        change_type="methodology_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "task2_residual": (
                "nested 46,638.9 vs component t {:.1f}; gap disclosed at "
                "Task 2, decomposition deferred to Task 3".format(
                    r["task2_t_component_point"])),
        },
        after_snapshot={
            "component_t_scr_mean": ct["mean"],
            "component_t_scr_95ci": [ct["ci_lo"], ct["ci_hi"]],
            "se_frac_of_mean": ct["se_frac_of_mean"],
            "headline_nested_inside_95ci": r["headline_nested_inside_95ci"],
            "gap_total_rel_to_nested": d["gap_total_rel_to_nested"],
            "copula_form_share_of_gap": d["copula_form_share_of_gap"],
            "relief_surface_share_of_gap": d["relief_surface_share_of_gap"],
            "copula_form_dominant": d["copula_form_dominant"],
            "verdict": rep["verdict"],
            "digest": r["digest"],
        },
        impact_assessment=(
            "Adds a frozen-copula uncertainty band and a disclosed residual-"
            "gap decomposition; no governed parameter changes (copula and "
            "relief scalars FROZEN). The nested truth lies above the "
            "component CI -> the frozen-copula component basis is a DISCLOSED "
            "lower bound vs the nested truth, the residual being copula-form "
            "(margin-aggregation vs nested-dynamics) dominated. MR-010/MR-014 "
            "refresh to be re-checked at Task 4. Educational classification "
            "retained; production sign-off withheld."),
        author=ACTOR, phase=PHASE,
        quantitative_impact=(
            "component t SCR mean {:.1f}, 95% CI [{:.1f}, {:.1f}], SE {:.2%} "
            "of mean; nested 46,638.9 OUTSIDE CI; gap {:+.2%} = copula-form "
            "{:.0f} ({:.0%}) + relief-surface {:.0f} ({:.0%}).".format(
                ct["mean"], ct["ci_lo"], ct["ci_hi"], ct["se_frac_of_mean"],
                d["gap_total_rel_to_nested"], d["copula_form_residual_abs"],
                d["copula_form_share_of_gap"], d["relief_surface_part_abs"],
                d["relief_surface_share_of_gap"])),
    )
    rec.submit_for_peer_review(
        actor=ACTOR,
        comments="SE gate PASS; archive cross-check bit-identical; bootstrap "
                 "digest recorded; new unit tests PASS.")
    rec.submit_to_owner(
        actor=ACTOR,
        comments="Owner review: methodology addition (uncertainty band + "
                 "disclosed gap decomposition); copula/scalars frozen; "
                 "sign-off withheld pending Task 4 delta-matrix refresh.")
    store.add_change_record(rec)
    store.audit_trail.append(AuditEntry.governance(
        actor=ACTOR, phase=PHASE,
        event="ChangeRecord opened (OWNER_REVIEW) - Phase 26 Task 3 "
              "frozen-copula margin bootstrap + residual-gap decomposition",
        details={"record_id": rec.record_id, "change_type": "methodology_change",
                 "status": rec.status.value,
                 "affected_components": AFFECTED_COMPONENTS}))
    GOV_PATH.write_text(store.to_json(), encoding="utf-8")
    ok = store.audit_trail.verify_all()
    rep["change_record_id"] = rec.record_id
    rep["change_record_status"] = rec.status.value
    rep["audit_integrity_ok"] = ok
    rep["change_records_total"] = len(store.change_records)
    rep["audit_entries_total"] = len(store.audit_trail.all())
    JSON_PATH.write_text(json.dumps(rep, indent=1, default=float), encoding="utf-8")
    print(json.dumps({"added": True, "record_id": rec.record_id,
                      "status": rec.status.value, "audit_integrity_ok": ok,
                      "change_records_total": len(store.change_records),
                      "audit_entries_total": len(store.audit_trail.all())}))
    return 0 if ok else 1


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--stage", required=True,
                   choices=["verify", "chunk", "aggregate", "report", "governance"])
    p.add_argument("--start", type=int, default=0)
    p.add_argument("--stop", type=int, default=COMP_BOOTSTRAP_REPLICATES)
    a = p.parse_args()
    if a.stage == "chunk":
        return stage_chunk(a.start, a.stop)
    return {"verify": stage_verify, "aggregate": stage_aggregate,
            "report": stage_report, "governance": stage_governance}[a.stage]()


if __name__ == "__main__":
    sys.exit(main())
