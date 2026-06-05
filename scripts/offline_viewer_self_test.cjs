const fs = require("fs");
const path = require("path");
const { JSDOM, VirtualConsole } = require("jsdom");

const htmlPath = process.argv[2] || path.join(process.cwd(), "model_result_viewer.html");
const html = fs.readFileSync(htmlPath, "utf8");
const errors = [];
const networkCalls = [];
const virtualConsole = new VirtualConsole();

virtualConsole.on("jsdomError", err => errors.push(String(err && err.message || err)));

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
      open(_method, url) { networkCalls.push(["xhr", String(url)]); }
      send() { throw new Error("offline self-test blocked XMLHttpRequest"); }
    };
  },
});

const done = (ok, checks) => {
  console.log(JSON.stringify({ ok, checks, errors, networkCalls }, null, 2));
  process.exit(ok ? 0 : 1);
};

setTimeout(() => {
  const { document, exportSvgToPng } = dom.window;
  const tabs = [...document.querySelectorAll(".tab")];
  tabs.forEach(tab => tab.click());
  const checks = {
    embeddedLoaded: /PAR Fund|Stochastic|Actuarial/i.test(document.body.textContent),
    tabCount: tabs.length,
    svgCount: document.querySelectorAll("svg").length,
    exportButtons: [...document.querySelectorAll("button")].filter(b => b.textContent.trim() === "Export PNG").length,
    printButton: !!document.getElementById("printView"),
    filePicker: !!document.getElementById("file"),
    dropZone: !!document.getElementById("drop"),
    networkCalls: networkCalls.length,
    jsErrors: errors.length,
    exportFunction: typeof exportSvgToPng === "function",
    canvasExportSource: String(exportSvgToPng || "").includes("createElement(\"canvas\")"),
  };
  const ok = checks.embeddedLoaded && checks.tabCount >= 4 && checks.svgCount >= 6
    && checks.exportButtons >= checks.svgCount && checks.printButton
    && checks.filePicker && checks.dropZone && checks.networkCalls === 0
    && checks.jsErrors === 0 && checks.exportFunction && checks.canvasExportSource;
  done(ok, checks);
}, 350);
