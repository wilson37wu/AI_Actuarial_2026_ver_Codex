"""
Path-Wise vs Current (Horizon-Level) TVOG Bridge — RB *and* TB Declaration
==========================================================================

Roadmap §4.1 item #8 (Limitation #4 — stochastic bonus declaration).  The
path-wise bonus-declaration work (Phase 25,
:mod:`par_model_v2.projection.pathwise_bonus_dynamics`) demonstrated the
recognition-lag *mechanism* for the **reversionary bonus (RB)** at the
SCR/VaR level.  This module carries that work into a **TVOG** (Time Value of
Options and Guarantees) framing, extends it to the **terminal bonus (TB)**,
and delivers the number the roadmap item asks for: a *quantified, documented
bridge from the CURRENT TVOG to the PATH-WISE TVOG*.

Two declaration bases (common random numbers)
---------------------------------------------
* ``horizon`` — the **CURRENT governed convention** (Phase 24 Task 3): the
  RB/TB cut is decided ONCE at the outer node from the *initial* coverage
  ratio ``CR_0`` and frozen for the whole projection.
* ``pathwise`` — the refinement: the RB cut is re-declared at EVERY inner
  step on the path-wise coverage ratio ``CR_t = A_t / L_t`` and the TB is
  re-declared at maturity on the *terminal* coverage ratio ``CR_T``.

``without`` (full target bonus) and ``max_cut`` (PRE floor) bracket the two.

TVOG definitions (risk-neutral / Q, single representative participating fund)
----------------------------------------------------------------------------
Assets follow a risk-neutral GBM (drift = the risk-free rate ``rf``), so the
discounted terminal asset is a Q-martingale — verified as a gate
(``martingale_ok``).  Two shortfall costs are reported per basis:

* ``tvog_guarantee``  = E^Q[ disc · max( L_T^RB − A_T , 0 ) ] — the **hard
  guarantee** (guaranteed accrual + *vested* RB) shortfall.  RB declaration
  flows in; more RB declared ⇒ higher floor ⇒ higher cost.
* ``tvog_declared``   = E^Q[ disc · max( L_T^RB·(1+TB_decl) − A_T , 0 ) ] —
  the **declared-benefit funding** shortfall (guaranteed accrual + declared
  RB + *declared* TB).  This is the measure that makes **TB declaration
  timing** bite (a frozen-high horizon TB stranded on a deteriorated path is
  expensive; the path-wise basis cuts it).

The bridge is the exact, additive reconciliation

    TVOG_pathwise − TVOG_horizon = Δ_healthy_nodes + Δ_stressed_nodes

partitioning outer nodes by ``CR_0`` against the rule trigger (healthy =
horizon never cuts; stressed = horizon already cut at t=0).  Both partition
sums are exact so the identity holds to floating point (asserted in tests).

Relation to the Phase 25 SCR pre-study (disclosed)
--------------------------------------------------
The Phase 25 pre-study reported path-wise **SCR** (a 99.5% *tail*) ABOVE the
horizon SCR (restoration lifts the tail).  A **TVOG** is a risk-neutral
*mean* cost, and path-wise re-declaration cuts over-declared bonuses on
deteriorating paths, so the mean-cost bridge can move OPPOSITE to the tail —
this module reports the signed bridge and both mechanism shares so the two
views reconcile rather than conflict.

SCOPE / PRODUCTION USE RESTRICTION
----------------------------------
EDUCATIONAL representative-single-fund diagnostic.  NOT the governed
portfolio TVOG headline (produced by the stochastic aggregation engine and
left byte-untouched).  Re-baselining the governed headline onto a path-wise
declaration basis stays OWNER-GATED.  Parameters are educational
placeholders; sign-off is automation-driven.  UNSIGNED pending APS X2 review.

Standards: SOA ASOP 56 §3.1 (model documentation), ASOP 7 §3.3 (management
actions / policyholder behaviour); IA TAS M §3.2 (market-consistent
valuation), §3.6 (assumption traceability); IFoA MCEV Principles §7 (TVOG).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np

from par_model_v2.projection.management_actions import ManagementActionRule
from par_model_v2.projection.pathwise_bonus_dynamics import retained_bonus_rate

SCHEMA = "pathwise-tvog-bridge-1.0"

#: Ordered declaration bases (common random numbers across all four).
BASES: Tuple[str, ...] = ("without", "horizon", "pathwise", "max_cut")


# ---------------------------------------------------------------------------
# Configuration (educational placeholders)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PathwiseTVOGConfig:
    """Risk-neutral representative participating-fund configuration.

    All parameters are educational placeholders.  ``rf`` is BOTH the
    risk-neutral asset drift and the discount rate (so the discounted asset is
    a Q-martingale).
    """

    n_outer: int = 4000
    n_inner: int = 100
    n_steps: int = 10
    rf: float = 0.02
    sigma: float = 0.15
    guaranteed_rate: float = 0.02
    rb_target: float = 0.02
    tb_target: float = 0.06
    cr0_center: float = 1.12
    cr0_sigma: float = 0.15
    l0: float = 100.0
    seed: int = 42
    healthy_cr_reference: Optional[float] = None  # default: rule.cr_trigger

    def __post_init__(self) -> None:
        if self.n_outer < 100:
            raise ValueError("n_outer must be >= 100")
        if self.n_inner < 10:
            raise ValueError("n_inner must be >= 10")
        if self.n_steps < 2:
            raise ValueError("n_steps must be >= 2 (path-wise needs a path)")
        if self.sigma <= 0.0 or self.cr0_sigma <= 0.0:
            raise ValueError("sigma and cr0_sigma must be positive")
        if self.rf < 0.0:
            raise ValueError("rf must be >= 0")
        if self.rb_target < 0.0 or self.tb_target < 0.0:
            raise ValueError("rb_target, tb_target must be >= 0")
        if self.l0 <= 0.0 or self.cr0_center <= 0.0:
            raise ValueError("l0 and cr0_center must be positive")

    def to_dict(self) -> Dict[str, float]:
        return {
            "n_outer": self.n_outer, "n_inner": self.n_inner,
            "n_steps": self.n_steps, "rf": self.rf, "sigma": self.sigma,
            "guaranteed_rate": self.guaranteed_rate, "rb_target": self.rb_target,
            "tb_target": self.tb_target, "cr0_center": self.cr0_center,
            "cr0_sigma": self.cr0_sigma, "l0": self.l0, "seed": self.seed,
            "healthy_cr_reference": self.healthy_cr_reference,
        }


# ---------------------------------------------------------------------------
# Core simulation (risk-neutral, common random numbers across bases)
# ---------------------------------------------------------------------------

def simulate_tvog_bases(
    cfg: PathwiseTVOGConfig, rule: ManagementActionRule
) -> Dict[str, object]:
    """Simulate the four declaration bases on COMMON random numbers.

    Returns, per basis, the per-outer-node discounted expected shortfall for
    both the hard-guarantee and the declared-benefit measures, plus the mean
    net liability and the path-wise mechanism diagnostics, plus the martingale
    check on the shared asset paths.
    """
    rng = np.random.default_rng(cfg.seed)
    # Initial coverage per outer node (lognormal, mean ~ cr0_center).
    cr0 = cfg.cr0_center * np.exp(
        cfg.cr0_sigma * rng.standard_normal(cfg.n_outer)
        - 0.5 * cfg.cr0_sigma ** 2
    )
    # Risk-neutral asset log-returns (drift rf), shared by every basis.
    z = rng.standard_normal((cfg.n_steps, cfg.n_outer, cfg.n_inner))
    log_step = (cfg.rf - 0.5 * cfg.sigma ** 2) + cfg.sigma * z
    disc = float(np.exp(-cfg.rf * cfg.n_steps))

    a0 = np.repeat((cr0 * cfg.l0)[:, None], cfg.n_inner, axis=1)
    a_paths = a0[None, ...] * np.exp(np.cumsum(log_step, axis=0))  # (steps,outer,inner)
    a_final = a_paths[-1]                                          # (outer, inner)

    # Martingale gate: E^Q[disc * A_T] == A_0 (to MC error).
    mart_ratio = float((a_final.mean(axis=1) * disc / (cr0 * cfg.l0)).mean())

    ret_h0 = retained_bonus_rate(rule, cr0)  # frozen horizon RB share per node
    eps = 1e-12
    out: Dict[str, object] = {
        "cr0": cr0, "disc": disc, "martingale_ratio": mart_ratio,
        "config": cfg.to_dict(), "rule": rule.to_dict(),
    }

    for basis in BASES:
        liab = np.full((cfg.n_outer, cfg.n_inner), cfg.l0)
        a_prev = a0.copy()
        prev_ret = None
        had_cut = np.zeros((cfg.n_outer, cfg.n_inner), dtype=bool)
        restored = np.zeros_like(had_cut)
        for t in range(cfg.n_steps):
            if basis == "without":
                ret = np.ones_like(liab)
            elif basis == "horizon":
                ret = np.repeat(ret_h0[:, None], cfg.n_inner, axis=1)
            elif basis == "max_cut":
                ret = np.full_like(liab, rule.pre_floor)
            else:  # pathwise: RB re-declared on the path-wise coverage ratio
                ret = retained_bonus_rate(rule, a_prev / liab)
                if prev_ret is not None:
                    restored |= had_cut & (ret > prev_ret + eps)
                had_cut |= ret < 1.0 - eps
                prev_ret = ret
            liab = liab * (1.0 + cfg.guaranteed_rate + cfg.rb_target * ret)
            a_prev = a_paths[t]

        # Terminal bonus declaration share by basis.
        if basis == "without":
            tb_ret = np.ones_like(liab)
        elif basis == "horizon":
            tb_ret = np.repeat(ret_h0[:, None], cfg.n_inner, axis=1)
        elif basis == "max_cut":
            tb_ret = np.full_like(liab, rule.pre_floor)
        else:  # pathwise TB on the terminal coverage ratio
            tb_ret = retained_bonus_rate(rule, a_final / liab)

        declared = liab * (1.0 + cfg.tb_target * tb_ret)
        shortfall_g = np.maximum(liab - a_final, 0.0)
        shortfall_d = np.maximum(declared - a_final, 0.0)

        out[basis] = {
            "tvog_guarantee_node": shortfall_g.mean(axis=1) * disc,
            "tvog_declared_node": shortfall_d.mean(axis=1) * disc,
            "net_liability_node": (liab - a_final).mean(axis=1) * disc,
        }
        if basis == "pathwise":
            out["pathwise_action_share"] = float(had_cut.mean())
            out["pathwise_restoration_share"] = float((had_cut & restored).mean())
    return out


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TVOGBasisRow:
    """TVOG figures for one declaration basis (mean over outer nodes)."""

    basis: str
    tvog_guarantee: float
    tvog_declared: float
    mean_net_liability: float

    def to_dict(self) -> Dict[str, object]:
        return {
            "basis": self.basis,
            "tvog_guarantee": round(self.tvog_guarantee, 6),
            "tvog_declared": round(self.tvog_declared, 6),
            "mean_net_liability": round(self.mean_net_liability, 6),
        }


@dataclass(frozen=True)
class TVOGBridgeLeg:
    """One additive bridge (current → path-wise) for a single measure."""

    measure: str                 # "guarantee" | "declared"
    tvog_current_horizon: float
    delta_healthy_nodes: float
    delta_stressed_nodes: float
    tvog_pathwise: float
    delta_total: float
    delta_pct_of_current: float
    identity_residual: float

    def to_dict(self) -> Dict[str, object]:
        return {
            "measure": self.measure,
            "tvog_current_horizon": round(self.tvog_current_horizon, 6),
            "delta_healthy_nodes": round(self.delta_healthy_nodes, 6),
            "delta_stressed_nodes": round(self.delta_stressed_nodes, 6),
            "tvog_pathwise": round(self.tvog_pathwise, 6),
            "delta_total": round(self.delta_total, 6),
            "delta_pct_of_current": round(self.delta_pct_of_current, 6),
            "identity_residual": self.identity_residual,
        }


@dataclass(frozen=True)
class PathwiseTVOGBridgeResult:
    """Full path-wise-vs-current TVOG bridge artifact."""

    schema: str
    run_timestamp: str
    config: Dict[str, float]
    rule: Dict[str, float]
    healthy_cr_reference: float
    healthy_node_share: float
    bases: Tuple[TVOGBasisRow, ...]
    bridge_guarantee: TVOGBridgeLeg
    bridge_declared: TVOGBridgeLeg
    martingale_ratio: float
    martingale_ok: bool
    bounds_ok: bool
    pathwise_action_share: float
    pathwise_restoration_share: float
    tail_vs_mean_note: str
    unsigned: bool = True
    unsigned_banner: str = (
        "UNSIGNED — educational representative single-fund TVOG bridge; NOT "
        "the governed portfolio TVOG headline. Re-baselining the governed "
        "headline onto a path-wise declaration basis is OWNER-GATED. Replace "
        "the placeholder fund parameters and obtain APS X2 review before use."
    )
    standard_references: Tuple[str, ...] = (
        "SOA ASOP 56 §3.1", "SOA ASOP 7 §3.3", "IA TAS M §3.2",
        "IA TAS M §3.6", "IFoA MCEV Principles §7",
    )

    def to_dict(self) -> Dict[str, object]:
        return {
            "schema": self.schema,
            "run_timestamp": self.run_timestamp,
            "config": self.config,
            "rule": self.rule,
            "healthy_cr_reference": self.healthy_cr_reference,
            "healthy_node_share": round(self.healthy_node_share, 6),
            "bases": [b.to_dict() for b in self.bases],
            "bridge_guarantee": self.bridge_guarantee.to_dict(),
            "bridge_declared": self.bridge_declared.to_dict(),
            "martingale_ratio": round(self.martingale_ratio, 8),
            "martingale_ok": self.martingale_ok,
            "bounds_ok": self.bounds_ok,
            "pathwise_action_share": round(self.pathwise_action_share, 6),
            "pathwise_restoration_share": round(self.pathwise_restoration_share, 6),
            "tail_vs_mean_note": self.tail_vs_mean_note,
            "unsigned": self.unsigned,
            "unsigned_banner": self.unsigned_banner,
            "standard_references": list(self.standard_references),
        }

    def content_digest(self) -> str:
        """Deterministic SHA-256 over the numeric content (ex-timestamp)."""
        payload = self.to_dict()
        payload.pop("run_timestamp", None)
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def markdown(self) -> str:
        rows = "\n".join(
            "| {} | {:,.4f} | {:,.4f} | {:,.4f} |".format(
                b.basis, b.tvog_guarantee, b.tvog_declared, b.mean_net_liability
            )
            for b in self.bases
        )
        g, d = self.bridge_guarantee, self.bridge_declared
        return (
            "### Path-wise vs current (horizon) TVOG bridge — RB + TB "
            "declaration\n\n"
            f"Risk-neutral representative fund (rf={self.config['rf']:.3%}, "
            f"σ={self.config['sigma']:.3f}, {int(self.config['n_outer'])}×"
            f"{int(self.config['n_inner'])} outer×inner, seed "
            f"{int(self.config['seed'])}). Martingale check "
            f"E^Q[disc·A_T]/A_0 = {self.martingale_ratio:.4f} "
            f"({'PASS' if self.martingale_ok else 'FAIL'}).\n\n"
            "| Basis | TVOG guarantee | TVOG declared | Mean net liab |\n"
            "|---|---:|---:|---:|\n"
            f"{rows}\n\n"
            "**Current convention = `horizon`** (Phase 24 Task 3: cut frozen "
            "at CR₀). **Refinement = `pathwise`** (RB re-declared each step, "
            "TB re-declared at maturity).\n\n"
            "Bridge (exact additive decomposition, partitioned by CR₀ vs "
            f"trigger {self.healthy_cr_reference:.3f}; healthy node share "
            f"{self.healthy_node_share:.1%}):\n\n"
            "| Measure | Current (horizon) | Δ healthy nodes | Δ stressed "
            "nodes | Path-wise | Δ total | Δ % of current |\n"
            "|---|---:|---:|---:|---:|---:|---:|\n"
            f"| Hard guarantee | {g.tvog_current_horizon:,.4f} | "
            f"{g.delta_healthy_nodes:+,.4f} | {g.delta_stressed_nodes:+,.4f} | "
            f"{g.tvog_pathwise:,.4f} | {g.delta_total:+,.4f} | "
            f"{g.delta_pct_of_current:+.3%} |\n"
            f"| Declared benefit | {d.tvog_current_horizon:,.4f} | "
            f"{d.delta_healthy_nodes:+,.4f} | {d.delta_stressed_nodes:+,.4f} | "
            f"{d.tvog_pathwise:,.4f} | {d.delta_total:+,.4f} | "
            f"{d.delta_pct_of_current:+.3%} |\n\n"
            f"Path-wise cut share {self.pathwise_action_share:.1%}; "
            f"cut-then-restore share {self.pathwise_restoration_share:.1%}. "
            f"{self.tail_vs_mean_note}\n\n"
            f"> {self.unsigned_banner}\n"
        )


# ---------------------------------------------------------------------------
# Bridge builder
# ---------------------------------------------------------------------------

def _bridge_leg(
    measure: str,
    node_key: str,
    sim: Dict[str, object],
    healthy_mask: np.ndarray,
) -> TVOGBridgeLeg:
    hz = np.asarray(sim["horizon"][node_key], dtype=float)
    pw = np.asarray(sim["pathwise"][node_key], dtype=float)
    n = hz.size
    tvog_h = float(hz.mean())
    tvog_p = float(pw.mean())
    diff = pw - hz
    # Exact additive partition by starting-node régime (means over ALL nodes).
    delta_healthy = float(diff[healthy_mask].sum() / n)
    delta_stressed = float(diff[~healthy_mask].sum() / n)
    delta_total = tvog_p - tvog_h
    residual = float(delta_total - (delta_healthy + delta_stressed))
    pct = (delta_total / abs(tvog_h)) if tvog_h != 0.0 else float("nan")
    return TVOGBridgeLeg(
        measure=measure,
        tvog_current_horizon=tvog_h,
        delta_healthy_nodes=delta_healthy,
        delta_stressed_nodes=delta_stressed,
        tvog_pathwise=tvog_p,
        delta_total=delta_total,
        delta_pct_of_current=pct,
        identity_residual=residual,
    )


def build_pathwise_tvog_bridge(
    cfg: Optional[PathwiseTVOGConfig] = None,
    rule: Optional[ManagementActionRule] = None,
) -> PathwiseTVOGBridgeResult:
    """Compute the full path-wise-vs-current TVOG bridge (RB + TB)."""
    cfg = cfg or PathwiseTVOGConfig()
    rule = rule or ManagementActionRule()
    sim = simulate_tvog_bases(cfg, rule)

    cr0 = np.asarray(sim["cr0"], dtype=float)
    healthy_cr = (
        cfg.healthy_cr_reference
        if cfg.healthy_cr_reference is not None
        else rule.cr_trigger
    )
    # "Healthy" outer nodes: horizon retains the FULL bonus (never cuts).
    healthy_mask = cr0 >= healthy_cr
    healthy_share = float(healthy_mask.mean())

    bases_rows: List[TVOGBasisRow] = []
    for b in BASES:
        node = sim[b]
        bases_rows.append(
            TVOGBasisRow(
                basis=b,
                tvog_guarantee=float(np.asarray(node["tvog_guarantee_node"]).mean()),
                tvog_declared=float(np.asarray(node["tvog_declared_node"]).mean()),
                mean_net_liability=float(np.asarray(node["net_liability_node"]).mean()),
            )
        )

    bridge_g = _bridge_leg("guarantee", "tvog_guarantee_node", sim, healthy_mask)
    bridge_d = _bridge_leg("declared", "tvog_declared_node", sim, healthy_mask)

    # Elementwise bounds: max_cut <= {horizon, pathwise} <= without (per node).
    def _bounds(node_key: str) -> bool:
        wo = np.asarray(sim["without"][node_key], dtype=float)
        mc = np.asarray(sim["max_cut"][node_key], dtype=float)
        hz = np.asarray(sim["horizon"][node_key], dtype=float)
        pw = np.asarray(sim["pathwise"][node_key], dtype=float)
        tol = 1e-9 * cfg.l0
        return bool(
            np.all(hz <= wo + tol) and np.all(hz >= mc - tol)
            and np.all(pw <= wo + tol) and np.all(pw >= mc - tol)
        )

    bounds_ok = bool(_bounds("tvog_guarantee_node") and _bounds("tvog_declared_node"))
    mart_ratio = float(sim["martingale_ratio"])
    martingale_ok = bool(abs(mart_ratio - 1.0) < 0.02)

    note = (
        "Path-wise re-declaration cuts over-declared bonuses on deteriorating "
        "paths, so the mean-cost (TVOG) bridge can move opposite to the "
        "Phase 25 path-wise SCR tail (restoration lifts the 99.5% tail while "
        "trimming the mean). Tail and mean are complementary, not conflicting."
    )

    return PathwiseTVOGBridgeResult(
        schema=SCHEMA,
        run_timestamp=datetime.now(timezone.utc).isoformat(),
        config=cfg.to_dict(),
        rule=rule.to_dict(),
        healthy_cr_reference=float(healthy_cr),
        healthy_node_share=healthy_share,
        bases=tuple(bases_rows),
        bridge_guarantee=bridge_g,
        bridge_declared=bridge_d,
        martingale_ratio=mart_ratio,
        martingale_ok=martingale_ok,
        bounds_ok=bounds_ok,
        pathwise_action_share=float(sim["pathwise_action_share"]),
        pathwise_restoration_share=float(sim["pathwise_restoration_share"]),
        tail_vs_mean_note=note,
    )


def pathwise_tvog_use_restrictions() -> Dict[str, object]:
    """Use restrictions for the path-wise TVOG bridge (disclosed)."""
    return {
        "classification": "EDUCATIONAL",
        "production_use": False,
        "governed_headline_touched": False,
        "owner_gated_followon": (
            "Re-baselining the governed portfolio TVOG/aggregation headline "
            "onto a path-wise RB/TB declaration basis."
        ),
        "restrictions": [
            "Single representative participating fund; not the 7-driver "
            "governed nested model.",
            "Risk-neutral GBM assets + placeholder guaranteed/bonus rates are "
            "educational; martingale property is verified but the level is "
            "illustrative.",
            "TB modelled as a uniform uplift on the guaranteed benefit; the "
            "declared-benefit shortfall is a funding-cost proxy, not a booked "
            "reserve.",
            "Declaration parameters (trigger/floor/PRE/targets) are the "
            "governed ManagementActionRule placeholders pending credentialled "
            "data + APS X2 review.",
        ],
    }


__all__ = [
    "SCHEMA",
    "BASES",
    "PathwiseTVOGConfig",
    "simulate_tvog_bases",
    "TVOGBasisRow",
    "TVOGBridgeLeg",
    "PathwiseTVOGBridgeResult",
    "build_pathwise_tvog_bridge",
    "pathwise_tvog_use_restrictions",
]
