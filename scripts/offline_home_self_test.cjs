// Offline self-test for offline_home.html (zero-install landing page).
// Loads under jsdom with network BLOCKED; asserts: parses, 0 network, 0 JS errors,
// every offline view linked, governed headline rendered, provenance object set.
const fs = require("fs");
const path = require("path");
const { JSDOM, VirtualConsole } = require("jsdom");

const htmlPath = process.argv[2] || path.join(process.cwd(), "offline_home.html");
const html = fs.readFileSync(htmlPath, "utf8");
const errors = [], net = [];
const vc = new VirtualConsole();
vc.on("jsdomError", e => errors.push(String((e && e.message) || e)));

const dom = new JSDOM(html, {
  runScripts: "dangerously", virtualConsole: vc,
  beforeParse(w) {
    w.fetch = (...a) => { net.push(["fetch", a[0]]); return Promise.reject(new Error("blocked")); };
    w.XMLHttpRequest = function(){ this.open=(...a)=>net.push(["xhr",a[1]]); this.send=()=>{}; this.setRequestHeader=()=>{}; };
  },
});
const doc = dom.window.document;
const checks = [];
function ok(name, cond){ checks.push({name, pass: !!cond}); }

ok("title present", /Offline Home/.test(doc.title));
const links = [...doc.querySelectorAll("a.card")].map(a => a.getAttribute("href"));
["ui_app.html","model_result_viewer.html","combined_model_app.html",
 "par_projection_gui.html","launchers/README.md"].forEach(v =>
  ok("links "+v, links.includes(v)));
ok("classification banner", /EDUCATIONAL ONLY/.test(doc.body.textContent));
ok("governed headline rendered", /39,975\.65/.test(doc.body.textContent));
ok("nested SCR rendered", /48,707/.test(doc.body.textContent));
ok("at least 8 figure rows", doc.querySelectorAll(".fig").length >= 8);
ok("provenance object set", dom.window.__OFFLINE_HOME__ &&
   dom.window.__OFFLINE_HOME__.headline === 39975.654628199336);
ok("ZERO network calls", net.length === 0);
ok("ZERO JS errors", errors.length === 0);
// "which view do I want?" chooser (additive, static) present
ok("which-view chooser", /Which view do I want\?/.test(doc.body.textContent));
ok("chooser >=6 rows", doc.querySelectorAll(".crow").length >= 6);
// snapshot-loader (additive, zero-network) elements present & wired
ok("loader drop zone", !!doc.getElementById("drop"));
ok("loader file input", !!doc.getElementById("file"));
ok("loader reset button", !!doc.getElementById("reset"));
ok("loader banner region", !!doc.getElementById("lbanner"));
ok("updatable header ids", !!doc.getElementById("hv") && !!doc.getElementById("hc") && !!doc.getElementById("hs"));

const failed = checks.filter(c => !c.pass);
const result = { ok: failed.length === 0, checks: checks.length,
  passed: checks.length - failed.length, failed: failed.map(f=>f.name),
  network: net.length, js_errors: errors };
console.log(JSON.stringify(result, null, 2));
process.exit(result.ok ? 0 : 1);
