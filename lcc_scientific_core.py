"""Referenced scientific Life-Cycle Costing core.

Publication rule:
- pure computation only;
- no Streamlit imports;
- no project defaults masquerading as evidence;
- every row carries source provenance;
- benefits are excluded from LCC;
- residual/recovery is credited exactly once.

CANONICAL IDENTITY
------------------
    LCC_NPV = PV(Construction)
            + PV(Operation)
            + PV(Maintenance & Renewal)
            + PV(End of Life)
            - PV(Residual / Recovery Value)

Benefits (jobs, time savings, avoided CO2, economic multiplier, noise, land use)
NEVER reduce LCC_NPV. They belong to a separately named Cost-Benefit module.

EVIDENCE LABELS USED IN THIS FILE
---------------------------------
REF-VERIFIED-Q1         peer-reviewed source, journal verified SJR/Scopus 2024 Q1.
METHOD-REFERENCE        official standard / professional standard; NOT called Q1.
REF-DERIVED             equation assembled from several authoritative sources; it is
                        NOT presented as copied verbatim from one paper.
PROJECT-SOURCE-REQUIRED value must come from the project/Egypt geography; a foreign
                        paper cannot supply it.
SOURCE-OPEN             source still missing or not independently verified.
SCENARIO-ONLY           exploratory only; never a publication headline.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict


ALLOWED_PHASES = {
    "construction",
    "operation",
    "maintenance_renewal",
    "end_of_life",
}

ALLOWED_DISCOUNT_BASIS = {"real", "nominal"}

# Only these evidence classes can carry a publication claim. REF-PROXY may be
# computed for diagnostics but never satisfies the publication source gate.
PUBLICATION_ACCEPTABLE_EVIDENCE = {
    "PROJECT-SPECIFIC",
    "REF-VERIFIED-Q1",
    "METHOD-REFERENCE",
}


class ScientificLCCInputError(ValueError):
    """Raised when the LCC model would otherwise use missing or untraceable data."""


@dataclass(frozen=True)
class CostRow:
    """One dated, sourced cost activity in the LCC ledger.

    Construction, electricity, labour, station OPEX, inspection, replacement,
    demolition, transport and disposal are all representable as
    quantity x unit cost with independent year, escalation and provenance.
    """

    cost_id: str
    phase: str
    category: str
    asset: str
    activity: str
    project_year: int
    calendar_year: int
    quantity: float
    unit: str
    unit_cost_base: float
    currency: str
    price_base_year: int
    escalation_rate: float
    source_file: str
    source_location: str
    geography: str
    evidence_status: str
    note: str = ""


@dataclass(frozen=True)
class ResidualRow:
    """Residual / recovery / salvage / reuse REVENUE, entered as a positive amount.

    It lives in its own collection so the main identity can subtract its present
    value exactly ONCE. It must never also appear as a negative end-of-life cost.
    """

    residual_id: str
    asset: str
    activity: str
    project_year: int
    calendar_year: int
    amount_base: float
    currency: str
    price_base_year: int
    escalation_rate: float
    source_file: str
    source_location: str
    geography: str
    evidence_status: str
    note: str = ""


@dataclass(frozen=True)
class LCCModel:
    """A complete LCC run: one analysis period, one currency, one discount basis.

    The discount rate carries its OWN provenance because a model-level rate is as
    much an evidence claim as any row-level number, and Q1 literature supports the
    method rather than the numerical rate for this project.
    """

    analysis_base_year: int
    analysis_period_years: int
    currency: str
    discount_rate: float
    discount_basis: str
    discount_source_file: str
    discount_source_location: str
    discount_evidence_status: str
    cost_rows: tuple[CostRow, ...]
    residual_rows: tuple[ResidualRow, ...]


def _finite(x: float, field: str) -> float:
    x = float(x)
    if not math.isfinite(x):
        raise ScientificLCCInputError(f"{field} must be finite")
    return x


def _validate_rate(rate: float, field: str) -> float:
    rate = _finite(rate, field)
    if rate <= -1.0:
        raise ScientificLCCInputError(f"{field} must be > -1")
    return rate


def _validate_project_year(year: int, N: int, field: str) -> int:
    year = int(year)
    if year < 0 or year > int(N):
        raise ScientificLCCInputError(
            f"{field}={year} outside analysis period 0..{N}"
        )
    return year


def _source_complete(source_file: str, source_location: str, evidence_status: str) -> bool:
    """Provenance is complete only with a file, an exact location inside it, and an
    evidence class that is acceptable for publication. A blank or SOURCE-OPEN /
    SCENARIO-ONLY row keeps the calculation available for diagnostics but fails the gate.
    """
    return bool(
        str(source_file).strip()
        and str(source_location).strip()
        and evidence_status in PUBLICATION_ACCEPTABLE_EVIDENCE
    )


def present_value(future_amount: float, project_year: int, discount_rate: float) -> float:
    # METHOD-REFERENCE
    # Authors/Organization: ASTM International
    # Title: "Standard Practice for Measuring Life-Cycle Costs of Buildings and Building Systems"
    # Journal/Standard: ASTM E917-17(2023)
    # Year/Version: 2023 reapproval of the 2017 edition
    # DOI/Identifier: 10.1520/E0917-17R23
    # Role: establishes the present-value treatment of life-cycle cash flows over an
    #       agreed study period.
    # Limitation: it does NOT supply the numerical discount rate for the Cairo project.
    #
    # METHOD-REFERENCE
    # Authors/Organization: International Organization for Standardization (ISO)
    # Title: "Buildings and constructed assets — Service life planning — Part 5: Life-cycle costing"
    # Journal/Standard: ISO 15686-5:2017, Edition 2
    # Year/Version: 2017
    # DOI/Identifier: ISO 15686-5:2017
    # Role: agreed analysis period and cash flows from acquisition through disposal.
    # Limitation: it does NOT establish any project-specific cost or rate.
    #
    # REF-DERIVED equation used here:
    #     PV_t = FutureCost_t / (1 + r)^t
    amount = _finite(future_amount, "future_amount")
    r = _validate_rate(discount_rate, "discount_rate")
    t = int(project_year)
    if amount < 0:
        raise ScientificLCCInputError("future_amount must be non-negative")
    if t < 0:
        raise ScientificLCCInputError("project_year must be >= 0")
    return amount / ((1.0 + r) ** t)


def escalate_cost(
    base_cost: float,
    escalation_rate: float,
    years_from_price_base: int,
    discount_basis: str,
) -> float:
    # REF-DERIVED | Q1-SUPPORTED
    # Authors/Organization: Mona AbouHamad; Metwally Abu-Hamd
    # Title: "Framework for construction system selection based on life cycle cost and
    #        sustainability assessment"
    # Journal/Standard: Journal of Cleaner Production 241, 118397
    # Year/Version: 2019
    # DOI/Identifier: 10.1016/j.jclepro.2019.118397
    # Role: LCC framework including inflation/interest and discounting of future costs.
    # Limitation: its case-study rates are not Cairo/project rates.
    #
    # REF-DERIVED | Q1-SUPPORTED — secondary economic-consistency support
    # Authors/Organization: W. Hill Balliet; Patrick Balducci; Venkat Durvasulu; Thomas Mosier
    # Title: "Determining the profitability of energy storage over its life cycle using
    #        levelized cost of storage"
    # Journal/Standard: Energy Economics 142, 108174
    # Year/Version: 2025
    # DOI/Identifier: 10.1016/j.eneco.2024.108174
    # Role: life-cycle economic consistency and repeatable escalation/discounting architecture.
    # Limitation: not rail-specific, and supplies no project escalation rate.
    #
    # PROJECT-SOURCE-REQUIRED: the numerical escalation rate used for Cairo/project costs.
    #
    # REF-DERIVED equation:
    #     C_t = C_0 * (1 + g)^Delta
    base_cost = _finite(base_cost, "base_cost")
    g = _validate_rate(escalation_rate, "escalation_rate")
    delta = int(years_from_price_base)

    if base_cost < 0:
        raise ScientificLCCInputError("base_cost must be non-negative")
    if delta < 0:
        raise ScientificLCCInputError("calendar_year precedes price_base_year")
    if discount_basis not in ALLOWED_DISCOUNT_BASIS:
        raise ScientificLCCInputError(
            f"discount_basis must be one of {sorted(ALLOWED_DISCOUNT_BASIS)}"
        )

    # v1 convention:
    # real = constant-price cash flows, so no nominal escalation is allowed.
    # This deliberately BLOCKS the silent mixing of nominal escalation with a real
    # discount rate, which would double-count inflation.
    if discount_basis == "real":
        if abs(g) > 1e-12:
            raise ScientificLCCInputError(
                "Real basis requires escalation_rate=0 in v1. "
                "Use nominal basis for nominal escalation, or add an explicitly "
                "sourced real differential escalation method later."
            )
        return base_cost

    return base_cost * ((1.0 + g) ** delta)


def cost_row_base_amount(row: CostRow) -> float:
    # REF-VERIFIED-Q1
    # Authors/Organization: Gu-Taek Kim; Kyoon-Tai Kim; Du-Heon Lee; Choong-Hee Han;
    #                       Hyun-Bae Kim; Jin-Taek Jun
    # Title: "Development of a life cycle cost estimate system for structures of light
    #        rail transit infrastructure"
    # Journal/Standard: Automation in Construction 19(3), 308-325; SJR 2024 Q1
    # Year/Version: 2010
    # DOI/Identifier: 10.1016/j.autcon.2009.12.001
    # Role: LRT life-cycle costing built from structured construction / operation /
    #       maintenance cost estimation rather than a single lump scalar.
    # Limitation: its Korean LRT unit rates are not Cairo project rates.
    #
    # METHOD-REFERENCE
    # Authors/Organization: Royal Institution of Chartered Surveyors (RICS)
    # Title: "NRM 2: Detailed measurement for building works"
    # Journal/Standard: RICS NRM suite
    # Year/Version: reissued October 2022 as practice information
    # DOI/Identifier: RICS NRM 2
    # Role: quantity measurement and cost-coding methodology.
    # Limitation: project quantities and unit prices remain PROJECT-SOURCE-REQUIRED.
    #
    # REF-DERIVED equation:
    #     BaseCost_i = Quantity_i * UnitCost_i
    q = _finite(row.quantity, f"{row.cost_id}.quantity")
    u = _finite(row.unit_cost_base, f"{row.cost_id}.unit_cost_base")
    if q < 0 or u < 0:
        raise ScientificLCCInputError(
            f"negative quantity/unit cost not allowed for {row.cost_id}"
        )
    return q * u


def calculate_cost_row(
    row: CostRow,
    *,
    analysis_period_years: int,
    model_currency: str,
    discount_rate: float,
    discount_basis: str,
) -> dict:
    """Base amount -> escalated future amount -> present value, with provenance."""
    if not str(row.cost_id).strip():
        raise ScientificLCCInputError("cost_id is required")
    if row.phase not in ALLOWED_PHASES:
        raise ScientificLCCInputError(
            f"{row.cost_id}: invalid phase {row.phase!r}"
        )
    t = _validate_project_year(
        row.project_year, analysis_period_years, f"{row.cost_id}.project_year"
    )

    # v1 rejects mixed currencies outright. A silent conversion would hide an
    # unsourced FX assumption inside the headline number.
    if row.currency != model_currency:
        raise ScientificLCCInputError(
            f"{row.cost_id}: currency {row.currency!r} != model currency "
            f"{model_currency!r}. Convert FX explicitly before LCC."
        )

    delta = int(row.calendar_year) - int(row.price_base_year)
    base_amount = cost_row_base_amount(row)

    future_amount = escalate_cost(
        base_amount,
        row.escalation_rate,
        delta,
        discount_basis,
    )

    pv = present_value(future_amount, t, discount_rate)

    return {
        **asdict(row),
        "base_amount": base_amount,
        "future_amount": future_amount,
        "present_value": pv,
        "source_complete": _source_complete(
            row.source_file,
            row.source_location,
            row.evidence_status,
        ),
    }


def calculate_residual_row(
    row: ResidualRow,
    *,
    analysis_period_years: int,
    model_currency: str,
    discount_rate: float,
    discount_basis: str,
) -> dict:
    # REF-VERIFIED-Q1
    # Authors/Organization: Sepani Senaratne; Olivia Mirza; Timothy Dekruif; Christophe Camille
    # Title: "Life cycle cost analysis of alternative railway track support material:
    #        A case study of the Sydney harbour bridge"
    # Journal/Standard: Journal of Cleaner Production 276, 124258; SJR 2024 Q1
    # Year/Version: 2020
    # DOI/Identifier: 10.1016/j.jclepro.2020.124258
    # Role: railway LCC phases explicitly include end of life alongside planning,
    #       acquisition, operation and maintenance.
    # Limitation: Sydney case values are not Cairo project values.
    #
    # REF-VERIFIED-Q1
    # Authors/Organization: Mona AbouHamad; Metwally Abu-Hamd
    # Title: "Framework for construction system selection based on life cycle cost and
    #        sustainability assessment"
    # Journal/Standard: Journal of Cleaner Production 241, 118397; SJR 2024 Q1
    # Year/Version: 2019
    # DOI/Identifier: 10.1016/j.jclepro.2019.118397
    # Role: end-of-life / recycling / reuse scenarios inside an LCC framework.
    # Limitation: does not supply a project salvage price.
    #
    # Role of this function: residual/recovery/reuse REVENUE is kept apart from cost
    # rows so the canonical identity can credit it exactly ONCE.
    if not str(row.residual_id).strip():
        raise ScientificLCCInputError("residual_id is required")

    t = _validate_project_year(
        row.project_year, analysis_period_years, f"{row.residual_id}.project_year"
    )

    if row.currency != model_currency:
        raise ScientificLCCInputError(
            f"{row.residual_id}: currency mismatch"
        )

    amount = _finite(row.amount_base, f"{row.residual_id}.amount_base")
    if amount < 0:
        raise ScientificLCCInputError(
            "Residual/recovery value must be entered as a positive revenue"
        )

    delta = int(row.calendar_year) - int(row.price_base_year)

    future_value = escalate_cost(
        amount,
        row.escalation_rate,
        delta,
        discount_basis,
    )
    pv = present_value(future_value, t, discount_rate)

    return {
        **asdict(row),
        "base_value": amount,
        "future_value": future_value,
        "present_value": pv,
        "source_complete": _source_complete(
            row.source_file,
            row.source_location,
            row.evidence_status,
        ),
    }


def calculate_lcc(model: LCCModel) -> dict:
    # METHOD-REFERENCE
    # Authors/Organization: ASTM International
    # Title: "Standard Practice for Measuring Life-Cycle Costs of Buildings and Building Systems"
    # Journal/Standard: ASTM E917-17(2023)
    # Year/Version: 2023
    # DOI/Identifier: 10.1520/E0917-17R23
    # Role: present-value/annual-value LCC framework; study period; inclusion of initial
    #       and future operating, maintenance, repair, replacement and disposal costs.
    # Limitation: authoritative standard, NOT a Q1 journal article, and it supplies no
    #             project rate or unit cost.
    #
    # METHOD-REFERENCE
    # Authors/Organization: International Organization for Standardization (ISO)
    # Title: "Buildings and constructed assets — Service life planning — Part 5: Life-cycle costing"
    # Journal/Standard: ISO 15686-5:2017, Edition 2
    # Year/Version: 2017
    # DOI/Identifier: ISO 15686-5:2017
    # Role: agreed analysis period and acquisition-to-disposal cash-flow scope.
    # Limitation: establishes scope, not project numbers.
    #
    # REF-VERIFIED-Q1 — light rail transit
    # Authors/Organization: Gu-Taek Kim et al.
    # Title: "Development of a life cycle cost estimate system for structures of light
    #        rail transit infrastructure"
    # Journal/Standard: Automation in Construction 19(3), 308-325; SJR 2024 Q1
    # Year/Version: 2010
    # DOI/Identifier: 10.1016/j.autcon.2009.12.001
    # Role: LRT initial investment plus operation and maintenance in one LCC algorithm.
    # Limitation: foreign case study; no Cairo values.
    #
    # REF-VERIFIED-Q1 — railway lifecycle / end of life
    # Authors/Organization: Sepani Senaratne; Olivia Mirza; Timothy Dekruif; Christophe Camille
    # Title: "Life cycle cost analysis of alternative railway track support material:
    #        A case study of the Sydney harbour bridge"
    # Journal/Standard: Journal of Cleaner Production 276, 124258; SJR 2024 Q1
    # Year/Version: 2020
    # DOI/Identifier: 10.1016/j.jclepro.2020.124258
    # Role: railway LCC including the end-of-life phase.
    # Limitation: foreign case study; no Cairo values.
    #
    # REF-DERIVED canonical identity (assembled from the standards + Q1 sources above;
    # no single paper prints this exact combined identity verbatim):
    #     LCC_NPV = PV(Construction)
    #             + PV(Operation)
    #             + PV(Maintenance & Renewal)
    #             + PV(End of Life)
    #             - PV(Residual / Recovery Value)
    if int(model.analysis_period_years) <= 0:
        raise ScientificLCCInputError(
            "analysis_period_years must be > 0"
        )
    if model.discount_basis not in ALLOWED_DISCOUNT_BASIS:
        raise ScientificLCCInputError(
            f"invalid discount_basis {model.discount_basis!r}"
        )
    _validate_rate(model.discount_rate, "discount_rate")

    phase_pv = {p: 0.0 for p in ALLOWED_PHASES}
    phase_row_count = {p: 0 for p in ALLOWED_PHASES}
    cost_details = []
    residual_details = []
    open_items = []

    for row in model.cost_rows:
        d = calculate_cost_row(
            row,
            analysis_period_years=model.analysis_period_years,
            model_currency=model.currency,
            discount_rate=model.discount_rate,
            discount_basis=model.discount_basis,
        )
        phase_pv[row.phase] += d["present_value"]
        phase_row_count[row.phase] += 1
        cost_details.append(d)
        if not d["source_complete"]:
            open_items.append(
                f"{row.cost_id}: incomplete/diagnostic evidence "
                f"({row.evidence_status})"
            )

    residual_pv = 0.0
    for row in model.residual_rows:
        d = calculate_residual_row(
            row,
            analysis_period_years=model.analysis_period_years,
            model_currency=model.currency,
            discount_rate=model.discount_rate,
            discount_basis=model.discount_basis,
        )
        residual_pv += d["present_value"]
        residual_details.append(d)
        if not d["source_complete"]:
            open_items.append(
                f"{row.residual_id}: incomplete/diagnostic evidence "
                f"({row.evidence_status})"
            )

    # PROJECT-SOURCE-REQUIRED — the model-level discount rate is an evidence claim in
    # its own right. Q1 literature supports the discounting METHOD; it can never
    # establish that a particular rate is correct for this project.
    discount_source_complete = _source_complete(
        model.discount_source_file,
        model.discount_source_location,
        model.discount_evidence_status,
    )
    if not discount_source_complete:
        open_items.append("Discount rate: source/evidence incomplete")

    lcc_npv = (
        phase_pv["construction"]
        + phase_pv["operation"]
        + phase_pv["maintenance_renewal"]
        + phase_pv["end_of_life"]
        - residual_pv
    )

    return {
        "analysis_base_year": int(model.analysis_base_year),
        "analysis_period_years": int(model.analysis_period_years),
        "currency": model.currency,
        "discount_rate": float(model.discount_rate),
        "discount_basis": model.discount_basis,
        "discount_source_complete": discount_source_complete,
        "pv_construction": phase_pv["construction"],
        "pv_operation": phase_pv["operation"],
        "pv_maintenance_renewal": phase_pv["maintenance_renewal"],
        "pv_end_of_life": phase_pv["end_of_life"],
        "pv_residual": residual_pv,
        "lcc_npv": lcc_npv,
        # v1 phase gate: rows present / absent. An EMPTY phase is NOT proof that the
        # phase costs zero — phase declarations (documented_zero /
        # not_applicable_with_justification) arrive in the second tranche.
        "phase_row_count": dict(phase_row_count),
        "phase_has_rows": {p: phase_row_count[p] > 0 for p in ALLOWED_PHASES},
        "cost_rows": cost_details,
        "residual_rows": residual_details,
        "open_items": open_items,
        "publication_source_gate": not open_items,
        "equation_id": "LCC-NPV-01",
    }
