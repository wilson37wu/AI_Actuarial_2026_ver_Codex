# Design Spec — Asset–ESG Path Coupling

**Document ID:** `DESIGN-ASSET-ESG-COUPLING-2026`
**Date:** 2026-06-23
**Status:** Actionable design proposal (Tier-1 #2)
**Owner area:** `par_model_v2/projection/*`, consumes `par_model_v2/stochastic/*`
**Companion docs:** `INDUSTRY_BENCHMARK_REVIEW.md`, `DEEP_DIVE_ESG_CALIBRATION.md`

---

## 1. Problem statement

The model discounts liabilities along each stochastic scenario, but **assets do not follow the same
scenario paths**. Concretely:

| Where | Current behaviour | Evidence |
|---|---|---|
| Asset-share recursion | Grows at a flat `r_proxy = discount_rate / 12`, explicitly *"no ESG"* | `monthly_projection.py:234-235`, accumulation at `:277` |
| Asset cashflows | Static `annual_yield` per class + flat `reinvest_at_rate`; hard-coded fallbacks (Govt 3.2%, Credit 3.8%, Equity 6% growth, Cash 2%) | `monthly_projection.py:382-468` |
| Dynamic ALM engine | `step()/run()` apply a **single static `annual_returns` dict every period** | `dynamic_alm.py:300-360` |
| TVOG | Per-scenario discounting of *guaranteed* cashflows only; asset side / bonus not on the path | `tvog.py:83-160` |

**Consequence.** Surrender values, terminal bonus, dividend/RB declarations, and management actions all
depend on asset share — but asset share is deterministic. So the model cannot capture the core ALM
feedback that Prophet ALS / AXIS exist to model: *when rates fall and equities crash, earned returns
fall, the asset share falls, bonuses are cut, surrenders change, and the cost of guarantees rises — all
on the same scenario.* Without coupling, TVOG and economic capital are understated and asset-liability
interactions are invisible.

**Goal.** Make asset returns, reinvestment, asset share, and bonus declarations **functions of the ESG
scenario**, so a single scenario drives both sides of the balance sheet — while preserving exact
backward compatibility for the deterministic case.

---

## 2. Design principles

1. **Single source of economic truth.** All asset returns derive from the same `ScenarioSet` that drives
   discounting. No second, independent return assumption.
2. **No-arbitrage / deflator consistency.** Under Q, the discounted total return of each tradable asset
   must be a martingale (priced off the same curve used to discount). This is testable and is the gate.
3. **Backward compatible.** A degenerate (zero-vol / flat) scenario must reproduce today's numbers
   bit-for-bit. Existing call sites keep working unchanged (`scenario_path=None` → current behaviour).
4. **Vectorised by construction.** Operate on `[N_scenarios, T]` arrays. Assets now run *inside* the
   stochastic loop, so per-scenario Python loops are not acceptable at scale.
5. **Governed.** New parameters (spread duration, default assumptions, smoothing) are assumptions with
   limitation cards and sign-off, like every other.

---

## 3. ESG inputs consumed

From each scenario in `ScenarioSet` (`esg_process.py`), per month `m`:

| Symbol | Source | Field |
|---|---|---|
| `r[m]` short rate | HW1F / G2++ | short-rate path |
| `y(t)[m]` zero curve | HW1F closed-form `P(t,T)` | reprice bonds (duration proxy or full curve) |
| `R_eq[m]` equity total return | GBM / Merton | equity index path |
| `s[m]` credit spread | CIR++ | `credit_spread.py` |
| `fx[m]` (optional) | lognormal FX | for non-HKD assets |

These are already generated; this design only *consumes* them. No ESG change required.

---

## 4. Proposed architecture

### 4.1 New module: `projection/asset_return_model.py`

A pure, vectorised mapping **ESG paths → per-asset-class total returns**. No engine state, fully testable.

```python
# Illustrative signatures — not final code.

@dataclass(frozen=True)
class AssetClassParams:
    """Per-class repricing parameters (assumptions; governed)."""
    asset_class: str            # 'Govt' | 'Credit' | 'Equity' | 'Cash'
    effective_duration: float   # for rate-driven price change
    spread_duration: float = 0.0
    base_spread: float = 0.0    # carry over risk-free (Credit)
    annual_default_loss: float = 0.0   # expected default × LGD (Credit)
    dividend_yield: float = 0.0        # Equity income component

class AssetReturnModel:
    def __init__(self, params: dict[str, AssetClassParams]): ...

    def monthly_total_returns(
        self,
        short_rate: np.ndarray,      # shape [N, T] or [T]
        equity_return: np.ndarray,   # shape [N, T] or [T]
        credit_spread: np.ndarray,   # shape [N, T] or [T]
    ) -> dict[str, np.ndarray]:      # {class: returns[N, T]}
        """Total monthly return per asset class, vectorised over scenarios."""
```

**Return definitions (monthly, total return):**

- **Cash:** `r_cash[m] = short_rate[m] / 12`.
- **Govt bond:** carry + price change from rate moves
  `r_govt[m] = y_short[m]/12  −  duration × Δy[m]`
  where `Δy[m]` is the change in the relevant-tenor zero yield implied by the HW1F curve. (Phase A may
  use an effective-duration proxy; Phase D upgrades to full curve repricing via `P(t,T)`.)
- **Credit bond:** govt return + spread carry − spread price impact − expected default loss
  `r_credit[m] = r_govt[m] + base_spread/12 − spread_duration × Δs[m] − annual_default_loss/12`.
- **Equity:** the ESG total-return path directly (already includes dividend + capital + jumps)
  `r_equity[m] = R_eq[m]` (or split into `dividend_yield/12` + price path if income is needed separately).

This replaces the hard-coded constants at `monthly_projection.py:444-468` with scenario-driven returns,
and the static SAA `annual_returns` dict at `dynamic_alm.py:303`.

### 4.2 Portfolio earned rate

Given the SAA weights `w` (from `SAAPolicy`, `dynamic_alm.py:96`) the **earned portfolio return** each
month, per scenario, is:

```
r_earned[N, m] = Σ_class  w_class · r_class[N, m]
```

This single series is what the asset-share recursion and bonus mechanism consume.

### 4.3 Refactors to existing code (backward-compatible)

| # | File / function | Change | Compatibility |
|---|---|---|---|
| R1 | `monthly_projection.py` asset-share recursion (`:234`,`:277`) | Replace `r_proxy` constant with `r_earned[m]` when a scenario is supplied | `scenario=None` ⇒ keep flat `r_proxy` |
| R2 | `project_asset_cashflows` (`:382`) | Add optional `scenario_returns: dict[str,np.ndarray] \| None`; when present, derive monthly income/reinvestment from it instead of static `annual_yield`/`reinvest_at_rate` | default `None` ⇒ unchanged |
| R3 | `DynamicALMEngine.step/run` (`:300`,`:356`) | Accept a **per-period** returns sequence (or a callable `m → returns`) in addition to the static dict | static dict path unchanged |
| R4 | `project_liability_cashflows` (`:182`) | Thread an optional `scenario_path` so surrender value / terminal bonus use scenario asset share | default `None` ⇒ unchanged |
| R5 | Bonus / RB declaration (`pathwise_bonus_dynamics.py`, `management_actions.py`) | Link declared rate + coverage-ratio trigger to the *scenario* earned rate / asset share | reduces to current rule at flat returns |

### 4.4 New: market-consistent TVOG-with-assets

Add a TVOG variant in `tvog.py` (or a sibling) where, per Q-scenario:

1. Build the scenario discount curve (existing `_scenario_discount_factors`, `tvog.py:83`).
2. Drive asset share / bonus / management actions with `AssetReturnModel` on the **same** scenario.
3. Value the **net** cost of guarantees (guarantee shortfall after asset-side dynamics and bonus cuts).

`TVOG_with_assets = E^Q[ PV(guarantee shortfall | assets follow scenario) ] − deterministic base`.

This is the figure Prophet ALS / AXIS produce and the current `tvog.py` cannot, because it ignores the
asset side.

---

## 5. Validation & acceptance gates

| Gate | Test | Pass criterion |
|---|---|---|
| **G-AC1 Backward compat** | Run with a zero-vol / flat scenario | Asset share, cashflows, TVOG match current outputs to ≤1e-9 (golden test) |
| **G-AC2 Q-martingale (deflator)** | Discounted total asset value per Q-scenario | Mean ≈ initial value within Monte-Carlo k-σ band (reuse the ZCB-martingale harness in `esg_process.py`) |
| **G-AC3 Fund conservation** | Per scenario: ΔFund = premiums − benefits − expenses + investment income | Residual ≤ 1e-6 of fund |
| **G-AC4 Monotonicity** | TVOG vs guarantee level; bonus cut vs coverage ratio | Signs/monotonicity preserved (reuse `multi_driver_proxy_validation` style checks) |
| **G-AC5 Sensitivity** | TVOG-with-assets vs equity vol, duration, spread | Directionally correct, documented (feeds Layer-4 validation) |

G-AC1 and G-AC2 are the non-negotiable gates: backward compatibility and no-arbitrage.

---

## 6. Phasing (each phase: code + tests + governance note)

- **Phase A — `AssetReturnModel` (pure function).** Implement §4.1 + unit tests incl. analytic checks
  (flat scenario ⇒ constant returns). No engine change. *Lowest risk, immediately testable.*
- **Phase B — asset cashflows opt-in (R2).** Wire scenario returns into `project_asset_cashflows`;
  golden test G-AC1.
- **Phase C — scenario-earned asset share + bonus (R1, R4, R5).** Asset share, surrender, terminal bonus
  and RB declaration follow the scenario; add G-AC3.
- **Phase D — ALM engine scenario run + TVOG-with-assets (R3, §4.4).** Full coupled stochastic
  projection; add G-AC2, G-AC4.
- **Phase E — validation, sensitivity, sign-off.** G-AC5, limitation cards updated, Assumption-Owner
  `ChangeRecord`, retire the *"no ESG"* limitation.

---

## 7. Governance & assumptions introduced

New governed assumptions (each needs a limitation card + sign-off, consistent with
`governance/limitation_cards.py`):

- Effective duration and spread duration per asset class (repricing sensitivities).
- Credit base spread and expected default loss (carry and credit cost).
- Bonus-smoothing / earned-rate averaging window for declarations.

Calibration of these ties into `DEEP_DIVE_ESG_CALIBRATION.md` (durations from the asset portfolio;
default assumptions from credit experience). Until calibrated, mark them placeholder (MR-001 family) so
the coupling does not silently inherit unsupported parameters.

---

## 8. Performance considerations

Coupling moves the asset calculation *inside* the stochastic loop, multiplying cost by `N_scenarios`.
Mitigations, by priority:

1. **Vectorise** `AssetReturnModel` over `[N, T]` (NumPy) — no per-scenario Python loops (principle 4).
2. **Reuse the proxy/LSMC path** for tail capital: fit the proxy on coupled inner valuations so the
   expensive nested run is sampled, not exhaustive (`nested_stochastic_tvog.py`, `mlmc_inner_estimator.py`).
3. **Chunk + distribute** across scenarios using the existing `execution/distributed_executor.py` and
   `chunked_processor.py`.
4. Consider Numba/JIT for the asset-share recursion if it remains a hotspot after vectorisation.

---

## 9. Benchmark alignment

| Capability | Prophet ALS / AXIS | After this design |
|---|---|---|
| Assets & liabilities on one scenario | ✅ core feature | ✅ (Phase C–D) |
| Dynamic reinvestment on simulated curves | ✅ | ✅ (R2, full curve in Phase D) |
| Earned-rate-driven crediting / bonus | ✅ | ✅ (R5) |
| Market-consistent TVOG net of asset dynamics | ✅ | ✅ (§4.4) |
| Stochastic asset returns by class | ✅ | ✅ (§4.1) |
| Hedging / derivative overlay feedback | ✅ | 🟡 future (hook via `derivatives.py`) |

This closes the **single largest ALM credibility gap** identified in the benchmark and makes the existing
copula-aggregation and MLMC/TVOG machinery operate on economically coherent inputs.

---

## 10. Summary

- **Root cause:** assets grow at a flat proxy rate, decoupled from the scenarios that drive discounting
  (`monthly_projection.py:234-277`, `dynamic_alm.py:300-360`).
- **Fix:** a vectorised `AssetReturnModel` mapping ESG paths to per-class returns, threaded through asset
  cashflows, asset share, bonus declaration, and a new asset-aware TVOG — all behind opt-in
  `scenario` arguments that preserve exact backward compatibility.
- **Guardrails:** backward-compat golden test (G-AC1) and Q-martingale deflator test (G-AC2) are the
  gates; fund-conservation, monotonicity and sensitivity complete the validation set.
- **Sequencing:** five low-risk phases, starting with a pure, unit-tested return model.
