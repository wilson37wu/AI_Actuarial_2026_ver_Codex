# G-05 Runtime Measure Enforcement — Phase 14 Task 1

**Gate:** G-05 — P/Q Measure Runtime Enforcement
**Risk:** MR-004 (P/Q measure not enforced at runtime) → **MITIGATED**
**Date:** 2026-06-04
**Standards:** SOA ASOP 56 §3.1.3 (measure appropriateness for model purpose); IA TAS M §3.4 (consistency and segregation of bases)

## What changed

Runtime measure enforcement previously existed only at the two material **consumers**
(`RiskMetrics` requires `Measure.P`; `TVOGEngine` requires `Measure.Q`). Phase 14 Task 1
adds enforcement at the **producer** side so the P/Q contract is checked at the entry of
every scenario-generation execution path.

New code in `par_model_v2/stochastic/esg_process.py`:

- `MeasureEnforcementError(ValueError)` — raised on unsupported or mismatched measures.
- `_enforce_simulation_measure(process, measure)` — single runtime entry-point guard.
  Coerces the requested measure and validates it against the calling generator's declared
  `SUPPORTED_MEASURES`. Accepts an instance, a class (for classmethods), or a string label.
- `_assert_output_measure(frame, measure, label)` — post-condition that verifies every
  output row carries the requested measure stamp (catches silent mis-stamping).
- `SUPPORTED_MEASURES = (Measure.P, Measure.Q)` declared on `HullWhiteRateProcess`,
  `G2PlusRateProcess`, `GBMEquityProcess`, `FXSpotProcess`, and `ScenarioSet`.

Guard applied to all five generation paths:

| Path | Entry guard | Output post-condition |
|------|-------------|----------------------|
| `HullWhiteRateProcess.simulate` | ✅ | ✅ |
| `G2PlusRateProcess.simulate` | ✅ | ✅ |
| `GBMEquityProcess.simulate` | ✅ | ✅ |
| `FXSpotProcess.simulate` | ✅ | ✅ |
| `ScenarioSet.generate` | ✅ | ✅ |

## Why this clears the historical blocker

Earlier runs could only attach **static** source evidence because the reachable interpreter
lacked `numpy`, `pandas`, `scipy`, and `pytest`. The automation sandbox now provides them, so
the guards are **executed** and verified at runtime.

## Runtime execution evidence

- Suite: `tests/test_measure_enforcement.py` — **30 passed**
- Machine-readable record: `docs/G05_RUNTIME_EVIDENCE_2026-06-04T103044Z.json`
- Regression (no behavioural change for valid P/Q requests): `test_esg_process.py` (79),
  `test_tvog.py` (28, incl. VR-T01 P-measure rejection), `test_risk_metrics.py` (46),
  `test_schema_compatibility.py`, `test_integration_e2e.py`, `test_esg_adapter.py`,
  `test_governance.py`, `test_ia_validation.py`, `test_phase13_ia_validation.py` — all PASS.
- Static guard verifier `scripts/verify_measure_guards.py` — PASS.

## Residual

Full production closure additionally requires an independent reviewer to confirm complete
consumer coverage. MR-004 is therefore **MITIGATED** (not fully CLOSED) and G-05 is cleared
at **educational** level.
