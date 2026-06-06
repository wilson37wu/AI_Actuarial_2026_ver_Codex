# Five-Driver Tail-Convergence & Stability Diagnostics — Model-Use Card

**Component:** FiveDriverTailDiagnostics (par_model_v2/projection/multi_driver_tail_diagnostics.py)

**Classification:** EDUCATIONAL ONLY - NOT a regulatory capital model

**Risk drivers:** short rate, equity level, credit spread, lapse behaviour, mortality trend

## Method

Outer-count convergence, non-parametric bootstrap CI/SE on the 99.5% VaR/ES, and a crude/antithetic/Sobol variance-reduction comparison for the five-driver 99.5% capital metric, built on the Phase 19 Task 3 quintivariate LSMC surface (the outer-sampling error is probed; proxy error is bounded separately by the five-driver OOS proxy-validation report).

## Evidence (report config; seed 42)

- Outer-count convergence over N_outer 1k-16k: 99.5% VaR converges to ~230,879 (ES ~246,337); converged True at recommended N_outer >= 8,000 (tol 2%).
- Five-driver VaR ~230,879 is a small monotone increment over the four-driver ~230,388 — consistent with mortality-trend benefit-timing on a sum-assured endowment (mortality is the smallest, most orthogonal driver, standalone SCR ~413).
- Non-parametric bootstrap 95% CI on VaR [227,582, 241,861], SE ~3,104 (+/-3.07% of point).
- Variance reduction: Sobol QMC ~4.80x on the VaR estimator; antithetic ~0.78x (expected-ineffective for an extreme quantile, documented).
- VERDICT PASS; reproducibility digest bit-identical across reruns.

## Limitations

- Outer sampling and bootstrap diagnostics probe Monte-Carlo error only; the proxy (surface) error is bounded separately by the five-driver OOS validation.
- The variance-reduction study runs on a smooth pilot-anchored Gaussian-copula surrogate of the horizon-state distribution, NOT the raw governed processes; antithetic/QMC require a controllable normal/uniform driver.
- Five drivers only (rates + equity + credit + lapse + mortality-trend); FX and liquidity remain outside the tail.
- Mortality trend is a single systemic OU index (Lee-Carter-style) with placeholder parameters; the benefit coupling is educational.
- Lapse behaviour is a single systemic OU index with placeholder parameters; the in-force coupling is multiplicative and educational.
- Independent APS X2 review and credentialled calibration data are still required before any production use.

## Standards

- SOA ASOP 56 §3.5
- SOA ASOP 56 §3.1.3
- SOA ASOP 25 §3.3
- SOA ASOP 7 §3.3
- IA TAS M §3.6
- L'Ecuyer (2018) RQMC
