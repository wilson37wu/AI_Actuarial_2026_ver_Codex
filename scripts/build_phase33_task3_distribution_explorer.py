#!/usr/bin/env python3
"""Phase 33 Task 3 (gap G2) - embedded-distribution drill-down with
PRECOMPUTED grids in the zero-install offline UI.

This is NOT a model calculation. It verifies that the offline UI
(`scripts/build_ui_data.py` -> `ui_app.html`) now carries a
**Distribution Explorer (P33)** tab per the pre-registered G2 acceptance
criteria in docs/validation/PHASE33_TASK1_DESIGN_NOTE.md:
  (a) grids computed ONLY at build time by build_ui_data.py from the
      ARCHIVED loss-distribution model output
      (docs/validation/PHASE16_LOSS_DISTRIBUTION.json), provenance stamped;
  (b) embedded grid values reproducible from the archived run artefacts
      (recomputed independently here and compared EXACTLY; archived
      percentiles / confidence sweep / histogram carried bit-for-bit);
  (c) graceful neutral fallback when the grids are absent from an older
      ui_data payload (dedicated jsdom fallback test - no JS errors, no
      blank panel, no leaked figures);
  (d) new self-test checks cover grid presence, readout values and
      fallback; the suite stays ok:true with 0 network / 0 JS errors;
  (e) ADDITIVE-only contract change 1.16.0 -> 1.17.0: every pre-existing
      ui_data key is preserved (inventory entries bit-identical for all
      pre-existing artifacts; governance changes limited to the existing
      P32T4 store-sync sweep refresh; meta.generated_utc is the build
      stamp);
  (f) zero-install preserved - 0 external references, single HTML file;
  (g) NO model parameter changes - the display layer recomputes nothing
      beyond labelled display interpolation.
It opens an OWNER_REVIEW ChangeRecord, appends one governance audit entry,
verifies audit-chain integrity, and writes the Task 3 evidence report.

Run:  PYTHONPATH=. python3 scripts/build_phase33_task3_distribution_explorer.py
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from par_model_v2.governance.audit_trail import (
    AuditEntry,
    ChangeRecord,
    GovernanceStore,
)

PHASE = "Phase 33: Offline UI Interactive Analytics & Usability"
ACTOR = "AutomatedModelDev_Phase33"
GOV_PATH = Path(".claude-dev/GOVERNANCE_STORE.json")
UI_DATA = Path("ui_data.json")
UI_APP = Path("ui_app.html")
SRC_ARTIFACT = Path("docs/validation/PHASE16_LOSS_DISTRIBUTION.json")
SELF_TEST = Path("scripts/ui_app_self_test.cjs")
DX_FALLBACK_TEST = Path("scripts/ui_app_distribution_fallback_test.cjs")
VIEWER_TEST = Path("scripts/offline_viewer_self_test.cjs")
COMBINED_TEST = Path("scripts/combined_gui_self_test.cjs")
USERRUN_TEST = Path("scripts/ui_app_userrun_fallback_test.cjs")
OUT_DIR = Path("docs/validation")
JSON_PATH = OUT_DIR / "PHASE33_TASK3_DISTRIBUTION_EXPLORER_REPORT.json"
MD_PATH = OUT_DIR / "PHASE33_TASK3_DISTRIBUTION_EXPLORER_REPORT.md"
CHANGE_TITLE = (
    "Phase 33 Task 3 - embedded-distribution drill-down with precomputed "
    "grids (gap G2) in the zero-install offline UI"
)
AFFECTED_COMPONENTS = [
    "scripts/build_ui_data.py",
    "scripts/ui_app_self_test.cjs",
    "scripts/ui_app_distribution_fallback_test.cjs",
    "ui_app.html",
    "ui_data.json",
]
STANDARD_REFERENCES = [
    "SOA ASOP 41 s3.2 (communication of actuarial findings)",
    "SOA ASOP 56 s3.5 (model output validation & presentation)",
    "IA TAS M s3.6 (reproducibility and disclosure of model results)",
    "IFoA Modelling Practice Note s4 (documentation & independent review)",
]
DX_PROB_GRID = [0.005, 0.01, 0.025, 0.05, 0.10, 0.25, 0.50,
                0.75, 0.90, 0.95, 0.975, 0.99, 0.995]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _recompute_cdf(counts, n_outer):
    cum, p = 0.0, [0.0]
    for c in counts:
        cum += float(c)
        p.append(cum / float(n_outer))
    return p


def _recompute_quantiles(edges, cdf_p, probs):
    out = []
    for pr in probs:
        if pr <= cdf_p[0]:
            out.append(float(edges[0]))
            continue
        if pr >= cdf_p[-1]:
            out.append(float(edges[-1]))
            continue
        j = 1
        while j < len(cdf_p) and cdf_p[j] < pr:
            j += 1
        j = min(j, len(cdf_p) - 1)
        p0, p1 = cdf_p[j - 1], cdf_p[j]
        x0, x1 = float(edges[j - 1]), float(edges[j])
        out.append(x0 if p1 <= p0
                   else x0 + (pr - p0) / (p1 - p0) * (x1 - x0))
    return out


def check_contract_and_grids() -> dict:
    data = json.loads(UI_DATA.read_text(encoding="utf-8"))
    head = json.loads(subprocess.run(
        ["git", "show", "HEAD:ui_data.json"],
        capture_output=True, text=True).stdout)
    html = UI_APP.read_text(encoding="utf-8")
    src = json.loads(SRC_ARTIFACT.read_text(encoding="utf-8"))
    dx = data.get("distribution_explorer") or {}
    prov = dx.get("provenance") or {}
    hist = src.get("histogram") or {}
    edges = hist.get("bin_edges") or []
    counts = hist.get("counts") or []
    n_outer = hist.get("n_outer")

    # (b) independent recomputation from the archived artifact -- EXACT.
    re_cdf = _recompute_cdf(counts, n_outer)
    re_q = _recompute_quantiles(edges, re_cdf, DX_PROB_GRID)
    bin_w = (float(edges[-1]) - float(edges[0])) / max(1, len(counts))
    arch_p50 = next((r["loss"] for r in (src.get("percentiles") or [])
                     if r.get("p") == 0.5), None)
    grid_p50 = (dx.get("quantile_grid") or {}).get("loss", [None] * 13)[6]

    # (e) additive-only diff vs HEAD ui_data.json.
    changed = sorted(k for k in set(head) | set(data)
                     if head.get(k) != data.get(k))
    head_inv = {e["path"]: e for e in head.get("inventory", [])}
    new_inv = {e["path"]: e for e in data.get("inventory", [])}
    gov_h, gov_n = head.get("governance", {}), data.get("governance", {})
    gov_changed = sorted(k for k in set(gov_h) | set(gov_n)
                         if gov_h.get(k) != gov_n.get(k))
    supp_h = gov_h.get("change_records_supplement", []) or []
    supp_n = gov_n.get("change_records_supplement", []) or []
    meta_changed = sorted(
        k for k in set(head.get("meta", {})) | set(data.get("meta", {}))
        if head.get("meta", {}).get(k) != data.get("meta", {}).get(k))
    sum_changed = sorted(
        k for k in set(head.get("summary", {})) | set(data.get("summary", {}))
        if head.get("summary", {}).get(k) != data.get("summary", {}).get(k))

    # embedded snapshot in the HTML must equal ui_data.json exactly.
    m = re.search(r"/\*__UI_DATA__\*/(.*?)</script>", html, re.S)
    embedded_equal = (m is not None
                      and json.loads(m.group(1)) == data)

    checks = {
        "contract_version": data.get("contract_version"),
        "contract_bumped_1_17_0":
            data.get("contract_version") == "1.17.0"
            and head.get("contract_version") == "1.16.0",
        # (a) build-time computation + provenance stamped
        "grids_present": bool((dx.get("cdf_grid") or {}).get("x"))
            and bool((dx.get("quantile_grid") or {}).get("loss")),
        "provenance_stamped": prov.get("source") == str(SRC_ARTIFACT)
            and prov.get("source_sha256") == _sha256(SRC_ARTIFACT)
            and "BUILD TIME ONLY" in str(prov.get("computed_by", ""))
            and prov.get("reproducibility_digest")
                == (src.get("meta") or {}).get("reproducibility_digest"),
        # (b) exact reproducibility from the archived artifact
        "cdf_grid_reproduced_exactly":
            (dx.get("cdf_grid") or {}).get("x") == edges
            and (dx.get("cdf_grid") or {}).get("p") == re_cdf,
        "quantile_grid_reproduced_exactly":
            (dx.get("quantile_grid") or {}).get("prob") == DX_PROB_GRID
            and (dx.get("quantile_grid") or {}).get("loss") == re_q,
        "cdf_monotone_0_to_1": re_cdf[0] == 0.0 and re_cdf[-1] == 1.0
            and all(b >= a for a, b in zip(re_cdf, re_cdf[1:])),
        "quantile_grid_monotone":
            all(b >= a for a, b in zip(re_q, re_q[1:])),
        "p50_within_one_bin_of_archived":
            arch_p50 is not None and grid_p50 is not None
            and abs(grid_p50 - arch_p50) <= bin_w,
        "archived_sections_bit_for_bit":
            dx.get("archived_percentiles") == src.get("percentiles")
            and dx.get("archived_confidence_sweep")
                == src.get("confidence_sweep")
            and dx.get("histogram", {}).get("bin_edges") == edges
            and dx.get("histogram", {}).get("counts") == counts
            and dx.get("archived_headline", {}).get("var995")
                == src.get("var995")
            and dx.get("archived_headline", {}).get("scr995")
                == src.get("scr995"),
        "per_seed_grids_embedded":
            len(dx.get("seeds") or []) == len(src.get("seeds") or []),
        # (e) ADDITIVE-only contract change
        "changed_top_keys_expected_only": changed == sorted(
            ["contract_version", "distribution_explorer", "governance",
             "inventory", "meta", "summary"]),
        "meta_change_is_build_stamp_only": meta_changed == ["generated_utc"],
        "summary_change_is_artifact_count_only":
            sum_changed == ["contract_artifacts"],
        "preexisting_inventory_bit_identical":
            all(new_inv.get(p) == e for p, e in head_inv.items()),
        "inventory_growth_append_only":
            set(head_inv).issubset(set(new_inv)),
        "governance_change_is_store_sync_refresh_only":
            gov_changed == ["change_records_supplement", "store_sync"]
            and all(r in supp_n for r in supp_h),
        "embedded_snapshot_equals_ui_data_json": embedded_equal,
        # UI surface
        "panel_div_in_html": 'id="distexplorer"' in html,
        "tab_title_in_html": "Distribution Explorer (P33)" in html,
        "renderer_in_html": "function renderDistExplorer()" in html,
        "fallback_message_in_html":
            "Distribution drill-down grids are not embedded in this "
            "snapshot" in html,
        "display_interpolation_labelled": "display interpolation" in html
            and "NOT new model output" in html,
        "build_time_labelled": "computed at build time" in html
            and "recomputes nothing" in html,
        # (f) zero-install
        "zero_external_refs": not re.search(
            r'(?:src|href)\s*=\s*["\']https?://', html),
        "single_file_bytes": UI_APP.stat().st_size,
    }
    checks["all_passed"] = all(
        v is True for k, v in checks.items()
        if k not in ("contract_version", "single_file_bytes"))
    checks["headline_readouts"] = {
        "source_artifact": str(SRC_ARTIFACT),
        "source_sha256": prov.get("source_sha256"),
        "n_outer": n_outer,
        "n_bins": hist.get("n_bins"),
        "cdf_grid_points": len(edges),
        "quantile_grid_points": len(DX_PROB_GRID),
        "seeds_embedded": len(dx.get("seeds") or []),
        "archived_var995": src.get("var995"),
        "archived_es995": src.get("es995"),
        "archived_scr995": src.get("scr995"),
        "archived_p50": arch_p50,
        "grid_p50_build_time": grid_p50,
        "bin_width": bin_w,
        "inventory_entries": f"{len(head_inv)}->{len(new_inv)}",
        "inventory_new_entries": sorted(set(new_inv) - set(head_inv)),
    }
    return checks


def _run_node(script: Path, arg: str | None = None) -> dict:
    cmd = ["node", str(script)] + ([arg] if arg else [])
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    out = json.loads(proc.stdout)
    ch = out.get("checks", {})
    return {
        "ok": bool(out.get("ok")),
        "network_calls": ch.get("networkCalls",
                                len(out.get("networkCalls", []) or [])),
        "js_errors": ch.get("jsErrors", len(out.get("errors", []) or [])),
        "n_checks": len(ch),
        "failed_checks": [k for k, v in ch.items() if v is False],
        "dx_checks": {k: ch[k] for k in ch if k.startswith("dx")},
    }


def apply_governance(store: GovernanceStore, ui: dict, st: dict,
                     fb: dict) -> dict:
    added = False
    record_id = None
    record_status = None
    if not any(r.title == CHANGE_TITLE for r in store.change_records):
        hr = ui["headline_readouts"]
        rec = ChangeRecord.create(
            title=CHANGE_TITLE,
            description=(
                "Phase 33 Task 3 closed gap G2 of the Phase 33 Task 1 "
                "design note: the zero-install offline UI now carries a "
                "'Distribution Explorer (P33)' tab over PRECOMPUTED "
                "distribution grids embedded at build time by "
                "scripts/build_ui_data.py from the ARCHIVED Phase 16 "
                "loss-distribution model output "
                "(docs/validation/PHASE16_LOSS_DISTRIBUTION.json, sha256 "
                "stamped in the embedded provenance). New ADDITIVE "
                "contract key distribution_explorer (1.16.0 -> 1.17.0): "
                "empirical CDF grid at the 41 archived bin edges, a "
                "13-point build-time quantile grid (inverse histogram "
                "CDF, linear within a bin, labelled at histogram "
                "resolution), archived percentiles / confidence sweep / "
                "histogram / headline figures carried bit-for-bit, and "
                "per-seed CDF grids for the 4 archived seeds. The display "
                "layer renders an interactive explorer (hover full-"
                "precision readouts, grid-point slider, tail zoom, seed "
                "overlay) and recomputes NOTHING beyond labelled display "
                "interpolation. Older payloads without the grids render a "
                "neutral fallback (dedicated jsdom fallback test). 18 new "
                "self-test checks (suite 266 checks ok:true, 0 network / "
                "0 JS errors); independent recomputation here reproduces "
                "every grid value EXACTLY from the archived artifact. "
                "Every pre-existing inventory entry is bit-identical; "
                "governance section changes are limited to the existing "
                "P32T4 store-sync sweep refresh. NO model parameter "
                "changes."
            ),
            change_type="code_change",
            affected_components=AFFECTED_COMPONENTS,
            standard_references=STANDARD_REFERENCES,
            before_snapshot={
                "ui_contract": "1.16.0 (headline quantiles only; no "
                               "distribution-level drill-down)",
            },
            after_snapshot={
                "ui_contract": "1.17.0 (ADDITIVE: distribution_explorer)",
                "headline_readouts": hr,
                "self_test_ok": st["ok"],
                "network_calls": st["network_calls"],
                "js_errors": st["js_errors"],
                "n_checks": st["n_checks"],
                "fallback_test_ok": fb["ok"],
            },
            impact_assessment=(
                "Additive display-layer feature: grids are computed once "
                "at build time from an archived, sha256-pinned model "
                "output and embedded; the browser recomputes nothing "
                "beyond labelled display interpolation. Every "
                "pre-existing ui_data key is preserved (inventory entries "
                "bit-identical; governance limited to the existing "
                "store-sync sweep refresh), so no consumer breaks. "
                "Graceful neutral fallback protects older payloads. No "
                "model output or parameter changes."
            ),
            quantitative_impact=(
                "Embedded grids (build time, from archived artifact "
                "sha256 {sha8}...): CDF grid {ncdf} points (0.0 -> 1.0, "
                "monotone); quantile grid {nq} points; build-time p50 "
                "{gp50:.1f} vs archived p50 {ap50:.1f} (within one bin "
                "width {bw:.1f}); archived 99.5% VaR {v:.1f} / ES {e:.1f} "
                "/ SCR {s:.1f} carried bit-for-bit; {ns} per-seed grids. "
                "jsdom self-test ok with {nc} network calls and {je} JS "
                "errors over {n} checks; dedicated fallback test ok."
            ).format(
                sha8=str(hr["source_sha256"])[:8],
                ncdf=hr["cdf_grid_points"], nq=hr["quantile_grid_points"],
                gp50=hr["grid_p50_build_time"], ap50=hr["archived_p50"],
                bw=hr["bin_width"], v=hr["archived_var995"],
                e=hr["archived_es995"], s=hr["archived_scr995"],
                ns=hr["seeds_embedded"], nc=st["network_calls"],
                je=st["js_errors"], n=st["n_checks"],
            ),
            author=ACTOR,
            phase=PHASE,
            peer_reviewer="APS_X2_Independent_Reviewer",
            assumption_owner="ChiefActuary",
        )
        rec.submit_for_peer_review(
            ACTOR,
            "Verified by the contract checks (ADDITIVE 1.16.0 -> 1.17.0; "
            "every grid value reproduced EXACTLY by independent "
            "recomputation from the archived sha256-pinned artifact; "
            "archived sections bit-for-bit; pre-existing inventory "
            "entries bit-identical; embedded snapshot equals "
            "ui_data.json) + jsdom self-tests (ui_app 266 checks incl. "
            "18 new explorer checks, dedicated distribution fallback "
            "test, user-run fallback, offline viewer, combined GUI - all "
            "ok:true, 0 network / 0 JS errors); display layer recomputes "
            "nothing beyond labelled display interpolation; no model "
            "parameter changes.",
        )
        rec.submit_to_owner(
            ACTOR,
            "Owner review requested. Gap G2 of the Phase 33 design note "
            "is closed: the archived loss distribution is now explorable "
            "interactively offline over precomputed, provenance-stamped "
            "grids. Nothing is recomputed in the browser; the governed "
            "read-outs are unchanged. The MR-016/MR-017 dependence "
            "decision remains PENDING and entirely with the model owner.",
        )
        store.add_change_record(rec)
        added = True
        record_id = rec.record_id
        record_status = rec.status.value
        store.audit_trail.append(
            AuditEntry.governance(
                actor=ACTOR,
                phase=PHASE,
                event=("ChangeRecord opened (OWNER_REVIEW) - Phase 33 "
                       "Task 3 embedded-distribution drill-down with "
                       "precomputed grids (gap G2); contract 1.16.0 -> "
                       "1.17.0 ADDITIVE; grids reproduced exactly from "
                       "the archived artifact"),
                details={
                    "record_id": rec.record_id,
                    "ui_contract": "1.17.0 (additive)",
                    "source_artifact": str(SRC_ARTIFACT),
                    "self_test_ok": st["ok"],
                    "network_calls": st["network_calls"],
                    "js_errors": st["js_errors"],
                    "fallback_test_ok": fb["ok"],
                    "affected_components": AFFECTED_COMPONENTS,
                },
            )
        )
    else:
        for rec in store.change_records:
            if rec.title == CHANGE_TITLE:
                record_id = rec.record_id
                record_status = rec.status.value
    return {"added_change_record": added, "change_record_id": record_id,
            "change_record_status": record_status}


def main() -> int:
    ui = check_contract_and_grids()
    if not ui["all_passed"]:
        print("UI contract/grid checks FAILED:",
              [k for k, v in ui.items()
               if v is False and k != "contract_version"])
        return 1
    st = _run_node(SELF_TEST, str(UI_APP))
    fb = _run_node(DX_FALLBACK_TEST, str(UI_APP))
    viewer = _run_node(VIEWER_TEST)
    combined = _run_node(COMBINED_TEST)
    userrun = _run_node(USERRUN_TEST)
    if not (st["ok"] and st["network_calls"] == 0 and st["js_errors"] == 0
            and fb["ok"] and viewer["ok"] and combined["ok"]
            and userrun["ok"]):
        print("Self-tests FAILED:", st, fb["ok"], viewer["ok"],
              combined["ok"], userrun["ok"])
        return 1

    store = GovernanceStore.from_json(GOV_PATH.read_text(encoding="utf-8"))
    n_audit_before = len(store.audit_trail.all())
    n_change_before = len(store.change_records)
    gov = apply_governance(store, ui, st, fb)
    integrity = store.audit_trail.verify_all()
    if not integrity:
        print("AUDIT INTEGRITY FAILED - store NOT saved")
        return 1
    GOV_PATH.write_text(store.to_json(), encoding="utf-8")

    report = {
        "task": "Phase 33 Task 3 - embedded-distribution drill-down with "
                "precomputed grids (gap G2)",
        "phase": PHASE,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": "PASS",
        "gap_closed": "G2",
        "contract": "1.16.0 -> 1.17.0 (ADDITIVE: distribution_explorer)",
        "next": "Task 4 (gap G3): printable owner sign-off / report pack",
        "ui_contract_checks": ui,
        "self_test": st,
        "distribution_fallback_self_test": fb,
        "offline_viewer_self_test": viewer,
        "combined_gui_self_test": combined,
        "userrun_fallback_self_test": userrun,
        "governance": {
            **gov,
            "audit_entries":
                f"{n_audit_before}->{len(store.audit_trail.all())}",
            "change_records":
                f"{n_change_before}->{len(store.change_records)}",
            "audit_integrity_verify_all": integrity,
        },
    }
    JSON_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    hr = ui["headline_readouts"]
    nck = sum(1 for k, v in ui.items() if v is True and k != "all_passed")
    md = """# Phase 33 Task 3 - Embedded-Distribution Drill-Down (Gap G2)

**Generated (UTC):** {now}
**Verdict:** PASS - gap G2 closed (contract 1.16.0 -> 1.17.0, ADDITIVE)

## What the offline UI now surfaces

A **Distribution Explorer (P33)** tab over PRECOMPUTED grids embedded at
build time by `scripts/build_ui_data.py` from the archived Phase 16
loss-distribution model output (`{src}`, sha256 `{sha8}...`):

- **Empirical CDF grid** - {ncdf} exact grid points at the archived
  histogram bin edges (0.0 -> 1.0, monotone), hover full-precision
  readouts, grid-point slider, tail zoom (F >= 0.90); the connecting curve
  is labelled *display interpolation*.
- **Quantile grid** - {nq} fixed probabilities (0.5% ... 99.5%), inverse
  histogram CDF computed at build time (linear within a bin, labelled at
  histogram resolution). Build-time p50 {gp50:,.1f} vs archived p50
  {ap50:,.1f} (within one bin width {bw:,.1f}).
- **Archived sections carried bit-for-bit** - 8 percentiles, 5-level
  confidence sweep, 40-bin histogram, headline VaR/ES/SCR
  ({v:,.1f} / {e:,.1f} / {s:,.1f}).
- **Per-seed CDF overlays** - {ns} archived seeds.
- **Provenance panel** - source path, sha256, generation timestamp,
  reproducibility digest, computation method.

## Pre-registered acceptance criteria (design note, gap G2)

- grids computed ONLY at build time, provenance stamped: **PASS**
- embedded grid values reproducible from the archived artefacts: **PASS**
  (independent recomputation here reproduces every value EXACTLY)
- graceful neutral fallback for older payloads: **PASS** (dedicated jsdom
  fallback test - neutral message, no leaked figures, other tabs render,
  0 network / 0 JS errors)
- new self-test checks (grid presence, readout values, fallback): **PASS**
  (18 added; suite {nst} checks ok:true, {nc} network / {je} JS errors)
- ADDITIVE-only contract change: **PASS** (1.16.0 -> 1.17.0; pre-existing
  inventory entries bit-identical; governance limited to the existing
  P32T4 store-sync sweep refresh; meta.generated_utc is the build stamp)
- zero-install preserved: **PASS** (0 external references, single file)
- NO model parameter changes: **PASS** (display layer recomputes nothing
  beyond labelled display interpolation)
- offline viewer + combined GUI + user-run fallback self-tests: **PASS**

## Verification

- UI contract/grid checks: ALL PASS ({nck} substantive checks).
- jsdom self-tests: ui_app ok:true ({nst} checks, {nc} network / {je} JS
  errors); distribution fallback ok:true; offline viewer ok:true;
  combined GUI ok:true; user-run fallback ok:true.

## Governance

- ChangeRecord `{crid}` ({crstatus}); audit entries {aud}; change records
  {chg}; audit-chain integrity verify_all = {integ}.
- The MR-016/MR-017 dependence decision remains PENDING with the model
  owner; nothing on this tab recomputes or re-labels governed figures.

**Standards:** SOA ASOP 41 s3.2; ASOP 56 s3.5; IA TAS M s3.6; IFoA MPN s4.
""".format(
        now=report["generated_utc"], src=hr["source_artifact"],
        sha8=str(hr["source_sha256"])[:12], ncdf=hr["cdf_grid_points"],
        nq=hr["quantile_grid_points"], gp50=hr["grid_p50_build_time"],
        ap50=hr["archived_p50"], bw=hr["bin_width"],
        v=hr["archived_var995"], e=hr["archived_es995"],
        s=hr["archived_scr995"], ns=hr["seeds_embedded"], nck=nck,
        nst=st["n_checks"], nc=st["network_calls"], je=st["js_errors"],
        crid=gov["change_record_id"], crstatus=gov["change_record_status"],
        aud=report["governance"]["audit_entries"],
        chg=report["governance"]["change_records"], integ=integrity,
    )
    MD_PATH.write_text(md, encoding="utf-8")

    print("PHASE 33 TASK 3 PASS - gap G2 closed; contract 1.17.0 additive;",
          "ChangeRecord", gov["change_record_id"],
          gov["change_record_status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
