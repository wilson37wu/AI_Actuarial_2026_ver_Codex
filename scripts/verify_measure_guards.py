"""Static evidence collector for G-05 / MR-004 measure guard verification.

This script avoids third-party dependencies so it can run in stripped-down
Python environments where numpy/pandas/scipy/pytest are unavailable.
It captures governance evidence that:
  1. RiskMetrics rejects non-P inputs at runtime.
  2. TVOGEngine rejects non-Q inputs at runtime.
  3. The targeted test files explicitly cover those guardrails.
  4. VR-S04 documents hard-fail behaviour rather than warnings.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8", errors="replace")


def find_markers(text: str, markers: List[str]) -> Dict[str, bool]:
    return {marker: marker in text for marker in markers}


def main() -> int:
    risk_metrics_text = read_text("par_model_v2/risk/risk_metrics.py")
    tvog_text = read_text("par_model_v2/projection/tvog.py")
    test_risk_metrics_text = read_text("tests/test_risk_metrics.py")
    test_tvog_text = read_text("tests/test_tvog.py")
    ia_validation_text = read_text("par_model_v2/validation/ia_validation.py")

    checks = {
        "risk_metrics_guard": find_markers(
            risk_metrics_text,
            [
                "if loss_distribution.measure != \"P\":",
                "RiskMetrics requires measure='P' (real-world) loss distributions.",
                "Q-measure losses are not valid inputs for VaR/ES.",
            ],
        ),
        "tvog_guard": find_markers(
            tvog_text,
            [
                "if scenarios.measure != Measure.Q:",
                "TVOGEngine requires Q-measure scenarios (risk-neutral).",
                "TVOG computed under P-measure is not ",
                "market-consistent. See ASOP 56",
            ],
        ),
        "risk_metrics_tests": find_markers(
            test_risk_metrics_text,
            [
                "def test_q_measure_warning(self):",
                "def test_risk_metrics_rejects_q_measure(self):",
                "with pytest.raises(ValueError, match=\"measure='P'\"):",
            ],
        ),
        "tvog_tests": find_markers(
            test_tvog_text,
            [
                "def _q_scenarios",
                "def _p_scenarios",
                "def test_vr_t01_p_measure_rejected(self):",
                "with pytest.raises(ValueError, match=\"Q-measure\"):",
            ],
        ),
        "vr_s04_requirement": find_markers(
            ia_validation_text,
            [
                "name=\"P / Q Measure Segregation Test\"",
                "Passing Q-measure scenarios to VaR/ES must raise",
                "passing P-measure to TVOG must raise ValueError.",
                "Production validation must confirm every consumer hard-fails on measure mismatches.",
            ],
        ),
    }

    all_pass = all(all(group.values()) for group in checks.values())
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": str(ROOT),
        "status": "PASS" if all_pass else "FAIL",
        "checks": checks,
        "summary": [
            "Static guard evidence captured without importing model dependencies.",
            "Runtime execution evidence remains separate and still requires a Python environment with numpy/pandas/scipy/pytest.",
        ],
    }

    print(json.dumps(report, indent=2))
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
