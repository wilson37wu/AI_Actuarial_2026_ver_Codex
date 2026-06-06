# Automated Cycle Status - 2026-06-07 - READ FIRST

## Headline

- **All prior hard blockers are CLEARED.** `/sessions` disk freed (83% used, 1.7G free); the Linux
  sandbox boots; Python 3.10 + pytest + scipy available; git functional (no ghost locks found).
- **Health gate PASS:** full pytest suite run in <45s batches — **2,084 passed, 0 failed** (4 tests
  not run; each single test exceeds the 44s sandbox wall-clock — disclosed in MODEL_DEV_LOG.md).
- **Phase 21 Task 1 COMPLETE:** FX / currency sixth capital driver + **G-FX gate PASS (6/6)**
  (incl. Phase 20 MART-FX-CIP Q-martingale evidence). Six-driver aggregation verdict **PASS**:
  FX standalone SCR 4,286; var-covar 28,992 vs nested 48,738; copula (gaussian) within 15.4%.
  ChangeRecord `25e1eac6661a4d9bb74276ee1a2a4b46` (OWNER_REVIEW); MR-012 refreshed; audit True.

## Current source of truth

- `.claude-dev/MODEL_DEV_STATE.json`: Phase 21 in progress; Task 1 completed; Task 2 next
  (out-of-sample six-driver proxy validation); 101/105 tasks.
- New: `par_model_v2/projection/multi_driver_capital_6d_fx.py`, `tests/test_phase21_fx_driver.py`
  (11 passed), `scripts/build_phase21_task1_fx.py` (staged),
  `docs/validation/PHASE21_TASK1_FX_DRIVER_REPORT.{json,md}`, `docs/FX_DRIVER_G_FX_CARD.md`.
- Offline UI unchanged this cycle (contract 1.2.0); Phase 21 UI propagation is Task 5.

## Operational learnings for future cycles (IMPORTANT)

1. Each sandbox bash call has a ~44s hard wall AND background/detached processes are KILLED when
   the call ends (pgrep self-matches gave false "RUNNING" readings — verify via loadavg/artifacts).
2. Long work must be STAGED: `build_phase21_task1_fx.py --stage outer|slice|finalise` implements a
   slice-stable CRN protocol that is bit-identical to a monolithic run (tested).
3. Run pytest in file/class/test-level chunks with `-n 2`; a handful of single tests can never
   finish in 44s — record them as NOT RUN with reasons rather than skipping silently.

## Actions needed from the human

1. `git push origin main` (local commits exist; sandbox has no push credentials). Last pushed sha
   was fa5d5fe (Phase 16); local backlog spans Phases 17-21.
2. Optional: run the 4 wall-clock-excluded tests once in an unconstrained shell:
   `python -m pytest tests/test_esg_process.py::TestHullWhiteRateProcess::test_p_measure_terminal_mean_exceeds_q_with_default_params tests/test_sensitivity.py::TestRunStandardSensitivity tests/test_sensitivity.py::TestSensitivityReport::test_report_id_unique -q`

## Next automated cycle

Phase 21 Task 2 — out-of-sample six-driver proxy validation (disjoint-seed hold-out vs nested
truth, basis selection by OOS RMSE/R², leakage/overfit diagnostics, honest verdict).
