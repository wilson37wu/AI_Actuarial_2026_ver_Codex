"""Tests for par_model_v2.calibration.live_market_data_pipeline (Roadmap item #1, MR-006)."""

import json
from datetime import date

import pandas as pd
import pytest

from par_model_v2.calibration.live_market_data_pipeline import (
    CNYYieldCurveLoader,
    CSI300IndexLoader,
    MarketDataFetchError,
    MarketDataResult,
    PROVENANCE_CACHE,
    PROVENANCE_FIXTURE,
    PROVENANCE_LIVE,
    SnapshotCache,
    SnapshotIntegrityError,
)


@pytest.fixture
def cache(tmp_path):
    return SnapshotCache(tmp_path / "snapshots")


def _curve_records(as_of="2026-02-13"):
    tenors = [0.25, 1, 2, 5, 10, 30]
    zeros = [0.011, 0.013, 0.014, 0.016, 0.019, 0.023]
    return [
        {"date": as_of, "tenor_years": t, "zero_rate": z}
        for t, z in zip(tenors, zeros)
    ]


def _equity_records(n=300, as_of_start="2025-01-01"):
    dates = pd.bdate_range(as_of_start, periods=n)
    return [
        {"date": d.strftime("%Y-%m-%d"), "index_level": 3500.0 + i}
        for i, d in enumerate(dates)
    ]


# ---------------------------------------------------------------- fixture tier

def test_curve_fixture_loads_and_snapshots(cache):
    loader = CNYYieldCurveLoader(cache)
    result = loader.load()
    assert isinstance(result, MarketDataResult)
    assert result.provenance == PROVENANCE_FIXTURE
    assert result.as_of_date == "2026-01-01"
    assert len(result.frame) == 11
    assert (pd.to_numeric(result.frame["zero_rate"]) <= 0.03).all()  # CBIRC cap
    assert cache.path_for("cny_yield_curve", "2026-01-01").exists()
    assert result.lineage.sha256_checksum == result.sha256

    series = loader.to_curve_series(result)
    assert series.index[0] == 0.25 and series.index[-1] == 30.0
    assert series.is_monotonic_increasing  # upward-sloping proxy curve


def test_csi300_fixture_loads_and_snapshots(cache):
    loader = CSI300IndexLoader(cache)
    result = loader.load()
    assert result.provenance == PROVENANCE_FIXTURE
    assert len(result.frame) >= 252  # equity_index interface minimum
    series = loader.to_level_series(result)
    assert (series > 0).all()
    assert series.index.is_monotonic_increasing


# ---------------------------------------------------------------- cache tier

def test_second_load_prefers_cached_snapshot(cache):
    loader = CNYYieldCurveLoader(cache)
    first = loader.load()
    second = loader.load(as_of=first.as_of_date)
    assert second.provenance == PROVENANCE_CACHE
    assert second.sha256 == first.sha256
    pd.testing.assert_frame_equal(first.frame, second.frame)


def test_latest_snapshot_selected_when_no_as_of(cache):
    cache.store("cny_yield_curve", "2026-01-01", _curve_records("2026-01-01"),
                PROVENANCE_LIVE, "stub")
    cache.store("cny_yield_curve", "2026-03-01", _curve_records("2026-03-01"),
                PROVENANCE_LIVE, "stub")
    loader = CNYYieldCurveLoader(cache)
    result = loader.load()
    assert result.provenance == PROVENANCE_CACHE
    assert result.as_of_date == "2026-03-01"


def test_tampered_snapshot_rejected_then_fixture_fallback(cache):
    loader = CNYYieldCurveLoader(cache)
    first = loader.load()
    path = cache.path_for("cny_yield_curve", first.as_of_date)
    payload = json.loads(path.read_text())
    payload["records"][0]["zero_rate"] = 0.029  # tamper without resealing
    path.write_text(json.dumps(payload))
    with pytest.raises(SnapshotIntegrityError):
        cache.load("cny_yield_curve", first.as_of_date)
    # loader falls through to the fixture tier and re-seals the snapshot
    recovered = loader.load(as_of=first.as_of_date)
    assert recovered.provenance == PROVENANCE_FIXTURE
    assert recovered.sha256 == first.sha256


# ---------------------------------------------------------------- live tier

def test_live_fetch_validates_caches_and_flags_unsigned(cache):
    calls = []

    def fetcher(as_of):
        calls.append(as_of)
        return _curve_records(as_of.isoformat())

    loader = CNYYieldCurveLoader(cache, fetcher=fetcher)
    result = loader.load(as_of=date(2026, 2, 13))
    assert result.provenance == PROVENANCE_LIVE
    assert calls == [date(2026, 2, 13)]
    assert result.lineage.approved_by == "UNSIGNED_PENDING_OWNER_APPROVAL"
    assert cache.path_for("cny_yield_curve", "2026-02-13").exists()
    # cached copy now satisfies subsequent loads without refetch
    again = loader.load(as_of="2026-02-13")
    assert again.provenance == PROVENANCE_CACHE
    assert len(calls) == 1


def test_refresh_forces_refetch_over_snapshot(cache):
    calls = []

    def fetcher(as_of):
        calls.append(as_of)
        return _curve_records(as_of.isoformat())

    loader = CNYYieldCurveLoader(cache, fetcher=fetcher)
    loader.load(as_of=date(2026, 2, 13))
    loader.load(as_of=date(2026, 2, 13), refresh=True)
    assert len(calls) == 2


def test_failing_fetcher_falls_back_to_fixture(cache):
    def fetcher(as_of):
        raise ConnectionError("vendor endpoint unreachable")

    loader = CNYYieldCurveLoader(cache, fetcher=fetcher)
    result = loader.load()
    assert result.provenance == PROVENANCE_FIXTURE


def test_invalid_live_payload_rejected_not_cached(cache):
    def fetcher(as_of):
        bad = _curve_records(as_of.isoformat())
        bad[2]["zero_rate"] = 1.5  # breaches interface max 1.0
        return bad

    loader = CNYYieldCurveLoader(cache, fetcher=fetcher,
                                 fixture_path="/nonexistent.json")
    with pytest.raises(MarketDataFetchError):
        loader.load(as_of=date(2026, 2, 13))
    assert not cache.list_snapshots("cny_yield_curve")


# ---------------------------------------------------------------- schema checks

def test_curve_structural_validation(cache):
    loader = CNYYieldCurveLoader(cache, fixture_path="/nonexistent.json")

    with pytest.raises(ValueError, match="strictly increasing"):
        rows = _curve_records()
        rows[1], rows[2] = rows[2], rows[1]
        loader._validate(rows)

    with pytest.raises(ValueError, match="one as-of date"):
        rows = _curve_records()
        rows[0]["date"] = "2026-02-12"
        loader._validate(rows)

    with pytest.raises(ValueError, match="tenors"):
        loader._validate(_curve_records()[:3])  # below MIN_TENOR_COUNT

    with pytest.raises(ValueError):
        rows = [{"date": r["date"], "tenor_years": r["tenor_years"]}
                for r in _curve_records()]
        loader._validate(rows)  # missing zero_rate column


def test_equity_structural_validation(cache):
    loader = CSI300IndexLoader(cache, fixture_path="/nonexistent.json")

    with pytest.raises(ValueError, match="strictly positive"):
        rows = _equity_records()
        rows[10]["index_level"] = 0.0
        loader._validate(rows)

    with pytest.raises(ValueError, match="duplicate"):
        rows = _equity_records()
        rows[5]["date"] = rows[4]["date"]
        loader._validate(rows)

    with pytest.raises(ValueError):
        loader._validate(_equity_records(n=100))  # below 252 minimum


def test_all_tiers_exhausted_raises(cache):
    loader = CNYYieldCurveLoader(cache, fixture_path="/nonexistent.json")
    with pytest.raises(MarketDataFetchError, match="all provenance tiers exhausted"):
        loader.load()
