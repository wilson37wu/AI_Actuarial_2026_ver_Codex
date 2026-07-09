"""Roadmap 4.1 #10 -- profile the 100,000-policy deterministic batch, locate the
top hotspot, publish a reproducible benchmark.

Finding (evidence: ``docs/validation/PERF_PROFILE_100K.json`` /
``docs/PERF_PROFILE_100K_CARD.md``)
--------------------------------------------------------------------------------
The single largest cost in the 100k-policy deterministic batch is the SHA-256
**reproducibility digest** of the generated portfolio, computed with pandas
``DataFrame.to_csv`` (~50-55% of portfolio-generation runtime; the top
``tottime`` function in a cProfile of the batch is pandas'
``io.formats.csvs._save_chunk``).  That digest's byte output *defines* the
governed reproducibility value recorded on every run, so it CANNOT be reduced
by output-identical means.

Safe (byte-identical) optimisation is limited to the redundant work *around*
the digest -- a duplicate canonical re-sort and a column re-subset that
:func:`portfolio_digest` performs defensively.  Skipping them on the
already-canonical generated frame (see
:func:`~par_model_v2.projection.portfolio_generator._portfolio_digest_presorted`)
is byte-identical and worth ~9% of generation -- **below** the roadmap's 20%
bar.

A >=20% cut IS achievable, but only by replacing the ``to_csv`` digest with a
column-buffer hash (~85-90% faster on the hotspot), which **changes the digest
value** and therefore requires Model Owner sign-off (a governed re-baseline of
the reproducibility digest scheme).  Per the roadmap DoD -- "*>=20% runtime cut
on benchmark or documented finding that none is available*" -- this module is
that documented, reproducible finding, plus the safe sub-20% optimisation that
*is* available (already applied, governed digest untouched).

Design
------
Stdlib + numpy/pandas only (no scipy, no new dependency).  Timings use
``time.perf_counter``; function-level hotspots use ``cProfile``.  Absolute
milliseconds are environment-dependent; the *structure* of the finding
(digest is the dominant hotspot; safe cut < 20%; owner-gated cut >= 20%) is
what the accompanying tests assert.  ``inputs_digest`` hashes the run inputs
(config knobs + schema), not the timings, so idempotent re-runs are stable.

SOA / IA references: ASOP 56 s3.6 (model performance & scalability is a model
risk consideration); IA TAS M s3.5 (document computational-performance
limitations).  Educational reference implementation -- targets are indicative,
not production commitments.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from statistics import median
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import pandas as pd

from par_model_v2.projection.portfolio_generator import (
    UNIFIED_COLUMNS,
    PortfolioGenerationConfig,
    generate_hk_par_portfolio,
    portfolio_digest,
    _portfolio_digest_presorted,
)

SCHEMA_VERSION = "perf-profile-100k-1.0"
SAFE_CUT_TARGET_PCT = 20.0
UNSIGNED_BANNER = (
    "UNSIGNED educational performance evidence -- timings are environment-"
    "dependent and are NOT a production commitment; the governed reproducibility "
    "digest value is unchanged by the safe optimisation."
)


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _time_call(fn: Callable[[], Any], reps: int, warmup: int) -> List[float]:
    for _ in range(max(0, warmup)):
        fn()
    samples: List[float] = []
    for _ in range(max(1, reps)):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000.0)
    return samples


@dataclass
class TimedStage:
    name: str
    reps: int
    mean_ms: float
    median_ms: float
    min_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def time_stage(name: str, fn: Callable[[], Any], *, reps: int = 5, warmup: int = 1) -> TimedStage:
    """Time ``fn`` ``reps`` times (after ``warmup`` untimed calls)."""
    s = _time_call(fn, reps, warmup)
    return TimedStage(
        name=name,
        reps=len(s),
        mean_ms=round(sum(s) / len(s), 3),
        median_ms=round(median(s), 3),
        min_ms=round(min(s), 3),
    )


@dataclass
class HotspotRecord:
    function: str
    filename: str
    lineno: int
    ncalls: int
    tottime_s: float
    cumtime_s: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def top_hotspots(fn: Callable[[], Any], *, reps: int = 1, top_n: int = 12) -> List[HotspotRecord]:
    """Return the ``top_n`` functions by internal (``tottime``) time in a
    cProfile of ``reps`` calls of ``fn``."""
    import cProfile
    import pstats

    pr = cProfile.Profile()
    pr.enable()
    for _ in range(max(1, reps)):
        fn()
    pr.disable()
    st = pstats.Stats(pr)
    st.sort_stats("tottime")
    out: List[HotspotRecord] = []
    for func, stat in st.stats.items():  # type: ignore[attr-defined]
        filename, lineno, name = func
        cc, nc, tt, ct, _callers = stat
        out.append(
            HotspotRecord(
                function=name,
                filename=filename,
                lineno=int(lineno),
                ncalls=int(nc),
                tottime_s=round(float(tt), 6),
                cumtime_s=round(float(ct), 6),
            )
        )
    out.sort(key=lambda r: r.tottime_s, reverse=True)
    return out[: max(1, top_n)]


# --------------------------------------------------------------------------- #
# Digest scheme comparison (quantifies the OWNER-GATED >=20% opportunity)
# --------------------------------------------------------------------------- #

def _buffer_hash_digest(table: pd.DataFrame) -> str:
    """A faster reproducibility digest that hashes the canonical column buffers
    directly instead of a CSV rendering.

    MEASUREMENT-ONLY: this produces a DIFFERENT value from the governed
    :func:`portfolio_digest`, so adopting it is a governed re-baseline that
    requires Model Owner sign-off.  It is never wired into any run path; it
    exists here purely to quantify the owner-gated speed-up.
    """
    h = hashlib.sha256()
    ordered = table.sort_values(["product_line", "policy_id"], kind="mergesort")
    for col in UNIFIED_COLUMNS:
        arr = ordered[col].to_numpy()
        if arr.dtype == object:
            h.update("\x1f".join(map(str, arr.tolist())).encode("utf-8"))
        else:
            h.update(np.ascontiguousarray(arr).tobytes())
        h.update(b"\x1e")
    return h.hexdigest()


@dataclass
class DigestSchemeComparison:
    to_csv_ms: float
    buffer_hash_ms: float
    speedup_pct: float
    values_differ: bool
    note: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def compare_digest_schemes(table: pd.DataFrame, *, reps: int = 5, warmup: int = 1) -> DigestSchemeComparison:
    cur = _time_call(lambda: portfolio_digest(table), reps, warmup)
    alt = _time_call(lambda: _buffer_hash_digest(table), reps, warmup)
    cur_ms = sum(cur) / len(cur)
    alt_ms = sum(alt) / len(alt)
    speedup = 100.0 * (cur_ms - alt_ms) / cur_ms if cur_ms > 0 else 0.0
    return DigestSchemeComparison(
        to_csv_ms=round(cur_ms, 3),
        buffer_hash_ms=round(alt_ms, 3),
        speedup_pct=round(speedup, 1),
        values_differ=_buffer_hash_digest(table) != portfolio_digest(table),
        note=(
            "buffer-hash is a MEASUREMENT-ONLY alternative; it changes the "
            "governed digest value and requires owner sign-off (re-baseline)."
        ),
    )


# --------------------------------------------------------------------------- #
# Safe (byte-identical) optimisation measurement
# --------------------------------------------------------------------------- #

@dataclass
class SafeOptimizationResult:
    redundant_resort_ms: float
    redundant_subset_ms: float
    saving_ms: float
    generation_ms: float
    saving_pct_of_generation: float
    digest_byte_identical: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def measure_safe_optimization(
    config: Optional[PortfolioGenerationConfig] = None, *, reps: int = 5, warmup: int = 1
) -> SafeOptimizationResult:
    """Measure the byte-identical saving from skipping the redundant re-sort and
    column re-subset on the already-canonical generated frame, and prove the
    presorted digest is byte-for-byte identical to the public digest."""
    config = config or PortfolioGenerationConfig()
    res = generate_hk_par_portfolio(config)
    table = res.policies

    resort = _time_call(
        lambda: table.sort_values(["product_line", "policy_id"], kind="mergesort"), reps, warmup
    )
    subset = _time_call(lambda: table[list(UNIFIED_COLUMNS)], reps, warmup)
    gen = _time_call(lambda: generate_hk_par_portfolio(config), reps, warmup=0)

    resort_ms = sum(resort) / len(resort)
    subset_ms = sum(subset) / len(subset)
    saving_ms = resort_ms + subset_ms
    gen_ms = sum(gen) / len(gen)
    identical = (
        _portfolio_digest_presorted(table) == portfolio_digest(table) == res.digest
    )
    return SafeOptimizationResult(
        redundant_resort_ms=round(resort_ms, 3),
        redundant_subset_ms=round(subset_ms, 3),
        saving_ms=round(saving_ms, 3),
        generation_ms=round(gen_ms, 3),
        saving_pct_of_generation=round(100.0 * saving_ms / gen_ms, 2) if gen_ms > 0 else 0.0,
        digest_byte_identical=bool(identical),
    )


# --------------------------------------------------------------------------- #
# Generation decomposition: digest vs modelling compute
# --------------------------------------------------------------------------- #

@dataclass
class GenerationDecomposition:
    total_ms: float
    digest_ms: float
    modelling_ms: float
    digest_fraction: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def decompose_generation(
    config: Optional[PortfolioGenerationConfig] = None, *, reps: int = 5, warmup: int = 1
) -> GenerationDecomposition:
    """Split generation runtime into the reproducibility-digest cost and the
    remaining modelling compute."""
    config = config or PortfolioGenerationConfig()
    res = generate_hk_par_portfolio(config)
    table = res.policies
    total = _time_call(lambda: generate_hk_par_portfolio(config), reps, warmup)
    digest = _time_call(lambda: portfolio_digest(table), reps, warmup)
    total_ms = sum(total) / len(total)
    digest_ms = sum(digest) / len(digest)
    modelling_ms = max(total_ms - digest_ms, 0.0)
    return GenerationDecomposition(
        total_ms=round(total_ms, 3),
        digest_ms=round(digest_ms, 3),
        modelling_ms=round(modelling_ms, 3),
        digest_fraction=round(digest_ms / total_ms, 4) if total_ms > 0 else 0.0,
    )


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #

@dataclass
class PerfProfileReport:
    schema_version: str
    generated_at: str
    n_policies: int
    seed: int
    reps: int
    stages: List[TimedStage]
    generation: GenerationDecomposition
    digest_scheme: DigestSchemeComparison
    safe_optimization: SafeOptimizationResult
    hotspots: List[HotspotRecord]
    top_hotspot_function: str
    safe_cut_pct: float
    owner_gated_cut_pct: float
    meets_20pct_safely: bool
    finding: str
    inputs_digest: str
    unsigned: bool = True
    unsigned_banner: str = UNSIGNED_BANNER

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    def to_markdown(self) -> str:
        g = self.generation
        so = self.safe_optimization
        ds = self.digest_scheme
        lines = [
            f"# 100k-Policy Batch Performance Profile ({self.schema_version})",
            "",
            f"> {self.unsigned_banner}",
            "",
            f"- Generated: `{self.generated_at}`",
            f"- Portfolio: **{self.n_policies:,} policies**, seed `{self.seed}`, reps `{self.reps}`",
            f"- Inputs digest: `{self.inputs_digest[:16]}...`",
            "",
            "## Stage wall times (mean ms)",
            "",
            "| Stage | mean ms | median ms | min ms |",
            "|---|---:|---:|---:|",
        ]
        for s in self.stages:
            lines.append(f"| {s.name} | {s.mean_ms:.1f} | {s.median_ms:.1f} | {s.min_ms:.1f} |")
        lines += [
            "",
            "## Top hotspot",
            "",
            f"Top `tottime` function: **`{self.top_hotspot_function}`**.",
            "",
            f"Generation decomposition: total `{g.total_ms:.1f} ms`, reproducibility "
            f"digest `{g.digest_ms:.1f} ms` (**{g.digest_fraction*100:.0f}%**), "
            f"modelling compute `{g.modelling_ms:.1f} ms`.",
            "",
            "## Safe (byte-identical) optimisation -- APPLIED",
            "",
            f"Skip the redundant canonical re-sort (`{so.redundant_resort_ms:.1f} ms`) and "
            f"column re-subset (`{so.redundant_subset_ms:.1f} ms`) on the already-canonical "
            f"generated frame: saves `{so.saving_ms:.1f} ms` = "
            f"**{so.saving_pct_of_generation:.1f}%** of generation. "
            f"Digest byte-identical: `{so.digest_byte_identical}` (governed value untouched).",
            "",
            "## Owner-gated path to >=20% (NOT applied -- requires sign-off)",
            "",
            f"Replacing the `to_csv` digest with a column-buffer hash runs the digest in "
            f"`{ds.buffer_hash_ms:.1f} ms` vs `{ds.to_csv_ms:.1f} ms` "
            f"(**{ds.speedup_pct:.0f}% faster**), but changes the digest value "
            f"(`values_differ={ds.values_differ}`) -- a governed re-baseline requiring "
            f"Model Owner sign-off.",
            "",
            "## Finding",
            "",
            self.finding,
        ]
        return "\n".join(lines) + "\n"


def _inputs_digest(config: PortfolioGenerationConfig, reps: int) -> str:
    payload = {
        "schema": SCHEMA_VERSION,
        "n_policies": int(config.n_policies),
        "seed": int(config.seed),
        "reps": int(reps),
        "unified_columns": list(UNIFIED_COLUMNS),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def build_report(
    config: Optional[PortfolioGenerationConfig] = None,
    *,
    reps: int = 5,
    hotspot_top_n: int = 12,
) -> PerfProfileReport:
    """Build the full, reproducible performance-profile report for the batch."""
    config = config or PortfolioGenerationConfig()

    res = generate_hk_par_portfolio(config)
    table = res.policies

    stages = [
        time_stage("generate_hk_par_portfolio", lambda: generate_hk_par_portfolio(config), reps=reps),
        time_stage("portfolio_digest (to_csv, governed)", lambda: portfolio_digest(table), reps=reps),
    ]
    generation = decompose_generation(config, reps=reps)
    digest_scheme = compare_digest_schemes(table, reps=reps)
    safe_opt = measure_safe_optimization(config, reps=reps)
    hotspots = top_hotspots(lambda: generate_hk_par_portfolio(config), reps=1, top_n=hotspot_top_n)
    top_fn = hotspots[0].function if hotspots else ""

    safe_cut = safe_opt.saving_pct_of_generation
    owner_gated_cut = digest_scheme.speedup_pct
    meets = safe_cut >= SAFE_CUT_TARGET_PCT

    finding = (
        "The top hotspot of the 100k-policy batch is the SHA-256 reproducibility "
        "digest of the generated portfolio, computed via pandas to_csv "
        f"(~{generation.digest_fraction*100:.0f}% of generation runtime). Its byte "
        "output defines the governed reproducibility value, so it cannot be reduced "
        "by output-identical means. The available SAFE (byte-identical) optimisation "
        f"-- skipping the redundant re-sort and column re-subset -- is "
        f"{safe_cut:.1f}% of generation, BELOW the 20% target; it has been applied "
        "with the governed digest value regression-locked (unchanged). A >=20% cut "
        f"IS achievable ({owner_gated_cut:.0f}% faster digest via a column-buffer "
        "hash) but CHANGES the governed digest value and therefore requires Model "
        "Owner sign-off (governed re-baseline). Per the roadmap DoD this is the "
        "documented finding that no >=20% cut is available by safe means, plus the "
        "sub-20% safe optimisation that is."
    )

    return PerfProfileReport(
        schema_version=SCHEMA_VERSION,
        generated_at=_now_utc(),
        n_policies=int(config.n_policies),
        seed=int(config.seed),
        reps=int(reps),
        stages=stages,
        generation=generation,
        digest_scheme=digest_scheme,
        safe_optimization=safe_opt,
        hotspots=hotspots,
        top_hotspot_function=top_fn,
        safe_cut_pct=round(safe_cut, 2),
        owner_gated_cut_pct=round(owner_gated_cut, 1),
        meets_20pct_safely=bool(meets),
        finding=finding,
        inputs_digest=_inputs_digest(config, reps),
    )
