# Phase 32 Task 3 - User-Input Run-Result Surface (gap G2)

**Verdict: PASS** | contract 1.14.0 -> **1.15.0 (ADDITIVE)** | display-layer only - NO model parameter changes

## What changed

`ui_app.html` gains a **User Run (UIL)** tab that surfaces the latest `scripts/run_model.py` evidence VERBATIM: headline SCRs (nested 71,112.1; gaussian copula 49,825.9; var-covar 37,625.9), per-driver standalone SCRs, tail bootstrap CIs, the run configuration with per-setting provenance, model-point counts (2 PAR rows), the validated input chain (model_inputs.json -> par_model_v2.user_inputs loader -> run_model), the stamped currency/output_label display provenance ('docs/validation/RUN_MODEL_SUMMARY.json (latest run_model.py evidence)'), the book-scaling DISCLOSED APPROXIMATION and the use restrictions.

## Pre-registered acceptance criteria (G2)

- renders exclusively from embedded model-output JSON: **PASS** (summary + report blocks bit-for-bit)
- graceful neutral fallback: **PASS** (dedicated jsdom test: no JS errors, no blank tab, no leaked figures)
- currency/output_label provenance exactly as stamped: **PASS** (bit-identical to meta)
- ADDITIVE-only contract change: **PASS** (pre-existing keys bit-identical; inventory gains new entries only)
- self-tests: ui_app ok:true (223 checks, 0 network / 0 JS errors); viewer + combined GUI green
- zero-install preserved: 0 external references, single file
- NO model parameter changes: display layer only

## Governance

- ChangeRecord `fcdac39175ea472f8edadd9dd8aa3249` (OWNER_REVIEW)
- audit integrity: True

Next: **Task 4 (gap G3)** - governed read-out completeness sweep.