#!/usr/bin/env python3
"""Phase 25 Task 3 build + governance - matching path-wise proxy basis + OOS.

The LSMC proxy gains the matching analytic post-composition action basis so
truth and proxy share an IDENTICAL path-wise action basis (the G1 convention):
the smoothed-relief response surface relieved_hat = alpha * phi_sigma(CR_hat)
* clip(B_hat, 0, L_hat), with (sigma, alpha) calibrated on the FIT sample
ONLY (leakage-free), candidate (b) of the pre-registered Phase 25 Task 1
design note s5; the zero-shock expected-path candidate (a) is evaluated and
its rejection DISCLOSED.  Seven-driver OOS re-validation at the UNCHANGED
Phase 22 gates (R^2 >= 0.95, VaR rel err <= 10%).

The truth-side per-node path-wise relieved amounts on the FIT and VALIDATION
samples are produced by BIT-IDENTICAL re-runs of the archived Phase 22
Task 2 inner paths (exact equality of total/benefit/credit vs the archived
Phase 24 Task 3 decomposition enforced at every slice).  The nested-eval
truth relieved amounts are the archived Phase 25 Task 2 stage (digest-
verified before use).

Run staged (each stage < 45 s):
  PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase25_task3_pathwise_proxy_basis.py --stage verify
  ... --stage pwfit --i0 0    --i1 500
  ... --stage pwfit --i0 500  --i1 1000
  ... --stage pwfit --i0 1000 --i1 1500
  ... --stage pwfit --i0 1500 --i1 2000
  ... --stage pwval
  ... --stage det --part fit_a
  ... --stage det --part fit_b
  ... --stage det --part valeval
  ... --stage actions
  ... --stage governance
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import numpy as np

from par_model_v2.governance.audit_trail import (
    AuditEntry,
    ChangeRecord,
    GovernanceStore,
)
from par_model_v2.projection.inner_path_action_dynamics import (
    pathwise_declaration_heavy_sliced,
)
from par_model_v2.projection.management_actions import ManagementActionRule
from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.multi_driver_proxy_validation_7d import (
    SevenDriverLiquidityProxyValidator,
    seven_driver_proxy_config,
)
from par_model_v2.projection.pathwise_bonus_dynamics import (
    PATHWISE_OOS_R2_GATE,
    PATHWISE_VAR_REL_ERROR_GATE,
)
from par_model_v2.projection.pathwise_proxy_basis import (
    calibrate_pathwise_level_factor,
    calibrate_pathwise_response_surface,
    deterministic_pathwise_relieved,
    pathwise_declaration_fit_sliced,
    pathwise_proxy_basis_use_restrictions,
    smoothed_relief_response,
    validate_pathwise_proxy_basis,
)

PHASE = "Phase 25: Path-Wise Bonus Declaration Dynamics"
ACTOR = "AutomatedModelDev_Phase25"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
OUT_DIR = Path("docs/validation")
JSON_PATH = OUT_DIR / "PHASE25_TASK3_PATHWISE_PROXY_BASIS_REPORT.json"
MD_PATH = OUT_DIR / "PHASE25_TASK3_PATHWISE_PROXY_BASIS_REPORT.md"
CARD_PATH = Path("docs/PATHWISE_PROXY_BASIS_CARD.md")
P23T3_ARRAYS = Path("/var/tmp/p23t3_stage/arrays.npz")
P24T3_STAGE = Path("/var/tmp/p24t3_stage")
P25T2_STAGE = Path("/var/tmp/p25t2_stage")
P25T2_REPORT = OUT_DIR / "PHASE25_TASK2_PATHWISE_DECLARATION_REPORT.json"
P25T1_NOTE = OUT_DIR / "PHASE25_TASK1_DESIGN_NOTE.json"
STAGE_DIR = Path("/var/tmp/p25t3_stage")
VERIFY_PATH = STAGE_DIR / "verify.json"

CHANGE_TITLE = (
    "Phase 25 Task 3 - matching path-wise proxy basis feature "
    "(smoothed-relief response surface) + seven-driver OOS re-validation"
)

AFFECTED_COMPONENTS = [
    "par_model_v2/projection/pathwise_proxy_basis.py",
    "tests/test_phase25_task3_pathwise_proxy_basis.py",
    "scripts/build_phase25_task3_pathwise_proxy_basis.py",
    "docs/PATHWISE_PROXY_BASIS_CARD.md",
    "docs/validation/PHASE25_TASK3_PATHWISE_PROXY_BASIS_REPORT.{json,md}",
]

STANDARD_REFERENCES = [
    "Solvency II Delegated Regulation Article 23 (management actions "
    "modelled consistently in valuation and capital bases)",
    "Solvency II Delegated Regulation Article 234 (no silent copula/proxy "
    "re-tuning; identical action basis convention)",
    "SOA ASOP 56 section 3.1.3/3.4 (consistency of modelled management "
    "behaviour across model components)",
    "IA TAS M section 3.2/3.6 (quantified, reproducible proxy evidence)",
    "IFoA proxy-modelling working party (analytic post-composition features)",
    "Phase 25 Task 1 design note s5 (fixed pre-registered gates)",
]


def _product() -> ParEndowmentProduct:
    return ParEndowmentProduct(
        issue_age=45, gender="M", sum_assured=100000.0,
        annual_premium=5000.0, term_years=20)


def _validator() -> SevenDriverLiquidityProxyValidator:
    return SevenDriverLiquidityProxyValidator(_product())


def _assemble_comp(part: str, n: int) -> Dict[str, np.ndarray]:
    out = {k: np.full(n, np.nan) for k in ("total", "benefit", "credit")}
    for f in sorted(P24T3_STAGE.glob("comp_%s_*.npz" % part)):
        i0, i1 = (int(x) for x in f.stem.split("_")[-2:])
        d = np.load(f)
        for k in out:
            out[k][i0:i1] = d[k]
    for k in out:
        if np.isnan(out[k]).any():
            raise RuntimeError("P24T3 component slices for %s incomplete" % part)
    return out


def _assemble_p25t2_pw(n: int) -> Dict[str, np.ndarray]:
    keys = ("total", "benefit", "credit", "relieved_pathwise",
            "relieved_horizon", "action_share", "restoration_share",
            "cr_path0_mean")
    out = {k: np.full(n, np.nan) for k in keys}
    for f in sorted(P25T2_STAGE.glob("pw_*.npz")):
        i0, i1 = (int(x) for x in f.stem.split("_")[-2:])
        d = np.load(f)
        for k in keys:
            out[k][i0:i1] = d[k]
    for k in keys:
        if np.isnan(out[k]).any():
            raise RuntimeError("P25T2 pathwise slices incomplete")
    return out


def _p25t2_digest(pw: Dict[str, np.ndarray], nested_l: np.ndarray,
                  rule: ManagementActionRule) -> str:
    arrs = {"nested_l": nested_l, "benefit": pw["benefit"],
            "relieved_pathwise": pw["relieved_pathwise"],
            "relieved_horizon": pw["relieved_horizon"]}
    h = hashlib.sha256()
    for k in sorted(arrs):
        h.update(k.encode())
        h.update(np.ascontiguousarray(arrs[k]).tobytes())
    h.update(json.dumps(rule.to_dict(), sort_keys=True).encode())
    return h.hexdigest()


def stage_verify() -> int:
    """Archive cross-checks BEFORE any new computation."""
    t0 = time.monotonic()
    STAGE_DIR.mkdir(parents=True, exist_ok=True)
    cfg = seven_driver_proxy_config()
    v = _validator()
    rule = ManagementActionRule()

    data = np.load(P23T3_ARRAYS)
    nested_l = data["nested_l"]
    fit_mean = float(data["fit_mean"][0])
    a_ref = rule.reference_assets(fit_mean)

    p25t2 = json.loads(P25T2_REPORT.read_text(encoding="utf-8"))
    p25t1 = json.loads(P25T1_NOTE.read_text(encoding="utf-8"))
    pw = _assemble_p25t2_pw(cfg.n_eval)
    comp_fit = _assemble_comp("fit", cfg.n_fit)
    comp_val = _assemble_comp("val", cfg.n_validation)
    comp_nested = _assemble_comp("nested", cfg.n_eval)

    fit_X = v.states(cfg.n_fit, cfg.fit_seed)
    val_X = v.states(cfg.n_validation, cfg.validation_seed)
    eval_X = v.states(cfg.n_eval, cfg.eval_seed)
    fit_offsets = v.fx_term(fit_X) + v.liquidity_term(fit_X)
    val_offsets = v.fx_term(val_X) + v.liquidity_term(val_X)
    eval_offsets = v.fx_term(eval_X) + v.liquidity_term(eval_X)

    fit_l7 = comp_fit["total"] + fit_offsets
    val_l7 = comp_val["total"] + val_offsets
    nested_l7 = comp_nested["total"] + eval_offsets
    fit_hz = rule.relief_fraction(rule.coverage_ratio(fit_l7, a_ref))
    val_hz = rule.relief_fraction(rule.coverage_ratio(val_l7, a_ref))

    checks = {
        "p25t2_verdict_pass": p25t2["verdict"] == "PASS",
        "p25t2_rule_unchanged": p25t2["result"]["rule"] == rule.to_dict(),
        "p25t2_digest_match": (
            _p25t2_digest(pw, nested_l, rule)
            == p25t2["reproducibility_digest"]),
        "p25t1_task3_gates_pre_registered": bool(
            p25t1.get("task3_acceptance_criteria")),
        "nested_l7_consistent": bool(
            np.allclose(nested_l7, nested_l, rtol=0, atol=1e-6)),
        "fit_mean_match": abs(fit_mean - float(fit_l7.mean())) <= 1e-6,
        "p24t3_fit_components_complete": len(comp_fit["total"]) == cfg.n_fit,
        "p24t3_val_components_complete": (
            len(comp_val["total"]) == cfg.n_validation),
        "p25t2_scr_reference_match": abs(
            p25t2["result"]["nested_capital_with_pathwise"]["scr_proxy"]
            - 46638.8659) < 1e-3,
        "gates_unchanged_phase22": (
            PATHWISE_OOS_R2_GATE == 0.95
            and PATHWISE_VAR_REL_ERROR_GATE == 0.10),
    }
    if not all(checks.values()):
        raise RuntimeError("verify failed: " + json.dumps(checks))
    np.savez(STAGE_DIR / "inputs.npz",
             fit_offsets=fit_offsets, val_offsets=val_offsets,
             eval_offsets=eval_offsets, fit_hz=fit_hz, val_hz=val_hz,
             fit_l7=fit_l7, val_l7=val_l7)
    VERIFY_PATH.write_text(json.dumps({
        "checks": checks,
        "fit_mean_liability": fit_mean,
        "reference_assets": a_ref,
        "p25t2_nested_scr_with_pathwise": p25t2["result"][
            "nested_capital_with_pathwise"]["scr_proxy"],
        "p25t2_nested_var_with_pathwise": p25t2["result"][
            "nested_capital_with_pathwise"]["var_liability"],
        "config": cfg.to_dict(),
        "duration_seconds": time.monotonic() - t0,
    }, indent=2) + "\n", encoding="utf-8")
    print("verify OK:", json.dumps(checks))
    return 0


def stage_pwfit(i0: int, i1: int) -> int:
    """Truth path-wise declaration on FIT nodes [i0, i1); without-actions
    components exact-equality checked vs the archived P24T3 decomposition."""
    t0 = time.monotonic()
    if not VERIFY_PATH.exists():
        raise RuntimeError("run --stage verify first")
    verify = json.loads(VERIFY_PATH.read_text(encoding="utf-8"))
    cfg = seven_driver_proxy_config()
    if not (0 <= i0 < i1 <= cfg.n_fit):
        raise ValueError("bad slice")
    v = _validator()
    rule = ManagementActionRule()
    inputs = np.load(STAGE_DIR / "inputs.npz")
    fit_X = v.states(cfg.n_fit, cfg.fit_seed)

    res = pathwise_declaration_fit_sliced(
        v, fit_X, i0, i1, cfg.fit_seed, cfg.fit_n_inner,
        rule, float(verify["reference_assets"]),
        inputs["fit_offsets"], inputs["fit_hz"])

    comp = _assemble_comp("fit", cfg.n_fit)
    for k in ("total", "benefit", "credit"):
        if not np.array_equal(res[k], comp[k][i0:i1]):
            raise RuntimeError(
                "without-actions %s NOT bit-identical to archive "
                "(fit slice [%d,%d), maxdiff=%g)" % (
                    k, i0, i1,
                    float(np.max(np.abs(res[k] - comp[k][i0:i1])))))
    np.savez(STAGE_DIR / ("pwfit_%05d_%05d.npz" % (i0, i1)), **res)
    print("pwfit [%d,%d) OK bit-identical; %.1fs"
          % (i0, i1, time.monotonic() - t0))
    return 0


def stage_pwval() -> int:
    """Truth path-wise declaration on the VALIDATION nodes (heavy inner);
    without-actions components exact-equality checked vs the archive."""
    t0 = time.monotonic()
    if not VERIFY_PATH.exists():
        raise RuntimeError("run --stage verify first")
    verify = json.loads(VERIFY_PATH.read_text(encoding="utf-8"))
    cfg = seven_driver_proxy_config()
    v = _validator()
    rule = ManagementActionRule()
    inputs = np.load(STAGE_DIR / "inputs.npz")
    val_X = v.states(cfg.n_validation, cfg.validation_seed)

    res = pathwise_declaration_heavy_sliced(
        v, val_X, 0, cfg.n_validation, cfg.n_inner_heavy,
        cfg.validation_seed, rule, float(verify["reference_assets"]),
        inputs["val_offsets"], inputs["val_hz"])

    comp = _assemble_comp("val", cfg.n_validation)
    for k in ("total", "benefit", "credit"):
        if not np.array_equal(res[k], comp[k]):
            raise RuntimeError(
                "without-actions %s NOT bit-identical to archive (val, "
                "maxdiff=%g)" % (
                    k, float(np.max(np.abs(res[k] - comp[k])))))
    np.savez(STAGE_DIR / "pwval.npz", **res)
    print("pwval OK bit-identical; %.1fs" % (time.monotonic() - t0))
    return 0


def stage_det(part: str) -> int:
    """Cache the zero-shock deterministic relieved amounts (candidate (a)
    + cadence sensitivity); heavy enough to stage per part."""
    t0 = time.monotonic()
    if not VERIFY_PATH.exists():
        raise RuntimeError("run --stage verify first")
    verify = json.loads(VERIFY_PATH.read_text(encoding="utf-8"))
    a_ref = float(verify["reference_assets"])
    cfg = seven_driver_proxy_config()
    v = _validator()
    rule = ManagementActionRule()
    inputs = np.load(STAGE_DIR / "inputs.npz")
    if part == "fit_a":
        X = v.states(cfg.n_fit, cfg.fit_seed)
        np.savez(STAGE_DIR / "det_fit_a.npz",
                 arr=deterministic_pathwise_relieved(
                     v, X[:1000], rule, a_ref, inputs["fit_offsets"][:1000]))
    elif part == "fit_b":
        X = v.states(cfg.n_fit, cfg.fit_seed)
        np.savez(STAGE_DIR / "det_fit_b.npz",
                 arr=deterministic_pathwise_relieved(
                     v, X[1000:], rule, a_ref, inputs["fit_offsets"][1000:]))
    elif part == "valeval":
        val_X = v.states(cfg.n_validation, cfg.validation_seed)
        eval_X = v.states(cfg.n_eval, cfg.eval_seed)
        np.savez(
            STAGE_DIR / "det_valeval.npz",
            val=deterministic_pathwise_relieved(
                v, val_X, rule, a_ref, inputs["val_offsets"]),
            eval=deterministic_pathwise_relieved(
                v, eval_X, rule, a_ref, inputs["eval_offsets"]),
            eval_annual=deterministic_pathwise_relieved(
                v, eval_X, rule, a_ref, inputs["eval_offsets"],
                cadence_months=12),
        )
    else:
        raise ValueError("part must be fit_a / fit_b / valeval")
    print("det %s OK; %.1fs" % (part, time.monotonic() - t0))
    return 0


def _assemble_pwfit(n: int) -> Dict[str, np.ndarray]:
    keys = ("total", "benefit", "credit", "relieved_pathwise",
            "relieved_horizon", "action_share", "restoration_share",
            "cr_path0_mean")
    out = {k: np.full(n, np.nan) for k in keys}
    for f in sorted(STAGE_DIR.glob("pwfit_*.npz")):
        i0, i1 = (int(x) for x in f.stem.split("_")[-2:])
        d = np.load(f)
        for k in keys:
            out[k][i0:i1] = d[k]
    for k in keys:
        if np.isnan(out[k]).any():
            raise RuntimeError("pwfit slices incomplete")
    return out


def _digest(arrs: Dict[str, np.ndarray], rule: ManagementActionRule,
            surface: Dict[str, float], kappa: float) -> str:
    h = hashlib.sha256()
    for k in sorted(arrs):
        h.update(k.encode())
        h.update(np.ascontiguousarray(arrs[k]).tobytes())
    h.update(json.dumps(rule.to_dict(), sort_keys=True).encode())
    h.update(("sigma=%.12g;alpha=%.12g;kappa=%.12g" % (
        surface["sigma"], surface["alpha"], kappa)).encode())
    return h.hexdigest()


def stage_actions() -> int:
    t0 = time.monotonic()
    cfg = seven_driver_proxy_config()
    v = _validator()
    verify = json.loads(VERIFY_PATH.read_text(encoding="utf-8"))
    rule = ManagementActionRule()
    a_ref = float(verify["reference_assets"])
    fit_mean = float(verify["fit_mean_liability"])

    data = np.load(P23T3_ARRAYS)
    val_truth = data["val_truth"]
    val_pred = data["val_pred"]
    nested_l = data["nested_l"]
    proxy_l = data["proxy_l"]

    inputs = np.load(STAGE_DIR / "inputs.npz")
    pwfit = _assemble_pwfit(cfg.n_fit)
    pwval = {k: np.load(STAGE_DIR / "pwval.npz")[k]
             for k in ("benefit", "relieved_pathwise")}
    pw_nested = _assemble_p25t2_pw(cfg.n_eval)
    comp_fit = _assemble_comp("fit", cfg.n_fit)

    det_fit = np.concatenate([
        np.load(STAGE_DIR / "det_fit_a.npz")["arr"],
        np.load(STAGE_DIR / "det_fit_b.npz")["arr"]])
    det_ve = np.load(STAGE_DIR / "det_valeval.npz")

    # --- FIT-only calibrations (leakage-free) -----------------------------
    # kappa: the P24T3 credit carve-out level factor (reproduced).
    cd_fit = np.concatenate([
        np.load(P24T3_STAGE / "cdet_fit_a.npz")["arr"],
        np.load(P24T3_STAGE / "cdet_fit_b.npz")["arr"]])
    kappa = float(comp_fit["credit"].mean() / cd_fit.mean())
    cd_ve = np.load(P24T3_STAGE / "cdet_valeval.npz")

    # candidate (b): smoothed-relief response surface (sigma, alpha).
    fit_l7 = inputs["fit_l7"]
    cr_fit = rule.coverage_ratio(fit_l7, a_ref)
    surface = calibrate_pathwise_response_surface(
        rule, cr_fit, pwfit["benefit"], pwfit["relieved_pathwise"])

    # candidate (a): zero-shock expected path + single level factor.
    lam = calibrate_pathwise_level_factor(
        pwfit["relieved_pathwise"], det_fit)
    pred_a = lam * det_fit
    pred_b = (surface["alpha"]
              * smoothed_relief_response(rule, cr_fit, surface["sigma"])
              * pwfit["benefit"])
    t = pwfit["relieved_pathwise"]
    ss_tot = float(((t - t.mean()) ** 2).sum())

    def _fit_r2(pred: np.ndarray) -> float:
        return 1.0 - float(((t - pred) ** 2).sum()) / ss_tot

    candidate_comparison = {
        "selected": "b_smoothed_relief_response_surface",
        "selection_basis": "FIT sample only (leakage-free; no real-data "
                           "OOS/nested evidence consumed in selection)",
        "candidate_a_zero_shock_level_factor": {
            "lambda": lam,
            "fit_r2_relieved": _fit_r2(pred_a),
            "fit_active_share_det": float(np.mean(det_fit > 1e-9)),
            "fit_active_share_truth": float(np.mean(t > 1e-9)),
            "rejection_reason": (
                "The zero-shock path misses diffusion-driven cuts at "
                "mid-coverage nodes (state-dependent bias: exact in the "
                "saturated deep tail, near-zero signal at mid coverage), "
                "so one level factor cannot match the per-node relieved "
                "amounts; disclosed and retained for the cadence "
                "sensitivity."),
        },
        "candidate_b_smoothed_relief_surface": {
            "sigma": surface["sigma"],
            "alpha": surface["alpha"],
            "fit_r2_relieved": surface["fit_r2_relieved"],
        },
    }

    annual = det_ve["eval_annual"]
    monthly = det_ve["eval"]
    act = monthly > 1e-9
    cadence_sensitivity = {
        "basis": "zero-shock deterministic relieved on the nested-eval "
                 "states (proxy-side read-out; truth re-run not required)",
        "monthly_mean_relieved": float(monthly.mean()),
        "annual_mean_relieved": float(annual.mean()),
        "annual_over_monthly_mean_ratio": float(
            annual.mean() / monthly.mean()) if monthly.mean() > 0 else 1.0,
        "max_abs_node_delta": float(np.max(np.abs(annual - monthly))),
        "active_nodes_monthly": float(act.mean()),
    }

    # --- matching proxy benefit bases (P24T3 kappa pattern, reproduced) ---
    val_X = v.states(cfg.n_validation, cfg.validation_seed)
    eval_X = v.states(cfg.n_eval, cfg.eval_seed)
    poly5_val = val_pred - v.fx_term(val_X) - v.liquidity_term(val_X)
    poly5_eval = proxy_l - v.fx_term(eval_X) - v.liquidity_term(eval_X)
    benefit_proxy_val = poly5_val - kappa * cd_ve["val"]
    benefit_proxy_eval = poly5_eval - kappa * cd_ve["eval"]

    res = validate_pathwise_proxy_basis(
        rule, fit_mean, surface, kappa,
        val_truth, val_pred, nested_l, proxy_l,
        pwval["benefit"], pw_nested["benefit"],
        benefit_proxy_val, benefit_proxy_eval,
        pwval["relieved_pathwise"], pw_nested["relieved_pathwise"],
        cfg.confidence_level, cfg.capital_horizon_months,
        calibration_leakage_free=True,
        candidate_comparison=candidate_comparison,
        cadence_sensitivity=cadence_sensitivity,
    )

    # cross-check: truth nested with-actions capital equals the archived
    # P25T2 read-out (same arrays, same transform).
    p25t2_consistency = {
        "scr_pathwise_basis": res["nested_capital_with_pathwise"]["scr_proxy"],
        "scr_p25t2_archived": verify["p25t2_nested_scr_with_pathwise"],
        "abs_diff": abs(
            res["nested_capital_with_pathwise"]["scr_proxy"]
            - verify["p25t2_nested_scr_with_pathwise"]),
        "match": abs(
            res["nested_capital_with_pathwise"]["scr_proxy"]
            - verify["p25t2_nested_scr_with_pathwise"]) < 1e-6,
    }

    arrs = {"val_truth": val_truth, "val_pred": val_pred,
            "nested_l": nested_l, "proxy_l": proxy_l,
            "benefit_val": pwval["benefit"],
            "benefit_nested": pw_nested["benefit"],
            "benefit_proxy_val": benefit_proxy_val,
            "benefit_proxy_eval": benefit_proxy_eval,
            "relieved_truth_val": pwval["relieved_pathwise"],
            "relieved_truth_nested": pw_nested["relieved_pathwise"],
            "relieved_truth_fit": pwfit["relieved_pathwise"],
            "det_fit": det_fit}

    report = {
        "task": "Phase 25 Task 3 - matching path-wise proxy basis feature "
                "(smoothed-relief response surface) + seven-driver OOS "
                "re-validation",
        "phase": PHASE,
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": "p25t3-" + _digest(arrs, rule, surface, kappa)[:8],
        "verdict": res["verdict"],
        "gates_definition": {
            "oos_r2_gate": PATHWISE_OOS_R2_GATE,
            "var_rel_error_gate": PATHWISE_VAR_REL_ERROR_GATE,
            "source": "Phase 25 Task 1 design note s5 (FIXED pre-registered"
                      ", unchanged Phase 22 gates, no gate-shopping)",
        },
        "result": res,
        "p25t2_truth_consistency": p25t2_consistency,
        "fit_truth_diagnostics": {
            "fit_action_share_mean": float(pwfit["action_share"].mean()),
            "fit_restoration_share_mean": float(
                pwfit["restoration_share"].mean()),
            "fit_relieved_mean": float(pwfit["relieved_pathwise"].mean()),
            "fit_nodes_with_any_action": float(
                np.mean(pwfit["action_share"] > 0.0)),
        },
        "verify_stage": verify,
        "primitives_provenance": (
            "FIT/VALIDATION truth path-wise relieved amounts are "
            "BIT-IDENTICAL re-runs of the archived Phase 22 Task 2 inner "
            "paths (exact equality of total/benefit/credit vs the archived "
            "Phase 24 Task 3 decomposition enforced at every slice); the "
            "nested-eval truth relieved amounts are the archived Phase 25 "
            "Task 2 stage (report digest re-verified); the L7 arrays, "
            "fit-mean and selected proxy surface are the archived Phase 23 "
            "Task 3 stage; kappa reproduces the archived Phase 24 Task 3 "
            "credit carve-out."
        ),
        "method": (
            "Proxy action basis: relieved_hat = alpha * phi_sigma(CR_hat) "
            "* clip(B_hat, 0, L_hat) with phi_sigma the governed relief "
            "curve smoothed over an effective lognormal dispersion of the "
            "path-wise coverage ratio (Gauss-Hermite order 21), CR_hat = "
            "a_ref / L_hat, and B_hat = clip(poly5 - kappa * C_det, 0, "
            "L_hat) the P24T3 carve-out base. (sigma, alpha) and kappa are "
            "calibrated on the FIT sample only. Truth and proxy apply the "
            "IDENTICAL node-level envelope transform relieved <= "
            "max_relief * clip(B, 0, L) (G1 convention)."
        ),
        "residuals_documented": [
            "Declaration cadence: the truth declares monthly; the annual-"
            "cadence sensitivity is quantified on the deterministic "
            "expected-path basis (see declaration_cadence_sensitivity).",
            "Adaptedness: the truth coverage proxy discounts remaining "
            "cashflows with the realised inner path (perfect-foresight "
            "proxy); an adapted valuation would require nested-nested "
            "simulation.",
            "The node-level analytic FX/liquidity offset enters the "
            "coverage proxy undecayed.",
            "The effective dispersion sigma is constant across nodes; a "
            "(CR, vol)-state-dependent sigma is the documented refinement.",
        ],
        "limitations": [
            "Management-action parameters are educational placeholders "
            "pending credentialled data + APS X2 review.",
            "The proxy relieved amount is an analytic approximation of the "
            "per-node inner-path mean; per-node error disclosed in "
            "relieved_approximation_diagnostics.",
            "Tail diagnostics + MR-010/MR-014 refresh on the path-wise "
            "basis are Task 4 (refresh trigger MET at Task 2: +14.17%).",
        ],
        "use_restrictions": pathwise_proxy_basis_use_restrictions(),
        "reproducibility_digest": _digest(arrs, rule, surface, kappa),
        "duration_seconds": time.monotonic() - t0,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    MD_PATH.write_text(_markdown(report), encoding="utf-8")
    CARD_PATH.write_text(_card(report), encoding="utf-8")
    json.loads(JSON_PATH.read_text(encoding="utf-8"))
    print("actions OK; verdict:", res["verdict"],
          "; gates:", json.dumps(res["gates"]))
    return 0 if res["verdict"] == "PASS" else 1


def _markdown(rep: Dict[str, Any]) -> str:
    r = rep["result"]
    sur = r["surface_calibration_fit_only"]
    cc = r["candidate_comparison"]
    cs = r["declaration_cadence_sensitivity"]
    nw = r["nested_capital_without"]
    nwp = r["nested_capital_with_pathwise"]
    pw = r["proxy_capital_with_pathwise"]
    dg = r["relieved_approximation_diagnostics"]
    gates = "\n".join("* {}: {}".format(k, "PASS" if v else "FAIL")
                      for k, v in r["gates"].items())
    lims = "\n".join("* " + x for x in rep["limitations"])
    resid = "\n".join("* " + x for x in rep["residuals_documented"])
    return """# Phase 25 Task 3 - Matching Path-Wise Proxy Basis + Seven-Driver OOS Re-Validation

Run: {ts}

## Verdict: {verdict}

The LSMC proxy gains the matching analytic path-wise action basis
(relieved_hat = alpha * phi_sigma(CR_hat) * clip(B_hat, 0, L_hat); sigma,
alpha and kappa calibrated on the FIT sample only), so truth and proxy share
an IDENTICAL action basis (G1 convention) and the seven-driver OOS
re-validation runs at the unchanged Phase 22 gates.

## Gates (fixed pre-registered, Phase 25 Task 1 design note s5)

{gates}

## OOS re-validation (with actions, path-wise basis)

* OOS R^2: **{r2:.4f}** (gate >= {r2g}); without actions {r2wo:.4f}
* Proxy VaR99.5 {pvar:.1f} vs nested {nvar:.1f}; rel err **{vrel:.2%}** (gate <= {vg:.0%})
* ES rel err {esrel:.2%}; SCR rel err {scrrel:.2%}
* Nested SCR with-actions (path-wise) {nscr:.1f}; without {woscr:.1f}

## Surface calibration (FIT sample only, leakage-free)

* sigma = {sig:.3f} (effective path-wise CR dispersion; grid interior: {sint})
* alpha = {alp:.3f}; fit R^2 on per-node relieved amounts = {fr2:.4f}
* kappa (credit carve-out, P24T3 reproduced) = {kap:.4f}

## Candidate comparison (selection on FIT evidence only)

Selected: **{sel}**. Candidate (a) zero-shock + level factor lambda =
{lam:.2f} achieves fit R^2 {ar2:.3f} (active on {aact:.0%} of fit nodes vs
truth {tact:.0%}): {arej}

## Relieved-amount approximation (disclosed)

| sample | corr | mean abs err | active truth | active proxy |
| --- | --- | --- | --- | --- |
| validation (60) | {vc:.3f} | {vme:.1f} | {vat:.0%} | {vap:.0%} |
| nested eval (500) | {nc:.3f} | {nme:.1f} | {nat:.0%} | {nap:.0%} |

Envelope clip binding: truth {clt:.1%} / proxy {clp:.1%} of nested nodes.

## Declaration-cadence sensitivity (residual read-out)

Annual vs monthly declaration on the deterministic basis: mean relieved
ratio {cr:.3f} (monthly {cm:.1f} -> annual {ca:.1f}); max node delta {cd:.1f}.

## Truth consistency

Nested with-actions (path-wise) SCR reproduces the archived P25T2 report:
|diff| = {tdiff:.2e} ({tmatch}).

## Residuals documented

{resid}

## Limitations

{lims}

Reproducibility digest: `{dig}`
""".format(
        ts=rep["run_timestamp"], verdict=rep["verdict"], gates=gates,
        r2=r["oos_r2_with_actions_pathwise"],
        r2g=rep["gates_definition"]["oos_r2_gate"],
        r2wo=r["oos_r2_without_actions"],
        pvar=pw["var_liability"], nvar=nwp["var_liability"],
        vrel=r["var_rel_error_with_actions"],
        vg=rep["gates_definition"]["var_rel_error_gate"],
        esrel=r["es_rel_error_with_actions"],
        scrrel=r["scr_rel_error_with_actions"],
        nscr=nwp["scr_proxy"], woscr=nw["scr_proxy"],
        sig=sur["sigma"], sint=sur["sigma_interior"], alp=sur["alpha"],
        fr2=sur["fit_r2_relieved"], kap=r["kappa_credit_fit_calibrated"],
        sel=cc["selected"],
        lam=cc["candidate_a_zero_shock_level_factor"]["lambda"],
        ar2=cc["candidate_a_zero_shock_level_factor"]["fit_r2_relieved"],
        aact=cc["candidate_a_zero_shock_level_factor"][
            "fit_active_share_det"],
        tact=cc["candidate_a_zero_shock_level_factor"][
            "fit_active_share_truth"],
        arej=cc["candidate_a_zero_shock_level_factor"]["rejection_reason"],
        vc=dg["val_nodes"]["corr"], vme=dg["val_nodes"]["mean_abs_error"],
        vat=dg["val_nodes"]["active_share_truth"],
        vap=dg["val_nodes"]["active_share_estimate"],
        nc=dg["nested_nodes"]["corr"],
        nme=dg["nested_nodes"]["mean_abs_error"],
        nat=dg["nested_nodes"]["active_share_truth"],
        nap=dg["nested_nodes"]["active_share_estimate"],
        clt=r["clip_binding_share_truth_nested"],
        clp=r["clip_binding_share_proxy_nested"],
        cr=cs["annual_over_monthly_mean_ratio"],
        cm=cs["monthly_mean_relieved"], ca=cs["annual_mean_relieved"],
        cd=cs["max_abs_node_delta"],
        tdiff=rep["p25t2_truth_consistency"]["abs_diff"],
        tmatch="match" if rep["p25t2_truth_consistency"]["match"]
        else "MISMATCH",
        resid=resid, lims=lims, dig=rep["reproducibility_digest"])


def _card(rep: Dict[str, Any]) -> str:
    r = rep["result"]
    sur = r["surface_calibration_fit_only"]
    return """# Path-Wise Proxy Basis Card (Phase 25 Task 3)

**What:** the LSMC proxy now carries the MATCHING path-wise action basis:
relieved_hat = alpha * phi_sigma(CR_hat) * clip(B_hat, 0, L_hat), the
governed relief curve smoothed over an effective lognormal dispersion of the
path-wise coverage ratio. Two scalars (sigma {sig:.3f}, alpha {alp:.3f}) +
kappa {kap:.4f}, ALL calibrated on the FIT sample only (leakage-free). Truth
and proxy apply the identical envelope transform (G1 convention).

**Verdict:** {verdict}. OOS R^2 {r2:.4f} (gate >= 0.95); VaR99.5 rel err
{vrel:.2%} (gate <= 10%); SCR rel err {scrrel:.2%}.

**Candidate comparison:** the pre-registered zero-shock + level-factor
candidate was evaluated and REJECTED on fit evidence (state-dependent bias;
fit R^2 {ar2:.3f} vs {fr2:.4f}); disclosed in the report.

**Residuals:** declaration cadence (annual sensitivity quantified);
perfect-foresight coverage discounting; node offset undecayed; constant
sigma across nodes.

**EDUCATIONAL MODEL** - parameters are placeholders; NOT for production
capital decisions. See PHASE25_TASK3_PATHWISE_PROXY_BASIS_REPORT.md.
""".format(verdict=rep["verdict"], sig=sur["sigma"], alp=sur["alpha"],
           kap=r["kappa_credit_fit_calibrated"],
           r2=r["oos_r2_with_actions_pathwise"],
           vrel=r["var_rel_error_with_actions"],
           scrrel=r["scr_rel_error_with_actions"],
           ar2=r["candidate_comparison"][
               "candidate_a_zero_shock_level_factor"]["fit_r2_relieved"],
           fr2=sur["fit_r2_relieved"])


def _has_change_record(store: GovernanceStore) -> bool:
    return any(x.title == CHANGE_TITLE for x in store.change_records)


def stage_governance() -> int:
    rep = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    r = rep["result"]
    sur = r["surface_calibration_fit_only"]
    store = GovernanceStore.from_json(GOV_PATH.read_text(encoding="utf-8"))

    if _has_change_record(store):
        rec = next(x for x in store.change_records if x.title == CHANGE_TITLE)
        print("already applied:", rec.record_id)
        print("audit integrity:", store.audit_trail.verify_all())
        return 0

    rec = ChangeRecord.create(
        title=CHANGE_TITLE,
        description=(
            "The LSMC proxy gains the matching analytic path-wise action "
            "basis (G1 identical-basis convention): relieved_hat = alpha * "
            "phi_sigma(CR_hat) * clip(B_hat, 0, L_hat), with phi_sigma the "
            "governed relief curve smoothed over an effective lognormal "
            "dispersion of the path-wise coverage ratio (Gauss-Hermite "
            "21). (sigma, alpha) and the credit carve-out kappa are "
            "calibrated on the FIT sample only (leakage-free; no "
            "per-state learned coefficients). The pre-registered "
            "zero-shock + level-factor candidate was evaluated and "
            "rejected on FIT evidence (disclosed). Seven-driver OOS "
            "re-validation at the unchanged Phase 22 gates."
        ),
        change_type="code_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "proxy_action_basis": "horizon-level inner-path benefit cut "
                                  "(Phase 24 Task 3); truth path-wise "
                                  "since Phase 25 Task 2 (basis mismatch "
                                  "documented as the Task 3 item)",
            "oos_r2_with_actions_horizon_basis_p24t3": None,
        },
        after_snapshot={
            "proxy_action_basis": "matching path-wise smoothed-relief "
                                  "response surface",
            "sigma": sur["sigma"],
            "alpha": sur["alpha"],
            "kappa": r["kappa_credit_fit_calibrated"],
            "oos_r2_with_actions_pathwise":
                r["oos_r2_with_actions_pathwise"],
            "var_rel_error_with_actions":
                r["var_rel_error_with_actions"],
            "gates": r["gates"],
            "verdict": rep["verdict"],
            "reproducibility_digest": rep["reproducibility_digest"],
        },
        impact_assessment=(
            "Proxy-side consistency feature (SII Art. 23/234, ASOP 56 "
            "3.1.3): truth and proxy now share an identical path-wise "
            "action basis, removing the Task 2 documented basis mismatch. "
            "Without-actions results unchanged (bit-identical archive "
            "re-use); nested truth with-actions figures unchanged "
            "(archived P25T2 stage, digest-verified). No copula or risk-"
            "driver change; rank invariance untouched (Task 4 re-check)."
        ),
        quantitative_impact=(
            "OOS R^2 with actions (path-wise) {r2:.4f}; proxy-vs-nested "
            "VaR99.5 rel err {vrel:.2%}; ES rel err {esrel:.2%}; SCR rel "
            "err {scrrel:.2%}; surface sigma {sig:.3f} / alpha {alp:.3f}; "
            "fit R^2 on per-node relieved {fr2:.4f}; annual-cadence "
            "sensitivity ratio {cad:.3f}."
        ).format(r2=r["oos_r2_with_actions_pathwise"],
                 vrel=r["var_rel_error_with_actions"],
                 esrel=r["es_rel_error_with_actions"],
                 scrrel=r["scr_rel_error_with_actions"],
                 sig=sur["sigma"], alp=sur["alpha"],
                 fr2=sur["fit_r2_relieved"],
                 cad=r["declaration_cadence_sensitivity"][
                     "annual_over_monthly_mean_ratio"]),
        author=ACTOR,
        phase=PHASE,
        peer_reviewer="APS_X2_Independent_Reviewer",
        assumption_owner="ChiefActuary",
    )
    rec.submit_for_peer_review(
        ACTOR,
        "Matching path-wise proxy basis at the FIXED pre-registered Task 1 "
        "s5 gates (unchanged Phase 22 gates); FIT-only calibration "
        "(leakage-free); candidate comparison disclosed; truth arrays "
        "digest-verified against the archived P25T2 stage.",
    )
    rec.submit_to_owner(
        ACTOR,
        "Owner review requested. Production sign-off withheld pending tail "
        "diagnostics + MR-010/MR-014 refresh (Task 4, trigger MET), "
        "credentialled management-practice data, and independent APS X2 "
        "review.",
    )
    store.add_change_record(rec)

    entry = AuditEntry.model_run(
        actor=ACTOR,
        phase=PHASE,
        run_id=rep["run_id"],
        scenario_count=500,
        duration_seconds=rep["duration_seconds"],
        outcome=rep["verdict"],
        files_changed=AFFECTED_COMPONENTS,
        test_summary=(
            "pathwise proxy basis: OOS R^2 {r2:.4f}; VaR rel err {vrel:.2%}"
            "; sigma {sig:.3f} alpha {alp:.3f}; gates {ng}/{nt} PASS".format(
                r2=r["oos_r2_with_actions_pathwise"],
                vrel=r["var_rel_error_with_actions"],
                sig=sur["sigma"], alp=sur["alpha"],
                ng=sum(r["gates"].values()), nt=len(r["gates"]))
        ),
    )
    store.audit_trail.append(entry)

    ok = store.audit_trail.verify_all()
    GOV_PATH.write_text(store.to_json() + "\n", encoding="utf-8")

    rep["change_record_id"] = rec.record_id
    rep["change_record_status"] = (
        rec.status.value if hasattr(rec.status, "value") else str(rec.status))
    rep["audit_integrity_ok"] = ok
    rep["change_records_total"] = len(store.change_records)
    JSON_PATH.write_text(json.dumps(rep, indent=2) + "\n", encoding="utf-8")

    print("ChangeRecord {} ({}); audit entries {}; verify_all {}".format(
        rec.record_id, rep["change_record_status"],
        len(store.audit_trail.entries), ok))
    return 0 if ok else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True,
                    choices=["verify", "pwfit", "pwval", "det", "actions",
                             "governance"])
    ap.add_argument("--i0", type=int, default=0)
    ap.add_argument("--i1", type=int, default=0)
    ap.add_argument("--part", type=str, default="")
    a = ap.parse_args()
    if a.stage == "verify":
        sys.exit(stage_verify())
    if a.stage == "pwfit":
        sys.exit(stage_pwfit(a.i0, a.i1))
    if a.stage == "pwval":
        sys.exit(stage_pwval())
    if a.stage == "det":
        sys.exit(stage_det(a.part))
    if a.stage == "actions":
        sys.exit(stage_actions())
    sys.exit(stage_governance())
