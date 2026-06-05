"""Model limitation cards for Phase 12 educational packaging."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


SOURCE_ID = "PHASE12-T2-LIMITATION-CARDS"
REPORT_VERSION = "1.0.0"


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class ModelLimitationCard:
    """A short, reviewable limitation disclosure for one model component."""

    limitation_id: str
    module_area: str
    module_name: str
    component_path: str
    severity: str
    limitation: str
    unsuitable_uses: Tuple[str, ...]
    current_mitigation: str
    required_upgrade: str
    owner_role: str
    standards_reference: Tuple[str, ...]
    source_id: str = SOURCE_ID
    status: str = "OPEN"
    notes: str = ""

    def __post_init__(self) -> None:
        for field_name in ("limitation_id", "module_area", "module_name", "component_path"):
            if not str(getattr(self, field_name)).strip():
                raise ValueError(f"{field_name} is required")
        if self.severity not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
            raise ValueError("severity must be LOW, MEDIUM, HIGH, or CRITICAL")
        if self.status not in {"OPEN", "MITIGATED", "ACCEPTED", "REQUIRES_REVIEW"}:
            raise ValueError("status must be OPEN, MITIGATED, ACCEPTED, or REQUIRES_REVIEW")
        if not self.unsuitable_uses:
            raise ValueError("unsuitable_uses must not be empty")
        if not self.standards_reference:
            raise ValueError("standards_reference must not be empty")

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass
class LimitationCardReport:
    """Collection of model limitation cards plus summary metadata."""

    report_id: str
    generated_at: str
    version: str
    cards: List[ModelLimitationCard]
    source_id: str = SOURCE_ID

    def by_area(self) -> Dict[str, int]:
        summary: Dict[str, int] = {}
        for card in self.cards:
            summary[card.module_area] = summary.get(card.module_area, 0) + 1
        return summary

    def by_severity(self) -> Dict[str, int]:
        summary: Dict[str, int] = {}
        for card in self.cards:
            summary[card.severity] = summary.get(card.severity, 0) + 1
        return summary

    @property
    def open_critical_count(self) -> int:
        return sum(1 for card in self.cards if card.severity == "CRITICAL" and card.status == "OPEN")

    def to_dict(self) -> Dict[str, object]:
        return {
            "report_id": self.report_id,
            "generated_at": self.generated_at,
            "version": self.version,
            "source_id": self.source_id,
            "by_area": self.by_area(),
            "by_severity": self.by_severity(),
            "open_critical_count": self.open_critical_count,
            "cards": [card.to_dict() for card in self.cards],
        }

    def to_markdown(self) -> str:
        lines = [
            "# Phase 12 Model Limitation Cards",
            "",
            f"**Report ID:** `{self.report_id}`  ",
            f"**Generated:** {self.generated_at}  ",
            f"**Open critical limitations:** {self.open_critical_count}  ",
            f"**Source ID:** {self.source_id}",
            "",
            "## Summary by Area",
            "",
            "| Area | Cards |",
            "|------|------:|",
        ]
        for area, count in sorted(self.by_area().items()):
            lines.append(f"| {area} | {count} |")

        lines += [
            "",
            "## Cards",
            "",
            "| ID | Area | Module | Severity | Status | Owner |",
            "|----|------|--------|----------|--------|-------|",
        ]
        for card in self.cards:
            lines.append(
                f"| {card.limitation_id} | {card.module_area} | {card.module_name} | "
                f"{card.severity} | {card.status} | {card.owner_role} |"
            )

        lines += ["", "## Detail", ""]
        for card in self.cards:
            lines += [
                f"### {card.limitation_id} - {card.module_name}",
                "",
                f"**Component:** `{card.component_path}`  ",
                f"**Severity:** {card.severity}  ",
                f"**Status:** {card.status}  ",
                f"**Owner:** {card.owner_role}",
                "",
                card.limitation,
                "",
                "**Unsuitable uses:** " + "; ".join(card.unsuitable_uses),
                "",
                "**Current mitigation:** " + card.current_mitigation,
                "",
                "**Required upgrade:** " + card.required_upgrade,
                "",
            ]
        return "\n".join(lines).rstrip() + "\n"

    def write_json(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return path

    def write_markdown(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_markdown(), encoding="utf-8")
        return path


def _card(
    limitation_id: str,
    module_area: str,
    module_name: str,
    component_path: str,
    severity: str,
    limitation: str,
    unsuitable_uses: Iterable[str],
    current_mitigation: str,
    required_upgrade: str,
    owner_role: str,
    standards_reference: Iterable[str],
    status: str = "OPEN",
    notes: str = "",
) -> ModelLimitationCard:
    return ModelLimitationCard(
        limitation_id=limitation_id,
        module_area=module_area,
        module_name=module_name,
        component_path=component_path,
        severity=severity,
        limitation=limitation,
        unsuitable_uses=tuple(unsuitable_uses),
        current_mitigation=current_mitigation,
        required_upgrade=required_upgrade,
        owner_role=owner_role,
        standards_reference=tuple(standards_reference),
        status=status,
        notes=notes,
    )


def default_model_limitation_cards() -> List[ModelLimitationCard]:
    """Return the Phase 12 ESG and HK liability limitation card catalogue."""
    refs = ("SOA ASOP 56 Sections 3.5-3.6", "IA TAS M Sections 3.5-3.6")
    return [
        _card(
            "ESG-LC-001",
            "ESG",
            "Hull-White 1F rate process",
            "par_model_v2/stochastic/esg_process.py::HullWhiteRateProcess",
            "CRITICAL",
            "HW1F parameters and starter curves are educational placeholders and are not calibrated to live swaption or OIS markets.",
            ("TVOG sign-off", "market-consistent embedded value", "regulatory reserves"),
            "Curve IDs, source IDs, Q-measure labels, and martingale evidence scaffolds are retained.",
            "Calibrate to approved curve and swaption data; attach fit diagnostics and owner sign-off.",
            "Market Assumption Owner",
            refs,
        ),
        _card(
            "ESG-LC-002",
            "ESG",
            "G2++ rate prototype",
            "par_model_v2/stochastic/esg_process.py::G2PlusRateProcess",
            "HIGH",
            "The two-factor rate process is a transparent prototype and has not been fitted to a full volatility surface.",
            ("curve-shape hedging", "basis-risk capital", "production ALM"),
            "Factor paths and correlation diagnostics are exposed for validation examples.",
            "Fit to swaption surface by expiry/tenor and validate curve-shape stresses.",
            "Market Assumption Owner",
            refs,
        ),
        _card(
            "ESG-LC-003",
            "ESG",
            "Regional equity GBM factors",
            "par_model_v2/stochastic/esg_process.py::RegionalEquityFactor",
            "HIGH",
            "Equity factors use constant-volatility GBM and do not capture stochastic volatility, jumps, or crash clustering.",
            ("equity-option pricing", "capital tail calibration", "hedging strategy design"),
            "Regional source IDs and P-measure backtest scaffolds disclose placeholder status.",
            "Replace with governed historical/implied calibration and consider stochastic volatility or jump diffusion.",
            "Market Assumption Owner",
            refs,
        ),
        _card(
            "ESG-LC-004",
            "ESG",
            "FX translation factors",
            "par_model_v2/stochastic/esg_process.py::FXSpotProcess",
            "HIGH",
            "FX factors use a single-pair lognormal process and omit peg-break, basis, capital-control, and intervention dynamics.",
            ("foreign-currency TVOG", "currency hedging", "regulatory capital"),
            "FX use is optional, source-tagged, and limited to educational HKD reporting examples.",
            "Calibrate to approved FX histories, forward points, and stress regimes by currency pair.",
            "Market Assumption Owner",
            refs,
        ),
        _card(
            "ESG-LC-005",
            "ESG",
            "Static correlation matrix",
            "par_model_v2/stochastic/esg_process.py::CorrelationMatrixValidator",
            "HIGH",
            "Correlations are static and PSD repair is evidence, not an approved automatic override.",
            ("tail-dependence modelling", "stress capital", "cross-market hedge design"),
            "Validation reports preserve original and repaired matrices with adjustment diagnostics.",
            "Add regime-specific or dynamic correlation calibration and governance approval for any repair.",
            "Model Risk Owner",
            refs,
        ),
        _card(
            "ESG-LC-006",
            "ESG",
            "P-measure backtest scaffold",
            "par_model_v2/stochastic/esg_process.py::PMeasureBacktestValidator",
            "HIGH",
            "Backtesting logic does not fetch, clean, approve, or version live market reference data.",
            ("model validation sign-off", "capital model approval", "external disclosure"),
            "The validator records diagnostics when governed reference data is supplied by callers.",
            "Connect to approved calibration datasets and archive exception reports by valuation date.",
            "Independent Validator",
            refs,
        ),
        _card(
            "HK-LC-001",
            "Liability",
            "HK cash dividend mechanics",
            "par_model_v2/projection/hk_participating.py::HKCashDividendMechanics",
            "HIGH",
            "Cash dividend mechanics are educational and do not represent PRE policy, board declarations, or insurer filing rules.",
            ("pricing", "policyholder illustration", "regulatory filing"),
            "Product, source, and limitation IDs are carried through schedules and reporting views.",
            "Calibrate to approved product filing, board declaration policy, and supportability evidence.",
            "Liability Assumption Owner",
            refs,
        ),
        _card(
            "HK-LC-002",
            "Liability",
            "HK reversionary bonus mechanics",
            "par_model_v2/projection/hk_participating.py::HKReversionaryBonusMechanics",
            "HIGH",
            "Vested and terminal bonus examples are simplified and do not prove future declaration supportability.",
            ("pricing", "bonus declaration", "IFRS 17 cash-flow sign-off"),
            "Guarantee split and terminal-bonus status are explicit in reporting outputs.",
            "Tie mechanics to product filing, asset-share policy, and governance-approved management actions.",
            "Liability Assumption Owner",
            refs,
        ),
        _card(
            "HK-LC-003",
            "Liability",
            "Declaration assumption hooks",
            "par_model_v2/projection/hk_participating.py::HKDeclarationAssumption",
            "CRITICAL",
            "Declaration rates are placeholder sensitivities and are not derived from supportable surplus or PRE governance.",
            ("bonus declaration", "policyholder communication", "reserve sign-off"),
            "Sensitivity labels, floors, caps, source IDs, and limitation IDs are explicit.",
            "Replace placeholders with board-approved declaration basis and supportable range analysis.",
            "Liability Assumption Owner",
            refs,
        ),
        _card(
            "HK-LC-004",
            "Liability",
            "Asset-share support tests",
            "par_model_v2/projection/hk_participating.py::HKAssetShareSupportReport",
            "MEDIUM",
            "Support tests are deterministic and do not capture stochastic ALM, liquidity, or management-action feasibility.",
            ("stochastic bonus supportability", "liquidity adequacy", "capital planning"),
            "Final support margin and sensitivity labels are retained at policy level.",
            "Run stochastic asset-share support with calibrated ESG and liquidity stress scenarios.",
            "Liability Assumption Owner",
            refs,
        ),
        _card(
            "HK-LC-005",
            "Liability",
            "Liability reporting views",
            "par_model_v2/projection/hk_participating.py::HKLiabilityReportingPack",
            "HIGH",
            "Reserve, TVOG, and management summaries are educational views and are not statutory HKRBC or IFRS 17 bases.",
            ("statutory reporting", "external audit", "management bonus approval"),
            "Missing Q-measure TVOG evidence is labelled rather than substituted with deterministic proxies.",
            "Map to approved valuation basis, accounting policy, and reporting close controls.",
            "Reporting Actuary",
            refs,
        ),
    ]


def build_limitation_card_report(
    module_area: Optional[str] = None,
    severity: Optional[str] = None,
) -> LimitationCardReport:
    """Build a limitation-card report, optionally filtered by area/severity."""
    cards = default_model_limitation_cards()
    if module_area:
        area = module_area.lower()
        cards = [card for card in cards if card.module_area.lower() == area]
    if severity:
        sev = severity.upper()
        cards = [card for card in cards if card.severity == sev]
    return LimitationCardReport(
        report_id="P12-LIMIT-" + _now_utc().replace("-", "").replace(":", "").replace("Z", ""),
        generated_at=_now_utc(),
        version=REPORT_VERSION,
        cards=cards,
    )


def write_default_limitation_cards(output_dir: str | Path) -> LimitationCardReport:
    """Write JSON and Markdown limitation-card reports to an output directory."""
    report = build_limitation_card_report()
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    report.write_json(out / "phase12_model_limitation_cards.json")
    report.write_markdown(out / "phase12_model_limitation_cards.md")
    return report


__all__ = [
    "LimitationCardReport",
    "ModelLimitationCard",
    "build_limitation_card_report",
    "default_model_limitation_cards",
    "write_default_limitation_cards",
]
