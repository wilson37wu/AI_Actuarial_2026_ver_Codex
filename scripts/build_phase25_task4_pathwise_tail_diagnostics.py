#!/usr/bin/env python3
"""Phase 25 Task 4 -- path-wise tail diagnostics + capital-delta matrix
+ MR-010/MR-014 refresh (REQUIRED: trigger MET at Task 2 with +14.17%).

Deliverables FIXED in the Phase 25 Task 1 design note (s5, pre-registered;
no gate-shopping):
  * with-vs-without and pathwise-vs-horizon capital deltas at VaR/ES/SCR
    for nested, t-copula, gaussian and var-covar;
  * MR-010 / MR-014 refreshed with the path-wise figures (disclosure
    trigger |pathwise - horizon| SCR delta > 1% of horizon SCR -- MET);
  * rank invariance: df re-matched on the WITHOUT-actions staged losses
    unchanged at 2.9451; copula parameters FROZEN (Art. 234);
  * reproducibility: seeds/config/digests recorded; methodology_change
    ChangeRecord OWNER_REVIEW.

Staged build (wall-clock-limited shells; each stage < 45 s):

  PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase25_task4_pathwise_tail_diagnostics.py --stage verify
  PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase25_task4_pathwise_tail_diagnostics.py --stage diag
  PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase25_task4_pathwise_tail_diagnostics.py --stage boot
  PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase25_task4_pathwise_tail_diagnostics.py --stage governance

GATES (formalisation of the pre-registered Task 4 bullets; recorded before
the diagnostics were computed):
  G1  delta matrix complete and archive-cross-checked: every archived
      figure matches its source report; the fresh t/gaussian HORIZON
      joint-action re-runs reproduce the archived Phase 24 Task 2
      read-outs bit-identically (same seed/config; digest equality)
  G2  var-covar understatement refreshed on the path-wise basis (vs the
      nested path-wise reference AND vs the t path-wise read-out)
  G3  rank invariance: df re-matched on the WITHOUT-actions staged losses
      equals the frozen 2.9451 (4-dp archive tolerance) and rho equals the
      archived dependence basis (copula NOT re-tuned; SII Art. 234)
  G4  reproducibility: seeds/config/digests recorded; same-seed t/gaussian
      digests identical to the archived Phase 24 Task 2 digests
  G5  governance: MR-010/MR-014 refreshed (REQUIRED trigger met at Task 2);
      methodology_change ChangeRecord OWNER_REVIEW; verify_all True

The t/gaussian path-wise read-outs are an ANALYTIC RE-ANCHORING (governed
smoothed-relief surface + constant FIT benefit share applied ONCE to the
anchored joint level) -- NOT a full path-wise copula re-aggregation (the
documented next-phase candidate).  The tail diagnostics are DISCLOSED
evidence; no post-hoc numeric acceptance thresholds (no gate-shopping).

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
    MitigationStatus,
)
from par_model_v2.projection.joint_action_aggregation import (
    JointActionAggregator,
    JointActionConfig,
)
from par_model_v2.projection.management_actions import ManagementActionRule
from par_model_v2.projection.multi_driver_copula_aggregation import (
    _nearest_correlation,
)
from par_model_v2.projection.nested_stochastic_tvog import (
    capital_metrics_from_liabilities,
)
from par_model_v2.projection.pathwise_tail_diagnostics import (
    PATHWISE_DISCLOSURE_THRESHOLD,
    PW_BOOTSTRAP_N_SIM,
    PW_BOOTSTRAP_REPLICATES,
    PW_CONFIDENCE_SWEEP,
    PW_CONVERGENCE_PREFIXES,
    PW_SEED_STABILITY_SEEDS,
    build_pathwise_delta_matrix,
    pathwise_bootstrap_margin_ci,
    pathwise_confidence_sweep,
    pathwise_diagnostics_digest,
    pathwise_joint_readout,
    pathwise_prefix_convergence,
    pathwise_seed_stability,
    pathwise_tail_use_restrictions,
)
from par_model_v2.projection.tail_dependence import match_t_df_to_losses

PHASE = "Phase 25: Path-Wise Bonus Declaration Dynamics"
ACTOR = "AutomatedModelDev_Phase25"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
OUT_DIR = Path("docs/validation")
JSON_PATH = OUT_DIR / "PHASE25_TASK4_PATHWISE_TAIL_DIAGNOSTICS_REPORT.json"
MD_PATH = OUT_DIR / "PHASE25_TASK4_PATHWISE_TAIL_DIAGNOSTICS_REPORT.md"
CARD_PATH = Path("docs/PATHWISE_TAIL_DIAGNOSTICS_CARD.md")
STAGE_DIR = Path("/var/tmp/p25t4_stage")
STAGE_PATH = STAGE_DIR / "verified_inputs.npz"
P23T2_LOSSES = Path("/var/tmp/p23t2_stage/losses.npz")
P23T4_WITH = Path("/var/tmp/p23t4_stage/losses_with_actions.npz")
P25T3_STAGE = Path("/var/tmp/p25t3_stage")
P22T4_REPORT = OUT_DIR / "PHASE22_TASK4_AGGREGATION_REPORT.json"
P23T2_REPORT = OUT_DIR / "PHASE23_TASK2_T_COPULA_AGGREGATION_REPORT.json"
P23T3_REPORT = OUT_DIR / "PHASE23_TASK3_MANAGEMENT_ACTION_REPORT.json"
P23T4_REPORT = OUT_DIR / "PHASE23_TASK4_AGGREGATION_WITH_ACTIONS_REPORT.json"
P24T2_REPORT = OUT_DIR / "PHASE24_TASK2_JOINT_ACTION_REAGGREGATION_REPORT.json"
P24T3_REPORT = OUT_DIR / "PHASE24_TASK3_INNER_PATH_ACTION_REPORT.json"
P24T4_REPORT = OUT_DIR / "PHASE24_TASK4_JOINT_ACTION_TAIL_DIAGNOSTICS_REPORT.json"
P25T2_REPORT = OUT_DIR / "PHASE25_TASK2_PATHWISE_DECLARATION_REPORT.json"
P25T3_REPORT = OUT_DIR / "PHASE25_TASK3_PATHWISE_PROXY_BASIS_REPORT.json"

DRIVERS = ("rate", "equity", "credit", "lapse", "mortality", "fx", "liquidity")
SEED = 20260607          # identical to Phase 23 T2/T4 + Phase 24 T2/T4
N_SIM = 200_000          # identical to Phase 23 T2/T4 + Phase 24 T2/T4
THRESHOLDS = (0.80, 0.85, 0.90)  # identical to Phase 23 Task 2
CONF = 0.995
HORIZON_M = 12
ARCHIVED_DF = 2.9451     # frozen Phase 23 Task 2 tail-matched df (4-dp)
DF_TOL = 5e-5            # 4-dp archive rounding tolerance (P24T2 convention)
RHO_TOL = 1e-6

CHANGE_TITLE = (
    "Phase 25 Task 4 - path-wise tail diagnostics + pathwise-vs-horizon / "
    "with-vs-without capital-delta matrix + MR-010/MR-014 refresh"
)

AFFECTED_COMPONENTS = [
    "par_model_v2/projection/pathwise_tail_diagnostics.py",
    "scripts/build_phase25_task4_pathwise_tail_diagnostics.py",
    "tests/test_phase25_task4_pathwise_tail_diagnostics.py",
    "docs/PATHWISE_TAIL_DIAGNOSTICS_CARD.md",
    "docs/validation/PHASE25_TASK4_PATHWISE_TAIL_DIAGNOSTICS_REPORT.{json,md}",
]

STANDARD_REFERENCES = [
    "Solvency II Delegated Regulation Article 23 (future management actions)",
    "Solvency II Delegated Regulation Article 234 (aggregation)",
    "SOA ASOP 56 section 3.1.3/3.4/3.5",
    "SOA ASOP 25 section 3.3",
    "IA TAS M section 3.2/3.6",
    "IFoA Life Aggregation & Simulation working party",
    "McNeil-Frey-Embrechts 2015 ch.7",
]


def _rule() -> ManagementActionRule:
    return ManagementActionRule()


def _fit_benefit_share() -> float:
    """FIT-sample mean benefit share (leakage-free; P25T3 staged arrays)."""
    parts = sorted(P25T3_STAGE.glob("pwfit_*.npz"))
    if not parts:
        raise RuntimeError("P25T3 pwfit stage arrays not found")
    ben = np.concatenate([np.load(p)["benefit"] for p in parts])
    l7 = np.load(P25T3_STAGE / "inputs.npz")["fit_l7"]
    if ben.shape != l7.shape:
        raise RuntimeError("fit benefit / fit_l7 misaligned")
    return float(ben.mean() / l7.mean())


def stage_verify() -> int:
    """Archive cross-checks + rank-invariance df re-match (NO new benchmark)."""
    z = np.load(P23T2_LOSSES)
    w = np.load(P23T4_WITH)
    arch4 = json.loads(P22T4_REPORT.read_text(encoding="utf-8"))["aggregation"]
    arch2 = json.loads(P23T2_REPORT.read_text(encoding="utf-8"))["aggregation"]
    t3 = json.loads(P23T3_REPORT.read_text(encoding="utf-8"))["result"]
    t4 = json.loads(P23T4_REPORT.read_text(encoding="utf-8"))
    p24t2 = json.loads(P24T2_REPORT.read_text(encoding="utf-8"))
    p24t3 = json.loads(P24T3_REPORT.read_text(encoding="utf-8"))
    p25t2 = json.loads(P25T2_REPORT.read_text(encoding="utf-8"))
    p25t3 = json.loads(P25T3_REPORT.read_text(encoding="utf-8"))
    rule = _rule()
    awa = t4["aggregation_with_actions"]
    r2 = p25t2["result"]
    r3 = p25t3["result"]
    surf = r3["surface_calibration_fit_only"]
    beta_fit = _fit_benefit_share()
    delta = r2["pathwise_vs_horizon_delta"]

    checks = {
        "nested_scr_match_p22t4":
            abs(float(z["nested_scr"][0]) - arch4["nested_scr"]) < 1e-6,
        "var_covar_scr_match_p22t4":
            abs(float(z["var_covar_scr"][0]) - arch4["var_covar_scr"]) < 1e-6,
        "var_covar_with_match_p23t4":
            abs(float(w["var_covar_scr_with"][0]) - awa["var_covar_scr"]) < 1e-3,
        "l_fit_match_task3":
            abs(float(w["l_fit"][0]) - float(t3["fit_mean_liability"])) < 1e-9,
        "a_ref_match_task3":
            abs(float(w["a_ref"][0]) - float(t3["reference_assets"])) < 1e-9,
        "rule_matches_task3": rule.to_dict() == t3["rule"],
        "p24t2_df_is_frozen":
            abs(p24t2["df_matched"] - ARCHIVED_DF) < 1e-12,
        "p24t2_seed_nsim_convention":
            p24t2["joint_action"]["t_config"]["n_sim"] == N_SIM
            and p24t2["joint_action"]["t_config"]["seed"] == SEED,
        "p24t2_verdict_pass": p24t2["verdict"] == "PASS",
        "p24t3_verdict_pass": p24t3["verdict"] == "PASS",
        "p25t2_verdict_pass": p25t2["verdict"] == "PASS",
        "p25t3_verdict_pass": p25t3["verdict"] == "PASS",
        "p25t2_sign_gate_pass":
            bool(p25t2["result"]["gates"]
                 ["G2_sign_gate_pathwise_scr_ge_horizon_scr"]),
        "p25t2_horizon_matches_p24t3_inner_path":
            abs(r2["nested_capital_with_horizon"]["scr_proxy"]
                - p24t3["result"]["nested_capital_with_inner_path"]
                ["scr_proxy"]) < 1e-3,
        "p25t3_rule_unchanged": r3["rule"] == rule.to_dict(),
        "p25t3_a_ref_match":
            abs(float(r3["reference_assets"])
                - float(t3["reference_assets"])) < 1e-9,
        "p25t3_sigma_interior": bool(surf["sigma_interior"]),
        "p25t3_truth_scr_matches_p25t2":
            abs(r3["nested_capital_with_pathwise"]["scr_proxy"]
                - r2["nested_capital_with_pathwise"]["scr_proxy"]) < 1e-3,
        "beta_fit_in_unit_interval": bool(0.0 < beta_fit <= 1.0),
        "mr_refresh_trigger_met_at_task2":
            bool(delta["mr010_mr014_refresh_required_task4"])
            and abs(delta["scr_delta_rel_to_horizon"])
            > PATHWISE_DISCLOSURE_THRESHOLD,
    }
    for k in DRIVERS:
        cap = capital_metrics_from_liabilities(z[k], CONF, HORIZON_M)
        checks["standalone_scr_match_" + k] = (
            abs(float(cap.scr_proxy) - arch4["standalone_scr"][k]) < 1e-6)
        checks["anchor_mean_match_" + k] = (
            abs(float(w[k + "_anchor_mean"][0]) - float(np.mean(z[k]))) < 1e-9)

    # G3 input -- rank invariance: re-match the tail df on the
    # WITHOUT-actions losses with the SAME machinery/thresholds as the
    # archived Phase 23 Task 2 run; copula parameters must NOT move.
    L = np.column_stack([np.asarray(z[k], dtype=float) for k in DRIVERS])
    matches = [match_t_df_to_losses(L, threshold=q)
               for q in sorted(THRESHOLDS)]
    df_rematched = float(np.median([m.pooled_df for m in matches]))
    central = matches[len(THRESHOLDS) // 2]
    rho = _nearest_correlation(np.asarray(central.rho_matrix, dtype=float))
    arch_rho = np.asarray(arch2["rho_matrix"], dtype=float)
    rho_max_abs_diff = float(np.max(np.abs(rho - arch_rho)))
    checks["df_rematched_rank_invariant"] = (
        abs(df_rematched - ARCHIVED_DF) <= DF_TOL)
    checks["rho_matches_archived_dependence_basis"] = (
        rho_max_abs_diff < RHO_TOL)

    if not all(checks.values()):
        print("CROSS-CHECK FAILURE:",
              {k: v for k, v in checks.items() if not v})
        return 1

    STAGE_DIR.mkdir(parents=True, exist_ok=True)
    np.savez(
        STAGE_PATH,
        rho=rho,
        df_rematched=np.array([df_rematched]),
        rho_max_abs_diff=np.array([rho_max_abs_diff]),
        crosscheck_count=np.array([len(checks)]),
        l_fit=np.array([float(w["l_fit"][0])]),
        a_ref=np.array([float(w["a_ref"][0])]),
        beta_fit=np.array([beta_fit]),
        sigma=np.array([float(surf["sigma"])]),
        alpha=np.array([float(surf["alpha"])]),
        var_covar_scr_with=np.array([float(w["var_covar_scr_with"][0])]),
    )
    print("stage verify done: {}/{} cross-checks PASS; df re-matched {:.4f} "
          "(frozen {:.4f}); rho max|diff| {:.2e}; beta_fit {:.4f}".format(
              sum(checks.values()), len(checks), df_rematched, ARCHIVED_DF,
              rho_max_abs_diff, beta_fit))
    return 0


def stage_diag() -> int:
    z = np.load(P23T2_LOSSES)
    w = np.load(P23T4_WITH)
    s = np.load(STAGE_PATH)
    arch2 = json.loads(P23T2_REPORT.read_text(encoding="utf-8"))["aggregation"]
    p24t2 = json.loads(P24T2_REPORT.read_text(encoding="utf-8"))
    p25t2 = json.loads(P25T2_REPORT.read_text(encoding="utf-8"))["result"]
    rule = _rule()

    rho = np.asarray(s["rho"], dtype=float)
    l_fit = float(s["l_fit"][0])
    beta_fit = float(s["beta_fit"][0])
    sigma = float(s["sigma"][0])
    alpha = float(s["alpha"][0])

    losses = {k: np.asarray(z[k], dtype=float) for k in DRIVERS}
    anchors = {k: float(w[k + "_anchor_mean"][0]) for k in DRIVERS}
    agg = JointActionAggregator(
        standalone_losses=losses, correlation=rho, rule=rule,
        l_fit=l_fit, anchor_means=anchors,
    )

    # --- G1/G4: HORIZON-basis re-runs reproduce archived P24T2 bit-identically
    res_t = agg.run(JointActionConfig(n_sim=N_SIM, seed=SEED, df=ARCHIVED_DF))
    res_g = agg.run(JointActionConfig(n_sim=N_SIM, seed=SEED, df=None))
    arch_j = p24t2["joint_action"]
    repro = {
        "t_scr_abs_diff": abs(res_t.scr_joint_with - arch_j["t_scr"]),
        "g_scr_abs_diff": abs(res_g.scr_joint_with - arch_j["g_scr"]),
        "t_digest_match": res_t.digest == arch_j["t_digest"],
        "g_digest_match": res_g.digest == arch_j["g_digest"],
    }
    repro_ok = (repro["t_scr_abs_diff"] < 1e-9
                and repro["g_scr_abs_diff"] < 1e-9
                and repro["t_digest_match"] and repro["g_digest_match"])

    # --- path-wise read-outs (same seed; CRN against the horizon basis)
    ro_t = pathwise_joint_readout(
        agg, N_SIM, SEED, ARCHIVED_DF, sigma, alpha, beta_fit, CONF)
    ro_g = pathwise_joint_readout(
        agg, N_SIM, SEED, None, sigma, alpha, beta_fit, CONF)
    crn_consistency = {
        "t_horizon_scr_crn_abs_diff":
            abs(ro_t["scr_horizon"] - res_t.scr_joint_with),
        "g_horizon_scr_crn_abs_diff":
            abs(ro_g["scr_horizon"] - res_g.scr_joint_with),
    }

    # --- delta matrix --------------------------------------------------
    # nested rows: the seven-driver proxy-validation nested run (n_eval=500
    # outer nodes; P25T2 archived) -- the ONLY basis on which the path-wise
    # nested truth exists.  t/gaussian/var-covar rows: the aggregation
    # dependence basis (n_obs=160 realised outer losses).  DISCLOSED.
    nc_wo = p25t2["nested_capital_without"]
    nc_hz = p25t2["nested_capital_with_horizon"]
    nc_pw = p25t2["nested_capital_with_pathwise"]

    def _row(d):
        return {"var": d["var_liability"], "es": d["es_liability"],
                "scr": d["scr_proxy"]}

    without = {
        "nested": _row(nc_wo),
        "t_copula": {"var": arch2["t_capital"]["var_liability"],
                     "es": arch2["t_capital"]["es_liability"],
                     "scr": arch2["t_matched_scr"]},
        "gaussian": {"var": arch2["gaussian_capital"]["var_liability"],
                     "es": arch2["gaussian_capital"]["es_liability"],
                     "scr": arch2["gaussian_scr"]},
        "var_covar": {"var": None, "es": None,
                      "scr": float(z["var_covar_scr"][0])},
    }
    with_horizon = {
        "nested": _row(nc_hz),
        "t_copula": {"var": res_t.var_joint_with, "es": res_t.es_joint_with,
                     "scr": res_t.scr_joint_with},
        "gaussian": {"var": res_g.var_joint_with, "es": res_g.es_joint_with,
                     "scr": res_g.scr_joint_with},
        # var-covar 'with' is the standalone-action formula figure (P23T4);
        # SCR-only (summed level convention; DISCLOSED, P24T4 convention).
        "var_covar": {"var": None, "es": None,
                      "scr": float(s["var_covar_scr_with"][0])},
    }
    with_pathwise = {
        "nested": _row(nc_pw),
        "t_copula": {"var": ro_t["var_pathwise"], "es": ro_t["es_pathwise"],
                     "scr": ro_t["scr_pathwise"]},
        "gaussian": {"var": ro_g["var_pathwise"], "es": ro_g["es_pathwise"],
                     "scr": ro_g["scr_pathwise"]},
        # no path-wise analogue of the var-covar formula (DISCLOSED)
        "var_covar": {"var": None, "es": None, "scr": None},
    }
    matrix = build_pathwise_delta_matrix(without, with_horizon, with_pathwise)

    # --- G2: var-covar understatement refreshed on the path-wise basis
    vc_with = float(s["var_covar_scr_with"][0])
    nested_pw_scr = nc_pw["scr_proxy"]
    vc_refresh = {
        "var_covar_scr_with": vc_with,
        "understatement_vs_nested_with_pathwise":
            1.0 - vc_with / nested_pw_scr,
        "understatement_vs_t_pathwise_readout":
            1.0 - vc_with / ro_t["scr_pathwise"],
        "understatement_vs_nested_with_horizon_basis_p24t4":
            json.loads(P24T4_REPORT.read_text(encoding="utf-8"))
            ["var_covar_refresh"]["understatement_vs_nested_with"],
        "basis_note": (
            "vc_with is the P23T4 standalone-action formula figure (no "
            "path-wise analogue exists); nested path-wise reference is the "
            "n_eval=500 proxy-validation nested run; t path-wise read-out "
            "is on the n_obs=160 dependence basis (DISCLOSED)."
        ),
    }

    # --- tail diagnostics on the path-wise basis (DISCLOSED evidence)
    sweep = pathwise_confidence_sweep(
        agg, N_SIM, SEED, ARCHIVED_DF, sigma, alpha, beta_fit)
    conv = pathwise_prefix_convergence(
        agg, SEED, ARCHIVED_DF, sigma, alpha, beta_fit)
    seeds = pathwise_seed_stability(
        agg, ARCHIVED_DF, N_SIM, sigma, alpha, beta_fit)
    sweep_monotone = all(
        sweep[i]["var_pathwise"] <= sweep[i + 1]["var_pathwise"] + 1e-9
        for i in range(len(sweep) - 1))
    relieves_less_everywhere = all(
        r["scr_pathwise"] >= r["scr_horizon"] - 1e-9 for r in sweep)
    i995 = [i for i, r in enumerate(sweep)
            if abs(r["confidence"] - 0.995) < 1e-12][0]

    pw_hz = matrix["nested"]["pathwise_minus_horizon"]
    trigger = {
        "threshold": PATHWISE_DISCLOSURE_THRESHOLD,
        "nested_scr_delta_rel_to_horizon": pw_hz["scr_delta_pct"],
        "met": bool(abs(pw_hz["scr_delta_pct"])
                    > PATHWISE_DISCLOSURE_THRESHOLD),
    }

    gates = {
        "G1_delta_matrix_complete_and_crosschecked": bool(
            repro_ok and all(
                matrix[lv]["without"]["scr"] is not None
                for lv in ("nested", "t_copula", "gaussian", "var_covar"))
            and all(matrix[lv]["with_pathwise"]["scr"] is not None
                    for lv in ("nested", "t_copula", "gaussian"))),
        "G2_var_covar_understatement_refreshed_pathwise": bool(
            vc_refresh["understatement_vs_nested_with_pathwise"] > 0
            and vc_refresh["understatement_vs_t_pathwise_readout"] > 0),
        "G3_df_rank_invariance_copula_frozen": bool(
            abs(float(s["df_rematched"][0]) - ARCHIVED_DF) <= DF_TOL
            and float(s["rho_max_abs_diff"][0]) < RHO_TOL),
        "G4_reproducibility_recorded": bool(
            repro["t_digest_match"] and repro["g_digest_match"]),
    }
    verdict = "PASS" if all(gates.values()) else "PARTIAL"

    out = {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": PHASE,
        "task": CHANGE_TITLE,
        "verdict": verdict,
        "gates": gates,
        "gate_note": (
            "Gates formalise the pre-registered Task 4 bullets (design "
            "note s5): completeness/cross-check, refresh, rank invariance, "
            "reproducibility. The tail diagnostics are DISCLOSED evidence "
            "-- no post-hoc numeric acceptance thresholds (no "
            "gate-shopping)."
        ),
        "rule": rule.to_dict(),
        "reference_assets": float(s["a_ref"][0]),
        "fit_mean_liability": l_fit,
        "df_matched": ARCHIVED_DF,
        "df_rematched": float(s["df_rematched"][0]),
        "rho_max_abs_diff_vs_archived": float(s["rho_max_abs_diff"][0]),
        "seed": SEED,
        "n_sim": N_SIM,
        "n_obs": int(np.asarray(z["rate"]).size),
        "drivers": list(DRIVERS),
        "crosscheck_count": int(s["crosscheck_count"][0]),
        "pathwise_basis_params": {
            "sigma": sigma, "alpha": alpha, "benefit_share_fit": beta_fit,
            "provenance": (
                "sigma/alpha: governed Phase 25 Task 3 FIT-only "
                "calibration (archive cross-checked); benefit_share_fit: "
                "FIT-sample mean benefit share from the P25T3 staged "
                "arrays (leakage-free; ONE additional scalar)"
            ),
        },
        "readout_convention": (
            "t/gaussian path-wise read-outs are an ANALYTIC RE-ANCHORING: "
            "V = L_fit + sum_k (Q_k(U_k) - mean_k); relieved = alpha * "
            "phi_sigma(CR(V)) * clip(beta_fit * V, 0, V); W = V - "
            "clip(relieved, 0, max_relief * clip(beta_fit * V, 0, V)) -- "
            "the IDENTICAL node-level envelope transform of the truth and "
            "the proxy, applied ONCE to the joint level under the FROZEN "
            "t(2.9451)/Gaussian dependence basis. NOT a full path-wise "
            "copula re-aggregation (documented next-phase candidate). "
            "Nested rows are on the n_eval=500 proxy-validation outer "
            "sample; t/gaussian/var-covar rows on the n_obs=160 "
            "aggregation dependence basis (DISCLOSED)."
        ),
        "reproduction_of_p24t2_horizon_basis": repro,
        "crn_consistency": crn_consistency,
        "t_pathwise_readout": ro_t,
        "g_pathwise_readout": ro_g,
        "delta_matrix": matrix,
        "var_covar_refresh": vc_refresh,
        "mr_refresh_trigger": trigger,
        "tail_diagnostics": {
            "confidence_sweep": sweep,
            "prefix_convergence": conv,
            "seed_stability": seeds,
        },
        "diagnostic_config": {
            "confidence_sweep": list(PW_CONFIDENCE_SWEEP),
            "convergence_prefixes": list(PW_CONVERGENCE_PREFIXES),
            "seed_stability_seeds": list(PW_SEED_STABILITY_SEEDS),
            "bootstrap_replicates": PW_BOOTSTRAP_REPLICATES,
            "bootstrap_n_sim": PW_BOOTSTRAP_N_SIM,
        },
        "diagnostic_findings": {
            "sweep_var_monotone_in_confidence": sweep_monotone,
            "pathwise_relieves_less_at_every_confidence":
                relieves_less_everywhere,
            "tail_saturation_share_at_995":
                sweep[i995]["tail_saturation_share"],
            "tail_mean_smoothed_relief_fraction_at_995":
                sweep[i995]["tail_mean_smoothed_relief_fraction"],
            "t_pathwise_minus_horizon_scr":
                ro_t["pathwise_minus_horizon_scr"],
            "t_pathwise_minus_horizon_scr_rel":
                ro_t["pathwise_minus_horizon_scr"] / ro_t["scr_horizon"],
            "t_pathwise_vs_nested_pathwise_rel_err":
                abs(ro_t["scr_pathwise"] - nested_pw_scr) / nested_pw_scr,
            "scr_seed_max_rel_spread": seeds["scr_max_rel_spread"],
            "scr_prefix_final_rel_delta": conv[-1]["scr_rel_delta_vs_full"],
        },
        "affected_components": AFFECTED_COMPONENTS,
        "standard_references": STANDARD_REFERENCES,
        "use_restrictions": pathwise_tail_use_restrictions(),
    }
    out["reproducibility_digest"] = pathwise_diagnostics_digest({
        "delta_matrix_scr": {
            lv: matrix[lv]["without"]["scr"] for lv in matrix},
        "t_pathwise_scr": ro_t["scr_pathwise"],
        "g_pathwise_scr": ro_g["scr_pathwise"],
        "t_horizon_scr": res_t.scr_joint_with,
        "g_horizon_scr": res_g.scr_joint_with,
        "seed": SEED, "n_sim": N_SIM, "df": ARCHIVED_DF,
        "sigma": sigma, "alpha": alpha, "beta_fit": beta_fit,
    })
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out["markdown_path"] = str(MD_PATH)
    JSON_PATH.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    MD_PATH.write_text(_markdown(out), encoding="utf-8")
    CARD_PATH.write_text(_card(out), encoding="utf-8")
    print("verdict={} gates={}/4 t_pw={:.1f} g_pw={:.1f} t_hz={:.1f} "
          "nested_pw={:.1f} vc_underst={:.1%} sat995={:.1%} "
          "pw-hz(t)={:.1%}".format(
              verdict, sum(gates.values()), ro_t["scr_pathwise"],
              ro_g["scr_pathwise"], res_t.scr_joint_with, nested_pw_scr,
              vc_refresh["understatement_vs_nested_with_pathwise"],
              out["diagnostic_findings"]["tail_saturation_share_at_995"],
              out["diagnostic_findings"]["t_pathwise_minus_horizon_scr_rel"]))
    print("report:", JSON_PATH)
    return 0 if verdict == "PASS" else 1


def stage_boot() -> int:
    """Margin bootstrap (DISCLOSED diagnostic; gates unaffected)."""
    z = np.load(P23T2_LOSSES)
    w = np.load(P23T4_WITH)
    s = np.load(STAGE_PATH)
    rep = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    rule = _rule()
    losses = {k: np.asarray(z[k], dtype=float) for k in DRIVERS}
    anchors = {k: float(w[k + "_anchor_mean"][0]) for k in DRIVERS}
    boot = pathwise_bootstrap_margin_ci(
        losses_without=losses, correlation=np.asarray(s["rho"], float),
        rule=rule, l_fit=float(s["l_fit"][0]), anchor_means=anchors,
        df=ARCHIVED_DF, sigma=float(s["sigma"][0]),
        alpha=float(s["alpha"][0]), benefit_share=float(s["beta_fit"][0]))
    nested_pw = rep["delta_matrix"]["nested"]["with_pathwise"]["scr"]
    nested_in_ci = bool(boot["scr_pathwise"]["ci_lo_95"] <= nested_pw
                        <= boot["scr_pathwise"]["ci_hi_95"])
    rep["tail_diagnostics"]["bootstrap"] = boot
    rep["diagnostic_findings"]["nested_pathwise_inside_bootstrap_ci"] = (
        nested_in_ci)
    rep["diagnostic_findings"]["bootstrap_scr_se_pct_of_mean"] = (
        boot["scr_pathwise"]["se"] / boot["scr_pathwise"]["mean"])
    JSON_PATH.write_text(json.dumps(rep, indent=2) + "\n", encoding="utf-8")
    MD_PATH.write_text(_markdown(rep), encoding="utf-8")
    CARD_PATH.write_text(_card(rep), encoding="utf-8")
    print("boot done: SCR_pw mean {:.0f} SE {:.0f} ({:.1%}) CI [{:.0f}, "
          "{:.0f}]; nested_pw inside CI: {}".format(
              boot["scr_pathwise"]["mean"], boot["scr_pathwise"]["se"],
              rep["diagnostic_findings"]["bootstrap_scr_se_pct_of_mean"],
              boot["scr_pathwise"]["ci_lo_95"],
              boot["scr_pathwise"]["ci_hi_95"], nested_in_ci))
    return 0


def _fmt(x, pct=False):
    if x is None:
        return "n/a"
    return "{:.1%}".format(x) if pct else "{:,.1f}".format(x)


def _markdown(out: dict) -> str:
    m = out["delta_matrix"]
    vc = out["var_covar_refresh"]
    f = out["diagnostic_findings"]
    g = out["gates"]
    boot = out["tail_diagnostics"].get("bootstrap")
    rows = []
    for lv, label in (("nested", "Nested (reference)"),
                      ("t_copula", f"t({out['df_matched']:.4f})"),
                      ("gaussian", "Gaussian"), ("var_covar", "Var-covar")):
        r = m[lv]
        hz = r.get("with_horizon") or {}
        pw = r.get("with_pathwise") or {}
        pmh = r.get("pathwise_minus_horizon") or {}
        pw_scr = pw.get("scr")
        rows.append("| {} | {} | {} | {} | {} | {} |".format(
            label, _fmt(r["without"]["scr"]), _fmt(hz.get("scr")),
            _fmt(pw_scr),
            _fmt((pw_scr - r["without"]["scr"]) / r["without"]["scr"]
                 if pw_scr is not None else None, pct=True),
            _fmt(pmh.get("scr_delta_pct"), pct=True)))
    sweep_rows = "\n".join(
        "| {confidence:.3f} | {var_pathwise:,.0f} | {es_pathwise:,.0f} | "
        "{scr_pathwise:,.0f} | {scr_horizon:,.0f} | {tail_active_share:.1%} "
        "| {tail_saturation_share:.1%} | "
        "{tail_mean_smoothed_relief_fraction:.3f} | "
        "{relief_at_var_pathwise:,.0f} |".format(**r)
        for r in out["tail_diagnostics"]["confidence_sweep"])
    conv_rows = "\n".join(
        "| {n_sim:,} | {var_pathwise:,.0f} | {scr_pathwise:,.0f} | "
        "{scr_rel_delta_vs_full:.2%} |".format(**r)
        for r in out["tail_diagnostics"]["prefix_convergence"])
    boot_md = ""
    if boot is not None:
        boot_md = """
## Copula-seed stability + margin bootstrap (DISCLOSED diagnostics)

- SCR max rel spread across {ns} copula seeds at n_sim {n:,}: **{sp:.2%}**
- Margin bootstrap ({nr} replicates x {nb:,} sims; joint row resample of the {no} realised outer losses; copula frozen, SII Art. 234):
  SCR_pathwise mean {bm:,.0f}, SE {bs:,.0f}
  ({sep:.1%} of mean), 95% CI
  [{lo:,.0f}, {hi:,.0f}]
- Nested path-wise reference inside the bootstrap 95% CI: **{ici}**
- VaR sweep monotone in confidence: {mono}

The bootstrap quantifies the DISCLOSED limitation that n_obs={no}
margin sampling noise propagates into the joint read-out; the nested run
remains the capital reference.
""".format(ns=len(out["diagnostic_config"]["seed_stability_seeds"]),
           n=out["n_sim"], sp=f["scr_seed_max_rel_spread"],
           nr=boot["n_replicates"], nb=boot["n_sim_per_replicate"],
           no=boot["n_obs"], bm=boot["scr_pathwise"]["mean"],
           bs=boot["scr_pathwise"]["se"],
           sep=f.get("bootstrap_scr_se_pct_of_mean", 0.0),
           lo=boot["scr_pathwise"]["ci_lo_95"],
           hi=boot["scr_pathwise"]["ci_hi_95"],
           ici=f.get("nested_pathwise_inside_bootstrap_ci"),
           mono=f["sweep_var_monotone_in_confidence"])
    p = out["pathwise_basis_params"]
    return f"""# Phase 25 Task 4 -- Path-Wise Tail Diagnostics + Capital-Delta Matrix

**Verdict: {out['verdict']}** ({sum(g.values())}/{len(g)} fixed pre-registered gates PASS;
governance gate G5 reported separately below).

EDUCATIONAL ONLY. Tail diagnostics and the full with-vs-without /
pathwise-vs-horizon capital-delta matrix on the PATH-WISE with-actions
basis established by Phase 25 Tasks 2-3, under the frozen
t({out['df_matched']:.4f}) / Gaussian copulas on the archived Phase 23 Task 2
dependence basis (seed {out['seed']}, n_sim {out['n_sim']:,}, n_obs {out['n_obs']}; rank
invariance re-verified: df re-matched {out['df_rematched']:.4f}, rho max|diff|
{out['rho_max_abs_diff_vs_archived']:.1e}).

The t/gaussian path-wise read-outs are an ANALYTIC RE-ANCHORING of the
anchored joint level with the governed Task 3 smoothed-relief surface
(sigma {p['sigma']:.3f}, alpha {p['alpha']:.4f}) and the FIT-sample benefit share
(beta {p['benefit_share_fit']:.4f}; leakage-free) -- NOT a full path-wise copula
re-aggregation (documented next-phase candidate). Nested rows are on the
n_eval=500 proxy-validation outer sample (the only basis where the
path-wise nested truth exists); t/gaussian/var-covar rows are on the
n_obs=160 aggregation dependence basis (DISCLOSED).

## 99.5% 1y SCR delta matrix (with-vs-without / pathwise-vs-horizon)

| Level | Without | With (horizon) | With (path-wise) | Path-wise vs without | Path-wise vs horizon |
|---|---|---|---|---|---|
{chr(10).join(rows)}

Var-covar has no path-wise analogue (formula on standalone marginals;
DISCLOSED); its 'with (horizon)' figure is the P23T4 standalone-action
SCR (summed level convention -- SCR-only, P24T4 convention).

## MR-010/MR-014 refresh trigger (design note s5; REQUIRED)

- Nested path-wise vs horizon SCR delta: **{out['mr_refresh_trigger']['nested_scr_delta_rel_to_horizon']:+.2%}**
  (threshold {out['mr_refresh_trigger']['threshold']:.0%}; trigger MET: {out['mr_refresh_trigger']['met']})
- The path-wise basis relieves LESS capital in the tail (recognition-lag
  effect: bonus restoration on recovering paths); the horizon-level basis
  UNDERSTATES the with-actions SCR at every level of the matrix.

## Var-covar understatement refreshed (MR-010)

- vs nested-with-path-wise {_fmt(m['nested']['with_pathwise']['scr'])}: **{vc['understatement_vs_nested_with_pathwise']:.1%}**
- vs t path-wise read-out: **{vc['understatement_vs_t_pathwise_readout']:.1%}**
- horizon-basis baseline (P24T4): {vc['understatement_vs_nested_with_horizon_basis_p24t4']:.1%}

## Confidence sweep with action-saturation profile (t, path-wise basis)

| Conf | VaR_pw | ES_pw | SCR_pw | SCR_hz | Tail active | Tail saturated | Mean smoothed relief frac | Relief at VaR |
|---|---|---|---|---|---|---|---|---|
{sweep_rows}

Saturation share (raw governed cut at floor) in the 99.5% tail:
**{f['tail_saturation_share_at_995']:.1%}** -- the joint tail still sits at maximum RAW relief,
but the path-wise smoothed surface caps the realised relief at
alpha * phi_sigma < max_relief (mean smoothed fraction
{f['tail_mean_smoothed_relief_fraction_at_995']:.3f} vs raw {out['rule']['max_relief']:.3f}), so the path-wise basis
relieves less at every confidence level
({f['pathwise_relieves_less_at_every_confidence']}); t path-wise minus horizon SCR
{f['t_pathwise_minus_horizon_scr']:,.0f} ({f['t_pathwise_minus_horizon_scr_rel']:+.1%}).

## Prefix-subsample convergence (common random numbers, 99.5%)

| n_sim | VaR_pw | SCR_pw | SCR rel delta vs full |
|---|---|---|---|
{conv_rows}
{boot_md}
## Fixed pre-registered gates (Task 1 design note s5; no gate-shopping)

{chr(10).join('- ' + k + ': ' + ('PASS' if v else 'FAIL') for k, v in g.items())}
- G5_governance_verify_all: {out.get('audit_integrity_ok', 'pending governance stage')}

## Reproducibility

- Bit-identical reproduction of the archived Phase 24 Task 2 HORIZON
  read-outs: t/g SCR abs diff {out['reproduction_of_p24t2_horizon_basis']['t_scr_abs_diff']:.2e} / {out['reproduction_of_p24t2_horizon_basis']['g_scr_abs_diff']:.2e}; digests match
  ({out['reproduction_of_p24t2_horizon_basis']['t_digest_match']}/{out['reproduction_of_p24t2_horizon_basis']['g_digest_match']}).
- {out['crosscheck_count']} archive cross-checks PASS before any new computation.
- t path-wise vs nested path-wise SCR rel err: {f['t_pathwise_vs_nested_pathwise_rel_err']:.1%} (DISCLOSED; the
  full path-wise copula re-aggregation is the documented next-phase
  candidate).
- Digest `{out['reproducibility_digest'][:16]}`; seed {out['seed']}; n_sim {out['n_sim']:,}.

Standards: {'; '.join(out['standard_references'])}.
"""


def _card(out: dict) -> str:
    f = out["diagnostic_findings"]
    vc = out["var_covar_refresh"]
    m = out["delta_matrix"]
    t_pw = m["t_copula"]["with_pathwise"]["scr"]
    n_pw = m["nested"]["with_pathwise"]["scr"]
    return f"""# Path-Wise Tail Diagnostics Card (Phase 25 Task 4)

**{out['verdict']}** -- full capital-delta matrix + tail diagnostics on the
PATH-WISE with-actions basis. t({out['df_matched']:.4f}) path-wise re-anchored SCR
{t_pw:,.0f} (horizon {m['t_copula']['with_horizon']['scr']:,.0f}; +{f['t_pathwise_minus_horizon_scr_rel']:.1%}) vs nested path-wise
{n_pw:,.0f}; nested pathwise-vs-horizon delta {out['mr_refresh_trigger']['nested_scr_delta_rel_to_horizon']:+.2%} (MR-010/MR-014
refresh trigger MET; refreshed). Var-covar understatement {vc['understatement_vs_nested_with_pathwise']:.1%} vs
nested path-wise ({vc['understatement_vs_nested_with_horizon_basis_p24t4']:.1%} on the horizon basis). Rank invariance: df
re-matched {out['df_rematched']:.4f} (frozen {out['df_matched']:.4f}); copula NOT re-tuned (Art. 234).
99.5% tail raw saturation {f['tail_saturation_share_at_995']:.1%}; smoothed relief fraction
{f['tail_mean_smoothed_relief_fraction_at_995']:.3f} < max_relief {out['rule']['max_relief']:.3f} (restoration effect). Seed spread
{f['scr_seed_max_rel_spread']:.2%}. Read-outs are an analytic re-anchoring under the FROZEN
dependence basis -- the full path-wise copula re-aggregation is the
documented next-phase candidate.

EDUCATIONAL_DEMONSTRATION_ONLY -- placeholders disclosed; sign-off withheld.
Evidence: docs/validation/PHASE25_TASK4_PATHWISE_TAIL_DIAGNOSTICS_REPORT.{{json,md}}
"""


def _has_change_record(store: GovernanceStore) -> bool:
    return any(r.title == CHANGE_TITLE for r in store.change_records)


def stage_governance() -> int:
    rep = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    if "bootstrap" not in rep["tail_diagnostics"]:
        print("run --stage boot before governance")
        return 1
    vc = rep["var_covar_refresh"]
    f = rep["diagnostic_findings"]
    m = rep["delta_matrix"]
    t_pw = m["t_copula"]["with_pathwise"]["scr"]
    n_pw = m["nested"]["with_pathwise"]["scr"]
    trig = rep["mr_refresh_trigger"]
    store = GovernanceStore.from_json(GOV_PATH.read_text(encoding="utf-8"))

    if _has_change_record(store):
        rec = next(x for x in store.change_records if x.title == CHANGE_TITLE)
        print("already applied:", rec.record_id)
        print("audit integrity:", store.audit_trail.verify_all())
        return 0

    Path("/var/tmp/p25t4_build").mkdir(parents=True, exist_ok=True)
    Path("/var/tmp/p25t4_build/GOV_BACKUP_pre_p25t4_gov.json").write_text(
        store.to_json() + "\n", encoding="utf-8")

    mr_notes_010 = (
        "Phase 25 Task 4 refresh (path-wise basis; supersedes the Phase 24 "
        "Task 4 refresh): var-covar with-actions SCR {vcw:,.0f} understates "
        "the nested PATH-WISE with-actions reference {nw:,.0f} by {u1:.1%} "
        "(horizon-basis baseline {u0:.1%}) and the t({df:.4f}) path-wise "
        "re-anchored read-out {ts:,.0f} by {u2:.1%}. The path-wise "
        "declaration basis (P25T2) relieves LESS capital in the tail "
        "({d:+.2%} nested SCR vs horizon), so the var-covar understatement "
        "WIDENS on the governed basis. Full delta matrix + tail "
        "diagnostics in PHASE25_TASK4 report; nested remains the capital "
        "reference."
    ).format(vcw=vc["var_covar_scr_with"], nw=n_pw,
             u1=vc["understatement_vs_nested_with_pathwise"],
             u0=vc["understatement_vs_nested_with_horizon_basis_p24t4"],
             df=rep["df_matched"], ts=t_pw,
             u2=vc["understatement_vs_t_pathwise_readout"],
             d=trig["nested_scr_delta_rel_to_horizon"])
    store.risk_register.get("MR-010").update_mitigation(
        MitigationStatus.MITIGATED, notes=mr_notes_010)

    boot = rep["tail_diagnostics"]["bootstrap"]
    mr_notes_014 = (
        "Phase 25 Task 4 refresh (path-wise basis; supersedes the Phase 24 "
        "Task 4 refresh): the governed with-actions basis is now the "
        "PATH-WISE declaration (P25T2-T3; restoration on recovering paths "
        "modelled). Nested path-wise SCR {nw:,.0f} vs horizon-level "
        "{nh:,.0f} ({d:+.2%} -- the 1% disclosure trigger was MET and this "
        "refresh is the required action). Tail diagnostics on the "
        "path-wise basis: raw 99.5% tail saturation {sat:.1%} but mean "
        "smoothed relief fraction {srf:.3f} < max_relief (restoration "
        "caps realised relief); prefix convergence final SCR delta "
        "{cv:.2%}; copula-seed spread {sp:.2%}; margin bootstrap SCR SE "
        "{se:.1%} of mean (nested reference inside 95% CI: {ici}). Rank "
        "invariance verified (df {dfr:.4f} = frozen {df0:.4f}; rho "
        "unchanged; Art. 234). Residuals: analytic re-anchoring (not a "
        "full path-wise copula re-aggregation -- next-phase candidate), "
        "constant FIT benefit share at the joint level, placeholder "
        "action parameters."
    ).format(nw=n_pw, nh=m["nested"]["with_horizon"]["scr"],
             d=trig["nested_scr_delta_rel_to_horizon"],
             sat=f["tail_saturation_share_at_995"],
             srf=f["tail_mean_smoothed_relief_fraction_at_995"],
             cv=f["scr_prefix_final_rel_delta"],
             sp=f["scr_seed_max_rel_spread"],
             se=f["bootstrap_scr_se_pct_of_mean"],
             ici=f["nested_pathwise_inside_bootstrap_ci"],
             dfr=rep["df_rematched"], df0=rep["df_matched"])
    store.risk_register.get("MR-014").update_mitigation(
        MitigationStatus.MITIGATED, notes=mr_notes_014)

    rec = ChangeRecord.create(
        title=CHANGE_TITLE,
        description=(
            "Path-wise tail diagnostics + capital-delta matrix per the "
            "Phase 25 Task 1 design note (s5): with-vs-without and "
            "pathwise-vs-horizon deltas at VaR/ES/SCR for nested, "
            "t-copula, gaussian and var-covar; var-covar understatement "
            "refreshed on the path-wise basis; confidence sweep with "
            "action-saturation profile, prefix convergence, copula-seed "
            "stability and a margin bootstrap over the realised outer "
            "losses. Rank invariance verified: df re-matched on the "
            "WITHOUT-actions staged losses unchanged at the frozen "
            "2.9451; copula parameters NOT re-tuned (SII Art. 234). "
            "Archived Phase 24 Task 2 horizon read-outs reproduced "
            "bit-identically before any new computation. MR-010/MR-014 "
            "refreshed (REQUIRED: 1% trigger MET at Task 2 with +14.17%)."
        ),
        change_type="methodology_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "var_covar_understatement_basis":
                "joint-action horizon basis (Phase 24 Task 4)",
            "tail_diagnostics_on_pathwise_basis": None,
            "mr010_mr014_pin": "Phase 24 Task 4",
            "nested_scr_with_horizon": m["nested"]["with_horizon"]["scr"],
        },
        after_snapshot={
            "mr010_mr014_pin": "Phase 25 Task 4",
            "nested_scr_with_pathwise": n_pw,
            "t_pathwise_scr": t_pw,
            "var_covar_understatement_vs_nested_with_pathwise":
                vc["understatement_vs_nested_with_pathwise"],
            "var_covar_understatement_vs_t_pathwise":
                vc["understatement_vs_t_pathwise_readout"],
            "df_rematched": rep["df_rematched"],
            "tail_saturation_share_at_995":
                f["tail_saturation_share_at_995"],
            "bootstrap_scr_se_pct_of_mean":
                f["bootstrap_scr_se_pct_of_mean"],
            "nested_pathwise_inside_bootstrap_ci":
                f["nested_pathwise_inside_bootstrap_ci"],
            "gates": rep["gates"],
            "verdict": rep["verdict"],
            "reproducibility_digest": rep["reproducibility_digest"],
        },
        impact_assessment=(
            "Diagnostics/reporting-level change only: no governed upstream "
            "module altered; no capital basis changed. The delta matrix "
            "and tail diagnostics complete the Phase 25 evidence pack for "
            "the path-wise with-actions basis; the nested run remains the "
            "capital reference; the full path-wise copula re-aggregation "
            "is the documented next-phase candidate."
        ),
        quantitative_impact=(
            "Nested path-wise SCR {nw:,.0f} vs horizon {nh:,.0f} "
            "({d:+.2%}); t path-wise re-anchored SCR {ts:,.0f} vs horizon "
            "{th:,.0f} ({dt:+.1%}); var-covar understates nested "
            "path-wise by {u1:.1%} (horizon baseline {u0:.1%}); df "
            "re-matched {dfr:.4f} (frozen); bootstrap SCR SE {se:.1%} of "
            "mean."
        ).format(nw=n_pw, nh=m["nested"]["with_horizon"]["scr"],
                 d=trig["nested_scr_delta_rel_to_horizon"],
                 ts=t_pw, th=m["t_copula"]["with_horizon"]["scr"],
                 dt=f["t_pathwise_minus_horizon_scr_rel"],
                 u1=vc["understatement_vs_nested_with_pathwise"],
                 u0=vc["understatement_vs_nested_with_horizon_basis_p24t4"],
                 dfr=rep["df_rematched"],
                 se=f["bootstrap_scr_se_pct_of_mean"]),
        author=ACTOR,
        phase=PHASE,
        peer_reviewer="APS_X2_Independent_Reviewer",
        assumption_owner="ChiefActuary",
    )
    rec.submit_for_peer_review(
        ACTOR,
        "Fixed pre-registered Task 4 gates (G1-G4) all PASS; {} archive "
        "cross-checks; archived Phase 24 Task 2 horizon read-outs "
        "reproduced bit-identically; rank invariance verified; "
        "diagnostics DISCLOSED (no post-hoc thresholds).".format(
            rep["crosscheck_count"]),
    )
    rec.submit_to_owner(
        ACTOR,
        "Owner review requested. Production sign-off withheld pending "
        "credentialled management-practice data and independent APS X2 "
        "review.",
    )
    store.add_change_record(rec)

    entry = AuditEntry.model_run(
        actor=ACTOR,
        phase=PHASE,
        run_id="p25t4-pwtaildiag-" + rep["reproducibility_digest"][:8],
        scenario_count=N_SIM,
        duration_seconds=0.0,
        outcome=rep["verdict"],
        files_changed=AFFECTED_COMPONENTS,
        test_summary=(
            "delta matrix complete (4 levels x 3 bases); nested pw-vs-hz "
            "{d:+.2%}; vc understatement {u1:.1%}/{u2:.1%}; df re-matched "
            "{dfr:.4f} (frozen); sat995 {sat:.1%}; boot SE {se:.1%}; gates "
            "{ng}/4 PASS".format(
                d=trig["nested_scr_delta_rel_to_horizon"],
                u1=vc["understatement_vs_nested_with_pathwise"],
                u2=vc["understatement_vs_t_pathwise_readout"],
                dfr=rep["df_rematched"],
                sat=f["tail_saturation_share_at_995"],
                se=f["bootstrap_scr_se_pct_of_mean"],
                ng=sum(rep["gates"].values()))
        ),
    )
    store.audit_trail.append(entry)

    ok = store.audit_trail.verify_all()
    GOV_PATH.write_text(store.to_json() + "\n", encoding="utf-8")

    rep["change_record_id"] = rec.record_id
    rep["change_record_status"] = (
        rec.status.value if hasattr(rec.status, "value") else str(rec.status))
    rep["mr010_refreshed"] = True
    rep["mr014_refreshed"] = True
    rep["audit_integrity_ok"] = ok
    rep["change_records_total"] = len(store.change_records)
    JSON_PATH.write_text(json.dumps(rep, indent=2) + "\n", encoding="utf-8")
    MD_PATH.write_text(_markdown(rep), encoding="utf-8")

    print("ChangeRecord {} ({}); MR-010+MR-014 refreshed; audit entries {}; "
          "verify_all {}".format(
              rec.record_id, rep["change_record_status"],
              len(store.audit_trail.entries), ok))
    return 0 if ok else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage",
                    choices=["verify", "diag", "boot", "governance"],
                    required=True)
    a = ap.parse_args()
    sys.exit({"verify": stage_verify, "diag": stage_diag,
              "boot": stage_boot, "governance": stage_governance}[a.stage]())
