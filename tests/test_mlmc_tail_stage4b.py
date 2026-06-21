"""Stage-4b (W67) regression guards for the WIRED, mode-selectable tail
variance-reduction diagnostics (``tail_capital_diagnostics`` /
``resolve_tail_outer_sampler``).

Stage-4b packages the W66 stage-4 tail tools (stratified outer sampling + ES
bootstrap bias correction) as a single, mode-selectable entry point on the
opt-in tail path -- the tail analogue of the W60 stage-3
``engine_mean_liability_diagnostics`` mean wiring. The contract these guards
lock:

* DEFAULT is OFF (``variance_reduction="none"``, ``es_bias_correction=False``)
  and is BIT-IDENTICAL both to a plain-outer ``nested_single_level_tail`` call
  and to a FROZEN reference snapshot captured at W67 (the frozen-snapshot
  equivalence gate);
* the MODE resolver returns the right sampler and rejects unknown modes;
* stratified mode keeps the SAME inner-path cost yet differs from plain, and
  REDUCES the replicate variance of the 99.5% tail VaR/ES/SCR (generous,
  seed-stable margin);
* the optional ES bias correction obeys the bootstrap identity and is
  deterministic;
* the diagnostics dict is JSON-serialisable.

Everything here is opt-in; nothing touches the governed SCR/VaR/ES headline
``39975.654628199336`` (a fixed single-level figure until owner-signed-off
stage 5).
"""
import json

import numpy as np
import pytest

from par_model_v2.projection.mlmc_inner_estimator import (
    TAIL_VR_MODES,
    resolve_tail_outer_sampler,
    tail_capital_diagnostics,
    nested_single_level_tail,
    stratified_normal_outer_sampler,
    DEFAULT_TAIL_CONFIDENCE,
)

# Frozen reference config + snapshot, captured at W67 from the plain-outer
# fixed-256 estimator. The DEFAULT ("none") mode must reproduce these
# bit-for-bit forever (proving future edits never perturb the default path).
CFG = dict(mu_x=0.02, sigma_x=0.01, sigma_inner=0.05,
           n_outer=4000, n_inner=256, seed=20260619)
FROZEN = dict(
    var=0.04820076634696653,
    es=0.051878781816970275,
    scr=0.027892778037151456,
    mean_liability=0.020307988309815075,
    var_empirical=0.048203134971483055,
    es_empirical=0.051878781816970275,
    inner_path_cost=1024000,
)
ALPHA = DEFAULT_TAIL_CONFIDENCE
SIGMA_INNER = CFG["sigma_inner"]


def _inner(x, m, rng):
    return rng.normal(float(x), SIGMA_INNER, size=int(m))


def _plain(rng, n):
    return rng.normal(CFG["mu_x"], CFG["sigma_x"], size=int(n))


# --- MODE resolver ---------------------------------------------------------
def test_modes_constant():
    assert TAIL_VR_MODES == ("none", "stratified", "stratified_antithetic")


def test_resolver_returns_callable_samplers():
    for mode in TAIL_VR_MODES:
        s = resolve_tail_outer_sampler(mode, 0.02, 0.01)
        z = np.asarray(s(np.random.default_rng(1), 64), dtype=float)
        assert z.shape == (64,)


def test_resolver_rejects_unknown_mode():
    with pytest.raises(ValueError):
        resolve_tail_outer_sampler("bogus", 0.0, 1.0)


# --- frozen-snapshot equivalence (the stage-4b gate) -----------------------
def test_default_mode_matches_frozen_snapshot_bit_for_bit():
    d = tail_capital_diagnostics(**CFG)
    assert d["variance_reduction"] == "none"
    assert d["es_bias_correction"] is False
    for k, v in FROZEN.items():
        assert d[k] == v, (k, d[k], v)


def test_default_mode_bit_identical_to_plain_nested_single_level():
    d = tail_capital_diagnostics(**CFG)
    ref = nested_single_level_tail(
        _plain, _inner, alpha=ALPHA, n_outer=CFG["n_outer"],
        n_inner=CFG["n_inner"], rng=np.random.default_rng(CFG["seed"]))
    assert d["var"] == ref.var
    assert d["es"] == ref.es
    assert d["scr"] == ref.scr
    assert d["mean_liability"] == ref.mean_liability


def test_default_mode_deterministic():
    a = tail_capital_diagnostics(**CFG)
    b = tail_capital_diagnostics(**CFG)
    assert a == b


# --- stratified MODE: matched cost, lower variance -------------------------
def test_stratified_mode_same_cost_differs():
    base = tail_capital_diagnostics(**CFG)
    strat = tail_capital_diagnostics(variance_reduction="stratified", **CFG)
    assert strat["inner_path_cost"] == base["inner_path_cost"]
    assert strat["var"] != base["var"]


def test_stratified_mode_reduces_tail_variance():
    R, n_out = 24, 1500
    pv = np.empty(R)
    sv = np.empty(R)
    for r in range(R):
        cfg = dict(CFG, n_outer=n_out, seed=20260619 + r)
        pv[r] = tail_capital_diagnostics(variance_reduction="none", **cfg)["scr"]
        sv[r] = tail_capital_diagnostics(variance_reduction="stratified", **cfg)["scr"]
    # Stratification is free (matched cost), so a >1x variance-reduction factor
    # is a matched-cost speedup. Generous seed-stable margin (>=1.5x).
    factor = float(pv.var(ddof=1) / sv.var(ddof=1))
    assert factor >= 1.5


# --- optional ES bias correction -------------------------------------------
def test_es_bias_correction_optional_and_identity():
    d = tail_capital_diagnostics(es_bias_correction=True, es_bias_n_boot=120, **CFG)
    assert d["es_bias_correction"] is True
    assert "es_bias_corrected" in d
    # bootstrap identity: es_bc == 2*es_raw - boot_mean
    assert abs(d["es_bias_corrected"] - (2 * d["es"] - d["es_bias_boot_mean"])) < 1e-12


def test_es_bias_correction_deterministic():
    a = tail_capital_diagnostics(es_bias_correction=True, es_bias_n_boot=120, **CFG)
    b = tail_capital_diagnostics(es_bias_correction=True, es_bias_n_boot=120, **CFG)
    assert a["es_bias_corrected"] == b["es_bias_corrected"]


def test_es_correction_does_not_change_core_figures():
    base = tail_capital_diagnostics(**CFG)
    corr = tail_capital_diagnostics(es_bias_correction=True, es_bias_n_boot=80, **CFG)
    # The correction is additive: the canonical var/es/scr stay bit-identical.
    assert (corr["var"], corr["es"], corr["scr"]) == (base["var"], base["es"], base["scr"])


# --- serialisation ---------------------------------------------------------
def test_diagnostics_json_serialisable():
    for mode in TAIL_VR_MODES:
        d = tail_capital_diagnostics(variance_reduction=mode,
                                     es_bias_correction=(mode == "none"),
                                     es_bias_n_boot=60, **CFG)
        json.loads(json.dumps(d))
