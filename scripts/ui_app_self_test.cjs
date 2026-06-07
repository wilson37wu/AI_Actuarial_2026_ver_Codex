// Offline self-test for ui_app.html (UI Tasks 1-5 + Phase 21-24 propagation).
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
  const checks = {
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
    checks.networkCalls === 0 &&
    checks.jsErrors === 0;
  done(ok, checks);
}, 400);
