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

REFERENCE_CATALOG: dict[str, dict[str, str]] = {
    "RICS_WLCA_2024": {
        "file": "Whole_life_carbon_assessment_PS_Sept23.pdf",
        "edition": "RICS professional standard, 2nd edition September 2023, version 3 August 2024",
        "role": "Modular A-C/D structure, A5 waste defaults, B2-B5, B6, C1-C4 and Module D reporting",
        "status": "REF-VERIFIED-METHOD",
    },
    "UK_GHG_2025_METHOD": {
        "file": "2025-GHG-CF-methodology-paper.pdf",
        "edition": "June 2025 final methodology paper",
        "role": "Methodology for fuel, freight, electricity, passenger rail and waste conversion factors",
        "status": "REF-VERIFIED-METHOD",
    },
    "UK_GHG_2025_DATA": {
        "file": "ghg-conversion-factors-2025-full-set.xlsx",
        "edition": "2025 full factor set",
        "role": "Numeric transport, fuel and waste factors",
        "status": "REF-VERIFIED-NUMERIC-PROXY-UK",
    },
    "ICE_V4_1_2025": {
        "file": "ICE DB Educational V4.1 - Oct 2025.xlsx",
        "edition": "Educational V4.1, October 2025",
        "role": "Generic A1-A3 embodied-carbon factors",
        "status": "REF-VERIFIED-NUMERIC-PROXY",
    },
    "NTD_2024": {
        "file": "2024 Energy Consumption_250812.xlsx + 2024 TS2.1 Service Data and Operating Expenses Time Series by Mode.xlsx",
        "edition": "2024 datasets",
        "role": "Derived US light-rail and automated-guideway energy-intensity proxies",
        "status": "REF-DERIVED-PROXY-US",
    },
    "IEA_2025_METHOD_ONLY": {
        "file": "IEA_Methodology_Emission_Factors_final_2025.pdf",
        "edition": "2025 methodology",
        "role": "Method only; numeric annual Egypt electricity factors were not uploaded",
        "status": "SOURCE-OPEN-NUMERIC",
    },
    "CLOSED_FACTOR_AUDIT": {
        "file": "lca_q1_closed_numbers_from_uploaded_files.xlsx",
        "edition": "Project audit workbook",
        "role": "Internal traceability index that maps verified numbers to original uploaded files",
        "status": "REF-VERIFIED-INTERNAL-AUDIT-NOT-PRIMARY-SOURCE",
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
# EQUATION REGISTRY
# Each equation is kept next to its scientific / standards basis.
# -----------------------------------------------------------------------------
EQUATIONS: dict[str, dict[str, str]] = {
    # METHOD-REFERENCE: ISO 14040/14044 inventory principle + RICS modular reporting.
    "E1_A1_A3": {
        "stage": "A1-A3",
        "equation": "I_A1-A3,j = M_j * EF_j / 1000",
        "unit_check": "kg * kgCO2e/kg / 1000 = tCO2e",
        "source_file": "ISO 14040:2006; ISO 14044:2006; Whole_life_carbon_assessment_PS_Sept23.pdf",
        "location": "RICS sections 4.5, 4.7 and 5.1; numeric factor location is stored per Evidence record",
        "status": "METHOD-CLOSED; NUMERIC-FACTOR-CONDITIONAL",
        "future_action": "Replace generic ICE factors with project/product EPDs when available.",
    },
    # METHOD-REFERENCE: conditional inventory mixing equation; not a universal credit formula.
    "E2_EFFECTIVE_EF": {
        "stage": "A1-A3 recycled content",
        "equation": "EF_eff = (1 - RC) * EF_virgin + RC * EF_secondary",
        "unit_check": "fraction * kgCO2e/kg + fraction * kgCO2e/kg",
        "source_file": "ICE/EPD metadata + RICS/EN inventory allocation logic",
        "location": "Applicable only when the base factor is explicitly virgin and the secondary-route EF is documented",
        "status": "METHOD-CLOSED; INPUT-CONDITIONAL",
        "future_action": "Do not use with market-average factors that already contain recycled input.",
    },
    # METHOD-REFERENCE: RICS A4/C2 activity structure; numeric EFs from the 2025 UK GHG workbook.
    "E3_A4_C2": {
        "stage": "A4/C2",
        "equation": "I = sum_legs[(M_kg / 1000) * D_km * EF_kgCO2e_per_tkm] / 1000",
        "unit_check": "t * km * kgCO2e/(t.km) / 1000 = tCO2e",
        "source_file": "Whole_life_carbon_assessment_PS_Sept23.pdf; ghg-conversion-factors-2025-full-set.xlsx",
        "location": "RICS modules A4/C2; GHG worksheets Freighting goods and WTT - delivery vehicles & freight",
        "status": "METHOD-CLOSED; UK-FACTOR-PROXY",
        "future_action": "Replace route distance, vehicle class and factor with project/local evidence when available.",
    },
    # METHOD-REFERENCE: activity data multiplied by a fuel conversion factor.
    "E4_FUEL": {
        "stage": "A5/C1/B2-B5",
        "equation": "I_fuel = Activity_fuel * EF_fuel / 1000",
        "unit_check": "L * kgCO2e/L / 1000 = tCO2e",
        "source_file": "2025-GHG-CF-methodology-paper.pdf; ghg-conversion-factors-2025-full-set.xlsx",
        "location": "Methodology section 2; Fuels and WTT - fuels worksheets",
        "status": "METHOD-CLOSED; UK-FACTOR-PROXY",
        "future_action": "Use project fuel type and local/supplier factor if different from UK average diesel blend.",
    },
    # METHOD-REFERENCE: annual electricity activity multiplied by year-specific CI components.
    "E5_ELECTRICITY": {
        "stage": "A5/B2-B5/B6/C1",
        "equation": "I_electricity,t = E_t * CI_t / 1000",
        "unit_check": "kWh * kgCO2e/kWh / 1000 = tCO2e",
        "source_file": "IEA_Methodology_Emission_Factors_final_2025.pdf; Whole_life_carbon_assessment_PS_Sept23.pdf",
        "location": "IEA electricity-factor method; RICS Appendix H and Appendix I",
        "status": "METHOD-CLOSED; EGYPT-NUMERIC-SOURCE-OPEN",
        "future_action": "Upload official annual Egypt/project generation, T&D and upstream/WTT factors.",
    },
    # METHOD-REFERENCE: passenger-km multiplied by operational energy intensity.
    "E6_B6_ENERGY": {
        "stage": "B6",
        "equation": "E_t = PKM_t * EI_t",
        "unit_check": "passenger-km * kWh/passenger-km = kWh",
        "source_file": "2025-GHG-CF-methodology-paper.pdf; project operational/design data preferred",
        "location": "Light-rail energy table, page 79; project data location recorded in Evidence",
        "status": "METHOD-CLOSED; PROXY-OR-PROJECT-INPUT",
        "future_action": "Replace proxy EI with measured or design-specific monorail electricity and passenger-km.",
    },
    # METHOD-REFERENCE: waste factors in the 2025 GHG workbook are per tonne of waste.
    "E7_WASTE": {
        "stage": "A5/C3/C4/B2-B5",
        "equation": "I_waste = (W_kg / 1000) * EF_waste_kgCO2e_per_tonne / 1000",
        "unit_check": "t waste * kgCO2e/t waste / 1000 = tCO2e",
        "source_file": "2025-GHG-CF-methodology-paper.pdf; ghg-conversion-factors-2025-full-set.xlsx",
        "location": "Methodology section 12; Waste disposal worksheet",
        "status": "METHOD-CLOSED; ROUTE/MATERIAL-FACTOR-CONDITIONAL",
        "future_action": "Select the correct waste material and route; never treat kgCO2e/tonne as kgCO2e/kg.",
    },
    # METHOD-REFERENCE: RICS waste rate is a fraction of delivered/purchased quantity.
    "E8_WASTE_FROM_INSTALLED": {
        "stage": "A5.3",
        "equation": "W_kg = M_installed_kg * WR / (1 - WR)",
        "unit_check": "kg * fraction / fraction = kg",
        "source_file": "Whole_life_carbon_assessment_PS_Sept23.pdf",
        "location": "RICS A5.3 waste-rate logic; default rates in Table 18, page 83",
        "status": "METHOD-CLOSED; PROJECT-WASTE-RATE-PREFERRED",
        "future_action": "Replace UK default waste rates with the contractor/project waste plan when available.",
    },
    # METHOD-REFERENCE: each maintenance/use event is activity-based; carbon is not discounted.
    "E9_B2_B5": {
        "stage": "B2-B5",
        "equation": "I_event = new_materials + fuel + electricity + transport + waste_processing; I_B2-B5 = sum_events(I_event)",
        "unit_check": "all event terms are converted to tCO2e before summation",
        "source_file": "Whole_life_carbon_assessment_PS_Sept23.pdf",
        "location": "RICS section 5.2, modules B2-B5",
        "status": "METHOD-CLOSED; PROJECT-ACTIVITY-DATA-REQUIRED",
        "future_action": "Populate B2, B3, B4 and B5 from the asset/O&M plan; do not use discounted cost as carbon.",
    },
    # METHOD-REFERENCE: end-of-life modules must remain separately traceable.
    "E10_C1_C4": {
        "stage": "C1-C4",
        "equation": "I_C1-C4 = I_C1 + I_C2 + I_C3 + I_C4",
        "unit_check": "tCO2e + tCO2e + tCO2e + tCO2e",
        "source_file": "Whole_life_carbon_assessment_PS_Sept23.pdf",
        "location": "RICS section 5.6, modules C1-C4",
        "status": "METHOD-CLOSED; PROJECT-EOL-SCENARIO-REQUIRED",
        "future_action": "Supply per-material EOL shares, treatment factors, transport routes and C1 activity data.",
    },
    # METHOD-REFERENCE: net-flow substitution method; Module D is never included in gross A-C.
    "E11_MODULE_D": {
        "stage": "D1",
        "equation": "Q_net = Q_recovered_output - Q_secondary_input; Benefit_D1 = Q_net * q_sub * (EF_primary - EF_to_substitution) / 1000",
        "unit_check": "kg * fraction * kgCO2e/kg / 1000 = tCO2e",
        "source_file": "Whole_life_carbon_assessment_PS_Sept23.pdf",
        "location": "RICS section 5.7 and Appendix K; EN 15804 net-flow principle",
        "status": "METHOD-CLOSED; MATERIAL-SUBSTITUTION-DATA-REQUIRED",
        "future_action": "Use C-stage-consistent recovered output, secondary input, quality ratio and substitution factors.",
    },
    # METHOD-REFERENCE: modular gross sum; Module D excluded.
    "E12_GROSS": {
        "stage": "A-C total",
        "equation": "Gross_A-C = A1-A3 + A4 + A5 + B2-B5 + B6 + C1-C4",
        "unit_check": "sum of tCO2e modules",
        "source_file": "Whole_life_carbon_assessment_PS_Sept23.pdf",
        "location": "RICS modular structure, sections 2.1, 4.1 and 5",
        "status": "METHOD-CLOSED",
        "future_action": "Do not call the result full cradle-to-grave unless every applicable module is included or justified N/A.",
    },
    # METHOD-REFERENCE: functional unit selected in the study goal/scope.
    "E13_FUNCTIONAL_UNIT": {
        "stage": "Functional unit",
        "equation": "GWP_kgCO2e_per_pkm = Gross_A-C_tCO2e * 1000 / lifetime_PKM",
        "unit_check": "tCO2e * 1000 kg/t / passenger-km",
        "source_file": "ISO 14040:2006; ISO 14044:2006; project goal-and-scope statement",
        "location": "Declared functional unit = 1 passenger-km; passenger-km source recorded per project year",
        "status": "METHOD-CLOSED; PROJECT-SERVICE-DATA-REQUIRED",
        "future_action": "Use measured/design passenger-km and disclose availability/capacity assumptions.",
    },
}



# -----------------------------------------------------------------------------
# VERIFIED / AUDITED FACTOR REGISTRIES
# Numerical values are copied from the uploaded closed-factor audit workbook.
# -----------------------------------------------------------------------------
MATERIAL_EF: dict[str, Evidence] = {
    # REF-PROXY: 0.10336134453781512 kgCO2e/kg.
    # REFERENCE: ICE DB Educational V4.1 - Oct 2025.xlsx, ICE Summary row 277.
    # SOURCE STATUS: verified UK average concrete proxy, not a project mix.
    # FUTURE-REPLACEMENT: project concrete grade/mix EPD or supplier-specific verified data.
    "concrete": Evidence(
        code="ICE-CONCRETE-AVG-UK-ROW277",
        value=0.10336134453781512,
        unit="kgCO2e/kg",
        stage="A1-A3",
        source_file="ICE DB Educational V4.1 - Oct 2025.xlsx",
        location="ICE Summary row 277",
        status="verified_proxy",
        boundary_scope="A1-A3; average UK concrete mix",
        note=(
            "Use only when no project-specific concrete mix/EPD is available. "
            "RICS prefers project-specific concrete grade and mix."
        ),
        factor_basis="market_average",
    ),
    # REF-VERIFIED-PROXY: 1.61 kgCO2e/kg.
    # REFERENCE: ICE DB Educational V4.1 - Oct 2025.xlsx, ICE Summary row 893, Steel Section, A1-A3.
    # FUTURE-REPLACEMENT: separate rebar, rail, plate and section factors if the BOQ distinguishes them.
    "steel": Evidence(
        code="ICE-STEEL-SECTION-ROW893",
        value=1.61,
        unit="kgCO2e/kg",
        stage="A1-A3",
        source_file="ICE DB Educational V4.1 - Oct 2025.xlsx",
        location="ICE Summary row 893",
        status="verified",
        boundary_scope="A1-A3; Steel, Section",
        note="Use the A1-A3 value only. Module D remains separate.",
        factor_basis="market_average",
    ),
    # REF-VERIFIED-PROXY: 13.055539991305551 kgCO2e/kg.
    # REFERENCE: ICE DB Educational V4.1 - Oct 2025.xlsx, ICE Summary rows 47/58.
    # IMPORTANT: market-average worldwide factor already includes about 31% scrap input.
    # FUTURE-REPLACEMENT: project/product EPD; do not apply an extra recycled-content mix to this factor.
    "aluminum": Evidence(
        code="ICE-ALUMINIUM-WORLD-ROW47-58",
        value=13.055539991305551,
        unit="kgCO2e/kg",
        stage="A1-A3",
        source_file="ICE DB Educational V4.1 - Oct 2025.xlsx",
        location="ICE Summary rows 47/58",
        status="verified",
        boundary_scope="A1-A3; Aluminium General, Worldwide",
        note=(
            "ICE worldwide average already includes about 31% scrap input. "
            "Do not apply another recycled-content adjustment to this market-average factor."
        ),
        factor_basis="market_average",
    ),
    # REF-PROXY: 0.49282614286872206 kgCO2e/kg.
    # REFERENCE: ICE DB Educational V4.1 - Oct 2025.xlsx, ICE Summary row 926.
    # SCOPE: timber average, no carbon storage; conservative until biogenic carbon and EOL are modelled.
    "wood": Evidence(
        code="ICE-TIMBER-NO-STORAGE-ROW926",
        value=0.49282614286872206,
        unit="kgCO2e/kg",
        stage="A1-A3",
        source_file="ICE DB Educational V4.1 - Oct 2025.xlsx",
        location="ICE Summary row 926",
        status="verified_proxy",
        boundary_scope="A1-A3; timber average; no carbon storage",
        note="Conservative core until biogenic carbon and EOL are fully modelled.",
        factor_basis="market_average",
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
    ),
    # REF-VERIFIED-PROXY: 1.4369670638496768 kgCO2e/kg.
    # REFERENCE: ICE DB Educational V4.1 - Oct 2025.xlsx, ICE Summary row 618.
    # PROJECT-SOURCE-REQUIRED: area-to-mass conversion needs sourced thickness and density.
    # REF-PROXY: 1% - RICS WLCA Sept 2023, Table 18 p.83; glass waste default.
    "glass": Evidence(
        code="ICE-GLASS-GENERAL-ROW618",
        value=1.4369670638496768,
        unit="kgCO2e/kg",
        stage="A1-A3",
        source_file="ICE DB Educational V4.1 - Oct 2025.xlsx",
        location="ICE Summary row 618",
        status="verified",
        boundary_scope="A1-A3; Glass, General, per kg",
        note="If the UI starts from area, convert area and thickness to mass using a sourced density.",
        factor_basis="market_average",
    ),
}


TRANSPORT_EF: dict[str, dict[str, Evidence]] = {
    # REFERENCE FAMILY: UK Government GHG Conversion Factors 2025, freight worksheets.
    # REF-PROXY: UK fleet/mode averages. Replace with local route/vehicle factors when available.
    "truck": {
        # REF-VERIFIED-PROXY: 0.10163 kgCO2e/tonne.km.
        # REFERENCE: ghg-conversion-factors-2025-full-set.xlsx, Freighting goods row 63.
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
        ),
        # REF-VERIFIED-PROXY: 0.02359 kgCO2e/tonne.km.
        # REFERENCE: ghg-conversion-factors-2025-full-set.xlsx,
        # WTT - delivery vehicles & freight row 57.
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
        ),
        # REF-DERIVED-PROXY: 0.12522 = 0.10163 direct + 0.02359 WTT.
        # REFERENCE: the two verified source rows above.
        # IMPORTANT: select WTW OR direct-only; never add WTT twice.
        "wtw": Evidence(
            "GHG25-HGV-ALL-AVG-LADEN-WTW",
            0.12522,
            "kgCO2e/tonne.km",
            "A4/C2",
            "Derived from 2025 UK GHG full set",
            "row 63 direct + row 57 WTT",
            "verified_derived_proxy_UK",
            "Direct + WTT",
            "0.10163 + 0.02359 = 0.12522",
        ),
    },
    "rail": {
        # REF-VERIFIED-PROXY: 0.02779 kgCO2e/tonne.km.
        # REFERENCE: ghg-conversion-factors-2025-full-set.xlsx, Freighting goods row 106.
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
        ),
        # REF-VERIFIED-PROXY: 0.00691 kgCO2e/tonne.km.
        # REFERENCE: ghg-conversion-factors-2025-full-set.xlsx,
        # WTT - delivery vehicles & freight row 100.
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
        ),
        # REF-DERIVED-PROXY: 0.03470 = 0.02779 direct + 0.00691 WTT.
        # REFERENCE: the two verified source rows above.
        # IMPORTANT: select WTW OR direct-only; never add WTT twice.
        "wtw": Evidence(
            "GHG25-RAIL-FREIGHT-WTW",
            0.03470,
            "kgCO2e/tonne.km",
            "A4/C2",
            "Derived from 2025 UK GHG full set",
            "row 106 direct + row 100 WTT",
            "verified_derived_proxy_UK",
            "Direct + WTT",
            "0.02779 + 0.00691 = 0.03470",
        ),
    },
    "ship": {
        # REF-VERIFIED-PROXY: 0.01321 kgCO2e/tonne.km.
        # REFERENCE: ghg-conversion-factors-2025-full-set.xlsx, Freighting goods row 152.
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
        ),
        # REF-VERIFIED-PROXY: 0.00300 kgCO2e/tonne.km.
        # REFERENCE: ghg-conversion-factors-2025-full-set.xlsx,
        # WTT - delivery vehicles & freight row 146.
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
        ),
        # REF-DERIVED-PROXY: 0.01621 = 0.01321 direct + 0.00300 WTT.
        # REFERENCE: the two verified source rows above.
        # IMPORTANT: select WTW OR direct-only; never add WTT twice.
        "wtw": Evidence(
            "GHG25-SHIP-GENERAL-CARGO-WTW",
            0.01621,
            "kgCO2e/tonne.km",
            "A4/C2",
            "Derived from 2025 UK GHG full set",
            "row 152 direct + row 146 WTT",
            "verified_derived_proxy_UK",
            "Direct + WTT",
            "0.01321 + 0.00300 = 0.01621",
        ),
    },
}

DIESEL_EF: dict[str, Evidence] = {
    # REF-VERIFIED-PROXY: 2.57082 kgCO2e/L direct combustion.
    # REFERENCE: ghg-conversion-factors-2025-full-set.xlsx, Fuels row 72.
    "direct": Evidence(
        "GHG25-DIESEL-AVG-BIOFUEL-DIRECT",
        2.57082,
        "kgCO2e/L",
        "A5/C1/B2-B5",
        "ghg-conversion-factors-2025-full-set.xlsx",
        "Fuels row 72",
        "verified_proxy_UK",
        "Average biofuel blend; direct combustion",
    ),
    # REF-VERIFIED-PROXY: 0.61101 kgCO2e/L upstream/WTT.
    # REFERENCE: ghg-conversion-factors-2025-full-set.xlsx, WTT - fuels row 71.
    "wtt": Evidence(
        "GHG25-DIESEL-AVG-BIOFUEL-WTT",
        0.61101,
        "kgCO2e/L",
        "A5/C1/B2-B5",
        "ghg-conversion-factors-2025-full-set.xlsx",
        "WTT - fuels row 71",
        "verified_proxy_UK",
        "Fuel upstream/WTT",
    ),
    # REF-DERIVED-PROXY: 3.18183 = 2.57082 direct + 0.61101 WTT.
    # IMPORTANT: use either WTW or direct+WTT components, never both twice.
    "wtw": Evidence(
        "GHG25-DIESEL-AVG-BIOFUEL-WTW",
        3.18183,
        "kgCO2e/L",
        "A5/C1/B2-B5",
        "Derived from 2025 UK GHG full set",
        "Fuels row 72 + WTT fuels row 71",
        "verified_derived_proxy_UK",
        "Direct + WTT",
        "2.57082 + 0.61101 = 3.18183",
    ),
    # REF-VERIFIED: 0.14 kgCO2e/L outside scopes.
    # REFERENCE: ghg-conversion-factors-2025-full-set.xlsx, Outside of scopes row 22.
    # REPORTING: disclose separately; do not add to gross A-C.
    "biogenic_outside_scopes": Evidence(
        "GHG25-DIESEL-BIOGENIC-OUTSIDE-SCOPES",
        0.14,
        "kgCO2e/L",
        "Outside gross LCA",
        "ghg-conversion-factors-2025-full-set.xlsx",
        "Outside of scopes row 22",
        "verified_proxy_UK",
        "Report separately; do not add to gross",
    ),
}


WASTE_EF: dict[str, Evidence] = {
    # REF-VERIFIED-PROXY: all values below are kgCO2e per TONNE of waste, not per kg.
    # REFERENCE: ghg-conversion-factors-2025-full-set.xlsx, Waste disposal worksheet.
    "mineral_open_loop": Evidence(
        "GHG25-WASTE-MINERAL-OPEN-LOOP",
        1.00835,
        "kgCO2e/tonne waste",
        "A5/C3",
        "ghg-conversion-factors-2025-full-set.xlsx",
        "Waste disposal rows 24/27/29",
        "verified_proxy_UK",
        "Construction aggregate/concrete/asphalt/brick open-loop route",
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
    ),
}


B6_ENERGY_INTENSITY: dict[str, Evidence] = {
    # REF-PROXY: 0.124 kWh/passenger.km, UK passenger-km-weighted light-rail/tram average.
    # REFERENCE: 2025-GHG-CF-methodology-paper.pdf, light-rail table, page 79.
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
    ),
    # REF-DERIVED-PROXY-US: 0.3031307255338944 kWh/passenger.km.
    # REFERENCE: 2024 Energy Consumption_250812.xlsx + 2024 TS2.1 service PMT dataset.
    "ntd_light_rail_proxy": Evidence(
        "NTD2024-LR-EI-DERIVED",
        0.3031307255338944,
        "kWh/passenger.km",
        "B6",
        "2024 NTD Energy Consumption + TS2.1 PMT",
        "Energy Consumption and PMT 2024",
        "verified_derived_proxy_US",
        "US NTD light-rail aggregate proxy",
    ),
    # REF-DERIVED-PROXY-US: 0.7844814382730434 kWh/passenger.km.
    # REFERENCE: same 2024 NTD energy and PMT files; use only if MG mapping is accepted.
    "ntd_automated_guideway_proxy": Evidence(
        "NTD2024-MG-EI-DERIVED",
        0.7844814382730434,
        "kWh/passenger.km",
        "B6",
        "2024 NTD Energy Consumption + TS2.1 PMT",
        "Energy Consumption and PMT 2024",
        "verified_derived_proxy_US",
        "Monorail/automated-guideway proxy only when mode mapping is accepted",
    ),
}


RICS_WASTE_RATES: dict[str, Evidence] = {
    # REF-PROXY-UK-DEFAULT: RICS Table 18, page 83. Project waste plan has priority.
    "concrete_in_situ": Evidence(
        "RICS23-WR-CONCRETE-IN-SITU", 0.05, "fraction of delivered quantity", "A5.3",
        "Whole_life_carbon_assessment_PS_Sept23.pdf", "Table 18, page 83",
        "verified_default_UK", "Traditional construction default", "5%"
    ),
    # REF-PROXY: 1% - RICS WLCA Sept 2023, Table 18 p.83; replace with project waste plan.
    "concrete_precast": Evidence(
        "RICS23-WR-CONCRETE-PRECAST", 0.01, "fraction of delivered quantity", "A5.3",
        "Whole_life_carbon_assessment_PS_Sept23.pdf", "Table 18, page 83",
        "verified_default_UK", "Traditional construction default", "1%"
    ),
    # REF-PROXY: 10% - RICS WLCA Sept 2023, Table 18 p.83; replace with project waste plan.
    "concrete_sprayed": Evidence(
        "RICS23-WR-CONCRETE-SPRAYED", 0.10, "fraction of delivered quantity", "A5.3",
        "Whole_life_carbon_assessment_PS_Sept23.pdf", "Table 18, page 83",
        "verified_default_UK", "Traditional construction default", "10%"
    ),
    # REF-PROXY: 5% - RICS WLCA Sept 2023, Table 18 p.83; reinforcement waste default.
    "steel_reinforcement": Evidence(
        "RICS23-WR-STEEL-REBAR", 0.05, "fraction of delivered quantity", "A5.3",
        "Whole_life_carbon_assessment_PS_Sept23.pdf", "Table 18, page 83",
        "verified_default_UK", "Traditional construction default", "5%"
    ),
    # REF-PROXY: 1% - RICS WLCA Sept 2023, Table 18 p.83; steel-frame waste default.
    "steel_frame": Evidence(
        "RICS23-WR-STEEL-FRAME", 0.01, "fraction of delivered quantity", "A5.3",
        "Whole_life_carbon_assessment_PS_Sept23.pdf", "Table 18, page 83",
        "verified_default_UK", "Traditional construction default", "1%"
    ),
    # REF-PROXY: 2% - RICS WLCA Sept 2023, Table 18 p.83; timber-frame waste default.
    "timber_frame": Evidence(
        "RICS23-WR-TIMBER-FRAME", 0.02, "fraction of delivered quantity", "A5.3",
        "Whole_life_carbon_assessment_PS_Sept23.pdf", "Table 18, page 83",
        "verified_default_UK", "Traditional construction default", "2%"
    ),
    # REF-PROXY: 10% - RICS WLCA Sept 2023, Table 18 p.83; formwork waste default.
    "timber_formwork": Evidence(
        "RICS23-WR-TIMBER-FORMWORK", 0.10, "fraction of delivered quantity", "A5.3",
        "Whole_life_carbon_assessment_PS_Sept23.pdf", "Table 18, page 83",
        "verified_default_UK", "Traditional construction default", "10%"
    ),
    # REF-PROXY: 1% - RICS WLCA Sept 2023, Table 18 p.83; aluminium waste default.
    "aluminium_sheet_or_extrusion": Evidence(
        "RICS23-WR-ALUMINIUM", 0.01, "fraction of delivered quantity", "A5.3",
        "Whole_life_carbon_assessment_PS_Sept23.pdf", "Table 18, page 83",
        "verified_default_UK", "Traditional construction default", "1%"
    ),
    # REF-VERIFIED-PROXY: 1.4369670638496768 kgCO2e/kg.
    # REFERENCE: ICE DB Educational V4.1 - Oct 2025.xlsx, ICE Summary row 618.
    # PROJECT-SOURCE-REQUIRED: area-to-mass conversion needs sourced thickness and density.
    # REF-PROXY: 1% - RICS WLCA Sept 2023, Table 18 p.83; glass waste default.
    "glass": Evidence(
        "RICS23-WR-GLASS", 0.01, "fraction of delivered quantity", "A5.3",
        "Whole_life_carbon_assessment_PS_Sept23.pdf", "Table 18, page 83",
        "verified_default_UK", "Traditional construction default", "1%"
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


def _factor_audit_row(factor: Evidence, used_value: Optional[float] = None) -> dict[str, Any]:
    row = asdict(factor)
    row["used_value"] = factor.value if used_value is None else used_value
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
    return pd.DataFrame(
        [{"equation_id": key, **value} for key, value in EQUATIONS.items()]
    )


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
) -> Evidence:
    """Create a sourced project-specific factor, e.g. an EPD or Egypt grid value."""
    _require_source(source_file, f"{code} source_file")
    _require_source(location, f"{code} location")
    if not math.isfinite(float(value)):
        raise ScientificInputError(f"{code} value must be finite.")
    return Evidence(
        code=code,
        value=float(value),
        unit=unit,
        stage=stage,
        source_file=source_file,
        location=location,
        status="project_specific_verified_by_user",
        boundary_scope=boundary_scope,
        note=note,
        factor_basis=factor_basis,
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
    # METHOD-REFERENCE E2_EFFECTIVE_EF:
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
        # METHOD-REFERENCE E3_A4_C2:
        # I = (M_kg/1000) * D_km * EF_kgCO2e_per_tkm / 1000.
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
                "equation_id": "E3_A4_C2",
            }
        )
        audit.append(_factor_audit_row(factor, ef))

    return {
        "stage": stage,
        "total_tco2e": total_tco2e,
        "legs": rows,
        "source_audit": audit,
        "equation_ids": ["E3_A4_C2"],
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
        "equation_ids": ["E1_A1_A3", "E3_A4_C2", "E4_FUEL", "E5_ELECTRICITY", "E7_WASTE"],
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
        "equation_ids": ["E10_C1_C4", "E3_A4_C2", "E4_FUEL", "E5_ELECTRICITY", "E7_WASTE"],
    }


# -----------------------------------------------------------------------------
# Module D1 - separate from gross
# -----------------------------------------------------------------------------
def calculate_module_d1(net_flow_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Calculate signed D1 potential benefits/loads using net output flows.

    Positive result = potential benefit. Negative result = potential load.
    It is never added to or subtracted from the reported gross A-C total.
    """
    output_rows: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []
    total_signed_tco2e = 0.0

    for index, row in enumerate(net_flow_rows, start=1):
        recovered_output_kg = float(row.get("recovered_output_kg", 0.0))
        secondary_input_kg = float(row.get("secondary_input_kg", 0.0))
        substitution_ratio = float(row.get("substitution_ratio", 0.0))
        if recovered_output_kg < 0.0 or secondary_input_kg < 0.0:
            raise ScientificInputError(f"D1 row {index} has a negative flow.")
        if substitution_ratio < 0.0 or substitution_ratio > 1.0:
            raise ScientificInputError(f"D1 row {index} substitution ratio must be 0..1.")
        _require_source(str(row.get("flow_source", "")), f"D1 row {index} flows")
        _require_source(str(row.get("substitution_source", "")), f"D1 row {index} substitution")

        primary = row.get("primary_factor")
        recovery = row.get("recovery_to_substitution_factor")
        if not isinstance(primary, Evidence) or not isinstance(recovery, Evidence):
            raise ScientificInputError(
                f"D1 row {index} requires primary_factor and recovery_to_substitution_factor Evidence."
            )
        ef_primary = primary.require_value()
        ef_recovery = recovery.require_value()
        # METHOD-REFERENCE E11_MODULE_D:
        # Q_net = recovered output - secondary input.
        # Module D is separate supplementary information and never part of gross A-C.
        net_output_kg = recovered_output_kg - secondary_input_kg
        signed_tco2e = (
            net_output_kg
            * substitution_ratio
            * (ef_primary - ef_recovery)
            / KG_CO2E_PER_TONNE_CO2E
        )
        total_signed_tco2e += signed_tco2e
        audit.extend([_factor_audit_row(primary), _factor_audit_row(recovery)])
        output_rows.append(
            {
                "material": row.get("material", "not specified"),
                "recovered_output_kg": recovered_output_kg,
                "secondary_input_kg": secondary_input_kg,
                "net_output_kg": net_output_kg,
                "substitution_ratio": substitution_ratio,
                "primary_ef_kgco2e_per_kg": ef_primary,
                "recovery_to_substitution_ef_kgco2e_per_kg": ef_recovery,
                "D1_signed_tCO2e": signed_tco2e,
                "equation_id": "E11_MODULE_D",
            }
        )

    return {
        "stage": "D1",
        "signed_tco2e": total_signed_tco2e,
        "benefit_positive_tco2e": max(total_signed_tco2e, 0.0),
        "load_positive_tco2e": max(-total_signed_tco2e, 0.0),
        "rows": output_rows,
        "source_audit": audit,
        "equation_ids": ["E11_MODULE_D"],
        "reporting_note": "Module D1 is separate supplementary information; never part of gross A-C.",
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
        "module_D1_signed_tCO2e_separate": d_signed,
        # REPORTING-ONLY arithmetic: gross A-C minus separate signed D1. Never label as gross A-C.
        "supplementary_net_if_shown_tCO2e": gross_tco2e - d_signed,
        "stage_contribution": stage_rows,
        "source_audit": pd.DataFrame(audit_rows).drop_duplicates(
            subset=["code", "source_file", "location"], keep="first"
        ) if audit_rows else pd.DataFrame(),
        "equation_audit": equation_registry_dataframe(),
        "reporting_note": (
            "Headline and functional-unit result use gross A-C only. "
            "Module D1 remains separate supplementary information."
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

    return {
        "publication_grade": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
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
