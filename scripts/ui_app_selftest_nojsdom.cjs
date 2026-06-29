// ============================================================================
// ui_app_selftest_nojsdom.cjs  —  jsdom-FREE companion self-test for ui_app.html
// ----------------------------------------------------------------------------
// WHY THIS EXISTS
//   The full ui_app self-test (scripts/ui_app_self_test.cjs) loads the page in
//   jsdom to exercise tab/click/layout behaviour. jsdom is absent in the
//   offline auto-cycle sandbox (`require('jsdom')` -> MODULE_NOT_FOUND), so that
//   gate cannot run here. This companion mirrors the PROVEN jsdom-free pattern
//   of scripts/offline_home_loader_parity.cjs (node-stdlib only) and asserts the
//   governance-critical, DOM-independent invariants of ui_app.html so the
//   owner-gated Phase 38 Task 3 cutover becomes CI/sandbox-verifiable WITHOUT a
//   jsdom-equipped environment.
//
//   This is TEST TOOLING ONLY: it reads ui_app.html, computes nothing that the
//   page ships, and changes no governed byte / model figure / contract.
//
// WHAT IT ASSERTS (no DOM, no network, no storage, no third-party deps)
//   1. Zero external references in the executable surface (HTML/CSS/JS, i.e. the
//      file minus the inert <script id="ui-data"> JSON): no http(s)://, no
//      protocol-relative //host, no remote src=/href=, no <link>/@import/url(http).
//   2. The embedded ui_data payload parses and carries the GOVERNED contract
//      version (1.23.0) and the GOVERNED headline (39975.654628199336).
//   3. Every governed tab/section anchor id is present as a static
//      `id="..." class="panel"` section (21 panels), and the panel count matches
//      the governed baseline (so an added/removed panel is caught).
//   4. Content-integrity self-consistency, two independent ways:
//        4a. The page's OWN embedded pure-JS SHA-256 (_ciSha256) reproduces the
//            standard SHA-256 test vectors for "abc" and "" — proving the shipped
//            hasher is a correct SHA-256.
//        4b. The page's OWN embedded _ciSectionDigests(DATA) reproduces, byte for
//            byte, the build-time contract_manifest.section_digests + root_digest.
//        4c. An INDEPENDENT recompute (node `crypto` SHA-256 over a faithful
//            re-implementation of the page's canonical serialiser) reproduces the
//            same 26 section digests + root — cross-checking the shipped helpers
//            against a trusted implementation.
//      Plus: contract_manifest.required_top_level_keys are all present and
//      key_count is self-consistent.
//
//   Layout/click assertions (narrow-viewport guarantee, full tab-click
//   traversal) intentionally REMAIN in the jsdom path (ui_app_self_test.cjs),
//   which stays owner/CI-gated.
//
// USAGE:   node scripts/ui_app_selftest_nojsdom.cjs [path/to/ui_app.html]
// EXIT:    0 if every check passes, 1 otherwise. Prints a JSON report.
// ============================================================================
"use strict";
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const vm = require("vm");

// ---- governed expectations (byte-pinned; update only under an approved change)
const GOVERNED_CONTRACT = "1.23.0";
const GOVERNED_HEADLINE = 39975.654628199336;
const GOVERNED_PANEL_IDS = [
  "overview", "inventory", "calibrations", "capital", "actions",
  "phase24", "phase25", "phase26", "phase27", "phase28", "phase29",
  "phase30", "comparator", "distexplorer", "ownerdecision", "userrun",
  "governance", "integrity", "glossary", "vrpanel", "vr2panel",
];
// Standard NIST SHA-256 test vectors.
const SHA256_ABC = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad";
const SHA256_EMPTY = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855";

const ROOT = path.resolve(__dirname, "..");
const htmlPath = process.argv[2] || path.join(ROOT, "ui_app.html");

const checks = [];
const ok = (name, cond, detail) =>
  checks.push({ name, pass: !!cond, detail: detail === undefined ? null : detail });
const fail = (name, detail) => checks.push({ name, pass: false, detail: detail || null });

function finish() {
  const failed = checks.filter((c) => !c.pass);
  console.log(JSON.stringify({
    ok: failed.length === 0,
    file: path.relative(ROOT, htmlPath) || htmlPath,
    checks: checks.length,
    passed: checks.length - failed.length,
    failed: failed.map((f) => f.name + (f.detail ? " :: " + f.detail : "")),
  }, null, 2));
  process.exit(failed.length === 0 ? 0 : 1);
}

let html;
try {
  html = fs.readFileSync(htmlPath, "utf8");
} catch (e) {
  fail("ui_app.html readable", String((e && e.message) || e));
  finish();
}

// ---- split off the inert embedded JSON so a URL inside DATA text never
//      false-fails the external-reference scan (data is not an executable load).
const dataRe = /<script id="ui-data" type="application\/json">([\s\S]*?)<\/script>/;
const dm = html.match(dataRe);
ok("embedded <script id=ui-data> block present", !!dm);
const dataRaw = dm ? dm[1] : "";
const nonData = dm ? html.slice(0, dm.index) + html.slice(dm.index + dm[0].length) : html;

// ===== Check 1: zero external references in the executable surface ==========
{
  const patterns = [
    ["http:// scheme", /http:\/\//g],
    ["https:// scheme", /https:\/\//g],
    ["protocol-relative //host", /["'(]\/\/[A-Za-z0-9.]/g],
    ["remote src=", /src\s*=\s*["'](?:https?:)?\/\//gi],
    ["remote href=", /href\s*=\s*["'](?:https?:)?\/\//gi],
    ["<link> element", /<link\b/gi],
    ["@import", /@import/gi],
    ["url(http...)", /url\(\s*["']?https?:/gi],
  ];
  let total = 0;
  const offenders = [];
  for (const [label, re] of patterns) {
    const n = (nonData.match(re) || []).length;
    if (n) { total += n; offenders.push(label + "×" + n); }
  }
  ok("0 external references (executable HTML/CSS/JS surface)", total === 0,
     total === 0 ? "0 refs" : offenders.join(", "));
}

// ===== Parse the embedded payload (sentinel-prefixed canonical JSON) =========
let DATA = null;
try {
  DATA = JSON.parse(dataRaw.replace(/^\s*\/\*__UI_DATA__\*\//, ""));
  ok("embedded ui_data parses as JSON", true);
} catch (e) {
  fail("embedded ui_data parses as JSON", String((e && e.message) || e));
}

// ===== Check 2: governed contract + headline ================================
if (DATA) {
  ok("contract_version == " + GOVERNED_CONTRACT, DATA.contract_version === GOVERNED_CONTRACT,
     "got " + JSON.stringify(DATA.contract_version));
  let hl;
  try { hl = DATA.owner_decision_p31.evidence_pack.governed_headline.value; } catch (e) { hl = undefined; }
  ok("governed headline == " + GOVERNED_HEADLINE, hl === GOVERNED_HEADLINE,
     "got " + JSON.stringify(hl));
}

// ===== Check 3: governed panel anchor ids present (static, no DOM) ==========
{
  const presentIds = new Set(
    [...nonData.matchAll(/id="([^"]+)"[^>]*class="panel"/g)].map((m) => m[1])
  );
  for (const id of GOVERNED_PANEL_IDS) {
    ok('panel anchor id "' + id + '" present', presentIds.has(id));
  }
  ok("panel count == governed baseline (" + GOVERNED_PANEL_IDS.length + ")",
     presentIds.size === GOVERNED_PANEL_IDS.length,
     "found " + presentIds.size);
}

// ===== Check 4: content-integrity self-consistency ==========================
// 4a/4b use the page's OWN embedded helpers; 4c is an independent cross-check.
function extractFn(src, name) {
  const sig = "function " + name + "(";
  const i = src.indexOf(sig);
  if (i < 0) return null;
  let depth = 0, started = false;
  for (let k = src.indexOf("{", i); k < src.length; k++) {
    const c = src[k];
    if (c === "{") { depth++; started = true; }
    else if (c === "}") { depth--; if (started && depth === 0) return src.slice(i, k + 1); }
  }
  return null;
}

// faithful re-implementation of the page's _ciCanon, for the independent path.
function canonIndep(v) {
  if (v === null || v === undefined) return "null";
  const t = typeof v;
  if (t === "number") return isFinite(v) ? String(v) : "null";
  if (t === "boolean") return v ? "true" : "false";
  if (t === "string") return JSON.stringify(v);
  if (Array.isArray(v)) return "[" + v.map(canonIndep).join(",") + "]";
  const ks = Object.keys(v).sort();
  return "{" + ks.map((k) => JSON.stringify(k) + ":" + canonIndep(v[k])).join(",") + "}";
}
const nodeSha = (s) => crypto.createHash("sha256").update(Buffer.from(s, "utf8")).digest("hex");

if (DATA) {
  const man = DATA.contract_manifest;
  ok("contract_manifest present with section_digests + root_digest",
     !!(man && man.section_digests && man.root_digest));

  // extract + evaluate the page's own integrity helpers in an isolated context
  let page = null;
  try {
    const srcCanon = extractFn(nonData, "_ciCanon");
    const srcSha = extractFn(nonData, "_ciSha256");
    const srcSec = extractFn(nonData, "_ciSectionDigests");
    if (srcCanon && srcSha && srcSec) {
      const sandbox = {};
      vm.createContext(sandbox);
      vm.runInContext(
        srcCanon + "\n" + srcSha + "\n" + srcSec +
        "\nthis._ciSha256=_ciSha256;this._ciCanon=_ciCanon;this._ciSectionDigests=_ciSectionDigests;",
        sandbox
      );
      page = sandbox;
      ok("embedded integrity helpers (_ciCanon/_ciSha256/_ciSectionDigests) extracted", true);
    } else {
      fail("embedded integrity helpers (_ciCanon/_ciSha256/_ciSectionDigests) extracted",
           "missing: " + [["_ciCanon", srcCanon], ["_ciSha256", srcSha], ["_ciSectionDigests", srcSec]]
             .filter(([, s]) => !s).map(([n]) => n).join(","));
    }
  } catch (e) {
    fail("embedded integrity helpers extracted", String((e && e.message) || e));
  }

  // 4a: the shipped pure-JS SHA-256 reproduces standard SHA-256 test vectors
  if (page) {
    ok('embedded _ciSha256("abc") == SHA-256 test vector', page._ciSha256("abc") === SHA256_ABC);
    ok('embedded _ciSha256("") == SHA-256 test vector', page._ciSha256("") === SHA256_EMPTY);
  }

  // 4b: the shipped verifier reproduces the build-time manifest digests
  if (page && man && man.section_digests && man.root_digest) {
    const rec = page._ciSectionDigests(DATA);
    let mismatch = 0, missing = 0, extra = 0;
    for (const k of rec.keys) if (rec.section_digests[k] !== man.section_digests[k]) mismatch++;
    for (const k of Object.keys(man.section_digests)) if (rec.section_digests[k] === undefined) missing++;
    for (const k of rec.keys) if (man.section_digests[k] === undefined) extra++;
    ok("embedded verifier reproduces manifest section_digests (0 mismatch)", mismatch === 0, "mismatch=" + mismatch);
    ok("manifest covers every recomputed section (0 missing)", missing === 0, "missing=" + missing);
    ok("no recomputed section absent from manifest (0 extra)", extra === 0, "extra=" + extra);
    ok("embedded verifier reproduces manifest root_digest", rec.root_digest === man.root_digest);
  }

  // 4c: INDEPENDENT cross-check (node crypto + reimplemented canon)
  if (man && man.section_digests && man.root_digest) {
    const ks = Object.keys(DATA).filter((k) => k !== "contract_manifest").sort();
    const sd = {};
    ks.forEach((k) => (sd[k] = nodeSha(canonIndep(DATA[k]))));
    const root = nodeSha(canonIndep(sd));
    let indepMismatch = 0;
    ks.forEach((k) => { if (sd[k] !== man.section_digests[k]) indepMismatch++; });
    ok("independent node-crypto recompute matches manifest section_digests", indepMismatch === 0, "mismatch=" + indepMismatch);
    ok("independent node-crypto recompute matches manifest root_digest", root === man.root_digest);
    // sanity: the independent SHA-256 itself is correct
    ok("node-crypto SHA-256 matches test vectors", nodeSha("abc") === SHA256_ABC && nodeSha("") === SHA256_EMPTY);
  }

  // required top-level keys present + key_count self-consistent
  if (man && Array.isArray(man.required_top_level_keys)) {
    const missingReq = man.required_top_level_keys.filter((k) => !(k in DATA));
    ok("all required_top_level_keys present in payload", missingReq.length === 0,
       missingReq.length ? "missing: " + missingReq.join(",") : "");
    if (typeof man.key_count === "number") {
      const nonManifestKeys = Object.keys(DATA).filter((k) => k !== "contract_manifest").length;
      ok("contract_manifest.key_count matches non-manifest top-level key count",
         man.key_count === nonManifestKeys, "manifest=" + man.key_count + " actual=" + nonManifestKeys);
    }
  }
}

finish();
