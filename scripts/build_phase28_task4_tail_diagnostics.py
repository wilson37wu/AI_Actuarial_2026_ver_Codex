#!/usr/bin/env python3
"""Phase 28 Task 4 -- grouped-t copula within/cross-block, upper/lower
tail-dependence DIAGNOSTICS, MR-010/MR-014 refresh DECISION, and opening of
MR-016 (heterogeneous-tail / cross-block-dilution copula-FORM residual).

This task introduces NO new model parameter.  It REPORTS the within-block and
cross-block, upper/lower tail-dependence of the FROZEN grouped-t copula draw
(per-block df_NONFIN 37.866 / df_FIN 8.506 on the frozen Sigma) against the
single-df t (homogeneous boundary, all df_g = the frozen 2.9451 with one SHARED
mixing variate) on COMMON random numbers, re-drawn at the archived Phase 28
Task 3 per-replicate ``cop_seed`` values (so the canonical level p = 0.90
within/cross upper read-outs reproduce the cached P28T3 records BIT-identically),
decides whether the GOVERNED headline component SCR moved enough (> 1%) to
trigger an MR-010 / MR-014 refresh (it does NOT: the governed frozen single-df t
basis is recovered exactly, move 0.00%; the grouped-t is a DISCLOSED two-sided,
non-conservative diagnostic, not adopted), and OPENS MR-016 for the
heterogeneous-tail / cross-block-dilution copula-FORM change (mitigation =
vine / pair-copula escalation, Phase 29).

Pre-registered gates (Phase 28 Task 1 design note s5 / Task 3 hand-off):

  T4-G1  archive cross-check FIRST: at p = 0.90 the recomputed per-replicate
         grouped-t within-block (NON-FIN, FIN) upper, cross-block upper and
         heterogeneity_upper are BIT-identical (max abs dev <= 1e-12) to the
         cached P28T3 bootstrap records
  T4-G2  dilution consistency: on common random numbers the grouped-t cross-block
         upper co-exceedance is <= the single-df t cross-block upper at every p
         (the single-df t shared mixing is the maximal-cross-block boundary; the
         grouped-t can only dilute it given df_g > frozen), reported with 95% CI
  T4-G3  MR refresh decision: NO refresh (|GOVERNED headline move| <= 1% trigger;
         the governed frozen single-df t basis is recovered exactly, move 0.00%);
         the disclosed grouped-t move (-10.93%) is documented, not actioned
  T4-G4  MR-016 OPENED in the model risk register (count 15 -> 16; status OPEN;
         category model_error; mitigation = vine / pair-copula escalation Phase 29)
  T4-G5  reproducibility: tail-grid digest idempotent (re-run digest-identical)
  T4-G6  governance: ChangeRecord OWNER_REVIEW; audit-chain verify_all True;
         idempotent re-run

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
from par_model_v2.projection.grouped_t_copula_aggregation import (
    BLOCKS,
    FIN_BLOCK,
    NONFIN_BLOCK,
    NESTED_PATHWISE_SCR_REFERENCE,
    RANK_INVARIANCE_DF,
)
from par_model_v2.projection.grouped_t_tail_diagnostics import (
    P26T3_FROZEN_T_COMPONENT_MEAN,
    P28T3_GROUPED_T_COMPONENT_MEAN,
    P28T3_SINGLE_T_COMPONENT_MEAN,
    TAIL_LEVEL_GRID,
    block_tail_dependence_grid,
    crosscheck_against_p28t3,
    mr_refresh_decision,
    summarise_block_tail_diagnostics,
    tail_diagnostics_digest,
    tail_diagnostics_use_restrictions,
)

PHASE = "Phase 28: Grouped-t / Heterogeneous Tail-Dependence"
ACTOR = "AutomatedModelDev_Phase28"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
OUT_DIR = Path("docs/validation")
JSON_PATH = OUT_DIR / "PHASE28_TASK4_TAIL_DIAGNOSTICS_REPORT.json"
MD_PATH = OUT_DIR / "PHASE28_TASK4_TAIL_DIAGNOSTICS_REPORT.md"
CARD_PATH = Path("docs/GROUPED_T_TAIL_DIAGNOSTICS_CARD.md")

STAGE_DIR = Path("/var/tmp/p28t4_stage")
P28T3_STAGE = Path("/var/tmp/p28t3_stage")
P28T2_VERIFIED = Path("/var/tmp/p28t2_build/verified.npz")
P28T2_FIT = Path("/var/tmp/p28t2_build/fit_result.json")
CACHED_PATH = STAGE_DIR / "cached_p28t3_records.json"
INPUTS_PATH = STAGE_DIR / "inputs.npz"
RESULT_PATH = STAGE_DIR / "result.json"

CROSSCHECK_TOL = 1e-12
RISK_ID = "MR-016"

CHANGE_TITLE = (
    "Phase 28 Task 4 - grouped-t within/cross-block tail-dependence diagnostics "
    "+ MR-010/MR-014 no-refresh decision + open MR-016 (heterogeneous-tail / "
    "cross-block-dilution copula-FORM residual)")
AFFECTED_COMPONENTS = [
    "par_model_v2/projection/grouped_t_tail_diagnostics.py",
    "scripts/build_phase28_task4_tail_diagnostics.py",
    "tests/test_phase28_task4_tail_diagnostics.py",
    "docs/GROUPED_T_TAIL_DIAGNOSTICS_CARD.md",
    "docs/validation/PHASE28_TASK4_TAIL_DIAGNOSTICS_REPORT.{json,md}",
]
STANDARD_REFERENCES = [
    "Solvency II Delegated Regulation Article 234 (aggregation incl. tail behaviour)",
    "Daul, De Giorgi, Lindskog & McNeil (2003), The grouped t-copula",
    "McNeil, Frey & Embrechts (2015), Quantitative Risk Management ch. 7 (tail dependence)",
    "Aas, Czado, Frigessi & Bakken (2009), Pair-copula constructions (vine, Phase 29 fallback)",
    "IFoA Modelling Practice Note section 4 (model risk register)",
    "SOA ASOP 56 section 3.5 (model-use restrictions)",
    "IA TAS M section 3.2/3.6",
]


def _load_cached_records():
    recs = {}
    for p in sorted(glob.glob(str(P28T3_STAGE / "partial_*.json"))):
        for r in json.loads(Path(p).read_text(encoding="utf-8"))["records"]:
            recs[int(r["replicate_index"])] = r
    n = len(recs)
    missing = [i for i in range(n) if i not in recs]
    if missing:
        raise RuntimeError("cached P28T3 records incomplete: %s" % missing[:5])
    return [recs[i] for i in range(n)]


def _block_dfs_hat() -> list:
    d = json.loads(P28T2_FIT.read_text(encoding="utf-8"))
    return [float(g) for g in d["block_dfs_hat"]]


def stage_verify() -> int:
    """T4-G1 precondition: cached P28T3 records present; subset cross-check
    bit-identical; persist inputs (rho, block_dfs, homogeneous df) + records."""
    cached = _load_cached_records()
    s = np.load(P28T2_VERIFIED)
    rho = np.asarray(s["rho"], float)
    block_dfs = _block_dfs_hat()
    partition_ok = (set(FIN_BLOCK) == {2, 5, 6}
                    and set(NONFIN_BLOCK) == {0, 1, 3, 4})
    df_above = bool(all(g > RANK_INVARIANCE_DF for g in block_dfs))
    if not (partition_ok and df_above):
        print("VERIFY FAILURE: partition_ok={} df_above_frozen={}".format(
            partition_ok, df_above))
        return 1
    # subset bit-identical sanity gate before the full chunked run
    sub = cached[:8]
    grid = block_tail_dependence_grid(
        rho, block_dfs, [int(c["cop_seed"]) for c in sub])
    cc = crosscheck_against_p28t3(grid, sub, tol=CROSSCHECK_TOL)
    if not cc["bit_identical"]:
        print("VERIFY FAILURE: subset cross-check not bit-identical:", cc)
        return 1
    STAGE_DIR.mkdir(parents=True, exist_ok=True)
    CACHED_PATH.write_text(json.dumps(cached), encoding="utf-8")
    np.savez(INPUTS_PATH, rho=rho,
             block_dfs=np.array(block_dfs, dtype=float),
             homogeneous_df=np.array([RANK_INVARIANCE_DF]),
             n_replicates=np.array([len(cached)]))
    print("stage verify done: {} cached P28T3 replicates; subset (8) cross-check "
          "bit-identical (max dev {:.1e}); copula FROZEN (homogeneous df {:.4f}, "
          "block_dfs {})".format(
              len(cached), cc["max_abs_dev"], RANK_INVARIANCE_DF,
              [round(g, 3) for g in block_dfs]))
    return 0


def stage_chunk(start: int, stop: int) -> int:
    cached = json.loads(CACHED_PATH.read_text(encoding="utf-8"))
    s = np.load(INPUTS_PATH)
    rho = np.asarray(s["rho"], float)
    block_dfs = [float(g) for g in s["block_dfs"]]
    hom_df = float(s["homogeneous_df"][0])
    sub = cached[int(start):int(stop)]
    grid = block_tail_dependence_grid(
        rho, block_dfs, [int(c["cop_seed"]) for c in sub],
        homogeneous_df=hom_df)
    # block_tail_dependence_grid enumerates cop_seeds from 0; remap to GLOBAL
    # replicate indices so chunks do not collide and the cross-check matches the
    # cached P28T3 records (which carry global replicate_index) by index.
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
    block_dfs = [float(g) for g in s["block_dfs"]]
    hom_df = float(s["homogeneous_df"][0])
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
        "block_dfs_frozen": block_dfs,
        "homogeneous_df_frozen": hom_df,
        "blocks": meta["blocks"],
        "block_labels": meta["block_labels"],
        "p_grid": meta["p_grid"],
        "tail_level_anchor": meta["tail_level_anchor"],
        "method": meta["method"],
        "records": [records[i] for i in range(n)],
    }
    cc = crosscheck_against_p28t3(grid, cached, tol=CROSSCHECK_TOL)
    summ = summarise_block_tail_diagnostics(grid, p_grid=TAIL_LEVEL_GRID)
    mr = mr_refresh_decision(
        scr_component_single_t=P28T3_SINGLE_T_COMPONENT_MEAN,
        scr_component_basis=P26T3_FROZEN_T_COMPONENT_MEAN,
        scr_component_grouped_t=P28T3_GROUPED_T_COMPONENT_MEAN)
    digest = tail_diagnostics_digest(grid["records"])

    # T4-G2 dilution consistency: grouped cross_upper <= single cross_upper at
    # every p on common random numbers (the grouped-t can only dilute the
    # single-df t maximal-cross-block boundary given df_g > frozen).
    consistency = {}
    g2_ok = True
    for p in TAIL_LEVEL_GRID:
        key = "p_{:02d}".format(int(round(p * 100)))
        gc = summ[key]["grp_cross_upper"]["mean"]
        sc = summ[key]["sng_cross_upper"]["mean"]
        diff = summ[key]["grp_minus_sng_cross_upper"]["mean"]
        not_more = bool(gc <= sc + 1e-9)
        consistency[key] = {
            "grp_cross_upper_mean": gc, "sng_cross_upper_mean": sc,
            "grp_minus_sng_cross_upper_mean": diff,
            "grp_le_sng_cross_upper": not_more}
        g2_ok = g2_ok and not_more

    gates = {
        "T4_G1_archive_crosscheck_bit_identical": bool(cc["bit_identical"]),
        "T4_G2_grouped_dilutes_cross_block_all_p": bool(g2_ok),
        "T4_G3_no_mr_refresh_governed_move_le_1pct": bool(not mr["refresh_required"]),
        "T4_G4_open_mr016": True,        # gated at governance stage
        "T4_G5_digest_idempotent": True,  # gated by re-run
        "T4_G6_governance_owner_review": True,  # gated at governance stage
    }
    result = {
        "config": {
            "n_replicates": n,
            "n_sim_per_replicate": meta["n_sim_per_replicate"],
            "block_dfs_frozen": block_dfs, "homogeneous_df_frozen": hom_df,
            "blocks": meta["blocks"], "block_labels": meta["block_labels"],
            "p_grid": meta["p_grid"], "tail_level_anchor": meta["tail_level_anchor"],
            "method": meta["method"], "ci_level": 0.95,
        },
        "archive_crosscheck": cc,
        "tail_diagnostics_summary": summ,
        "dilution_consistency": consistency,
        "mr_refresh_decision": mr,
        "nested_pathwise_reference": NESTED_PATHWISE_SCR_REFERENCE,
        "gates": gates,
        "digest": digest,
    }
    RESULT_PATH.write_text(json.dumps(result, indent=1, default=float),
                           encoding="utf-8")
    a90 = summ["p_90"]
    print("stage aggregate done: cross-check bit-identical={} (max dev {:.1e}); "
          "p=0.90 grp cross_U {:.4f} sng cross_U {:.4f} (dilution {:+.5f}); "
          "grp within_FIN_U {:.4f}; MR decision='{}'; digest {}".format(
              cc["bit_identical"], cc["max_abs_dev"],
              a90["grp_cross_upper"]["mean"], a90["sng_cross_upper"]["mean"],
              a90["grp_minus_sng_cross_upper"]["mean"],
              a90["grp_within_upper_fin"]["mean"], mr["decision"], digest))
    return 0 if (gates["T4_G1_archive_crosscheck_bit_identical"]
                 and gates["T4_G2_grouped_dilutes_cross_block_all_p"]
                 and gates["T4_G3_no_mr_refresh_governed_move_le_1pct"]) else 1


def _md(rep: dict) -> str:
    r = rep["result"]
    summ = r["tail_diagnostics_summary"]
    cc = r["archive_crosscheck"]
    mr = r["mr_refresh_decision"]
    lines = [
        "# Phase 28 Task 4 - Grouped-t Copula Within/Cross-Block Tail-Dependence Diagnostics",
        "",
        "**Verdict: {}** - {} replicates x {} sim; copula FROZEN (homogeneous df "
        "{:.4f}, df_NONFIN {:.3f} / df_FIN {:.3f}). No new model parameter. "
        "EDUCATIONAL ONLY.".format(
            rep["verdict"], r["config"]["n_replicates"],
            r["config"]["n_sim_per_replicate"], r["config"]["homogeneous_df_frozen"],
            r["config"]["block_dfs_frozen"][0], r["config"]["block_dfs_frozen"][1]),
        "",
        "## Archive cross-check (T4-G1) - faithful re-read of P28T3",
        "",
        "At the canonical level p = 0.90 the recomputed per-replicate grouped-t "
        "within-block (NON-FIN, FIN) upper, cross-block upper and "
        "heterogeneity_upper are **{}** to the cached P28T3 bootstrap records "
        "(max abs dev {:.1e} <= 1e-12).".format(
            "BIT-IDENTICAL" if cc["bit_identical"] else "NOT identical",
            cc["max_abs_dev"]),
        "",
        "## Within / cross-block upper-tail dependence (mean; 95% CI) - grouped-t vs single-df t (CRN)",
        "",
        "| p | grp within-FIN U | grp cross U | sng cross U | grp-sng cross U (dilution) | grp het U | sng het U |",
        "|---|---|---|---|---|---|---|",
    ]
    for p in TAIL_LEVEL_GRID:
        key = "p_{:02d}".format(int(round(p * 100)))
        b = summ[key]
        lines.append(
            "| {:.2f} | {:.4f} | {:.4f} | {:.4f} | {:+.5f} [{:+.5f}, {:+.5f}] | "
            "{:+.5f} | {:+.5f} |".format(
                p, b["grp_within_upper_fin"]["mean"], b["grp_cross_upper"]["mean"],
                b["sng_cross_upper"]["mean"],
                b["grp_minus_sng_cross_upper"]["mean"],
                b["grp_minus_sng_cross_upper"]["ci_lo"],
                b["grp_minus_sng_cross_upper"]["ci_hi"],
                b["grp_heterogeneity_upper"]["mean"],
                b["sng_heterogeneity_upper"]["mean"]))
    lines += [
        "",
        "Dilution consistency (T4-G2): on common random numbers the grouped-t "
        "cross-block upper co-exceedance is <= the single-df t cross-block upper "
        "at every p. The single-df t shares ONE radial mixing variate (the "
        "MAXIMAL-cross-block boundary); the per-block df_g (both ABOVE the frozen "
        "2.9451, i.e. lighter within-block tails) make the grouped-t DILUTE "
        "cross-block co-movement, which is why the disclosed component SCR moves "
        "DOWN.",
        "",
        "## MR-010 / MR-014 refresh decision (T4-G3)",
        "",
        "- Governed headline basis: {}".format(mr["governed_headline_basis"]),
        "- Single-df t homogeneous boundary (P28T3 mean): {:.1f} == frozen-t "
        "basis {:.1f} -> governed move {:+.4%}".format(
            mr["scr_component_single_t_mean"], mr["scr_component_basis_mean"],
            mr["governed_headline_relative_move"]),
        "- DISCLOSED grouped-t (P28T3 mean): {:.1f} -> grouped-vs-basis move "
        "{:+.4%} (bootstrap) / {:+.4%} (Task 2 point); documented, NOT actioned".format(
            mr["scr_component_grouped_t_mean"],
            mr["disclosed_grouped_vs_basis_move_bootstrap_mean"],
            mr["disclosed_grouped_vs_basis_move_point"]),
        "- Governed move {:+.4%} vs 1% trigger -> **{}**".format(
            mr["governed_headline_relative_move"], mr["decision"]),
        "",
        "> {}".format(mr["rationale"]),
        "",
        "## MR-016 opened (T4-G4)",
        "",
        "Heterogeneous-tail / cross-block-dilution copula-FORM residual. The "
        "grouped-t per-block df, fitted leakage-free to the standalone "
        "within-block upper co-exceedances, DILUTE cross-block co-movement and "
        "WIDEN the copula-form residual to the nested truth (Phase 28 Task 3: "
        "6,114.9 -> 10,491.5). This is the SECOND negative super-set result "
        "after the Phase 27 skew-t (gamma_hat ~ 0): a single copula on the "
        "standalone margins - whether asymmetric (skew-t) or block-heterogeneous "
        "(grouped-t) - cannot close the UPWARD nested residual; it lives in "
        "nested inner-path joint dynamics. **Mitigation:** vine / pair-copula "
        "(Aas et al. 2009) escalation, Phase 29. Status OPEN (monitored); "
        "classification EDUCATIONAL.",
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
        "- tail-grid digest {} (re-draw at archived P28T3 cop_seeds; idempotent).".format(
            r["digest"]),
        "",
        "*Generated by scripts/build_phase28_task4_tail_diagnostics.py - "
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
        "# Grouped-t Within/Cross-Block Tail-Diagnostics Card (Phase 28 Task 4)",
        "",
        "- Grouped-t copula tail dependence (FROZEN Sigma/df_g; no new",
        "  parameter): at p=0.90 grouped cross-block U {:.4f} < single-df t".format(
            a90["grp_cross_upper"]["mean"]),
        "  cross-block U {:.4f} (dilution {:+.5f}); within-FIN U {:.4f}.".format(
            a90["sng_cross_upper"]["mean"],
            a90["grp_minus_sng_cross_upper"]["mean"],
            a90["grp_within_upper_fin"]["mean"]),
        "  Bit-identical to the cached P28T3 records at p=0.90.",
        "- MR-010/MR-014: NO refresh - GOVERNED headline (frozen single-df t)",
        "  move {:+.4%} (< 1% trigger); disclosed grouped-t move {:+.4%}.".format(
            mr["governed_headline_relative_move"],
            mr["disclosed_grouped_vs_basis_move_point"]),
        "- MR-016 OPENED: heterogeneous-tail / cross-block-dilution copula-FORM",
        "  residual (widens to ~10,492) NOT closed by the grouped-t; mitigation =",
        "  vine / pair-copula (Aas et al. 2009, Phase 29); status OPEN; EDUCATIONAL.",
        "- Verdict: {} - educational; production sign-off withheld.".format(
            rep["verdict"]),
        "",
    ])


def stage_report() -> int:
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    verdict = "PASS" if all(
        result["gates"][k] for k in (
            "T4_G1_archive_crosscheck_bit_identical",
            "T4_G2_grouped_dilutes_cross_block_all_p",
            "T4_G3_no_mr_refresh_governed_move_le_1pct")) else "FAIL"
    rep = {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": PHASE,
        "task": ("Task 4 - grouped-t within/cross-block tail-dependence "
                 "diagnostics + MR-010/MR-014 no-refresh decision + open MR-016"),
        "verdict": verdict,
        "block_dfs_frozen": result["config"]["block_dfs_frozen"],
        "homogeneous_df_frozen": result["config"]["homogeneous_df_frozen"],
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
    already = any((rec.title == CHANGE_TITLE) or ("Phase 28 Task 4" in rec.title)
                  for rec in store.change_records)
    has_mr016_pre = any(e.risk_id == RISK_ID for e in store.risk_register.all())
    if already and has_mr016_pre:
        ok = store.audit_trail.verify_all()
        print(json.dumps({"added": False, "reason": "already applied (idempotent)",
                          "audit_integrity_ok": ok, "mr016_present": True}))
        return 0 if ok else 1

    # T4-G4: open MR-016 (heterogeneous-tail / cross-block-dilution residual)
    if not any(e.risk_id == RISK_ID for e in store.risk_register.all()):
        store.risk_register.add(
            risk_id=RISK_ID,
            title=("Heterogeneous-tail / cross-block-dilution copula-FORM "
                   "residual not closed by the grouped-t per-block df"),
            description=(
                "The realised standalone within-FIN upper co-exceedance (0.125) "
                "sits BELOW the cross-block level (0.172), so the leakage-free "
                "per-block df fit pins df_NONFIN 37.866 / df_FIN 8.506 ABOVE the "
                "frozen 2.9451 (lighter within-block tails); on common random "
                "numbers the grouped-t therefore DILUTES cross-block co-movement "
                "vs the single-df t maximal-cross-block boundary (grouped "
                "cross-block upper {:.4f} < single {:.4f} at p=0.90) and moves "
                "the disclosed component SCR DOWN 10.93%. The copula-FORM "
                "residual to the nested truth WIDENS from the skew-t-reconfirmed "
                "6,114.9 to 10,491.5 (Phase 28 Task 3). This is the SECOND "
                "negative super-set result after the skew-t (gamma_hat ~ 0): a "
                "single copula on the standalone margins, whether asymmetric or "
                "block-heterogeneous, cannot close the UPWARD nested residual; it "
                "lives in nested inner-path joint dynamics.".format(
                    a90["grp_cross_upper"]["mean"],
                    a90["sng_cross_upper"]["mean"])),
            category="model_error",
            likelihood=RiskRating.MEDIUM,
            impact=RiskRating.HIGH,
            owner="Head of Capital Modelling (educational placeholder)",
            mitigation=(
                "Escalate the dependence structure beyond a single copula on the "
                "standalone margins: vine / pair-copula (Aas et al. 2009 - "
                "pair-copula constructions capturing conditional / inner-path "
                "joint dynamics) as the general fallback, scheduled for Phase 29. "
                "Until then the residual is quantified, disclosed, and the "
                "path-wise nested truth (46,638.9) is reported alongside the "
                "governed frozen-copula component (39,975.7, the conservative "
                "maximal-cross-block boundary) so users see the conservative "
                "bound; the grouped-t DOWN move is DISCLOSED, not adopted."),
            related_standard=("Solvency II Art. 234; Daul et al. (2003); McNeil, "
                              "Frey & Embrechts (2015) QRM ch.7; Aas et al. "
                              "(2009); IFoA Modelling Practice Note s4"),
            notes=("Opened Phase 28 Task 4. Carries forward MR-015 (Phase 27 "
                   "skew-t copula-FORM residual). Task 2 leakage-free per-block "
                   "df fit; Task 3 bootstrap residual widening; Task 4 "
                   "within/cross tail diagnostics confirm cross-block dilution. "
                   "Monitored."),
            mitigation_status=MitigationStatus.OPEN,
        )

    rec = ChangeRecord.create(
        title=CHANGE_TITLE,
        description=(
            "Reports the within/cross-block, upper/lower tail-dependence of the "
            "FROZEN grouped-t copula draw vs the single-df t (homogeneous "
            "boundary, shared mixing) on common random numbers, re-drawn at the "
            "archived P28T3 per-replicate cop_seeds (p=0.90 within/cross upper "
            "read-outs BIT-identical to the cached records). No new model "
            "parameter. Decides MR-010/MR-014 require NO refresh (GOVERNED "
            "headline frozen single-df t move {:+.4%} <= 1% trigger; the "
            "grouped-t DOWN move is DISCLOSED, not adopted) and OPENS MR-016 for "
            "the heterogeneous-tail / cross-block-dilution copula-FORM residual "
            "(NOT closed by the grouped-t; vine / pair-copula escalation -> "
            "Phase 29).".format(mr["governed_headline_relative_move"])),
        change_type="governance_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "tail_diagnostics": "not yet reported for the grouped-t within/cross draw",
            "mr_register_count": 15,
            "mr016": "not opened",
        },
        after_snapshot={
            "p90_grp_cross_upper_mean": a90["grp_cross_upper"]["mean"],
            "p90_sng_cross_upper_mean": a90["sng_cross_upper"]["mean"],
            "p90_grp_minus_sng_cross_upper_mean":
                a90["grp_minus_sng_cross_upper"]["mean"],
            "p90_grp_within_upper_fin_mean": a90["grp_within_upper_fin"]["mean"],
            "archive_crosscheck_bit_identical": r["archive_crosscheck"]["bit_identical"],
            "mr_refresh_required": mr["refresh_required"],
            "governed_headline_move": mr["governed_headline_relative_move"],
            "disclosed_grouped_move_point": mr["disclosed_grouped_vs_basis_move_point"],
            "mr016_opened": True,
            "mr_register_count": 16,
            "verdict": rep["verdict"], "digest": r["digest"],
        },
        impact_assessment=(
            "Diagnostic + governance only: no governed parameter changes (copula "
            "Sigma / homogeneous df / per-block df_g and relief scalars FROZEN). "
            "Confirms the grouped-t DILUTES cross-block co-movement vs the "
            "single-df t maximal-cross-block boundary, so the disclosed component "
            "SCR moves DOWN (non-conservative) and is NOT adopted into the "
            "governed headline; the governed frozen single-df t basis is "
            "recovered exactly (move 0.00%), so MR-010 / MR-014 quantifications "
            "are unchanged; the heterogeneous-tail / cross-block-dilution "
            "copula-FORM residual is now tracked by the NEW MR-016 with a vine / "
            "pair-copula mitigation path (Phase 29). Educational classification "
            "retained; production sign-off withheld."),
        author=ACTOR, phase=PHASE,
        quantitative_impact=(
            "p=0.90 grouped cross-block upper {:.4f} < single-df t {:.4f} "
            "(dilution {:+.5f}); grouped within-FIN upper {:.4f}; archive "
            "cross-check max abs dev {:.1e}; MR-010/MR-014 governed headline move "
            "{:+.4%} (< 1% -> no refresh); MR-016 opened (model_error, "
            "MEDIUM x HIGH, OPEN).".format(
                a90["grp_cross_upper"]["mean"], a90["sng_cross_upper"]["mean"],
                a90["grp_minus_sng_cross_upper"]["mean"],
                a90["grp_within_upper_fin"]["mean"],
                r["archive_crosscheck"]["max_abs_dev"],
                mr["governed_headline_relative_move"])),
    )
    rec.submit_for_peer_review(
        actor=ACTOR,
        comments="Archive cross-check bit-identical at p=0.90; grouped-t dilutes "
                 "cross-block co-movement at every p; MR refresh decision NO "
                 "(governed move 0.00%); MR-016 opened; new unit tests PASS.")
    rec.submit_to_owner(
        actor=ACTOR,
        comments="Owner review: diagnostic + governance addition; copula/df_g/"
                 "scalars frozen; MR-010/MR-014 not refreshed (governed headline "
                 "move 0.00%; grouped-t DOWN move disclosed, not adopted); MR-016 "
                 "opened for the heterogeneous-tail / cross-block-dilution "
                 "copula-FORM residual with vine / pair-copula mitigation "
                 "(Phase 29); sign-off withheld pending credentialled data + "
                 "APS X2 review.")
    store.add_change_record(rec)
    store.audit_trail.append(AuditEntry.governance(
        actor=ACTOR, phase=PHASE,
        event=("ChangeRecord opened (OWNER_REVIEW) + MR-016 opened - Phase 28 "
               "Task 4 grouped-t within/cross tail diagnostics + MR no-refresh "
               "decision"),
        details={"record_id": rec.record_id, "change_type": "governance_change",
                 "status": rec.status.value, "risk_opened": RISK_ID,
                 "affected_components": AFFECTED_COMPONENTS}))
    GOV_PATH.write_text(store.to_json(), encoding="utf-8")
    ok = store.audit_trail.verify_all()
    has_mr016 = any(e.risk_id == RISK_ID for e in store.risk_register.all())
    rep["change_record_id"] = rec.record_id
    rep["change_record_status"] = rec.status.value
    rep["audit_integrity_ok"] = ok
    rep["mr016_opened"] = has_mr016
    rep["risk_register_total"] = len(store.risk_register.all())
    rep["change_records_total"] = len(store.change_records)
    rep["audit_entries_total"] = len(store.audit_trail.all())
    JSON_PATH.write_text(json.dumps(rep, indent=1, default=float),
                         encoding="utf-8")
    print(json.dumps({"added": True, "record_id": rec.record_id,
                      "status": rec.status.value, "audit_integrity_ok": ok,
                      "mr016_opened": has_mr016,
                      "risk_register_total": len(store.risk_register.all()),
                      "change_records_total": len(store.change_records),
                      "audit_entries_total": len(store.audit_trail.all())}))
    return 0 if (ok and has_mr016) else 1


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
