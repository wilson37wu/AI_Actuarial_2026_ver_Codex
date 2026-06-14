// Phase 34 Task 2 (gap H1) - degraded-mode self-test for the data-contract
// integrity guard. Deletes ONE required top-level section from the embedded
// ui_data contract (simulates an incomplete / mismatched payload), re-loads
// ui_app.html under jsdom (network blocked), and asserts the pre-registered
// criterion: NO JS errors, NO network calls, NO blank panel - a NEUTRAL
// degraded-mode banner is shown naming the missing section, the Integrity tab
// marks it absent, and every other tab still renders. Nothing is recomputed.
const fs = require("fs");
const path = require("path");
const { JSDOM, VirtualConsole } = require("jsdom");

const htmlPath = process.argv[2] || path.join(process.cwd(), "ui_app.html");
let html = fs.readFileSync(htmlPath, "utf8");

const m = html.match(/\/\*__UI_DATA__\*\/(.*?)<\/script>/s);
if (!m) { console.log(JSON.stringify({ ok: false, error: "no embedded data" })); process.exit(1); }
const data = JSON.parse(m[1]);
// Drop a required section so the load-time guard must degrade gracefully.
const dropped = "governance";
delete data[dropped];
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
    window.fetch = (...args) => { networkCalls.push(["fetch", String(args[0])]); return Promise.reject(new Error("offline self-test blocked fetch")); };
    window.XMLHttpRequest = class OfflineBlockedXHR { open(_m, url){ networkCalls.push(["xhr", String(url)]); } send(){ throw new Error("offline self-test blocked XMLHttpRequest"); } };
  },
});

setTimeout(() => {
  const { document } = dom.window;
  const tabs = [...document.querySelectorAll(".tab")];
  tabs.forEach(t => t.click());
  const intTab = tabs.find(t => t.getAttribute("data-target") === "integrity");
  if (intTab) intTab.click();
  const banner = document.getElementById("integritybanner");
  const bannerText = (banner && banner.textContent) || "";
  const bannerVisible = !!banner && banner.style.display !== "none" && banner.getAttribute("aria-hidden") === "false";
  const intEl = document.getElementById("integrity");
  const intText = (intEl && intEl.textContent) || "";
  const absentRows = [...document.querySelectorAll('#integrity table.inttable tbody tr[data-int-present="0"]')];
  const droppedRowAbsent = absentRows.some(r => r.getAttribute("data-int-key") === dropped);
  const bodyText = document.body.textContent || "";
  const checks = {
    bannerShown: bannerVisible,
    bannerNamesMissing: /Data-contract (notice|check)/.test(bannerText) && new RegExp("missing").test(bannerText) && bannerText.indexOf(dropped) >= 0,
    bannerNeutralNoSteering: !/recommended|should adopt|we recommend|do not use|broken|corrupt/i.test(bannerText),
    bannerStatesNoRecompute: /No figures are recomputed/.test(bannerText),
    integrityPanelNotBlank: intText.trim().length > 50,
    integrityMarksDropAbsent: droppedRowAbsent,
    integrityShowsDegraded: /DEGRADED/.test(intText),
    otherTabsStillRender: /contract v\d/.test(bodyText) &&
      document.querySelectorAll("#invtable tbody tr").length >= 20 &&
      document.querySelectorAll("#capital .card").length >= 7,
    networkCalls: networkCalls.length,
    jsErrors: errors.length,
  };
  const ok = checks.bannerShown && checks.bannerNamesMissing && checks.bannerNeutralNoSteering &&
    checks.bannerStatesNoRecompute && checks.integrityPanelNotBlank && checks.integrityMarksDropAbsent &&
    checks.integrityShowsDegraded && checks.otherTabsStillRender &&
    checks.networkCalls === 0 && checks.jsErrors === 0;
  console.log(JSON.stringify({ ok, checks, errors, networkCalls }, null, 2));
  process.exit(ok ? 0 : 1);
}, 0);
