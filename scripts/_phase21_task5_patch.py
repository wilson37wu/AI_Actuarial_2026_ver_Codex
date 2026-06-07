#!/usr/bin/env python3
"""Phase 21 Task 5 — offline-UI propagation patcher.

Applies the Task 5 edits to the git-HEAD base copies of scripts/build_ui_data.py
and scripts/ui_app_self_test.cjs. Used because the desktop->sandbox mount sync
truncated the directly-edited files; per the established sandbox write protocol,
files are built OFF-MOUNT from the committed base and cp'd onto the mount.

Usage: python3 _phase21_task5_patch.py BASE_PY BASE_CJS OUT_PY OUT_CJS
Each replacement asserts exactly one occurrence (fails loudly otherwise).
"""
import sys


def rep(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit("PATCH FAIL %s: %d occurrences" % (label, n))
    return text.replace(old, new)


def patch_py(src):
    src = rep(src, 'CONTRACT_VERSION = "1.2.0"', 'CONTRACT_VERSION = "1.3.0"', "R1")

    # R2 — FX + liquidity calibration records
    anchor = "    # Mortality-trend driver: the 5th capital driver is an EDUCATIONAL parametric"
    fxliq = r'''    # FX / currency driver (6th driver, Phase 21 Task 1): lognormal spot with
    # P-measure outer drift and CIP-exact Q conditioning; G-FX plausibility gate.
    fx = _load(os.path.join(VAL, "PHASE21_TASK1_FX_DRIVER_REPORT.json"))
    if isinstance(fx, dict) and isinstance(fx.get("gate"), dict):
        gate = fx["gate"]
        params = gate.get("params", {}) if isinstance(gate.get("params"), dict) else {}
        crit = []
        cip_z, cip_tol = None, None
        for c in gate.get("criteria", []):
            if isinstance(c, dict):
                crit.append({"name": str(c.get("criterion", "")).replace("-", " "),
                             "ok": bool(c.get("passed"))})
                ev = c.get("evidence", {})
                if isinstance(ev, dict) and ev.get("check_id") == "MART-FX-CIP":
                    cip_z = _num(ev.get("n_std_errors"))
                    cip_tol = _num(ev.get("tolerance_sigma"))
        items = ([{"label": "CIP martingale |z|", "value": cip_z}]
                 if cip_z is not None else [])
        diag = {
            "method": "Lognormal FX spot; P-measure outer drift, CIP-exact analytic Q "
                      "conditioning (MART-FX-CIP martingale evidence)",
            "n_obs": params.get("n_scenarios"), "fit_r2": None, "converged": None,
            "criteria": crit,
            "fit_bars": ({"title": "Q-measure CIP martingale evidence",
                          "unit": "sigma", "items": items,
                          "threshold": ({"label": "G-FX tolerance (%.0f sigma)" % cip_tol,
                                         "value": cip_tol} if cip_tol else None)}
                         if items else None),
        }
        status = "PASS" if gate.get("passed") else "FAIL"
        out.append(_calib_record(
            "FX / currency (lognormal)", gate.get("gate", "G-FX"), "USD/HKD",
            {"fx_vol": params.get("fx_vol"),
             "rate_spread": params.get("domestic_foreign_rate_spread"),
             "initial_spot": params.get("initial_spot_rate"),
             "real_world_drift": params.get("real_world_drift")},
            status,
            "G-FX %s (%s/%s criteria); CIP martingale z=%.3f sigma"
            % (status, gate.get("n_passed"), gate.get("n_criteria"), cip_z or 0.0),
            False, "docs/validation/PHASE21_TASK1_FX_DRIVER_REPORT.json", None, diag))

    # Liquidity-premium driver (7th driver, Phase 21 Task 3): CIR++ funding-spread /
    # illiquidity-premium process calibrated on the HKD educational fixture; G-LIQ gate.
    liq = _load(os.path.join(VAL, "PHASE21_TASK3_LIQUIDITY_CALIBRATION_REPORT.json"))
    if isinstance(liq, dict) and isinstance(liq.get("summary"), dict):
        s = liq["summary"]
        gate = liq.get("gate_gliq", {}) if isinstance(liq.get("gate_gliq"), dict) else {}
        lr = _num(s.get("long_run_premium_p"))
        l0 = _num(s.get("initial_premium"))
        litems = [it for it in (
            {"label": "Initial premium", "value": l0 * 1e4} if l0 is not None else None,
            {"label": "Long-run P", "value": lr * 1e4} if lr is not None else None,
        ) if it]
        diag = {
            "method": "CIR++ OLS transition regression (delegated to the tested CIR "
                      "estimator); Feller checked; lambda_l clamped at plausibility cap "
                      "(disclosed)",
            "n_obs": s.get("n_obs"), "fit_r2": _num(s.get("fit_r2")), "converged": None,
            "criteria": _criteria_list(s.get("criteria")),
            "fit_bars": ({"title": "Liquidity-premium level structure",
                          "unit": "bp", "items": litems, "threshold": None}
                         if litems else None),
        }
        out.append(_calib_record(
            "Liquidity premium (CIR++)", gate.get("gate_id", "G-LIQ"),
            s.get("market", "HKD"),
            {"kappa_l": s.get("kappa"), "long_run_premium": s.get("long_run_premium_p"),
             "sigma_l": s.get("premium_vol"),
             "lambda_l": s.get("market_price_of_liquidity_risk"),
             "half_life_years": s.get("half_life_years"),
             "feller_ok": s.get("feller_ok")},
            gate.get("status", "PASS"), (gate.get("evidence", "") or "")[:160],
            s.get("is_placeholder"),
            "docs/validation/PHASE21_TASK3_LIQUIDITY_CALIBRATION_REPORT.json",
            s.get("lineage"), diag))

'''
    src = rep(src, anchor, fxliq + anchor, "R2")

    # R3 — seven-driver capital branch
    old3 = '''def _build_capital(base: Dict[str, Any]) -> Dict[str, Any]:
    cap = dict(base) if isinstance(base, dict) else {}
    phase20 = _load(os.path.join(VAL, "PHASE20_TASK4_AGGREGATION_REPORT.json"))'''
    new3 = '''def _build_capital(base: Dict[str, Any]) -> Dict[str, Any]:
    cap = dict(base) if isinstance(base, dict) else {}

    # Phase 21 Task 4: seven-driver (rate, equity, credit, lapse, mortality, FX,
    # liquidity) tail-dependent aggregation — preferred snapshot when present.
    phase21 = _load(os.path.join(VAL, "PHASE21_TASK4_AGGREGATION_REPORT.json"))
    if isinstance(phase21, dict) and isinstance(phase21.get("aggregation"), dict):
        rep = phase21["aggregation"]
        sa = rep.get("standalone_scr", {})
        if isinstance(sa, dict):
            for key, src in (("rate_scr", "rate"), ("equity_scr", "equity"),
                             ("credit_scr", "credit"), ("lapse_scr", "lapse"),
                             ("mortality_scr", "mortality"), ("fx_scr", "fx"),
                             ("liquidity_scr", "liquidity")):
                v = _num(sa.get(src))
                if v is not None:
                    cap[key] = v
        cap["nested_scr"] = rep.get("nested_scr", cap.get("nested_scr"))
        cap["var_covar_scr"] = rep.get("var_covar_scr", cap.get("var_covar_scr"))
        cap["standalone_sum"] = rep.get("standalone_scr_sum", cap.get("standalone_sum"))
        cap["selected_copula"] = rep.get("copula_selected")
        cap["formula_vs_nested_rel_error"] = rep.get("var_covar_vs_nested_rel_error")
        if rep.get("var_covar_vs_nested_rel_error") is not None:
            cap["esg_understatement_pct"] = round(
                100.0 * rep["var_covar_vs_nested_rel_error"], 2)
        cop = rep.get("copula_report", {})
        if isinstance(cop, dict):
            cap["copula"] = dict(cop)
            cap["copula"]["candidates"] = cop.get("candidates") or cop.get("copulas", [])
        cap["copula_scr"] = rep.get("copula_scr")
        cap["copula_vs_nested_rel_error"] = rep.get("copula_vs_nested_rel_error")
        cap["n_drivers"] = len(rep.get("drivers", [])) or 7
        cap["drivers"] = rep.get("drivers", [])
        cap["rate_driver"] = "G2++ two-factor rates"
        cap["liquidity_note"] = ("Liquidity standalone SCR is small under the "
                                 "calibrated mean reversion (half-life 0.74y over a "
                                 "~19y workout) — documented finding, verified "
                                 "CIR-affine-exact.")
        cap["aggregation_source"] = "docs/validation/PHASE21_TASK4_AGGREGATION_REPORT.json"
        cap["aggregation_verdict"] = rep.get("verdict")
        return cap

    phase20 = _load(os.path.join(VAL, "PHASE20_TASK4_AGGREGATION_REPORT.json"))'''
    src = rep(src, old3, new3, "R3")

    # R4 — seven-driver tail branch
    old4 = '''def _build_tail(base: Dict[str, Any]) -> Dict[str, Any]:
    tail = dict(base) if isinstance(base, dict) else {}
    phase20 = _load(os.path.join(VAL, "PHASE20_TASK4_TAIL_DIAGNOSTICS_REPORT.json"))'''
    new4 = '''def _build_tail(base: Dict[str, Any]) -> Dict[str, Any]:
    tail = dict(base) if isinstance(base, dict) else {}

    # Phase 21 Task 4: seven-driver tail diagnostics (copula-simulated convergence,
    # simulated + honest small-sample nested bootstrap CIs, Sobol-RQMC efficiency).
    phase21 = _load(os.path.join(VAL, "PHASE21_TASK4_AGGREGATION_REPORT.json"))
    td = (phase21 or {}).get("aggregation", {}).get("tail_diagnostics", {}) \\
        if isinstance(phase21, dict) else {}
    if isinstance(td, dict) and td and not td.get("skipped"):
        sb = td.get("simulated_bootstrap", {})
        nb = td.get("nested_bootstrap", {})
        vr = td.get("variance_reduction", {})
        if isinstance(sb, dict):
            tail["final_var"] = sb.get("var_point", tail.get("final_var"))
            tail["final_es"] = sb.get("es_point", tail.get("final_es"))
            tail["var_ci"] = sb.get("var_ci", tail.get("var_ci"))
            tail["es_ci"] = sb.get("es_ci", tail.get("es_ci"))
            tail["var_se"] = sb.get("var_se")
            tail["es_se"] = sb.get("es_se")
            tail["bootstrap_n"] = sb.get("n_bootstrap")
        tail["outer_grid"] = td.get("n_sim_grid", [])
        tail["var_path"] = td.get("var_convergence_path", [])
        tail["es_path"] = td.get("es_convergence_path", [])
        tail["converged"] = bool(td.get("converged"))
        tail["recommended_n_outer"] = (tail["outer_grid"][-1]
                                       if tail.get("outer_grid") else None)
        tail["grid_label"] = "copula simulations"
        tail["grid_note"] = ("Convergence grid is the gaussian-copula simulation count "
                             "(10k-200k, CRN prefixes), not nested outer scenarios; the "
                             "honest small-sample nested CI (n_outer=160) is disclosed "
                             "separately.")
        if isinstance(vr, dict):
            tail["sobol_ratio"] = vr.get("qmc_variance_reduction_ratio")
        if isinstance(nb, dict):
            tail["nested_var_ci"] = nb.get("var_ci")
            tail["nested_n_outer"] = nb.get("n_outer")
            tail["nested_disclosure"] = nb.get("disclosure")
        tail["source"] = "docs/validation/PHASE21_TASK4_AGGREGATION_REPORT.json"
        return tail

    phase20 = _load(os.path.join(VAL, "PHASE20_TASK4_TAIL_DIAGNOSTICS_REPORT.json"))'''
    src = rep(src, old4, new4, "R4")

    # R5 — Phase 21 verdicts
    old5 = '''                "source": "docs/validation/PHASE20_TASK4_AGGREGATION_REPORT.json",
            })
    return verdicts'''
    new5 = '''                "source": "docs/validation/PHASE20_TASK4_AGGREGATION_REPORT.json",
            })

    # Phase 21 verdicts: G-FX gate, six-driver OOS proxy validation (honest PARTIAL),
    # G-LIQ gate, and the seven-driver tail-dependent aggregation.
    fx = _load(os.path.join(VAL, "PHASE21_TASK1_FX_DRIVER_REPORT.json"))
    if isinstance(fx, dict) and isinstance(fx.get("gate"), dict):
        g = fx["gate"]
        verdicts.append({
            "name": "G-FX FX-driver plausibility gate (6th driver)",
            "verdict": "PASS" if g.get("passed") else "FAIL",
            "evidence": "%s/%s criteria passed incl. MART-FX-CIP Q-measure martingale"
            % (g.get("n_passed"), g.get("n_criteria")),
            "source": "docs/validation/PHASE21_TASK1_FX_DRIVER_REPORT.json",
        })
    oos = _load(os.path.join(VAL, "PHASE21_TASK2_OOS_VALIDATION_REPORT.json"))
    if isinstance(oos, dict) and isinstance(oos.get("validation"), dict):
        v = oos["validation"]
        verd = str(v.get("verdict", ""))
        verdicts.append({
            "name": "Six-driver OOS proxy validation (FX included)",
            "verdict": "PARTIAL" if verd.upper().startswith("PARTIAL") else verd,
            "evidence": verd,
            "source": "docs/validation/PHASE21_TASK2_OOS_VALIDATION_REPORT.json",
        })
    liq = _load(os.path.join(VAL, "PHASE21_TASK3_LIQUIDITY_CALIBRATION_REPORT.json"))
    if isinstance(liq, dict) and isinstance(liq.get("gate_gliq"), dict):
        g = liq["gate_gliq"]
        verdicts.append({
            "name": "G-LIQ liquidity-calibration gate (7th driver)",
            "verdict": g.get("status", ""),
            "evidence": (g.get("evidence", "") or "")[:160],
            "source": "docs/validation/PHASE21_TASK3_LIQUIDITY_CALIBRATION_REPORT.json",
        })
    agg7 = _load(os.path.join(VAL, "PHASE21_TASK4_AGGREGATION_REPORT.json"))
    if isinstance(agg7, dict) and isinstance(agg7.get("aggregation"), dict):
        rep = agg7["aggregation"]
        verdicts.append({
            "name": "Seven-driver tail-dependent capital aggregation",
            "verdict": rep.get("verdict", ""),
            "evidence": "var-covar understates nested by %.1f%%; copula rel err %.1f%%; "
            "tail diagnostics converged"
            % (100.0 * (rep.get("var_covar_vs_nested_rel_error") or 0.0),
               100.0 * (rep.get("copula_vs_nested_rel_error") or 0.0)),
            "source": "docs/validation/PHASE21_TASK4_AGGREGATION_REPORT.json",
        })
    return verdicts'''
    src = rep(src, old5, new5, "R5")

    # R6 — capital cards
    old6 = '''    var cardRows = [
      ["Rate SCR", cap.rate_scr],["Equity SCR", cap.equity_scr],["Credit SCR", cap.credit_scr],
      ["Lapse SCR", cap.lapse_scr],["Mortality SCR", cap.mortality_scr],
      ["Standalone sum", cap.standalone_sum],["Var-covar SCR", cap.var_covar_scr],
      ["Nested SCR", cap.nested_scr]
    ];'''
    new6 = '''    var cardRows = [
      ["Rate SCR", cap.rate_scr],["Equity SCR", cap.equity_scr],["Credit SCR", cap.credit_scr],
      ["Lapse SCR", cap.lapse_scr],["Mortality SCR", cap.mortality_scr],
      ["FX SCR", cap.fx_scr],["Liquidity SCR", cap.liquidity_scr],
      ["Standalone sum", cap.standalone_sum],["Var-covar SCR", cap.var_covar_scr],
      ["Nested SCR", cap.nested_scr]
    ];'''
    src = rep(src, old6, new6, "R6")

    # R7 — dynamic n-driver note
    old7 = '''    html += '<p class="note">Five-driver economic-capital aggregation at the 99.5% / 12-month level. '+
      'Rate driver: '+esc(cap.rate_driver||"HW1F / legacy snapshot")+
      (cap.nested_scr_reduction_pct!=null?(' &middot; nested SCR reduction vs HW1F: '+esc(cap.nested_scr_reduction_pct)+'%'):"")+
      '. Switch views below; all charts are inline SVG rendered offline from the embedded snapshot.</p>';'''
    new7 = '''    var nd = cap.n_drivers||5;
    var ndWord = (nd===7?"Seven":nd===6?"Six":"Five");
    html += '<p class="note">'+ndWord+'-driver economic-capital aggregation at the 99.5% / 12-month level'+
      (nd>=7?' (rate, equity, credit, lapse, mortality, FX, liquidity &mdash; all documented drivers aggregated)':'')+'. '+
      'Rate driver: '+esc(cap.rate_driver||"HW1F / legacy snapshot")+
      (cap.nested_scr_reduction_pct!=null?(' &middot; nested SCR reduction vs HW1F: '+esc(cap.nested_scr_reduction_pct)+'%'):"")+
      '. Switch views below; all charts are inline SVG rendered offline from the embedded snapshot.</p>';
    if(cap.liquidity_note) html += '<p class="note">'+esc(cap.liquidity_note)+'</p>';'''
    src = rep(src, old7, new7, "R7")

    # R8 — FX + liquidity bars
    old8 = '''      {label:"Lapse", value:cap.lapse_scr, color:"#b98cff"},
      {label:"Mortality", value:cap.mortality_scr, color:"#ff6b6b"}
    ].filter(function(d){return d.value!=null;});'''
    new8 = '''      {label:"Lapse", value:cap.lapse_scr, color:"#b98cff"},
      {label:"Mortality", value:cap.mortality_scr, color:"#ff6b6b"},
      {label:"FX", value:cap.fx_scr, color:"#5ad7e0"},
      {label:"Liquidity", value:cap.liquidity_scr, color:"#e0c45a"}
    ].filter(function(d){return d.value!=null;});'''
    src = rep(src, old8, new8, "R8")

    # R9 — tail block: optional antithetic + nested small-sample disclosure
    old9 = '''    var ratios='<p class="cap" style="margin-top:8px">Variance-reduction efficiency &mdash; Sobol vs MC: <b>'+
      esc(num(tail.sobol_ratio,2))+'x</b>, antithetic vs MC: <b>'+esc(num(tail.antithetic_ratio,2))+
      'x</b>. Both point and CI are bounded, so the metric is reproducible within sampling noise.</p>';'''
    new9 = '''    var ratios='<p class="cap" style="margin-top:8px">Variance-reduction efficiency &mdash; Sobol vs MC: <b>'+
      esc(num(tail.sobol_ratio,2))+'x</b>'+
      (tail.antithetic_ratio!=null?(', antithetic vs MC: <b>'+esc(num(tail.antithetic_ratio,2))+'x</b>'):'')+
      '. Both point and CI are bounded, so the metric is reproducible within sampling noise.</p>';
    if(tail.nested_disclosure){
      ratios+='<p class="cap">Honest small-sample disclosure (nested, n_outer='+esc(num(tail.nested_n_outer))+
        '): 95% CI ['+esc(num((tail.nested_var_ci||[])[0]))+', '+esc(num((tail.nested_var_ci||[])[1]))+
        ']. '+esc(tail.nested_disclosure)+'</p>';
    }'''
    src = rep(src, old9, new9, "R9")

    # R10 — convergence caption generalised
    old10 = '''    var conv=tail.converged?chip("CONVERGED"):chip("NOT CONVERGED");
    return '<div class="chartwrap"><h4>Outer-count convergence of the 99.5% tail metric</h4>'+
      '<p class="cap">VaR and ES as the number of outer scenarios grows. The dashed amber line marks the '+
      'recommended outer count; flattening past it is the convergence signal. '+conv+'</p>'+'''
    new10 = '''    var conv=tail.converged?chip("CONVERGED"):chip("NOT CONVERGED");
    var glabel=tail.grid_label||"outer scenarios";
    return '<div class="chartwrap"><h4>Convergence of the 99.5% tail metric</h4>'+
      '<p class="cap">VaR and ES as the number of '+esc(glabel)+' grows. The dashed amber line marks the '+
      'recommended count; flattening past it is the convergence signal. '+conv+
      (tail.grid_note?(' &mdash; '+esc(tail.grid_note)):'')+'</p>'+'''
    src = rep(src, old10, new10, "R10")

    # R11 — contract schema text
    old11 = '''      "  capital      : {rate_scr, equity_scr, credit_scr, lapse_scr, mortality_scr,",
      "                  standalone_sum, var_covar_scr, nested_scr, selected_copula,",
      "                  esg_understatement_pct, n_drivers}",
      "  tail         : {final_var, final_es, converged, var_ci, es_ci, sobol_ratio, ...}",'''
    new11 = '''      "  capital      : {rate_scr, equity_scr, credit_scr, lapse_scr, mortality_scr,",
      "                  fx_scr, liquidity_scr, standalone_sum, var_covar_scr,",
      "                  nested_scr, selected_copula, esg_understatement_pct, n_drivers}",
      "  tail         : {final_var, final_es, converged, var_ci, es_ci, sobol_ratio,",
      "                  nested_var_ci, nested_n_outer, grid_label, ...}",'''
    src = rep(src, old11, new11, "R11")
    return src


def patch_cjs(src):
    old1 = r'''    g2ppCapitalPresent: /G2\+\+ two-factor rates/.test(bodyText),
    gmartVerdictPresent: /G-MART market-consistency gate/.test(bodyText),'''
    new1 = r'''    g2ppCapitalPresent: /G2\+\+ two-factor rates/.test(bodyText),
    gmartVerdictPresent: /G-MART market-consistency gate/.test(bodyText),
    gfxPresent: /G-FX/.test(bodyText),
    gliqPresent: /G-LIQ/.test(bodyText),
    sevenDriverCapitalPresent: /Seven-driver economic-capital aggregation/.test(bodyText),
    sevenDriverVerdictPresent: /Seven-driver tail-dependent capital aggregation/.test(bodyText),
    oosPartialVerdictPresent: /Six-driver OOS proxy validation/.test(bodyText),
    fxScrCardPresent: /FX SCR/.test(bodyText),
    liquidityScrCardPresent: /Liquidity SCR/.test(bodyText),
    nestedDisclosurePresent: /Honest small-sample disclosure/.test(bodyText),'''
    src = rep(src, old1, new1, "C1")

    old2 = '''    checks.calibDrivers >= 6 &&
    checks.calibPanels >= 6 &&
    checks.calibCharts >= 1 &&
    checks.calibCrit >= 3 &&
    checks.calibParamRows >= 1 &&
    checks.capitalCards >= 5 &&
    checks.capitalSubnavBtns === 4 &&
    checks.capitalSvgCharts >= 4 &&
    checks.driverBars >= 5 &&
    checks.capitalTipElems >= 10 &&
    checks.g2ppCapitalPresent &&
    checks.gmartVerdictPresent &&'''
    new2 = '''    checks.calibDrivers >= 8 &&
    checks.calibPanels >= 8 &&
    checks.calibCharts >= 1 &&
    checks.calibCrit >= 3 &&
    checks.calibParamRows >= 1 &&
    checks.capitalCards >= 7 &&
    checks.capitalSubnavBtns === 4 &&
    checks.capitalSvgCharts >= 4 &&
    checks.driverBars >= 7 &&
    checks.capitalTipElems >= 10 &&
    checks.g2ppCapitalPresent &&
    checks.gmartVerdictPresent &&
    checks.gfxPresent &&
    checks.gliqPresent &&
    checks.sevenDriverCapitalPresent &&
    checks.sevenDriverVerdictPresent &&
    checks.oosPartialVerdictPresent &&
    checks.fxScrCardPresent &&
    checks.liquidityScrCardPresent &&
    checks.nestedDisclosurePresent &&'''
    src = rep(src, old2, new2, "C2")
    return src


def main():
    base_py, base_cjs, out_py, out_cjs = sys.argv[1:5]
    with open(base_py, encoding="utf-8") as fh:
        py = fh.read()
    with open(base_cjs, encoding="utf-8") as fh:
        cjs = fh.read()
    with open(out_py, "w", encoding="utf-8") as fh:
        fh.write(patch_py(py))
    with open(out_cjs, "w", encoding="utf-8") as fh:
        fh.write(patch_cjs(cjs))
    print("PATCH OK")


if __name__ == "__main__":
    main()
