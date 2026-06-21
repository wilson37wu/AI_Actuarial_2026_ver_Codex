"""Tests for the Phase 11 synthetic HK PAR portfolio generator."""

from __future__ import annotations

import json
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from par_model_v2.projection import (
    PortfolioGenerationConfig,
    PRODUCT_LINE_CASH,
    PRODUCT_LINE_RB,
    generate_hk_par_portfolio,
    iter_policy_chunks,
    load_portfolio,
    portfolio_digest,
    portfolio_summary,
    validate_portfolio,
    write_metadata,
    write_portfolio,
)
from par_model_v2.projection.monthly_projection import VALID_TERMS
from par_model_v2.projection.portfolio_generator import UNIFIED_COLUMNS


SMALL = PortfolioGenerationConfig(n_policies=5_000, seed=12345)


@pytest.fixture(scope="module")
def small_result():
    return generate_hk_par_portfolio(SMALL)


def test_row_count_and_columns(small_result):
    df = small_result.policies
    assert len(df) == SMALL.n_policies
    assert list(df.columns) == list(UNIFIED_COLUMNS)


def test_default_config_targets_100k():
    cfg = PortfolioGenerationConfig()
    assert cfg.n_policies == 100_000


def test_reproducible_digest_and_table():
    a = generate_hk_par_portfolio(SMALL)
    b = generate_hk_par_portfolio(SMALL)
    assert a.digest == b.digest
    pd.testing.assert_frame_equal(a.policies, b.policies)


def test_different_seed_changes_portfolio():
    a = generate_hk_par_portfolio(SMALL)
    b = generate_hk_par_portfolio(replace(SMALL, seed=SMALL.seed + 1))
    assert a.digest != b.digest


def test_unique_policy_ids(small_result):
    df = small_result.policies
    assert not df["policy_id"].duplicated().any()


def test_policy_year_within_term(small_result):
    df = small_result.policies
    assert (df["policy_year"] >= 1).all()
    assert (df["policy_year"] <= df["term_years"]).all()


def test_terms_supported(small_result):
    df = small_result.policies
    assert set(df["term_years"].unique()).issubset(set(VALID_TERMS))


def test_value_ranges(small_result):
    df = small_result.policies
    assert (df["sum_assured"] >= 50_000.0).all()
    assert (df["sum_assured"] <= 10_000_000.0).all()
    assert (df["annual_premium"] > 0.0).all()
    assert (df["issue_age"] >= 18).all()
    assert (df["issue_age"] <= 65).all()
    assert (df["inforce_count"] == 1.0).all()
    assert set(df["gender"].unique()).issubset({"M", "F"})


def test_product_line_specific_fields(small_result):
    df = small_result.policies
    cash = df[df["product_line"] == PRODUCT_LINE_CASH]
    rb = df[df["product_line"] == PRODUCT_LINE_RB]
    assert not cash.empty and not rb.empty
    # Cash dividend policies carry no vested bonus and use the CASH option.
    assert (cash["initial_vested_bonus"] == 0.0).all()
    assert (cash["dividend_option"] == "CASH").all()
    assert (cash["product_code"] == "HKCD_PAR_2026").all()
    # Reversionary bonus policies have non-negative vested bonus.
    assert (rb["initial_vested_bonus"] >= 0.0).all()
    assert (rb["bonus_option"] == "VESTED_REVERSIONARY").all()
    assert (rb["product_code"] == "HKRB_PAR_2026").all()
    # New-business RB (policy_year 1) has zero accrued vested bonus.
    rb_year1 = rb[rb["policy_year"] == 1]
    assert (rb_year1["initial_vested_bonus"] == 0.0).all()


def test_validate_portfolio_full(small_result):
    assert validate_portfolio(small_result.policies, sample_size=None) is True


def test_validate_portfolio_sampled(small_result):
    assert validate_portfolio(small_result.policies, sample_size=500) is True


def test_validate_rejects_duplicate_ids(small_result):
    df = small_result.policies.copy()
    df.loc[df.index[1], "policy_id"] = df.loc[df.index[0], "policy_id"]
    with pytest.raises(ValueError, match="unique"):
        validate_portfolio(df, sample_size=None)


def test_validate_rejects_missing_column(small_result):
    df = small_result.policies.drop(columns=["sum_assured"])
    with pytest.raises(ValueError, match="missing required columns"):
        validate_portfolio(df)


def test_validate_rejects_out_of_range_sum_assured(small_result):
    df = small_result.policies.copy()
    df.loc[df.index[0], "sum_assured"] = 1.0  # below product minimum
    with pytest.raises(ValueError):
        validate_portfolio(df, sample_size=None)


def test_summary_reconciles(small_result):
    df = small_result.policies
    summary = portfolio_summary(df)
    assert summary["n_policies"] == len(df)
    assert summary["n_cash_dividend"] + summary["n_reversionary_bonus"] == len(df)
    assert summary["total_sum_assured"] == pytest.approx(df["sum_assured"].sum())
    assert summary["total_annual_premium"] == pytest.approx(df["annual_premium"].sum())
    assert sum(summary["term_mix"].values()) == len(df)
    assert sum(summary["gender_mix"].values()) == len(df)
    assert sum(summary["channel_mix"].values()) == len(df)


def test_chunking_partitions_without_loss(small_result):
    df = small_result.policies
    chunks = list(iter_policy_chunks(df, chunk_size=700))
    assert sum(len(c) for c in chunks) == len(df)
    # Chunks are non-overlapping and cover every policy exactly once.
    recovered = pd.concat(chunks)["policy_id"]
    assert set(recovered) == set(df["policy_id"])
    assert not recovered.duplicated().any()


def test_chunking_is_deterministic(small_result):
    df = small_result.policies
    first = [c["policy_id"].tolist() for c in iter_policy_chunks(df, 700)]
    second = [c["policy_id"].tolist() for c in iter_policy_chunks(df, 700)]
    assert first == second


def test_chunk_size_must_be_positive(small_result):
    with pytest.raises(ValueError):
        list(iter_policy_chunks(small_result.policies, chunk_size=0))


def test_digest_changes_on_edit(small_result):
    df = small_result.policies
    base = portfolio_digest(df)
    edited = df.copy()
    edited.loc[edited.index[0], "sum_assured"] += 1000.0
    assert portfolio_digest(edited) != base


def test_roundtrip_csv(small_result, tmp_path):
    path = write_portfolio(small_result.policies, tmp_path / "portfolio.csv")
    loaded = load_portfolio(path)
    assert len(loaded) == len(small_result.policies)
    assert portfolio_digest(loaded) == small_result.digest


def test_metadata_serialisable(small_result, tmp_path):
    path = write_metadata(small_result, tmp_path / "meta.json")
    meta = json.loads(path.read_text(encoding="utf-8"))
    assert meta["n_policies"] == len(small_result.policies)
    assert meta["digest_sha256"] == small_result.digest
    assert meta["seed"] == SMALL.seed


def test_config_rejects_unsupported_term():
    with pytest.raises(ValueError, match="supported terms"):
        PortfolioGenerationConfig(term_weights=((7, 1.0),))


def test_config_rejects_bad_share():
    with pytest.raises(ValueError):
        PortfolioGenerationConfig(cash_dividend_share=1.5)


def test_config_rejects_nonpositive_count():
    with pytest.raises(ValueError):
        PortfolioGenerationConfig(n_policies=0)


def test_mechanics_range_clamping():
    # Tighten product issue-age range and confirm generation respects it.
    from par_model_v2.projection.hk_participating import (
        default_hk_cash_dividend_mechanics,
        default_hk_reversionary_bonus_mechanics,
    )
    cash = replace(default_hk_cash_dividend_mechanics(), issue_age_min=30, issue_age_max=55)
    rb = replace(default_hk_reversionary_bonus_mechanics(), issue_age_min=30, issue_age_max=55)
    res = generate_hk_par_portfolio(SMALL, cash_mechanics=cash, rb_mechanics=rb)
    df = res.policies
    assert (df["issue_age"] >= 30).all()
    assert (df["issue_age"] <= 55).all()
    assert validate_portfolio(df, cash_mechanics=cash, rb_mechanics=rb, sample_size=None)
