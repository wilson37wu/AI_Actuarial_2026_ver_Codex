"""
Phase 11 Task 1: synthetic 100,000-policy Hong Kong PAR portfolio generator.

This module builds a large, reproducible, *educational* in-force portfolio of
Hong Kong participating policies that mixes the Phase 10 cash dividend
(``HKCD_PAR_2026``) and reversionary bonus (``HKRB_PAR_2026``) product lines.
It exists so that the Phase 11 reporting cycle (chunked processing, checkpoint
restart, reconciliation, and reporting packs) has a realistic-scale data set to
run against without depending on any insurer's confidential policy file.

Design goals
------------
* **Reproducible.**  All randomness flows from a single ``numpy`` seed.  The
  same config produces a byte-stable policy table; a SHA-256 ``digest`` over the
  canonical record ordering is returned as reproducibility evidence (SOA ASOP 56
  reproducibility; IA TAS M traceability).
* **Schema-compatible.**  Every generated record satisfies the Phase 10
  ``HKCashDividendPolicy`` / ``HKReversionaryBonusPolicy`` field constraints and
  validates against the starter product mechanics, so downstream Phase 10
  reporting consumers can ingest the portfolio unchanged.
* **Vectorised.**  100,000 policies are generated with array operations rather
  than per-policy Python objects, keeping generation well under a second and
  leaving full dataclass round-trip validation as an opt-in / sampled check.
* **Chunk-ready.**  ``iter_policy_chunks`` yields stable, ordered slices to seed
  the next Phase 11 task (grouping, chunking, checkpoint restart).

Limitations
-----------
The portfolio is synthetic and uncalibrated.  Distributions of age, term, sum
assured, premium, and vested bonus are illustrative heuristics chosen for
plausibility and coverage, *not* fitted to any market experience, insurer
filing, or PRE policy.  Premiums are a simple deterministic loading of
``sum_assured / term`` and must not be read as priced rates.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterator, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from par_model_v2.projection.monthly_projection import VALID_TERMS
from par_model_v2.projection.hk_participating import (
    HKCashDividendMechanics,
    HKReversionaryBonusMechanics,
    HKCashDividendPolicy,
    HKReversionaryBonusPolicy,
    default_hk_cash_dividend_mechanics,
    default_hk_reversionary_bonus_mechanics,
    validate_hk_cash_dividend_policy_table,
    validate_hk_reversionary_bonus_policy_table,
)

PRODUCT_LINE_CASH = "CASH_DIVIDEND"
PRODUCT_LINE_RB = "REVERSIONARY_BONUS"

DISTRIBUTION_CHANNELS: Tuple[str, ...] = ("AGENCY", "BROKER", "BANCASSURANCE", "DIRECT")

#: Canonical column order for the unified portfolio table.  Both product lines
#: share these columns; product-specific fields (``dividend_option`` /
#: ``bonus_option`` / ``initial_vested_bonus``) are populated where they apply
#: and carry neutral defaults otherwise.
UNIFIED_COLUMNS: Tuple[str, ...] = (
    "policy_id",
    "product_line",
    "product_code",
    "issue_age",
    "gender",
    "term_years",
    "sum_assured",
    "annual_premium",
    "policy_year",
    "initial_vested_bonus",
    "inforce_count",
    "premium_mode",
    "dividend_option",
    "bonus_option",
    "distribution_channel",
    "source_id",
)

_DEFAULT_TERM_WEIGHTS: Tuple[Tuple[int, float], ...] = (
    (5, 0.20),
    (10, 0.45),
    (20, 0.35),
)

_DEFAULT_CHANNEL_WEIGHTS: Tuple[Tuple[str, float], ...] = (
    ("AGENCY", 0.45),
    ("BROKER", 0.25),
    ("BANCASSURANCE", 0.22),
    ("DIRECT", 0.08),
)


def _normalise_weights(pairs: Sequence[Tuple[object, float]]) -> Tuple[np.ndarray, np.ndarray]:
    """Return parallel (values, probabilities) arrays from labelled weights."""
    if not pairs:
        raise ValueError("weight specification must be non-empty")
    values = np.array([value for value, _ in pairs], dtype=object)
    weights = np.array([float(weight) for _, weight in pairs], dtype=float)
    if np.any(weights < 0.0) or not np.isfinite(weights).all():
        raise ValueError("weights must be finite and non-negative")
    total = weights.sum()
    if total <= 0.0:
        raise ValueError("weights must sum to a positive value")
    return values, weights / total


@dataclass(frozen=True)
class PortfolioGenerationConfig:
    """Reproducible configuration for the synthetic HK PAR portfolio.

    All fields have educational defaults that yield a 100,000-policy portfolio
    with a roughly even split between the cash dividend and reversionary bonus
    product lines.
    """

    n_policies: int = 100_000
    seed: int = 20_260_604
    cash_dividend_share: float = 0.5

    # Issue-age sampling (truncated normal, clipped to the mechanics range).
    issue_age_mean: float = 40.0
    issue_age_sd: float = 11.0
    issue_age_min: int = 18
    issue_age_max: int = 65

    # Term and channel mixes (label, weight).
    term_weights: Tuple[Tuple[int, float], ...] = _DEFAULT_TERM_WEIGHTS
    channel_weights: Tuple[Tuple[str, float], ...] = _DEFAULT_CHANNEL_WEIGHTS

    # Sum-assured sampling (lognormal, rounded, clipped).
    sum_assured_log_mean: float = float(np.log(500_000.0))
    sum_assured_log_sd: float = 0.60
    sum_assured_min: float = 50_000.0
    sum_assured_max: float = 10_000_000.0
    sum_assured_round_to: float = 1_000.0

    # Gender mix.
    female_share: float = 0.50

    # Premium loading on sum_assured / term.
    premium_base_factor: float = 0.85
    premium_age_slope: float = 0.0030
    premium_short_term_uplift: float = 0.05
    premium_noise_sd: float = 0.03
    premium_round_to: float = 100.0

    # Policy-duration decay: larger -> more weight on early policy years
    # (new business heavier than seasoned business).
    policy_year_decay: float = 0.12

    source_id: str = "PHASE11-HK-PAR-SYNTHETIC-100K"

    def __post_init__(self) -> None:
        if int(self.n_policies) <= 0:
            raise ValueError("n_policies must be positive")
        if not 0.0 <= float(self.cash_dividend_share) <= 1.0:
            raise ValueError("cash_dividend_share must be in [0, 1]")
        if self.issue_age_min < 0 or self.issue_age_max < self.issue_age_min:
            raise ValueError("issue-age range is invalid")
        if self.issue_age_sd <= 0.0:
            raise ValueError("issue_age_sd must be positive")
        if self.sum_assured_min <= 0.0 or self.sum_assured_max < self.sum_assured_min:
            raise ValueError("sum-assured range is invalid")
        if self.sum_assured_round_to <= 0.0 or self.premium_round_to <= 0.0:
            raise ValueError("rounding granularity must be positive")
        if not 0.0 <= float(self.female_share) <= 1.0:
            raise ValueError("female_share must be in [0, 1]")
        if self.policy_year_decay < 0.0:
            raise ValueError("policy_year_decay must be non-negative")
        # Validate the term mix against currently supported projection terms.
        terms = tuple(int(term) for term, _ in self.term_weights)
        unsupported = [term for term in terms if term not in VALID_TERMS]
        if unsupported:
            raise ValueError(
                "term_weights must use supported terms {}; got {}".format(VALID_TERMS, unsupported)
            )


@dataclass(frozen=True)
class PortfolioGenerationResult:
    """Output bundle from :func:`generate_hk_par_portfolio`."""

    policies: pd.DataFrame
    summary: Dict[str, object]
    config: PortfolioGenerationConfig
    generated_at: str
    digest: str

    def to_metadata(self) -> Dict[str, object]:
        """Return a JSON-serialisable run-metadata record (no policy rows)."""
        return {
            "generated_at": self.generated_at,
            "digest_sha256": self.digest,
            "n_policies": int(len(self.policies)),
            "source_id": self.config.source_id,
            "seed": int(self.config.seed),
            "summary": self.summary,
        }


def _policy_year_weights(term: int, decay: float) -> np.ndarray:
    """Return a normalised decaying weight vector over policy years 1..term."""
    years = np.arange(1, int(term) + 1, dtype=float)
    weights = np.exp(-decay * (years - 1.0))
    return weights / weights.sum()


def _sample_issue_ages(rng: np.random.Generator, config: PortfolioGenerationConfig, n: int) -> np.ndarray:
    """Sample integer issue ages from a clipped normal distribution."""
    raw = rng.normal(config.issue_age_mean, config.issue_age_sd, size=n)
    ages = np.rint(raw).astype(int)
    return np.clip(ages, config.issue_age_min, config.issue_age_max)


def _sample_sum_assured(rng: np.random.Generator, config: PortfolioGenerationConfig, n: int) -> np.ndarray:
    """Sample rounded, clipped lognormal sums assured."""
    raw = rng.lognormal(config.sum_assured_log_mean, config.sum_assured_log_sd, size=n)
    rounded = np.rint(raw / config.sum_assured_round_to) * config.sum_assured_round_to
    return np.clip(rounded, config.sum_assured_min, config.sum_assured_max).astype(float)


def _sample_terms(rng: np.random.Generator, config: PortfolioGenerationConfig, n: int) -> np.ndarray:
    """Sample policy terms from the configured term mix."""
    values, probs = _normalise_weights(config.term_weights)
    idx = rng.choice(len(values), size=n, p=probs)
    return np.array([int(values[i]) for i in idx], dtype=int)


def _sample_policy_years(rng: np.random.Generator, terms: np.ndarray, decay: float) -> np.ndarray:
    """Sample a policy year in [1, term] per policy using a decaying profile."""
    policy_years = np.empty(terms.shape, dtype=int)
    for term in np.unique(terms):
        mask = terms == term
        count = int(mask.sum())
        weights = _policy_year_weights(int(term), decay)
        draws = rng.choice(np.arange(1, int(term) + 1), size=count, p=weights)
        policy_years[mask] = draws
    return policy_years


def _compute_premiums(
    rng: np.random.Generator,
    config: PortfolioGenerationConfig,
    sum_assured: np.ndarray,
    terms: np.ndarray,
    issue_ages: np.ndarray,
) -> np.ndarray:
    """Return a deterministic-plus-noise annual premium loading of SA / term."""
    age_load = config.premium_age_slope * (issue_ages - config.issue_age_min)
    short_term_uplift = np.where(terms <= 5, config.premium_short_term_uplift, 0.0)
    factor = config.premium_base_factor + age_load + short_term_uplift
    noise = rng.normal(1.0, config.premium_noise_sd, size=sum_assured.shape)
    noise = np.clip(noise, 0.80, 1.20)
    premium = (sum_assured / terms) * factor * noise
    premium = np.rint(premium / config.premium_round_to) * config.premium_round_to
    # Floor so the positivity constraint always holds, even for tiny SA.
    return np.maximum(premium, config.premium_round_to)


def _make_policy_ids(prefix: str, count: int) -> np.ndarray:
    """Return zero-padded sequential policy identifiers."""
    return np.array([f"{prefix}{i:08d}" for i in range(1, count + 1)], dtype=object)


def generate_hk_par_portfolio(
    config: Optional[PortfolioGenerationConfig] = None,
    *,
    cash_mechanics: Optional[HKCashDividendMechanics] = None,
    rb_mechanics: Optional[HKReversionaryBonusMechanics] = None,
) -> PortfolioGenerationResult:
    """Generate a reproducible synthetic HK PAR portfolio.

    Parameters
    ----------
    config:
        Generation configuration; defaults to a 100,000-policy portfolio.
    cash_mechanics, rb_mechanics:
        Product mechanics whose issue-age / sum-assured ranges and product codes
        the generated records must respect.  Defaults to the Phase 10 starters.

    Returns
    -------
    PortfolioGenerationResult
        The policy table (unified schema), summary statistics, the effective
        config, an ISO-8601 generation timestamp, and a SHA-256 digest of the
        canonical record ordering for reproducibility evidence.
    """
    config = config or PortfolioGenerationConfig()
    cash_mechanics = cash_mechanics or default_hk_cash_dividend_mechanics()
    rb_mechanics = rb_mechanics or default_hk_reversionary_bonus_mechanics()

    # Clamp the configured ranges to the product mechanics so every record is
    # admissible under validate_against(...).
    age_min = max(config.issue_age_min, cash_mechanics.issue_age_min, rb_mechanics.issue_age_min)
    age_max = min(config.issue_age_max, cash_mechanics.issue_age_max, rb_mechanics.issue_age_max)
    sa_min = max(config.sum_assured_min, cash_mechanics.min_sum_assured, rb_mechanics.min_sum_assured)
    sa_max = min(config.sum_assured_max, cash_mechanics.max_sum_assured, rb_mechanics.max_sum_assured)
    if age_max < age_min or sa_max < sa_min:
        raise ValueError("config ranges are incompatible with product mechanics")
    config = replace(
        config,
        issue_age_min=int(age_min),
        issue_age_max=int(age_max),
        sum_assured_min=float(sa_min),
        sum_assured_max=float(sa_max),
    )

    rng = np.random.default_rng(config.seed)
    n = int(config.n_policies)

    # Product-line assignment first so per-line identifiers stay contiguous.
    is_cash = rng.random(n) < config.cash_dividend_share
    n_cash = int(is_cash.sum())
    n_rb = n - n_cash

    issue_ages = _sample_issue_ages(rng, config, n)
    terms = _sample_terms(rng, config, n)
    policy_years = _sample_policy_years(rng, terms, config.policy_year_decay)
    sum_assured = _sample_sum_assured(rng, config, n)
    premiums = _compute_premiums(rng, config, sum_assured, terms, issue_ages)
    genders = np.where(rng.random(n) < config.female_share, "F", "M")
    channel_values, channel_probs = _normalise_weights(config.channel_weights)
    channel_idx = rng.choice(len(channel_values), size=n, p=channel_probs)
    channels = np.array([str(channel_values[i]) for i in channel_idx], dtype=object)

    # Vested bonus only applies to reversionary-bonus policies and accrues with
    # duration: SA * rb_rate * (policy_year - 1) with light multiplicative noise.
    rb_rate = rb_mechanics.annual_reversionary_bonus_rate
    vested_noise = np.clip(rng.normal(1.0, 0.10, size=n), 0.50, 1.50)
    vested = sum_assured * rb_rate * np.maximum(policy_years - 1, 0) * vested_noise
    vested = np.rint(vested / 100.0) * 100.0
    initial_vested_bonus = np.where(is_cash, 0.0, np.maximum(vested, 0.0))

    # Stable, contiguous identifiers per product line.
    policy_id = np.empty(n, dtype=object)
    policy_id[is_cash] = _make_policy_ids("HKCDG", n_cash)
    policy_id[~is_cash] = _make_policy_ids("HKRBG", n_rb)

    product_line = np.where(is_cash, PRODUCT_LINE_CASH, PRODUCT_LINE_RB)
    product_code = np.where(is_cash, cash_mechanics.product_code, rb_mechanics.product_code)
    dividend_option = np.where(is_cash, "CASH", "NONE")
    bonus_option = np.where(is_cash, "NONE", "VESTED_REVERSIONARY")
    source_id = np.where(
        is_cash,
        f"{config.source_id}-CASH",
        f"{config.source_id}-RB",
    )

    table = pd.DataFrame(
        {
            "policy_id": policy_id,
            "product_line": product_line,
            "product_code": product_code,
            "issue_age": issue_ages.astype(int),
            "gender": genders,
            "term_years": terms.astype(int),
            "sum_assured": sum_assured.astype(float),
            "annual_premium": premiums.astype(float),
            "policy_year": policy_years.astype(int),
            "initial_vested_bonus": initial_vested_bonus.astype(float),
            "inforce_count": np.ones(n, dtype=float),
            "premium_mode": np.full(n, "ANNUAL", dtype=object),
            "dividend_option": dividend_option,
            "bonus_option": bonus_option,
            "distribution_channel": channels,
            "source_id": source_id,
        },
        columns=list(UNIFIED_COLUMNS),
    )
    # Deterministic ordering: cash line first, then RB, each by ascending id.
    table = table.sort_values(["product_line", "policy_id"], kind="mergesort").reset_index(drop=True)

    summary = portfolio_summary(table)
    digest = _portfolio_digest_presorted(table)  # table already canonical (roadmap 4.1 #10)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return PortfolioGenerationResult(
        policies=table,
        summary=summary,
        config=config,
        generated_at=generated_at,
        digest=digest,
    )


def portfolio_digest(table: pd.DataFrame) -> str:
    """Return a SHA-256 digest of the canonical policy ordering.

    The digest is stable across runs for identical inputs and is used as
    reproducibility evidence in run metadata.
    """
    ordered = table[list(UNIFIED_COLUMNS)].sort_values(["product_line", "policy_id"], kind="mergesort")
    payload = ordered.to_csv(index=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _portfolio_digest_presorted(table: pd.DataFrame) -> str:
    """SHA-256 digest of a portfolio that is ALREADY in canonical order.

    Byte-for-byte identical to :func:`portfolio_digest` **when** ``table`` is
    already sorted by ``["product_line", "policy_id"]`` and already carries
    exactly :data:`UNIFIED_COLUMNS` in order -- which is the case for the frame
    :func:`generate_hk_par_portfolio` has just built and sorted.  It skips the
    redundant re-sort and column re-subset that :func:`portfolio_digest`
    performs defensively for arbitrary inputs; that redundant work is a measured
    ~9% of the 100k-policy generation runtime (see roadmap 4.1 #10 /
    ``docs/PERF_PROFILE_100K_CARD.md``).  The governed digest *value* is
    unchanged (regression-locked); this is a pure output-identical speed-up.

    Not for external use with an arbitrary frame -- callers holding an unsorted
    or reordered table MUST use :func:`portfolio_digest`.
    """
    payload = table.to_csv(index=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def portfolio_summary(table: pd.DataFrame) -> Dict[str, object]:
    """Compute headline portfolio statistics for reporting and reconciliation."""
    n = int(len(table))
    by_line = table["product_line"].value_counts().to_dict()
    summary: Dict[str, object] = {
        "n_policies": n,
        "n_cash_dividend": int(by_line.get(PRODUCT_LINE_CASH, 0)),
        "n_reversionary_bonus": int(by_line.get(PRODUCT_LINE_RB, 0)),
        "total_sum_assured": float(table["sum_assured"].sum()),
        "total_annual_premium": float(table["annual_premium"].sum()),
        "total_initial_vested_bonus": float(table["initial_vested_bonus"].sum()),
        "mean_sum_assured": float(table["sum_assured"].mean()),
        "mean_annual_premium": float(table["annual_premium"].mean()),
        "mean_issue_age": float(table["issue_age"].mean()),
        "issue_age_min": int(table["issue_age"].min()),
        "issue_age_max": int(table["issue_age"].max()),
        "sum_assured_min": float(table["sum_assured"].min()),
        "sum_assured_max": float(table["sum_assured"].max()),
        "term_mix": {int(k): int(v) for k, v in table["term_years"].value_counts().sort_index().items()},
        "gender_mix": {str(k): int(v) for k, v in table["gender"].value_counts().items()},
        "channel_mix": {str(k): int(v) for k, v in table["distribution_channel"].value_counts().items()},
    }
    return summary


def _cash_subset(table: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "policy_id", "product_code", "issue_age", "gender", "term_years",
        "sum_assured", "annual_premium", "policy_year", "inforce_count",
        "premium_mode", "dividend_option", "distribution_channel", "source_id",
    ]
    return table.loc[table["product_line"] == PRODUCT_LINE_CASH, cols].reset_index(drop=True)


def _rb_subset(table: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "policy_id", "product_code", "issue_age", "gender", "term_years",
        "sum_assured", "annual_premium", "policy_year", "initial_vested_bonus",
        "inforce_count", "premium_mode", "bonus_option", "distribution_channel",
        "source_id",
    ]
    return table.loc[table["product_line"] == PRODUCT_LINE_RB, cols].reset_index(drop=True)


def validate_portfolio(
    table: pd.DataFrame,
    *,
    cash_mechanics: Optional[HKCashDividendMechanics] = None,
    rb_mechanics: Optional[HKReversionaryBonusMechanics] = None,
    sample_size: Optional[int] = 2_000,
    seed: int = 0,
) -> bool:
    """Validate the portfolio against the Phase 10 product mechanics.

    Full dataclass round-trip validation of every policy is expensive at
    100k scale, so by default a deterministic random ``sample_size`` of each
    product line is validated through the existing Phase 10 table validators.
    Pass ``sample_size=None`` to validate every record.

    Structural checks (unique ids, required columns, schema membership) always
    run over the full table.
    """
    cash_mechanics = cash_mechanics or default_hk_cash_dividend_mechanics()
    rb_mechanics = rb_mechanics or default_hk_reversionary_bonus_mechanics()

    missing_cols = sorted(set(UNIFIED_COLUMNS).difference(table.columns))
    if missing_cols:
        raise ValueError("portfolio missing required columns: {}".format(", ".join(missing_cols)))
    if table["policy_id"].duplicated().any():
        raise ValueError("policy_id values must be unique across the portfolio")
    unknown_lines = set(table["product_line"]).difference({PRODUCT_LINE_CASH, PRODUCT_LINE_RB})
    if unknown_lines:
        raise ValueError("unknown product_line values: {}".format(sorted(unknown_lines)))

    cash = _cash_subset(table)
    rb = _rb_subset(table)

    def _maybe_sample(subset: pd.DataFrame) -> pd.DataFrame:
        if sample_size is None or len(subset) <= sample_size:
            return subset
        rng = np.random.default_rng(seed)
        idx = rng.choice(len(subset), size=int(sample_size), replace=False)
        return subset.iloc[np.sort(idx)].reset_index(drop=True)

    if not cash.empty:
        validate_hk_cash_dividend_policy_table(_maybe_sample(cash), cash_mechanics)
    if not rb.empty:
        validate_hk_reversionary_bonus_policy_table(_maybe_sample(rb), rb_mechanics)
    return True


def iter_policy_chunks(table: pd.DataFrame, chunk_size: int = 10_000) -> Iterator[pd.DataFrame]:
    """Yield stable, ordered slices of the portfolio for chunked processing.

    Seeds the next Phase 11 task (grouping / chunking / checkpoint restart):
    the slicing is deterministic over the canonical record ordering so a chunk
    index uniquely identifies the same policies on every run.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    ordered = table.sort_values(["product_line", "policy_id"], kind="mergesort").reset_index(drop=True)
    for start in range(0, len(ordered), chunk_size):
        yield ordered.iloc[start:start + chunk_size].reset_index(drop=True)


def write_portfolio(table: pd.DataFrame, path: Path | str) -> Path:
    """Persist the portfolio to CSV (``.csv``) or Parquet (``.parquet``)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".parquet":
        table.to_parquet(path, index=False)
    else:
        table.to_csv(path, index=False)
    return path


def write_metadata(result: PortfolioGenerationResult, path: Path | str) -> Path:
    """Persist run metadata (summary + digest, no policy rows) as JSON."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(result.to_metadata(), handle, indent=2, sort_keys=True)
    return path


def load_portfolio(path: Path | str) -> pd.DataFrame:
    """Load a previously persisted portfolio (CSV or Parquet)."""
    path = Path(path)
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


# ---------------------------------------------------------------------------
# Phase UIL Task 2 (B2): user model points (additive, backward-compatible)
# ---------------------------------------------------------------------------

#: Template product types (scripts/load_user_inputs.py) -> PAR product line.
#: ``GMMB_EQ_2026`` is the equity-guarantee book and is routed by the run
#: orchestrator (B3), not the PAR portfolio.  PC-2 (track 4.0d):
#: ``WL_PAR_2026`` (whole-life par) joins the RB line under the documented
#: endowment-at-limit convention; ``TERM_2026`` / ``ANNUITY_2026`` are
#: NON-PAR protection/annuity books - they carry no participation or
#: financial-option guarantee in this model form, so the stochastic PAR
#: TVOG/SCR run routes them OUT of the PAR portfolio (scope note: their
#: cash flows are covered by the deterministic CF projection set).
USER_PRODUCT_LINE_MAP: Mapping[str, str] = {
    "HKCD_PAR_2026": PRODUCT_LINE_CASH,
    "HKRB_PAR_2026": PRODUCT_LINE_RB,
    "WL_PAR_2026": PRODUCT_LINE_RB,
}


def split_model_points(model_points: Sequence[Mapping[str, object]]
                       ) -> Tuple[list, list]:
    """Split user model points into (PAR rows, non-PAR rows).

    PAR rows are the product types in ``USER_PRODUCT_LINE_MAP``; everything
    else (GMMB equity-guarantee book + the PC-2 TERM/ANNUITY non-par books)
    is returned in the second list for the orchestrator to route/disclose."""
    par, nonpar = [], []
    for p in model_points:
        (par if str(p.get("product_type")) in USER_PRODUCT_LINE_MAP
         else nonpar).append(dict(p))
    return par, nonpar


def portfolio_from_model_points(
    model_points: Sequence[Mapping[str, object]],
    *,
    cash_mechanics: Optional[HKCashDividendMechanics] = None,
    rb_mechanics: Optional[HKReversionaryBonusMechanics] = None,
) -> PortfolioGenerationResult:
    """Build the unified PAR portfolio table from user model points.

    Each model point becomes ONE record with ``inforce_count`` equal to the
    user's ``policy_count`` (model-point semantics).  Rows are validated
    fail-loud against the Phase 10 product mechanics ranges; every offending
    row is reported (source_row refers to the template row).  GMMB rows must
    be split out first (``split_model_points``); passing one here is an error.

    The synthetic generator (``generate_hk_par_portfolio``) is untouched: with
    no user inputs the pipeline remains bit-identical to the governed runs.
    """
    cash_mechanics = cash_mechanics or default_hk_cash_dividend_mechanics()
    rb_mechanics = rb_mechanics or default_hk_reversionary_bonus_mechanics()
    if not model_points:
        raise ValueError("model_points is empty -- nothing to build")

    errors = []
    rows = []
    n_cd = n_rb = 0
    for k, p in enumerate(model_points):
        src = p.get("source_row", k + 1)
        n_before = len(errors)
        ptype = str(p.get("product_type"))
        line = USER_PRODUCT_LINE_MAP.get(ptype)
        if line is None:
            errors.append("row %s: product_type %r is not a PAR product "
                          "(GMMB rows are routed by the orchestrator)" % (src, ptype))
            continue
        mech = cash_mechanics if line == PRODUCT_LINE_CASH else rb_mechanics
        try:
            age = int(p["issue_age"]); term = int(p["term_years"])
            sa = float(p["sum_assured"]); prem = float(p["annual_premium"])
            count = int(p["policy_count"]); vb = float(p["vested_bonus"])
            gender = str(p["gender"]).upper()
        except (KeyError, TypeError, ValueError) as exc:
            errors.append("row %s: incomplete or non-numeric model point (%s)" % (src, exc))
            continue
        if not (mech.issue_age_min <= age <= mech.issue_age_max):
            errors.append("row %s: issue_age %d outside mechanics range [%d, %d]"
                          % (src, age, mech.issue_age_min, mech.issue_age_max))
        if not (mech.min_sum_assured <= sa <= mech.max_sum_assured):
            errors.append("row %s: sum_assured %s outside mechanics range [%s, %s]"
                          % (src, sa, mech.min_sum_assured, mech.max_sum_assured))
        if term <= 0:
            errors.append("row %s: term_years must be positive" % src)
        if count <= 0:
            errors.append("row %s: policy_count must be positive" % src)
        if prem < 0 or vb < 0:
            errors.append("row %s: annual_premium and vested_bonus must be >= 0" % src)
        if line == PRODUCT_LINE_CASH and vb > 0:
            errors.append("row %s: cash-dividend product cannot carry a vested "
                          "reversionary bonus (got %s)" % (src, vb))
        if gender not in ("M", "F"):
            errors.append("row %s: gender must be M or F, got %r" % (src, gender))
        if len(errors) > n_before:
            continue
        if line == PRODUCT_LINE_CASH:
            n_cd += 1
            pid = "UCD%06d" % n_cd
            dividend_option, bonus_option = "CASH", "NONE"
        else:
            n_rb += 1
            pid = "URB%06d" % n_rb
            dividend_option, bonus_option = "NONE", "VESTED_REVERSIONARY"
        rows.append({
            "policy_id": pid,
            "product_line": line,
            "product_code": mech.product_code,
            "issue_age": age,
            "gender": gender,
            "term_years": term,
            "sum_assured": sa,
            "annual_premium": prem,
            "policy_year": 1,
            "initial_vested_bonus": vb,
            "inforce_count": float(count),
            "premium_mode": "ANNUAL",
            "dividend_option": dividend_option,
            "bonus_option": bonus_option,
            "distribution_channel": "DIRECT",
            "source_id": "USER_INPUTS",
        })
    if errors:
        raise ValueError("user model points rejected:\n  " + "\n  ".join(errors))

    table = pd.DataFrame(rows, columns=list(UNIFIED_COLUMNS))
    table = table.sort_values(["product_line", "policy_id"], kind="mergesort").reset_index(drop=True)
    config = replace(PortfolioGenerationConfig(), n_policies=len(table),
                     source_id="USER_INPUTS")
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return PortfolioGenerationResult(
        policies=table,
        summary=portfolio_summary(table),
        config=config,
        generated_at=generated_at,
        digest=portfolio_digest(table),
    )


def build_portfolio(
    config: Optional[PortfolioGenerationConfig] = None,
    *,
    user_inputs: Optional[Mapping[str, object]] = None,
    cash_mechanics: Optional[HKCashDividendMechanics] = None,
    rb_mechanics: Optional[HKReversionaryBonusMechanics] = None,
) -> PortfolioGenerationResult:
    """Single entry point for B2/B3: user model points if supplied, else the
    synthetic governed book (bit-identical to ``generate_hk_par_portfolio``).
    """
    from par_model_v2.user_inputs import user_model_points

    pts = user_model_points(dict(user_inputs) if user_inputs is not None else None)
    if pts:
        par_pts, _gmmb = split_model_points(pts)
        if not par_pts:
            raise ValueError("user inputs contain no PAR model points "
                             "(only non-PAR rows: GMMB/term/annuity); "
                             "nothing to build")
        return portfolio_from_model_points(
            par_pts, cash_mechanics=cash_mechanics, rb_mechanics=rb_mechanics)
    return generate_hk_par_portfolio(
        config, cash_mechanics=cash_mechanics, rb_mechanics=rb_mechanics)
