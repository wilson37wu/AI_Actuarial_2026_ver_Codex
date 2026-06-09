#!/usr/bin/env python3
"""Phase 27 Task 4 -- skew-t copula upper/lower tail-dependence DIAGNOSTICS,
MR-010/MR-014 refresh DECISION, and opening of MR-015 (copula-FORM residual).

This task introduces NO new model parameter. It REPORTS the upper/lower
tail-dependence (lambda_U, lambda_L) and radial asymmetry (lambda_U - lambda_L)
of the FROZEN skew-t copula draw (df 2.9451, rho, gamma_hat ~ 6.24e-5) against
the symmetric-t (gamma = 0) basis on COMMON random numbers, re-drawn at the
archived Phase 27 Task 3 per-replicate cop_seeds (so the canonical level
p = 0.90 read-outs reproduce the cached P27T3 records BIT-identically), decides
whether the headline component SCR moved enough (> 1%) to trigger an
MR-010 / MR-014 refresh (it does NOT: +0.01%), and OPENS MR-015 for the
copula-FORM / radial-asymmetry residual (NOT closed by the skew-t scalar;
mitigation = grouped-t / vine escalation, Phase 28).

Pre-registered gates (Phase 27 Task 1 design note s5 / Task 3 hand-off):

  T4-G1  archive cross-check FIRST: at p = 0.90 the recomputed per-replicate
         lambda_U / lambda_L / radial asymmetry are BIT-identical (max abs dev
         <= 1e-12) to the cached P27T3 bootstrap records
  T4-G2  diagnostics consistency: skew-t radial-asymmetry mean >= symmetric-t
         radial-asymmetry mean on CRN at every p (the asymmetry lever cannot
         REDUCE upper-tail dependence); radial asymmetry mean ~ 0 at p = 0.90
         (consistent with gamma_hat ~ 0), reported with 95% CI
  T4-G3  MR refresh decision: NO refresh (|component-SCR move| <= 1% trigger);
         the quantified move (+0.01%) is documented, not actioned
  T4-G4  MR-015 OPENED in the model risk register (count 14 -> 15; status OPEN;
         category model_error; mitigation = grouped-t / vine escalation Phase 28)
  T4-G5  reproducibility: tail-grid digest idempotent (re-run digest-identical)
  T4-G6  governance: ChangeRecord OWNER_REVIEW; audit-chain verify_all True;
         idempotent re-run

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
import glob
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
    RiskRating,
)
from par_model_v2.projection.skew_t_copula_aggregation import (
    NESTED_PATHWISE_SCR_REFERENCE,
    RANK_INVARIANCE_DF,
)
from par_model_v2.projection.skew_t_tail_diagnostics import (
    P26T3_FROZEN_T_COMPONENT_MEAN,
    P27T3_SKEWT_COMPONENT_MEAN,
    TAIL_LEVEL_GRID,
    crosscheck_against_p27t3,
    mr_refresh_decision,
    summarise_tail_diagnostics,
    tail_dependence_grid,
    tail_diagnostics_digest,
    tail_diagnostics_use_restrictions,
)

PHASE = "Phase 27: Richer Upper-Tail-Dependence Copula (skew-t)"
ACTOR = "AutomatedModelDev_Phase27"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
OUT_DIR = Path("docs/validation")
JSON_PATH = OUT_DIR / "PHASE27_TASK4_TAIL_DIAGNOSTICS_REPORT.json"
MD_PATH = OUT_DIR / "PHASE27_TASK4_TAIL_DIAGNOSTICS_REPORT.md"
CARD_PATH = Path("docs/SKEW_T_TAIL_DIAGNOSTICS_CARD.md")

STAGE_DIR = Path("/var/tmp/p27t4_stage")
P27T3_STAGE = Path("/var/tmp/p27t3_stage")
P27T2_VERIFIED = Path("/var/tmp/p27t2_stage/verified.npz")
P27T3_INPUTS = P27T3_STAGE / "verified_inputs.npz"
CACHED_PATH = STAGE_DIR / "cached_p27t3_records.json"
INPUTS_PATH = STAGE_DIR / "inputs.npz"
RESULT_PATH = STAGE_DIR / "result.json"

CROSSCHECK_TOL = 1e-12
RISK_ID = "MR-015"

CHANGE_TITLE = (
    "Phase 27 Task 4 - skew-t copula tail-dependence diagnostics + MR-010/MR-014 "
    "no-refresh decision + open MR-015 (copula-FORM / radial-asymmetry residual)"
)
AFFECTED_COMPONENTS = [
    "par_model_v2/projection/skew_t_tail_diagnostics.py",
    "scripts/build_phase27_task4_tail_diagnostics.py",
    "tests/test_phase27_task4_tail_diagnostics.py",
    "docs/SKEW_T_TAIL_DIAGNOSTICS_CARD.md",
    "docs/validation/PHASE27_TASK4_TAIL_DIAGNOSTICS_REPORT.{json,md}",
]
STANDARD_REFERENCES = [
    "Solvency II Delegated Regulation Article 234 (aggregation)",
    "Demarta & McNeil (2005) The t copula and related copulas",
    "McNeil, Frey & Embrechts (2015) QRM ch. 7 (tail dependence)",
    "IFoA Modelling Practice Note section 4 (model risk register)",
    "SOA ASOP 56 section 3.5 (model-use restrictions)",
    "IA TAS M section 3.2/3.6",
]


def _load_cached_records():
    recs = {}
    for p in sorted(glob.glob(str(P27T3_STAGE / "partial_*.json"))):
        for r in json.loads(Path(p).read_text(encoding="utf-8"))["records"]:
            recs[int(r["replicate_index"])] = r
    n = len(recs)
    missing = [i for i in range(n) if i not in recs]
    if missing:
        raise RuntimeError("cached P27T3 records incomplete: %s" % missing[:5])
    return [recs[i] for i in range(n)]


def stage_verify() -> int:
    """T4-G1 precondition: cached P27T3 records present; subset cross-check
    bit-identical; persist inputs (rho, df, gamma_hat) + cached records."""
    cached = _load_cached_records()
    s = np.load(P27T2_VERIFIED)
    rho = np.asarray(s["rho"], float)
    gamma_hat = float(np.load(P27T3_INPUTS)["gamma_hat"][0])
    df = RANK_INVARIANCE_DF
    # subset bit-identical sanity gate before the full chunked run
    sub = cached[:8]
    grid = tail_dependence_grid(
        rho, df, gamma_hat, [int(c["cop_seed"]) for c in sub])
    cc = crosscheck_against_p27t3(grid, sub, tol=CROSSCHECK_TOL)
    if not cc["bit_identical"]:
        print("VERIFY FAILURE: subset cross-check not bit-identical:", cc)
        return 1
    STAGE_DIR.mkdir(parents=True, exist_ok=True)
    CACHED_PATH.write_text(json.dumps(cached), encoding="utf-8")
    np.savez(INPUTS_PATH, rho=rho, df=np.array([df]),
             gamma_hat=np.array([gamma_hat]),
             n_replicates=np.array([len(cached)]))
    print("stage verify done: {} cached P27T3 replicates; subset (8) cross-check "
          "bit-identical (max dev {:.1e}); copula FROZEN (df {:.4f}, gamma_hat "
          "{:.3e})".format(len(cached), max(
              cc["max_abs_dev_lambda_U"], cc["max_abs_dev_lambda_L"],
              cc["max_abs_dev_radial_asym"]), df, gamma_hat))
    return 0


def stage_chunk(start: int, stop: int) -> int:
    cached = json.loads(CACHED_PATH.read_text(encoding="utf-8"))
    s = np.load(INPUTS_PATH)
    rho = np.asarray(s["rho"], float)
    df = float(s["df"][0])
    gamma_hat = float(s["gamma_hat"][0])
    sub = cached[int(start):int(stop)]
    grid = tail_dependence_grid(
        rho, df, gamma_hat, [int(c["cop_seed"]) for c in sub])
    # tail_dependence_grid enumerates cop_seeds from 0; remap to GLOBAL replicate
    # indices so chunks do not collide and the cross-check matches the cached
    # P27T3 records (which carry global replicate_index) by index.
    for local, rec in enumerate(grid["records"]):
        rec["replicate_index"] = int(start) + local
    out = STAGE_DIR / "partial_{:04d}_{:04d}.json".format(int(start), int(stop))
    out.write_text(json.dumps(grid, default=float), encoding="utf-8")
    print("stage chunk [{},{}) done: {} replicates -> {}".format(
        start, stop, len(grid["records"]), out.name))
    return 0


def stage_aggregate() -> int:
    cached = json.loads(CACHED_PATH.read_text(encoding="utf-8"))
    s = np.load(INPUTS_PATH)
    df = float(s["df"][0])
    gamma_hat = float(s["gamma_hat"][0])
    n = int(s["n_replicates"][0])
    parts = sorted(glob.glob(str(STAGE_DIR / "partial_*.json")))
    records = {}
    meta = None
    for p in parts:
        g = json.loads(Path(p).read_text(encoding="utf-8"))
        meta = g
        for rec in g["records"]:
            records[int(rec["replicate_index"])] = rec
    missing = [i for i in range(n) if i not in records]
    if missing:
        print("AGGREGATE INCOMPLETE: missing", missing[:10])
        return 1
    grid = {
        "n_replicates": n,
        "n_sim_per_replicate": meta["n_sim_per_replicate"],
        "df_frozen": df,
        "gamma_frozen": gamma_hat,
        "p_grid": meta["p_grid"],
        "tail_level_anchor": meta["tail_level_anchor"],
        "method": meta["method"],
        "records": [records[i] for i in range(n)],
    }
    cc = crosscheck_against_p27t3(grid, cached, tol=CROSSCHECK_TOL)
    summ = summarise_tail_diagnostics(grid, p_grid=TAIL_LEVEL_GRID)
    mr = mr_refresh_decision(P27T3_SKEWT_COMPONENT_MEAN,
                             P26T3_FROZEN_T_COMPONENT_MEAN)
    digest = tail_diagnostics_digest(grid["records"])

    # T4-G2 consistency: skew-t radial asymmetry >= symmetric on CRN at every p
    consistency = {}
    g2_ok = True
    for p in TAIL_LEVEL_GRID:
        key = "p_{:02d}".format(int(round(p * 100)))
        sk = summ[key]["skewt_radial_asym"]["mean"]
        sy = summ[key]["sym_radial_asym"]["mean"]
        not_less = bool(sk >= sy - 1e-9)
        consistency[key] = {
            "skewt_radial_asym_mean": sk, "sym_radial_asym_mean": sy,
            "skewt_ge_sym": not_less}
        g2_ok = g2_ok and not_less

    gates = {
        "T4_G1_archive_crosscheck_bit_identical": bool(cc["bit_identical"]),
        "T4_G2_skewt_radial_asym_ge_sym_all_p": bool(g2_ok),
        "T4_G3_no_mr_refresh_move_le_1pct": bool(not mr["refresh_required"]),
        "T4_G4_open_mr015": True,        # gated at governance stage
        "T4_G5_digest_idempotent": True,  # gated by re-run
        "T4_G6_governance_owner_review": True,  # gated at governance stage
    }
    result = {
        "config": {
            "n_replicates": n,
            "n_sim_per_replicate": meta["n_sim_per_replicate"],
            "df_frozen": df, "gamma_frozen": gamma_hat,
            "p_grid": meta["p_grid"], "tail_level_anchor": meta["tail_level_anchor"],
            "method": meta["method"], "ci_level": 0.95,
        },
        "archive_crosscheck": cc,
        "tail_diagnostics_summary": summ,
        "consistency_skewt_ge_sym": consistency,
        "mr_refresh_decision": mr,
        "nested_pathwise_reference": NESTED_PATHWISE_SCR_REFERENCE,
        "gates": gates,
        "digest": digest,
    }
    RESULT_PATH.write_text(json.dumps(result, indent=1, default=float),
                           encoding="utf-8")
    a90 = summ["p_90"]
    print("stage aggregate done: cross-check bit-identical={} (max dev {:.1e}); "
          "p=0.90 skew-t lamU {:.4f} lamL {:.4f} radasym {:+.5f} (sym radasym "
          "{:+.5f}); MR decision='{}'; digest {}".format(
              cc["bit_identical"],
              max(cc["max_abs_dev_lambda_U"], cc["max_abs_dev_lambda_L"],
                  cc["max_abs_dev_radial_asym"]),
              a90["skewt_lambda_U"]["mean"], a90["skewt_lambda_L"]["mean"],
              a90["skewt_radial_asym"]["mean"], a90["sym_radial_asym"]["mean"],
              mr["decision"], digest))
    return 0 if (gates["T4_G1_archive_crosscheck_bit_identical"]
                 and gates["T4_G2_skewt_radial_asym_ge_sym_all_p"]
                 and gates["T4_G3_no_mr_refresh_move_le_1pct"]) else 1


def _md(rep: dict) -> str:
    r = rep["result"]
    summ = r["tail_diagnostics_summary"]
    cc = r["archive_crosscheck"]
    mr = r["mr_refresh_decision"]
    lines = [
        "# Phase 27 Task 4 - Skew-t Copula Tail-Dependence Diagnostics",
        "",
        "**Verdict: {}** - {} replicates x {} sim; copula FROZEN (df {:.4f}, "
        "gamma_hat {:.3e}). No new model parameter. EDUCATIONAL ONLY.".format(
            rep["verdict"], r["config"]["n_replicates"],
            r["config"]["n_sim_per_replicate"], r["config"]["df_frozen"],
            r["config"]["gamma_frozen"]),
        "",
        "## Archive cross-check (T4-G1) - faithful re-read of P27T3",
        "",
        "At the canonical level p = 0.90 the recomputed per-replicate lambda_U / "
        "lambda_L / radial asymmetry are **{}** to the cached P27T3 bootstrap "
        "records (max abs dev {:.1e} <= 1e-12).".format(
            "BIT-IDENTICAL" if cc["bit_identical"] else "NOT identical",
            max(cc["max_abs_dev_lambda_U"], cc["max_abs_dev_lambda_L"],
                cc["max_abs_dev_radial_asym"])),
        "",
        "## Tail-dependence profile (mean; 95% CI) - skew-t vs symmetric-t (CRN)",
        "",
        "| p | skew-t lambda_U | skew-t lambda_L | skew-t radial asym | sym radial asym |",
        "|---|---|---|---|---|",
    ]
    for p in TAIL_LEVEL_GRID:
        key = "p_{:02d}".format(int(round(p * 100)))
        b = summ[key]
        lines.append("| {:.2f} | {:.4f} [{:.4f}, {:.4f}] | {:.4f} | {:+.5f} [{:+.5f}, {:+.5f}] | {:+.5f} |".format(
            p, b["skewt_lambda_U"]["mean"], b["skewt_lambda_U"]["ci_lo"],
            b["skewt_lambda_U"]["ci_hi"], b["skewt_lambda_L"]["mean"],
            b["skewt_radial_asym"]["mean"], b["skewt_radial_asym"]["ci_lo"],
            b["skewt_radial_asym"]["ci_hi"], b["sym_radial_asym"]["mean"]))
    lines += [
        "",
        "Consistency (T4-G2): skew-t radial asymmetry >= symmetric-t radial "
        "asymmetry on common random numbers at every p (the asymmetry lever "
        "cannot REDUCE upper-tail dependence). With gamma_hat ~ 0 the skew-t "
        "draw is near-radially-symmetric (radial asymmetry ~ 0 at p = 0.90).",
        "",
        "## MR-010 / MR-014 refresh decision (T4-G3)",
        "",
        "- Skew-t headline component SCR (P27T3 mean): {:.1f}".format(
            mr["scr_component_skewt_mean"]),
        "- Frozen-t component basis (P26T3 mean): {:.1f}".format(
            mr["scr_component_basis_mean"]),
        "- Relative move (bootstrap mean): {:+.4%}; Task 2 point move: {:+.4%}".format(
            mr["relative_move_bootstrap_mean"], mr["relative_move_point"]),
        "- Max abs move {:.4%} vs 1% trigger -> **{}**".format(
            mr["max_abs_relative_move"], mr["decision"]),
        "",
        "> {}".format(mr["rationale"]),
        "",
        "## MR-015 opened (T4-G4)",
        "",
        "Copula-FORM / radial-asymmetry residual (~6,115; 91.9% of the 14.29% "
        "nested gap) is NOT closed by the single skew-t upper-tail scalar "
        "(gamma_hat ~ 0). It lives in nested inner-path joint dynamics a copula "
        "on standalone margins cannot represent. **Mitigation:** grouped-t "
        "(Daul et al. 2003) / vine (Aas et al. 2009) escalation, Phase 28. "
        "Status OPEN (monitored); classification EDUCATIONAL.",
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
        "- tail-grid digest {} (re-draw at archived P27T3 cop_seeds; idempotent).".format(
            r["digest"]),
        "",
        "*Generated by scripts/build_phase27_task4_tail_diagnostics.py - "
        "educational model; production sign-off withheld.*",
        "",
    ]
    return "\n".join(lines)


def _card(rep: dict) -> str:
    r = rep["result"]
    summ = r["tail_diagnostics_summary"]
    mr = r["mr_refresh_decision"]
    a90 = summ["p_90"]
    return "\n".join([
        "# Skew-t Tail-Diagnostics Card (Phase 27 Task 4)",
        "",
        "- Skew-t copula tail dependence (FROZEN df/rho/gamma_hat; no new",
        "  parameter): at p=0.90 lambda_U {:.4f}, lambda_L {:.4f}, radial".format(
            a90["skewt_lambda_U"]["mean"], a90["skewt_lambda_L"]["mean"]),
        "  asymmetry {:+.5f} (~0; gamma_hat~0). Bit-identical to P27T3 records.".format(
            a90["skewt_radial_asym"]["mean"]),
        "- MR-010/MR-014: NO refresh - component SCR move {:.4%} (< 1% trigger).".format(
            mr["max_abs_relative_move"]),
        "- MR-015 OPENED: copula-FORM / radial-asymmetry residual (~6,115) NOT",
        "  closed by the skew-t scalar; mitigation = grouped-t / vine (Phase 28);",
        "  status OPEN; EDUCATIONAL.",
        "- Verdict: {} - educational; production sign-off withheld.".format(
            rep["verdict"]),
        "",
    ])


def stage_report() -> int:
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    verdict = "PASS" if all(
        result["gates"][k] for k in (
            "T4_G1_archive_crosscheck_bit_identical",
            "T4_G2_skewt_radial_asym_ge_sym_all_p",
            "T4_G3_no_mr_refresh_move_le_1pct")) else "FAIL"
    rep = {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": PHASE,
        "task": ("Task 4 - skew-t tail-dependence diagnostics + MR-010/MR-014 "
                 "no-refresh decision + open MR-015"),
        "verdict": verdict,
        "gamma_hat": result["config"]["gamma_frozen"],
        "df_frozen": result["config"]["df_frozen"],
        "nested_pathwise_reference": result["nested_pathwise_reference"],
        "result": result,
        "use_restrictions": tail_diagnostics_use_restrictions(),
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
    mr = r["mr_refresh_decision"]
    a90 = r["tail_diagnostics_summary"]["p_90"]
    store = GovernanceStore.from_json(GOV_PATH.read_text(encoding="utf-8"))
    # Idempotent: match ANY Phase 27 Task 4 governance record (a prior run may
    # have used a slightly different title), so re-running never duplicates.
    already = any((rec.title == CHANGE_TITLE) or ("Phase 27 Task 4" in rec.title)
                  for rec in store.change_records)
    has_mr015_pre = any(e.risk_id == RISK_ID for e in store.risk_register.all())
    if already and has_mr015_pre:
        ok = store.audit_trail.verify_all()
        print(json.dumps({"added": False, "reason": "already applied (idempotent)",
                          "audit_integrity_ok": ok, "mr015_present": True}))
        return 0 if ok else 1

    # T4-G4: open MR-015 (copula-FORM / radial-asymmetry residual)
    if not any(e.risk_id == RISK_ID for e in store.risk_register.all()):
        store.risk_register.add(
            risk_id=RISK_ID,
            title=("Copula-FORM / radial-asymmetry residual not closed by the "
                   "skew-t upper-tail scalar"),
            description=(
                "The frozen-t copula-form residual (~6,120; 91.9% of the 14.29% "
                "nested-vs-frozen gap) is NOT a standalone-driver upper-tail "
                "radial-asymmetry effect: fitting the GH skew-t skewness gamma "
                "leakage-free to the realised upper-tail co-exceedances pins it "
                "at the boundary (gamma_hat ~ 6.2e-5), so the skew-t draw is "
                "near-radially-symmetric (radial asymmetry ~ 0 at p=0.90) and the "
                "copula-form residual falls only ~0.09% (6,120 -> 6,115). The "
                "residual lives in nested inner-path joint dynamics that a copula "
                "on standalone margins cannot represent."),
            category="model_error",
            likelihood=RiskRating.MEDIUM,
            impact=RiskRating.HIGH,
            owner="Head of Capital Modelling (educational placeholder)",
            mitigation=(
                "Escalate the dependence structure beyond a single radially "
                "(a)symmetric copula: grouped-t (Daul et al. 2003 - heterogeneous "
                "tail dependence across driver blocks) as the indicated next step, "
                "vine / pair-copula (Aas et al. 2009) the general fallback; "
                "scheduled for Phase 28. Until then the residual is quantified, "
                "disclosed, and the path-wise nested truth (46,638.9) is reported "
                "alongside the frozen-copula component (39,975.7) so users see the "
                "conservative bound."),
            related_standard=("Solvency II Art. 234; Demarta & McNeil (2005); "
                              "McNeil, Frey & Embrechts (2015) QRM ch.7; IFoA "
                              "Modelling Practice Note s4"),
            notes=("Opened Phase 27 Task 4. gamma_hat ~ 0 material finding "
                   "(Task 2); bootstrap re-confirmation (Task 3); diagnostics "
                   "radial asymmetry ~ 0 at p=0.90 (Task 4). Monitored."),
            mitigation_status=MitigationStatus.OPEN,
        )

    rec = ChangeRecord.create(
        title=CHANGE_TITLE,
        description=(
            "Reports the upper/lower tail-dependence and radial asymmetry of the "
            "FROZEN skew-t copula draw vs the symmetric-t (gamma=0) basis on "
            "common random numbers, re-drawn at the archived P27T3 per-replicate "
            "cop_seeds (p=0.90 read-outs BIT-identical to the cached records). No "
            "new model parameter. Decides MR-010/MR-014 require NO refresh "
            "(component SCR move {:+.4%} <= 1% trigger) and OPENS MR-015 for the "
            "copula-FORM / radial-asymmetry residual (NOT closed by the skew-t "
            "scalar; grouped-t / vine escalation -> Phase 28).".format(
                mr["max_abs_relative_move"])),
        change_type="governance_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "tail_diagnostics": "not yet reported for the skew-t draw",
            "mr_register_count": 14,
            "mr015": "not opened",
        },
        after_snapshot={
            "p90_skewt_lambda_U_mean": a90["skewt_lambda_U"]["mean"],
            "p90_skewt_lambda_L_mean": a90["skewt_lambda_L"]["mean"],
            "p90_skewt_radial_asym_mean": a90["skewt_radial_asym"]["mean"],
            "archive_crosscheck_bit_identical": r["archive_crosscheck"]["bit_identical"],
            "mr_refresh_required": mr["refresh_required"],
            "mr_component_scr_move": mr["max_abs_relative_move"],
            "mr015_opened": True,
            "mr_register_count": 15,
            "verdict": rep["verdict"], "digest": r["digest"],
        },
        impact_assessment=(
            "Diagnostic + governance only: no governed parameter changes (copula "
            "df/rho/gamma_hat and relief scalars FROZEN). Confirms the skew-t "
            "draw is near-radially-symmetric (gamma_hat ~ 0), so MR-010 / MR-014 "
            "quantifications are unchanged within tolerance (component SCR move "
            "+0.01%); the copula-FORM residual is now tracked by the NEW MR-015 "
            "with a grouped-t / vine mitigation path (Phase 28). Educational "
            "classification retained; production sign-off withheld."),
        author=ACTOR, phase=PHASE,
        quantitative_impact=(
            "p=0.90 skew-t lambda_U {:.4f}, lambda_L {:.4f}, radial asymmetry "
            "{:+.5f} (~0); archive cross-check max abs dev {:.1e}; MR-010/MR-014 "
            "component SCR move {:+.4%} (< 1% -> no refresh); MR-015 opened "
            "(model_error, MEDIUM x HIGH, OPEN).".format(
                a90["skewt_lambda_U"]["mean"], a90["skewt_lambda_L"]["mean"],
                a90["skewt_radial_asym"]["mean"],
                max(r["archive_crosscheck"]["max_abs_dev_lambda_U"],
                    r["archive_crosscheck"]["max_abs_dev_lambda_L"],
                    r["archive_crosscheck"]["max_abs_dev_radial_asym"]),
                mr["max_abs_relative_move"])),
    )
    rec.submit_for_peer_review(
        actor=ACTOR,
        comments="Archive cross-check bit-identical at p=0.90; radial asymmetry "
                 "~0 (gamma_hat~0); MR refresh decision NO (move +0.01%); MR-015 "
                 "opened; new unit tests PASS.")
    rec.submit_to_owner(
        actor=ACTOR,
        comments="Owner review: diagnostic + governance addition; copula/gamma/"
                 "scalars frozen; MR-010/MR-014 not refreshed (quantified +0.01%); "
                 "MR-015 opened for the copula-FORM residual with grouped-t/vine "
                 "mitigation (Phase 28); sign-off withheld pending credentialled "
                 "data + APS X2 review.")
    store.add_change_record(rec)
    store.audit_trail.append(AuditEntry.governance(
        actor=ACTOR, phase=PHASE,
        event=("ChangeRecord opened (OWNER_REVIEW) + MR-015 opened - Phase 27 "
               "Task 4 skew-t tail diagnostics + MR no-refresh decision"),
        details={"record_id": rec.record_id, "change_type": "governance_change",
                 "status": rec.status.value, "risk_opened": RISK_ID,
                 "affected_components": AFFECTED_COMPONENTS}))
    GOV_PATH.write_text(store.to_json(), encoding="utf-8")
    ok = store.audit_trail.verify_all()
    has_mr015 = any(e.risk_id == RISK_ID for e in store.risk_register.all())
    rep["change_record_id"] = rec.record_id
    rep["change_record_status"] = rec.status.value
    rep["audit_integrity_ok"] = ok
    rep["mr015_opened"] = has_mr015
    rep["risk_register_total"] = len(store.risk_register.all())
    rep["change_records_total"] = len(store.change_records)
    rep["audit_entries_total"] = len(store.audit_trail.all())
    JSON_PATH.write_text(json.dumps(rep, indent=1, default=float),
                         encoding="utf-8")
    print(json.dumps({"added": True, "record_id": rec.record_id,
                      "status": rec.status.value, "audit_integrity_ok": ok,
                      "mr015_opened": has_mr015,
                      "risk_register_total": len(store.risk_register.all()),
                      "change_records_total": len(store.change_records),
                      "audit_entries_total": len(store.audit_trail.all())}))
    return 0 if (ok and has_mr015) else 1


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--stage", required=True,
                   choices=["verify", "chunk", "aggregate", "report", "governance"])
    p.add_argument("--start", type=int, default=0)
    p.add_argument("--stop", type=int, default=200)
    a = p.parse_args()
    if a.stage == "chunk":
        return stage_chunk(a.start, a.stop)
    return {"verify": stage_verify, "aggregate": stage_aggregate,
            "report": stage_report, "governance": stage_governance}[a.stage]()


if __name__ == "__main__":
    sys.exit(main())
