#!/usr/bin/env python3
"""Phase 24 Task 3 build + governance - inner-path action dynamics prototype.

The governed Phase 23 bonus-cut rule is moved from the outer-node
conditional-liability transform INTO the inner-path projected
policyholder-benefit cashflows (horizon-level declared-rate response): the
cuttable base per inner path is the in-force benefit PV (guaranteed +
equity-guarantee); the asset-side credit-loss PV and the analytic
FX/liquidity offsets are excluded.  Nested ground truth rebuilt on that
basis from BIT-IDENTICAL re-runs of the archived Phase 22 Task 2 inner
paths (exact-equality cross-checked); the LSMC proxy gains the matching
analytic post-composition benefit base (expected-path credit carve-out,
fit-calibrated level factor kappa, leakage-free).  OOS re-validation at the
unchanged Phase 22 gates (R^2 >= 0.95, VaR rel err <= 10%).

Run staged (each stage < 45 s):
  PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase24_task3_inner_path_action.py --stage verify
  ... --stage components --part nested --i0 0 --i1 250
  ... --stage components --part nested --i0 250 --i1 500
  ... --stage components --part val --i0 0 --i1 60
  ... --stage components --part fit --i0 0 --i1 1000
  ... --stage components --part fit --i0 1000 --i1 2000
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
    MitigationStatus,
)
from par_model_v2.projection.inner_path_action_dynamics import (
    INNER_PATH_OOS_R2_GATE,
    INNER_PATH_VAR_REL_ERROR_GATE,
    benefit_credit_fit_sliced,
    benefit_credit_heavy_sliced,
    deterministic_credit_pv,
    inner_path_use_restrictions,
    validate_inner_path_actions,
)
from par_model_v2.projection.management_actions import ManagementActionRule
from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.multi_driver_proxy_validation_7d import (
    SevenDriverLiquidityProxyValidator,
    seven_driver_proxy_config,
)

PHASE = "Phase 24: With-Actions Aggregation Consistency + Inner-Path Action Dynamics"
ACTOR = "AutomatedModelDev_Phase24"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
OUT_DIR = Path("docs/validation")
JSON_PATH = OUT_DIR / "PHASE24_TASK3_INNER_PATH_ACTION_REPORT.json"
MD_PATH = OUT_DIR / "PHASE24_TASK3_INNER_PATH_ACTION_REPORT.md"
CARD_PATH = Path("docs/INNER_PATH_ACTION_CARD.md")
P22T2_STAGE = Path(".phase22_task2_stage")
P23T3_ARRAYS = Path("/var/tmp/p23t3_stage/arrays.npz")
P23T3_CROSSCHECK = Path("/var/tmp/p23t3_stage/crosscheck.json")
P23T3_REPORT = OUT_DIR / "PHASE23_TASK3_MANAGEMENT_ACTION_REPORT.json"
STAGE_DIR = Path("/var/tmp/p24t3_stage")
VERIFY_PATH = STAGE_DIR / "verify.json"

CHANGE_TITLE = (
    "Phase 24 Task 3 - inner-path management-action dynamics prototype "
    "(bonus cut on inner-path benefit cashflows)"
)

AFFECTED_COMPONENTS = [
    "par_model_v2/projection/inner_path_action_dynamics.py",
    "tests/test_phase24_task3_inner_path_action.py",
    "scripts/build_phase24_task3_inner_path_action.py",
    "docs/INNER_PATH_ACTION_CARD.md",
    "docs/validation/PHASE24_TASK3_INNER_PATH_ACTION_REPORT.{json,md}",
]

STANDARD_REFERENCES = [
    "Solvency II Delegated Regulation Article 23 (future management actions)",
    "SOA ASOP 56 section 3.1.3/3.4/3.5 (outer-node vs inner-path dynamics)",
    "IA TAS M section 3.2/3.6",
    "IFoA proxy-modelling working party (analytic post-composition features)",
    "Longstaff & Schwartz (2001)",
]


def _product() -> ParEndowmentProduct:
    return ParEndowmentProduct(
        issue_age=45, gender="M", sum_assured=100000.0,
        annual_premium=5000.0, term_years=20)


def _validator() -> SevenDriverLiquidityProxyValidator:
    return SevenDriverLiquidityProxyValidator(_product())


def _staged_part(part: str, n: int) -> np.ndarray:
    full = np.full(n, np.nan)
    for f in sorted(P22T2_STAGE.glob(part + "_*.npz")):
        i0, i1 = (int(x) for x in f.stem.split("_")[-2:])
        full[i0:i1] = np.load(f)["arr"]
    if np.isnan(full).any():
        raise RuntimeError("staged slices for %s incomplete" % part)
    return full


def stage_verify() -> int:
    """Cross-check the archived Phase 23 Task 3 arrays + report digest and
    the Phase 22 Task 2 staged slices BEFORE any new computation."""
    t0 = time.monotonic()
    STAGE_DIR.mkdir(parents=True, exist_ok=True)
    cfg = seven_driver_proxy_config()

    data = np.load(P23T3_ARRAYS)
    arrs = {k: data[k] for k in
            ("val_truth", "val_pred", "nested_l", "proxy_l")}
    fit_mean = float(data["fit_mean"][0])

    # digest must match the archived Phase 23 Task 3 report (rule default)
    rule = ManagementActionRule()
    h = hashlib.sha256()
    for k in sorted(arrs):
        h.update(k.encode())
        h.update(np.ascontiguousarray(arrs[k]).tobytes())
    h.update(json.dumps(rule.to_dict(), sort_keys=True).encode())
    digest = h.hexdigest()
    p23t3 = json.loads(P23T3_REPORT.read_text(encoding="utf-8"))
    crosscheck = json.loads(P23T3_CROSSCHECK.read_text(encoding="utf-8"))

    checks = {
        "p23t3_digest_match": digest == p23t3["reproducibility_digest"],
        "p23t3_verdict_pass": p23t3["verdict"] == "PASS",
        "p23t3_crosscheck_all_pass": all(crosscheck["checks"].values()),
        "fit_mean_match": abs(
            fit_mean - crosscheck["fit_mean_liability"]) <= 1e-9,
        "staged_fit_complete": len(_staged_part("fit", cfg.n_fit)) == cfg.n_fit,
        "staged_val_complete": len(
            _staged_part("val", cfg.n_validation)) == cfg.n_validation,
        "staged_nested_complete": len(
            _staged_part("nested", cfg.n_eval)) == cfg.n_eval,
        "arrays_lengths_ok": (
            len(arrs["val_truth"]) == cfg.n_validation
            and len(arrs["val_pred"]) == cfg.n_validation
            and len(arrs["nested_l"]) == cfg.n_eval
            and len(arrs["proxy_l"]) == cfg.n_eval),
    }
    if not all(checks.values()):
        raise RuntimeError("verify failed: " + json.dumps(checks))
    VERIFY_PATH.write_text(json.dumps({
        "checks": checks,
        "p23t3_digest": digest,
        "fit_mean_liability": fit_mean,
        "config": cfg.to_dict(),
        "duration_seconds": time.monotonic() - t0,
    }, indent=2) + "\n", encoding="utf-8")
    print("verify OK:", json.dumps(checks))
    return 0


def stage_components(part: str, i0: int, i1: int) -> int:
    """Recompute the inner-path component decomposition for [i0, i1) of the
    given part with BIT-IDENTICAL seeds; exact-equality check vs archive."""
    t0 = time.monotonic()
    if not VERIFY_PATH.exists():
        raise RuntimeError("run --stage verify first")
    cfg = seven_driver_proxy_config()
    v = _validator()
    sizes = {"fit": cfg.n_fit, "val": cfg.n_validation, "nested": cfg.n_eval}
    n = sizes[part]
    if not (0 <= i0 < i1 <= n):
        raise ValueError("bad slice")
    if part == "fit":
        states = v.states(cfg.n_fit, cfg.fit_seed)
        tot, ben, cre = benefit_credit_fit_sliced(
            v, states, i0, i1, cfg.fit_seed, cfg.fit_n_inner)
    elif part == "val":
        states = v.states(cfg.n_validation, cfg.validation_seed)
        tot, ben, cre = benefit_credit_heavy_sliced(
            v, states, i0, i1, cfg.n_inner_heavy, cfg.validation_seed)
    else:
        states = v.states(cfg.n_eval, cfg.eval_seed)
        tot, ben, cre = benefit_credit_heavy_sliced(
            v, states, i0, i1, cfg.nested_n_inner, cfg.nested_inner_seed)
    arc = _staged_part(part, n)[i0:i1]
    if not np.array_equal(tot, arc):
        raise RuntimeError(
            "decomposition total does not match archive bit-identically "
            "(part=%s, maxdiff=%g)" % (part, float(np.max(np.abs(tot - arc)))))
    np.savez(STAGE_DIR / ("comp_%s_%05d_%05d.npz" % (part, i0, i1)),
             total=tot, benefit=ben, credit=cre)
    print("components %s [%d,%d) OK bit-identical; %.1fs"
          % (part, i0, i1, time.monotonic() - t0))
    return 0


def _assemble_components(part: str, n: int) -> Dict[str, np.ndarray]:
    out = {k: np.full(n, np.nan) for k in ("total", "benefit", "credit")}
    for f in sorted(STAGE_DIR.glob("comp_%s_*.npz" % part)):
        i0, i1 = (int(x) for x in f.stem.split("_")[-2:])
        d = np.load(f)
        for k in out:
            out[k][i0:i1] = d[k]
    for k in out:
        if np.isnan(out[k]).any():
            raise RuntimeError("component slices for %s incomplete" % part)
    return out


def _digest(arrs: Dict[str, np.ndarray], rule: ManagementActionRule,
            kappa: float) -> str:
    h = hashlib.sha256()
    for k in sorted(arrs):
        h.update(k.encode())
        h.update(np.ascontiguousarray(arrs[k]).tobytes())
    h.update(json.dumps(rule.to_dict(), sort_keys=True).encode())
    h.update(("kappa=%.12g" % kappa).encode())
    return h.hexdigest()



def stage_cdet(part: str) -> int:
    """Cache the deterministic expected-path credit PVs (heavy: one
    zero-shock path pair per node) so stage_actions fits the bash wall."""
    t0 = time.monotonic()
    cfg = seven_driver_proxy_config()
    v = _validator()
    if part == "fit_a":
        X = v.states(cfg.n_fit, cfg.fit_seed)
        np.savez(STAGE_DIR / "cdet_fit_a.npz",
                 arr=deterministic_credit_pv(v, X[:1000]))
    elif part == "fit_b":
        X = v.states(cfg.n_fit, cfg.fit_seed)
        np.savez(STAGE_DIR / "cdet_fit_b.npz",
                 arr=deterministic_credit_pv(v, X[1000:]))
    elif part == "valeval":
        val_X = v.states(cfg.n_validation, cfg.validation_seed)
        eval_X = v.states(cfg.n_eval, cfg.eval_seed)
        np.savez(STAGE_DIR / "cdet_valeval.npz",
                 val=deterministic_credit_pv(v, val_X),
                 eval=deterministic_credit_pv(v, eval_X))
    else:
        raise ValueError("part must be fit_a / fit_b / valeval")
    print("cdet %s OK; %.1fs" % (part, time.monotonic() - t0))
    return 0


def stage_actions() -> int:
    t0 = time.monotonic()
    cfg = seven_driver_proxy_config()
    v = _validator()
    verify = json.loads(VERIFY_PATH.read_text(encoding="utf-8"))
    data = np.load(P23T3_ARRAYS)
    val_truth = data["val_truth"]
    val_pred = data["val_pred"]
    nested_l = data["nested_l"]
    proxy_l = data["proxy_l"]
    fit_mean = float(data["fit_mean"][0])

    comp_fit = _assemble_components("fit", cfg.n_fit)
    comp_val = _assemble_components("val", cfg.n_validation)
    comp_nested = _assemble_components("nested", cfg.n_eval)

    fit_X = v.states(cfg.n_fit, cfg.fit_seed)
    val_X = v.states(cfg.n_validation, cfg.validation_seed)
    eval_X = v.states(cfg.n_eval, cfg.eval_seed)

    # consistency: staged 5d totals + analytic offsets == archived L7 arrays
    val_l7 = comp_val["total"] + v.fx_term(val_X) + v.liquidity_term(val_X)
    nested_l7 = (comp_nested["total"] + v.fx_term(eval_X)
                 + v.liquidity_term(eval_X))
    assert np.allclose(val_l7, val_truth, rtol=0, atol=1e-6), "val L7 mismatch"
    assert np.allclose(nested_l7, nested_l, rtol=0, atol=1e-6), "nested L7 mismatch"

    # kappa: single level adjustment for the expected-path credit carve-out,
    # calibrated on the FIT sample only (leakage-free).  The deterministic
    # credit PVs are precomputed by --stage cdet (cached).
    for f in ("cdet_fit_a.npz", "cdet_fit_b.npz", "cdet_valeval.npz"):
        if not (STAGE_DIR / f).exists():
            raise RuntimeError("run --stage cdet (fit_a, fit_b, valeval) first")
    cdet_fit = np.concatenate([
        np.load(STAGE_DIR / "cdet_fit_a.npz")["arr"],
        np.load(STAGE_DIR / "cdet_fit_b.npz")["arr"]])
    cd_ve = np.load(STAGE_DIR / "cdet_valeval.npz")
    kappa = float(comp_fit["credit"].mean() / cdet_fit.mean())

    cdet_val = kappa * cd_ve["val"]
    cdet_eval = kappa * cd_ve["eval"]

    # matching analytic post-composition benefit base for the proxy:
    # poly5 part = L7 prediction minus the analytic FX + liquidity offsets.
    poly5_val = val_pred - v.fx_term(val_X) - v.liquidity_term(val_X)
    poly5_eval = proxy_l - v.fx_term(eval_X) - v.liquidity_term(eval_X)
    benefit_proxy_val = poly5_val - cdet_val
    benefit_proxy_eval = poly5_eval - cdet_eval

    rule = ManagementActionRule()
    res = validate_inner_path_actions(
        rule, fit_mean, val_truth, val_pred, nested_l, proxy_l,
        comp_val["benefit"], comp_nested["benefit"],
        benefit_proxy_val, benefit_proxy_eval,
        cfg.confidence_level, cfg.capital_horizon_months)

    # credit carve-out approximation diagnostics (disclosed)
    def _diag(emp, det):
        rel = np.abs(det - emp) / np.maximum(np.abs(emp), 1e-9)
        return {
            "mean_abs_rel_error": float(rel.mean()),
            "max_abs_rel_error": float(rel.max()),
            "corr": float(np.corrcoef(emp, det)[0, 1]),
        }
    credit_diag = {
        "kappa_fit_calibrated": kappa,
        "val_nodes": _diag(comp_val["credit"], cdet_val),
        "nested_nodes": _diag(comp_nested["credit"], cdet_eval),
        "credit_share_of_liability_nested": float(
            (comp_nested["credit"] / comp_nested["total"]).mean()),
        "benefit_share_of_liability_nested": float(
            (comp_nested["benefit"] / comp_nested["total"]).mean()),
    }

    arrs = {"val_truth": val_truth, "val_pred": val_pred,
            "nested_l": nested_l, "proxy_l": proxy_l,
            "benefit_val": comp_val["benefit"],
            "benefit_nested": comp_nested["benefit"],
            "benefit_proxy_val": benefit_proxy_val,
            "benefit_proxy_eval": benefit_proxy_eval}

    report = {
        "task": "Phase 24 Task 3 - inner-path management-action dynamics "
                "prototype (bonus cut on inner-path benefit cashflows)",
        "phase": PHASE,
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": "p24t3-" + _digest(arrs, rule, kappa)[:8],
        "verdict": res["verdict"],
        "gates_definition": {
            "oos_r2_gate": INNER_PATH_OOS_R2_GATE,
            "var_rel_error_gate": INNER_PATH_VAR_REL_ERROR_GATE,
            "source": "Phase 24 Task 1 design note s5 (pre-registered, "
                      "module constants in joint_action_aggregation.py)",
        },
        "result": res,
        "credit_carveout_diagnostics": credit_diag,
        "verify_stage": verify,
        "parallel_run_reconciliation": {
            "event": (
                "2026-06-07 ~18:08-18:22 UTC: a parallel automated run "
                "implemented Task 3 as a scalar bonus-cashflow-response "
                "variant (relief = response_factor * rule_relief * L; "
                "response 1.0 recovers the Phase 23 outer-node transform "
                "exactly) and its governance write left "
                ".claude-dev/GOVERNANCE_STORE.json truncated/corrupt."
            ),
            "remediation": [
                "Store restored from the verified cycle-18 commit on "
                "branch p22c9 (40 change records / 67 audit entries / "
                "verify_all True); corrupted file preserved at "
                "/var/tmp/p24t3_build/GOV_STORE_CORRUPTED_20260607T1822.json.",
                "The variant's ChangeRecord was faithfully re-applied "
                "(6b16ab1d99ed49dca866a8e295108635, incl. MR-014 refresh) "
                "and then SUPERSEDED with documented reason: it does not "
                "implement the pre-registered Task 3 basis (bonus cut "
                "entering horizon-level inner cashflows in the nested "
                "truth).",
                "Variant evidence retained as a disclosed recognition-lag "
                "sensitivity at docs/validation/"
                "PHASE24_TASK3_INNER_PATH_SCALAR_RESPONSE_VARIANT_REPORT"
                ".{json,md}; its module/script/tests remain in the repo.",
            ],
        },
        "primitives_provenance": (
            "All inner-path component decompositions are BIT-IDENTICAL "
            "re-runs of the archived Phase 22 Task 2 stage "
            "(.phase22_task2_stage; seeds 42/20260607/142; exact equality "
            "of the per-node total enforced at every slice); the L7 arrays "
            "and fit-mean are the archived Phase 23 Task 3 stage "
            "(/var/tmp/p23t3_stage), digest-matched to the archived report."
        ),
        "method": (
            "Inner-path basis: PV_with_i = PV_i - relief(CR_outer) * B_i "
            "with B_i = guaranteed_pv_i + eq_guarantee_pv_i (in-force "
            "policyholder benefits); asset-side credit-loss PV and analytic "
            "FX/liquidity offsets are NOT cuttable. The action decision "
            "remains the PRE-action outer-node coverage ratio "
            "CR = A_ref / L7 (declared-rate response at horizon level). "
            "Proxy: matching analytic post-composition base "
            "B_hat = clip(poly5 - kappa * C_det(r,s), 0, L_hat); kappa "
            "calibrated on the FIT sample only."
        ),
        "residual_documented": (
            "Full path-wise dynamic declaration (action re-evaluated at "
            "every inner time step on a path-wise solvency position) "
            "remains OUT of scope (Phase 24 Task 1 design note, Method B "
            "scope note); the relief factor is constant across the inner "
            "paths of one outer node. A per-time-step declared-rate "
            "mechanism is the documented future refinement."
        ),
        "limitations": [
            "Management-action parameters are educational placeholders "
            "pending credentialled data + APS X2 review.",
            "Declared-rate response is horizon-level (outer-node decision); "
            "full path-wise declaration is a documented residual.",
            "The proxy credit carve-out is an expected-path approximation "
            "with a single fit-calibrated level factor; per-node "
            "approximation error is disclosed in "
            "credit_carveout_diagnostics.",
            "Coverage ratio uses a fixed reference-asset proxy.",
        ],
        "use_restrictions": inner_path_use_restrictions(),
        "reproducibility_digest": _digest(arrs, rule, kappa),
        "duration_seconds": time.monotonic() - t0,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    MD_PATH.write_text(_markdown(report), encoding="utf-8")
    CARD_PATH.write_text(_card(report), encoding="utf-8")
    json.loads(JSON_PATH.read_text(encoding="utf-8"))
    print("actions OK; verdict:", res["verdict"],
          "; gates:", json.dumps(res["gates"]))
    return 0


def _markdown(rep: Dict[str, Any]) -> str:
    r = rep["result"]
    d = r["outer_vs_inner_path_delta"]
    cd = rep["credit_carveout_diagnostics"]
    nwo = r["nested_capital_without"]
    nwi = r["nested_capital_with_inner_path"]
    nwo_node = r["nested_capital_with_outer_node"]
    gates = "\n".join("* {}: {}".format(k, "PASS" if v else "FAIL")
                      for k, v in r["gates"].items())
    lims = "\n".join("* " + x for x in rep["limitations"])
    return """# Phase 24 Task 3 - Inner-Path Management-Action Dynamics Prototype

Run: {ts}

## Verdict: {verdict}

The governed bonus-cut rule moves from the outer-node liability transform
into the inner-path benefit cashflows: only in-force policyholder benefits
(guaranteed + equity-guarantee PVs) are cuttable; the asset-side credit
loss and the analytic FX/liquidity offsets are carved out. The action
decision remains the pre-action outer-node coverage ratio (horizon-level
declared-rate response).

## Gates (fixed pre-registered, Phase 24 Task 1 design note s5)

{gates}

## Capital: outer-node vs inner-path with-actions basis (nested truth, n=500)

| metric | without actions | with (outer-node, Phase 23) | with (inner-path, this task) | inner - outer |
| --- | --- | --- | --- | --- |
| mean liability | {nwo_mean:.1f} | {on_mean:.1f} | {ip_mean:.1f} | {dmean:.1f} |
| VaR 99.5 | {nwo_var:.1f} | {on_var:.1f} | {ip_var:.1f} | {dvar:.1f} |
| ES | {nwo_es:.1f} | {on_es:.1f} | {ip_es:.1f} | {des:.1f} |
| SCR proxy | {nwo_scr:.1f} | {on_scr:.1f} | {ip_scr:.1f} | {dscr:.1f} |

{interp}

## Proxy OOS re-validation (inner-path with-actions basis)

* OOS R2: {r2:.4f} (without actions: {r2wo:.4f}; gate >= {r2g})
* Proxy-vs-nested VaR99.5 rel err: {vrel:.2%} (gate <= {vg:.0%})
* ES rel err: {esrel:.2%}; SCR rel err: {scrrel:.2%}
* Action active on {act:.1%} of nested outer states; {flo:.1%} at the floor.

## Proxy credit carve-out (matching analytic post-composition base)

* kappa (fit-calibrated, leakage-free): {kap:.4f}
* val nodes: mean abs rel err {vmae:.2%}, corr {vcorr:.4f}
* nested nodes: mean abs rel err {nmae:.2%}, corr {ncorr:.4f}
* credit share of 5d liability (nested mean): {cshare:.2%}

## Residual (documented)

{resid}

## Provenance

{prov}

## Limitations

{lims}

## Reproducibility

* Digest: `{digest}`

*EDUCATIONAL MODEL - management-action parameters are placeholders;
production sign-off withheld pending credentialled data + APS X2 review.*
""".format(
        ts=rep["run_timestamp"], verdict=rep["verdict"], gates=gates,
        nwo_mean=nwo["mean_liability"], on_mean=nwo_node["mean_liability"],
        ip_mean=nwi["mean_liability"],
        dmean=nwi["mean_liability"] - nwo_node["mean_liability"],
        nwo_var=nwo["var_liability"], on_var=nwo_node["var_liability"],
        ip_var=nwi["var_liability"], dvar=d["nested_var_99_5_delta"],
        nwo_es=nwo["es_liability"], on_es=nwo_node["es_liability"],
        ip_es=nwi["es_liability"],
        des=nwi["es_liability"] - nwo_node["es_liability"],
        nwo_scr=nwo["scr_proxy"], on_scr=nwo_node["scr_proxy"],
        ip_scr=nwi["scr_proxy"], dscr=d["nested_scr_delta"],
        interp=d["interpretation"],
        r2=r["oos_r2_with_actions_inner_path"],
        r2wo=r["oos_r2_without_actions"],
        r2g=rep["gates_definition"]["oos_r2_gate"],
        vrel=r["var_rel_error_with_actions"],
        vg=rep["gates_definition"]["var_rel_error_gate"],
        esrel=r["es_rel_error_with_actions"],
        scrrel=r["scr_rel_error_with_actions"],
        act=r["active_share_nested"], flo=r["floor_share_nested"],
        kap=cd["kappa_fit_calibrated"],
        vmae=cd["val_nodes"]["mean_abs_rel_error"],
        vcorr=cd["val_nodes"]["corr"],
        nmae=cd["nested_nodes"]["mean_abs_rel_error"],
        ncorr=cd["nested_nodes"]["corr"],
        cshare=cd["credit_share_of_liability_nested"],
        resid=rep["residual_documented"], prov=rep["primitives_provenance"],
        lims=lims, digest=rep["reproducibility_digest"])


def _card(rep: Dict[str, Any]) -> str:
    r = rep["result"]
    d = r["outer_vs_inner_path_delta"]
    return """# Inner-Path Action Dynamics Card (Phase 24 Task 3)

**What changed:** the governed reversionary-bonus cut now acts on the
INNER-PATH policyholder-benefit cashflows (guaranteed + equity-guarantee
PVs, in-force scaled) instead of uniformly rescaling the whole outer-node
conditional liability. Credit-loss (asset-side) and analytic FX/liquidity
offsets are no longer relieved.

* Decision unchanged: pre-action outer-node coverage ratio CR = A_ref / L.
* Per inner path i: PV_with_i = PV_i - relief(CR) * B_i.
* Proxy gains the matching analytic base B_hat = clip(poly5 - kappa*C_det, 0, L_hat);
  kappa fit-calibrated (leakage-free).

**Verdict: {verdict}** - OOS R2 {r2:.4f} (gate >= 0.95); VaR rel err
{vrel:.2%} (gate <= 10%); nested SCR with actions: outer-node basis
{on_scr:.1f} -> inner-path basis {ip_scr:.1f} (delta {dscr:+.1f};
the outer-node transform over-relieved non-cuttable components).

**Residual:** full path-wise dynamic declaration (per-time-step action)
remains out of scope - documented for a future phase.

**Use restrictions:** EDUCATIONAL_DEMONSTRATION_ONLY.

Evidence: docs/validation/PHASE24_TASK3_INNER_PATH_ACTION_REPORT.{{json,md}}
""".format(
        verdict=rep["verdict"], r2=r["oos_r2_with_actions_inner_path"],
        vrel=r["var_rel_error_with_actions"],
        on_scr=d["nested_scr_outer_node"], ip_scr=d["nested_scr_inner_path"],
        dscr=d["nested_scr_delta"])


def _has_change_record(store: GovernanceStore) -> bool:
    return any(rec.title == CHANGE_TITLE for rec in store.change_records)


def stage_governance() -> int:
    rep = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    r = rep["result"]
    d = r["outer_vs_inner_path_delta"]
    store = GovernanceStore.from_json(GOV_PATH.read_text(encoding="utf-8"))

    if _has_change_record(store):
        rec = next(x for x in store.change_records if x.title == CHANGE_TITLE)
        print("already applied:", rec.record_id)
        print("audit integrity:", store.audit_trail.verify_all())
        return 0

    if rep["verdict"] == "PASS":
        store.risk_register.get("MR-014").update_mitigation(
            MitigationStatus.MITIGATED,
            notes=(
                "Phase 24 Task 3 PASS: outer-node approximation relaxed - "
                "the bonus cut now enters the inner-path policyholder-"
                "benefit cashflows (credit-loss and FX/liquidity offsets "
                "carved out of the cuttable base); OOS R2 {r2:.4f}, VaR "
                "rel err {vrel:.2%} at the unchanged Phase 22 gates; "
                "nested with-actions SCR {on:.1f} (outer-node) -> {ip:.1f} "
                "(inner-path basis, delta {dl:+.1f} disclosed). Residual: "
                "full path-wise dynamic declaration out of scope; "
                "parameters remain educational placeholders."
            ).format(r2=r["oos_r2_with_actions_inner_path"],
                     vrel=r["var_rel_error_with_actions"],
                     on=d["nested_scr_outer_node"],
                     ip=d["nested_scr_inner_path"],
                     dl=d["nested_scr_delta"]),
        )

    rec = ChangeRecord.create(
        title=CHANGE_TITLE,
        description=(
            "Implemented Method B of the Phase 24 Task 1 design note: the "
            "governed reversionary-bonus participation cut applies to the "
            "inner-path projected policyholder-benefit cashflows "
            "(PV_with_i = PV_i - relief(CR_outer) * B_i, B_i = guaranteed "
            "+ equity-guarantee PV) instead of uniformly rescaling the "
            "outer-node conditional liability; the asset-side credit-loss "
            "PV and analytic FX/liquidity offsets are excluded from the "
            "cuttable base. Nested ground truth rebuilt from bit-identical "
            "re-runs of the archived Phase 22 Task 2 inner paths; the LSMC "
            "proxy gains the matching analytic post-composition benefit "
            "base (expected-path credit carve-out, fit-calibrated kappa, "
            "leakage-free). Seven-driver OOS re-validation at the "
            "unchanged Phase 22 gates."
        ),
        change_type="assumption_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "with_actions_basis": "outer-node uniform liability transform "
                                  "(Phase 23 Task 3)",
            "nested_var_99_5_with_outer_node": d["nested_var_99_5_outer_node"],
            "nested_scr_with_outer_node": d["nested_scr_outer_node"],
        },
        after_snapshot={
            "with_actions_basis": "inner-path benefit-cashflow cut "
                                  "(horizon-level declared-rate response)",
            "nested_var_99_5_with_inner_path": d["nested_var_99_5_inner_path"],
            "nested_scr_with_inner_path": d["nested_scr_inner_path"],
            "oos_r2_with_actions": r["oos_r2_with_actions_inner_path"],
            "var_rel_error_with_actions": r["var_rel_error_with_actions"],
            "kappa": rep["credit_carveout_diagnostics"]["kappa_fit_calibrated"],
            "gates": r["gates"],
            "verdict": rep["verdict"],
            "reproducibility_digest": rep["reproducibility_digest"],
        },
        impact_assessment=(
            "Refinement of the with-actions valuation basis (ASOP 56 "
            "3.1.3 outer-node vs inner-path; SII Art. 23 realism): the "
            "outer-node transform over-relieved non-cuttable components "
            "(asset-side credit loss, FX/liquidity offsets). The "
            "inner-path basis relieves less and is more conservative; the "
            "delta is disclosed at every capital level. Without-actions "
            "results unchanged (archived Phase 22 evidence intact)."
        ),
        quantitative_impact=(
            "Nested with-actions VaR99.5 {onv:.1f} (outer-node) -> "
            "{ipv:.1f} (inner-path, {dv:+.1f}); SCR {ons:.1f} -> {ips:.1f} "
            "({ds:+.1f}); OOS R2 with actions {r2:.4f}; proxy-vs-nested "
            "VaR rel err {vrel:.2%}; action active on {act:.1%} of outer "
            "states."
        ).format(onv=d["nested_var_99_5_outer_node"],
                 ipv=d["nested_var_99_5_inner_path"],
                 dv=d["nested_var_99_5_delta"],
                 ons=d["nested_scr_outer_node"],
                 ips=d["nested_scr_inner_path"], ds=d["nested_scr_delta"],
                 r2=r["oos_r2_with_actions_inner_path"],
                 vrel=r["var_rel_error_with_actions"],
                 act=r["active_share_nested"]),
        author=ACTOR,
        phase=PHASE,
        peer_reviewer="APS_X2_Independent_Reviewer",
        assumption_owner="ChiefActuary",
    )
    rec.submit_for_peer_review(
        ACTOR,
        "Inner-path action basis at fixed pre-registered gates; "
        "bit-identical primitive reuse exact-equality checked at every "
        "slice; outer-vs-inner delta and carve-out approximation error "
        "disclosed.",
    )
    rec.submit_to_owner(
        ACTOR,
        "Owner review requested. Production sign-off withheld pending "
        "credentialled management-practice data, full path-wise dynamic "
        "declaration, and independent APS X2 review.",
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
            "inner-path with-actions nested SCR {ip:.1f} (outer-node "
            "{on:.1f}, delta {dl:+.1f}); OOS R2 {r2:.4f}; VaR rel err "
            "{vrel:.2%}; gates {ng}/5 PASS".format(
                ip=d["nested_scr_inner_path"], on=d["nested_scr_outer_node"],
                dl=d["nested_scr_delta"],
                r2=r["oos_r2_with_actions_inner_path"],
                vrel=r["var_rel_error_with_actions"],
                ng=sum(r["gates"].values()))
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
                    choices=["verify", "components", "cdet", "actions",
                             "governance"])
    ap.add_argument("--part",
                    choices=["fit", "val", "nested", "fit_a", "fit_b",
                             "valeval"])
    ap.add_argument("--i0", type=int, default=0)
    ap.add_argument("--i1", type=int, default=0)
    a = ap.parse_args()
    if a.stage == "verify":
        sys.exit(stage_verify())
    if a.stage == "components":
        if not a.part:
            ap.error("--part required for components")
        sys.exit(stage_components(a.part, a.i0, a.i1))
    if a.stage == "cdet":
        if not a.part:
            ap.error("--part required for cdet")
        sys.exit(stage_cdet(a.part))
    if a.stage == "actions":
        sys.exit(stage_actions())
    sys.exit(stage_governance())
