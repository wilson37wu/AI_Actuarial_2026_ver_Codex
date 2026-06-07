#!/usr/bin/env python3
"""Phase 22 Task 1 build + governance — six-driver OOS proxy-validation REMEDIATION.

Re-runs the six-driver out-of-sample LSMC proxy validation applying the three
remediation options recorded after the Phase 21 Task 2 honest PARTIAL
(OOS R² 0.9498 vs 0.95): de-noised fitting targets (8 inner Q-paths/state),
4× training states (2,000), de-noised eval nested benchmark (256 inner), and a
targeted rate/equity-curvature candidate basis competing in the same OOS
selection.  Applies the stricter Phase 22 gate (OOS R² ≥ 0.95; VaR, ES AND SCR
rel err ≤ 10%), writes the validation report (JSON + Markdown), updates the
six-driver OOS model card, opens an OWNER_REVIEW ChangeRecord, refreshes
MR-011 / MR-012, and verifies audit-chain integrity.

Run (staged; bit-identical to monolithic):
  PYTHONPATH=. python3 scripts/build_phase22_task1_oos_remediation.py --stage part --part fit    --i0 0   --i1 2000
  PYTHONPATH=. python3 scripts/build_phase22_task1_oos_remediation.py --stage part --part val    --i0 0   --i1 60
  PYTHONPATH=. python3 scripts/build_phase22_task1_oos_remediation.py --stage part --part inheavy --i0 0  --i1 60
  PYTHONPATH=. python3 scripts/build_phase22_task1_oos_remediation.py --stage part --part nested --i0 0   --i1 250
  PYTHONPATH=. python3 scripts/build_phase22_task1_oos_remediation.py --stage part --part nested --i0 250 --i1 500
  PYTHONPATH=. python3 scripts/build_phase22_task1_oos_remediation.py --stage finalise
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.multi_driver_proxy_validation_6d_remediation import (
    REMEDIATED_FIT_N_INNER,
    RemediatedHexProxyValidator,
    remediated_config,
    remediation_use_restrictions,
    run_remediated_validation,
)

PHASE = "Phase 22: Proxy Hardening + Seven-Driver OOS Validation"
ACTOR = "AutomatedModelDev_Phase22"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
OUT_DIR = Path("docs/validation")
JSON_PATH = OUT_DIR / "PHASE22_TASK1_OOS_REMEDIATION_REPORT.json"
MD_PATH = OUT_DIR / "PHASE22_TASK1_OOS_REMEDIATION_REPORT.md"
CARD_PATH = Path("docs/SIX_DRIVER_OOS_VALIDATION_CARD.md")
CHANGE_TITLE = "Phase 22 Task 1 - Six-driver OOS proxy-validation remediation (hardened)"

AFFECTED_COMPONENTS = [
    "par_model_v2/projection/multi_driver_proxy_validation_6d_remediation.py",
    "tests/test_phase22_task1_oos_remediation.py",
    "scripts/build_phase22_task1_oos_remediation.py",
    "docs/SIX_DRIVER_OOS_VALIDATION_CARD.md",
    "docs/validation/PHASE22_TASK1_OOS_REMEDIATION_REPORT.{json,md}",
]

STANDARD_REFERENCES = [
    "SOA ASOP 7 section 3.3",
    "SOA ASOP 25 section 3.3",
    "SOA ASOP 56 section 3.1.3/3.5",
    "IA TAS M section 3.2/3.6",
    "IFoA proxy-modelling working party",
    "Longstaff & Schwartz (2001)",
    "Solvency II Delegated Regulation Article 188/234",
]

STAGE_DIR = Path("/var/tmp/p22t1_stage")


def _product() -> ParEndowmentProduct:
    return ParEndowmentProduct(
        issue_age=45, gender="M", sum_assured=100000.0,
        annual_premium=5000.0, term_years=20,
    )


def _validator() -> RemediatedHexProxyValidator:
    return RemediatedHexProxyValidator(_product())


# ---------------------------------------------------------------------------
# Staged execution (slice-stable CRN; bit-identical to monolithic)
# ---------------------------------------------------------------------------

def _part_states(v, cfg, part):
    if part == "fit":
        return v.states(cfg.n_fit, cfg.fit_seed)
    if part == "val":
        return v.states(cfg.n_validation, cfg.validation_seed)
    if part == "inheavy":
        return v.states(cfg.n_fit, cfg.fit_seed)[: cfg.n_insample_heavy]
    if part == "nested":
        return v.states(cfg.n_eval, cfg.eval_seed)
    raise ValueError("unknown part: {}".format(part))


def stage_part(part: str, i0: int, i1: int) -> int:
    import numpy as np

    STAGE_DIR.mkdir(parents=True, exist_ok=True)
    cfg = remediated_config()
    v = _validator()
    X = _part_states(v, cfg, part)
    if part == "fit":
        arr = v.denoised_fit_payoffs_sliced(
            X, i0, i1, cfg.fit_seed, n_inner=REMEDIATED_FIT_N_INNER)
    elif part == "val":
        arr = v.heavy_targets_sliced(X, i0, i1, cfg.n_inner_heavy, cfg.validation_seed)
    elif part == "inheavy":
        arr = v.heavy_targets_sliced(
            X, i0, i1, cfg.n_inner_heavy, cfg.insample_heavy_seed)
    elif part == "nested":
        arr = v.heavy_targets_sliced(X, i0, i1, cfg.nested_n_inner, cfg.nested_inner_seed)
    else:
        raise ValueError("unknown part: {}".format(part))
    np.savez(STAGE_DIR / "{}_{:05d}_{:05d}.npz".format(part, i0, i1), arr=arr)
    print("stage {} [{}, {}) done".format(part, i0, i1))
    return 0


def _assemble_precomputed():
    import numpy as np

    cfg = remediated_config()
    sizes = {
        "fit": cfg.n_fit, "val": cfg.n_validation,
        "inheavy": cfg.n_insample_heavy, "nested": cfg.n_eval,
    }
    keys = {"fit": "fit_y5", "val": "val_truth5",
            "inheavy": "insample_truth5", "nested": "nested_l5"}
    pre = {}
    for part, n in sizes.items():
        full = np.full(n, np.nan)
        for f in sorted(STAGE_DIR.glob(part + "_*.npz")):
            i0, i1 = (int(x) for x in f.stem.split("_")[-2:])
            full[i0:i1] = np.load(f)["arr"]
        if np.isnan(full).any():
            raise RuntimeError(
                "staged slices for part '{}' do not cover [0, {}); "
                "rerun missing slices".format(part, n))
        pre[keys[part]] = full
    return pre


# ---------------------------------------------------------------------------
# Governance + reporting
# ---------------------------------------------------------------------------

def _markdown(report: Dict[str, Any]) -> str:
    rep = report["validation"]
    fin = rep["final_selected"]
    cap = rep["capital_comparison"]
    fx = rep["fx_axis_evidence"]
    rem = rep["remediation_applied"]
    base = rem["baseline_phase21"]
    rows = []
    for r in rep["governed_engine_report"]["basis_rows"] + [rep["targeted_candidate"]]:
        rows.append("| {} | ({}, {}) | {} | {:.4f} | {:.1f} | {:.4f} |".format(
            r["fx_mode"], r["degree"], r["max_interaction_order"],
            r["n_basis_terms"], r["oos_r2"], r["oos_rmse"], r["overfit_gap"]))
    return """# Phase 22 Task 1 — Six-Driver OOS Proxy-Validation Remediation

Run: {ts}

## Verdict: {verdict}

Remediation applied vs the Phase 21 Task 2 PARTIAL (OOS R² {b_r2:.6f}):
fit targets de-noised 1 → {fni} inner Q-paths/state; training states
{b_nfit} → {nfit}; eval nested benchmark {b_ni} → {ni} inner; targeted
rate/equity-curvature candidate ({tgt}).

Final selected surface: **{mode}** ({terms} terms) — targeted_wins={tw};
selection by OOS RMSE across the FULL governed sweep + the targeted candidate.

| fx_mode | (deg, max_int) | terms | OOS R^2 | OOS RMSE | overfit gap |
| --- | --- | --- | --- | --- | --- |
{rows}

## Capital comparison (final surface vs de-noised nested benchmark, same eval states)

* Proxy VaR99.5: {pvar:.1f} vs nested {nvar:.1f} (rel err {var:.2%})
* Proxy ES: {pes:.1f} vs nested {nes:.1f} (rel err {es:.2%})
* SCR rel err: {scr:.2%} (n_eval={ne}, nested_n_inner={nni})
* Phase 22 gate: OOS R² ≥ 0.95 AND VaR, ES AND SCR rel err ≤ 10% (stricter than Phase 21).

## FX-axis recovery

* Theoretical CIP-exact slope: {tfx:.2f}; recovered: {rfx:.2f} (rel err {sre:.2%})

## Leakage / reproducibility

* Hold-out leakage-free: {lf} (disjoint seeds; same protocol as Phase 21 Task 2)
* Reproducibility digest: `{digest}`

## Governance

* ChangeRecord: {rec} ({recst})
* MR-011: {mr11}; MR-012: {mr12}
* Audit integrity: {audit}

## Notes

{notes}
""".format(
        ts=report["run_timestamp"], verdict=rep["verdict"],
        b_r2=base["oos_r2"], fni=rem["fit_n_inner"], b_nfit=base["n_fit"],
        nfit=rem["n_fit"], b_ni=base["nested_n_inner"], ni=rem["nested_n_inner"],
        tgt=rem["targeted_basis"], mode=fin["fx_mode"], terms=fin["n_basis_terms"],
        tw=rep["targeted_wins"], rows="\n".join(rows),
        pvar=cap["proxy_capital"]["var_liability"],
        nvar=cap["nested_capital"]["var_liability"], var=cap["var_rel_error"],
        pes=cap["proxy_capital"]["es_liability"],
        nes=cap["nested_capital"]["es_liability"], es=cap["es_rel_error"],
        scr=cap["scr_rel_error"], ne=cap["nested_n_outer"], nni=cap["nested_n_inner"],
        tfx=fx["theoretical_fx_slope"], rfx=fx["recovered_fx_slope"],
        sre=fx["slope_rel_error"],
        lf=rep["governed_engine_report"]["leakage"]["leakage_free"],
        digest=rep["reproducibility_digest"],
        rec=report["change_record_id"], recst=report["change_record_status"],
        mr11=report["risk_actions"].get("MR-011", "n/a"),
        mr12=report["risk_actions"].get("MR-012", "n/a"),
        audit=report["audit_integrity_ok"],
        notes="\n".join("* " + n for n in rep["governed_engine_report"]["notes"]),
    )


def finalise() -> int:
    from par_model_v2.governance.audit_trail import (
        AuditEntry, ChangeRecord, GovernanceStore, MitigationStatus,
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cfg = remediated_config()
    v = _validator()
    pre = _assemble_precomputed()

    store = (
        GovernanceStore.from_json(GOV_PATH.read_text(encoding="utf-8"))
        if GOV_PATH.exists() else GovernanceStore()
    )
    rep = run_remediated_validation(
        v, config=cfg, precomputed=pre,
        fit_n_inner=REMEDIATED_FIT_N_INNER,
        governance_store=store, actor=ACTOR, phase=PHASE,
    )

    fin = rep["final_selected"]
    cap = rep["capital_comparison"]
    passed = rep["verdict"].startswith("PASS")

    # --- MR refresh ---------------------------------------------------------
    note = (
        "Phase 22 Task 1 remediated the six-driver OOS PARTIAL: final surface {} "
        "({} terms) OOS R^2 {:.4f} (gate 0.95), VaR/ES/SCR rel err {:.2%}/{:.2%}/{:.2%} "
        "(gate 10% each), leakage-free, overfit gap {:.4f}; verdict {}. De-noised "
        "fit targets ({} inner Q-paths/state) + training states 500->2000 + de-noised "
        "nested benchmark (256 inner) + targeted rate/equity-curvature candidate in the "
        "same OOS selection. Parameters remain educational placeholders pending "
        "credentialled calibration."
    ).format(
        fin["fx_mode"], fin["n_basis_terms"], fin["oos_r2"],
        cap["var_rel_error"], cap["es_rel_error"], cap["scr_rel_error"],
        fin["overfit_gap"], "PASS" if passed else "PARTIAL",
        REMEDIATED_FIT_N_INNER,
    )
    risk_actions = {}
    for rid in ("MR-011", "MR-012"):
        try:
            store.risk_register.get(rid).update_mitigation(
                MitigationStatus.MITIGATED if passed else MitigationStatus.IN_PROGRESS,
                notes=note,
            )
            risk_actions[rid] = "refreshed"
        except KeyError:
            risk_actions[rid] = "missing"

    # --- ChangeRecord (idempotent) ----------------------------------------
    record_id = None
    record_status = None
    existing = [r for r in store.change_records if r.title == CHANGE_TITLE]
    if existing:
        record_id = existing[0].record_id
        record_status = existing[0].status.value
    else:
        rec = ChangeRecord.create(
            title=CHANGE_TITLE,
            description=(
                "Remediated re-run of the six-driver (G2++ rate, equity, credit, lapse, "
                "mortality, FX-translation) OOS LSMC proxy validation per the remediation "
                "options recorded after the Phase 21 Task 2 honest PARTIAL (OOS R^2 "
                "0.9498 vs 0.95): (1) de-noised regression targets - each fit state's "
                "target is the mean of {} inner Q-paths (was 1), same SeedSequence "
                "protocol so n_inner=1 is bit-identical to Phase 21 (regression-tested); "
                "(2) training states 500 -> 2,000 via the staged slice-stable CRN "
                "protocol; (3) eval nested benchmark de-noised 96 -> 256 inner; plus a "
                "targeted rate/equity-curvature 9-term candidate basis (deg-1 all "
                "drivers + r^2, S^2, r*S; analytic CIP-exact FX offset) competing "
                "against the FULL governed sweep on the same fitting data and the same "
                "disjoint-seed hold-out. Selection stays by OOS RMSE - no gate-shopping. "
                "Stricter Phase 22 gate: OOS R^2 >= 0.95 AND VaR, ES AND SCR rel err "
                "<= 10%."
            ).format(REMEDIATED_FIT_N_INNER),
            change_type="methodology_change",
            affected_components=AFFECTED_COMPONENTS,
            standard_references=STANDARD_REFERENCES,
            before_snapshot={
                "six_driver_oos": "PARTIAL - OOS R^2 0.949837 < 0.95 "
                                  "(Phase 21 Task 2, c2f29042b5f44dd7b3670d7de87e09a2)",
                "fit_targets": "single inner Q-path (noisy)",
                "n_fit": 500, "nested_n_inner": 96,
            },
            after_snapshot={
                "six_driver_oos": "remediated ({})".format("PASS" if passed else "PARTIAL"),
                "final_surface": "{} ({} terms)".format(fin["fx_mode"], fin["n_basis_terms"]),
                "targeted_wins": rep["targeted_wins"],
                "oos_r2": fin["oos_r2"],
                "var_rel_error": cap["var_rel_error"],
                "es_rel_error": cap["es_rel_error"],
                "scr_rel_error": cap["scr_rel_error"],
                "fit_n_inner": REMEDIATED_FIT_N_INNER,
                "n_fit": cfg.n_fit, "nested_n_inner": cfg.nested_n_inner,
            },
            impact_assessment=(
                "Validation-evidence change only: hardens the six-driver proxy OOS "
                "evidence without altering any production engine output (additive "
                "remediation module). Clears (or honestly re-documents) the recorded "
                "Phase 21 PARTIAL with a stricter capital-error gate."
            ),
            quantitative_impact=(
                "Final ({mode}, {t} terms): OOS R^2 {r2:.4f} (was 0.9498), OOS RMSE "
                "{rmse:.1f} (was 4686.0), VaR rel err {var:.2%} (was 5.99%), ES rel err "
                "{es:.2%} (was 4.63%), SCR rel err {scr:.2%} (was 15.97%), overfit gap "
                "{gap:.4f}; n_fit={nf}, fit_n_inner={fni}, n_eval={ne}, "
                "nested_n_inner={ni}."
            ).format(
                mode=fin["fx_mode"], t=fin["n_basis_terms"], r2=fin["oos_r2"],
                rmse=fin["oos_rmse"], var=cap["var_rel_error"], es=cap["es_rel_error"],
                scr=cap["scr_rel_error"], gap=fin["overfit_gap"], nf=cfg.n_fit,
                fni=REMEDIATED_FIT_N_INNER, ne=cfg.n_eval, ni=cfg.nested_n_inner,
            ),
            author=ACTOR,
            phase=PHASE,
            peer_reviewer="APS_X2_Independent_Reviewer",
            assumption_owner="ChiefActuary",
        )
        rec.submit_for_peer_review(
            ACTOR,
            "Remediated six-driver OOS validation staged with slice-stable CRN; "
            "n_inner=1 bit-identity to the governed Phase 21 kernel regression-tested; "
            "credentialled calibration and independent review required before approval.",
        )
        rec.submit_to_owner(
            ACTOR,
            "Owner review requested. Production sign-off withheld pending Phase 22 "
            "Tasks 2-5 and credentialled calibration.",
        )
        store.add_change_record(rec)
        record_id = rec.record_id
        record_status = rec.status.value
        store.audit_trail.append(
            AuditEntry.governance(
                actor=ACTOR,
                phase=PHASE,
                event="ChangeRecord opened (OWNER_REVIEW) - six-driver OOS remediation",
                details={
                    "record_id": rec.record_id,
                    "verdict": rep["verdict"][:140],
                    "final_surface": fin["fx_mode"],
                    "targeted_wins": rep["targeted_wins"],
                    "oos_r2": fin["oos_r2"],
                    "var_rel_error": cap["var_rel_error"],
                    "scr_rel_error": cap["scr_rel_error"],
                    "affected_components": AFFECTED_COMPONENTS,
                    "risk_actions": risk_actions,
                },
            )
        )

    audit_ok = store.audit_trail.verify_all()
    if GOV_PATH.exists():
        GOV_PATH.write_text(store.to_json() + "\n", encoding="utf-8")

    report = {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": PHASE,
        "task": "Task 1 - Six-driver OOS proxy-validation remediation",
        "validation": rep,
        "affected_components": AFFECTED_COMPONENTS,
        "standard_references": STANDARD_REFERENCES,
        "change_record_id": record_id,
        "change_record_status": record_status,
        "risk_actions": risk_actions,
        "audit_integrity_ok": bool(audit_ok),
        "change_records_total": len(store.change_records),
        "use_restrictions": remediation_use_restrictions(),
    }
    report["markdown"] = _markdown(report)

    JSON_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    MD_PATH.write_text(report["markdown"], encoding="utf-8")
    print("verdict:", rep["verdict"][:160])
    print("final:", fin["fx_mode"], fin["n_basis_terms"], "terms, OOS R2",
          fin["oos_r2"], "RMSE", fin["oos_rmse"], "| targeted_wins:", rep["targeted_wins"])
    print("capital rel err VaR/ES/SCR: {:.4f}/{:.4f}/{:.4f}".format(
        cap["var_rel_error"], cap["es_rel_error"], cap["scr_rel_error"]))
    print("change record:", record_id, record_status)
    print("audit integrity:", audit_ok, "| change records:", len(store.change_records))
    print("wrote", JSON_PATH, "and", MD_PATH)
    return 0 if (passed and audit_ok) else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["part", "finalise"], required=True)
    ap.add_argument("--part", choices=["fit", "val", "inheavy", "nested"])
    ap.add_argument("--i0", type=int, default=0)
    ap.add_argument("--i1", type=int, default=0)
    args = ap.parse_args()
    if args.stage == "part":
        if not args.part:
            ap.error("--part required with --stage part")
        return stage_part(args.part, args.i0, args.i1)
    return finalise()


if __name__ == "__main__":
    sys.exit(main())
