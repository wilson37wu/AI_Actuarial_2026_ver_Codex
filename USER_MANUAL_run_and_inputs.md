# Actuarial Stochastic Capital Model — User Manual: Inputs, Execution, and GUI

**Audience:** a non-developer who wants to feed their own inputs into the model and produce the interactive offline GUI (`ui_app.html`).
**Scope:** how the pieces fit together, which Python file to start with, what to put in the input template, how parameters are applied, and how to run the calculation through to the GUI.
**Classification:** EDUCATIONAL. Outputs are not for production capital, dividend, or reporting decisions without credentialled data and an independent APS X2 review.

---

## 1. The big picture — two layers

The system has two distinct layers. Understanding the split answers most "which file do I run?" questions.

**Layer A — the calculation engine.** A library (`par_model_v2/`) plus a set of staged build scripts (`scripts/build_phaseXX_taskY_*.py`). These take the inputs (asset balances, portfolio, calibrated risk drivers, assumptions), run the Monte-Carlo projection and the copula capital aggregation, and write machine-readable result files into `docs/validation/*.json`.

**Layer B — the offline GUI.** A single no-calculation bundler, `scripts/build_ui_data.py`, scans the result files from Layer A, normalises them into one `ui_data.json` contract, and embeds that snapshot into a self-contained `ui_app.html`. The GUI **only displays** model output — it never re-runs a calculation, needs no install, and works offline.

```
   Inputs (your numbers)                Layer A: calculation              Layer B: GUI
 ┌───────────────────────┐      ┌──────────────────────────────┐   ┌────────────────────┐
 │ MODEL_INPUTS_TEMPLATE  │  →   │ par_model_v2 + build_phaseXX  │ → │ build_ui_data.py    │ → ui_app.html
 │ .xlsx (you fill this)  │      │ → docs/validation/*.json      │   │ → ui_data.json+HTML │    (open in browser)
 └───────────────────────┘      └──────────────────────────────┘   └────────────────────┘
```

---

## 2. Which `.py` do I start with?

It depends on what you want to do right now.

| Goal | Start with | Needs Python? |
|---|---|---|
| **Just look at the latest results** | Double-click **`ui_app.html`** | No |
| **Rebuild the GUI** from the current result files | **`scripts/build_ui_data.py`** | Yes |
| **See the model workflows run end-to-end** (demo data) | **`par_model_v2/examples/guided_examples.py`** → `run_all_examples()` | Yes |
| **Re-run a specific capital calculation** (current staged data) | the relevant **`scripts/build_phaseXX_taskY_*.py`** | Yes |
| **Run the model on YOUR inputs** | the **input loader + orchestrator** described in §4 (being added — see the Implementation Plan) | Yes |

**Short answer:** to refresh the GUI from whatever results exist, you start with **`scripts/build_ui_data.py`**. To run the model on *your own* numbers and then refresh the GUI, you start with the **input loader** (§4), which reads `MODEL_INPUTS_TEMPLATE.xlsx`, then `build_ui_data.py`.

> **Today vs. target.** Right now the calculation scripts read *synthetic, staged* inputs (e.g. a backing asset value of 100,000 baked into a fixture). The input loader that reads your Excel template is the next implementation step (it is fully specified in `IMPLEMENTATION_PLAN_currency_and_inputs.md`). Until it is wired in, you can already (a) open and explore `ui_app.html`, and (b) rebuild the GUI with `build_ui_data.py`. Once the loader is in, §4 becomes the full user run.

---

## 3. What inputs to provide — the Excel template

Open **`MODEL_INPUTS_TEMPLATE.xlsx`**. Fill the **blue/yellow** cells; leave the **grey/italic** cells alone (they are model-governed). There are six tabs.

### Colour legend
- **Blue text** — a value you enter.
- **Yellow cell** — a key input that must be set before running.
- **Grey / italic** — governed / calibrated; do not change without re-validation.

### 3.1 Currency tab — replaces the hardcoded "CNY"
| Field | Example | What it does |
|---|---|---|
| Reporting currency code | `USD` | The 3-letter code shown on every monetary figure. |
| Reporting currency symbol | `$` | The symbol shown next to amounts in the GUI. |
| Decimal places | `0` | Decimals on currency amounts. |
| Amount scale | `units` | Whether your monetary inputs are in units / thousands / millions. |
| Calibration market label | `Local market` | The provenance label that currently reads "CNY". Describes the market the drivers were fit to. |
| Valuation date | `2026-01-01` | As-of date written to output metadata. |

Setting the code/symbol/scale **relabels** all outputs. Using a genuinely different *calibration market* (different yield curve, equity index, credit spreads) means supplying that market's data — see the Implementation Plan, "Full re-currency."

### 3.2 Balance Sheet tab — your assets and liability
Enter the **market value of each asset class** and flag whether each is **illiquid**. The template derives:
- **Total backing asset MV** = sum of the class values.
- **Illiquid MV** and **illiquid share** = the illiquid classes ÷ total.

Then set the **forced-sale fraction** (the mass-lapse shock, default 0.40), the **best-estimate liability** (your reserve), and the **equity-guarantee initial index level**. These replace the synthetic balance-sheet fixture (asset MV 100,000, illiquid share 0.55, forced-sale 0.40 → liquidity exposure notional 22,000). The liquidity exposure notional the model uses is `illiquid MV × forced-sale fraction`.

### 3.3 Portfolio tab — your in-force book
Each row is a **group of like policies** (a model point), replacing the synthetic 100,000-policy generator. Columns: product type, issue age, gender, term, sum assured, annual premium, policy count, vested bonus. Three worked examples are pre-filled; add as many rows as you need, keeping the headers. Product types: `HKCD_PAR` (cash dividend par), `HKRB_PAR` (reversionary bonus par), `GMMB_EQ` (equity guarantee).

### 3.4 Assumptions tab — confidence + relief scalars
- **Confidence level** — the capital level (default `0.995` = 1-in-200, Solvency II).
- **Management-action relief scalars** — `sigma` (0.225), `alpha` (0.7567), `benefit share / beta` (0.8450). These are governed defaults; override only with documented justification.
- The **governed / frozen** block (grey) shows, read-only: the copula degrees of freedom (single-df t = 2.9451), the grouped-t block dfs (NON-FIN 37.866 / FIN 8.506), the seven drivers, and the fact that the **governed headline copula is the single-df t** (the conservative boundary; the grouped-t is disclosed, not adopted). Do not edit these without re-running the calibration/validation cycle.

### 3.5 Run Settings tab
- **Number of simulations** — outer Monte-Carlo paths (20,000 standard; 200,000 for the canonical reference run).
- **Random seed** — fixes reproducibility; keep constant to reproduce a run.
- **Bootstrap replicates** — replicates for the SCR confidence interval (200).
- **Projection horizon** — months (12).
- **Output label** — a tag written into the outputs and shown in the GUI.

---

## 4. How to run the calculation (target workflow)

> These are the steps once the input loader (Implementation Plan) is wired in. They assume Python 3 is available. In this sandbox, scientific libraries live under `/var/tmp/pylibs`, so prefix commands with `PYTHONPATH=/var/tmp/pylibs:.`; on a normal machine, install the packages in `requirements.txt` once (`pip install -r requirements.txt`) and drop the `/var/tmp/pylibs:` prefix.

**Step 1 — fill and save the template.** Complete `MODEL_INPUTS_TEMPLATE.xlsx` (§3) and save it in the model folder.

**Step 2 — load your inputs.** Run the loader to validate the workbook and emit a normalised `model_inputs.json`:
```
PYTHONPATH=/var/tmp/pylibs:. python3 scripts/load_user_inputs.py --template MODEL_INPUTS_TEMPLATE.xlsx --out model_inputs.json
```
The loader checks ranges (e.g. shares in 0–1, positive asset values), echoes the currency and totals, and stops with a clear message if anything is missing.

**Step 3 — run the model.** The orchestrator consumes `model_inputs.json`, runs the projection + capital aggregation, and writes the result JSONs:
```
PYTHONPATH=/var/tmp/pylibs:. python3 scripts/run_model.py --inputs model_inputs.json
```
This produces the standalone driver losses, the copula aggregation (single-df t headline + grouped-t diagnostic), the bootstrap SCR confidence interval, and the tail diagnostics — into `docs/validation/*.json`.

**Step 4 — build the GUI.** Bundle the results into the offline viewer:
```
PYTHONPATH=. python3 scripts/build_ui_data.py
```
Outputs (in the model folder): **`ui_data.json`** and **`ui_app.html`**.

**Step 5 — open the GUI.** Double-click **`ui_app.html`** in any modern browser. No server, internet, or install. You can also drag a different `ui_data.json` onto the page to load another run.

### What you can do today (before the loader is wired in)
- **View:** double-click `ui_app.html`.
- **Rebuild the GUI** from the current result files:
  ```
  PYTHONPATH=. python3 scripts/build_ui_data.py
  ```
- **See the engine run on demo data:**
  ```
  PYTHONPATH=/var/tmp/pylibs:. python3 -c "from par_model_v2.examples.guided_examples import run_all_examples; run_all_examples()"
  ```

---

## 5. Reading the GUI

The GUI opens with the embedded snapshot pre-loaded. Core tabs:
- **Overview** — headline roll-up (tasks/phases/gates/risks) and the nested 99.5% SCR.
- **Inventory & Contract** — every result artifact, content-addressed (SHA-256), with the `ui_data.json` schema.
- **Calibrations** — per-driver explorer with gate criteria, calibrated parameters, and fit-diagnostic charts.
- **Capital & Tail** — the seven-driver SCRs, the standalone → var-covar → copula → nested aggregation, VaR/ES with 95% bootstrap CIs, and convergence.
- **Governance** — deployment gates, the model-risk register heatmap, the change-record approval trail, and a recomputed audit-integrity badge.

Phase deep-dive tabs surface the dependence-structure track, including **Grouped-t Tail (P28)**: grouped-t vs single-df t vs nested SCR, the within/cross-block tail-dependence and cross-block dilution, the residual widening, and MR-016. The GUI can export charts to PNG, tables to CSV, and the whole report to PDF (browser "Save as PDF").

---

## 6. How parameters flow (so you know what changes what)

- **Currency tab** → output **labels and scale** only. It does not change any number; it changes how numbers are displayed and described.
- **Balance Sheet tab** → the **asset side and the liquidity exposure**. Asset MV and the illiquid/forced-sale inputs set the liquidity-driver exposure notional; the liability/reserve sets the size of the liability the capital protects.
- **Portfolio tab** → the **liability projection**. The model points drive the cash-dividend / reversionary-bonus / guarantee mechanics that produce the liability paths.
- **Assumptions tab** → the **capital level and management-action relief**. Confidence sets the SCR percentile; the relief scalars set how much management actions offset adverse scenarios. The frozen copula/df govern the *dependence* between drivers and are not user inputs.
- **Run Settings tab** → **run control** (accuracy vs. speed via simulation count, reproducibility via seed, CI width via bootstrap replicates).

---

## 7. Tips and gotchas

- **Keep the headers.** The loader reads by tab name + column header. You can add portfolio rows and asset classes, but don't rename or reorder the header cells.
- **Match the scale.** If you set "Amount scale = thousands" on the Currency tab, enter every monetary value in thousands consistently.
- **Reproducibility.** Same inputs + same seed = identical outputs. Change the seed only to test Monte-Carlo noise.
- **Governed cells.** If you must change a grey/frozen parameter, that is a model change, not an input — it needs a re-validation cycle and a governance change record.
- **Sandbox libraries.** If a run reports `No module named scipy`, add `PYTHONPATH=/var/tmp/pylibs:.` to the command (sandbox) or `pip install -r requirements.txt` (your machine).

---

*Companion documents: `MODEL_INPUTS_TEMPLATE.xlsx` (the input template) and `IMPLEMENTATION_PLAN_currency_and_inputs.md` (the code changes that wire the template and the generic currency into the engine).*
