"""Canonical source and equation registry for the scientific Benefits domain.

WHY THIS FILE EXISTS
--------------------
A reviewer reading `benefits_scientific_core.py` sees an inline `#` comment on
every arithmetic line naming the document that authorises that equation. That
comment is for immediate human inspection while reading the code; it is prose,
and prose cannot be tested. This module is the machine-readable half of the same
contract: every `REF-*` mentioned in a core comment resolves here to a full
record — title, issuer or authors, year, exact page/annex/table, DOI or official
URL, geography, and the limitation that stops the source being over-claimed.

The two halves are cross-checked by `tests/benefits_reference_integrity_test.py`,
which reads the core source text and fails if an equation is registered without a
matching comment, or cites a reference that has no record here.

THE RULE THAT SHAPES EVERYTHING BELOW
-------------------------------------
    THE SOURCE OF AN EQUATION IS NOT THE SOURCE OF A NUMERICAL VALUE.

A standard, a metadata sheet or a foreign Q1 paper can establish that
`avoided = baseline - project` is the correct operation. None of them can
establish what Cairo's modal-shift fraction is. So each record carries an
`evidence_role` and an `evidence_status`, and each equation declares which
classes of numeric evidence its project inputs need before the result may carry
a publication headline. `METHOD-REFERENCE` never certifies a project number.

This module holds no science. It calculates nothing except its own integrity.
It imports nothing from the LCA or LCC domains, and nothing from Streamlit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReferenceRecord:
    """One document a reviewer can open and check.

    `exact_location` is deliberately not optional and deliberately not a page
    range alone: "Annex 1, GHG Methodology Used for Monorail, printed pp.30-31"
    lands the reviewer on the method, whereas "p.30" makes them hunt.
    """

    ref_id: str
    title: str
    authors_or_issuer: str
    year: int
    document_type: str
    doi: str
    official_url: str
    local_source_file: str
    exact_location: str
    geography: str
    evidence_role: str
    units_or_basis: str
    price_base_year: Optional[int] = None
    evidence_status: str = "METHOD-REFERENCE"
    limitations: str = ""
    notes: str = ""


@dataclass(frozen=True)
class EquationRecord:
    """One scientific operation implemented in the Benefits core.

    `required_numeric_evidence` names the project quantities the equation
    consumes that a method reference cannot supply. It is what the publication
    gate walks to decide whether a computed number may be presented as a project
    finding or only as a scenario illustration.
    """

    equation_id: str
    name: str
    formula_text: str
    output_unit_contract: str
    method_ref_ids: tuple[str, ...]
    exact_source_locations: tuple[str, ...]
    evidence_role: str
    geography_rule: str
    publication_status: str
    required_numeric_evidence: tuple[str, ...]
    limitations: str = ""
    double_count_rule: str = ""


# ---------------------------------------------------------------------------
# Evidence vocabulary
# ---------------------------------------------------------------------------

#: A project number may carry a publication headline only under these statuses.
PUBLICATION_ACCEPTABLE_NUMERIC_EVIDENCE = frozenset(
    {"PROJECT-SPECIFIC", "OFFICIAL-PROJECT-DATA"}
)

#: These establish that a formula is correct. They never certify a project number.
METHOD_EVIDENCE_CLASSES = frozenset({"METHOD-REFERENCE", "STANDARD-REFERENCE"})

#: Displayable, but only with explicit proxy/scenario labelling.
QUALIFIED_EVIDENCE_CLASSES = frozenset({"REF-PROXY", "SCENARIO-ONLY", "HISTORICAL"})

#: No evidence yet. Blocks the publication headline outright.
OPEN_EVIDENCE_CLASSES = frozenset({"SOURCE-OPEN", "BLOCKED"})

ALL_EVIDENCE_CLASSES = (
    PUBLICATION_ACCEPTABLE_NUMERIC_EVIDENCE
    | METHOD_EVIDENCE_CLASSES
    | QUALIFIED_EVIDENCE_CLASSES
    | OPEN_EVIDENCE_CLASSES
)


# ---------------------------------------------------------------------------
# Reference registry
# ---------------------------------------------------------------------------

REFERENCES: dict[str, ReferenceRecord] = {}


def _register(record: ReferenceRecord) -> ReferenceRecord:
    if record.ref_id in REFERENCES:
        raise ValueError(f"duplicate reference id: {record.ref_id}")
    REFERENCES[record.ref_id] = record
    return record


_register(
    ReferenceRecord(
        ref_id="REF-EGY-GB-2022",
        title="Egypt Sovereign Green Bond Allocation & Impact Report - 2022",
        authors_or_issuer="Ministry of Finance, Government of Egypt",
        year=2022,
        document_type="Official government allocation and impact report",
        doi="n/a",
        official_url=(
            "https://assets.mof.gov.eg/files/2022-12/"
            "d3dec230-8900-11ed-ad5c-d5697d806e26.pdf"
        ),
        local_source_file="d3dec230-8900-11ed-ad5c-d5697d806e26-1.pdf",
        exact_location=(
            "Annex 1: Impact Reporting Methodology, printed pp.30-31, "
            "GHG Methodology Used for Monorail; featured project page for the "
            "reported monorail scenario and job figures"
        ),
        geography="Egypt / Cairo Monorail",
        evidence_role=(
            "METHOD-REFERENCE for the activity x factor x GWP structure and for "
            "modal-shift avoided-emission accounting; OFFICIAL-PROJECT-DATA only "
            "for figures the report states about this monorail explicitly"
        ),
        units_or_basis=(
            "Emissions = Activity Data x Emission Factor x GWP; passenger travel "
            "derived from projected ridership x average passenger distance"
        ),
        evidence_status="METHOD-REFERENCE",
        limitations=(
            "The 20-50% modal-shift range, the 30% featured scenario, the 365 "
            "operating days and the UK emission factors used inside that report "
            "are that report's own assumptions. They are not universal constants "
            "and must not be hard-coded as present Cairo evidence unless the "
            "assessment deliberately adopts the official scenario and labels it "
            "SCENARIO-ONLY."
        ),
        notes=(
            "Also the official source for up to 4,000 construction jobs and "
            "approximately 450 operational jobs, which are reported figures and "
            "not model outputs."
        ),
    )
)

_register(
    ReferenceRecord(
        ref_id="REF-TRD-MODAL-2024",
        title=(
            "Using different transport modes: An opportunity to reduce UK "
            "passenger transport emissions?"
        ),
        authors_or_issuer="Hugh Thomas; Andre Cabrera Serrenho",
        year=2024,
        document_type="Peer-reviewed journal article",
        doi="10.1016/j.trd.2023.103989",
        official_url="https://doi.org/10.1016/j.trd.2023.103989",
        local_source_file="n/a",
        exact_location=(
            "Transportation Research Part D: Transport and Environment, "
            "vol. 126 (2024), article 103989; modal-shift avoided-emissions "
            "method and distance x conversion-factor logic"
        ),
        geography="United Kingdom",
        evidence_role="METHOD-REFERENCE",
        units_or_basis="passenger-km x emission factor per passenger-km",
        evidence_status="METHOD-REFERENCE",
        limitations=(
            "The paper's numerical UK factors are UK factors. They must not be "
            "transferred to Cairo as project emission factors."
        ),
    )
)

_register(
    ReferenceRecord(
        ref_id="REF-WB-ENRRP-ICR",
        title=(
            "Egypt National Railways Restructuring Project (P101103) - "
            "Implementation Completion and Results Report"
        ),
        authors_or_issuer="The World Bank",
        year=2021,
        document_type="Official implementation completion and results report",
        doi="n/a",
        official_url=(
            "https://documents1.worldbank.org/curated/en/367961628584958285/pdf/"
            "Egypt-Railways-Restructuring-Project.pdf"
        ),
        local_source_file="Egypt-Railways-Restructuring-Project.pdf",
        exact_location=(
            "Report No. ICR00005398, Annex 4 Efficiency Analysis, "
            "printed pp.71-72, including the Rule-of-Half treatment of "
            "generated traffic on printed p.72"
        ),
        geography="Egypt (national railways)",
        evidence_role="METHOD-REFERENCE for Egyptian rail appraisal practice",
        units_or_basis=(
            "time saving valued as traffic x time difference x value of time; "
            "generated traffic entered at half the benefit"
        ),
        evidence_status="METHOD-REFERENCE",
        limitations=(
            "The Rule of Half applies to generated traffic only. Applying it to "
            "existing passengers halves a benefit the method says is fully "
            "realised. The report's own appraisal values are railway-project "
            "values and are not monorail project data."
        ),
    )
)

_register(
    ReferenceRecord(
        ref_id="REF-EGY-VOT-2022",
        title=(
            "Estimation of Cross Classified Value of Travel Time Using Binary "
            "Logit Model on Egyptian Roads"
        ),
        authors_or_issuer=(
            "Heba M. Bakry; Yusra M. H. Elgohary; Aya Farag; Ibrahim M. I. Ramadan"
        ),
        year=2022,
        document_type="Peer-reviewed journal article",
        doi="10.2174/18744478-v16-e2209140",
        official_url=(
            "https://opentransportationjournal.com/VOLUME/16/ELOCATOR/"
            "e187444782209140/FULLTEXT/"
        ),
        local_source_file="n/a",
        exact_location=(
            "The Open Transportation Journal, vol. 16, article e187444782209140; "
            "Theoretical Framework, reviewed PDF pp.3-4, the equation defining "
            "VOT as the ratio of the time and cost coefficients"
        ),
        geography="Egypt",
        evidence_role=(
            "METHOD-REFERENCE for VOT = (beta_time / beta_cost) x 60; historical "
            "numeric evidence only where the study's own price year is respected"
        ),
        units_or_basis=(
            "EGP per hour under the study's stated unit convention; reported "
            "study values include 32.5 LE/h private car and 18.3 LE/h public "
            "transport"
        ),
        price_base_year=2022,
        evidence_status="METHOD-REFERENCE",
        limitations=(
            "The reported values belong to the study's price year. They may not "
            "be escalated to a later appraisal year until the source price year "
            "and the chosen official index or deflator method are both documented."
        ),
    )
)

_register(
    ReferenceRecord(
        ref_id="REF-PLOS-TOD-2023",
        title=(
            "A framework to measure transit-oriented development around transit "
            "nodes: Case study of a mass rapid transit system in Dhaka, Bangladesh"
        ),
        authors_or_issuer=(
            "Md. Anwar Uddin; Md. Shamsul Hoque; Tahsin Tamanna; Saima Adiba; "
            "Shah Md. Muniruzzaman; Mohammad Shahriyar Parvez"
        ),
        year=2023,
        document_type="Peer-reviewed journal article",
        doi="10.1371/journal.pone.0280275",
        official_url=(
            "https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0280275"
        ),
        local_source_file="n/a",
        exact_location=(
            "PLOS ONE 18(1) e0280275, paper page 9, Land use diversity (LUD), "
            "Equations (1) and (2)"
        ),
        geography="Dhaka, Bangladesh",
        evidence_role="METHOD-REFERENCE",
        units_or_basis="dimensionless index in [0,1] for non-degenerate share vectors",
        evidence_status="METHOD-REFERENCE",
        limitations=(
            "The rendered equation carries a LEADING MINUS SIGN which plain-text "
            "extraction of the PDF silently drops. Implementations that lose it "
            "produce a negative index and invert the interpretation. The minus "
            "sign was verified visually in the rendered PDF."
        ),
    )
)

_register(
    ReferenceRecord(
        ref_id="REF-INDIA-TOD-POLICY-2017",
        title="National Transit Oriented Development (TOD) Policy",
        authors_or_issuer=(
            "Government of India, Ministry responsible for Housing and Urban "
            "Affairs / Urban Development"
        ),
        year=2017,
        document_type="National policy document",
        doi="n/a",
        official_url=(
            "https://mohua.gov.in/upload/whatsnew/"
            "59a4070e85256Transit_Oriented_Developoment_Policy.pdf"
        ),
        local_source_file="n/a",
        exact_location=(
            "influence-zone discussion describing approximately 500-800 m "
            "walking-distance influence zones around transit nodes"
        ),
        geography="India",
        evidence_role="METHOD/POLICY-REFERENCE",
        units_or_basis="metres of walking-distance influence radius",
        evidence_status="METHOD-REFERENCE",
        limitations=(
            "500-800 m is an Indian policy benchmark. It is not automatically the "
            "Cairo project influence radius; the Cairo radius needs project, "
            "planning or GIS evidence of its own."
        ),
    )
)

_register(
    ReferenceRecord(
        ref_id="REF-UNHABITAT-SDG1131-2025",
        title=(
            "Metadata for SDG Indicator 11.3.1 - Ratio of land consumption rate "
            "to population growth rate"
        ),
        authors_or_issuer="UN-Habitat / UN SDG metadata system",
        year=2025,
        document_type="Official SDG indicator metadata (version 2025-04-23)",
        doi="n/a",
        official_url="https://unstats.un.org/sdgs/metadata/files/Metadata-11-03-01.pdf",
        local_source_file="Metadata-11-03-01.pdf",
        exact_location=(
            "reviewed pp.7-9: spatial analysis and computation of the land "
            "consumption rate (pp.7-8), Population Growth Rate formula (p.8), "
            "total change in built-up area and built-up area per capita (p.9)"
        ),
        geography="global SDG methodology",
        evidence_role="METHOD-REFERENCE",
        units_or_basis=(
            "LCR and PGR are annualised rates over the SAME analysis period; "
            "built-up area per capita in m2/person"
        ),
        evidence_status="METHOD-REFERENCE",
        limitations=(
            "LCR and PGR must be computed over identical years. A "
            "baseline-versus-design scenario difference is not an SDG 11.3.1 land "
            "consumption rate, because the indicator is defined over real elapsed "
            "time."
        ),
    )
)

_register(
    ReferenceRecord(
        ref_id="REF-EGY-IO-ALAYOUTY-2022",
        title=(
            "Identifying Activities for Greater Employment Generation in Egypt: "
            "An Input-Output Analysis"
        ),
        authors_or_issuer="Iman Al-Ayouty; African Economic Research Consortium",
        year=2022,
        document_type="Working paper (AERC GSYE Working Paper GSYE-007)",
        doi="n/a",
        official_url=(
            "https://publication.aercafricalibrary.org/items/"
            "035e42e5-5fbb-416e-932a-494a2fd50965"
        ),
        local_source_file=(
            "Identifying-activities-for-greater-employment-generation-in-Egypt-"
            "An-input-output-analysis.pdf"
        ),
        exact_location=(
            "methodology pp.11-12 (technical coefficients, Leontief inverse, "
            "output multiplier, employment multiplier); results tables later in "
            "the paper"
        ),
        geography="Egypt",
        evidence_role="METHOD-REFERENCE plus HISTORICAL numerical evidence",
        units_or_basis="Egypt 2016-2017 input-output table",
        evidence_status="HISTORICAL",
        limitations=(
            "The published multipliers rest on the 2016-2017 Egyptian I-O table "
            "and the paper itself discusses a limited stability window. They may "
            "be reported as historical Egyptian structure; they may not be "
            "labelled current 2026 Cairo project truth. The reported ~1.44-type "
            "figure is an employment MULTIPLIER under the paper's definition, not "
            "jobs per EGP and not jobs per USD."
        ),
    )
)

_register(
    ReferenceRecord(
        ref_id="REF-MOSZORO-2024",
        title="The direct employment impact of public investment",
        authors_or_issuer="Marian W. Moszoro",
        year=2024,
        document_type="Peer-reviewed journal article",
        doi="10.2478/ijme-2023-0020",
        official_url="https://reference-global.com/article/10.2478/ijme-2023-0020",
        local_source_file="n/a",
        exact_location=(
            "International Journal of Management and Economics 60(1), pp.59-74; "
            "results tables reporting jobs per US$1 million of investment, with "
            "approximately 10-17 jobs per US$1m in emerging market economies"
        ),
        geography="cross-country firm-level infrastructure construction",
        evidence_role="REF-PROXY",
        units_or_basis=(
            "jobs per US$1 million of investment, with monetary data standardised "
            "to constant 2015 USD using GDP deflators"
        ),
        price_base_year=2015,
        evidence_status="REF-PROXY",
        limitations=(
            "This is a cross-country benchmark, not a Cairo measurement. A model "
            "using it must express investment in the same constant 2015 USD basis "
            "or document the conversion. The result is a model benchmark, never "
            "'Cairo jobs created', and it must never be added to officially "
            "reported project jobs."
        ),
    )
)

_register(
    ReferenceRecord(
        ref_id="REF-RAIL-CBA-2026",
        title=(
            "Cost-Benefit Analysis of Regional Railway Modernization with "
            "Emphasis on Investment Costs and Electrification"
        ),
        authors_or_issuer="Brumercik et al.",
        year=2026,
        document_type="Peer-reviewed journal article",
        doi="10.3390/app16094222",
        official_url="https://www.mdpi.com/2076-3417/16/9/4222",
        local_source_file="n/a",
        exact_location="Applied Sciences 16(9), article 4222; rail CBA structure",
        geography="Slovakia",
        evidence_role="METHOD-REFERENCE (supplementary rail CBA support)",
        units_or_basis="rail cost-benefit appraisal structure",
        evidence_status="METHOD-REFERENCE",
        limitations="Slovak numerical values must not be transferred to Cairo.",
    )
)

_register(
    ReferenceRecord(
        ref_id="REF-EU-NOISE-2002",
        title=(
            "Directive 2002/49/EC relating to the assessment and management of "
            "environmental noise"
        ),
        authors_or_issuer="European Parliament and Council",
        year=2002,
        document_type="EU Directive",
        doi="n/a",
        official_url="https://eur-lex.europa.eu/eli/dir/2002/49/oj/eng",
        local_source_file="n/a",
        exact_location=(
            "definition and use of Lden for overall annoyance and Lnight for "
            "sleep disturbance"
        ),
        geography="European Union",
        evidence_role="STANDARD-REFERENCE",
        units_or_basis="dB, Lden and Lnight indicators",
        evidence_status="STANDARD-REFERENCE",
        limitations=(
            "Establishes which acoustic indicators are meaningful. It does not "
            "supply any Cairo noise level."
        ),
    )
)

_register(
    ReferenceRecord(
        ref_id="REF-EU-CNOSSOS-2015",
        title=(
            "Commission Directive (EU) 2015/996 establishing common noise "
            "assessment methods according to Directive 2002/49/EC"
        ),
        authors_or_issuer="European Commission",
        year=2015,
        document_type="EU Directive",
        doi="n/a",
        official_url="https://eur-lex.europa.eu/eli/dir/2015/996/oj/eng",
        local_source_file="n/a",
        exact_location="common noise assessment methods (CNOSSOS-EU)",
        geography="European Union",
        evidence_role="STANDARD-REFERENCE",
        units_or_basis="dB under a documented common assessment method",
        evidence_status="STANDARD-REFERENCE",
        limitations=(
            "Establishes that baseline and project levels must share one "
            "assessment method before they can be differenced."
        ),
    )
)

_register(
    ReferenceRecord(
        ref_id="REF-EU-EXTCOST-2019",
        title="Handbook on the external costs of transport",
        authors_or_issuer=(
            "European Commission, DG MOVE / Publications Office of the European "
            "Union"
        ),
        year=2019,
        document_type="Official handbook",
        doi="10.2832/27212",
        official_url=(
            "https://op.europa.eu/en/publication-detail/-/publication/"
            "e021854b-a451-11e9-9d01-01aa75ed71a1"
        ),
        local_source_file="n/a",
        exact_location="external-cost valuation framework for transport",
        geography="European Union",
        evidence_role="METHOD-REFERENCE for external-cost valuation structure",
        units_or_basis="EUR per unit of exposure, EU price basis",
        evidence_status="METHOD-REFERENCE",
        limitations=(
            "No Cairo noise monetisation may be produced from this handbook until "
            "exposed population, exposure levels and an explicit value-transfer "
            "basis are all supplied."
        ),
    )
)


# ---------------------------------------------------------------------------
# Equation registry
# ---------------------------------------------------------------------------

EQUATIONS: dict[str, EquationRecord] = {}


def _register_eq(record: EquationRecord) -> EquationRecord:
    if record.equation_id in EQUATIONS:
        raise ValueError(f"duplicate equation id: {record.equation_id}")
    EQUATIONS[record.equation_id] = record
    return record


_EGY_GB_LOC = (
    "REF-EGY-GB-2022 Annex 1, GHG Methodology Used for Monorail, printed pp.30-31"
)
_WB_LOC = "REF-WB-ENRRP-ICR Annex 4 Efficiency Analysis, printed pp.71-72"
_PLOS_LOC = "REF-PLOS-TOD-2023 p.9, Land use diversity, Eq.(1) and Eq.(2)"
_UNH_LOC_LCR = (
    "REF-UNHABITAT-SDG1131-2025 reviewed pp.7-8, computation of the land "
    "consumption rate"
)
_UNH_LOC_P9 = (
    "REF-UNHABITAT-SDG1131-2025 reviewed p.9, total built-up area change and "
    "built-up area per capita"
)
_IO_LOC = "REF-EGY-IO-ALAYOUTY-2022 methodology pp.11-12"


_register_eq(
    EquationRecord(
        equation_id="BEN-PKM-01",
        name="Annual passenger-km",
        formula_text="PKM_y = P_day,y * d_avg,y * D_y",
        output_unit_contract="passenger-km per year",
        method_ref_ids=("REF-EGY-GB-2022",),
        exact_source_locations=(_EGY_GB_LOC,),
        evidence_role="METHOD-REFERENCE",
        geography_rule=(
            "method is geography-neutral; all three inputs must be Cairo project "
            "quantities"
        ),
        publication_status="METHOD-READY-NUMERIC-EVIDENCE-REQUIRED",
        required_numeric_evidence=(
            "passengers_per_day",
            "avg_distance_km",
            "operating_days_per_year",
        ),
        limitations=(
            "Operating days must be supplied as project evidence. The 365 days "
            "used inside the green bond report is that report's own assumption "
            "and may not be substituted silently."
        ),
        double_count_rule="Physical activity only; carries no carbon and no money.",
    )
)

_register_eq(
    EquationRecord(
        equation_id="BEN-MODAL-01",
        name="Shifted passenger-km",
        formula_text="PKM_shift,y = PKM_y * MS_y,  MS_y in [0,1]",
        output_unit_contract="passenger-km per year",
        method_ref_ids=("REF-EGY-GB-2022", "REF-TRD-MODAL-2024"),
        exact_source_locations=(
            _EGY_GB_LOC,
            "REF-TRD-MODAL-2024 modal-shift avoided-emissions method",
        ),
        evidence_role="METHOD-REFERENCE",
        geography_rule="the modal-shift fraction must be Cairo evidence",
        publication_status="METHOD-READY-NUMERIC-EVIDENCE-REQUIRED",
        required_numeric_evidence=("modal_shift_fraction",),
        limitations=(
            "0.30 must not be hard-coded. It is a scenario in the green bond "
            "report, not a measured Cairo fraction."
        ),
        double_count_rule="Physical activity only.",
    )
)

_register_eq(
    EquationRecord(
        equation_id="BEN-MODE-SPLIT-01",
        name="Car/bus allocation of shifted passenger-km",
        formula_text="PKM_car = PKM_shift * s_car;  PKM_bus = PKM_shift * s_bus;  s_car + s_bus = 1",
        output_unit_contract="passenger-km per year, per displaced mode",
        method_ref_ids=("REF-EGY-GB-2022", "REF-TRD-MODAL-2024"),
        exact_source_locations=(
            _EGY_GB_LOC,
            "REF-TRD-MODAL-2024 mode-specific emission accounting",
        ),
        evidence_role="DERIVED/APPLIED-METHOD",
        geography_rule="the split must come from a Cairo travel survey or model",
        publication_status="METHOD-READY-NUMERIC-EVIDENCE-REQUIRED",
        required_numeric_evidence=("car_share_of_shift", "bus_share_of_shift"),
        limitations=(
            "Algebraic allocation supporting the sourced modal-shift framework; "
            "the shares themselves are project inputs and are rejected if they do "
            "not sum to 1."
        ),
        double_count_rule="Partition of BEN-MODAL-01; the parts never exceed the whole.",
    )
)

_register_eq(
    EquationRecord(
        equation_id="BEN-GHG-GAS-01",
        name="Gas-specific emissions with explicit GWP",
        formula_text="E = Activity * EF_gas * GWP_gas",
        output_unit_contract="kgCO2e (activity unit x factor unit must cancel)",
        method_ref_ids=("REF-EGY-GB-2022",),
        exact_source_locations=(_EGY_GB_LOC,),
        evidence_role="METHOD-REFERENCE",
        geography_rule="the emission factor must match the assessed fleet and year",
        publication_status="METHOD-READY-NUMERIC-EVIDENCE-REQUIRED",
        required_numeric_evidence=("emission_factor_gas", "gwp"),
        limitations="Only for factors expressed per unit mass of a specific gas.",
        double_count_rule=(
            "If the factor is already CO2e, this route must not be used; "
            "multiplying an already-CO2e factor by GWP double-counts."
        ),
    )
)

_register_eq(
    EquationRecord(
        equation_id="BEN-GHG-CO2E-01",
        name="Emissions from an already-CO2e factor",
        formula_text="E_CO2e = Activity * EF_CO2e",
        output_unit_contract="kgCO2e (activity unit x factor unit must cancel)",
        method_ref_ids=("REF-EGY-GB-2022", "REF-TRD-MODAL-2024"),
        exact_source_locations=(
            _EGY_GB_LOC,
            "REF-TRD-MODAL-2024 distance x conversion-factor logic",
        ),
        evidence_role="METHOD-REFERENCE",
        geography_rule=(
            "factor value, unit, basis, mode, year and geography must all be "
            "declared; UK factors are not Cairo factors"
        ),
        publication_status="METHOD-READY-NUMERIC-EVIDENCE-REQUIRED",
        required_numeric_evidence=("emission_factor_co2e",),
        limitations="Factor must already include the global warming potential.",
        double_count_rule="No GWP multiplication on this route.",
    )
)

_register_eq(
    EquationRecord(
        equation_id="BEN-GHG-AVOID-01",
        name="Signed avoided greenhouse-gas emissions",
        formula_text="dE = E_baseline - E_project",
        output_unit_contract="kgCO2e, signed (positive = avoided, negative = disbenefit)",
        method_ref_ids=("REF-EGY-GB-2022", "REF-TRD-MODAL-2024"),
        exact_source_locations=(
            _EGY_GB_LOC,
            "REF-TRD-MODAL-2024 modal-shift avoided-emissions method",
        ),
        evidence_role="METHOD-REFERENCE",
        geography_rule="baseline and project must share activity basis and year",
        publication_status="METHOD-READY-NUMERIC-EVIDENCE-REQUIRED",
        required_numeric_evidence=("baseline_emissions", "project_emissions"),
        limitations=(
            "No max(delta, 0) truncation. A negative result is a real finding and "
            "is reported as a disbenefit, not hidden as zero."
        ),
        double_count_rule=(
            "Physical avoided emissions are a Benefits-domain quantity. They never "
            "reduce LCA Gross A-C and never enter LCC NPV."
        ),
    )
)

_register_eq(
    EquationRecord(
        equation_id="BEN-TIME-01",
        name="Passenger-hours saved",
        formula_text="H_saved,y = Q_y * (t_0,y - t_1,y)",
        output_unit_contract="passenger-hours per year, signed",
        method_ref_ids=("REF-WB-ENRRP-ICR",),
        exact_source_locations=(_WB_LOC,),
        evidence_role="METHOD-REFERENCE",
        geography_rule="travel times must be measured on the assessed corridor",
        publication_status="METHOD-READY-NUMERIC-EVIDENCE-REQUIRED",
        required_numeric_evidence=("annual_trips", "baseline_time", "project_time"),
        limitations=(
            "Times must be in consistent units; minutes are converted to hours on "
            "a visibly named line before multiplication. Sign is preserved."
        ),
        double_count_rule="Physical time only; monetisation is a separate equation.",
    )
)

_register_eq(
    EquationRecord(
        equation_id="BEN-TIME-MONEY-01",
        name="Monetary value of time savings",
        formula_text="B_time,y = H_saved,y * VOT_y",
        output_unit_contract="currency per year at a declared price base year",
        method_ref_ids=("REF-WB-ENRRP-ICR",),
        exact_source_locations=(_WB_LOC,),
        evidence_role="METHOD-REFERENCE",
        geography_rule="VOT must be Egyptian and its price year declared",
        publication_status="METHOD-READY-NUMERIC-EVIDENCE-REQUIRED",
        required_numeric_evidence=("passenger_hours_saved", "value_of_time"),
        limitations=(
            "VOT must carry currency, currency basis, price base year, source "
            "geography, exact source location, and the escalation source if it "
            "was converted."
        ),
        double_count_rule=(
            "A CBA benefit. It never reduces LCC NPV inside this system; any "
            "netting belongs to a future, separately named CBA module."
        ),
    )
)

_register_eq(
    EquationRecord(
        equation_id="BEN-GEN-TRAFFIC-01",
        name="Generated-traffic benefit under the Rule of Half",
        formula_text="B_generated,y = 0.5 * Q_generated,y * dt_y * VOT_y",
        output_unit_contract="currency per year at a declared price base year",
        method_ref_ids=("REF-WB-ENRRP-ICR",),
        exact_source_locations=(
            "REF-WB-ENRRP-ICR Annex 4, Rule-of-Half treatment for generated "
            "traffic, printed p.72",
        ),
        evidence_role="METHOD-REFERENCE",
        geography_rule="generated trips must come from a project demand model",
        publication_status="METHOD-READY-NUMERIC-EVIDENCE-REQUIRED",
        required_numeric_evidence=("generated_trips", "time_saved", "value_of_time"),
        limitations=(
            "The 0.5 applies to GENERATED traffic only. Existing passengers "
            "receive the full benefit through BEN-TIME-MONEY-01."
        ),
        double_count_rule=(
            "Generated trips must not also be counted in the existing-passenger "
            "time benefit."
        ),
    )
)

_register_eq(
    EquationRecord(
        equation_id="BEN-VOT-01",
        name="Value of travel time from logit coefficients",
        formula_text="VOT = (beta_time / beta_cost) * 60",
        output_unit_contract="currency per hour under the source unit convention",
        method_ref_ids=("REF-EGY-VOT-2022",),
        exact_source_locations=(
            "REF-EGY-VOT-2022 Theoretical Framework, reviewed PDF pp.3-4",
        ),
        evidence_role="METHOD-REFERENCE",
        geography_rule="coefficients must come from an Egyptian fitted model",
        publication_status="METHOD-READY-NUMERIC-EVIDENCE-REQUIRED",
        required_numeric_evidence=("beta_time", "beta_cost"),
        limitations=(
            "The x60 factor encodes the source's per-minute to per-hour "
            "convention. Reported study values belong to the study price year and "
            "may not be escalated without a documented official index."
        ),
        double_count_rule="Produces a unit price, not a benefit.",
    )
)

_register_eq(
    EquationRecord(
        equation_id="BEN-LU-SHARE-01",
        name="Land-use class share",
        formula_text="p_i = A_i / A_total",
        output_unit_contract="dimensionless share, shares sum to 1",
        method_ref_ids=("REF-PLOS-TOD-2023",),
        exact_source_locations=("REF-PLOS-TOD-2023 p.9, Eq.(2)",),
        evidence_role="METHOD-REFERENCE",
        geography_rule="class schema must be identical for baseline and project",
        publication_status="METHOD-READY-NUMERIC-EVIDENCE-REQUIRED",
        required_numeric_evidence=("area_by_class",),
        limitations="Areas must be non-negative and the total strictly positive.",
        double_count_rule="Spatial indicator; carries no money and no carbon.",
    )
)

_register_eq(
    EquationRecord(
        equation_id="BEN-LUD-01",
        name="Normalised Shannon land-use diversity",
        formula_text="LUD = -sum(p_i * ln(p_i)) / ln(n)",
        output_unit_contract="dimensionless index in [0,1]",
        method_ref_ids=("REF-PLOS-TOD-2023",),
        exact_source_locations=(_PLOS_LOC,),
        evidence_role="METHOD-REFERENCE",
        geography_rule=(
            "method is geography-neutral; the land-use maps must be project maps "
            "with a stated source and date"
        ),
        publication_status="METHOD-READY-NUMERIC-EVIDENCE-REQUIRED",
        required_numeric_evidence=("area_by_class",),
        limitations=(
            "The leading minus sign is mandatory and was verified visually in the "
            "rendered PDF. n >= 2. p = 0 contributes zero by the mathematical "
            "limit and must never reach log(0)."
        ),
        double_count_rule="Spatial indicator; never monetised here.",
    )
)

_register_eq(
    EquationRecord(
        equation_id="BEN-LUD-DELTA-01",
        name="Land-use diversity change",
        formula_text="dLUD = LUD_project - LUD_baseline",
        output_unit_contract="dimensionless index difference, signed",
        method_ref_ids=("REF-PLOS-TOD-2023",),
        exact_source_locations=(_PLOS_LOC,),
        evidence_role="DERIVED-FROM-METHOD",
        geography_rule="both LUD values must use one class schema and one area",
        publication_status="DERIVED-METHOD-NUMERIC-EVIDENCE-REQUIRED",
        required_numeric_evidence=("baseline_area_by_class", "project_area_by_class"),
        limitations=(
            "This delta is a comparison built on the sourced LUD definition. The "
            "PLOS paper does not print this exact difference equation."
        ),
        double_count_rule="Spatial indicator only.",
    )
)

_register_eq(
    EquationRecord(
        equation_id="BEN-BUILTUP-CHANGE-01",
        name="Total change in built-up area",
        formula_text="dBU% = 100 * (BU_current - BU_past) / BU_past",
        output_unit_contract="percent change over the stated period",
        method_ref_ids=("REF-UNHABITAT-SDG1131-2025",),
        exact_source_locations=(_UNH_LOC_P9,),
        evidence_role="METHOD-REFERENCE",
        geography_rule="both observations must cover the same spatial extent",
        publication_status="METHOD-READY-NUMERIC-EVIDENCE-REQUIRED",
        required_numeric_evidence=("built_up_past", "built_up_present"),
        limitations="Past built-up area must be strictly positive.",
        double_count_rule="Spatial indicator only.",
    )
)

_register_eq(
    EquationRecord(
        equation_id="BEN-LCR-01",
        name="Annual land consumption rate",
        formula_text="LCR = ((V_present - V_past) / V_past) * (1 / t)",
        output_unit_contract="annual rate (fraction per year)",
        method_ref_ids=("REF-UNHABITAT-SDG1131-2025",),
        exact_source_locations=(_UNH_LOC_LCR,),
        evidence_role="METHOD-REFERENCE",
        geography_rule="same city extent, real elapsed years",
        publication_status="METHOD-READY-NUMERIC-EVIDENCE-REQUIRED",
        required_numeric_evidence=("built_up_past", "built_up_present", "period_years"),
        limitations=(
            "A baseline-versus-design scenario difference is not an SDG 11.3.1 "
            "LCR. The indicator is defined over real elapsed time."
        ),
        double_count_rule="Spatial indicator only.",
    )
)

_register_eq(
    EquationRecord(
        equation_id="BEN-PGR-01",
        name="Population growth rate",
        formula_text="PGR = ln(Pop_t+n / Pop_t) / y",
        output_unit_contract="annual continuous growth rate",
        method_ref_ids=("REF-UNHABITAT-SDG1131-2025",),
        exact_source_locations=(
            "REF-UNHABITAT-SDG1131-2025 reviewed p.8, Population Growth Rate "
            "formula",
        ),
        evidence_role="METHOD-REFERENCE",
        geography_rule="same population boundary as the built-up observation",
        publication_status="METHOD-READY-NUMERIC-EVIDENCE-REQUIRED",
        required_numeric_evidence=(
            "population_past",
            "population_present",
            "period_years",
        ),
        limitations="Both populations must be strictly positive.",
        double_count_rule="Demographic indicator only.",
    )
)

_register_eq(
    EquationRecord(
        equation_id="BEN-LCRPGR-01",
        name="Ratio of land consumption rate to population growth rate",
        formula_text="LCRPGR = LCR / PGR",
        output_unit_contract="dimensionless ratio, or undefined when PGR is ~0",
        method_ref_ids=("REF-UNHABITAT-SDG1131-2025",),
        exact_source_locations=(_UNH_LOC_LCR,),
        evidence_role="METHOD-REFERENCE",
        geography_rule="LCR and PGR must span the IDENTICAL analysis period",
        publication_status="METHOD-READY-NUMERIC-EVIDENCE-REQUIRED",
        required_numeric_evidence=("lcr_inputs", "pgr_inputs"),
        limitations=(
            "When PGR is zero or numerically near zero the ratio is undefined and "
            "is reported as undefined with a diagnostic. It is never replaced by "
            "zero and never divided through an epsilon."
        ),
        double_count_rule="Spatial/demographic indicator only.",
    )
)

_register_eq(
    EquationRecord(
        equation_id="BEN-BUILTUP-PC-01",
        name="Built-up area per capita",
        formula_text="BuiltUpPerCapita = UrBU_t / Pop_t",
        output_unit_contract="m2 per person (built-up unit must be m2)",
        method_ref_ids=("REF-UNHABITAT-SDG1131-2025",),
        exact_source_locations=(_UNH_LOC_P9,),
        evidence_role="METHOD-REFERENCE",
        geography_rule="area and population must share one boundary and one year",
        publication_status="METHOD-READY-NUMERIC-EVIDENCE-REQUIRED",
        required_numeric_evidence=("built_up_area", "population"),
        limitations="Population must be strictly positive.",
        double_count_rule="Spatial indicator only.",
    )
)

_register_eq(
    EquationRecord(
        equation_id="BEN-IO-A-01",
        name="Input-output technical coefficients",
        formula_text="a_ij = x_ij / X_j",
        output_unit_contract="dimensionless coefficient matrix",
        method_ref_ids=("REF-EGY-IO-ALAYOUTY-2022",),
        exact_source_locations=(_IO_LOC,),
        evidence_role="METHOD-REFERENCE",
        geography_rule=(
            "the transactions table must state its economy and its base year; the "
            "reviewed Egyptian table is 2016-2017"
        ),
        publication_status="METHOD-READY-NUMERIC-EVIDENCE-REQUIRED",
        required_numeric_evidence=("transactions_matrix", "total_output_vector"),
        limitations="Every sector total output must be strictly positive.",
        double_count_rule="Economic structure, not a welfare benefit.",
    )
)

_register_eq(
    EquationRecord(
        equation_id="BEN-IO-L-01",
        name="Leontief inverse",
        formula_text="L = (I - A)^-1",
        output_unit_contract="dimensionless total-requirements matrix",
        method_ref_ids=("REF-EGY-IO-ALAYOUTY-2022",),
        exact_source_locations=(_IO_LOC,),
        evidence_role="METHOD-REFERENCE",
        geography_rule="inherits the geography and base year of A",
        publication_status="METHOD-READY-NUMERIC-EVIDENCE-REQUIRED",
        required_numeric_evidence=("technical_coefficients",),
        limitations=(
            "A must be square and finite, and I - A must be genuinely invertible. "
            "A near-singular system raises a scientific input error rather than "
            "silently falling back to a pseudo-inverse."
        ),
        double_count_rule="Economic structure, not a welfare benefit.",
    )
)

_register_eq(
    EquationRecord(
        equation_id="BEN-IO-DELTA-01",
        name="Output response to a final-demand change",
        formula_text="dx = L * dy",
        output_unit_contract="same monetary unit and price basis as the demand change",
        method_ref_ids=("REF-EGY-IO-ALAYOUTY-2022",),
        exact_source_locations=(_IO_LOC,),
        evidence_role="DERIVED/APPLIED-METHOD",
        geography_rule=(
            "the demand change must be expressed in the price basis of the I-O "
            "table, not in current project prices"
        ),
        publication_status="DERIVED-METHOD-NUMERIC-EVIDENCE-REQUIRED",
        required_numeric_evidence=("leontief_inverse", "final_demand_change"),
        limitations=(
            "Standard application of the sourced Leontief inverse; the exact "
            "symbol arrangement is not quoted verbatim from the Egyptian paper."
        ),
        double_count_rule=(
            "Economic activity, NOT a CBA welfare benefit. It must never be added "
            "to monetised time savings."
        ),
    )
)

_register_eq(
    EquationRecord(
        equation_id="BEN-IO-OMULT-01",
        name="Output multiplier",
        formula_text="OMULT_j = sum_i l_ij",
        output_unit_contract="dimensionless multiplier per sector",
        method_ref_ids=("REF-EGY-IO-ALAYOUTY-2022",),
        exact_source_locations=(_IO_LOC,),
        evidence_role="METHOD-REFERENCE",
        geography_rule="inherits the geography and base year of L",
        publication_status="METHOD-READY-NUMERIC-EVIDENCE-REQUIRED",
        required_numeric_evidence=("leontief_inverse",),
        limitations="Column sums of the total-requirements matrix.",
        double_count_rule="A ratio, not a benefit.",
    )
)

_register_eq(
    EquationRecord(
        equation_id="BEN-IO-EMULT-01",
        name="Employment multiplier",
        formula_text="EMULT_j = (sum_i w_i * l_ij) / w_j",
        output_unit_contract="dimensionless multiplier per sector",
        method_ref_ids=("REF-EGY-IO-ALAYOUTY-2022",),
        exact_source_locations=(
            "REF-EGY-IO-ALAYOUTY-2022 methodology p.12, employment multiplier",
        ),
        evidence_role="METHOD-REFERENCE",
        geography_rule="employment coefficients must belong to the same table",
        publication_status="METHOD-READY-NUMERIC-EVIDENCE-REQUIRED",
        required_numeric_evidence=("employment_coefficients", "leontief_inverse"),
        limitations=(
            "This is a MULTIPLIER. The paper's reported ~1.44-type value is not "
            "jobs per EGP and not jobs per USD, so jobs = CAPEX * 1.44 is a "
            "category error and is prohibited."
        ),
        double_count_rule="A ratio, not a job count.",
    )
)

_register_eq(
    EquationRecord(
        equation_id="BEN-JOBS-PROXY-01",
        name="Jobs supported per unit investment (proxy benchmark)",
        formula_text="Jobs_proxy = Investment_million_constant2015USD * JobContent",
        output_unit_contract="jobs, on a constant-2015-USD investment basis",
        method_ref_ids=("REF-MOSZORO-2024",),
        exact_source_locations=(
            "REF-MOSZORO-2024 results tables reporting jobs per US$1 million; "
            "monetary data standardised to constant 2015 USD",
        ),
        evidence_role="REF-PROXY",
        geography_rule=(
            "cross-country emerging-market benchmark; not a Cairo measurement"
        ),
        publication_status="PROXY-ONLY",
        required_numeric_evidence=(
            "proxy_investment_constant_2015_usd_m",
            "jobs_per_musd_proxy",
        ),
        limitations=(
            "Label the result 'model benchmark / proxy jobs supported', never "
            "'Cairo jobs created'. The investment must be in the same constant "
            "2015 USD basis or the conversion must be documented."
        ),
        double_count_rule=(
            "Never added to officially reported project jobs. The two are "
            "different evidence products measuring different things."
        ),
    )
)

_register_eq(
    EquationRecord(
        equation_id="BEN-NOISE-PHYS-01",
        name="Same-metric receptor noise difference",
        formula_text="dL_r = L_baseline,r - L_project,r",
        output_unit_contract="dB difference at one receptor, signed",
        method_ref_ids=("REF-EU-NOISE-2002", "REF-EU-CNOSSOS-2015"),
        exact_source_locations=(
            "REF-EU-NOISE-2002 Lden/Lnight indicator definitions",
            "REF-EU-CNOSSOS-2015 common noise assessment methods",
        ),
        evidence_role="STANDARD-REFERENCE",
        geography_rule=(
            "one receptor, one metric, one assessment period, one method for both "
            "the baseline and the project level"
        ),
        publication_status="CONDITIONAL-ACOUSTIC-STUDY-REQUIRED",
        required_numeric_evidence=("baseline_db", "project_db"),
        limitations=(
            "dB is logarithmic. noise_delta_db / baseline_db is not a percentage "
            "reduction and is prohibited. Levels at different receptors are never "
            "averaged arithmetically."
        ),
        double_count_rule=(
            "Physical only. Monetisation is BLOCKED until exposed population and "
            "an explicit valuation basis are supplied."
        ),
    )
)


# ---------------------------------------------------------------------------
# Blocked topics — recorded so the gate can explain the absence
# ---------------------------------------------------------------------------

#: Deliberately NOT equations. Each entry names what would close it.
BLOCKED_TOPICS: dict[str, str] = {
    "BEN-FORMALIZATION": (
        "Informal-sector formalization benefit is SOURCE-OPEN. The reviewed "
        "corpus supports the qualitative concept but provides no defensible "
        "quantitative causal formula for this project. Closing it requires a "
        "validated quantitative methodology."
    ),
    "BEN-CARBON-MONEY": (
        "Carbon monetisation is SOURCE-OPEN. Physical avoided tCO2e is reported; "
        "converting it to money requires an official appraisal carbon value with "
        "a declared currency and price base year."
    ),
    "BEN-NOISE-MONEY": (
        "Noise monetisation is SOURCE-OPEN. REF-EU-EXTCOST-2019 supplies the "
        "valuation framework only. Closing it requires exposed population, "
        "exposure levels and an explicit value-transfer basis for Cairo."
    ),
}


# ---------------------------------------------------------------------------
# Integrity checks
# ---------------------------------------------------------------------------

#: Substrings that would amount to an unverified journal-ranking claim in a
#: source record. The registry describes documents, not their prestige.
_QUARTILE_CLAIM_MARKERS = (
    "quartile",
    "jcr",
    "impact factor",
    "scimago",
    "sjr",
)


def _reference_text(record: ReferenceRecord) -> str:
    return " ".join(
        str(getattr(record, field))
        for field in (
            "title",
            "authors_or_issuer",
            "document_type",
            "exact_location",
            "evidence_role",
            "units_or_basis",
            "evidence_status",
            "limitations",
            "notes",
        )
    ).lower()


def validate_registry() -> list[str]:
    """Return a list of integrity problems; an empty list means the registry is sound.

    Returning problems instead of raising lets the test suite report every fault
    in one run rather than stopping at the first.
    """
    problems: list[str] = []

    for ref_id, ref in REFERENCES.items():
        if ref.ref_id != ref_id:
            problems.append(f"{ref_id}: key does not match ref_id {ref.ref_id!r}")
        if not ref.title.strip():
            problems.append(f"{ref_id}: title is blank")
        if not ref.authors_or_issuer.strip():
            problems.append(f"{ref_id}: authors_or_issuer is blank")
        if not ref.exact_location.strip():
            problems.append(f"{ref_id}: exact_location is blank")
        if not ref.geography.strip():
            problems.append(f"{ref_id}: geography is blank")
        if not ref.units_or_basis.strip():
            problems.append(f"{ref_id}: units_or_basis is blank")

        # A reference must be openable. A DOI or an official URL is enough, but
        # blank-and-blank is not, and "n/a" in both slots means unreachable.
        has_doi = bool(ref.doi.strip()) and ref.doi.strip().lower() != "n/a"
        has_url = bool(ref.official_url.strip()) and ref.official_url.strip().lower() != "n/a"
        if not (has_doi or has_url):
            problems.append(
                f"{ref_id}: neither a resolvable DOI nor an official URL is given"
            )
        if not ref.doi.strip():
            problems.append(f"{ref_id}: doi is blank; write 'n/a' explicitly")
        if not ref.official_url.strip():
            problems.append(f"{ref_id}: official_url is blank; write 'n/a' explicitly")

        if ref.evidence_status not in ALL_EVIDENCE_CLASSES:
            problems.append(
                f"{ref_id}: unknown evidence_status {ref.evidence_status!r}"
            )

        # Any source that is not itself project data must state what it cannot
        # certify, otherwise a later reader will over-claim it.
        if (
            ref.evidence_status not in PUBLICATION_ACCEPTABLE_NUMERIC_EVIDENCE
            and not ref.limitations.strip()
        ):
            problems.append(
                f"{ref_id}: non-project-data reference states no limitations"
            )

        text = _reference_text(ref)
        for marker in _QUARTILE_CLAIM_MARKERS:
            if marker in text:
                problems.append(
                    f"{ref_id}: contains a journal-ranking claim ({marker!r}); "
                    "evidence status is about authority and traceability, not "
                    "about quartiles"
                )

    for eq_id, eq in EQUATIONS.items():
        if eq.equation_id != eq_id:
            problems.append(f"{eq_id}: key does not match equation_id {eq.equation_id!r}")
        if not eq.name.strip():
            problems.append(f"{eq_id}: name is blank")
        if not eq.formula_text.strip():
            problems.append(f"{eq_id}: formula_text is blank")
        if not eq.output_unit_contract.strip():
            problems.append(f"{eq_id}: output_unit_contract is blank")
        if not eq.method_ref_ids:
            problems.append(f"{eq_id}: no method reference id")
        if not eq.exact_source_locations:
            problems.append(f"{eq_id}: no exact source location")
        for loc in eq.exact_source_locations:
            if not loc.strip():
                problems.append(f"{eq_id}: blank exact source location")
        if not eq.geography_rule.strip():
            problems.append(f"{eq_id}: geography_rule is blank")
        if not eq.publication_status.strip():
            problems.append(f"{eq_id}: publication_status is blank")

        for ref_id in eq.method_ref_ids:
            if ref_id not in REFERENCES:
                problems.append(f"{eq_id}: cites unknown reference {ref_id!r}")

        # A SOURCE-OPEN equation cannot be publication-ready. Any status that
        # merely says "ready" without naming its numeric evidence requirement is
        # the exact over-claim this registry exists to prevent.
        status = eq.publication_status.upper()
        if "SOURCE-OPEN" in status and "REQUIRED" not in status:
            problems.append(
                f"{eq_id}: SOURCE-OPEN equation is not marked as evidence-required"
            )
        if status in {"PUBLICATION-READY", "READY"}:
            problems.append(
                f"{eq_id}: bare '{eq.publication_status}' status hides the numeric "
                "evidence requirement"
            )

    return problems


def reference(ref_id: str) -> ReferenceRecord:
    """Resolve a reference id, failing loudly rather than returning None."""
    try:
        return REFERENCES[ref_id]
    except KeyError:
        raise KeyError(
            f"unknown Benefits reference id {ref_id!r}; register it in "
            "benefits_reference_registry.REFERENCES before citing it"
        ) from None


def equation(equation_id: str) -> EquationRecord:
    """Resolve an equation id, failing loudly rather than returning None."""
    try:
        return EQUATIONS[equation_id]
    except KeyError:
        raise KeyError(
            f"unknown Benefits equation id {equation_id!r}; register it in "
            "benefits_reference_registry.EQUATIONS before citing it"
        ) from None


def equation_audit_rows() -> list[dict]:
    """Flatten the equation registry for export and reviewer inspection."""
    rows: list[dict] = []
    for eq in EQUATIONS.values():
        refs = [REFERENCES[r] for r in eq.method_ref_ids if r in REFERENCES]
        rows.append(
            {
                "equation_id": eq.equation_id,
                "name": eq.name,
                "formula_text": eq.formula_text,
                "output_unit_contract": eq.output_unit_contract,
                "evidence_role": eq.evidence_role,
                "publication_status": eq.publication_status,
                "method_ref_ids": "; ".join(eq.method_ref_ids),
                "source_titles": "; ".join(r.title for r in refs),
                "exact_source_locations": " | ".join(eq.exact_source_locations),
                "doi": "; ".join(r.doi for r in refs),
                "official_url": "; ".join(r.official_url for r in refs),
                "geography_rule": eq.geography_rule,
                "required_numeric_evidence": "; ".join(eq.required_numeric_evidence),
                "limitations": eq.limitations,
                "double_count_rule": eq.double_count_rule,
            }
        )
    return rows


def reference_registry_rows() -> list[dict]:
    """Flatten the reference registry for export and reviewer inspection."""
    return [
        {
            "ref_id": r.ref_id,
            "title": r.title,
            "authors_or_issuer": r.authors_or_issuer,
            "year": r.year,
            "document_type": r.document_type,
            "doi": r.doi,
            "official_url": r.official_url,
            "local_source_file": r.local_source_file,
            "exact_location": r.exact_location,
            "geography": r.geography,
            "evidence_role": r.evidence_role,
            "units_or_basis": r.units_or_basis,
            "price_base_year": r.price_base_year,
            "evidence_status": r.evidence_status,
            "limitations": r.limitations,
            "notes": r.notes,
        }
        for r in REFERENCES.values()
    ]
