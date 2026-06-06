"""
G2++ two-factor additive Gaussian interest-rate model (Phase 20, Task 1).
=========================================================================

Ground-truth simulator and closed-form / semi-analytic pricing for the
two-additive-factor Gaussian short-rate model (G2++), the multi-factor
uplift of the single-factor Hull-White (HW1F) rates driver used in the
capital model.  This module provides:

  * ``G2ppParams``                -- the parameter container (a, b, sigma,
                                     eta, rho) plus the initial discount curve.
  * ``zcb_price``                 -- EXACT closed-form zero-coupon bond price
                                     P(t,T | x(t), y(t)).
  * ``swaption_price``            -- Brigo & Mercurio (2006) eq. (4.31)
                                     semi-analytic European swaption price
                                     (1-D Gaussian integral; deterministic).
  * ``swaption_normal_vol``       -- implied Bachelier (normal) ATM vol of a
                                     payer swaption, the quantity the
                                     calibrator fits to the market surface.
  * ``G2ppSimulator``             -- EXACT-increment Monte-Carlo simulator of
                                     (x, y, r, bank-account) used as the
                                     market-consistency ground truth.

Model (under the risk-neutral measure Q), Brigo & Mercurio Ch. 4:

    r(t) = x(t) + y(t) + phi(t)
    dx(t) = -a x(t) dt + sigma dW1(t),   x(0) = 0
    dy(t) = -b y(t) dt + eta   dW2(t),   y(0) = 0
    dW1(t) dW2(t) = rho dt

phi(t) is chosen so the model exactly reprices the initial discount curve
P^M(0,.) (so ``zcb_price`` reprices the curve at t=0 by construction).

Standards
---------
SOA ASOP 56 sec.3.1.3 -- stochastic process documentation (drivers, measure).
SOA ASOP 56 sec.3.4   -- calibration methodology (see ``g2pp_calibrator``).
Solvency II Del. Reg. (EU) 2015/35, Art. 22 -- market-consistent valuation.
IA TAS M sec.3.5/3.6  -- assumption appropriateness and source->output traceability.

Reference
---------
D. Brigo & F. Mercurio (2006), "Interest Rate Models -- Theory and Practice",
2nd ed., Springer, Chapter 4 (sections 4.2.1, 4.2.4, 4.2.5).

PRODUCTION USE RESTRICTION
--------------------------
Parameters are calibrated to an EDUCATIONAL PROXY swaption surface.  Replace
the fixture surface with a credentialled live-market source and re-run the
full sign-off workflow before any regulatory submission.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import math
import numpy as np

SQRT_2PI = math.sqrt(2.0 * math.pi)


# --------------------------------------------------------------------------- #
# Standard normal helpers (vectorised, no scipy dependency).
# --------------------------------------------------------------------------- #
def _norm_cdf(x):
    """Vectorised standard-normal CDF via the error function."""
    return 0.5 * (1.0 + np.vectorize(math.erf)(np.asarray(x, dtype=float) / math.sqrt(2.0)))


def _norm_cdf_scalar(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


# --------------------------------------------------------------------------- #
# Initial discount curve.
# --------------------------------------------------------------------------- #
@dataclass
class DiscountCurve:
    """Initial market discount curve P^M(0, T).

    Stored as continuously-compounded zero rates R(T) on a tenor grid; the
    discount factor is P^M(0,T) = exp(-R(T) * T).  Off-grid tenors use
    linear interpolation in the zero rate (flat-extrapolated at the ends).
    The instantaneous forward f^M(0,t) = -d ln P^M(0,t)/dt is obtained by a
    central finite difference -- needed only for phi(t)/the simulator.
    """

    tenors: np.ndarray      # increasing maturities in years, > 0
    zero_rates: np.ndarray  # continuously-compounded annual rates (decimal)

    def __post_init__(self) -> None:
        self.tenors = np.asarray(self.tenors, dtype=float)
        self.zero_rates = np.asarray(self.zero_rates, dtype=float)
        if self.tenors.ndim != 1 or self.tenors.size < 2:
            raise ValueError("DiscountCurve needs >= 2 tenor points.")
        if np.any(np.diff(self.tenors) <= 0):
            raise ValueError("DiscountCurve tenors must be strictly increasing.")
        if self.tenors.shape != self.zero_rates.shape:
            raise ValueError("tenors and zero_rates must have the same shape.")

    @classmethod
    def flat(cls, rate: float, max_tenor: float = 50.0) -> "DiscountCurve":
        return cls(np.array([0.25, max_tenor]), np.array([rate, rate]))

    def zero_rate(self, t: float) -> float:
        t = max(float(t), 1e-8)
        return float(np.interp(t, self.tenors, self.zero_rates))

    def P(self, t: float) -> float:
        """Discount factor P^M(0,t)."""
        if t <= 0:
            return 1.0
        return math.exp(-self.zero_rate(t) * t)

    def forward(self, t: float, h: float = 1e-4) -> float:
        """Instantaneous forward rate f^M(0,t) = -d ln P^M(0,t)/dt."""
        t = max(float(t), h)
        lp_up = math.log(self.P(t + h))
        lp_dn = math.log(self.P(max(t - h, 1e-8)))
        return -(lp_up - lp_dn) / (2.0 * h)


# --------------------------------------------------------------------------- #
# Parameters.
# --------------------------------------------------------------------------- #
@dataclass
class G2ppParams:
    """G2++ parameters and the initial discount curve.

    a, b      : mean-reversion speeds of factors x, y  (a != b required).
    sigma, eta: instantaneous volatilities of x, y.
    rho       : instantaneous correlation of the two Brownian drivers, in (-1, 1).
    curve     : initial market discount curve P^M(0, .).
    """

    a: float
    b: float
    sigma: float
    eta: float
    rho: float
    curve: DiscountCurve

    def __post_init__(self) -> None:
        if self.a <= 0 or self.b <= 0:
            raise ValueError("Mean-reversion speeds a, b must be positive.")
        if abs(self.a - self.b) < 1e-8:
            raise ValueError("G2++ requires a != b (use HW1F if a == b).")
        if self.sigma <= 0 or self.eta <= 0:
            raise ValueError("Volatilities sigma, eta must be positive.")
        if not (-0.9999 < self.rho < 0.9999):
            raise ValueError("rho must be strictly inside (-1, 1).")


# --------------------------------------------------------------------------- #
# Core analytic building blocks.
# --------------------------------------------------------------------------- #
def _B(z: float, tau: float) -> float:
    """B(z, tau) = (1 - exp(-z tau)) / z."""
    return (1.0 - math.exp(-z * tau)) / z


def _V(p: G2ppParams, t: float, T: float) -> float:
    """V(t,T) = Var[ integral_t^T r(u) du ] under Q (Brigo & Mercurio 4.10)."""
    a, b, s, e, rho = p.a, p.b, p.sigma, p.eta, p.rho
    tau = T - t
    if tau <= 0:
        return 0.0
    term_a = (s * s / (a * a)) * (
        tau + (2.0 / a) * math.exp(-a * tau) - (1.0 / (2.0 * a)) * math.exp(-2.0 * a * tau) - 1.5 / a
    )
    term_b = (e * e / (b * b)) * (
        tau + (2.0 / b) * math.exp(-b * tau) - (1.0 / (2.0 * b)) * math.exp(-2.0 * b * tau) - 1.5 / b
    )
    term_ab = (2.0 * rho * s * e / (a * b)) * (
        tau
        + (math.exp(-a * tau) - 1.0) / a
        + (math.exp(-b * tau) - 1.0) / b
        - (math.exp(-(a + b) * tau) - 1.0) / (a + b)
    )
    return term_a + term_b + term_ab


def zcb_price(p: G2ppParams, t: float, T: float, x: float = 0.0, y: float = 0.0) -> float:
    """EXACT G2++ zero-coupon bond price P(t, T | x(t)=x, y(t)=y).

        P(t,T) = (P^M(0,T)/P^M(0,t))
                 * exp( 0.5[V(t,T) - V(0,T) + V(0,t)]
                        - B(a,T-t) x - B(b,T-t) y )

    By construction P(0,T)=P^M(0,T) at x=y=0 (reprices the initial curve).
    Brigo & Mercurio (2006) eq. (4.14).
    """
    if T < t:
        raise ValueError("Maturity T must be >= current time t.")
    if T == t:
        return 1.0
    tau = T - t
    A = 0.5 * (_V(p, t, T) - _V(p, 0.0, T) + _V(p, 0.0, t))
    ratio = p.curve.P(T) / p.curve.P(t)
    return ratio * math.exp(A - _B(p.a, tau) * x - _B(p.b, tau) * y)


# --------------------------------------------------------------------------- #
# Semi-analytic European swaption price (Brigo & Mercurio eq. 4.31).
# --------------------------------------------------------------------------- #
def _forward_measure_moments(p: G2ppParams, T: float):
    """Means/vars/correlation of (x(T), y(T)) under the T-forward measure."""
    a, b, s, e, rho = p.a, p.b, p.sigma, p.eta, p.rho
    mu_x = -((s * s / (a * a) + rho * s * e / (a * b)) * (1.0 - math.exp(-a * T))
             - (s * s) / (2.0 * a * a) * (1.0 - math.exp(-2.0 * a * T))
             - (rho * s * e) / (b * (a + b)) * (1.0 - math.exp(-(a + b) * T)))
    mu_y = -((e * e / (b * b) + rho * s * e / (a * b)) * (1.0 - math.exp(-b * T))
             - (e * e) / (2.0 * b * b) * (1.0 - math.exp(-2.0 * b * T))
             - (rho * s * e) / (a * (a + b)) * (1.0 - math.exp(-(a + b) * T)))
    sig_x = s * math.sqrt((1.0 - math.exp(-2.0 * a * T)) / (2.0 * a))
    sig_y = e * math.sqrt((1.0 - math.exp(-2.0 * b * T)) / (2.0 * b))
    rho_xy = (rho * s * e) / ((a + b) * sig_x * sig_y) * (1.0 - math.exp(-(a + b) * T))
    rho_xy = max(-0.999999, min(0.999999, rho_xy))
    return mu_x, mu_y, sig_x, sig_y, rho_xy


def swap_par_rate(p: G2ppParams, expiry: float, tenor: float, freq: int = 1) -> float:
    """Forward par swap rate for a swap starting at ``expiry`` running ``tenor``."""
    T = float(expiry)
    dt = 1.0 / freq
    pay_times = np.arange(T + dt, T + tenor + 1e-9, dt)
    annuity = sum(dt * p.curve.P(ti) for ti in pay_times)
    return (p.curve.P(T) - p.curve.P(T + tenor)) / annuity


def swaption_price(
    p: G2ppParams,
    expiry: float,
    tenor: float,
    strike: Optional[float] = None,
    freq: int = 1,
    payer: bool = True,
    notional: float = 1.0,
    n_quad: int = 96,
) -> float:
    """European swaption price under G2++ (Brigo & Mercurio 2006, eq. 4.31).

    Unit-notional payer-swap value at expiry T is 1 - sum_i c_i P(T, t_i),
    with c_i = strike*tau_i (i<n) and c_n = 1 + strike*tau_n.  The price is

        PS = N P(0,T) integral_R  n(z) [ Phi(-h1) - sum_i lam_i e^{kap_i} Phi(-h2_i) ] dz

    evaluated by Gauss-Legendre quadrature on +-8 sigma_x about mu_x.  The
    inner threshold ybar(z) solving sum_i c_i A_i e^{-Ba_i z - Bb_i ybar}=1 is
    found by Newton iteration (the LHS is strictly monotone decreasing in y).
    """
    if strike is None:
        strike = swap_par_rate(p, expiry, tenor, freq)
    T = float(expiry)
    dt = 1.0 / freq
    pay_times = np.arange(T + dt, T + tenor + 1e-9, dt)
    n = pay_times.size
    if n == 0:
        raise ValueError("No swap payment dates.")
    taus = np.full(n, dt)
    c = strike * taus
    c[-1] += 1.0  # c_n = 1 + strike*tau_n

    mu_x, mu_y, sig_x, sig_y, rho_xy = _forward_measure_moments(p, T)
    a, b = p.a, p.b
    Ba = np.array([_B(a, ti - T) for ti in pay_times])
    Bb = np.array([_B(b, ti - T) for ti in pay_times])
    # A_i = P^M(0,t_i)/P^M(0,T) * exp(0.5[V(T,t_i) - V(0,t_i) + V(0,T)])
    A = np.array([
        (p.curve.P(ti) / p.curve.P(T))
        * math.exp(0.5 * (_V(p, T, ti) - _V(p, 0.0, ti) + _V(p, 0.0, T)))
        for ti in pay_times
    ])

    omd = math.sqrt(1.0 - rho_xy * rho_xy)

    def ybar(z: float) -> float:
        # Solve f(y) = sum_i c_i A_i exp(-Ba_i z - Bb_i y) - 1 = 0 for y.
        coef = c * A * np.exp(-Ba * z)
        y = 0.0
        for _ in range(60):
            ev = coef * np.exp(-Bb * y)
            f = ev.sum() - 1.0
            df = -(Bb * ev).sum()
            if abs(df) < 1e-14:
                break
            step = f / df
            y -= step
            if abs(step) < 1e-12:
                break
        return y

    # Gauss-Legendre nodes on [mu_x - 8 sig_x, mu_x + 8 sig_x].
    nodes, weights = np.polynomial.legendre.leggauss(n_quad)
    lo, hi = mu_x - 8.0 * sig_x, mu_x + 8.0 * sig_x
    zs = 0.5 * (hi - lo) * nodes + 0.5 * (hi + lo)
    jac = 0.5 * (hi - lo)

    total = 0.0
    for z, w in zip(zs, weights):
        dens = math.exp(-0.5 * ((z - mu_x) / sig_x) ** 2) / (sig_x * SQRT_2PI)
        yb = ybar(z)
        h1 = (yb - mu_y) / (sig_y * omd) - rho_xy * (z - mu_x) / (sig_x * omd)
        lam = c * A * np.exp(-Ba * z)
        h2 = h1 + Bb * sig_y * omd
        kap = -Bb * (mu_y - 0.5 * (1.0 - rho_xy * rho_xy) * sig_y * sig_y * Bb
                     + rho_xy * sig_y * (z - mu_x) / sig_x)
        if payer:
            inner = _norm_cdf_scalar(-h1) - float((lam * np.exp(kap) * _norm_cdf(-h2)).sum())
        else:
            inner = -_norm_cdf_scalar(h1) + float((lam * np.exp(kap) * _norm_cdf(h2)).sum())
        total += w * dens * inner
    price = notional * p.curve.P(T) * jac * total
    return max(price, 0.0)


def swaption_normal_vol(
    p: G2ppParams, expiry: float, tenor: float, freq: int = 1, n_quad: int = 96
) -> float:
    """ATM payer-swaption Bachelier (normal) implied vol, in decimal p.a.

    Prices the ATM swaption analytically, then inverts the at-the-money
    Bachelier annuity formula  PS = annuity * sigma_N * sqrt(T/2pi)  to
    recover sigma_N (the d=0 ATM case).
    """
    T = float(expiry)
    dt = 1.0 / freq
    pay_times = np.arange(T + dt, T + tenor + 1e-9, dt)
    annuity = sum(dt * p.curve.P(ti) for ti in pay_times)
    ps = swaption_price(p, expiry, tenor, strike=None, freq=freq, payer=True, n_quad=n_quad)
    return ps / (annuity * math.sqrt(T) / SQRT_2PI)


# --------------------------------------------------------------------------- #
# Exact-increment Monte-Carlo simulator (market-consistency ground truth).
# --------------------------------------------------------------------------- #
def _phi(p: G2ppParams, t: float) -> float:
    """phi(t) = f^M(0,t) + 0.5*[factor-variance adjustment]  (B&M 4.12)."""
    a, b, s, e, rho = p.a, p.b, p.sigma, p.eta, p.rho
    fwd = p.curve.forward(t)
    adj = (s * s / (2.0 * a * a)) * (1.0 - math.exp(-a * t)) ** 2 \
        + (e * e / (2.0 * b * b)) * (1.0 - math.exp(-b * t)) ** 2 \
        + (rho * s * e / (a * b)) * (1.0 - math.exp(-a * t)) * (1.0 - math.exp(-b * t))
    return fwd + adj


@dataclass
class G2ppSimulator:
    """EXACT-increment Monte-Carlo simulator of the G2++ factors.

    For a step of size ``dt`` the OU factors update exactly (no Euler bias):

        x_{k+1} = x_k e^{-a dt} + innov_x
        y_{k+1} = y_k e^{-b dt} + innov_y

    where (innov_x, innov_y) ~ N(0, Cov) with

        Var[innov_x] = sigma^2 (1-e^{-2a dt})/(2a)
        Var[innov_y] = eta^2   (1-e^{-2b dt})/(2b)
        Cov          = rho sigma eta (1-e^{-(a+b) dt})/(a+b).

    The continuously-compounded bank account is accumulated by the trapezoid
    rule on r(t)=x+y+phi(t).
    """

    params: G2ppParams
    seed: int = 12345

    def simulate(
        self, horizon: float, n_paths: int, steps_per_year: int = 52
    ) -> Dict[str, np.ndarray]:
        p = self.params
        a, b, s, e, rho = p.a, p.b, p.sigma, p.eta, p.rho
        n_steps = max(1, int(round(horizon * steps_per_year)))
        dt = horizon / n_steps
        rng = np.random.default_rng(self.seed)

        var_x = s * s * (1.0 - math.exp(-2.0 * a * dt)) / (2.0 * a)
        var_y = e * e * (1.0 - math.exp(-2.0 * b * dt)) / (2.0 * b)
        cov_xy = rho * s * e * (1.0 - math.exp(-(a + b) * dt)) / (a + b)
        cov = np.array([[var_x, cov_xy], [cov_xy, var_y]])
        chol = np.linalg.cholesky(cov)
        ea, eb = math.exp(-a * dt), math.exp(-b * dt)

        x = np.zeros(n_paths)
        y = np.zeros(n_paths)
        log_bank = np.zeros(n_paths)          # integral of r dt
        t = 0.0
        r_prev = x + y + _phi(p, t)
        for _ in range(n_steps):
            z = rng.standard_normal((n_paths, 2)) @ chol.T
            x = x * ea + z[:, 0]
            y = y * eb + z[:, 1]
            t_next = t + dt
            r_next = x + y + _phi(p, t_next)
            log_bank += 0.5 * (r_prev + r_next) * dt   # trapezoid
            r_prev = r_next
            t = t_next
        return {
            "x": x, "y": y,
            "short_rate": x + y + _phi(p, horizon),
            "log_bank": log_bank,            # integral_0^horizon r ds
            "deflator": np.exp(-log_bank),   # exp(-integral r)
            "dt": dt, "n_steps": n_steps, "horizon": horizon,
        }
