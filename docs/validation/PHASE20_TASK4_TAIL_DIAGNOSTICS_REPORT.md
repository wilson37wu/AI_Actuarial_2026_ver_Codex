# Phase 20 Task 4 -- Tail Diagnostics (Two-Factor G2++ Rate Driver)

**Run:** 2026-06-06T10:25:50.364534+00:00

Diagnostics on the genuine five-driver nested loss vector with the 2F G2++ rate driver
(n_outer=240, confidence 99.5%).

## VaR / ES by confidence level

| Level | VaR | ES | SCR (VaR-mean) | SCR (ES-mean) |
|-------|----:|---:|---------------:|--------------:|
| 0.950 | 156,402 | 164,844 | 39,885 | 48,328 |
| 0.990 | 170,786 | 174,818 | 54,270 | 58,302 |
| 0.995 | 171,632 | 176,557 | 55,116 | 60,040 |

## Outer convergence (99.5% SCR over increasing subsamples)

| n_outer | SCR-proxy |
|--------:|----------:|
| 60 | 42,314 |
| 120 | 50,961 |
| 180 | 54,177 |
| 240 | 55,116 |

## Bootstrap 95% CI for the 99.5% SCR-proxy

- Point: 55,116; 95% CI [45,680, 65,409] over 2000 resamples; relative half-width 17.9%.

The relative half-width quantifies outer Monte-Carlo noise at this educational scale;
production sign-off requires a larger outer sample (recorded as a residual).
