# 100k-Policy Batch Performance Profile (perf-profile-100k-1.0)

> UNSIGNED educational performance evidence -- timings are environment-dependent and are NOT a production commitment; the governed reproducibility digest value is unchanged by the safe optimisation.

- Generated: `2026-07-09T17:26:24Z`
- Portfolio: **100,000 policies**, seed `20260604`, reps `5`
- Inputs digest: `2f5db6d1c7fa0a0b...`

## Stage wall times (mean ms)

| Stage | mean ms | median ms | min ms |
|---|---:|---:|---:|
| generate_hk_par_portfolio | 532.0 | 528.6 | 519.3 |
| portfolio_digest (to_csv, governed) | 385.3 | 380.1 | 372.0 |

## Top hotspot

Top `tottime` function: **`_save_chunk`**.

Generation decomposition: total `525.9 ms`, reproducibility digest `366.2 ms` (**70%**), modelling compute `159.7 ms`.

## Safe (byte-identical) optimisation -- APPLIED

Skip the redundant canonical re-sort (`48.3 ms`) and column re-subset (`11.2 ms`) on the already-canonical generated frame: saves `59.5 ms` = **11.5%** of generation. Digest byte-identical: `True` (governed value untouched).

## Owner-gated path to >=20% (NOT applied -- requires sign-off)

Replacing the `to_csv` digest with a column-buffer hash runs the digest in `86.6 ms` vs `390.9 ms` (**78% faster**), but changes the digest value (`values_differ=True`) -- a governed re-baseline requiring Model Owner sign-off.

## Finding

The top hotspot of the 100k-policy batch is the SHA-256 reproducibility digest of the generated portfolio, computed via pandas to_csv (~70% of generation runtime). Its byte output defines the governed reproducibility value, so it cannot be reduced by output-identical means. The available SAFE (byte-identical) optimisation -- skipping the redundant re-sort and column re-subset -- is 11.5% of generation, BELOW the 20% target; it has been applied with the governed digest value regression-locked (unchanged). A >=20% cut IS achievable (78% faster digest via a column-buffer hash) but CHANGES the governed digest value and therefore requires Model Owner sign-off (governed re-baseline). Per the roadmap DoD this is the documented finding that no >=20% cut is available by safe means, plus the sub-20% safe optimisation that is.
