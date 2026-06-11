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

  // Phase UIL Task 4 (B4+A1): currency wire-through assertions.
  // Parse the embedded contract to learn the configured currency, then assert
  // the GUI actually renders money with that symbol and shows the badge.
  let uiMeta = {};
  try {
    const rawData = (document.getElementById("ui-data").textContent || "")
      .replace("/*__UI_DATA__*/", "").trim();
    uiMeta = (JSON.parse(rawData) || {}).meta || {};
  } catch (e) { /* leave uiMeta empty; checks below will fail loudly */ }
  const curCfg = uiMeta.currency || {};
  const symEsc = curCfg.symbol
    ? curCfg.symbol.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") : null;
  const moneyRe = symEsc ? new RegExp(symEsc + "[0-9][0-9,]*") : null;
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
    currencyMetaStamped: !!(uiMeta.currency && ("currency_source" in uiMeta) && ("output_label" in uiMeta)),
    fmtMoneyDefined: /function fmtMoney\(/.test(html),
    moneySymbolRendered: moneyRe ? moneyRe.test(bodyText) : true,
    currencyBadgePresent: curCfg.code ? (new RegExp("currency " + curCfg.code)).test(bodyText) : true,
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
    checks.currencyMetaStamped &&
    checks.fmtMoneyDefined &&
    checks.moneySymbolRendered &&
    checks.currencyBadgePresent &&
    checks.networkCalls === 0 &&
    checks.jsErrors === 0;
  done(ok, checks);
}, 400);
