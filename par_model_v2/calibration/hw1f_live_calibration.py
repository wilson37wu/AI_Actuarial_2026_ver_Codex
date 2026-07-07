"""
HW1F Swaption Calibration on a Live/Proxy Quote Set (roadmap 4.1 #2)
====================================================================

Roadmap item #2 (docs/CONTINUOUS_IMPROVEMENT_ROADMAP.md 4.1), model-risk
register MR-001 / MR-008.  Closes the two gaps left after roadmap #1
(live curve/index pipeline) and GUI-3 (calibration console):

1. **Swaption quotes had no live/proxy provenance path.**  The Phase 13
   pipeline reads static file fixtures only.  This module extends the
   roadmap-#1 three-tier provenance design (``live_fetch`` /
   ``cached_snapshot`` / ``file_fixture``) to the FULL swaption surface
   payload (ATM normal-vol grid + spot curve + r0 + regulatory cap), with
   schema validation BEFORE caching and SHA-256-sealed snapshots whose
   integrity is re-verified on every read.

2. **No standalone governed parameter card.**  ``run_hw1f_live_calibration``
   executes ``HullWhiteCalibrator.calibrate()`` end-to-end per market and
   emits a PARAMETER CARD artifact (JSON + markdown) carrying the calibrated
   ``(a, sigma_r)``, full fit diagnostics (weighted SSE, RMSE bps, max
   abs error bps, optimizer convergence, per-point fit table), production
   gates G-02 / G-12, data lineage, an inputs digest (idempotent re-runs),
   and an explicit ``"unsigned": true`` flag.

GOVERNANCE - UNSIGNED BY CONSTRUCTION
-------------------------------------
Calibrated parameters are DIAGNOSTIC output flagged UNSIGNED pending Model
Owner approval.  This module never loads, mutates, or persists the
repository ``GovernanceStore`` and never touches governed ESG parameters or
governed headline figures.  Sign-off remains a human action.

Standards
---------
SOA ASOP 56 3.4 (calibration methodology), ASOP 23 (data quality),
IA TAS M 3.5/3.6 (assumption appropriateness, traceability),
IFoA APS X2 4.2 (independent review of material assumption changes).

PRODUCTION USE RESTRICTION
--------------------------
No credentialled vendor adapter ships with this module.  Injected fetchers
supply live/proxy quote sets; fixtures are educational proxies.  All results
are UNSIGNED until the Model Owner approves the source and the parameters
under the governance workflow.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import pandas as pd

from par_model_v2.calibration.calibration_framework import (
    HullWhiteCalibrator,
    SwaptionQuote,
)
from par_model_v2.calibration.live_market_data_pipeline import (
    PROVENANCE_CACHE,
    PROVENANCE_FIXTURE,
    PROVENANCE_LIVE,
    MarketDataFetchError,
    SnapshotCache,
    SnapshotIntegrityError,  # noqa: F401  (re-exported for callers/tests)
)
from par_model_v2.calibration.market_data_source import (
    DataLineageRecord,
    LiveSwaptionDataLoader,
    SwaptionMarketDataSource,
    default_fixture_dir,
    evaluate_g02_gate,
    evaluate_g12_gate,
)

SCHEMA_VERSION = "hw1f-live-cal-1.0"

SUPPORTED_MARKETS = ("CNY", "HKD")

#: Optimizer bounds matching the Phase 13 production loader (documented in
#: limitation_cards.py: wider ``a`` bound needed for high-vol HKD market).
DEFAULT_OPTIMIZER_BOUNDS: Dict[str, Tuple[float, float]] = {
    "a": (0.001, 3.0),
    "sigma_r": (0.001, 0.20),
}

#: G-02 RMSE threshold (bps) - HW1F one-factor achievable level; the G2++
#: upgrade (roadmap #7) targets 5 bps.
G02_RMSE_THRESHOLD_BPS = 25.0

UNSIGNED_REASON_TEMPLATE = (
    "Parameters UNSIGNED pending Model Owner approval (roadmap #2, MR-001/"
    "MR-008): quote-set provenance {provenances}; no owner-approved "
    "credentialled vendor source is configured (roadmap #1). Educational/"
    "proxy data - not for regulatory submission."
)

SurfaceFetcher = Callable[[date], Dict[str, Any]]


# ---------------------------------------------------------------------------
# 1. Swaption surface payload schema validation
# ---------------------------------------------------------------------------

def validate_swaption_surface_payload(payload: Any) -> List[str]:
    """Validate one swaption surface document; return a list of errors.

    Schema (matches the versioned fixture files so all three provenance
    tiers share one contract):

    ``{currency, as_of_date, swaption_grid: [{expiry_years,
    swap_tenor_years, normal_vol_bps, weight?}], spot_curve:
    {tenors_years: [...], rates_decimal: [...]}, initial_short_rate,
    regulatory_rate_cap?}``
    """
    errors: List[str] = []
    if not isinstance(payload, dict):
        return ["payload must be a dict, got {}".format(type(payload).__name__)]

    currency = payload.get("currency")
    if currency not in SUPPORTED_MARKETS:
        errors.append("currency must be one of {}, got {!r}".format(
            SUPPORTED_MARKETS, currency))

    as_of = payload.get("as_of_date")
    try:
        date.fromisoformat(str(as_of))
    except (TypeError, ValueError):
        errors.append("as_of_date must be ISO YYYY-MM-DD, got {!r}".format(as_of))

    grid = payload.get("swaption_grid")
    if not isinstance(grid, list) or not grid:
        errors.append("swaption_grid must be a non-empty list")
    else:
        for i, row in enumerate(grid):
            if not isinstance(row, dict):
                errors.append("swaption_grid[{}] must be a dict".format(i))
                continue
            for key in ("expiry_years", "swap_tenor_years", "normal_vol_bps"):
                val = row.get(key)
                if not isinstance(val, (int, float)) or isinstance(val, bool):
                    errors.append("swaption_grid[{}].{} must be numeric, got {!r}".format(
                        i, key, val))
                elif val <= 0:
                    errors.append("swaption_grid[{}].{} must be > 0, got {}".format(
                        i, key, val))
            weight = row.get("weight", 1.0)
            if not isinstance(weight, (int, float)) or isinstance(weight, bool) or weight < 0:
                errors.append("swaption_grid[{}].weight must be >= 0, got {!r}".format(
                    i, weight))

    curve = payload.get("spot_curve")
    if not isinstance(curve, dict):
        errors.append("spot_curve must be a dict with tenors_years/rates_decimal")
    else:
        tenors = curve.get("tenors_years")
        rates = curve.get("rates_decimal")
        if not isinstance(tenors, list) or not isinstance(rates, list) or not tenors:
            errors.append("spot_curve.tenors_years / rates_decimal must be non-empty lists")
        elif len(tenors) != len(rates):
            errors.append("spot_curve arrays differ in length: {} tenors vs {} rates".format(
                len(tenors), len(rates)))
        else:
            if any((not isinstance(t, (int, float)) or isinstance(t, bool) or t <= 0)
                   for t in tenors):
                errors.append("spot_curve.tenors_years must all be numeric > 0")
            bad_rates = [r for r in rates
                         if not isinstance(r, (int, float)) or isinstance(r, bool)
                         or r < -0.02 or r > 0.20]
            if bad_rates:
                errors.append("spot_curve.rates_decimal outside [-2%, 20%]: {}".format(
                    bad_rates[:5]))

    r0 = payload.get("initial_short_rate")
    if not isinstance(r0, (int, float)) or isinstance(r0, bool) or not (0.0 <= r0 <= 0.20):
        errors.append("initial_short_rate must be numeric in [0, 0.20], got {!r}".format(r0))

    cap = payload.get("regulatory_rate_cap", 0.05)
    if not isinstance(cap, (int, float)) or isinstance(cap, bool) or not (0.0 < cap <= 0.20):
        errors.append("regulatory_rate_cap must be numeric in (0, 0.20], got {!r}".format(cap))

    return errors


def _canonical_payload_sha256(payload: Dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# 2. Three-tier swaption surface loader (live_fetch / cached_snapshot / fixture)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SwaptionSurfaceResult:
    """Validated swaption surface plus provenance evidence for one load."""

    market: str
    as_of_date: str
    provenance: str
    payload: Dict[str, Any]
    snapshot_path: str
    sha256: str
    lineage: DataLineageRecord


class SwaptionSurfaceLoader:
    """Resolve one market's swaption surface through governed provenance tiers.

    Tier order (mirrors the roadmap-#1 loaders):

    1. ``live_fetch``      - injected ``fetcher(as_of) -> payload dict``
                             (vendor adapter / proxy quote set).  Schema is
                             validated BEFORE caching; a validation failure
                             raises ``MarketDataFetchError`` - bad live data
                             is never silently replaced by a fixture.
                             Lineage is flagged UNSIGNED.
    2. ``cached_snapshot`` - SHA-256-sealed snapshot re-verified on read.
    3. ``file_fixture``    - versioned educational fixture (offline default).
    """

    def __init__(
        self,
        market: str,
        cache: SnapshotCache,
        fetcher: Optional[SurfaceFetcher] = None,
        fixture_path: Optional[Path] = None,
        fixture_as_of: str = "20260101",
    ) -> None:
        market = str(market).upper()
        if market not in SUPPORTED_MARKETS:
            raise ValueError("Unsupported market {!r}; expected one of {}".format(
                market, SUPPORTED_MARKETS))
        self.market = market
        self.dataset = "swaption_surface_{}".format(market.lower())
        self._cache = cache
        self._fetcher = fetcher
        if fixture_path is None:
            fixture_path = default_fixture_dir() / "{}_swaption_surface_{}.json".format(
                market.lower(), fixture_as_of)
        self._fixture_path = Path(fixture_path)

    # -- helpers ----------------------------------------------------------

    def _validated(self, payload: Any, origin: str) -> Dict[str, Any]:
        errors = validate_swaption_surface_payload(payload)
        if not errors:
            if str(payload.get("currency", "")).upper() != self.market:
                errors.append("currency {!r} does not match loader market {!r}".format(
                    payload.get("currency"), self.market))
        if errors:
            raise MarketDataFetchError(
                "{} swaption surface from {} failed schema validation: {}".format(
                    self.market, origin, "; ".join(errors)))
        return payload

    def _lineage(self, payload: Dict[str, Any], provenance: str,
                 source_detail: str, sha256: str) -> DataLineageRecord:
        as_of = str(payload["as_of_date"])
        fixture_lineage = payload.get("data_lineage", {}) if provenance == PROVENANCE_FIXTURE else {}
        approved_by = fixture_lineage.get(
            "approved_by", "UNSIGNED_pending_owner_approval")
        return DataLineageRecord(
            lineage_id="LIN_HW1F_{}_{}".format(self.market, as_of.replace("-", "")),
            market=self.market,
            as_of_date=as_of,
            source_type=provenance,
            source_detail=source_detail,
            fixture_version=fixture_lineage.get("version", "n/a"),
            approved_by=approved_by,
            approval_timestamp=fixture_lineage.get(
                "approval_timestamp", "UNSIGNED"),
            sha256_checksum=sha256,
        )

    # -- tiers ------------------------------------------------------------

    def load(self, as_of: Optional[date] = None, refresh: bool = False) -> SwaptionSurfaceResult:
        """Resolve the surface through the tiers; validate; return evidence."""
        if self._fetcher is not None and (refresh or not self._has_snapshot(as_of)):
            return self._load_live(as_of or date.today())
        if as_of is not None and self._has_snapshot(as_of):
            return self._load_cached(as_of)
        latest = self._cache.latest(self.dataset)
        if latest is not None:
            return self._from_snapshot(latest)
        return self._load_fixture()

    def _has_snapshot(self, as_of: Optional[date]) -> bool:
        if as_of is None:
            return bool(self._cache.list_snapshots(self.dataset))
        return self._cache.path_for(self.dataset, as_of).exists()

    def _load_live(self, as_of: date) -> SwaptionSurfaceResult:
        raw = self._fetcher(as_of)  # type: ignore[misc]
        payload = self._validated(raw, "live_fetch")
        source_detail = "injected fetcher {} (live/proxy quote set)".format(
            getattr(self._fetcher, "__name__", repr(self._fetcher)))
        path, sha = self._cache.store(
            self.dataset, payload["as_of_date"], [payload], PROVENANCE_LIVE,
            source_detail)
        return SwaptionSurfaceResult(
            market=self.market,
            as_of_date=str(payload["as_of_date"]),
            provenance=PROVENANCE_LIVE,
            payload=payload,
            snapshot_path=str(path),
            sha256=sha,
            lineage=self._lineage(payload, PROVENANCE_LIVE, source_detail, sha),
        )

    def _load_cached(self, as_of: date) -> SwaptionSurfaceResult:
        snapshot = self._cache.load(self.dataset, as_of)  # integrity re-verified
        return self._from_snapshot(snapshot)

    def _from_snapshot(self, snapshot: Dict[str, Any]) -> SwaptionSurfaceResult:
        records = snapshot.get("records", [])
        if len(records) != 1:
            raise MarketDataFetchError(
                "{} snapshot must contain exactly one surface record, got {}".format(
                    self.market, len(records)))
        payload = self._validated(records[0], "cached_snapshot")
        path = str(self._cache.path_for(self.dataset, payload["as_of_date"]))
        sha = snapshot["sha256"]
        return SwaptionSurfaceResult(
            market=self.market,
            as_of_date=str(payload["as_of_date"]),
            provenance=PROVENANCE_CACHE,
            payload=payload,
            snapshot_path=path,
            sha256=sha,
            lineage=self._lineage(payload, PROVENANCE_CACHE, path, sha),
        )

    def _load_fixture(self) -> SwaptionSurfaceResult:
        if not self._fixture_path.exists():
            raise MarketDataFetchError(
                "{}: no live fetcher, no cached snapshot, and fixture missing: {}".format(
                    self.market, self._fixture_path))
        raw_bytes = self._fixture_path.read_bytes()
        payload = self._validated(json.loads(raw_bytes.decode("utf-8")), "file_fixture")
        sha = hashlib.sha256(raw_bytes).hexdigest()
        detail = str(self._fixture_path.resolve())
        return SwaptionSurfaceResult(
            market=self.market,
            as_of_date=str(payload["as_of_date"]),
            provenance=PROVENANCE_FIXTURE,
            payload=payload,
            snapshot_path=detail,
            sha256=sha,
            lineage=self._lineage(payload, PROVENANCE_FIXTURE, detail, sha),
        )


# ---------------------------------------------------------------------------
# 3. In-memory swaption source over a validated payload
# ---------------------------------------------------------------------------

class DictSwaptionSource(SwaptionMarketDataSource):
    """Adapts a validated surface payload + lineage to the Phase 13 source ABC.

    Lets the loader-resolved (live/cached/fixture) payload flow through the
    SAME ``LiveSwaptionDataLoader`` validation and input assembly the
    Phase 13 production path uses.
    """

    def __init__(self, result: SwaptionSurfaceResult) -> None:
        self._r = result
        self._d = result.payload

    @property
    def market(self) -> str:
        return self._r.market

    def fetch_swaption_quotes(self) -> List[SwaptionQuote]:
        return [
            SwaptionQuote(
                expiry_years=row["expiry_years"],
                swap_tenor_years=row["swap_tenor_years"],
                normal_vol_bps=row["normal_vol_bps"],
                weight=row.get("weight", 1.0),
            )
            for row in self._d["swaption_grid"]
        ]

    def fetch_spot_curve(self) -> pd.Series:
        sc = self._d["spot_curve"]
        return pd.Series(
            data=sc["rates_decimal"],
            index=sc["tenors_years"],
            name="{}_spot_{}".format(self.market, self._d["as_of_date"]),
            dtype=float,
        )

    def fetch_initial_short_rate(self) -> float:
        return float(self._d["initial_short_rate"])

    def fetch_calibration_date(self) -> date:
        return date.fromisoformat(str(self._d["as_of_date"]))

    def fetch_regulatory_rate_cap(self) -> float:
        return float(self._d.get("regulatory_rate_cap", 0.05))

    def build_lineage_record(self) -> DataLineageRecord:
        return self._r.lineage


# ---------------------------------------------------------------------------
# 4. End-to-end runner + parameter card
# ---------------------------------------------------------------------------

def _calibrate_market(result: SwaptionSurfaceResult) -> Dict[str, Any]:
    """Run calibrate() end-to-end for one resolved surface; return card block."""
    loader = LiveSwaptionDataLoader(
        DictSwaptionSource(result),
        optimizer_bounds=dict(DEFAULT_OPTIMIZER_BOUNDS),
    )
    inputs, lineage = loader.load()
    calibrator = HullWhiteCalibrator(inputs)
    cal = calibrator.calibrate()
    a, sigma_r = float(cal.a), float(cal.sigma_r)
    sse = float(calibrator.loss([a, sigma_r]))
    converged = "converged=True" in (cal.notes or "")
    optimizer = "L-BFGS-B"
    polish: Optional[Dict[str, Any]] = None
    fit_table = cal.swaption_fit_table
    rmse_bps = cal.swaption_rmse_bps
    max_err_bps = cal.max_swaption_error_bps

    if not converged:
        # Diagnostic-layer polish only: when scipy's L-BFGS-B line search ends
        # ABNORMAL (a known scipy>=1.15 behaviour on flat vol surfaces), refine
        # from its solution with bounded Nelder-Mead.  The governed
        # HullWhiteCalibrator is untouched; both stages are recorded on the card.
        from scipy import optimize as scipy_optimize
        res2 = scipy_optimize.minimize(
            calibrator.loss, [a, sigma_r], method="Nelder-Mead",
            bounds=[DEFAULT_OPTIMIZER_BOUNDS["a"], DEFAULT_OPTIMIZER_BOUNDS["sigma_r"]],
            options={"xatol": 1e-10, "fatol": 1e-16, "maxiter": 2000},
        )
        if res2.success and float(res2.fun) <= sse * (1.0 + 1e-12):
            a, sigma_r = float(res2.x[0]), float(res2.x[1])
            sse = float(res2.fun)
            converged = True
            optimizer = "L-BFGS-B + Nelder-Mead polish"
            fit_table = calibrator.goodness_of_fit_table(a, sigma_r)
            rmse_bps = fit_table.attrs.get("rmse_bps")
            max_err_bps = fit_table.attrs.get("max_abs_error_bps")
            polish = {
                "stage1": "L-BFGS-B (ABNORMAL line search)",
                "stage2": "Nelder-Mead polish converged",
                "stage2_iterations": int(res2.nit),
                "sse_improvement": True,
            }

    at_bounds = [name for name, (lo, hi), val in (
        ("a", DEFAULT_OPTIMIZER_BOUNDS["a"], a),
        ("sigma_r", DEFAULT_OPTIMIZER_BOUNDS["sigma_r"], sigma_r),
    ) if abs(val - lo) < 1e-9 or abs(val - hi) < 1e-9]

    fit_records: List[Dict[str, Any]] = []
    if fit_table is not None:
        fit_records = json.loads(fit_table.to_json(orient="records"))
    quotes = inputs.swaption_quotes
    return {
        "market": result.market,
        "as_of_date": result.as_of_date,
        "provenance": result.provenance,
        "source_sha256": result.sha256,
        "snapshot_path": result.snapshot_path,
        "parameters": {
            "a": a,
            "sigma_r": sigma_r,
            "lambda_r": cal.lambda_r,
            "r0": cal.r0,
        },
        "diagnostics": {
            "sse_weighted_bps_sq": sse,
            "params_at_bounds": at_bounds,
            "rmse_bps": rmse_bps,
            "max_abs_error_bps": max_err_bps,
            "converged": converged,
            "optimizer": optimizer,
            "polish": polish,
            "optimizer_bounds": {k: list(v) for k, v in DEFAULT_OPTIMIZER_BOUNDS.items()},
            "n_quotes_total": len(quotes),
            "n_quotes_active": sum(1 for q in quotes if q.weight > 0),
            "notes": cal.notes,
        },
        "fit_table": fit_records,
        "lineage": lineage.to_dict(),
        "is_placeholder": bool(cal.is_placeholder),
    }


def run_hw1f_live_calibration(
    markets: Sequence[str] = SUPPORTED_MARKETS,
    fetchers: Optional[Dict[str, SurfaceFetcher]] = None,
    cache_dir: Optional[Path] = None,
    fixture_dir: Optional[Path] = None,
    fixture_as_of: str = "20260101",
    out_dir: Optional[Path] = None,
    as_of: Optional[date] = None,
    refresh: bool = False,
) -> Dict[str, Any]:
    """Execute HW1F swaption calibration end-to-end on a live/proxy quote set.

    Parameters
    ----------
    markets : sequence of str
        Markets to calibrate (subset of ``SUPPORTED_MARKETS``).
    fetchers : dict market -> callable, optional
        Injected live/proxy quote-set fetchers (vendor adapters).  Markets
        without a fetcher resolve via cached snapshot then fixture.
    cache_dir : Path, optional
        Snapshot cache directory (default: ``<fixture_dir>/../.cache`` is NOT
        used; an explicit temp/cache dir is expected in production runs; when
        omitted a ``.hw1f_cal_cache`` directory beside the fixtures is used).
    out_dir : Path, optional
        Where to write ``HW1F_LIVE_CALIBRATION_PARAMETER_CARD.{json,md}``.
        Re-runs with an unchanged inputs digest return the cached card
        (``"cached": true``) unless ``refresh=True``.

    Returns
    -------
    dict
        The parameter card (schema ``hw1f-live-cal-1.0``).
    """
    fetchers = fetchers or {}
    if fixture_dir is None:
        fixture_dir = default_fixture_dir()
    fixture_dir = Path(fixture_dir)
    if cache_dir is None:
        cache_dir = fixture_dir.parent / ".hw1f_cal_cache"
    cache = SnapshotCache(cache_dir)

    results: List[SwaptionSurfaceResult] = []
    for market in markets:
        loader = SwaptionSurfaceLoader(
            market,
            cache,
            fetcher=fetchers.get(str(market).upper()),
            fixture_path=fixture_dir / "{}_swaption_surface_{}.json".format(
                str(market).lower(), fixture_as_of),
        )
        results.append(loader.load(as_of=as_of, refresh=refresh))

    inputs_digest = hashlib.sha256(
        "|".join("{}:{}".format(r.market, _canonical_payload_sha256(r.payload))
                 for r in sorted(results, key=lambda r: r.market)).encode("utf-8")
    ).hexdigest()

    # Idempotent digest-cache: unchanged inputs -> return the persisted card.
    card_json_path = None
    if out_dir is not None:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        card_json_path = out_dir / "HW1F_LIVE_CALIBRATION_PARAMETER_CARD.json"
        if card_json_path.exists() and not refresh:
            try:
                existing = json.loads(card_json_path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                existing = None
            if existing and existing.get("inputs_digest") == inputs_digest:
                existing["cached"] = True
                return existing

    market_blocks = [_calibrate_market(r) for r in results]

    provenances = sorted({b["provenance"] for b in market_blocks})
    unsigned_reason = UNSIGNED_REASON_TEMPLATE.format(
        provenances="/".join(provenances))

    gates: List[Dict[str, Any]] = []
    by_market = {b["market"]: b for b in market_blocks}
    if {"CNY", "HKD"} <= set(by_market):
        cny, hkd = by_market["CNY"], by_market["HKD"]
        gates.append(evaluate_g02_gate(
            cny["is_placeholder"], cny["diagnostics"]["rmse_bps"],
            hkd["is_placeholder"], hkd["diagnostics"]["rmse_bps"],
            rmse_threshold_bps=G02_RMSE_THRESHOLD_BPS,
        ).to_dict())
        gates.append(evaluate_g12_gate(
            [DataLineageRecord.from_dict(b["lineage"]) for b in market_blocks]
        ).to_dict())

    card: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "roadmap_item": "4.1 #2 - Execute HW1F swaption calibration on live/proxy quote set",
        "model_risk_refs": ["MR-001", "MR-008"],
        "inputs_digest": inputs_digest,
        "markets": market_blocks,
        "gates": gates,
        "unsigned": True,
        "unsigned_reason": unsigned_reason,
        "standards": [
            "SOA ASOP 56 3.4", "SOA ASOP 23", "IA TAS M 3.5/3.6",
            "IFoA APS X2 4.2",
        ],
        "cached": False,
    }

    if card_json_path is not None:
        card_json_path.write_text(
            json.dumps(card, indent=1, default=str), encoding="utf-8")
        md_path = card_json_path.with_suffix(".md")
        md_path.write_text(render_parameter_card_md(card), encoding="utf-8")
    return card


# ---------------------------------------------------------------------------
# 5. Markdown parameter card
# ---------------------------------------------------------------------------

def render_parameter_card_md(card: Dict[str, Any]) -> str:
    """Render the parameter card as a human-readable markdown report."""
    lines: List[str] = []
    lines.append("# HW1F Live/Proxy Swaption Calibration - Parameter Card")
    lines.append("")
    lines.append("> **UNSIGNED** - {}".format(card["unsigned_reason"]))
    lines.append("")
    lines.append("- Schema: `{}`".format(card["schema_version"]))
    lines.append("- Generated (UTC): {}".format(card["generated_utc"]))
    lines.append("- Roadmap item: {}".format(card["roadmap_item"]))
    lines.append("- Model-risk refs: {}".format(", ".join(card["model_risk_refs"])))
    lines.append("- Inputs digest: `{}`".format(card["inputs_digest"]))
    lines.append("")
    for blk in card["markets"]:
        p, d = blk["parameters"], blk["diagnostics"]
        lines.append("## {} ({}, as of {})".format(
            blk["market"], blk["provenance"], blk["as_of_date"]))
        lines.append("")
        lines.append("| Parameter | Value |")
        lines.append("|---|---|")
        lines.append("| a (mean reversion) | {:.6f} |".format(p["a"]))
        lines.append("| sigma_r (short-rate vol) | {:.6f} |".format(p["sigma_r"]))
        lines.append("| lambda_r (mkt price of risk) | {:.6f} |".format(p["lambda_r"]))
        lines.append("| r0 (initial short rate) | {:.6f} |".format(p["r0"]))
        lines.append("")
        lines.append("| Diagnostic | Value |")
        lines.append("|---|---|")
        lines.append("| Weighted SSE (bps^2) | {:.6e} |".format(
            d["sse_weighted_bps_sq"]))
        lines.append("| RMSE (bps) | {:.4f} |".format(d["rmse_bps"]))
        lines.append("| Max abs error (bps) | {:.4f} |".format(d["max_abs_error_bps"]))
        lines.append("| Converged ({}) | {} |".format(d["optimizer"], d["converged"]))
        lines.append("| Params at optimizer bound | {} |".format(
            ", ".join(d["params_at_bounds"]) or "none"))
        lines.append("| Quotes (active/total) | {}/{} |".format(
            d["n_quotes_active"], d["n_quotes_total"]))
        lines.append("| Source SHA-256 | `{}` |".format(blk["source_sha256"][:16] + "..."))
        lines.append("| Lineage approver | {} |".format(blk["lineage"]["approved_by"]))
        lines.append("")
    if card["gates"]:
        lines.append("## Production gates")
        lines.append("")
        lines.append("| Gate | Status | Evidence |")
        lines.append("|---|---|---|")
        for g in card["gates"]:
            lines.append("| {} | {} | {} |".format(
                g["gate_id"], g["status"], g["evidence"][:180]))
        lines.append("")
    lines.append("*Standards: {}.*".format("; ".join(card["standards"])))
    lines.append("")
    return "\n".join(lines)
