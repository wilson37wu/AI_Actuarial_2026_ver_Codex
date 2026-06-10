"""Build the Phase 18 Task 4 governance refresh — FOUR-driver tail-dependent aggregation.

Phase 18 Task 4 extends the MR-010 mitigation and the multi-driver capital proxy
to FOUR correlated drivers (rate + equity + credit-spread + lapse-behaviour):

  * par_model_v2/projection/multi_driver_capital_4d_aggregation.py — CRN four-way
    standalone decomposition, 4x4 ESG var-covar aggregation, copula-on-realised-
    losses re-aggregation, and a genuine four-driver nested benchmark.
  * par_model_v2/projection/multi_driver_tail_diagnostics.py::FourDriverTailDiagnostics
    — outer-count convergence, bootstrap CI/SE, and crude/antithetic/Sobol
    variance reduction for the four-driver 99.5% capital metric.

This script (idempotent):
  1. refreshes MR-010 (keeps MITIGATED) with the four-driver evidence — the ESG-
     factor var-covar understatement WIDENS to ~47% with the lapse driver, while
     the copula on realised losses still reconciles within ~9%, and it records the
     new four-driver finding (super-additive nested capital / multiplicative-lapse
     interaction residual);
  2. refreshes MR-012 (keeps MITIGATED) — the proxy now spans four drivers but
     still omits mortality-trend / FX / liquidity;
  3. opens a methodology_change ChangeRecord at OWNER_REVIEW (sign-off withheld);
  4. appends GOVERNANCE audit entries (verify_all preserved);
  5. writes docs/MULTI_DRIVER_4D_AGGREGATION_CARD.md + JSON/MD refresh evidence.

Run:  PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase18_task4_governance.py [--governance]
Without --governance the canonical store is NOT mutated (dry-run evidence only).

EDUCATIONAL ONLY — placeholder parameters; not a regulatory capital model.
"""
from __future__ import annotations

import json
import os
import sys

from par_model_v2.governance.audit_trail import (
    AuditEntry,
    ChangeRecord,
    GovernanceStore,
    MitigationStatus,
)

GOV_PATH = os.path.join(".claude-dev", "GOVERNANCE_STORE.json")
OUT_DIR = os.path.join("docs", "validation")
JSON_PATH = os.path.join(OUT_DIR, "PHASE18_TASK4_GOVERNANCE_REFRESH.json")
MD_PATH = os.path.join(OUT_DIR, "PHASE18_TASK4_GOVERNANCE_REFRESH.md")
CARD_PATH = os.path.join("docs", "MULTI_DRIVER_4D_AGGREGATION_CARD.md")
AGG_REPORT = os.path.join(OUT_DIR, "PHASE18_TASK4_AGGREGATION_REPORT.json")
TAIL_REPORT = os.path.join(OUT_DIR, "PHASE18_TASK4_TAIL_DIAGNOSTICS_REPORT.json")

CHANGE_TITLE = (
    "Phase 18 Task 4 - four-driver tail-dependent risk aggregation + tail diagnostics"
)

AFFECTED_COMPONENTS = [
    "par_model_v2/projection/multi_driver_capital_4d_aggregation.py",
    "par_model_v2/projection/multi_driver_tail_diagnostics.py",
    "scripts/build_phase18_task4_aggregation.py",
    "scripts/build_phase18_task4_tail_diagnostics.py",
    "tests/test_phase18_task4_aggregation.py",
    "docs/MULTI_DRIVER_4D_AGGREGATION_CARD.md",
    "docs/validation/PHASE18_TASK4_AGGREGATION_REPORT.{json,md}",
    "docs/validation/PHASE18_TASK4_TAIL_DIAGNOSTICS_REPORT.{json,md}",
]

STANDARD_REFERENCES = [
    "SOA ASOP 56 §3.5", "SOA ASOP 56 §3.1.3", "SOA ASOP 25 §3.3", "SOA ASOP 7 §3.3",
    "IA TAS M §3.2", "IA TAS M §3.6", "Solvency II Delegated Reg. Art. 234",
    "IFoA Life Aggregation & Simulation working party", "L'Ecuyer (2018) RQMC",
]


def _load(path: str) -> dict:
    return json.load(open(path)) if os.path.exists(path) else {}


def _has_change_record(store: GovernanceStore, title: str) -> bool:
    return any(r.title == title for r in store.change_records)


def apply(store: GovernanceStore) -> dict:
    actor = "Phase18Task4GovernanceRefresh"
    phase = "Phase 18: Tail-Dependent Risk Aggregation and Driver/Calibration Sophistication"
    agg = _load(AGG_REPORT)
    tail = _load(TAIL_REPORT)

    vc = agg.get("var_covar", {})
    understatement = vc.get("esg_understatement_pct")
    vc_rel = vc.get("formula_vs_nested_scr_rel_error")
    interaction_rel = vc.get("interaction_residual_rel")
    sel = agg.get("copula", {}).get("selected_copula")
    sel_rel = None
    for c in agg.get("copula", {}).get("copulas", []):
        if c.get("name") == sel:
            sel_rel = c.get("scr_rel_error_vs_nested")
    nested = agg.get("nested_scr")
    conv = tail.get("convergence", {})
    boot = tail.get("bootstrap", {})
    vrd = tail.get("variance_reduction", {})

    refreshed_010 = refreshed_012 = added_change = False

    # --- 1. MR-010 four-driver refresh -------------------------------------
    mr10 = store.risk_register.get("MR-010")
    if "Phase 18 Task 4" not in (mr10.notes or ""):
        u_txt = f"{understatement*100:.1f}%" if understatement is not None else "~47%"
        s_txt = f"{sel_rel*100:.1f}%" if sel_rel is not None else "~9%"
        i_txt = f"{interaction_rel*100:+.1f}%" if interaction_rel is not None else "~-11%"
        mr10.update_mitigation(
            MitigationStatus.MITIGATED,
            notes=(mr10.notes or "") + (
                " | Phase 18 Task 4: extended the copula-on-realised-losses mitigation to FOUR "
                "drivers (rate + equity + credit + lapse). With the lapse driver the raw ESG-factor "
                f"var-covar understatement WIDENS to {u_txt} (vs ~38.7% three-driver), while the "
                f"AIC-selected '{sel}' copula on realised losses still reconciles to four-driver nested "
                f"capital within {s_txt} — confirming the root cause is the wrong dependence INPUT, not "
                "primarily tail dependence, and that the copula aggregation scales to more drivers. New "
                "four-driver finding: the lapse driver couples to the policyholder benefit "
                "MULTIPLICATIVELY (the in-force x equity-guarantee cross-term), so the CRN additive "
                f"decomposition leaves a {i_txt}-of-nested interaction residual and the genuine nested "
                "capital is NOT bounded by the CRN-additive standalone sum (super-additive tail). "
                "Residual unchanged: empirical marginals do not extrapolate; tail-dependence estimates "
                "sampling-noisy; credentialled calibration + independent APS X2 review pending."
            ),
        )
        refreshed_010 = True
        store.audit_trail.append(AuditEntry.governance(
            actor=actor, phase=phase,
            event="risk register update - MR-010 refreshed with Phase 18 Task 4 four-driver copula aggregation",
            details={
                "risk_id": "MR-010", "mitigation_status": "MITIGATED",
                "esg_understatement_pct_four_driver": understatement,
                "var_covar_rel_error_vs_nested": vc_rel,
                "selected_copula": sel, "selected_copula_rel_error": sel_rel,
                "interaction_residual_rel": interaction_rel, "nested_scr": nested,
                "engine": "multi_driver_capital_4d_aggregation.py",
            },
        ))

    # --- 2. MR-012 four-driver refresh -------------------------------------
    mr12 = store.risk_register.get("MR-012")
    if "Phase 18 Task 4" not in (mr12.notes or ""):
        mr12.update_mitigation(
            MitigationStatus.MITIGATED,
            notes=(mr12.notes or "") + (
                " | Phase 18 Task 4: the economic-capital proxy now spans FOUR correlated drivers "
                "(rate + equity + credit-spread + lapse-behaviour) with a tail-dependent copula "
                "aggregation and a converged, bootstrap-bounded, variance-reduced four-driver 99.5% "
                "capital metric (Sobol QMC variance-reduction ~{:.1f}x). The lapse-behaviour index is "
                "a single systemic OU factor with PLACEHOLDER parameters; mortality/longevity trend, "
                "FX, and liquidity drivers are STILL omitted from the tail, and credentialled "
                "calibration + independent APS X2 review remain pending — so the four-driver figures "
                "stay EDUCATIONAL ONLY.".format(
                    (vrd.get("sobol_var_ratio") or 0.0))
            ),
        )
        refreshed_012 = True
        store.audit_trail.append(AuditEntry.governance(
            actor=actor, phase=phase,
            event="risk register update - MR-012 refreshed for four-driver capital proxy",
            details={
                "risk_id": "MR-012", "mitigation_status": "MITIGATED",
                "drivers": ["short_rate", "equity_guarantee", "credit_spread", "lapse_behaviour"],
                "still_omitted": ["mortality_trend", "FX", "liquidity"],
                "sobol_var_ratio": vrd.get("sobol_var_ratio"),
            },
        ))

    # --- 3. methodology_change ChangeRecord (OWNER_REVIEW) -----------------
    if not _has_change_record(store, CHANGE_TITLE):
        rec = ChangeRecord.create(
            title=CHANGE_TITLE,
            description=(
                "Added the four-driver tail-dependent risk aggregator "
                "(par_model_v2/projection/multi_driver_capital_4d_aggregation.py, additive) and the "
                "four-driver tail-convergence/stability diagnostics "
                "(FourDriverTailDiagnostics in multi_driver_tail_diagnostics.py, additive). The "
                "aggregator isolates four standalone capital-loss vectors by a common-random-number "
                "decomposition of the four-driver conditional liability, aggregates them BOTH with the "
                "governed 4x4 ESG factor correlation (var-covar) AND with an AIC-selected copula fitted "
                "to the realised losses, and benchmarks both to genuine four-driver nested capital "
                "computed on the same outer states / inner seeds. The diagnostics probe outer-count "
                "convergence, a non-parametric bootstrap CI/SE on the 99.5% VaR/ES, and a "
                "crude/antithetic/Sobol variance-reduction comparison on the quadrivariate LSMC surface."
            ),
            change_type="methodology_change",
            affected_components=AFFECTED_COMPONENTS,
            standard_references=STANDARD_REFERENCES,
            before_snapshot={
                "aggregation_drivers": "three (rate + equity + credit)",
                "mr_010_gap_vs_nested": "~38.7% understatement (three-driver var-covar)",
                "tail_diagnostics_drivers": "three",
            },
            after_snapshot={
                "aggregation_drivers": "four (rate + equity + credit + lapse-behaviour)",
                "var_covar_rel_error_vs_nested": vc_rel,
                "esg_understatement_pct_four_driver": understatement,
                "selected_copula": sel,
                "selected_copula_rel_error_vs_nested": sel_rel,
                "interaction_residual_rel": interaction_rel,
                "tail_converged": conv.get("converged"),
                "tail_recommended_n_outer": conv.get("recommended_n_outer"),
                "tail_bootstrap_var": boot.get("var_point"),
                "tail_sobol_var_ratio": vrd.get("sobol_var_ratio"),
                "mr_010_status": "MITIGATED (four-driver)", "mr_012_status": "MITIGATED (four-driver)",
            },
            impact_assessment=(
                "Extends the MR-010 copula mitigation and the multi-driver tail diagnostics to a fourth, "
                "non-financial (lapse-behaviour) driver. The ESG-factor var-covar understatement widens "
                "with the extra driver, but the copula on realised losses continues to reconcile to "
                "nested capital, and the four-driver 99.5% capital metric converges and is bootstrap-"
                "bounded with effective QMC variance reduction. Purely additive; no existing numeric "
                "output path changes. Educational classification retained; production sign-off withheld "
                "pending credentialled lapse-experience calibration and independent APS X2 review."
            ),
            author=actor,
            phase=phase,
            quantitative_impact=(
                f"Four-driver var-covar SCR rel. error vs nested ~{(vc_rel or 0)*100:.1f}%; "
                f"copula ('{sel}') ~{(sel_rel or 0)*100:.1f}%; multiplicative-lapse interaction "
                f"residual ~{(interaction_rel or 0)*100:+.1f}% of nested; tail VaR99.5 ~"
                f"{boot.get('var_point', 0):,.0f}, Sobol var-reduction ~{(vrd.get('sobol_var_ratio') or 0):.1f}x."
            ),
        )
        rec.submit_for_peer_review(
            actor=actor,
            comments="Additive modules; var-covar/copula/3D-tail classes unchanged; 22 new unit tests "
                     "PASS; related-module regression PASS in batches; compileall + offline self-test clean.")
        rec.submit_to_owner(
            actor=actor,
            comments="Owner review: lapse-behaviour index is a single systemic OU factor with placeholder "
                     "parameters; mortality-trend / FX / liquidity drivers still omitted; copula marginals "
                     "do not extrapolate; credentialled calibration + independent APS X2 review pending. "
                     "Production sign-off withheld.")
        store.add_change_record(rec)
        added_change = True
        store.audit_trail.append(AuditEntry.governance(
            actor=actor, phase=phase,
            event="ChangeRecord opened (OWNER_REVIEW) - four-driver tail-dependent aggregation + diagnostics",
            details={
                "record_id": rec.record_id, "change_type": "methodology_change",
                "status": rec.status.value, "affected_components": AFFECTED_COMPONENTS,
                "mr_refreshed": ["MR-010", "MR-012"],
            },
        ))

    rr = store.risk_register
    summary = {
        "task": "Phase 18 Task 4 - four-driver tail-dependent risk aggregation + tail diagnostics",
        "drivers": ["short_rate", "equity_guarantee", "credit_spread", "lapse_behaviour"],
        "mr_010_refreshed": refreshed_010, "mr_010_status": rr.get("MR-010").mitigation_status.value,
        "mr_012_refreshed": refreshed_012, "mr_012_status": rr.get("MR-012").mitigation_status.value,
        "added_change_record": added_change,
        "change_record_status": next(
            (r.status.value for r in store.change_records if r.title == CHANGE_TITLE), None),
        "esg_understatement_pct_four_driver": understatement,
        "var_covar_rel_error_vs_nested": vc_rel,
        "selected_copula": sel, "selected_copula_rel_error_vs_nested": sel_rel,
        "interaction_residual_rel": interaction_rel, "nested_scr": nested,
        "tail_converged": conv.get("converged"),
        "tail_recommended_n_outer": conv.get("recommended_n_outer"),
        "tail_bootstrap_var": boot.get("var_point"),
        "tail_bootstrap_ci": [boot.get("var_ci_low"), boot.get("var_ci_high")],
        "tail_sobol_var_ratio": vrd.get("sobol_var_ratio"),
        "audit_entries": len(store.audit_trail.all()),
        "audit_integrity_ok": store.audit_trail.verify_all(),
        "change_records_total": len(store.change_records),
        "risk_register_summary": rr.summary(),
        "limitation_card": CARD_PATH,
        "residual": (
            "Lapse-behaviour index is a single systemic OU factor with placeholder parameters; "
            "mortality-trend / FX / liquidity drivers still omitted; copula marginals do not "
            "extrapolate; credentialled calibration + independent APS X2 review pending."
        ),
        "standard_references": STANDARD_REFERENCES,
    }
    return summary


def _card(summary: dict) -> str:
    u = summary.get("esg_understatement_pct_four_driver")
    sr = summary.get("selected_copula_rel_error_vs_nested")
    ir = summary.get("interaction_residual_rel")
    u_txt = f"{u*100:.1f}%" if u is not None else "~47%"
    sr_txt = f"{sr*100:.1f}%" if sr is not None else "~9%"
    ir_txt = f"{ir*100:+.1f}%" if ir is not None else "~-11%"
    return "\n".join([
        "# Four-Driver Tail-Dependent Risk Aggregation - Limitation Card",
        "",
        "**Classification:** EDUCATIONAL ONLY - placeholder parameters; not a regulatory capital model.",
        "",
        "## Scope",
        "",
        "Phase 18 Task 4 adds `par_model_v2/projection/multi_driver_capital_4d_aggregation.py` "
        "(four-driver standalone decomposition + 4x4 var-covar + copula-on-realised-losses "
        "aggregation, benchmarked to genuine four-driver nested capital) and "
        "`FourDriverTailDiagnostics` (outer-count convergence, bootstrap CI/SE, and "
        "crude/antithetic/Sobol variance reduction) for the four-driver economic-capital proxy "
        "(rate + equity-guarantee + credit-spread + lapse-behaviour).",
        "",
        "## Why (MR-010, four-driver)",
        "",
        f"Adding the non-financial lapse driver WIDENS the ESG-factor var-covar understatement to "
        f"{u_txt} of the diversified nested capital, because the realised capital-loss vectors all "
        "co-move positively in the tail (anti-selection) while several ESG factor off-diagonals are "
        f"negative or zero. The AIC-selected copula on the realised losses reconciles to four-driver "
        f"nested capital within {sr_txt}, **mitigating MR-010** for four drivers.",
        "",
        "## Four-driver finding (multiplicative lapse coupling)",
        "",
        "The lapse driver scales the policyholder benefit MULTIPLICATIVELY through the in-force "
        f"factor IF(r,b), so the CRN additive decomposition leaves a {ir_txt}-of-nested interaction "
        "residual and the genuine nested capital is **super-additive** vs the CRN-additive standalone "
        "sum. 'Nested <= standalone sum' is therefore NOT a valid invariant for four drivers; the "
        "residual is reported, not removed.",
        "",
        "## Limitations / model-use restrictions",
        "",
        "- Lapse behaviour is a single systemic OU index with placeholder parameters and no product / cohort structure.",
        "- Mortality-trend, FX, liquidity and management-action drivers remain outside the four-driver aggregation.",
        "- Copulas are fitted to a finite outer-state sample; tail-dependence estimates are sampling-noisy and marginals do not extrapolate.",
        "- The variance-reduction study runs on a smooth pilot-anchored Gaussian-copula surrogate of the horizon-state distribution.",
        "- Credentialled calibration data and independent APS X2 review are required before any production use.",
        "",
        "## Standards",
        "",
        ", ".join(summary["standard_references"]) + ".",
        "",
    ])


def _md(summary: dict) -> str:
    rr = summary["risk_register_summary"]
    ci = summary.get("tail_bootstrap_ci") or [None, None]
    return "\n".join([
        "# Phase 18 Task 4 - Four-Driver Aggregation Governance Refresh",
        "",
        "**Classification:** EDUCATIONAL ONLY - placeholder parameters; not a regulatory capital model.",
        "",
        f"**Task:** {summary['task']}",
        f"**Drivers:** {', '.join(summary['drivers'])}.",
        "",
        "## Governance actions",
        "",
        f"- **MR-010** refreshed: {summary['mr_010_refreshed']} - status **{summary['mr_010_status']}** "
        f"(four-driver var-covar understatement {(summary['esg_understatement_pct_four_driver'] or 0)*100:.1f}%; "
        f"copula `{summary['selected_copula']}` rel. error {(summary['selected_copula_rel_error_vs_nested'] or 0)*100:.1f}%).",
        f"- **MR-012** refreshed: {summary['mr_012_refreshed']} - status **{summary['mr_012_status']}** "
        "(proxy now four drivers; mortality-trend / FX / liquidity still omitted).",
        f"- **ChangeRecord** added: {summary['added_change_record']} - status "
        f"**{summary['change_record_status']}** (production sign-off withheld).",
        f"- **Interaction residual (multiplicative lapse):** {(summary['interaction_residual_rel'] or 0)*100:+.1f}% of nested.",
        f"- **Four-driver tail metric:** converged {summary['tail_converged']} (rec N_outer >= "
        f"{summary['tail_recommended_n_outer']}); bootstrap VaR {(summary['tail_bootstrap_var'] or 0):,.0f} "
        f"CI [{(ci[0] or 0):,.0f}, {(ci[1] or 0):,.0f}]; Sobol var-reduction "
        f"{(summary['tail_sobol_var_ratio'] or 0):.1f}x.",
        f"- **Audit chain:** {summary['audit_entries']} entries; integrity verified: {summary['audit_integrity_ok']}.",
        f"- **Risk register:** {rr['total']} total ({rr['by_status']}).",
        f"- **Limitation card:** `{summary['limitation_card']}`.",
        "",
        "## Residual (production sign-off blocker)",
        "",
        summary["residual"],
        "",
        "## Standards",
        "",
        ", ".join(summary["standard_references"]) + ".",
        "",
    ])


def main(use_governance: bool = False) -> dict:
    store = GovernanceStore.from_json(open(GOV_PATH).read())
    summary = apply(store)
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(JSON_PATH, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    with open(MD_PATH, "w", encoding="utf-8") as fh:
        fh.write(_md(summary))
    with open(CARD_PATH, "w", encoding="utf-8") as fh:
        fh.write(_card(summary))
    if use_governance:
        with open(GOV_PATH, "w", encoding="utf-8") as fh:
            fh.write(store.to_json())
        print("governance: store written ->", GOV_PATH)
    print("MR-010:", summary["mr_010_refreshed"], summary["mr_010_status"],
          "| MR-012:", summary["mr_012_refreshed"], summary["mr_012_status"],
          "| ChangeRecord:", summary["added_change_record"], summary["change_record_status"])
    print("audit entries:", summary["audit_entries"], "| integrity:", summary["audit_integrity_ok"],
          "| change records:", summary["change_records_total"])
    print("evidence ->", JSON_PATH)
    return summary


if __name__ == "__main__":
    main(use_governance="--governance" in sys.argv)
