# Cycle Status — 2026-07-10 — §4.1 #11 Mortality Credibility Blending & Improvement (ASOP 25)

**Agent:** Claude Cowork (`actuarial-model-daily-improvement`)
**Item:** roadmap §4.1 #11 — Mortality improvement + credibility blending (ASOP 25) for qx tables
**Outcome:** DONE — highest-priority OPEN general-backlog item completed. §4.1 #1–#11 now all DONE.
**Governed headline:** UNTOUCHED (TVOG / aggregation). Change is purely additive.

## Delivered

- **Engine** `par_model_v2/projection/mortality_credibility.py` (schema
  `mortality-credibility-blend-1.0`): credibility-blended, improvement-projected
  `qx` generator.
  - Credibility (ASOP 25): limited-fluctuation (classical square-root rule,
    full-credibility death standard `λ_F=(z_{(1+p)/2}/k)²≈1082.2` at p=.90/k=.05)
    **and** Bühlmann (`Z=n/(n+K)`, `K=EPV/VHM`). Blend =
    `Z·AE_obs+(1−Z)·1` (complement = standard table). `aggregate` / `by_age`
    granularity. scipy-free `norm_ppf` (Acklam).
  - Improvement: age-tapered static (attained-age) projection
    `qx(v)=qx(base)·(1−MI_x)^(v−base)`.
  - Reads the governed `_base_annual_qx`; never mutates it.
- **Builder** `scripts/build_mortality_credibility_table.py` →
  `docs/validation/MORTALITY_CREDIBILITY_BLEND.json` (both genders, pinned
  digests, UNSIGNED) + report `docs/MORTALITY_CREDIBILITY_BLEND.md`.
- **Card** `docs/MORTALITY_CREDIBILITY_BLENDING_CARD.md`.
- **Assumptions register** `docs/ASSUMPTIONS_REGISTER.md` §3.A — mitigation note
  for gaps #1 (ASOP 25 credibility/basis) and #2 (no improvement factors).

## Verification

- New suite `tests/test_mortality_credibility.py`: **31/31 GREEN** (real
  `unittest`; runnable `python3 -m unittest tests.test_mortality_credibility`).
- Affected existing pytest-style suites via the minimal pytest shim (self-checked
  to detect planted failures): `test_monthly_projection.py` **62/62**,
  `test_data_validator.py` **63/63**.
- **Additive-only proof:** `git diff --stat` empty — zero existing source files
  modified; only 5 new files added (+ docs).
- Output passes `MortalityTableValidator`; governed `_base_annual_qx`
  byte-identical (regression-locked).
- scipy/pytest unavailable in the network-restricted sandbox (pip offline) — new
  tests are numpy-only unittest by design.

## Blockers / next

- No blockers. Adoption of a blended table as the governed base is **owner-gated**
  (sign-off + independent APS X2 review) — disclosed, never self-approved.
- **Next OPEN:** §4.1 #12 — model-health-check expansion (VR-H11 calibration
  drift, VR-H12 scenario-file schema hash).
