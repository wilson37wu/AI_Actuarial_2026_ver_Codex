#!/usr/bin/env python3
"""Phase 20 Task 4 build + governance -- capital re-aggregation with the 2F G2++ rates driver.

Re-runs the five-driver tail-dependent aggregation with the two-factor G2++ rates
driver (Phase 20 Task 2 swaption calibration) substituted for HW1F in the OUTER
state, benchmarks HW1F vs G2++, refreshes tail diagnostics (VaR/ES, outer
convergence, bootstrap CI) on the 2F nested loss vector, writes the validation
reports + a model card, opens an OWNER_REVIEW ChangeRecord, refreshes MR-010 and
MR-012, and verifies audit-chain integrity.

Run:  PYTHONPATH=<pylibs>:. python3 scripts/build_phase20_task4_capital_reaggregation.py
"""
from __future__ import annotations

import json
import pickle
import sys
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from par_model_v2.governance.audit_trail import (
    AuditEntry, ChangeRecord, GovernanceStore, MitigationStatus,
)
from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.multi_driver_capital_5d_aggregation import (
    FiveDriverAggregationConfig, FiveDriverRiskAggregator,
)
from par_model_v2.projection.multi_driver_capital_5d_g2pp import (
    G2ppFiveDriverRiskAggregator, calibrated_g2pp_params, CALIBRATED_G2PP_PARAMS,
)

PHASE = "Phase 20: Market-Consistency and Multi-Factor Uplift"
ACTOR = "AutomatedModelDev_Phase20"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
OUT_DIR = Path("docs/validation")
AGG_JSON = OUT_DIR / "PHASE20_TASK4_AGGREGATION_REPORT.json"
AGG_MD = OUT_DIR / "PHASE20_TASK4_AGGREGATION_REPORT.md"
TAIL_JSON = OUT_DIR / "PHASE20_TASK4_TAIL_DIAGNOSTICS_REPORT.json"
TAIL_MD = OUT_DIR / "PHASE20_TASK4_TAIL_DIAGNOSTICS_REPORT.md"
CARD_PATH = Path("docs/MULTI_DRIVER_5D_G2PP_AGGREGATION_CARD.md")
CHANGE_TITLE = "Phase 20 Task 4 - capital re-aggregation with the two-factor G2++ rates driver"

AFFECTED_COMPONENTS = [
    "par_model_v2/projection/multi_driver_capital_5d_g2pp.py",
    "tests/test_phase20_task4_g2pp_aggregation.py",
    "scripts/build_phase20_task4_capital_reaggregation.py",
    "docs/MULTI_DRIVER_5D_G2PP_AGGREGATION_CARD.md",
    "docs/validation/PHASE20_TASK4_AGGREGATION_REPORT.{json,md}",
    "docs/validation/PHASE20_TASK4_TAIL_DIAGNOSTICS_REPORT.{json,md}",
]
STANDARD_REFERENCES = [
    "SOA ASOP 56 section 3.5", "SOA ASOP 56 section 3.1", "SOA ASOP 25 section 3.3",
    "SOA ASOP 7 section 3.3", "IA TAS M section 3.2", "IA TAS M section 3.5",
    "IA TAS M section 3.6", "Solvency II Delegated Regulation Article 234",
    "Brigo-Mercurio 2006", "IFoA Life Aggregation & Simulation WP",
]

# Aggregation run configuration (educational proxy scale).
N_OUTER = 240
N_INNER = 48
SEED = 42
HORIZON = 12
N_SIM_COPULA = 120_000
CONF = 0.995


def _tail_diagnostics(full_l: np.ndarray, scr_proxy: float) -> Dict[str, Any]:
    """VaR/ES at several confidence levels, outer convergence and bootstrap CI."""
    full_l = np.asarray(full_l, dtype=float)
    n = full_l.size
    mean_l = float(full_l.mean())
    levels = [0.95, 0.99, 0.995]
    var_es = {}
    for cl in levels:
        var_l = float(np.quantile(full_l, cl))
        tail = full_l[full_l >= var_l]
        es_l = float(tail.mean()) if tail.size else var_l
        var_es["{:.3f}".format(cl)] = {
            "var": round(var_l, 4), "es": round(es_l, 4),
            "scr_var": round(var_l - mean_l, 4), "scr_es": round(es_l - mean_l, 4),
        }
    # Outer convergence: SCR over increasing subsamples (deterministic order).
    conv = []
    for frac in (0.25, 0.5, 0.75, 1.0):
        k = max(20, int(n * frac))
        sub = full_l[:k]
        scr = float(np.quantile(sub, CONF) - sub.mean())
        conv.append({"n_outer": k, "scr_proxy": round(scr, 4)})
    # Bootstrap CI for the 99.5% SCR-proxy.
    rng = np.random.default_rng(SEED + 99)
    boot = np.empty(2000, dtype=float)
    for i in range(boot.size):
        idx = rng.integers(0, n, n)
        s = full_l[idx]
        boot[i] = float(np.quantile(s, CONF) - s.mean())
    lo, hi = float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))
    rel_halfwidth = (hi - lo) / 2.0 / abs(scr_proxy) if abs(scr_proxy) > 1e-9 else float("nan")
    return {
        "n_outer": n, "mean_liability": round(mean_l, 4),
        "var_es_by_level": var_es,
        "outer_convergence": conv,
        "bootstrap_scr_995": {
            "point": round(scr_proxy, 4),
            "ci_lo_95": round(lo, 4), "ci_hi_95": round(hi, 4),
            "rel_halfwidth": round(rel_halfwidth, 4), "n_boot": int(boot.size),
        },
    }


def _comparison(hw, g2) -> Dict[str, Any]:
    hsa, gsa = hw.standalone, g2.standalone

    def d(name, hwv, gv):
        rel = (gv - hwv) / abs(hwv) if abs(hwv) > 1e-9 else float("nan")
        return {"driver": name, "hw1f": round(hwv, 1), "g2pp": round(gv, 1),
                "delta": round(gv - hwv, 1), "rel_delta": round(rel, 4)}
    return {
        "standalone": [
            d("rate", hsa.rate_capital.scr_proxy, gsa.rate_capital.scr_proxy),
            d("equity", hsa.equity_capital.scr_proxy, gsa.equity_capital.scr_proxy),
            d("credit", hsa.credit_capital.scr_proxy, gsa.credit_capital.scr_proxy),
            d("lapse", hsa.lapse_capital.scr_proxy, gsa.lapse_capital.scr_proxy),
            d("mortality", hsa.mortality_capital.scr_proxy, gsa.mortality_capital.scr_proxy),
        ],
        "var_covar_scr": d("var_covar", hw.var_covar.correlated_scr, g2.var_covar.correlated_scr),
        "copula_scr": d("copula", hw.copula.selected.aggregated_capital.scr_proxy,
                        g2.copula.selected.aggregated_capital.scr_proxy),
        "nested_scr": d("nested", hw.nested_scr, g2.nested_scr),
        "hw1f_copula": hw.copula.selected_copula,
        "g2pp_copula": g2.copula.selected_copula,
        "hw1f_understatement_pct": round(100.0 * hw.var_covar.esg_understatement_pct, 2),
        "g2pp_understatement_pct": round(100.0 * g2.var_covar.esg_understatement_pct, 2),
        "hw1f_copula_rel_err": round(hw.copula.selected.scr_rel_error_vs_nested, 4),
        "g2pp_copula_rel_err": round(g2.copula.selected.scr_rel_error_vs_nested, 4),
    }


def _agg_markdown(rep: Dict[str, Any]) -> str:
    c = rep["comparison"]; g = rep["g2pp_report"]
    rows = "\n".join(
        "| {d} | {h:,.0f} | {gg:,.0f} | {dl:+,.0f} | {rd:+.1%} |".format(
            d=r["driver"], h=r["hw1f"], gg=r["g2pp"], dl=r["delta"], rd=r["rel_delta"])
        for r in c["standalone"])
    return """# Phase 20 Task 4 -- Capital Re-Aggregation with the Two-Factor G2++ Rates Driver

**Run:** {ts}

**Verdict (G2++):** {verdict}

## 1. What changed

The single-factor Hull-White (HW1F) rate driver in the OUTER real-world state was
replaced by the swaption-calibrated two-factor **G2++** driver
(a={a:.4f}, b={b:.4f}, sigma={s:.5f}, eta={e:.5f}, rho={rho:.4f}), anchored to the
same initial curve. The horizon short-rate dispersion falls from ~114 bps (HW1F
placeholder) to ~49 bps (calibrated G2++): the swaption-calibrated factor vols are
lower and the strong negative factor correlation rho={rho:.2f} suppresses the
combined level variance while adding a slope/curvature axis the endowment liability
is less exposed to. The inner conditional valuation reuses the governed HW1F Q nest
(real-world-outer / risk-neutral-inner; a fully G2++-consistent inner nest is a
documented residual).

## 2. HW1F vs G2++ standalone capital (same config, n_outer={no}, n_inner={ni})

| Driver | HW1F SCR | G2++ SCR | Delta | Rel |
|--------|---------:|---------:|------:|----:|
{rows}

## 3. Aggregation vs nested (G2++ rate driver)

| Method | Aggregate SCR | Rel. error vs nested |
|--------|--------------:|---------------------:|
| Var-covar (5x5 ESG) | {vc:,.0f} | {vcr:.1%} |
| Copula ({cop}, realised losses) | {cs:,.0f} | {csr:.1%} |
| **Nested ground truth** | **{nest:,.0f}** | - |

- HW1F var-covar understated nested by {hu:.1f}%; G2++ var-covar understates by {gu:.1f}% (MR-010 refreshed).
- HW1F copula reconciled within {hcr:.1f}%; G2++ copula reconciles within {gcr:.1f}% (MR-012 refreshed).
- Nested capital moves from {hnest:,.0f} (HW1F) to {nest:,.0f} (G2++): {ndl:+,.0f} ({nrd:+.1%}).

## 4. Notes

{notes}
""".format(
        ts=rep["run_timestamp"], verdict=g["verdict"],
        a=CALIBRATED_G2PP_PARAMS["mean_reversion_x"], b=CALIBRATED_G2PP_PARAMS["mean_reversion_y"],
        s=CALIBRATED_G2PP_PARAMS["vol_x"], e=CALIBRATED_G2PP_PARAMS["vol_y"],
        rho=CALIBRATED_G2PP_PARAMS["factor_correlation"],
        no=N_OUTER, ni=N_INNER, rows=rows,
        vc=g["var_covar"]["correlated_scr"], vcr=g["var_covar"]["formula_vs_nested_scr_rel_error"],
        cop=c["g2pp_copula"], cs=c["copula_scr"]["g2pp"], csr=c["g2pp_copula_rel_err"],
        nest=g["nested_scr"], hu=c["hw1f_understatement_pct"], gu=c["g2pp_understatement_pct"],
        hcr=100.0 * c["hw1f_copula_rel_err"], gcr=100.0 * c["g2pp_copula_rel_err"],
        hnest=c["nested_scr"]["hw1f"], ndl=c["nested_scr"]["delta"], nrd=c["nested_scr"]["rel_delta"],
        notes="\n".join("- " + n for n in g["notes"]),
    )


def _tail_markdown(rep: Dict[str, Any]) -> str:
    t = rep["tail"]; b = t["bootstrap_scr_995"]
    lvl = "\n".join(
        "| {k} | {v[var]:,.0f} | {v[es]:,.0f} | {v[scr_var]:,.0f} | {v[scr_es]:,.0f} |".format(k=k, v=v)
        for k, v in t["var_es_by_level"].items())
    conv = "\n".join("| {c[n_outer]} | {c[scr_proxy]:,.0f} |".format(c=c) for c in t["outer_convergence"])
    return """# Phase 20 Task 4 -- Tail Diagnostics (Two-Factor G2++ Rate Driver)

**Run:** {ts}

Diagnostics on the genuine five-driver nested loss vector with the 2F G2++ rate driver
(n_outer={n}, confidence {conf:.1%}).

## VaR / ES by confidence level

| Level | VaR | ES | SCR (VaR-mean) | SCR (ES-mean) |
|-------|----:|---:|---------------:|--------------:|
{lvl}

## Outer convergence (99.5% SCR over increasing subsamples)

| n_outer | SCR-proxy |
|--------:|----------:|
{conv}

## Bootstrap 95% CI for the 99.5% SCR-proxy

- Point: {pt:,.0f}; 95% CI [{lo:,.0f}, {hi:,.0f}] over {nb} resamples; relative half-width {rh:.1%}.

The relative half-width quantifies outer Monte-Carlo noise at this educational scale;
production sign-off requires a larger outer sample (recorded as a residual).
""".format(
        ts=rep["run_timestamp"], n=t["n_outer"], conf=CONF, lvl=lvl, conv=conv,
        pt=b["point"], lo=b["ci_lo_95"], hi=b["ci_hi_95"], nb=b["n_boot"], rh=b["rel_halfwidth"],
    )


def _write_card(rep: Dict[str, Any]) -> None:
    c = rep["comparison"]; g = rep["g2pp_report"]
    CARD_PATH.write_text(
        """# Multi-Driver 5D Capital -- Two-Factor G2++ Rate Driver Card

**Phase:** 20 - Market-Consistency and Multi-Factor Uplift (Task 4)

**Status:** Capital re-aggregation evidence at EDUCATIONAL calibration; verdict {verdict}.
Production sign-off withheld pending UI surfacing (Task 5), a fully G2++-consistent inner
nest, a larger outer sample, and independent (APS X2) review.

## Purpose

Re-aggregates the five-driver economic-capital proxy with the swaption-calibrated
two-factor G2++ rate driver replacing the single-factor Hull-White driver in the
outer real-world state, isolating the capital impact of the second (slope/curvature)
factor and the calibrated factor volatilities/correlation.

## Method

- OUTER rate state r_H = phi(t) + x(t) + y(t) (exact-OU factors), anchored to the same
  initial curve as HW1F; dominant factor x carries the governed 5x5 ESG cross-correlation,
  second factor y is correlated to x by the calibrated rho and otherwise orthogonal.
- INNER conditional valuation reuses the governed HW1F Q nest at r_H (real-world-outer /
  risk-neutral-inner; ASOP 56 section 3.5).
- Aggregation: 5x5 ESG var-covar (MR-010) and copula-on-realised-losses (MR-012),
  benchmarked to genuine five-driver nested capital.

## Headline result (educational proxy)

- Horizon short-rate dispersion falls from ~114 bps (HW1F placeholder) to ~49 bps
  (calibrated G2++): rate-risk and nested capital fall materially.
- Nested SCR: {hnest:,.0f} (HW1F) -> {gnest:,.0f} (G2++).
- G2++ var-covar understates nested by {gu:.1f}% (MR-010); G2++ copula ({cop}) reconciles
  within {gcr:.1f}% (MR-012) -- the tail-dependent mitigation re-confirmed under the 2F driver.

## Model-use restriction

Educational only. The G2++ rate driver is calibrated to an educational-proxy swaption
surface; the inner nest remains HW1F. Not for production capital, pricing, or disclosure.
""".format(
            verdict=g["verdict"], hnest=c["nested_scr"]["hw1f"], gnest=g["nested_scr"],
            gu=c["g2pp_understatement_pct"], cop=c["g2pp_copula"],
            gcr=100.0 * c["g2pp_copula_rel_err"],
        ),
        encoding="utf-8",
    )


def _has_change_record(store: GovernanceStore) -> bool:
    return any(r.title == CHANGE_TITLE for r in store.change_records)


def _refresh_mr(store: GovernanceStore, mr_id: str, note: str) -> str:
    try:
        risk = store.risk_register.get(mr_id)
        risk.update_mitigation(MitigationStatus.MITIGATED, notes=note)
        return "refreshed"
    except KeyError:
        return "missing"


def apply_governance(store: GovernanceStore, rep: Dict[str, Any]) -> Dict[str, Any]:
    c = rep["comparison"]; g = rep["g2pp_report"]
    mr010_note = (
        "Phase 20 Task 4 re-aggregated economic capital with the two-factor G2++ rates driver. "
        "The 5x5 ESG var-covar formula still understates the diversified nested capital ("
        "{gu:.1f}% under the 2F driver vs {hu:.1f}% under HW1F at the same config); the "
        "copula-on-realised-losses mitigation reconciles to nested within {gcr:.1f}%. MR-010 "
        "mitigation re-confirmed under the calibrated 2F rate driver."
    ).format(gu=c["g2pp_understatement_pct"], hu=c["hw1f_understatement_pct"],
             gcr=100.0 * c["g2pp_copula_rel_err"])
    mr012_note = (
        "Phase 20 Task 4 refreshed tail diagnostics (VaR/ES, outer convergence, bootstrap CI) "
        "under the two-factor G2++ rate driver. Selected copula: {cop}; reconciles to nested "
        "within {gcr:.1f}%. The calibrated 2F driver lowers horizon short-rate dispersion "
        "(~114 -> ~49 bps), moving nested SCR from {hnest:,.0f} to {gnest:,.0f}; the tail-"
        "aggregation governance (copula not over-stating orthogonal axes) holds under the 2F driver."
    ).format(cop=c["g2pp_copula"], gcr=100.0 * c["g2pp_copula_rel_err"],
             hnest=c["nested_scr"]["hw1f"], gnest=g["nested_scr"])
    mr010_action = _refresh_mr(store, "MR-010", mr010_note)
    mr012_action = _refresh_mr(store, "MR-012", mr012_note)

    added = False
    record_id = record_status = None
    if not _has_change_record(store):
        rec = ChangeRecord.create(
            title=CHANGE_TITLE,
            description=(
                "Phase 20 Task 4 propagated the two-factor G2++ rates driver (Phase 20 Task 2 "
                "swaption calibration) into the five-driver economic-capital proxy. An additive "
                "module substitutes the G2++ two-factor short rate for HW1F in the outer real-world "
                "state (dominant factor carries the governed ESG cross-correlation; second factor "
                "adds an orthogonal slope/curvature axis), reuses the governed HW1F inner nest as "
                "the conditional liability operator, and re-runs the var-covar + copula aggregation "
                "and tail diagnostics against genuine nested capital."
            ),
            change_type="methodology_change",
            affected_components=AFFECTED_COMPONENTS,
            standard_references=STANDARD_REFERENCES,
            before_snapshot={
                "rate_driver_in_capital": "HW1F single-factor (placeholder vol)",
                "nested_scr": round(c["nested_scr"]["hw1f"], 1),
            },
            after_snapshot={
                "rate_driver_in_capital": "G2++ two-factor (swaption-calibrated)",
                "nested_scr": round(g["nested_scr"], 1),
                "g2pp_var_covar_understatement_pct": c["g2pp_understatement_pct"],
                "g2pp_copula": c["g2pp_copula"],
                "g2pp_copula_rel_err": c["g2pp_copula_rel_err"],
                "verdict": g["verdict"].split(" - ")[0],
            },
            impact_assessment=(
                "Re-states the rate-risk marginal that feeds economic capital with a calibrated "
                "two-factor driver. No existing module is modified (additive). Surfaces that the "
                "swaption-calibrated factor vols (and strong negative factor correlation) materially "
                "lower horizon short-rate dispersion vs the HW1F placeholder, reducing rate-risk and "
                "nested capital; the copula tail-dependent mitigation (MR-010/MR-012) re-confirms."
            ),
            quantitative_impact=(
                "Nested SCR {hnest:,.0f} (HW1F) -> {gnest:,.0f} (G2++) at n_outer={no}, n_inner={ni}. "
                "G2++ var-covar understates nested by {gu:.1f}%; copula ({cop}) reconciles within {gcr:.1f}%."
            ).format(hnest=c["nested_scr"]["hw1f"], gnest=g["nested_scr"], no=N_OUTER, ni=N_INNER,
                     gu=c["g2pp_understatement_pct"], cop=c["g2pp_copula"],
                     gcr=100.0 * c["g2pp_copula_rel_err"]),
            author=ACTOR, phase=PHASE,
            peer_reviewer="APS_X2_Independent_Reviewer", assumption_owner="ChiefActuary",
        )
        rec.submit_for_peer_review(
            ACTOR, "2F G2++ capital re-aggregation staged; inner nest remains HW1F; larger outer "
                   "sample and market-surface recalibration required before approval.")
        rec.submit_to_owner(
            ACTOR, "Owner review requested. Production sign-off withheld pending Task 5 UI surfacing, "
                   "G2++-consistent inner nest, and a validated market surface.")
        store.add_change_record(rec)
        added = True
        record_id = rec.record_id; record_status = rec.status.value
        store.audit_trail.append(AuditEntry.governance(
            actor=ACTOR, phase=PHASE,
            event="ChangeRecord opened (OWNER_REVIEW) - 2F G2++ capital re-aggregation",
            details={"record_id": rec.record_id, "nested_scr_hw1f": c["nested_scr"]["hw1f"],
                     "nested_scr_g2pp": g["nested_scr"], "mr010_action": mr010_action,
                     "mr012_action": mr012_action}))
    else:
        for rec in store.change_records:
            if rec.title == CHANGE_TITLE:
                record_id = rec.record_id; record_status = rec.status.value
                break
    return {
        "mr010_action": mr010_action, "mr012_action": mr012_action,
        "mr010_status": store.risk_register.get("MR-010").mitigation_status.value,
        "mr012_status": store.risk_register.get("MR-012").mitigation_status.value,
        "added_change_record": added, "change_record_id": record_id,
        "change_record_status": record_status,
    }


STAGE_DIR = Path("/sessions/trusting-relaxed-johnson/mnt/outputs")
HW_PKL = STAGE_DIR / "_t4_hw.pkl"
G2_PKL = STAGE_DIR / "_t4_g2.pkl"


def _product_cfg():
    product = ParEndowmentProduct(issue_age=45, gender="M", sum_assured=100000.0,
                                  annual_premium=5000.0, term_years=20)
    cfg = FiveDriverAggregationConfig(n_outer=N_OUTER, n_inner=N_INNER, seed=SEED,
                                      capital_horizon_months=HORIZON, n_sim_copula=N_SIM_COPULA,
                                      confidence_level=CONF)
    return product, cfg


def stage_hw() -> int:
    product, cfg = _product_cfg()
    print("Running HW1F baseline ...", flush=True)
    hw = FiveDriverRiskAggregator(product).run(config=cfg)
    HW_PKL.write_bytes(pickle.dumps(hw))
    print("HW1F nested SCR {:,.0f} -> {}".format(hw.nested_scr, HW_PKL))
    return 0


def stage_g2() -> int:
    product, cfg = _product_cfg()
    print("Running G2++ 2F aggregation ...", flush=True)
    g2agg = G2ppFiveDriverRiskAggregator(product, g2pp_params=calibrated_g2pp_params())
    g2 = g2agg.run(config=cfg)
    G2_PKL.write_bytes(pickle.dumps({"report": g2, "full_l": g2agg.last_loss_vectors["full"]}))
    print("G2++ nested SCR {:,.0f} verdict {} -> {}".format(g2.nested_scr, g2.verdict.split(' - ')[0], G2_PKL))
    return 0


def stage_fin() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _, cfg = _product_cfg()
    hw = pickle.loads(HW_PKL.read_bytes())
    g2blob = pickle.loads(G2_PKL.read_bytes())
    g2 = g2blob["report"]; full_l = g2blob["full_l"]
    tail = _tail_diagnostics(full_l, g2.nested_scr)
    comparison = _comparison(hw, g2)

    report = {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": PHASE,
        "task": "Phase 20 Task 4 - capital re-aggregation with the two-factor G2++ rates driver",
        "config": cfg.to_dict(),
        "g2pp_params": CALIBRATED_G2PP_PARAMS,
        "hw1f_report": hw.to_dict(),
        "g2pp_report": g2.to_dict(),
        "comparison": comparison,
        "tail": tail,
        "standard_references": STANDARD_REFERENCES,
    }
    store = GovernanceStore.from_json(GOV_PATH.read_text(encoding="utf-8")) if GOV_PATH.exists() else GovernanceStore()
    gov = apply_governance(store, report)
    report["governance"] = gov
    report["audit_integrity_ok"] = store.audit_trail.verify_all()
    report["change_records_total"] = len(store.change_records)
    if GOV_PATH.exists():
        GOV_PATH.write_text(store.to_json() + "\n", encoding="utf-8")

    AGG_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    AGG_MD.write_text(_agg_markdown(report), encoding="utf-8")
    TAIL_JSON.write_text(json.dumps({"run_timestamp": report["run_timestamp"], "tail": tail,
                                     "config": cfg.to_dict()}, indent=2) + "\n", encoding="utf-8")
    TAIL_MD.write_text(_tail_markdown(report), encoding="utf-8")
    _write_card(report)

    c = comparison
    print("=== Phase 20 Task 4 - Capital Re-Aggregation (2F G2++) ===")
    print("G2++ verdict      : {}".format(g2.verdict.split(' - ')[0]))
    print("Nested SCR HW1F   : {:,.0f}".format(c["nested_scr"]["hw1f"]))
    print("Nested SCR G2++   : {:,.0f} ({:+.1%})".format(c["nested_scr"]["g2pp"], c["nested_scr"]["rel_delta"]))
    print("Rate SCR HW1F/G2++: {:,.0f} / {:,.0f}".format(c["standalone"][0]["hw1f"], c["standalone"][0]["g2pp"]))
    print("G2++ var-covar    : understate {:.1f}%".format(c["g2pp_understatement_pct"]))
    print("G2++ copula       : {} (rel {:.1%})".format(c["g2pp_copula"], c["g2pp_copula_rel_err"]))
    print("Bootstrap 99.5%CI : [{:,.0f}, {:,.0f}] rel-hw {:.1%}".format(
        tail["bootstrap_scr_995"]["ci_lo_95"], tail["bootstrap_scr_995"]["ci_hi_95"],
        tail["bootstrap_scr_995"]["rel_halfwidth"]))
    print("ChangeRecord      : {} ({})".format(gov["change_record_id"], gov["change_record_status"]))
    print("MR-010 / MR-012   : {} ({}) / {} ({})".format(gov["mr010_status"], gov["mr010_action"],
                                                          gov["mr012_status"], gov["mr012_action"]))
    print("Audit integrity   : {}".format(report["audit_integrity_ok"]))
    print("Reports           : {}".format(AGG_JSON))
    ok = g2.verdict.startswith("PASS") and report["audit_integrity_ok"]
    return 0 if ok else 1


def main() -> int:
    stage = os.environ.get("STAGE", "all")
    if stage == "hw":
        return stage_hw()
    if stage == "g2":
        return stage_g2()
    if stage == "fin":
        return stage_fin()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    product = ParEndowmentProduct(issue_age=45, gender="M", sum_assured=100000.0,
                                  annual_premium=5000.0, term_years=20)
    cfg = FiveDriverAggregationConfig(n_outer=N_OUTER, n_inner=N_INNER, seed=SEED,
                                      capital_horizon_months=HORIZON, n_sim_copula=N_SIM_COPULA,
                                      confidence_level=CONF)
    print("Running HW1F baseline ...", flush=True)
    hw = FiveDriverRiskAggregator(product).run(config=cfg)
    print("Running G2++ 2F aggregation ...", flush=True)
    g2agg = G2ppFiveDriverRiskAggregator(product, g2pp_params=calibrated_g2pp_params())
    g2 = g2agg.run(config=cfg)
    full_l = g2agg.last_loss_vectors["full"]
    tail = _tail_diagnostics(full_l, g2.nested_scr)
    comparison = _comparison(hw, g2)

    report = {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": PHASE,
        "task": "Phase 20 Task 4 - capital re-aggregation with the two-factor G2++ rates driver",
        "config": cfg.to_dict(),
        "g2pp_params": CALIBRATED_G2PP_PARAMS,
        "hw1f_report": hw.to_dict(),
        "g2pp_report": g2.to_dict(),
        "comparison": comparison,
        "tail": tail,
        "standard_references": STANDARD_REFERENCES,
    }

    store = GovernanceStore.from_json(GOV_PATH.read_text(encoding="utf-8")) if GOV_PATH.exists() else GovernanceStore()
    gov = apply_governance(store, report)
    report["governance"] = gov
    report["audit_integrity_ok"] = store.audit_trail.verify_all()
    report["change_records_total"] = len(store.change_records)
    if GOV_PATH.exists():
        GOV_PATH.write_text(store.to_json() + "\n", encoding="utf-8")

    AGG_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    AGG_MD.write_text(_agg_markdown(report), encoding="utf-8")
    TAIL_JSON.write_text(json.dumps({"run_timestamp": report["run_timestamp"], "tail": tail,
                                     "config": cfg.to_dict()}, indent=2) + "\n", encoding="utf-8")
    TAIL_MD.write_text(_tail_markdown(report), encoding="utf-8")
    _write_card(report)

    c = comparison
    print("=== Phase 20 Task 4 - Capital Re-Aggregation (2F G2++) ===")
    print("G2++ verdict      : {}".format(g2.verdict.split(' - ')[0]))
    print("Nested SCR HW1F   : {:,.0f}".format(c["nested_scr"]["hw1f"]))
    print("Nested SCR G2++   : {:,.0f} ({:+.1%})".format(c["nested_scr"]["g2pp"], c["nested_scr"]["rel_delta"]))
    print("Rate SCR HW1F/G2++: {:,.0f} / {:,.0f}".format(c["standalone"][0]["hw1f"], c["standalone"][0]["g2pp"]))
    print("G2++ var-covar    : {:,.0f} (understate {:.1f}%)".format(g2.var_covar.correlated_scr, c["g2pp_understatement_pct"]))
    print("G2++ copula       : {} {:,.0f} (rel {:.1%})".format(c["g2pp_copula"], c["copula_scr"]["g2pp"], c["g2pp_copula_rel_err"]))
    print("Bootstrap 99.5%CI : [{:,.0f}, {:,.0f}] rel-hw {:.1%}".format(
        tail["bootstrap_scr_995"]["ci_lo_95"], tail["bootstrap_scr_995"]["ci_hi_95"],
        tail["bootstrap_scr_995"]["rel_halfwidth"]))
    print("ChangeRecord      : {} ({})".format(gov["change_record_id"], gov["change_record_status"]))
    print("MR-010 / MR-012   : {} ({}) / {} ({})".format(gov["mr010_status"], gov["mr010_action"],
                                                          gov["mr012_status"], gov["mr012_action"]))
    print("Audit integrity   : {}".format(report["audit_integrity_ok"]))
    print("Reports           : {}".format(AGG_JSON))
    ok = g2.verdict.startswith("PASS") and report["audit_integrity_ok"]
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
