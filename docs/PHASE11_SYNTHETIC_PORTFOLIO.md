# Phase 11 Task 1 — Synthetic 100,000-Policy HK PAR Portfolio

**Module:** `par_model_v2/projection/portfolio_generator.py`
**Tests:** `tests/test_portfolio_generator.py` (25 cases)
**Build script:** `scripts/build_phase11_portfolio.py`
**Reproducibility evidence:** `docs/PHASE11_PORTFOLIO_METADATA.json`

## Purpose

Provide a large, reproducible, *educational* in-force portfolio of Hong Kong
participating policies so the Phase 11 reporting cycle (chunked processing,
checkpoint restart, reconciliation, reporting packs) can run at realistic scale
without any insurer's confidential policy file. The portfolio mixes the two
Phase 10 product lines: cash dividend (`HKCD_PAR_2026`) and reversionary bonus
(`HKRB_PAR_2026`).

## Schema

The generator emits a single unified table whose columns are
`portfolio_generator.UNIFIED_COLUMNS`. Both product lines share the columns;
line-specific fields carry neutral defaults where they do not apply:

| Column | Notes |
|---|---|
| `policy_id` | `HKCDG########` (cash) / `HKRBG########` (RB), unique |
| `product_line` | `CASH_DIVIDEND` or `REVERSIONARY_BONUS` |
| `product_code` | `HKCD_PAR_2026` / `HKRB_PAR_2026` |
| `issue_age` | integer in product range (default 18–65) |
| `gender` | `M` / `F` |
| `term_years` | one of the supported projection terms `(5, 10, 20)` |
| `sum_assured` | rounded, clipped to product range (default 50k–10M HKD) |
| `annual_premium` | deterministic loading of `sum_assured / term` (+noise) |
| `policy_year` | integer in `[1, term_years]`, duration-decayed |
| `initial_vested_bonus` | RB only: `SA × rb_rate × (policy_year−1)`; 0 for cash |
| `inforce_count` | 1.0 |
| `premium_mode` | `ANNUAL` |
| `dividend_option` / `bonus_option` | `CASH`/`NONE` and `NONE`/`VESTED_REVERSIONARY` |
| `distribution_channel` | `AGENCY` / `BROKER` / `BANCASSURANCE` / `DIRECT` |
| `source_id` | tags synthetic provenance |

Every generated record satisfies the Phase 10 `HKCashDividendPolicy` /
`HKReversionaryBonusPolicy` field constraints and validates against the starter
product mechanics via `validate_portfolio(...)`, which reuses the existing
`validate_hk_cash_dividend_policy_table` / `validate_hk_reversionary_bonus_policy_table`.

## Reproducibility

All randomness flows from a single `numpy` seed (`PortfolioGenerationConfig.seed`).
The same config yields a byte-stable table; `portfolio_digest(...)` returns a
SHA-256 over the canonical (product_line, policy_id) ordering as evidence
(SOA ASOP 56 reproducibility; IA TAS M traceability — assumption source to run
metadata). The default-config digest is recorded in
`docs/PHASE11_PORTFOLIO_METADATA.json`.

## Default portfolio profile (seed 20260604, 100,000 policies)

- Product split ≈ 50/50 cash dividend vs reversionary bonus.
- Term mix ≈ 20% / 45% / 35% for 5 / 10 / 20-year terms.
- Issue age ~ clipped Normal(40, 11), range 18–65.
- Sum assured ~ Lognormal (median ≈ 500k HKD), mean ≈ 0.6M, clipped 50k–10M.
- Premiums ≈ `sum_assured / term × (0.85 + age load + short-term uplift) × noise`.
- Channel mix ≈ 45% agency / 25% broker / 22% bancassurance / 8% direct.

Generation runs in ~6s; full 100k dataclass validation in ~5s.

## Chunk-ready

`iter_policy_chunks(table, chunk_size)` yields deterministic, non-overlapping,
order-stable slices over the canonical ordering — seeding the next Phase 11 task
(grouping, chunking, checkpoint restart, reconciliation). A given chunk index
identifies the same policies on every run.

## Limitations (educational only)

The portfolio is synthetic and **uncalibrated**. Age, term, sum-assured,
premium, and vested-bonus distributions are illustrative heuristics chosen for
plausibility and coverage — not fitted to market experience, insurer filings, or
PRE policy. Premiums are a deterministic loading of `sum_assured / term` and must
not be read as priced rates. Not cleared for production or pricing use.

## Industry alignment

- **SOA ASOP 56** — reproducibility (seeded, digest-evidenced), documented data
  assumptions and limitations, model-use restriction disclosure.
- **IA TAS M / TAS 100** — traceability from assumption source (config) to run
  metadata (digest + summary), explicit data limitations.
- **ERM** — provenance tagging (`source_id`) and synthetic-data disclosure
  support governance and audit of the educational reporting cycle.
