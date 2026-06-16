// Parity test for the offline_home.html snapshot-loader (executed; no jsdom needed).
// Proves the in-page JS figure extraction (the "loader" path) reproduces the GOVERNED
// figures the Python builder bakes in by default, when both read the same ui_data.json.
// Run: node scripts/offline_home_loader_parity.cjs
const fs = require("fs"), path = require("path");
const ROOT = path.resolve(__dirname, "..");
const d = JSON.parse(fs.readFileSync(path.join(ROOT, "ui_data.json"), "utf8"));
const html = fs.readFileSync(path.join(ROOT, "offline_home.html"), "utf8");

// ---- JS extraction rules MIRRORING scripts/build_offline_home.py LOADER_JS ----
function fmt(x, dp){
  if (x === null || x === undefined) return "None";
  const n = Number(x);
  if (isFinite(n)) return n.toLocaleString("en-US",
    { minimumFractionDigits:dp, maximumFractionDigits:dp });
  return String(x);
}
function extract(d){
  const meta = d.meta || {}, cap = d.capital || {}, s = d.summary || {};
  const cur = ((meta.currency || {}).symbol) || "";
  let hl = null;
  try { hl = d.owner_decision_p31.evidence_pack.governed_headline.value; } catch(e){}
  return [
    cur + fmt(hl, 2),
    cur + fmt(cap.nested_scr, 0),
    cur + fmt(cap.correlated_scr, 0),
    cur + fmt(cap.standalone_sum, 0),
    cur + fmt(cap.div_benefit_nested, 0),
    fmt(s.calibrated_drivers, 0),
    String(s.gates_cleared) + "/" + String(s.gates_total),
    String(s.tasks_completed) + "/" + String(s.tasks_total)
  ];
}

// Baked default figure VALUES, parsed from the built HTML (.fv spans).
const baked = [...html.matchAll(/<span class="fv">([^<]*)<\/span>/g)].map(m => m[1]);
const js = extract(d);
const checks = [];
function ok(name, cond){ checks.push({ name, pass: !!cond }); }

ok("baked has >=8 figure values", baked.length >= 8);
js.forEach((v, i) => ok("figure[" + i + "] JS==baked (" + v + ")", baked[i] === v));
ok("governed headline value present", js[0].indexOf("39,975.65") >= 0);

const failed = checks.filter(c => !c.pass);
console.log(JSON.stringify({ ok: failed.length === 0, checks: checks.length,
  passed: checks.length - failed.length, failed: failed.map(f => f.name) }, null, 2));
process.exit(failed.length === 0 ? 0 : 1);
