// Phase 33 Task 3 (gap G2) - graceful-fallback self-test for the
// Distribution Explorer (P33) panel. Strips the distribution_explorer
// section from the embedded ui_data contract (simulates an OLDER,
// pre-1.17.0 payload), re-loads ui_app.html under jsdom (network blocked),
// and asserts the pre-registered fallback criterion: NO JS errors, NO
// network calls, NO blank panel - the tab renders a neutral explanatory
// message, no grid figures leak, and every pre-existing tab still renders.
const fs = require("fs");
const path = require("path");
const { JSDOM, VirtualConsole } = require("jsdom");

const htmlPath = process.argv[2] || path.join(process.cwd(), "ui_app.html");
let html = fs.readFileSync(htmlPath, "utf8");

// Strip distribution_explorer from the embedded contract (simulates an
// older ui_data payload built before contract 1.17.0).
const m = html.match(/\/\*__UI_DATA__\*\/(.*?)<\/script>/s);
if (!m) { console.log(JSON.stringify({ ok: false, error: "no embedded data" })); process.exit(1); }
const data = JSON.parse(m[1]);
delete data.distribution_explorer;
html = html.replace(m[1], JSON.stringify(data));

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

setTimeout(() => {
  const { document } = dom.window;
  const tabs = [...document.querySelectorAll(".tab")];
  tabs.forEach(t => t.click());
  const dxTab = tabs.find(t => t.getAttribute("data-target") === "distexplorer");
  if (dxTab) dxTab.click();
  const dxEl = document.getElementById("distexplorer");
  const dxText = (dxEl && dxEl.textContent) || "";
  const bodyText = document.body.textContent || "";
  const checks = {
    dxTabPresent: !!dxTab,
    panelNotBlank: dxText.trim().length > 50,
    fallbackMessagePresent:
      /Distribution drill-down grids are not embedded in this snapshot/.test(dxText) &&
      /pre-1\.17\.0/.test(dxText),
    fallbackNeutral: /governed read-outs in the other tabs are unaffected/.test(dxText),
    nothingRecomputedStated: /nothing is recomputed in the browser/.test(dxText),
    noGridFiguresLeaked: document.querySelectorAll("#dxcdf svg.chart").length === 0 &&
      document.querySelectorAll("#distexplorer table.dxqtable tbody tr").length === 0 &&
      !/164,142/.test(dxText) && !/107,159/.test(dxText),
    otherTabsStillRender: /contract v\d/.test(bodyText) &&
      document.querySelectorAll("#invtable tbody tr").length >= 20 &&
      document.querySelectorAll("#comparator table.cmptable tbody tr").length >= 5 &&
      document.querySelectorAll("#capital .card").length >= 7,
    networkCalls: networkCalls.length,
    jsErrors: errors.length,
  };
  const ok = checks.dxTabPresent && checks.panelNotBlank &&
    checks.fallbackMessagePresent && checks.fallbackNeutral &&
    checks.nothingRecomputedStated && checks.noGridFiguresLeaked &&
    checks.otherTabsStillRender &&
    checks.networkCalls === 0 && checks.jsErrors === 0;
  console.log(JSON.stringify({ ok, checks, errors, networkCalls }, null, 2));
  process.exit(ok ? 0 : 1);
}, 0);
