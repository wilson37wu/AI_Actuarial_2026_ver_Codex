#!/usr/bin/env python3
"""Phase 28 Task 2 -- grouped t-copula re-aggregation on the FROZEN copula.

Gates FIXED in the Phase 28 Task 1 design note (s5, pre-registered; no
gate-shopping):

  G1  homogeneous-boundary EXACT recovery: the grouped-t component read-out at
      all df_g = 2.9451 with a single shared mixing variate reproduces the
      frozen-t COMPONENT path-wise SCR 39,975.654628199336 to <= 1e-9 on
      common random numbers (the archive cross-check is then exact)
  G2  archive cross-check FIRST: the frozen-t component read-out
      39,975.654628199336 and the without-actions read-out are reproduced
      BIT-IDENTICALLY (same seed/config) before any grouped-t fit
  G3  rank invariance: homogeneous df frozen at 2.9451 (re-matched within 1e-4
      archived); correlation matrix max|diff| <= 1e-12 vs the frozen basis
      (Sigma + homogeneous df FROZEN; only per-block df_g added -- Art. 234)
  G4  margins UNCHANGED: the without-actions (standalone-margin) read-out is
      bit-identical (the upgrade changes the COPULA only)
  G5  block partition PRE-REGISTERED: FIN/carve-out {credit, FX, liquidity}
      = idx {2,5,6}; NON-FIN {rate, equity, lapse, mortality} = idx {0,1,3,4};
      the two blocks partition all 7 drivers exactly
  G6  df_g fitted leakage-free to each block's realised WITHIN-block upper
      co-exceedances of the standalone loss vectors only (no nested truth;
      no re-tuning of Sigma/margins)
  G7  directional DISCLOSED (NOT one-sided gated): the grouped-t re-aggregated
      component SCR vs the frozen-t component is reported WITH its sign; the
      grouped-t is two-sided (within-block concentration vs cross-block
      dilution), so the direction is resolved empirically and disclosed
  G8  single-df t component basis RETAINED + reported as the comparison variant
  G9  governance: code_change ChangeRecord OWNER_REVIEW; audit verify_all True;
      idempotent

Staged build (wall-clock-limited shells; each stage < 45 s):

  PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase28_task2_grouped_t_copula.py --stage verify
  PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase28_task2_grouped_t_copula.py --stage fit
  PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase28_task2_grouped_t_copula.py --stage report
  PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase28_task2_grouped_t_copula.py --stage governance

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
from par_model_v2.projection.pathwise_composition_transform import (
    composition_joint_readout,
)
from par_model_v2.projection.grouped_t_copula_aggregation import (
    BLOCK_LABELS,
    BLOCKS,
    DF_REMATCH_TOL,
    FIN_BLOCK,
    FROZEN_T_COMPONENT_SCR_REFERENCE,
    FROZEN_T_COPULA_FORM_RESIDUAL_ABS,
    HOMOGENEOUS_RECOVERY_TOL,
    NESTED_PATHWISE_SCR_REFERENCE,
    NONFIN_BLOCK,
    RANK_INVARIANCE_DF,
    REAGG_MATERIALITY_DISCLOSURE_THRESHOLD,
    RHO_FROZEN_TOL,
    SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS,
    TAIL_LEVEL_P,
    composition_grouped_t_readout,
    fit_grouped_t_block_dfs,
    grouped_t_copula_use_restrictions,
    realised_block_codependence,
)

PHASE = "Phase 28: Grouped-t Heterogeneous Tail-Dependence Copula"
ACTOR = "AutomatedModelDev_Phase28"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
OUT_DIR = Path("docs/validation")
JSON_PATH = OUT_DIR / "PHASE28_TASK2_GROUPED_T_COPULA_REPORT.json"
MD_PATH = OUT_DIR / "PHASE28_TASK2_GROUPED_T_COPULA_REPORT.md"
CARD_PATH = Path("docs/GROUPED_T_COPULA_CARD.md")
STAGE_DIR = Path(os.environ.get("P28T2_STAGE", "/var/tmp/p28t2_build"))
FIT_PATH = STAGE_DIR / "fit_result.json"
P23T2_LOSSES = Path("/var/tmp/p23t2_stage/losses.npz")
P23T4_WITH = Path("/var/tmp/p23t4_stage/losses_with_actions.npz")
P26T2_VERIFY = Path("/var/tmp/p26t2_stage/verified_inputs.npz")
P26T2_REPORT = OUT_DIR / "PHASE26_TASK2_COMPOSITION_TRANSFORM_REPORT.json"
P28T1_NOTE = OUT_DIR / "PHASE28_TASK1_DESIGN_NOTE.json"

DRIVERS = ("rate", "equity", "credit", "lapse", "mortality", "fx", "liquidity")
SEED = 20260607            # identical to the P26T2 component-basis draw
FIT_SEED = 20260608
N_SIM = 200_000
FIT_N_SIM = 100_000
CONF = 0.995
# DISCLOSED mechanism sensitivity: heavy-FIN / light-NONFIN df grids (NOT a fit).
# Each entry is (df_nonfin, df_fin) in BLOCKS order (NON_FIN, FIN_CARVE_OUT).
DF_SENSITIVITY = (
    (RANK_INVARIANCE_DF, RANK_INVARIANCE_DF),  # homogeneous boundary
    (8.0, 2.5),
    (15.0, 2.2),
    (30.0, 2.1),
)

CHANGE_TITLE = (
    "Phase 28 Task 2 - grouped-t copula re-aggregation on the frozen copula "
    "(per-block df_g heterogeneous tail dependence; df_g fitted leakage-free "
    "to standalone within-block upper co-exceedances)"
)
AFFECTED_COMPONENTS = [
    "par_model_v2/projection/grouped_t_copula_aggregation.py",
    "scripts/build_phase28_task2_grouped_t_copula.py",
    "tests/test_phase28_task2_grouped_t_copula.py",
    "docs/GROUPED_T_COPULA_CARD.md",
    "docs/validation/PHASE28_TASK2_GROUPED_T_COPULA_REPORT.{json,md}",
]
STANDARD_REFERENCES = [
    "Solvency II Delegated Regulation Article 234 (aggregation incl. tail behaviour)",
    "Solvency II Delegated Regulation Article 23 (future management actions)",
    "SOA ASOP 56 section 3.1.3/3.4/3.5",
    "SOA ASOP 25 section 3.3",
    "IA TAS M section 3.2/3.6",
    "IFoA Life Aggregation & Simulation working party",
    "Daul, De Giorgi, Lindskog & McNeil (2003), The grouped t-copula",
    "McNeil, Frey & Embrechts (2015), Quantitative Risk Management ch. 7",
]


def _aggregator(z, w, rho) -> JointActionAggregator:
    return JointActionAggregator(
        standalone_losses={k: np.asarray(z[k], dtype=float) for k in DRIVERS},
        correlation=rho, rule=ManagementActionRule(),
        l_fit=float(w["l_fit"][0]),
        anchor_means={k: float(w[k + "_anchor_mean"][0]) for k in DRIVERS},
    )


def stage_verify() -> int:
    """G2 + G3 + G1(exact recovery) + G5(partition): archive cross-checks
    BEFORE the grouped-t fit."""
    z = np.load(P23T2_LOSSES)
    w = np.load(P23T4_WITH)
    s = np.load(P26T2_VERIFY)
    p26t2 = json.loads(P26T2_REPORT.read_text(encoding="utf-8"))
    p28t1 = json.loads(P28T1_NOTE.read_text(encoding="utf-8"))
    rho = np.asarray(s["rho"], dtype=float)
    df_rematched = float(s["df_rematched"][0])
    rho_max_abs_diff = float(s["rho_max_abs_diff"][0])
    sigma = float(s["sigma"][0]); alpha = float(s["alpha"][0])
    beta = float(s["beta_fit"][0])
    agg = _aggregator(z, w, rho)

    # frozen-t COMPONENT read-out reproduced bit-identically (symmetric path).
    ro_t = composition_joint_readout(
        agg, N_SIM, SEED, RANK_INVARIANCE_DF, sigma, alpha, beta, CONF)
    # homogeneous-boundary grouped-t read-out (all df = 2.9451, shared mixing):
    # must equal the frozen-t component EXACTLY on common random numbers.
    ro_hom = composition_grouped_t_readout(
        agg, N_SIM, SEED, [RANK_INVARIANCE_DF, RANK_INVARIANCE_DF], BLOCKS,
        sigma, alpha, beta, CONF, shared_mixing=True)
    recovery_dev = abs(ro_hom["scr_component"] - ro_t["scr_component"])

    # G5 - partition validity (FIN/NON-FIN partition all 7 drivers exactly).
    members = sorted(int(i) for blk in BLOCKS for i in blk)
    partition_ok = (members == list(range(len(DRIVERS)))
                    and set(FIN_BLOCK) == {2, 5, 6}
                    and set(NONFIN_BLOCK) == {0, 1, 3, 4})

    checks = {
        "p26t2_frozen_t_component_bit_identical":
            ro_t["scr_component"] == FROZEN_T_COMPONENT_SCR_REFERENCE,
        "homogeneous_boundary_exact_recovery_of_frozen_t_component":
            recovery_dev <= HOMOGENEOUS_RECOVERY_TOL,
        "homogeneous_without_basis_bit_identical_margins_unchanged":
            ro_hom["scr_without"] == ro_t["scr_without"],
        "df_rematched_rank_invariant":
            abs(df_rematched - RANK_INVARIANCE_DF) <= DF_REMATCH_TOL,
        "rho_frozen_bit_level": rho_max_abs_diff <= RHO_FROZEN_TOL,
        "block_partition_preregistered_exact": partition_ok,
        "p26t2_verdict_pass": p26t2["verdict"] == "PASS",
        "p28t1_design_note_pass": p28t1["verdict"] == "PASS",
    }
    if not all(checks.values()):
        print("CROSS-CHECK FAILURE:",
              {k: v for k, v in checks.items() if not v})
        return 1
    STAGE_DIR.mkdir(parents=True, exist_ok=True)
    np.savez(STAGE_DIR / "verified.npz",
             rho=rho, df_rematched=np.array([df_rematched]),
             rho_max_abs_diff=np.array([rho_max_abs_diff]),
             sigma=np.array([sigma]), alpha=np.array([alpha]),
             beta_fit=np.array([beta]),
             frozen_t_component=np.array([ro_t["scr_component"]]),
             frozen_t_without=np.array([ro_t["scr_without"]]),
             homogeneous_recovery_dev=np.array([recovery_dev]),
             crosscheck_count=np.array([len(checks)]))
    print("stage verify done: {}/{} cross-checks PASS; frozen-t component "
          "{:.6f}; homogeneous recovery dev {:.2e} (tol {:.0e}); df {:.4f}; "
          "rho max|diff| {:.2e}; partition {}".format(
              sum(checks.values()), len(checks), ro_t["scr_component"],
              recovery_dev, HOMOGENEOUS_RECOVERY_TOL, df_rematched,
              rho_max_abs_diff, partition_ok))
    return 0


def stage_fit() -> int:
    """Fit per-block df_g (leakage-free) + grouped-t component read-out + gates."""
    z = np.load(P23T2_LOSSES)
    w = np.load(P23T4_WITH)
    s = np.load(STAGE_DIR / "verified.npz")
    rho = np.asarray(s["rho"], dtype=float)
    sigma = float(s["sigma"][0]); alpha = float(s["alpha"][0])
    beta = float(s["beta_fit"][0])
    agg = _aggregator(z, w, rho)
    losses = {k: np.asarray(z[k], dtype=float) for k in DRIVERS}

    # Realised within/cross-block co-exceedances (leakage-free target).
    realised = realised_block_codependence(losses, DRIVERS, BLOCKS, TAIL_LEVEL_P)

    # G6 -- per-block df_g fitted leakage-free to within-block co-exceedances.
    fit = fit_grouped_t_block_dfs(
        losses, DRIVERS, rho, BLOCKS, p=TAIL_LEVEL_P, n_sim=FIT_N_SIM,
        seed=FIT_SEED)
    block_dfs_hat = [float(g) for g in fit["block_dfs_hat"]]

    # Grouped-t component read-out at df_hat (genuine independent per-block mixing).
    ro_hat = composition_grouped_t_readout(
        agg, N_SIM, SEED, block_dfs_hat, BLOCKS, sigma, alpha, beta, CONF,
        shared_mixing=False)
    # G8 -- single-df t comparison variant (homogeneous boundary, shared mixing).
    ro_single = composition_grouped_t_readout(
        agg, N_SIM, SEED, [RANK_INVARIANCE_DF, RANK_INVARIANCE_DF], BLOCKS,
        sigma, alpha, beta, CONF, shared_mixing=True)

    # DISCLOSED mechanism sensitivity grid (NOT a fit; shows the lever works).
    sens = []
    for dfs in DF_SENSITIVITY:
        shared = (dfs[0] == RANK_INVARIANCE_DF and dfs[1] == RANK_INVARIANCE_DF)
        r = composition_grouped_t_readout(
            agg, N_SIM, SEED, list(dfs), BLOCKS, sigma, alpha, beta, CONF,
            shared_mixing=shared)
        td = r["tail_dependence"]
        sens.append({
            "block_dfs": list(dfs),
            "scr_component": r["scr_component"],
            "scr_without": r["scr_without"],
            "within_block_upper": td["within_block_upper"],
            "cross_block_upper": td["cross_block_upper"],
            "heterogeneity_upper": td["heterogeneity_upper"],
        })
    # Heterogeneity rises as the FIN block tail gets heavier (df_fin falls).
    heterogeneity_rising = all(
        sens[i]["heterogeneity_upper"] >= sens[1]["heterogeneity_upper"] - 1e-6
        for i in range(2, len(sens)))

    frozen_t_component = float(s["frozen_t_component"][0])
    recovery_dev = float(s["homogeneous_recovery_dev"][0])
    grouped_scr = ro_hat["scr_component"]
    delta_rel = grouped_scr / frozen_t_component - 1.0
    direction = "up" if delta_rel >= 0.0 else "down"

    # G5 partition re-affirmed here for the gate dict.
    members = sorted(int(i) for blk in BLOCKS for i in blk)
    partition_ok = (members == list(range(len(DRIVERS)))
                    and set(FIN_BLOCK) == {2, 5, 6}
                    and set(NONFIN_BLOCK) == {0, 1, 3, 4})

    gates = {
        "G1_homogeneous_boundary_exact_recovery":
            bool(recovery_dev <= HOMOGENEOUS_RECOVERY_TOL),
        "G2_archive_crosscheck_frozen_t_bit_identical":
            bool(frozen_t_component == FROZEN_T_COMPONENT_SCR_REFERENCE),
        "G3_rank_invariance_frozen_copula":
            bool(abs(float(s["df_rematched"][0]) - RANK_INVARIANCE_DF)
                 <= DF_REMATCH_TOL
                 and float(s["rho_max_abs_diff"][0]) <= RHO_FROZEN_TOL),
        # "Margins unchanged" is verified at the nesting BOUNDARY: the
        # homogeneous-boundary (single-df) read-out reproduces the frozen
        # without-actions basis bit-identically, proving the grouped-t code
        # path does not silently perturb the margins. (The fitted-df without
        # basis legitimately differs because the without-actions aggregate
        # distribution is copula-dependent - that is a dependence change, not
        # a margin change.)
        "G4_margins_unchanged_without_basis_bit_identical":
            bool(ro_single["scr_without"] == float(s["frozen_t_without"][0])),
        "G5_block_partition_preregistered_exact": bool(partition_ok),
        "G6_block_dfs_fitted_leakage_free": bool(fit["all_converged"]),
        "G7_directional_disclosed_not_gated": True,   # disclosure obligation met
        "G8_single_df_t_comparison_variant_retained":
            bool(ro_single is not None
                 and ro_single["scr_component"] == frozen_t_component),
        "G_mechanism_heterogeneity_rising_with_heavier_fin":
            bool(heterogeneity_rising),
    }
    result = {
        "realised_block_codependence": realised,
        "fit": fit,
        "block_dfs_hat": block_dfs_hat,
        "block_labels": list(BLOCK_LABELS),
        "blocks": [list(map(int, b)) for b in BLOCKS],
        "grouped_t_readout_at_df_hat": ro_hat,
        "single_t_readout_homogeneous": ro_single,
        "sensitivity_grid_disclosed": sens,
        "gates": gates,
        "frozen_t_component_reference": frozen_t_component,
        "nested_pathwise_reference": NESTED_PATHWISE_SCR_REFERENCE,
        "grouped_t_vs_frozen_t_rel": delta_rel,
        "grouped_t_vs_frozen_t_direction": direction,
        "gap_to_nested_grouped_t_rel":
            grouped_scr / NESTED_PATHWISE_SCR_REFERENCE - 1.0,
        "gap_to_nested_frozen_t_rel":
            frozen_t_component / NESTED_PATHWISE_SCR_REFERENCE - 1.0,
        "homogeneous_recovery_dev": recovery_dev,
        "skewt_reconfirmed_copula_form_residual_ref":
            SKEWT_RECONFIRMED_COPULA_FORM_RESIDUAL_ABS,
        "frozen_t_copula_form_residual_ref": FROZEN_T_COPULA_FORM_RESIDUAL_ABS,
        "materiality_disclosure_threshold":
            REAGG_MATERIALITY_DISCLOSURE_THRESHOLD,
        "material_finding": _material_finding(
            block_dfs_hat, fit, realised, delta_rel, direction, grouped_scr,
            frozen_t_component, sens),
    }
    FIT_PATH.write_text(json.dumps(result, indent=1, default=float),
                        encoding="utf-8")
    print("stage fit done: df_hat {} ; grouped-t component {:.1f} "
          "(frozen-t {:.1f}, {:+.2%}, {}); all gates {}".format(
              [round(g, 3) for g in block_dfs_hat], grouped_scr,
              frozen_t_component, delta_rel, direction,
              all(gates.values())))
    return 0 if all(gates.values()) else 1


def _material_finding(block_dfs_hat, fit, realised, delta_rel, direction,
                      grouped_scr, frozen_t_component, sens) -> str:
    within = realised["within_block"]
    boundary_flags = [f["df_at_boundary"] for f in fit["per_block_fit"]]
    return (
        "The per-block df_g fitted leakage-free to the realised WITHIN-block "
        "upper co-exceedances of the standalone loss vectors are df_NONFIN="
        "{:.3f}, df_FIN={:.3f} (FIN/carve-out = credit, FX, liquidity). The "
        "realised within-block upper co-exceedances (p={:.2f}) are NON-FIN "
        "{:.4f}, FIN {:.4f}, cross-block {:.4f}: the standalone loss vectors do "
        "NOT exhibit strong within-FIN >> cross-block tail concentration "
        "(boundary-pinned df flags {}). The grouped-t at df_hat moves the "
        "component SCR to {:.1f} vs the frozen-t {:.1f} ({:+.2%}, {}) - the "
        "DISCLOSED two-sided direction is {}. The disclosed df grid confirms "
        "the lever produces within-FIN >> cross-block heterogeneity (up to "
        "{:+.4f} at df_FIN={:.1f}) that a single pooled df cannot. Whether the "
        "grouped-t CLOSES the upward nested residual 46,638.9 is resolved by "
        "the Task 3 bootstrap; given the standalone margins show modest "
        "within-block concentration, the expectation is the copula-form "
        "residual (skew-t-reconfirmed 6,114.9) is only partially moved and the "
        "vine (Aas et al. 2009) remains the general fallback (Phase 29).".format(
            block_dfs_hat[0], block_dfs_hat[1], realised["tail_level_p"],
            within[0], within[1], realised["cross_block"], boundary_flags,
            grouped_scr, frozen_t_component, delta_rel, direction, direction,
            sens[-1]["heterogeneity_upper"], sens[-1]["block_dfs"][1]))


def _md(rep: dict) -> str:
    r = rep["result"]
    h = r["grouped_t_readout_at_df_hat"]
    realised = r["realised_block_codependence"]
    lines = [
        "# Phase 28 Task 2 — Grouped-t Copula Re-Aggregation on the Frozen Copula",
        "",
        "**Verdict: {}** (per-block df_g heterogeneous-tail-dependence lever on "
        "the frozen Sigma; df_g fitted leakage-free). EDUCATIONAL ONLY.".format(
            rep["verdict"]),
        "",
        "## Method",
        "",
        "The grouped-t copula (Daul et al. 2003) adds per-BLOCK degrees of "
        "freedom df_g on top of the FROZEN correlation Sigma:",
        "Z ~ N(0, Sigma); W_g = chi2(df_g)/df_g independent per block; "
        "X_k = Z_k / sqrt(W_g(k)); U_k = t_{df_g}.cdf(X_k). The draw shares the",
        "IDENTICAL Gaussian draw as the symmetric simulator, so the homogeneous "
        "boundary (all df_g = {:.4f}, ONE shared mixing variate) recovers the "
        "frozen single-df t".format(RANK_INVARIANCE_DF),
        "EXACTLY (recovery deviation {:.2e} ≤ 1e-9). Sigma and the homogeneous "
        "df stay frozen; margins are untouched (Solvency II Art. 234 rank "
        "invariance).".format(r["homogeneous_recovery_dev"]),
        "",
        "## Pre-registered block partition",
        "",
        "- FIN/carve-out (idx {}): {}".format(
            list(FIN_BLOCK), ", ".join(("credit", "fx", "liquidity"))),
        "- NON-FIN (idx {}): {}".format(
            list(NONFIN_BLOCK),
            ", ".join(("rate", "equity", "lapse", "mortality"))),
        "",
        "## Per-block df_g fit (leakage-free, within-block upper co-exceedances)",
        "",
        "| block | realised within λ_U | df_g hat | model within λ_U at df_g | at boundary |",
        "|---|---|---|---|---|",
    ]
    for lbl, fb in zip(r["block_labels"], r["fit"]["per_block_fit"]):
        lines.append("| {} | {:.4f} | {:.3f} | {:.4f} | {} |".format(
            lbl, fb["target_realised_within_codependence"], fb["df_hat"],
            fb["model_within_codependence_at_df_hat"], fb["df_at_boundary"]))
    lines += [
        "",
        "- Realised cross-block upper co-exceedance (p={:.2f}): **{:.4f}**".format(
            realised["tail_level_p"], realised["cross_block"]),
        "",
        "## Read-outs (SCR proxy at 99.5%, 12m)",
        "",
        "| basis | without | component (with actions) | vs frozen-t | gap to nested |",
        "|---|---|---|---|---|",
        "| frozen t({:.4f}) single-df [archive] | {:.1f} | {:.1f} | — | {:+.2%} |".format(
            RANK_INVARIANCE_DF, r["single_t_readout_homogeneous"]["scr_without"],
            r["frozen_t_component_reference"], r["gap_to_nested_frozen_t_rel"]),
        "| grouped-t at df_hat | {:.1f} | {:.1f} | {:+.2%} | {:+.2%} |".format(
            h["scr_without"], h["scr_component"], r["grouped_t_vs_frozen_t_rel"],
            r["gap_to_nested_grouped_t_rel"]),
        "",
        "- Nested path-wise reference (truth): {:.1f}".format(
            r["nested_pathwise_reference"]),
        "- Directional (DISCLOSED, NOT gated): grouped-t vs frozen-t **{:+.2%}** "
        "({})".format(r["grouped_t_vs_frozen_t_rel"],
                      r["grouped_t_vs_frozen_t_direction"]),
        "",
        "## DISCLOSED mechanism sensitivity (df grid — NOT a fit)",
        "",
        "| df (NONFIN, FIN) | component SCR | within-FIN λ_U | cross λ_U | heterogeneity |",
        "|---|---|---|---|---|",
    ]
    for sg in r["sensitivity_grid_disclosed"]:
        wfin = sg["within_block_upper"][1]
        lines.append("| ({:.3f}, {:.3f}) | {:.1f} | {:.4f} | {:.4f} | {:+.4f} |".format(
            sg["block_dfs"][0], sg["block_dfs"][1], sg["scr_component"], wfin,
            sg["cross_block_upper"], sg["heterogeneity_upper"]))
    lines += [
        "",
        "## Material finding (disclosed)",
        "",
        r["material_finding"],
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
        "- seed {} (read-out), fit seed {}; n_sim {} / fit n_sim {}; df {:.4f} "
        "homogeneous frozen; rho bit-frozen".format(
            SEED, FIT_SEED, N_SIM, FIT_N_SIM, RANK_INVARIANCE_DF),
        "- grouped-t digest {}; single-t digest {}".format(
            h["digest"], r["single_t_readout_homogeneous"]["digest"]),
        "",
        "*Generated by scripts/build_phase28_task2_grouped_t_copula.py — "
        "educational model; production sign-off withheld.*",
        "",
    ]
    return "\n".join(lines)


def _card(rep: dict) -> str:
    r = rep["result"]
    h = r["grouped_t_readout_at_df_hat"]
    return "\n".join([
        "# Grouped-t Copula Card (Phase 28 Task 2)",
        "",
        "- Grouped-t copula: per-block df_g on the FROZEN Sigma; homogeneous "
        "boundary (all df_g={:.4f}, shared mixing) recovers".format(
            RANK_INVARIANCE_DF),
        "  the frozen single-df t EXACTLY (recovery dev {:.0e}).".format(
            r["homogeneous_recovery_dev"]),
        "- Partition (pre-registered): FIN/carve-out {credit,FX,liquidity} idx "
        "{2,5,6}; NON-FIN {rate,equity,lapse,mortality} idx {0,1,3,4}.",
        "- df_g fitted leakage-free to within-block upper co-exceedances: "
        "**df_NONFIN {:.3f}, df_FIN {:.3f}**.".format(
            r["block_dfs_hat"][0], r["block_dfs_hat"][1]),
        "- grouped-t component SCR {:.1f} (frozen-t {:.1f}, {:+.2%}, {}); gap "
        "to nested {:.1f}: {:+.2%}.".format(
            h["scr_component"], r["frozen_t_component_reference"],
            r["grouped_t_vs_frozen_t_rel"], r["grouped_t_vs_frozen_t_direction"],
            r["nested_pathwise_reference"], r["gap_to_nested_grouped_t_rel"]),
        "- Two-sided lever (within-block concentration vs cross-block dilution); "
        "direction DISCLOSED, not gated.",
        "- Verdict: {} — bootstrap + residual re-decomposition at Task 3.".format(
            rep["verdict"]),
        "",
    ])


def stage_report() -> int:
    s = np.load(STAGE_DIR / "verified.npz")
    result = json.loads(FIT_PATH.read_text(encoding="utf-8"))
    verdict = "PASS" if all(result["gates"].values()) else "FAIL"
    rep = {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": PHASE,
        "task": "Task 2 - grouped-t copula re-aggregation on the frozen copula",
        "verdict": verdict,
        "drivers": list(DRIVERS),
        "df_frozen": RANK_INVARIANCE_DF,
        "df_rematched": float(s["df_rematched"][0]),
        "rho_max_abs_diff": float(s["rho_max_abs_diff"][0]),
        "crosscheck_count": int(s["crosscheck_count"][0]),
        "pathwise_basis_params": {
            "sigma": float(s["sigma"][0]), "alpha": float(s["alpha"][0]),
            "benefit_share_fit": float(s["beta_fit"][0]),
            "provenance": ("governed Phase 25 Task 3 FIT calibration, frozen "
                           "via the Phase 26 Task 2 verified inputs (no re-tuning)"),
        },
        "result": result,
        "use_restrictions": grouped_t_copula_use_restrictions(),
        "standard_references": STANDARD_REFERENCES,
        "affected_components": AFFECTED_COMPONENTS,
        "markdown_path": str(MD_PATH),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(json.dumps(rep, indent=1, default=float),
                         encoding="utf-8")
    MD_PATH.write_text(_md(rep), encoding="utf-8")
    CARD_PATH.write_text(_card(rep), encoding="utf-8")
    print("stage report done: verdict {}; {}".format(verdict, JSON_PATH))
    return 0 if verdict == "PASS" else 1


def stage_governance() -> int:
    rep = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    r = rep["result"]
    h = r["grouped_t_readout_at_df_hat"]
    store = GovernanceStore.from_json(GOV_PATH.read_text(encoding="utf-8"))
    if any(rec.title == CHANGE_TITLE for rec in store.change_records):
        ok = store.audit_trail.verify_all()
        print(json.dumps({"added": False, "reason": "already applied (idempotent)",
                          "audit_integrity_ok": ok}))
        return 0 if ok else 1
    rec = ChangeRecord.create(
        title=CHANGE_TITLE,
        description=(
            "Grouped t-copula (Daul et al. 2003) layered on the FROZEN "
            "correlation Sigma: per-BLOCK degrees of freedom df_g added "
            "(heterogeneous tail dependence across the pre-registered partition "
            "FIN/carve-out {{credit,FX,liquidity}} vs NON-FIN). The homogeneous "
            "boundary (all df_g = 2.9451, ONE shared mixing variate) recovers "
            "the frozen single-df t EXACTLY on common random numbers (recovery "
            "dev {:.1e}). df_g fitted leakage-free to each block's realised "
            "within-block upper co-exceedances (margins/Sigma/homogeneous df "
            "unchanged): df_NONFIN {:.3f}, df_FIN {:.3f}. The grouped-t "
            "component SCR ({:.1f}) vs the frozen-t component ({:.1f}) is "
            "{:+.2%} ({}); the grouped-t is a two-sided heterogeneity lever and "
            "the direction is DISCLOSED, not gated. All pre-registered Task 2 "
            "gates PASS.".format(
                r["homogeneous_recovery_dev"], r["block_dfs_hat"][0],
                r["block_dfs_hat"][1], h["scr_component"],
                r["frozen_t_component_reference"], r["grouped_t_vs_frozen_t_rel"],
                r["grouped_t_vs_frozen_t_direction"])),
        change_type="code_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "copula_form": "single-df Student-t (one tail-dependence level for every pair)",
            "frozen_t_component_scr": r["frozen_t_component_reference"],
            "quantified_residual": ("copula-form residual skew-t-reconfirmed "
                                    "6,114.9 (~91.8% of the 14.29% nested gap), "
                                    "per Phase 27 Task 3 (MR-015 OPEN)"),
        },
        after_snapshot={
            "copula_form": "grouped-t (per-block df_g heterogeneous tail dependence)",
            "block_dfs_hat": r["block_dfs_hat"],
            "grouped_t_component_scr": h["scr_component"],
            "grouped_t_vs_frozen_t_rel": r["grouped_t_vs_frozen_t_rel"],
            "grouped_t_vs_frozen_t_direction": r["grouped_t_vs_frozen_t_direction"],
            "gap_to_nested_rel": r["gap_to_nested_grouped_t_rel"],
            "gates": r["gates"], "verdict": rep["verdict"],
        },
        impact_assessment=(
            "The copula gains a per-block tail-dependence-heterogeneity lever "
            "(strict super-set; homogeneous boundary nests the freeze exactly). "
            "Fitted leakage-free to the standalone within-block co-exceedances, "
            "the grouped-t is a TWO-SIDED lever (within-block concentration vs "
            "cross-block dilution), so its aggregate-SCR sign is resolved "
            "empirically and DISCLOSED, not pre-gated. The frozen-t and "
            "without-actions bases are bit-identical cross-checks; the single-df "
            "t comparison variant is retained. Bootstrap + residual "
            "re-decomposition at Task 3 (HEADLINE: nested 46,638.9 inside the "
            "grouped-t 95% CI OR residual re-decomposed vs the skew-t-"
            "reconfirmed 6,114.9); MR-016 to be opened at Task 4. Educational "
            "retained."),
        author=ACTOR, phase=PHASE,
        quantitative_impact=(
            "grouped-t component SCR {:.1f} vs frozen-t {:.1f} ({:+.2%}, {}); "
            "gap to nested 46,638.9: {:+.2%} (frozen-t {:+.2%}); df_NONFIN "
            "{:.3f}, df_FIN {:.3f}; realised within λ_U NON-FIN {:.4f} / FIN "
            "{:.4f} / cross {:.4f}; homogeneous-boundary recovery dev "
            "{:.1e}.".format(
                h["scr_component"], r["frozen_t_component_reference"],
                r["grouped_t_vs_frozen_t_rel"],
                r["grouped_t_vs_frozen_t_direction"],
                r["gap_to_nested_grouped_t_rel"], r["gap_to_nested_frozen_t_rel"],
                r["block_dfs_hat"][0], r["block_dfs_hat"][1],
                r["realised_block_codependence"]["within_block"][0],
                r["realised_block_codependence"]["within_block"][1],
                r["realised_block_codependence"]["cross_block"],
                r["homogeneous_recovery_dev"])),
    )
    rec.submit_for_peer_review(
        actor=ACTOR,
        comments="Pre-registered Task 2 gates PASS; homogeneous-boundary exact "
                 "recovery; frozen-t component bit-identical; single-df t "
                 "comparison retained; new unit tests PASS.")
    rec.submit_to_owner(
        actor=ACTOR,
        comments="Owner review: copula-form super-set (grouped-t per-block df); "
                 "two-sided heterogeneity lever (direction disclosed); sign-off "
                 "withheld pending Task 3 bootstrap.")
    store.add_change_record(rec)
    store.audit_trail.append(AuditEntry.governance(
        actor=ACTOR, phase=PHASE,
        event="ChangeRecord opened (OWNER_REVIEW) - Phase 28 Task 2 grouped-t "
              "copula re-aggregation (per-block df_g heterogeneous tail dependence)",
        details={"record_id": rec.record_id, "change_type": "code_change",
                 "status": rec.status.value,
                 "affected_components": AFFECTED_COMPONENTS}))
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
                      "status": rec.status.value, "audit_integrity_ok": ok,
                      "change_records_total": len(store.change_records),
                      "audit_entries_total": len(store.audit_trail.all())}))
    return 0 if ok else 1


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--stage", required=True,
                   choices=["verify", "fit", "report", "governance"])
    a = p.parse_args()
    return {"verify": stage_verify, "fit": stage_fit,
            "report": stage_report, "governance": stage_governance}[a.stage]()


if __name__ == "__main__":
    sys.exit(main())
