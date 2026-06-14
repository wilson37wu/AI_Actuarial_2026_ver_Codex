// Phase 34 Task 3 (gap H2) - dedicated self-test for the global cross-tab search
// and deep-linkable read-outs. Loads ui_app.html under jsdom (network blocked) and
// asserts the pre-registered acceptance criteria:
//   * a search box exists and the index is built ONLY from already-rendered text
//     (tab titles, headline labels, table captions) - no network, no new data;
//   * the governed frozen-t headline is FINDABLE via search and is NEVER
//     re-labelled by the search/highlight (its exact value 39975.654628199336
//     carried in the comparator data attributes is byte-for-byte unchanged after a
//     jump, and the displayed text node is untouched);
//   * selecting a result activates the owning tab and writes a "tab~section" hash;
//   * a "#tab~section" deep link restores BOTH the tab and the in-tab section, and
//     a plain "#tab" hash still restores just the tab (Phase 33 G4 back-compat);
//   * NO storage APIs in the executable build (file:// safe);
//   * ZERO network calls and ZERO JS errors.
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

  const input = document.getElementById("gsearchInput");
  const box = document.getElementById("gsearchResults");
  const searchBoxPresent = !!input && !!box;
  // index entries assign stable "dl-*" anchors to already-rendered read-outs
  const dlIds = document.querySelectorAll('[id^="dl-"]').length;

  // The search index must be built from rendered text only: no fetch/XHR occurred
  // during load and render (asserted globally via networkCalls), and no <script>
  // or external reference is added.
  const codeOnly = html.replace(/<script id="ui-data"[^>]*>[\s\S]*?<\/script>/, "");
  const noStorageApis = !/\blocalStorage\b/.test(codeOnly) && !/\bsessionStorage\b/.test(codeOnly);
  const noExternalRefs = (codeOnly.match(/(src|href)\s*=\s*["']https?:/g) || []).length === 0;

  // --- search hit + jump + governed-headline-never-relabelled ------------------
  const cmpBefore = [...document.querySelectorAll('[data-cmp-point]')].map(e => e.getAttribute('data-cmp-point'));
  // exact governed full-precision value is present in the embedded read-outs
  const governedValuePresent = cmpBefore.indexOf("39975.654628199336") !== -1;

  input.value = "frozen single-df t";
  input.dispatchEvent(new window.Event("input", { bubbles: true }));
  const frozenHits = [...box.querySelectorAll(".gsearch-item")].length;

  input.value = "governed component scr headline";
  input.dispatchEvent(new window.Event("input", { bubbles: true }));
  const items = [...box.querySelectorAll(".gsearch-item")];
  const searchHit = items.length >= 1 && /Governed component SCR headline/.test(items[0].textContent);

  // capture the matched element's text BEFORE the jump
  let jumpActivatesTab = false, hashCarriesSection = false, headlineTextUnchanged = false;
  let resultsClosedAfterGo = false;
  if (items.length) {
    items[0].click();
    const sel = document.querySelector('#tabs [aria-selected="true"]');
    jumpActivatesTab = !!sel && document.getElementById(sel.getAttribute("data-target")).classList.contains("active");
    hashCarriesSection = /^#[a-z0-9]+~dl-/.test(window.location.hash || "");
    resultsClosedAfterGo = box.hidden === true;
  }
  // the governed headline figures are byte-for-byte unchanged after search+jump
  const cmpAfter = [...document.querySelectorAll('[data-cmp-point]')].map(e => e.getAttribute('data-cmp-point'));
  const headlineNeverRelabelled = JSON.stringify(cmpBefore) === JSON.stringify(cmpAfter) && governedValuePresent;
  // the deep-linked element keeps its exact text (no highlight markup injected)
  const dlTarget = document.querySelector('[id^="dl-ownerdecision-governed-component-scr-headline"]');
  if (dlTarget) headlineTextUnchanged = /Governed component SCR headline/.test(dlTarget.textContent) &&
    dlTarget.querySelectorAll("mark").length === 0;

  // --- deep-link restore: tab + in-tab section via URL hash only ---------------
  const capAnchor = document.querySelector('#capital [id^="dl-"]');
  let deepLinkTabSection = false;
  if (capAnchor) {
    window.location.hash = "#capital~" + capAnchor.id;
    window.dispatchEvent(new window.Event("hashchange"));
    const sel = document.querySelector('#tabs [aria-selected="true"]');
    deepLinkTabSection = !!sel && sel.getAttribute("data-target") === "capital" &&
      document.getElementById("capital").classList.contains("active") &&
      capAnchor.classList.contains("dl-flash");
  }

  // --- back-compat: a plain "#tab" hash still restores just the tab ------------
  window.location.hash = "#governance";
  window.dispatchEvent(new window.Event("hashchange"));
  const govSel = document.querySelector('#tabs [aria-selected="true"]');
  const deepLinkPlainTab = !!govSel && govSel.getAttribute("data-target") === "governance" &&
    document.getElementById("governance").classList.contains("active") &&
    document.querySelectorAll('#tabs [aria-selected="true"]').length === 1;

  // --- empty query closes the dropdown (no stray state) ------------------------
  input.value = "";
  input.dispatchEvent(new window.Event("input", { bubbles: true }));
  const emptyQueryCloses = box.hidden === true;

  // --- a no-match query shows a neutral "No matches" note, never an error ------
  input.value = "zzzzz-no-such-readout";
  input.dispatchEvent(new window.Event("input", { bubbles: true }));
  const noMatchNeutral = /No matches/.test(box.textContent) && box.querySelectorAll(".gsearch-item").length === 0;

  const checks = {
    searchBoxPresent,
    dlIds,
    noStorageApis,
    noExternalRefs,
    governedValuePresent,
    frozenHits,
    searchHit,
    jumpActivatesTab,
    hashCarriesSection,
    resultsClosedAfterGo,
    headlineNeverRelabelled,
    headlineTextUnchanged,
    deepLinkTabSection,
    deepLinkPlainTab,
    emptyQueryCloses,
    noMatchNeutral,
    networkCalls: networkCalls.length,
    jsErrors: errors.length,
  };

  const ok =
    checks.searchBoxPresent &&
    checks.dlIds >= 50 &&
    checks.noStorageApis &&
    checks.noExternalRefs &&
    checks.governedValuePresent &&
    checks.frozenHits >= 1 &&
    checks.searchHit &&
    checks.jumpActivatesTab &&
    checks.hashCarriesSection &&
    checks.resultsClosedAfterGo &&
    checks.headlineNeverRelabelled &&
    checks.headlineTextUnchanged &&
    checks.deepLinkTabSection &&
    checks.deepLinkPlainTab &&
    checks.emptyQueryCloses &&
    checks.noMatchNeutral &&
    checks.networkCalls === 0 &&
    checks.jsErrors === 0;
  done(ok, checks);
}, 600);
