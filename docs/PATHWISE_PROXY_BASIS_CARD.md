# Path-Wise Proxy Basis Card (Phase 25 Task 3)

**What:** the LSMC proxy now carries the MATCHING path-wise action basis:
relieved_hat = alpha * phi_sigma(CR_hat) * clip(B_hat, 0, L_hat), the
governed relief curve smoothed over an effective lognormal dispersion of the
path-wise coverage ratio. Two scalars (sigma 0.225, alpha 0.757) +
kappa 1.0368, ALL calibrated on the FIT sample only (leakage-free). Truth
and proxy apply the identical envelope transform (G1 convention).

**Verdict:** PASS. OOS R^2 0.9978 (gate >= 0.95); VaR99.5 rel err
0.40% (gate <= 10%); SCR rel err 1.16%.

**Candidate comparison:** the pre-registered zero-shock + level-factor
candidate was evaluated and REJECTED on fit evidence (state-dependent bias;
fit R^2 -15.152 vs 0.8006); disclosed in the report.

**Residuals:** declaration cadence (annual sensitivity quantified);
perfect-foresight coverage discounting; node offset undecayed; constant
sigma across nodes.

**EDUCATIONAL MODEL** - parameters are placeholders; NOT for production
capital decisions. See PHASE25_TASK3_PATHWISE_PROXY_BASIS_REPORT.md.
