// Phase 36 Task 4 (gap E3) - dedicated fallback test for the reproducibility
// evidence-pack export. Loads ui_app.html under jsdom (network blocked), captures
// the bytes + filename the "Reproducibility evidence pack" toolbar button hands to
// the Blob/download plumbing, and asserts the pre-registered acceptance criteria:
//   (1) the exported payload bytes are BYTE-IDENTICAL to the embedded ui_data;
//   (2) the export performs NO network call and uses NO storage API;
//   (3) the filename carries the contract version + root-digest provenance stamp;
//   (4) the exported payload is digest-verifiable by the EXISTING in-browser
//       verifier: re-embedding the exported bytes and opening the Integrity tab
//       yields INTEGRITY VERIFIED with the root digest matching and 0 altered rows;
//   (5) no JS errors.
const fs = require("fs");
const path = require("path");
const { JSDOM, VirtualConsole } = require("jsdom");

const htmlPath = process.argv[2] || path.join(process.cwd(), "ui_app.html");
const html = fs.readFileSync(htmlPath, "utf8");

// the exact embedded payload bytes (same strip the UI's getEmbeddedRaw performs)
const m = html.match(/\/\*__UI_DATA__\*\/(.*?)<\/script>/s);
if (!m) { console.log(JSON.stringify({ ok: false, error: "no embedded data" })); process.exit(1); }
const embedded = m[1].replace("/*__UI_DATA__*/", "").trim();

const errors = [];
const networkCalls = [];
const captured = { bytes: [], names: [], usedStorage: false };

const virtualConsole = new VirtualConsole();
virtualConsole.on("jsdomError", err => errors.push(String((err && err.message) || err)));

const dom = new JSDOM(html, {
  runScripts: "dangerously",
  pretendToBeVisual: true,
  virtualConsole,
  beforeParse(window) {
    window.onerror = message => errors.push(String(message));
    window.fetch = (...a) => { networkCalls.push(["fetch", String(a[0])]); return Promise.reject(new Error("blocked")); };
    window.XMLHttpRequest = class { open(_m, u){ networkCalls.push(["xhr", String(u)]); } send(){ throw new Error("blocked"); } };
    // capture Blob contents
    const RealBlob = window.Blob;
    window.Blob = function(parts, opts){ this._parts = parts; this._opts = opts; this._real = new RealBlob(parts, opts); };
    // capture the object-URL target (the Blob) and revoke
    window.URL.createObjectURL = (b) => { captured.bytes.push(b && b._parts && b._parts[0]); return "blob:capture"; };
    window.URL.revokeObjectURL = () => {};
    // trip-wires for any storage use on the export path
    try { Object.defineProperty(window, "localStorage", { get(){ captured.usedStorage = true; throw new Error("no storage"); } }); } catch (e) {}
    try { Object.defineProperty(window, "sessionStorage", { get(){ captured.usedStorage = true; throw new Error("no storage"); } }); } catch (e) {}
  },
});

setTimeout(() => {
  const { document } = dom.window;
  // record any anchor download (the download path uses an <a download> click)
  dom.window.HTMLAnchorElement.prototype.click = function(){ captured.names.push(this.download); };

  const btn = document.getElementById("btnEvidencePack");
  const buttonPresent = !!btn;
  if (btn) btn.click();

  const exported = captured.bytes.length ? captured.bytes[captured.bytes.length - 1] : null;
  const filename = captured.names.length ? captured.names[captured.names.length - 1] : "";

  const byteIdentical = exported === embedded;
  const filenameStamped = /^reproducibility_evidence_pack_v\d+\.\d+\.\d+_[0-9a-f]{8}\.json$/.test(filename);

  // (4) digest-verifiable by the EXISTING in-browser verifier: re-embed the
  // exported bytes into a fresh UI instance and read the verifier verdict after
  // it has initialised.
  const html2 = html.replace(m[1], exported);
  const errors2 = [], net2 = [];
  const vc2 = new VirtualConsole();
  vc2.on("jsdomError", err => errors2.push(String((err && err.message) || err)));
  const dom2 = new JSDOM(html2, {
    runScripts: "dangerously", pretendToBeVisual: true, virtualConsole: vc2,
    beforeParse(window){
      window.onerror = msg => errors2.push(String(msg));
      window.fetch = (...a)=>{ net2.push(String(a[0])); return Promise.reject(new Error("blocked")); };
      window.XMLHttpRequest = class { open(){} send(){ throw new Error("blocked"); } };
    },
  });

  setTimeout(() => {
    let verifierIntegrityVerified = false, verifierRootMatch = false, verifierAltRows = -1, verifierRows = 0;
    try {
      const doc2 = dom2.window.document;
      const tabs2 = [...doc2.querySelectorAll(".tab")];
      tabs2.forEach(t => t.click());
      const intTab2 = tabs2.find(t => t.getAttribute("data-target") === "integrity");
      if (intTab2) intTab2.click();
      const intText2 = (doc2.getElementById("integrity") || {}).textContent || "";
      verifierRows = doc2.querySelectorAll('#integrity table.intverify tbody tr').length;
      verifierAltRows = doc2.querySelectorAll('#integrity table.intverify tbody tr[data-int-verify="alt"]').length;
      verifierIntegrityVerified = /INTEGRITY VERIFIED/.test(intText2);
      verifierRootMatch = /Root digest match/.test(intText2);
    } catch (e) { errors.push("reverify:" + String(e && e.message)); }

    const checks = {
      buttonPresent,
      exportTriggered: exported !== null,
      byteIdentical,
      filenameStamped,
      noStorageUsed: captured.usedStorage === false,
      verifierRendered: verifierRows >= 20,
      verifierIntegrityVerified,
      verifierRootMatch,
      verifierZeroAltered: verifierAltRows === 0,
      reverifyNoErrors: errors2.length === 0 && net2.length === 0,
      networkCalls: networkCalls.length,
      jsErrors: errors.length,
    };
    const ok = checks.buttonPresent && checks.exportTriggered && checks.byteIdentical &&
      checks.filenameStamped && checks.noStorageUsed && checks.verifierRendered &&
      checks.verifierIntegrityVerified && checks.verifierRootMatch && checks.verifierZeroAltered &&
      checks.reverifyNoErrors && checks.networkCalls === 0 && checks.jsErrors === 0;
    console.log(JSON.stringify({ ok, checks, errors, networkCalls }, null, 2));
    process.exit(ok ? 0 : 1);
  }, 400);
}, 300);
