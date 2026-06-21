"""Phase UIL Task 2 (B2): optional user-input plumbing with governed fallbacks.

Single access point for ``model_inputs.json`` (the schema-versioned output of
``scripts/load_user_inputs.py``).  Every consumer follows the same contract:

* **No inputs file present** -> return ``None`` / governed defaults, so every
  governed read-out stays **bit-identical** to the fixture-driven pipeline.
* **Inputs file present but unreadable / wrong schema** -> raise loudly
  (``UserInputsError``).  Silent fallback on a *present-but-broken* file is
  never allowed.

Resolution order for the inputs file:

1. explicit ``path`` argument,
2. ``PAR_MODEL_INPUTS`` environment variable,
3. ``<repo_root>/production_run/model_inputs.json``,
4. ``<repo_root>/model_inputs.json``.

Frozen dependence parameters (copula df, grouped-t dfs) are **never** read
from user inputs; they remain governed and read-only.

Governed capital-path defaults (Phase 23/24 lineage):
confidence 0.995, relief sigma 0.225, relief alpha 0.7567,
benefit share (beta_fit) 0.8450.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

__all__ = [
    "UserInputsError",
    "GOVERNED_CAPITAL_PARAMS",
    "SUPPORTED_SCHEMA_MAJOR",
    "find_model_inputs",
    "exposure_overrides",
    "capital_params",
    "user_model_points",
    "run_settings",
]

_REPO_ROOT = Path(__file__).resolve().parents[1]
_ENV_VAR = "PAR_MODEL_INPUTS"
SUPPORTED_SCHEMA_MAJOR = 1

#: Governed defaults used whenever no user inputs are supplied.  These mirror
#: the frozen Phase 23/24 capital-path parameters and MUST NOT be edited
#: outside a governed change record.
GOVERNED_CAPITAL_PARAMS: Dict[str, float] = {
    "confidence": 0.995,
    "relief_sigma": 0.225,
    "relief_alpha": 0.7567,
    "benefit_share": 0.8450,
}


class UserInputsError(ValueError):
    """A model_inputs.json file exists but cannot be used (fail loud)."""


def _candidate_paths(path: Optional[os.PathLike] = None) -> List[Path]:
    if path is not None:
        return [Path(path)]
    cands: List[Path] = []
    env = os.environ.get(_ENV_VAR)
    if env:
        cands.append(Path(env))
    cands.append(_REPO_ROOT / "production_run" / "model_inputs.json")
    cands.append(_REPO_ROOT / "model_inputs.json")
    return cands


def find_model_inputs(path: Optional[os.PathLike] = None) -> Optional[Dict[str, Any]]:
    """Return the parsed user-inputs dict, or ``None`` if no file exists.

    Raises ``UserInputsError`` if a file is found but is corrupt JSON or has
    an unsupported ``schema_version`` major.  When ``path`` (or the env var)
    is given explicitly, a missing file is also an error -- the caller asked
    for that specific file.
    """
    explicit = path is not None or bool(os.environ.get(_ENV_VAR))
    for p in _candidate_paths(path):
        if not p.exists():
            if explicit:
                raise UserInputsError("model inputs file not found: %s" % p)
            continue
        try:
            with open(p, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            raise UserInputsError("cannot read model inputs %s: %s" % (p, exc)) from exc
        sv = str(data.get("schema_version", ""))
        try:
            major = int(sv.split(".")[0])
        except (ValueError, IndexError):
            raise UserInputsError(
                "model inputs %s: bad schema_version %r" % (p, sv))
        if major != SUPPORTED_SCHEMA_MAJOR:
            raise UserInputsError(
                "model inputs %s: unsupported schema_version %r (need major %d)"
                % (p, sv, SUPPORTED_SCHEMA_MAJOR))
        data["_source_path"] = str(p)
        return data
    return None


def exposure_overrides(inputs: Optional[Dict[str, Any]]) -> Optional[Dict[str, float]]:
    """Balance-sheet overrides for the liquidity exposure derivation.

    Returns ``{"backing_asset_mv", "illiquid_share", "forced_sale_fraction"}``
    or ``None`` when no user inputs are supplied.  Raises ``UserInputsError``
    if inputs are present but the balance-sheet block is incomplete.
    """
    if inputs is None:
        return None
    bs = inputs.get("balance_sheet") or {}
    try:
        mv = float(bs["backing_asset_mv"])
        share = float(bs["illiquid_share"])
        frac = float(bs["forced_sale_fraction"])
    except (KeyError, TypeError, ValueError) as exc:
        raise UserInputsError(
            "balance_sheet block incomplete in user inputs: %s" % exc) from exc
    if mv <= 0 or not (0.0 < share <= 1.0) or not (0.0 < frac <= 1.0):
        raise UserInputsError(
            "balance_sheet values out of range: mv=%r share=%r frac=%r"
            % (mv, share, frac))
    return {"backing_asset_mv": mv, "illiquid_share": share,
            "forced_sale_fraction": frac}


def capital_params(inputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Capital-path parameters with governed fallbacks.

    Returns confidence / relief_sigma / relief_alpha / benefit_share plus a
    ``"source"`` key (``"governed_defaults"`` or ``"user_inputs"``).  With no
    inputs the values are exactly ``GOVERNED_CAPITAL_PARAMS`` (bit-identical
    regression gate).
    """
    out: Dict[str, Any] = dict(GOVERNED_CAPITAL_PARAMS)
    out["source"] = "governed_defaults"
    if inputs is None:
        return out
    asm = inputs.get("assumptions") or {}
    touched = False
    for key in ("confidence", "relief_sigma", "relief_alpha", "benefit_share"):
        if key in asm and asm[key] is not None:
            val = float(asm[key])
            if val <= 0.0:
                raise UserInputsError("assumption %r must be positive, got %r"
                                      % (key, val))
            if key != "relief_sigma" and val > 1.0:
                raise UserInputsError("assumption %r must be <= 1, got %r"
                                      % (key, val))
            out[key] = val
            touched = True
    if touched:
        out["source"] = "user_inputs"
    return out


def user_model_points(inputs: Optional[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
    """The user's model-point rows, or ``None`` when not supplied."""
    if inputs is None:
        return None
    pts = inputs.get("portfolio")
    if not pts:
        return None
    return list(pts)


def run_settings(inputs: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Run settings (n_sim / seed / output_label), or ``None``."""
    if inputs is None:
        return None
    rs = inputs.get("run_settings")
    return dict(rs) if rs else None
