// Phase 34 Task 4 (gap H3) - dedicated self-test for the one-click full evidence
// bundle export and the print-all sign-off pack. Loads ui_app.html under jsdom
// (network blocked) and asserts the pre-registered acceptance criteria:
//   * a single action exports EVERY governed read-out into one provenance-stamped
//     bundle (CSV multi-section + JSON), covering all 13 governed sections;
//   * every value is bit-for-bit from the embedded snapshot - the governed frozen-t
//     headline 39975.654628199336 is carried exactly (string in CSV, exact Number in
//     JSON) and is never re-labelled;
//   * the bundle is provenance-stamped (contract version + build stamp + headline) and
//     the decision record is exported BLANK (owner decision not pre-empted);
//   * owner options stay in registry order;
//   * a print-all mode lays out all governed surfaces (CSS present; the button toggles
//     html.printall on during print and clears it after) and adds NO external resource;
//   * NO storage APIs (file:// safe); ZERO network calls and ZERO JS errors.
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
    window.fetch = (...args) => { networkCalls.push(["fetch", String(args[0])]); return Promise.reject(new Error("offline self-test blocked fetch")); };
    window.XMLHttpRequest = class OfflineBlockedXHR { open(_m, url){ networkCalls.push(["xhr", String(url)]); } send(){ throw new Error("offline self-test blocked XMLHttpRequest"); } };
  },
});

const done = (ok, checks) => {
  console.log(JSON.stringify({ ok, checks, errors, networkCalls }, null, 2));
  process.exit(ok ? 0 : 1);
};

setTimeout(() => {
  const { window } = dom;
  const { document } = window;
  const ux = window.__uiExport || {};
  const call = (fn) => (typeof ux[fn] === "function" ? ux[fn]() : "");

  const bundleCSV = call("evidenceBundleCSV");
  const bundleJSON = call("evidenceBundleJSON");
  let json = null; try { json = JSON.parse(bundleJSON); } catch (e) {}

  const headers = ["## Inventory","## Risk register","## Change records","## Deployment gates",
    "## Owner options","## Evidence pack","## Copula-form residual ladder","## Dependence-form escalation history",
    "## Binding stop-rule record","## Sign-off workflow","## SCR comparator","## Distribution grid","## Decision record"];

  // code-only view (strip embedded data) for static guards
  const codeOnly = html.replace(/<script id="ui-data"[^>]*>[\s\S]*?<\/script>/, "");
  const noStorageApis = !/\blocalStorage\b/.test(codeOnly) && !/\bsessionStorage\b/.test(codeOnly);
  const noExternalRefs = (codeOnly.match(/(src|href)\s*=\s*["']https?:/g) || []).length === 0;

  // owner-options registry order (first governed option id)
  const optsCSV = call("ownerOptionsCSV");
  const optsRows = optsCSV ? optsCSV.split("\r\n") : [];
  const optsFirstId = optsRows.length > 1 ? optsRows[1].split(",")[1] : "";

  // print-all toggle: stub print, capture class state DURING the call, verify cleared AFTER
  let classOnDuringPrint = false, classClearedAfter = false, printAllNoThrow = false;
  try {
    const orig = window.print;
    window.print = function(){ classOnDuringPrint = document.documentElement.classList.contains("printall"); };
    const b = document.getElementById("btnPrintAll");
    if (b) b.click();
    classClearedAfter = !document.documentElement.classList.contains("printall");
    window.print = orig;
    printAllNoThrow = true;
  } catch (e) { printAllNoThrow = false; }

  const decRows = bundleCSV.split("\r\n").filter(r => /BLANK - awaiting owner decision/.test(r));

  const checks = {
    bundleButtonsPresent: !!document.getElementById("btnBundleCsv") && !!document.getElementById("btnBundleJson") && !!document.getElementById("btnPrintAll"),
    registryExportsPresent: typeof ux.evidenceBundleCSV === "function" && typeof ux.evidenceBundleJSON === "function",
    bundleCsvAllSections: headers.every(h => bundleCSV.indexOf(h) !== -1),
    bundleSectionCount13: !!json && Array.isArray(json.section_order) && json.section_order.length === 13 && Object.keys(json.sections_csv).length === 13,
    bundleProvenanceStamped: /# Provenance: contract v/.test(bundleCSV) && /build\/generated/.test(bundleCSV) && /Governed component SCR headline/.test(bundleCSV),
    bundleProvenanceJson: !!json && !!json.provenance && json.provenance.contract_version != null && json.provenance.build_stamp != null,
    headlineBitForBitCsv: /# Governed component SCR headline \(frozen single-df t\): 39975\.654628199336/.test(bundleCSV),
    headlineBitForBitJson: !!json && json.provenance.governed_headline.value === 39975.654628199336,
    // The governed headline is carried at full precision and never re-labelled: the dedicated
    // headline provenance line holds the exact value, and the exact value recurs (evidence pack,
    // comparator) bit-for-bit. (Rounded forms like "39,975.7" that appear inside the snapshot's
    // risk-register prose are part of the embedded data, carried verbatim - not a re-labelling.)
    headlineNeverRelabelled: /# Governed component SCR headline \(frozen single-df t\): 39975\.654628199336/.test(bundleCSV) && (bundleCSV.match(/39975\.654628199336/g) || []).length >= 2,
    decisionRecordBlankCsv: /## Decision record \(BLANK until the owner decides\)/.test(bundleCSV) && decRows.length >= 1,
    decisionRecordBlankJson: !!json && /BLANK - awaiting owner decision/.test(json.sections_csv.decision_record),
    ownerOptionsRegistryOrder: optsFirstId === "O1_adopt_disclosed_vine_readout" && bundleCSV.indexOf("## Owner options (registry order)") !== -1,
    noRecomputeStated: /Nothing in this bundle is recomputed/.test(bundleCSV),
    printAllCssPresent: /html\.printall \.panel\{display:block !important\}/.test(html) && /html\.printall \.calibpanel,html\.printall \.capview,html\.printall \.govview\{display:block !important\}/.test(html),
    printAllTogglesClassDuringPrint: classOnDuringPrint === true,
    printAllClearsClassAfter: classClearedAfter === true,
    printAllNoThrow: printAllNoThrow,
    noStorageApis: noStorageApis,
    noExternalRefs: noExternalRefs,
    networkCalls: networkCalls.length,
    jsErrors: errors.length,
  };

  const ok =
    checks.bundleButtonsPresent &&
    checks.registryExportsPresent &&
    checks.bundleCsvAllSections &&
    checks.bundleSectionCount13 &&
    checks.bundleProvenanceStamped &&
    checks.bundleProvenanceJson &&
    checks.headlineBitForBitCsv &&
    checks.headlineBitForBitJson &&
    checks.headlineNeverRelabelled &&
    checks.decisionRecordBlankCsv &&
    checks.decisionRecordBlankJson &&
    checks.ownerOptionsRegistryOrder &&
    checks.noRecomputeStated &&
    checks.printAllCssPresent &&
    checks.printAllTogglesClassDuringPrint &&
    checks.printAllClearsClassAfter &&
    checks.printAllNoThrow &&
    checks.noStorageApis &&
    checks.noExternalRefs &&
    checks.networkCalls === 0 &&
    checks.jsErrors === 0;
  done(ok, checks);
}, 400);
