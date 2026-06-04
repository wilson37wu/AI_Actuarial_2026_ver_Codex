"""
Tests — Phase 13 HW1F Calibration: Live CNY/HKD Swaption Data Integration
==========================================================================
Test count target: 38
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from par_model_v2.calibration.market_data_source import (
    DataLineageRecord,
    FileBasedSwaptionSource,
    LiveSwaptionDataLoader,
    ProductionGateStatus,
    SwaptionMarketDataSource,
    build_file_based_loader,
    evaluate_g02_gate,
    evaluate_g12_gate,
)
from par_model_v2.calibration.phase13_hw1f_calibration import (
    MarketCalibrationSummary,
    Phase13CalibrationReport,
    run_phase13_hw1f_calibration,
)
from par_model_v2.calibration.calibration_framework import SwaptionQuote

FIXTURES_DIR = Path(__file__).parent.parent / "par_model_v2" / "calibration" / "fixtures"
CNY_FIXTURE = FIXTURES_DIR / "cny_swaption_surface_20260101.json"
HKD_FIXTURE = FIXTURES_DIR / "hkd_swaption_surface_20260101.json"


# ---------------------------------------------------------------------------
# A. FileBasedSwaptionSource
# ---------------------------------------------------------------------------

class TestFileBasedSwaptionSource:

    def test_cny_fixture_loads(self):
        assert FileBasedSwaptionSource(CNY_FIXTURE).market == "CNY"

    def test_hkd_fixture_loads(self):
        assert FileBasedSwaptionSource(HKD_FIXTURE).market == "HKD"

    def test_cny_swaption_quotes_non_empty(self):
        assert len(FileBasedSwaptionSource(CNY_FIXTURE).fetch_swaption_quotes()) >= 8

    def test_hkd_swaption_quotes_non_empty(self):
        assert len(FileBasedSwaptionSource(HKD_FIXTURE).fetch_swaption_quotes()) >= 8

    def test_cny_all_quotes_positive_vol(self):
        for q in FileBasedSwaptionSource(CNY_FIXTURE).fetch_swaption_quotes():
            assert q.normal_vol_bps > 0

    def test_spot_curve_cny_ascending_tenors(self):
        curve = FileBasedSwaptionSource(CNY_FIXTURE).fetch_spot_curve()
        assert len(curve) >= 5
        assert curve.index[0] < curve.index[-1]

    def test_spot_curve_cny_rates_in_range(self):
        curve = FileBasedSwaptionSource(CNY_FIXTURE).fetch_spot_curve()
        assert (curve >= 0.0).all()
        assert (curve <= 0.15).all()

    def test_initial_short_rate_cny_range(self):
        r0 = FileBasedSwaptionSource(CNY_FIXTURE).fetch_initial_short_rate()
        assert 0.0 < r0 < 0.15

    def test_calibration_date_cny_is_date(self):
        d = FileBasedSwaptionSource(CNY_FIXTURE).fetch_calibration_date()
        assert isinstance(d, date)
        assert d.year >= 2020

    def test_lineage_record_cny_has_sha256(self):
        lin = FileBasedSwaptionSource(CNY_FIXTURE).build_lineage_record()
        assert lin.sha256_checksum and len(lin.sha256_checksum) >= 16

    def test_lineage_record_cny_market_matches(self):
        assert FileBasedSwaptionSource(CNY_FIXTURE).build_lineage_record().market == "CNY"

    def test_missing_fixture_raises(self):
        with pytest.raises(FileNotFoundError):
            FileBasedSwaptionSource(FIXTURES_DIR / "nonexistent.json")

    def test_hkd_regulatory_cap_in_range(self):
        cap = FileBasedSwaptionSource(HKD_FIXTURE).fetch_regulatory_rate_cap()
        assert 0.01 < cap < 0.20


# ---------------------------------------------------------------------------
# B. LiveSwaptionDataLoader
# ---------------------------------------------------------------------------

class TestLiveSwaptionDataLoader:

    def test_cny_load_returns_inputs_and_lineage(self):
        inputs, lineage = build_file_based_loader("CNY", fixture_dir=FIXTURES_DIR).load()
        assert inputs is not None
        assert lineage is not None

    def test_hkd_load_returns_inputs_and_lineage(self):
        inputs, lineage = build_file_based_loader("HKD", fixture_dir=FIXTURES_DIR).load()
        assert inputs is not None
        assert lineage is not None

    def test_cny_inputs_have_swaption_quotes(self):
        inputs, _ = build_file_based_loader("CNY", fixture_dir=FIXTURES_DIR).load()
        assert len(inputs.swaption_quotes) >= 8

    def test_cny_spot_curve_is_series(self):
        inputs, _ = build_file_based_loader("CNY", fixture_dir=FIXTURES_DIR).load()
        assert isinstance(inputs.spot_curve, pd.Series)

    def test_validation_rejects_too_few_quotes(self):
        src = FileBasedSwaptionSource(CNY_FIXTURE)
        loader = LiveSwaptionDataLoader(src, min_swaption_count=999)
        with pytest.raises(ValueError, match="active quotes"):
            loader.load()

    def test_validation_rejects_negative_vol(self):
        src = FileBasedSwaptionSource(CNY_FIXTURE)

        class BadSource(SwaptionMarketDataSource):
            @property
            def market(self): return "CNY"
            def fetch_swaption_quotes(self):
                return [SwaptionQuote(1.0, 1.0, -5.0, 1.0)]
            def fetch_spot_curve(self):
                return pd.Series([0.02, 0.025], index=[1.0, 5.0])
            def fetch_initial_short_rate(self): return 0.02
            def fetch_calibration_date(self): return date(2026, 1, 1)
            def fetch_regulatory_rate_cap(self): return 0.03
            def build_lineage_record(self): return src.build_lineage_record()

        loader = LiveSwaptionDataLoader(BadSource(), min_swaption_count=1)
        with pytest.raises(ValueError, match="non-positive normal_vol_bps"):
            loader.load()

    def test_build_file_based_loader_cny(self):
        assert build_file_based_loader("CNY", fixture_dir=FIXTURES_DIR).market == "CNY"

    def test_build_file_based_loader_hkd(self):
        assert build_file_based_loader("HKD", fixture_dir=FIXTURES_DIR).market == "HKD"


# ---------------------------------------------------------------------------
# C. Production gates
# ---------------------------------------------------------------------------

class TestProductionGates:

    def test_g02_pass_when_both_calibrated_and_rmse_ok(self):
        gate = evaluate_g02_gate(False, 15.0, False, 18.0)
        assert gate.gate_id == "G-02"
        assert gate.status == "PASS"

    def test_g02_fail_when_placeholder_cny(self):
        gate = evaluate_g02_gate(True, 15.0, False, 18.0)
        assert gate.status == "FAIL"
        assert "is_placeholder=True" in gate.evidence

    def test_g02_fail_when_rmse_exceeds_threshold(self):
        gate = evaluate_g02_gate(False, 30.0, False, 18.0)
        assert gate.status == "FAIL"
        assert "30.00bps > 25.0bps" in gate.evidence

    def test_g02_fail_when_rmse_none(self):
        gate = evaluate_g02_gate(False, None, False, 18.0)
        assert gate.status == "FAIL"
        assert "not available" in gate.evidence

    def test_g12_pass_when_both_lineages_present(self):
        cny = DataLineageRecord("LIN_CNY", "CNY", "2026-01-01", "file_fixture",
                                "/p/cny.json", "1.0.0", "test", "2026-01-01T00:00:00Z", "abc123")
        hkd = DataLineageRecord("LIN_HKD", "HKD", "2026-01-01", "file_fixture",
                                "/p/hkd.json", "1.0.0", "test", "2026-01-01T00:00:00Z", "def456")
        assert evaluate_g12_gate([cny, hkd]).status == "PASS"

    def test_g12_fail_when_market_missing(self):
        cny = DataLineageRecord("LIN_CNY", "CNY", "2026-01-01", "file_fixture",
                                "/p/cny.json", "1.0.0", "test", "2026-01-01T00:00:00Z", "abc")
        gate = evaluate_g12_gate([cny])
        assert gate.status == "FAIL"
        assert "HKD" in gate.evidence

    def test_gate_status_to_dict(self):
        d = ProductionGateStatus("G-02", "desc", "PASS", "evidence", "2026-01-01T00:00:00Z").to_dict()
        assert d["gate_id"] == "G-02"
        assert d["status"] == "PASS"


# ---------------------------------------------------------------------------
# D. DataLineageRecord round-trip
# ---------------------------------------------------------------------------

class TestDataLineageRecord:

    def test_round_trip(self):
        lr = DataLineageRecord("LIN_TEST", "CNY", "2026-01-01", "file_fixture",
                               "/x/y.json", "2.0.0", "owner", "2026-01-01T00:00:00Z", "cafebabe")
        lr2 = DataLineageRecord.from_dict(lr.to_dict())
        assert lr2.market == "CNY"
        assert lr2.sha256_checksum == "cafebabe"


# ---------------------------------------------------------------------------
# E. End-to-end pipeline
# ---------------------------------------------------------------------------

class TestRunPhase13HW1FCalibration:

    @pytest.fixture(scope="class")
    def report(self):
        import warnings
        warnings.filterwarnings("ignore")
        return run_phase13_hw1f_calibration(fixture_dir=FIXTURES_DIR)

    def test_pipeline_returns_report(self, report):
        assert isinstance(report, Phase13CalibrationReport)

    def test_cny_not_placeholder(self, report):
        assert not report.cny.is_placeholder

    def test_hkd_not_placeholder(self, report):
        assert not report.hkd.is_placeholder

    def test_cny_a_positive(self, report):
        assert report.cny.a > 0

    def test_hkd_sigma_positive(self, report):
        assert report.hkd.sigma_r > 0

    def test_cny_rmse_finite(self, report):
        assert report.cny.swaption_rmse_bps is not None
        assert np.isfinite(report.cny.swaption_rmse_bps)

    def test_hkd_rmse_finite(self, report):
        assert report.hkd.swaption_rmse_bps is not None
        assert np.isfinite(report.hkd.swaption_rmse_bps)

    def test_gate_g02_pass(self, report):
        assert report.gate_g02.status == "PASS", report.gate_g02.evidence

    def test_gate_g12_pass(self, report):
        assert report.gate_g12.status == "PASS", report.gate_g12.evidence

    def test_gates_all_pass(self, report):
        assert report.gates_all_pass()

    def test_change_record_id_non_empty(self, report):
        assert report.change_record_id and len(report.change_record_id) >= 8

    def test_markdown_contains_phase_header(self, report):
        assert "Phase 13 HW1F Calibration Report" in report.markdown_report

    def test_markdown_contains_gate_rows(self, report):
        assert "G-02" in report.markdown_report
        assert "G-12" in report.markdown_report

    def test_json_round_trip(self, report):
        d = json.loads(report.to_json())
        assert d["cny"]["market"] == "CNY"
        assert d["hkd"]["market"] == "HKD"
        assert d["gate_g02"]["status"] == report.gate_g02.status

    def test_report_written_to_path(self, tmp_path):
        import warnings
        warnings.filterwarnings("ignore")
        md_path = tmp_path / "PHASE13_HW1F_CALIBRATION_REPORT.md"
        rpt = run_phase13_hw1f_calibration(fixture_dir=FIXTURES_DIR, report_output_path=md_path)
        assert md_path.exists()
        assert "Phase 13" in md_path.read_text(encoding="utf-8")
        assert (md_path.with_suffix(".json")).exists()

    def test_cny_r0_matches_fixture(self, report):
        assert abs(report.cny.r0 - 0.0207) < 1e-6

    def test_hkd_r0_matches_fixture(self, report):
        assert abs(report.hkd.r0 - 0.0450) < 1e-6
