#!/usr/bin/env python3
"""Phase 21 Task 2 build + governance -- six-driver out-of-sample proxy validation.

Runs the disjoint-seed hold-out validation of the six-driver (G2++ rate, equity,
credit, lapse, mortality, FX-translation) LSMC capital proxy against heavy nested
truth, sweeping the (degree, max_interaction_order) basis grid in BOTH fx modes
(learned hexavariate vs analytic CIP-exact offset), writes the validation report
(JSON + Markdown) and a model card, opens an OWNER_REVIEW ChangeRecord, refreshes
risks MR-011 / MR-012, and verifies audit-chain integrity.

Run (monolithic):  PYTHONPATH=. python3 scripts/build_phase21_task2_oos.py
Run (staged, for wall-clock-limited shells; bit-identical to monolithic):
  PYTHONPATH=. python3 scripts/build_phase21_task2_oos.py --stage part --part fit --i0 0 --i1 500
  PYTHONPATH=. python3 scripts/build_phase21_task2_oos.py --stage part --part val --i0 0 --i1 60
  PYTHONPATH=. python3 scripts/build_phase21_task2_oos.py --stage part --part inheavy --i0 0 --i1 60
  PYTHONPATH=. python3 scripts/build_phase21_task2_oos.py --stage part --part nested --i0 0 --i1 250
  PYTHONPATH=. python3 scripts/build_phase21_task2_oos.py --stage part --part nested --i0 250 --i1 500
  PYTHONPATH=. python3 scripts/build_phase21_task2_oos.py --stage finalise
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from par_model_v2.governance.audit_trail import (
    AuditEntry,
    ChangeRecord,
    GovernanceStore,
    MitigationStatus,
)
from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.multi_driver_proxy_validation_6d import (
    HexProxyValidationConfig,
    SixDriverFXProxyValidator,
    hex_proxy_validation_use_restrictions,
)

PHASE = "Phase 21: FX + Liquidity Drivers and Six/Seven-Driver Economic Capital"
ACTOR = "AutomatedModelDev_Phase21"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
OUT_DIR = Path("docs/validation")
JSON_PATH = OUT_DIR / "PHASE21_TASK2_OOS_VALIDATION_REPORT.json"
MD_PATH = OUT_DIR / "PHASE21_TASK2_OOS_VALIDATION_REPORT.md"
CARD_PATH = Path("docs/SIX_DRIVER_OOS_VALIDATION_CARD.md")
CHANGE_TITLE = "Phase 21 Task 2 - Six-driver out-of-sample LSMC proxy validation (FX included)"

AFFECTED_COMPONENTS = [
    "par_model_v2/projection/multi_driver_proxy_validation_6d.py",
    "tests/test_phase21_oos_validation.py",
    "scripts/build_phase21_task2_oos.py",
    "docs/SIX_DRIVER_OOS_VALIDATION_CARD.md",
    "docs/validation/PHASE21_TASK2_OOS_VALIDATION_REPORT.{json,md}",
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

STAGE_DIR = Path("/var/tmp/p21t2_stage")


def _product() -> ParEndowmentProduct:
    return ParEndowmentProduct(
        issue_age=45, gender="M", sum_assured=100000.0,
        annual_premium=5000.0, term_years=20,
    )


def _cfg() -> HexProxyValidationConfig:
    # Full educational-scale defaults (mirror Phase 19 Task 3 scale).
    return HexProxyValidationConfig()


def _validator() -> SixDriverFXProxyValidator:
    return SixDriverFXProxyValidator(_product())


# ---------------------------------------------------------------------------
# Staged execution (slice-stable CRN; bit-identical to monolithic)
# ---------------------------------------------------------------------------

_PART_SPECS = {
    # part -> (state_set, n_rows_attr, kernel)
    "fit": ("fit", "n_fit"),
    "val": ("val", "n_validation"),
    "inheavy": ("inheavy", "n_insample_heavy"),
    "nested": ("eval", "n_eval"),
}


def _part_states(v: SixDriverFXProxyValidator, cfg: HexProxyValidationConfig, part: str):
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
    cfg = _cfg()
    v = _validator()
    X = _part_states(v, cfg, part)
    if part == "fit":
        arr = v.single_path_payoffs_sliced(X, i0, i1, cfg.fit_seed)
    elif part == "val":
        arr = v.heavy_targets_sliced(X, i0, i1, cfg.n_inner_heavy, cfg.validation_seed)
    elif part == "inheavy":
        arr = v.heavy_targets_sliced(
            X, i0, i1, cfg.n_inner_heavy, cfg.insample_heavy_seed)
    elif part == "nested":
        arr = v.heavy_targets_sliced(X, i0, i1, cfg.nested_n_inner, cfg.nested_inner_seed)
    else:
        raise ValueError("unknown part: {}".format(part))
    np.savez(STAGE_DIR / "{}_{:04d}_{:04d}.npz".format(part, i0, i1), arr=arr)
    print("stage {} [{}, {}) done".format(part, i0, i1))
    return 0


def _assemble_precomputed():
    import numpy as np

    cfg = _cfg()
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
                "staged slices for part '{}' do not cover [0, {}); rerun missing slices".format(part, n))
        pre[keys[part]] = full
    return pre


# ---------------------------------------------------------------------------
# Governance
# ---------------------------------------------------------------------------

def _has_change_record(store: GovernanceStore) -> bool:
    return any(r.title == CHANGE_TITLE for r in store.change_records)


def _refresh_risks(store: GovernanceStore, rep: Dict[str, Any]) -> Dict[str, str]:
    sel = rep["selected_row"]
    cap = rep["capital_comparison"]
    out = {}
    note = (
        "Phase 21 Task 2 validated the six-driver (incl. FX) LSMC capital proxy "
        "out-of-sample: selected basis ({mode}, degree {d}, max_int {m}, {t} terms), "
        "OOS R^2 {r2:.4f}, VaR rel err {var:.2%} vs heavy nested truth "
        "(disjoint-seed hold-out, leakage-free, overfit gap {gap:.4f}); verdict {v}. "
        "FX-mode head-to-head documented: the analytic CIP-exact offset (control-"
        "variate) design was swept against a fully-learned hexavariate basis and "
        "selection was by OOS error. Liquidity driver remains open (Task 3); "
        "parameters remain educational placeholders pending credentialled calibration."
    ).format(
        mode=rep["selected_fx_mode"], d=rep["selected_degree"],
        m=rep["selected_max_interaction_order"], t=sel["n_basis_terms"],
        r2=sel["oos_r2"], var=cap["var_rel_error"], gap=sel["overfit_gap"],
        v="PASS" if rep["verdict"].startswith("PASS") else "PARTIAL",
    )
    for rid in ("MR-011", "MR-012"):
        try:
            store.risk_register.get(rid).update_mitigation(
                MitigationStatus.MITIGATED if rid == "MR-011" else MitigationStatus.IN_PROGRESS,
                notes=note,
            )
            out[rid] = "refreshed"
        except KeyError:
            out[rid] = "missing"
    return out


def _basis_rows_md(rep: Dict[str, Any]) -> str:
    rows = []
    for r in rep["basis_rows"]:
        rows.append(
            "| {} | ({}, {}) | {} | {:.4f} | {:.1f} | {:.4f} |".format(
                r["fx_mode"], r["degree"], r["max_interaction_order"],
                r["n_basis_terms"], r["oos_r2"], r["oos_rmse"], r["overfit_gap"]))
    return "\n".join(rows)


def _markdown(report: Dict[str, Any]) -> str:
    rep = report["validation"]
    sel = rep["selected_row"]
    cap = rep["capital_comparison"]
    fx = rep["fx_axis_evidence"]
    return """# Phase 21 Task 2 -- Six-Driver Out-of-Sample Proxy Validation (FX included)

Run: {ts}

## Verdict: {verdict}

Selected surface: **fx_mode={mode}, degree={d}, max_interaction_order={m}** ({t} terms),
chosen by {metric} across BOTH fx modes and the full basis grid.

| fx_mode | (deg, max_int) | terms | OOS R^2 | OOS RMSE | overfit gap |
| --- | --- | --- | --- | --- | --- |
{rows}

## Capital comparison (selected surface vs nested benchmark, same eval states)

* Proxy VaR99.5: {pvar:.1f} vs nested {nvar:.1f} (rel err {var:.2%})
* Proxy ES: {pes:.1f} vs nested {nes:.1f} (rel err {es:.2%})
* SCR rel err: {scr:.2%} (n_eval={ne}, nested_n_inner={ni})

## FX-axis recovery

* Theoretical CIP-exact slope: {ts_fx:.2f}; recovered: {rs_fx:.2f} (rel err {sre:.2%})

## Leakage / reproducibility

* Hold-out leakage-free: {lf} (0 shared states; seeds {fs} vs {vs})
* Reproducibility digest: `{digest}`

## Governance

* ChangeRecord: {rec} ({recst})
* MR-011: {mr11}; MR-012: {mr12}
* Audit integrity: {audit}

## Notes

{notes}
""".format(
        ts=report["run_timestamp"], verdict=rep["verdict"],
        mode=rep["selected_fx_mode"], d=rep["selected_degree"],
        m=rep["selected_max_interaction_order"], t=sel["n_basis_terms"],
        metric=rep["selection_metric"], rows=_basis_rows_md(rep),
        pvar=cap["proxy_capital"]["var_liability"],
        nvar=cap["nested_capital"]["var_liability"], var=cap["var_rel_error"],
        pes=cap["proxy_capital"]["es_liability"],
        nes=cap["nested_capital"]["es_liability"], es=cap["es_rel_error"],
        scr=cap["scr_rel_error"], ne=cap["nested_n_outer"], ni=cap["nested_n_inner"],
        ts_fx=fx["theoretical_fx_slope"], rs_fx=fx["recovered_fx_slope"],
        sre=fx["slope_rel_error"], lf=rep["leakage"]["leakage_free"],
        fs=rep["leakage"]["fit_seed"], vs=rep["leakage"]["validation_seed"],
        digest=rep["reproducibility_digest"],
        rec=report["change_record_id"], recst=report["change_record_status"],
        mr11=report["risk_actions"].get("MR-011"), mr12=report["risk_actions"].get("MR-012"),
        audit=report["audit_integrity_ok"],
        notes="\n".join("* " + n for n in rep["notes"]),
    )


def _write_card(report: Dict[str, Any]) -> None:
    rep = report["validation"]
    sel = rep["selected_row"]
    CARD_PATH.write_text(
        """# Six-Driver OOS Proxy-Validation Card (FX included)

**Phase:** 21 - FX + Liquidity Drivers and Six/Seven-Driver Economic Capital (Task 2)

**Status:** EDUCATIONAL. Verdict **{verdict_word}**. Production sign-off withheld pending the
liquidity driver (Task 3), re-aggregation + tail diagnostics (Task 4), UI propagation
(Task 5), credentialled calibration, and independent (APS X2) review.

## What was validated

The six-driver (G2++ rate, equity, credit spread, dynamic lapse, mortality trend,
FX translation) LSMC capital surface, out-of-sample against heavy nested truth on an
independent disjoint-seed hold-out, with basis selection by OOS error over a
(degree, max_interaction_order) grid swept in TWO fx modes:

* **analytic** -- the CIP-exact FX leg fx_l(X_H) = notional * (1 - X_H/X0) enters as a
  known offset (control variate); the polynomial spans the five stochastic-valuation
  drivers (production-sensible structure exploitation).
* **learned** -- a fully hexavariate basis must estimate the FX axis from noisy
  single-path fitting targets (standard error ~ sigma_noise / (sqrt(n_fit) * sd(X_H))).

## Selected surface

fx_mode = **{mode}**, degree {d}, max_interaction_order {m} ({t} terms);
OOS R^2 = {r2:.4f}; VaR rel err = {var:.2%}; overfit gap = {gap:.4f};
FX-axis slope recovered within {sre:.2%} of the CIP-exact theoretical slope.

## Honest findings

{notes}

## Limitations / use restrictions

{restrictions}

## Standards

{standards}
""".format(
            verdict_word="PASS" if rep["verdict"].startswith("PASS") else "PARTIAL",
            mode=rep["selected_fx_mode"], d=rep["selected_degree"],
            m=rep["selected_max_interaction_order"], t=sel["n_basis_terms"],
            r2=sel["oos_r2"], var=rep["capital_comparison"]["var_rel_error"],
            gap=sel["overfit_gap"], sre=rep["fx_axis_evidence"]["slope_rel_error"],
            notes="\n".join("* " + n for n in rep["notes"]),
            restrictions="\n".join(
                "* " + r for r in [
                    hex_proxy_validation_use_restrictions()["selection_caveat"],
                    hex_proxy_validation_use_restrictions()["residual_risk"],
                ]),
            standards="\n".join("* " + s for s in STANDARD_REFERENCES),
        ),
        encoding="utf-8",
    )


def apply_governance(store: GovernanceStore, rep: Dict[str, Any]) -> Dict[str, Any]:
    risk_actions = _refresh_risks(store, rep)
    added = False
    record_id = None
    record_status = None
    sel = rep["selected_row"]
    cap = rep["capital_comparison"]

    if not _has_change_record(store):
        rec = ChangeRecord.create(
            title=CHANGE_TITLE,
            description=(
                "Phase 21 Task 2 validated the six-driver (G2++ rate, equity, credit, "
                "lapse, mortality, FX-translation) LSMC economic-capital proxy out-of-"
                "sample: noisy single-inner-path fitting targets at six-driver outer "
                "states; an independent disjoint-seed hold-out scored against heavy "
                "nested truth; basis selection by OOS error over a (degree, "
                "max_interaction_order) grid swept in BOTH fx modes (fully-learned "
                "hexavariate basis vs the analytic CIP-exact FX offset / control-"
                "variate design); leakage, overfit and FX-axis-recovery diagnostics; "
                "and a same-states proxy-vs-nested capital comparison. This closes the "
                "Task 1 deferral ('the nested benchmark is the only validated 6D "
                "ground truth until Task 2 reports')."
            ),
            change_type="methodology_change",
            affected_components=AFFECTED_COMPONENTS,
            standard_references=STANDARD_REFERENCES,
            before_snapshot={
                "six_driver_proxy": "UNVALIDATED (Task 1 deferral)",
                "fx_axis": "nested benchmark only",
            },
            after_snapshot={
                "six_driver_proxy": "OOS-validated ({})".format(
                    "PASS" if rep["verdict"].startswith("PASS") else "PARTIAL"),
                "selected_fx_mode": rep["selected_fx_mode"],
                "selected_basis": "(deg {}, max_int {}, {} terms)".format(
                    rep["selected_degree"], rep["selected_max_interaction_order"],
                    sel["n_basis_terms"]),
                "oos_r2": sel["oos_r2"],
                "var_rel_error": cap["var_rel_error"],
                "fx_slope_rel_error": rep["fx_axis_evidence"]["slope_rel_error"],
            },
            impact_assessment=(
                "Provides the OOS validation evidence for the six-driver proxy surface "
                "without changing any engine output (additive validator module). The "
                "FX-mode head-to-head documents when learning a known-analytic axis "
                "from noisy LSMC targets is statistically unjustified."
            ),
            quantitative_impact=(
                "Selected ({mode}, deg {d}, max_int {m}): OOS R^2 {r2:.4f}, OOS RMSE "
                "{rmse:.1f}, VaR rel err {var:.2%}, ES rel err {es:.2%}, overfit gap "
                "{gap:.4f}, FX slope rel err {sre:.2%}; n_fit={nf}, n_val={nv}, "
                "n_inner_heavy={nih}, n_eval={ne}, nested_n_inner={ni}."
            ).format(
                mode=rep["selected_fx_mode"], d=rep["selected_degree"],
                m=rep["selected_max_interaction_order"], r2=sel["oos_r2"],
                rmse=sel["oos_rmse"], var=cap["var_rel_error"],
                es=cap["es_rel_error"], gap=sel["overfit_gap"],
                sre=rep["fx_axis_evidence"]["slope_rel_error"],
                nf=rep["config"]["n_fit"], nv=rep["config"]["n_validation"],
                nih=rep["config"]["n_inner_heavy"], ne=rep["config"]["n_eval"],
                ni=rep["config"]["nested_n_inner"],
            ),
            author=ACTOR,
            phase=PHASE,
            peer_reviewer="APS_X2_Independent_Reviewer",
            assumption_owner="ChiefActuary",
        )
        rec.submit_for_peer_review(
            ACTOR,
            "Six-driver OOS proxy validation staged with dual fx-mode basis sweep; "
            "credentialled calibration and independent review required before approval.",
        )
        rec.submit_to_owner(
            ACTOR,
            "Owner review requested. Production sign-off withheld pending Phase 21 "
            "Tasks 3-5 and credentialled calibration.",
        )
        store.add_change_record(rec)
        added = True
        record_id = rec.record_id
        record_status = rec.status.value
        store.audit_trail.append(
            AuditEntry.governance(
                actor=ACTOR,
                phase=PHASE,
                event="ChangeRecord opened (OWNER_REVIEW) - six-driver OOS proxy validation",
                details={
                    "record_id": rec.record_id,
                    "verdict": rep["verdict"][:120],
                    "selected_fx_mode": rep["selected_fx_mode"],
                    "oos_r2": sel["oos_r2"],
                    "var_rel_error": cap["var_rel_error"],
                    "affected_components": AFFECTED_COMPONENTS,
                    "risk_actions": risk_actions,
                },
            )
        )
    else:
        for rec in store.change_records:
            if rec.title == CHANGE_TITLE:
                record_id = rec.record_id
                record_status = rec.status.value
                break

    return {
        "risk_actions": risk_actions,
        "added_change_record": added,
        "change_record_id": record_id,
        "change_record_status": record_status,
    }


def main(precomputed=None) -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    cfg = _cfg()
    store = (
        GovernanceStore.from_json(GOV_PATH.read_text(encoding="utf-8"))
        if GOV_PATH.exists() else GovernanceStore()
    )
    validation = _validator().validate(
        config=cfg, precomputed=precomputed,
        governance_store=store, actor=ACTOR, phase=PHASE,
    )
    rep = validation.to_dict()

    gov = apply_governance(store, rep)
    rep_for_report = {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": PHASE,
        "task": CHANGE_TITLE,
        "validation": rep,
        "affected_components": AFFECTED_COMPONENTS,
        "standard_references": STANDARD_REFERENCES,
        "change_record_id": gov["change_record_id"],
        "change_record_status": gov["change_record_status"],
        "risk_actions": gov["risk_actions"],
        "audit_integrity_ok": store.audit_trail.verify_all(),
        "change_records_total": len(store.change_records),
        "use_restrictions": hex_proxy_validation_use_restrictions(),
    }
    _write_card(rep_for_report)
    rep_for_report["markdown"] = _markdown(rep_for_report)

    if GOV_PATH.exists():
        GOV_PATH.write_text(store.to_json() + "\n", encoding="utf-8")

    JSON_PATH.write_text(json.dumps(rep_for_report, indent=2) + "\n", encoding="utf-8")
    MD_PATH.write_text(rep_for_report["markdown"], encoding="utf-8")

    sel = rep["selected_row"]
    print("=== Phase 21 Task 2 - Six-Driver OOS Proxy Validation ===")
    print("Verdict          : {}".format(rep["verdict"][:140]))
    print("Selected surface : fx_mode={}, deg={}, max_int={} ({} terms)".format(
        rep["selected_fx_mode"], rep["selected_degree"],
        rep["selected_max_interaction_order"], sel["n_basis_terms"]))
    print("OOS R^2 / RMSE   : {:.4f} / {:.1f}".format(sel["oos_r2"], sel["oos_rmse"]))
    print("VaR rel err      : {:.2%}".format(rep["capital_comparison"]["var_rel_error"]))
    print("FX slope rel err : {:.2%}".format(rep["fx_axis_evidence"]["slope_rel_error"]))
    print("Leakage-free     : {}".format(rep["leakage"]["leakage_free"]))
    print("ChangeRecord     : {} ({})".format(gov["change_record_id"], gov["change_record_status"]))
    print("Risk refresh     : {}".format(gov["risk_actions"]))
    print("Audit integrity  : {}".format(store.audit_trail.verify_all()))
    print("Report           : {}".format(JSON_PATH))
    ok = rep["verdict"].startswith("PASS") and store.audit_trail.verify_all()
    return 0 if ok else 1


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["part", "finalise"], default=None)
    ap.add_argument("--part", choices=["fit", "val", "inheavy", "nested"], default=None)
    ap.add_argument("--i0", type=int, default=0)
    ap.add_argument("--i1", type=int, default=0)
    args = ap.parse_args()
    if args.stage == "part":
        sys.exit(stage_part(args.part, args.i0, args.i1))
    elif args.stage == "finalise":
        sys.exit(main(precomputed=_assemble_precomputed()))
    sys.exit(main())
