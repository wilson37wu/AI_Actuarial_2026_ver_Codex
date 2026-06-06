# Phase 20 Task 2 - G2++ Swaption-Surface Calibration

**Run timestamp:** 2026-06-06T08:25:30.201161+00:00

**Gate:** `G-SWPN` - **PASS**

## Calibrated G2++ Parameters

| a | b | sigma | eta | rho |
| ---: | ---: | ---: | ---: | ---: |
| 0.03454 | 0.95828 | 0.00637 | 0.00240 | -0.9082 |

Initial seed: a=0.1000, b=0.5000, sigma=0.0100, eta=0.0070, rho=-0.600.

## Fit Quality

| Metric | Value |
| --- | ---: |
| ATM quotes | 24 |
| Implied-vol RMSE | 54.67 bps |
| Worst-point vol error | 172.99 bps |
| Relative-price RMSE | 0.0270 |
| Objective (mean rel-price^2) | 0.000727136 |
| Simplex iterations | 931 |

## G-SWPN Checks

- **G-SWPN-01**: PASS (observed `9.71445e-17`, threshold `<= 1e-7 absolute price difference`)
- **G-SWPN-02**: PASS (observed `0.000727136`, threshold `converged and objective < 0.1`)
- **G-SWPN-03**: PASS (observed `54.6706`, threshold `<= 75 bps`)
- **G-SWPN-04**: PASS (observed `172.988`, threshold `<= 200 bps`)
- **G-SWPN-05**: PASS (observed `-0.908214`, threshold `a,b>0 distinct; sigma,eta>0; -1<rho<1`)
- **G-SWPN-06**: PASS (observed `0.00206577`, threshold `> 0 for every grid point`)
- **G-SWPN-07**: PASS (observed `0`, threshold `<= 1e-12 absolute price error`)

## Per-Quote Fit (ATM, semi-annual)

| Expiry x Tenor | Forward | Market vol | Model vol | Error (bps) |
| --- | ---: | ---: | ---: | ---: |
| 1y x 1y | 0.0226 | 0.2374 | 0.2379 | +4.8 |
| 1y x 2y | 0.0237 | 0.2315 | 0.2348 | +32.7 |
| 1y x 5y | 0.0257 | 0.2214 | 0.2173 | -41.0 |
| 1y x 10y | 0.0271 | 0.2125 | 0.1952 | -173.0 |
| 2y x 1y | 0.0247 | 0.2271 | 0.2252 | -19.2 |
| 2y x 2y | 0.0253 | 0.2212 | 0.2235 | +23.0 |
| 2y x 5y | 0.0270 | 0.2111 | 0.2073 | -38.2 |
| 2y x 10y | 0.0277 | 0.2022 | 0.1901 | -120.7 |
| 3y x 1y | 0.0260 | 0.2171 | 0.2175 | +4.0 |
| 3y x 2y | 0.0269 | 0.2112 | 0.2118 | +6.0 |
| 3y x 5y | 0.0277 | 0.2011 | 0.2012 | +0.7 |
| 3y x 10y | 0.0281 | 0.1923 | 0.1858 | -65.2 |
| 5y x 1y | 0.0278 | 0.2034 | 0.2029 | -4.9 |
| 5y x 2y | 0.0284 | 0.1974 | 0.1984 | +10.1 |
| 5y x 5y | 0.0286 | 0.1873 | 0.1910 | +37.1 |
| 5y x 10y | 0.0285 | 0.1785 | 0.1787 | +2.3 |
| 7y x 1y | 0.0281 | 0.1966 | 0.1977 | +11.2 |
| 7y x 2y | 0.0284 | 0.1906 | 0.1944 | +38.2 |
| 7y x 5y | 0.0284 | 0.1805 | 0.1874 | +69.0 |
| 7y x 10y | 0.0286 | 0.1717 | 0.1727 | +10.4 |
| 10y x 1y | 0.0278 | 0.1899 | 0.1929 | +30.3 |
| 10y x 2y | 0.0280 | 0.1840 | 0.1905 | +65.1 |
| 10y x 5y | 0.0283 | 0.1738 | 0.1805 | +66.7 |
| 10y x 10y | 0.0289 | 0.1650 | 0.1634 | -15.5 |

## Governance

- ChangeRecord: `6c7d5354530c451a9a6ab46f33a8dba0` - **OWNER_REVIEW**
- MR-013: **IN_PROGRESS** (refreshed)
- Audit integrity: **True**

## Production Restriction

EDUCATIONAL ONLY. Calibrated to a synthetic proxy swaption surface; re-calibrate to a validated market surface and obtain independent review before any production, capital, or disclosure use.
