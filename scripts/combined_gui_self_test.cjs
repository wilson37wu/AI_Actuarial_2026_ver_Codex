#!/usr/bin/env node
/* Offline self-test for combined_model_app.html.
 * Verifies: zero network anywhere (shell + both embedded sub-apps), structure,
 * the unified data contract, and — critically — that the projection sub-app's
 * SVG chart shim actually renders <svg> charts with NO JS errors (i.e. Chart.js
 * is genuinely gone and the offline replacement works).
 *
 * Usage: node scripts/combined_gui_self_test.cjs combined_model_app.html
 */
const fs = require('fs');
const { JSDOM, VirtualConsole } = require('jsdom');

const file = process.argv[2] || 'combined_model_app.html';
const html = fs.readFileSync(file, 'utf8');
const out = { ok: false, checks: {}, errors: [] };
function check(name, cond, detail) { out.checks[name] = !!cond; if (!cond) out.errors.push(name + (detail ? ': ' + detail : '')); }

// --- 1. pull the embedded sub-apps out of the shell ----------------------
function grab(varName) {
  const m = html.match(new RegExp(varName + '\\s*=\\s*"([A-Za-z0-9+/=]+)"'));
  return m ? Buffer.from(m[1], 'base64').toString('utf8') : null;
}
const projHtml = grab('PROJ_B64');
const viewHtml = grab('VIEW_B64');
check('proj_blob_present', projHtml && projHtml.length > 1000);
check('view_blob_present', viewHtml && viewHtml.length > 1000);

// --- 2. zero-network guarantee (shell + decoded blobs) -------------------
const shellNoBlobs = html.replace(/"[A-Za-z0-9+/=]{500,}"/g, '""'); // drop base64 blobs
const netRe = /(?:src|href)\s*=\s*"https?:\/\//i;
check('shell_no_network', !netRe.test(shellNoBlobs));
check('proj_no_network', projHtml && !netRe.test(projHtml) && !/cdnjs|chart\.umd/i.test(projHtml),
  projHtml && (projHtml.match(/https?:\/\/[^"']+/g) || []).slice(0, 3).join(','));
check('view_no_network', viewHtml && !netRe.test(viewHtml));

// --- 3. structure --------------------------------------------------------
check('has_mode_projection', /id="modeProjection"/.test(html));
check('has_mode_results', /id="modeResults"/.test(html));
check('has_frame_projection', /id="frameProjection"/.test(html));
check('has_frame_results', /id="frameResults"/.test(html));
check('has_data_loader', /id="dataFile"/.test(html) && /FileReader/.test(html));
check('proj_has_run', projHtml && /Run Projection/.test(projHtml));
check('proj_has_shim', projHtml && /svg_chart_shim|window\.mkChart\s*=\s*mkChart/.test(projHtml));
check('view_has_tabs', viewHtml && /Capital/.test(viewHtml) && /Governance/.test(viewHtml));

// --- 4. unified data contract -------------------------------------------
let appData = null;
try {
  const m = html.match(/<script id="appData"[^>]*>([\s\S]*?)<\/script>/);
  appData = JSON.parse(m[1].replace(/<\\\/script>/g, '</script>'));
} catch (e) { out.errors.push('appData parse: ' + e.message); }
check('data_has_results', appData && appData.results && appData.results.capital);
check('data_has_projection', appData && appData.projection && appData.projection.curve);
check('data_schema', appData && appData.schema === 'par-combined-app/v1');

// --- 5. FUNCTIONAL: run the projection sub-app, confirm SVG charts render -
function runDoc(label, doc, afterLoad) {
  return new Promise((resolve) => {
    const vc = new VirtualConsole();
    const jsErrors = [];
    const net = [];
    vc.on('jserror', (e) => jsErrors.push(String(e && e.message || e)));
    const dom = new JSDOM(doc, {
      runScripts: 'dangerously', pretendToBeVisual: true, virtualConsole: vc,
      resources: undefined,
      beforeParse(w) {
        w.TextDecoder = global.TextDecoder;
        // trap any network attempt
        w.fetch = () => { net.push('fetch'); return Promise.reject(new Error('no-net')); };
        const OX = w.XMLHttpRequest;
        w.XMLHttpRequest = function () { net.push('xhr'); return new OX(); };
      },
    });
    const w = dom.window;
    w.addEventListener('error', (e) => jsErrors.push(String(e.message)));
    setTimeout(() => {
      try {
        w.document.dispatchEvent(new w.Event('DOMContentLoaded', { bubbles: true }));
        if (typeof afterLoad === 'function') afterLoad(w);
      } catch (e) { jsErrors.push('DCL/afterLoad: ' + e.message); }
      setTimeout(() => {
        const svg = w.document.querySelectorAll('svg').length;
        const canvasLeft = w.document.querySelectorAll('canvas').length;
        const chartUndef = jsErrors.filter((m) => /Chart/.test(m)).length;
        resolve({ label, svg, canvasLeft, jsErrors, net, chartUndef });
        dom.window.close();
      }, 120);
    }, 60);
  });
}

(async () => {
  const proj = await runDoc('projection', projHtml);
  check('proj_renders_svg', proj.svg > 0, 'svg=' + proj.svg);
  check('proj_no_js_errors', proj.jsErrors.length === 0, proj.jsErrors.slice(0, 3).join(' | '));
  check('proj_no_chart_ref', proj.chartUndef === 0, 'Chart refs=' + proj.chartUndef);
  check('proj_no_runtime_net', proj.net.length === 0, proj.net.join(','));
  out.projection = { svg: proj.svg, canvasLeft: proj.canvasLeft, jsErrors: proj.jsErrors.slice(0, 5), net: proj.net };

  // governed reference_run: render it in the projection sub-app via runModel()
  var refRun = appData && appData.projection && appData.projection.reference_run;
  check('data_has_reference_run', !!(refRun && refRun.L && refRun.L.length), refRun ? ('months=' + (refRun.L||[]).length) : 'missing');
  var model = await runDoc('model', projHtml, function (w) {
    if (refRun && typeof w.setReferenceRun === 'function') { w.setReferenceRun(refRun); }
    if (typeof w.runModel === 'function') { w.runModel(); }
  });
  var mr = null;
  try { /* re-run to read DOM post-runModel */ } catch (e) {}
  check('model_renders_svg', model.svg > 0, 'svg=' + model.svg);
  check('model_no_js_errors', model.jsErrors.length === 0, model.jsErrors.slice(0, 3).join(' | '));
  check('model_btn_or_run', /id="btn-model"/.test(projHtml) && /function runModel/.test(projHtml));
  out.model = { svg: model.svg, jsErrors: model.jsErrors.slice(0, 5), net: model.net };

  const view = await runDoc('results', viewHtml);
  check('view_renders_svg', view.svg > 0, 'svg=' + view.svg);
  check('view_no_js_errors', view.jsErrors.length === 0, view.jsErrors.slice(0, 3).join(' | '));
  check('view_no_runtime_net', view.net.length === 0, view.net.join(','));
  out.results = { svg: view.svg, jsErrors: view.jsErrors.slice(0, 5), net: view.net };

  out.ok = Object.values(out.checks).every(Boolean);
  console.log(JSON.stringify(out, null, 2));
  process.exit(out.ok ? 0 : 1);
})();
