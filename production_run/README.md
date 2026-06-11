# production_run/ — run the model without touching developer code

Everything a **user** needs to carry out a model run lives in this folder.
Everything else in the repository is developer territory:

| folder | who touches it |
|---|---|
| `production_run/` | **you (the user)** |
| `par_model_v2/` | developers only — core calculation logic |
| `scripts/` | developers only — staged phase-build / validation scripts |
| `tests/` | developers only |
| `docs/` | reference reports + `docs/cycle_status/` (agent run logs) |

## Quick start

```bash
# 1. Full run (ESG + assets + liabilities + stochastic interaction)
python3 production_run/run_production_model.py --stage all

# 2. Rebuild the offline GUI from the results
python3 production_run/build_gui.py

# 3. Open ui_app.html (repo root) in any browser — works fully offline
```

Requirements: Python 3 with `numpy`, `scipy`, `pandas`. No other install;
the GUI itself needs nothing at all (single self-contained HTML file).

## What's in here

| file | purpose |
|---|---|
| `run_production_model.py` | One-command run: `esg`, `assets`, `liabilities`, `interaction`, or `all`. Results land in `production_run/output/*.json`. |
| `build_gui.py` | Refreshes `ui_data.json` + `ui_app.html` from the current result files (display only, no calculation). |
| `MODEL_INPUTS_TEMPLATE.xlsx` | The input workbook (asset balances, portfolio, assumptions). |
| `USER_MANUAL_run_and_inputs.md` | The full manual: which script to run when, input conventions, currency handling. |

## Stages

- **esg** — Economic Scenario Generator: Q-measure short-rate / equity / FX
  paths, dimension- and measure-validated. `--scenarios` (default 1,000) and
  `--seed` (default 42) are reproducible.
- **assets** — asset cash-flow / fixed-income pricing run.
- **liabilities** — liability cash-flow valuation (HK participating endowment).
- **interaction** — the stochastic model reflecting the asset↔liability
  interaction: TVOG (guarantee cost across stochastic paths) and a dynamic
  ALM projection where asset returns, crediting and liability cash flows
  interact path by path.

## Not yet wired in

`scripts/load_user_inputs.py` / `scripts/run_model.py` (reading your own
numbers from `MODEL_INPUTS_TEMPLATE.xlsx` into the run) are **planned but not
yet implemented** — see `IMPLEMENTATION_PLAN_currency_and_inputs.md`. Until
then the stages run on the governed example portfolio.

## Status

MODEL-USE RESTRICTION: all parameters are educational placeholders pending
credentialled data and independent review (ASOP 56 §3.5 / TAS M §3.2).
"Production run" refers to the workflow, not regulatory sign-off.
