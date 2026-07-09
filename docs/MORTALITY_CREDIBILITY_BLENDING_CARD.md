# Mortality Credibility Blending & Improvement — Model Card

**Roadmap:** §4.1 #11 (Accuracy) — mortality improvement + credibility blending (ASOP 25)
**Module:** `par_model_v2/projection/mortality_credibility.py`
**Evidence:** `docs/validation/MORTALITY_CREDIBILITY_BLEND.json` · report `docs/MORTALITY_CREDIBILITY_BLEND.md`
**Builder:** `scripts/build_mortality_credibility_table.py`
**Tests:** `tests/test_mortality_credibility.py` (31 tests, unittest + numpy)
**Status:** UNSIGNED — educational; governed `_base_annual_qx` never mutated.

---

## 1. What this adds

Two industry-grade assumption-setting steps that the governed base table
(`monthly_projection._base_annual_qx`, "basis undocumented" per
`ASSUMPTIONS_REGISTER.md` §3.A gaps #1–#2) did not implement, supplied **without
changing the governed base**:

1. **Credibility blending (SOA ASOP 25 §3.2/§3.3).** Company experience is blended
   with the standard/prior table by an actuarially-sound credibility procedure.
   The credibility-weighted actual-to-expected multiplier is

   > `AE_blended = Z · AE_observed + (1 − Z) · 1.0`

   the complement of credibility falling back on the standard table (`AE = 1`).

2. **Mortality improvement (ASOP 25 §3.3 trend clause).** The blended base-year
   table is projected to the valuation year by an age-tapered annual improvement
   scale on the static (attained-age) convention:

   > `qx(valuation) = qx(base) · (1 − MI_x)^(valuation − base)`

The blended-and-projected `qx` scales the **central** table that the stochastic
`mortality_trend` OU driver (a separate systemic-tail capital factor) multiplies.

## 2. Credibility methods (both ASOP-25-sanctioned)

| Family | Factor | Full-credibility standard |
|---|---|---|
| Limited fluctuation ("classical", **default**) | `Z = min(1, √(n / λ_F))` | `λ_F = (z_{(1+p)/2} / k)²` deaths; p=0.90, k=0.05 → **λ_F ≈ 1082.2** |
| Greatest accuracy (Bühlmann) | `Z = n / (n + K)` | `K = EPV / VHM` from ≥2 homogeneous sub-classes |

`granularity`: `aggregate` (one Z from total deaths — default, robust for thin
data) or `by_age` (per-age Z — requires thick data). The standard-normal quantile
`z` uses a scipy-free Acklam rational approximation (`norm_ppf`).

## 3. Improvement scale

`ImprovementScale(base_rate, taper_start_age, taper_end_age)`: constant
`base_rate` to `taper_start_age`, linear to 0 at `taper_end_age`, 0 beyond
(illustrative MP-style shape). Default 1.0%/yr, taper 60→95.

## 4. Demonstration result (synthetic experience, base 2020 → valuation 2026)

| Gender | Observed A/E | Deaths / λ_F | Z (classical) | Blended A/E |
|---|---:|---:|---:|---:|
| M | 0.9200 | 121 / 1082.2 | 0.3346 | 0.9732 |
| F | 0.9200 | 80 / 1082.2 | 0.2715 | 0.9783 |

Pinned content digests: M `df49af04…`, F `e02398fb…`. The default experience is
**SYNTHETIC** (A/E built to ≈0.92) — not company data.

## 5. Governance & limitations

- **Purely additive.** The module *reads* `_base_annual_qx`; it never redefines
  or mutates it. `git diff` for this cycle touches no existing source file.
  Regression-locked test `test_governed_base_not_mutated`.
- Every produced table carries an **UNSIGNED** banner. Adoption as the governed
  base requires **owner sign-off + independent APS X2 review**.
- Output tables pass `MortalityTableValidator` (age 18–85, qx∈(1e-6,0.5),
  monotone) — regression-tested.
- **Residual limitations:** improvement is *static* (attained-age), not
  generational/cohort; the demonstration scale and experience are illustrative,
  not a credentialled MP-2021 / CMI scale or a real portfolio study;
  credibility is on a life-count (frequency) basis — amount-based credibility
  (with the 1+CV² inflation) is a documented extension.

## 6. Standards

SOA ASOP 25 §3.2/§3.3 (credibility, blending with a related table; mortality
trend); ASOP 56 §3.1/§3.5 (documentation, input validation); IA TAS M
§3.5/§3.6/§3.9. Longley-Cook (1962) / Herzog — limited fluctuation; Bühlmann
(1967) — greatest accuracy.
