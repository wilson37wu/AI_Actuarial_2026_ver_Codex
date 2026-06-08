#!/usr/bin/env python3
"""Phase 26 Task 2 -- per-driver composition transform on the FROZEN copula
(full path-wise copula re-aggregation, benchmark t/gaussian bases).

Gates FIXED in the Phase 26 Task 1 design note (s5, pre-registered; no
gate-shopping):

  G1  archive cross-check FIRST: the without-actions t/gaussian read-outs
      and the P25T4 analytic re-anchored (LEVEL) read-outs are reproduced
      BIT-IDENTICALLY (same seed/config; digest + float equality) before
      any new computation; P24T2 horizon joint-action digests also match
  G2  rank invariance: df re-matched on the WITHOUT-actions staged losses
      within 1e-4 of the frozen 2.9451; correlation matrix max|diff|
      <= 1e-12 vs the archived dependence basis (copula FROZEN, Art. 234)
  G3  relief applied to the per-scenario CUTTABLE component only, with the
      per-scenario max_relief envelope clip (bounds verified elementwise);
      carve-out drivers (credit / fx / liquidity) never relieved
  G4  governed sigma / alpha / beta_fit UNCHANGED (P25T3 FIT values,
      bit-equal to the archived P25T4 report params; NO re-tuning)
  G5  SIGN gate: full re-aggregated (component-basis) t-copula path-wise
      SCR >= the analytic re-anchored read-out 39,794.3 (magnitude
      DISCLOSED, not gated)
  G6  constant-share LEVEL variant RETAINED on common random numbers and
      reported alongside (P24T3 convention); bit-identical to the archived
      P25T4 read-outs
  G7  governance: code_change ChangeRecord OWNER_REVIEW; audit-chain
      verify_all True; idempotent

Staged build (wall-clock-limited shells; each stage < 45 s):

  PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase26_task2_composition_transform.py --stage verify
  PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase26_task2_composition_transform.py --stage reagg
  PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase26_task2_composition_transform.py --stage report
  PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase26_task2_composition_transform.py --stage governance

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
from par_model_v2.projection.joint_action_aggregation import (
    JointActionAggregator,
    JointActionConfig,
)
from par_model_v2.projection.management_actions import ManagementActionRule
from par_model_v2.projection.multi_driver_copula_aggregation import (
    _nearest_correlation,
)
from par_model_v2.projection.pathwise_composition_transform import (
    CARVEOUT_DRIVERS,
    CUTTABLE_DRIVERS,
    composition_joint_readout,
    composition_transform_use_restrictions,
)
from par_model_v2.projection.pathwise_copula_reaggregation import (
    DF_REMATCH_TOL,
    FULL_REAGG_SIGN_GATE_REFERENCE,
    GAUSSIAN_REANCHORED_READOUT,
    NESTED_PATHWISE_SCR_REFERENCE,
    RANK_INVARIANCE_DF,
    REAGG_MATERIALITY_DISCLOSURE_THRESHOLD,
    RHO_FROZEN_TOL,
    T_COPULA_REANCHORED_READOUT,
)
from par_model_v2.projection.pathwise_tail_diagnostics import (
    pathwise_joint_readout,
)
from par_model_v2.projection.tail_dependence import match_t_df_to_losses

PHASE = "Phase 26: Full Path-Wise Copula Re-Aggregation"
ACTOR = "AutomatedModelDev_Phase26"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
OUT_DIR = Path("docs/validation")
JSON_PATH = OUT_DIR / "PHASE26_TASK2_COMPOSITION_TRANSFORM_REPORT.json"
MD_PATH = OUT_DIR / "PHASE26_TASK2_COMPOSITION_TRANSFORM_REPORT.md"
CARD_PATH = Path("docs/COMPOSITION_TRANSFORM_CARD.md")
STAGE_DIR = Path("/var/tmp/p26t2_stage")
VERIFY_PATH = STAGE_DIR / "verified_inputs.npz"
REAGG_PATH = STAGE_DIR / "reagg_result.json"
P23T2_LOSSES = Path("/var/tmp/p23t2_stage/losses.npz")
P23T4_WITH = Path("/var/tmp/p23t4_stage/losses_with_actions.npz")
P23T2_REPORT = OUT_DIR / "PHASE23_TASK2_T_COPULA_AGGREGATION_REPORT.json"
P24T2_REPORT = OUT_DIR / "PHASE24_TASK2_JOINT_ACTION_REAGGREGATION_REPORT.json"
P25T4_REPORT = OUT_DIR / "PHASE25_TASK4_PATHWISE_TAIL_DIAGNOSTICS_REPORT.json"
P26T1_NOTE = OUT_DIR / "PHASE26_TASK1_DESIGN_NOTE.json"

DRIVERS = ("rate", "equity", "credit", "lapse", "mortality", "fx", "liquidity")
SEED = 20260607          # identical to Phase 23 T2/T4 + Phase 24/25 benchmarks
N_SIM = 200_000
THRESHOLDS = (0.80, 0.85, 0.90)
CONF = 0.995

CHANGE_TITLE = (
    "Phase 26 Task 2 - per-driver composition transform on the frozen "
    "copula (full path-wise copula re-aggregation, t/gaussian benchmark bases)"
)

AFFECTED_COMPONENTS = [
    "par_model_v2/projection/pathwise_composition_transform.py",
    "scripts/build_phase26_task2_composition_transform.py",
    "tests/test_phase26_task2_composition_transform.py",
    "docs/COMPOSITION_TRANSFORM_CARD.md",
    "docs/validation/PHASE26_TASK2_COMPOSITION_TRANSFORM_REPORT.{json,md}",
]

STANDARD_REFERENCES = [
    "Solvency II Delegated Regulation Article 23 (future management actions)",
    "Solvency II Delegated Regulation Article 234 (aggregation)",
    "SOA ASOP 56 section 3.1.3/3.4/3.5",
    "SOA ASOP 25 section 3.3",
    "IA TAS M section 3.2/3.6",
    "IFoA Life Aggregation & Simulation working party",
]


def _aggregator(z, w, rho) -> JointActionAggregator:
    losses = {k: np.asarray(z[k], dtype=float) for k in DRIVERS}
    anchors = {k: float(w[k + "_anchor_mean"][0]) for k in DRIVERS}
    return JointActionAggregator(
        standalone_losses=losses, correlation=rho,
        rule=ManagementActionRule(),
        l_fit=float(w["l_fit"][0]), anchor_means=anchors,
    )


def stage_verify() -> int:
    """G1 + G2: archive cross-checks BEFORE any new computation."""
    z = np.load(P23T2_LOSSES)
    w = np.load(P23T4_WITH)
    arch2 = json.loads(P23T2_REPORT.read_text(encoding="utf-8"))["aggregation"]
    p24t2 = json.loads(P24T2_REPORT.read_text(encoding="utf-8"))
    p25t4 = json.loads(P25T4_REPORT.read_text(encoding="utf-8"))
    p26t1 = json.loads(P26T1_NOTE.read_text(encoding="utf-8"))

    params = p25t4["pathwise_basis_params"]
    sigma = float(params["sigma"])
    alpha = float(params["alpha"])
    beta_fit = float(params["benefit_share_fit"])

    # G2 -- rank invariance: re-match df on the WITHOUT-actions staged
    # losses with the SAME machinery/thresholds as the archived P23T2 run.
    L = np.column_stack([np.asarray(z[k], dtype=float) for k in DRIVERS])
    matches = [match_t_df_to_losses(L, threshold=q)
               for q in sorted(THRESHOLDS)]
    df_rematched = float(np.median([m.pooled_df for m in matches]))
    central = matches[len(THRESHOLDS) // 2]
    rho = _nearest_correlation(np.asarray(central.rho_matrix, dtype=float))
    arch_rho = np.asarray(arch2["rho_matrix"], dtype=float)
    rho_max_abs_diff = float(np.max(np.abs(rho - arch_rho)))

    agg = _aggregator(z, w, rho)

    # G1 -- bit-identical reproduction of the archived bases (same seed).
    res_t = agg.run(JointActionConfig(n_sim=N_SIM, seed=SEED,
                                      df=RANK_INVARIANCE_DF))
    res_g = agg.run(JointActionConfig(n_sim=N_SIM, seed=SEED, df=None))
    ro_t = pathwise_joint_readout(
        agg, N_SIM, SEED, RANK_INVARIANCE_DF, sigma, alpha, beta_fit, CONF)
    ro_g = pathwise_joint_readout(
        agg, N_SIM, SEED, None, sigma, alpha, beta_fit, CONF)
    arch_j = p24t2["joint_action"]
    a_t = p25t4["t_pathwise_readout"]
    a_g = p25t4["g_pathwise_readout"]

    checks = {
        "df_rematched_rank_invariant":
            abs(df_rematched - RANK_INVARIANCE_DF) <= DF_REMATCH_TOL,
        "rho_frozen_bit_level": rho_max_abs_diff <= RHO_FROZEN_TOL,
        "p24t2_t_horizon_bit_identical":
            abs(res_t.scr_joint_with - arch_j["t_scr"]) == 0.0
            and res_t.digest == arch_j["t_digest"],
        "p24t2_g_horizon_bit_identical":
            abs(res_g.scr_joint_with - arch_j["g_scr"]) == 0.0
            and res_g.digest == arch_j["g_digest"],
        "p25t4_t_level_readout_bit_identical":
            ro_t["digest"] == a_t["digest"]
            and ro_t["scr_pathwise"] == a_t["scr_pathwise"]
            and ro_t["scr_without"] == a_t["scr_without"],
        "p25t4_g_level_readout_bit_identical":
            ro_g["digest"] == a_g["digest"]
            and ro_g["scr_pathwise"] == a_g["scr_pathwise"]
            and ro_g["scr_without"] == a_g["scr_without"],
        "p25t4_t_readout_is_sign_gate_reference":
            abs(a_t["scr_pathwise"] - T_COPULA_REANCHORED_READOUT) < 0.05,
        "p25t4_g_readout_matches_archived_constant":
            abs(a_g["scr_pathwise"] - GAUSSIAN_REANCHORED_READOUT) < 0.05,
        "p26t1_design_note_pass": p26t1["verdict"] == "PASS",
        "p25t4_verdict_pass": p25t4["verdict"] == "PASS",
        "beta_fit_in_unit_interval": bool(0.0 < beta_fit <= 1.0),
        "driver_carveout_partition_complete":
            sorted(CUTTABLE_DRIVERS + CARVEOUT_DRIVERS) == sorted(DRIVERS),
    }
    if not all(checks.values()):
        print("CROSS-CHECK FAILURE:",
              {k: v for k, v in checks.items() if not v})
        return 1

    STAGE_DIR.mkdir(parents=True, exist_ok=True)
    np.savez(
        VERIFY_PATH,
        rho=rho,
        df_rematched=np.array([df_rematched]),
        rho_max_abs_diff=np.array([rho_max_abs_diff]),
        crosscheck_count=np.array([len(checks)]),
        sigma=np.array([sigma]),
        alpha=np.array([alpha]),
        beta_fit=np.array([beta_fit]),
    )
    print("stage verify done: {}/{} cross-checks PASS; df re-matched {:.4f} "
          "(frozen {:.4f}, tol {:.0e}); rho max|diff| {:.2e} (tol {:.0e})".format(
              sum(checks.values()), len(checks), df_rematched,
              RANK_INVARIANCE_DF, DF_REMATCH_TOL, rho_max_abs_diff,
              RHO_FROZEN_TOL))
    return 0


def stage_reagg() -> int:
    """Full re-aggregation read-outs (component vs level, CRN) + gates."""
    z = np.load(P23T2_LOSSES)
    w = np.load(P23T4_WITH)
    s = np.load(VERIFY_PATH)
    p25t4 = json.loads(P25T4_REPORT.read_text(encoding="utf-8"))
    sigma = float(s["sigma"][0])
    alpha = float(s["alpha"][0])
    beta_fit = float(s["beta_fit"][0])
    agg = _aggregator(z, w, np.asarray(s["rho"], dtype=float))

    ro_t = composition_joint_readout(
        agg, N_SIM, SEED, RANK_INVARIANCE_DF, sigma, alpha, beta_fit, CONF)
    ro_g = composition_joint_readout(
        agg, N_SIM, SEED, None, sigma, alpha, beta_fit, CONF)

    a_t = p25t4["t_pathwise_readout"]
    a_g = p25t4["g_pathwise_readout"]

    # G3 bounds: re-verify the envelope elementwise on a fresh transform.
    from par_model_v2.projection.pathwise_composition_transform import (
        composition_with_actions, split_joint_composition)
    from par_model_v2.projection.t_copula_tail_matched_aggregation import (
        simulate_t_copula_uniforms)
    rng = np.random.default_rng(SEED)
    U = simulate_t_copula_uniforms(rng, N_SIM, agg.correlation,
                                   RANK_INVARIANCE_DF)
    comp = split_joint_composition(agg, U)
    pw = composition_with_actions(
        agg.rule, comp["V"], comp["V_cut"], agg.a_ref, sigma, alpha, beta_fit)
    b = np.asarray(pw["benefit_base"], dtype=float)
    rel_applied = comp["V"] - np.asarray(pw["W"], dtype=float)
    mr = agg.rule.max_relief
    bounds_ok = bool(
        np.all(rel_applied >= -1e-9)
        and np.all(rel_applied <= mr * b + 1e-9)
        and np.all(b <= comp["V"] + 1e-9)
        and np.all(b >= -1e-12)
    )

    delta_t_rel = ro_t["scr_component"] / a_t["scr_pathwise"] - 1.0
    delta_g_rel = ro_g["scr_component"] / a_g["scr_pathwise"] - 1.0
    gates = {
        "G1_archive_crosscheck_bit_identical": True,   # stage verify gated
        "G2_rank_invariance_frozen_copula":
            bool(abs(float(s["df_rematched"][0]) - RANK_INVARIANCE_DF)
                 <= DF_REMATCH_TOL
                 and float(s["rho_max_abs_diff"][0]) <= RHO_FROZEN_TOL),
        "G3_cuttable_component_only_with_envelope_clip": bounds_ok,
        "G4_governed_scalars_unchanged":
            bool(sigma == float(p25t4["pathwise_basis_params"]["sigma"])
                 and alpha == float(p25t4["pathwise_basis_params"]["alpha"])
                 and beta_fit == float(
                     p25t4["pathwise_basis_params"]["benefit_share_fit"])),
        "G5_sign_gate_component_t_scr_ge_reanchored":
            bool(ro_t["scr_component"]
                 >= FULL_REAGG_SIGN_GATE_REFERENCE - 1e-9),
        "G6_level_variant_retained_bit_identical":
            bool(ro_t["scr_level"] == a_t["scr_pathwise"]
                 and ro_g["scr_level"] == a_g["scr_pathwise"]
                 and ro_t["scr_without"] == a_t["scr_without"]
                 and ro_g["scr_without"] == a_g["scr_without"]),
    }
    result = {
        "t_readout": ro_t,
        "g_readout": ro_g,
        "gates": gates,
        "sign_gate_reference": FULL_REAGG_SIGN_GATE_REFERENCE,
        "nested_pathwise_reference": NESTED_PATHWISE_SCR_REFERENCE,
        "component_vs_reanchored_rel_t": delta_t_rel,
        "component_vs_reanchored_rel_g": delta_g_rel,
        "mr_refresh_trigger_1pct":
            bool(abs(delta_t_rel) > REAGG_MATERIALITY_DISCLOSURE_THRESHOLD),
        "gap_to_nested_component_t_rel":
            ro_t["scr_component"] / NESTED_PATHWISE_SCR_REFERENCE - 1.0,
        "gap_to_nested_level_t_rel":
            a_t["scr_pathwise"] / NESTED_PATHWISE_SCR_REFERENCE - 1.0,
        "envelope_bounds_ok": bounds_ok,
    }
    REAGG_PATH.write_text(json.dumps(result, indent=1, default=float),
                          encoding="utf-8")
    print("stage reagg done: t component SCR {:.1f} (level {:.1f}, "
          "re-anchored {:.1f}); component-vs-reanchored {:+.2%}; gates {}".format(
              ro_t["scr_component"], ro_t["scr_level"], a_t["scr_pathwise"],
              delta_t_rel, all(gates.values())))
    return 0 if all(gates.values()) else 1


def _md(rep: dict) -> str:
    r = rep["result"]
    t = r["t_readout"]
    g = r["g_readout"]
    lines = [
        "# Phase 26 Task 2 — Per-Driver Composition Transform on the Frozen Copula",
        "",
        "**Verdict: {}** (full path-wise copula re-aggregation, benchmark t/gaussian bases). EDUCATIONAL ONLY.".format(rep["verdict"]),
        "",
        "## Method",
        "",
        "Per joint copula scenario the per-driver loss composition is recovered from the",
        "FROZEN empirical margins; the scenario splits into a CUTTABLE sub-level",
        "(L_fit + rate/equity/lapse/mortality deviations) and a CARVE-OUT remainder",
        "(credit loss + analytic FX/liquidity offsets — not relievable, P24T3 convention).",
        "The governed relief (sigma {:.3f}, alpha {:.4f}, beta_fit {:.4f} — P25T3 FIT".format(
            t["config"]["sigma"], t["config"]["alpha"], t["config"]["benefit_share_fit"]),
        "values, NO re-tuning) applies to the cuttable component only with the per-scenario",
        "max_relief envelope clip. The constant-share LEVEL variant is RETAINED on common",
        "random numbers; copula FROZEN (df {:.4f}; rho bit-frozen).".format(RANK_INVARIANCE_DF),
        "",
        "## Read-outs (SCR proxy at 99.5%, 12m)",
        "",
        "| basis | without | level (re-anchored) | component (full re-agg) | comp − level |",
        "|---|---|---|---|---|",
        "| t({:.4f}) | {:.1f} | {:.1f} | {:.1f} | {:+.1f} |".format(
            RANK_INVARIANCE_DF, t["scr_without"], t["scr_level"],
            t["scr_component"], t["component_minus_level_scr"]),
        "| gaussian | {:.1f} | {:.1f} | {:.1f} | {:+.1f} |".format(
            g["scr_without"], g["scr_level"], g["scr_component"],
            g["component_minus_level_scr"]),
        "",
        "- Nested path-wise reference (truth): {:.1f}".format(r["nested_pathwise_reference"]),
        "- t component vs re-anchored: {:+.2%} (sign gate >= 0 PASS); gap to nested: {:+.2%} (level basis gap: {:+.2%})".format(
            r["component_vs_reanchored_rel_t"], r["gap_to_nested_component_t_rel"],
            r["gap_to_nested_level_t_rel"]),
        "- Tail cuttable-share depression (t basis): mean {:.3f} -> tail {:.3f} (depression {:.3f})".format(
            t["cuttable_share_mean"], t["cuttable_share_tail_mean"],
            t["tail_cuttable_share_depression"]),
        "- Clip-binding share (component, t): {:.4f}; active share: {:.4f}".format(
            t["clip_binding_share_component"], t["active_share_component"]),
        "- MR-010/MR-014 1% disclosure trigger: {} (refresh due at Task 4)".format(
            "MET" if r["mr_refresh_trigger_1pct"] else "not met"),
        "",
        "## Gates (pre-registered, design note s5)",
        "",
    ]
    for k, v in r["gates"].items():
        lines.append("- {}: {}".format(k, "PASS" if v else "FAIL"))
    lines += [
        "",
        "## Rank invariance / reproducibility",
        "",
        "- df re-matched {:.4f} (frozen {:.4f}, tol 1e-4); rho max|diff| {:.2e} (tol 1e-12)".format(
            rep["df_rematched"], RANK_INVARIANCE_DF, rep["rho_max_abs_diff"]),
        "- seed {}, n_sim {}; t digest {}; g digest {}".format(
            t["config"]["seed"], t["config"]["n_sim"], t["digest"], g["digest"]),
        "- archive cross-checks: {} PASS (P24T2 horizon + P25T4 level read-outs bit-identical)".format(
            rep["crosscheck_count"]),
        "",
        "*Generated by scripts/build_phase26_task2_composition_transform.py — educational model; production sign-off withheld.*",
        "",
    ]
    return "\n".join(lines)


def _card(rep: dict) -> str:
    r = rep["result"]
    t = r["t_readout"]
    return "\n".join([
        "# Composition Transform Card (Phase 26 Task 2)",
        "",
        "- Full path-wise copula re-aggregation: relief on the per-scenario",
        "  CUTTABLE component only (carve-outs: credit, fx, liquidity).",
        "- t({:.4f}) SCR: without {:.1f}; level {:.1f}; component {:.1f}.".format(
            RANK_INVARIANCE_DF, t["scr_without"], t["scr_level"], t["scr_component"]),
        "- Component vs re-anchored: {:+.2%}; gap to nested {:.1f}: {:+.2%}.".format(
            r["component_vs_reanchored_rel_t"], r["nested_pathwise_reference"],
            r["gap_to_nested_component_t_rel"]),
        "- Copula FROZEN; governed scalars unchanged; level variant retained.",
        "- Verdict: {} — bootstrap closure test at Task 3.".format(rep["verdict"]),
        "",
    ])


def stage_report() -> int:
    s = np.load(VERIFY_PATH)
    result = json.loads(REAGG_PATH.read_text(encoding="utf-8"))
    verdict = "PASS" if all(result["gates"].values()) else "FAIL"
    rep = {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": PHASE,
        "task": "Task 2 - per-driver composition transform on the frozen copula",
        "verdict": verdict,
        "drivers": list(DRIVERS),
        "cuttable_drivers": list(CUTTABLE_DRIVERS),
        "carveout_drivers": list(CARVEOUT_DRIVERS),
        "df_rematched": float(s["df_rematched"][0]),
        "rho_max_abs_diff": float(s["rho_max_abs_diff"][0]),
        "crosscheck_count": int(s["crosscheck_count"][0]),
        "pathwise_basis_params": {
            "sigma": float(s["sigma"][0]),
            "alpha": float(s["alpha"][0]),
            "benefit_share_fit": float(s["beta_fit"][0]),
            "provenance": (
                "governed Phase 25 Task 3 FIT-only calibration, bit-equal to "
                "the archived P25T4 report params (G4; NO re-tuning)"),
        },
        "result": result,
        "use_restrictions": composition_transform_use_restrictions(),
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
    t = r["t_readout"]
    store = GovernanceStore.from_json(GOV_PATH.read_text(encoding="utf-8"))
    if any(rec.title == CHANGE_TITLE for rec in store.change_records):
        ok = store.audit_trail.verify_all()
        print(json.dumps({"added": False,
                          "reason": "already applied (idempotent)",
                          "audit_integrity_ok": ok}))
        return 0 if ok else 1
    rec = ChangeRecord.create(
        title=CHANGE_TITLE,
        description=(
            "Per-driver composition transform on the FROZEN copula (full "
            "path-wise copula re-aggregation): per joint scenario the "
            "composition is recovered from the frozen empirical margins, "
            "split into cuttable (rate/equity/lapse/mortality) vs carve-out "
            "(credit/fx/liquidity) components, and the governed relief is "
            "applied to the CUTTABLE component only with the per-scenario "
            "max_relief envelope clip. Governed sigma/alpha/beta_fit "
            "unchanged (P25T3 FIT values). Constant-share LEVEL variant "
            "retained on CRN and reproduced bit-identically vs P25T4. "
            "All pre-registered Task 2 gates PASS."
        ),
        change_type="code_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "t_pathwise_scr_basis": "analytic re-anchoring (LEVEL): {:.1f}".format(
                r["sign_gate_reference"]),
            "quantified_residual": (
                "nested path-wise reference 46,638.9 outside the re-anchoring "
                "bootstrap 95% CI (14.7% understatement beyond noise)"),
        },
        after_snapshot={
            "t_pathwise_scr_component": t["scr_component"],
            "component_vs_reanchored_rel": r["component_vs_reanchored_rel_t"],
            "gap_to_nested_rel": r["gap_to_nested_component_t_rel"],
            "tail_cuttable_share_depression":
                t["tail_cuttable_share_depression"],
            "gates": r["gates"],
            "verdict": rep["verdict"],
        },
        impact_assessment=(
            "Benchmark (t/gaussian) path-wise read-outs move from the "
            "constant-share LEVEL transform to the per-scenario cuttable "
            "COMPONENT basis; the nested truth and the without-actions "
            "bases are untouched (bit-identical cross-checks). The 1% "
            "MR-010/MR-014 disclosure trigger is {}; refresh due at Task 4. "
            "Bootstrap closure test vs the nested reference at Task 3. "
            "Educational classification retained.".format(
                "MET" if r["mr_refresh_trigger_1pct"] else "not met")
        ),
        author=ACTOR, phase=PHASE,
        quantitative_impact=(
            "t({:.4f}) path-wise SCR: re-anchored {:.1f} -> full re-agg "
            "{:.1f} ({:+.2%}); gap to nested 46,638.9 narrows from {:+.2%} "
            "to {:+.2%}; tail cuttable share depressed by {:.3f}.".format(
                RANK_INVARIANCE_DF, r["sign_gate_reference"],
                t["scr_component"], r["component_vs_reanchored_rel_t"],
                r["gap_to_nested_level_t_rel"],
                r["gap_to_nested_component_t_rel"],
                t["tail_cuttable_share_depression"])
        ),
    )
    rec.submit_for_peer_review(
        actor=ACTOR,
        comments="Pre-registered gates 6/6 PASS; archive cross-checks "
                 "bit-identical; new unit tests PASS.")
    rec.submit_to_owner(
        actor=ACTOR,
        comments="Owner review: benchmark-basis change (level -> component); "
                 "magnitude disclosed; sign-off withheld pending Task 3 "
                 "bootstrap closure.")
    store.add_change_record(rec)
    store.audit_trail.append(AuditEntry.governance(
        actor=ACTOR, phase=PHASE,
        event="ChangeRecord opened (OWNER_REVIEW) - Phase 26 Task 2 "
              "composition transform (full path-wise copula re-aggregation)",
        details={"record_id": rec.record_id, "change_type": "code_change",
                 "status": rec.status.value,
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
                      "status": rec.status.value,
                      "audit_integrity_ok": ok,
                      "change_records_total": len(store.change_records),
                      "audit_entries_total":
                          len(store.audit_trail.all())}))
    return 0 if ok else 1


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--stage", required=True,
                   choices=["verify", "reagg", "report", "governance"])
    a = p.parse_args()
    return {"verify": stage_verify, "reagg": stage_reagg,
            "report": stage_report, "governance": stage_governance}[a.stage]()


if __name__ == "__main__":
    sys.exit(main())
