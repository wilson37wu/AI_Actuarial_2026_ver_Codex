# Model-Health Check Card — VR-H11 & VR-H12 (roadmap §4.1 #12)

**Status:** DELIVERED 2026-07-10 — auto-admissible governance addition, purely additive.
**Module:** `par_model_v2/validation/model_health.py` (10 → 12 automated health checks).
**Standards:** SOA ASOP 56 §3.5 (ongoing model-health monitoring); IA TAS M §3.3 (governance
traceability via the GovernanceStore VALIDATION audit entry).

## VR-H11 — Two-factor (G2++) rate-calibration drift
- **Monitors:** the live governed default calibration `G2PlusParams` (`esg_process.py`):
  `mean_reversion_x=0.10`, `mean_reversion_y=0.35`, `vol_x=0.010`, `vol_y=0.006`,
  `factor_correlation=−0.70`, `long_run_rate_p=0.025`, `market_price_of_risk_x=−0.10`,
  `market_price_of_risk_y=−0.05`.
- **How:** `compute_calibration_drift(ref, cand, warn_tol=0.02, fail_tol=0.05)` — per-parameter
  relative drift `|cand−ref| / max(|ref|, 1e-6)`; **PASS** ≤2%, **WARN** ≤5%, **FAIL** >5% or on any
  structural (missing/extra key) change.
- **Pinned reference digest:** `e0c55f3c5001a8282dcf6d2b0d5ae060569f5c821d9f3878ef36cf712f7d43bc`
  (canonical sha256 of the reference snapshot).
- **Self-test:** the check injects a +10% perturbation and asserts it is caught, so a broken
  monitor cannot pass silently.
- **On delivery:** live == reference → `max_drift = 0.0` → PASS.

## VR-H12 — ESG scenario-file schema hash
- **Monitors:** the live scenario-file column schema `esg_adapter._REQUIRED_COLUMNS` (7 required
  columns → dtype-kind codes): `scenario_id`, `month`, `r_short`, `zcb_1y`, `zcb_10y`,
  `equity_index`, `measure`.
- **How:** `_scenario_schema_fingerprint()` — canonical sha256 over the ordered `(name, kind_codes)`
  pairs.
- **Pinned fingerprint:** `9b2c4bec8d2a535fb10a249dd1845194f592861dbdcaa0a3843067da9e243938`.
- **Trips (FAIL) on:** any add / remove / rename of a required column, or a dtype-kind change — a
  tripwire for unreviewed scenario-file contract changes.

## Governance
- Both pins are **OWNER-GATED** to move: a legitimate recalibration (VR-H11) or an approved
  scenario-schema/contract change (VR-H12) must be signed off before the pinned digest/hash is
  re-baselined. The checks never self-approve a new baseline; they surface drift for review.
- Purely additive: no model-FORM / contract / headline change. Governed artifacts byte-stable
  (`offline_home.html` `03d6538d…`, `ui_data.json` `1.23.0`, headline `39975.654628199336`).
- Tests: `tests/test_model_health.py` — **63 PASS** (pytest, pinned engine lock).
