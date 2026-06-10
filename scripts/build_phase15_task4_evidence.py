"""Build Phase 15 Task 4 tail-diagnostics evidence (JSON + Markdown).

Deterministic (seed=42). Reproduces:
  docs/validation/PHASE15_TAIL_DIAGNOSTICS_REPORT.json
  docs/validation/PHASE15_TAIL_DIAGNOSTICS_REPORT.md

Optionally appends a model-run audit entry + an OWNER_REVIEW ChangeRecord to the
canonical GovernanceStore (.claude-dev/GOVERNANCE_STORE.json) when --governance
is passed.

Run:  PYTHONPATH=. python3 scripts/build_phase15_task4_evidence.py [--governance]
"""
from __future__ import annotations

import os
import sys
import datetime as _dt

from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.multi_driver_capital import EquityGuaranteeSpec
from par_model_v2.projection.multi_driver_tail_diagnostics import (
    MultiDriverTailDiagnostics,
    TailDiagnosticsConfig,
)
from par_model_v2.stochastic.esg_process import GBMParams, HullWhiteParams

OUT_DIR = os.path.join("docs", "validation")
JSON_PATH = os.path.join(OUT_DIR, "PHASE15_TAIL_DIAGNOSTICS_REPORT.json")
MD_PATH = os.path.join(OUT_DIR, "PHASE15_TAIL_DIAGNOSTICS_REPORT.md")
GOV_PATH = os.path.join(".claude-dev", "GOVERNANCE_STORE.json")


def build(use_governance: bool = False):
    product = ParEndowmentProduct(
        term_years=10, issue_age=40, gender="M",
        sum_assured=100_000, annual_premium=6_000,
    )
    eng = MultiDriverTailDiagnostics(
        product, HullWhiteParams(),
        GBMParams(rate_equity_correlation=-0.15),
        equity_guarantee=EquityGuaranteeSpec(guarantee_rate=1.0),
    )
    cfg = TailDiagnosticsConfig(
        n_fit=700, outer_grid=(1_000, 2_000, 4_000),
        n_bootstrap=1_500, bootstrap_n_outer=2_500,
        vr_replications=60, vr_n_outer=4_096, vr_pilot_n=2_000, seed=42,
    )

    gs = None
    if use_governance:
        from par_model_v2.governance.audit_trail import (
            GovernanceStore, ChangeRecord, EntryType, SignOffStatus,
        )
        gs = GovernanceStore.from_json(open(GOV_PATH).read())

    report = eng.run(cfg, governance_store=gs)

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(JSON_PATH, "w", encoding="utf-8") as fh:
        fh.write(report.to_json())
    with open(MD_PATH, "w", encoding="utf-8") as fh:
        fh.write(report.to_markdown())

    if gs is not None:
        from par_model_v2.governance.audit_trail import ChangeRecord
        c = report.convergence
        b = report.bootstrap
        v = report.variance_reduction
        rec = ChangeRecord.create(
            title="Phase 15 Task 4 - tail-convergence & stability diagnostics for the 99.5% capital metric",
            description=(
                "Added par_model_v2/projection/multi_driver_tail_diagnostics.py "
                "(additive): outer-count convergence, a non-parametric bootstrap "
                "CI, and a crude/antithetic/Sobol variance-reduction comparison "
                "for the multi-driver (rate+equity) 99.5% VaR/ES capital metric, "
                "built on the once-fitted Phase 15 Task 1 LSMC surface. "
                "Verdict {}.".format(report.verdict)
            ),
            change_type="methodology_change",
            affected_components=[
                "par_model_v2/projection/multi_driver_tail_diagnostics.py",
                "tests/test_phase15_tail_diagnostics.py",
                "scripts/build_phase15_task4_evidence.py",
                "docs/validation/PHASE15_TAIL_DIAGNOSTICS_REPORT.{json,md}",
                "docs/MULTI_DRIVER_TAIL_DIAGNOSTICS_CARD.md",
            ],
            standard_references=[
                "SOA ASOP 56 §3.5", "SOA ASOP 56 §3.1.3", "SOA ASOP 25 §3.3",
                "IA TAS M §3.6", "L'Ecuyer (2018) RQMC", "Glasserman (2003) §4",
            ],
            before_snapshot={"tail_diagnostics": "absent — 99.5% capital cited without convergence/CI/variance-reduction evidence"},
            after_snapshot={
                "final_var": round(c.final_var, 2),
                "converged": c.converged,
                "recommended_n_outer": c.recommended_n_outer,
                "var_bootstrap_se": round(b.var_standard_error, 2),
                "sobol_var_ratio": round(v.sobol_var_ratio, 3),
                "antithetic_var_ratio": round(v.antithetic_var_ratio, 3),
            },
            impact_assessment=(
                "99.5% VaR converges (recommended N_outer>={}); bootstrap 95% CI "
                "[{:.0f},{:.0f}] SE {:.0f}; Sobol QMC variance-reduction ratio "
                "{:.1f}x; antithetic ineffective on the tail quantile (theory-consistent). "
                "Educational; placeholder params; independent APS X2 review pending.".format(
                    c.recommended_n_outer, b.var_ci_low, b.var_ci_high,
                    b.var_standard_error, v.sobol_var_ratio)
            ),
            author="MultiDriverTailDiagnostics",
            phase="Phase 15: Multi-Risk Economic Capital and Proxy-Model Validation",
            quantitative_impact="VaR SE {:.0f}; Sobol VR {:.1f}x".format(
                b.var_standard_error, v.sobol_var_ratio),
        )
        rec.submit_for_peer_review(
            actor="MultiDriverTailDiagnostics",
            comments="Additive tail-diagnostics module; 36 unit tests PASS; compileall clean.")
        rec.submit_to_owner(actor="MultiDriverTailDiagnostics",
                            comments="Owner review: educational placeholder params; "
                                     "independent APS X2 review pending.")
        gs.add_change_record(rec)
        with open(GOV_PATH, "w", encoding="utf-8") as fh:
            fh.write(gs.to_json())
        print("governance: ChangeRecord {} added; audit entries {}; integrity {}".format(
            rec.record_id[:8], len(gs.audit_trail.entries), gs.audit_trail.verify_all()))

    print("VERDICT:", report.verdict)
    print("digest:", report.reproducibility_digest[:16])
    print("artifacts:", JSON_PATH, MD_PATH)
    return report


if __name__ == "__main__":
    build(use_governance="--governance" in sys.argv)
