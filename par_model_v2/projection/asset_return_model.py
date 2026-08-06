"""
Asset return model — ESG path → per-asset-class total returns (Phase A).

This module implements the *pure, vectorised* return-mapping component of the
asset–ESG coupling design (``docs/DESIGN_ASSET_ESG_COUPLING.md`` §4.1–§4.2).
It maps economic-scenario-generator (ESG) paths — short rate, equity total
return, credit spread — to the monthly total return of each asset class, and
combines those into a portfolio earned rate given a strategic-asset-allocation
(SAA) weight set.

Scope of Phase A
----------------
* No engine state and no side effects: every method is a pure function of its
  inputs.  Nothing in the projection / ALM engine consumes this module yet, so
  importing or testing it cannot change any existing model output.
* Vectorised by construction: all inputs accept either a single path of shape
  ``(T,)`` or a batch of scenarios of shape ``(N, T)``.  Operations run over the
  last axis, so a batched call equals stacking the single-path results.

Return definitions (monthly, total return)
-------------------------------------------
For month ``m`` with annualised short rate ``r[m]`` and credit spread ``s[m]``:

* **Cash**   : ``r[m] / 12``
* **Govt**   : ``r[m]/12  −  D · Δr[m]``                     (carry − rate price move)
* **Credit** : ``r[m]/12 − D·Δr[m]  +  base_spread/12 − D_s·Δs[m] − default_loss/12``
* **Equity** : the supplied monthly equity total-return path, passed through.

where ``D`` is the class effective duration, ``D_s`` the spread duration, and
``Δx[m] = x[m] − x[m−1]`` is the within-month change.  The first element uses
``Δx[0] = x[0] − x0`` with ``x0`` an optional reference level (default ``x[0]``,
i.e. ``Δx[0] = 0``), which makes a flat scenario produce constant returns.

Governance / limitations
-------------------------
* The repricing parameters (effective duration, spread duration, base spread,
  expected default loss) are governed assumptions.  Until calibrated they are
  placeholders in the MR-001 family — see ``docs/DEEP_DIVE_ESG_CALIBRATION.md``.
* Measure-agnostic: returns are computed from whatever scenario is supplied.
  The caller is responsible for P/Q measure consistency (e.g. discounting Q
  paths with the same curve used here), per the deflator gate G-AC2 in the
  design spec.
* Duration is a first-order (linear) repricing proxy.  Full-curve repricing via
  the HW1F ``P(t,T)`` closed form is a Phase-D upgrade (design §4.3 R-notes).

Standards: SOA ASOP 56 §3.4 (methodology documentation); IA TAS M §3.5
(material assumption ownership).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Optional

import numpy as np

from par_model_v2.projection.dynamic_alm import ASSET_CLASSES

__all__ = [
    "AssetClassParams",
    "AssetReturnModel",
    "portfolio_earned_return",
]

#: Asset classes whose monthly return is rate-sensitive (need a duration).
_RATE_SENSITIVE = ("Govt", "Credit")

#: Weight tolerance for SAA weight-sum validation.
_WEIGHT_SUM_TOL = 1e-8

_MONTHS_PER_YEAR = 12.0


def _require_finite(name: str, value: float) -> None:
    if not np.isfinite(value):
        raise ValueError(f"{name} must be finite; got {value!r}")


def _period_change(path: np.ndarray, initial: Optional[float]) -> np.ndarray:
    """Within-period change ``Δx[m] = x[m] − x[m−1]`` along the last axis.

    ``initial`` sets the reference for the first element: ``Δx[0] = x[0] − x0``.
    When ``initial is None`` the first element's own value is used so that
    ``Δx[0] = 0`` (a flat path then has zero change everywhere).

    ``initial`` may be a scalar (applied to every scenario) or a per-scenario
    array whose shape matches the leading dimensions of ``path``.
    """
    path = np.asarray(path, dtype=float)
    head = path[..., :1]
    if initial is None:
        prepend = head
    else:
        init = np.asarray(initial, dtype=float)
        if init.ndim == 0:
            prepend = np.broadcast_to(init, head.shape)
        else:
            # Per-scenario reference; reshape to (..., 1) to align with head.
            prepend = init.reshape(head.shape)
    return np.diff(path, axis=-1, prepend=prepend)


@dataclass(frozen=True)
class AssetClassParams:
    """Repricing parameters for one asset class (a governed assumption set).

    Parameters
    ----------
    asset_class:
        One of :data:`par_model_v2.projection.dynamic_alm.ASSET_CLASSES`
        (``'Govt' | 'Credit' | 'Equity' | 'Cash'``).
    effective_duration:
        Rate sensitivity (years).  Used for the ``−D·Δr`` price term on
        rate-sensitive classes.  Ignored for Cash and Equity.
    spread_duration:
        Credit-spread sensitivity (years).  Used for the ``−D_s·Δs`` term on
        Credit.
    base_spread:
        Annualised spread carry over the risk-free rate (Credit).
    annual_default_loss:
        Annualised expected default loss (PD × LGD) deducted from Credit return.
    dividend_yield:
        Annualised dividend yield (Equity).  Informational in Phase A — equity
        total return is supplied directly; retained for downstream income/price
        splitting in later phases.
    """

    asset_class: str
    effective_duration: float = 0.0
    spread_duration: float = 0.0
    base_spread: float = 0.0
    annual_default_loss: float = 0.0
    dividend_yield: float = 0.0

    def __post_init__(self) -> None:
        if self.asset_class not in ASSET_CLASSES:
            raise ValueError(
                f"asset_class must be one of {ASSET_CLASSES}; got {self.asset_class!r}"
            )
        for name in (
            "effective_duration",
            "spread_duration",
            "base_spread",
            "annual_default_loss",
            "dividend_yield",
        ):
            _require_finite(name, getattr(self, name))
        if self.effective_duration < 0.0:
            raise ValueError("effective_duration must be non-negative")
        if self.spread_duration < 0.0:
            raise ValueError("spread_duration must be non-negative")
        if self.annual_default_loss < 0.0:
            raise ValueError("annual_default_loss must be non-negative")


class AssetReturnModel:
    """Map ESG paths to per-asset-class monthly total returns.

    Parameters
    ----------
    params:
        Mapping ``asset_class -> AssetClassParams``.  Keys must be a subset of
        :data:`ASSET_CLASSES`, and each value's ``asset_class`` must match its
        key.  Only the classes present here are returned by
        :meth:`monthly_total_returns`.

    Examples
    --------
    >>> import numpy as np
    >>> model = AssetReturnModel({
    ...     "Cash": AssetClassParams("Cash"),
    ...     "Govt": AssetClassParams("Govt", effective_duration=7.0),
    ... })
    >>> r = model.monthly_total_returns(short_rate=np.full(3, 0.03))
    >>> bool(np.allclose(r["Cash"], 0.03 / 12))
    True
    """

    def __init__(self, params: Mapping[str, AssetClassParams]) -> None:
        if not params:
            raise ValueError("params must contain at least one asset class")
        for key, value in params.items():
            if key not in ASSET_CLASSES:
                raise ValueError(
                    f"unknown asset class {key!r}; expected one of {ASSET_CLASSES}"
                )
            if not isinstance(value, AssetClassParams):
                raise TypeError(
                    f"params[{key!r}] must be AssetClassParams, got {type(value).__name__}"
                )
            if value.asset_class != key:
                raise ValueError(
                    f"params[{key!r}].asset_class is {value.asset_class!r}; "
                    "key and asset_class must match"
                )
        # Preserve canonical ordering for stable, reproducible output.
        self._params: Dict[str, AssetClassParams] = {
            cls: params[cls] for cls in ASSET_CLASSES if cls in params
        }

    @property
    def asset_classes(self) -> tuple:
        """Asset classes handled by this model, in canonical order."""
        return tuple(self._params.keys())

    def monthly_total_returns(
        self,
        short_rate: np.ndarray,
        equity_return: Optional[np.ndarray] = None,
        credit_spread: Optional[np.ndarray] = None,
        initial_short_rate: Optional[float] = None,
        initial_credit_spread: Optional[float] = None,
    ) -> Dict[str, np.ndarray]:
        """Monthly total return per asset class.

        Parameters
        ----------
        short_rate:
            Annualised short-rate path, shape ``(T,)`` or ``(N, T)``.  Required.
        equity_return:
            Monthly equity total-return path, same shape as ``short_rate``.
            Required iff ``'Equity'`` is configured.
        credit_spread:
            Annualised credit-spread path, same shape as ``short_rate``.
            Required iff ``'Credit'`` is configured.
        initial_short_rate, initial_credit_spread:
            Optional reference levels for the first-period change (see
            :func:`_period_change`).  Scalars or per-scenario arrays.

        Returns
        -------
        dict
            ``asset_class -> ndarray`` of monthly total returns, each with the
            same shape as ``short_rate``, in canonical class order.
        """
        sr = np.asarray(short_rate, dtype=float)
        if sr.ndim not in (1, 2):
            raise ValueError(
                f"short_rate must be 1-D (T,) or 2-D (N, T); got shape {sr.shape}"
            )
        if sr.shape[-1] == 0:
            raise ValueError("short_rate must have at least one time step")

        needs_equity = "Equity" in self._params
        needs_credit = "Credit" in self._params
        if needs_equity and equity_return is None:
            raise ValueError("equity_return is required when 'Equity' is configured")
        if needs_credit and credit_spread is None:
            raise ValueError("credit_spread is required when 'Credit' is configured")

        eq = self._validate_companion("equity_return", equity_return, sr)
        cs = self._validate_companion("credit_spread", credit_spread, sr)

        d_short = _period_change(sr, initial_short_rate)
        carry = sr / _MONTHS_PER_YEAR

        out: Dict[str, np.ndarray] = {}
        for cls, p in self._params.items():
            if cls == "Cash":
                out[cls] = carry.copy()
            elif cls == "Govt":
                out[cls] = carry - p.effective_duration * d_short
            elif cls == "Credit":
                d_spread = _period_change(cs, initial_credit_spread)
                out[cls] = (
                    carry
                    - p.effective_duration * d_short
                    + p.base_spread / _MONTHS_PER_YEAR
                    - p.spread_duration * d_spread
                    - p.annual_default_loss / _MONTHS_PER_YEAR
                )
            elif cls == "Equity":
                out[cls] = eq.copy()
        return out

    @staticmethod
    def _validate_companion(
        name: str, value: Optional[np.ndarray], reference: np.ndarray
    ) -> Optional[np.ndarray]:
        if value is None:
            return None
        arr = np.asarray(value, dtype=float)
        if arr.shape != reference.shape:
            raise ValueError(
                f"{name} shape {arr.shape} must match short_rate shape {reference.shape}"
            )
        return arr


def portfolio_earned_return(
    returns_by_class: Mapping[str, np.ndarray],
    weights: Mapping[str, float],
) -> np.ndarray:
    """Weighted portfolio earned return ``r_earned = Σ_c w_c · r_c``.

    Parameters
    ----------
    returns_by_class:
        Output of :meth:`AssetReturnModel.monthly_total_returns`.
    weights:
        SAA weights ``asset_class -> weight``.  Keys must be a subset of
        ``returns_by_class``; weights must sum to 1 (within tolerance).

    Returns
    -------
    ndarray
        Portfolio monthly earned return, same shape as the class arrays.
    """
    if not weights:
        raise ValueError("weights must be non-empty")
    missing = set(weights) - set(returns_by_class)
    if missing:
        raise ValueError(
            f"weights reference classes with no returns: {sorted(missing)}"
        )
    total = float(sum(weights.values()))
    if abs(total - 1.0) > _WEIGHT_SUM_TOL:
        raise ValueError(f"weights must sum to 1.0 (within tol); got {total}")

    earned = None
    for cls, w in weights.items():
        _require_finite(f"weights[{cls!r}]", w)
        contrib = float(w) * np.asarray(returns_by_class[cls], dtype=float)
        earned = contrib if earned is None else earned + contrib
    return earned
