"""
Mortality Credibility Blending & Improvement — ASOP 25 qx-Table Generator
=========================================================================

Roadmap §4.1 #11 (Accuracy).  A **purely-additive** generator that constructs a
credibility-blended, improvement-projected annual mortality (``q_x``) table from
(a) a *standard / prior* table and (b) *company experience* data, following
**SOA ASOP 25** (Credibility Procedures) and **ASOP 25 §3.3** (blending the
subject experience with a related, more-credible table).

Why this module
---------------
The governed projection base table is the Gompertz form
:func:`par_model_v2.projection.monthly_projection._base_annual_qx`
("calibrated to China Life Experience Study *shape*") with the standing
limitation *"Basis undocumented"* in ``docs/ASSUMPTIONS_REGISTER.md`` §3.A.  Two
industry-grade steps are missing and are supplied here **without changing the
governed base table**:

1. **Credibility blending (ASOP 25).**  When portfolio experience exists it must
   be blended with the standard table by an actuarially-sound credibility
   procedure, *not* adopted raw (thin data over-fits) nor ignored (leaves signal
   on the table).  The blended actual-to-expected (A/E) multiplier is

       AE_blended = Z · AE_observed + (1 − Z) · 1.0

   where the complement of credibility falls back on the standard table
   (AE = 1).  This module implements **both** ASOP-25-sanctioned credibility
   families:

   * *Limited fluctuation* ("classical", the default): full-credibility death
     standard ``λ_F = (z_{(1+p)/2} / k)²`` (Poisson claim-count basis) and the
     square-root partial-credibility rule ``Z = min(1, sqrt(n / λ_F))``.
   * *Greatest accuracy* (Bühlmann): ``Z = n / (n + K)``, ``K = EPV / VHM``
     estimated from a set of homogeneous sub-class experiences.

2. **Mortality improvement (ASOP 25 §3.3 mortality-trend clause).**  The blended
   *base-year* table is projected to the valuation year with an age-tapered
   annual improvement scale (constant to a taper-start age, linearly to zero by a
   taper-end age — the shape of an MP-style scale), on the **static** (attained-
   age) convention:

       q_x(valuation) = q_x(base) · (1 − MI_x)^(valuation − base)

Scope & measure
---------------
This is a **best-estimate assumption-setting** tool (real-world basis).  It is
orthogonal to :mod:`par_model_v2.stochastic.mortality_trend` — that module is the
*stochastic systemic-trend capital driver* (an OU log-multiplier in the tail);
this module sets the *central* ``q_x`` table those multipliers scale.

PRODUCTION USE RESTRICTION
--------------------------
EDUCATIONAL.  The default demonstration experience is a documented *synthetic*
set and the improvement scale is illustrative (NOT a credentialled MP-2021 /
CMI scale).  Every produced table carries an UNSIGNED banner.  Adopting a blended
table as the governed base requires owner sign-off and independent APS X2 review;
this module never mutates the governed ``_base_annual_qx``.

Standards
---------
SOA ASOP 25 §3.2/§3.3 — credibility procedures, blending with a related table
SOA ASOP 25 §3.3     — mortality-improvement / trend basis
SOA ASOP 56 §3.1/§3.5 — assumption documentation & model-input validation
IA  TAS M   §3.5/§3.6/§3.9 — assumption appropriateness, traceability, data plausibility
Longley-Cook (1962); Herzog, *Intro to Credibility Theory* — limited fluctuation
Bühlmann (1967) — greatest-accuracy (least-squares) credibility
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from par_model_v2.projection.monthly_projection import _base_annual_qx

SCHEMA = "mortality-credibility-blend-1.0"

#: qx clip bounds — aligned with MortalityTableValidator D2 range (1e-6, 0.50).
_QX_MIN = 1.0e-6
_QX_MAX = 0.50

#: Default limited-fluctuation full-credibility parameters (ASOP 25 classical):
#: probability p and tolerance k for the number-of-deaths standard.
DEFAULT_CRED_P = 0.90
DEFAULT_CRED_K = 0.05

UNSIGNED_BANNER = (
    "UNSIGNED — EDUCATIONAL credibility-blended / improvement-projected qx "
    "table. Default experience is SYNTHETIC and the improvement scale is "
    "illustrative (not a credentialled MP/CMI scale). Adoption as the governed "
    "base table requires owner sign-off + independent APS X2 review. The "
    "governed _base_annual_qx is never mutated by this module."
)

STANDARD_REFERENCES: Tuple[str, ...] = (
    "SOA ASOP 25 §3.2/§3.3 — credibility procedures; blend with related table",
    "SOA ASOP 25 §3.3 — mortality-improvement / trend basis",
    "SOA ASOP 56 §3.1/§3.5 — assumption documentation & input validation",
    "IA TAS M §3.5/§3.6/§3.9 — appropriateness, traceability, data plausibility",
    "Longley-Cook (1962); Herzog — limited-fluctuation credibility",
    "Bühlmann (1967) — greatest-accuracy (least-squares) credibility",
)


# ---------------------------------------------------------------------------
# 0. Inverse standard-normal CDF (scipy-free — Acklam rational approximation)
# ---------------------------------------------------------------------------

# Coefficients for Peter Acklam's algorithm (abs rel error < 1.15e-9).
_A = (-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
      1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00)
_B = (-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
      6.680131188771972e+01, -1.328068155288572e+01)
_C = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
      -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00)
_D = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
      3.754408661907416e+00)


def norm_ppf(p: float) -> float:
    """Standard-normal quantile (inverse CDF) — stdlib-only, no scipy.

    Peter Acklam's rational approximation, valid on the open interval (0, 1).
    """
    if not (0.0 < p < 1.0):
        raise ValueError(f"norm_ppf requires 0<p<1, got {p!r}")
    plow, phigh = 0.02425, 1.0 - 0.02425
    if p < plow:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((_C[0]*q+_C[1])*q+_C[2])*q+_C[3])*q+_C[4])*q+_C[5]) / \
               ((((_D[0]*q+_D[1])*q+_D[2])*q+_D[3])*q+1.0)
    if p > phigh:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        return -(((((_C[0]*q+_C[1])*q+_C[2])*q+_C[3])*q+_C[4])*q+_C[5]) / \
                ((((_D[0]*q+_D[1])*q+_D[2])*q+_D[3])*q+1.0)
    q = p - 0.5
    r = q * q
    return (((((_A[0]*r+_A[1])*r+_A[2])*r+_A[3])*r+_A[4])*r+_A[5]) * q / \
           (((((_B[0]*r+_B[1])*r+_B[2])*r+_B[3])*r+_B[4])*r+1.0)


# ---------------------------------------------------------------------------
# 1. Credibility primitives (ASOP 25)
# ---------------------------------------------------------------------------

def full_credibility_deaths(p: float = DEFAULT_CRED_P,
                            k: float = DEFAULT_CRED_K) -> float:
    """Limited-fluctuation full-credibility standard, in **number of deaths**.

    Claim-count (Poisson) basis: ``λ_F = (z_{(1+p)/2} / k)²`` — the expected
    number of deaths at which the observed rate is within ±k of its mean with
    probability p.  With the default p=0.90, k=0.05 → z=1.6448… → λ_F ≈ 1082.2.
    """
    if not (0.0 < p < 1.0):
        raise ValueError("p must be in (0,1)")
    if k <= 0.0:
        raise ValueError("k must be > 0")
    z = norm_ppf(0.5 * (1.0 + p))
    return (z / k) ** 2


def limited_fluctuation_z(n_deaths: float, n_full: float) -> float:
    """Square-root partial-credibility factor ``Z = min(1, sqrt(n/n_full))``."""
    if n_full <= 0.0:
        raise ValueError("n_full must be > 0")
    if n_deaths < 0.0:
        raise ValueError("n_deaths must be >= 0")
    return float(min(1.0, math.sqrt(n_deaths / n_full)))


def buhlmann_k_from_classes(
    class_means: Sequence[float],
    class_process_var: Sequence[float],
    class_weights: Optional[Sequence[float]] = None,
) -> float:
    """Bühlmann ``K = EPV / VHM`` estimated from homogeneous sub-classes.

    EPV — expected process variance (weighted mean of within-class variances);
    VHM — variance of the hypothetical means (weighted variance of class means).
    """
    m = np.asarray(class_means, dtype=float)
    v = np.asarray(class_process_var, dtype=float)
    if m.shape != v.shape or m.size < 2:
        raise ValueError("need >=2 classes with matching means/process-vars")
    if class_weights is None:
        w = np.ones_like(m)
    else:
        w = np.asarray(class_weights, dtype=float)
        if w.shape != m.shape or np.any(w < 0) or w.sum() <= 0:
            raise ValueError("class_weights must be non-negative and sum > 0")
    wn = w / w.sum()
    epv = float(np.sum(wn * v))
    mbar = float(np.sum(wn * m))
    vhm = float(np.sum(wn * (m - mbar) ** 2))
    if vhm <= 0.0:
        raise ValueError("VHM <= 0 (classes indistinguishable); K undefined")
    return epv / vhm


def buhlmann_z(n: float, k: float) -> float:
    """Greatest-accuracy credibility ``Z = n / (n + K)``."""
    if n < 0.0:
        raise ValueError("n must be >= 0")
    if k < 0.0:
        raise ValueError("K must be >= 0")
    if n == 0.0 and k == 0.0:
        return 0.0
    return float(n / (n + k))


# ---------------------------------------------------------------------------
# 2. Standard table, experience, improvement scale
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StandardMortalityTable:
    """The *prior / related* table — the governed Gompertz base (read-only).

    Wraps :func:`_base_annual_qx` so the complement of credibility always falls
    back on the governed shape.  This class **reads** the governed function; it
    never redefines or mutates it.
    """

    gender: str = "M"
    name: str = "GOVERNED_GOMPERTZ_BASE"

    def qx(self, age: int) -> float:
        return float(_base_annual_qx(int(age), self.gender))

    def vector(self, ages: Sequence[int]) -> np.ndarray:
        return np.array([self.qx(a) for a in ages], dtype=float)


@dataclass(frozen=True)
class MortalityExperience:
    """Company / portfolio mortality experience by attained age.

    Parameters
    ----------
    ages : sequence[int]
        Attained ages observed.
    exposure : sequence[float]
        Central exposure (life-years) at each age.
    actual_deaths : sequence[float]
        Observed deaths at each age.
    label : str
        Free-text provenance label (SYNTHETIC by default — see the factory).
    is_synthetic : bool
        True for the built-in illustrative set (drives the UNSIGNED banner).
    """

    ages: Tuple[int, ...]
    exposure: Tuple[float, ...]
    actual_deaths: Tuple[float, ...]
    label: str = "SYNTHETIC_ILLUSTRATIVE"
    is_synthetic: bool = True

    def __post_init__(self) -> None:
        n = len(self.ages)
        if not (n == len(self.exposure) == len(self.actual_deaths)):
            raise ValueError("ages/exposure/actual_deaths length mismatch")
        if n == 0:
            raise ValueError("experience is empty")
        if any(e < 0 for e in self.exposure):
            raise ValueError("exposure must be non-negative")
        if any(d < 0 for d in self.actual_deaths):
            raise ValueError("actual_deaths must be non-negative")

    @property
    def total_deaths(self) -> float:
        return float(sum(self.actual_deaths))

    @property
    def total_exposure(self) -> float:
        return float(sum(self.exposure))

    def expected_deaths(self, standard: StandardMortalityTable) -> float:
        return float(sum(e * standard.qx(a)
                         for a, e in zip(self.ages, self.exposure)))

    def observed_ae(self, standard: StandardMortalityTable) -> float:
        exp = self.expected_deaths(standard)
        if exp <= 0.0:
            raise ValueError("expected deaths <= 0; A/E undefined")
        return self.total_deaths / exp

    def digest(self) -> str:
        blob = json.dumps(
            {"ages": list(self.ages), "exposure": list(self.exposure),
             "actual_deaths": list(self.actual_deaths), "label": self.label},
            sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ImprovementScale:
    """Age-tapered constant annual mortality-improvement scale (static basis).

    ``MI(age) = base_rate`` for ``age <= taper_start_age``, linearly to 0 at
    ``taper_end_age``, and 0 beyond.  Illustrative MP-style shape — UNSIGNED.
    """

    base_rate: float = 0.010
    taper_start_age: int = 60
    taper_end_age: int = 95

    def __post_init__(self) -> None:
        if not (0.0 <= self.base_rate < 1.0):
            raise ValueError("base_rate must be in [0,1)")
        if self.taper_end_age <= self.taper_start_age:
            raise ValueError("taper_end_age must exceed taper_start_age")

    def rate(self, age: int) -> float:
        a = int(age)
        if a <= self.taper_start_age:
            return self.base_rate
        if a >= self.taper_end_age:
            return 0.0
        frac = (self.taper_end_age - a) / (self.taper_end_age - self.taper_start_age)
        return self.base_rate * frac


@dataclass(frozen=True)
class CredibilityConfig:
    """Credibility method + parameters.

    method : "limited_fluctuation" | "buhlmann"
    granularity : "aggregate" (one Z from total deaths — default; robust for
        thin data) | "by_age" (per-age Z from per-age deaths — needs thick data)
    """

    method: str = "limited_fluctuation"
    granularity: str = "aggregate"
    p: float = DEFAULT_CRED_P
    k: float = DEFAULT_CRED_K
    buhlmann_k: Optional[float] = None

    def __post_init__(self) -> None:
        if self.method not in ("limited_fluctuation", "buhlmann"):
            raise ValueError(f"unknown method {self.method!r}")
        if self.granularity not in ("aggregate", "by_age"):
            raise ValueError(f"unknown granularity {self.granularity!r}")
        if self.method == "buhlmann" and self.buhlmann_k is None:
            raise ValueError("buhlmann method requires buhlmann_k")


# ---------------------------------------------------------------------------
# 3. Blended-table result
# ---------------------------------------------------------------------------

@dataclass
class BlendedMortalityTable:
    schema: str
    gender: str
    age_min: int
    age_max: int
    base_year: int
    valuation_year: int
    ages: List[int]
    standard_qx: List[float]
    blended_ae: List[float]
    blended_base_qx: List[float]
    projected_qx: List[float]
    credibility_z: float
    per_age_z: Optional[List[float]]
    observed_ae: float
    total_deaths: float
    total_exposure: float
    full_credibility_deaths: float
    credibility_method: str
    credibility_granularity: str
    improvement: Dict[str, float]
    experience_label: str
    experience_is_synthetic: bool
    experience_digest: str
    unsigned: bool
    inputs_digest: str = ""
    content_digest: str = ""

    def to_dataframe(self):
        import pandas as pd
        return pd.DataFrame({
            "age": self.ages,
            "qx": self.projected_qx,
            "gender": [self.gender] * len(self.ages),
            "table_name": [f"BLENDED_{self.gender}_{self.valuation_year}"]
                          * len(self.ages),
        })

    def to_dict(self) -> dict:
        return {
            "schema": self.schema,
            "gender": self.gender,
            "age_range": [self.age_min, self.age_max],
            "base_year": self.base_year,
            "valuation_year": self.valuation_year,
            "credibility": {
                "method": self.credibility_method,
                "granularity": self.credibility_granularity,
                "Z": self.credibility_z,
                "observed_AE": self.observed_ae,
                "total_deaths": self.total_deaths,
                "total_exposure": self.total_exposure,
                "full_credibility_deaths": self.full_credibility_deaths,
                "per_age_Z": self.per_age_z,
            },
            "improvement": self.improvement,
            "experience": {
                "label": self.experience_label,
                "is_synthetic": self.experience_is_synthetic,
                "digest": self.experience_digest,
            },
            "table": {
                "ages": self.ages,
                "standard_qx": self.standard_qx,
                "blended_AE": self.blended_ae,
                "blended_base_qx": self.blended_base_qx,
                "projected_qx": self.projected_qx,
            },
            "unsigned": self.unsigned,
            "unsigned_banner": UNSIGNED_BANNER,
            "standard_references": list(STANDARD_REFERENCES),
            "roadmap_item": "§4.1 #11 mortality improvement + credibility blending (ASOP 25)",
            "inputs_digest": self.inputs_digest,
            "content_digest": self.content_digest,
        }

    def to_markdown(self) -> str:
        lines = [
            "# Credibility-Blended Mortality Table (ASOP 25)",
            "",
            f"**Schema:** `{self.schema}`  ",
            f"**Gender:** {self.gender}  •  **Ages:** {self.age_min}–{self.age_max}  "
            f"•  **Base→Valuation:** {self.base_year}→{self.valuation_year}  ",
            f"**Inputs digest:** `{self.inputs_digest[:16]}…`  •  "
            f"**Content digest:** `{self.content_digest[:16]}…`  ",
            "",
            "## Credibility",
            "",
            f"- Method: **{self.credibility_method}** ({self.credibility_granularity})",
            f"- Observed A/E vs standard: **{self.observed_ae:.4f}**",
            f"- Total deaths / full-credibility standard: "
            f"**{self.total_deaths:.0f} / {self.full_credibility_deaths:.1f}**",
            f"- Credibility Z: **{self.credibility_z:.4f}**",
            "",
            "## Improvement scale",
            "",
            f"- base_rate **{self.improvement['base_rate']:.4f}**/yr, "
            f"taper {int(self.improvement['taper_start_age'])}→"
            f"{int(self.improvement['taper_end_age'])}, "
            f"static projection over **{self.valuation_year - self.base_year}** years",
            "",
            "## Table (selected ages)",
            "",
            "| age | standard qx | blended A/E | blended base qx | projected qx |",
            "|----:|------------:|------------:|----------------:|-------------:|",
        ]
        for i, a in enumerate(self.ages):
            if a % 10 == 0 or a in (self.age_min, self.age_max):
                lines.append(
                    f"| {a} | {self.standard_qx[i]:.6f} | {self.blended_ae[i]:.4f} "
                    f"| {self.blended_base_qx[i]:.6f} | {self.projected_qx[i]:.6f} |")
        lines += ["", "> " + UNSIGNED_BANNER, ""]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 4. Generator
# ---------------------------------------------------------------------------

def _clip_qx(x: float) -> float:
    return float(min(_QX_MAX, max(_QX_MIN, x)))


def generate_blended_table(
    experience: Optional[MortalityExperience] = None,
    *,
    gender: str = "M",
    standard: Optional[StandardMortalityTable] = None,
    credibility: Optional[CredibilityConfig] = None,
    improvement: Optional[ImprovementScale] = None,
    base_year: int = 2020,
    valuation_year: int = 2026,
    age_min: int = 18,
    age_max: int = 85,
) -> BlendedMortalityTable:
    """Build a credibility-blended, improvement-projected qx table.

    The blended A/E multiplier (credibility-weighted toward the standard table)
    scales the governed Gompertz base; the result is then projected from
    ``base_year`` to ``valuation_year`` by the age-tapered improvement scale on
    the static (attained-age) convention.  Purely additive — the governed base
    table is read, never mutated.
    """
    if age_max <= age_min:
        raise ValueError("age_max must exceed age_min")
    if valuation_year < base_year:
        raise ValueError("valuation_year must be >= base_year")

    standard = standard or StandardMortalityTable(gender=gender)
    if standard.gender != gender:
        standard = StandardMortalityTable(gender=gender, name=standard.name)
    credibility = credibility or CredibilityConfig()
    improvement = improvement or ImprovementScale()
    if experience is None:
        experience = default_experience(gender=gender)

    ages = list(range(int(age_min), int(age_max) + 1))
    std_vec = standard.vector(ages)

    observed_ae = experience.observed_ae(standard)
    total_deaths = experience.total_deaths
    lam_full = full_credibility_deaths(credibility.p, credibility.k)

    # ---- credibility factor(s) ----
    per_age_z: Optional[List[float]] = None
    if credibility.method == "limited_fluctuation":
        z_agg = limited_fluctuation_z(total_deaths, lam_full)
    else:  # buhlmann — n = total exposure units
        z_agg = buhlmann_z(experience.total_exposure, float(credibility.buhlmann_k))

    exp_by_age = {a: (e, d) for a, e, d
                  in zip(experience.ages, experience.exposure, experience.actual_deaths)}

    blended_ae: List[float] = []
    if credibility.granularity == "aggregate":
        ae_mult = z_agg * observed_ae + (1.0 - z_agg) * 1.0
        blended_ae = [ae_mult] * len(ages)
        cred_z = z_agg
    else:  # by_age
        per_age_z = []
        for a in ages:
            e, d = exp_by_age.get(a, (0.0, 0.0))
            exp_deaths = e * standard.qx(a)
            ae_obs_a = (d / exp_deaths) if exp_deaths > 0 else 1.0
            if credibility.method == "limited_fluctuation":
                z_a = limited_fluctuation_z(d, lam_full)
            else:
                z_a = buhlmann_z(e, float(credibility.buhlmann_k))
            per_age_z.append(z_a)
            blended_ae.append(z_a * ae_obs_a + (1.0 - z_a) * 1.0)
        cred_z = z_agg  # reported aggregate reference

    # ---- blend + project ----
    n_years = int(valuation_year - base_year)
    blended_base_qx: List[float] = []
    projected_qx: List[float] = []
    for i, a in enumerate(ages):
        base_q = _clip_qx(blended_ae[i] * float(std_vec[i]))
        blended_base_qx.append(base_q)
        mi = improvement.rate(a)
        projected_qx.append(_clip_qx(base_q * (1.0 - mi) ** n_years))

    tbl = BlendedMortalityTable(
        schema=SCHEMA,
        gender=gender,
        age_min=int(age_min),
        age_max=int(age_max),
        base_year=int(base_year),
        valuation_year=int(valuation_year),
        ages=ages,
        standard_qx=[float(x) for x in std_vec],
        blended_ae=blended_ae,
        blended_base_qx=blended_base_qx,
        projected_qx=projected_qx,
        credibility_z=float(cred_z),
        per_age_z=per_age_z,
        observed_ae=float(observed_ae),
        total_deaths=float(total_deaths),
        total_exposure=float(experience.total_exposure),
        full_credibility_deaths=float(lam_full),
        credibility_method=credibility.method,
        credibility_granularity=credibility.granularity,
        improvement={
            "base_rate": improvement.base_rate,
            "taper_start_age": improvement.taper_start_age,
            "taper_end_age": improvement.taper_end_age,
            "years_projected": n_years,
        },
        experience_label=experience.label,
        experience_is_synthetic=experience.is_synthetic,
        experience_digest=experience.digest(),
        unsigned=True,
    )
    tbl.inputs_digest = _inputs_digest(tbl, credibility, improvement, standard)
    tbl.content_digest = _content_digest(tbl)
    return tbl


def _inputs_digest(tbl: BlendedMortalityTable, cred: CredibilityConfig,
                   imp: ImprovementScale, std: StandardMortalityTable) -> str:
    basis = {
        "schema": tbl.schema,
        "gender": tbl.gender,
        "age_range": [tbl.age_min, tbl.age_max],
        "years": [tbl.base_year, tbl.valuation_year],
        "standard": std.name,
        "credibility": {"method": cred.method, "granularity": cred.granularity,
                        "p": cred.p, "k": cred.k, "buhlmann_k": cred.buhlmann_k},
        "improvement": {"base_rate": imp.base_rate,
                        "taper_start_age": imp.taper_start_age,
                        "taper_end_age": imp.taper_end_age},
        "experience_digest": tbl.experience_digest,
    }
    payload = json.dumps(basis, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _content_digest(tbl: BlendedMortalityTable) -> str:
    payload = json.dumps(
        {"ages": tbl.ages, "projected_qx": [round(q, 12) for q in tbl.projected_qx],
         "blended_base_qx": [round(q, 12) for q in tbl.blended_base_qx]},
        sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# 5. Built-in SYNTHETIC demonstration experience (documented, deterministic)
# ---------------------------------------------------------------------------

def default_experience(gender: str = "M") -> MortalityExperience:
    """Deterministic *synthetic* experience for the builder/tests.

    Constructed so that A/E ≈ 0.92 vs the standard table (a mild favourable
    experience) with a realistic age-tapered exposure profile.  Clearly labelled
    SYNTHETIC — NOT company data.  Actual deaths are the exact rounded product of
    exposure × (0.92 × standard qx) so the observed A/E is reproducible.
    """
    std = StandardMortalityTable(gender=gender)
    ages = list(range(30, 71, 5))                     # 30,35,...,70
    exposure = [4200.0, 5100.0, 6000.0, 6800.0, 6200.0,
                5000.0, 3600.0, 2200.0, 1200.0]        # 9 bands, ~40k life-years
    target_ae = 0.92
    deaths = [round(e * target_ae * std.qx(a), 3) for a, e in zip(ages, exposure)]
    return MortalityExperience(
        ages=tuple(ages), exposure=tuple(exposure), actual_deaths=tuple(deaths),
        label="SYNTHETIC_ILLUSTRATIVE_AE_0.92", is_synthetic=True)


__all__ = [
    "SCHEMA", "UNSIGNED_BANNER", "STANDARD_REFERENCES",
    "norm_ppf", "full_credibility_deaths", "limited_fluctuation_z",
    "buhlmann_k_from_classes", "buhlmann_z",
    "StandardMortalityTable", "MortalityExperience", "ImprovementScale",
    "CredibilityConfig", "BlendedMortalityTable",
    "generate_blended_table", "default_experience",
]
