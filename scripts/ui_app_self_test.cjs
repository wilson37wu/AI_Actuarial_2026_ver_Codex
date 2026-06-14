// Offline self-test for ui_app.html (UI Tasks 1-5 + Phase 21-28 propagation).
// Loads the standalone HTML under jsdom, blocks fetch/XHR, clicks every tab and
// sub-view, and asserts: embedded data parsed; inventory + calibration explorer +
// capital dashboard + governance view render; ZERO network calls; ZERO JS errors.
const fs = require("fs");
const path = require("path");
const { JSDOM, VirtualConsole } = require("jsdom");

const htmlPath = process.argv[2] || path.join(process.cwd(), "ui_app.html");
const html = fs.readFileSync(htmlPath, "utf8");
const errors = [];
const networkCalls = [];
const virtualConsole = new VirtualConsole();
virtualConsole.on("jsdomError", err => errors.push(String((err && err.message) || err)));

const dom = new JSDOM(html, {
  runScripts: "dangerously",
  pretendToBeVisual: true,
  virtualConsole,
  beforeParse(window) {
    window.onerror = message => errors.push(String(message));
    window.fetch = (...args) => {
      networkCalls.push(["fetch", String(args[0])]);
      return Promise.reject(new Error("offline self-test blocked fetch"));
    };
    window.XMLHttpRequest = class OfflineBlockedXHR {
      open(_m, url) { networkCalls.push(["xhr", String(url)]); }
      send() { throw new Error("offline self-test blocked XMLHttpRequest"); }
    };
  },
});

const done = (ok, checks) => {
  console.log(JSON.stringify({ ok, checks, errors, networkCalls }, null, 2));
  process.exit(ok ? 0 : 1);
};

setTimeout(() => {
  const { document } = dom.window;
  const tabs = [...document.querySelectorAll(".tab")];
  tabs.forEach(t => t.click());
  // re-activate inventory tab to ensure its DOM is built
  const invTab = tabs.find(t => t.getAttribute("data-target") === "inventory");
  if (invTab) invTab.click();

  // UI Task 2: open Capital & Tail tab and click through every chart sub-view.
  const capTab = tabs.find(t => t.getAttribute("data-target") === "capital");
  if (capTab) capTab.click();
  const segBtns = [...document.querySelectorAll("#capnav .segbtn")];
  segBtns.forEach(b => b.click());
  const driverBars = document.querySelectorAll("#cap-bars svg.chart rect.bar").length;
  segBtns.forEach(b => { if (b.getAttribute("data-view") === "bars") b.click(); });

  // UI Task 3: open the Calibration explorer and click through every driver panel.
  const calibTab = tabs.find(t => t.getAttribute("data-target") === "calibrations");
  if (calibTab) calibTab.click();
  const calibBtns = [...document.querySelectorAll("#calibnav .segbtn")];
  calibBtns.forEach(b => b.click());
  const calibCharts = document.querySelectorAll("#calibrations svg.chart").length;
  const calibCrit = document.querySelectorAll("#calibrations .crit").length;
  const calibParamRows = document.querySelectorAll("#calibrations table.ptable tbody tr").length;
  calibBtns.forEach(b => { if (b.getAttribute("data-idx") === "0") b.click(); });

  // Phase 23 Task 5: open the Management Actions panel and count its elements.
  const maTab = tabs.find(t => t.getAttribute("data-target") === "actions");
  if (maTab) maTab.click();
  const maCards = document.querySelectorAll("#actions .card").length;
  const maGateCrits = document.querySelectorAll("#actions .crit").length;
  const maBarRects = document.querySelectorAll("#actions svg.chart rect.bar").length;
  const maTrigRows = document.querySelectorAll("#actions table.trigtable tbody tr").length;
  const maStandaloneRows = document.querySelectorAll("#actions table.matable tbody tr").length;
  const maRuleRows = document.querySelectorAll("#actions table.ruletable tbody tr").length;

  // Phase 24 Task 5: open the Joint Actions (P24) panel and count its elements.
  const p24Tab = tabs.find(t => t.getAttribute("data-target") === "phase24");
  if (p24Tab) p24Tab.click();
  const p24Cards = document.querySelectorAll("#phase24 .card").length;
  const p24GateCrits = document.querySelectorAll("#phase24 .crit").length;
  const p24DeltaRows = document.querySelectorAll("#phase24 table.dmtable tbody tr").length;
  const p24SweepRows = document.querySelectorAll("#phase24 table.swtable tbody tr").length;
  const p24InnerRows = document.querySelectorAll("#phase24 table.iptable tbody tr").length;
  const p24BarRects = document.querySelectorAll("#phase24 svg.chart rect.bar").length;

  // Phase 25 Task 5: open the Path-wise Actions (P25) panel and count its elements.
  const p25Tab = tabs.find(t => t.getAttribute("data-target") === "phase25");
  if (p25Tab) p25Tab.click();
  const p25Cards = document.querySelectorAll("#phase25 .card").length;
  const p25GateCrits = document.querySelectorAll("#phase25 .crit").length;
  const p25DeltaRows = document.querySelectorAll("#phase25 table.pwtable tbody tr").length;
  const p25SweepRows = document.querySelectorAll("#phase25 table.pwswtable tbody tr").length;
  const p25ProxyRows = document.querySelectorAll("#phase25 table.pxtable tbody tr").length;
  const p25BarRects = document.querySelectorAll("#phase25 svg.chart rect.bar").length;

  // Phase 26 Task 5: open the Full Re-Agg (P26) panel and count its elements.
  const p26Tab = tabs.find(t => t.getAttribute("data-target") === "phase26");
  if (p26Tab) p26Tab.click();
  const p26Cards = document.querySelectorAll("#phase26 .card").length;
  const p26GateCrits = document.querySelectorAll("#phase26 .crit").length;
  const p26MatrixRows = document.querySelectorAll("#phase26 table.p26matrix tbody tr").length;
  const p26DeltaRows = document.querySelectorAll("#phase26 table.p26dtable tbody tr").length;
  const p26GapRows = document.querySelectorAll("#phase26 table.p26gaptable tbody tr").length;
  const p26BarRects = document.querySelectorAll("#phase26 svg.chart rect.bar").length;

  // Phase 28 Task 5: open the Grouped-t Tail (P28) panel and count its elements.
  const p28Tab = tabs.find(t => t.getAttribute("data-target") === "phase28");
  if (p28Tab) p28Tab.click();
  const p28Cards = document.querySelectorAll("#phase28 .card").length;
  const p28GateCrits = document.querySelectorAll("#phase28 .crit").length;
  const p28TailRows = document.querySelectorAll("#phase28 table.p28tail tbody tr").length;
  const p28GapRows = document.querySelectorAll("#phase28 table.p28gaptable tbody tr").length;
  const p28BarRects = document.querySelectorAll("#phase28 svg.chart rect.bar").length;

  // Phase 29 Task 5: open the Vine Tail (P29) panel and count its elements.
  const p29Tab = tabs.find(t => t.getAttribute("data-target") === "phase29");
  if (p29Tab) p29Tab.click();
  const p29Cards = document.querySelectorAll("#phase29 .card").length;
  const p29GateCrits = document.querySelectorAll("#phase29 .crit").length;
  const p29PairRows = document.querySelectorAll("#phase29 table.p29pairs tbody tr").length;
  const p29GapRows = document.querySelectorAll("#phase29 table.p29gaptable tbody tr").length;
  const p29BarRects = document.querySelectorAll("#phase29 svg.chart rect.bar").length;

  // Phase 30 Task 5: open the Stop-Rule (P30) panel and count its elements.
  const p30Tab = tabs.find(t => t.getAttribute("data-target") === "phase30");
  if (p30Tab) p30Tab.click();
  const p30Cards = document.querySelectorAll("#phase30 .card").length;
  const p30GateCrits = document.querySelectorAll("#phase30 .crit").length;
  const p30PairRows = document.querySelectorAll("#phase30 table.p30pairs tbody tr").length;
  const p30EdgeRows = document.querySelectorAll("#phase30 table.p30edges tbody tr").length;
  const p30GapRows = document.querySelectorAll("#phase30 table.p30gaptable tbody tr").length;
  const p30BarRects = document.querySelectorAll("#phase30 svg.chart rect.bar").length;
  const p30El = document.getElementById("phase30");
  const p30Text = (p30El && p30El.textContent) || "";

  // Phase 32 Task 2 (gap G1): open the Owner Decision (P31) panel and count
  // its elements - evidence cards, option cards (registry order), workflow,
  // BLANK decision record, provenance, residual ladder, history, bar chart.
  const odTab = tabs.find(t => t.getAttribute("data-target") === "ownerdecision");
  if (odTab) odTab.click();
  const odCards = document.querySelectorAll("#ownerdecision .card").length;
  const odOptionCards = document.querySelectorAll("#ownerdecision .card.odoption").length;
  const odLadderRows = document.querySelectorAll("#ownerdecision table.odladder tbody tr").length;
  const odHistRows = document.querySelectorAll("#ownerdecision table.odhist tbody tr").length;
  const odWfRows = document.querySelectorAll("#ownerdecision table.odwf tbody tr").length;
  const odDrRows = document.querySelectorAll("#ownerdecision table.oddr tbody tr").length;
  const odProvRows = document.querySelectorAll("#ownerdecision table.odprov tbody tr").length;
  const odBarRects = document.querySelectorAll("#ownerdecision svg.chart rect.bar").length;
  const odBlankChips = [...document.querySelectorAll("#ownerdecision table.oddr .chip")]
    .filter(c => /BLANK/.test(c.textContent)).length;
  const odEl = document.getElementById("ownerdecision");
  const odText = (odEl && odEl.textContent) || "";
  const odO1 = odText.indexOf("O1_adopt_disclosed_vine_readout");
  const odO2 = odText.indexOf("O2_accept_residual_with_monitoring");
  const odO3 = odText.indexOf("O3_fund_second_independent_nested_run");

  // Phase 32 Task 3 (gap G2): open the User Run (UIL) panel and count its
  // elements - headline cards, standalone-SCR table + bar chart, bootstrap
  // CI table, run-configuration table (with per-setting provenance),
  // model-point/portfolio table, input & display provenance table.
  const urTab = tabs.find(t => t.getAttribute("data-target") === "userrun");
  if (urTab) urTab.click();
  const urCards = document.querySelectorAll("#userrun .card").length;
  const urScrRows = document.querySelectorAll("#userrun table.urscr tbody tr").length;
  const urCiRows = document.querySelectorAll("#userrun table.urci tbody tr").length;
  const urPlanRows = document.querySelectorAll("#userrun table.urplan tbody tr").length;
  const urPfRows = document.querySelectorAll("#userrun table.urpf tbody tr").length;
  const urProvRows = document.querySelectorAll("#userrun table.urprov tbody tr").length;
  const urBarRects = document.querySelectorAll("#userrun svg.chart rect.bar").length;
  const urEl = document.getElementById("userrun");
  const urText = (urEl && urEl.textContent) || "";

  // UI Task 4: open the Governance & assumptions view and click through every sub-view.
  const govTab = tabs.find(t => t.getAttribute("data-target") === "governance");
  if (govTab) govTab.click();
  const govBtns = [...document.querySelectorAll("#govnav .segbtn")];
  govBtns.forEach(b => b.click());
  const govGateCards = document.querySelectorAll("#gov-gates .gate").length;
  // exercise the risk filter (change a select and re-render)
  const rfRating = document.getElementById("rfRating");
  if (rfRating) { rfRating.value = "HIGH"; rfRating.onchange && rfRating.onchange(); }
  const govRiskRowsFiltered = document.querySelectorAll("#gov-risk-body tr.rrow").length;
  if (rfRating) { rfRating.value = ""; rfRating.onchange && rfRating.onchange(); }
  const govRiskRows = document.querySelectorAll("#gov-risk-body tr.rrow").length;
  const govHeatCells = document.querySelectorAll("#gov-risk-body svg.chart rect").length;
  const govChangeItems = document.querySelectorAll("#gov-changes .tl-item").length;
  // expand first change record to confirm sign-off history toggles
  const firstCrow = document.querySelector("#gov-changes .crow");
  if (firstCrow) firstCrow.click();
  const govSignoff = document.querySelectorAll("#gov-changes .tl-soh").length;
  const govAuditBadge = document.querySelectorAll("#gov-audit .auditbadge").length;
  // Phase 32 Task 4 (gap G3): governance-store completeness sweep surface.
  const govStoreSyncCards = document.querySelectorAll("#gov-audit .storesync .card").length;
  const govAuditEl = document.getElementById("gov-audit");
  const govAuditText = (govAuditEl && govAuditEl.textContent) || "";
  const govChangesText = (document.getElementById("gov-changes") || {}).textContent || "";
  const govSyncBadges = (govChangesText.match(/store-sync/g) || []).length;
  govBtns.forEach(b => { if (b.getAttribute("data-view") === "gates") b.click(); });

  // UI Task 5: export buttons, CSV builders, ARIA roles, print stylesheet.
  const toolbar = document.getElementById("toolbar");
  const exportBtns = ["btnExportPng","btnCsvInv","btnCsvRisk","btnCsvChg","btnPrint"].filter(id => !!document.getElementById(id)).length;
  const ux = dom.window.__uiExport || {};
  const invCSV = typeof ux.inventoryCSV === "function" ? ux.inventoryCSV() : "";
  const riskCSV = typeof ux.riskCSV === "function" ? ux.riskCSV() : "";
  const chgCSV = typeof ux.changesCSV === "function" ? ux.changesCSV() : "";
  const invCsvRows = invCSV ? invCSV.split("\r\n").length : 0;
  const riskCsvRows = riskCSV ? riskCSV.split("\r\n").length : 0;
  const chgCsvRows = chgCSV ? chgCSV.split("\r\n").length : 0;
  const tablistRoles = document.querySelectorAll('[role="tablist"]').length;
  const tabRoleCount = document.querySelectorAll('#tabs [role="tab"]').length;
  const ariaSelectedTabs = document.querySelectorAll('#tabs [aria-selected="true"]').length;
  const segTabRoles = document.querySelectorAll('.subnav [role="tab"]').length;
  const printCssPresent = /@media print/.test(html);
  const dataTitlePanels = document.querySelectorAll('.panel[data-title]').length;
  const bodyText = document.body.textContent || "";

  // Phase 34 Task 2 (gap H1): data-contract integrity guard surface.
  const intTab = tabs.find(t => t.getAttribute("data-target") === "integrity");
  if (intTab) intTab.click();
  const intEl = document.getElementById("integrity");
  const intText = (intEl && intEl.textContent) || "";
  const intKeyRows = document.querySelectorAll('#integrity table.inttable tbody tr').length;
  const intAbsentRows = document.querySelectorAll('#integrity table.inttable tbody tr[data-int-present="0"]').length;
  const intBannerEl = document.getElementById("integritybanner");
  const intBannerVisible = !!intBannerEl && intBannerEl.style.display !== "none" && intBannerEl.getAttribute("aria-hidden") === "false";
  const uiDataObj = (function(){ const mm = html.match(/\/\*__UI_DATA__\*\/(.*?)<\/script>/s); try { return JSON.parse(mm[1]); } catch(e){ return null; } })();
  const intManifest = uiDataObj && uiDataObj.contract_manifest;

  // Phase UIL Task 4 (B4+A1): currency wire-through assertions.
  // Parse the embedded contract to learn the configured currency, then assert
  // the GUI actually renders money with that symbol and shows the badge.
  let uiMeta = {};
  let uiGov = {};
  try {
    const rawData = (document.getElementById("ui-data").textContent || "")
      .replace("/*__UI_DATA__*/", "").trim();
    const uiParsed = JSON.parse(rawData) || {};
    uiMeta = uiParsed.meta || {};
    uiGov = uiParsed.governance || {};
  } catch (e) { /* leave uiMeta empty; checks below will fail loudly */ }
  // Phase 32 Task 4 (gap G3): sweep consistency recomputed from embedded data.
  const g3ss = uiGov.store_sync || {};
  const g3supp = uiGov.change_records_supplement || [];
  const g3embedded = uiGov.change_records || [];
  const g3ids = new Set(g3embedded.map(c => c.record_id));
  const g3overlap = g3supp.filter(c => g3ids.has(c.record_id)).length;
  const g3statusTotal = Object.values(g3ss.change_record_status_counts || {})
    .reduce((a, b) => a + b, 0);
  const curCfg = uiMeta.currency || {};
  const symEsc = curCfg.symbol
    ? curCfg.symbol.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") : null;
  const moneyRe = symEsc ? new RegExp(symEsc + "[0-9][0-9,]*") : null;

  // Phase 33 Task 2 (gap G1): interactive cross-phase SCR comparator.
  const cmpTab = tabs.find(t => t.getAttribute("data-target") === "comparator");
  if (cmpTab) cmpTab.click();
  const cmpEl = document.getElementById("comparator");
  const cmpText0 = (cmpEl && cmpEl.textContent) || "";
  const readCmpRows = () => [...document.querySelectorAll("#comparator table.cmptable tbody tr")];
  const readCmpDeltas = () => { const m = {}; readCmpRows().forEach(r => {
    const td = r.querySelector("td.cmpdelta");
    if (td) m[r.getAttribute("data-cmp-id")] = td.getAttribute("data-cmp-delta"); }); return m; };
  const cmpRows0 = readCmpRows();
  const cmpIds0 = cmpRows0.map(r => r.getAttribute("data-cmp-id"));
  const cmpPoints0 = {}; cmpRows0.forEach(r => { cmpPoints0[r.getAttribute("data-cmp-id")] = r.getAttribute("data-cmp-point"); });
  const cmpDelta0 = readCmpDeltas();
  const cmpCiSvg0 = document.querySelectorAll("#comparator svg.chart").length;
  const cmpCiCircles0 = document.querySelectorAll("#comparator svg.chart circle").length;
  const cmpVineBtn = [...document.querySelectorAll("#cmpnav .segbtn")].find(b => b.getAttribute("data-base") === "vine2");
  if (cmpVineBtn) cmpVineBtn.click();
  const cmpDelta1 = readCmpDeltas();
  const cmpText1 = (cmpEl && cmpEl.textContent) || "";
  const cmpCiSvg1 = document.querySelectorAll("#comparator svg.chart").length;
  const cmpFrozenBtn = [...document.querySelectorAll("#cmpnav .segbtn")].find(b => b.getAttribute("data-base") === "frozen_t");
  if (cmpFrozenBtn) cmpFrozenBtn.click();
  const cmpText2 = (cmpEl && cmpEl.textContent) || "";
  const cmpDelta2 = readCmpDeltas();
  const cmpProvRows = document.querySelectorAll("#comparator table.cmpprov tbody tr").length;

  // Phase 33 Task 3 (gap G2): embedded-distribution drill-down explorer.
  let dxData = null;
  try {
    const rawDx = (document.getElementById("ui-data").textContent || "")
      .replace("/*__UI_DATA__*/", "").trim();
    dxData = (JSON.parse(rawDx) || {}).distribution_explorer || null;
  } catch (e) { /* dxData stays null; checks fail loudly */ }
  const dxTab = tabs.find(t => t.getAttribute("data-target") === "distexplorer");
  if (dxTab) dxTab.click();
  const dxEl = document.getElementById("distexplorer");
  const dxText0 = (dxEl && dxEl.textContent) || "";
  const dxSvg0 = document.querySelectorAll("#dxcdf svg.chart").length;
  const dxPts0 = document.querySelectorAll("#dxcdf svg.chart circle.dxpt").length;
  const dxSeedPaths0 = document.querySelectorAll("#dxcdf svg.chart path.dxseed").length;
  const dxQRows = [...document.querySelectorAll("#distexplorer table.dxqtable tbody tr")];
  const dxPRows = [...document.querySelectorAll("#distexplorer table.dxptable tbody tr")];
  const dxSRows = document.querySelectorAll("#distexplorer table.dxstable tbody tr").length;
  const dxP50Row = dxPRows.find(r => r.getAttribute("data-dx-p") === "0.5");
  const dxSlider = document.getElementById("dxslider");
  const dxReadout = document.getElementById("dx-readout");
  let dxReadoutLast = "", dxReadoutFirst = "";
  if (dxSlider && dxReadout) {
    dxSlider.value = String(dxSlider.max);
    dxSlider.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
    dxReadoutLast = dxReadout.textContent || "";
    dxSlider.value = "0";
    dxSlider.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
    dxReadoutFirst = dxReadout.textContent || "";
  }
  const dxTailBtn = [...document.querySelectorAll("#dxnav .segbtn")].find(b => b.getAttribute("data-zoom") === "tail");
  if (dxTailBtn) dxTailBtn.click();
  const dxSvgTail = document.querySelectorAll("#dxcdf svg.chart").length;
  const dxPtsTail = document.querySelectorAll("#dxcdf svg.chart circle.dxpt").length;
  const dxFullBtn = [...document.querySelectorAll("#dxnav .segbtn")].find(b => b.getAttribute("data-zoom") === "full");
  if (dxFullBtn) dxFullBtn.click();
  const dxPtsBack = document.querySelectorAll("#dxcdf svg.chart circle.dxpt").length;
  const dxCdfP = ((dxData || {}).cdf_grid || {}).p || [];
  const dxCdfX = ((dxData || {}).cdf_grid || {}).x || [];
  const dxQGrid = (dxData || {}).quantile_grid || {};
  const dxArchP = (dxData || {}).archived_percentiles || [];
  const dxProv = (dxData || {}).provenance || {};

  // Phase 33 Task 4 (gap G3): printable owner sign-off pack + complete CSV
  // export coverage for governed read-out tables. Parse the embedded snapshot
  // owner-decision + governance keys and assert the CSV builders reproduce them
  // bit-for-bit, plus the print-only sign-off cover is present and neutral.
  let g3od = {}, g3gov = {}, g3dx = {};
  try {
    const rawG3 = (document.getElementById("ui-data").textContent || "")
      .replace("/*__UI_DATA__*/", "").trim();
    const pj = JSON.parse(rawG3) || {};
    g3od = pj.owner_decision_p31 || {};
    g3gov = pj.governance || {};
    g3dx = pj.distribution_explorer || {};
  } catch (e) { /* leave empty; checks fail loudly */ }
  const uxG3 = dom.window.__uiExport || {};
  const call = (fn) => (typeof uxG3[fn] === "function" ? uxG3[fn]() : "");
  const rowsOf = (csv) => (csv ? csv.split("\r\n") : []);
  const gatesCSV = call("deploymentGatesCSV");
  const optsCSV = call("ownerOptionsCSV");
  const evidCSV = call("evidenceCSV");
  const ladderCSV = call("residualLadderCSV");
  const histCSV = call("escalationHistoryCSV");
  const stopCSV = call("stopRuleCSV");
  const wfCSV = call("signoffWorkflowCSV");
  const drCSV = call("decisionRecordCSV");
  const cmpCSV = call("comparatorCSV");
  const distCSV = call("distGridCSV");
  const packCSV = call("signoffPackCSV");
  // Phase 34 Task 4 (gap H3): full evidence bundle + print-all
  const bundleCSV = call("evidenceBundleCSV");
  const bundleJSON = call("evidenceBundleJSON");
  const h3Headers = ["## Inventory","## Risk register","## Change records","## Deployment gates",
    "## Owner options","## Evidence pack","## Copula-form residual ladder","## Dependence-form escalation history",
    "## Binding stop-rule record","## Sign-off workflow","## SCR comparator","## Distribution grid","## Decision record"];
  const h3AllSections = h3Headers.every(h => bundleCSV.indexOf(h) !== -1);
  let h3JsonObj = null; try { h3JsonObj = JSON.parse(bundleJSON); } catch (e) {}
  const h3JsonHeadlineNumber = !!h3JsonObj && h3JsonObj.provenance && h3JsonObj.provenance.governed_headline
    && h3JsonObj.provenance.governed_headline.value === 39975.654628199336;
  const h3DecRowsBundle = bundleCSV.split("\r\n").filter(r => /BLANK - awaiting owner decision/.test(r));
  const g3gates = g3gov.deployment_gates || [];
  const g3order = g3od.owner_option_order || [];
  const g3drt = g3od.decision_record_template || {};
  const optsRows = rowsOf(optsCSV);
  const drRows = rowsOf(drCSV);
  const gatesRows = rowsOf(gatesCSV);
  // first data row of options CSV: order=1, option_id=first registry id
  const optsFirstId = optsRows.length > 1 ? optsRows[1].split(",")[1] : "";
  // decision record CSV: every field BLANK preserved (none pre-filled in template)
  const drBlankAll = drRows.slice(1).every(r => /BLANK - awaiting owner decision/.test(r));
  const drFieldCount = drRows.length - 1;
  const signoffCoverEl = document.getElementById("signoffcover");
  const signoffCoverText = (signoffCoverEl && signoffCoverEl.textContent) || "";
  const printCoverCssPresent = /\.signoffcover\{display:block !important/.test(html)
    && /\.signoffcover\{display:none\}/.test(html);
  const dxCdfXn = ((g3dx.cdf_grid || {}).x || []).length;

  // Phase 33 Task 5 (gap G4): accessibility & usability pass on the main tab
  // strip and data tables. Drive keyboard activation, URL-hash persistence, and
  // verify visually-hidden table captions. No model figures are touched.
  const KeyboardEvent = dom.window.KeyboardEvent;
  const Event = dom.window.Event;
  const mainTabs = [...document.querySelectorAll("#tabs .tab")];
  const tabById = (id) => mainTabs.find(t => t.getAttribute("data-target") === id);
  // sr-only caption CSS present in the single-file build
  const g4SrOnlyCssPresent = /\.sr-only\{position:absolute/.test(html);
  // tabpanel roles wired for every tab
  const g4TabpanelRoles = document.querySelectorAll('.panel[role="tabpanel"]').length;
  const g4TabsAriaControls = document.querySelectorAll('#tabs [role="tab"][aria-controls]').length;
  // Enter activates a focused (non-active) tab
  const govTabK = tabById("governance");
  let g4EnterActivates = false, g4SpaceActivates = false, g4ArrowMoves = false;
  if (govTabK) {
    govTabK.focus();
    govTabK.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    g4EnterActivates = govTabK.getAttribute("aria-selected") === "true" &&
      document.getElementById("governance").classList.contains("active");
  }
  const ovTabK = tabById("overview");
  if (ovTabK) {
    ovTabK.focus();
    ovTabK.dispatchEvent(new KeyboardEvent("keydown", { key: " ", bubbles: true }));
    g4SpaceActivates = ovTabK.getAttribute("aria-selected") === "true" &&
      document.getElementById("overview").classList.contains("active");
    // ArrowRight moves selection to the next tab (roving tabindex)
    ovTabK.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }));
    const nextSel = document.querySelector('#tabs [aria-selected="true"]');
    g4ArrowMoves = !!nextSel && nextSel.getAttribute("data-target") !== "overview";
  }
  // URL hash is written when a tab is activated
  let g4HashWritten = false, g4HashRestores = false, g4ExactlyOneSelectedAfterHash = false;
  if (govTabK) {
    govTabK.click();
    g4HashWritten = (dom.window.location.hash || "") === "#governance";
  }
  // Hash drives selection: point hash at a different tab and fire hashchange
  if (tabById("inventory")) {
    dom.window.location.hash = "#inventory";
    dom.window.dispatchEvent(new Event("hashchange"));
    const invTabK = tabById("inventory");
    g4HashRestores = invTabK.getAttribute("aria-selected") === "true" &&
      document.getElementById("inventory").classList.contains("active");
    g4ExactlyOneSelectedAfterHash =
      document.querySelectorAll('#tabs [aria-selected="true"]').length === 1;
  }
  // No browser storage APIs anywhere in the single-file build (file:// safe)
  // Phase 34 Task 2 (gap H1): scope the storage-API scan to the executable UI
  // code, EXCLUDING the embedded data island (governance prose can legitimately
  // *mention* "localStorage"/"sessionStorage" as text; that is data, not a code
  // call). Any real storage-API use in the script/markup is still caught.
  const g4CodeOnlyHtml = html.replace(/<script id="ui-data"[^>]*>[\s\S]*?<\/script>/, "");
  const g4NoStorageApis = !/\blocalStorage\b/.test(g4CodeOnlyHtml) && !/\bsessionStorage\b/.test(g4CodeOnlyHtml);
  // Every table carries exactly one visually-hidden caption (accessible name)
  const allTables = [...document.querySelectorAll("table")];
  const g4TablesTotal = allTables.length;
  const g4TablesWithCaption = allTables.filter(t => {
    const c = t.querySelector("caption");
    return c && (c.className || "").indexOf("sr-only") !== -1 &&
      (c.textContent || "").trim().length > 0;
  }).length;
  const g4TablesWithoutCaption = g4TablesTotal - g4TablesWithCaption;
  const g4NoDuplicateCaptions =
    allTables.every(t => t.querySelectorAll("caption").length <= 1);
  // restore overview selection so downstream state is neutral
  if (ovTabK) ovTabK.click();

  // ===== Phase 34 Task 3 (gap H2): global search + deep-linkable read-outs =====
  // All assertions exercise ONLY already-rendered text; nothing is fetched and no
  // model figure is recomputed. The governed headline must be findable yet never
  // re-labelled, and deep links must restore tab + in-tab section via URL hash.
  const h2Input = document.getElementById("gsearchInput");
  const h2Box = document.getElementById("gsearchResults");
  const h2SearchBoxPresent = !!h2Input && !!h2Box;
  const h2DlIdsAssigned = document.querySelectorAll('[id^="dl-"]').length;
  let h2HitForGovernedHeadline = false, h2JumpActivatesTab = false,
      h2HeadlineNeverRelabelled = false, h2HashCarriesSection = false;
  if (h2Input && h2Box) {
    const cmpBefore = [...document.querySelectorAll('[data-cmp-point]')]
      .map(e => e.getAttribute('data-cmp-point'));
    h2Input.value = "governed component scr headline";
    h2Input.dispatchEvent(new Event("input", { bubbles: true }));
    const items = [...h2Box.querySelectorAll(".gsearch-item")];
    h2HitForGovernedHeadline = items.length >= 1 &&
      /Governed component SCR headline/.test(items[0].textContent);
    if (items.length) {
      items[0].click();
      const sel = document.querySelector('#tabs [aria-selected="true"]');
      h2JumpActivatesTab = !!sel &&
        document.getElementById(sel.getAttribute("data-target")).classList.contains("active");
      h2HashCarriesSection = /~dl-/.test(dom.window.location.hash || "");
      const cmpAfter = [...document.querySelectorAll('[data-cmp-point]')]
        .map(e => e.getAttribute('data-cmp-point'));
      h2HeadlineNeverRelabelled =
        JSON.stringify(cmpBefore) === JSON.stringify(cmpAfter) &&
        cmpBefore.indexOf("39975.654628199336") !== -1;
    }
  }
  // deep link restores BOTH the tab and the in-tab section via the URL hash only
  let h2DeepLinkTabSection = false, h2DeepLinkPlainTabStillWorks = false;
  const h2CapAnchorEl = document.querySelector('#capital [id^="dl-"]');
  if (h2CapAnchorEl) {
    dom.window.location.hash = "#capital~" + h2CapAnchorEl.id;
    dom.window.dispatchEvent(new Event("hashchange"));
    const sel = document.querySelector('#tabs [aria-selected="true"]');
    h2DeepLinkTabSection = !!sel && sel.getAttribute("data-target") === "capital" &&
      h2CapAnchorEl.classList.contains("dl-flash");
  }
  // a plain "#tab" hash (no section) still restores just the tab (G4 back-compat)
  dom.window.location.hash = "#governance";
  dom.window.dispatchEvent(new Event("hashchange"));
  {
    const sel = document.querySelector('#tabs [aria-selected="true"]');
    h2DeepLinkPlainTabStillWorks = !!sel && sel.getAttribute("data-target") === "governance" &&
      document.getElementById("governance").classList.contains("active");
  }
  // the search/deep-link layer introduces no storage APIs (file:// safe)
  const h2NoStorageApis = g4NoStorageApis;
  if (ovTabK) ovTabK.click();

  // ===== Phase 34 Task 5 (gap H4): responsive + high-contrast usability pass =====
  // jsdom does not compute layout, so the narrow-viewport guarantee is asserted
  // structurally (responsive @media + table overflow-scroll present) plus
  // behaviourally for the CSS-only high-contrast toggle and the reduced-motion
  // media query. Nothing is fetched; no model figure is recomputed.
  const h4Css = (function(){ const m = html.match(/<style[\s\S]*?<\/style>/i); return m ? m[0] : ""; })();
  const h4ResponsiveMediaPresent = /@media[^\{]*max-width:\s*768px/i.test(h4Css);
  const h4ResponsiveTableScroll = /@media[^\{]*max-width:\s*768px[\s\S]*?overflow-x:\s*auto/i.test(h4Css);
  const h4ReducedMotionPresent = /@media[^\{]*prefers-reduced-motion[^\{]*reduce/i.test(h4Css);
  const h4HighContrastThemePresent = /html\.hc\b/.test(h4Css);
  const h4Btn = document.getElementById("hcToggle");
  const h4ToggleButtonPresent = !!h4Btn && h4Btn.tagName === "BUTTON";
  let h4ToggleAppliesClass=false, h4ToggleWritesHash=false, h4ToggleAriaPressed=false,
      h4ToggleRemovesClass=false, h4ToggleClearsHash=false, h4RestoreFromHash=false,
      h4FlagDoesNotBreakTabRouting=false;
  const hcRaw = () => (dom.window.location.hash||"").replace(/^#/,"");
  const hcHasFlag = () => hcRaw().split("&").indexOf("hc=1") > -1;
  if (h4Btn) {
    dom.window.location.hash = "#overview";
    dom.window.dispatchEvent(new Event("hashchange"));
    h4Btn.click(); // ON
    h4ToggleAppliesClass = document.documentElement.classList.contains("hc");
    h4ToggleWritesHash = hcHasFlag();
    h4ToggleAriaPressed = h4Btn.getAttribute("aria-pressed") === "true";
    h4Btn.click(); // OFF
    h4ToggleRemovesClass = !document.documentElement.classList.contains("hc");
    h4ToggleClearsHash = !hcHasFlag();
    dom.window.location.hash = "#governance&hc=1";
    dom.window.dispatchEvent(new Event("hashchange"));
    h4RestoreFromHash = document.documentElement.classList.contains("hc");
    const selH4 = document.querySelector('#tabs [aria-selected="true"]');
    h4FlagDoesNotBreakTabRouting = !!selH4 && selH4.getAttribute("data-target") === "governance" &&
      document.getElementById("governance").classList.contains("active");
    dom.window.location.hash = "#overview";
    dom.window.dispatchEvent(new Event("hashchange"));
    if (document.documentElement.classList.contains("hc")) h4Btn.click();
  }
  const h4NoStorageApis = g4NoStorageApis;

  // Phase 35 Task 2 (gap A1): formal WCAG 2.1 AA keyboard + contrast pass.
  // CSS-only :focus-visible must cover EVERY interactive control type; the
  // embedded a11y_audit must be a real, fully-passing AA record measured at
  // build time; and the Integrity panel must render it read-only.
  const a1Css = h4Css; // the single-file <style> block extracted above
  const a1FocusVisibleComprehensive = [
    "button:focus-visible", "input:focus-visible", "select:focus-visible",
    "textarea:focus-visible", "summary:focus-visible", ".hctoggle:focus-visible",
    "[tabindex]:focus-visible",
  ].every(sel => a1Css.indexOf(sel) >= 0);
  const a1Audit = uiDataObj && uiDataObj.a11y_audit;
  const a1AuditEmbedded = !!a1Audit && a1Audit.standard === "WCAG 2.1 AA" &&
    !!a1Audit.themes && !!a1Audit.themes.default && !!a1Audit.themes.high_contrast;
  const a1PairsBothThemes = a1AuditEmbedded &&
    Array.isArray(a1Audit.themes.default.pairs) &&
    a1Audit.themes.default.pairs.length >= 8 &&
    Array.isArray(a1Audit.themes.high_contrast.pairs) &&
    a1Audit.themes.high_contrast.pairs.length === a1Audit.themes.default.pairs.length;
  const a1AllPairsPassAA = a1PairsBothThemes &&
    ["default", "high_contrast"].every(t =>
      a1Audit.themes[t].pairs.every(p =>
        p.pass === true && Number(p.ratio) >= Number(p.required))) &&
    a1Audit.summary && a1Audit.summary.all_pass === true;
  const a1KeyboardInventory = !!a1Audit && !!a1Audit.keyboard &&
    Array.isArray(a1Audit.keyboard.controls) && a1Audit.keyboard.controls.length >= 8 &&
    a1Audit.keyboard.controls.every(c => c.operable === true);
  const a1FocusVisibleSelectorsListed = !!a1Audit && !!a1Audit.focus_visible &&
    a1Audit.focus_visible.css_only === true &&
    ["button", "summary", ".hctoggle", "[tabindex]"].every(
      s => (a1Audit.focus_visible.selectors || []).indexOf(s) >= 0);
  const a1ContrastTableRendered = /WCAG 2\.1 AA conformance/.test(intText) &&
    /Default theme/.test(intText) && /High-contrast theme/.test(intText);
  const a1KeyboardTableRendered = /Keyboard operability/.test(intText) &&
    /High-contrast toggle/.test(intText);
  const a1DisplayOnlyStated = /recomputes no model figure/.test(intText) &&
    /contrast ratio is not a model figure/.test(intText);
  const a1A11yTables = document.querySelectorAll('#integrity table.a11ytbl:not(.intverify)').length;

  // Phase 35 Task 3 (gap A2): per-section SHA-256 content digest + in-browser
  // tamper-evident verifier. The build embeds a digest of every top-level
  // section (except contract_manifest); the page RECOMPUTES them in-browser
  // from the embedded payload and renders a verified/altered table + badge.
  const a2Manifest = uiDataObj && uiDataObj.contract_manifest;
  const a2SectionDigests = a2Manifest && a2Manifest.section_digests;
  const a2TopKeysExclManifest = uiDataObj
    ? Object.keys(uiDataObj).filter(k => k !== "contract_manifest").sort()
    : [];
  const a2DigestsPresent = !!a2SectionDigests && typeof a2SectionDigests === "object" &&
    typeof a2Manifest.root_digest === "string" && a2Manifest.root_digest.length === 64 &&
    a2Manifest.digest_algo === "sha256";
  const a2DigestsHex = a2DigestsPresent &&
    Object.keys(a2SectionDigests).every(k => /^[0-9a-f]{64}$/.test(a2SectionDigests[k]));
  const a2DigestsCoverAllSections = a2DigestsPresent &&
    JSON.stringify(Object.keys(a2SectionDigests).sort()) === JSON.stringify(a2TopKeysExclManifest);
  const a2VerifierRows = document.querySelectorAll('#integrity table.intverify tbody tr').length;
  const a2VerifierAltRows = document.querySelectorAll('#integrity table.intverify tbody tr[data-int-verify="alt"]').length;
  const a2VerifierOkRows = document.querySelectorAll('#integrity table.intverify tbody tr[data-int-verify="ok"]').length;
  const a2VerifierTableRendered = /Content integrity/.test(intText) &&
    /per-section SHA-256/.test(intText) && a2VerifierRows === a2TopKeysExclManifest.length &&
    a2VerifierRows > 0;
  // The verifier executes the pure-JS SHA-256 under jsdom; if any recomputed
  // digest diverged from the build digest the badge would read ALTERED. So this
  // asserts the in-browser recompute genuinely matches the embedded digests.
  const a2AllSectionsVerified = a2VerifierRows > 0 && a2VerifierAltRows === 0 &&
    a2VerifierOkRows === a2VerifierRows && /INTEGRITY VERIFIED/.test(intText) &&
    !/CONTENT ALTERED/.test(intText);
  const a2RootDigestShown = a2DigestsPresent &&
    intText.indexOf(a2Manifest.root_digest.slice(0, 24)) >= 0;
  const a2HelpersEmbedded = /_ciSectionDigests/.test(html) && /_ciSha256/.test(html) &&
    /renderIntegrityVerifierHtml/.test(html);
  const a2NoNetworkStated = /no network/.test(intText) &&
    /recomputes a content digest/.test(intText);

  const checks = {
    // Phase 33 Task 5 (gap G4): accessibility & usability pass
    g4SrOnlyCssPresent,
    g4TabpanelRoles,
    g4TabsAriaControls,
    g4EnterActivates,
    g4SpaceActivates,
    g4ArrowMoves,
    g4HashWritten,
    g4HashRestores,
    g4ExactlyOneSelectedAfterHash,
    g4NoStorageApis,
    g4TablesTotal,
    g4TablesWithCaption,
    g4TablesWithoutCaption,
    g4NoDuplicateCaptions,
    dxTabPresent: !!dxTab,
    dxTabTextPresent: /Distribution Explorer \(P33\)/.test(bodyText),
    dxGridEmbedded: !!dxData && dxCdfX.length === 41 && dxCdfP.length === 41,
    dxCdfMonotoneEnds: dxCdfP.length > 1 && dxCdfP[0] === 0 && dxCdfP[dxCdfP.length - 1] === 1 &&
      dxCdfP.every((v, i) => i === 0 || v >= dxCdfP[i - 1]),
    dxProvenanceEmbedded: typeof dxProv.source_sha256 === "string" && dxProv.source_sha256.length === 64 &&
      /PHASE16_LOSS_DISTRIBUTION\.json$/.test(String(dxProv.source || "")) &&
      /BUILD TIME ONLY/.test(String(dxProv.computed_by || "")),
    dxCdfSvgRendered: dxSvg0 === 1,
    dxCdfGridPointCount: dxPts0 === 41,
    dxSeedOverlayRendered: dxSeedPaths0 === 4,
    dxQuantileRows: dxQRows.length === 13 &&
      dxQRows.every((r, i) => r.getAttribute("data-dx-q-loss") === String((dxQGrid.loss || [])[i])),
    dxArchivedPercentileRows: dxPRows.length === 8 &&
      dxPRows.every((r, i) => r.getAttribute("data-dx-loss") === String((dxArchP[i] || {}).loss)),
    dxP50ExactArchivedKey: !!dxP50Row && dxP50Row.getAttribute("data-dx-loss") === "107159.2854",
    dxSweepRows: dxSRows === 5,
    dxSliderReadoutWorks: /grid point 40 of 40/.test(dxReadoutLast) && /F\(loss\) = 1\.0000/.test(dxReadoutLast) &&
      dxReadoutLast.indexOf(String(dxCdfX[dxCdfX.length - 1])) !== -1 &&
      /grid point 0 of 40/.test(dxReadoutFirst) && /F\(loss\) = 0\.0000/.test(dxReadoutFirst),
    dxZoomWorks: dxSvgTail === 1 && dxPtsTail > 0 && dxPtsTail < 41 && dxPtsBack === 41,
    dxBuildTimeStated: /computed at build time/.test(dxText0) && /recomputes nothing/.test(dxText0),
    dxInterpolationLabelled: /display interpolation/.test(dxText0) && /NOT new model output/.test(dxText0),
    dxArchivedBitForBitStated: /carried bit-for-bit/.test(dxText0),
    dxNoFallbackInFullPayload: !/grids are not embedded in this snapshot/.test(dxText0),
    // Phase 33 Task 4 (gap G3): sign-off pack + CSV export coverage
    g3SignoffCoverPresent: !!signoffCoverEl,
    g3SignoffCoverNeutralBlank: /Owner sign-off pack/.test(signoffCoverText) && /intentionally BLANK/.test(signoffCoverText) && /NO default and NO recommendation/.test(signoffCoverText),
    g3SignoffCoverHeadline: /39,976/.test(signoffCoverText) && /frozen single-df t/.test(signoffCoverText),
    g3PrintCoverCssPresent: printCoverCssPresent,
    g3ExportButtonsPresent: !!document.getElementById('btnCsvGates') && !!document.getElementById('btnCsvSignoff'),
    g3GatesCsvComplete: gatesRows.length === g3gates.length + 1 && /(^|,)gate_id(,|$)/.test(gatesRows[0] || ''),
    g3GatesCsvBitForBit: g3gates.length > 0 && gatesRows[1].split(',')[0] === String(g3gates[0].gate_id),
    g3OwnerOptionsCsvOrder: optsRows.length === g3order.length + 1 && optsFirstId === String(g3order[0] || '') && optsFirstId === 'O1_adopt_disclosed_vine_readout',
    g3EvidenceCsvHeadlineKey: /39975\.654628199336|39,?975/.test(evidCSV) && rowsOf(evidCSV).length === 7,
    g3ResidualLadderCsv: rowsOf(ladderCSV).length >= 2,
    g3EscalationHistoryCsv: rowsOf(histCSV).length >= 2,
    g3StopRuleCsv: /(^|,)trigger(,|$)/.test((rowsOf(stopCSV)[1] || '')) || rowsOf(stopCSV).length >= 2,
    g3SignoffWorkflowCsv: rowsOf(wfCSV).length >= 2,
    g3DecisionRecordBlankPreserved: drFieldCount === 6 && drBlankAll,
    g3ComparatorCsvComplete: rowsOf(cmpCSV).length === 7 && /39975\.654628199336/.test(cmpCSV),
    g3DistGridCsvComplete: rowsOf(distCSV).length === dxCdfXn + 1 && dxCdfXn === 41,
    g3SignoffPackComplete: /OWNER SIGN-OFF PACK/.test(packCSV) && /## Owner options/.test(packCSV) && /## Decision record/.test(packCSV) && /## Deployment gates/.test(packCSV) && /BLANK - awaiting owner decision/.test(packCSV),
    h3BundleButtonsPresent: !!document.getElementById("btnBundleCsv") && !!document.getElementById("btnBundleJson") && !!document.getElementById("btnPrintAll"),
    h3BundleCoversAllSections: h3AllSections,
    h3BundleHeadlineBitForBit: /39975\.654628199336/.test(bundleCSV) && /39975\.654628199336/.test(bundleJSON),
    h3BundleProvenanceStamped: /# Provenance: contract v/.test(bundleCSV) && /build\/generated/.test(bundleCSV) && /Governed component SCR headline/.test(bundleCSV),
    h3BundleDecisionBlank: /## Decision record \(BLANK until the owner decides\)/.test(bundleCSV) && h3DecRowsBundle.length >= 1,
    h3BundleJsonValid: !!h3JsonObj && h3JsonObj.bundle === "full_evidence_bundle" && Array.isArray(h3JsonObj.section_order) && h3JsonObj.section_order.length === 13,
    h3BundleJsonHeadlineNumberExact: h3JsonHeadlineNumber,
    h3BundleJsonDecisionBlank: !!h3JsonObj && /BLANK - awaiting owner decision/.test(h3JsonObj.sections_csv.decision_record),
    h3PrintAllCssPresent: /html\.printall \.panel\{display:block !important\}/.test(html) && /H3 print-all/.test(html),
    h3PrintAllButtonNoThrow: (function(){ try { var w=document.defaultView; var orig=w.print; w.print=function(){}; var b=document.getElementById("btnPrintAll"); if(b) b.click(); var clean=!document.documentElement.classList.contains("printall"); w.print=orig; return clean; } catch(e){ return false; } })(),
    cmpTabPresent: !!cmpTab,
    cmpTabTextPresent: /SCR Comparator \(P33\)/.test(bodyText),
    cmpRegistryOrder: cmpIds0.join(",") === "frozen_t,grouped_t,skew_t,vine2,tree3,nested",
    cmpGovernedHeadlineExactKey: cmpPoints0.frozen_t === "39975.654628199336",
    cmpDefaultBaselineFrozenT: cmpDelta0.frozen_t === "zero" && /Frozen single-df t/.test((cmpRows0[0]||{textContent:""}).textContent) && /BASELINE/.test((cmpRows0[0]||{textContent:""}).textContent),
    cmpDeltaSignsDefault: cmpDelta0.grouped_t === "neg" && cmpDelta0.skew_t === "pos" && cmpDelta0.vine2 === "pos" && cmpDelta0.tree3 === "pos" && cmpDelta0.nested === "pos",
    cmpCiOverlayRendered: cmpCiSvg0 === 1 && cmpCiCircles0 >= 6,
    cmpBaselineSwitchWorks: cmpDelta1.vine2 === "zero" && cmpDelta1.frozen_t === "neg" && cmpDelta1.grouped_t === "neg" && cmpDelta1.nested === "pos" && cmpCiSvg1 === 1,
    cmpGovernedPersistsNonDefaultBaseline: /GOVERNED HEADLINE/.test(cmpText1) && /governed headline basis remains the frozen single-df t/.test(cmpText1),
    cmpBaselineRestoreWorks: cmpDelta2.frozen_t === "zero" && cmpDelta2.vine2 === "pos",
    cmpDisplayArithmeticLabelled: /display arithmetic/.test(cmpText0) && /NOT new model output/.test(cmpText0),
    cmpNothingRecomputedStated: /nothing is recomputed/.test(cmpText0),
    cmpNeutralityStated: /registry order/.test(cmpText0) && /neutral/.test(cmpText0) && /rests with the owner/.test(cmpText0),
    cmpNoSteeringLanguage: !/recommended structure|should adopt|we recommend|best structure/i.test(cmpText0),
    cmpProvenanceRows: cmpProvRows === 6,
    cmpNestedPointOnly: /no bootstrap CI embedded/.test(cmpText0),

    embeddedParsed: /contract v\d/.test(bodyText),
    tabCount: tabs.length,
    inventoryRows: document.querySelectorAll("#invtable tbody tr").length,
    inventoryFilter: !!document.getElementById("invq") && !!document.getElementById("invcat"),
    contractSchemaPresent: /ui_data\.json -- stable offline UI contract/.test(bodyText),
    calibrationGates: document.querySelectorAll("#calibrations .gate").length,
    glapsePresent: /G-LAPSE/.test(bodyText),
    gswpnPresent: /G-SWPN/.test(bodyText),
    calibDrivers: calibBtns.length,
    calibPanels: document.querySelectorAll("#calibrations .calibpanel").length,
    calibCharts,
    calibCrit,
    calibParamRows,
    capitalCards: document.querySelectorAll("#capital .card").length,
    capitalSubnavBtns: segBtns.length,
    capitalSvgCharts: document.querySelectorAll("#capital svg.chart").length,
    driverBars,
    capitalTipElems: document.querySelectorAll("#capital [data-tip]").length,
    g2ppCapitalPresent: /G2\+\+ two-factor rates/.test(bodyText),
    gmartVerdictPresent: /G-MART market-consistency gate/.test(bodyText),
    gfxPresent: /G-FX/.test(bodyText),
    gliqPresent: /G-LIQ/.test(bodyText),
    sevenDriverCapitalPresent: /Seven-driver economic-capital aggregation/.test(bodyText),
    sevenDriverVerdictPresent: /Seven-driver (tail-dependent capital aggregation|capital aggregation \(G-LIQX-CALIBRATED)/.test(bodyText),
    oosPartialVerdictPresent: /Six-driver OOS proxy validation/.test(bodyText),
    gliqxPanelPresent: /G-LIQX/.test(bodyText),
    oosRemediatedPresent: /REMEDIATED, Phase 22 Task 1/.test(bodyText),
    sevenDriverOosPassPresent: /Seven-driver OOS proxy validation/.test(bodyText),
    calibratedLiquidityPresent: /G-LIQX-CALIBRATED/.test(bodyText),
    fxScrCardPresent: /FX SCR/.test(bodyText),
    liquidityScrCardPresent: /Liquidity SCR/.test(bodyText),
    nestedDisclosurePresent: /Honest small-sample disclosure/.test(bodyText),
    governancePresent: /Audit integrity/.test(bodyText),
    govSubnavBtns: govBtns.length,
    govGateCards,
    govRiskRows,
    govRiskRowsFiltered,
    govRiskFilterWorks: govRiskRowsFiltered > 0 && govRiskRowsFiltered <= govRiskRows,
    govHeatCells,
    govChangeItems,
    govSignoff,
    govAuditBadge,
    // Phase 32 Task 4 (gap G3): governance-store completeness sweep.
    govStoreSyncCards,
    govStoreSyncPanel: /Governance-store sync \(Phase 32 Task 4/.test(govAuditText),
    govStoreSyncPresent: !!(g3ss && g3ss.source === ".claude-dev/GOVERNANCE_STORE.json"),
    govSupplementPresent: g3supp.length >= 1,
    govSupplementNoOverlap: g3overlap === 0,
    govSweepTotalsConsistent: g3ss.change_records_store_total === (g3embedded.length + g3supp.length)
      && g3ss.change_records_supplemented === g3supp.length
      && g3ss.change_records_embedded === g3embedded.length
      && g3statusTotal === g3ss.change_records_store_total,
    govTimelineComplete: govChangeItems === (g3embedded.length + g3supp.length),
    govSyncBadgesRendered: govSyncBadges >= g3supp.length,
    govChangesCsvComplete: chgCsvRows >= (g3embedded.length + g3supp.length),
    toolbarPresent: !!toolbar,
    exportBtns,
    invCsvHasHeader: /(^|,)sha256(,|$)/.test((invCSV.split("\r\n")[0]||"")),
    invCsvRows, riskCsvRows, chgCsvRows,
    tablistRoles, tabRoleCount, ariaSelectedTabs, segTabRoles,
    printCssPresent, dataTitlePanels,
    managementTabPresent: !!maTab,
    maCards, maGateCrits, maBarRects, maTrigRows, maStandaloneRows, maRuleRows,
    mgmtRulePresent: /reversionary-bonus/.test(bodyText),
    withActionsNestedPresent: /33,11[78]/.test(bodyText),
    tCopulaDfPresent: /2\.9451/.test(bodyText),
    saturationFindingPresent: /saturates/.test(bodyText),
    tCopulaVerdictPresent: /Student-t copula aggregation/.test(bodyText),
    withActionsVerdictPresent: /WITH management actions/.test(bodyText),
    phase24TabPresent: !!p24Tab,
    p24Cards, p24GateCrits, p24DeltaRows, p24SweepRows, p24InnerRows, p24BarRects,
    jointActionScrPresent: /31,00[12]/.test(bodyText),
    saturationGapClosurePresent: /22\.54% to 6\.39%/.test(bodyText),
    tailSaturationPresent: /100\.0% saturated/.test(bodyText),
    bootstrapCiPresent: /26,471/.test(bodyText) && /33,637/.test(bodyText),
    innerPathDeltaPresent: /inner-path basis is the more conservative/.test(bodyText),
    varCovarRefreshPresent: /56\.4%/.test(bodyText),
    jointActionVerdictPresent: /action-after-aggregation t-copula/.test(bodyText),
    innerPathVerdictPresent: /Inner-path management-action dynamics/.test(bodyText),
    phase25TabPresent: !!p25Tab,
    p25Cards, p25GateCrits, p25DeltaRows, p25SweepRows, p25ProxyRows, p25BarRects,
    pathwiseScrPresent: /46,639/.test(bodyText),
    pathwiseDeltaPresent: /\+14\.17%/.test(bodyText),
    pathwiseRelievesLessPresent: /relieves LESS/.test(bodyText),
    restorationSharePresent: /29\.4%/.test(bodyText),
    varCovarPathwiseRefreshPresent: /69\.1%/.test(bodyText),
    bootstrapOutsideCiPresent: /35,793/.test(bodyText) && /42,496/.test(bodyText) && /OUTSIDE/.test(bodyText),
    copulaFrozenPresent: /FROZEN/.test(bodyText),
    pathwiseDeclVerdictPresent: /Path-wise bonus declaration in the nested truth/.test(bodyText),
    pathwiseProxyVerdictPresent: /Matching path-wise proxy basis/.test(bodyText),
    pathwiseTailVerdictPresent: /Path-wise tail diagnostics/.test(bodyText),
    phase26TabPresent: !!p26Tab,
    p26Cards, p26GateCrits, p26MatrixRows, p26DeltaRows, p26GapRows, p26BarRects,
    componentScrPresent: /39,976/.test(bodyText) && /39,595/.test(bodyText),
    componentBootstrapCiPresent: /36,676/.test(bodyText) && /42,943/.test(bodyText),
    copulaFormGapPresent: /91\.9%/.test(bodyText) && /COPULA-FORM/.test(bodyText),
    gapToNestedPresent: /14\.29%/.test(bodyText),
    compositionImmaterialPresent: /ECONOMICALLY IMMATERIAL/.test(bodyText),
    mr015FreePresent: /MR-015/.test(bodyText),
    nestedOutsideComponentCiPresent: /OUTSIDE/.test(bodyText),
    reaggCompositionVerdictPresent: /per-driver composition transform/.test(bodyText),
    reaggBootstrapVerdictPresent: /frozen-copula margin bootstrap \+ gap decomposition/.test(bodyText),
    reaggDeltaVerdictPresent: /paired full-vs-reanchored delta matrix/.test(bodyText),
    phase28TabPresent: !!p28Tab,
    p28Cards, p28GateCrits, p28TailRows, p28GapRows, p28BarRects,
    groupedTailTabTextPresent: /Grouped-t Tail \(P28\)/.test(bodyText),
    groupedScrPresent: /35,372/.test(bodyText) && /35,604/.test(bodyText),
    groupedBootstrapCiPresent: /33,034/.test(bodyText) && /38,009/.test(bodyText),
    singleDfScrPresent: /39,595/.test(bodyText) && /39,976/.test(bodyText),
    nestedP28Present: /46,639/.test(bodyText),
    crossBlockDilutionPresent: /-0\.0871/.test(bodyText),
    residualWideningPresent: /10,491/.test(bodyText) && /6,115/.test(bodyText),
    blockDfPresent: /37\.866/.test(bodyText) && /8\.506/.test(bodyText),
    mr016Present: /MR-016/.test(bodyText),
    vineEscalationPresent: /vine \/ pair-copula/.test(bodyText),
    phase29TabPresent: !!p29Tab,
    p29Cards, p29GateCrits, p29PairRows, p29GapRows, p29BarRects,
    vineTailTabTextPresent: /Vine Tail \(P29\)/.test(bodyText),
    vineScrPresent: /42,459/.test(bodyText) && /41,918/.test(bodyText),
    vineBootstrapCiPresent: /38,655/.test(bodyText) && /45,284/.test(bodyText),
    vineNestedOutsidePresent: /OUTSIDE/.test(bodyText) && /46,639/.test(bodyText),
    vineResidualNarrowingPresent: /-65\.33%/.test(bodyText) && /-40\.52%/.test(bodyText),
    vineRateLiquidityLiftPresent: /\+0\.8514/.test(bodyText),
    vineOverfitRatioPresent: /0\.049/.test(bodyText),
    vineFrozenHeadlinePresent: /39,976/.test(bodyText),
    mr017Present: /MR-017/.test(bodyText),
    vineNotAdoptedPresent: /NOT adopted/.test(bodyText),
    phase30TabPresent: !!p30Tab,
    p30Cards, p30GateCrits, p30PairRows, p30EdgeRows, p30GapRows, p30BarRects,
    stopRuleTabTextPresent: /Stop-Rule \(P30\)/.test(bodyText),
    p30StopRuleAppliedPresent: /STOP-RULE/.test(p30Text) && /escalation ENDS/.test(p30Text),
    p30Tree3ScrPresent: /42,459/.test(p30Text) && /41,752/.test(p30Text),
    p30BootstrapCiPresent: /38,594/.test(p30Text) && /44,556/.test(p30Text),
    p30NestedOutsidePresent: /OUTSIDE/.test(p30Text) && /46,639/.test(p30Text),
    p30ZeroStrengthPresent: /zero-strength/.test(p30Text),
    p30Mr016KeepOpenPresent: /MR-016/.test(p30Text) && /KEEP OPEN/.test(p30Text),
    p30Mr017Present: /MR-017/.test(p30Text),
    p30Phase31Present: /Phase 31/.test(p30Text) && /OWNER DECISION PACKAGE/i.test(p30Text),
    p30GovernedHeadlinePresent: /39,976/.test(p30Text) && /0\.0000%/.test(p30Text),
    p30OverfitRatioPresent: /0\.049/.test(p30Text),
    ownerDecisionTabPresent: !!odTab,
    odCards, odOptionCards, odLadderRows, odHistRows, odWfRows, odDrRows,
    odProvRows, odBarRects,
    odTabTextPresent: /Owner Decision \(P31\)/.test(bodyText),
    odGovernedHeadlinePresent: /39,976/.test(odText),
    odVine2PointPresent: /42,459/.test(odText) && /41,918/.test(odText),
    odTree3MeanPresent: /41,752/.test(odText),
    odVine2CiPresent: /38,655/.test(odText) && /45,284/.test(odText),
    odTree3CiPresent: /38,594/.test(odText) && /44,556/.test(odText),
    odNestedPresent: /46,639/.test(odText),
    odResidualPresent: /3,637/.test(odText),
    odCapitalEffectPresent: /2,483/.test(odText),
    odOptionsRegistryOrder: odO1 >= 0 && odO2 > odO1 && odO3 > odO2,
    odNoDefaultPresent: /NO default/.test(odText),
    odDecisionBlankCount: odBlankChips,
    odStopRulePresent: /escalation ENDS/.test(odText),
    odMrOpenPresent: /MR-016/.test(odText) && /MR-017/.test(odText),
    odSingleRunCaveatPresent: /SINGLE run/.test(odText),
    userRunTabPresent: !!urTab,
    urCards, urScrRows, urCiRows, urPlanRows, urPfRows, urProvRows, urBarRects,
    urTabTextPresent: /User Run \(UIL\)/.test(bodyText),
    urRunLabelPresent: /WorkedExample_TemplateDemoBook/.test(urText),
    urNestedScrPresent: /71,112/.test(urText),
    urCopulaScrPresent: /49,826/.test(urText) && /gaussian/.test(urText),
    urVarCovarScrPresent: /37,626/.test(urText),
    urLapseScrPresent: /30,360/.test(urText),
    urEquityScrPresent: /21,207/.test(urText),
    urVarCiPresent: /192,141/.test(urText) && /191,055/.test(urText) && /193,042/.test(urText),
    urEsgUnderstatementPresent: /0\.47%/.test(urText),
    urVerdictPresent: /REVIEW/.test(urText),
    urSeedPresent: /20260608/.test(urText),
    urModelPointCountsPresent: /2 PAR rows \(1 GMMB row/.test(urText),
    urInputChainPresent: /model_inputs\.json/.test(urText) && /par_model_v2\.user_inputs loader/.test(urText) && /run_model/.test(urText),
    urCurrencySourceStamped: uiMeta.currency_source ? urText.indexOf(uiMeta.currency_source) >= 0 : false,
    urOutputLabelStamped: uiMeta.output_label ? urText.indexOf(uiMeta.output_label) >= 0 : false,
    urDigestPresent: /48bc9c19/.test(urText),
    urBookScalingDisclosedPresent: /DISCLOSED APPROXIMATION/.test(urText),
    urFrozenDependencePresent: /never user-settable/.test(urText),
    urNothingRecomputedPresent: /recomputes NOTHING/.test(urText),
    currencyMetaStamped: !!(uiMeta.currency && ("currency_source" in uiMeta) && ("output_label" in uiMeta)),
    fmtMoneyDefined: /function fmtMoney\(/.test(html),
    moneySymbolRendered: moneyRe ? moneyRe.test(bodyText) : true,
    currencyBadgePresent: curCfg.code ? (new RegExp("currency " + curCfg.code)).test(bodyText) : true,
    // Phase 34 Task 2 (gap H1): self-describing data-contract guard.
    h1IntegrityTabPresent: !!intTab,
    h1IntegrityTabText: /Data-contract integrity/.test(intText),
    h1ContractIs120: !!uiDataObj && uiDataObj.contract_version === "1.20.0",
    // Phase 35 Task 3 (gap A2): content-integrity digests + in-browser verifier
    a2DigestsPresent,
    a2DigestsHex,
    a2DigestsCoverAllSections,
    a2VerifierTableRendered,
    a2AllSectionsVerified,
    a2RootDigestShown,
    a2HelpersEmbedded,
    a2NoNetworkStated,
    h1ManifestEmbedded: !!intManifest && intManifest.expected_contract_version === uiDataObj.contract_version &&
      Array.isArray(intManifest.required_top_level_keys) && intManifest.required_top_level_keys.length >= 20,
    h1ManifestExcludesItself: !!intManifest && intManifest.required_top_level_keys.indexOf("contract_manifest") === -1,
    h1ManifestKeysAllPresent: !!intManifest &&
      intManifest.required_top_level_keys.every(k => Object.prototype.hasOwnProperty.call(uiDataObj, k)),
    h1IntegrityKeyRows: !!intManifest && intKeyRows === intManifest.required_top_level_keys.length,
    h1ValidatorPassOnFullPayload: /PASS/.test(intText) && intAbsentRows === 0,
    h1VersionMatchShown: !!uiDataObj && intText.indexOf(uiDataObj.contract_version) >= 0,
    h1BannerHiddenOnFullPayload: !intBannerVisible,
    h1DisplayOnlyStated: /recomputes no model figure/.test(intText) && /[Nn]othing is recomputed in the browser/.test(intText),
    h2SearchBoxPresent,
    h2DlIdsAssigned,
    h2HitForGovernedHeadline,
    h2JumpActivatesTab,
    h2HashCarriesSection,
    h2HeadlineNeverRelabelled,
    h2DeepLinkTabSection,
    h2DeepLinkPlainTabStillWorks,
    h2NoStorageApis,
    h4ResponsiveMediaPresent,
    h4ResponsiveTableScroll,
    h4ReducedMotionPresent,
    h4HighContrastThemePresent,
    h4ToggleButtonPresent,
    h4ToggleAppliesClass,
    h4ToggleWritesHash,
    h4ToggleAriaPressed,
    h4ToggleRemovesClass,
    h4ToggleClearsHash,
    h4RestoreFromHash,
    h4FlagDoesNotBreakTabRouting,
    h4NoStorageApis,
    // Phase 35 Task 2 (gap A1): WCAG 2.1 AA keyboard + contrast pass
    a1FocusVisibleComprehensive,
    a1AuditEmbedded,
    a1PairsBothThemes,
    a1AllPairsPassAA,
    a1KeyboardInventory,
    a1FocusVisibleSelectorsListed,
    a1ContrastTableRendered,
    a1KeyboardTableRendered,
    a1DisplayOnlyStated,
    a1A11yTables,
    networkCalls: networkCalls.length,
    jsErrors: errors.length,
  };
  const ok =
    checks.embeddedParsed &&
    checks.tabCount >= 5 &&
    checks.inventoryRows >= 20 &&
    checks.inventoryFilter &&
    checks.contractSchemaPresent &&
    checks.calibrationGates >= 4 &&
    checks.glapsePresent &&
    checks.gswpnPresent &&
    checks.calibDrivers >= 8 &&
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
    checks.gliqxPanelPresent &&
    checks.oosRemediatedPresent &&
    checks.sevenDriverOosPassPresent &&
    checks.calibratedLiquidityPresent &&
    checks.fxScrCardPresent &&
    checks.liquidityScrCardPresent &&
    checks.nestedDisclosurePresent &&
    checks.governancePresent &&
    checks.govSubnavBtns === 4 &&
    checks.govGateCards >= 5 &&
    checks.govRiskRows >= 5 &&
    checks.govRiskFilterWorks &&
    checks.govHeatCells >= 25 &&
    checks.govChangeItems >= 5 &&
    checks.govSignoff >= 1 &&
    checks.govAuditBadge >= 1 &&
    checks.govStoreSyncCards >= 5 &&
    checks.govStoreSyncPanel &&
    checks.govStoreSyncPresent &&
    checks.govSupplementPresent &&
    checks.govSupplementNoOverlap &&
    checks.govSweepTotalsConsistent &&
    checks.govTimelineComplete &&
    checks.govSyncBadgesRendered &&
    checks.govChangesCsvComplete &&
    checks.toolbarPresent &&
    checks.exportBtns === 5 &&
    checks.invCsvHasHeader &&
    checks.invCsvRows >= 21 &&
    checks.riskCsvRows >= 13 &&
    checks.chgCsvRows >= 19 &&
    checks.tablistRoles >= 1 &&
    checks.tabRoleCount >= 5 &&
    checks.ariaSelectedTabs === 1 &&
    checks.segTabRoles >= 4 &&
    checks.printCssPresent &&
    checks.dataTitlePanels >= 6 &&
    checks.managementTabPresent &&
    checks.maCards >= 6 &&
    checks.maGateCrits >= 9 &&
    checks.maBarRects >= 8 &&
    checks.maTrigRows >= 3 &&
    checks.maStandaloneRows >= 7 &&
    checks.maRuleRows >= 6 &&
    checks.mgmtRulePresent &&
    checks.withActionsNestedPresent &&
    checks.tCopulaDfPresent &&
    checks.saturationFindingPresent &&
    checks.tCopulaVerdictPresent &&
    checks.withActionsVerdictPresent &&
    checks.phase24TabPresent &&
    checks.p24Cards >= 12 &&
    checks.p24GateCrits >= 12 &&
    checks.p24DeltaRows === 4 &&
    checks.p24SweepRows === 5 &&
    checks.p24InnerRows === 2 &&
    checks.p24BarRects >= 7 &&
    checks.jointActionScrPresent &&
    checks.saturationGapClosurePresent &&
    checks.tailSaturationPresent &&
    checks.bootstrapCiPresent &&
    checks.innerPathDeltaPresent &&
    checks.varCovarRefreshPresent &&
    checks.jointActionVerdictPresent &&
    checks.innerPathVerdictPresent &&
    checks.phase25TabPresent &&
    checks.p25Cards >= 12 &&
    checks.p25GateCrits >= 15 &&
    checks.p25DeltaRows === 4 &&
    checks.p25SweepRows === 5 &&
    checks.p25ProxyRows >= 8 &&
    checks.p25BarRects >= 8 &&
    checks.pathwiseScrPresent &&
    checks.pathwiseDeltaPresent &&
    checks.pathwiseRelievesLessPresent &&
    checks.restorationSharePresent &&
    checks.varCovarPathwiseRefreshPresent &&
    checks.bootstrapOutsideCiPresent &&
    checks.copulaFrozenPresent &&
    checks.pathwiseDeclVerdictPresent &&
    checks.pathwiseProxyVerdictPresent &&
    checks.pathwiseTailVerdictPresent &&
    checks.phase26TabPresent &&
    checks.p26Cards >= 12 &&
    checks.p26GateCrits >= 15 &&
    checks.p26MatrixRows === 3 &&
    checks.p26DeltaRows === 5 &&
    checks.p26GapRows === 3 &&
    checks.p26BarRects >= 5 &&
    checks.componentScrPresent &&
    checks.componentBootstrapCiPresent &&
    checks.copulaFormGapPresent &&
    checks.gapToNestedPresent &&
    checks.compositionImmaterialPresent &&
    checks.mr015FreePresent &&
    checks.nestedOutsideComponentCiPresent &&
    checks.reaggCompositionVerdictPresent &&
    checks.reaggBootstrapVerdictPresent &&
    checks.reaggDeltaVerdictPresent &&
    checks.phase28TabPresent &&
    checks.p28Cards >= 12 &&
    checks.p28GateCrits >= 20 &&
    checks.p28TailRows === 4 &&
    checks.p28GapRows === 4 &&
    checks.p28BarRects >= 8 &&
    checks.groupedTailTabTextPresent &&
    checks.groupedScrPresent &&
    checks.groupedBootstrapCiPresent &&
    checks.singleDfScrPresent &&
    checks.nestedP28Present &&
    checks.crossBlockDilutionPresent &&
    checks.residualWideningPresent &&
    checks.blockDfPresent &&
    checks.mr016Present &&
    checks.vineEscalationPresent &&
    checks.phase29TabPresent &&
    checks.p29Cards >= 12 &&
    checks.p29GateCrits >= 19 &&
    checks.p29PairRows === 14 &&
    checks.p29GapRows === 4 &&
    checks.p29BarRects >= 6 &&
    checks.vineTailTabTextPresent &&
    checks.vineScrPresent &&
    checks.vineBootstrapCiPresent &&
    checks.vineNestedOutsidePresent &&
    checks.vineResidualNarrowingPresent &&
    checks.vineRateLiquidityLiftPresent &&
    checks.vineOverfitRatioPresent &&
    checks.vineFrozenHeadlinePresent &&
    checks.mr017Present &&
    checks.vineNotAdoptedPresent &&
    checks.phase30TabPresent &&
    checks.p30Cards >= 10 &&
    checks.p30GateCrits >= 22 &&
    checks.p30PairRows === 18 &&
    checks.p30EdgeRows === 4 &&
    checks.p30GapRows === 4 &&
    checks.p30BarRects >= 6 &&
    checks.stopRuleTabTextPresent &&
    checks.p30StopRuleAppliedPresent &&
    checks.p30Tree3ScrPresent &&
    checks.p30BootstrapCiPresent &&
    checks.p30NestedOutsidePresent &&
    checks.p30ZeroStrengthPresent &&
    checks.p30Mr016KeepOpenPresent &&
    checks.p30Mr017Present &&
    checks.p30Phase31Present &&
    checks.p30GovernedHeadlinePresent &&
    checks.p30OverfitRatioPresent &&
    checks.ownerDecisionTabPresent &&
    checks.odCards >= 12 &&
    checks.odOptionCards === 3 &&
    checks.odLadderRows === 4 &&
    checks.odHistRows === 5 &&
    checks.odWfRows === 6 &&
    checks.odDrRows === 6 &&
    checks.odProvRows >= 7 &&
    checks.odBarRects >= 5 &&
    checks.odTabTextPresent &&
    checks.odGovernedHeadlinePresent &&
    checks.odVine2PointPresent &&
    checks.odTree3MeanPresent &&
    checks.odVine2CiPresent &&
    checks.odTree3CiPresent &&
    checks.odNestedPresent &&
    checks.odResidualPresent &&
    checks.odCapitalEffectPresent &&
    checks.odOptionsRegistryOrder &&
    checks.odNoDefaultPresent &&
    checks.odDecisionBlankCount === 6 &&
    checks.odStopRulePresent &&
    checks.odMrOpenPresent &&
    checks.odSingleRunCaveatPresent &&
    checks.userRunTabPresent &&
    checks.urCards >= 8 &&
    checks.urScrRows === 7 &&
    checks.urCiRows === 4 &&
    checks.urPlanRows === 9 &&
    checks.urPfRows >= 8 &&
    checks.urProvRows === 8 &&
    checks.urBarRects >= 7 &&
    checks.urTabTextPresent &&
    checks.urRunLabelPresent &&
    checks.urNestedScrPresent &&
    checks.urCopulaScrPresent &&
    checks.urVarCovarScrPresent &&
    checks.urLapseScrPresent &&
    checks.urEquityScrPresent &&
    checks.urVarCiPresent &&
    checks.urEsgUnderstatementPresent &&
    checks.urVerdictPresent &&
    checks.urSeedPresent &&
    checks.urModelPointCountsPresent &&
    checks.urInputChainPresent &&
    checks.urCurrencySourceStamped &&
    checks.urOutputLabelStamped &&
    checks.urDigestPresent &&
    checks.urBookScalingDisclosedPresent &&
    checks.urFrozenDependencePresent &&
    checks.urNothingRecomputedPresent &&
    checks.currencyMetaStamped &&
    checks.fmtMoneyDefined &&
    checks.moneySymbolRendered &&
    checks.currencyBadgePresent &&
    checks.cmpTabPresent &&
    checks.cmpTabTextPresent &&
    checks.cmpRegistryOrder &&
    checks.cmpGovernedHeadlineExactKey &&
    checks.cmpDefaultBaselineFrozenT &&
    checks.cmpDeltaSignsDefault &&
    checks.cmpCiOverlayRendered &&
    checks.cmpBaselineSwitchWorks &&
    checks.cmpGovernedPersistsNonDefaultBaseline &&
    checks.cmpBaselineRestoreWorks &&
    checks.cmpDisplayArithmeticLabelled &&
    checks.cmpNothingRecomputedStated &&
    checks.cmpNeutralityStated &&
    checks.cmpNoSteeringLanguage &&
    checks.cmpProvenanceRows &&
    checks.cmpNestedPointOnly &&
    checks.dxTabPresent &&
    checks.dxTabTextPresent &&
    checks.dxGridEmbedded &&
    checks.dxCdfMonotoneEnds &&
    checks.dxProvenanceEmbedded &&
    checks.dxCdfSvgRendered &&
    checks.dxCdfGridPointCount &&
    checks.dxSeedOverlayRendered &&
    checks.dxQuantileRows &&
    checks.dxArchivedPercentileRows &&
    checks.dxP50ExactArchivedKey &&
    checks.dxSweepRows &&
    checks.dxSliderReadoutWorks &&
    checks.dxZoomWorks &&
    checks.dxBuildTimeStated &&
    checks.dxInterpolationLabelled &&
    checks.dxArchivedBitForBitStated &&
    checks.dxNoFallbackInFullPayload &&
    checks.g3SignoffCoverPresent &&
    checks.g3SignoffCoverNeutralBlank &&
    checks.g3SignoffCoverHeadline &&
    checks.g3PrintCoverCssPresent &&
    checks.g3ExportButtonsPresent &&
    checks.g3GatesCsvComplete &&
    checks.g3GatesCsvBitForBit &&
    checks.g3OwnerOptionsCsvOrder &&
    checks.g3EvidenceCsvHeadlineKey &&
    checks.g3ResidualLadderCsv &&
    checks.g3EscalationHistoryCsv &&
    checks.g3StopRuleCsv &&
    checks.g3SignoffWorkflowCsv &&
    checks.g3DecisionRecordBlankPreserved &&
    checks.g3ComparatorCsvComplete &&
    checks.g3DistGridCsvComplete &&
    checks.g3SignoffPackComplete &&
    checks.g4SrOnlyCssPresent &&
    checks.g4TabpanelRoles >= 5 &&
    checks.g4TabsAriaControls >= 5 &&
    checks.g4EnterActivates &&
    checks.g4SpaceActivates &&
    checks.g4ArrowMoves &&
    checks.g4HashWritten &&
    checks.g4HashRestores &&
    checks.g4ExactlyOneSelectedAfterHash &&
    checks.g4NoStorageApis &&
    checks.g4TablesTotal >= 20 &&
    checks.g4TablesWithoutCaption === 0 &&
    checks.g4NoDuplicateCaptions &&
    checks.h1IntegrityTabPresent &&
    checks.h1IntegrityTabText &&
    checks.h1ContractIs120 &&
    checks.a2DigestsPresent &&
    checks.a2DigestsHex &&
    checks.a2DigestsCoverAllSections &&
    checks.a2VerifierTableRendered &&
    checks.a2AllSectionsVerified &&
    checks.a2RootDigestShown &&
    checks.a2HelpersEmbedded &&
    checks.a2NoNetworkStated &&
    checks.a1FocusVisibleComprehensive &&
    checks.a1AuditEmbedded &&
    checks.a1PairsBothThemes &&
    checks.a1AllPairsPassAA &&
    checks.a1KeyboardInventory &&
    checks.a1FocusVisibleSelectorsListed &&
    checks.a1ContrastTableRendered &&
    checks.a1KeyboardTableRendered &&
    checks.a1DisplayOnlyStated &&
    checks.a1A11yTables === 2 &&
    checks.h1ManifestEmbedded &&
    checks.h1ManifestExcludesItself &&
    checks.h1ManifestKeysAllPresent &&
    checks.h1IntegrityKeyRows &&
    checks.h1ValidatorPassOnFullPayload &&
    checks.h1VersionMatchShown &&
    checks.h1BannerHiddenOnFullPayload &&
    checks.h1DisplayOnlyStated &&
    checks.h2SearchBoxPresent &&
    checks.h2DlIdsAssigned >= 50 &&
    checks.h2HitForGovernedHeadline &&
    checks.h2JumpActivatesTab &&
    checks.h2HashCarriesSection &&
    checks.h2HeadlineNeverRelabelled &&
    checks.h2DeepLinkTabSection &&
    checks.h2DeepLinkPlainTabStillWorks &&
    checks.h2NoStorageApis &&
    checks.h3BundleButtonsPresent &&
    checks.h3BundleCoversAllSections &&
    checks.h3BundleHeadlineBitForBit &&
    checks.h3BundleProvenanceStamped &&
    checks.h3BundleDecisionBlank &&
    checks.h3BundleJsonValid &&
    checks.h3BundleJsonHeadlineNumberExact &&
    checks.h3BundleJsonDecisionBlank &&
    checks.h3PrintAllCssPresent &&
    checks.h3PrintAllButtonNoThrow &&
    checks.h4ResponsiveMediaPresent &&
    checks.h4ResponsiveTableScroll &&
    checks.h4ReducedMotionPresent &&
    checks.h4HighContrastThemePresent &&
    checks.h4ToggleButtonPresent &&
    checks.h4ToggleAppliesClass &&
    checks.h4ToggleWritesHash &&
    checks.h4ToggleAriaPressed &&
    checks.h4ToggleRemovesClass &&
    checks.h4ToggleClearsHash &&
    checks.h4RestoreFromHash &&
    checks.h4FlagDoesNotBreakTabRouting &&
    checks.h4NoStorageApis &&
    checks.networkCalls === 0 &&
    checks.jsErrors === 0;
  done(ok, checks);
}, 400);
