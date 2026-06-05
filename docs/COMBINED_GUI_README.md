# Combined GUI — one offline file, two modes

`combined_model_app.html` merges the two former interfaces into a single
self-contained, **offline** application. Double-click it; no install, no server,
no network.

## What it contains

| Mode | Source GUI | Purpose |
|------|-----------|---------|
| 📈 **Projection** | `par_projection_gui.html` | Interactive input → run → illustrate. Product / Assets / Assumptions / Stress / Results tabs, presets, yield curves, live in-browser projection engine. |
| 📊 **Results** | `model_result_viewer.html` | Offline result dashboard: Capital / Aggregation / Proxy / Governance, reading pre-computed model output. |

The two apps are embedded in isolated `<iframe srcdoc>` containers, so their CSS
and JavaScript never collide. A thin shell adds the mode switch and one shared
data loader.

### Fully offline — what changed
The projection GUI previously loaded **Chart.js from a CDN**, which breaks the
project's no-network mandate. That dependency is removed and replaced by an
inline SVG chart renderer (`par_model_v2/viewer/svg_chart_shim.js`) that
re-implements exactly the chart types it used (line, stacked/grouped bar,
doughnut, dual-axis). The results dashboard already used hand-rolled SVG. Net
result: **zero `http(s)://` references anywhere**, verified by the self-test.

## Recommended way to consume an output data file (the advice you asked for)

The design follows a **"model computes, UI only displays"** contract and supports
three consumption paths — use them in this priority order:

1. **Embedded snapshot (default, most robust).** `scripts/build_combined_gui.py`
   bakes the current `combined_app_data.json` straight into the HTML at build
   time. The file opens already populated — nothing to load, nothing to break,
   works on a machine with no model and no network. This is the recommended
   distribution form: re-run the bundler whenever the model output changes and
   hand someone the single HTML.

2. **Drag-and-drop / file-picker (ad-hoc).** Drop a `combined_app_data.json`
   (or a bare `viewer_data.json`) onto the header, or use *Load data file*. The
   shell routes `results` → the Results dashboard's `render()` and `projection`
   → the Projection mode's seed, both via `postMessage`. Good for comparing runs
   without rebuilding.

3. **One unified file, not many.** Keep a **single** enriched output file rather
   than separate per-panel JSONs. One file is easier to version, hash, and ship,
   and it guarantees the two modes show the *same* run.

Why a data file at all (vs. computing in the UI): it keeps the heavy/stochastic
numerics in the governed Python model (reproducible, testable, audit-trailed)
and keeps the UI a pure, dependency-free viewer — the same separation the
result-viewer mandate already requires.

## Enriched unified data contract — `combined_app_data.json`

One file now captures **both** GUIs:

```jsonc
{
  "schema": "par-combined-app/v1",
  "meta":   { model_name, model_version, generated_utc, classification, ... },
  "results": {            // == viewer_data.json (drives Results mode)
     "meta", "verdicts", "summary",
     "capital", "tail", "proxy", "loss", "governance"
  },
  "projection": {         // drives Projection mode (NEW)
     "scenario_name", "curve", "preset", "auto_run",
     "inputs": { elementId: value },        // applied if the id exists
     "assumptions_snapshot": { discount_rate, ph_share, lapse_schedule_pct, ... },
     "available_curves", "available_presets"
  }
}
```

`results` is produced by the existing model pipeline (`scripts/build_offline_viewer.py`
→ `viewer_data.json`). `projection` records the saved scenario (starting curve,
asset preset, key inputs) so a projection is reproducible from the file; the
Projection engine still computes live in-browser.

## Rebuild

```bash
python3 scripts/build_combined_gui.py          # -> combined_model_app.html + combined_app_data.json
node    scripts/combined_gui_self_test.cjs combined_model_app.html   # offline gate: ok:true
```

The self-test decodes both embedded sub-apps and asserts: zero network in the
shell **and** both blobs, the mode switch + data loader exist, the data contract
has `results` + `projection`, and — by executing the projection sub-app in jsdom
— that the SVG shim renders real charts with **0 JS errors and 0 Chart.js
references**.

## Governed model result in Projection mode (implemented)
`projection.reference_run` is now produced by the **governed Python model**
(`par_model_v2.projection.monthly_projection.run_full_projection`) via
`scripts/build_projection_reference.py` → `docs/validation/PROJECTION_REFERENCE_RUN.json`,
and embedded into `combined_app_data.json` under `projection.reference_run`.

In the Combined GUI, Projection mode loads this and renders the **governed**
numbers by default (banner: 🏛 GOVERNED MODEL): metrics, the liability/
asset/asset-share charts, the data tables, and the policy illustration all come
from the Python model. A **▶ Run (in-browser)** button still recomputes the
original educational JS engine for side-by-side comparison; **🏛 Show model
result** re-renders the governed run.

The schema matches the GUI's result object exactly (monthly `L`/`A`/`S` arrays +
PV summary). To support the in-force/RB chart, the model now also emits per-month
`rb_accum` and `asset_share_proxy` columns (additive change to
`monthly_projection.py`; 62/62 tests still pass).

## Status / limitations
- Educational only — same classification as the underlying model.
- The governed reference run is a single representative policy (20Y CNY par
  endowment, balanced fund, 3.0% discount); edit `scripts/build_projection_reference.py`
  to change the scenario, then rebuild.
