"""Phase 16 — offline result-viewer bundler.

Scans the model's already-produced output artifacts (no model calculation is done
here), normalises them into a single ``viewer_data.json`` schema, and emits a
fully self-contained ``model_result_viewer.html`` with that snapshot embedded so
the file opens OFFLINE with data pre-loaded (no CDN, no server, no install).

The same HTML also accepts a drag-and-drop / file-picker load of a viewer_data.json
at runtime, so it works with or without the embedded snapshot.

Run:  PYTHONPATH=. python3 scripts/build_offline_viewer.py
Outputs (repo root):  viewer_data.json , model_result_viewer.html
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VAL = os.path.join(REPO, "docs", "validation")
GOV_PATH = os.path.join(REPO, ".claude-dev", "GOVERNANCE_STORE.json")
STATE_PATH = os.path.join(REPO, ".claude-dev", "MODEL_DEV_STATE.json")
GATES_MD = os.path.join(REPO, "docs", "DEPLOYMENT_READINESS_CHECKLIST.md")
TEMPLATE = os.path.join(REPO, "par_model_v2", "viewer", "viewer_template.html")
OUT_JSON = os.path.join(REPO, "viewer_data.json")
OUT_HTML = os.path.join(REPO, "model_result_viewer.html")

DATA_TOKEN = "/*__VIEWER_DATA__*/null"


def _load(path: str) -> Optional[dict]:
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _verify_audit_integrity(gov: dict) -> Tuple[bool, int, int]:
    """Recompute every audit-entry digest (same scheme as
    ``AuditEntry.verify_digest``: sha256(entry_id + timestamp + description +
    json.dumps(details, sort_keys=True))) and report the tally.

    Returns (all_ok, n_verified, n_failed). This makes the viewer's
    audit-integrity badge a *computed* result rather than a hard-coded flag
    (IA TAS M section 3.7 traceability; SOA ASOP 56 section 3.5).
    """
    entries = (gov or {}).get("audit_trail", [])
    n_ok = 0
    n_bad = 0
    for e in entries:
        try:
            raw = (e["entry_id"] + e["timestamp"] + e["description"]
                   + json.dumps(e.get("details", {}), sort_keys=True))
            if hashlib.sha256(raw.encode()).hexdigest() == e.get("digest"):
                n_ok += 1
            else:
                n_bad += 1
        except (KeyError, TypeError):
            n_bad += 1
    return (n_bad == 0 and n_ok > 0), n_ok, n_bad


# Gates G-11/G-12 are not given dedicated rows in the checklist table; their
# status is grounded in docs/PHASE13_DYNAMIC_LAPSE_REPORT.* (G-11) and
# docs/PHASE13_HW1F_CALIBRATION_REPORT.* (G-12), both PASS (educational).
_EXTRA_GATES = [
    {"gate_id": "G-11", "description": "Dynamic lapse calibrated to experience study",
     "status": "CLEARED (educational)", "blocking": "Pricing, MCEV"},
    {"gate_id": "G-12", "description": "Calibration data lineage documented (HW1F)",
     "status": "CLEARED (educational)", "blocking": "Capital adequacy"},
]


def _parse_deployment_gates() -> List[Dict[str, Any]]:
    """Parse the gate summary table from DEPLOYMENT_READINESS_CHECKLIST.md
    (rows ``| G-NN | description | status | blocking |``) and merge in the two
    extra gates (G-11/G-12). Each gate is normalised to
    {gate_id, description, status, level, blocking, cleared}."""
    gates: Dict[str, Dict[str, Any]] = {}
    try:
        with open(GATES_MD, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        text = ""
    row = re.compile(r"^\|\s*(G-\d{2})\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*$")
    for line in text.splitlines():
        m = row.match(line)
        if not m:
            continue
        gid, desc, status, blocking = (s.strip() for s in m.groups())
        if gid in gates:
            continue  # first match wins (the summary table precedes the sign-off table)
        status_clean = re.sub(r"[✅❌]", "", status).strip()
        gates[gid] = {
            "gate_id": gid,
            "description": desc,
            "status": status_clean,
            "level": "educational" if "educational" in status_clean.lower() else "production",
            "blocking": blocking,
            "cleared": ("cleared" in status_clean.lower() or "pass" in status_clean.lower()),
        }
    for g in _EXTRA_GATES:
        if g["gate_id"] not in gates:
            gates[g["gate_id"]] = {
                "gate_id": g["gate_id"], "description": g["description"],
                "status": g["status"], "level": "educational",
                "blocking": g["blocking"], "cleared": True,
            }
    return [gates[k] for k in sorted(gates)]


def build_viewer_data() -> Dict[str, Any]:
    sources: List[str] = []

    def src(path: str, obj):
        if obj is not None:
            sources.append(os.path.relpath(path, REPO))
        return obj

    gov = src(GOV_PATH, _load(GOV_PATH))
    state = src(STATE_PATH, _load(STATE_PATH))

    def _prefer(*names):
        """Load the first existing report among ``names`` (newest phase first).

        Later phases supersede earlier reports of the same kind so the viewer
        shows the most advanced economic-capital proxy with zero churn.
        """
        for n in names:
            p = os.path.join(VAL, n)
            obj = _load(p)
            if obj is not None:
                return src(p, obj)
        return None

    tail = _prefer("PHASE18_TASK4_TAIL_DIAGNOSTICS_REPORT.json",
                   "PHASE17_TAIL_DIAGNOSTICS_REPORT.json",
                   "PHASE15_TAIL_DIAGNOSTICS_REPORT.json")
    agg = _prefer("PHASE18_TASK4_AGGREGATION_REPORT.json",
                  "PHASE17_RISK_AGGREGATION_REPORT.json",
                  "PHASE15_RISK_AGGREGATION_REPORT.json")
    proxy = _prefer("PHASE18_TASK3_PROXY_VALIDATION_REPORT.json",
                    "PHASE17_PROXY_VALIDATION_REPORT.json",
                    "PHASE15_PROXY_VALIDATION_REPORT.json")
    capev = src(os.path.join(VAL, "PHASE15_MULTI_DRIVER_CAPITAL_EVIDENCE.json"),
                _load(os.path.join(VAL, "PHASE15_MULTI_DRIVER_CAPITAL_EVIDENCE.json")))
    lossd = src(os.path.join(VAL, "PHASE16_LOSS_DISTRIBUTION.json"),
                _load(os.path.join(VAL, "PHASE16_LOSS_DISTRIBUTION.json")))
    limitation_cards = []
    for rel, title in [
        ("docs/MULTI_DRIVER_4D_AGGREGATION_CARD.md",
         "Four-driver tail-dependent aggregation limitation card"),
        ("docs/MULTI_DRIVER_4D_PROXY_LIMITATION_CARD.md",
         "Four-driver proxy limitation card"),
    ]:
        p = os.path.join(REPO, rel)
        if os.path.exists(p):
            sources.append(rel)
            limitation_cards.append({"title": title, "path": rel})

    data: Dict[str, Any] = {"meta": {}, "verdicts": [], "summary": {},
                            "capital": {}, "tail": {}, "proxy": {},
                            "loss": {}, "governance": {}}

    # ---- meta + summary -------------------------------------------------
    data["meta"] = {
        "model_name": (gov or {}).get("model_name", "PAR Fund Stochastic ALM & TVOG"),
        "model_version": (gov or {}).get("model_version", "0.2.0"),
        "generated_utc": (capev or {}).get("generated_utc"),
        "source_files": sources,
        "classification": "EDUCATIONAL ONLY -- NOT a regulatory capital model",
    }
    if state:
        m = state.get("progress_metrics", {})
        cs = state.get("completion_summary", {})
        data["summary"] = {
            "tasks_completed": m.get("tasks_completed"),
            "tasks_total": m.get("total_tasks"),
            "phases_completed": m.get("phases_completed"),
            "estimated_completion_pct": m.get("estimated_completion_pct"),
            "gates_cleared": cs.get("production_gates_cleared"),
            "gates_total": cs.get("production_gates_total"),
            "risks_open": cs.get("model_risks_open"),
            "risks_mitigated": cs.get("model_risks_mitigated"),
            "production_status": cs.get("production_status"),
        }

    # ---- verdicts -------------------------------------------------------
    for key, label, obj in [("proxy", "Out-of-sample proxy validation", proxy),
                            ("aggregation", "Correlated risk aggregation", agg),
                            ("tail", "Tail convergence & stability", tail)]:
        if obj and obj.get("verdict"):
            data["verdicts"].append({"key": key, "label": label, "verdict": obj["verdict"]})

    # ---- capital (aggregation + proxy nested) ---------------------------
    if agg:
        sa = agg.get("standalone", {})
        ag = agg.get("aggregation") or agg.get("var_covar", {})
        cop = agg.get("copula") or {}
        rate = sa.get("rate_capital", {}) or {}
        eq = sa.get("equity_capital", {}) or {}
        credit = sa.get("credit_capital", {}) or {}
        lapse = sa.get("lapse_capital", {}) or {}
        nested = ag.get("full_nested_capital", {}) or {}
        drivers = agg.get("drivers") or (
            ["short_rate", "equity", "credit_spread", "lapse_behaviour"] if lapse
            else ["short_rate", "equity", "credit_spread"] if credit
            else ["short_rate", "equity"])

        # Realised capital-loss correlation: Phase 15 reports a scalar
        # (rate-equity); Phase 17 reports a 3x3 matrix. Normalise both to a
        # representative scalar (mean off-diagonal) plus carry the full matrix.
        loss_corr_matrix = sa.get("loss_correlation_matrix")
        comp_loss = sa.get("component_loss_correlation")
        if comp_loss is None and loss_corr_matrix:
            offs = [loss_corr_matrix[i][j]
                    for i in range(len(loss_corr_matrix))
                    for j in range(len(loss_corr_matrix)) if i < j]
            comp_loss = (sum(offs) / len(offs)) if offs else None
        esg_matrix = ag.get("esg_correlation_matrix")
        esg_re = ag.get("esg_rate_equity_correlation")
        if esg_re is None and esg_matrix and len(esg_matrix) >= 2:
            esg_re = esg_matrix[0][1]
        copula_rows = cop.get("copulas") or []
        selected_copula = cop.get("selected_copula")
        selected_copula_row = next(
            (r for r in copula_rows if r.get("name") == selected_copula),
            copula_rows[0] if copula_rows else {},
        )
        best_copula_rel_error = None
        if copula_rows:
            rels = [r.get("scr_rel_error_vs_nested") for r in copula_rows
                    if r.get("scr_rel_error_vs_nested") is not None]
            best_copula_rel_error = min(rels) if rels else None

        data["capital"] = {
            "drivers": drivers,
            "confidence_level": (rate.get("confidence_level") or eq.get("confidence_level")),
            "horizon_months": (rate.get("capital_horizon_months") or eq.get("capital_horizon_months")),
            "rate_scr": rate.get("scr_proxy") or rate.get("var_liability"),
            "equity_scr": eq.get("scr_proxy") or eq.get("var_liability"),
            "credit_scr": (credit.get("scr_proxy") or credit.get("var_liability")) if credit else None,
            "lapse_scr": (lapse.get("scr_proxy") or lapse.get("var_liability")) if lapse else None,
            "standalone_sum": sa.get("standalone_scr_sum"),
            "correlated_scr": ag.get("correlated_scr"),
            "nested_scr": nested.get("scr_proxy") or nested.get("var_liability"),
            "diversification_benefit_formula": ag.get("diversification_benefit_formula"),
            "diversification_benefit_nested": ag.get("diversification_benefit_nested"),
            "component_loss_correlation": comp_loss,
            "loss_correlation_matrix": loss_corr_matrix,
            "esg_correlation_matrix": esg_matrix,
            "esg_understatement_pct": ag.get("esg_understatement_pct"),
            "formula_vs_nested_rel_error": ag.get("formula_vs_nested_scr_rel_error"),
            "esg_rate_equity_correlation": esg_re,
            "copula_selected": selected_copula,
            "copula_scr": (selected_copula_row.get("aggregated_scr")
                           or (selected_copula_row.get("aggregated_capital") or {}).get("scr_proxy")),
            "copula_rel_error_vs_nested": selected_copula_row.get("scr_rel_error_vs_nested"),
            "best_copula_rel_error_vs_nested": best_copula_rel_error,
            "copula_upper_tail_dependence": selected_copula_row.get("upper_tail_dependence"),
            "copula_diversification_benefit": selected_copula_row.get("diversification_benefit"),
            "copula_rows": [
                {"name": r.get("name"),
                 "aggregated_scr": r.get("aggregated_scr"),
                 "scr_rel_error_vs_nested": r.get("scr_rel_error_vs_nested"),
                 "upper_tail_dependence": r.get("upper_tail_dependence"),
                 "aic": r.get("aic")}
                for r in copula_rows
            ],
            "crn_additive_scr": (ag.get("crn_additive_capital") or {}).get("scr_proxy"),
            "interaction_residual_scr": ag.get("interaction_residual_scr"),
            "interaction_residual_rel": ag.get("interaction_residual_rel"),
            "limitation_cards": limitation_cards,
        }
    # fill VaR/ES from tail
    if tail:
        c = tail.get("convergence", {})
        b = tail.get("bootstrap", {})
        v = tail.get("variance_reduction", {})
        data["tail"] = {
            "verdict": tail.get("verdict"),
            "converged": c.get("converged"),
            "recommended_n_outer": c.get("recommended_n_outer"),
            "outer_grid": tail.get("config", {}).get("outer_grid"),
            "var_path": c.get("var_path"),
            "es_path": c.get("es_path"),
            "final_var": c.get("final_var"),
            "final_es": c.get("final_es"),
            "var_ci": [b.get("var_ci_low"), b.get("var_ci_high")],
            "es_ci": [b.get("es_ci_low"), b.get("es_ci_high")],
            "var_point": b.get("var_point"),
            "es_point": b.get("es_point"),
            "var_se": b.get("var_standard_error"),
            "es_se": b.get("es_standard_error"),
            "sobol_ratio": (v.get("sobol") or {}).get("var_ratio") or v.get("sobol_var_ratio"),
            "antithetic_ratio": (v.get("antithetic") or {}).get("var_ratio") or v.get("antithetic_var_ratio"),
        }
        data["capital"].setdefault("var", c.get("final_var"))
        data["capital"].setdefault("es", c.get("final_es"))

    # ---- proxy validation ----------------------------------------------
    if proxy:
        cc = proxy.get("capital_comparison", {})
        # Phase 15 reports `degree_rows` + `overfit_onset_degree`; Phase 17 (three
        # driver) reports `basis_rows` (degree x max_interaction_order grid) +
        # `overfit_onset_terms`. Normalise both to the viewer's degree_rows shape.
        raw_rows = proxy.get("degree_rows") or proxy.get("basis_rows") or []
        rows = [
            {"degree": r.get("degree"),
             "in_sample_r2": (r.get("in_sample_r2") if r.get("in_sample_r2") is not None
                              else r.get("in_sample_r2_heavy")),
             "oos_r2": r.get("oos_r2"),
             "oos_max_abs_rel_error": r.get("oos_max_abs_rel_error"),
             "n_basis_terms": r.get("n_basis_terms")}
            for r in raw_rows
        ]
        onset = proxy.get("overfit_onset_degree")
        if onset is None and proxy.get("overfit_onset_terms") is not None:
            # map the onset term-count to the degree of the matching basis row
            ot = proxy.get("overfit_onset_terms")
            onset = next((r.get("degree") for r in raw_rows
                          if r.get("n_basis_terms") == ot), None)
        data["proxy"] = {
            "verdict": proxy.get("verdict"),
            "selected_degree": proxy.get("selected_degree"),
            "overfit_onset_degree": onset,
            "overfit_onset_terms": proxy.get("overfit_onset_terms"),
            "selection_metric": proxy.get("selection_metric"),
            "degree_rows": rows,
            "var_rel_error": cc.get("var_rel_error"),
            "es_rel_error": cc.get("es_rel_error"),
        }

    # ---- loss distribution (Phase 16 Task 2; viewer-consumed, pre-computed) ---
    if lossd:
        lm = lossd.get("meta", {})
        data["loss"] = {
            "confidence_level": lm.get("confidence_level"),
            "horizon_months": lm.get("horizon_months"),
            "measure": lm.get("measure"),
            "n_outer": lm.get("n_outer"),
            "n_fit": lm.get("n_fit"),
            "fit_r2": lm.get("fit_r2"),
            "seed_base": lm.get("seed_base"),
            "reproducibility_digest": lm.get("reproducibility_digest"),
            "mean_liability": lossd.get("mean_liability"),
            "histogram": lossd.get("histogram"),
            "confidence_sweep": lossd.get("confidence_sweep"),
            "percentiles": lossd.get("percentiles"),
            "var995": lossd.get("var995"),
            "es995": lossd.get("es995"),
            "scr995": lossd.get("scr995"),
            "seeds": lossd.get("seeds", []),
        }

    # ---- governance -----------------------------------------------------
    if gov:
        at = gov.get("audit_trail", [])
        integrity_ok, n_ok, n_bad = _verify_audit_integrity(gov)
        data["governance"] = {
            "audit_entries": len(at),
            "audit_integrity_ok": integrity_ok,  # COMPUTED: digest recomputation at build time
            "audit_verified": n_ok,
            "audit_failed": n_bad,
            "change_records": [
                {"record_id": r.get("record_id"), "title": r.get("title"),
                 "status": r.get("status"), "change_type": r.get("change_type"),
                 "created_at": r.get("created_at"), "phase": r.get("phase"),
                 "author": r.get("author"), "peer_reviewer": r.get("peer_reviewer"),
                 "standard_references": r.get("standard_references", []),
                 "sign_off_history": [
                     {"timestamp": s.get("timestamp"), "actor": s.get("actor"),
                      "status": s.get("status"), "comments": s.get("comments")}
                     for s in (r.get("sign_off_history") or [])
                 ]}
                for r in gov.get("change_records", [])
            ],
            "deployment_gates": _parse_deployment_gates(),
            "risk_register": [
                {"risk_id": r.get("risk_id"), "title": r.get("title"),
                 "overall_rating": r.get("overall_rating"),
                 "mitigation_status": r.get("mitigation_status"),
                 "category": r.get("category"), "owner": r.get("owner"),
                 "likelihood": r.get("likelihood"), "impact": r.get("impact"),
                 "description": r.get("description"),
                 "mitigation": r.get("mitigation"),
                 "related_standard": r.get("related_standard"),
                 "updated_at": r.get("updated_at")}
                for r in gov.get("risk_register", [])
            ],
        }
    return data


def render_html(data: Dict[str, Any]) -> str:
    with open(TEMPLATE, encoding="utf-8") as fh:
        tpl = fh.read()
    if DATA_TOKEN not in tpl:
        raise RuntimeError("data token not found in template")
    payload = json.dumps(data, ensure_ascii=False)
    return tpl.replace(DATA_TOKEN, payload)


def main() -> Dict[str, Any]:
    data = build_viewer_data()
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    html = render_html(data)
    with open(OUT_HTML, "w", encoding="utf-8") as fh:
        fh.write(html)
    print("sources:", ", ".join(data["meta"]["source_files"]) or "(none)")
    g = data.get("governance", {})
    print("verdicts:", len(data["verdicts"]),
          "| risks:", len(g.get("risk_register", [])),
          "| change records:", len(g.get("change_records", [])),
          "| gates:", len(g.get("deployment_gates", [])),
          "| audit integrity:", ("OK" if g.get("audit_integrity_ok") else "FAIL"),
          "({}/{} verified)".format(g.get("audit_verified"), g.get("audit_entries")),
          "| loss seeds:", len(data.get("loss", {}).get("seeds", [])))
    print("wrote:", os.path.relpath(OUT_JSON, REPO), "+", os.path.relpath(OUT_HTML, REPO),
          "({} bytes)".format(len(html)))
    return data


if __name__ == "__main__":
    main()
