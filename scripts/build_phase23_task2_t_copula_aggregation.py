#!/usr/bin/env python3
"""Phase 23 Task 2 -- Student-t copula aggregation with tail-matched df.

Staged build (wall-clock-limited shells; each stage < 45 s):

  PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase23_task2_t_copula_aggregation.py --stage losses
  PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase23_task2_t_copula_aggregation.py --stage aggregate
  PYTHONPATH=/var/tmp/pylibs:. python3 scripts/build_phase23_task2_t_copula_aggregation.py --stage governance

Stage `losses` reuses the Phase 22 Task 4 calibrated aggregation primitives
(staged CRN slices in /var/tmp/p22t4_stage, bit-identical reuse) to realise
the seven-driver standalone capital-loss vectors + nested / var-covar /
gaussian benchmarks, and persists them to /var/tmp/p23t2_stage/losses.npz.
Stage `aggregate` runs the TailMatchedTCopulaAggregator and writes the
evidence report + card.  Stage `governance` (idempotent) refreshes MR-010 and
opens the methodology_change ChangeRecord at OWNER_REVIEW.
"""
from __future__ import annotations

import argparse
import importlib.util
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
)
from par_model_v2.projection.t_copula_tail_matched_aggregation import (
    TailMatchedTCopulaAggregator,
    TCopulaAggregationConfig,
    t_copula_aggregation_use_restrictions,
)

PHASE = "Phase 23: Tail-Dependence Upgrade + Management Actions"
ACTOR = "AutomatedModelDev_Phase23"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
OUT_DIR = Path("docs/validation")
JSON_PATH = OUT_DIR / "PHASE23_TASK2_T_COPULA_AGGREGATION_REPORT.json"
MD_PATH = OUT_DIR / "PHASE23_TASK2_T_COPULA_AGGREGATION_REPORT.md"
CARD_PATH = Path("docs/T_COPULA_AGGREGATION_CARD.md")
STAGE_DIR = Path("/var/tmp/p23t2_stage")
LOSSES_PATH = STAGE_DIR / "losses.npz"
P22T4_REPORT = OUT_DIR / "PHASE22_TASK4_AGGREGATION_REPORT.json"

DRIVERS = ("rate", "equity", "credit", "lapse", "mortality", "fx", "liquidity")
SEED = 20260607
N_SIM = 200_000
THRESHOLDS = (0.80, 0.85, 0.90)

CHANGE_TITLE = (
    "Phase 23 Task 2 - Student-t copula aggregation with df calibrated by "
    "tail-dependence matching"
)

AFFECTED_COMPONENTS = [
    "par_model_v2/projection/t_copula_tail_matched_aggregation.py",
    "par_model_v2/projection/tail_dependence.py",
    "tests/test_phase23_task2_t_copula.py",
    "scripts/build_phase23_task2_t_copula_aggregation.py",
    "docs/T_COPULA_AGGREGATION_CARD.md",
    "docs/validation/PHASE23_TASK2_T_COPULA_AGGREGATION_REPORT.{json,md}",
]

STANDARD_REFERENCES = [
    "SOA ASOP 56 section 3.5",
    "SOA ASOP 25 section 3.3",
    "IA TAS M section 3.6",
    "Solvency II Delegated Regulation Article 234",
    "IFoA Life Aggregation & Simulation working party",
    "Demarta-McNeil 2005; McNeil-Frey-Embrechts 2015 ch.7",
]


def _load_p22t4_module():
    spec = importlib.util.spec_from_file_location(
        "build_phase22_task4_aggregation",
        Path("scripts/build_phase22_task4_aggregation.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def stage_losses() -> int:
    """Realise the seven-driver loss vectors via the Phase 22 Task 4 primitives."""
    b = _load_p22t4_module()
    pre = b._assemble_precomputed()
    agg = b._calibrated_aggregator()
    rep = agg.run_7d(config=b._cfg(), precomputed=pre, run_tail_diagnostics=False)
    d = rep.to_dict()
    loss = agg.last_loss_vectors_7d
    STAGE_DIR.mkdir(parents=True, exist_ok=True)
    np.savez(
        LOSSES_PATH,
        nested_scr=np.array([d["nested_scr"]]),
        var_covar_scr=np.array([d["var_covar_scr"]]),
        archived_gaussian_scr=np.array([d["copula_scr"]]),
        archived_gaussian_rel=np.array([d["copula_vs_nested_rel_error"]]),
        full=loss["full"],
        **{k: loss[k] for k in DRIVERS},
    )
    # cross-check against the archived Phase 22 Task 4 report
    arch = json.loads(P22T4_REPORT.read_text(encoding="utf-8"))["aggregation"]
    same = (abs(arch["nested_scr"] - d["nested_scr"]) < 1e-6
            and abs(arch["var_covar_scr"] - d["var_covar_scr"]) < 1e-6)
    print("stage losses done: n_obs={}, nested={:.1f}, var_covar={:.1f}, "
          "archived-report match={}".format(
              len(loss["rate"]), d["nested_scr"], d["var_covar_scr"], same))
    return 0 if same else 1


def _aggregate():
    z = np.load(LOSSES_PATH)
    aggr = TailMatchedTCopulaAggregator(
        loss_vectors=[z[k] for k in DRIVERS],
        driver_names=list(DRIVERS),
        nested_scr=float(z["nested_scr"][0]),
        var_covar_scr=float(z["var_covar_scr"][0]),
    )
    cfg = TCopulaAggregationConfig(thresholds=THRESHOLDS, n_sim=N_SIM, seed=SEED)
    rep = aggr.run(cfg)
    return rep, float(z["archived_gaussian_scr"][0]), float(z["archived_gaussian_rel"][0])


def _markdown(r: dict, arch_g_scr: float, arch_g_rel: float) -> str:
    rows = "\n".join(
        "| {threshold:.2f} | {expected_tail_obs:.0f} | {pooled_df:.2f} | "
        "{capped_share:.0%} | {mean_offdiag_lambda:.3f} | {max_offdiag_lambda:.3f} |".format(**s)
        for s in r["threshold_sensitivity"]
    )
    return f"""# Phase 23 Task 2 -- Tail-Matched Student-t Copula Aggregation

**Verdict: {r['verdict']}** (gate: {r['gate']})

EDUCATIONAL ONLY. Drivers: {', '.join(r['drivers'])} (n_obs={r['n_obs']}).

## Benchmarks (99.5% 1y SCR)

| Aggregation | SCR | rel err vs nested |
|---|---|---|
| Nested ground truth | {r['nested_scr']:.1f} | -- |
| Var-covar (ESG factor) | {r['var_covar_scr']:.1f} | {r['var_covar_rel_error_vs_nested']:.1%} (MR-010) |
| Gaussian copula (AIC incumbent, same-seed rerun) | {r['gaussian_scr']:.1f} | {r['gaussian_rel_error_vs_nested']:.1%} |
| Gaussian copula (archived Phase 22 Task 4) | {arch_g_scr:.1f} | {arch_g_rel:.1%} |
| **t(df={r['df_matched']:.2f}) tail-matched** | **{r['t_matched_scr']:.1f}** | **{r['t_matched_rel_error_vs_nested']:.1%}** |

## Tail-dependence matching (>=3 thresholds; pooled MEDIAN df)

| q | E[tail obs] | pooled df | capped share | mean lambda_U | max lambda_U |
|---|---|---|---|---|---|
{rows}

Matched df = **{r['df_matched']:.2f}** (median across thresholds; capped-pair share {r['df_matched_capped_share']:.0%}).

## Disclosures

{chr(10).join('- ' + n for n in r['notes'])}

Digest `{r['reproducibility_digest'][:16]}`; run `{r['run_id']}`; config seed {r['config']['seed']}, n_sim {r['config']['n_sim']}.

Standards: {'; '.join(r['standards'])}.
"""


def stage_aggregate() -> int:
    rep, ag, arel = _aggregate()
    d = rep.to_dict()
    out = {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": PHASE,
        "task": CHANGE_TITLE,
        "aggregation": d,
        "archived_gaussian_scr_phase22_task4": ag,
        "archived_gaussian_rel_error_phase22_task4": arel,
        "affected_components": AFFECTED_COMPONENTS,
        "standard_references": STANDARD_REFERENCES,
        "use_restrictions": t_copula_aggregation_use_restrictions(),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    md = _markdown(d, ag, arel)
    out["markdown"] = md
    JSON_PATH.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    MD_PATH.write_text(md, encoding="utf-8")
    CARD_PATH.write_text(_card(d, ag, arel), encoding="utf-8")
    print("verdict={} df_matched={:.2f} t_scr={:.1f} (rel {:.2%}) gauss_scr={:.1f} "
          "(rel {:.2%}) nested={:.1f}".format(
              d["verdict"], d["df_matched"], d["t_matched_scr"],
              d["t_matched_rel_error_vs_nested"], d["gaussian_scr"],
              d["gaussian_rel_error_vs_nested"], d["nested_scr"]))
    print("report:", JSON_PATH)
    return 0 if d["verdict"] == "PASS" else 1


def _card(d: dict, ag: float, arel: float) -> str:
    return f"""# Model Card -- Tail-Matched t-Copula Aggregation (Phase 23 Task 2)

**Classification: EDUCATIONAL.** Replaces AIC-only copula selection with a
Student-t copula whose df ({d['df_matched']:.2f}) is calibrated by matching the
empirical pairwise upper-tail dependence of the REALISED seven-driver
standalone capital losses (Demarta-McNeil closed-form inversion; pooled
MEDIAN pairwise df; median across thresholds {d['config']['thresholds']}).

| Metric | Value |
|---|---|
| Nested SCR (truth) | {d['nested_scr']:.1f} |
| Var-covar SCR | {d['var_covar_scr']:.1f} ({d['var_covar_rel_error_vs_nested']:.1%} under; MR-010) |
| Gaussian copula SCR (same-seed) | {d['gaussian_scr']:.1f} ({d['gaussian_rel_error_vs_nested']:.1%}) |
| t(df-matched) SCR | {d['t_matched_scr']:.1f} ({d['t_matched_rel_error_vs_nested']:.1%}) |
| Verdict | {d['verdict']} |

**Fixed gate (recorded Phase 23 Task 1, before benchmark errors were seen):**
{d['gate']}.

**Limitations:** finite-threshold lambda_U estimator is noisy at n={d['n_obs']}
(thresholds 0.80/0.85/0.90, not the large-n 0.97+ of the design pre-study);
single pooled df (exchangeable); empirical marginals bounded by realised
support; educational-proxy data; APS X2 independent review pending.

**Use restrictions:** see `t_copula_aggregation_use_restrictions()`.
Evidence: `docs/validation/PHASE23_TASK2_T_COPULA_AGGREGATION_REPORT.json`.
"""


def _has_change_record(store: GovernanceStore) -> bool:
    return any(r.title == CHANGE_TITLE for r in store.change_records)


def stage_governance() -> int:
    rep = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    d = rep["aggregation"]
    store = GovernanceStore.from_json(GOV_PATH.read_text(encoding="utf-8"))

    if _has_change_record(store):
        rec = next(r for r in store.change_records if r.title == CHANGE_TITLE)
        print("already applied:", rec.record_id)
        print("audit integrity:", store.audit_trail.verify_all())
        return 0

    # MR-010 refresh: tail-dependence-aware aggregation now implemented.
    mr010_action = "missing"
    try:
        risk = store.risk_register.get("MR-010")
        risk.update_mitigation(
            MitigationStatus.MITIGATED,
            notes=(
                "Phase 23 Task 2 upgraded the governed copula mitigation from "
                "AIC-only selection to TAIL-DEPENDENCE-MATCHED Student-t "
                "aggregation (df={df:.2f} by Demarta-McNeil inversion on the "
                "realised seven-driver losses; thresholds {thr}; capped share "
                "{cap:.0%}): t(df) SCR {tscr:.0f} vs nested {nest:.0f} (rel "
                "{trel:.1%}) vs gaussian {gscr:.0f} (rel {grel:.1%}); var-covar "
                "still understates by {vc:.1%}. Dependence INPUT remains "
                "realised losses, per the Phase 18 Task 1 root-cause finding; "
                "the tail-matching upgrade makes the Art. 234 empirical "
                "justification explicit at the TAIL, not the body."
            ).format(
                df=d["df_matched"], thr=list(d["config"]["thresholds"]),
                cap=d["df_matched_capped_share"], tscr=d["t_matched_scr"],
                nest=d["nested_scr"], trel=d["t_matched_rel_error_vs_nested"],
                gscr=d["gaussian_scr"], grel=d["gaussian_rel_error_vs_nested"],
                vc=d["var_covar_rel_error_vs_nested"],
            ),
        )
        mr010_action = "refreshed"
    except KeyError:
        pass

    rec = ChangeRecord.create(
        title=CHANGE_TITLE,
        description=(
            "Implemented the Phase 23 Task 1 design: Student-t copula "
            "aggregation of the realised seven-driver standalone capital "
            "losses with df calibrated by tail-dependence matching "
            "(empirical pairwise lambda_U at >=3 thresholds -> Kendall-tau "
            "rho -> closed-form df inversion -> pooled MEDIAN df, median "
            "across thresholds). Benchmarked t(df_matched) vs the gaussian "
            "AIC incumbent vs nested truth under the FIXED pre-registered "
            "gate. New additive module t_copula_tail_matched_aggregation.py; "
            "governed CopulaRiskAggregator untouched."
        ),
        change_type="methodology_change",
        affected_components=AFFECTED_COMPONENTS,
        standard_references=STANDARD_REFERENCES,
        before_snapshot={
            "aggregation": "AIC-selected copula (gaussian incumbent)",
            "gaussian_scr_archived": rep["archived_gaussian_scr_phase22_task4"],
            "tail_dependence_calibration": "none (df pinned at MLE grid cap)",
        },
        after_snapshot={
            "df_matched": d["df_matched"],
            "df_matched_capped_share": d["df_matched_capped_share"],
            "t_matched_scr": d["t_matched_scr"],
            "t_matched_rel_error_vs_nested": d["t_matched_rel_error_vs_nested"],
            "gaussian_scr_same_seed": d["gaussian_scr"],
            "gaussian_rel_error_vs_nested": d["gaussian_rel_error_vs_nested"],
            "nested_scr": d["nested_scr"],
            "verdict": d["verdict"],
            "reproducibility_digest": d["reproducibility_digest"],
        },
        impact_assessment=(
            "Additive methodology upgrade to the MR-010 mitigation: the "
            "aggregation dependence is now empirically justified at the tail "
            "(Solvency II Art. 234) instead of by body-dominated AIC. No "
            "change to standalone SCRs, var-covar, nested truth, or any "
            "upstream driver module."
        ),
        quantitative_impact=(
            "t(df={df:.2f}) SCR {tscr:.1f} (rel err {trel:.2%} vs nested "
            "{nest:.1f}); gaussian same-seed {gscr:.1f} ({grel:.2%}); "
            "var-covar understatement {vc:.1%}; seed {seed}, n_sim {ns}, "
            "n_obs {no}."
        ).format(
            df=d["df_matched"], tscr=d["t_matched_scr"],
            trel=d["t_matched_rel_error_vs_nested"], nest=d["nested_scr"],
            gscr=d["gaussian_scr"], grel=d["gaussian_rel_error_vs_nested"],
            vc=d["var_covar_rel_error_vs_nested"], seed=d["config"]["seed"],
            ns=d["config"]["n_sim"], no=d["n_obs"],
        ),
        author=ACTOR,
        phase=PHASE,
        peer_reviewer="APS_X2_Independent_Reviewer",
        assumption_owner="ChiefActuary",
    )
    rec.submit_for_peer_review(
        ACTOR,
        "Tail-matched t-copula aggregation with pre-registered gate, threshold "
        "sensitivity, capped-share disclosure, and same-seed gaussian baseline.",
    )
    rec.submit_to_owner(
        ACTOR,
        "Owner review requested. Production sign-off withheld pending "
        "credentialled data, management-action modelling (Task 3), and "
        "independent APS X2 review.",
    )
    store.add_change_record(rec)

    entry = AuditEntry.model_run(
        actor=ACTOR,
        phase=PHASE,
        run_id=d["run_id"],
        scenario_count=d["config"]["n_sim"],
        duration_seconds=d["duration_seconds"],
        outcome=d["verdict"],
        files_changed=AFFECTED_COMPONENTS,
        test_summary=(
            "t(df={:.2f}) SCR {:.1f} rel {:.2%} vs nested {:.1f}; gaussian "
            "{:.1f} rel {:.2%}; verdict {}".format(
                d["df_matched"], d["t_matched_scr"],
                d["t_matched_rel_error_vs_nested"], d["nested_scr"],
                d["gaussian_scr"], d["gaussian_rel_error_vs_nested"],
                d["verdict"],
            )
        ),
    )
    store.audit_trail.append(entry)

    ok = store.audit_trail.verify_all()
    GOV_PATH.write_text(store.to_json() + "\n", encoding="utf-8")

    # reflect governance into the report
    rep["change_record_id"] = rec.record_id
    rep["change_record_status"] = (
        rec.status.value if hasattr(rec.status, "value") else str(rec.status))
    rep["mr010_action"] = mr010_action
    rep["mr010_status"] = "MITIGATED"
    rep["audit_integrity_ok"] = ok
    rep["change_records_total"] = len(store.change_records)
    JSON_PATH.write_text(json.dumps(rep, indent=2) + "\n", encoding="utf-8")

    print("ChangeRecord {} ({}); MR-010 {}; audit entries {}; verify_all {}".format(
        rec.record_id, rep["change_record_status"], mr010_action,
        len(store.audit_trail.entries), ok))
    return 0 if ok else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["losses", "aggregate", "governance"], required=True)
    a = ap.parse_args()
    sys.exit({"losses": stage_losses, "aggregate": stage_aggregate,
              "governance": stage_governance}[a.stage]())
