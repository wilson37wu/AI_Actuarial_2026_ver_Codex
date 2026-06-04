"""Runtime P/Q measure-enforcement tests (gate G-05 / risk MR-004).

These tests verify that every scenario-generation execution path enforces the
P (real-world) / Q (risk-neutral) measure contract at runtime, rather than
relying on soft coercion alone.

SOA ASOP 56 ss3.1.3 (measure appropriateness for model purpose);
IA TAS M ss3.4 (consistency and segregation of bases).

Phase 14, Task 1.
"""

import numpy as np
import pandas as pd
import pytest

from par_model_v2.stochastic.esg_process import (
    Measure,
    MeasureEnforcementError,
    HullWhiteRateProcess,
    G2PlusRateProcess,
    GBMEquityProcess,
    FXSpotProcess,
    ScenarioSet,
    _enforce_simulation_measure,
    _assert_output_measure,
)


PROCESS_FACTORIES = {
    "HullWhiteRateProcess": lambda: HullWhiteRateProcess(),
    "G2PlusRateProcess": lambda: G2PlusRateProcess(),
    "GBMEquityProcess": lambda: GBMEquityProcess(),
    "FXSpotProcess": lambda: FXSpotProcess(),
}


class TestSupportedMeasuresDeclared:
    """Every generator declares an explicit, auditable measure contract."""

    @pytest.mark.parametrize("factory", list(PROCESS_FACTORIES.values()),
                             ids=list(PROCESS_FACTORIES.keys()))
    def test_process_declares_supported_measures(self, factory):
        process = factory()
        assert hasattr(process, "SUPPORTED_MEASURES")
        supported = tuple(process.SUPPORTED_MEASURES)
        assert supported, "SUPPORTED_MEASURES must not be empty"
        assert all(isinstance(m, Measure) for m in supported)
        # Reference processes support both bases.
        assert set(supported) == {Measure.P, Measure.Q}

    def test_scenarioset_declares_supported_measures(self):
        assert set(ScenarioSet.SUPPORTED_MEASURES) == {Measure.P, Measure.Q}


class TestRuntimeGuardAcceptsValidMeasures:
    """Valid P/Q requests run and are stamped uniformly on the output."""

    @pytest.mark.parametrize("measure_in,expected", [
        (Measure.P, "P"), (Measure.Q, "Q"), ("p", "P"), ("Q", "Q"), (" q ", "Q"),
    ])
    def test_hw_accepts_and_stamps(self, measure_in, expected):
        df = HullWhiteRateProcess().simulate(4, 6, measure_in, seed=3)
        assert set(df["measure"]) == {expected}

    def test_all_processes_stamp_requested_measure(self):
        hw = HullWhiteRateProcess()
        assert set(hw.simulate(3, 4, Measure.P, seed=1)["measure"]) == {"P"}
        assert set(G2PlusRateProcess().simulate(3, 4, Measure.Q, seed=1)["measure"]) == {"Q"}
        assert set(GBMEquityProcess().simulate(3, 4, Measure.P, seed=1)["measure"]) == {"P"}
        assert set(FXSpotProcess().simulate(3, 4, Measure.Q, seed=1)["measure"]) == {"Q"}

    def test_scenarioset_generate_stamps_measure(self):
        ss = ScenarioSet.generate(16, 12, Measure.Q, seed=5)
        assert set(ss.data["measure"]) == {"Q"}
        assert ss.measure == Measure.Q


class TestRuntimeGuardRejectsInvalid:
    """The guard hard-fails on malformed or unsupported measures."""

    @pytest.mark.parametrize("bad", ["X", "real-world", "", None, 1, "PQ"])
    def test_invalid_measure_raises_value_error(self, bad):
        with pytest.raises(ValueError):
            HullWhiteRateProcess().simulate(3, 4, bad)

    def test_unsupported_measure_raises_measure_enforcement_error(self):
        class QOnlyProcess(HullWhiteRateProcess):
            SUPPORTED_MEASURES = (Measure.Q,)

        with pytest.raises(MeasureEnforcementError, match="not permitted"):
            QOnlyProcess().simulate(3, 4, Measure.P)

    def test_empty_supported_measures_raises(self):
        class NoMeasureProcess(HullWhiteRateProcess):
            SUPPORTED_MEASURES = ()

        with pytest.raises(MeasureEnforcementError, match="no supported measures"):
            NoMeasureProcess().simulate(3, 4, Measure.P)

    def test_enforcement_error_is_value_error_subclass(self):
        assert issubclass(MeasureEnforcementError, ValueError)


class TestEnforceSimulationMeasureHelper:
    """Direct unit tests of the runtime guard helper."""

    def test_accepts_instance(self):
        assert _enforce_simulation_measure(GBMEquityProcess(), "p") == Measure.P

    def test_accepts_class_for_classmethods(self):
        assert _enforce_simulation_measure(ScenarioSet, "Q") == Measure.Q

    def test_accepts_string_label_with_default_scope(self):
        assert _enforce_simulation_measure("AdHocProcess", Measure.P) == Measure.P

    def test_rejects_unsupported_for_class(self):
        class QOnly(GBMEquityProcess):
            SUPPORTED_MEASURES = (Measure.Q,)
        with pytest.raises(MeasureEnforcementError):
            _enforce_simulation_measure(QOnly, Measure.P)


class TestAssertOutputMeasurePostCondition:
    """The post-condition catches silent mis-stamping at runtime."""

    def test_passes_on_uniform_correct_stamp(self):
        frame = pd.DataFrame({"measure": ["Q", "Q", "Q"]})
        assert _assert_output_measure(frame, Measure.Q, "T") is frame

    def test_rejects_mismatched_stamp(self):
        frame = pd.DataFrame({"measure": ["P", "P"]})
        with pytest.raises(MeasureEnforcementError, match="does not match"):
            _assert_output_measure(frame, Measure.Q, "T")

    def test_rejects_mixed_stamp(self):
        frame = pd.DataFrame({"measure": ["P", "Q"]})
        with pytest.raises(MeasureEnforcementError):
            _assert_output_measure(frame, Measure.P, "T")

    def test_rejects_missing_column(self):
        frame = pd.DataFrame({"x": [1, 2]})
        with pytest.raises(MeasureEnforcementError, match="missing the 'measure'"):
            _assert_output_measure(frame, Measure.P, "T")


class TestMeasureSeparationIsMeaningful:
    """P and Q produce different dynamics, confirming the contract has teeth."""

    def test_p_and_q_short_rate_paths_differ(self):
        process = HullWhiteRateProcess()
        p_df = process.simulate(200, 60, Measure.P, seed=11)
        q_df = process.simulate(200, 60, Measure.Q, seed=11)
        p_term = p_df[p_df["month"] == 60]["r_short"].mean()
        q_term = q_df[q_df["month"] == 60]["r_short"].mean()
        assert not np.isclose(p_term, q_term)
