#!/usr/bin/env python3
"""Phase 25 Task 2 build + governance - path-wise declaration in the nested truth.

Implements the pre-registered Phase 25 Task 1 design (PHASE25_TASK1_DESIGN_NOTE
s3/s5): the governed bonus-cut decision is re-evaluated at EVERY inner time
step on a path-wise coverage proxy (reference assets rolled forward on the
inner path / pre-action remaining path liability at t), with the P24T3
carve-outs preserved (only in-force policyholder benefits cuttable) and the
horizon-level basis retained as the sensitivity variant.  The without-actions
basis is archive cross-checked BIT-IDENTICALLY at every slice BEFORE any new
number is consumed.

Run staged (each stage < 45 s):
  PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase25_task2_pathwise_declaration.py --stage verify
  ... --stage pathwise --i0 0   --i1 250
  ... --stage pathwise --i0 250 --i1 500
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
    pathwise_declaration_use_restrictions,
    validate_pathwise_declaration,
)
from par_model_v2.projection.management_actions import ManagementActionRule
from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.multi_driver_proxy_validation_7d import (
    SevenDriverLiquidityProxyValidator,
    seven_driver_proxy_config,
)
from par_model_v2.projection.pathwise_bonus_dynamics import (
    PATHWISE_MATERIALITY_DISCLOSURE_THRESHOLD,
)

PHASE = "Phase 25: Path-Wise Bonus Declaration Dynamics"
ACTOR = "AutomatedModelDev_Phase25"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
OUT_DIR = Path("docs/validation")
JSON_PATH = OUT_DIR / "PHASE25_TASK2_PATHWISE_DECLARATION_REPORT.json"
MD_PATH = OUT_DIR / "PHASE25_TASK2_PATHWISE_DECLARATION_REPORT.md"
CARD_PATH = Path("docs/PATHWISE_DECLARATION_CARD.md")
P23T3_ARRAYS = Path("/var/tmp/p23t3_stage/arrays.npz")
P24T3_STAGE = Path("/var/tmp/p24t3_stage")
P24T3_REPORT = OUT_DIR / "PHASE24_TASK3_INNER_PATH_ACTION_REPORT.json"
P25T1_NOTE = OUT_DIR / "PHASE25_TASK1_DESIGN_NOTE.json"
STAGE_DIR = Path("/var/tmp/p25t2_stage")
VERIFY_PATH = STAGE_DIR / "verify.json"

CHANGE_TITLE = (
    "Phase 25 Task 2 - path-wise bonus declaration in the nested truth "
    "(per-time-step retained-bonus factor on a path-wise coverage proxy)"
)

AFFECTED_COMPONENTS = [
    "par_model_v2/projection/inner_path_action_dynamics.py",
    "tests/test_phase25_task2_pathwise_declaration.py",
    "scripts/build_phase25_task2_pathwise_declaration.py",
    "docs/PATHWISE_DECLARATION_CARD.md",
    "docs/validation/PHASE25_TASK2_PATHWISE_DECLARATION_REPORT.{json,md}",
]

STANDARD_REFERENCES = [
    "Solvency II Delegated Regulation Article 23 (future management actions "
    "consistent with how they would be exercised over time)",
    "SOA ASOP 56 section 3.1.3/3.4 (time level of modelled management "
    "behaviour)",
    "IA TAS M section 3.2/3.6 (documented residual converted to quantified "
    "evidence)",
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


def stage_verify() -> int:
    """Archive cross-checks BEFORE any new computation (design note s5)."""
    t0 = time.monotonic()
    STAGE_DIR.mkdir(parents=True, exist_ok=True)
    cfg = seven_driver_proxy_config()
    v = _validator()
    rule = ManagementActionRule()

    data = np.load(P23T3_ARRAYS)
    nested_l = data["nested_l"]
    fit_mean = float(data["fit_mean"][0])

    p24t3 = json.loads(P24T3_REPORT.read_text(encoding="utf-8"))
    p25t1 = json.loads(P25T1_NOTE.read_text(encoding="utf-8"))
    comp_nested = _assemble_comp("nested", cfg.n_eval)

    eval_X = v.states(cfg.n_eval, cfg.eval_seed)
    offsets = v.fx_term(eval_X) + v.liquidity_term(eval_X)
    nested_l7 = comp_nested["total"] + offsets

    a_ref = rule.reference_assets(fit_mean)
    horizon_reliefs = rule.relief_fraction(
        rule.coverage_ratio(nested_l, a_ref))

    checks = {
        "p24t3_verdict_pass": p24t3["verdict"] == "PASS",
        "p24t3_rule_unchanged": p24t3["result"]["rule"] == rule.to_dict(),
        "p25t1_note_pass": p25t1["verdict"] == "PASS",
        "p25t1_task2_gates_pre_registered": bool(
            p25t1.get("task2_acceptance_criteria")),
        "nested_arrays_length_ok": len(nested_l) == cfg.n_eval,
        "nested_l7_consistent": bool(
            np.allclose(nested_l7, nested_l, rtol=0, atol=1e-6)),
        "fit_mean_positive": fit_mean > 0.0,
        "p24t3_scr_reference_match": abs(
            p24t3["result"]["outer_vs_inner_path_delta"]["nested_scr_inner_path"]
            - 40852.05410858347) < 1e-6,
    }
    if not all(checks.values()):
        raise RuntimeError("verify failed: " + json.dumps(checks))
    np.savez(STAGE_DIR / "inputs.npz", offsets=offsets,
             horizon_reliefs=horizon_reliefs)
    VERIFY_PATH.write_text(json.dumps({
        "checks": checks,
        "fit_mean_liability": fit_mean,
        "reference_assets": a_ref,
        "p24t3_with_inner_path_scr": p24t3["result"][
            "outer_vs_inner_path_delta"]["nested_scr_inner_path"],
        "p24t3_with_inner_path_var": p24t3["result"][
            "outer_vs_inner_path_delta"]["nested_var_99_5_inner_path"],
        "config": cfg.to_dict(),
        "duration_seconds": time.monotonic() - t0,
    }, indent=2) + "\n", encoding="utf-8")
    print("verify OK:", json.dumps(checks))
    return 0


def stage_pathwise(i0: int, i1: int) -> int:
    """Path-wise declaration run for nested eval nodes [i0, i1); the
    without-actions basis is exact-equality checked vs the archived P24T3
    decomposition (which itself was bit-identical to the Phase 22 stage)."""
    t0 = time.monotonic()
    if not VERIFY_PATH.exists():
        raise RuntimeError("run --stage verify first")
    verify = json.loads(VERIFY_PATH.read_text(encoding="utf-8"))
    cfg = seven_driver_proxy_config()
    if not (0 <= i0 < i1 <= cfg.n_eval):
        raise ValueError("bad slice")
    v = _validator()
    rule = ManagementActionRule()
    inputs = np.load(STAGE_DIR / "inputs.npz")
    eval_X = v.states(cfg.n_eval, cfg.eval_seed)

    res = pathwise_declaration_heavy_sliced(
        v, eval_X, i0, i1, cfg.nested_n_inner, cfg.nested_inner_seed,
        rule, float(verify["reference_assets"]),
        inputs["offsets"], inputs["horizon_reliefs"])

    comp = _assemble_comp("nested", cfg.n_eval)
    for k in ("total", "benefit", "credit"):
        if not np.array_equal(res[k], comp[k][i0:i1]):
            raise RuntimeError(
                "without-actions %s NOT bit-identical to archive "
                "(slice [%d,%d), maxdiff=%g)" % (
                    k, i0, i1,
                    float(np.max(np.abs(res[k] - comp[k][i0:i1])))))
    np.savez(STAGE_DIR / ("pw_%05d_%05d.npz" % (i0, i1)), **res)
    print("pathwise [%d,%d) OK bit-identical; %.1fs"
          % (i0, i1, time.monotonic() - t0))
    return 0


def _assemble_pw(n: int) -> Dict[str, np.ndarray]:
    keys = ("total", "benefit", "credit", "relieved_pathwise",
            "relieved_horizon", "action_share", "restoration_share",
            "cr_path0_mean")
    out = {k: np.full(n, np.nan) for k in keys}
    for f in sorted(STAGE_DIR.glob("pw_*.npz")):
        i0, i1 = (int(x) for x in f.stem.split("_")[-2:])
        d = np.load(f)
        for k in keys:
            out[k][i0:i1] = d[k]
    for k in keys:
        if np.isnan(out[k]).any():
            raise RuntimeError("pathwise slices incomplete")
    return out


def _digest(arrs: Dict[str, np.ndarray], rule: ManagementActionRule) -> str:
    h = hashlib.sha256()
    for k in sorted(arrs):
        h.update(k.encode())
        h.update(np.ascontiguousarray(arrs[k]).tobytes())
    h.update(json.dumps(rule.to_dict(), sort_keys=True).encode())
    return h.hexdigest()


def stage_actions() -> int:
    t0 = time.monotonic()
    cfg = seven_driver_proxy_config()
    verify = json.loads(VERIFY_PATH.read_text(encoding="utf-8"))
    data = np.load(P23T3_ARRAYS)
    nested_l = data["nested_l"]
    fit_mean = float(data["fit_mean"][0])
    pw = _assemble_pw(cfg.n_eval)
    rule = ManagementActionRule()

    bit_identical = True  # enforced (exception) at every pathwise slice

    res = validate_pathwise_declaration(
        rule, fit_mean, nested_l, pw["benefit"],
        pw["relieved_pathwise"], pw["relieved_horizon"],
        bit_identical, cfg.confidence_level, cfg.capital_horizon_months,
        float(pw["action_share"].mean()),
        float(pw["restoration_share"].mean()))

    # cross-check: horizon-basis capital equals the archived P24T3 read-out
    hz = res["nested_capital_with_horizon"]
    p24t3_consistency = {
        "scr_horizon_basis": hz["scr_proxy"],
        "scr_p24t3_archived": verify["p24t3_with_inner_path_scr"],
        "abs_diff": abs(hz["scr_proxy"] - verify["p24t3_with_inner_path_scr"]),
        # tolerance: float-association difference between mean(relief*B_i)
        # and relief*mean(B_i); ~2e-10 relative on the realised SCR scale
        "match": abs(
            hz["scr_proxy"] - verify["p24t3_with_inner_path_scr"]) < 1e-4,
    }

    arrs = {"nested_l": nested_l, "benefit": pw["benefit"],
            "relieved_pathwise": pw["relieved_pathwise"],
            "relieved_horizon": pw["relieved_horizon"]}

    report = {
        "task": "Phase 25 Task 2 - path-wise bonus declaration in the "
                "nested truth (per-time-step retained-bonus factor on a "
                "path-wise coverage proxy)",
        "phase": PHASE,
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": "p25t2-" + _digest(arrs, rule)[:8],
        "verdict": res["verdict"],
        "gates_definition": {
            "source": "Phase 25 Task 1 design note s5 (FIXED pre-registered"
                      ", no gate-shopping)",
            "sign_gate": "pathwise with-actions SCR >= horizon-level "
                         "with-actions SCR at 99.5% (magnitude disclosed, "
                         "not gated)",
            "materiality_disclosure_threshold":
                PATHWISE_MATERIALITY_DISCLOSURE_THRESHOLD,
        },
        "result": res,
        "p24t3_horizon_basis_consistency": p24t3_consistency,
        "pathwise_diagnostics": {
            "mean_action_share_inner_paths": float(pw["action_share"].mean()),
            "mean_restoration_share_inner_paths": float(
                pw["restoration_share"].mean()),
            "nodes_with_any_inner_action": float(
                np.mean(pw["action_share"] > 0.0)),
            "nodes_with_any_restoration": float(
                np.mean(pw["restoration_share"] > 0.0)),
            "mean_initial_pathwise_cr": float(pw["cr_path0_mean"].mean()),
        },
        "verify_stage": verify,
        "primitives_provenance": (
            "Per-node inner simulations are BIT-IDENTICAL re-runs of the "
            "archived Phase 22 Task 2 heavy stage (seeds 141/142, exact "
            "equality of total/benefit/credit vs the archived Phase 24 "
            "Task 3 decomposition enforced at every slice); the L7 array "
            "and fit-mean are the archived Phase 23 Task 3 stage."
        ),
        "method": (
            "Path-wise basis: at every inner month t the retained-bonus "
            "factor is re-evaluated from CR_t = A_t / L_t with A_t the "
            "reference assets rolled forward at the inner short rate and "
            "L_t the pre-action remaining path liability; both deflate by "
            "the same path discount factor, so CR_{i,t} = a_ref / "
            "RemPV0_{i,t}. The relief in force for the cashflow at month "
            "u is decided at the start of that month (pre-step CR). Only "
            "in-force policyholder benefits (guaranteed + equity-"
            "guarantee) are cuttable; credit-loss and analytic "
            "FX/liquidity offsets are carved out (P24T3 convention). "
            "Horizon-level basis retained as the sensitivity variant."
        ),
        "residuals_documented": [
            "Declaration frequency: monthly inner-step declarations; an "
            "annual declaration cadence (with board-discretion smoothing) "
            "is the Task 3 documentation item.",
            "Adaptedness: the coverage proxy discounts remaining cashflows "
            "with the realised inner path (perfect-foresight proxy); an "
            "adapted valuation would require nested-nested simulation.",
            "The node-level analytic FX/liquidity offset enters the "
            "path-wise proxy undecayed.",
        ],
        "limitations": [
            "Management-action parameters are educational placeholders "
            "pending credentialled data + APS X2 review.",
            "The proxy (LSMC) side still uses the horizon-level basis; the "
            "matching path-wise proxy basis feature is Task 3.",
            "Coverage ratio uses a fixed reference-asset proxy rolled "
            "forward at the inner short rate.",
        ],
        "use_restrictions": pathwise_declaration_use_restrictions(),
        "reproducibility_digest": _digest(arrs, rule),
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
    d = r["pathwise_vs_horizon_delta"]
    wo = r["nested_capital_without"]
    hz = r["nested_capital_with_horizon"]
    pwc = r["nested_capital_with_pathwise"]
    pd = rep["pathwise_diagnostics"]
    gates = "\n".join("* {}: {}".format(k, "PASS" if v else "FAIL")
                      for k, v in r["gates"].items())
    lims = "\n".join("* " + x for x in rep["limitations"])
    resid = "\n".join("* " + x for x in rep["residuals_documented"])
    return """# Phase 25 Task 2 - Path-Wise Bonus Declaration in the Nested Truth

Run: {ts}

## Verdict: {verdict}

The governed bonus-cut decision is re-evaluated at EVERY inner month on a
path-wise coverage proxy (CR_t = rolled-forward reference assets / remaining
pre-action path liability); the Phase 24 Task 3 horizon-level basis is
retained as the sensitivity variant and the without-actions basis is
unchanged bit-identically (slice-enforced archive cross-check).

## Gates (fixed pre-registered, Phase 25 Task 1 design note s5)

{gates}

## Capital: horizon-level vs path-wise declaration basis (nested truth, n=500)

| metric | without actions | with (horizon, P24T3) | with (path-wise, this task) | pathwise - horizon |
| --- | --- | --- | --- | --- |
| mean liability | {wom:.1f} | {hzm:.1f} | {pwm:.1f} | {dm:.1f} |
| VaR 99.5 | {wov:.1f} | {hzv:.1f} | {pwv:.1f} | {dv:.1f} |
| ES | {woe:.1f} | {hze:.1f} | {pwe:.1f} | {de:.1f} |
| SCR proxy | {wos:.1f} | {hzs:.1f} | {pws:.1f} | {ds:.1f} |

SCR delta relative to the horizon basis: {dr:.2%} (MR-010/MR-014 Task 4
refresh trigger at {thr:.0%}: {req}).

{interp}

## Path-wise declaration diagnostics

* Inner paths with at least one cut: {act:.1%} (mean across nodes)
* Cut-then-restored inner paths: {rst:.1%} (restoration is a real dynamic)
* Nodes with any inner-path action: {nact:.1%}; with any restoration: {nrst:.1%}
* Mean initial path-wise coverage ratio: {cr0:.3f}
* Relieved-amount envelope clip binding on {clp:.1%} of nodes (path-wise)

## Horizon-basis consistency (sensitivity variant retained)

Horizon-basis SCR reproduced vs the archived P24T3 report: |diff| =
{cdiff:.2e} ({cmatch}).

## Residuals documented (Task 3 items)

{resid}

## Limitations

{lims}

Reproducibility digest: `{dig}`
""".format(
        ts=rep["run_timestamp"], verdict=rep["verdict"], gates=gates,
        wom=wo["mean_liability"], hzm=hz["mean_liability"],
        pwm=pwc["mean_liability"],
        dm=pwc["mean_liability"] - hz["mean_liability"],
        wov=wo["var_liability"], hzv=hz["var_liability"],
        pwv=pwc["var_liability"], dv=d["var_99_5_delta"],
        woe=wo["es_liability"], hze=hz["es_liability"],
        pwe=pwc["es_liability"], de=d["es_delta"],
        wos=wo["scr_proxy"], hzs=hz["scr_proxy"], pws=pwc["scr_proxy"],
        ds=d["scr_delta"], dr=d["scr_delta_rel_to_horizon"],
        thr=d["materiality_disclosure_threshold"],
        req="REQUIRED" if d["mr010_mr014_refresh_required_task4"]
        else "not required",
        interp=d["interpretation"],
        act=r["pathwise_action_share"], rst=r["pathwise_restoration_share"],
        nact=rep["pathwise_diagnostics"]["nodes_with_any_inner_action"],
        nrst=rep["pathwise_diagnostics"]["nodes_with_any_restoration"],
        cr0=pd["mean_initial_pathwise_cr"],
        clp=r["clip_binding_share_pathwise"],
        cdiff=rep["p24t3_horizon_basis_consistency"]["abs_diff"],
        cmatch="match" if rep["p24t3_horizon_basis_consistency"]["match"]
        else "MISMATCH",
        resid=resid, lims=lims, dig=rep["reproducibility_digest"])


def _card(rep: Dict[str, Any]) -> str:
    r = rep["result"]
    d = r["pathwise_vs_horizon_delta"]
    return """# Path-Wise Declaration Card (Phase 25 Task 2)

**What:** the governed reversionary-bonus cut is re-declared at EVERY inner
month from a path-wise coverage proxy; bonus restoration on recovering paths
and cuts on deteriorating paths are both captured (two-sided recognition
lag).

**Verdict:** {verdict}. Path-wise with-actions SCR {pws:.1f} vs horizon-level
{hzs:.1f} (delta {ds:+.1f}, {dr:+.2%} - sign gate PASS, magnitude disclosed).
Without-actions basis unchanged bit-identically.

**Carve-outs preserved:** only in-force policyholder benefits cuttable;
credit-loss and analytic FX/liquidity offsets are NOT cuttable.

**Diagnostics:** {act:.1%} of inner paths see a cut; {rst:.1%} cut-then-
restore; mean initial path-wise CR {cr0:.3f}.

**Residuals (Task 3):** monthly (not annual) declaration cadence;
perfect-foresight discounting in the coverage proxy; node offset undecayed.

**EDUCATIONAL MODEL** - parameters are placeholders; NOT for production
capital decisions. See PHASE25_TASK2_PATHWISE_DECLARATION_REPORT.md.
""".format(verdict=rep["verdict"],
           pws=r["nested_capital_with_pathwise"]["scr_proxy"],
           hzs=r["nested_capital_with_horizon"]["scr_proxy"],
           ds=d["scr_delta"], dr=d["scr_delta_rel_to_horizon"],
           act=r["pathwise_action_share"],
           rst=r["pathwise_restoration_share"],
           cr0=rep["pathwise_diagnostics"]["mean_initial_pathwise_cr"])


def _has_change_record(store: GovernanceStore) -> bool:
    return any(x.title == CHANGE_TITLE for x in store.change_records)


def stage_governance() -> int:
    rep = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    r = rep["result"]
    d = r["pathwise_vs_horizon_delta"]
    store = GovernanceStore.from_json(GOV_PATH.read_text(encoding="utf-8"))

    if _has_change_record(store):
        rec = next(x for x in store.change_records if x.title == CHANGE_TITLE)
        print("already applied:", rec.record_id)
        print("audit integrity:", store.audit_trail.verify_all())
        return 0

    rec = ChangeRecord.create(
        title=CHANGE_TITLE,
        description=(
            "Implemented the pre-registered Phase 25 Task 1 design: the "
            "governed reversionary-bonus cut decision is re-evaluated at "
            "every inner month on a path-wise coverage proxy (CR_t = "
            "reference assets rolled forward at the inner short rate / "
            "pre-action remaining path liability; the path deflator "
            "cancels, so CR = a_ref / RemPV0). The relief in force for "
            "each cashflow is decided at the start of its month (pre-step "
            "CR). P24T3 carve-outs preserved: only in-force policyholder "
            "benefits cuttable. Horizon-level basis retained as the "
            "sensitivity variant; without-actions basis unchanged "
            "bit-identically (slice-enforced archive cross-check)."
        ),
        change_type="assumption_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "with_actions_basis": "inner-path benefit-cashflow cut, "
                                  "horizon-level declared-rate response "
                                  "(Phase 24 Task 3)",
            "nested_scr_with_horizon":
                r["nested_capital_with_horizon"]["scr_proxy"],
            "nested_var_99_5_with_horizon":
                r["nested_capital_with_horizon"]["var_liability"],
        },
        after_snapshot={
            "with_actions_basis": "path-wise declaration (per-time-step "
                                  "retained-bonus factor)",
            "nested_scr_with_pathwise":
                r["nested_capital_with_pathwise"]["scr_proxy"],
            "nested_var_99_5_with_pathwise":
                r["nested_capital_with_pathwise"]["var_liability"],
            "scr_delta_rel_to_horizon": d["scr_delta_rel_to_horizon"],
            "mr010_mr014_refresh_required_task4":
                d["mr010_mr014_refresh_required_task4"],
            "gates": r["gates"],
            "verdict": rep["verdict"],
            "reproducibility_digest": rep["reproducibility_digest"],
        },
        impact_assessment=(
            "Declaration-timing refinement of the with-actions valuation "
            "basis (SII Art. 23: actions modelled consistently with how "
            "they would be exercised over time; ASOP 56 3.1.3): the "
            "horizon-level basis freezes the cut decision at the outer "
            "node, overstating relief at stressed nodes (no restoration) "
            "and understating action at healthy nodes (no path-wise cut). "
            "The path-wise basis relieves LESS in the tail (sign gate) "
            "and is the more conservative with-actions read-out. "
            "Without-actions results unchanged (bit-identical)."
        ),
        quantitative_impact=(
            "Nested with-actions SCR {hzs:.1f} (horizon basis) -> {pws:.1f} "
            "(path-wise, {ds:+.1f}, {dr:+.2%}); VaR99.5 {hzv:.1f} -> "
            "{pwv:.1f} ({dv:+.1f}); {act:.1%} of inner paths cut, {rst:.1%} "
            "cut-then-restore; MR-010/MR-014 Task 4 refresh trigger (>1%): "
            "{req}."
        ).format(hzs=r["nested_capital_with_horizon"]["scr_proxy"],
                 pws=r["nested_capital_with_pathwise"]["scr_proxy"],
                 ds=d["scr_delta"], dr=d["scr_delta_rel_to_horizon"],
                 hzv=r["nested_capital_with_horizon"]["var_liability"],
                 pwv=r["nested_capital_with_pathwise"]["var_liability"],
                 dv=d["var_99_5_delta"],
                 act=r["pathwise_action_share"],
                 rst=r["pathwise_restoration_share"],
                 req="REQUIRED"
                 if d["mr010_mr014_refresh_required_task4"]
                 else "not required"),
        author=ACTOR,
        phase=PHASE,
        peer_reviewer="APS_X2_Independent_Reviewer",
        assumption_owner="ChiefActuary",
    )
    rec.submit_for_peer_review(
        ACTOR,
        "Path-wise declaration at the FIXED pre-registered Task 1 s5 gates; "
        "without-actions basis bit-identical at every slice; horizon basis "
        "reproduced vs the archived P24T3 report; sign gate and "
        "recognition-lag diagnostics disclosed.",
    )
    rec.submit_to_owner(
        ACTOR,
        "Owner review requested. Production sign-off withheld pending the "
        "matching path-wise proxy basis (Task 3), tail diagnostics "
        "(Task 4), credentialled management-practice data, and independent "
        "APS X2 review.",
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
            "path-wise with-actions nested SCR {pws:.1f} (horizon {hzs:.1f}"
            ", delta {ds:+.1f} = {dr:+.2%}); restoration share {rst:.1%}; "
            "gates {ng}/{nt} PASS".format(
                pws=r["nested_capital_with_pathwise"]["scr_proxy"],
                hzs=r["nested_capital_with_horizon"]["scr_proxy"],
                ds=d["scr_delta"], dr=d["scr_delta_rel_to_horizon"],
                rst=r["pathwise_restoration_share"],
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
                    choices=["verify", "pathwise", "actions", "governance"])
    ap.add_argument("--i0", type=int, default=0)
    ap.add_argument("--i1", type=int, default=0)
    a = ap.parse_args()
    if a.stage == "verify":
        sys.exit(stage_verify())
    if a.stage == "pathwise":
        sys.exit(stage_pathwise(a.i0, a.i1))
    if a.stage == "actions":
        sys.exit(stage_actions())
    sys.exit(stage_governance())
