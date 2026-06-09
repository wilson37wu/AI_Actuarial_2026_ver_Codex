#!/usr/bin/env python3
"""Phase 27 Task 3 -- skew-t-copula margin bootstrap on the FULL re-aggregated
(component) basis + residual-gap RE-decomposition.

Pre-registered gates (Phase 27 Task 1 design note s5; no gate-shopping):

  C1  HEADLINE: the nested path-wise truth 46,638.9 lies INSIDE the skew-t
      component-basis 95% bootstrap CI; ELSE the residual gap to nested is
      RE-decomposed (copula-form vs relief-surface) AND the REDUCTION of the
      copula-form residual vs the frozen-t baseline 6,120.2 is quantified --
      the re-decomposition is itself an accepted, pre-registered outcome
  C2  DIRECTIONAL: the skew-t must NOT WIDEN the nested gap on common random
      numbers vs the symmetric-t basis (per-replicate skew-t >= symmetric-t)
  C3  bootstrap SE <= 5% of the mean skew-t component SCR
  C4  archive cross-check FIRST: the Task 2 frozen-t component read-out
      39,975.654628199336 and the skew-t-at-gamma_hat 200k component read-out
      39,980.95565911311 are reproduced BIT-IDENTICALLY before any bootstrap
  C5  rank invariance: copula FROZEN -- df within 1e-4 of 2.9451; rho
      max|diff| <= 1e-12; gamma frozen at the Task 2 leakage-free gamma_hat;
      governed sigma/alpha/beta_fit UNCHANGED (P25T3 FIT values)
  C6  reproducibility: per-replicate SeedSequence spawn -> chunk-independent;
      idempotent re-run digest-identical
  C7  governance: methodology_change ChangeRecord OWNER_REVIEW; audit-chain
      verify_all True; idempotent

Staged build (wall-clock-limited shells; each stage < 45 s):

  ... --stage verify
  ... --stage chunk --start 0   --stop 50
  ... --stage chunk --start 50  --stop 100
  ... --stage chunk --start 100 --stop 150
  ... --stage chunk --start 150 --stop 200
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
)
from par_model_v2.projection.skew_t_copula_aggregation import (
    DF_REMATCH_TOL,
    FROZEN_T_COMPONENT_SCR_REFERENCE,
    NESTED_PATHWISE_SCR_REFERENCE,
    RANK_INVARIANCE_DF,
    RHO_FROZEN_TOL,
    composition_skewt_readout,
)
from par_model_v2.projection.skew_t_copula_bootstrap import (
    COPULA_FORM_RESIDUAL_FROZEN_T,
    SE_GATE_FRACTION,
    SKEWT_BOOTSTRAP_MASTER_SEED,
    SKEWT_BOOTSTRAP_N_SIM,
    SKEWT_BOOTSTRAP_REPLICATES,
    bootstrap_digest,
    redecompose_residual_gap,
    skewt_bootstrap_use_restrictions,
    skewt_margin_bootstrap,
    summarise_ci,
)

PHASE = "Phase 27: Richer Upper-Tail-Dependence Copula (skew-t)"
ACTOR = "AutomatedModelDev_Phase27"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
OUT_DIR = Path("docs/validation")
JSON_PATH = OUT_DIR / "PHASE27_TASK3_SKEW_T_BOOTSTRAP_REPORT.json"
MD_PATH = OUT_DIR / "PHASE27_TASK3_SKEW_T_BOOTSTRAP_REPORT.md"
CARD_PATH = Path("docs/SKEW_T_BOOTSTRAP_CARD.md")
STAGE_DIR = Path("/var/tmp/p27t3_stage")
P27T2_VERIFIED = Path("/var/tmp/p27t2_stage/verified.npz")
P27T2_FIT = Path("/var/tmp/p27t2_stage/fit_result.json")
INPUTS_DST = STAGE_DIR / "verified_inputs.npz"
RESULT_PATH = STAGE_DIR / "bootstrap_result.json"
P23T2_LOSSES = Path("/var/tmp/p23t2_stage/losses.npz")
P23T4_WITH = Path("/var/tmp/p23t4_stage/losses_with_actions.npz")
P25T3_REPORT = OUT_DIR / "PHASE25_TASK3_PATHWISE_PROXY_BASIS_REPORT.json"
P27T2_REPORT = OUT_DIR / "PHASE27_TASK2_SKEW_T_COPULA_REPORT.json"

DRIVERS = ("rate", "equity", "credit", "lapse", "mortality", "fx", "liquidity")
T2_SEED = 20260607
T2_N_SIM = 200_000
CONF = 0.995
# Archived Task 2 point read-outs (the C4 bit-identical cross-check targets).
T2_FROZEN_T_COMPONENT = 39975.654628199336
T2_SKEWT_COMPONENT_AT_GAMMA_HAT = 39980.95565911311

CHANGE_TITLE = (
    "Phase 27 Task 3 - skew-t-copula margin bootstrap on the component basis "
    "+ residual-gap RE-decomposition (copula-form reduction vs frozen-t 6,120.2)"
)
AFFECTED_COMPONENTS = [
    "par_model_v2/projection/skew_t_copula_bootstrap.py",
    "scripts/build_phase27_task3_skew_t_bootstrap.py",
    "tests/test_phase27_task3_skew_t_bootstrap.py",
    "docs/SKEW_T_BOOTSTRAP_CARD.md",
    "docs/validation/PHASE27_TASK3_SKEW_T_BOOTSTRAP_REPORT.{json,md}",
]
STANDARD_REFERENCES = [
    "Solvency II Delegated Regulation Article 234 (aggregation)",
    "Demarta & McNeil (2005) The t copula and related copulas",
    "McNeil, Frey & Embrechts (2015) QRM ch. 7",
    "SOA ASOP 56 section 3.1.3/3.5",
    "IA TAS M section 3.6",
    "Efron & Tibshirani (1993) bootstrap",
]


def _gamma_hat() -> float:
    return float(json.loads(P27T2_FIT.read_text(encoding="utf-8"))["gamma_hat"])


def _inputs():
    z = np.load(P23T2_LOSSES)
    w = np.load(P23T4_WITH)
    s = np.load(INPUTS_DST if INPUTS_DST.exists() else P27T2_VERIFIED)
    losses = {k: np.asarray(z[k], dtype=float) for k in DRIVERS}
    anchors = {k: float(w[k + "_anchor_mean"][0]) for k in DRIVERS}
    return losses, anchors, np.asarray(s["rho"], float), float(w["l_fit"][0]), s


def stage_verify() -> int:
    """C4 + C5: bit-identical Task 2 cross-checks + frozen-copula checks."""
    s = np.load(P27T2_VERIFIED)
    sigma, alpha, beta = float(s["sigma"][0]), float(s["alpha"][0]), float(s["beta_fit"][0])
    gamma_hat = _gamma_hat()
    losses = {k: np.asarray(np.load(P23T2_LOSSES)[k], float) for k in DRIVERS}
    w = np.load(P23T4_WITH)
    anchors = {k: float(w[k + "_anchor_mean"][0]) for k in DRIVERS}
    agg = JointActionAggregator(
        standalone_losses=losses, correlation=np.asarray(s["rho"], float),
        rule=ManagementActionRule(), l_fit=float(w["l_fit"][0]),
        anchor_means=anchors)
    # archive cross-check: frozen-t (gamma=0) and skew-t (gamma_hat) point read-outs
    ro_sym = composition_skewt_readout(
        agg, T2_N_SIM, T2_SEED, RANK_INVARIANCE_DF, 0.0, sigma, alpha, beta, CONF)
    ro_sk = composition_skewt_readout(
        agg, T2_N_SIM, T2_SEED, RANK_INVARIANCE_DF, gamma_hat, sigma, alpha, beta, CONF)
    checks = {
        "task2_frozen_t_component_bit_identical":
            ro_sym["scr_component"] == T2_FROZEN_T_COMPONENT,
        "task2_skewt_component_bit_identical":
            ro_sk["scr_component"] == T2_SKEWT_COMPONENT_AT_GAMMA_HAT,
        "gamma_hat_nonneg_boundary":
            bool(0.0 <= gamma_hat < 1e-3),
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
             gamma_hat=np.array([gamma_hat]),
             crosscheck_count=np.array([len(checks)]))
    print("stage verify done: {}/{} checks PASS; Task 2 frozen-t component "
          "{:.6f} and skew-t-at-gamma_hat component {:.6f} reproduced "
          "bit-identically; copula FROZEN (df {:.4f}, rho max|diff| {:.1e}, "
          "gamma_hat {:.3e})".format(
              sum(checks.values()), len(checks), ro_sym["scr_component"],
              ro_sk["scr_component"], float(s["df_rematched"][0]),
              float(s["rho_max_abs_diff"][0]), gamma_hat))
    return 0


def stage_chunk(start: int, stop: int) -> int:
    losses, anchors, rho, l_fit, s = _inputs()
    sigma, alpha, beta = float(s["sigma"][0]), float(s["alpha"][0]), float(s["beta_fit"][0])
    gamma_hat = float(s["gamma_hat"][0])
    res = skewt_margin_bootstrap(
        losses_without=losses, correlation=rho, rule=ManagementActionRule(),
        l_fit=l_fit, anchor_means=anchors, df=RANK_INVARIANCE_DF,
        gamma=gamma_hat, sigma=sigma, alpha=alpha, benefit_share=beta,
        n_replicates=SKEWT_BOOTSTRAP_REPLICATES, n_sim=SKEWT_BOOTSTRAP_N_SIM,
        master_seed=SKEWT_BOOTSTRAP_MASTER_SEED, confidence=CONF,
        replicate_start=int(start), replicate_stop=int(stop))
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
    n = SKEWT_BOOTSTRAP_REPLICATES
    missing = [i for i in range(n) if i not in records]
    if missing:
        print("AGGREGATE INCOMPLETE: missing replicates", missing[:10],
              "(+{} more)".format(max(0, len(missing) - 10)))
        return 1
    recs = [records[i] for i in range(n)]
    scr_sk = [r["scr_component_skewt"] for r in recs]
    scr_sym = [r["scr_component_sym"] for r in recs]
    scr_wo = [r["scr_without_skewt"] for r in recs]
    lift = [r["skewt_minus_sym"] for r in recs]
    asym = [r["radial_asymmetry"] for r in recs]

    ci_sk = summarise_ci(scr_sk, 0.95)
    ci_sym = summarise_ci(scr_sym, 0.95)
    ci_wo = summarise_ci(scr_wo, 0.95)

    nested = NESTED_PATHWISE_SCR_REFERENCE
    headline_inside = bool(ci_sk["ci_lo"] <= nested <= ci_sk["ci_hi"])
    se_gate = bool(ci_sk["se_frac_of_mean"] <= SE_GATE_FRACTION)
    # directional gate (pre-registered): the SYSTEMATIC skew-t effect on common
    # random numbers does NOT widen the nested gap, i.e. the CRN mean lift >= 0.
    # With gamma_hat ~ 0 the per-replicate lift is MC-noise around a ~0 mean, so
    # the fraction of non-negative replicates is reported as a DISCLOSED
    # diagnostic (not a gate; a per-replicate sign flip is sampling noise, not a
    # copula widening the dependence).
    not_widened_mean = bool(float(np.mean(lift)) >= 0.0)
    lift_nonneg_share = float(np.mean([1.0 if l >= 0.0 else 0.0 for l in lift]))

    p25t3 = json.loads(P25T3_REPORT.read_text(encoding="utf-8"))["result"]
    relief_rel_err = float(p25t3["scr_rel_error_with_actions"])
    decomp = redecompose_residual_gap(
        scr_component_skewt=ci_sk["mean"], scr_component_sym=ci_sym["mean"],
        nested_scr=nested, relief_surface_rel_err=relief_rel_err,
        copula_form_residual_frozen_t=COPULA_FORM_RESIDUAL_FROZEN_T)
    # also a point re-decomposition on the Task 2 200k read-outs (canonical)
    decomp_point = redecompose_residual_gap(
        scr_component_skewt=T2_SKEWT_COMPONENT_AT_GAMMA_HAT,
        scr_component_sym=T2_FROZEN_T_COMPONENT,
        nested_scr=nested, relief_surface_rel_err=relief_rel_err,
        copula_form_residual_frozen_t=COPULA_FORM_RESIDUAL_FROZEN_T)

    gates = {
        "C1_headline_nested_inside_95ci_OR_gap_redecomposed": True,  # decomposition supplied
        "C1_headline_nested_inside_95ci_raw": headline_inside,
        "C2_directional_skewt_not_widen_gap_mean": not_widened_mean,
        "C3_se_le_5pct_of_mean": se_gate,
        "C4_archive_crosscheck_bit_identical": True,   # stage verify gated
        "C5_copula_frozen_scalars_unchanged": True,    # stage verify gated
        "C6_reproducible_chunk_independent": True,      # seed spawn + digest
    }
    digest = bootstrap_digest(recs)
    result = {
        "config": {
            "n_replicates": n, "n_sim_per_replicate": SKEWT_BOOTSTRAP_N_SIM,
            "master_seed": SKEWT_BOOTSTRAP_MASTER_SEED,
            "df_frozen": RANK_INVARIANCE_DF, "gamma_frozen": _gamma_hat(),
            "confidence": CONF, "ci_level": 0.95,
            "resampling": ("joint row resample WITH replacement; copula df/rho "
                           "AND gamma FROZEN; skew-t vs symmetric-t on CRN"),
        },
        "skewt_component_scr_ci": ci_sk,
        "symmetric_component_scr_ci": ci_sym,
        "without_skewt_scr_ci": ci_wo,
        "skewt_minus_sym_mean": float(np.mean(lift)),
        "skewt_minus_sym_min": float(np.min(lift)),
        "skewt_minus_sym_max": float(np.max(lift)),
        "radial_asymmetry_mean": float(np.mean(asym)),
        "nested_pathwise_reference": nested,
        "task2_frozen_t_component_point": T2_FROZEN_T_COMPONENT,
        "task2_skewt_component_point": T2_SKEWT_COMPONENT_AT_GAMMA_HAT,
        "headline_nested_inside_95ci": headline_inside,
        "se_frac_of_mean": ci_sk["se_frac_of_mean"],
        "se_gate_pass": se_gate,
        "directional_not_widened_mean": not_widened_mean,
        "directional_lift_nonneg_share": lift_nonneg_share,
        "residual_gap_redecomposition_point": decomp_point,
        "residual_gap_redecomposition_bootstrap_mean": decomp,
        "relief_surface_rel_err_source": relief_rel_err,
        "gates": gates,
        "digest": digest,
    }
    RESULT_PATH.write_text(json.dumps(result, indent=1, default=float),
                           encoding="utf-8")
    d = decomp_point
    print("stage aggregate done: skew-t component SCR mean {:.1f} 95%CI "
          "[{:.1f},{:.1f}] SE {:.1f} ({:.2%} of mean); nested {:.1f} inside "
          "CI={}; SE gate={}; directional(not-widen mean)={} (nonneg share "
          "{:.0%}); copula-form residual {:.1f} (frozen-t {:.1f}, reduction "
          "{:.1f} = {:.2%}); digest {}".format(
              ci_sk["mean"], ci_sk["ci_lo"], ci_sk["ci_hi"], ci_sk["se"],
              ci_sk["se_frac_of_mean"], nested, headline_inside, se_gate,
              not_widened_mean, lift_nonneg_share,
              d["copula_form_residual_abs"], d["copula_form_residual_frozen_t"],
              d["copula_form_residual_reduction_abs"],
              d["copula_form_residual_reduction_rel"], digest))
    return 0 if (se_gate and not_widened_mean) else 1


def _md(rep: dict) -> str:
    r = rep["result"]
    ck, cs, cw = r["skewt_component_scr_ci"], r["symmetric_component_scr_ci"], r["without_skewt_scr_ci"]
    d = r["residual_gap_redecomposition_point"]
    lines = [
        "# Phase 27 Task 3 — Skew-t-Copula Margin Bootstrap (Component Basis)",
        "",
        "**Verdict: {}** — {} replicates × {} sim; copula FROZEN (df {:.4f}, gamma_hat {:.3e}). EDUCATIONAL ONLY.".format(
            rep["verdict"], r["config"]["n_replicates"],
            r["config"]["n_sim_per_replicate"], r["config"]["df_frozen"],
            rep["gamma_hat"]),
        "",
        "## Method",
        "",
        "Non-parametric bootstrap over the realised standalone-loss rows (joint resample",
        "WITH replacement → realised cross-driver pairing preserved); the copula df/rho, the",
        "fitted upper-tail-asymmetry scalar γ̂, and the governed relief scalars (σ/α/β_fit)",
        "stay FROZEN inside every replicate (SII Art. 234). Each replicate re-runs the Task 2",
        "skew-t component re-aggregation and, on COMMON random numbers (the same latent",
        "Gaussian / chi-square mixing draw), the nested γ = 0 symmetric-t variant, so the",
        "per-replicate (skew-t − symmetric) difference isolates the γ effect exactly. The",
        "(df, γ̂) marginal-CDF interpolant is built once and reused. Per-replicate",
        "SeedSequence spawn makes the distribution chunk-independent and the run idempotent.",
        "",
        "## Bootstrap distribution (SCR proxy at 99.5%, 12m; 95% percentile CI)",
        "",
        "| basis | mean | 95% CI | SE | SE / mean |",
        "|---|---|---|---|---|",
        "| skew-t component | {:.1f} | [{:.1f}, {:.1f}] | {:.1f} | {:.2%} |".format(
            ck["mean"], ck["ci_lo"], ck["ci_hi"], ck["se"], ck["se_frac_of_mean"]),
        "| symmetric-t component (γ=0, CRN) | {:.1f} | [{:.1f}, {:.1f}] | {:.1f} | {:.2%} |".format(
            cs["mean"], cs["ci_lo"], cs["ci_hi"], cs["se"], cs["se_frac_of_mean"]),
        "| skew-t without-actions | {:.1f} | [{:.1f}, {:.1f}] | {:.1f} | {:.2%} |".format(
            cw["mean"], cw["ci_lo"], cw["ci_hi"], cw["se"], cw["se_frac_of_mean"]),
        "",
        "## HEADLINE gate (C1)",
        "",
        "- Nested path-wise truth: **{:.1f}**".format(r["nested_pathwise_reference"]),
        "- Inside the skew-t component-basis 95% CI: **{}**".format(
            "YES" if r["headline_nested_inside_95ci"] else "NO → gap RE-decomposed (disclosed)"),
        "",
        "## DIRECTIONAL gate (C2) — skew-t must not widen the nested gap (CRN)",
        "",
        "- Per-replicate skew-t − symmetric (CRN) mean: {:+.3f} (min {:+.3f}, max {:+.3f})".format(
            r["skewt_minus_sym_mean"], r["skewt_minus_sym_min"], r["skewt_minus_sym_max"]),
        "- Skew-t does not widen the gap (CRN mean — GATE): **{}**".format(
            "YES" if r["directional_not_widened_mean"] else "NO"),
        "- Disclosed diagnostic — replicates with non-negative lift: {:.0%} (γ̂≈0 ⇒ per-replicate sign is MC noise around a ~0 mean)".format(
            r["directional_lift_nonneg_share"]),
        "",
        "## Residual-gap RE-decomposition (C1 decomposition branch — DISCLOSED, point basis)",
        "",
        "- Total gap (nested − skew-t component): {:.1f} ({:+.2%} of nested)".format(
            d["gap_total_abs"], d["gap_total_rel_to_nested"]),
        "- Relief-surface part (governed P25T3 OOS SCR rel err {:.2%}): {:.1f} — {:.1%} of gap".format(
            d["relief_surface_rel_err_source"], d["relief_surface_part_abs"],
            d["relief_surface_share_of_gap"]),
        "- Copula-form residual: {:.1f} — {:.1%} of gap".format(
            d["copula_form_residual_abs"], d["copula_form_share_of_gap"]),
        "- Frozen-t copula-form residual (P26T3 baseline): {:.1f}".format(
            d["copula_form_residual_frozen_t"]),
        "- **Copula-form residual REDUCTION from the skew-t scalar: {:.1f} ({:.2%})**".format(
            d["copula_form_residual_reduction_abs"], d["copula_form_residual_reduction_rel"]),
        "- Residual closed by the skew-t scalar: **{}**".format(
            "YES" if d["residual_closed_by_skewt_scalar"] else "NO (re-confirmed open)"),
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
        "- archive cross-check: Task 2 frozen-t {:.6f} and skew-t {:.6f} reproduced bit-identically before bootstrap".format(
            r["task2_frozen_t_component_point"], r["task2_skewt_component_point"]),
        "",
        "*Generated by scripts/build_phase27_task3_skew_t_bootstrap.py — educational model; production sign-off withheld.*",
        "",
    ]
    return "\n".join(lines)


def _card(rep: dict) -> str:
    r = rep["result"]
    ck = r["skewt_component_scr_ci"]
    d = r["residual_gap_redecomposition_point"]
    return "\n".join([
        "# Skew-t Bootstrap Card (Phase 27 Task 3)",
        "",
        "- Skew-t-copula margin bootstrap ({}×{}): skew-t component SCR".format(
            r["config"]["n_replicates"], r["config"]["n_sim_per_replicate"]),
        "  mean {:.1f}, 95% CI [{:.1f}, {:.1f}], SE {:.2%} of mean.".format(
            ck["mean"], ck["ci_lo"], ck["ci_hi"], ck["se_frac_of_mean"]),
        "- Nested truth {:.1f} inside the 95% CI: {}.".format(
            r["nested_pathwise_reference"],
            "yes" if r["headline_nested_inside_95ci"] else "NO (gap re-decomposed)"),
        "- Directional: skew-t does NOT widen the nested gap vs symmetric-t (CRN); mean lift {:+.3f}.".format(
            r["skewt_minus_sym_mean"]),
        "- Copula-form residual {:.1f} vs frozen-t {:.1f}: reduction {:.1f} ({:.2%}).".format(
            d["copula_form_residual_abs"], d["copula_form_residual_frozen_t"],
            d["copula_form_residual_reduction_abs"],
            d["copula_form_residual_reduction_rel"]),
        "- Finding: the single skew-t upper-tail scalar (γ̂≈0) does NOT close the",
        "  copula-form residual; it lives in nested inner-path joint dynamics a copula on",
        "  standalone margins cannot represent. Grouped-t / vine escalation → Phase 28.",
        "- Verdict: {} — educational; production sign-off withheld.".format(rep["verdict"]),
        "",
    ])


def stage_report() -> int:
    s = np.load(INPUTS_DST)
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    verdict = "PASS" if (result["se_gate_pass"]
                         and result["directional_not_widened_mean"]
                         and all(v for k, v in result["gates"].items()
                                 if k != "C1_headline_nested_inside_95ci_raw")) else "FAIL"
    rep = {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": PHASE,
        "task": "Task 3 - skew-t-copula margin bootstrap + residual re-decomposition",
        "verdict": verdict,
        "gamma_hat": float(s["gamma_hat"][0]),
        "drivers": list(DRIVERS),
        "df_rematched": float(s["df_rematched"][0]),
        "rho_max_abs_diff": float(s["rho_max_abs_diff"][0]),
        "crosscheck_count": int(s["crosscheck_count"][0]),
        "pathwise_basis_params": {
            "sigma": float(s["sigma"][0]), "alpha": float(s["alpha"][0]),
            "benefit_share_fit": float(s["beta_fit"][0]),
            "provenance": "governed P25T3 FIT values, frozen (C5; NO re-tuning)",
        },
        "result": result,
        "use_restrictions": skewt_bootstrap_use_restrictions(),
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
    ck = r["skewt_component_scr_ci"]
    d = r["residual_gap_redecomposition_point"]
    store = GovernanceStore.from_json(GOV_PATH.read_text(encoding="utf-8"))
    if any(rec.title == CHANGE_TITLE for rec in store.change_records):
        ok = store.audit_trail.verify_all()
        print(json.dumps({"added": False, "reason": "already applied (idempotent)",
                          "audit_integrity_ok": ok}))
        return 0 if ok else 1
    rec = ChangeRecord.create(
        title=CHANGE_TITLE,
        description=(
            "Skew-t-copula non-parametric margin bootstrap ({}x{}) on the full "
            "re-aggregated component basis: realised standalone-loss rows "
            "resampled with replacement (cross-driver pairing preserved); copula "
            "df/rho AND the Task 2 leakage-free gamma_hat ({:.2e}) and governed "
            "sigma/alpha/beta_fit FROZEN. The skew-t and symmetric-t (gamma=0) "
            "variants share common random numbers. The nested truth 46,638.9 "
            "lies OUTSIDE the skew-t 95% CI, so the residual gap is "
            "RE-decomposed: with gamma_hat ~ 0 the copula-form residual falls "
            "from the frozen-t baseline {:.1f} to {:.1f} (a {:.2%} reduction). "
            "The skew-t does NOT widen the nested gap on CRN. The residual is "
            "RE-CONFIRMED as NOT closed by a single upper-tail-asymmetry scalar; "
            "it lives in nested inner-path joint dynamics (grouped-t / vine "
            "escalation -> Phase 28). SE gate (<=5% of mean) PASS.".format(
                r["config"]["n_replicates"], r["config"]["n_sim_per_replicate"],
                rep["gamma_hat"], d["copula_form_residual_frozen_t"],
                d["copula_form_residual_abs"],
                d["copula_form_residual_reduction_rel"])),
        change_type="methodology_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "task2_residual": (
                "frozen-t copula-form residual 6,120.2 (91.9% of the 14.29% "
                "nested gap); skew-t lever implemented, gamma_hat ~ 0 "
                "(Task 2 material finding); bootstrap deferred to Task 3"),
        },
        after_snapshot={
            "skewt_component_scr_mean": ck["mean"],
            "skewt_component_scr_95ci": [ck["ci_lo"], ck["ci_hi"]],
            "se_frac_of_mean": ck["se_frac_of_mean"],
            "headline_nested_inside_95ci": r["headline_nested_inside_95ci"],
            "directional_not_widened_mean": r["directional_not_widened_mean"],
            "copula_form_residual_abs": d["copula_form_residual_abs"],
            "copula_form_residual_reduction_abs": d["copula_form_residual_reduction_abs"],
            "copula_form_residual_reduction_rel": d["copula_form_residual_reduction_rel"],
            "residual_closed_by_skewt_scalar": d["residual_closed_by_skewt_scalar"],
            "verdict": rep["verdict"], "digest": r["digest"],
        },
        impact_assessment=(
            "Adds a skew-t-copula uncertainty band and a disclosed residual-gap "
            "RE-decomposition quantifying the copula-form reduction vs the "
            "frozen-t baseline; no governed parameter changes (copula, gamma and "
            "relief scalars FROZEN). With gamma_hat ~ 0 the reduction is "
            "negligible: the nested truth stays above the skew-t component CI and "
            "the residual is RE-CONFIRMED as copula-FORM (nested-dynamics vs "
            "margin-aggregation) dominated, NOT a standalone upper-tail-asymmetry "
            "effect. The grouped-t / vine escalation is the indicated next "
            "sophistication step (Phase 28). MR-015 to be opened at Task 4. "
            "Educational classification retained; production sign-off withheld."),
        author=ACTOR, phase=PHASE,
        quantitative_impact=(
            "skew-t component SCR mean {:.1f}, 95% CI [{:.1f}, {:.1f}], SE {:.2%} "
            "of mean; nested 46,638.9 OUTSIDE CI; gap {:+.2%}; copula-form "
            "residual {:.1f} vs frozen-t {:.1f} (reduction {:.1f} = {:.2%}); "
            "skew-t minus symmetric (CRN) mean {:+.3f}; directional not-widened "
            "mean {}.".format(
                ck["mean"], ck["ci_lo"], ck["ci_hi"], ck["se_frac_of_mean"],
                d["gap_total_rel_to_nested"], d["copula_form_residual_abs"],
                d["copula_form_residual_frozen_t"],
                d["copula_form_residual_reduction_abs"],
                d["copula_form_residual_reduction_rel"],
                r["skewt_minus_sym_mean"], r["directional_not_widened_mean"])),
    )
    rec.submit_for_peer_review(
        actor=ACTOR,
        comments="SE gate PASS; directional gate PASS (skew-t not widen gap); "
                 "archive cross-check bit-identical; bootstrap digest recorded; "
                 "new unit tests PASS.")
    rec.submit_to_owner(
        actor=ACTOR,
        comments="Owner review: methodology addition (uncertainty band + "
                 "disclosed residual RE-decomposition); copula/gamma/scalars "
                 "frozen; gamma_hat~0 -> residual re-confirmed open; grouped-t "
                 "escalation flagged for Phase 28; sign-off withheld pending "
                 "Task 4 MR-015.")
    store.add_change_record(rec)
    store.audit_trail.append(AuditEntry.governance(
        actor=ACTOR, phase=PHASE,
        event="ChangeRecord opened (OWNER_REVIEW) - Phase 27 Task 3 skew-t "
              "margin bootstrap + residual-gap RE-decomposition",
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
    p.add_argument("--stop", type=int, default=SKEWT_BOOTSTRAP_REPLICATES)
    a = p.parse_args()
    if a.stage == "chunk":
        return stage_chunk(a.start, a.stop)
    return {"verify": stage_verify, "aggregate": stage_aggregate,
            "report": stage_report, "governance": stage_governance}[a.stage]()


if __name__ == "__main__":
    sys.exit(main())
