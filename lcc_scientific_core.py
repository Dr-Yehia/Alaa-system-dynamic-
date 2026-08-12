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

THE TWO EVIDENCE AXES — READ THIS BEFORE CHANGING THE GATE
----------------------------------------------------------
A standard or a Q1 paper can establish an EQUATION. It can never establish a
NUMBER for this project. ASTM E917 does not know a Cairo unit rate; Kim et al.
(2010) priced a Korean LRT, not this monorail. So evidence is classified on two
separate axes and they are NOT interchangeable:

  METHOD / EQUATION evidence   -> METHOD_EVIDENCE_CLASSES
      METHOD-REFERENCE, REF-VERIFIED-Q1
      Valid for LCC_EQUATION_REGISTRY entries. NEVER sufficient for a number.

  NUMERICAL / DATA evidence    -> PUBLICATION_ACCEPTABLE_NUMERIC_EVIDENCE
      PROJECT-SPECIFIC        project BOQ / contract / tender / O&M records
      OFFICIAL-PROJECT-DATA   official published data for the project geography
                              (national tariff schedule, central-bank rate, ...)
      Both additionally require source_file + exact source_location + geography.

  DIAGNOSTIC ONLY              -> REF-PROXY, SOURCE-OPEN, SCENARIO-ONLY
      Computes, is reported, and always fails the publication gate.

Attaching "METHOD-REFERENCE / ASTM E917" to a unit cost of 5000 therefore does
NOT make that 5000 publication-grade; it produces an explicit open item saying the
source establishes method only.

EVIDENCE LABELS USED IN COMMENTS
--------------------------------
REF-VERIFIED-Q1         peer-reviewed source; quartile stated as SJR 2024 Q1
                        (SCImago; Scopus-based data). This is NOT a JCR claim.
METHOD-REFERENCE        official standard / professional standard; never called Q1.
REF-DERIVED             equation assembled from several authoritative sources; it is
                        NOT presented as copied verbatim from one paper.
PROJECT-SOURCE-REQUIRED value must come from the project/Egypt geography.
SOURCE-OPEN             source still missing or not independently verified.
SCENARIO-ONLY           exploratory only; never a publication headline.

SCOPE LIMIT OF THIS VERSION
---------------------------
`publication_source_gate` proves EVIDENCE completeness. It does NOT yet prove
PHASE completeness: a model with no end-of-life rows is reported through
`phase_has_rows` / `empty_phases` but is not failed, because an absent phase is
ambiguous (truly zero vs. not yet entered). Do not describe this gate as
"Publication/Q1 ready" until PhaseDeclaration (documented_zero /
not_applicable_with_justification) lands in the ledger tranche.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Any


ALLOWED_PHASES = {
    "construction",
    "operation",
    "maintenance_renewal",
    "end_of_life",
}

ALLOWED_DISCOUNT_BASIS = {"real", "nominal"}

# Evidence that can certify a NUMBER for this project.
PUBLICATION_ACCEPTABLE_NUMERIC_EVIDENCE = {
    "PROJECT-SPECIFIC",
    "OFFICIAL-PROJECT-DATA",
}

# Evidence that certifies a METHOD or EQUATION only. Never a number.
METHOD_EVIDENCE_CLASSES = {
    "METHOD-REFERENCE",
    "REF-VERIFIED-Q1",
}

# Computed and shown, but never publication-grade.
DIAGNOSTIC_ONLY_EVIDENCE = {
    "REF-PROXY",
    "SOURCE-OPEN",
    "SCENARIO-ONLY",
}

# Descriptors a publication-grade cost row must actually fill in. A number with no
# unit or no owning asset is not auditable even when its source file exists.
REQUIRED_COST_DESCRIPTORS = ("unit", "category", "asset", "activity")
REQUIRED_RESIDUAL_DESCRIPTORS = ("asset", "activity")


# -----------------------------------------------------------------------------
# REFERENCE CATALOG
# Full bibliographic identity for every source cited by an LCC equation. Mirrors
# the frozen LCA architecture so a reviewer can resolve any citation mechanically.
# Quartiles are stated as "SJR 2024 Q1 (SCImago; Scopus-based data)" — this is a
# SCImago quartile, NOT a Clarivate JCR claim, and must be re-verified against JCR
# at submission time if the target venue requires JCR.
# -----------------------------------------------------------------------------
LCC_REFERENCE_CATALOG: dict[str, dict[str, str]] = {
    "ASTM_E917_2023": {
        "evidence_class": "METHOD-REFERENCE",
        "authors_or_organization": "ASTM International",
        "title": "Standard Practice for Measuring Life-Cycle Costs of Buildings and Building Systems",
        "publication": "ASTM E917-17(2023)",
        "year_version": "2023 reapproval of the 2017 edition",
        "doi_or_identifier": "10.1520/E0917-17R23",
        "quartile_note": "Authoritative standard; NOT a journal article and never labelled Q1.",
        "role": "Present-value/annual-value LCC framework; study period; inclusion of initial and future operating, maintenance, repair, replacement and disposal costs.",
        "limitation": "Supplies no discount rate, unit cost or quantity for this project.",
    },
    "ISO_15686_5_2017": {
        "evidence_class": "METHOD-REFERENCE",
        "authors_or_organization": "International Organization for Standardization (ISO)",
        "title": "Buildings and constructed assets — Service life planning — Part 5: Life-cycle costing",
        "publication": "ISO 15686-5:2017, Edition 2",
        "year_version": "2017 (current published edition)",
        "doi_or_identifier": "ISO 15686-5:2017",
        "quartile_note": "Authoritative standard; NOT a journal article and never labelled Q1.",
        "role": "Agreed analysis period; cash flows from acquisition through operation to disposal; scope declaration.",
        "limitation": "Establishes scope and method, not project numbers.",
    },
    "RICS_NRM2_2022": {
        "evidence_class": "METHOD-REFERENCE",
        "authors_or_organization": "Royal Institution of Chartered Surveyors (RICS)",
        "title": "NRM 2: Detailed measurement for building works",
        "publication": "RICS NRM suite, reissued October 2022 as practice information",
        "year_version": "Reissued October 2022",
        "doi_or_identifier": "RICS NRM 2",
        "quartile_note": "Professional standard; not a journal article.",
        "role": "Quantity measurement and cost-coding methodology behind quantity x unit cost.",
        "limitation": "Project quantities and unit prices remain PROJECT-SOURCE-REQUIRED.",
    },
    "KIM_2010_LRT_LCC": {
        "evidence_class": "REF-VERIFIED-Q1",
        "authors_or_organization": "Gu-Taek Kim; Kyoon-Tai Kim; Du-Heon Lee; Choong-Hee Han; Hyun-Bae Kim; Jin-Taek Jun",
        "title": "Development of a life cycle cost estimate system for structures of light rail transit infrastructure",
        "publication": "Automation in Construction 19(3), 308-325",
        "year_version": "2010",
        "doi_or_identifier": "10.1016/j.autcon.2009.12.001",
        "quartile_note": "SJR 2024 Q1 (SCImago; Scopus-based data)",
        "role": "LRT life-cycle cost structured as initial investment plus operation and maintenance, estimated from quantities rather than one lump scalar.",
        "limitation": "Korean LRT case study; its unit rates are NOT Cairo project values.",
    },
    "ABOUHAMAD_2019_LCC_MC": {
        "evidence_class": "REF-VERIFIED-Q1",
        "authors_or_organization": "Mona AbouHamad; Metwally Abu-Hamd",
        "title": "Framework for construction system selection based on life cycle cost and sustainability assessment",
        "publication": "Journal of Cleaner Production 241, 118397",
        "year_version": "2019",
        "doi_or_identifier": "10.1016/j.jclepro.2019.118397",
        "quartile_note": "SJR 2024 Q1 (SCImago; Scopus-based data)",
        "role": "LCC framework that discounts future costs to present value, treats inflation and interest, covers end-of-life/recycling scenarios and Monte Carlo uncertainty.",
        "limitation": "Case-study rates are not Cairo/project rates.",
    },
    "SENARATNE_2020_RAIL_LCC_EOL": {
        "evidence_class": "REF-VERIFIED-Q1",
        "authors_or_organization": "Sepani Senaratne; Olivia Mirza; Timothy Dekruif; Christophe Camille",
        "title": "Life cycle cost analysis of alternative railway track support material: A case study of the Sydney harbour bridge",
        "publication": "Journal of Cleaner Production 276, 124258",
        "year_version": "2020",
        "doi_or_identifier": "10.1016/j.jclepro.2020.124258",
        "quartile_note": "SJR 2024 Q1 (SCImago; Scopus-based data)",
        "role": "Railway LCC phases explicitly including planning, acquisition, operation and maintenance, and end of life.",
        "limitation": "Sydney case study; supplies no Cairo salvage or demolition price.",
    },
    "BALLIET_2025_ESCALATION": {
        "evidence_class": "REF-VERIFIED-Q1",
        "authors_or_organization": "W. Hill Balliet; Patrick Balducci; Venkat Durvasulu; Thomas Mosier",
        "title": "Determining the profitability of energy storage over its life cycle using levelized cost of storage",
        "publication": "Energy Economics 142, 108174",
        "year_version": "2025",
        "doi_or_identifier": "10.1016/j.eneco.2024.108174",
        "quartile_note": "SJR 2024 Q1 (SCImago; Scopus-based data)",
        "role": "Life-cycle economic consistency: O&M and electricity-price escalation together with discounting in one repeatable architecture.",
        "limitation": "Secondary support only — not rail-specific, and supplies no project escalation rate.",
    },
    "COMPARE_2022_CBM_LCC": {
        "evidence_class": "REF-VERIFIED-Q1",
        "authors_or_organization": "Michele Compare; Federico Antonello; Luca Pinciroli; Enrico Zio",
        "title": "A general model for life-cycle cost analysis of Condition-Based Maintenance enabled by PHM capabilities",
        "publication": "Reliability Engineering & System Safety 224, 108499",
        "year_version": "2022",
        "doi_or_identifier": "10.1016/j.ress.2022.108499",
        "quartile_note": "SJR 2024 Q1 (SCImago; Scopus-based data)",
        "role": "Life-cycle cost of condition-based maintenance / PHM policies; supports event-based maintenance costing.",
        "limitation": "Supplies no project maintenance interval or unit cost. Cited by the maintenance/renewal builder in the ledger tranche.",
    },
    "SEDGHI_2021_RAIL_MAINTENANCE": {
        "evidence_class": "REF-VERIFIED-Q1",
        "authors_or_organization": "Mahdieh Sedghi; Osmo Kauppila; Bjarne Bergquist; Erik Vanhatalo; Murat Kulahci",
        "title": "A taxonomy of railway track maintenance planning and scheduling: A review and research trends",
        "publication": "Reliability Engineering & System Safety 215, 107827",
        "year_version": "2021",
        "doi_or_identifier": "10.1016/j.ress.2021.107827",
        "quartile_note": "SJR 2024 Q1 (SCImago; Scopus-based data)",
        "role": "Railway maintenance/renewal planning and scheduling taxonomy; supports discrete events instead of one flat annual maintenance scalar.",
        "limitation": "Supplies no project intervention frequency or cost. Cited by the maintenance/renewal builder in the ledger tranche.",
    },
    "SOLEIMANI_2024_RAIL_LCC": {
        "evidence_class": "REF-VERIFIED-Q1",
        "authors_or_organization": "Khosro Soleimani-Chamkhorami; A.H.S. Garmabaki; Ahmad Kasraei; Stephen M. Famurewa; J. Odelius; Gustav Strandberg",
        "title": "Life cycle cost assessment of railways infrastructure asset under climate change impacts",
        "publication": "Transportation Research Part D: Transport and Environment 127, 104072",
        "year_version": "2024",
        "doi_or_identifier": "10.1016/j.trd.2024.104072",
        "quartile_note": "SJR 2024 Q1 (SCImago; Scopus-based data)",
        "role": "Dynamic railway LCC under reliability/deterioration uncertainty.",
        "limitation": "Supplies no project deterioration rate. Cited by the uncertainty tranche.",
    },
}


# -----------------------------------------------------------------------------
# EQUATION REGISTRY
# Every equation in this module resolves to catalog sources, a reference class, an
# explicit role and an explicit limitation. No equation is described as a verbatim
# quotation from one paper unless it actually is one.
# -----------------------------------------------------------------------------
LCC_EQUATIONS: dict[str, dict[str, Any]] = {
    "LCC-PV-01": {
        "name": "Present value of a dated cash flow",
        "equation": "PV_t = FutureCost_t / (1 + r)^t",
        "unit_check": "currency / dimensionless = currency",
        "reference_class": "REF-DERIVED | METHOD-REFERENCE | Q1-SUPPORTED",
        "source_ids": ["ASTM_E917_2023", "ISO_15686_5_2017", "ABOUHAMAD_2019_LCC_MC"],
        "role": "Discounting of every dated cost and residual flow to the analysis base year.",
        "limitation": "The standards and the Q1 companion establish the discounting METHOD. The numerical discount rate r is PROJECT-SOURCE-REQUIRED.",
    },
    "LCC-ESC-01": {
        "name": "Nominal escalation of a base-year cost",
        "equation": "C_t = C_0 * (1 + g)^Delta,  Delta = calendar_year - price_base_year",
        "unit_check": "currency * dimensionless = currency",
        "reference_class": "REF-DERIVED | Q1-SUPPORTED",
        "source_ids": ["ABOUHAMAD_2019_LCC_MC", "BALLIET_2025_ESCALATION"],
        "role": "Moves a cost stated in its price base year to the calendar year in which it occurs, in nominal basis only.",
        "limitation": "The numerical escalation rate g is PROJECT-SOURCE-REQUIRED. Never use a foreign uplift such as 17% as a universal project factor.",
    },
    "LCC-BASE-01": {
        "name": "Ledger row base cost",
        "equation": "BaseCost_i = Quantity_i * UnitCost_i",
        "unit_check": "quantity_unit * currency/quantity_unit = currency",
        "reference_class": "REF-DERIVED | Q1-SUPPORTED | METHOD-REFERENCE",
        "source_ids": ["KIM_2010_LRT_LCC", "RICS_NRM2_2022"],
        "role": "Derives each cost from a measured project quantity and a sourced unit rate rather than a lump scalar.",
        "limitation": "Both the quantity and the unit rate are PROJECT-SOURCE-REQUIRED; Kim's Korean LRT rates are not Cairo rates.",
    },
    "LCC-RESIDUAL-01": {
        "name": "Residual / recovery value credited once",
        "equation": "PV(R_residual) = sum_j R_j / (1 + r)^t_j,  subtracted once from LCC_NPV",
        "unit_check": "currency",
        "reference_class": "REF-DERIVED | Q1-SUPPORTED",
        "source_ids": ["SENARATNE_2020_RAIL_LCC_EOL", "ABOUHAMAD_2019_LCC_MC"],
        "role": "Keeps salvage/recovery/reuse revenue outside the end-of-life cost rows so it can be credited exactly once.",
        "limitation": "The residual price itself is PROJECT-SOURCE-REQUIRED.",
    },
    "LCC-NPV-01": {
        "name": "Canonical life-cycle cost identity",
        "equation": ("LCC_NPV = PV(Construction) + PV(Operation) + PV(Maintenance & Renewal) "
                     "+ PV(End of Life) - PV(Residual / Recovery)"),
        "unit_check": "sum of currency terms = currency",
        "reference_class": "REF-DERIVED | METHOD-REFERENCE | Q1-SUPPORTED",
        "source_ids": ["ASTM_E917_2023", "ISO_15686_5_2017",
                       "KIM_2010_LRT_LCC", "SENARATNE_2020_RAIL_LCC_EOL"],
        "role": "The single headline identity. Benefits are structurally absent from it.",
        "limitation": "No single cited work prints this exact combined identity verbatim; it is assembled from the standards and the Q1 rail/LRT sources.",
    },
}


def validate_lcc_reference_catalog() -> list[str]:
    """Every catalog record must carry a full bibliographic identity."""
    issues: list[str] = []
    required = ("evidence_class", "authors_or_organization", "title", "publication",
                "year_version", "doi_or_identifier", "role", "limitation")
    for source_id, record in LCC_REFERENCE_CATALOG.items():
        for field in required:
            if not str(record.get(field, "")).strip():
                issues.append(f"LCC_REFERENCE_CATALOG[{source_id}] missing {field}")
        # A quartile CLAIM must name SCImago explicitly and must never claim JCR.
        # The rule keys off evidence_class, not a substring: a standard's note
        # legitimately contains the word Q1 while DENYING the claim
        # ("never labelled Q1"), and that denial must not be flagged as a claim.
        note = str(record.get("quartile_note", ""))
        if record.get("evidence_class") == "REF-VERIFIED-Q1":
            if note != "SJR 2024 Q1 (SCImago; Scopus-based data)":
                issues.append(
                    f"{source_id}: Q1 claim must read exactly "
                    "'SJR 2024 Q1 (SCImago; Scopus-based data)'")
        elif "SJR" in note or "Q1 (" in note:
            issues.append(f"{source_id}: non-Q1 record must not assert a quartile")
        if "JCR" in note:
            issues.append(f"{source_id}: JCR quartile is not verified in this freeze")
    return issues


def validate_lcc_equation_registry() -> list[str]:
    """Every equation must be classified and resolve to real catalog sources."""
    issues: list[str] = []
    for equation_id, eq in LCC_EQUATIONS.items():
        for field in ("equation", "reference_class", "role", "limitation"):
            if not str(eq.get(field, "")).strip():
                issues.append(f"{equation_id}: missing {field}")
        source_ids = eq.get("source_ids") or []
        if not source_ids:
            issues.append(f"{equation_id}: no source_ids")
        for sid in source_ids:
            if sid not in LCC_REFERENCE_CATALOG:
                issues.append(f"{equation_id}: unresolved source_id {sid}")
    return issues


def lcc_reference_integrity_check() -> dict[str, Any]:
    issues = validate_lcc_reference_catalog() + validate_lcc_equation_registry()
    return {"ok": not issues, "issues": issues}


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

    Both model-level NUMBERS carry their own provenance, because each is as much an
    evidence claim as any ledger row:
      * the discount rate  — Q1 literature supports the discounting method, never
        the rate that is correct for this project;
      * the analysis period N — it scales every discounted term, so a project
        design-life document must state it.

    Provenance fields default to blank so that omitting them CLOSES the publication
    gate rather than crashing: the safe default is "blocked", never "assumed".
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
    discount_source_geography: str = ""
    analysis_period_source_file: str = ""
    analysis_period_source_location: str = ""
    analysis_period_evidence_status: str = "SOURCE-OPEN"
    analysis_period_geography: str = ""


def _finite(x: float, field: str) -> float:
    try:
        x = float(x)
    except (TypeError, ValueError):
        raise ScientificLCCInputError(f"{field} must be numeric") from None
    if not math.isfinite(x):
        raise ScientificLCCInputError(f"{field} must be finite")
    return x


def _validate_rate(rate: float, field: str) -> float:
    rate = _finite(rate, field)
    if rate <= -1.0:
        raise ScientificLCCInputError(f"{field} must be > -1")
    return rate


def _exact_int(value: Any, field: str) -> int:
    """Years are counts, not measurements.

    A fractional year is an input error, never something to truncate. `int(5.8)`
    would silently become 5 and shift a whole discounting period, so a non-integral
    value is rejected outright — the same rule the frozen LCA core applies to its
    annual series.
    """
    if isinstance(value, bool):
        raise ScientificLCCInputError(f"{field} must be an integer year, got {value!r}")
    try:
        as_float = float(value)
    except (TypeError, ValueError):
        raise ScientificLCCInputError(f"{field} must be an integer year, got {value!r}") from None
    if not math.isfinite(as_float) or as_float != int(as_float):
        raise ScientificLCCInputError(
            f"{field} must be an exact integer year (no truncation), got {value!r}"
        )
    return int(as_float)


def _validate_project_year(year: Any, N: int, field: str) -> int:
    year = _exact_int(year, field)
    if year < 0 or year > int(N):
        raise ScientificLCCInputError(
            f"{field}={year} outside analysis period 0..{N}"
        )
    return year


def _numeric_evidence_issues(
    *,
    label: str,
    source_file: str,
    source_location: str,
    geography: str,
    evidence_status: str,
    descriptors: dict[str, Any] | None = None,
) -> list[str]:
    """Provenance issues for a NUMBER (not for an equation).

    A method source cannot certify a number. That distinction is the whole point of
    this function, so an attempt to certify a value with METHOD-REFERENCE or with a
    foreign Q1 paper produces an explicit, self-explaining open item.
    """
    issues: list[str] = []
    if not str(source_file).strip():
        issues.append(f"{label}: missing source_file")
    if not str(source_location).strip():
        issues.append(f"{label}: missing source_location")
    if not str(geography).strip():
        issues.append(f"{label}: missing geography")

    status = str(evidence_status).strip()
    if status in METHOD_EVIDENCE_CLASSES:
        issues.append(
            f"{label}: {status} establishes METHOD/EQUATION only and cannot certify a "
            "numerical project value; supply PROJECT-SPECIFIC or OFFICIAL-PROJECT-DATA "
            "evidence for the number itself"
        )
    elif status not in PUBLICATION_ACCEPTABLE_NUMERIC_EVIDENCE:
        issues.append(
            f"{label}: evidence status {status!r} is not publication-grade for a "
            f"number (accepted: {sorted(PUBLICATION_ACCEPTABLE_NUMERIC_EVIDENCE)})"
        )

    for name, value in (descriptors or {}).items():
        if not str(value).strip():
            issues.append(f"{label}: missing {name}")
    return issues


def present_value(future_amount: float, project_year: int, discount_rate: float) -> float:
    # LCC-PV-01 — REF-DERIVED | METHOD-REFERENCE | Q1-SUPPORTED
    #
    # METHOD-REFERENCE
    # Authors/Organization: ASTM International
    # Title: "Standard Practice for Measuring Life-Cycle Costs of Buildings and Building Systems"
    # Journal/Standard: ASTM E917-17(2023)
    # Year/Version: 2023 reapproval of the 2017 edition
    # DOI/Identifier: 10.1520/E0917-17R23
    # Role: establishes the present-value treatment of life-cycle cash flows over an
    #       agreed study period.
    # Limitation: does NOT supply the numerical discount rate for the Cairo project.
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
    # REF-VERIFIED-Q1 — Q1 companion for the discounting of future costs
    # Authors/Organization: Mona AbouHamad; Metwally Abu-Hamd
    # Title: "Framework for construction system selection based on life cycle cost and
    #        sustainability assessment"
    # Journal/Standard: Journal of Cleaner Production 241, 118397
    # Year/Version: 2019; SJR 2024 Q1 (SCImago; Scopus-based data)
    # DOI/Identifier: 10.1016/j.jclepro.2019.118397
    # Role: an LCC framework that explicitly discounts future costs to present value
    #       and treats inflation and interest.
    # Limitation: its case-study rates are not Cairo/project rates. The standards
    #             above remain the primary method source; this paper is the Q1
    #             companion, not a replacement for them.
    #
    # REF-DERIVED equation used here:
    #     PV_t = FutureCost_t / (1 + r)^t
    amount = _finite(future_amount, "future_amount")
    r = _validate_rate(discount_rate, "discount_rate")
    t = _exact_int(project_year, "project_year")
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
    # LCC-ESC-01 — REF-DERIVED | Q1-SUPPORTED
    #
    # REF-VERIFIED-Q1
    # Authors/Organization: Mona AbouHamad; Metwally Abu-Hamd
    # Title: "Framework for construction system selection based on life cycle cost and
    #        sustainability assessment"
    # Journal/Standard: Journal of Cleaner Production 241, 118397
    # Year/Version: 2019; SJR 2024 Q1 (SCImago; Scopus-based data)
    # DOI/Identifier: 10.1016/j.jclepro.2019.118397
    # Role: LCC framework including inflation/interest and discounting of future costs.
    # Limitation: its case-study rates are not Cairo/project rates.
    #
    # REF-VERIFIED-Q1 — secondary economic-consistency support
    # Authors/Organization: W. Hill Balliet; Patrick Balducci; Venkat Durvasulu; Thomas Mosier
    # Title: "Determining the profitability of energy storage over its life cycle using
    #        levelized cost of storage"
    # Journal/Standard: Energy Economics 142, 108174
    # Year/Version: 2025; SJR 2024 Q1 (SCImago; Scopus-based data)
    # DOI/Identifier: 10.1016/j.eneco.2024.108174
    # Role: O&M and electricity-price escalation alongside discounting in one
    #       repeatable life-cycle economic architecture.
    # Limitation: not rail-specific, and supplies no project escalation rate.
    #
    # PROJECT-SOURCE-REQUIRED: the numerical escalation rate used for Cairo/project costs.
    #
    # REF-DERIVED equation:
    #     C_t = C_0 * (1 + g)^Delta
    base_cost = _finite(base_cost, "base_cost")
    g = _validate_rate(escalation_rate, "escalation_rate")
    delta = _exact_int(years_from_price_base, "years_from_price_base")

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
    # LCC-BASE-01 — REF-DERIVED | Q1-SUPPORTED | METHOD-REFERENCE
    #
    # REF-VERIFIED-Q1
    # Authors/Organization: Gu-Taek Kim; Kyoon-Tai Kim; Du-Heon Lee; Choong-Hee Han;
    #                       Hyun-Bae Kim; Jin-Taek Jun
    # Title: "Development of a life cycle cost estimate system for structures of light
    #        rail transit infrastructure"
    # Journal/Standard: Automation in Construction 19(3), 308-325
    # Year/Version: 2010; SJR 2024 Q1 (SCImago; Scopus-based data)
    # DOI/Identifier: 10.1016/j.autcon.2009.12.001
    # Role: LRT life-cycle costing built from structured construction / operation /
    #       maintenance cost estimation rather than a single lump scalar.
    # Limitation: its Korean LRT unit rates are NOT Cairo project rates.
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


def _validate_year_consistency(
    *,
    label: str,
    project_year: int,
    calendar_year: Any,
    price_base_year: Any,
    analysis_base_year: int,
    discount_basis: str,
) -> tuple[int, int]:
    """The calendar year and the project year must describe the SAME instant.

    Discounting uses `project_year` while escalation uses
    `calendar_year - price_base_year`. If those two clocks disagree, the row is
    escalated to one date and discounted to another, and the present value is
    silently meaningless. So the identity is enforced:

        calendar_year == analysis_base_year + project_year

    In REAL basis v1 the cost is a constant-price amount that is never escalated,
    which is only sound when it is already stated in the analysis base year;
    otherwise a 2020-priced cost would be discounted as if it were a 2026 cost. So
    real basis additionally requires price_base_year == analysis_base_year until a
    sourced official cost-index rebasing method exists.
    """
    calendar_year = _exact_int(calendar_year, f"{label}.calendar_year")
    price_base_year = _exact_int(price_base_year, f"{label}.price_base_year")

    expected = int(analysis_base_year) + int(project_year)
    if calendar_year != expected:
        raise ScientificLCCInputError(
            f"{label}: calendar_year={calendar_year} is inconsistent with "
            f"analysis_base_year={analysis_base_year} + project_year={project_year} "
            f"(expected {expected}). Escalation and discounting would use different dates."
        )

    if discount_basis == "real" and price_base_year != int(analysis_base_year):
        raise ScientificLCCInputError(
            f"{label}: real basis v1 requires price_base_year=={analysis_base_year} "
            f"(got {price_base_year}). A constant-price cost stated in another year must "
            "first be rebased with an explicitly sourced official cost index."
        )

    return calendar_year, price_base_year


def calculate_cost_row(
    row: CostRow,
    *,
    analysis_base_year: int,
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

    calendar_year, price_base_year = _validate_year_consistency(
        label=row.cost_id,
        project_year=t,
        calendar_year=row.calendar_year,
        price_base_year=row.price_base_year,
        analysis_base_year=analysis_base_year,
        discount_basis=discount_basis,
    )

    delta = calendar_year - price_base_year
    base_amount = cost_row_base_amount(row)

    future_amount = escalate_cost(
        base_amount,
        row.escalation_rate,
        delta,
        discount_basis,
    )

    pv = present_value(future_amount, t, discount_rate)

    evidence_issues = _numeric_evidence_issues(
        label=row.cost_id,
        source_file=row.source_file,
        source_location=row.source_location,
        geography=row.geography,
        evidence_status=row.evidence_status,
        descriptors={name: getattr(row, name) for name in REQUIRED_COST_DESCRIPTORS},
    )

    return {
        **asdict(row),
        "base_amount": base_amount,
        "future_amount": future_amount,
        "present_value": pv,
        "source_complete": not evidence_issues,
        "evidence_issues": evidence_issues,
    }


def calculate_residual_row(
    row: ResidualRow,
    *,
    analysis_base_year: int,
    analysis_period_years: int,
    model_currency: str,
    discount_rate: float,
    discount_basis: str,
) -> dict:
    # LCC-RESIDUAL-01 — REF-DERIVED | Q1-SUPPORTED
    #
    # REF-VERIFIED-Q1
    # Authors/Organization: Sepani Senaratne; Olivia Mirza; Timothy Dekruif; Christophe Camille
    # Title: "Life cycle cost analysis of alternative railway track support material:
    #        A case study of the Sydney harbour bridge"
    # Journal/Standard: Journal of Cleaner Production 276, 124258
    # Year/Version: 2020; SJR 2024 Q1 (SCImago; Scopus-based data)
    # DOI/Identifier: 10.1016/j.jclepro.2020.124258
    # Role: railway LCC phases explicitly include end of life alongside planning,
    #       acquisition, operation and maintenance.
    # Limitation: Sydney case values are not Cairo project values.
    #
    # REF-VERIFIED-Q1
    # Authors/Organization: Mona AbouHamad; Metwally Abu-Hamd
    # Title: "Framework for construction system selection based on life cycle cost and
    #        sustainability assessment"
    # Journal/Standard: Journal of Cleaner Production 241, 118397
    # Year/Version: 2019; SJR 2024 Q1 (SCImago; Scopus-based data)
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

    calendar_year, price_base_year = _validate_year_consistency(
        label=row.residual_id,
        project_year=t,
        calendar_year=row.calendar_year,
        price_base_year=row.price_base_year,
        analysis_base_year=analysis_base_year,
        discount_basis=discount_basis,
    )

    delta = calendar_year - price_base_year

    future_value = escalate_cost(
        amount,
        row.escalation_rate,
        delta,
        discount_basis,
    )
    pv = present_value(future_value, t, discount_rate)

    evidence_issues = _numeric_evidence_issues(
        label=row.residual_id,
        source_file=row.source_file,
        source_location=row.source_location,
        geography=row.geography,
        evidence_status=row.evidence_status,
        descriptors={name: getattr(row, name) for name in REQUIRED_RESIDUAL_DESCRIPTORS},
    )

    return {
        **asdict(row),
        "base_value": amount,
        "future_value": future_value,
        "present_value": pv,
        "source_complete": not evidence_issues,
        "evidence_issues": evidence_issues,
    }


def calculate_lcc(model: LCCModel) -> dict:
    # LCC-NPV-01 — REF-DERIVED | METHOD-REFERENCE | Q1-SUPPORTED
    #
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
    # Journal/Standard: Automation in Construction 19(3), 308-325
    # Year/Version: 2010; SJR 2024 Q1 (SCImago; Scopus-based data)
    # DOI/Identifier: 10.1016/j.autcon.2009.12.001
    # Role: LRT initial investment plus operation and maintenance in one LCC algorithm.
    # Limitation: foreign case study; no Cairo values.
    #
    # REF-VERIFIED-Q1 — railway lifecycle / end of life
    # Authors/Organization: Sepani Senaratne; Olivia Mirza; Timothy Dekruif; Christophe Camille
    # Title: "Life cycle cost analysis of alternative railway track support material:
    #        A case study of the Sydney harbour bridge"
    # Journal/Standard: Journal of Cleaner Production 276, 124258
    # Year/Version: 2020; SJR 2024 Q1 (SCImago; Scopus-based data)
    # DOI/Identifier: 10.1016/j.jclepro.2020.124258
    # Role: railway LCC including the end-of-life phase.
    # Limitation: foreign case study; no Cairo values.
    #
    # REF-DERIVED canonical identity (assembled from the standards + Q1 sources above;
    # no single cited work prints this exact combined identity verbatim):
    #     LCC_NPV = PV(Construction)
    #             + PV(Operation)
    #             + PV(Maintenance & Renewal)
    #             + PV(End of Life)
    #             - PV(Residual / Recovery Value)
    analysis_base_year = _exact_int(model.analysis_base_year, "analysis_base_year")
    analysis_period_years = _exact_int(
        model.analysis_period_years, "analysis_period_years")
    if analysis_period_years <= 0:
        raise ScientificLCCInputError(
            "analysis_period_years must be > 0"
        )
    if model.discount_basis not in ALLOWED_DISCOUNT_BASIS:
        raise ScientificLCCInputError(
            f"invalid discount_basis {model.discount_basis!r}"
        )
    _validate_rate(model.discount_rate, "discount_rate")

    # Identifiers must be unique inside the CORE, not only in the integration layer:
    # the core has to be safe when called directly, and a duplicated id would make the
    # audit ledger ambiguous.
    cost_ids = [r.cost_id for r in model.cost_rows]
    if len(cost_ids) != len(set(cost_ids)):
        dupes = sorted({i for i in cost_ids if cost_ids.count(i) > 1})
        raise ScientificLCCInputError(f"duplicate cost_id in LCC ledger: {dupes}")
    residual_ids = [r.residual_id for r in model.residual_rows]
    if len(residual_ids) != len(set(residual_ids)):
        dupes = sorted({i for i in residual_ids if residual_ids.count(i) > 1})
        raise ScientificLCCInputError(f"duplicate residual_id in LCC ledger: {dupes}")

    phase_pv = {p: 0.0 for p in ALLOWED_PHASES}
    phase_row_count = {p: 0 for p in ALLOWED_PHASES}
    cost_details = []
    residual_details = []
    open_items = []

    for row in model.cost_rows:
        d = calculate_cost_row(
            row,
            analysis_base_year=analysis_base_year,
            analysis_period_years=analysis_period_years,
            model_currency=model.currency,
            discount_rate=model.discount_rate,
            discount_basis=model.discount_basis,
        )
        phase_pv[row.phase] += d["present_value"]
        phase_row_count[row.phase] += 1
        cost_details.append(d)
        open_items.extend(d["evidence_issues"])

    residual_pv = 0.0
    for row in model.residual_rows:
        d = calculate_residual_row(
            row,
            analysis_base_year=analysis_base_year,
            analysis_period_years=analysis_period_years,
            model_currency=model.currency,
            discount_rate=model.discount_rate,
            discount_basis=model.discount_basis,
        )
        residual_pv += d["present_value"]
        residual_details.append(d)
        open_items.extend(d["evidence_issues"])

    # PROJECT-SOURCE-REQUIRED — the model-level discount rate is an evidence claim in
    # its own right. Q1 literature supports the discounting METHOD; it can never
    # establish that a particular rate is correct for this project, so a
    # METHOD-REFERENCE or foreign Q1 status on the rate is rejected here too.
    discount_issues = _numeric_evidence_issues(
        label="Discount rate",
        source_file=model.discount_source_file,
        source_location=model.discount_source_location,
        geography=model.discount_source_geography,
        evidence_status=model.discount_evidence_status,
    )
    open_items.extend(discount_issues)

    # PROJECT-SOURCE-REQUIRED — the analysis period N scales every discounted term,
    # so the project design-life/reference-study-period document must state it.
    period_issues = _numeric_evidence_issues(
        label="Analysis period N",
        source_file=model.analysis_period_source_file,
        source_location=model.analysis_period_source_location,
        geography=model.analysis_period_geography,
        evidence_status=model.analysis_period_evidence_status,
    )
    open_items.extend(period_issues)

    lcc_npv = (
        phase_pv["construction"]
        + phase_pv["operation"]
        + phase_pv["maintenance_renewal"]
        + phase_pv["end_of_life"]
        - residual_pv
    )

    return {
        "analysis_base_year": analysis_base_year,
        "analysis_period_years": analysis_period_years,
        "currency": model.currency,
        "discount_rate": float(model.discount_rate),
        "discount_basis": model.discount_basis,
        "discount_source_complete": not discount_issues,
        "analysis_period_source_complete": not period_issues,
        "pv_construction": phase_pv["construction"],
        "pv_operation": phase_pv["operation"],
        "pv_maintenance_renewal": phase_pv["maintenance_renewal"],
        "pv_end_of_life": phase_pv["end_of_life"],
        "pv_residual": residual_pv,
        "lcc_npv": lcc_npv,
        # v1 phase gate: rows present / absent. An EMPTY phase is NOT proof that the
        # phase costs zero, and `publication_source_gate` deliberately does NOT fail on
        # it yet — phase declarations (documented_zero /
        # not_applicable_with_justification) arrive in the ledger tranche. Until then
        # this result must not be described as Publication/Q1 ready on phase grounds.
        "phase_row_count": dict(phase_row_count),
        "phase_has_rows": {p: phase_row_count[p] > 0 for p in ALLOWED_PHASES},
        "empty_phases": sorted(p for p in ALLOWED_PHASES if phase_row_count[p] == 0),
        "phase_declarations_implemented": False,
        "cost_rows": cost_details,
        "residual_rows": residual_details,
        "open_items": open_items,
        # Evidence completeness only. See `phase_declarations_implemented`.
        "publication_source_gate": not open_items,
        "equation_id": "LCC-NPV-01",
        "equation_ids": ["LCC-NPV-01", "LCC-PV-01", "LCC-ESC-01",
                         "LCC-BASE-01", "LCC-RESIDUAL-01"],
    }
