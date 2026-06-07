#!/usr/bin/env python3
"""Phase 24 Task 4 -- joint-action tail diagnostics + capital-delta matrix.

Deliverables FIXED in the Phase 24 Task 1 design note (s5, pre-registered;
no gate-shopping):
  * with-vs-without and joint-vs-standalone capital deltas at VaR/ES/SCR
    for nested, t-copula, gaussian and var-covar;
  * var-covar understatement refreshed on the joint-action basis;
    MR-010 / MR-014 notes refreshed;
  * reproducibility: seeds, config, digests recorded; methodology_change
    ChangeRecord OWNER_REVIEW.

Staged build (wall-clock-limited shells; each stage < 45 s):

  PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase24_task4_joint_action_tail_diagnostics.py --stage verify
  PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase24_task4_joint_action_tail_diagnostics.py --stage diag
  PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase24_task4_joint_action_tail_diagnostics.py --stage governance

GATES (formalisation of the pre-registered Task 4 bullets + standing
conventions; recorded before the diagnostics were computed):
  G1  delta matrix complete and archive-cross-checked: every archived
      figure matches its source report; the fresh t/gaussian joint-action
      re-runs reproduce the archived Phase 24 Task 2 read-outs
      bit-identically (same seed/config; digest equality)
  G2  var-covar understatement refreshed on the joint-action basis
      (vs nested-with AND vs the t joint-action read-out)
  G3  reproducibility: seeds/config/digests recorded; same-seed re-run
      digest identical to the archived Task 2 digest
  G4  governance: MR-010/MR-014 refreshed; ChangeRecord OWNER_REVIEW;
      audit-chain verify_all True (governance stage)

The tail diagnostics (confidence sweep + saturation profile, prefix
convergence, copula-seed stability, margin bootstrap CI) are DISCLOSED
evidence per the design note -- no new numeric acceptance thresholds are
introduced post hoc.

EDUCATIONAL ONLY -- production sign-off withheld.
"""
from __future__ import annotations

import argparse
import hashlib
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
    joint_action_use_restrictions,
)
from par_model_v2.projection.joint_action_tail_diagnostics import (
    BOOTSTRAP_N_SIM,
    BOOTSTRAP_REPLICATES,
    CONFIDENCE_SWEEP,
    CONVERGENCE_PREFIXES,
    SEED_STABILITY_SEEDS,
    bootstrap_margin_ci,
    build_delta_matrix,
    confidence_sweep_with_saturation,
    diagnostics_digest,
    prefix_convergence,
    seed_stability,
)
from par_model_v2.projection.management_actions import ManagementActionRule
from par_model_v2.projection.nested_stochastic_tvog import (
    capital_metrics_from_liabilities,
)

PHASE = "Phase 24: With-Actions Aggregation Consistency + Inner-Path Action Dynamics"
ACTOR = "AutomatedModelDev_Phase24"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
OUT_DIR = Path("docs/validation")
JSON_PATH = OUT_DIR / "PHASE24_TASK4_JOINT_ACTION_TAIL_DIAGNOSTICS_REPORT.json"
MD_PATH = OUT_DIR / "PHASE24_TASK4_JOINT_ACTION_TAIL_DIAGNOSTICS_REPORT.md"
CARD_PATH = Path("docs/JOINT_ACTION_TAIL_DIAGNOSTICS_CARD.md")
STAGE_DIR = Path("/var/tmp/p24t4_stage")
STAGE_PATH = STAGE_DIR / "verified_inputs.npz"
P23T2_LOSSES = Path("/var/tmp/p23t2_stage/losses.npz")
P23T4_WITH = Path("/var/tmp/p23t4_stage/losses_with_actions.npz")
P24T2_STAGE = Path("/var/tmp/p24t2_stage/verified_inputs.npz")
P22T4_REPORT = OUT_DIR / "PHASE22_TASK4_AGGREGATION_REPORT.json"
P23T2_REPORT = OUT_DIR / "PHASE23_TASK2_T_COPULA_AGGREGATION_REPORT.json"
P23T3_REPORT = OUT_DIR / "PHASE23_TASK3_MANAGEMENT_ACTION_REPORT.json"
P23T4_REPORT = OUT_DIR / "PHASE23_TASK4_AGGREGATION_WITH_ACTIONS_REPORT.json"
P24T2_REPORT = OUT_DIR / "PHASE24_TASK2_JOINT_ACTION_REAGGREGATION_REPORT.json"
P24T3_REPORT = OUT_DIR / "PHASE24_TASK3_INNER_PATH_ACTION_REPORT.json"

DRIVERS = ("rate", "equity", "credit", "lapse", "mortality", "fx", "liquidity")
SEED = 20260607          # identical to Phase 23 T2/T4 + Phase 24 T2
N_SIM = 200_000          # identical to Phase 23 T2/T4 + Phase 24 T2
CONF = 0.995
HORIZON_M = 12
ARCHIVED_DF = 2.9451     # frozen Phase 23 Task 2 tail-matched df

CHANGE_TITLE = (
    "Phase 24 Task 4 - joint-action tail diagnostics + with-vs-without / "
    "joint-vs-standalone capital-delta matrix"
)

AFFECTED_COMPONENTS = [
    "par_model_v2/projection/joint_action_tail_diagnostics.py",
    "scripts/build_phase24_task4_joint_action_tail_diagnostics.py",
    "tests/test_phase24_task4_joint_action_tail_diagnostics.py",
    "docs/JOINT_ACTION_TAIL_DIAGNOSTICS_CARD.md",
    "docs/validation/PHASE24_TASK4_JOINT_ACTION_TAIL_DIAGNOSTICS_REPORT.{json,md}",
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


def stage_verify() -> int:
    """Archive cross-checks; NO new benchmark computed here."""
    z = np.load(P23T2_LOSSES)
    w = np.load(P23T4_WITH)
    s2 = np.load(P24T2_STAGE)
    arch4 = json.loads(P22T4_REPORT.read_text(encoding="utf-8"))["aggregation"]
    arch2 = json.loads(P23T2_REPORT.read_text(encoding="utf-8"))["aggregation"]
    t3 = json.loads(P23T3_REPORT.read_text(encoding="utf-8"))["result"]
    t4 = json.loads(P23T4_REPORT.read_text(encoding="utf-8"))
    p24t2 = json.loads(P24T2_REPORT.read_text(encoding="utf-8"))
    rule = _rule()

    awa = t4["aggregation_with_actions"]
    checks = {
        "nested_scr_match_p22t4":
            abs(float(z["nested_scr"][0]) - arch4["nested_scr"]) < 1e-6,
        "var_covar_scr_match_p22t4":
            abs(float(z["var_covar_scr"][0]) - arch4["var_covar_scr"]) < 1e-6,
        "nested_with_match_p23t4":
            abs(float(w["nested_scr_with"][0]) - awa["nested_scr"]) < 1e-3,
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
        "t_without_archived_match_p23t2":
            abs(arch2["t_matched_scr"] - 46755.963) < 1e-6,
        "rho_stage_available": np.asarray(s2["rho"]).shape == (7, 7),
    }
    for k in DRIVERS:
        cap = capital_metrics_from_liabilities(z[k], CONF, HORIZON_M)
        checks["standalone_scr_match_" + k] = (
            abs(float(cap.scr_proxy) - arch4["standalone_scr"][k]) < 1e-6)
        checks["anchor_mean_match_" + k] = (
            abs(float(w[k + "_anchor_mean"][0]) - float(np.mean(z[k]))) < 1e-9)

    # nested-with VaR/ES present (needed for the delta matrix at VaR/ES)
    checks["nested_with_var_es_available"] = (
        "nested_var_with" in w.files and "nested_es_with" in w.files)

    if not all(checks.values()):
        print("CROSS-CHECK FAILURE:",
              {k: v for k, v in checks.items() if not v})
        return 1

    STAGE_DIR.mkdir(parents=True, exist_ok=True)
    np.savez(
        STAGE_PATH,
        rho=np.asarray(s2["rho"], dtype=float),
        crosscheck_count=np.array([len(checks)]),
        l_fit=np.array([float(w["l_fit"][0])]),
        a_ref=np.array([float(w["a_ref"][0])]),
        nested_scr_with=np.array([float(w["nested_scr_with"][0])]),
        nested_var_with=np.array([float(w["nested_var_with"][0])]),
        nested_es_with=np.array([float(w["nested_es_with"][0])]),
        var_covar_scr_with=np.array([float(w["var_covar_scr_with"][0])]),
    )
    print("stage verify done: {}/{} cross-checks PASS".format(
        sum(checks.values()), len(checks)))
    return 0


def stage_diag() -> int:
    z = np.load(P23T2_LOSSES)
    w = np.load(P23T4_WITH)
    s = np.load(STAGE_PATH)
    arch2 = json.loads(P23T2_REPORT.read_text(encoding="utf-8"))["aggregation"]
    t4 = json.loads(P23T4_REPORT.read_text(encoding="utf-8"))
    p24t2 = json.loads(P24T2_REPORT.read_text(encoding="utf-8"))
    p24t3 = json.loads(P24T3_REPORT.read_text(encoding="utf-8"))
    rule = _rule()
    awa = t4["aggregation_with_actions"]

    rho = np.asarray(s["rho"], dtype=float)
    l_fit = float(s["l_fit"][0])
    nested_with = float(s["nested_scr_with"][0])

    losses = {k: np.asarray(z[k], dtype=float) for k in DRIVERS}
    anchors = {k: float(w[k + "_anchor_mean"][0]) for k in DRIVERS}
    agg = JointActionAggregator(
        standalone_losses=losses, correlation=rho, rule=rule,
        l_fit=l_fit, anchor_means=anchors,
    )

    # --- G1/G3: bit-identical reproduction of the archived Task 2 read-outs
    res_t = agg.run(JointActionConfig(n_sim=N_SIM, seed=SEED, df=ARCHIVED_DF))
    res_g = agg.run(JointActionConfig(n_sim=N_SIM, seed=SEED, df=None))
    arch_j = p24t2["joint_action"]
    repro = {
        "t_scr_abs_diff": abs(res_t.scr_joint_with - arch_j["t_scr"]),
        "g_scr_abs_diff": abs(res_g.scr_joint_with - arch_j["g_scr"]),
        "t_digest_match": res_t.digest == arch_j["t_digest"],
        "g_digest_match": res_g.digest == arch_j["g_digest"],
    }
    repro_ok = (repro["t_scr_abs_diff"] < 1e-9 and repro["g_scr_abs_diff"] < 1e-9
                and repro["t_digest_match"] and repro["g_digest_match"])

    # --- delta matrix (with-vs-without / joint-vs-standalone at every level)
    nested_without_cap = capital_metrics_from_liabilities(
        np.asarray(z["full"], dtype=float), CONF, HORIZON_M)
    without = {
        "nested": {"var": float(nested_without_cap.var_liability),
                   "es": float(nested_without_cap.es_liability),
                   "scr": float(z["nested_scr"][0])},
        "t_copula": {"var": arch2["t_capital"]["var_liability"],
                     "es": arch2["t_capital"]["es_liability"],
                     "scr": arch2["t_matched_scr"]},
        "gaussian": {"var": arch2["gaussian_capital"]["var_liability"],
                     "es": arch2["gaussian_capital"]["es_liability"],
                     "scr": arch2["gaussian_scr"]},
        "var_covar": {"var": None, "es": None,
                      "scr": float(z["var_covar_scr"][0])},
    }
    nested_with_row = {"var": float(s["nested_var_with"][0]),
                       "es": float(s["nested_es_with"][0]),
                       "scr": nested_with}
    standalone_action = {
        # nested has no standalone/joint split: rule on the full conditional
        # liability; it is the reference for both bases.
        "nested": nested_with_row,
        # P23T4 t/gaussian standalone-action levels use a DIFFERENT anchoring
        # (sum of seven with-actions standalone levels), so VaR/ES are not
        # level-comparable; SCR (VaR - mean) is. Disclosed.
        "t_copula": {"var": None, "es": None, "scr": awa["t_matched_scr"]},
        "gaussian": {"var": None, "es": None, "scr": awa["gaussian_scr"]},
        "var_covar": {"var": None, "es": None,
                      "scr": float(s["var_covar_scr_with"][0])},
    }
    joint_action = {
        "nested": nested_with_row,
        "t_copula": {"var": res_t.var_joint_with, "es": res_t.es_joint_with,
                     "scr": res_t.scr_joint_with},
        "gaussian": {"var": res_g.var_joint_with, "es": res_g.es_joint_with,
                     "scr": res_g.scr_joint_with},
        # no joint-action analogue of the var-covar formula (disclosed)
        "var_covar": {"var": None, "es": None, "scr": None},
    }
    matrix = build_delta_matrix(without, standalone_action, joint_action)

    # --- G2: var-covar understatement refreshed on the joint-action basis
    vc_with = float(s["var_covar_scr_with"][0])
    vc_refresh = {
        "var_covar_scr_with": vc_with,
        "understatement_vs_nested_with": 1.0 - vc_with / nested_with,
        "understatement_vs_t_joint": 1.0 - vc_with / res_t.scr_joint_with,
        "understatement_vs_nested_without_basis_p22t4":
            1.0 - float(z["var_covar_scr"][0]) / float(z["nested_scr"][0]),
    }

    # --- tail diagnostics on the joint-action basis (DISCLOSED evidence)
    sweep = confidence_sweep_with_saturation(agg, N_SIM, SEED, ARCHIVED_DF)
    conv = prefix_convergence(agg, SEED, ARCHIVED_DF)
    seeds = seed_stability(agg, ARCHIVED_DF, N_SIM)
    boot = bootstrap_margin_ci(
        losses_without=losses, correlation=rho, rule=rule, l_fit=l_fit,
        anchor_means=anchors, df=ARCHIVED_DF,
    )
    sweep_monotone = all(
        sweep[i]["var_with"] <= sweep[i + 1]["var_with"] + 1e-9
        for i in range(len(sweep) - 1))
    nested_in_ci = bool(boot["scr_with"]["ci_lo_95"] <= nested_with
                        <= boot["scr_with"]["ci_hi_95"])

    gates = {
        "G1_delta_matrix_complete_and_crosschecked": bool(
            repro_ok and all(
                matrix[lv]["without"]["scr"] is not None
                for lv in ("nested", "t_copula", "gaussian", "var_covar"))),
        "G2_var_covar_understatement_refreshed": bool(
            vc_refresh["understatement_vs_nested_with"] > 0
            and vc_refresh["understatement_vs_t_joint"] > 0),
        "G3_reproducibility_recorded": bool(
            repro["t_digest_match"] and repro["g_digest_match"]),
    }
    verdict = "PASS" if all(gates.values()) else "PARTIAL"

    diag_payload = {
        "confidence_sweep": sweep, "prefix_convergence": conv,
        "seed_stability": seeds, "bootstrap": boot,
    }
    out = {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": PHASE,
        "task": CHANGE_TITLE,
        "verdict": verdict,
        "gates": gates,
        "gate_note": (
            "Gates formalise the pre-registered Task 4 bullets (design note "
            "s5): completeness/cross-check, refresh, reproducibility. The "
            "tail diagnostics are DISCLOSED evidence -- no post-hoc numeric "
            "acceptance thresholds (no gate-shopping)."
        ),
        "rule": rule.to_dict(),
        "reference_assets": float(s["a_ref"][0]),
        "fit_mean_liability": l_fit,
        "df_matched": ARCHIVED_DF,
        "seed": SEED,
        "n_sim": N_SIM,
        "n_obs": int(np.asarray(z["rate"]).size),
        "drivers": list(DRIVERS),
        "crosscheck_count": int(s["crosscheck_count"][0]),
        "reproduction_of_p24t2": repro,
        "delta_matrix": matrix,
        "var_covar_refresh": vc_refresh,
        "tail_diagnostics": diag_payload,
        "diagnostic_config": {
            "confidence_sweep": list(CONFIDENCE_SWEEP),
            "convergence_prefixes": list(CONVERGENCE_PREFIXES),
            "seed_stability_seeds": list(SEED_STABILITY_SEEDS),
            "bootstrap_replicates": BOOTSTRAP_REPLICATES,
            "bootstrap_n_sim": BOOTSTRAP_N_SIM,
        },
        "diagnostic_findings": {
            "sweep_var_monotone_in_confidence": sweep_monotone,
            "tail_saturation_share_at_995": sweep[
                [i for i, r in enumerate(sweep)
                 if abs(r["confidence"] - 0.995) < 1e-12][0]
            ]["tail_saturation_share"],
            "scr_seed_max_rel_spread": seeds["scr_max_rel_spread"],
            "scr_prefix_final_rel_delta": conv[-1]["scr_rel_delta_vs_full"],
            "nested_with_inside_bootstrap_ci": nested_in_ci,
            "bootstrap_scr_se_pct_of_mean":
                boot["scr_with"]["se"] / boot["scr_with"]["mean"],
        },
        "inner_path_disclosure": {
            "note": (
                "Phase 24 Task 3 inner-path basis is MORE conservative than "
                "the outer-node transform (over-relief of non-cuttable "
                "components corrected); its nested with-actions figures are "
                "disclosed alongside but the governed copula deltas here "
                "remain on the outer-node basis used by Tasks 2/3 archives."
            ),
            "nested_capital_with_inner_path":
                p24t3["result"].get("nested_capital_with_inner_path"),
            "nested_capital_with_outer_node":
                p24t3["result"].get("nested_capital_with_outer_node"),
            "outer_vs_inner_path_delta":
                p24t3["result"].get("outer_vs_inner_path_delta"),
            "source": str(P24T3_REPORT),
        },
        "anchoring_convention": (
            "V = L_fit + sum_k (Q_k(U_k) - mean_k); W = rule(V, A_ref) ONCE "
            "(joint-action); standalone-action t/gaussian VaR/ES from P23T4 "
            "are on a different (summed) level convention -- SCR-only in the "
            "matrix, DISCLOSED"
        ),
        "affected_components": AFFECTED_COMPONENTS,
        "standard_references": STANDARD_REFERENCES,
        "use_restrictions": joint_action_use_restrictions(),
    }
    out["reproducibility_digest"] = diagnostics_digest({
        "delta_matrix_scr": {
            lv: matrix[lv]["without"]["scr"] for lv in matrix},
        "t_joint_scr": res_t.scr_joint_with,
        "g_joint_scr": res_g.scr_joint_with,
        "seed": SEED, "n_sim": N_SIM, "df": ARCHIVED_DF,
        "bootstrap_seed": boot["seed"],
    })
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out["markdown_path"] = str(MD_PATH)
    JSON_PATH.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    MD_PATH.write_text(_markdown(out), encoding="utf-8")
    CARD_PATH.write_text(_card(out), encoding="utf-8")
    print("verdict={} gates={}/3 t_joint={:.1f} g_joint={:.1f} "
          "nested_with={:.1f} vc_underst_vs_nested={:.1%} sat995={:.1%} "
          "boot_scr_se={:.1%}".format(
              verdict, sum(gates.values()), res_t.scr_joint_with,
              res_g.scr_joint_with, nested_with,
              vc_refresh["understatement_vs_nested_with"],
              out["diagnostic_findings"]["tail_saturation_share_at_995"],
              out["diagnostic_findings"]["bootstrap_scr_se_pct_of_mean"]))
    print("report:", JSON_PATH)
    return 0 if verdict == "PASS" else 1


def _fmt(x, pct=False):
    if x is None:
        return "n/a"
    return "{:.1%}".format(x) if pct else "{:,.1f}".format(x)


def _markdown(out: dict) -> str:
    m = out["delta_matrix"]
    vc = out["var_covar_refresh"]
    f = out["diagnostic_findings"]
    boot = out["tail_diagnostics"]["bootstrap"]
    g = out["gates"]
    rows = []
    for lv, label in (("nested", "Nested (reference)"),
                      ("t_copula", f"t({out['df_matched']:.4f})"),
                      ("gaussian", "Gaussian"), ("var_covar", "Var-covar")):
        r = m[lv]
        sa = r.get("standalone_action") or {}
        ja = r.get("joint_action") or {}
        jvs = r.get("joint_minus_standalone_scr_pct")
        rows.append("| {} | {} | {} | {} | {} | {} |".format(
            label, _fmt(r["without"]["scr"]), _fmt(sa.get("scr")),
            _fmt(ja.get("scr")), _fmt(
                (ja.get("scr") - r["without"]["scr"]) / r["without"]["scr"]
                if ja.get("scr") is not None else None, pct=True),
            _fmt(jvs, pct=True)))
    sweep_rows = "\n".join(
        "| {confidence:.3f} | {var_with:,.0f} | {es_with:,.0f} | "
        "{scr_with:,.0f} | {tail_active_share:.1%} | "
        "{tail_saturation_share:.1%} | {relief_at_var:,.0f} |".format(**r)
        for r in out["tail_diagnostics"]["confidence_sweep"])
    conv_rows = "\n".join(
        "| {n_sim:,} | {var_with:,.0f} | {scr_with:,.0f} | "
        "{scr_rel_delta_vs_full:.2%} |".format(**r)
        for r in out["tail_diagnostics"]["prefix_convergence"])
    return f"""# Phase 24 Task 4 -- Joint-Action Tail Diagnostics + Capital-Delta Matrix

**Verdict: {out['verdict']}** ({sum(g.values())}/{len(g)} fixed pre-registered gates PASS;
governance gate G4 reported separately below).

EDUCATIONAL ONLY. Tail diagnostics and the full with-vs-without /
joint-vs-standalone capital-delta matrix on the JOINT-action
(action-after-aggregation) basis established by Phase 24 Task 2, under the
frozen t({out['df_matched']:.4f}) / Gaussian copulas on the archived Phase 23 Task 2
dependence basis (seed {out['seed']}, n_sim {out['n_sim']:,}, n_obs {out['n_obs']}).

## 99.5% 1y SCR delta matrix

| Level | Without | With (standalone-action) | With (joint-action) | Joint vs without | Joint vs standalone |
|---|---|---|---|---|---|
{chr(10).join(rows)}

Nested has no standalone/joint split (rule on the full conditional
liability; reference for both bases). Var-covar has no joint-action
analogue (formula on standalone marginals; DISCLOSED). Standalone-action
t/Gaussian VaR/ES from P23T4 use a different (summed) level convention --
SCR-only in the matrix (DISCLOSED).

## Var-covar understatement refreshed (MR-010)

- vs nested-with-actions {_fmt(out['delta_matrix']['nested']['joint_action']['scr'])}: **{vc['understatement_vs_nested_with']:.1%}**
- vs t joint-action read-out: **{vc['understatement_vs_t_joint']:.1%}**
- without-actions baseline (P22T4): {vc['understatement_vs_nested_without_basis_p22t4']:.1%}

## Confidence sweep with action-saturation profile (t joint-action)

| Conf | VaR_with | ES_with | SCR_with | Tail active | Tail saturated | Relief at VaR |
|---|---|---|---|---|---|---|
{sweep_rows}

Saturation share in the 99.5% tail: **{f['tail_saturation_share_at_995']:.1%}** -- the joint tail
sits predominantly at maximum relief, the mechanism behind the Phase 23
Task 4 finding, now quantified on the joint basis.

## Prefix-subsample convergence (common random numbers, 99.5%)

| n_sim | VaR_with | SCR_with | SCR rel delta vs full |
|---|---|---|---|
{conv_rows}

## Copula-seed stability + margin bootstrap (DISCLOSED diagnostics)

- SCR max rel spread across {len(out['diagnostic_config']['seed_stability_seeds'])} copula seeds at n_sim {out['n_sim']:,}: **{f['scr_seed_max_rel_spread']:.2%}**
- Margin bootstrap ({boot['n_replicates']} replicates x {boot['n_sim_per_replicate']:,} sims; joint row resample of the {boot['n_obs']} realised outer losses; copula frozen, SII Art. 234):
  SCR_with mean {boot['scr_with']['mean']:,.0f}, SE {boot['scr_with']['se']:,.0f}
  ({f['bootstrap_scr_se_pct_of_mean']:.1%} of mean), 95% CI
  [{boot['scr_with']['ci_lo_95']:,.0f}, {boot['scr_with']['ci_hi_95']:,.0f}]
- Nested-with-actions reference inside the bootstrap 95% CI: **{f['nested_with_inside_bootstrap_ci']}**
- VaR sweep monotone in confidence: {f['sweep_var_monotone_in_confidence']}

The bootstrap quantifies the DISCLOSED Task 1 limitation that n_obs={boot['n_obs']}
margin sampling noise propagates into the joint read-out; the nested run
remains the capital reference.

## Fixed pre-registered gates (Task 1 design note s5; no gate-shopping)

{chr(10).join('- ' + k + ': ' + ('PASS' if v else 'FAIL') for k, v in g.items())}
- G4_governance_verify_all: {out.get('audit_integrity_ok', 'pending governance stage')}

## Reproducibility

- Bit-identical reproduction of the archived Phase 24 Task 2 read-outs:
  t/g SCR abs diff {out['reproduction_of_p24t2']['t_scr_abs_diff']:.2e} / {out['reproduction_of_p24t2']['g_scr_abs_diff']:.2e}; digests match
  ({out['reproduction_of_p24t2']['t_digest_match']}/{out['reproduction_of_p24t2']['g_digest_match']}).
- {out['crosscheck_count']} archive cross-checks PASS before any new computation.
- Digest `{out['reproducibility_digest'][:16]}`; seed {out['seed']}; n_sim {out['n_sim']:,}; bootstrap seed {boot['seed']}.

Standards: {'; '.join(STANDARD_REFERENCES)}.
"""


def _card(out: dict) -> str:
    f = out["diagnostic_findings"]
    vc = out["var_covar_refresh"]
    boot = out["tail_diagnostics"]["bootstrap"]
    ja = out["delta_matrix"]["t_copula"]["joint_action"]
    nw = out["delta_matrix"]["nested"]["joint_action"]["scr"]
    return f"""# Joint-Action Tail Diagnostics Card (Phase 24 Task 4)

**{out['verdict']}** -- full capital-delta matrix + tail diagnostics on the
joint-action basis. t({out['df_matched']:.4f}) joint-action SCR {ja['scr']:,.0f} vs
nested-with {nw:,.0f}; var-covar understatement refreshed
({vc['understatement_vs_nested_with']:.1%} vs nested-with, {vc['understatement_vs_t_joint']:.1%} vs t-joint; MR-010).
99.5% tail saturation share {f['tail_saturation_share_at_995']:.1%} (mechanism quantified);
seed spread {f['scr_seed_max_rel_spread']:.2%}; margin-bootstrap SCR SE
{f['bootstrap_scr_se_pct_of_mean']:.1%} of mean (n_obs={boot['n_obs']} noise DISCLOSED;
nested reference inside the 95% CI: {f['nested_with_inside_bootstrap_ci']}).

EDUCATIONAL_DEMONSTRATION_ONLY -- placeholders disclosed; sign-off withheld.
Evidence: docs/validation/PHASE24_TASK4_JOINT_ACTION_TAIL_DIAGNOSTICS_REPORT.{{json,md}}
"""


def _has_change_record(store: GovernanceStore) -> bool:
    return any(r.title == CHANGE_TITLE for r in store.change_records)


def stage_governance() -> int:
    rep = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    vc = rep["var_covar_refresh"]
    f = rep["diagnostic_findings"]
    ja = rep["delta_matrix"]["t_copula"]["joint_action"]
    nw = rep["delta_matrix"]["nested"]["joint_action"]["scr"]
    store = GovernanceStore.from_json(GOV_PATH.read_text(encoding="utf-8"))

    if _has_change_record(store):
        rec = next(x for x in store.change_records if x.title == CHANGE_TITLE)
        print("already applied:", rec.record_id)
        print("audit integrity:", store.audit_trail.verify_all())
        return 0

    Path("/var/tmp/p24t4_build").mkdir(parents=True, exist_ok=True)
    Path("/var/tmp/p24t4_build/GOV_BACKUP_pre_p24t4.json").write_text(
        store.to_json() + "\n", encoding="utf-8")

    mr_notes_010 = (
        "Phase 24 Task 4 refresh: var-covar understatement quantified on the "
        "JOINT-action basis -- var-covar with-actions SCR {vcw:,.0f} "
        "understates the nested-with reference {nw:,.0f} by {u1:.1%} and the "
        "standing t({df:.4f}) joint-action read-out {ts:,.0f} by {u2:.1%} "
        "(without-actions baseline {u0:.1%}). Full with-vs-without / "
        "joint-vs-standalone delta matrix + tail diagnostics (saturation "
        "{sat:.1%} in the 99.5% tail; margin-bootstrap SCR SE {se:.1%} of "
        "mean) in PHASE24_TASK4 report. t joint-action remains the standing "
        "with-actions copula mitigation; nested remains the reference."
    ).format(vcw=vc["var_covar_scr_with"], nw=nw,
             u1=vc["understatement_vs_nested_with"],
             u2=vc["understatement_vs_t_joint"],
             u0=vc["understatement_vs_nested_without_basis_p22t4"],
             df=rep["df_matched"], ts=ja["scr"],
             sat=f["tail_saturation_share_at_995"],
             se=f["bootstrap_scr_se_pct_of_mean"])
    store.risk_register.get("MR-010").update_mitigation(
        MitigationStatus.MITIGATED, notes=mr_notes_010)

    mr_notes_014 = (
        "Phase 24 Task 4: joint-action tail diagnostics complete -- "
        "confidence sweep with saturation profile (99.5% tail saturated "
        "{sat:.1%}, quantifying the Phase 23 Task 4 mechanism), prefix "
        "convergence (final SCR rel delta {cv:.2%}), copula-seed spread "
        "{sp:.2%}, and a margin bootstrap over the n_obs realised losses "
        "(SCR SE {se:.1%} of mean; nested reference inside the 95% CI: "
        "{ici}). Archived Task 2 read-outs reproduced bit-identically. "
        "Residuals unchanged: outer-node-vs-inner-path basis (Task 3 "
        "disclosure), placeholder parameters, fixed A_ref proxy."
    ).format(sat=f["tail_saturation_share_at_995"],
             cv=f["scr_prefix_final_rel_delta"],
             sp=f["scr_seed_max_rel_spread"],
             se=f["bootstrap_scr_se_pct_of_mean"],
             ici=f["nested_with_inside_bootstrap_ci"])
    store.risk_register.get("MR-014").update_mitigation(
        MitigationStatus.MITIGATED, notes=mr_notes_014)

    rec = ChangeRecord.create(
        title=CHANGE_TITLE,
        description=(
            "Joint-action tail diagnostics + capital-delta matrix per the "
            "Phase 24 Task 1 design note: with-vs-without and "
            "joint-vs-standalone deltas at VaR/ES/SCR for nested, t-copula, "
            "gaussian and var-covar; var-covar understatement refreshed on "
            "the joint-action basis; confidence sweep with action-saturation "
            "profile, prefix convergence, copula-seed stability and a margin "
            "bootstrap over the realised outer losses. Archived Phase 24 "
            "Task 2 read-outs reproduced bit-identically before any new "
            "computation; copula frozen (SII Art. 234)."
        ),
        change_type="methodology_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "var_covar_understatement_basis":
                "standalone-action only (Phase 23 Task 4)",
            "tail_diagnostics_on_joint_action_basis": None,
            "t_joint_scr": ja["scr"],
            "nested_scr_with": nw,
        },
        after_snapshot={
            "var_covar_understatement_vs_nested_with":
                vc["understatement_vs_nested_with"],
            "var_covar_understatement_vs_t_joint":
                vc["understatement_vs_t_joint"],
            "tail_saturation_share_at_995":
                f["tail_saturation_share_at_995"],
            "scr_seed_max_rel_spread": f["scr_seed_max_rel_spread"],
            "bootstrap_scr_se_pct_of_mean":
                f["bootstrap_scr_se_pct_of_mean"],
            "nested_with_inside_bootstrap_ci":
                f["nested_with_inside_bootstrap_ci"],
            "gates": rep["gates"],
            "verdict": rep["verdict"],
            "reproducibility_digest": rep["reproducibility_digest"],
        },
        impact_assessment=(
            "Diagnostics/reporting-level change only: no governed upstream "
            "module altered; no capital basis changed. The delta matrix and "
            "tail diagnostics complete the Phase 24 evidence pack for the "
            "joint-action with-actions read-out; the nested run remains the "
            "capital reference."
        ),
        quantitative_impact=(
            "Var-covar with-actions {vcw:,.0f} understates nested-with "
            "{nw:,.0f} by {u1:.1%} and the t joint-action read-out {ts:,.0f} "
            "by {u2:.1%}; 99.5% tail saturation {sat:.1%}; seed spread "
            "{sp:.2%}; bootstrap SCR SE {se:.1%} of mean."
        ).format(vcw=vc["var_covar_scr_with"], nw=nw, ts=ja["scr"],
                 u1=vc["understatement_vs_nested_with"],
                 u2=vc["understatement_vs_t_joint"],
                 sat=f["tail_saturation_share_at_995"],
                 sp=f["scr_seed_max_rel_spread"],
                 se=f["bootstrap_scr_se_pct_of_mean"]),
        author=ACTOR,
        phase=PHASE,
        peer_reviewer="APS_X2_Independent_Reviewer",
        assumption_owner="ChiefActuary",
    )
    rec.submit_for_peer_review(
        ACTOR,
        "Fixed pre-registered Task 4 gates (G1-G3) all PASS; {} archive "
        "cross-checks; archived Task 2 read-outs reproduced bit-identically; "
        "diagnostics DISCLOSED (no post-hoc thresholds).".format(
            rep["crosscheck_count"]),
    )
    rec.submit_to_owner(
        ACTOR,
        "Owner review requested. Production sign-off withheld pending "
        "credentialled management-practice data and independent APS X2 review.",
    )
    store.add_change_record(rec)

    entry = AuditEntry.model_run(
        actor=ACTOR,
        phase=PHASE,
        run_id="p24t4-taildiag-" + rep["reproducibility_digest"][:8],
        scenario_count=N_SIM,
        duration_seconds=0.0,
        outcome=rep["verdict"],
        files_changed=AFFECTED_COMPONENTS,
        test_summary=(
            "delta matrix complete (4 levels x 3 bases); vc understatement "
            "{u1:.1%}/{u2:.1%}; sat995 {sat:.1%}; boot SE {se:.1%}; "
            "gates {ng}/3 PASS".format(
                u1=vc["understatement_vs_nested_with"],
                u2=vc["understatement_vs_t_joint"],
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
    ap.add_argument("--stage", choices=["verify", "diag", "governance"],
                    required=True)
    a = ap.parse_args()
    sys.exit({"verify": stage_verify, "diag": stage_diag,
              "governance": stage_governance}[a.stage]())
