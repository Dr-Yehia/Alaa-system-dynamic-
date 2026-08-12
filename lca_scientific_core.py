"""Scientific LCA core for the monorail Streamlit application.

Purpose
-------
This module replaces the scientific LCA calculation block only. This v5 clean edition keeps full inline # REFERENCE / # SOURCE STATUS / # FUTURE-REPLACEMENT comments beside every central LCA equation and fixed numeric factor. It keeps
A1-A3, A4, A5, B2-B5, B6, C1-C4 and Module D traceable by:

1. attaching a source record to every emission factor;
2. attaching a source statement to every equation;
3. placing an inline ``# REFERENCE`` / ``# SOURCE STATUS`` comment immediately
   beside every scientific equation and fixed numerical factor;
4. refusing to silently use open/unverified factors;
5. keeping Module D separate from the gross A-C result;
6. using explicit unit conversions and sourced project activity data.

INLINE COMMENT CONVENTION
-------------------------
# REF-VERIFIED       Directly copied from a named uploaded source and exact row/page.
# REF-PROXY          Documented source, but geography/technology is not project-specific.
# REF-DERIVED        Arithmetic combination derived only from verified source values.
# METHOD-REFERENCE   Source of the equation/method; no universal numeric value implied.
# PROJECT-SOURCE-REQUIRED  Project quantity/scenario must carry its own source.
# SOURCE-OPEN        No acceptable source is currently available; blocks publication.
# SCENARIO-ONLY      Permitted only for scenario/sensitivity analysis, not as a fact.
# FUTURE-REPLACEMENT The exact evidence that must replace the current proxy/open value.
# UNIT-DEFINITION    Exact conversion or dimensional identity, not empirical evidence.

The UI/dashboard/heuristic score code is intentionally not included here because
those parts are not part of the ISO/RICS LCA result.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping, Optional, Sequence
import math

import pandas as pd


# -----------------------------------------------------------------------------
# Exact unit conversions. These are definitions, not empirical scientific data.
# -----------------------------------------------------------------------------
KG_PER_TONNE = 1000.0
KG_CO2E_PER_TONNE_CO2E = 1000.0

# UNIT-DEFINITION: 1 metric tonne = 1000 kg; SI unit conversion, no empirical source needed.
# UNIT-DEFINITION: 1 tCO2e = 1000 kgCO2e; SI reporting conversion.

# SCENARIO/GOVERNANCE — frozen factor year for reproducibility.
# DESNZ 2026 factors exist; 2025 remains intentionally pinned until a controlled
# factor-year migration and regression review are approved.
ASSESSMENT_FACTOR_YEAR = 2025

REFERENCE_CATALOG: dict[str, dict[str, str]] = {
    "RICS_WLCA_2024": {
        "organization": "Royal Institution of Chartered Surveyors (RICS)",
        "title": "Whole life carbon assessment for the built environment",
        "identifier": "RICS Professional Standard, Global",
        "edition": "2nd edition, September 2023",
        "version": "Version 3, August 2024",
        "publication_date": "2024-08",
        "effective_date": "2024-07-01",
        "publisher": "Royal Institution of Chartered Surveyors (RICS)",
        "file": "Whole_life_carbon_assessment_PS_Sept23.pdf",
        "geography": "Global standard; UK defaults explicitly identified where applicable",
        "evidence_status": "REF-VERIFIED-METHOD",
        "notes": "Primary method source for A1-C4 modular reporting, A4/A5/C2 and Module D guidance.",
    },
    "ISO_14040_2006": {
        "organization": "International Organization for Standardization (ISO)",
        "title": "Environmental management — Life cycle assessment — Principles and framework",
        "identifier": "ISO 14040:2006",
        "edition": "Edition 2",
        "version": "2006",
        "publication_date": "2006-07",
        "publisher": "ISO",
        "file": "official ISO standard / licensed copy if available",
        "geography": "International",
        "evidence_status": "METHOD-REFERENCE",
        "notes": "Goal/scope, functional unit and LCA framework.",
    },
    "ISO_14044_2006": {
        "organization": "International Organization for Standardization (ISO)",
        "title": "Environmental management — Life cycle assessment — Requirements and guidelines",
        "identifier": "ISO 14044:2006",
        "edition": "Edition 1",
        "version": "2006",
        "publication_date": "2006-07",
        "publisher": "ISO",
        "file": "official ISO standard / licensed copy if available",
        "geography": "International",
        "evidence_status": "METHOD-REFERENCE",
        "notes": "LCA requirements and reporting framework.",
    },
    "BS_EN_15804_A2": {
        "organization": "British Standards Institution (BSI) / CEN",
        "title": "Sustainability of construction works. Environmental product declarations. Core rules for the product category of construction products",
        "identifier": "BS EN 15804:2012+A2:2019",
        "edition": "A2:2019",
        "version": "EN 15804:2012+A2:2019/AC:2021 aligned",
        "publication_date": "2019",
        "publisher": "BSI / CEN",
        "file": "licensed standard if available; equation reproduced through RICS Appendix K",
        "geography": "European/UK standard",
        "evidence_status": "METHOD-REFERENCE",
        "notes": "EPD/PCR framework and Module D net-flow principle.",
    },
    "BS_EN_17472_2022": {
        "organization": "British Standards Institution (BSI) / CEN",
        "title": "Sustainability of construction works. Sustainability assessment of civil engineering works. Calculation methods",
        "identifier": "BS EN 17472:2022",
        "edition": "2022",
        "version": "2022",
        "publication_date": "2022-03-31",
        "publisher": "BSI / CEN",
        "file": "licensed standard if available",
        "geography": "Civil engineering works",
        "evidence_status": "METHOD-REFERENCE",
        "notes": "Infrastructure/civil-engineering assessment context for the monorail project.",
    },
    "UK_GHG_2025_METHOD": {
        "organization": "UK Department for Energy Security and Net Zero (DESNZ)",
        "title": "2025 Government greenhouse gas conversion factors for company reporting: Methodology paper",
        "identifier": "Greenhouse gas reporting: conversion factors 2025",
        "edition": "2025",
        "version": "2025 final methodology",
        "publication_date": "2025-06-10",
        "publisher": "DESNZ",
        "file": "2025-GHG-CF-methodology-paper.pdf",
        "geography": "UK proxy unless project/local data replace it",
        "evidence_status": "REF-VERIFIED-METHOD",
        "notes": "Fuel, freight, electricity, passenger rail and waste factor methodology.",
    },
    "UK_GHG_2025_DATA": {
        "organization": "UK Department for Energy Security and Net Zero (DESNZ)",
        "title": "Conversion factors 2025: full set (for advanced users)",
        "identifier": "Greenhouse gas reporting: conversion factors 2025",
        "edition": "2025",
        "version": "Full set",
        "publication_date": "2025-06-10",
        "publisher": "DESNZ",
        "file": "ghg-conversion-factors-2025-full-set.xlsx",
        "geography": "UK proxy",
        "evidence_status": "REF-PROXY-UK",
        "notes": "Numeric freight, fuel and waste factors; factor year intentionally pinned to 2025.",
    },
    "ICE_V4_1_2025": {
        "organization": "Circular Ecology",
        "title": "Inventory of Carbon & Energy (ICE) Database v4.1",
        "identifier": "ICE Database v4.1",
        "edition": "Educational V4.1",
        "version": "October 2025",
        "publication_date": "2025-10",
        "publisher": "Circular Ecology",
        "file": "ICE DB Educational V4.1 - Oct 2025.xlsx",
        "geography": "Generic/UK-influenced proxy; material-specific geography varies by record",
        "evidence_status": "REF-PROXY-PRIMARY-RECHECK-REQUIRED",
        "notes": "Values are currently mapped through the internal audit workbook; reopen the primary workbook before claiming direct-primary verification.",
    },
    "NTD_2024_ENERGY": {
        "organization": "U.S. Department of Transportation, Federal Transit Administration",
        "title": "2024 Annual Database Energy Consumption",
        "identifier": "National Transit Database (NTD)",
        "edition": "2024",
        "version": "2024 Annual Database",
        "publication_date": "2025",
        "publisher": "Federal Transit Administration",
        "file": "2024 Energy Consumption_250812.xlsx",
        "geography": "United States proxy",
        "evidence_status": "REF-DERIVED-PROXY-US",
        "notes": "Used with NTD service/PMT data to derive kWh/passenger-km proxies.",
    },
    "NTD_2024_SERVICE": {
        "organization": "U.S. Department of Transportation, Federal Transit Administration",
        "title": "TS2.1 - Service Data and Operating Expenses Time Series by Mode",
        "identifier": "National Transit Database (NTD)",
        "edition": "2024",
        "version": "2024 update",
        "publication_date": "2025",
        "publisher": "Federal Transit Administration",
        "file": "2024 TS2.1 Service Data and Operating Expenses Time Series by Mode.xlsx",
        "geography": "United States proxy",
        "evidence_status": "REF-DERIVED-PROXY-US",
        "notes": "Passenger-mile/service denominator for derived NTD energy-intensity proxies.",
    },
    "IEA_EF_2025": {
        "organization": "International Energy Agency (IEA)",
        "title": "Emissions Factors 2025",
        "identifier": "IEA data product",
        "edition": "2025",
        "version": "2025",
        "publication_date": "2025-09",
        "publisher": "International Energy Agency",
        "file": "IEA Emissions Factors 2025 database/table — numeric Egypt series not yet supplied",
        "geography": "Country annual factors",
        "evidence_status": "SOURCE-OPEN-NUMERIC-EGYPT",
        "notes": "Method/data-product reference is known; actual Egypt annual values must be supplied before use.",
    },
    "IEA_LC_UPSTREAM_2025": {
        "organization": "International Energy Agency (IEA)",
        "title": "Life Cycle Upstream Emissions Factors 2025",
        "identifier": "IEA data product",
        "edition": "2025",
        "version": "2025",
        "publication_date": "2025-10",
        "publisher": "International Energy Agency",
        "file": "IEA Life Cycle Upstream Emissions Factors 2025 database/table",
        "geography": "Country/technology life-cycle factors",
        "evidence_status": "SOURCE-OPEN-NUMERIC-EGYPT",
        "notes": "Use only if actual project/Egypt upstream values and scope are supplied.",
    },
    "CLOSED_FACTOR_AUDIT": {
        "organization": "Project internal audit",
        "title": "lca_q1_closed_numbers_from_uploaded_files.xlsx",
        "identifier": "Internal traceability index",
        "edition": "Project audit workbook",
        "version": "current uploaded audit",
        "publication_date": "not applicable",
        "publisher": "Project",
        "file": "lca_q1_closed_numbers_from_uploaded_files.xlsx",
        "geography": "not applicable",
        "evidence_status": "INTERNAL-AUDIT-NOT-PRIMARY-SOURCE",
        "notes": "Maps factors to claimed primary rows; never sufficient by itself for direct-primary verification.",
    },
}

# SOURCE-OPEN tracker copied from the uploaded project audit workbook, Still_Open sheet.
# These items must remain visible so a future programmer knows exactly what evidence is missing.
OPEN_SOURCE_REQUIREMENTS: dict[str, dict[str, str]] = {
    "EGYPT_GRID_CI_T": {
        "status": "SOURCE-OPEN",
        "needed": "IEA Emission Factors Excel/database or official Egypt annual grid-CI table",
        "reason": "Only the IEA methodology PDF was uploaded; no numeric Egypt time series was supplied.",
        "blocks": "Publication-grade B6, electricity in B2-B5, and C1 end-of-life electricity.",
    },
    "FRP_A1_A3_EF": {
        "status": "SOURCE-OPEN",
        "needed": "Product-specific FRP/GRP EPD with A1-A3 GWP, or set FRP mass to zero",
        "reason": "No acceptable FRP factor exists in the uploaded evidence set.",
        "blocks": "Publication-grade A1-A3 and any FRP waste/Module-D calculation.",
    },
    "PROJECT_A5_WASTE_RATES": {
        "status": "PROJECT-SOURCE-REQUIRED",
        "needed": "Project waste-management plan or contractor waste assumptions",
        "reason": "RICS defaults are UK proxies; the GHG file supplies treatment factors, not project generation rates.",
        "blocks": "Project-specific A5.3.",
    },
    "PROJECT_EOL_SHARES": {
        "status": "PROJECT-SOURCE-REQUIRED",
        "needed": "Project EOL plan or clearly declared documented scenario table for each material",
        "reason": "Reuse/recycling/disposal shares are project/scenario dependent.",
        "blocks": "C3, C4 and Module D.",
    },
    "MAINTENANCE_ACTIVITY_DATA": {
        "status": "PROJECT-SOURCE-REQUIRED",
        "needed": "Maintenance/repair/replacement/refurbishment schedule with materials, fuel, electricity, transport and waste",
        "reason": "Cost-to-carbon or percentage-of-A1-A3 proxies are not acceptable as the final activity model.",
        "blocks": "Publication-grade B2-B5.",
    },
    "EMBODIED_ENERGY_FACTORS": {
        "status": "SOURCE-OPEN",
        "needed": "ICE v2/legacy primary-energy source or product EPD primary-energy indicators",
        "reason": "ICE V4.1 audit used here is carbon-focused; legacy MJ/kg values are not fully closed.",
        "blocks": "Publication claim for embodied energy; carbon LCA remains available.",
    },
    "PROJECT_DENSITIES": {
        "status": "PROJECT-SOURCE-REQUIRED",
        "needed": "Project material datasheet/EPD/BOQ density or direct mass quantities",
        "reason": "Volume/area-to-mass conversion must not use silent generic densities.",
        "blocks": "Mass calculation for concrete, wood and glass when direct masses are unavailable.",
    },
    "PROJECT_RSP": {
        "status": "PROJECT-SOURCE-REQUIRED",
        "needed": "Project brief/design-life document with reference study period",
        "reason": "RSP is project-defined; 50 years must not be treated as a universal standard constant.",
        "blocks": "Lifetime B6, B2-B5 event horizon and functional-unit denominator.",
    },
}


class ScientificInputError(ValueError):
    """Raised when the model would otherwise use missing or untraceable data."""


@dataclass(frozen=True)
class Evidence:
    """A traceable numerical factor or project-specific value."""

    code: str
    value: Optional[float]
    unit: str
    stage: str
    source_file: str
    location: str
    status: str
    boundary_scope: str
    note: str = ""
    factor_basis: str = "not_applicable"
    # Citation-freeze metadata. APPEND-ONLY: parts of the registry construct Evidence
    # positionally, so these must stay at the END of the field list.
    #   source_id           -> key inside REFERENCE_CATALOG; blank ONLY for project-specific
    #                          evidence, whose proof is source_file + location.
    #   source_kind         -> empirical_factor | derived_factor | default_rate |
    #                          project_specific | unit_definition
    #   reference_class     -> REF-VERIFIED | REF-PROXY | REF-DERIVED | SOURCE-OPEN | ...
    #   parent_factor_codes -> mandatory for derived (e.g. WTW = direct + WTT) factors.
    source_id: str = ""
    source_kind: str = "empirical_factor"
    reference_class: str = ""
    parent_factor_codes: tuple[str, ...] = ()

    def require_value(self) -> float:
        if self.value is None or not math.isfinite(float(self.value)):
            raise ScientificInputError(
                f"{self.code} has no usable value. Required source: "
                f"{self.source_file}, {self.location}."
            )
        return float(self.value)


@dataclass(frozen=True)
class GridCarbonYear:
    """Annual electricity carbon factor with explicit scope components.

    RICS Appendix H requires the assessor to understand which parts of the energy
    supply chain are included. For a complete B6 life-cycle factor, enter the
    generation, T&D and upstream/WTT components. A component can be zero only when
    its source explicitly states that it is zero or intentionally excluded.
    """

    year: int
    generation_kgco2e_per_kwh: float
    td_kgco2e_per_kwh: float
    upstream_kgco2e_per_kwh: float
    source_file: str
    location: str
    geographic_scope: str
    note: str = ""

    @property
    def total_kgco2e_per_kwh(self) -> float:
        return (
            float(self.generation_kgco2e_per_kwh)
            + float(self.td_kgco2e_per_kwh)
            + float(self.upstream_kgco2e_per_kwh)
        )


@dataclass(frozen=True)
class ProjectQuantity:
    """A project quantity and its provenance."""

    value: float
    unit: str
    source: str
    location: str = ""

    def require_nonnegative(self, label: str) -> float:
        value = float(self.value)
        if not math.isfinite(value) or value < 0.0:
            raise ScientificInputError(f"{label} must be a finite non-negative value.")
        if not str(self.source).strip():
            raise ScientificInputError(f"{label} requires a project-data source.")
        return value


# -----------------------------------------------------------------------------
# EQUATION REGISTRY (citation freeze)
#
# Every entry is explicitly CLASSIFIED so a reviewer can tell at a glance what kind
# of statement it is:
#   METHOD-REFERENCE      the equation is stated by a named standard/method source;
#   REF-DERIVED           an algebraic/derived form built on a standard's definitions;
#   ACCOUNTING-IDENTITY   a bookkeeping identity (sums, mass balance) needing no source;
#   UNIT-DEFINITION       an exact unit conversion, not empirical evidence.
# `source_ids` resolve against REFERENCE_CATALOG, which holds the FULL bibliographic
# identity (organization, exact title, identifier, edition, version, date). Comments
# therefore never need to restate abbreviated titles.
# -----------------------------------------------------------------------------
EQUATIONS: dict[str, dict[str, Any]] = {
    "E1_A1_A3": {
        "stage": "A1-A3",
        "equation": "I_A1-A3,j = M_j * EF_j / 1000",
        "unit_check": "kg * kgCO2e/kg / 1000 = tCO2e",
        "reference_class": "METHOD-REFERENCE",
        "source_ids": ["RICS_WLCA_2024", "ISO_14040_2006", "ISO_14044_2006"],
        "source_location": "RICS product stage A1-A3 / section 5.1.2; material quantity × embodied-carbon factor; ISO goal/scope and inventory framework",
        "note": "Numeric EF provenance is stored per Evidence record.",
    },
    "E2_EFFECTIVE_EF": {
        "stage": "A1-A3 recycled-content conditional mixing",
        "equation": "EF_eff = (1 - RC) * EF_virgin + RC * EF_secondary",
        "unit_check": "fraction * kgCO2e/kg + fraction * kgCO2e/kg = kgCO2e/kg",
        "reference_class": "REF-DERIVED-INPUT-CONDITIONAL",
        "source_ids": ["BS_EN_15804_A2", "RICS_WLCA_2024"],
        "source_location": "Inventory aggregation logic; NOT a universal Module-D/credit equation",
        "note": "Use only when base EF is explicitly virgin and secondary-route EF is independently documented. Never apply to a market-average EF already containing recycled input.",
    },
    "E3_TRANSPORT_LEG": {
        "stage": "A4/C2/A5 waste/B2-B5 transport computational leg",
        "equation": "I_leg = (M_kg / 1000) * D_km * EF_kgCO2e_per_tkm / 1000",
        "unit_check": "t * km * kgCO2e/(t.km) / 1000 = tCO2e",
        "reference_class": "ACCOUNTING-IDENTITY-METHOD-IMPLEMENTATION",
        "source_ids": ["RICS_WLCA_2024", "UK_GHG_2025_DATA"],
        "source_location": "RICS A4 section 5.1.3 and C2 section 5.6.3; DESNZ freight worksheets for numeric EF",
        "note": "This is ONE explicit leg. Full RICS A4/C2 route closure additionally requires outward + documented return/empty-running treatment where applicable.",
    },
    "E3A_RICS_A4": {
        "stage": "A4",
        "equation": "A4 = M * D * [EF_outward + empty_running_factor * EF_return]",
        "unit_check": "mass * distance * transport factor = carbon impact; implementation normalises to tCO2e",
        "reference_class": "METHOD-REFERENCE",
        "source_ids": ["RICS_WLCA_2024"],
        "source_location": "Section 5.1.3 Transport impacts (A4)",
        "note": "For non-UK projects do not silently apply the UK 43% empty-running default; use project/local evidence or disclose proxy/scenario.",
    },
    "E3C_RICS_C2": {
        "stage": "C2",
        "equation": "C2 = M * D * [EF_outward + empty_running_factor * EF_return]",
        "unit_check": "mass * distance * transport factor = carbon impact; implementation normalises to tCO2e",
        "reference_class": "METHOD-REFERENCE",
        "source_ids": ["RICS_WLCA_2024"],
        "source_location": "Section 5.6.3 Transport impacts (C2)",
        "note": "C2 route must close return/empty-running assumptions where applicable; remaining mass comes from post-B2-B5 balance.",
    },
    "E4_FUEL": {
        "stage": "A5/C1/B2-B5",
        "equation": "I_fuel = Activity_fuel_L * EF_fuel_kgCO2e_per_L / 1000",
        "unit_check": "L * kgCO2e/L / 1000 = tCO2e",
        "reference_class": "METHOD-REFERENCE",
        "source_ids": ["UK_GHG_2025_METHOD", "UK_GHG_2025_DATA"],
        "source_location": "DESNZ fuel methodology; Fuels and WTT-fuels worksheets",
        "note": "UK factor is a proxy unless project/local fuel factor is supplied.",
    },
    "E5_ELECTRICITY": {
        "stage": "A5/B2-B5/B6/C1",
        "equation": "I_electricity,t = E_t * CI_t / 1000",
        "unit_check": "kWh * kgCO2e/kWh / 1000 = tCO2e",
        "reference_class": "METHOD-REFERENCE-NUMERIC-SOURCE-CONDITIONAL",
        "source_ids": ["RICS_WLCA_2024", "IEA_EF_2025", "IEA_LC_UPSTREAM_2025"],
        "source_location": "RICS operational-energy reporting + IEA annual-factor data products",
        "note": "Egypt/project numeric CI_t remains SOURCE-OPEN until actual annual values are supplied.",
    },
    "E6_B6_ENERGY": {
        "stage": "B6",
        "equation": "E_t = PKM_t * EI_t",
        "unit_check": "passenger-km * kWh/passenger-km = kWh",
        "reference_class": "METHOD-REFERENCE",
        "source_ids": ["UK_GHG_2025_METHOD"],
        "source_location": "Light-rail/tram energy-intensity methodology/table; project operational/design data preferred",
        "note": "Proxy EI must remain labelled proxy; project EI needs its own source.",
    },
    "E6A_ANNUAL_SERVICE": {
        "stage": "B6 service denominator",
        "equation": "Served_day,t = min(Demand_day,t, Capacity_day,t); PKM_t = Served_day,t * TripLength_t * Availability_t * OperatingDays_t",
        "unit_check": "passengers/day * km/passenger * fraction * day/year = passenger-km/year",
        "reference_class": "REF-DERIVED-PROJECT-SERVICE-MODEL",
        "source_ids": ["ISO_14040_2006", "ISO_14044_2006"],
        "source_location": "Functional-unit/service-model derivation; every project input must be sourced",
        "note": "Not a universal standard equation. It is the declared project service-model implementation. Direct sourced annual PKM may be used instead.",
    },
    "E7_WASTE": {
        "stage": "A5/C3/C4/B2-B5",
        "equation": "I_waste = (W_kg / 1000) * EF_waste_kgCO2e_per_tonne / 1000",
        "unit_check": "t waste * kgCO2e/t waste / 1000 = tCO2e",
        "reference_class": "METHOD-IMPLEMENTATION",
        "source_ids": ["UK_GHG_2025_METHOD", "UK_GHG_2025_DATA", "RICS_WLCA_2024"],
        "source_location": "DESNZ waste methodology/workbook; RICS A5/C-stage route logic",
        "note": "Never interpret kgCO2e/tonne as kgCO2e/kg.",
    },
    "E8_WASTE_FROM_INSTALLED": {
        "stage": "A5.3",
        "equation": "W_extra = M_installed * WR / (1 - WR)",
        "unit_check": "kg * fraction / fraction = kg",
        "reference_class": "REF-DERIVED-ALGEBRAIC",
        "source_ids": ["RICS_WLCA_2024"],
        "source_location": "RICS defines WR as fraction of material brought to site that is wasted; equation is algebraically derived for installed-mass BOQ basis",
        "note": "Do not label this exact algebraic form as a verbatim RICS equation.",
    },
    "E9_B2_B5": {
        "stage": "B2-B5",
        "equation": "I_event = I_new_materials + I_fuel + I_electricity + I_transport + I_waste; I_B2-B5 = sum(I_event)",
        "unit_check": "all terms are tCO2e before summation",
        "reference_class": "REF-DERIVED-ACTIVITY-INVENTORY",
        "source_ids": ["RICS_WLCA_2024", "BS_EN_17472_2022"],
        "source_location": "RICS B2-B5 modular activity inventory; project O&M plan supplies event data",
        "note": "Not cost-to-carbon and not percentage-of-A1-A3. Carbon is not financially discounted.",
    },
    "E10_C1_C4": {
        "stage": "C1-C4",
        "equation": "I_C1-C4 = I_C1 + I_C2 + I_C3 + I_C4",
        "unit_check": "tCO2e + tCO2e + tCO2e + tCO2e = tCO2e",
        "reference_class": "METHOD-REFERENCE",
        "source_ids": ["RICS_WLCA_2024", "BS_EN_17472_2022"],
        "source_location": "RICS section 5.6, modules C1-C4",
        "note": "C-stage mass must come from remaining mass after B2-B5, not a free user mass.",
    },
    "E11_MODULE_D": {
        "stage": "D1",
        "equation": "D1_standard_signed = Q_net * (EF_recovery_after_EoW - q_quality * EF_primary_substituted) / 1000; Q_net = Q_recovered_out - Q_secondary_in",
        "unit_check": "kg * kgCO2e/kg / 1000 = tCO2e",
        "reference_class": "METHOD-REFERENCE",
        "source_ids": ["RICS_WLCA_2024", "BS_EN_15804_A2"],
        "source_location": "RICS Appendix K, Module D1 calculation; equation taken from EN 15804:2012+A2:2019",
        "note": "Standard signed convention: negative = potential benefit; positive = potential load. Quality ratio multiplies the substituted primary-material term, NOT the recovery burden.",
    },
    "E12_GROSS": {
        "stage": "A-C total",
        "equation": "Gross_A-C = A1-A3 + A4 + A5 + B2-B5 + B6 + C1-C4",
        "unit_check": "sum of tCO2e modules",
        "reference_class": "METHOD-REFERENCE-MODULAR-SUM",
        "source_ids": ["RICS_WLCA_2024", "BS_EN_17472_2022"],
        "source_location": "RICS modular reporting structure; Module D reported separately",
        "note": "Module D is excluded from Gross A-C.",
    },
    "E13_FUNCTIONAL_UNIT": {
        "stage": "Functional unit",
        "equation": "GWP_kgCO2e_per_pkm = Gross_A-C_tCO2e * 1000 / Lifetime_PKM",
        "unit_check": "tCO2e * 1000 kg/t / passenger-km = kgCO2e/pkm",
        "reference_class": "REF-DERIVED-FUNCTIONAL-UNIT-REPORTING",
        "source_ids": ["ISO_14040_2006", "ISO_14044_2006", "BS_EN_17472_2022"],
        "source_location": "Declared study functional unit = 1 passenger-km; denominator must come from sourced project service data",
        "note": "This exact division is the project reporting implementation, not a universal fixed numerical factor.",
    },
}



# -----------------------------------------------------------------------------
# VERIFIED / AUDITED FACTOR REGISTRIES
# Numerical values are copied from the uploaded closed-factor audit workbook.
# -----------------------------------------------------------------------------
MATERIAL_EF: dict[str, Evidence] = {
    # REF-PROXY / PRIMARY-RECHECK-REQUIRED — Circular Ecology,
    # "Inventory of Carbon & Energy (ICE) Database v4.1",
    # Educational V4.1, October 2025,
    # project-audit mapping -> ICE Summary row 277. Value 0.10336134453781512 kgCO2e/kg.
    # SCOPE: UK average concrete proxy, not a project mix.
    # CURRENT VERIFICATION LIMIT: the primary ICE workbook was NOT independently
    # reopened during the citation freeze; this is traceable through the internal
    # project-audit mapping only. Do NOT call it direct-primary verified yet.
    # FUTURE-REPLACEMENT: project concrete grade/mix EPD or supplier-specific verified data.
    "concrete": Evidence(
        code="ICE-CONCRETE-AVG-UK-ROW277",
        value=0.10336134453781512,
        unit="kgCO2e/kg",
        stage="A1-A3",
        source_file="ICE DB Educational V4.1 - Oct 2025.xlsx",
        location="ICE Summary row 277",
        status="verified_via_internal_audit_proxy_primary_recheck_required",
        boundary_scope="A1-A3; average UK concrete mix",
        note=(
            "Use only when no project-specific concrete mix/EPD is available. "
            "RICS prefers project-specific concrete grade and mix."
        ),
        factor_basis="market_average",
        source_id="ICE_V4_1_2025",
        source_kind="empirical_factor",
        reference_class="REF-PROXY-PRIMARY-RECHECK-REQUIRED",
    ),
    # REF-PROXY / PRIMARY-RECHECK-REQUIRED — Circular Ecology,
    # "Inventory of Carbon & Energy (ICE) Database v4.1",
    # Educational V4.1, October 2025,
    # project-audit mapping -> ICE Summary row 893 (Steel, Section, A1-A3). Value 1.61 kgCO2e/kg.
    # CURRENT VERIFICATION LIMIT: the primary ICE workbook was NOT independently
    # reopened during the citation freeze; this is traceable through the internal
    # project-audit mapping only. Do NOT call it direct-primary verified yet.
    # FUTURE-REPLACEMENT: separate rebar, rail, plate and section factors if the BOQ distinguishes them.
    "steel": Evidence(
        code="ICE-STEEL-SECTION-ROW893",
        value=1.61,
        unit="kgCO2e/kg",
        stage="A1-A3",
        source_file="ICE DB Educational V4.1 - Oct 2025.xlsx",
        location="ICE Summary row 893",
        status="verified_via_internal_audit_proxy_primary_recheck_required",
        boundary_scope="A1-A3; Steel, Section",
        note="Use the A1-A3 value only. Module D remains separate.",
        factor_basis="market_average",
        source_id="ICE_V4_1_2025",
        source_kind="empirical_factor",
        reference_class="REF-PROXY-PRIMARY-RECHECK-REQUIRED",
    ),
    # REF-PROXY / PRIMARY-RECHECK-REQUIRED — Circular Ecology,
    # "Inventory of Carbon & Energy (ICE) Database v4.1",
    # Educational V4.1, October 2025,
    # project-audit mapping -> ICE Summary rows 47/58. Value 13.055539991305551 kgCO2e/kg.
    # CURRENT VERIFICATION LIMIT: the primary ICE workbook was NOT independently
    # reopened during the citation freeze; this is traceable through the internal
    # project-audit mapping only. Do NOT call it direct-primary verified yet.
    # IMPORTANT: market-average worldwide factor already includes about 31% scrap input.
    # FUTURE-REPLACEMENT: project/product EPD; do not apply an extra recycled-content mix to this factor.
    "aluminum": Evidence(
        code="ICE-ALUMINIUM-WORLD-ROW47-58",
        value=13.055539991305551,
        unit="kgCO2e/kg",
        stage="A1-A3",
        source_file="ICE DB Educational V4.1 - Oct 2025.xlsx",
        location="ICE Summary rows 47/58",
        status="verified_via_internal_audit_proxy_primary_recheck_required",
        boundary_scope="A1-A3; Aluminium General, Worldwide",
        note=(
            "ICE worldwide average already includes about 31% scrap input. "
            "Do not apply another recycled-content adjustment to this market-average factor."
        ),
        factor_basis="market_average",
        source_id="ICE_V4_1_2025",
        source_kind="empirical_factor",
        reference_class="REF-PROXY-PRIMARY-RECHECK-REQUIRED",
    ),
    # REF-PROXY / PRIMARY-RECHECK-REQUIRED — Circular Ecology,
    # "Inventory of Carbon & Energy (ICE) Database v4.1",
    # Educational V4.1, October 2025,
    # project-audit mapping -> ICE Summary row 926. Value 0.49282614286872206 kgCO2e/kg.
    # CURRENT VERIFICATION LIMIT: the primary ICE workbook was NOT independently
    # reopened during the citation freeze; this is traceable through the internal
    # project-audit mapping only. Do NOT call it direct-primary verified yet.
    # SCOPE: timber average, no carbon storage; conservative until biogenic carbon and EOL are modelled.
    "wood": Evidence(
        code="ICE-TIMBER-NO-STORAGE-ROW926",
        value=0.49282614286872206,
        unit="kgCO2e/kg",
        stage="A1-A3",
        source_file="ICE DB Educational V4.1 - Oct 2025.xlsx",
        location="ICE Summary row 926",
        status="verified_via_internal_audit_proxy_primary_recheck_required",
        boundary_scope="A1-A3; timber average; no carbon storage",
        note="Conservative core until biogenic carbon and EOL are fully modelled.",
        factor_basis="market_average",
        source_id="ICE_V4_1_2025",
        source_kind="empirical_factor",
        reference_class="REF-PROXY-PRIMARY-RECHECK-REQUIRED",
    ),
    # SOURCE-OPEN: no verified FRP/GRP A1-A3 factor is available in the uploaded evidence.
    # REQUIRED: product-specific EPD PDF with A1-A3 GWP, declared unit and validity period.
    # PUBLICATION RULE: set FRP mass = 0 or provide an approved factor override.
    "frp": Evidence(
        code="FRP-OPEN-EPD-REQUIRED",
        value=None,
        unit="kgCO2e/kg",
        stage="A1-A3",
        source_file="Not provided",
        location="Product-specific EPD required",
        status="OPEN",
        boundary_scope="A1-A3",
        note="Set FRP mass to zero for publication or supply a verified product-specific EPD.",
        factor_basis="unknown",
        source_id="",
        source_kind="empirical_factor",
        reference_class="SOURCE-OPEN",
    ),
    # REF-PROXY / PRIMARY-RECHECK-REQUIRED — Circular Ecology,
    # "Inventory of Carbon & Energy (ICE) Database v4.1",
    # Educational V4.1, October 2025,
    # project-audit mapping -> ICE Summary row 618. Value 1.4369670638496768 kgCO2e/kg.
    # PROJECT-SOURCE-REQUIRED: area-to-mass conversion needs sourced thickness and density.
    # CURRENT VERIFICATION LIMIT: the primary ICE workbook was NOT independently
    # reopened during the citation freeze; this is traceable through the internal
    # project-audit mapping only. Do NOT call it direct-primary verified yet.
    "glass": Evidence(
        code="ICE-GLASS-GENERAL-ROW618",
        value=1.4369670638496768,
        unit="kgCO2e/kg",
        stage="A1-A3",
        source_file="ICE DB Educational V4.1 - Oct 2025.xlsx",
        location="ICE Summary row 618",
        status="verified_via_internal_audit_proxy_primary_recheck_required",
        boundary_scope="A1-A3; Glass, General, per kg",
        note="If the UI starts from area, convert area and thickness to mass using a sourced density.",
        factor_basis="market_average",
        source_id="ICE_V4_1_2025",
        source_kind="empirical_factor",
        reference_class="REF-PROXY-PRIMARY-RECHECK-REQUIRED",
    ),
}


TRANSPORT_EF: dict[str, dict[str, Evidence]] = {
    # REFERENCE FAMILY: UK Government GHG Conversion Factors 2025, freight worksheets.
    # REF-PROXY: UK fleet/mode averages. Replace with local route/vehicle factors when available.
    "truck": {
        # REF-PROXY-UK — UK Department for Energy Security and Net Zero (DESNZ),
        # "Greenhouse gas reporting: conversion factors 2025",
        # "Conversion factors 2025: full set (for advanced users)",
        # published 10 June 2025, worksheet "Freighting goods", row 63.
        # Value 0.10163 kgCO2e/tonne.km.
        # SCOPE: direct/TTW only.
        "direct": Evidence(
            "GHG25-HGV-ALL-AVG-LADEN-DIRECT",
            0.10163,
            "kgCO2e/tonne.km",
            "A4/C2",
            "ghg-conversion-factors-2025-full-set.xlsx",
            "Freighting goods row 63",
            "verified_proxy_UK",
            "All HGV average laden; direct",
            "Use a project/local vehicle class factor when known.",
            source_id="UK_GHG_2025_DATA",
            source_kind="empirical_factor",
            reference_class="REF-PROXY-UK",
        ),
        # REF-PROXY-UK — UK Department for Energy Security and Net Zero (DESNZ),
        # "Greenhouse gas reporting: conversion factors 2025",
        # "Conversion factors 2025: full set (for advanced users)",
        # published 10 June 2025, worksheet "WTT - delivery vehicles & freight", row 57.
        # Value 0.02359 kgCO2e/tonne.km.
        # SCOPE: upstream/WTT only.
        "wtt": Evidence(
            "GHG25-HGV-ALL-AVG-LADEN-WTT",
            0.02359,
            "kgCO2e/tonne.km",
            "A4/C2",
            "ghg-conversion-factors-2025-full-set.xlsx",
            "WTT - delivery vehicles & freight row 57",
            "verified_proxy_UK",
            "Fuel upstream/WTT",
            source_id="UK_GHG_2025_DATA",
            source_kind="empirical_factor",
            reference_class="REF-PROXY-UK",
        ),
        # REF-DERIVED-PROXY-UK — 0.12522 = 0.10163 direct + 0.02359 WTT.
        # Parent factors: GHG25-HGV-ALL-AVG-LADEN-DIRECT + GHG25-HGV-ALL-AVG-LADEN-WTT.
        # Parent source: DESNZ 2025 full factor set, Freighting goods row 63 + WTT - delivery vehicles & freight row 57.
        # IMPORTANT: select WTW OR direct-only; never add WTT twice.
        "wtw": Evidence(
            "GHG25-HGV-ALL-AVG-LADEN-WTW",
            0.12522,
            "kgCO2e/tonne.km",
            "A4/C2",
            "ghg-conversion-factors-2025-full-set.xlsx",
            "row 63 direct + row 57 WTT",
            "verified_derived_proxy_UK",
            "Direct + WTT",
            "0.10163 + 0.02359 = 0.12522",
            source_id="UK_GHG_2025_DATA",
            source_kind="derived_factor",
            reference_class="REF-DERIVED-PROXY-UK",
            parent_factor_codes=("GHG25-HGV-ALL-AVG-LADEN-DIRECT", "GHG25-HGV-ALL-AVG-LADEN-WTT",),
        ),
    },
    "rail": {
        # REF-PROXY-UK — UK Department for Energy Security and Net Zero (DESNZ),
        # "Greenhouse gas reporting: conversion factors 2025",
        # "Conversion factors 2025: full set (for advanced users)",
        # published 10 June 2025, worksheet "Freighting goods", row 106.
        # Value 0.02779 kgCO2e/tonne.km.
        # SCOPE: direct/TTW only.
        "direct": Evidence(
            "GHG25-RAIL-FREIGHT-DIRECT",
            0.02779,
            "kgCO2e/tonne.km",
            "A4/C2",
            "ghg-conversion-factors-2025-full-set.xlsx",
            "Freighting goods row 106",
            "verified_proxy_UK",
            "Rail freight direct",
            source_id="UK_GHG_2025_DATA",
            source_kind="empirical_factor",
            reference_class="REF-PROXY-UK",
        ),
        # REF-PROXY-UK — UK Department for Energy Security and Net Zero (DESNZ),
        # "Greenhouse gas reporting: conversion factors 2025",
        # "Conversion factors 2025: full set (for advanced users)",
        # published 10 June 2025, worksheet "WTT - delivery vehicles & freight", row 100.
        # Value 0.00691 kgCO2e/tonne.km.
        # SCOPE: upstream/WTT only.
        "wtt": Evidence(
            "GHG25-RAIL-FREIGHT-WTT",
            0.00691,
            "kgCO2e/tonne.km",
            "A4/C2",
            "ghg-conversion-factors-2025-full-set.xlsx",
            "WTT - delivery vehicles & freight row 100",
            "verified_proxy_UK",
            "Rail freight upstream/WTT",
            source_id="UK_GHG_2025_DATA",
            source_kind="empirical_factor",
            reference_class="REF-PROXY-UK",
        ),
        # REF-DERIVED-PROXY-UK — 0.03470 = 0.02779 direct + 0.00691 WTT.
        # Parent factors: GHG25-RAIL-FREIGHT-DIRECT + GHG25-RAIL-FREIGHT-WTT.
        # Parent source: DESNZ 2025 full factor set, Freighting goods row 106 + WTT - delivery vehicles & freight row 100.
        # IMPORTANT: select WTW OR direct-only; never add WTT twice.
        "wtw": Evidence(
            "GHG25-RAIL-FREIGHT-WTW",
            0.03470,
            "kgCO2e/tonne.km",
            "A4/C2",
            "ghg-conversion-factors-2025-full-set.xlsx",
            "row 106 direct + row 100 WTT",
            "verified_derived_proxy_UK",
            "Direct + WTT",
            "0.02779 + 0.00691 = 0.03470",
            source_id="UK_GHG_2025_DATA",
            source_kind="derived_factor",
            reference_class="REF-DERIVED-PROXY-UK",
            parent_factor_codes=("GHG25-RAIL-FREIGHT-DIRECT", "GHG25-RAIL-FREIGHT-WTT",),
        ),
    },
    "ship": {
        # REF-PROXY-UK — UK Department for Energy Security and Net Zero (DESNZ),
        # "Greenhouse gas reporting: conversion factors 2025",
        # "Conversion factors 2025: full set (for advanced users)",
        # published 10 June 2025, worksheet "Freighting goods", row 152.
        # Value 0.01321 kgCO2e/tonne.km.
        # SCOPE: direct/TTW only.
        "direct": Evidence(
            "GHG25-SHIP-GENERAL-CARGO-DIRECT",
            0.01321,
            "kgCO2e/tonne.km",
            "A4/C2",
            "ghg-conversion-factors-2025-full-set.xlsx",
            "Freighting goods row 152",
            "verified_proxy_UK",
            "General cargo ship average; direct",
            source_id="UK_GHG_2025_DATA",
            source_kind="empirical_factor",
            reference_class="REF-PROXY-UK",
        ),
        # REF-PROXY-UK — UK Department for Energy Security and Net Zero (DESNZ),
        # "Greenhouse gas reporting: conversion factors 2025",
        # "Conversion factors 2025: full set (for advanced users)",
        # published 10 June 2025, worksheet "WTT - delivery vehicles & freight", row 146.
        # Value 0.00300 kgCO2e/tonne.km.
        # SCOPE: upstream/WTT only.
        "wtt": Evidence(
            "GHG25-SHIP-GENERAL-CARGO-WTT",
            0.00300,
            "kgCO2e/tonne.km",
            "A4/C2",
            "ghg-conversion-factors-2025-full-set.xlsx",
            "WTT - delivery vehicles & freight row 146",
            "verified_proxy_UK",
            "General cargo ship upstream/WTT",
            source_id="UK_GHG_2025_DATA",
            source_kind="empirical_factor",
            reference_class="REF-PROXY-UK",
        ),
        # REF-DERIVED-PROXY-UK — 0.01621 = 0.01321 direct + 0.00300 WTT.
        # Parent factors: GHG25-SHIP-GENERAL-CARGO-DIRECT + GHG25-SHIP-GENERAL-CARGO-WTT.
        # Parent source: DESNZ 2025 full factor set, Freighting goods row 152 + WTT - delivery vehicles & freight row 146.
        # IMPORTANT: select WTW OR direct-only; never add WTT twice.
        "wtw": Evidence(
            "GHG25-SHIP-GENERAL-CARGO-WTW",
            0.01621,
            "kgCO2e/tonne.km",
            "A4/C2",
            "ghg-conversion-factors-2025-full-set.xlsx",
            "row 152 direct + row 146 WTT",
            "verified_derived_proxy_UK",
            "Direct + WTT",
            "0.01321 + 0.00300 = 0.01621",
            source_id="UK_GHG_2025_DATA",
            source_kind="derived_factor",
            reference_class="REF-DERIVED-PROXY-UK",
            parent_factor_codes=("GHG25-SHIP-GENERAL-CARGO-DIRECT", "GHG25-SHIP-GENERAL-CARGO-WTT",),
        ),
    },
}

DIESEL_EF: dict[str, Evidence] = {
    # REF-PROXY-UK — UK Department for Energy Security and Net Zero (DESNZ),
    # "Greenhouse gas reporting: conversion factors 2025",
    # "Conversion factors 2025: full set (for advanced users)",
    # published 10 June 2025, worksheet "Fuels", row 72.
    # Value 2.57082 kgCO2e/L.
    # SCOPE: direct combustion (TTW) only.
    "direct": Evidence(
        "GHG25-DIESEL-AVG-BIOFUEL-DIRECT",
        2.57082,
        "kgCO2e/L",
        "A5/C1/B2-B5",
        "ghg-conversion-factors-2025-full-set.xlsx",
        "Fuels row 72",
        "verified_proxy_UK",
        "Average biofuel blend; direct combustion",
        source_id="UK_GHG_2025_DATA",
        source_kind="empirical_factor",
        reference_class="REF-PROXY-UK",
    ),
    # REF-PROXY-UK — UK Department for Energy Security and Net Zero (DESNZ),
    # "Greenhouse gas reporting: conversion factors 2025",
    # "Conversion factors 2025: full set (for advanced users)",
    # published 10 June 2025, worksheet "WTT - fuels", row 71.
    # Value 0.61101 kgCO2e/L.
    # SCOPE: upstream/WTT only.
    "wtt": Evidence(
        "GHG25-DIESEL-AVG-BIOFUEL-WTT",
        0.61101,
        "kgCO2e/L",
        "A5/C1/B2-B5",
        "ghg-conversion-factors-2025-full-set.xlsx",
        "WTT - fuels row 71",
        "verified_proxy_UK",
        "Fuel upstream/WTT",
        source_id="UK_GHG_2025_DATA",
        source_kind="empirical_factor",
        reference_class="REF-PROXY-UK",
    ),
    # REF-DERIVED-PROXY-UK — 3.18183 = 2.57082 direct + 0.61101 WTT.
    # Parent factors: GHG25-DIESEL-AVG-BIOFUEL-DIRECT + GHG25-DIESEL-AVG-BIOFUEL-WTT.
    # Parent source: DESNZ 2025 full factor set, Fuels row 72 + WTT - fuels row 71.
    # IMPORTANT: select WTW OR direct-only; never add WTT twice.
    "wtw": Evidence(
        "GHG25-DIESEL-AVG-BIOFUEL-WTW",
        3.18183,
        "kgCO2e/L",
        "A5/C1/B2-B5",
        "ghg-conversion-factors-2025-full-set.xlsx",
        "Fuels row 72 + WTT fuels row 71",
        "verified_derived_proxy_UK",
        "Direct + WTT",
        "2.57082 + 0.61101 = 3.18183",
        source_id="UK_GHG_2025_DATA",
        source_kind="derived_factor",
        reference_class="REF-DERIVED-PROXY-UK",
        parent_factor_codes=("GHG25-DIESEL-AVG-BIOFUEL-DIRECT", "GHG25-DIESEL-AVG-BIOFUEL-WTT",),
    ),
    # REF-PROXY-UK — UK Department for Energy Security and Net Zero (DESNZ),
    # "Greenhouse gas reporting: conversion factors 2025",
    # "Conversion factors 2025: full set (for advanced users)",
    # published 10 June 2025, worksheet "Outside of scopes", row 22.
    # Value 0.14 kgCO2e/L.
    # REPORTING: biogenic CO2 disclosed separately; NEVER added to gross A-C.
    "biogenic_outside_scopes": Evidence(
        "GHG25-DIESEL-BIOGENIC-OUTSIDE-SCOPES",
        0.14,
        "kgCO2e/L",
        "Outside gross LCA",
        "ghg-conversion-factors-2025-full-set.xlsx",
        "Outside of scopes row 22",
        "verified_proxy_UK",
        "Report separately; do not add to gross",
        source_id="UK_GHG_2025_DATA",
        source_kind="empirical_factor",
        reference_class="REF-PROXY-UK",
    ),
}


WASTE_EF: dict[str, Evidence] = {
    # REF-PROXY-UK — UK Department for Energy Security and Net Zero (DESNZ),
    # "Greenhouse gas reporting: conversion factors 2025",
    # "Conversion factors 2025: full set (for advanced users)",
    # published 10 June 2025, worksheet "Waste disposal" (exact rows per factor below).
    # UNIT WARNING: every value below is kgCO2e per TONNE of waste, NEVER per kg.
    "mineral_open_loop": Evidence(
        "GHG25-WASTE-MINERAL-OPEN-LOOP",
        1.00835,
        "kgCO2e/tonne waste",
        "A5/C3",
        "ghg-conversion-factors-2025-full-set.xlsx",
        "Waste disposal rows 24/27/29",
        "verified_proxy_UK",
        "Construction aggregate/concrete/asphalt/brick open-loop route",
        source_id="UK_GHG_2025_DATA",
        source_kind="empirical_factor",
        reference_class="REF-PROXY-UK",
    ),
    "mineral_landfill": Evidence(
        "GHG25-WASTE-MINERAL-LANDFILL",
        1.26338,
        "kgCO2e/tonne waste",
        "A5/C4",
        "ghg-conversion-factors-2025-full-set.xlsx",
        "Waste disposal rows 24/27/29",
        "verified_proxy_UK",
        "Construction mineral waste landfill route",
        source_id="UK_GHG_2025_DATA",
        source_kind="empirical_factor",
        reference_class="REF-PROXY-UK",
    ),
    "metal_landfill": Evidence(
        "GHG25-WASTE-METAL-LANDFILL",
        1.26435,
        "kgCO2e/tonne waste",
        "A5/C4",
        "ghg-conversion-factors-2025-full-set.xlsx",
        "Waste disposal row 31",
        "verified_proxy_UK",
        "Construction metals landfill route",
        source_id="UK_GHG_2025_DATA",
        source_kind="empirical_factor",
        reference_class="REF-PROXY-UK",
    ),
    "plastic_landfill_proxy": Evidence(
        "GHG25-WASTE-PLASTIC-LANDFILL",
        8.98311,
        "kgCO2e/tonne waste",
        "A5/C4",
        "ghg-conversion-factors-2025-full-set.xlsx",
        "Waste disposal rows 74-82",
        "verified_proxy_UK",
        "Proxy for polymer/FRP only when no product-specific EOL data exist",
        source_id="UK_GHG_2025_DATA",
        source_kind="empirical_factor",
        reference_class="REF-PROXY-UK-SCENARIO-SUBSTITUTE",
    ),
}


B6_ENERGY_INTENSITY: dict[str, Evidence] = {
    # REF-PROXY-UK — UK Department for Energy Security and Net Zero (DESNZ),
    # "2025 Government greenhouse gas conversion factors for company reporting:
    #  Methodology paper", published 10 June 2025, Table 27, page 79.
    # Value 0.124 kWh/passenger.km — UK passenger-km-weighted light-rail/tram average.
    # FUTURE-REPLACEMENT: measured/design monorail traction + station electricity / passenger-km.
    "uk_light_rail_weighted_proxy": Evidence(
        "GHG25-LIGHT-RAIL-WEIGHTED-EI",
        0.124,
        "kWh/passenger.km",
        "B6",
        "2025-GHG-CF-methodology-paper.pdf",
        "Table 27, page 79",
        "verified_proxy_UK",
        "UK weighted light-rail/tram average",
        "Use measured monorail electricity and passenger-km when available.",
        source_id="UK_GHG_2025_METHOD",
        source_kind="empirical_factor",
        reference_class="REF-PROXY-UK",
    ),
    # REF-DERIVED-PROXY-US — 0.3031307255338944 kWh/passenger.km = NTD light-rail annual
    # energy consumption / NTD light-rail annual passenger-miles (converted to pkm).
    # Parent datasets: NTD_2024_ENERGY ("2024 Annual Database Energy Consumption") and
    # NTD_2024_SERVICE ("TS2.1 - Service Data and Operating Expenses Time Series by Mode"),
    # U.S. DOT Federal Transit Administration, National Transit Database, 2024.
    "ntd_light_rail_proxy": Evidence(
        "NTD2024-LR-EI-DERIVED",
        0.3031307255338944,
        "kWh/passenger.km",
        "B6",
        "2024 NTD Energy Consumption + TS2.1 PMT",
        "Energy Consumption and PMT 2024",
        "verified_derived_proxy_US",
        "US NTD light-rail aggregate proxy",
        source_id="NTD_2024_ENERGY",
        source_kind="derived_factor",
        reference_class="REF-DERIVED-PROXY-US",
        parent_factor_codes=("NTD_2024_ENERGY", "NTD_2024_SERVICE",),
    ),
    # REF-DERIVED-PROXY-US — 0.7844814382730434 kWh/passenger.km, derived the same way for
    # the NTD "MG" (automated guideway) mode. Same parent datasets: NTD_2024_ENERGY and
    # NTD_2024_SERVICE, U.S. DOT Federal Transit Administration, 2024.
    # USE ONLY if the monorail-to-automated-guideway mode mapping is accepted and disclosed.
    "ntd_automated_guideway_proxy": Evidence(
        "NTD2024-MG-EI-DERIVED",
        0.7844814382730434,
        "kWh/passenger.km",
        "B6",
        "2024 NTD Energy Consumption + TS2.1 PMT",
        "Energy Consumption and PMT 2024",
        "verified_derived_proxy_US",
        "Monorail/automated-guideway proxy only when mode mapping is accepted",
        source_id="NTD_2024_ENERGY",
        source_kind="derived_factor",
        reference_class="REF-DERIVED-PROXY-US",
        parent_factor_codes=("NTD_2024_ENERGY", "NTD_2024_SERVICE",),
    ),
}


RICS_WASTE_RATES: dict[str, Evidence] = {
    # REF-PROXY-UK-DEFAULT — Royal Institution of Chartered Surveyors (RICS),
    # "Whole life carbon assessment for the built environment",
    # 2nd ed. September 2023, Version 3 August 2024, Table 18, page 83.
    # These are UK DEFAULT waste rates, never project-specific facts: a project waste
    # management plan always takes priority over the values below.
    "concrete_in_situ": Evidence(
        "RICS23-WR-CONCRETE-IN-SITU", 0.05, "fraction of delivered quantity", "A5.3",
        "Whole_life_carbon_assessment_PS_Sept23.pdf", "Table 18, page 83",
        "verified_default_UK", "Traditional construction default", "5%",
        source_id="RICS_WLCA_2024",
        source_kind="default_rate",
        reference_class="REF-PROXY-UK-DEFAULT",
    ),
    # REF-PROXY: 1% - RICS WLCA Sept 2023, Table 18 p.83; replace with project waste plan.
    "concrete_precast": Evidence(
        "RICS23-WR-CONCRETE-PRECAST", 0.01, "fraction of delivered quantity", "A5.3",
        "Whole_life_carbon_assessment_PS_Sept23.pdf", "Table 18, page 83",
        "verified_default_UK", "Traditional construction default", "1%",
        source_id="RICS_WLCA_2024",
        source_kind="default_rate",
        reference_class="REF-PROXY-UK-DEFAULT",
    ),
    # REF-PROXY: 10% - RICS WLCA Sept 2023, Table 18 p.83; replace with project waste plan.
    "concrete_sprayed": Evidence(
        "RICS23-WR-CONCRETE-SPRAYED", 0.10, "fraction of delivered quantity", "A5.3",
        "Whole_life_carbon_assessment_PS_Sept23.pdf", "Table 18, page 83",
        "verified_default_UK", "Traditional construction default", "10%",
        source_id="RICS_WLCA_2024",
        source_kind="default_rate",
        reference_class="REF-PROXY-UK-DEFAULT",
    ),
    # REF-PROXY: 5% - RICS WLCA Sept 2023, Table 18 p.83; reinforcement waste default.
    "steel_reinforcement": Evidence(
        "RICS23-WR-STEEL-REBAR", 0.05, "fraction of delivered quantity", "A5.3",
        "Whole_life_carbon_assessment_PS_Sept23.pdf", "Table 18, page 83",
        "verified_default_UK", "Traditional construction default", "5%",
        source_id="RICS_WLCA_2024",
        source_kind="default_rate",
        reference_class="REF-PROXY-UK-DEFAULT",
    ),
    # REF-PROXY: 1% - RICS WLCA Sept 2023, Table 18 p.83; steel-frame waste default.
    "steel_frame": Evidence(
        "RICS23-WR-STEEL-FRAME", 0.01, "fraction of delivered quantity", "A5.3",
        "Whole_life_carbon_assessment_PS_Sept23.pdf", "Table 18, page 83",
        "verified_default_UK", "Traditional construction default", "1%",
        source_id="RICS_WLCA_2024",
        source_kind="default_rate",
        reference_class="REF-PROXY-UK-DEFAULT",
    ),
    # REF-PROXY: 2% - RICS WLCA Sept 2023, Table 18 p.83; timber-frame waste default.
    "timber_frame": Evidence(
        "RICS23-WR-TIMBER-FRAME", 0.02, "fraction of delivered quantity", "A5.3",
        "Whole_life_carbon_assessment_PS_Sept23.pdf", "Table 18, page 83",
        "verified_default_UK", "Traditional construction default", "2%",
        source_id="RICS_WLCA_2024",
        source_kind="default_rate",
        reference_class="REF-PROXY-UK-DEFAULT",
    ),
    # REF-PROXY: 10% - RICS WLCA Sept 2023, Table 18 p.83; formwork waste default.
    "timber_formwork": Evidence(
        "RICS23-WR-TIMBER-FORMWORK", 0.10, "fraction of delivered quantity", "A5.3",
        "Whole_life_carbon_assessment_PS_Sept23.pdf", "Table 18, page 83",
        "verified_default_UK", "Traditional construction default", "10%",
        source_id="RICS_WLCA_2024",
        source_kind="default_rate",
        reference_class="REF-PROXY-UK-DEFAULT",
    ),
    # REF-PROXY: 1% - RICS WLCA Sept 2023, Table 18 p.83; aluminium waste default.
    "aluminium_sheet_or_extrusion": Evidence(
        "RICS23-WR-ALUMINIUM", 0.01, "fraction of delivered quantity", "A5.3",
        "Whole_life_carbon_assessment_PS_Sept23.pdf", "Table 18, page 83",
        "verified_default_UK", "Traditional construction default", "1%",
        source_id="RICS_WLCA_2024",
        source_kind="default_rate",
        reference_class="REF-PROXY-UK-DEFAULT",
    ),
    # REF-VERIFIED-PROXY: 1.4369670638496768 kgCO2e/kg.
    # REFERENCE: ICE DB Educational V4.1 - Oct 2025.xlsx, ICE Summary row 618.
    # PROJECT-SOURCE-REQUIRED: area-to-mass conversion needs sourced thickness and density.
    # REF-PROXY: 1% - RICS WLCA Sept 2023, Table 18 p.83; glass waste default.
    "glass": Evidence(
        "RICS23-WR-GLASS", 0.01, "fraction of delivered quantity", "A5.3",
        "Whole_life_carbon_assessment_PS_Sept23.pdf", "Table 18, page 83",
        "verified_default_UK", "Traditional construction default", "1%",
        source_id="RICS_WLCA_2024",
        source_kind="default_rate",
        reference_class="REF-PROXY-UK-DEFAULT",
    ),
}


# -----------------------------------------------------------------------------
# Validation and audit helpers
# -----------------------------------------------------------------------------
def _require_source(text: str, label: str) -> str:
    source = str(text or "").strip()
    if not source:
        raise ScientificInputError(f"{label} requires a source/reference.")
    return source


def _reference_record(source_id: str) -> dict[str, str]:
    """Resolve a factor's source_id to its full bibliographic record."""
    return dict(REFERENCE_CATALOG.get(source_id, {}))


def _factor_audit_row(factor: Evidence, used_value: Optional[float] = None) -> dict[str, Any]:
    """One audit row carrying the factor AND the full identity of its source.

    The audit trail must be readable without opening REFERENCE_CATALOG, so the
    organization / exact title / identifier / edition / version / date are copied in.
    """
    row = asdict(factor)
    row["used_value"] = factor.value if used_value is None else used_value
    ref = _reference_record(factor.source_id)
    row.update({
        "reference_organization": ref.get("organization", ""),
        "reference_title": ref.get("title", ""),
        "reference_identifier": ref.get("identifier", ""),
        "reference_edition": ref.get("edition", ""),
        "reference_version": ref.get("version", ""),
        "reference_publication_date": ref.get("publication_date", ""),
        "reference_publisher": ref.get("publisher", ""),
        "reference_geography": ref.get("geography", ""),
        "reference_catalog_status": ref.get("evidence_status", ""),
    })
    return row


def factor_registry_dataframe() -> pd.DataFrame:
    factors: list[Evidence] = list(MATERIAL_EF.values())
    for mode_factors in TRANSPORT_EF.values():
        factors.extend(mode_factors.values())
    factors.extend(DIESEL_EF.values())
    factors.extend(WASTE_EF.values())
    factors.extend(B6_ENERGY_INTENSITY.values())
    factors.extend(RICS_WASTE_RATES.values())
    return pd.DataFrame([asdict(f) for f in factors])


def equation_registry_dataframe() -> pd.DataFrame:
    """Equation registry with every source_id resolved to its full identity."""
    rows = []
    for equation_id, eq in EQUATIONS.items():
        source_ids = list(eq.get("source_ids", []))
        resolved = [REFERENCE_CATALOG.get(sid, {}) for sid in source_ids]
        rows.append({
            "equation_id": equation_id,
            **eq,
            "source_ids": "; ".join(source_ids),
            "source_organizations": "; ".join(r.get("organization", "") for r in resolved),
            "source_titles": "; ".join(r.get("title", "") for r in resolved),
            "source_identifiers": "; ".join(r.get("identifier", "") for r in resolved),
            "source_editions_versions": "; ".join(
                " / ".join(x for x in (r.get("edition", ""), r.get("version", "")) if x)
                for r in resolved
            ),
        })
    return pd.DataFrame(rows)


# -----------------------------------------------------------------------------
# CITATION-FREEZE INTEGRITY VALIDATORS
# These prove — mechanically, not by assertion in prose — that every equation and
# every fixed empirical number in the registry resolves to a full bibliographic
# record, that derived factors name their parents, and that the internal audit
# workbook is never the sole basis of a direct-primary verification claim.
# -----------------------------------------------------------------------------
def validate_reference_catalog() -> list[str]:
    issues: list[str] = []
    required = {"organization", "title", "identifier", "publisher", "evidence_status"}
    for source_id, record in REFERENCE_CATALOG.items():
        missing = [k for k in required if not str(record.get(k, "")).strip()]
        if missing:
            issues.append(f"REFERENCE_CATALOG[{source_id}] missing: {', '.join(missing)}")
    return issues


def validate_equation_registry() -> list[str]:
    issues: list[str] = []
    for equation_id, eq in EQUATIONS.items():
        if not str(eq.get("equation", "")).strip():
            issues.append(f"{equation_id}: missing equation")
        if not str(eq.get("reference_class", "")).strip():
            issues.append(f"{equation_id}: missing reference_class")
        source_ids = eq.get("source_ids") or []
        if not source_ids and "UNIT-DEFINITION" not in str(eq.get("reference_class", "")):
            issues.append(f"{equation_id}: no source_ids")
        for sid in source_ids:
            if sid not in REFERENCE_CATALOG:
                issues.append(f"{equation_id}: unresolved source_id {sid}")
    return issues


def validate_factor_registry() -> list[str]:
    issues: list[str] = []
    df = factor_registry_dataframe()
    if df.empty:
        return ["factor registry is empty"]
    for _, row in df.iterrows():
        code = str(row.get("code", "?"))
        value = row.get("value")
        status = str(row.get("status", ""))
        source_id = str(row.get("source_id", "")).strip()
        source_file = str(row.get("source_file", "")).strip()
        location = str(row.get("location", "")).strip()
        source_kind = str(row.get("source_kind", "")).strip()
        parents = row.get("parent_factor_codes", ())

        # A SOURCE-OPEN factor legitimately has no value and no source yet; it is blocked
        # at calculation time by require_value(), not here. NOTE: pandas turns a None
        # value into NaN, so test for a usable number rather than `is not None`.
        try:
            has_value = value is not None and math.isfinite(float(value))
        except (TypeError, ValueError):
            has_value = False

        if has_value and source_kind in {"empirical_factor", "default_rate", "derived_factor"}:
            if not source_file or not location:
                issues.append(f"{code}: empirical/derived factor missing source_file/location")
            if not source_id:
                issues.append(f"{code}: empirical/derived factor missing source_id")
            elif source_id not in REFERENCE_CATALOG:
                issues.append(f"{code}: unresolved source_id {source_id}")

        if "derived" in source_kind.lower() and not parents:
            issues.append(f"{code}: derived factor missing parent_factor_codes")

        # An internal traceability index can map a number to a claimed primary row,
        # but it can never itself be the primary verification.
        if "verified" in status.lower() and source_id == "CLOSED_FACTOR_AUDIT":
            issues.append(f"{code}: internal audit cannot be the sole primary verified source")

    return issues


def scientific_reference_integrity_check() -> dict[str, Any]:
    issues = (
        validate_reference_catalog()
        + validate_equation_registry()
        + validate_factor_registry()
    )
    return {"ok": len(issues) == 0, "issues": issues}


def make_project_evidence(
    code: str,
    value: float,
    unit: str,
    stage: str,
    source_file: str,
    location: str,
    boundary_scope: str,
    note: str = "",
    factor_basis: str = "project_specific",
    status: str = "project_specific_user_supplied",
    source_id: str = "",
    reference_class: str = "PROJECT-SOURCE-REQUIRED",
) -> Evidence:
    """Create a sourced project-specific factor, e.g. an EPD or Egypt grid value.

    NOTE: text in a form field does NOT prove scientific verification. The default
    status is 'project_specific_user_supplied'. Only pass a stronger status
    ('project_specific_documented' / 'project_specific_verified') when the evidence
    carries file + edition/year + sheet/table/page + row/clause + unit + boundary +
    geography (+ EPD validity). Allowed statuses:
      project_specific_user_supplied, project_specific_documented,
      project_specific_verified, verified_proxy, scenario_only, source_open.
    """
    # PROJECT-SOURCE-REQUIRED — no universal/default project value is permitted here.
    # A project record proves itself with source_file + location; it does NOT need a
    # REFERENCE_CATALOG source_id, because the evidence is the project document itself.
    _require_source(source_file, f"{code} source_file")
    _require_source(location, f"{code} location")
    if not math.isfinite(float(value)):
        raise ScientificInputError(f"{code} value must be finite.")
    _allowed = {"project_specific_user_supplied", "project_specific_documented",
                "project_specific_verified", "verified_proxy", "scenario_only", "source_open"}
    if status not in _allowed:
        status = "project_specific_user_supplied"
    return Evidence(
        code=code,
        value=float(value),
        unit=unit,
        stage=stage,
        source_file=source_file,
        location=location,
        status=status,
        boundary_scope=boundary_scope,
        note=note,
        factor_basis=factor_basis,
        source_id=source_id,
        source_kind="project_specific",
        reference_class=reference_class,
    )


def calculate_effective_ef(
    virgin_factor: Evidence,
    recycled_content_fraction: float,
    secondary_factor: Evidence,
) -> Evidence:
    """E2: combine documented virgin and secondary-route factors.

    This function intentionally rejects market-average factors because they already
    include a production mix and applying recycled content again can double count.
    """
    rc = float(recycled_content_fraction)
    if rc < 0.0 or rc > 1.0:
        raise ScientificInputError("Recycled-content fraction must be between 0 and 1.")
    if virgin_factor.factor_basis != "virgin":
        raise ScientificInputError(
            f"{virgin_factor.code} is not an explicitly virgin factor; "
            "do not apply an additional recycled-content adjustment."
        )
    v = virgin_factor.require_value()
    s = secondary_factor.require_value()
    # REF-DERIVED E2_EFFECTIVE_EF — conditional weighted inventory aggregation.
    # NOT a verbatim universal EN 15804 credit equation.
    # EF_eff = (1-RC)*EF_virgin + RC*EF_secondary.
    # SOURCE STATUS: valid only for explicitly virgin + documented secondary-route factors.
    value = (1.0 - rc) * v + rc * s
    return Evidence(
        code=f"EFFECTIVE-{virgin_factor.code}-{secondary_factor.code}",
        value=value,
        unit="kgCO2e/kg",
        stage="A1-A3",
        source_file=f"{virgin_factor.source_file}; {secondary_factor.source_file}",
        location=f"{virgin_factor.location}; {secondary_factor.location}",
        status="verified_derived",
        boundary_scope="A1-A3",
        note=(
            f"Derived with E2 using RC={rc:.6f}. Base factor is explicitly virgin; "
            "secondary factor is documented."
        ),
        factor_basis="effective_mix",
        source_kind="derived_factor",
        reference_class="REF-DERIVED-INPUT-CONDITIONAL",
        parent_factor_codes=(virgin_factor.code, secondary_factor.code),
    )


# -----------------------------------------------------------------------------
# A1-A3
# -----------------------------------------------------------------------------
def calculate_a1_a3(
    material_masses_kg: Mapping[str, ProjectQuantity],
    factor_overrides: Optional[Mapping[str, Evidence]] = None,
) -> dict[str, Any]:
    """Calculate gross A1-A3 embodied carbon.

    E1: I_A1-A3,j = M_j * EF_j / 1000.
    """
    overrides = dict(factor_overrides or {})
    rows: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []
    total_tco2e = 0.0

    for material, quantity in material_masses_kg.items():
        mass_kg = quantity.require_nonnegative(f"A1-A3 mass for {material}")
        factor = overrides.get(material, MATERIAL_EF.get(material))
        if factor is None:
            raise ScientificInputError(f"No A1-A3 factor is registered for {material}.")
        # A zero-mass material does not consume its factor. This allows FRP=0 in a
        # publication scenario without pretending that an FRP EPD exists.
        if mass_kg == 0.0:
            ef = float(factor.value) if factor.value is not None else float("nan")
            impact_tco2e = 0.0
        else:
            ef = factor.require_value()
            # METHOD-REFERENCE E1_A1_A3:
            # I_A1-A3,j = M_j[kg] * EF_j[kgCO2e/kg] / 1000[kgCO2e/tCO2e].
            # NUMERIC REFERENCE: factor Evidence record immediately above in the registry.
            impact_tco2e = mass_kg * ef / KG_CO2E_PER_TONNE_CO2E
        total_tco2e += impact_tco2e
        rows.append(
            {
                "material": material,
                "mass_kg": mass_kg,
                "mass_source": quantity.source,
                "ef_kgco2e_per_kg": ef,
                "factor_code": factor.code,
                "factor_source": factor.source_file,
                "factor_location": factor.location,
                "factor_status": factor.status,
                "A1_A3_tCO2e": impact_tco2e,
                "equation_id": "E1_A1_A3",
            }
        )
        if mass_kg > 0.0:
            audit.append(_factor_audit_row(factor, ef))

    return {
        "stage": "A1-A3",
        "total_tco2e": total_tco2e,
        "by_material": rows,
        "source_audit": audit,
        "equation_ids": ["E1_A1_A3"],
    }


# -----------------------------------------------------------------------------
# A4 / C2 transport
# -----------------------------------------------------------------------------
def calculate_transport_legs(
    legs: Sequence[Mapping[str, Any]],
    stage: str,
    default_scope: str = "wtw",
) -> dict[str, Any]:
    """Calculate A4 or C2 from explicit transport legs.

    E3 is applied to every leg. Do not create an undocumented return multiplier.
    When a return/empty-running impact is required, enter it as a separate sourced
    leg or supply a documented route-specific factor.
    """
    if stage not in {"A4", "C2", "A5-waste-transport", "B2-B5-transport"}:
        raise ScientificInputError(f"Unsupported transport stage: {stage}")

    rows: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []
    total_tco2e = 0.0

    for index, leg in enumerate(legs, start=1):
        mass_kg = float(leg.get("mass_kg", 0.0))
        distance_km = float(leg.get("distance_km", 0.0))
        if mass_kg < 0.0 or distance_km < 0.0:
            raise ScientificInputError(f"Transport leg {index} has a negative value.")
        _require_source(str(leg.get("mass_source", "")), f"transport leg {index} mass")
        _require_source(str(leg.get("distance_source", "")), f"transport leg {index} distance")

        mode = str(leg.get("mode", "truck")).lower()
        scope = str(leg.get("scope", default_scope)).lower()
        override = leg.get("factor_override")
        if override is not None and not isinstance(override, Evidence):
            raise ScientificInputError("factor_override must be an Evidence object.")
        factor = override or TRANSPORT_EF.get(mode, {}).get(scope)
        if factor is None:
            raise ScientificInputError(
                f"No transport factor for mode={mode!r}, scope={scope!r}."
            )
        ef = factor.require_value()
        # ACCOUNTING-IDENTITY / METHOD-IMPLEMENTATION E3_TRANSPORT_LEG:
        # One explicit transport leg only. Full A4/C2 closure is enforced in integration.
        # I_leg = (M_kg/1000) * D_km * EF_kgCO2e_per_tkm / 1000.
        # UNIT-DEFINITION: /1000 twice — kg->tonne on mass, kgCO2e->tCO2e on the result.
        # PROJECT-SOURCE-REQUIRED: mass source and route distance source are mandatory.
        impact_tco2e = (
            (mass_kg / KG_PER_TONNE)
            * distance_km
            * ef
            / KG_CO2E_PER_TONNE_CO2E
        )
        total_tco2e += impact_tco2e
        rows.append(
            {
                "leg": index,
                "stage": stage,
                "material": leg.get("material", "not specified"),
                "mass_kg": mass_kg,
                "distance_km": distance_km,
                "mode": mode,
                "scope": scope,
                "ef_kgco2e_per_tkm": ef,
                "factor_code": factor.code,
                "tCO2e": impact_tco2e,
                "equation_id": "E3_TRANSPORT_LEG",
            }
        )
        audit.append(_factor_audit_row(factor, ef))

    return {
        "stage": stage,
        "total_tco2e": total_tco2e,
        "legs": rows,
        "source_audit": audit,
        "equation_ids": ["E3_TRANSPORT_LEG"],
    }


# -----------------------------------------------------------------------------
# Shared activity calculations: fuel, electricity and waste
# -----------------------------------------------------------------------------
def calculate_fuel(
    litres: ProjectQuantity,
    stage: str,
    scope: str = "wtw",
    factor_override: Optional[Evidence] = None,
) -> dict[str, Any]:
    """E4: fuel activity multiplied by a sourced conversion factor."""
    litres_value = litres.require_nonnegative(f"{stage} diesel litres")
    factor = factor_override or DIESEL_EF.get(scope)
    if factor is None:
        raise ScientificInputError(f"No diesel factor for scope={scope!r}.")
    ef = factor.require_value()
    # METHOD-REFERENCE E4_FUEL:
    # I_fuel = litres * EF_kgCO2e_per_L / 1000.
    # NUMERIC REFERENCE: DIESEL_EF[scope] with source row stored in Evidence.
    impact = litres_value * ef / KG_CO2E_PER_TONNE_CO2E
    return {
        "stage": stage,
        "litres": litres_value,
        "litres_source": litres.source,
        "factor": factor,
        "tco2e": impact,
        "equation_id": "E4_FUEL",
    }


def calculate_electricity(
    electricity_kwh: ProjectQuantity,
    grid: GridCarbonYear,
    stage: str,
) -> dict[str, Any]:
    """E5: electricity multiplied by the documented annual carbon factor."""
    energy = electricity_kwh.require_nonnegative(f"{stage} electricity")
    _require_source(grid.source_file, f"{stage} grid source")
    _require_source(grid.location, f"{stage} grid location")
    ci = grid.total_kgco2e_per_kwh
    if ci < 0.0 or not math.isfinite(ci):
        raise ScientificInputError(f"{stage} grid CI must be finite and non-negative.")
    # METHOD-REFERENCE E5_ELECTRICITY:
    # I_electricity,t = kWh_t * CI_t / 1000.
    # SOURCE-OPEN FOR EGYPT: grid record must name official file/table/year.
    impact = energy * ci / KG_CO2E_PER_TONNE_CO2E
    return {
        "stage": stage,
        "electricity_kwh": energy,
        "electricity_source": electricity_kwh.source,
        "grid_year": grid.year,
        "grid_ci_kgco2e_per_kwh": ci,
        "grid_source": grid.source_file,
        "grid_location": grid.location,
        "tco2e": impact,
        "equation_id": "E5_ELECTRICITY",
    }


def calculate_waste_treatment(
    waste_items: Sequence[Mapping[str, Any]],
    stage: str,
) -> dict[str, Any]:
    """E7: route-specific waste mass multiplied by kgCO2e/tonne factor.

    Important correction relative to the old code: the GHG waste factors are per
    tonne of waste, not per kg. Therefore W_kg is divided by 1000 before applying
    the factor.
    """
    rows: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []
    total_tco2e = 0.0

    for index, item in enumerate(waste_items, start=1):
        waste_kg = float(item.get("waste_kg", 0.0))
        if waste_kg < 0.0 or not math.isfinite(waste_kg):
            raise ScientificInputError(f"Waste item {index} has an invalid mass.")
        _require_source(str(item.get("waste_source", "")), f"waste item {index} mass")

        override = item.get("factor_override")
        if override is not None and not isinstance(override, Evidence):
            raise ScientificInputError("Waste factor_override must be an Evidence object.")
        factor_code = item.get("factor_code")
        factor = override or WASTE_EF.get(str(factor_code))
        if factor is None:
            raise ScientificInputError(
                f"Waste item {index} requires factor_code or factor_override."
            )
        ef = factor.require_value()
        # METHOD-REFERENCE E7_WASTE:
        # I_waste = (W_kg/1000) * EF_kgCO2e_per_tonne / 1000.
        # IMPORTANT UNIT CHECK: the uploaded 2025 waste EFs are per tonne, never per kg.
        impact = (
            (waste_kg / KG_PER_TONNE)
            * ef
            / KG_CO2E_PER_TONNE_CO2E
        )
        total_tco2e += impact
        rows.append(
            {
                "item": index,
                "stage": stage,
                "material": item.get("material", "not specified"),
                "route": item.get("route", factor_code or factor.code),
                "waste_kg": waste_kg,
                "ef_kgco2e_per_tonne": ef,
                "factor_code": factor.code,
                "tCO2e": impact,
                "equation_id": "E7_WASTE",
            }
        )
        audit.append(_factor_audit_row(factor, ef))

    return {
        "stage": stage,
        "total_tco2e": total_tco2e,
        "items": rows,
        "source_audit": audit,
        "equation_ids": ["E7_WASTE"],
    }


def derive_waste_mass_from_installed(
    installed_mass: ProjectQuantity,
    waste_rate: Evidence,
) -> ProjectQuantity:
    """E8: derive extra purchased waste when the BOQ quantity is installed mass."""
    installed = installed_mass.require_nonnegative("installed material mass")
    wr = waste_rate.require_value()
    if wr < 0.0 or wr >= 1.0:
        raise ScientificInputError("Waste rate must satisfy 0 <= WR < 1.")
    # METHOD-REFERENCE E8_WASTE_FROM_INSTALLED:
    # installed = purchased*(1-WR) -> extra waste = installed*WR/(1-WR).
    # REF-PROXY/PROJECT INPUT: WR Evidence identifies RICS default or project waste plan.
    waste_kg = installed * wr / (1.0 - wr)
    return ProjectQuantity(
        value=waste_kg,
        unit="kg",
        source=(
            f"Derived from {installed_mass.source} using {waste_rate.code}, "
            f"{waste_rate.source_file}, {waste_rate.location}"
        ),
        location="Equation E8_WASTE_FROM_INSTALLED",
    )


# -----------------------------------------------------------------------------
# A5
# -----------------------------------------------------------------------------
def calculate_a5(
    diesel_litres: Optional[ProjectQuantity],
    diesel_scope: str,
    electricity_kwh: Optional[ProjectQuantity],
    grid: Optional[GridCarbonYear],
    extra_waste_materials_kg: Optional[Mapping[str, ProjectQuantity]],
    waste_factor_overrides: Optional[Mapping[str, Evidence]],
    waste_delivery_legs: Sequence[Mapping[str, Any]],
    waste_treatment_items: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Calculate A5.2 construction activities and A5.3 waste impacts.

    A5 includes only supplied activities. No undocumented default diesel, equipment
    utilisation, climate correction or productivity-loss multiplier is inserted.
    """
    fuel_t = 0.0
    electricity_t = 0.0
    waste_production_t = 0.0
    audit: list[dict[str, Any]] = []
    details: dict[str, Any] = {}

    if diesel_litres is not None:
        fuel = calculate_fuel(diesel_litres, "A5", diesel_scope)
        fuel_t = fuel["tco2e"]
        audit.append(_factor_audit_row(fuel["factor"]))
        details["fuel"] = fuel

    if electricity_kwh is not None:
        if grid is None:
            raise ScientificInputError("A5 electricity was supplied without a sourced grid factor.")
        electricity = calculate_electricity(electricity_kwh, grid, "A5")
        electricity_t = electricity["tco2e"]
        details["electricity"] = electricity

    # Production of extra waste only when the A1-A3 masses represent installed quantities.
    if extra_waste_materials_kg:
        a1a3_waste = calculate_a1_a3(
            extra_waste_materials_kg,
            factor_overrides=waste_factor_overrides,
        )
        waste_production_t = a1a3_waste["total_tco2e"]
        audit.extend(a1a3_waste["source_audit"])
        details["extra_waste_product_A1_A3"] = a1a3_waste

    waste_transport = calculate_transport_legs(
        waste_delivery_legs,
        stage="A5-waste-transport",
        default_scope="wtw",
    ) if waste_delivery_legs else {
        "total_tco2e": 0.0, "legs": [], "source_audit": [], "equation_ids": []
    }
    waste_treatment = calculate_waste_treatment(
        waste_treatment_items,
        stage="A5.3",
    ) if waste_treatment_items else {
        "total_tco2e": 0.0, "items": [], "source_audit": [], "equation_ids": []
    }
    audit.extend(waste_transport.get("source_audit", []))
    audit.extend(waste_treatment.get("source_audit", []))

    # METHOD-REFERENCE A5_TOTAL: RICS WLCA A5.2 construction activities + A5.3 waste.
    # A5 = fuel + site electricity + production of extra waste + waste transport + waste treatment.
    # PROJECT-SOURCE-REQUIRED: every non-zero component must carry site/contractor records.
    total = (
        fuel_t
        + electricity_t
        + waste_production_t
        + float(waste_transport["total_tco2e"])
        + float(waste_treatment["total_tco2e"])
    )
    return {
        "stage": "A5",
        "total_tco2e": total,
        "fuel_tco2e": fuel_t,
        "electricity_tco2e": electricity_t,
        "extra_waste_product_tco2e": waste_production_t,
        "waste_transport_tco2e": waste_transport["total_tco2e"],
        "waste_treatment_tco2e": waste_treatment["total_tco2e"],
        "details": details,
        "waste_transport": waste_transport,
        "waste_treatment": waste_treatment,
        "source_audit": audit,
        "equation_ids": ["E1_A1_A3", "E3_TRANSPORT_LEG", "E4_FUEL", "E5_ELECTRICITY", "E7_WASTE"],
    }


# -----------------------------------------------------------------------------
# B2-B5 activity-based use stage
# -----------------------------------------------------------------------------
def calculate_b2_b5(
    events: Sequence[Mapping[str, Any]],
    grid_by_year: Mapping[int, GridCarbonYear],
    material_factor_overrides: Optional[Mapping[str, Evidence]] = None,
) -> dict[str, Any]:
    """Calculate B2-B5 using actual events, not a percentage-of-carbon proxy.

    Each event can contain:
      module: B2/B3/B4/B5
      year: operating year
      event_source: maintenance/replacement plan reference
      new_materials_kg: {material: ProjectQuantity}
      diesel_litres: ProjectQuantity or None
      diesel_scope: direct/wtw
      electricity_kwh: ProjectQuantity or None
      transport_legs: list of E3 legs
      waste_items: list of E7 treatment items
      added_mass_kg / removed_mass_kg: mass-balance dictionaries
    """
    totals = {"B2": 0.0, "B3": 0.0, "B4": 0.0, "B5": 0.0}
    rows: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []
    added: dict[str, float] = {}
    removed: dict[str, float] = {}

    for index, event in enumerate(events, start=1):
        module = str(event.get("module", "")).upper()
        if module not in totals:
            raise ScientificInputError(f"Event {index} module must be B2, B3, B4 or B5.")
        year = int(event.get("year", 0))
        if year <= 0:
            raise ScientificInputError(f"Event {index} requires a positive operating year.")
        _require_source(str(event.get("event_source", "")), f"{module} event {index}")

        event_total = 0.0
        components: dict[str, float] = {}

        materials = event.get("new_materials_kg") or {}
        if materials:
            a1 = calculate_a1_a3(materials, material_factor_overrides)
            components["new_materials_tco2e"] = a1["total_tco2e"]
            event_total += a1["total_tco2e"]
            audit.extend(a1["source_audit"])
        else:
            components["new_materials_tco2e"] = 0.0

        diesel = event.get("diesel_litres")
        if diesel is not None:
            fuel = calculate_fuel(
                diesel,
                stage=module,
                scope=str(event.get("diesel_scope", "wtw")),
            )
            components["fuel_tco2e"] = fuel["tco2e"]
            event_total += fuel["tco2e"]
            audit.append(_factor_audit_row(fuel["factor"]))
        else:
            components["fuel_tco2e"] = 0.0

        electricity = event.get("electricity_kwh")
        if electricity is not None:
            grid = grid_by_year.get(year)
            if grid is None:
                raise ScientificInputError(f"No sourced grid CI exists for {module} year {year}.")
            elec = calculate_electricity(electricity, grid, module)
            components["electricity_tco2e"] = elec["tco2e"]
            event_total += elec["tco2e"]
        else:
            components["electricity_tco2e"] = 0.0

        transport = calculate_transport_legs(
            event.get("transport_legs") or [],
            stage="B2-B5-transport",
            default_scope="wtw",
        ) if event.get("transport_legs") else {
            "total_tco2e": 0.0, "source_audit": []
        }
        components["transport_tco2e"] = transport["total_tco2e"]
        event_total += transport["total_tco2e"]
        audit.extend(transport.get("source_audit", []))

        waste = calculate_waste_treatment(
            event.get("waste_items") or [],
            stage=module,
        ) if event.get("waste_items") else {
            "total_tco2e": 0.0, "source_audit": []
        }
        components["waste_tco2e"] = waste["total_tco2e"]
        event_total += waste["total_tco2e"]
        audit.extend(waste.get("source_audit", []))

        for material, mass in (event.get("added_mass_kg") or {}).items():
            added[material] = added.get(material, 0.0) + float(mass)
        for material, mass in (event.get("removed_mass_kg") or {}).items():
            removed[material] = removed.get(material, 0.0) + float(mass)

        # METHOD-REFERENCE E9_B2_B5: RICS activity-based B2/B3/B4/B5 inventory.
        # Event carbon = new materials + fuel + year-specific electricity + transport + waste.
        # PROJECT-SOURCE-REQUIRED: event year, quantities and O&M schedule reference.
        totals[module] += event_total
        rows.append(
            {
                "event": index,
                "module": module,
                "year": year,
                **components,
                "event_tco2e": event_total,
                "equation_id": "E9_B2_B5",
            }
        )

    return {
        "stage": "B2-B5",
        # METHOD-REFERENCE E9_B2_B5: total = sum of separately inventoried B2+B3+B4+B5 events.
        "total_tco2e": sum(totals.values()),
        "module_totals_tco2e": totals,
        "events": rows,
        "material_added_kg": added,
        "material_removed_kg": removed,
        "source_audit": audit,
        "equation_ids": ["E9_B2_B5"],
    }


def update_mass_balance(
    initial_masses_kg: Mapping[str, ProjectQuantity],
    added_kg: Mapping[str, float],
    removed_kg: Mapping[str, float],
) -> dict[str, Any]:
    """Mass balance used to avoid counting B4/B5 removals again in C1-C4."""
    rows: list[dict[str, Any]] = []
    remaining: dict[str, ProjectQuantity] = {}
    for material, quantity in initial_masses_kg.items():
        initial = quantity.require_nonnegative(f"initial mass {material}")
        added = float(added_kg.get(material, 0.0))
        removed = float(removed_kg.get(material, 0.0))
        # UNIT/MASS-BALANCE IDENTITY: M_remaining = M_initial + M_added(B4/B5) - M_removed(B4/B5).
        # PURPOSE: prevents removed replacement material from being counted again in C1-C4.
        value = initial + added - removed
        if value < -1e-9:
            raise ScientificInputError(
                f"Mass balance for {material} is negative ({value} kg)."
            )
        value = max(value, 0.0)
        remaining[material] = ProjectQuantity(
            value=value,
            unit="kg",
            source=(
                f"Mass balance: initial from {quantity.source}; added={added} kg; "
                f"removed={removed} kg"
            ),
            location="B4/B5 mass balance",
        )
        rows.append(
            {
                "material": material,
                "initial_kg": initial,
                "added_B4_B5_kg": added,
                "removed_B4_B5_kg": removed,
                "remaining_for_C1_C4_kg": value,
            }
        )
    return {"remaining_masses_kg": remaining, "rows": rows}


# -----------------------------------------------------------------------------
# B6
# -----------------------------------------------------------------------------
def calculate_b6(
    annual_pkm_by_year: Mapping[int, ProjectQuantity],
    grid_by_year: Mapping[int, GridCarbonYear],
    energy_intensity: Evidence,
) -> dict[str, Any]:
    """Calculate annual and lifetime B6 without an unsupported renewable shortcut.

    E6: E_t = PKM_t * EI_t.
    E5: I_B6,t = E_t * CI_t / 1000.
    """
    ei = energy_intensity.require_value()
    if energy_intensity.unit != "kWh/passenger.km":
        raise ScientificInputError("B6 energy intensity must use kWh/passenger.km.")

    rows: list[dict[str, Any]] = []
    total_energy_kwh = 0.0
    total_pkm = 0.0
    total_tco2e = 0.0

    for year in sorted(annual_pkm_by_year):
        pkm_quantity = annual_pkm_by_year[year]
        pkm = pkm_quantity.require_nonnegative(f"B6 passenger-km in year {year}")
        grid = grid_by_year.get(year)
        if grid is None:
            raise ScientificInputError(
                f"B6 year {year} has no sourced grid carbon-intensity record."
            )
        ci = grid.total_kgco2e_per_kwh
        # METHOD-REFERENCE E6_B6_ENERGY: E_t = PKM_t * EI_t.
        # METHOD-REFERENCE E5_ELECTRICITY: B6_t = E_t * CI_t / 1000.
        # PROJECT-SOURCE-REQUIRED: annual passenger-km and annual Egypt/project CI_t.
        energy_kwh = pkm * ei
        impact = energy_kwh * ci / KG_CO2E_PER_TONNE_CO2E
        total_pkm += pkm
        total_energy_kwh += energy_kwh
        total_tco2e += impact
        rows.append(
            {
                "year": year,
                "annual_pkm": pkm,
                "pkm_source": pkm_quantity.source,
                "energy_intensity_kwh_per_pkm": ei,
                "energy_intensity_code": energy_intensity.code,
                "energy_kwh": energy_kwh,
                "grid_ci_kgco2e_per_kwh": ci,
                "grid_source": grid.source_file,
                "grid_location": grid.location,
                "B6_tCO2e": impact,
                "equation_ids": "E6_B6_ENERGY; E5_ELECTRICITY",
            }
        )

    return {
        "stage": "B6",
        "total_tco2e": total_tco2e,
        "total_energy_kwh": total_energy_kwh,
        "total_pkm": total_pkm,
        "yearly": rows,
        "source_audit": [_factor_audit_row(energy_intensity, ei)],
        "equation_ids": ["E6_B6_ENERGY", "E5_ELECTRICITY"],
    }


# -----------------------------------------------------------------------------
# C1-C4
# -----------------------------------------------------------------------------
def calculate_c1_c4(
    c1_diesel_litres: Optional[ProjectQuantity],
    c1_diesel_scope: str,
    c1_electricity_kwh: Optional[ProjectQuantity],
    c1_grid: Optional[GridCarbonYear],
    c2_transport_legs: Sequence[Mapping[str, Any]],
    treatment_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Calculate C1 deconstruction, C2 transport, C3 processing and C4 disposal.

    Each treatment row requires:
      material, mass_kg, mass_source,
      reuse_share, recycle_share, disposal_share, share_source,
      reuse_factor / recycle_factor / disposal_factor (Evidence or None).

    C3 is an emission. Recovery benefits are not credited here; they belong to D1.
    """
    c1 = 0.0
    audit: list[dict[str, Any]] = []
    c1_details: dict[str, Any] = {}

    if c1_diesel_litres is not None:
        fuel = calculate_fuel(c1_diesel_litres, "C1", c1_diesel_scope)
        c1 += fuel["tco2e"]
        c1_details["fuel"] = fuel
        audit.append(_factor_audit_row(fuel["factor"]))
    if c1_electricity_kwh is not None:
        if c1_grid is None:
            raise ScientificInputError("C1 electricity requires a sourced grid factor.")
        electricity = calculate_electricity(c1_electricity_kwh, c1_grid, "C1")
        c1 += electricity["tco2e"]
        c1_details["electricity"] = electricity

    c2 = calculate_transport_legs(
        c2_transport_legs,
        stage="C2",
        default_scope="wtw",
    ) if c2_transport_legs else {
        "total_tco2e": 0.0, "legs": [], "source_audit": []
    }
    audit.extend(c2.get("source_audit", []))

    c3_total = 0.0
    c4_total = 0.0
    treatment_output: list[dict[str, Any]] = []

    for index, row in enumerate(treatment_rows, start=1):
        mass_kg = float(row.get("mass_kg", 0.0))
        if mass_kg < 0.0 or not math.isfinite(mass_kg):
            raise ScientificInputError(f"C-stage treatment row {index} has invalid mass.")
        _require_source(str(row.get("mass_source", "")), f"C-stage row {index} mass")
        _require_source(str(row.get("share_source", "")), f"C-stage row {index} shares")

        reuse = float(row.get("reuse_share", 0.0))
        recycle = float(row.get("recycle_share", 0.0))
        disposal = float(row.get("disposal_share", 0.0))
        if min(reuse, recycle, disposal) < 0.0:
            raise ScientificInputError(f"C-stage treatment row {index} has a negative share.")
        if abs((reuse + recycle + disposal) - 1.0) > 1e-9:
            raise ScientificInputError(
                f"C-stage treatment row {index}: reuse+recycle+disposal must equal 1."
            )

        def factor_value(name: str, share: float) -> tuple[float, Optional[Evidence]]:
            factor = row.get(name)
            if share == 0.0:
                return 0.0, factor if isinstance(factor, Evidence) else None
            if not isinstance(factor, Evidence):
                raise ScientificInputError(
                    f"C-stage row {index} requires Evidence for {name}."
                )
            return factor.require_value(), factor

        reuse_ef, reuse_factor = factor_value("reuse_factor", reuse)
        recycle_ef, recycle_factor = factor_value("recycle_factor", recycle)
        disposal_ef, disposal_factor = factor_value("disposal_factor", disposal)

        # E7 with route-share-weighted kgCO2e per tonne factors.
        # METHOD-REFERENCE E7_WASTE / E10_C1_C4:
        # C3 uses reuse/recycling PROCESSING emissions; recovery benefits are not credited here.
        # C4 uses disposal-route emissions. Shares must sum exactly to 1 and carry a source.
        c3_kgco2e = (mass_kg / KG_PER_TONNE) * (
            reuse * reuse_ef + recycle * recycle_ef
        )
        c4_kgco2e = (mass_kg / KG_PER_TONNE) * disposal * disposal_ef
        c3_t = c3_kgco2e / KG_CO2E_PER_TONNE_CO2E
        c4_t = c4_kgco2e / KG_CO2E_PER_TONNE_CO2E
        c3_total += c3_t
        c4_total += c4_t

        for factor in (reuse_factor, recycle_factor, disposal_factor):
            if factor is not None:
                audit.append(_factor_audit_row(factor))

        treatment_output.append(
            {
                "material": row.get("material", "not specified"),
                "mass_kg": mass_kg,
                "reuse_share": reuse,
                "recycle_share": recycle,
                "disposal_share": disposal,
                "C3_tCO2e": c3_t,
                "C4_tCO2e": c4_t,
                "equation_id": "E7_WASTE",
            }
        )

    # METHOD-REFERENCE E10_C1_C4: RICS end-of-life modular sum C1 + C2 + C3 + C4.
    # PROJECT-SOURCE-REQUIRED: deconstruction activity, routes, treatment shares and factors.
    total = c1 + c2["total_tco2e"] + c3_total + c4_total
    return {
        "stage": "C1-C4",
        "total_tco2e": total,
        "C1_tco2e": c1,
        "C2_tco2e": c2["total_tco2e"],
        "C3_tco2e": c3_total,
        "C4_tco2e": c4_total,
        "C1_details": c1_details,
        "C2_details": c2,
        "treatment_rows": treatment_output,
        "source_audit": audit,
        "equation_ids": ["E10_C1_C4", "E3C_RICS_C2", "E3_TRANSPORT_LEG", "E4_FUEL", "E5_ELECTRICITY", "E7_WASTE"],
    }


# -----------------------------------------------------------------------------
# Module D1 - separate from gross
# -----------------------------------------------------------------------------
def calculate_module_d1(net_flow_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Calculate RICS/EN 15804 Module D1 using the standard signed convention.

    RICS Appendix K reproduces the EN 15804 net-flow structure:
      D1 = (MMR_out - MMR_in) *
           [EMR_after_EoW_out - EVMSub_out * (QR_out / QSub)]

    Mapping used here:
      net_output_kg        = MMR_out - MMR_in
      ef_recovery          = EMR_after_EoW_out
      ef_primary           = EVMSub_out
      substitution_ratio   = QR_out / QSub

    Sign convention:
      negative = potential benefit
      positive = potential load

    Module D1 remains separate from Gross A-C.
    """
    output_rows: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []
    total_standard_signed_tco2e = 0.0

    for index, row in enumerate(net_flow_rows, start=1):
        recovered_output_kg = float(row.get("recovered_output_kg", 0.0))
        secondary_input_kg = float(row.get("secondary_input_kg", 0.0))
        quality_ratio = float(row.get("substitution_ratio", 0.0))

        if recovered_output_kg < 0.0 or secondary_input_kg < 0.0:
            raise ScientificInputError(f"D1 row {index} has a negative flow.")
        if quality_ratio < 0.0 or quality_ratio > 1.0:
            raise ScientificInputError(f"D1 row {index} quality/substitution ratio must be 0..1.")

        _require_source(str(row.get("flow_source", "")), f"D1 row {index} flows")
        _require_source(str(row.get("substitution_source", "")), f"D1 row {index} quality/substitution")

        primary = row.get("primary_factor")
        recovery = row.get("recovery_to_substitution_factor")
        if not isinstance(primary, Evidence) or not isinstance(recovery, Evidence):
            raise ScientificInputError(
                f"D1 row {index} requires primary_factor and recovery_to_substitution_factor Evidence."
            )

        ef_primary = primary.require_value()
        ef_recovery = recovery.require_value()
        net_output_kg = recovered_output_kg - secondary_input_kg

        # METHOD-REFERENCE — Royal Institution of Chartered Surveyors (RICS),
        # "Whole life carbon assessment for the built environment",
        # 2nd ed. September 2023, Version 3 August 2024,
        # Appendix K, Module D1 calculation; equation stated as taken from
        # EN 15804:2012+A2:2019.
        # D1_standard_signed = Q_net * (EF_recovery - q_quality*EF_primary) / 1000.
        # The quality ratio multiplies the SUBSTITUTED PRIMARY term only — it must never
        # also scale the recovery burden (that was the previous, non-conforming form).
        # UNIT-DEFINITION: /1000 converts kgCO2e to tCO2e.
        standard_signed_tco2e = (
            net_output_kg
            * (ef_recovery - quality_ratio * ef_primary)
            / KG_CO2E_PER_TONNE_CO2E
        )

        total_standard_signed_tco2e += standard_signed_tco2e
        audit.extend([_factor_audit_row(primary), _factor_audit_row(recovery)])

        output_rows.append({
            "material": row.get("material", "not specified"),
            "recovered_output_kg": recovered_output_kg,
            "secondary_input_kg": secondary_input_kg,
            "net_output_kg": net_output_kg,
            "quality_ratio_QR_out_over_QSub": quality_ratio,
            "primary_substitution_ef_kgco2e_per_kg": ef_primary,
            "recovery_after_EoW_ef_kgco2e_per_kg": ef_recovery,
            "D1_standard_signed_tCO2e": standard_signed_tco2e,
            "D1_benefit_positive_tCO2e": max(-standard_signed_tco2e, 0.0),
            "D1_load_positive_tCO2e": max(standard_signed_tco2e, 0.0),
            "equation_id": "E11_MODULE_D",
        })

    return {
        "stage": "D1",
        "standard_signed_tco2e": total_standard_signed_tco2e,
        # Compatibility alias: from now on signed_tco2e means RICS/EN standard signed.
        "signed_tco2e": total_standard_signed_tco2e,
        "benefit_positive_tco2e": max(-total_standard_signed_tco2e, 0.0),
        "load_positive_tco2e": max(total_standard_signed_tco2e, 0.0),
        "rows": output_rows,
        "source_audit": audit,
        "equation_ids": ["E11_MODULE_D"],
        "reporting_note": (
            "Module D1 uses the RICS/EN 15804 standard signed convention: "
            "negative = potential benefit; positive = potential load. "
            "It is reported separately and is never part of Gross A-C."
        ),
    }

# -----------------------------------------------------------------------------
# Final gross LCA summary
# -----------------------------------------------------------------------------
def combine_lca_modules(
    a1_a3: Mapping[str, Any],
    a4: Mapping[str, Any],
    a5: Mapping[str, Any],
    b2_b5: Mapping[str, Any],
    b6: Mapping[str, Any],
    c1_c4: Mapping[str, Any],
    module_d1: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    """E12/E13: gross A-C total and GWP per passenger-km.

    The B6 total_pkm defines the denominator because it is the modelled delivered
    passenger-km over the assessment period.
    """
    stage_values = {
        "A1-A3": float(a1_a3.get("total_tco2e", 0.0)),
        "A4": float(a4.get("total_tco2e", 0.0)),
        "A5": float(a5.get("total_tco2e", 0.0)),
        "B2-B5": float(b2_b5.get("total_tco2e", 0.0)),
        "B6": float(b6.get("total_tco2e", 0.0)),
        "C1-C4": float(c1_c4.get("total_tco2e", 0.0)),
    }
    for stage, value in stage_values.items():
        if not math.isfinite(value) or value < -1e-12:
            raise ScientificInputError(f"{stage} total is invalid: {value}")

    # METHOD-REFERENCE E12_GROSS:
    # Gross A-C = A1-A3 + A4 + A5 + B2-B5 + B6 + C1-C4; Module D excluded.
    gross_tco2e = sum(stage_values.values())
    total_pkm = float(b6.get("total_pkm", 0.0))
    if total_pkm <= 0.0:
        raise ScientificInputError("Lifetime passenger-km must be positive for the functional unit.")
    # METHOD-REFERENCE E13_FUNCTIONAL_UNIT:
    # GWP[kgCO2e/pkm] = Gross[tCO2e] * 1000 / lifetime passenger-km.
    # PROJECT-SOURCE-REQUIRED: lifetime passenger-km must come from sourced service data.
    gwp_kgco2e_per_pkm = (
        gross_tco2e * KG_CO2E_PER_TONNE_CO2E / total_pkm
    )

    d_signed = float((module_d1 or {}).get("signed_tco2e", 0.0))
    stage_rows = []
    for stage, value in stage_values.items():
        stage_rows.append(
            {
                "stage": stage,
                "tCO2e": value,
                "percent_of_gross": (100.0 * value / gross_tco2e) if gross_tco2e > 0.0 else 0.0,
            }
        )

    audit_rows: list[dict[str, Any]] = []
    for result in (a1_a3, a4, a5, b2_b5, b6, c1_c4, module_d1 or {}):
        audit_rows.extend(result.get("source_audit", []))

    return {
        "gross_A_C_tCO2e": gross_tco2e,
        "GWP_kgCO2e_per_pkm": gwp_kgco2e_per_pkm,
        "lifetime_pkm": total_pkm,
        # RICS/EN 15804 STANDARD SIGNED convention: negative = potential benefit,
        # positive = potential load. Never prefix a manual minus sign when displaying it,
        # and never fold it into Gross A-C.
        "module_D1_signed_tCO2e_separate": d_signed,
        # DEVELOPER-DIAGNOSTIC ONLY — arithmetic combination of the gross total and the
        # separate signed D1. It is NOT a "net" result, must never be called Gross, and is
        # never shown in Publication mode. (The former "supplementary_net_if_shown_tCO2e"
        # field is deliberately removed: no field named "net" exists in canonical output.)
        "supplementary_gross_plus_D_standard_signed_tCO2e": gross_tco2e + d_signed,
        "stage_contribution": stage_rows,
        "source_audit": pd.DataFrame(audit_rows).drop_duplicates(
            subset=["code", "source_file", "location"], keep="first"
        ) if audit_rows else pd.DataFrame(),
        "equation_audit": equation_registry_dataframe(),
        "reporting_note": (
            "Headline and functional-unit result use gross A-C only. "
            "Module D1 remains separate supplementary information, reported in the "
            "RICS/EN 15804 standard signed convention: negative = potential benefit; "
            "positive = potential load."
        ),
    }


# -----------------------------------------------------------------------------
# Publication-quality checks
# -----------------------------------------------------------------------------
def publication_checks(
    material_masses_kg: Mapping[str, ProjectQuantity],
    grid_by_year: Mapping[int, GridCarbonYear],
    used_factor_audit: pd.DataFrame,
    assessment_period_years: int,
) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []

    frp_mass = float(material_masses_kg.get("frp", ProjectQuantity(0.0, "kg", "not used")).value)
    if frp_mass > 0.0 and MATERIAL_EF["frp"].value is None:
        issues.append("FRP mass is non-zero but no product-specific A1-A3 EPD factor is supplied.")

    if assessment_period_years <= 0:
        issues.append("Assessment period / RSP must be a positive project-defined value.")
    if len(grid_by_year) != assessment_period_years:
        issues.append(
            "B6 requires one sourced grid-carbon record per assessment year; "
            f"expected {assessment_period_years}, received {len(grid_by_year)}."
        )

    if not used_factor_audit.empty:
        statuses = used_factor_audit.get("status", pd.Series(dtype=str)).astype(str)
        if statuses.str.contains("OPEN", case=False, na=False).any():
            issues.append("At least one OPEN factor was used.")
        if statuses.str.contains("proxy", case=False, na=False).any():
            warnings.append(
                "Verified proxy factors are present. Disclose geography/technology mismatch "
                "and replace with project/local EPDs where available."
            )

    # Citation-freeze gate: a result is not publication-grade while any equation or
    # fixed factor fails to resolve to a full bibliographic record.
    ref_integrity = scientific_reference_integrity_check()
    issues.extend(ref_integrity["issues"])

    return {
        "publication_grade": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "reference_integrity_ok": bool(ref_integrity["ok"]),
    }


# -----------------------------------------------------------------------------
# Streamlit audit display helper
# -----------------------------------------------------------------------------
def render_lca_audit_streamlit(st: Any, final_result: Mapping[str, Any]) -> None:
    """Render equations and factor sources in the existing Streamlit application."""
    with st.expander("Scientific LCA equation audit", expanded=False):
        st.dataframe(final_result["equation_audit"], use_container_width=True, hide_index=True)

    with st.expander("Scientific LCA factor/source audit", expanded=False):
        audit = final_result["source_audit"]
        if isinstance(audit, pd.DataFrame) and not audit.empty:
            columns = [
                "code", "used_value", "unit", "stage", "source_file", "location",
                "status", "boundary_scope", "note",
            ]
            st.dataframe(
                audit[[c for c in columns if c in audit.columns]],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No scientific factors were used in the current run.")


__all__ = [
    "Evidence",
    "GridCarbonYear",
    "ProjectQuantity",
    "ScientificInputError",
    "MATERIAL_EF",
    "TRANSPORT_EF",
    "DIESEL_EF",
    "WASTE_EF",
    "B6_ENERGY_INTENSITY",
    "RICS_WASTE_RATES",
    "EQUATIONS",
    "REFERENCE_CATALOG",
    "OPEN_SOURCE_REQUIREMENTS",
    "make_project_evidence",
    "calculate_effective_ef",
    "calculate_a1_a3",
    "calculate_transport_legs",
    "derive_waste_mass_from_installed",
    "calculate_a5",
    "calculate_b2_b5",
    "update_mass_balance",
    "calculate_b6",
    "calculate_c1_c4",
    "calculate_module_d1",
    "combine_lca_modules",
    "publication_checks",
    "factor_registry_dataframe",
    "equation_registry_dataframe",
    "render_lca_audit_streamlit",
]
