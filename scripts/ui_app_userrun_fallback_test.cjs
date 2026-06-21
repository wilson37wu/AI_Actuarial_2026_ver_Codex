// Phase 32 Task 3 (gap G2) - graceful-fallback self-test for the User Run
// (UIL) panel. Strips the user_run section from the embedded ui_data
// contract, re-loads ui_app.html under jsdom (network blocked), and asserts
// the pre-registered fallback criterion: NO JS errors, NO network calls,
// NO blank tab - the panel renders a neutral explanatory message and every
// pre-existing tab still renders.
const fs = require("fs");
const path = require("path");
const { JSDOM, VirtualConsole } = require("jsdom");

const htmlPath = process.argv[2] || path.join(process.cwd(), "ui_app.html");
let html = fs.readFileSync(htmlPath, "utf8");

// Strip user_run from the embedded contract (simulates a build with no
// scripts/run_model.py evidence present).
const m = html.match(/\/\*__UI_DATA__\*\/(.*?)<\/script>/s);
if (!m) { console.log(JSON.stringify({ ok: false, error: "no embedded data" })); process.exit(1); }
const data = JSON.parse(m[1]);
delete data.user_run;
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
  const urTab = tabs.find(t => t.getAttribute("data-target") === "userrun");
  if (urTab) urTab.click();
  const urEl = document.getElementById("userrun");
  const urText = (urEl && urEl.textContent) || "";
  const bodyText = document.body.textContent || "";
  const checks = {
    userRunTabPresent: !!urTab,
    panelNotBlank: urText.trim().length > 50,
    fallbackMessagePresent: /No user-input run is embedded/.test(urText),
    fallbackHowToPresent: /MODEL_INPUTS_TEMPLATE\.xlsx/.test(urText) && /scripts\/run_model\.py/.test(urText),
    fallbackNeutral: /governed read-outs in the other tabs are unaffected/.test(urText),
    noRunFiguresLeaked: !/71,112/.test(urText) && !/WorkedExample_TemplateDemoBook/.test(urText),
    otherTabsStillRender: /contract v\d/.test(bodyText) &&
      document.querySelectorAll("#invtable tbody tr").length >= 20 &&
      document.querySelectorAll("#ownerdecision .card").length >= 12 &&
      document.querySelectorAll("#capital .card").length >= 7,
    networkCalls: networkCalls.length,
    jsErrors: errors.length,
  };
  const ok = checks.userRunTabPresent && checks.panelNotBlank &&
    checks.fallbackMessagePresent && checks.fallbackHowToPresent &&
    checks.fallbackNeutral && checks.noRunFiguresLeaked &&
    checks.otherTabsStillRender &&
    checks.networkCalls === 0 && checks.jsErrors === 0;
  console.log(JSON.stringify({ ok, checks, errors, networkCalls }, null, 2));
  process.exit(ok ? 0 : 1);
}, 400);
