// ============================================================================
// ui_data_section_digest_recompute_parity.cjs  —  W91 standalone-payload gate
// ----------------------------------------------------------------------------
// WHY THIS EXISTS
//   offline_home.html consumes the STANDALONE ui_data.json (the user can also
//   drag-drop a different ui_data.json snapshot into it). Its 26 top-level
//   section payloads carry a contract_manifest with per-section SHA-256
//   section_digests + a root_digest. Until now NO gate recomputed those 26
//   section digests FROM THE STANDALONE ui_data.json payload:
//     * scripts/ui_app_selftest_nojsdom.cjs (40 checks) recomputes the 26
//       digests from the payload EMBEDDED IN ui_app.html, not the standalone file.
//     * tests/test_ui_data_contract_manifest_{digest,structure}.py (W89/W90) pin
//       the manifest's digest VALUES + STRUCTURE, but never recompute a section
//       payload -> digest from the standalone file.
//     * the several `test_embedded_payload_matches_standalone` tests compare only
//       the contract_manifest sub-object (root_digest + section_digests map),
//       plus at most one individual section - never all 26 section payloads.
//     * build_offline_home_validate.py "recomputes nothing" (renders figures);
//       offline_home_loader_parity.cjs compares rendered FIGURES, not digests.
//   So a standalone ui_data.json whose section PAYLOAD drifted while its manifest
//   digests stayed byte-identical would pass every existing gate. This gate is
//   the missing backstop: it recomputes all 26 section_digests + root_digest
//   directly from the standalone ui_data.json and asserts parity with that file's
//   own contract_manifest, using BOTH (a) the page's OWN authoritative embedded
//   serialiser (_ciCanon/_ciSha256/_ciSectionDigests, extracted from ui_app.html
//   and run over the STANDALONE data) and (b) an independent node:crypto recompute.
//
//   TEST TOOLING ONLY: reads ui_data.json + ui_app.html, writes nothing, changes
//   no governed byte / model figure / contract. node-stdlib only (fs/path/crypto/
//   vm; zero third-party deps), jsdom-FREE, so it runs in the offline auto-cycle
//   sandbox. A pure-Python recompute is infeasible (the recipe uses JS-native
//   String(Number) formatting; 19/26 sections diverge under Python json.dumps),
//   which is exactly why the authoritative path borrows the page's JS recipe.
//
// USAGE:   node scripts/ui_data_section_digest_recompute_parity.cjs [ui_data.json] [ui_app.html]
// EXIT:    0 if every check passes, 1 otherwise. Prints a single JSON report.
// ============================================================================
"use strict";
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const vm = require("vm");

// ---- governed expectations (byte-pinned; update only under an approved change)
const GOVERNED_CONTRACT = "1.23.0";
const GOVERNED_ROOT_DIGEST =
  "456f772166a1198363e16c7ccc68f87175ab4e4fa289cc0e798a009f1b257d01";
const GOVERNED_KEY_COUNT = 26;
// Standard NIST SHA-256 test vectors.
const SHA256_ABC = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad";
const SHA256_EMPTY = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855";

const ROOT = path.resolve(__dirname, "..");
const dataPath = process.argv[2] || path.join(ROOT, "ui_data.json");
const htmlPath = process.argv[3] || path.join(ROOT, "ui_app.html");

const checks = [];
const ok = (name, cond, detail) =>
  checks.push({ name, pass: !!cond, detail: detail === undefined ? null : detail });
const fail = (name, detail) => checks.push({ name, pass: false, detail: detail || null });

function finish() {
  const failed = checks.filter((c) => !c.pass);
  console.log(JSON.stringify({
    ok: failed.length === 0,
    data_file: path.relative(ROOT, dataPath) || dataPath,
    recipe_file: path.relative(ROOT, htmlPath) || htmlPath,
    checks: checks.length,
    passed: checks.length - failed.length,
    failed: failed.map((f) => f.name + (f.detail ? " :: " + f.detail : "")),
  }, null, 2));
  process.exit(failed.length === 0 ? 0 : 1);
}

// ---- brace-matched function extraction (mirrors ui_app_selftest_nojsdom.cjs) -
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

// ---- independent canonical serialiser (faithful re-impl of the page _ciCanon) -
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

// ===== Load the STANDALONE ui_data.json (the file offline_home.html consumes) =
let DATA = null;
try {
  DATA = JSON.parse(fs.readFileSync(dataPath, "utf8"));
  ok("standalone ui_data.json readable + parses as JSON", true);
} catch (e) {
  fail("standalone ui_data.json readable + parses as JSON", String((e && e.message) || e));
  finish();
}

const man = DATA.contract_manifest;
ok("standalone contract_version == " + GOVERNED_CONTRACT,
   DATA.contract_version === GOVERNED_CONTRACT, "got " + JSON.stringify(DATA.contract_version));
ok("standalone contract_version pinned-governed (" + GOVERNED_CONTRACT + ")",
   DATA.contract_version === GOVERNED_CONTRACT);
ok("contract_manifest present with section_digests + root_digest",
   !!(man && man.section_digests && man.root_digest));
ok("manifest digest_algo == sha256", !!man && man.digest_algo === "sha256",
   man ? "got " + JSON.stringify(man.digest_algo) : "no manifest");

// ===== Load ui_app.html — ONLY to borrow the authoritative JS recipe ==========
let nonData = "";
try {
  const html = fs.readFileSync(htmlPath, "utf8");
  // strip the inert embedded <script id="ui-data"> JSON so extraction sees only
  // the executable JS recipe (and we never read the EMBEDDED payload here).
  const dataRe = /<script id="ui-data" type="application\/json">([\s\S]*?)<\/script>/;
  const dm = html.match(dataRe);
  nonData = dm ? html.slice(0, dm.index) + html.slice(dm.index + dm[0].length) : html;
  ok("ui_app.html readable (authoritative recipe source)", true);
} catch (e) {
  fail("ui_app.html readable (authoritative recipe source)", String((e && e.message) || e));
}

// extract + evaluate the page's own integrity helpers in an isolated vm context
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
    ok("authoritative serialiser (_ciCanon/_ciSha256/_ciSectionDigests) extracted from ui_app.html", true);
  } else {
    fail("authoritative serialiser (_ciCanon/_ciSha256/_ciSectionDigests) extracted from ui_app.html",
      "missing: " + [["_ciCanon", srcCanon], ["_ciSha256", srcSha], ["_ciSectionDigests", srcSec]]
        .filter(([, s]) => !s).map(([n]) => n).join(","));
  }
} catch (e) {
  fail("authoritative serialiser extracted from ui_app.html", String((e && e.message) || e));
}

// the borrowed hasher must be a correct SHA-256 (else parity below is vacuous)
if (page) {
  ok('page _ciSha256("abc") == NIST vector', page._ciSha256("abc") === SHA256_ABC);
  ok('page _ciSha256("") == NIST vector', page._ciSha256("") === SHA256_EMPTY);
}

// ===== CORE: recompute the 26 digests FROM THE STANDALONE payload =============
// Path A — authoritative: the page's OWN _ciSectionDigests, run over STANDALONE DATA.
if (page && man && man.section_digests && man.root_digest) {
  const rec = page._ciSectionDigests(DATA);
  let mismatch = 0, missing = 0, extra = 0;
  for (const k of rec.keys) if (rec.section_digests[k] !== man.section_digests[k]) mismatch++;
  for (const k of Object.keys(man.section_digests)) if (rec.section_digests[k] === undefined) missing++;
  for (const k of rec.keys) if (man.section_digests[k] === undefined) extra++;
  ok("AUTH: page serialiser over STANDALONE reproduces manifest section_digests (0 mismatch)",
     mismatch === 0, "mismatch=" + mismatch);
  ok("AUTH: manifest covers every recomputed standalone section (0 missing)", missing === 0, "missing=" + missing);
  ok("AUTH: no recomputed standalone section absent from manifest (0 extra)", extra === 0, "extra=" + extra);
  ok("AUTH: page serialiser over STANDALONE reproduces manifest root_digest",
     rec.root_digest === man.root_digest, "got " + rec.root_digest);
  ok("AUTH: recomputed standalone root_digest == GOVERNED pin",
     rec.root_digest === GOVERNED_ROOT_DIGEST, "got " + rec.root_digest);
}

// Path B — independent: node:crypto + reimplemented canon, over STANDALONE DATA.
if (man && man.section_digests && man.root_digest) {
  const ks = Object.keys(DATA).filter((k) => k !== "contract_manifest").sort();
  const sd = {};
  ks.forEach((k) => (sd[k] = nodeSha(canonIndep(DATA[k]))));
  const root = nodeSha(canonIndep(sd));
  let indepMismatch = 0;
  ks.forEach((k) => { if (sd[k] !== man.section_digests[k]) indepMismatch++; });
  ok("INDEP: node-crypto recompute over STANDALONE matches manifest section_digests (0 mismatch)",
     indepMismatch === 0, "mismatch=" + indepMismatch);
  ok("INDEP: node-crypto recompute over STANDALONE matches manifest root_digest", root === man.root_digest);
  ok("INDEP: recomputed standalone root_digest == GOVERNED pin", root === GOVERNED_ROOT_DIGEST);
  ok("node-crypto SHA-256 matches NIST vectors",
     nodeSha("abc") === SHA256_ABC && nodeSha("") === SHA256_EMPTY);
  // coverage: section_digests keys are EXACTLY the standalone non-manifest sections
  const sdKeys = Object.keys(man.section_digests).sort();
  ok("manifest section_digests keys == standalone non-manifest top-level keys (exact coverage)",
     JSON.stringify(sdKeys) === JSON.stringify(ks),
     "n_manifest=" + sdKeys.length + " n_payload=" + ks.length);
  ok("standalone non-manifest top-level key count == " + GOVERNED_KEY_COUNT,
     ks.length === GOVERNED_KEY_COUNT, "got " + ks.length);
}

// manifest self-consistency vs the STANDALONE payload it describes
if (man && Array.isArray(man.required_top_level_keys)) {
  const missingReq = man.required_top_level_keys.filter((k) => !(k in DATA));
  ok("all required_top_level_keys present in standalone payload", missingReq.length === 0,
     missingReq.length ? "missing: " + missingReq.join(",") : "");
  if (typeof man.key_count === "number") {
    const nonManifestKeys = Object.keys(DATA).filter((k) => k !== "contract_manifest").length;
    ok("manifest.key_count matches standalone non-manifest key count",
       man.key_count === nonManifestKeys, "manifest=" + man.key_count + " actual=" + nonManifestKeys);
  }
}

finish();
