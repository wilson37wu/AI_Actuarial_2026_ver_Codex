"""
Six-Driver Economic Capital: FX / Currency as the Sixth Driver (Phase 21 Task 1)
================================================================================

Adds a stochastic **FX / currency** driver to the Phase 20 five-driver
(G2++ rate, equity, credit-spread, dynamic-lapse, mortality-trend) economic-
capital proxy, per the MR-012 residual ("FX and liquidity omitted").

Design (additive — imports, never modifies, the Phase 19/20 engines)
--------------------------------------------------------------------
* OUTER real-world state becomes ``(r_H, S_H, s_H, b_H, m_H, X_H)`` where
  ``X_H`` is a lognormal FX spot (base units per foreign unit, e.g. HKD per
  USD) driven by a sixth governed, Cholesky-correlated shock under the
  **P measure** (real-world drift).  The first five drivers are bit-compatible
  with the Phase 20 G2++ aggregator: the same shock stream construction is
  used and the five-driver CRN component liabilities are reused verbatim.
* INNER Q-nest conditioning on the FX state is **analytic and CIP-exact**: the
  educational FX exposure is a foreign-currency asset leg backing a fraction of
  the liability.  Under the domestic Q measure with the covered-interest-parity
  drift ``(r_d - r_f)``, the deflated translated foreign money-market account is
  a martingale (Phase 20 ``MART-FX-CIP``):

      E^Q[ D_d(H+s) X(H+s) exp(r_f (H+s)) | X_H ] = D_d(H) X_H exp(r_f H)

  so the inner conditional PV of the translated leg given ``X_H`` equals its
  time-H translated value — no inner FX simulation noise is introduced and the
  conditional mean is exact, not approximated.  The FX liability component is
  therefore ``fx_l = notional * (1 - X_H / X_0)``: a translation **loss** when
  the foreign currency depreciates against the domestic currency.
* Aggregation mirrors Phase 19/20: standalone SCRs (now six), var-covar with
  the governed 6x6 ESG correlation, copula-on-realised-losses across the six
  loss vectors, and the nested full benchmark ``full_l6 = full_l5 + fx_l``.

G-FX plausibility gate
----------------------
``evaluate_g_fx_gate`` checks: positive spots (FX-01), lognormal terminal
moments (FX-02), P/Q drift separation (FX-03), Q-measure CIP martingale
evidence reusing the Phase 20 ``MART-FX-CIP`` check (FX-04), governed
rate-FX shock-correlation wiring (FX-05), and exposure-mapping sanity (FX-06).

EDUCATIONAL MODEL: parameters are placeholder/proxy, not calibrated to
credentialled market data; see ``six_driver_fx_use_restrictions``.

SOA ASOP 56 §3.1.3/§3.4/§3.5; SOA ASOP 25 §3.3; IA TAS M §3.2/§3.5/§3.6;
Solvency II Delegated Reg. Art. 234 (currency risk: Art. 188); Brigo-Mercurio (2006).
"""

from __future__ import annotations

import hashlib
import json
import math
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from par_model_v2.projection.monthly_projection import ParEndowmentProduct
from par_model_v2.projection.nested_stochastic_tvog import (
    capital_metrics_from_liabilities,
)
from par_model_v2.projection.multi_driver_capital_5d import (
    FiveDriverCorrelation,
)
from par_model_v2.projection.multi_driver_capital_5d_aggregation import (
    FiveDriverAggregationConfig,
)
from par_model_v2.projection.multi_driver_capital_5d_g2pp import (
    G2ppFiveDriverRiskAggregator,
    calibrated_g2pp_params,
)
from par_model_v2.projection.multi_driver_copula_aggregation import (
    CopulaAggregationConfig,
    CopulaRiskAggregator,
)
from par_model_v2.stochastic.esg_process import (
    CorrelationMatrixValidator,
    FXParams,
    FXSpotProcess,
    GBMEquityProcess,
    G2PlusParams,
    Measure,
    RiskFreeCurve,
    _antithetic_normals,
)
from par_model_v2.stochastic.credit_spread import CreditSpreadProcess
from par_model_v2.stochastic.lapse_behaviour import LapseBehaviourProcess
from par_model_v2.stochastic.mortality_trend import MortalityTrendProcess
from par_model_v2.validation.phase20_market_consistency import martingale_fx


# ---------------------------------------------------------------------------
# Educational default FX parameters (HKD per USD translation, placeholder)
# ---------------------------------------------------------------------------

#: Educational placeholder FX parameters: HKD-domestic book with a USD asset
#: leg (USDHKD ~ 7.8).  Volatility is set above the pegged-regime historical
#: level so the driver expresses a genuine de-peg / regime tail axis.
DEFAULT_FX_PARAMS = FXParams(
    fx_vol=0.06,
    real_world_drift=0.0,
    domestic_foreign_rate_spread=0.02,
    rate_fx_correlation=0.0,
    initial_spot_rate=7.8,
)


@dataclass(frozen=True)
class FXExposureSpec:
    """Educational FX exposure: a foreign-currency asset leg backing the book.

    ``exposure_notional`` is the domestic-currency time-H value (at the initial
    spot) of foreign-currency assets backing the liability.  The conditional
    inner-Q valuation of this leg given ``X_H`` is analytic and CIP-exact (see
    module docstring), so the FX liability component is::

        fx_l(X_H) = exposure_notional * (1 - X_H / X_0)

    i.e. a translation loss when the foreign currency depreciates.
    """

    exposure_notional: float = 30_000.0
    initial_spot_rate: float = DEFAULT_FX_PARAMS.initial_spot_rate

    def __post_init__(self) -> None:
        if self.exposure_notional < 0.0:
            raise ValueError("exposure_notional must be >= 0")
        if self.initial_spot_rate <= 0.0:
            raise ValueError("initial_spot_rate must be positive")

    def liability_impact(self, x_h: np.ndarray) -> np.ndarray:
        """Translation loss (positive = liability increase) given spot at H."""
        x = np.asarray(x_h, dtype=float)
        return self.exposure_notional * (1.0 - x / self.initial_spot_rate)


# ---------------------------------------------------------------------------
# 6x6 governed correlation (five-driver block + FX couplings)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SixDriverFXCorrelation:
    """6x6 ESG correlation among (rate, equity, credit, lapse, mortality, fx).

    The 5x5 (rate, equity, credit, lapse, mortality) block is inherited from the
    governed :class:`FiveDriverCorrelation`.  FX couplings default to a mild
    negative rate-FX and equity-FX co-movement (domestic-rate-up / foreign-
    currency-down educational convention) and zero against the non-financial
    drivers, injecting FX as a predominantly orthogonal translation-tail axis.
    """

    five_driver: FiveDriverCorrelation = None  # type: ignore[assignment]
    fx_rate: float = -0.15
    fx_equity: float = -0.10
    fx_spread: float = 0.05
    fx_lapse: float = 0.0
    fx_mortality: float = 0.0

    def __post_init__(self) -> None:
        if self.five_driver is None:
            object.__setattr__(self, "five_driver", FiveDriverCorrelation())
        for name in ("fx_rate", "fx_equity", "fx_spread", "fx_lapse", "fx_mortality"):
            v = getattr(self, name)
            if not (-1.0 <= v <= 1.0):
                raise ValueError("{} must be in [-1, 1]; got {}".format(name, v))

    def matrix(self, gbm_rate_equity: float) -> np.ndarray:
        c5 = self.five_driver.matrix(gbm_rate_equity)
        C = np.eye(6, dtype=float)
        C[:5, :5] = c5
        fx = np.array(
            [self.fx_rate, self.fx_equity, self.fx_spread,
             self.fx_lapse, self.fx_mortality],
            dtype=float,
        )
        C[5, :5] = fx
        C[:5, 5] = fx
        return C

    def cholesky(self, gbm_rate_equity: float) -> np.ndarray:
        """Lower-triangular Cholesky factor; nearest-PD fallback if needed."""
        C = self.matrix(gbm_rate_equity)
        try:
            return np.linalg.cholesky(C)
        except np.linalg.LinAlgError:
            w, V = np.linalg.eigh(C)
            w = np.clip(w, 1e-8, None)
            C_pd = V @ np.diag(w) @ V.T
            d = np.sqrt(np.diag(C_pd))
            C_pd = C_pd / np.outer(d, d)
            return np.linalg.cholesky(C_pd)


def _correlated_shocks_6(
    rng: np.random.Generator,
    n: int,
    steps: int,
    chol: np.ndarray,
) -> Tuple[np.ndarray, ...]:
    """Six (n, steps) correlated antithetic-normal shock arrays.

    The first five rows of the 6x6 Cholesky factor reproduce the five-driver
    construction exactly (same draw order), so the (rate, equity, credit,
    lapse, mortality) outer joint is bit-compatible with the Phase 20
    five-driver G2++ aggregator for the same seed.
    """
    z = [_antithetic_normals(rng, n, steps) for _ in range(6)]
    out = []
    for i in range(6):
        acc = np.zeros_like(z[0])
        for j in range(i + 1):
            if chol[i, j] != 0.0:
                acc = acc + chol[i, j] * z[j]
        out.append(acc)
    return tuple(out)


# ---------------------------------------------------------------------------
# Report containers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SixDriverFXAggregationReport:
    """Structured six-driver aggregation evidence (JSON-serialisable)."""

    config: Dict[str, object]
    drivers: Tuple[str, ...]
    standalone_scr: Dict[str, float]
    standalone_scr_sum: float
    esg_correlation_matrix: Tuple[Tuple[float, ...], ...]
    correlation_matrix_passed: bool
    var_covar_scr: float
    nested_scr: float
    var_covar_vs_nested_rel_error: float
    esg_understatement_pct: float
    copula_selected: str
    copula_scr: float
    copula_vs_nested_rel_error: float
    interaction_residual_rel: float
    fx_exposure_notional: float
    fx_initial_spot: float
    run_id: str
    duration_seconds: float
    verdict: str
    reproducibility_digest: str
    notes: Tuple[str, ...]

    def to_dict(self) -> Dict[str, object]:
        return {
            "config": dict(self.config),
            "drivers": list(self.drivers),
            "standalone_scr": dict(self.standalone_scr),
            "standalone_scr_sum": self.standalone_scr_sum,
            "esg_correlation_matrix": [list(r) for r in self.esg_correlation_matrix],
            "correlation_matrix_passed": self.correlation_matrix_passed,
            "var_covar_scr": self.var_covar_scr,
            "nested_scr": self.nested_scr,
            "var_covar_vs_nested_rel_error": self.var_covar_vs_nested_rel_error,
            "esg_understatement_pct": self.esg_understatement_pct,
            "copula_selected": self.copula_selected,
            "copula_scr": self.copula_scr,
            "copula_vs_nested_rel_error": self.copula_vs_nested_rel_error,
            "interaction_residual_rel": self.interaction_residual_rel,
            "fx_exposure_notional": self.fx_exposure_notional,
            "fx_initial_spot": self.fx_initial_spot,
            "run_id": self.run_id,
            "duration_seconds": self.duration_seconds,
            "verdict": self.verdict,
            "reproducibility_digest": self.reproducibility_digest,
            "notes": list(self.notes),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


# ---------------------------------------------------------------------------
# Six-driver aggregator
# ---------------------------------------------------------------------------

class SixDriverFXRiskAggregator(G2ppFiveDriverRiskAggregator):
    """Six-driver standalone capital + var-covar / copula aggregation with the
    FX / currency translation driver added to the Phase 20 G2++ five-driver
    engine.

    The five-driver CRN component liabilities and the G2++ outer rate dynamics
    are reused unchanged; FX enters through (a) a sixth correlated outer shock
    and (b) a CIP-exact analytic inner conditional valuation of the translated
    foreign asset leg (see module docstring).
    """

    def __init__(
        self,
        *args,
        fx_params: Optional[FXParams] = None,
        fx_exposure: Optional[FXExposureSpec] = None,
        correlation6: Optional[SixDriverFXCorrelation] = None,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.fx_params = fx_params if fx_params is not None else DEFAULT_FX_PARAMS
        self.fx_exposure = fx_exposure if fx_exposure is not None else FXExposureSpec(
            initial_spot_rate=self.fx_params.initial_spot_rate
        )
        self.correlation6 = correlation6 if correlation6 is not None else SixDriverFXCorrelation(
            five_driver=self.correlation
        )
        if abs(self.fx_exposure.initial_spot_rate - self.fx_params.initial_spot_rate) > 1e-12:
            raise ValueError(
                "fx_exposure.initial_spot_rate must equal fx_params.initial_spot_rate"
            )
        self.last_loss_vectors_6d = None

    # -- outer state ------------------------------------------------------ #
    def _outer_states_6d(
        self,
        n_outer: int,
        capital_horizon_months: int,
        measure: Measure,
        seed: int,
    ) -> np.ndarray:
        """(n, 6) outer array (r_H, S_H, s_H, b_H, m_H, X_H).

        G2++ two-factor rates (Phase 20 construction), GBM equity, CIR++
        credit, OU lapse, OU mortality and lognormal FX all driven off ONE
        shared 6-factor Cholesky-correlated antithetic draw.
        """
        g2pp_params = self.g2pp_params
        gbm_params = self.gbm_params
        rng = np.random.default_rng(seed)
        chol = self.correlation6.cholesky(gbm_params.rate_equity_correlation)
        z_rate, z_equity, z_spread, z_lapse, z_mort, z_fx = _correlated_shocks_6(
            rng, n_outer, capital_horizon_months, chol
        )

        curve = self.initial_curve if self.initial_curve is not None else RiskFreeCurve.flat(
            self.hw_params.initial_short_rate
        )

        # G2++ second-factor shock: correlated to the rate shock by the
        # calibrated rho, idiosyncratic part orthogonal (Phase 20 convention).
        rho = float(g2pp_params.factor_correlation)
        z_indep = rng.standard_normal((n_outer, capital_horizon_months))
        z_y = rho * z_rate + math.sqrt(max(0.0, 1.0 - rho * rho)) * z_indep

        a = float(g2pp_params.mean_reversion_x)
        b = float(g2pp_params.mean_reversion_y)
        sigma = float(g2pp_params.vol_x)
        eta = float(g2pp_params.vol_y)
        dt = 1.0 / 12.0
        mx = math.exp(-a * dt)
        my = math.exp(-b * dt)
        sx = sigma * math.sqrt((1.0 - math.exp(-2.0 * a * dt)) / (2.0 * a))
        sy = eta * math.sqrt((1.0 - math.exp(-2.0 * b * dt)) / (2.0 * b))

        steps = capital_horizon_months
        x = np.empty((n_outer, steps + 1), dtype=float)
        y = np.empty((n_outer, steps + 1), dtype=float)
        r = np.empty((n_outer, steps + 1), dtype=float)
        x[:, 0] = float(g2pp_params.initial_x)
        y[:, 0] = float(g2pp_params.initial_y)
        r[:, 0] = float(curve.instantaneous_forward(0.0)) + x[:, 0] + y[:, 0]
        for month in range(steps):
            x[:, month + 1] = mx * x[:, month] + sx * z_rate[:, month]
            y[:, month + 1] = my * y[:, month] + sy * z_y[:, month]
            phi = float(curve.instantaneous_forward(float(month + 1) * dt))
            r[:, month + 1] = phi + x[:, month + 1] + y[:, month + 1]

        gbm = GBMEquityProcess(gbm_params, rate_process=None)
        csp = CreditSpreadProcess(self.spread_params)
        lap = LapseBehaviourProcess(self.lapse_params)
        mor = MortalityTrendProcess(self.mortality_params)
        fxp = FXSpotProcess(self.fx_params)

        equity_paths, _ret = gbm._simulate_array(
            n_outer, capital_horizon_months, measure, r, z_equity
        )
        spread_paths = csp._simulate_array(n_outer, capital_horizon_months, measure, z_spread)
        lapse_paths = lap._simulate_array(n_outer, capital_horizon_months, measure, z_lapse)
        mort_paths = mor._simulate_array(n_outer, capital_horizon_months, measure, z_mort)
        fx_paths, _fxret = fxp._simulate_array(n_outer, capital_horizon_months, measure, z_fx)

        h = capital_horizon_months
        return np.column_stack([
            r[:, h], equity_paths[:, h], spread_paths[:, h],
            lapse_paths[:, h], mort_paths[:, h], fx_paths[:, h],
        ])


    # -- staged execution helpers ------------------------------------------ #
    def component_liabilities_sliced(
        self,
        outer5_full: np.ndarray,
        i0: int,
        i1: int,
        cfg: FiveDriverAggregationConfig,
    ) -> Dict[str, np.ndarray]:
        """CRN component liabilities for outer rows ``[i0, i1)`` of the FULL
        outer array, with seeds identical to the monolithic run.

        ``FiveDriverRiskAggregator._component_liabilities`` spawns one child
        seed per outer row from ``SeedSequence(cfg.seed)``; this helper spawns
        the FULL set and slices it, so a staged run (any slicing) reproduces
        the monolithic loss vectors bit-for-bit (sandbox wall-clock limits
        require staging; ASOP 56 reproducibility).
        """
        from par_model_v2.projection.multi_driver_capital_5d import (
            _inner_pathwise_pvs_5d,
        )
        from par_model_v2.projection.multi_driver_capital import EquityGuaranteeSpec
        from par_model_v2.projection.multi_driver_capital_3d import CreditExposureSpec
        from par_model_v2.projection.multi_driver_capital_5d_aggregation import (
            _NoLapseExposure,
            _NoMortalityExposure,
        )

        rem = self.product.term_months - cfg.capital_horizon_months
        eq_on = self.equity_guarantee
        eq_off = EquityGuaranteeSpec(
            guarantee_rate=0.0,
            initial_index_level=self.equity_guarantee.initial_index_level,
        )
        cr_on = self.credit_exposure
        cr_off = CreditExposureSpec(exposure_rate=0.0)
        lapse_on = self.lapse_exposure
        lapse_off = _NoLapseExposure(
            assumption=self.lapse_exposure.assumption,
            credited_rate=self.lapse_exposure.credited_rate,
            lapse_cap=self.lapse_exposure.lapse_cap,
        )
        mort_on = self.mortality_exposure
        mort_off = _NoMortalityExposure(
            trend_sensitivity=self.mortality_exposure.trend_sensitivity,
            qx_cap=self.mortality_exposure.qx_cap,
        )

        child = np.random.SeedSequence(cfg.seed).spawn(len(outer5_full))[i0:i1]
        n = i1 - i0
        out = {k: np.empty(n, dtype=float) for k in
               ("rate", "equity", "credit", "lapse", "mortality", "full5")}
        for j in range(n):
            r, sv, c, b, m = outer5_full[i0 + j]
            inner_seed = int(child[j].generate_state(1)[0])

            def _mean(eq_spec, cr_spec, lapse_spec, mort_spec):
                pvs = _inner_pathwise_pvs_5d(
                    float(r), float(sv), float(c), float(b), float(m),
                    cfg.n_inner, rem, self.product, self.hw_params,
                    self.gbm_params, self.spread_params, self.correlation,
                    cfg.capital_horizon_months, inner_seed,
                    eq_spec, cr_spec, lapse_spec, mort_spec, self.annual_qx_fn,
                )
                return float(pvs.mean())

            l_base = _mean(eq_off, cr_off, lapse_off, mort_off)
            out["rate"][j] = l_base
            out["equity"][j] = _mean(eq_on, cr_off, lapse_off, mort_off) - l_base
            out["credit"][j] = _mean(eq_off, cr_on, lapse_off, mort_off) - l_base
            out["lapse"][j] = _mean(eq_off, cr_off, lapse_on, mort_off) - l_base
            out["mortality"][j] = _mean(eq_off, cr_off, lapse_off, mort_on) - l_base
            out["full5"][j] = _mean(eq_on, cr_on, lapse_on, mort_on)
        return out

    # -- run --------------------------------------------------------------- #
    def run_6d(
        self,
        config: Optional[FiveDriverAggregationConfig] = None,
        governance_store: Optional["object"] = None,
        actor: str = "SixDriverFXRiskAggregator",
        phase: str = "Phase 21: FX + Liquidity Drivers and Six/Seven-Driver Economic Capital",
        precomputed: Optional[Dict[str, np.ndarray]] = None,
    ) -> SixDriverFXAggregationReport:
        cfg = config or FiveDriverAggregationConfig()
        if cfg.capital_horizon_months >= self.product.term_months:
            raise ValueError("capital_horizon_months must be less than product term")

        t0 = time.monotonic()
        run_id = "fx-6d-riskagg-" + uuid.uuid4().hex[:8]

        if precomputed is not None:
            # Staged execution: loss vectors precomputed slice-by-slice via
            # component_liabilities_sliced (bit-identical CRN protocol).
            rate_l = np.asarray(precomputed["rate"], dtype=float)
            equity_l = np.asarray(precomputed["equity"], dtype=float)
            credit_l = np.asarray(precomputed["credit"], dtype=float)
            lapse_l = np.asarray(precomputed["lapse"], dtype=float)
            mortality_l = np.asarray(precomputed["mortality"], dtype=float)
            full_l5 = np.asarray(precomputed["full5"], dtype=float)
            fx_l = np.asarray(precomputed["fx"], dtype=float)
            if len(rate_l) != cfg.n_outer:
                raise ValueError("precomputed vectors must match cfg.n_outer")
        else:
            outer6 = self._outer_states_6d(
                cfg.n_outer, cfg.capital_horizon_months, cfg.outer_measure, cfg.seed
            )
            outer5 = outer6[:, :5]
            x_h = outer6[:, 5]

            (rate_l, equity_l, credit_l, lapse_l, mortality_l,
             full_l5) = self._component_liabilities(outer5, cfg)
            fx_l = self.fx_exposure.liability_impact(x_h)
        full_l6 = full_l5 + fx_l
        self.last_loss_vectors_6d = {
            "rate": rate_l, "equity": equity_l, "credit": credit_l,
            "lapse": lapse_l, "mortality": mortality_l, "fx": fx_l,
            "full": full_l6,
        }

        conf = cfg.confidence_level
        hm = cfg.capital_horizon_months
        caps = {
            "rate": capital_metrics_from_liabilities(rate_l, conf, hm),
            "equity": capital_metrics_from_liabilities(equity_l, conf, hm),
            "credit": capital_metrics_from_liabilities(credit_l, conf, hm),
            "lapse": capital_metrics_from_liabilities(lapse_l, conf, hm),
            "mortality": capital_metrics_from_liabilities(mortality_l, conf, hm),
            "fx": capital_metrics_from_liabilities(fx_l, conf, hm),
        }
        full_cap = capital_metrics_from_liabilities(full_l6, conf, hm)
        crn_sum_cap = capital_metrics_from_liabilities(
            rate_l + equity_l + credit_l + lapse_l + mortality_l + fx_l, conf, hm
        )

        scr = {k: float(v.scr_proxy) for k, v in caps.items()}
        scr_vec = np.array([scr[k] for k in
                            ("rate", "equity", "credit", "lapse", "mortality", "fx")],
                           dtype=float)
        standalone_sum = float(scr_vec.sum())

        C = self.correlation6.matrix(self.gbm_params.rate_equity_correlation)
        C_t = tuple(tuple(float(v) for v in row) for row in C)
        corr_report = CorrelationMatrixValidator().validate_matrix(C_t, repair=False)
        var_covar_scr = float(np.sqrt(max(0.0, float(scr_vec @ C @ scr_vec))))

        nested_scr = float(full_cap.scr_proxy)
        denom = abs(nested_scr) if abs(nested_scr) > 1e-9 else 1.0
        rel_err = abs(var_covar_scr - nested_scr) / denom
        understatement_pct = (nested_scr - var_covar_scr) / denom
        interaction_residual_rel = float(crn_sum_cap.scr_proxy - nested_scr) / denom

        copula_cfg = CopulaAggregationConfig(
            n_sim=cfg.n_sim_copula, seed=cfg.seed + 11,
            confidence_level=conf, capital_horizon_months=hm,
        )
        copula = CopulaRiskAggregator(
            loss_vectors=[rate_l, equity_l, credit_l, lapse_l, mortality_l, fx_l],
            driver_names=["rate", "equity", "credit", "lapse", "mortality", "fx"],
            nested_scr=nested_scr,
            var_covar_scr=var_covar_scr,
        ).run(config=copula_cfg)

        notes = (
            "SIXTH DRIVER = lognormal FX spot (P-measure real-world drift outer; "
            "CIP drift r_d - r_f under Q), vol={:.3f}, X0={:.3f}; educational "
            "placeholder parameters, NOT calibrated to credentialled data.".format(
                self.fx_params.fx_vol, self.fx_params.initial_spot_rate),
            "Inner Q-nest FX conditioning is ANALYTIC and CIP-EXACT: the deflated "
            "translated foreign money-market account is a Q-martingale (Phase 20 "
            "MART-FX-CIP), so the conditional PV of the foreign asset leg given X_H "
            "is its time-H translated value; fx_l = notional * (1 - X_H/X0).",
            "First five drivers and their CRN component liabilities are reused "
            "verbatim from the Phase 20 G2++ five-driver engine; the 6x6 governed "
            "correlation embeds the 5x5 block unchanged (ASOP 25 §3.3).",
            "Var-covar (6x6 ESG) understates nested by {:.1f}%; copula ({}) "
            "reconciles within {:.1f}% (MR-010/MR-012 refresh under six drivers).".format(
                100.0 * understatement_pct, copula.selected_copula,
                100.0 * copula.selected.scr_rel_error_vs_nested),
            "FX standalone SCR {:.1f} vs rate {:.1f}, equity {:.1f}; the additive "
            "FX leg leaves the five-driver interaction residual unchanged in kind "
            "(residual rel {:.1f}%).".format(
                scr["fx"], scr["rate"], scr["equity"],
                100.0 * interaction_residual_rel),
        )

        copula_ok = copula.selected.scr_rel_error_vs_nested <= 0.25
        verdict = "PASS" if (corr_report.passed and copula_ok and nested_scr > 0.0) else "REVIEW"

        digest = hashlib.sha256(
            np.round(
                np.concatenate([
                    full_l6, rate_l, equity_l, credit_l, lapse_l, mortality_l, fx_l,
                    np.array([var_covar_scr, nested_scr,
                              copula.selected.aggregated_capital.scr_proxy], dtype=float),
                    C.ravel(),
                ]),
                9,
            ).tobytes()
        ).hexdigest()

        duration = time.monotonic() - t0
        if governance_store is not None:
            try:
                from par_model_v2.governance.audit_trail import AuditEntry

                entry = AuditEntry.model_run(
                    actor=actor, phase=phase, run_id=run_id,
                    scenario_count=cfg.n_outer * cfg.n_inner * 6,
                    duration_seconds=round(duration, 4),
                    outcome=verdict,
                    files_changed=[
                        "par_model_v2/projection/multi_driver_capital_6d_fx.py"
                    ],
                    test_summary=(
                        "6D FX aggregation; fx={:.1f}; var-cov={:.1f} (rel {:.1%}); "
                        "copula({})={:.1f} (rel {:.1%}); nested={:.1f}".format(
                            scr["fx"], var_covar_scr, rel_err,
                            copula.selected_copula,
                            copula.selected.aggregated_capital.scr_proxy,
                            copula.selected.scr_rel_error_vs_nested, nested_scr,
                        )
                    ),
                )
                governance_store.audit_trail.append(entry)
            except Exception:  # pragma: no cover - governance optional
                pass

        return SixDriverFXAggregationReport(
            config=cfg.to_dict(),
            drivers=("short_rate_g2pp_2f", "equity_guarantee", "credit_spread",
                     "lapse_behaviour", "mortality_trend", "fx_translation"),
            standalone_scr=scr,
            standalone_scr_sum=standalone_sum,
            esg_correlation_matrix=C_t,
            correlation_matrix_passed=bool(corr_report.passed),
            var_covar_scr=var_covar_scr,
            nested_scr=nested_scr,
            var_covar_vs_nested_rel_error=rel_err,
            esg_understatement_pct=understatement_pct,
            copula_selected=str(copula.selected_copula),
            copula_scr=float(copula.selected.aggregated_capital.scr_proxy),
            copula_vs_nested_rel_error=float(copula.selected.scr_rel_error_vs_nested),
            interaction_residual_rel=interaction_residual_rel,
            fx_exposure_notional=float(self.fx_exposure.exposure_notional),
            fx_initial_spot=float(self.fx_params.initial_spot_rate),
            run_id=run_id,
            duration_seconds=duration,
            verdict=verdict,
            reproducibility_digest=digest,
            notes=notes,
        )


# ---------------------------------------------------------------------------
# G-FX plausibility gate
# ---------------------------------------------------------------------------

def evaluate_g_fx_gate(
    fx_params: Optional[FXParams] = None,
    correlation6: Optional[SixDriverFXCorrelation] = None,
    fx_exposure: Optional[FXExposureSpec] = None,
    n_scenarios: int = 4000,
    test_month: int = 12,
    domestic_rate: float = 0.03,
    foreign_rate: float = 0.01,
    seed: int = 20260607,
    k_sigma: float = 4.0,
) -> Dict[str, object]:
    """G-FX plausibility gate for the sixth (FX / currency) capital driver.

    Criteria (all must pass):

    * **FX-01 positive spots** — lognormal spot paths are strictly positive.
    * **FX-02 lognormal moments** — terminal log-spot mean and volatility match
      the exact lognormal theory within ``k_sigma`` standard errors.
    * **FX-03 P/Q drift separation** — the P (real-world) and Q (CIP) drifts
      produce measurably different terminal means when configured to differ,
      and the process refuses unsupported measures (G-05 / MR-004 wiring).
    * **FX-04 Q-measure CIP martingale** — Phase 20 ``MART-FX-CIP`` evidence:
      ``E^Q[D_d(t) X(t) exp(r_f t)] = X(0)`` within ``k_sigma`` standard errors.
    * **FX-05 correlation wiring** — realised rate-FX shock correlation under
      the 6x6 governed Cholesky matches the target within sampling tolerance.
    * **FX-06 exposure mapping** — the FX liability impact is zero at the
      initial spot, positive under depreciation, monotone decreasing in spot.

    Returns a JSON-serialisable dict with per-criterion evidence.
    """
    p = fx_params if fx_params is not None else DEFAULT_FX_PARAMS
    corr = correlation6 if correlation6 is not None else SixDriverFXCorrelation()
    expo = fx_exposure if fx_exposure is not None else FXExposureSpec(
        initial_spot_rate=p.initial_spot_rate
    )
    criteria: List[Dict[str, object]] = []
    t = test_month / 12.0
    dt = 1.0 / 12.0

    proc = FXSpotProcess(p)
    rng = np.random.default_rng(seed)
    shocks = _antithetic_normals(rng, n_scenarios, test_month)
    spot, _ret = proc._simulate_array(n_scenarios, test_month, Measure.P, shocks)

    # FX-01 positive spots
    min_spot = float(spot.min())
    criteria.append({
        "criterion": "FX-01-positive-spots",
        "passed": bool(min_spot > 0.0),
        "evidence": {"min_spot": min_spot},
    })

    # FX-02 lognormal terminal moments (exact discrete lognormal theory)
    log_term = np.log(spot[:, test_month] / p.initial_spot_rate)
    mu_theory = (p.real_world_drift - 0.5 * p.fx_vol ** 2) * t
    sd_theory = p.fx_vol * math.sqrt(t)
    se_mean = sd_theory / math.sqrt(n_scenarios)
    z_mean = abs(float(log_term.mean()) - mu_theory) / se_mean
    sd_emp = float(log_term.std(ddof=1))
    se_sd = sd_theory / math.sqrt(2.0 * (n_scenarios - 1))
    z_sd = abs(sd_emp - sd_theory) / se_sd
    # Antithetic pairing halves the effective independent count for the SD
    # estimator; widen tolerance accordingly (documented, conservative).
    criteria.append({
        "criterion": "FX-02-lognormal-moments",
        "passed": bool(z_mean <= k_sigma and z_sd <= 2.0 * k_sigma),
        "evidence": {
            "log_mean_emp": float(log_term.mean()), "log_mean_theory": mu_theory,
            "z_mean": float(z_mean), "log_sd_emp": sd_emp,
            "log_sd_theory": sd_theory, "z_sd": float(z_sd),
        },
    })

    # FX-03 P/Q drift separation + measure enforcement
    p_q = FXParams(
        fx_vol=p.fx_vol,
        real_world_drift=0.05,
        domestic_foreign_rate_spread=domestic_rate - foreign_rate,
        rate_fx_correlation=p.rate_fx_correlation,
        initial_spot_rate=p.initial_spot_rate,
    )
    proc_pq = FXSpotProcess(p_q)
    rng_pq = np.random.default_rng(seed + 1)
    sh = _antithetic_normals(rng_pq, n_scenarios, test_month)
    spot_p, _ = proc_pq._simulate_array(n_scenarios, test_month, Measure.P, sh)
    spot_q, _ = proc_pq._simulate_array(n_scenarios, test_month, Measure.Q, sh)
    mean_p = float(spot_p[:, test_month].mean())
    mean_q = float(spot_q[:, test_month].mean())
    expected_ratio = math.exp((0.05 - (domestic_rate - foreign_rate)) * t)
    ratio = mean_p / mean_q
    criteria.append({
        "criterion": "FX-03-pq-measure-separation",
        "passed": bool(abs(ratio - expected_ratio) < 0.02 * expected_ratio),
        "evidence": {
            "terminal_mean_P": mean_p, "terminal_mean_Q": mean_q,
            "ratio": ratio, "expected_ratio": expected_ratio,
        },
    })

    # FX-04 Q-measure CIP martingale (Phase 20 MART-FX-CIP reuse)
    mart = martingale_fx(
        domestic_rate, foreign_rate, test_month, p.fx_vol,
        p.initial_spot_rate, n_scenarios, seed + 2, k_sigma,
    )[0]
    criteria.append({
        "criterion": "FX-04-q-cip-martingale",
        "passed": bool(mart.passed),
        "evidence": {
            "check_id": mart.check_id, "estimate": mart.estimate,
            "target": mart.target, "n_std_errors": mart.n_std_errors,
            "rel_error": mart.rel_error, "tolerance_sigma": mart.tolerance_sigma,
        },
    })

    # FX-05 correlation wiring (rate-FX under the 6x6 governed Cholesky)
    rng_c = np.random.default_rng(seed + 3)
    chol = corr.cholesky(-0.25)
    sh6 = _correlated_shocks_6(rng_c, 2000, 60, chol)
    z_rate_flat = sh6[0].ravel()
    z_fx_flat = sh6[5].ravel()
    realised = float(np.corrcoef(z_rate_flat, z_fx_flat)[0, 1])
    target = float(corr.matrix(-0.25)[5, 0])
    tol = max(4.0 / math.sqrt(z_fx_flat.size), 0.02)
    criteria.append({
        "criterion": "FX-05-correlation-wiring",
        "passed": bool(abs(realised - target) <= tol),
        "evidence": {"realised_rate_fx_corr": realised, "target": target, "tolerance": tol},
    })

    # FX-06 exposure mapping sanity
    grid = np.linspace(0.5, 1.5, 11) * expo.initial_spot_rate
    impact = expo.liability_impact(grid)
    at_par = float(expo.liability_impact(np.array([expo.initial_spot_rate]))[0])
    monotone = bool(np.all(np.diff(impact) < 0.0)) if expo.exposure_notional > 0 else True
    deprec_loss = float(expo.liability_impact(np.array([0.8 * expo.initial_spot_rate]))[0])
    criteria.append({
        "criterion": "FX-06-exposure-mapping",
        "passed": bool(abs(at_par) < 1e-9 and monotone and deprec_loss > 0.0),
        "evidence": {
            "impact_at_initial_spot": at_par,
            "monotone_decreasing_in_spot": monotone,
            "loss_at_20pct_depreciation": deprec_loss,
        },
    })

    passed = all(c["passed"] for c in criteria)
    return {
        "gate": "G-FX",
        "passed": passed,
        "n_criteria": len(criteria),
        "n_passed": sum(1 for c in criteria if c["passed"]),
        "criteria": criteria,
        "params": {
            "fx_vol": p.fx_vol,
            "real_world_drift": p.real_world_drift,
            "domestic_foreign_rate_spread": p.domestic_foreign_rate_spread,
            "initial_spot_rate": p.initial_spot_rate,
            "n_scenarios": n_scenarios,
            "test_month": test_month,
            "k_sigma": k_sigma,
            "seed": seed,
        },
        "standards": [
            "SOA ASOP 56 §3.1.3/§3.4/§3.5",
            "IA TAS M §3.6",
            "Solvency II Delegated Reg. Art. 188/234",
        ],
    }


# ---------------------------------------------------------------------------
# Use restrictions / limitations (IA TAS M §3.5 disclosure)
# ---------------------------------------------------------------------------

def six_driver_fx_use_restrictions() -> Dict[str, object]:
    """Documented limitations and unsuitable uses for the six-driver FX build."""
    return {
        "model": "SixDriverFXRiskAggregator",
        "status": "EDUCATIONAL",
        "restrictions": [
            "FX parameters are educational placeholders (fx_vol, drift, couplings); "
            "NOT calibrated to credentialled market data.",
            "The FX exposure is a single translated foreign asset leg with an "
            "analytic CIP-exact conditional valuation; real books carry "
            "term-structured, optioned and partially hedged FX exposures.",
            "The lognormal FX process has no jumps, stochastic volatility or peg/"
            "de-peg regime dynamics; a pegged currency (e.g. HKD) is materially "
            "regime-driven, so the tail is stylised, not historical.",
            "The first five drivers' inner Q nest remains the governed HW1F nest "
            "conditioned at the realised G2++ r_H (Phase 20 residual).",
            "Six-driver LSMC proxy-surface validation is Phase 21 Task 2; until it "
            "reports, the nested benchmark is the only validated 6D ground truth.",
            "Not for production capital, pricing, or regulatory reporting.",
        ],
        "standards": ["SOA ASOP 56 §3.4", "IA TAS M §3.5", "SOA ASOP 41 §3.4.4"],
    }


def six_driver_fx_use_restrictions_json() -> str:
    return json.dumps(six_driver_fx_use_restrictions(), indent=2, sort_keys=True)


__all__ = [
    "DEFAULT_FX_PARAMS",
    "FXExposureSpec",
    "SixDriverFXCorrelation",
    "SixDriverFXAggregationReport",
    "SixDriverFXRiskAggregator",
    "evaluate_g_fx_gate",
    "six_driver_fx_use_restrictions",
    "six_driver_fx_use_restrictions_json",
]
