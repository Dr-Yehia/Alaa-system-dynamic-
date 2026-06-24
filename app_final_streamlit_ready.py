import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import io

# ═══════════════════════════════════════════════════════════════
# PAGE CONFIGURATION
# ═══════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Enhanced Monorail LCA/LCCA Assessment Tool",
    page_icon="🚝",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ═══════════════════════════════════════════════════════════════
# LI & ZHU (2022) MONORAIL LCA BENCHMARK - EXTERNAL COMPARISON ONLY
# Reference: Li and Zhu (2022)
# DOI: 10.1155/2022/3872069
# Journal: Computational Intelligence and Neuroscience (Hindawi)
# Used ONLY as an external benchmark / reproduction reference.
# It is NEVER a source of material factors and NEVER a calibration input
# to the core LCA/LCCA model.
# NOTE: confirm exact article title from the uploaded Li & Zhu (2022) PDF.
# ═══════════════════════════════════════════════════════════════

LIZHU_2022_BENCHMARK = {
    'reference': {
        'title': '[confirm exact title from uploaded Li & Zhu (2022) PDF]',
        'authors': 'Li and Zhu',
        'journal': 'Computational Intelligence and Neuroscience (Hindawi)',
        'year': 2022,
        'doi': '10.1155/2022/3872069',
        'indexing': '[verify current indexing/quartile before publication]',
        'verification': 'Peer-reviewed scientific publication (benchmark only)'
    },
    'system_parameters': {
        'length_km': 96,
        'lifetime_years': 100,
        'functional_unit': '1 passenger-km',
        'system_boundary': 'Cradle-to-grave'
    },
    'material_intensity_per_km': {
        'concrete_m3': 7291.67,
        'steel_tons': 1041.67,
        'aluminum_tons': 52.08,
        'unit': 'per km'
    },
    'embodied_impact_per_km': {
        'energy_GJ': 55982,
        'carbon_tons_CO2': 4662,
        'unit': 'per km'
    },
    'operational_performance': {
        'energy_kwh_per_pkm': 0.088,
        'carbon_kgCO2_per_pkm': 0.0352,
        'unit': 'per passenger-km'
    }
}

# ═══════════════════════════════════════════════════════════════
# REFERENCE VALUES
# ═══════════════════════════════════════════════════════════════
REF_CONCRETE = 700000
REF_STEEL = 100000
REF_ALUMINUM = 10000
REF_WOOD = 2000
REF_FRP = 1000
REF_GLASS = 500
REF_LENGTH = 96

# ═══════════════════════════════════════════════════════════════
# MATERIAL EMBODIED CARBON FACTORS — A1-A3 (cradle-to-gate)
# ───────────────────────────────────────────────────────────────
# SOURCE HIERARCHY (applied per material, most-specific first):
#   1) Project BOQ quantities (user input)
#   2) Local / product-specific EPD  (highest evidence — use if available)
#   3) ICE Database Educational V4.1 (Oct 2025), "ICE Summary" sheet
#   4) Li and Zhu (2022)  → BENCHMARK COMPARISON ONLY, never a factor source
#
# CARBON (gwp_kgco2e_per_kg): taken EXACTLY from ICE Database Educational
#   V4.1 (Oct 2025), ICE Summary sheet, Embodied Carbon column (A1-A3).
#   Each factor records: ice_name (exact ICE row), dqi_score (data quality),
#   boundary, declared unit, and status.
#
# ENERGY (ee_mj_per_kg): LEGACY values (Hammond & Jones 2008 / ICE v2.0).
#   These are NOT from ICE V4.1 and are reported as a secondary indicator
#   only. Carbon (kgCO2e) is the PRIMARY LCA indicator of this study.
#
# Module D (end-of-life recycling credit) is NOT netted into A1-A3 here;
#   it is reported separately downstream per EN 15804.
# ═══════════════════════════════════════════════════════════════
MATERIAL_FACTORS = {
    "concrete_32_40": {
        "ee_mj_per_kg": 0.91,
        "gwp_kgco2e_per_kg": 0.1342,
        "ice_name": "Concrete 32/40 MPa",
        "source": "ICE Database Educational V4.1 (Oct 2025), ICE Summary sheet, Embodied Carbon (A1-A3)",
        "ee_source": "Legacy Hammond & Jones (2008) / ICE v2.0 — NOT from ICE V4.1 (secondary indicator)",
        "dqi_score": 0.7133,
        "version": "ICE V4.1 (carbon) + ICE v2.0 (energy, legacy)",
        "material_category": "Concrete RC 32/40 MPa (structural)",
        "boundary": "A1-A3 / cradle-to-gate",
        "source_id": "ICE-CONC-3240",
        "declared_unit": "1 kg",
        "status": "verified_ICE_V4.1_carbon"
    },
    "steel_section": {
        "ee_mj_per_kg": 20.10,
        "gwp_kgco2e_per_kg": 1.61,
        "ice_name": "Steel, Section",
        "source": "ICE Database Educational V4.1 (Oct 2025), ICE Summary sheet, Embodied Carbon (A1-A3)",
        "ee_source": "Legacy Hammond & Jones (2008) / ICE v2.0 — NOT from ICE V4.1 (secondary indicator)",
        "dqi_score": 0.80,
        "version": "ICE V4.1 (carbon) + ICE v2.0 (energy, legacy)",
        "material_category": "Structural steel section (use Steel, Rebar = 1.72 if reinforcement)",
        "boundary": "A1-A3 / cradle-to-gate",
        "source_id": "ICE-STEEL-SECTION",
        "declared_unit": "1 kg",
        "status": "verified_ICE_V4.1_carbon"
    },
    "aluminum_general": {
        "ee_mj_per_kg": 155.0,
        "gwp_kgco2e_per_kg": 13.0555,
        "ice_name": "Aluminium General, Worldwide",
        "source": "ICE Database Educational V4.1 (Oct 2025), ICE Summary sheet, Embodied Carbon (A1-A3)",
        "ee_source": "Legacy Hammond & Jones (2008) / ICE v2.0 — NOT from ICE V4.1 (secondary indicator)",
        "dqi_score": 0.64,
        "version": "ICE V4.1 (carbon) + ICE v2.0 (energy, legacy)",
        "material_category": "Primary aluminium, worldwide mix (most conservative; sensitivity: ME=10.81, EU=6.67)",
        "boundary": "A1-A3 / cradle-to-gate",
        "source_id": "ICE-AL-WORLDWIDE",
        "declared_unit": "1 kg",
        "status": "verified_ICE_V4.1_carbon"
    },
    "wood_general": {
        "ee_mj_per_kg": 10.0,
        "gwp_kgco2e_per_kg": 0.4928,
        "ice_name": "Timber - Average of all data - No Carbon Storage",
        "source": "ICE Database Educational V4.1 (Oct 2025), ICE Summary sheet, Embodied Carbon (A1-A3)",
        "ee_source": "Legacy Hammond & Jones (2008) / ICE v2.0 — NOT from ICE V4.1 (secondary indicator)",
        "dqi_score": 0.7103,
        "version": "ICE V4.1 (carbon) + ICE v2.0 (energy, legacy)",
        "material_category": "Timber, average — NO carbon storage (EoL C1-C4 not yet closed)",
        "boundary": "A1-A3 / cradle-to-gate",
        "source_id": "ICE-TIMBER-NOSTORAGE",
        "declared_unit": "1 kg",
        "status": "verified_ICE_V4.1_carbon"
    },
    "frp_general": {
        "ee_mj_per_kg": 95.0,
        "gwp_kgco2e_per_kg": 6.50,
        "ice_name": "n/a — ICE V4.1 GRP has no published A1-A3 carbon value",
        "source": "PLACEHOLDER — not from ICE V4.1; requires product-specific EPD before publication",
        "ee_source": "Legacy estimate — NOT verified",
        "dqi_score": None,
        "version": "UNVERIFIED placeholder",
        "material_category": "FRP / GRP composite",
        "boundary": "A1-A3 / cradle-to-gate",
        "source_id": "FRP-UNVERIFIED",
        "declared_unit": "1 kg",
        "status": "UNVERIFIED — requires product-specific EPD (do NOT use ICE/guess)"
    },
    "glass_primary": {
        "ee_mj_per_kg": 15.0,
        "gwp_kgco2e_per_kg": 1.4370,
        "ice_name": "Glass, General, per kg",
        "source": "ICE Database Educational V4.1 (Oct 2025), ICE Summary sheet, Embodied Carbon (A1-A3)",
        "ee_source": "Legacy Hammond & Jones (2008) / ICE v2.0 — NOT from ICE V4.1 (secondary indicator)",
        "dqi_score": 0.6363,
        "version": "ICE V4.1 (carbon) + ICE v2.0 (energy, legacy)",
        "material_category": "Flat glass, general (sensitivity: double=1.6256, toughened=1.6672)",
        "boundary": "A1-A3 / cradle-to-gate",
        "source_id": "ICE-GLASS-GENERAL",
        "declared_unit": "1 kg",
        "status": "verified_ICE_V4.1_carbon"
    }
}



MATERIAL_FACTOR_AUDIT = pd.DataFrame([
    {
        "material": key,
        "ice_name": val.get("ice_name", "n/a"),
        "gwp_kgco2e_per_kg": val["gwp_kgco2e_per_kg"],
        "dqi_score": val.get("dqi_score", None),
        "ee_mj_per_kg (legacy)": val["ee_mj_per_kg"],
        "carbon_source": val["source"],
        "energy_source": val.get("ee_source", "n/a"),
        "source_id": val.get("source_id", "not specified"),
        "declared_unit": val.get("declared_unit", "1 kg"),
        "version": val["version"],
        "material_category": val["material_category"],
        "boundary": val["boundary"],
        "status": val["status"],
    }
    for key, val in MATERIAL_FACTORS.items()
])

RECYCLING_CREDIT_SCENARIOS = {
    "none": {
        "steel": {"energy_credit_fraction": 0.0, "carbon_credit_fraction": 0.0},
        "aluminum": {"energy_credit_fraction": 0.0, "carbon_credit_fraction": 0.0},
        "source": "No end-of-life credit scenario"
    },
    "conservative": {
        "steel": {"energy_credit_fraction": 0.35, "carbon_credit_fraction": 0.30},
        "aluminum": {"energy_credit_fraction": 0.50, "carbon_credit_fraction": 0.50},
        "source": "Scenario assumption; use for sensitivity only"
    },
    "base": {
        "steel": {"energy_credit_fraction": 0.70, "carbon_credit_fraction": 0.65},
        "aluminum": {"energy_credit_fraction": 0.85, "carbon_credit_fraction": 0.90},
        "source": "Scenario assumption; requires EPD/EoL allocation evidence before final publication"
    }
}

UNCERTAINTY_FACTORS = {
    "concrete_factor": {"cv": 0.10, "source": "Scenario assumption; replace with EPD/database uncertainty before final statistical claims"},
    "steel_factor": {"cv": 0.08, "source": "Scenario assumption; replace with EPD/database uncertainty before final statistical claims"},
    "energy_factor": {"cv": 0.15, "source": "Scenario assumption; replace with measured operational uncertainty before final statistical claims"},
    "grid_carbon_factor": {"cv": 0.12, "source": "Scenario assumption; replace with grid-factor uncertainty before final statistical claims"}
}

TRANSPORT_EMISSION_FACTORS = {"truck":0.10,"rail":0.03,"ship":0.015}

# ═══════════════════════════════════════════════════════════════
# FUEL FACTORS REGISTRY (combustion EFs) — scenario/default values
# Every factor carries source/unit/status, like MATERIAL_FACTORS.
# Replace with verified local factors before publication.
# ═══════════════════════════════════════════════════════════════
FUEL_FACTORS = {
    "diesel": {
        "ef_kgco2e_per_l": 2.68,
        "unit": "kgCO2e/L",
        "source": "DEFRA/BEIS GHG conversion factors (generic diesel, combustion)",
        "status": "scenario/default — replace with verified local factor before publication",
    },
}

# ═══════════════════════════════════════════════════════════════
# MATERIAL DENSITIES (kg/m³)
# ═══════════════════════════════════════════════════════════════
DENSITIES = {
    'concrete': 2400,
    'wood': 600,
    'steel': 7850,
    'aluminum': 2700,
    'frp': 1850,
    'glass': 2500,
    'glass_surface': 10
}


# ═══════════════════════════════════════════════════════════════
# SCIENTIFIC CALCULATION FUNCTIONS
# ═══════════════════════════════════════════════════════════════


def calculate_intensity_score(value, ref_value, min_scale=0.5, max_scale=1.5):
    """Calculate intensity score based on reference value"""
    intensity = value / ref_value
    if intensity < min_scale:
        return 100 * (1 - (min_scale - intensity) / min_scale)
    elif intensity > max_scale:
        return 100 * (1 - (intensity - max_scale) / max_scale)
    else:
        return 100


def calculate_material_score_integrated(material_data):
    """Integrated material score with recycling bonuses"""
    concrete_intensity = material_data['concrete_intensity']
    steel_intensity = material_data['steel_intensity']
    aluminum_intensity = material_data['aluminum_intensity']
    wood_intensity = material_data['wood_intensity']
    frp_intensity = material_data['frp_intensity']
    glass_intensity = material_data['glass_intensity']

    steel_recycle_bonus = material_data['steel_recycle_rate'] / 100.0 * 0.05
    aluminum_recycle_bonus = material_data['aluminum_recycle_rate'] / 100.0 * 0.05
    recycling_bonus = steel_recycle_bonus + aluminum_recycle_bonus

    base_material_score = (
        0.30 * concrete_intensity +
        0.30 * steel_intensity +
        0.20 * aluminum_intensity +
        0.10 * wood_intensity +
        0.05 * frp_intensity +
        0.05 * glass_intensity
    )

    material_score = min(100.0, base_material_score * (1.0 + recycling_bonus))
    return material_score


def calculate_environmental_display_score(env_data):
    """Heuristic environmental display score (not ISO LCA result)."""
    operational_co2 = env_data['operational_co2']
    embodied_co2 = env_data['embodied_co2']
    renewable_share = env_data['renewable_share']
    noise_reduction = env_data['noise_reduction']
    land_efficiency = env_data['land_efficiency']

    renewable_mitigation_factor = 1.0 - (renewable_share / 100.0) * 0.40
    adjusted_operational_co2 = operational_co2 * renewable_mitigation_factor

    land_efficiency_bonus = (land_efficiency / 5000.0) * 0.15
    land_efficiency_bonus = np.clip(land_efficiency_bonus, 0, 0.15)
    adjusted_embodied_co2 = embodied_co2 * (1.0 - land_efficiency_bonus)

    total_co2_adjusted = adjusted_operational_co2 + adjusted_embodied_co2

    noise_quality_multiplier = 1.0 + (noise_reduction / 15.0) * 0.10
    noise_quality_multiplier = np.clip(noise_quality_multiplier, 1.0, 1.10)

    co2_normalized = (total_co2_adjusted - 5000.0) / (50000.0 - 5000.0)
    co2_normalized = np.clip(co2_normalized, 0, 1)
    co2_score = (1.0 - co2_normalized) * 100.0

    environmental_score = co2_score * noise_quality_multiplier
    environmental_score = np.clip(environmental_score, 0, 100)
    return float(environmental_score)


def calculate_operational_score_integrated(op_data):
    """Integrated operational score with internal coupling effects"""
    time_savings = op_data['time_savings']
    availability = op_data['availability']
    land_efficiency = op_data['land_efficiency']
    energy_efficiency = op_data['energy_per_pax_km']

    availability_factor = availability / 100.0
    effective_time_savings = time_savings * availability_factor
    time_score = min(100.0, (effective_time_savings / 2500.0) * 100.0)

    energy_bonus = (0.20 - energy_efficiency) / 0.20
    energy_bonus = np.clip(energy_bonus, 0, 1)

    adjusted_land_efficiency = land_efficiency * (1.0 + energy_bonus * 0.20)
    land_score = min(100.0, (adjusted_land_efficiency / 5000.0) * 100.0)

    synergy_multiplier = 1.0 + (availability_factor * float(energy_bonus) * 0.10)
    availability_score = availability * synergy_multiplier
    availability_score = min(100.0, availability_score)

    operational_score = (
        time_score * 0.40 +
        availability_score * 0.40 +
        land_score * 0.20
    )

    operational_score = np.clip(operational_score, 0, 100)
    return float(operational_score)


def calculate_economic_score_integrated(econ_data):
    """Heuristic economic display score using NPV-LCC-aware cost efficiency."""
    construction_cost = econ_data['construction_cost']
    npv_lcc_m = econ_data['npv_lcc_m']
    jobs_created = econ_data['jobs_created']
    economic_multiplier = econ_data['economic_multiplier']

    jobs_per_million = jobs_created / max(construction_cost, 1.0)
    job_efficiency_bonus = min(1.0, jobs_per_million / 2.0) * 0.15

    lcc_ratio = npv_lcc_m / max(construction_cost, 1.0)
    cost_efficiency_score = 100.0 / (1.0 + max(lcc_ratio - 1.0, 0.0))
    cost_efficiency_score = min(100.0, cost_efficiency_score * (1.0 + job_efficiency_bonus))

    total_economic_impact = jobs_created * economic_multiplier
    jobs_score = min(100.0, (total_economic_impact / 12000.0) * 100.0)

    multiplier_score = min(100.0, (economic_multiplier / 3.5) * 100.0)

    economic_score = (
        jobs_score * 0.50 +
        cost_efficiency_score * 0.30 +
        multiplier_score * 0.20
    )

    economic_score = np.clip(economic_score, 0, 100)
    return float(economic_score)


def calculate_cross_category_interactions(mat_score, env_score, op_score, econ_score):
    """Calculate cross-category interaction effects (synergies and trade-offs)"""
    mat_norm = mat_score / 100.0
    env_norm = env_score / 100.0
    op_norm = op_score / 100.0
    econ_norm = econ_score / 100.0

    # Heuristic interaction visualization only.
    # Coefficients are illustrative and are not validated causal effects.
    interaction_matrix = {
        'mat_to_env': -0.25,
        'env_to_op': 0.15,
        'op_to_econ': 0.30,
        'econ_to_mat': 0.20,
        'mat_to_op': 0.10,
        'env_to_econ': -0.15
    }

    interaction_effects = {
        'mat_env_effect': mat_norm * interaction_matrix['mat_to_env'] * 100,
        'env_op_effect': env_norm * interaction_matrix['env_to_op'] * 100,
        'op_econ_effect': op_norm * interaction_matrix['op_to_econ'] * 100,
        'econ_mat_effect': econ_norm * interaction_matrix['econ_to_mat'] * 100,
        'mat_op_effect': mat_norm * interaction_matrix['mat_to_op'] * 100,
        'env_econ_effect': env_norm * interaction_matrix['env_to_econ'] * 100
    }

    adjusted_material_score = mat_score + interaction_effects['econ_mat_effect']
    adjusted_environmental_score = env_score + interaction_effects['mat_env_effect']
    adjusted_operational_score = (op_score +
                                   interaction_effects['env_op_effect'] +
                                   interaction_effects['mat_op_effect'])
    adjusted_economic_score = (econ_score +
                                interaction_effects['op_econ_effect'] +
                                interaction_effects['env_econ_effect'])

    adjusted_material_score = float(np.clip(adjusted_material_score, 0, 100))
    adjusted_environmental_score = float(np.clip(adjusted_environmental_score, 0, 100))
    adjusted_operational_score = float(np.clip(adjusted_operational_score, 0, 100))
    adjusted_economic_score = float(np.clip(adjusted_economic_score, 0, 100))

    total_synergy = sum([abs(effect) for key, effect in interaction_effects.items() if effect > 0])
    total_tradeoff = sum([abs(effect) for key, effect in interaction_effects.items() if effect < 0])

    synergy_ratio = total_synergy / max(total_tradeoff, 0.01)

    return {
        'adjusted_material_score': adjusted_material_score,
        'adjusted_environmental_score': adjusted_environmental_score,
        'adjusted_operational_score': adjusted_operational_score,
        'adjusted_economic_score': adjusted_economic_score,
        'interaction_effects': interaction_effects,
        'total_synergy': total_synergy,
        'total_tradeoff': total_tradeoff,
        'synergy_ratio': synergy_ratio
    }



ASSESSMENT_LIFETIME_YEARS = 50


def calculate_a4_transport_co2(material_masses_kg, distance_km, mode):
    ef = TRANSPORT_EMISSION_FACTORS.get(mode, TRANSPORT_EMISSION_FACTORS["truck"])
    total_mass_tons = sum(material_masses_kg.values()) / 1000.0
    return total_mass_tons * distance_km * ef / 1000.0


def calculate_lca_summary(embodied_co2_tons, annual_operational_co2_tons, embodied_energy_mj,
                          annual_operational_energy_kwh, daily_pax_km, lifetime_years,
                          a4_transport_co2_tons=0.0,
                          module_d_carbon_credit_tons=0.0, module_d_energy_credit_mj=0.0):
    lifetime_operational_co2_tons = annual_operational_co2_tons * lifetime_years
    # A1-A3 (gross) + A4 + B6. Module D is NOT added here (EN 15804: separate module).
    total_lifecycle_co2_tons = embodied_co2_tons + a4_transport_co2_tons + lifetime_operational_co2_tons
    lifetime_pax_km = daily_pax_km * 365 * lifetime_years
    co2_kg_per_pkm = (total_lifecycle_co2_tons * 1000 / lifetime_pax_km) if lifetime_pax_km > 0 else np.nan

    return {
        "scope": "Gross modular A1-C4 LCA: A1-A3 + A4 + optional A5 + activity-based B2-B5 + active B6 + optional C1-C4. Module D reported separately.",
        "embodied_co2_tons": embodied_co2_tons,
        "a4_transport_co2_tons": a4_transport_co2_tons,
        "annual_operational_co2_tons": annual_operational_co2_tons,
        "lifetime_operational_co2_tons": lifetime_operational_co2_tons,
        "total_lifecycle_co2_tons": total_lifecycle_co2_tons,
        "module_d_carbon_credit_tons": module_d_carbon_credit_tons,
        "module_d_energy_credit_mj": module_d_energy_credit_mj,
        "co2_kg_per_pkm": co2_kg_per_pkm,
        "embodied_energy_mj": embodied_energy_mj,
        "annual_operational_energy_kwh": annual_operational_energy_kwh,
        "lifetime_operational_energy_kwh": annual_operational_energy_kwh * lifetime_years,
        "lifetime_pax_km": lifetime_pax_km,
        "stage_coverage": {
            "A1_A3_materials": "included (gross)",
            "A4_transport": "included" if a4_transport_co2_tons > 0 else "not included",
            "A5_construction": "not included",
            "B2_B5_maintenance_replacement": "not included",
            "B6_operation": "included",
            "C1_C4_end_of_life": "not included",
            "D_recycling_credit": "reported separately (not in A1-C4 total)"
        }
    }


def calculate_lcc_npv(construction_cost_m, annual_maintenance_m, annual_energy_cost_m=0.0,
                      replacement_costs=None, end_of_life_cost_m=0.0, residual_value_m=0.0,
                      discount_rate_pct=5.0, lifetime_years=50):
    r = discount_rate_pct / 100.0
    n = lifetime_years
    replacement_costs = replacement_costs or {}

    def pv_single(cost, year):
        return cost / ((1 + r) ** year) if r > 0 else cost

    upv = (1 - (1 + r) ** (-n)) / r if r > 0 else n

    pv_maintenance = annual_maintenance_m * upv
    pv_energy = annual_energy_cost_m * upv
    pv_replacement = sum(pv_single(cost, year) for year, cost in replacement_costs.items())
    pv_end_of_life = pv_single(end_of_life_cost_m, n)
    pv_residual = pv_single(residual_value_m, n)

    npv_lcc = construction_cost_m + pv_maintenance + pv_energy + pv_replacement + pv_end_of_life - pv_residual

    return {"npv_lcc_m": npv_lcc, "discount_rate_pct": discount_rate_pct, "lifetime_years": n}

# ═══════════════════════════════════════════════════════════════
# PHASE 2 — SYSTEM DYNAMICS LAYER FOR B6 (asset condition -> energy)
# ───────────────────────────────────────────────────────────────
# SYMBOL TABLE (scenario-based; NOT validated unless calibrated)
#   t      operating year (annual step), 1..T
#   T      assessment lifetime (years) = ASSESSMENT_LIFETIME_YEARS
#   C_t    asset condition at START of year t (dimensionless 0..1) — STOCK
#   C0     initial condition (default 1.0)
#   DR_t   degradation outflow (condition/year)
#   MR_t   maintenance recovery inflow (condition/year)
#   delta  annual degradation coefficient (condition/year) — scenario
#   rho    maintenance recovery efficiency (condition/action) — scenario
#   m_t    maintenance action (0/1), 1 on maintenance years
#   tau    maintenance effect delay (years)
#   alpha  energy penalty coefficient for degradation (dimensionless) — sensitivity
#   EI0    base energy intensity (kWh/pkm) = params['energy_per_pax']
#   EI_t   dynamic energy intensity (kWh/pkm)
#   PKM_t  annual passenger-km
#   g      annual demand growth (fraction)
#   CI_t   grid carbon intensity (kgCO2/kWh) — NO renewable multiplier in Phase 2
#
# Stock-flow (continuous):   dC/dt = MR(t) - DR(t)
#   DR_t = min(delta, C_t/dt)        constant annual loss, capped so C >= 0
#   MR_t = rho * m_(t-tau)           delayed recovery, capped so C <= 1
# Euler annual step (dt=1), degradation applied BEFORE recovery.
# Coupling:  EI_t = EI0 * [1 + alpha*(1 - C_t)]  ->  dynamic B6 emissions.
# SD parameters are SCENARIO ASSUMPTIONS unless calibrated with inspection,
# maintenance, or measured operational-energy data. The model is NOT validated.
# ═══════════════════════════════════════════════════════════════

def simulate_asset_condition(C0=1.0, delta=0.005, maintenance_interval=5,
                             rho=0.05, tau=1, lifetime_years=ASSESSMENT_LIFETIME_YEARS, dt=1.0):
    """Stock-flow simulation of asset condition C(t).
    Returns (rows, condition_start) where condition_start[t-1] = C at start of year t.
    Degradation is applied first, then delayed maintenance recovery, each capped."""
    def is_maint_year(yr):
        return bool(maintenance_interval) and maintenance_interval > 0 and yr >= 1 and (yr % maintenance_interval == 0)

    rows, condition_start = [], []
    C = float(np.clip(C0, 0.0, 1.0))
    for t in range(1, int(lifetime_years) + 1):
        C_start = C
        condition_start.append(C_start)
        # Outflow: degradation (constant annual loss, capped so condition stays >= 0)
        DR = min(delta, C_start / dt) if dt > 0 else 0.0
        C_pre = max(0.0, C_start - dt * DR)
        # Inflow: delayed maintenance recovery (capped so condition stays <= 1)
        m_action = 1 if is_maint_year(t) else 0
        src_year = t - tau
        delayed = 1 if (src_year >= 1 and is_maint_year(src_year)) else 0
        MR_request = rho * delayed
        MR_actual = max(0.0, min(MR_request, (1.0 - C_pre) / dt)) if dt > 0 else 0.0
        C_end = float(np.clip(C_pre + dt * MR_actual, 0.0, 1.0))
        rows.append({
            'year': t, 'C_start': C_start,
            'maintenance_action': m_action, 'delayed_maintenance': delayed,
            'degradation_flow': dt * DR, 'maintenance_recovery_flow': dt * MR_actual,
            'C_end': C_end,
        })
        C = C_end
    return rows, condition_start


def calculate_dynamic_b6(condition_start, EI0, daily_pkm, CI,
                         lifetime_years=ASSESSMENT_LIFETIME_YEARS, alpha=0.10, g=0.0):
    """Condition-dependent dynamic B6 operational carbon vs static baseline.
    EI_t = EI0*(1+alpha*(1-C_t)); PKM_t = daily_pkm*365*(1+g)^(t-1); CI_t = CI (no renewable)."""
    yearly, b6_dyn, b6_static, ei_sum, pkm_sum = [], 0.0, 0.0, 0.0, 0.0
    for idx, t in enumerate(range(1, int(lifetime_years) + 1)):
        C_t = condition_start[idx]
        EI_t = EI0 * (1.0 + alpha * (1.0 - C_t))
        # (1+g)^(t-1): the first operating year (t=1) is the baseline (no growth yet)
        PKM_t = daily_pkm * 365.0 * ((1.0 + g) ** (t - 1))
        co2_dyn = EI_t * PKM_t * CI / 1000.0
        co2_static = EI0 * PKM_t * CI / 1000.0
        b6_dyn += co2_dyn
        b6_static += co2_static
        ei_sum += EI_t
        pkm_sum += PKM_t
        yearly.append({'year': t, 'C_t': C_t, 'EI_t': EI_t, 'PKM_t': PKM_t, 'B6_co2_tons': co2_dyn})
    n = int(lifetime_years) if lifetime_years else 1
    return {
        'yearly': yearly,
        'b6_dynamic_tons': b6_dyn,
        'b6_static_tons': b6_static,
        'delta_b6_tons': b6_dyn - b6_static,
        'average_EI': ei_sum / n,
        'total_pkm': pkm_sum,
    }


# ═══════════════════════════════════════════════════════════════
# PHASE 3 — MODULAR GROSS A1-C4 LCA (3A: A5 + full-LCA backbone)
# ───────────────────────────────────────────────────────────────
# SYMBOL TABLE (Phase 3)
#   I_A5      construction/installation emissions (tCO2e)
#   I_B2_B5   maintenance/repair/replacement/refurbishment (tCO2e) [Phase 3B]
#   I_C1_C4   end-of-life (tCO2e) [Phase 3C]
#   F_f,p     fuel of type f in stage p (L or kg);  EF_f fuel factor (kgCO2e/unit)
#   E_p       electricity in stage p (kWh);         CI_t grid carbon (kgCO2e/kWh)
#   M_j       mass of material j (kg);              EF_j material factor (kgCO2e/kg)
#   w_j       waste rate (waste / purchased, 0..1)
#   D_x       transport distance (km);              EF_tr transport factor (kgCO2e/ton-km)
#   gross A1-C4 = A1-A3 + A4 + A5 + B2-B5 + B6_active + C1-C4
#   GWP/pkm   uses GROSS (never net). Module D is reported SEPARATELY (supplementary).
# All Phase 3 factors/quantities are user inputs / scenario parameters (not validated).
# ═══════════════════════════════════════════════════════════════

# Map core mass keys -> MATERIAL_FACTORS keys (for reusing A1-A3 carbon factors)
MATERIAL_KEY_MAP = {
    'concrete': 'concrete_32_40', 'steel': 'steel_section', 'aluminum': 'aluminum_general',
    'wood': 'wood_general', 'frp': 'frp_general', 'glass': 'glass_primary',
}


def calculate_a5_construction(masses_kg, params, CI0):
    """A5 construction/installation emissions (tCO2e), reported SEPARATELY from A4.
    BOQ mode prevents double counting of material-production waste:
      - 'installed'  : core masses are installed quantities; extra purchased waste
                       (mass*w/(1-w)) is produced and its A1-A3 production IS added here.
      - 'purchased'  : core masses are purchased quantities; production already in A1-A3,
                       so NO production term is added (only transport + treatment of waste)."""
    if not params.get('include_a5', False):
        return {'included': False, 'a5_total_tons': 0.0, 'a5_fuel_tons': 0.0,
                'a5_electricity_tons': 0.0, 'a5_material_waste_tons': 0.0,
                'a5_waste_transport_tons': 0.0, 'a5_waste_treatment_tons': 0.0,
                'waste_mass_total_kg': 0.0}

    mode = params.get('a5_boq_mode', 'installed')
    w = float(params.get('a5_waste_rate', 0.0))
    truck_ef = TRANSPORT_EMISSION_FACTORS['truck']

    diesel_ef = params.get('a5_diesel_ef', FUEL_FACTORS['diesel']['ef_kgco2e_per_l'])
    diesel_t = params.get('a5_diesel_l', 0.0) * diesel_ef / 1000.0
    elec_t = params.get('a5_elec_kwh', 0.0) * CI0 / 1000.0

    waste_prod_kg = 0.0
    waste_mass_total_kg = 0.0
    for mat, M in masses_kg.items():
        if mode == 'installed':
            waste_mass = M * (w / (1.0 - w)) if 0.0 <= w < 1.0 else 0.0
            # Production of the EXTRA waste is NOT yet in A1-A3 (which used installed mass)
            waste_prod_kg += waste_mass * MATERIAL_FACTORS[MATERIAL_KEY_MAP[mat]]['gwp_kgco2e_per_kg'] * params.get(f'unc_ef_mult_{mat}', 1.0)
        else:  # purchased: production already counted in A1-A3 -> no production term
            waste_mass = M * w
        waste_mass_total_kg += waste_mass

    waste_prod_t = waste_prod_kg / 1000.0
    waste_transport_t = (waste_mass_total_kg / 1000.0) * params.get('a5_waste_transport_km', 0.0) * truck_ef / 1000.0
    waste_treatment_t = waste_mass_total_kg * params.get('a5_waste_treatment_ef', 0.0) / 1000.0

    a5_total = diesel_t + elec_t + waste_prod_t + waste_transport_t + waste_treatment_t
    return {'included': True, 'a5_total_tons': a5_total, 'a5_fuel_tons': diesel_t,
            'a5_electricity_tons': elec_t, 'a5_material_waste_tons': waste_prod_t,
            'a5_waste_transport_tons': waste_transport_t, 'a5_waste_treatment_tons': waste_treatment_t,
            'waste_mass_total_kg': waste_mass_total_kg}


# ═══════════════════════════════════════════════════════════════
# PHASE 3B — B2-B5 USE-STAGE (activity-based) + MASS BALANCE
# ───────────────────────────────────────────────────────────────
# SYMBOL TABLE (Phase 3B)
#   a        activity in {B2 maintenance, B3 repair, B4 replacement, B5 refurb}
#   n_(a,t)  count of activity a in year t
#   M_(j,a)  material j mass per activity (kg);  EF_j material factor
#   F_(f,a)  fuel per activity (L);              EF_f fuel factor
#   E_a      electricity per activity (kWh);     CI_t grid carbon
#   A_(j,t)  material added (replacement/refurb), kg/year
#   R_(j,t)  material removed (replacement/refurb), kg/year
#   M_remaining = M_initial + Σ A - Σ R   (feeds Phase 3C; removed NOT re-counted)
#   B2 schedule may be LINKED to the SD maintenance schedule (m_t) so that SD
#   condition recovery is never "free" — it incurs B2 activity emissions/cost.
# All quantities/factors are user inputs / scenario parameters (not validated).
# ═══════════════════════════════════════════════════════════════

def _parse_year_list(text, T):
    years = set()
    for tok in str(text).replace(';', ',').split(','):
        tok = tok.strip()
        if tok.isdigit():
            y = int(tok)
            if 1 <= y <= T:
                years.add(y)
    return years


def build_b2_b5_activity_schedule(sd_rows, params, lifetime_years=ASSESSMENT_LIFETIME_YEARS):
    """Yearly activity counts. B2 is linked to the SD maintenance schedule when
    'b2_use_sd_schedule' is True (prevents 'free maintenance')."""
    use_sd = params.get('b2_use_sd_schedule', True)
    b2_interval = int(params.get('b2_interval', 5))
    enable_b4 = params.get('enable_b4', False)
    b4_years = _parse_year_list(params.get('b4_years', ''), int(lifetime_years)) if enable_b4 else set()
    rows = []
    for t in range(1, int(lifetime_years) + 1):
        if use_sd and sd_rows:
            b2 = int(sd_rows[t - 1]['maintenance_action'])
            src = 'SD maintenance schedule'
        else:
            b2 = 1 if (b2_interval > 0 and t % b2_interval == 0) else 0
            src = 'fixed interval'
        b4 = 1 if t in b4_years else 0
        rows.append({'year': t, 'B2_count': b2, 'B3_count': 0, 'B4_count': b4, 'B5_count': 0, 'source': src})
    return rows


def calculate_b2_b5_use_stage(schedule, masses_kg, total_embodied_carbon_kg, total_mass_kg,
                              params, CI, diesel_ef, truck_ef):
    """Activity-based B2-B5 emissions (tCO2e) + material added/removed (kg) for mass balance.
    I_(a,t) = n_(a,t)[Σ M_j EF_j + Σ F_f EF_f + E_a CI_t + Σ (M_j/1000) D EF_tr + Σ Rwaste EF_waste]/1000."""
    if not params.get('include_b2b5', False):
        return {'included': False, 'b2_b5_total_tons': 0.0, 'b2_tons': 0.0, 'b3_tons': 0.0,
                'b4_tons': 0.0, 'b5_tons': 0.0, 'yearly': [],
                'material_added_kg': {k: 0.0 for k in masses_kg},
                'material_removed_kg': {k: 0.0 for k in masses_kg}}

    ef_steel = MATERIAL_FACTORS['steel_section']['gwp_kgco2e_per_kg'] * params.get('unc_ef_mult_steel', 1.0)
    ef_concrete = MATERIAL_FACTORS['concrete_32_40']['gwp_kgco2e_per_kg'] * params.get('unc_ef_mult_concrete', 1.0)
    b2_mat_frac = params.get('b2_material_pct', 0.0) / 100.0
    added = {k: 0.0 for k in masses_kg}
    removed = {k: 0.0 for k in masses_kg}
    b2_tons = b4_tons = 0.0
    yearly = []
    for row in schedule:
        t = row['year']
        # B2 routine maintenance (consumables; does not change structural mass balance)
        b2_kg = 0.0
        if row['B2_count']:
            mat = b2_mat_frac * total_embodied_carbon_kg
            dies = params.get('b2_diesel_l', 0.0) * diesel_ef
            ele = params.get('b2_elec_kwh', 0.0) * CI
            trans = (b2_mat_frac * total_mass_kg / 1000.0) * params.get('b2_transport_km', 0.0) * truck_ef
            b2_kg = row['B2_count'] * (mat + dies + ele + trans)
        b2_tons += b2_kg / 1000.0
        # B4 replacement (like-for-like): new material production + removed-material waste
        b4_kg = 0.0
        if row['B4_count']:
            rs = params.get('b4_frac_steel', 0.0) * masses_kg.get('steel', 0.0)
            rc = params.get('b4_frac_concrete', 0.0) * masses_kg.get('concrete', 0.0)
            new_mat = rs * ef_steel + rc * ef_concrete
            waste_treat = (rs + rc) * params.get('b4_waste_ef', 0.0)
            waste_trans = ((rs + rc) / 1000.0) * params.get('b4_transport_km', 0.0) * truck_ef
            b4_kg = row['B4_count'] * (new_mat + waste_treat + waste_trans)
            added['steel'] += row['B4_count'] * rs
            added['concrete'] += row['B4_count'] * rc
            removed['steel'] += row['B4_count'] * rs
            removed['concrete'] += row['B4_count'] * rc
        b4_tons += b4_kg / 1000.0
        yearly.append({'year': t, 'B2_count': row['B2_count'], 'B4_count': row['B4_count'],
                       'B2_tCO2e': b2_kg / 1000.0, 'B4_tCO2e': b4_kg / 1000.0})
    total = b2_tons + b4_tons
    return {'included': True, 'b2_b5_total_tons': total, 'b2_tons': b2_tons, 'b3_tons': 0.0,
            'b4_tons': b4_tons, 'b5_tons': 0.0, 'yearly': yearly,
            'material_added_kg': added, 'material_removed_kg': removed}


def update_material_mass_balance(initial_masses_kg, added_kg, removed_kg):
    """remaining = initial + Σ added - Σ removed. Removed material is handled in B4/B5
    and is NOT re-counted in C1-C4 (Phase 3C uses remaining_masses_for_c1_c4)."""
    remaining = {}
    table = []
    for k, M0 in initial_masses_kg.items():
        a = added_kg.get(k, 0.0)
        r = removed_kg.get(k, 0.0)
        rem = M0 + a - r
        remaining[k] = rem
        table.append({'material': k, 'initial_kg': M0, 'added_B4_B5_kg': a,
                      'removed_B4_B5_kg': r, 'remaining_for_C1_C4_kg': rem})
    return {'mass_balance_by_material': table, 'remaining_masses_for_c1_c4': remaining}


def calculate_lcc_npv_activity_based(construction_cost_m, annual_energy_cost_m, maintenance_mode,
                                     annual_maintenance_m, b2b3b5_costs_by_year, replacement_costs_by_year,
                                     end_of_life_cost_m=0.0, residual_value_m=0.0,
                                     discount_rate_pct=5.0, lifetime_years=ASSESSMENT_LIFETIME_YEARS):
    """LCCA with a maintenance mode that prevents double counting:
      simple_annual : routine cost = annual_maintenance (NO activity routine costs)
      activity_based: routine cost = Σ B2/B3/B5 activity costs (NO annual_maintenance)
    B4 replacement cost is a discrete capital event added in BOTH modes (so B4 LCA
    emissions always have a matching LCCA cost)."""
    r = discount_rate_pct / 100.0
    n = int(lifetime_years)

    def pv(cost, year):
        return cost / ((1 + r) ** year) if r > 0 else cost

    upv = (1 - (1 + r) ** (-n)) / r if r > 0 else n
    pv_energy = annual_energy_cost_m * upv
    if maintenance_mode == 'activity_based':
        pv_routine = sum(pv(c, y) for y, c in (b2b3b5_costs_by_year or {}).items())
    else:
        pv_routine = annual_maintenance_m * upv
    pv_replacement = sum(pv(c, y) for y, c in (replacement_costs_by_year or {}).items())
    pv_eol = pv(end_of_life_cost_m, n)
    pv_residual = pv(residual_value_m, n)
    npv = construction_cost_m + pv_routine + pv_energy + pv_replacement + pv_eol - pv_residual
    return {'npv_lcc_m': npv, 'discount_rate_pct': discount_rate_pct, 'lifetime_years': n,
            'maintenance_mode': maintenance_mode, 'pv_routine_m': pv_routine,
            'pv_replacement_m': pv_replacement}


# ═══════════════════════════════════════════════════════════════
# PHASE 3C — C1-C4 END-OF-LIFE + MODULE-D-FROM-EOL
# ───────────────────────────────────────────────────────────────
# Uses remaining_masses_for_c1_c4 (after B4/B5) — NOT initial masses — so
# material removed during replacement is never re-counted at end of life.
# Per-material treatment shares must satisfy: s_reuse + s_recycle + s_disposal = 1.
# C3 processing is an EMISSION (not a credit); recovery credits go to Module D only.
# Module D is reported SEPARATELY and never enters gross. All factors are scenario inputs.
# ═══════════════════════════════════════════════════════════════
MATERIALS_LIST = list(MATERIAL_KEY_MAP.keys())


def validate_eol_treatment_shares(params, materials=MATERIALS_LIST):
    """Per material: reuse + recycle + disposal = 1 (disposal computed = 1 - reuse - recycle).
    Invalid when reuse+recycle > 1 (disposal would be negative)."""
    errors, table, valid = [], [], True
    for m in materials:
        reuse = params.get(f'eol_reuse_{m}', 0.0)
        recycle = params.get(f'eol_recycle_{m}', 0.0)
        disposal = 1.0 - reuse - recycle
        ok = (reuse >= 0.0 and recycle >= 0.0 and (reuse + recycle) <= 1.0 + 1e-9)
        if not ok:
            valid = False
            errors.append(f"{m}: reuse+recycle = {reuse + recycle:.3f} > 1 (disposal would be negative)")
        table.append({'material': m, 'reuse': reuse, 'recycle': recycle,
                      'disposal': max(disposal, 0.0), 'sum': reuse + recycle + max(disposal, 0.0)})
    return {'valid': valid, 'errors': errors, 'share_table': table}


def calculate_c1_c4_end_of_life(remaining_masses, params, CI_T, diesel_ef, truck_ef, materials=MATERIALS_LIST):
    """C1 deconstruction + C2 transport + C3 processing + C4 disposal (tCO2e)."""
    if not params.get('include_c1c4', False):
        return {'included': False, 'c1_tons': 0.0, 'c2_tons': 0.0, 'c3_tons': 0.0,
                'c4_tons': 0.0, 'c1_c4_total_tons': 0.0, 'eol_by_material': []}
    c1 = (params.get('c1_diesel_l', 0.0) * diesel_ef + params.get('c1_elec_kwh', 0.0) * CI_T) / 1000.0
    km = params.get('eol_transport_km', 50.0)
    reuse_ef = params.get('eol_reuse_ef', 0.0)
    recycle_ef = params.get('eol_recycle_ef', 0.0)
    disposal_ef = params.get('eol_disposal_ef', 0.0)
    c2 = c3 = c4 = 0.0
    rows = []
    for m in materials:
        M = remaining_masses.get(m, 0.0)
        reuse = params.get(f'eol_reuse_{m}', 0.0)
        recycle = params.get(f'eol_recycle_{m}', 0.0)
        disposal = max(1.0 - reuse - recycle, 0.0)
        c2_m = (M / 1000.0) * km * truck_ef / 1000.0
        c3_m = M * (reuse * reuse_ef + recycle * recycle_ef) / 1000.0
        c4_m = M * disposal * disposal_ef / 1000.0
        c2 += c2_m; c3 += c3_m; c4 += c4_m
        rows.append({'material': m, 'remaining_kg': M, 'reuse': reuse, 'recycle': recycle,
                     'disposal': disposal, 'C2_tCO2e': c2_m, 'C3_tCO2e': c3_m, 'C4_tCO2e': c4_m})
    return {'included': True, 'c1_tons': c1, 'c2_tons': c2, 'c3_tons': c3, 'c4_tons': c4,
            'c1_c4_total_tons': c1 + c2 + c3 + c4, 'eol_by_material': rows}


def calculate_module_d_from_eol(remaining_masses, params, materials=MATERIALS_LIST):
    """Module D credit from recovered EOL material: Σ M_recovered·η·(EF_virgin − EF_secondary)/1000.
    If a recovered material has no secondary EF supplied (<=0), its credit is skipped and the
    quality flag is set False (the reported net would otherwise be overstated)."""
    if not params.get('include_c1c4', False):
        return {'module_d_tons': 0.0, 'module_d_by_material': [], 'module_d_quality_ok': True}
    eta = params.get('eol_recovery_eta', 1.0)
    total, rows, quality_ok = 0.0, [], True
    for m in materials:
        M = remaining_masses.get(m, 0.0)
        reuse = params.get(f'eol_reuse_{m}', 0.0)
        recycle = params.get(f'eol_recycle_{m}', 0.0)
        recovered = M * (reuse + recycle)
        ef_virgin = MATERIAL_FACTORS[MATERIAL_KEY_MAP[m]]['gwp_kgco2e_per_kg'] * params.get(f'unc_ef_mult_{m}', 1.0)
        ef_secondary = params.get(f'eol_secondary_ef_{m}', 0.0)
        if recovered > 0 and ef_secondary <= 0.0:
            quality_ok = False
            rows.append({'material': m, 'recovered_kg': recovered, 'module_d_tons': 0.0,
                         'note': 'secondary EF missing → skipped'})
            continue
        credit = recovered * eta * (ef_virgin - ef_secondary) / 1000.0
        total += credit
        rows.append({'material': m, 'recovered_kg': recovered, 'module_d_tons': credit, 'note': ''})
    return {'module_d_tons': total, 'module_d_by_material': rows, 'module_d_quality_ok': quality_ok}


def update_lca_summary_full(I_A1_A3, I_A4, I_A5, I_B2_B5, I_B6_active, I_C1_C4,
                            module_d_tons, total_pkm, b6_mode, b2b5_included=False,
                            c1c4_included=False):
    """Combine modules into a GROSS A1-C4 result. Module D stays separate.
    Functional unit (GWP/pkm) uses GROSS, never net."""
    i_a5_val = I_A5['a5_total_tons'] if isinstance(I_A5, dict) else I_A5
    a5_included = (isinstance(I_A5, dict) and I_A5.get('included'))
    gross = I_A1_A3 + I_A4 + i_a5_val + I_B2_B5 + I_B6_active + I_C1_C4
    net = gross - module_d_tons
    gwp_pkm_gross = (gross * 1000.0 / total_pkm) if total_pkm > 0 else np.nan
    stages = [
        ('A1-A3 materials', I_A1_A3, 'included'),
        ('A4 transport', I_A4, 'included' if I_A4 > 0 else 'not included'),
        ('A5 construction', i_a5_val, 'included' if a5_included else 'not included'),
        ('B2-B5 use stage', I_B2_B5, 'included — activity-based scenario' if b2b5_included else 'not included'),
        (f'B6 operation ({b6_mode})', I_B6_active, 'included'),
        ('C1-C4 end-of-life', I_C1_C4, 'included — EOL scenario' if c1c4_included else 'not included'),
    ]
    contribution = []
    for name, val, status in stages:
        contribution.append({'Stage': name, 'tCO2e': val,
                             '% of gross': (val / gross * 100.0) if gross else 0.0,
                             'status': status})
    return {
        'gross_a1_c4_tons': gross,
        'module_d_tons': module_d_tons,
        'net_with_module_d_tons': net,
        'gwp_pkm_gross': gwp_pkm_gross,
        'i_a5_tons': i_a5_val,
        'stage_contribution': contribution,
    }


def calculate_core_lca_lcc(params):
    """SCIENTIFIC CORE — modular gross A1-C4 LCA (A1-A3 + A4 + A5 + B6; B2-B5/C1-C4
    in later sub-phases) + NPV-LCCA. ONLY publication-grade quantities."""
    # Material masses (unit harmonisation)
    concrete_m3 = params['concrete'] * 1000
    concrete_kg = concrete_m3 * DENSITIES['concrete']
    steel_tons = params['steel'] * 1000
    steel_kg = steel_tons * 1000
    aluminum_tons = params['aluminum'] * 1000
    aluminum_kg = aluminum_tons * 1000
    wood_m3 = params['wood'] * 1000
    wood_kg = wood_m3 * DENSITIES['wood']
    frp_tons = params['frp'] * 1000
    frp_kg = frp_tons * 1000
    glass_m2 = params['glass'] * 1000
    # Glass mass via geometry, NOT a flat areal density:
    #   mass [kg] = area [m2] x thickness [mm] x 2.5 [kg per mm per m2]
    #   (2500 kg/m3 flat-glass density / 1000 mm/m)  — per unit-harmonisation table.
    glass_thickness_mm = params.get('glass_thickness_mm', 12.0)
    glass_kg = glass_m2 * glass_thickness_mm * 2.5

    material_masses_kg = {"concrete": concrete_kg, "steel": steel_kg, "aluminum": aluminum_kg, "wood": wood_kg, "frp": frp_kg, "glass": glass_kg}
    a4_transport_co2_tons = calculate_a4_transport_co2(material_masses_kg, params.get("transport_distance_km", 0.0), params.get("transport_mode", "truck"))

    # Operational Energy & Carbon (B6)
    energy_per_pax_km = params['energy_per_pax']
    daily_pax_km = params['daily_pax_km'] * 1000
    carbon_intensity = params['carbon_intensity']
    renewable_share = params['renewable_share']  # dashboard-only in Phase 1b (see note)

    annual_operational_energy = energy_per_pax_km * daily_pax_km * 365

    # Phase 1b SAFE CHOICE — avoid double-counting renewable penetration.
    # The user-supplied grid carbon intensity ALREADY reflects the grid mix, so we
    # do NOT additionally multiply by (1 - renewable_share). Renewable share is kept
    # as a dashboard-only input here and is deferred to Phase 2, where it will be
    # defined explicitly as additional project renewable procurement (not grid mix).
    effective_carbon_intensity = carbon_intensity
    operational_carbon_intensity = energy_per_pax_km * effective_carbon_intensity
    annual_co2_operational = operational_carbon_intensity * daily_pax_km * 365 / 1000

    steel_recycle_rate = params['steel_recycle'] / 100.0
    recycling_scenario = params.get("recycling_scenario", "none")
    recycling_factors = RECYCLING_CREDIT_SCENARIOS[recycling_scenario]
    aluminum_recycle_rate = params['aluminum_recycle'] / 100.0

    # Embodied Energy (A1-A3, GROSS — legacy energy factors, secondary indicator)
    ee_concrete = concrete_kg * MATERIAL_FACTORS['concrete_32_40']['ee_mj_per_kg']
    ee_steel = steel_kg * MATERIAL_FACTORS['steel_section']['ee_mj_per_kg']
    ee_aluminum = aluminum_kg * MATERIAL_FACTORS['aluminum_general']['ee_mj_per_kg']
    ee_wood = wood_kg * MATERIAL_FACTORS['wood_general']['ee_mj_per_kg']
    ee_frp = frp_kg * MATERIAL_FACTORS['frp_general']['ee_mj_per_kg']
    ee_glass = glass_kg * MATERIAL_FACTORS['glass_primary']['ee_mj_per_kg']

    # A1-A3 GROSS embodied energy (no end-of-life credit netted in)
    total_ee = (ee_concrete + ee_steel + ee_aluminum +
                ee_wood + ee_frp + ee_glass)

    # Embodied Carbon (A1-A3, GROSS — ICE V4.1 carbon factors, primary indicator)
    # unc_ef_mult_<m> (default 1.0) lets Phase 4 propagate per-material EF uncertainty
    # consistently across A1-A3, A5, B2-B5 and Module D.
    ef_mult = {m: params.get(f'unc_ef_mult_{m}', 1.0)
               for m in ('concrete', 'steel', 'aluminum', 'wood', 'frp', 'glass')}
    carbon_concrete = concrete_kg * MATERIAL_FACTORS['concrete_32_40']['gwp_kgco2e_per_kg'] * ef_mult['concrete']
    carbon_steel = steel_kg * MATERIAL_FACTORS['steel_section']['gwp_kgco2e_per_kg'] * ef_mult['steel']
    carbon_aluminum = aluminum_kg * MATERIAL_FACTORS['aluminum_general']['gwp_kgco2e_per_kg'] * ef_mult['aluminum']
    carbon_wood = wood_kg * MATERIAL_FACTORS['wood_general']['gwp_kgco2e_per_kg'] * ef_mult['wood']
    carbon_frp = frp_kg * MATERIAL_FACTORS['frp_general']['gwp_kgco2e_per_kg'] * ef_mult['frp']
    carbon_glass = glass_kg * MATERIAL_FACTORS['glass_primary']['gwp_kgco2e_per_kg'] * ef_mult['glass']

    # A1-A3 GROSS embodied carbon (kg) — Module D credit is reported SEPARATELY below
    total_carbon_raw = (carbon_concrete + carbon_steel + carbon_aluminum +
                        carbon_wood + carbon_frp + carbon_glass)

    total_embodied_co2 = total_carbon_raw / 1000  # tons CO2e, A1-A3 gross (incl. any FRP placeholder)

    # FRP is unverified (no ICE V4.1 A1-A3 factor). A publication-grade result
    # must either have FRP = 0 or a supplied product-specific EPD.
    frp_epd_verified = bool(params.get('frp_epd_verified', False))
    publication_grade = (params['frp'] == 0) or frp_epd_verified
    # Core LCA EXCLUDING the unverified FRP placeholder (the defensible figure):
    total_embodied_co2_excl_frp = (total_carbon_raw - carbon_frp) / 1000

    # ── Module D (EN 15804): end-of-life recycling credits, reported SEPARATELY ──
    # These are an informational module and are NOT subtracted from A1-A3 and
    # NOT added into the A1-C4 lifecycle total.
    module_d_energy_credit_mj = (
        ee_steel * (params['steel_recycle'] / 100) * recycling_factors['steel']['energy_credit_fraction']
        + ee_aluminum * (params['aluminum_recycle'] / 100) * recycling_factors['aluminum']['energy_credit_fraction']
    )
    module_d_carbon_credit_tons = (
        carbon_steel * (params['steel_recycle'] / 100) * recycling_factors['steel']['carbon_credit_fraction']
        + carbon_aluminum * (params['aluminum_recycle'] / 100) * recycling_factors['aluminum']['carbon_credit_fraction']
    ) / 1000

    lca_results = calculate_lca_summary(
        embodied_co2_tons=total_embodied_co2,
        annual_operational_co2_tons=annual_co2_operational,
        embodied_energy_mj=total_ee,
        annual_operational_energy_kwh=annual_operational_energy,
        daily_pax_km=daily_pax_km,
        lifetime_years=ASSESSMENT_LIFETIME_YEARS,
        a4_transport_co2_tons=a4_transport_co2_tons,
        module_d_carbon_credit_tons=module_d_carbon_credit_tons,
        module_d_energy_credit_mj=module_d_energy_credit_mj
    )
    total_co2 = lca_results["total_lifecycle_co2_tons"]

    # ── PHASE 2: System Dynamics layer for B6 (asset condition -> energy) ──
    # Always simulated (cheap); 'sd_enable' controls whether it is the active
    # headline result. Renewable share is NOT used here (CI_t = grid only).
    sd_enabled = bool(params.get('sd_enable', False))
    sd_C0 = params.get('sd_C0', 1.0)
    sd_delta = params.get('sd_delta', 0.005)
    sd_interval = int(params.get('sd_maint_interval', 5))
    sd_rho = params.get('sd_rho', 0.05)
    sd_tau = int(params.get('sd_tau', 1))
    sd_alpha = params.get('sd_alpha', 0.10)
    sd_g = params.get('sd_growth_pct', 0.0) / 100.0

    sd_rows, sd_condition_start = simulate_asset_condition(
        C0=sd_C0, delta=sd_delta, maintenance_interval=sd_interval,
        rho=sd_rho, tau=sd_tau, lifetime_years=ASSESSMENT_LIFETIME_YEARS)
    b6 = calculate_dynamic_b6(
        sd_condition_start, EI0=energy_per_pax_km, daily_pkm=daily_pax_km,
        CI=effective_carbon_intensity, lifetime_years=ASSESSMENT_LIFETIME_YEARS,
        alpha=sd_alpha, g=sd_g)
    sd_final_condition = sd_rows[-1]['C_end'] if sd_rows else sd_C0
    sd_min_condition = min([r['C_end'] for r in sd_rows] + [sd_C0]) if sd_rows else sd_C0
    total_lifecycle_co2_dynamic = total_embodied_co2 + a4_transport_co2_tons + b6['b6_dynamic_tons']
    co2_kg_per_pkm_dynamic = (total_lifecycle_co2_dynamic * 1000 / b6['total_pkm']) if b6['total_pkm'] > 0 else np.nan

    # ── ACTIVE result selector — every headline card/report/export uses active_* ──
    # When SD is OFF the headline equals the Phase 1b static result (g not applied).
    # When SD is ON the headline switches to the dynamic, condition-dependent result.
    if sd_enabled:
        active_b6_mode = "dynamic"
        active_b6_tons = b6['b6_dynamic_tons']
        active_total_pkm = b6['total_pkm']
        active_total_lifecycle_co2_tons = total_lifecycle_co2_dynamic
    else:
        active_b6_mode = "static"
        active_b6_tons = lca_results['lifetime_operational_co2_tons']
        active_total_pkm = lca_results['lifetime_pax_km']
        active_total_lifecycle_co2_tons = lca_results['total_lifecycle_co2_tons']
    active_co2_kg_per_pkm = (active_total_lifecycle_co2_tons * 1000 / active_total_pkm) if active_total_pkm > 0 else np.nan

    # ── PHASE 3A: A5 construction ──
    a5 = calculate_a5_construction(material_masses_kg, params, effective_carbon_intensity)

    # ── PHASE 3B: B2-B5 activity-based use stage + mass balance ──
    b2b5_schedule = build_b2_b5_activity_schedule(sd_rows, params, ASSESSMENT_LIFETIME_YEARS)
    diesel_ef_val = params.get('a5_diesel_ef', FUEL_FACTORS['diesel']['ef_kgco2e_per_l'])
    b2b5 = calculate_b2_b5_use_stage(
        b2b5_schedule, material_masses_kg, total_carbon_raw, sum(material_masses_kg.values()),
        params, effective_carbon_intensity, diesel_ef_val, TRANSPORT_EMISSION_FACTORS['truck'])
    mass_balance = update_material_mass_balance(
        material_masses_kg, b2b5['material_added_kg'], b2b5['material_removed_kg'])
    I_B2_B5 = b2b5['b2_b5_total_tons']
    remaining_masses = mass_balance['remaining_masses_for_c1_c4']

    # ── PHASE 3C: C1-C4 end-of-life + Module-D-from-EOL ──
    include_c1c4 = params.get('include_c1c4', False)
    eol_validation = validate_eol_treatment_shares(params, MATERIALS_LIST)
    shares_ok = (not include_c1c4) or eol_validation['valid']
    truck_ef = TRANSPORT_EMISSION_FACTORS['truck']
    if include_c1c4 and eol_validation['valid']:
        c1c4 = calculate_c1_c4_end_of_life(
            remaining_masses, params, effective_carbon_intensity, diesel_ef_val, truck_ef, MATERIALS_LIST)
        md_eol = calculate_module_d_from_eol(remaining_masses, params, MATERIALS_LIST)
        I_C1_C4 = c1c4['c1_c4_total_tons']
        module_d_used_tons = md_eol['module_d_tons']
        module_d_ok = md_eol['module_d_quality_ok']
    else:
        c1c4 = {'included': False, 'c1_tons': 0.0, 'c2_tons': 0.0, 'c3_tons': 0.0,
                'c4_tons': 0.0, 'c1_c4_total_tons': 0.0, 'eol_by_material': []}
        md_eol = {'module_d_tons': module_d_carbon_credit_tons, 'module_d_by_material': [],
                  'module_d_quality_ok': True}
        I_C1_C4 = 0.0
        module_d_used_tons = module_d_carbon_credit_tons   # legacy slider-based when C1-C4 off
        module_d_ok = True

    full_lca = update_lca_summary_full(
        I_A1_A3=total_embodied_co2, I_A4=a4_transport_co2_tons, I_A5=a5,
        I_B2_B5=I_B2_B5, I_B6_active=active_b6_tons, I_C1_C4=I_C1_C4,
        module_d_tons=module_d_used_tons, total_pkm=active_total_pkm,
        b6_mode=active_b6_mode, b2b5_included=b2b5['included'], c1c4_included=c1c4['included'])
    # publication_grade_full_lca: False if FRP lacks EPD, shares don't sum to 1, or
    # Module D is reported with a missing secondary factor.
    publication_grade_full_lca = bool(publication_grade and shares_ok and module_d_ok)

    # Economic (LCCA)
    construction_cost = params['construction_cost']
    annual_maintenance = params['maintenance_cost']
    jobs_created = params['jobs_created']
    economic_multiplier = params['economic_multiplier']
    total_jobs = jobs_created * economic_multiplier
    total_maintenance_cost = annual_maintenance * ASSESSMENT_LIFETIME_YEARS

    # LCCA — when B2-B5 is active, use the mode-aware activity LCCA (prevents
    # double counting); B4 replacement cost is a discrete capital event in BOTH modes.
    lcca_maint_mode = params.get('lcca_maint_mode', 'simple_annual')
    b4_cost_per_event = params.get('b4_cost_per_event_m', 0.0)
    b2_cost_per_event = params.get('b2_cost_per_event_m', 0.0)
    replacement_costs_by_year = {row['year']: b4_cost_per_event
                                 for row in b2b5_schedule if row['B4_count'] and b4_cost_per_event}
    b2b3b5_costs_by_year = {row['year']: row['B2_count'] * b2_cost_per_event
                            for row in b2b5_schedule if row['B2_count'] and b2_cost_per_event}
    # EOL cost enters the LCCA exactly once (only when C1-C4 is included).
    eol_cost_m = params.get('eol_cost_m', 0.0) if include_c1c4 else 0.0
    if b2b5['included']:
        lcc_results = calculate_lcc_npv_activity_based(
            construction_cost_m=construction_cost,
            annual_energy_cost_m=params.get("annual_energy_cost", 0.0),
            maintenance_mode=lcca_maint_mode,
            annual_maintenance_m=annual_maintenance,
            b2b3b5_costs_by_year=b2b3b5_costs_by_year,
            replacement_costs_by_year=replacement_costs_by_year,
            end_of_life_cost_m=eol_cost_m,
            residual_value_m=params.get("residual_value", 0.0),
            discount_rate_pct=params.get("discount_rate", 5.0),
            lifetime_years=ASSESSMENT_LIFETIME_YEARS)
    else:
        lcc_results = calculate_lcc_npv(
            construction_cost_m=construction_cost,
            annual_maintenance_m=annual_maintenance,
            annual_energy_cost_m=params.get("annual_energy_cost", 0.0),
            end_of_life_cost_m=eol_cost_m,
            residual_value_m=params.get("residual_value", 0.0),
            discount_rate_pct=params.get("discount_rate", 5.0),
            lifetime_years=ASSESSMENT_LIFETIME_YEARS)

    return {
        'total_co2': total_co2,
        'annual_co2_operational': annual_co2_operational,
        'total_embodied_co2': total_embodied_co2,
        'total_embodied_co2_excl_frp': total_embodied_co2_excl_frp,
        'publication_grade': publication_grade,
        'module_d_carbon_credit_tons': module_d_carbon_credit_tons,
        'module_d_energy_credit_mj': module_d_energy_credit_mj,
        'effective_carbon_intensity': effective_carbon_intensity,
        'total_ee': total_ee,
        'annual_operational_energy': annual_operational_energy,
        'total_jobs': total_jobs,
        'total_maintenance_cost': total_maintenance_cost,
        'concrete_volume': concrete_m3,
        'steel_mass': steel_kg,
        'aluminum_mass': aluminum_kg,
        'steel_tons': steel_tons,
        'aluminum_tons': aluminum_tons,
        'frp_tons': frp_tons,
        'energy_per_pax_km': energy_per_pax_km,
        'operational_carbon_intensity': operational_carbon_intensity,
        'daily_pax_km': daily_pax_km,
        'construction_cost': construction_cost,
        'annual_maintenance': annual_maintenance,
        'jobs_created': jobs_created,
        'economic_multiplier': economic_multiplier,
        'steel_recycle_rate': steel_recycle_rate * 100,
        'aluminum_recycle_rate': aluminum_recycle_rate * 100,
        'renewable_share': renewable_share,
        'noise_reduction': params['noise_reduction'],
        'land_use_efficiency': params['land_use'],
        'lca_results': lca_results,
        'total_lifecycle_co2': lca_results['total_lifecycle_co2_tons'],
        'co2_kg_per_pkm': lca_results['co2_kg_per_pkm'],
        'lcc_results': lcc_results,
        'npv_lcc_m': lcc_results['npv_lcc_m'],
        'total_cost': lcc_results['npv_lcc_m'] * 1e6,
        'carbon_intensity': carbon_intensity,
        'ee_concrete': ee_concrete, 'ee_steel': ee_steel, 'ee_aluminum': ee_aluminum,
        'ee_wood': ee_wood, 'ee_frp': ee_frp, 'ee_glass': ee_glass,
        'carbon_concrete': carbon_concrete, 'carbon_steel': carbon_steel,
        'carbon_aluminum': carbon_aluminum, 'carbon_wood': carbon_wood,
        'carbon_frp': carbon_frp, 'carbon_glass': carbon_glass,
        # ── Phase 2 System Dynamics (B6) ──
        'sd_enabled': sd_enabled,
        'sd_rows': sd_rows,
        'sd_b6': b6,
        'b6_static_tons': b6['b6_static_tons'],
        'b6_dynamic_tons': b6['b6_dynamic_tons'],
        'delta_b6_tons': b6['delta_b6_tons'],
        'sd_average_EI': b6['average_EI'],
        'sd_min_condition': sd_min_condition,
        'sd_final_condition': sd_final_condition,
        'total_lifecycle_co2_dynamic': total_lifecycle_co2_dynamic,
        'co2_kg_per_pkm_dynamic': co2_kg_per_pkm_dynamic,
        'sd_params': {'C0': sd_C0, 'delta': sd_delta, 'interval': sd_interval,
                      'rho': sd_rho, 'tau': sd_tau, 'alpha': sd_alpha, 'g_pct': sd_g * 100},
        # ── ACTIVE result (static or dynamic depending on sd_enable) ──
        'active_b6_mode': active_b6_mode,
        'active_b6_tons': active_b6_tons,
        'active_total_pkm': active_total_pkm,
        'active_total_lifecycle_co2_tons': active_total_lifecycle_co2_tons,
        'active_co2_kg_per_pkm': active_co2_kg_per_pkm,
        # ── PHASE 3A: A5 + gross A1-C4 backbone ──
        'a5': a5,
        # ── PHASE 3B: B2-B5 use stage + mass balance ──
        'b2b5': b2b5,
        'i_b2b5_tons': I_B2_B5,
        'b2b5_schedule': b2b5_schedule,
        'mass_balance': mass_balance,
        'lcca_maint_mode': lcca_maint_mode,
        # ── PHASE 3C: C1-C4 end-of-life + Module-D-from-EOL ──
        'c1c4': c1c4,
        'i_c1c4_tons': I_C1_C4,
        'eol_validation': eol_validation,
        'module_d_eol': md_eol,
        'module_d_quality_ok': module_d_ok,
        'gross_a1_c4_tons': full_lca['gross_a1_c4_tons'],
        'gwp_pkm_gross': full_lca['gwp_pkm_gross'],
        'net_with_module_d_tons': full_lca['net_with_module_d_tons'],
        'module_d_tons': full_lca['module_d_tons'],
        'stage_contribution': full_lca['stage_contribution'],
        'publication_grade_full_lca': publication_grade_full_lca,
    }


def calculate_dashboard_display_scores(params, core):
    """DASHBOARD-ONLY — heuristic display scores and interaction visualization.
    NOT an ISO LCA/LCCA result and NOT a sustainability index. Do not publish
    these as scientific outputs; they exist purely for the interface."""
    # Heuristic material intensity scores (reference-based, not an LCA metric)
    material_data = {
        'concrete_intensity': calculate_intensity_score(core['concrete_volume'], REF_CONCRETE),
        'steel_intensity': calculate_intensity_score(core['steel_tons'], REF_STEEL),
        'aluminum_intensity': calculate_intensity_score(core['aluminum_tons'], REF_ALUMINUM),
        'wood_intensity': calculate_intensity_score(params['wood'] * 1000, REF_WOOD),
        'frp_intensity': calculate_intensity_score(core['frp_tons'], REF_FRP),
        'glass_intensity': calculate_intensity_score(params['glass'] * 1000, REF_GLASS),
        'steel_recycle_rate': params['steel_recycle'],
        'aluminum_recycle_rate': params['aluminum_recycle']
    }
    environmental_data = {
        'operational_co2': core['annual_co2_operational'],
        'embodied_co2': core['total_embodied_co2'],
        'renewable_share': core['renewable_share'],
        'noise_reduction': core['noise_reduction'],
        'land_efficiency': core['land_use_efficiency']
    }
    operational_data = {
        'time_savings': params['time_savings'] * 1000,
        'availability': params['availability'],
        'land_efficiency': core['land_use_efficiency'],
        'energy_per_pax_km': core['energy_per_pax_km']
    }
    economic_data = {
        'construction_cost': core['construction_cost'],
        'npv_lcc_m': core['npv_lcc_m'],
        'jobs_created': core['jobs_created'],
        'economic_multiplier': core['economic_multiplier']
    }

    material_score = calculate_material_score_integrated(material_data)
    environmental_score = calculate_environmental_display_score(environmental_data)
    operational_score = calculate_operational_score_integrated(operational_data)
    economic_score = calculate_economic_score_integrated(economic_data)

    interaction_results = calculate_cross_category_interactions(
        material_score, environmental_score, operational_score, economic_score
    )

    dashboard_display_score = float(np.clip(
        material_score * 0.25 + environmental_score * 0.30 +
        operational_score * 0.25 + economic_score * 0.20, 0, 100))

    return {
        'material_score': material_score,
        'environmental_score': environmental_score,
        'operational_score': operational_score,
        'economic_score': economic_score,
        'adjusted_material_score': interaction_results['adjusted_material_score'],
        'adjusted_environmental_score': interaction_results['adjusted_environmental_score'],
        'adjusted_operational_score': interaction_results['adjusted_operational_score'],
        'adjusted_economic_score': interaction_results['adjusted_economic_score'],
        'interaction_effects': interaction_results['interaction_effects'],
        'total_synergy': interaction_results['total_synergy'],
        'total_tradeoff': interaction_results['total_tradeoff'],
        'synergy_ratio': interaction_results['synergy_ratio'],
        'dashboard_display_score': dashboard_display_score,
    }


def run_full_assessment(params):
    """Orchestrator: SCIENTIFIC CORE + DASHBOARD-ONLY, kept logically separate.
    Returns a merged dict for backward-compatible UI consumption."""
    core = calculate_core_lca_lcc(params)
    dashboard = calculate_dashboard_display_scores(params, core)
    return {**core, **dashboard}


# ═══════════════════════════════════════════════════════════════
# PHASE 4 — COMPONENT-BASED MONTE CARLO UNCERTAINTY PROPAGATION
# ───────────────────────────────────────────────────────────────
# A statistical layer ON TOP of the A1-C4 model. It does NOT change any LCA
# equation. Each uncertain input is sampled from its own distribution and the
# full model is re-run, so uncertainty propagates per component while the model
# identities hold in EVERY draw:
#   gross = A1-A3 + A4 + A5 + B2-B5 + B6 + C1-C4
#   net   = gross - Module D            (Module D never enters gross)
#   GWP/pkm = gross * 1000 / PKM        (uses GROSS, never net)
# NO total-scaling. NO SI / CRITIC-Entropy. Treatment shares are sampled jointly
# (Dirichlet) so reuse+recycle+disposal = 1 in every draw.
# ═══════════════════════════════════════════════════════════════

def _norm_ppf(p):
    """Inverse standard-normal CDF (Acklam), numpy-only, vectorised."""
    p = np.asarray(p, dtype=float)
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    p = np.clip(p, 1e-12, 1 - 1e-12)
    x = np.zeros_like(p)
    lo = p < plow; hi = p > phigh; mid = (~lo) & (~hi)
    if np.any(lo):
        q = np.sqrt(-2 * np.log(p[lo]))
        x[lo] = (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if np.any(hi):
        q = np.sqrt(-2 * np.log(1 - p[hi]))
        x[hi] = -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if np.any(mid):
        q = p[mid] - 0.5; r = q * q
        x[mid] = (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5]) * q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)
    return x


def lhs_unit_samples(n, k, seed=42):
    """Latin Hypercube unit samples in [0,1]^(n x k)."""
    rng = np.random.default_rng(seed)
    u = np.zeros((n, k))
    for j in range(k):
        u[:, j] = (rng.permutation(n) + rng.random(n)) / n
    return u


def sample_from_distribution(u, spec):
    """Transform uniform u -> distribution. Positive quantities are clipped >= 0."""
    base = spec['base_value']; cv = spec.get('cv', 0.0); dist = spec['distribution']
    lo = spec.get('min', None); hi = spec.get('max', None)
    if dist == 'fixed' or cv <= 0 or base == 0:
        x = np.full_like(np.asarray(u, dtype=float), base)
    elif dist == 'lognormal':
        sigma = np.sqrt(np.log(1 + cv * cv)); mu = np.log(abs(base)) - 0.5 * sigma * sigma
        x = np.sign(base) * np.exp(mu + sigma * _norm_ppf(u))
    elif dist == 'normal':
        x = base + (cv * base) * _norm_ppf(u)
    elif dist == 'triangular':
        spread = min(2.0 * cv, 0.95)
        a = base * (1 - spread); cc = base; bb = base * (1 + spread)
        u = np.asarray(u, dtype=float); x = np.empty_like(u)
        fc = (cc - a) / (bb - a) if bb > a else 0.0
        left = u <= fc
        x[left] = a + np.sqrt(u[left] * (bb - a) * (cc - a))
        x[~left] = bb - np.sqrt((1 - u[~left]) * (bb - a) * (bb - cc))
    else:
        x = np.full_like(np.asarray(u, dtype=float), base)
    if lo is not None and np.isfinite(lo):
        x = np.maximum(x, lo)
    if hi is not None and np.isfinite(hi):
        x = np.minimum(x, hi)
    return x


def build_uncertainty_registry(params, results):
    """One row per uncertain input. Stage tags, distributions, CVs, bounds, quality."""
    reg = []
    def add(parameter, stage, base, dist, cv, mn, mx, unit, quality, active=True, group=None):
        reg.append({'parameter': parameter, 'stage': stage, 'base_value': base,
                    'distribution': dist, 'cv': cv, 'min': mn, 'max': mx, 'unit': unit,
                    'source_quality': quality, 'active_when': bool(active), 'correlation_group': group})
    mats = ['concrete', 'steel', 'aluminum', 'wood', 'frp', 'glass']
    ef_cv = {'concrete': 0.10, 'steel': 0.08, 'aluminum': 0.12, 'wood': 0.15, 'frp': 0.30, 'glass': 0.12}
    for m in mats:
        add(f'unc_ef_mult_{m}', 'A1-A3', 1.0, 'lognormal', ef_cv[m], 0.0, None, 'multiplier', 'ICE/EPD', True, 'material_EF')
        add(m, 'A1-A3', params.get(m, 0.0), 'normal', 0.05, 0.0, None, 'BOQ unit', 'project/BOQ', True, 'material_qty')
    add('carbon_intensity', 'B6/electricity', params.get('carbon_intensity', 0.5), 'lognormal', 0.12, 0.0, None, 'kgCO2e/kWh', 'database', True, 'grid')
    add('energy_per_pax', 'B6', params.get('energy_per_pax', 0.15), 'lognormal', 0.15, 0.0, None, 'kWh/pkm', 'scenario', True, 'B6')
    add('transport_distance_km', 'A4', params.get('transport_distance_km', 0.0), 'triangular', 0.20, 0.0, None, 'km', 'scenario', True, 'A4')
    a5_on = bool(params.get('include_a5', False))
    add('a5_diesel_l', 'A5', params.get('a5_diesel_l', 0.0), 'lognormal', 0.20, 0.0, None, 'L', 'scenario', a5_on, 'A5')
    add('a5_elec_kwh', 'A5', params.get('a5_elec_kwh', 0.0), 'lognormal', 0.20, 0.0, None, 'kWh', 'scenario', a5_on, 'A5')
    add('a5_diesel_ef', 'A5', params.get('a5_diesel_ef', FUEL_FACTORS['diesel']['ef_kgco2e_per_l']), 'lognormal', 0.08, 0.0, None, 'kgCO2e/L', 'database', a5_on, 'fuel')
    b_on = bool(params.get('include_b2b5', False))
    add('b2_material_pct', 'B2-B5', params.get('b2_material_pct', 0.0), 'triangular', 0.25, 0.0, None, '% A1-A3', 'scenario', b_on, 'B2B5')
    add('b4_frac_steel', 'B2-B5', params.get('b4_frac_steel', 0.0), 'triangular', 0.25, 0.0, 1.0, 'fraction', 'scenario', b_on, 'B2B5')
    add('b4_frac_concrete', 'B2-B5', params.get('b4_frac_concrete', 0.0), 'triangular', 0.25, 0.0, 1.0, 'fraction', 'scenario', b_on, 'B2B5')
    c_on = bool(params.get('include_c1c4', False))
    add('c1_diesel_l', 'C1-C4', params.get('c1_diesel_l', 0.0), 'lognormal', 0.20, 0.0, None, 'L', 'scenario', c_on, 'C1C4')
    add('eol_transport_km', 'C1-C4', params.get('eol_transport_km', 50.0), 'triangular', 0.20, 0.0, None, 'km', 'scenario', c_on, 'C1C4')
    add('eol_recycle_ef', 'C1-C4', params.get('eol_recycle_ef', 0.0), 'lognormal', 0.20, 0.0, None, 'kgCO2e/kg', 'scenario', c_on, 'C1C4')
    add('eol_disposal_ef', 'C1-C4', params.get('eol_disposal_ef', 0.0), 'lognormal', 0.20, 0.0, None, 'kgCO2e/kg', 'scenario', c_on, 'C1C4')
    add('eol_recovery_eta', 'Module D', params.get('eol_recovery_eta', 1.0), 'triangular', 0.10, 0.0, 1.0, 'fraction', 'scenario', c_on, 'moduleD')
    add('construction_cost', 'LCCA', params.get('construction_cost', 0.0), 'lognormal', 0.10, 0.0, None, '$M', 'project', True, 'cost')
    add('maintenance_cost', 'LCCA', params.get('maintenance_cost', 0.0), 'lognormal', 0.15, 0.0, None, '$M/yr', 'scenario', True, 'cost')
    return pd.DataFrame(reg)


def sample_uncertain_parameters(registry, n, seed=42, params=None):
    """LHS-sample active scalar parameters; sample EOL treatment shares jointly (Dirichlet)."""
    active = registry[registry['active_when']].reset_index(drop=True)
    k = len(active)
    u = lhs_unit_samples(n, k, seed) if k else np.zeros((n, 0))
    cols = {}
    for j, row in active.iterrows():
        cols[row['parameter']] = sample_from_distribution(u[:, j], row.to_dict())
    samples = pd.DataFrame(cols)
    # Treatment shares via Dirichlet (preserves reuse+recycle+disposal = 1)
    if params is not None and params.get('include_c1c4', False):
        rng = np.random.default_rng(seed + 1)
        conc = 50.0
        for m in ['concrete', 'steel', 'aluminum', 'wood', 'frp', 'glass']:
            reuse0 = params.get(f'eol_reuse_{m}', 0.0); recycle0 = params.get(f'eol_recycle_{m}', 0.0)
            disp0 = max(1.0 - reuse0 - recycle0, 0.0)
            alpha = np.array([reuse0, recycle0, disp0]) * conc + 1e-3
            draw = rng.dirichlet(alpha, size=n)
            samples[f'eol_reuse_{m}'] = draw[:, 0]
            samples[f'eol_recycle_{m}'] = draw[:, 1]
    return samples


def apply_uncertainty_sample(base_params, sample_row):
    """Return a NEW params dict with sampled overrides (base_params untouched)."""
    p = dict(base_params)
    for kk, vv in sample_row.items():
        p[kk] = float(vv)
    return p


def run_component_monte_carlo(base_params, n=5000, seed=42):
    """Component-based propagation. Returns samples/outputs/summary/drivers/convergence/quality."""
    baseline = run_full_assessment(base_params)
    registry = build_uncertainty_registry(base_params, baseline)
    samples = sample_uncertain_parameters(registry, n, seed, params=base_params)
    rows = []
    for i in range(n):
        sp = apply_uncertainty_sample(base_params, samples.iloc[i].to_dict())
        try:
            r = run_full_assessment(sp)
            gross = r['gross_a1_c4_tons']
            stage_sum = (r['total_embodied_co2'] + r['lca_results']['a4_transport_co2_tons']
                         + r['a5']['a5_total_tons'] + r['i_b2b5_tons'] + r['active_b6_tons'] + r['i_c1c4_tons'])
            failed = abs(stage_sum - gross) > 1e-6 or not np.isfinite(gross)
            rows.append({'run_id': i, 'A1_A3_tons': r['total_embodied_co2'],
                         'A4_tons': r['lca_results']['a4_transport_co2_tons'],
                         'A5_tons': r['a5']['a5_total_tons'], 'B2_B5_tons': r['i_b2b5_tons'],
                         'B6_tons': r['active_b6_tons'], 'C1_C4_tons': r['i_c1c4_tons'],
                         'gross_a1_c4_tons': gross, 'module_d_tons': r['module_d_tons'],
                         'net_with_module_d_tons': r['net_with_module_d_tons'],
                         'gwp_pkm_gross': r['gwp_pkm_gross'], 'npv_lcc_m': r['npv_lcc_m'],
                         'failed': bool(failed), 'failure_reason': 'identity' if failed else ''})
        except Exception as e:  # noqa
            rows.append({'run_id': i, 'A1_A3_tons': np.nan, 'A4_tons': np.nan, 'A5_tons': np.nan,
                         'B2_B5_tons': np.nan, 'B6_tons': np.nan, 'C1_C4_tons': np.nan,
                         'gross_a1_c4_tons': np.nan, 'module_d_tons': np.nan,
                         'net_with_module_d_tons': np.nan, 'gwp_pkm_gross': np.nan,
                         'npv_lcc_m': np.nan, 'failed': True, 'failure_reason': str(e)[:60]})
    outputs = pd.DataFrame(rows)
    summary = summarise_mc_outputs(outputs)
    drivers = compute_uncertainty_drivers(samples, outputs, 'gross_a1_c4_tons')
    convergence = compute_mc_convergence(outputs, 'gross_a1_c4_tons')
    quality = build_uncertainty_quality_table(registry)
    n_ok = int((~outputs['failed']).sum())
    registry_complete = len(registry[registry['active_when']]) > 0
    pgu = bool(baseline.get('publication_grade_full_lca', False) and registry_complete
               and n_ok >= 5000 and convergence['convergence_ok'])
    return {'samples': samples, 'outputs': outputs, 'summary': summary, 'drivers': drivers,
            'convergence': convergence, 'quality': quality, 'n': n, 'n_ok': n_ok,
            'component_mc_used': True, 'publication_grade_uncertainty': pgu, 'baseline': baseline}


def summarise_mc_outputs(outputs_df):
    """Per-output mean/median/std/CV and percentiles (P2.5..P97.5)."""
    cols = ['A1_A3_tons', 'A4_tons', 'A5_tons', 'B2_B5_tons', 'B6_tons', 'C1_C4_tons',
            'gross_a1_c4_tons', 'module_d_tons', 'net_with_module_d_tons', 'gwp_pkm_gross', 'npv_lcc_m']
    ok = outputs_df[~outputs_df['failed']]
    out = []
    for c in cols:
        v = ok[c].to_numpy(dtype=float); v = v[np.isfinite(v)]
        if v.size == 0:
            continue
        mean = float(np.mean(v))
        out.append({'metric': c, 'mean': mean, 'median': float(np.median(v)), 'std': float(np.std(v)),
                    'CV': float(np.std(v) / mean) if mean else np.nan,
                    'P2.5': float(np.percentile(v, 2.5)), 'P5': float(np.percentile(v, 5)),
                    'P50': float(np.percentile(v, 50)), 'P95': float(np.percentile(v, 95)),
                    'P97.5': float(np.percentile(v, 97.5)), 'min': float(v.min()), 'max': float(v.max())})
    return pd.DataFrame(out)


def _spearman(x, y):
    x = np.asarray(x, dtype=float); y = np.asarray(y, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = x[mask], y[mask]
    if x.size < 3 or np.all(x == x[0]):
        return 0.0
    rx = np.argsort(np.argsort(x)).astype(float); ry = np.argsort(np.argsort(y)).astype(float)
    rx -= rx.mean(); ry -= ry.mean()
    denom = np.sqrt((rx * rx).sum() * (ry * ry).sum())
    return float((rx * ry).sum() / denom) if denom > 0 else 0.0


def compute_uncertainty_drivers(samples_df, outputs_df, target='gross_a1_c4_tons'):
    """Spearman rank correlation of each sampled input with the target output (tornado)."""
    ok = ~outputs_df['failed'].to_numpy()
    y = outputs_df[target].to_numpy(dtype=float)
    rows = []
    for col in samples_df.columns:
        rho = _spearman(samples_df[col].to_numpy()[ok], y[ok])
        rows.append({'parameter': col, 'spearman_rho': rho, 'abs_rho': abs(rho),
                     'direction': 'increases' if rho > 0 else ('decreases' if rho < 0 else 'none')})
    return pd.DataFrame(rows).sort_values('abs_rho', ascending=False).reset_index(drop=True)


def compute_mc_convergence(outputs_df, target='gross_a1_c4_tons'):
    """Running mean / P95 / CV; convergence_ok if the last 20% move <1% (mean) and <2% (P95)."""
    ok = outputs_df[~outputs_df['failed']]
    v = ok[target].to_numpy(dtype=float); v = v[np.isfinite(v)]
    n = v.size
    run_mean = np.array([v[:i + 1].mean() for i in range(n)]) if n else np.array([])
    run_p95 = np.array([np.percentile(v[:i + 1], 95) for i in range(n)]) if n else np.array([])
    mean_stable = p95_stable = False
    if n >= 50:
        cut = int(0.8 * n)
        m_final = run_mean[-1]; p_final = run_p95[-1]
        mean_stable = abs(run_mean[cut:].max() - run_mean[cut:].min()) / abs(m_final) < 0.01 if m_final else False
        p95_stable = abs(run_p95[cut:].max() - run_p95[cut:].min()) / abs(p_final) < 0.02 if p_final else False
    return {'running_mean': run_mean, 'running_p95': run_p95,
            'mean_stable': bool(mean_stable), 'p95_stable': bool(p95_stable),
            'convergence_ok': bool(mean_stable and p95_stable)}


def build_uncertainty_quality_table(registry):
    act = registry[registry['active_when']].copy()
    return act[['parameter', 'stage', 'distribution', 'cv', 'source_quality', 'correlation_group']].reset_index(drop=True)


# ═══════════════════════════════════════════════════════════════
# PHASE 5 — SCIENTIFIC SUSTAINABILITY INDEX (hybrid CRITIC-Entropy)
# ───────────────────────────────────────────────────────────────
# A decision-support composite index over a scenario-year matrix. It does NOT
# replace the reported LCA/LCCA/uncertainty outputs and is NOT the legacy
# Dashboard Display Score. Indicators are NON-OVERLAPPING (no gross + its own
# sub-stages); net-with-Module-D is NEVER an environmental indicator (Module D
# enters only as a separate circularity ratio). Target-based normalization,
# hybrid weights w = λ·wE + (1-λ)·wC, additive hierarchical aggregation.
#   z_ij = f(x_ij) ∈ [0,1];  SI_i = Σ_g W_g Σ_{j∈g} (w_j|g) z_ij ∈ [0,1]
# ═══════════════════════════════════════════════════════════════

def build_indicator_metadata():
    """One row per indicator: pillar, direction, target/worst, group, include flag."""
    rows = [
        # Environmental
        ('gwp_pkm_gross', 'Environmental', 'lower', 'kgCO2e/pkm', 0.05, 0.20, 'model', True, 'carbon_primary'),
        ('energy_per_pax_km', 'Environmental', 'lower', 'kWh/pkm', 0.05, 0.20, 'model', True, 'energy'),
        ('module_d_recovery_ratio', 'Environmental', 'higher', 'ratio', 0.30, 0.0, 'model (circularity)', True, 'circularity'),
        ('gross_uncertainty_CV', 'Environmental', 'lower', 'CV', 0.05, 0.30, 'Phase 4 MC', True, 'robustness'),
        # Economic
        ('npv_lcc_per_pkm', 'Economic', 'lower', '$/pkm', 0.05, 0.50, 'model', True, 'cost'),
        ('jobs_per_million_usd', 'Economic', 'higher', 'jobs/$M', 3.0, 0.0, 'model', True, 'econ_benefit'),
        ('lcca_uncertainty_CV', 'Economic', 'lower', 'CV', 0.05, 0.30, 'Phase 4 MC', True, 'cost_robustness'),
        # Operational
        ('availability', 'Operational', 'higher', 'fraction', 0.99, 0.85, 'input', True, 'operational'),
        ('time_savings', 'Operational', 'higher', '1000h', 5.0, 0.0, 'input', True, 'operational_time'),
        ('land_use_efficiency', 'Operational', 'higher', 'pass/ha', 6000.0, 1000.0, 'input', True, 'land'),
        # Social / urban
        ('noise_reduction', 'Social', 'higher', 'dB', 15.0, 0.0, 'input', True, 'social'),
    ]
    return pd.DataFrame(rows, columns=['indicator', 'pillar', 'direction', 'unit', 'target',
                                       'worst', 'source', 'include_in_si', 'double_count_group'])


def _scenario_indicator_row(params, uncertainty_n=0, seed=42):
    r = run_full_assessment(params)
    pkm = r['active_total_pkm'] if r['active_total_pkm'] > 0 else np.nan
    row = {
        'gwp_pkm_gross': r['gwp_pkm_gross'],
        'energy_per_pax_km': r['energy_per_pax_km'],
        'module_d_recovery_ratio': (r['module_d_tons'] / r['gross_a1_c4_tons']) if r['gross_a1_c4_tons'] else 0.0,
        'npv_lcc_per_pkm': (r['npv_lcc_m'] * 1e6 / pkm) if pkm and np.isfinite(pkm) else np.nan,
        'jobs_per_million_usd': (r['total_jobs'] / r['construction_cost']) if r['construction_cost'] else 0.0,
        'availability': params.get('availability', 0.0) / 100.0,
        'time_savings': params.get('time_savings', 0.0),
        'land_use_efficiency': params.get('land_use', 0.0),
        'noise_reduction': params.get('noise_reduction', 0.0),
        'gross_uncertainty_CV': np.nan,
        'lcca_uncertainty_CV': np.nan,
        'publication_grade_full_lca': r.get('publication_grade_full_lca', False),
    }
    if uncertainty_n and uncertainty_n > 0:
        mc = run_component_monte_carlo(params, n=int(uncertainty_n), seed=seed)
        sm = mc['summary'].set_index('metric')
        if 'gross_a1_c4_tons' in sm.index:
            row['gross_uncertainty_CV'] = float(sm.loc['gross_a1_c4_tons', 'CV'])
        if 'npv_lcc_m' in sm.index:
            row['lcca_uncertainty_CV'] = float(sm.loc['npv_lcc_m', 'CV'])
    return row


def generate_default_scenarios(base_params, n=36, seed=42):
    """LHS-spread scenario-year set (deterministic) for the SI matrix."""
    ranges = {'carbon_intensity': (0.2, 0.7), 'energy_per_pax': (0.08, 0.20),
              'daily_pax_km': (300.0, 800.0), 'maintenance_cost': (20.0, 100.0),
              'construction_cost': (1500.0, 3500.0), 'availability': (88.0, 99.0),
              'land_use': (2000.0, 6000.0), 'noise_reduction': (5.0, 15.0),
              'jobs_created': (3000.0, 8000.0)}
    keys = list(ranges.keys())
    u = lhs_unit_samples(n, len(keys), seed)
    scenarios = []
    for i in range(n):
        ov = {}
        for j, k in enumerate(keys):
            lo, hi = ranges[k]
            ov[k] = lo + u[i, j] * (hi - lo)
        scenarios.append({'scenario_id': f'S{i+1:02d}', 'year': 2030 + 10 * (i % 2),
                          'description': f'LHS scenario {i+1}', 'overrides': ov})
    return scenarios


def build_scenario_year_matrix(scenarios, base_params, uncertainty_n=0, seed=42):
    """One row per scenario: id/year + indicator raw values + flags."""
    rows = []
    for sc in scenarios:
        p = dict(base_params); p.update(sc.get('overrides', {}))
        ind = _scenario_indicator_row(p, uncertainty_n=uncertainty_n, seed=seed)
        ind.update({'scenario_id': sc['scenario_id'], 'year': sc.get('year', 0),
                    'description': sc.get('description', '')})
        rows.append(ind)
    cols = ['scenario_id', 'year', 'description']
    df = pd.DataFrame(rows)
    return df[cols + [c for c in df.columns if c not in cols]]


def validate_indicator_matrix(meta, raw_df):
    """Direction/target presence, double-counting, net-as-environmental, data availability."""
    errors, warnings, valid = [], [], True
    for _, m in meta.iterrows():
        if m['direction'] not in ('higher', 'lower'):
            valid = False; errors.append(f"{m['indicator']}: missing/invalid direction")
        if pd.isna(m['target']) or pd.isna(m['worst']):
            valid = False; errors.append(f"{m['indicator']}: missing target/worst")
    # No gross + its own sub-stages in the SI indicator set
    names = set(meta['indicator'])
    substages = {'A1_A3_tons', 'A4_tons', 'A5_tons', 'B2_B5_tons', 'B6_tons', 'C1_C4_tons'}
    if 'gross_a1_c4_tons' in names and (names & substages):
        valid = False; errors.append("double counting: gross + its sub-stages in SI")
    if 'net_with_module_d_tons' in names:
        valid = False; errors.append("net_with_module_d must not be an SI environmental indicator")
    # Availability of data
    for _, m in meta[meta['include_in_si']].iterrows():
        ind = m['indicator']
        if ind not in raw_df.columns or raw_df[ind].isna().all():
            warnings.append(f"{ind}: no data → excluded from SI")
    return {'valid': valid, 'errors': errors, 'warnings': warnings}


def _active_indicators(meta, raw_df):
    act = []
    for _, m in meta[meta['include_in_si']].iterrows():
        ind = m['indicator']
        if ind in raw_df.columns and not raw_df[ind].isna().all():
            act.append(m['indicator'])
    return meta[meta['indicator'].isin(act)].reset_index(drop=True)


def normalize_indicators_target_based(raw_df, meta):
    """z ∈ [0,1] via target-based functions (clipped)."""
    Z = pd.DataFrame(index=raw_df.index)
    for _, m in meta.iterrows():
        ind = m['indicator']; x = raw_df[ind].astype(float)
        T, W = float(m['target']), float(m['worst'])
        if m['direction'] == 'higher':
            z = (x - W) / (T - W) if T != W else 0.0 * x
        else:
            z = (W - x) / (W - T) if W != T else 0.0 * x
        Z[ind] = np.clip(z, 0.0, 1.0)
    return Z


def compute_entropy_weights(Z):
    A = Z.to_numpy(dtype=float); n = A.shape[0]; eps = 1e-12
    P = (A + eps) / (A + eps).sum(axis=0, keepdims=True)
    e = -(P * np.log(P)).sum(axis=0) / np.log(n) if n > 1 else np.zeros(A.shape[1])
    d = 1.0 - e
    w = d / d.sum() if d.sum() > 0 else np.full(A.shape[1], 1.0 / A.shape[1])
    return pd.Series(w, index=Z.columns)


def compute_critic_weights(Z, method='pearson'):
    A = Z.to_numpy(dtype=float); m = A.shape[1]
    sigma = A.std(axis=0, ddof=0)
    if method == 'spearman':
        A2 = np.apply_along_axis(lambda c: np.argsort(np.argsort(c)).astype(float), 0, A)
    else:
        A2 = A
    with np.errstate(invalid='ignore', divide='ignore'):
        R = np.corrcoef(A2, rowvar=False)
    R = np.atleast_2d(R)
    R = np.nan_to_num(R, nan=0.0)
    np.fill_diagonal(R, 1.0)
    C = sigma * (1.0 - R).sum(axis=1)
    w = C / C.sum() if C.sum() > 0 else np.full(m, 1.0 / m)
    return pd.Series(w, index=Z.columns)


def combine_entropy_critic_weights(wE, wC, lam=0.5):
    w = lam * wE + (1.0 - lam) * wC
    w = w / w.sum() if w.sum() > 0 else wE
    return w


def compute_pillar_scores(Z, meta, weights, pillar_weights):
    """Within-pillar weights = w_j / Σ_{j∈g} w_j; pillar score S_{i,g} = Σ w_(j|g) z_ij."""
    pillars = list(pillar_weights.keys())
    S = pd.DataFrame(index=Z.index)
    for g in pillars:
        inds = meta[meta['pillar'] == g]['indicator'].tolist()
        inds = [i for i in inds if i in Z.columns]
        if not inds:
            S[g] = 0.0; continue
        wg = weights[inds]
        wg = wg / wg.sum() if wg.sum() > 0 else pd.Series(1.0 / len(inds), index=inds)
        S[g] = (Z[inds] * wg).sum(axis=1)
    return S


def compute_sustainability_index(Z, meta, weights, pillar_weights):
    pw = pd.Series(pillar_weights, dtype=float)
    pw = pw / pw.sum() if pw.sum() > 0 else pw
    S = compute_pillar_scores(Z, meta, weights, pw.to_dict())
    present = [g for g in pw.index if g in S.columns]
    pwp = pw[present] / pw[present].sum()
    si = (S[present] * pwp).sum(axis=1)
    si = np.clip(si, 0.0, 1.0)
    flat = (Z[weights.index] * weights).sum(axis=1)
    return pd.DataFrame({'SI': si, 'SI_100': si * 100.0, 'SI_flat': np.clip(flat, 0, 1)}), S


def rank_scenarios_by_si(raw_df, si_df):
    out = pd.concat([raw_df[['scenario_id', 'year', 'description']].reset_index(drop=True),
                     si_df.reset_index(drop=True)], axis=1)
    out = out.sort_values('SI', ascending=False).reset_index(drop=True)
    out.insert(0, 'rank', np.arange(1, len(out) + 1))
    return out


def run_si_lambda_sensitivity(Z, meta, wE, wC, pillar_weights, lambdas=(0.0, 0.25, 0.5, 0.75, 1.0)):
    rankings = {}
    si_by_lambda = {}
    for lam in lambdas:
        w = combine_entropy_critic_weights(wE, wC, lam)
        si_df, _ = compute_sustainability_index(Z, meta, w, pillar_weights)
        si_by_lambda[lam] = si_df['SI'].to_numpy()
        rankings[lam] = np.argsort(np.argsort(-si_df['SI'].to_numpy()))
    # rank stability = Spearman between λ=0 and λ=1 SI
    keys = list(si_by_lambda.keys())
    stability = _spearman(si_by_lambda[keys[0]], si_by_lambda[keys[-1]])
    tab = pd.DataFrame({f'SI(λ={lam})': si_by_lambda[lam] for lam in lambdas})
    return {'table': tab, 'rank_stability_spearman': stability, 'rankings': rankings}


def build_si_audit_table(meta, active_meta, validation, weights):
    rows = []
    for _, m in meta.iterrows():
        ind = m['indicator']
        included = ind in set(active_meta['indicator'])
        rows.append({'indicator': ind, 'pillar': m['pillar'], 'direction': m['direction'],
                     'target': m['target'], 'worst': m['worst'], 'group': m['double_count_group'],
                     'included': included, 'weight': float(weights.get(ind, 0.0)),
                     'target_source': m['source']})
    return pd.DataFrame(rows)


def run_phase5_si(scenarios, base_params, lam=0.5, pillar_weights=None, critic_method='pearson',
                  uncertainty_n=0, publication_grade_uncertainty=False, seed=42,
                  scenario_source='generated_demo', uploaded_matrix=None):
    if pillar_weights is None:
        pillar_weights = {'Environmental': 0.35, 'Economic': 0.25, 'Operational': 0.25, 'Social': 0.15}
    warnings = []
    meta = build_indicator_metadata()
    if uploaded_matrix is not None and len(uploaded_matrix) > 0:
        raw = uploaded_matrix.copy()
        scenario_source = 'uploaded'
    else:
        raw = build_scenario_year_matrix(scenarios, base_params, uncertainty_n=uncertainty_n, seed=seed)
    validation = validate_indicator_matrix(meta, raw)
    warnings += validation['warnings']
    active = _active_indicators(meta, raw)
    Z = normalize_indicators_target_based(raw, active)
    wE = compute_entropy_weights(Z)
    wC = compute_critic_weights(Z, method=critic_method)
    weights = combine_entropy_critic_weights(wE, wC, lam)
    si_df, pillar_df = compute_sustainability_index(Z, active, weights, pillar_weights)
    ranked = rank_scenarios_by_si(raw, si_df)
    lambda_sens = run_si_lambda_sensitivity(Z, active, wE, wC, pillar_weights)
    audit = build_si_audit_table(meta, active, validation, weights)
    n_scen = len(raw)
    base_full = run_full_assessment(base_params).get('publication_grade_full_lca', False)
    pw_sum_ok = abs(sum(pillar_weights.values()) - 1.0) < 1e-9
    w_sum_ok = abs(float(weights.sum()) - 1.0) < 1e-9
    # Synthetic LHS demo scenarios are NOT acceptable for publication: require a
    # documented or uploaded scenario-year matrix.
    source_ok = scenario_source in ('documented', 'uploaded')
    if not source_ok:
        warnings.append("Scenario source is 'generated_demo' (synthetic LHS) → publication_grade_si = False. "
                        "Upload or document a scenario-year matrix for publication.")
    pgs = bool(base_full and publication_grade_uncertainty and n_scen >= 30 and validation['valid']
               and pw_sum_ok and w_sum_ok and len(active) >= 3 and source_ok)
    weights_df = pd.DataFrame({'indicator': weights.index, 'entropy': wE.values,
                               'critic': wC.values, 'hybrid': weights.values})
    return {'raw_matrix': raw, 'normalized_matrix': Z, 'indicator_metadata': meta,
            'active_indicators': active, 'entropy_weights': wE, 'critic_weights': wC,
            'combined_weights': weights, 'weights_table': weights_df, 'pillar_scores': pillar_df,
            'si_scores': si_df, 'ranked_scenarios': ranked, 'lambda_sensitivity': lambda_sens,
            'audit': audit, 'validation': validation, 'n_scenarios': n_scen,
            'pillar_weights': pillar_weights, 'lambda': lam, 'scenario_source': scenario_source,
            'publication_grade_si': pgs, 'warnings': warnings}


# ═══════════════════════════════════════════════════════════════
# CUSTOM CSS STYLING
# ═══════════════════════════════════════════════════════════════
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    .stApp {
        font-family: 'Inter', sans-serif;
    }

    .main-header {
        background: linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%);
        padding: 2rem 2.5rem;
        border-radius: 16px;
        margin-bottom: 1.5rem;
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
    }
    .main-header h1 {
        color: #ffffff;
        font-size: 2rem;
        font-weight: 800;
        margin: 0;
        letter-spacing: -0.5px;
    }
    .main-header p {
        color: #a8d8ea;
        font-size: 1rem;
        margin: 0.3rem 0 0 0;
        font-weight: 400;
    }

    .metric-card {
        background: linear-gradient(145deg, #1a1a2e 0%, #16213e 100%);
        border: 1px solid rgba(100, 200, 255, 0.15);
        border-radius: 14px;
        padding: 1.5rem;
        text-align: center;
        box-shadow: 0 4px 20px rgba(0,0,0,0.2);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 30px rgba(0,0,0,0.3);
    }
    .metric-card .metric-value {
        font-size: 2rem;
        font-weight: 800;
        background: linear-gradient(135deg, #00d2ff, #3a7bd5);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
    }
    .metric-card .metric-label {
        color: #8892b0;
        font-size: 0.85rem;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-top: 0.3rem;
    }
    .metric-card .metric-delta {
        color: #64ffda;
        font-size: 0.8rem;
        margin-top: 0.2rem;
    }

    .score-badge {
        display: inline-block;
        padding: 0.4rem 1.2rem;
        border-radius: 20px;
        font-weight: 700;
        font-size: 0.9rem;
    }
    .score-excellent { background: linear-gradient(135deg, #00b09b, #96c93d); color: white; }
    .score-good { background: linear-gradient(135deg, #f7971e, #ffd200); color: #1a1a2e; }
    .score-poor { background: linear-gradient(135deg, #eb3349, #f45c43); color: white; }

    .interaction-synergy { color: #64ffda; font-weight: 600; }
    .interaction-tradeoff { color: #ff6b6b; font-weight: 600; }

    .info-box {
        background: rgba(100, 255, 218, 0.05);
        border-left: 4px solid #64ffda;
        border-radius: 0 8px 8px 0;
        padding: 1rem 1.5rem;
        margin: 0.5rem 0;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        background-color: #0a192f;
        border-radius: 12px;
        padding: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: transparent;
        border-radius: 8px;
        color: #8892b0;
        font-weight: 500;
        padding: 8px 16px;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #233554, #1a365d) !important;
        color: #64ffda !important;
    }

    div[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0a192f 0%, #112240 100%);
    }
    div[data-testid="stSidebar"] .stMarkdown h1,
    div[data-testid="stSidebar"] .stMarkdown h2,
    div[data-testid="stSidebar"] .stMarkdown h3 {
        color: #ccd6f6;
    }

    .report-box {
        background: #0a192f;
        border: 1px solid #233554;
        border-radius: 12px;
        padding: 1.5rem;
        font-family: 'Consolas', 'Courier New', monospace;
        font-size: 0.85rem;
        color: #a8b2d1;
        white-space: pre-wrap;
        max-height: 600px;
        overflow-y: auto;
    }
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# HEADER
# ═══════════════════════════════════════════════════════════════
st.markdown("""
<div class="main-header">
    <h1>🚝 Enhanced Monorail LCA/LCCA Assessment Tool</h1>
    <p>Gross modular A1-C4 LCA + NPV-based LCCA Framework | ISO 14040/14044 + ASTM E917 | Cairo University</p>
</div>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# SIDEBAR - INPUT PARAMETERS (WRAPPED IN FORM TO MIMIC TKINTER RUN)
# ═══════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## ⚙️ Controls")
    publication_mode = st.checkbox("📑 Publication mode", value=True, key="publication_mode",
                                   help="Shows only the scientific tabs (LCA/LCCA/Uncertainty/SI/Benchmark/Methodology). "
                                        "Turn off (Developer mode) to also see illustrative/legacy visualizations.")

    # ── Reactive module toggles (OUTSIDE the form → conditional visibility) ──
    st.markdown("#### 🧩 Modules")
    sd_enable = st.checkbox("Dynamic B6 (System Dynamics)", value=False, key="sd_enable")
    include_a5 = st.checkbox("A5 Construction", value=False, key="include_a5")
    include_b2b5 = st.checkbox("B2–B5 Use Stage", value=False, key="include_b2b5")
    enable_b4 = st.checkbox("↳ B4 Replacement", value=False, key="enable_b4") if include_b2b5 else False
    include_c1c4 = st.checkbox("C1–C4 End-of-Life", value=False, key="include_c1c4")
    show_legacy = st.checkbox("Legacy options", value=False, key="show_legacy",
                              help="Legacy Module-D recycling scenario (used only when C1–C4 is off) + dashboard-only inputs (renewable).")

    MATERIALS_UI = ['concrete', 'steel', 'aluminum', 'wood', 'frp', 'glass']

    with st.form("assessment_form"):
        run_top = st.form_submit_button("🚀 Run Assessment", type="primary", use_container_width=True)

        st.markdown("### 📦 Materials")
        concrete = st.number_input("Concrete (1000 m³)", value=700.0, min_value=0.0, step=10.0, key="concrete")
        steel = st.number_input("Steel (1000 tons)", value=100.0, min_value=0.0, step=5.0, key="steel")
        aluminum = st.number_input("Aluminum (1000 tons)", value=5.0, min_value=0.0, step=0.5, key="aluminum")
        wood = st.number_input("Wood (1000 m³)", value=2.0, min_value=0.0, step=0.5, key="wood")
        frp = st.number_input("FRP (1000 tons)", value=0.0, min_value=0.0, step=0.1, key="frp",
                              help="FRP/GRP has NO verified ICE V4.1 A1-A3 factor. Keep 0 for publication-grade unless a product EPD is supplied.")
        glass = st.number_input("Glass (1000 m²)", value=0.5, min_value=0.0, step=0.1, key="glass")
        glass_thickness_mm = st.number_input("Glass thickness (mm)", value=12.0, min_value=1.0, step=1.0, key="glass_thickness",
                                             help="Glass mass = area × thickness × 2.5 kg/(mm·m²).")

        st.markdown("### 🚚 Transport (A4)")
        transport_distance_km = st.number_input("Transport distance (km)", value=50.0, min_value=0.0, step=10.0, key="transport_distance")
        transport_mode = st.selectbox("Transport mode", ["truck", "rail", "ship"], index=0, key="transport_mode")

        st.markdown("### 🌍 Environmental")
        carbon_intensity_input = st.number_input("Grid carbon (kgCO₂/kWh)", value=0.5, min_value=0.0, step=0.05, key="carbon_int")
        land_use = st.number_input("Land use (pass/ha)", value=5000.0, min_value=0.0, step=100.0, key="land_use")
        noise_reduction = st.number_input("Noise reduction (dB)", value=10.0, min_value=0.0, step=1.0, key="noise")

        st.markdown("### ⚙️ Operational")
        energy_per_pax = st.number_input("Energy (kWh/pax-km)", value=0.15, min_value=0.0, step=0.01, format="%.3f", key="energy")
        daily_pax_km = st.number_input("Daily pax-km (1000)", value=500.0, min_value=0.0, step=10.0, key="daily_pax")
        time_savings = st.number_input("Time savings (1000h)", value=2.5, min_value=0.0, step=0.1, key="time_sav")
        availability = st.slider("Availability (%)", 0, 100, 98, key="avail")

        st.markdown("### 💰 Economic")
        construction_cost = st.number_input("Construction ($M)", value=2500.0, min_value=0.0, step=50.0, key="const_cost")
        maintenance_cost = st.number_input("Maintenance ($M/yr)", value=50.0, min_value=0.0, step=5.0, key="maint_cost")
        jobs_created = st.number_input("Jobs created", value=5000.0, min_value=0.0, step=100.0, key="jobs")
        economic_multiplier = st.number_input("Economic multiplier", value=2.5, min_value=1.0, step=0.1, key="econ_mult")
        discount_rate = st.number_input("Discount rate (%)", value=5.0, min_value=0.0, max_value=20.0, step=0.5, key="discount_rate")
        annual_energy_cost = st.number_input("Energy cost ($M/yr)", value=0.0, min_value=0.0, step=1.0, key="energy_cost")
        residual_value = st.number_input("Residual value ($M)", value=0.0, min_value=0.0, step=10.0, key="residual_value")

        # ── Advanced module fields (defaults; rendered only when the module is on) ──
        sd_C0, sd_delta, sd_maint_interval = 1.0, 0.005, 5
        sd_rho, sd_tau, sd_alpha, sd_growth_pct = 0.05, 1, 0.10, 0.0
        if sd_enable:
            st.markdown("### 🔧 System Dynamics (B6)")
            st.caption("Scenario — not validated unless calibrated.")
            sd_C0 = st.number_input("Initial condition C₀", value=1.0, min_value=0.0, max_value=1.0, step=0.05, key="sd_C0")
            sd_delta = st.number_input("Degradation δ (/yr)", value=0.005, min_value=0.0, step=0.005, format="%.3f", key="sd_delta")
            sd_maint_interval = st.number_input("Maintenance interval (yr)", value=5, min_value=0, step=1, key="sd_maint_interval")
            sd_rho = st.number_input("Recovery ρ", value=0.05, min_value=0.0, step=0.01, format="%.3f", key="sd_rho")
            sd_tau = st.number_input("Delay τ (yr)", value=1, min_value=0, step=1, key="sd_tau")
            sd_alpha = st.number_input("Energy penalty α", value=0.10, min_value=0.0, step=0.05, format="%.2f", key="sd_alpha")
            sd_growth_pct = st.number_input("Demand growth g (%)", value=0.0, min_value=0.0, step=0.5, key="sd_growth")

        a5_boq_mode, a5_diesel_l = 'installed', 0.0
        a5_diesel_ef = FUEL_FACTORS['diesel']['ef_kgco2e_per_l']
        a5_elec_kwh, a5_waste_rate, a5_waste_transport_km, a5_waste_treatment_ef = 0.0, 0.0, 0.0, 0.0
        if include_a5:
            st.markdown("### 🏗️ A5 Construction")
            st.caption("Scenario / user inputs. A5 is reported separately from A4.")
            a5_boq_mode = st.selectbox("BOQ basis", ["installed", "purchased"], index=0, key="a5_boq_mode",
                                       help="installed: extra waste production added here. purchased: production already in A1-A3.")
            a5_diesel_l = st.number_input("Construction diesel (L)", value=0.0, min_value=0.0, step=1000.0, key="a5_diesel_l")
            a5_diesel_ef = st.number_input("Diesel EF (kgCO₂e/L)", value=FUEL_FACTORS['diesel']['ef_kgco2e_per_l'],
                                           min_value=0.0, step=0.01, format="%.2f", key="a5_diesel_ef")
            a5_elec_kwh = st.number_input("Construction electricity (kWh)", value=0.0, min_value=0.0, step=1000.0, key="a5_elec_kwh")
            a5_waste_rate = st.number_input("Waste rate w (0–1)", value=0.0, min_value=0.0, max_value=0.95, step=0.01, format="%.2f", key="a5_waste_rate",
                                            help="Global scenario waste rate (per-material recommended before publication).")
            a5_waste_transport_km = st.number_input("Waste transport (km)", value=0.0, min_value=0.0, step=10.0, key="a5_waste_km")
            a5_waste_treatment_ef = st.number_input("Waste treatment EF (kgCO₂e/kg)", value=0.0, min_value=0.0, step=0.01, format="%.3f", key="a5_waste_ef")

        b2_use_sd_schedule, b2_interval, b2_material_pct = True, 5, 0.05
        b2_diesel_l, b2_elec_kwh, b2_transport_km, b2_cost_per_event_m = 0.0, 0.0, 0.0, 0.0
        b4_years, b4_frac_steel, b4_frac_concrete = "", 0.0, 0.0
        b4_cost_per_event_m, b4_waste_ef, b4_transport_km = 0.0, 0.0, 0.0
        lcca_maint_mode = 'simple_annual'
        if include_b2b5:
            st.markdown("### 🔁 B2–B5 Use Stage")
            st.caption("Activity-based scenario unless project records are supplied.")
            b2_use_sd_schedule = st.checkbox("Link B2 to SD schedule", value=True, key="b2_use_sd")
            b2_interval = st.number_input("B2 interval (yr)", value=5, min_value=0, step=1, key="b2_interval")
            b2_material_pct = st.number_input("B2 material/event (% A1-A3)", value=0.05, min_value=0.0, step=0.05, format="%.2f", key="b2_material_pct")
            b2_diesel_l = st.number_input("B2 diesel/event (L)", value=0.0, min_value=0.0, step=100.0, key="b2_diesel_l")
            b2_elec_kwh = st.number_input("B2 electricity/event (kWh)", value=0.0, min_value=0.0, step=100.0, key="b2_elec_kwh")
            b2_transport_km = st.number_input("B2 transport (km)", value=0.0, min_value=0.0, step=10.0, key="b2_transport_km")
            b2_cost_per_event_m = st.number_input("B2 cost/event ($M)", value=0.0, min_value=0.0, step=0.1, key="b2_cost_event")
            lcca_maint_mode = st.selectbox("LCCA maintenance mode", ["simple_annual", "activity_based"], index=0, key="lcca_maint_mode",
                                           help="simple_annual: annual maintenance only. activity_based: B2/B3/B5 activity costs only. B4 cost added in both.")
            if enable_b4:
                b4_years = st.text_input("B4 years (e.g. 25,40)", value="", key="b4_years")
                b4_frac_steel = st.number_input("B4 fraction — steel", value=0.0, min_value=0.0, max_value=1.0, step=0.05, format="%.2f", key="b4_frac_steel")
                b4_frac_concrete = st.number_input("B4 fraction — concrete", value=0.0, min_value=0.0, max_value=1.0, step=0.05, format="%.2f", key="b4_frac_concrete")
                b4_cost_per_event_m = st.number_input("B4 cost/event ($M)", value=0.0, min_value=0.0, step=1.0, key="b4_cost_event")
                b4_waste_ef = st.number_input("B4 waste EF (kgCO₂e/kg)", value=0.0, min_value=0.0, step=0.01, format="%.3f", key="b4_waste_ef")
                b4_transport_km = st.number_input("B4 waste transport (km)", value=0.0, min_value=0.0, step=10.0, key="b4_transport_km")

        c1_diesel_l, c1_elec_kwh, eol_transport_km = 0.0, 0.0, 50.0
        eol_reuse_ef, eol_recycle_ef, eol_disposal_ef = 0.0, 0.0, 0.0
        eol_recovery_eta, eol_cost_m = 1.0, 0.0
        eol_table = {m: {'reuse': 0.0, 'recycle': 0.0, 'secondary_ef': 0.0} for m in MATERIALS_UI}
        if include_c1c4:
            st.markdown("### ♻️ C1–C4 End-of-Life")
            st.caption("EOL scenario. Treatment shares must sum to 1 (uses remaining masses after B4/B5).")
            c1_diesel_l = st.number_input("C1 diesel (L)", value=0.0, min_value=0.0, step=1000.0, key="c1_diesel_l")
            c1_elec_kwh = st.number_input("C1 electricity (kWh)", value=0.0, min_value=0.0, step=1000.0, key="c1_elec_kwh")
            eol_transport_km = st.number_input("EOL transport (km)", value=50.0, min_value=0.0, step=10.0, key="eol_transport_km")
            eol_reuse_ef = st.number_input("Reuse EF (kgCO₂e/kg)", value=0.0, min_value=0.0, step=0.01, format="%.3f", key="eol_reuse_ef")
            eol_recycle_ef = st.number_input("Recycle EF (kgCO₂e/kg)", value=0.0, min_value=0.0, step=0.01, format="%.3f", key="eol_recycle_ef")
            eol_disposal_ef = st.number_input("Disposal EF (kgCO₂e/kg)", value=0.0, min_value=0.0, step=0.01, format="%.3f", key="eol_disposal_ef")
            eol_recovery_eta = st.number_input("Recovery efficiency η", value=1.0, min_value=0.0, max_value=1.0, step=0.05, format="%.2f", key="eol_eta")
            eol_cost_m = st.number_input("EOL cost ($M)", value=0.0, min_value=0.0, step=10.0, key="eol_cost_m")
            st.markdown("**Per-material treatment shares + secondary EF**")
            eol_df0 = pd.DataFrame({'material': MATERIALS_UI, 'reuse': [0.0]*6, 'recycle': [0.0]*6, 'secondary_EF': [0.0]*6})
            eol_edit = st.data_editor(eol_df0, hide_index=True, use_container_width=True, key="eol_editor",
                                      disabled=['material'])
            st.caption("Disposal share = 1 − reuse − recycle (auto). Secondary EF 0 = no Module D for that material.")
            for _, _r in pd.DataFrame(eol_edit).iterrows():
                eol_table[_r['material']] = {'reuse': float(_r['reuse']), 'recycle': float(_r['recycle']),
                                             'secondary_ef': float(_r['secondary_EF'])}

        steel_recycle, aluminum_recycle, recycling_scenario, renewable_share = 70, 85, 'none', 20
        if show_legacy:
            st.markdown("### 🗄️ Legacy / dashboard-only")
            st.caption("Module-D recycling scenario is used ONLY when C1–C4 is off. Renewable is dashboard-only.")
            steel_recycle = st.slider("Steel recycling (%)", 0, 100, 70, key="steel_recycle")
            aluminum_recycle = st.slider("Aluminum recycling (%)", 0, 100, 85, key="aluminum_recycle")
            recycling_scenario = st.selectbox("Legacy Module-D scenario", ["none", "conservative", "base"], index=0, key="recycling_scenario")
            renewable_share = st.slider("Renewable share (%) — dashboard-only", 0, 100, 20, key="renewable")

        st.markdown("---")
        run_btn = st.form_submit_button("🚀 Run Assessment", type="primary", use_container_width=True)
    run_btn = bool(run_btn or run_top)

# Collect parameters
current_params = {
    'concrete': concrete, 'steel': steel, 'aluminum': aluminum,
    'wood': wood, 'frp': frp, 'glass': glass, 'glass_thickness_mm': glass_thickness_mm,
    'steel_recycle': steel_recycle, 'aluminum_recycle': aluminum_recycle, 'recycling_scenario': recycling_scenario,
    'transport_distance_km': transport_distance_km, 'transport_mode': transport_mode,
    'carbon_intensity': carbon_intensity_input, 'renewable_share': renewable_share,
    'land_use': land_use, 'noise_reduction': noise_reduction,
    'energy_per_pax': energy_per_pax, 'daily_pax_km': daily_pax_km,
    'time_savings': time_savings, 'availability': availability,
    'construction_cost': construction_cost, 'maintenance_cost': maintenance_cost,
    'jobs_created': jobs_created, 'economic_multiplier': economic_multiplier,
    'discount_rate': discount_rate, 'annual_energy_cost': annual_energy_cost,
    'residual_value': residual_value,
    'sd_enable': sd_enable, 'sd_C0': sd_C0, 'sd_delta': sd_delta,
    'sd_maint_interval': sd_maint_interval, 'sd_rho': sd_rho, 'sd_tau': sd_tau,
    'sd_alpha': sd_alpha, 'sd_growth_pct': sd_growth_pct,
    'include_a5': include_a5, 'a5_boq_mode': a5_boq_mode, 'a5_diesel_l': a5_diesel_l,
    'a5_diesel_ef': a5_diesel_ef, 'a5_elec_kwh': a5_elec_kwh, 'a5_waste_rate': a5_waste_rate,
    'a5_waste_transport_km': a5_waste_transport_km, 'a5_waste_treatment_ef': a5_waste_treatment_ef,
    'include_b2b5': include_b2b5, 'b2_use_sd_schedule': b2_use_sd_schedule, 'b2_interval': b2_interval,
    'b2_material_pct': b2_material_pct, 'b2_diesel_l': b2_diesel_l, 'b2_elec_kwh': b2_elec_kwh,
    'b2_transport_km': b2_transport_km, 'b2_cost_per_event_m': b2_cost_per_event_m,
    'enable_b4': enable_b4, 'b4_years': b4_years, 'b4_frac_steel': b4_frac_steel,
    'b4_frac_concrete': b4_frac_concrete, 'b4_cost_per_event_m': b4_cost_per_event_m,
    'b4_waste_ef': b4_waste_ef, 'b4_transport_km': b4_transport_km, 'lcca_maint_mode': lcca_maint_mode,
    'include_c1c4': include_c1c4, 'c1_diesel_l': c1_diesel_l, 'c1_elec_kwh': c1_elec_kwh,
    'eol_transport_km': eol_transport_km, 'eol_reuse_ef': eol_reuse_ef, 'eol_recycle_ef': eol_recycle_ef,
    'eol_disposal_ef': eol_disposal_ef, 'eol_recovery_eta': eol_recovery_eta, 'eol_cost_m': eol_cost_m,
    **{f'eol_reuse_{_m}': eol_table[_m]['reuse'] for _m in eol_table},
    **{f'eol_recycle_{_m}': eol_table[_m]['recycle'] for _m in eol_table},
    **{f'eol_secondary_ef_{_m}': eol_table[_m]['secondary_ef'] for _m in eol_table},
}

@st.cache_data
def run_full_assessment_cached(params_tuple):
    params = dict(params_tuple)
    return run_full_assessment(params)

# Run assessment on button click or auto-run for the first time
if run_btn or 'results' not in st.session_state:
    params_tuple = tuple(sorted(current_params.items()))
    st.session_state['results'] = run_full_assessment_cached(params_tuple)
    st.session_state['params'] = current_params
    # No direct st.session_state assignments for widget keys to prevent StreamlitAPIException
results = st.session_state['results']
params = st.session_state['params']

if not results.get('publication_grade', True):
    st.error(
        "🚫 **NOT publication-grade:** FRP is included but has NO verified A1-A3 carbon factor. "
        f"FRP placeholder contribution = {results['carbon_frp']/1000:,.1f} t CO₂e. "
        f"**Defensible A1-A3 embodied carbon (excluding FRP) = {results['total_embodied_co2_excl_frp']:,.1f} t CO₂e** "
        f"vs {results['total_embodied_co2']:,.1f} t including the placeholder. "
        "Set FRP = 0, or supply a product-specific EPD, before reporting."
    )

with st.sidebar:
    st.markdown("#### ✅ Publication readiness")
    def _flag(label, ok):
        st.markdown(f"{'🟢' if ok else '🟡'} {label}: **{'yes' if ok else 'conditional'}**")
    _flag("Full LCA (A1–C4)", results.get('publication_grade_full_lca', False))
    _flag("Module D complete", results.get('module_d_quality_ok', True))
    st.caption("Uncertainty (Phase 4) & SI (Phase 5) readiness are shown in their tabs.")

with st.expander("🧩 LCA Stage Coverage", expanded=False):
    # Phase 3A: authoritative coverage comes from the modular stage_contribution.
    cov_df = pd.DataFrame(results['stage_contribution'])[['Stage', 'tCO2e', 'status']].copy()
    cov_df['tCO2e'] = cov_df['tCO2e'].map(lambda v: f"{v:,.1f}")
    st.dataframe(cov_df, use_container_width=True, hide_index=True)
    st.caption("Module D (recycling credit) is reported separately and is NOT part of the gross total.")

# ═══════════════════════════════════════════════════════════════
# MAIN CONTENT - TABS (Publication mode hides illustrative/legacy tabs)
# ═══════════════════════════════════════════════════════════════
_TAB_LABELS = {
    'results': "📊 Results & Analysis", 'oat': "📊 Sensitivity (OAT)",
    'uncertainty': "🎲 Uncertainty (Phase 4)", 'si': "🏁 Sustainability Index",
    'sd': "🔧 System Dynamics (B6)", 'benchmark': "🔬 External Benchmarking",
    'about': "📖 About & Methodology",
    'pareto': "🗄️ Pareto (illustrative)", 'twelve': "🗄️ 12-Element (illustrative)",
    'surface3d': "🗄️ 3D Surface (illustrative)", 'urban': "🗄️ Urban 3D (illustrative)",
    'interaction': "🗄️ Interaction Net (illustrative)",
}
_SCI_ORDER = ['results', 'oat', 'uncertainty', 'si', 'sd', 'benchmark', 'about']
_LEGACY_ORDER = ['pareto', 'twelve', 'surface3d', 'urban', 'interaction']
_order = _SCI_ORDER if publication_mode else (_SCI_ORDER + _LEGACY_ORDER)
_created = st.tabs([_TAB_LABELS[k] for k in _order])
TABS = {k: _created[i] for i, k in enumerate(_order)}

# ═══════════════════════════════════════════════════════════════
# TAB 1: RESULTS & ANALYSIS
# ═══════════════════════════════════════════════════════════════
with TABS['results']:
    # Key metrics row
    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        co2_pkm = results['gwp_pkm_gross']
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{co2_pkm:.4f}</div>
            <div class="metric-label">kg CO₂e / passenger-km (gross)</div>
            <div class="metric-delta">A1-C4 gross · B6 {results['active_b6_mode']}</div>
        </div>""", unsafe_allow_html=True)
    with m2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{results['gross_a1_c4_tons']:,.0f}</div>
            <div class="metric-label">Gross A1-C4 LCA CO₂ (tons)</div>
            <div class="metric-delta">A5: {results['a5']['a5_total_tons']:,.0f}t · Module D separate</div>
        </div>""", unsafe_allow_html=True)
    with m3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{results['total_ee']/1000:,.0f}</div>
            <div class="metric-label">Embodied Energy (GJ)</div>
            <div class="metric-delta">Annual Op: {results['annual_operational_energy']:,.0f} kWh</div>
        </div>""", unsafe_allow_html=True)
    with m4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">${results['npv_lcc_m']:,.0f}M</div>
            <div class="metric-label">LCC NPV Cost</div>
            <div class="metric-delta">Jobs: {results['total_jobs']:,.0f}</div>
        </div>""", unsafe_allow_html=True)
    with m5:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{params['renewable_share']}%</div>
            <div class="metric-label">Renewable (dashboard-only)</div>
            <div class="metric-delta">Grid carbon: {results['effective_carbon_intensity']:.3f} kg/kWh</div>
        </div>""", unsafe_allow_html=True)

    if results.get('sd_enabled'):
        st.info(
            f"🔧 **Dynamic B6 active (scenario-based SD).** "
            f"Static B6 = {results['b6_static_tons']:,.0f} t · "
            f"Dynamic B6 = {results['b6_dynamic_tons']:,.0f} t · "
            f"ΔB6 = {results['delta_b6_tons']:+,.0f} t · "
            f"Dynamic total LCA = {results['total_lifecycle_co2_dynamic']:,.0f} t "
            f"({results['co2_kg_per_pkm_dynamic']:.5f} kg/pkm). See the System Dynamics (B6) tab."
        )

    with st.expander("🧱 Stage Contribution (gross modular A1-C4 LCA)", expanded=True):
        sc_df = pd.DataFrame(results['stage_contribution'])
        sc_df['tCO2e'] = sc_df['tCO2e'].map(lambda v: f"{v:,.1f}")
        sc_df['% of gross'] = sc_df['% of gross'].map(lambda v: f"{v:.1f}%")
        st.dataframe(sc_df, use_container_width=True, hide_index=True)
        st.caption(
            f"Gross modular A1-C4 LCA total = {results['gross_a1_c4_tons']:,.1f} t CO₂e · "
            f"GWP = {results['gwp_pkm_gross']:.5f} kg/pkm (gross, never net) · "
            f"Module D (separate) = −{results['module_d_tons']:,.1f} t · "
            f"Net incl. Module D (supplementary) = {results['net_with_module_d_tons']:,.1f} t. "
            "Each stage is independently toggleable; statuses are shown above."
        )
        if not results.get('publication_grade_full_lca', True):
            st.error("🚫 Full-LCA result is NOT publication-grade (see FRP/EPD warning above).")

    if results['b2b5']['included']:
        with st.expander("🔁 B2–B5 activity & mass balance (Phase 3B)", expanded=False):
            bb = results['b2b5']
            mb1, mb2, mb3 = st.columns(3)
            with mb1: st.metric("B2 maintenance (t CO₂e)", f"{bb['b2_tons']:,.1f}")
            with mb2: st.metric("B4 replacement (t CO₂e)", f"{bb['b4_tons']:,.1f}")
            with mb3: st.metric("B2–B5 total (t CO₂e)", f"{bb['b2_b5_total_tons']:,.1f}")
            st.caption(f"LCCA maintenance mode: **{results['lcca_maint_mode']}** "
                       "(B4 replacement cost is added in both modes; routine maintenance never double-counted).")
            st.markdown("**Yearly B2–B5 activity** (years with activity only)")
            yb = pd.DataFrame(bb['yearly'])
            yb = yb[(yb['B2_count'] > 0) | (yb['B4_count'] > 0)]
            st.dataframe(yb, use_container_width=True, hide_index=True)
            st.markdown("**Material mass balance** (remaining feeds Phase 3C C1–C4; removed handled in B4/B5)")
            st.dataframe(pd.DataFrame(results['mass_balance']['mass_balance_by_material']),
                         use_container_width=True, hide_index=True)
            st.info("B2–B5 is an **activity-based scenario** and is not 'validated' unless project "
                    "maintenance/replacement records are supplied. Module D is unchanged by B2–B5 (deferred to Phase 3C).")

    if params.get('include_c1c4') and not results['eol_validation']['valid']:
        st.error("🚫 **C1–C4 not computed:** treatment shares do not sum to 1 for: "
                 + "; ".join(results['eol_validation']['errors'])
                 + ". Fix reuse/recycle shares (disposal = 1 − reuse − recycle). "
                 "publication_grade_full_lca is False.")

    if results['c1c4']['included']:
        with st.expander("♻️ C1–C4 End-of-Life & Module D (Phase 3C)", expanded=False):
            cc = results['c1c4']
            e1, e2, e3, e4, e5 = st.columns(5)
            with e1: st.metric("C1 deconstruction", f"{cc['c1_tons']:,.1f}")
            with e2: st.metric("C2 transport", f"{cc['c2_tons']:,.1f}")
            with e3: st.metric("C3 processing", f"{cc['c3_tons']:,.1f}")
            with e4: st.metric("C4 disposal", f"{cc['c4_tons']:,.1f}")
            with e5: st.metric("C1–C4 total", f"{cc['c1_c4_total_tons']:,.1f}")
            g1, g2, g3 = st.columns(3)
            with g1: st.metric("Gross A1–C4", f"{results['gross_a1_c4_tons']:,.1f} t")
            with g2: st.metric("Module D (separate)", f"−{results['module_d_tons']:,.1f} t")
            with g3: st.metric("Net incl. Module D", f"{results['net_with_module_d_tons']:,.1f} t")
            st.markdown("**End-of-life by material** (on remaining masses after B4/B5)")
            st.dataframe(pd.DataFrame(cc['eol_by_material']), use_container_width=True, hide_index=True)
            st.markdown("**Module D by material** (recovery credit — separate, never in gross)")
            st.dataframe(pd.DataFrame(results['module_d_eol']['module_d_by_material']),
                         use_container_width=True, hide_index=True)
            if not results['module_d_quality_ok']:
                st.warning("⚠️ Module D is incomplete (a recovered material has no secondary EF). "
                           "Net incl. Module D is understated and is NOT publication-grade.")

    with st.expander("🏷️ Data Quality / Publication Readiness", expanded=False):
        dq = pd.DataFrame([
            {'Stage': 'A1–A3 materials', 'source': 'ICE V4.1 / EPD', 'quality': 'medium–high',
             'publication-grade': 'yes' if results.get('publication_grade', True) else 'NO (FRP w/o EPD)'},
            {'Stage': 'A4 transport', 'source': 'scenario / user input', 'quality': 'low–medium', 'publication-grade': 'conditional'},
            {'Stage': 'A5 construction', 'source': 'scenario / user input', 'quality': 'low–medium',
             'publication-grade': 'conditional' if results['a5']['included'] else 'n/a (off)'},
            {'Stage': 'B2–B5 use stage', 'source': 'activity schedule / scenario', 'quality': 'low–medium',
             'publication-grade': 'conditional' if results['b2b5']['included'] else 'n/a (off)'},
            {'Stage': 'B6 operation', 'source': f"{results['active_b6_mode']} scenario", 'quality': 'conditional',
             'publication-grade': 'not validated unless calibrated'},
            {'Stage': 'C1–C4 end-of-life', 'source': 'EOL scenario / project data', 'quality': 'low–medium',
             'publication-grade': 'conditional' if results['c1c4']['included'] else 'n/a (off)'},
            {'Stage': 'Module D', 'source': 'EOL recovery + secondary EF', 'quality': 'conditional',
             'publication-grade': 'only if secondary factors supplied'},
        ])
        st.dataframe(dq, use_container_width=True, hide_index=True)
        flag = results.get('publication_grade_full_lca', True)
        (st.success if flag else st.error)(
            f"publication_grade_full_lca = {flag} "
            + ("" if flag else "(FRP without EPD, invalid treatment shares, or incomplete Module D)."))

    st.markdown("---")

    if not publication_mode:
        st.caption("Legacy dashboard scores & interaction network (interface-only) are hidden in Publication mode.")
        # Category Scores Comparison
        col_scores1, col_scores2 = st.columns(2)

        with col_scores1:
            st.markdown("#### 📊 Category Scores (Original vs Adjusted)")
            categories = ['Material', 'Environmental', 'Operational', 'Economic']
            original = [results['material_score'], results['environmental_score'],
                         results['operational_score'], results['economic_score']]
            adjusted = [results['adjusted_material_score'], results['adjusted_environmental_score'],
                         results['adjusted_operational_score'], results['adjusted_economic_score']]

            fig_scores = go.Figure()
            fig_scores.add_trace(go.Bar(name='Original', x=categories, y=original,
                                         marker_color='rgba(100, 149, 237, 0.7)',
                                         text=[f'{v:.1f}' for v in original], textposition='outside'))
            fig_scores.add_trace(go.Bar(name='Interaction-Adjusted', x=categories, y=adjusted,
                                         marker_color='rgba(100, 255, 218, 0.7)',
                                         text=[f'{v:.1f}' for v in adjusted], textposition='outside'))
            fig_scores.update_layout(
                barmode='group', height=400,
                plot_bgcolor='rgba(10,25,47,0.8)', paper_bgcolor='rgba(0,0,0,0)',
                font_color='#ccd6f6', yaxis_range=[0, 110],
                yaxis_title='Score (0-100)', margin=dict(t=30, b=30)
            )
            st.plotly_chart(fig_scores, use_container_width=True)

        with col_scores2:
            st.markdown("#### 🕸️ Dashboard Radar")
            fig_radar = go.Figure()
            fig_radar.add_trace(go.Scatterpolar(
                r=adjusted + [adjusted[0]],
                theta=categories + [categories[0]],
                fill='toself', fillcolor='rgba(100, 255, 218, 0.15)',
                line=dict(color='#64ffda', width=2), name='Adjusted'
            ))
            fig_radar.add_trace(go.Scatterpolar(
                r=original + [original[0]],
                theta=categories + [categories[0]],
                fill='toself', fillcolor='rgba(100, 149, 237, 0.1)',
                line=dict(color='#6495ed', width=2, dash='dash'), name='Original'
            ))
            fig_radar.update_layout(
                polar=dict(
                    bgcolor='rgba(10,25,47,0.8)',
                    radialaxis=dict(visible=True, range=[0, 100], gridcolor='rgba(255,255,255,0.1)'),
                    angularaxis=dict(gridcolor='rgba(255,255,255,0.1)')
                ),
                showlegend=True, height=400,
                paper_bgcolor='rgba(0,0,0,0)', font_color='#ccd6f6',
                margin=dict(t=30, b=30)
            )
            st.plotly_chart(fig_radar, use_container_width=True)

        # Interaction Analysis
        st.markdown("#### 🔄 Cross-Category Interaction Effects")
        effects = results['interaction_effects']

        int_col1, int_col2, int_col3 = st.columns(3)
        with int_col1:
            st.markdown(f"""
            <div class="info-box">
                <b>Synergy Effects</b><br>
                Total: <span class="interaction-synergy">{results['total_synergy']:.2f} pts</span><br>
                Ratio: <span class="interaction-synergy">{results['synergy_ratio']:.2f}</span>
            </div>""", unsafe_allow_html=True)
        with int_col2:
            st.markdown(f"""
            <div class="info-box">
                <b>Trade-off Effects</b><br>
                Total: <span class="interaction-tradeoff">{results['total_tradeoff']:.2f} pts</span><br>
                {"Synergies dominate ✅" if results['synergy_ratio'] > 1 else "Trade-offs dominate ⚠️"}
            </div>""", unsafe_allow_html=True)
        with int_col3:
            st.markdown(f"""
            <div class="info-box">
                <b>Dashboard Display Summary</b><br>
                Score: <b>{results['dashboard_display_score']:.1f}/100</b><br>
                {"Excellent 🎉" if results['dashboard_display_score'] >= 80 else ("Good 👍" if results['dashboard_display_score'] >= 60 else "Needs Improvement 📈")}
            </div>""", unsafe_allow_html=True)

        # Detailed interaction effects table
        with st.expander("📋 Detailed Interaction Effects", expanded=False):
            interaction_df = pd.DataFrame({
                'Interaction': ['Material → Environmental', 'Environmental → Operational',
                               'Operational → Economic', 'Economic → Material',
                               'Material → Operational', 'Environmental → Economic'],
                'Effect (pts)': [f"{effects['mat_env_effect']:+.2f}", f"{effects['env_op_effect']:+.2f}",
                                f"{effects['op_econ_effect']:+.2f}", f"{effects['econ_mat_effect']:+.2f}",
                                f"{effects['mat_op_effect']:+.2f}", f"{effects['env_econ_effect']:+.2f}"],
                'Type': ['Trade-off' if effects['mat_env_effect'] < 0 else 'Synergy',
                         'Trade-off' if effects['env_op_effect'] < 0 else 'Synergy',
                         'Trade-off' if effects['op_econ_effect'] < 0 else 'Synergy',
                         'Trade-off' if effects['econ_mat_effect'] < 0 else 'Synergy',
                         'Trade-off' if effects['mat_op_effect'] < 0 else 'Synergy',
                         'Trade-off' if effects['env_econ_effect'] < 0 else 'Synergy']
            })
            st.dataframe(interaction_df, use_container_width=True, hide_index=True)

    # Full Report Text
    with st.expander("📄 Full Assessment Report", expanded=False):
        _legacy_block = ""
        if not publication_mode:
            _legacy_block = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LEGACY DASHBOARD (non-scientific, interface-only)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Dashboard Display Score: {results['dashboard_display_score']:.1f}/100
Category (Material/Environmental/Operational/Economic): {results['material_score']:.1f} / {results['environmental_score']:.1f} / {results['operational_score']:.1f} / {results['economic_score']:.1f}
Synergy-to-Trade-off ratio: {results['synergy_ratio']:.2f}
"""
        report = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    ENHANCED MONORAIL LCA / LCCA ASSESSMENT RESULTS       ║
╚══════════════════════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🏗️ MATERIALS ASSESSMENT
   • Concrete Volume: {params['concrete']:.1f} thousand m³
   • Steel Mass: {params['steel']:.1f} thousand tons
   • Aluminum Mass: {params['aluminum']:.1f} thousand tons
   • Wood Volume: {params['wood']:.1f} thousand m³
   • FRP Mass: {params['frp']:.1f} thousand tons
   • Glass Area: {params['glass']:.1f} thousand m²
   • Steel Recycling Rate: {params['steel_recycle']:.1f}%
   • Aluminum Recycling Rate: {params['aluminum_recycle']:.1f}%

🌱 ENVIRONMENTAL ASSESSMENT
   • Annual Operational CO₂: {results['annual_co2_operational']:.1f} tons
   • Embodied CO₂ A1-A3 (GROSS): {results['total_embodied_co2']:.1f} tons
   • A4 Transport CO₂: {results['lca_results']['a4_transport_co2_tons']:.1f} tons
   • A5 Construction CO₂: {results['a5']['a5_total_tons']:.1f} tons ({'included' if results['a5']['included'] else 'not included'})
   • B2-B5 Use Stage CO₂: {results['i_b2b5_tons']:.1f} tons ({'included' if results['b2b5']['included'] else 'not included'})
   • B6 Operation ({results['active_b6_mode']}): {results['active_b6_tons']:.1f} tons
   • C1-C4 End-of-Life CO₂: {results['i_c1c4_tons']:.1f} tons ({'included' if results['c1c4']['included'] else 'not included'})
   • Gross modular A1-C4 LCA total (A1-A3 + A4 + A5 + B2-B5 + active B6 + C1-C4): {results['gross_a1_c4_tons']:.1f} tons
   • GWP per pkm (gross): {results['gwp_pkm_gross']:.6f} kg CO₂e/pkm
   • Module D recycling credit (separate, NOT in gross): -{results['module_d_tons']:.1f} tons
   • Net incl. Module D (supplementary): {results['net_with_module_d_tons']:.1f} tons
   • Grid Carbon Intensity (applied to core B6): {results['effective_carbon_intensity']:.3f} kg CO₂/kWh
   • Total Embodied Energy: {results['total_ee']:.0f} MJ
   • Renewable Share (dashboard-only, NOT applied to core LCA in Phase 1b): {params['renewable_share']:.1f}%

⚡ OPERATIONAL ASSESSMENT
   • Energy per Passenger-km: {params['energy_per_pax']:.3f} kWh
   • Daily Passenger-km: {params['daily_pax_km']:.1f} thousand
   • System Availability: {params['availability']:.1f}%

💰 ECONOMIC ASSESSMENT
   • Construction Cost: ${params['construction_cost']:.1f} million
   • Annual Maintenance: ${params['maintenance_cost']:.1f} million
   • Total Jobs Created: {results['total_jobs']:.0f}
   • 50-Year Maintenance (undiscounted): ${results['total_maintenance_cost']:.1f} million

{_legacy_block}
Assessment Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Methodology: Gross modular A1-C4 LCA (A1-A3 + A4 + optional A5 + activity-based B2-B5 + active B6 + optional C1-C4) + NPV-based LCCA.
Carbon factors: ICE Database Educational V4.1 (Oct 2025). Module D (recycling) reported separately per EN 15804. Li and Zhu (2022) is benchmark-only.
"""
        st.code(report, language=None)

        # Export buttons
        exp1, exp2, exp3 = st.columns(3)
        with exp1:
            st.download_button("📥 Download Report (.txt)", report,
                              file_name=f"monorail_report_{datetime.now().strftime('%Y%m%d')}.txt",
                              mime="text/plain")
        with exp2:
            csv_rows = [
                {'Category': 'LCA', 'Metric': f"Gross modular A1-C4 LCA total (B6 {results['active_b6_mode']})", 'Value': f"{results['gross_a1_c4_tons']:.1f}", 'Unit': 'tons CO₂e'},
                {'Category': 'LCA', 'Metric': 'GWP per pkm (gross)', 'Value': f"{results['gwp_pkm_gross']:.6f}", 'Unit': 'kg CO₂e/pkm'},
                {'Category': 'LCA', 'Metric': 'Embodied CO₂ A1-A3 (gross)', 'Value': f"{results['lca_results']['embodied_co2_tons']:.1f}", 'Unit': 'tons CO₂e'},
                {'Category': 'LCA', 'Metric': 'A4 Transport CO₂', 'Value': f"{results['lca_results']['a4_transport_co2_tons']:.1f}", 'Unit': 'tons CO₂e'},
                {'Category': 'LCA', 'Metric': 'A5 Construction CO₂', 'Value': f"{results['a5']['a5_total_tons']:.1f}", 'Unit': 'tons CO₂e'},
                {'Category': 'LCA', 'Metric': 'B2-B5 Use Stage CO₂', 'Value': f"{results['i_b2b5_tons']:.1f}", 'Unit': 'tons CO₂e'},
                {'Category': 'LCA', 'Metric': 'C1-C4 End-of-Life CO₂', 'Value': f"{results['i_c1c4_tons']:.1f}", 'Unit': 'tons CO₂e'},
                {'Category': 'Module D', 'Metric': 'Recovery credit (separate)', 'Value': f"-{results['module_d_tons']:.1f}", 'Unit': 'tons CO₂e'},
                {'Category': 'LCA', 'Metric': 'Lifetime operational CO₂', 'Value': f"{results['lca_results']['lifetime_operational_co2_tons']:.1f}", 'Unit': 'tons CO₂e'},
                {'Category': 'LCA', 'Metric': 'Embodied Energy', 'Value': f"{results['total_ee']:.0f}", 'Unit': 'MJ'},
                {'Category': 'LCCA', 'Metric': 'LCC NPV Cost', 'Value': f"{results['npv_lcc_m']:.0f}", 'Unit': '$M'},
            ]
            if not publication_mode:
                csv_rows.append({'Category': 'Display-only', 'Metric': 'Dashboard Display Score', 'Value': f"{results['dashboard_display_score']:.1f}", 'Unit': '/100'})
            csv_data = pd.DataFrame(csv_rows).to_csv(index=False)
            st.download_button("📥 Download CSV", csv_data,
                              file_name=f"monorail_data_{datetime.now().strftime('%Y%m%d')}.csv")
        with exp3:
            excel_buf = io.BytesIO()
            xl_metric = [
                f"Gross modular A1-C4 LCA total (B6 {results['active_b6_mode']})",
                'GWP per pkm (gross)', 'Embodied CO₂ A1-A3 (gross)', 'A4 Transport CO₂',
                'A5 Construction CO₂', 'B2-B5 Use Stage CO₂', 'B6 operation (active)',
                'C1-C4 End-of-Life CO₂', 'Module D (separate)', 'Net incl. Module D (supplementary)',
                'Embodied Energy', 'LCC NPV Cost']
            xl_value = [
                results['gross_a1_c4_tons'], results['gwp_pkm_gross'], results['lca_results']['embodied_co2_tons'],
                results['lca_results']['a4_transport_co2_tons'], results['a5']['a5_total_tons'],
                results['i_b2b5_tons'], results['active_b6_tons'], results['i_c1c4_tons'],
                -results['module_d_tons'], results['net_with_module_d_tons'], results['total_ee'], results['npv_lcc_m']]
            xl_unit = ['tons CO₂e', 'kg CO₂e/pkm', 'tons CO₂e', 'tons CO₂e', 'tons CO₂e', 'tons CO₂e',
                       'tons CO₂e', 'tons CO₂e', 'tons CO₂e', 'tons CO₂e', 'MJ', '$M']
            if not publication_mode:
                xl_metric.append('Dashboard Display Score'); xl_value.append(results['dashboard_display_score']); xl_unit.append('/100 display-only')
            with pd.ExcelWriter(excel_buf, engine='openpyxl') as writer:
                pd.DataFrame({'Metric': xl_metric, 'Value': xl_value, 'Unit': xl_unit}).to_excel(writer, sheet_name='Summary', index=False)
            st.download_button("📥 Download Excel", excel_buf.getvalue(),
                              file_name=f"monorail_report_{datetime.now().strftime('%Y%m%d')}.xlsx",
                              mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ═══════════════════════════════════════════════════════════════
# TAB 2: BENCHMARK / REPRODUCTION CHECK
# ═══════════════════════════════════════════════════════════════
with TABS['benchmark']:
    st.markdown("### 🔬 Benchmark / Reproduction Check Against Li and Zhu (2022)")
    st.markdown("""
    External comparison with a peer-reviewed monorail LCA study.
    **Benchmark:** Li and Zhu (2022) — Computational Intelligence and Neuroscience — DOI: 10.1155/2022/3872069
    """)
    st.warning(
        "⚠️ This is a **benchmark / reproduction check — NOT an independent validation.** "
        "The default material quantities reproduce the benchmark per-km intensities, so close agreement on "
        "material/energy totals is expected *by construction* and does not validate the model. "
        "Li and Zhu (2022) is used **only** as an external benchmark; it is **never** a source of material "
        "carbon factors (those come from the ICE Database Educational V4.1, Oct 2025)."
    )

    system_length_km = 96
    bench_total_concrete = LIZHU_2022_BENCHMARK['material_intensity_per_km']['concrete_m3'] * system_length_km
    bench_total_steel = LIZHU_2022_BENCHMARK['material_intensity_per_km']['steel_tons'] * system_length_km
    bench_total_aluminum = LIZHU_2022_BENCHMARK['material_intensity_per_km']['aluminum_tons'] * system_length_km
    bench_embodied_energy_total = LIZHU_2022_BENCHMARK['embodied_impact_per_km']['energy_GJ'] * system_length_km
    bench_embodied_carbon_total = LIZHU_2022_BENCHMARK['embodied_impact_per_km']['carbon_tons_CO2'] * system_length_km
    bench_operational_energy = LIZHU_2022_BENCHMARK['operational_performance']['energy_kwh_per_pkm']
    bench_operational_carbon = LIZHU_2022_BENCHMARK['operational_performance']['carbon_kgCO2_per_pkm']

    your_embodied_energy_GJ = results['total_ee'] / 1000.0
    your_operational_carbon_raw = results['energy_per_pax_km'] * results['effective_carbon_intensity']

    def get_status(your_val, bench_val):
        if bench_val == 0:
            return 'n/a (zero benchmark)', 'poor'
        err = abs((your_val - bench_val) / bench_val * 100)
        if err < 10: return '✓ Excellent', 'excellent'
        elif err < 20: return '~ Good', 'good'
        else: return '✗ Review', 'poor'

    comparisons = [
        ('Total Concrete (m³)', bench_total_concrete, results['concrete_volume']),
        ('Total Steel (tons)', bench_total_steel, results['steel_tons']),
        ('Total Aluminum (tons)', bench_total_aluminum, results['aluminum_tons']),
        ('Embodied Energy (GJ)', bench_embodied_energy_total, your_embodied_energy_GJ),
        ('Embodied Carbon (tons CO₂)', bench_embodied_carbon_total, results['total_embodied_co2']),
        ('Energy Intensity (kWh/pkm)', bench_operational_energy, results['energy_per_pax_km']),
        ('Carbon Intensity (kg CO₂/pkm)', bench_operational_carbon, your_operational_carbon_raw),
    ]

    bench_data = []
    excellent_count = good_count = review_count = 0
    for metric, bench_val, your_val in comparisons:
        error_pct = abs((your_val - bench_val) / bench_val * 100) if bench_val != 0 else 0
        status, tag = get_status(your_val, bench_val)
        if tag == 'excellent': excellent_count += 1
        elif tag == 'good': good_count += 1
        else: review_count += 1
        bench_data.append({
            'Metric': metric,
            'Li & Zhu 2022': f"{bench_val:,.2f}" if bench_val < 100 else f"{bench_val:,.0f}",
            'Your Tool': f"{your_val:,.2f}" if your_val < 100 else f"{your_val:,.0f}",
            'Difference': f"{your_val - bench_val:+,.2f}" if abs(your_val) < 100 else f"{your_val - bench_val:+,.0f}",
            'Error %': f"{error_pct:.1f}%",
            'Status': status
        })

    bench_df = pd.DataFrame(bench_data)
    st.dataframe(bench_df, use_container_width=True, hide_index=True)

    total_metrics = excellent_count + good_count + review_count
    agreement_rate = (excellent_count + good_count) / total_metrics * 100 if total_metrics > 0 else 0

    vc1, vc2, vc3, vc4 = st.columns(4)
    with vc1: st.metric("✓ Excellent (<10%)", excellent_count)
    with vc2: st.metric("~ Good (<20%)", good_count)
    with vc3: st.metric("✗ Review (>20%)", review_count)
    with vc4: st.metric("Reproduction Agreement", f"{agreement_rate:.0f}%",
                        help="Agreement with Li and Zhu (2022) totals — reproduction check, not independent validation.")


# ═══════════════════════════════════════════════════════════════
# TAB 3: PARETO OPTIMIZATION
# ═══════════════════════════════════════════════════════════════
if 'pareto' in TABS:
    with TABS['pareto']:
        st.markdown("### 🎯 Multi-Objective Optimization: Pareto Front Analysis")
        st.warning("Illustrative synthetic scenario visualization; not used in the scientific LCA/LCCA results.")
        st.markdown("Visualize trade-offs between Environmental Impact, Economic Cost, and Technical Performance.")

        if st.button("🔄 Generate Pareto Front", key="pareto_btn"):
            np.random.seed(42)
            n_solutions = 100

            base_co2 = results['total_co2']
            base_cost = results.get('total_cost', base_co2 * 0.01)
            base_score = results.get('dashboard_display_score', 75)

            co2_values = base_co2 * np.random.uniform(0.85, 1.15, n_solutions)
            cost_values = base_cost * np.random.uniform(0.80, 1.20, n_solutions)
            score_values = base_score * np.random.uniform(0.90, 1.10, n_solutions)

            # Identify Pareto-optimal
            pareto_mask = np.ones(n_solutions, dtype=bool)
            for i in range(n_solutions):
                if not pareto_mask[i]: continue
                for j in range(n_solutions):
                    if i == j: continue
                    if (co2_values[j] <= co2_values[i] and cost_values[j] <= cost_values[i] and
                        score_values[j] >= score_values[i] and
                        (co2_values[j] < co2_values[i] or cost_values[j] < cost_values[i] or score_values[j] > score_values[i])):
                        pareto_mask[i] = False
                        break

            fig = go.Figure()
            fig.add_trace(go.Scatter3d(
                x=co2_values[pareto_mask], y=cost_values[pareto_mask] / 1e6,
                z=score_values[pareto_mask], mode='markers',
                marker=dict(size=10, color=score_values[pareto_mask], colorscale='Viridis',
                           showscale=True, colorbar=dict(title="Score"), line=dict(color='gold', width=2)),
                name='Pareto Optimal',
                text=[f'CO₂: {c/1000:.1f}k<br>Cost: ${co/1e6:.2f}M<br>Score: {s:.1f}'
                      for c, co, s in zip(co2_values[pareto_mask], cost_values[pareto_mask], score_values[pareto_mask])],
                hoverinfo='text'
            ))
            fig.add_trace(go.Scatter3d(
                x=co2_values[~pareto_mask], y=cost_values[~pareto_mask] / 1e6,
                z=score_values[~pareto_mask], mode='markers',
                marker=dict(size=5, color='lightgray', opacity=0.3), name='Dominated'
            ))
            fig.add_trace(go.Scatter3d(
                x=[base_co2], y=[base_cost / 1e6], z=[base_score], mode='markers',
                marker=dict(size=15, color='red', symbol='diamond', line=dict(color='darkred', width=3)),
                name='Current Solution'
            ))
            fig.update_layout(
                title='3D Pareto Front: Environmental vs Economic vs Performance',
                scene=dict(
                    xaxis=dict(title='CO₂ (tons)', backgroundcolor='white'),
                    yaxis=dict(title='Cost ($M)', backgroundcolor='white'),
                    zaxis=dict(title='Score', backgroundcolor='white'),
                    camera=dict(eye=dict(x=1.5, y=1.5, z=1.3))
                ),
                height=700, paper_bgcolor='white', plot_bgcolor='white'
            )
            st.plotly_chart(fig, use_container_width=True)

            n_pareto = np.sum(pareto_mask)
            st.success(f"Found {n_pareto} Pareto-optimal solutions out of {n_solutions} evaluated.")


# ═══════════════════════════════════════════════════════════════
# TAB 4: 12-ELEMENT ANALYSIS (Parallel Coordinates)
# ═══════════════════════════════════════════════════════════════
if 'twelve' in TABS:
    with TABS['twelve']:
        st.warning("Illustrative synthetic scenario visualization; not used in the scientific LCA/LCCA results.")
        st.markdown("### 📈 Parallel Coordinates: 12 Illustrative Dashboard Elements")

        if st.button("📊 Generate Parallel Coordinates", key="parallel_btn"):
            np.random.seed(42)
            n_scenarios = 20
            scenarios_data = []
            for i in range(n_scenarios):
                variation = np.random.uniform(0.9, 1.1)
                scenario = {
                    'Concrete Impact': float(np.clip(100 - (results['concrete_volume'] / 10000) * variation, 0, 100)),
                    'Steel Impact': float(np.clip(100 - (results['steel_mass'] / 1500) * variation, 0, 100)),
                    'Aluminum Impact': float(np.clip(100 - (results['aluminum_mass'] / 75) * variation, 0, 100)),
                    'Embodied Energy': float(np.clip(100 - (results['total_ee'] / 100000) * variation, 0, 100)),
                    'Carbon Emissions': float(np.clip(100 - (results['total_co2'] / 4000) * variation, 0, 100)),
                    'Water Consumption': float(np.clip(np.random.uniform(60, 85) * variation, 0, 100)),
                    'Op. Efficiency': float(np.clip(np.random.uniform(70, 95) * variation, 0, 100)),
                    'Maintenance': float(np.clip(np.random.uniform(65, 90) * variation, 0, 100)),
                    'Safety Rating': float(np.clip(np.random.uniform(80, 98) * variation, 0, 100)),
                    'Economic Viability': float(np.clip(np.random.uniform(60, 85) * variation, 0, 100)),
                    'Social Impact': float(np.clip(np.random.uniform(55, 80) * variation, 0, 100)),
                    'Lifecycle Cost': float(np.clip(100 - (results.get('total_cost', 2500) / 40) * variation, 0, 100))
                }
                scenarios_data.append(scenario)

            df = pd.DataFrame(scenarios_data)
            df['Composite_Display_Score'] = df.mean(axis=1)

            dimensions = [dict(label=col, values=df[col], range=[0, 100]) for col in df.columns[:-1]]

            fig = go.Figure(data=go.Parcoords(
                line=dict(color=df['Composite_Display_Score'], colorscale='RdYlGn', showscale=True, cmin=0, cmax=100,
                         colorbar=dict(title="Composite<br>Display Score", thickness=20)),
                dimensions=dimensions
            ))
            fig.update_layout(title='12 Illustrative Dashboard Elements Across Scenarios', height=700, paper_bgcolor='white')
            st.plotly_chart(fig, use_container_width=True)

            best = df[df.columns[:-1]].mean().nlargest(3)
            worst = df[df.columns[:-1]].mean().nsmallest(3)
            bc1, bc2 = st.columns(2)
            with bc1:
                st.markdown("**🏆 Top Performing Elements:**")
                for i, (name, val) in enumerate(best.items()): st.write(f"{i+1}. {name}: {val:.1f}/100")
            with bc2:
                st.markdown("**⚠️ Needs Improvement:**")
                for i, (name, val) in enumerate(worst.items()): st.write(f"{i+1}. {name}: {val:.1f}/100")


# ═══════════════════════════════════════════════════════════════
# TAB 5: UNCERTAINTY ANALYSIS (Monte Carlo)
# ═══════════════════════════════════════════════════════════════
with TABS['uncertainty']:
    st.markdown("### 🎲 Phase 4 — Component-based Monte Carlo Uncertainty")
    st.caption("Each uncertain input is sampled from its own distribution and the full A1–C4 model is "
               "re-run, so uncertainty propagates per component while gross = Σ stages, net = gross − Module D, "
               "and GWP/pkm = gross/pkm hold in every draw. No total-scaling.")

    cmc1, cmc2, cmc3 = st.columns(3)
    with cmc1:
        mc_enable = st.checkbox("Enable Phase 4 MC", value=False, key="mc_enable")
        mc_n = st.number_input("n simulations", value=5000, min_value=100, max_value=20000, step=500, key="mc_n")
    with cmc2:
        mc_seed = st.number_input("random seed", value=42, min_value=0, step=1, key="mc_seed")
        st.caption("Sampling: Latin Hypercube + Dirichlet (shares).")
    with cmc3:
        st.caption("Publication-grade uncertainty requires n ≥ 5000 and convergence_ok.")

    if mc_enable:
        @st.cache_data(show_spinner=True)
        def _run_mc(params_tuple, n, seed):
            return run_component_monte_carlo(dict(params_tuple), n=int(n), seed=int(seed))
        mcres = _run_mc(tuple(sorted(params.items())), mc_n, mc_seed)
        st.session_state['phase4_pgu'] = bool(mcres['publication_grade_uncertainty'])
        sm = mcres['summary'].set_index('metric')
        g = sm.loc['gross_a1_c4_tons']
        st.success(f"Gross A1–C4: mean {g['mean']:,.0f} t · 95% uncertainty interval "
                   f"[{g['P2.5']:,.0f}, {g['P97.5']:,.0f}] t · CV {g['CV']*100:.1f}% "
                   f"({mcres['n_ok']}/{mcres['n']} valid runs).")
        flag = mcres['publication_grade_uncertainty']
        (st.success if flag else st.warning)(
            f"publication_grade_uncertainty = {flag}. "
            + ("" if flag else "Requires publication-grade full LCA, n ≥ 5000, and convergence_ok."))
        st.warning("Intervals are **scenario-based uncertainty intervals**, not measured statistical "
                   "confidence intervals (most distributions are scenario assumptions).")

        st.markdown("#### Stage & metric uncertainty (95% interval)")
        disp = mcres['summary'].copy()
        for c in ['mean', 'median', 'std', 'P2.5', 'P50', 'P97.5', 'min', 'max']:
            disp[c] = disp[c].map(lambda v: f"{v:,.3f}" if abs(v) < 10 else f"{v:,.0f}")
        disp['CV'] = mcres['summary']['CV'].map(lambda v: f"{v*100:.1f}%")
        st.dataframe(disp[['metric', 'mean', 'P2.5', 'P50', 'P97.5', 'CV']], use_container_width=True, hide_index=True)

        h1, h2 = st.columns(2)
        okrows = mcres['outputs'][~mcres['outputs']['failed']]
        with h1:
            fig = go.Figure(go.Histogram(x=okrows['gross_a1_c4_tons'] / 1000.0, nbinsx=50,
                                         marker=dict(color='rgba(100,255,218,0.6)')))
            fig.add_vline(x=g['P2.5']/1000, line_dash="dash", line_color="#ff6b6b")
            fig.add_vline(x=g['P97.5']/1000, line_dash="dash", line_color="#ff6b6b")
            fig.update_layout(title='Gross A1–C4 (k tCO₂e)', height=340, paper_bgcolor='rgba(0,0,0,0)',
                              plot_bgcolor='rgba(10,25,47,0.8)', font_color='#ccd6f6', margin=dict(t=40, b=30))
            st.plotly_chart(fig, use_container_width=True)
        with h2:
            fig = go.Figure(go.Histogram(x=okrows['gwp_pkm_gross'], nbinsx=50,
                                         marker=dict(color='rgba(100,149,237,0.6)')))
            fig.update_layout(title='GWP per pkm (gross)', height=340, paper_bgcolor='rgba(0,0,0,0)',
                              plot_bgcolor='rgba(10,25,47,0.8)', font_color='#ccd6f6', margin=dict(t=40, b=30))
            st.plotly_chart(fig, use_container_width=True)

        h3, h4 = st.columns(2)
        with h3:
            fig = go.Figure(go.Histogram(x=okrows['net_with_module_d_tons'] / 1000.0, nbinsx=50,
                                         marker=dict(color='rgba(247,151,30,0.6)')))
            fig.update_layout(title='Net incl. Module D (k tCO₂e, supplementary)', height=340,
                              paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(10,25,47,0.8)',
                              font_color='#ccd6f6', margin=dict(t=40, b=30))
            st.plotly_chart(fig, use_container_width=True)
        with h4:
            fig = go.Figure(go.Histogram(x=okrows['npv_lcc_m'], nbinsx=50,
                                         marker=dict(color='rgba(150,201,61,0.6)')))
            fig.update_layout(title='LCC NPV ($M)', height=340, paper_bgcolor='rgba(0,0,0,0)',
                              plot_bgcolor='rgba(10,25,47,0.8)', font_color='#ccd6f6', margin=dict(t=40, b=30))
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("#### Uncertainty drivers (Spearman tornado, target = gross A1–C4)")
        drv = mcres['drivers'].head(12)
        figd = go.Figure(go.Bar(x=drv['spearman_rho'], y=drv['parameter'], orientation='h',
                                marker_color=['#ff6b6b' if v > 0 else '#64ffda' for v in drv['spearman_rho']]))
        figd.update_layout(title='Top drivers (Spearman ρ)', height=420, paper_bgcolor='rgba(0,0,0,0)',
                           plot_bgcolor='rgba(10,25,47,0.8)', font_color='#ccd6f6',
                           yaxis=dict(autorange='reversed'), margin=dict(t=40, b=30))
        st.plotly_chart(figd, use_container_width=True)

        cv = mcres['convergence']
        if len(cv['running_mean']):
            figc = go.Figure(go.Scatter(y=cv['running_mean'] / 1000.0, mode='lines', line=dict(color='#64ffda')))
            figc.update_layout(title=f"Convergence — running mean (ok={cv['convergence_ok']})", height=320,
                               paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(10,25,47,0.8)',
                               font_color='#ccd6f6', xaxis_title='run', yaxis_title='mean gross (k t)', margin=dict(t=40, b=30))
            st.plotly_chart(figc, use_container_width=True)

        dl1, dl2 = st.columns(2)
        with dl1:
            st.download_button("📥 Download MC samples (CSV)", mcres['samples'].to_csv(index=False),
                               file_name=f"mc_samples_{datetime.now().strftime('%Y%m%d')}.csv")
        with dl2:
            mc_xl = io.BytesIO()
            with pd.ExcelWriter(mc_xl, engine='openpyxl') as wr:
                mcres['summary'].to_excel(wr, sheet_name='summary', index=False)
                mcres['drivers'].to_excel(wr, sheet_name='drivers', index=False)
                mcres['quality'].to_excel(wr, sheet_name='registry', index=False)
            st.download_button("📥 Download MC summary (Excel)", mc_xl.getvalue(),
                               file_name=f"mc_summary_{datetime.now().strftime('%Y%m%d')}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    if not publication_mode:
        st.markdown("---")
        st.markdown("#### 🗄️ Legacy illustrative MC (display-only, NOT publication-grade)")
        st.warning("⚠️ **Legacy total-scaling Monte Carlo — illustrative only.** It scales the *total* CO₂ by "
                   "concrete and grid factors and must NOT be used as scientific uncertainty. Superseded by the "
                   "Phase 4 component-based engine above.")

    if (not publication_mode) and st.button("🎲 Run legacy illustrative MC", key="mc_btn"):
        n_simulations = 1000
        np.random.seed(42)

        base_co2 = results['total_co2']
        base_energy = results['total_ee']
        base_cost = results.get('total_cost', base_co2 * 0.01)

        concrete_unc = UNCERTAINTY_FACTORS["concrete_factor"]["cv"]
        steel_unc = UNCERTAINTY_FACTORS["steel_factor"]["cv"]
        energy_unc = UNCERTAINTY_FACTORS["energy_factor"]["cv"]
        carbon_unc = UNCERTAINTY_FACTORS["grid_carbon_factor"]["cv"]

        co2_sim, energy_sim, cost_sim = [], [], []
        for _ in range(n_simulations):
            def lognormal_factor(cv, size=1):
                sigma = np.sqrt(np.log(1 + cv**2))
                mu = -0.5 * sigma**2
                return np.random.lognormal(mean=mu, sigma=sigma, size=size)

            cf = lognormal_factor(concrete_unc)[0]
            sf = lognormal_factor(steel_unc)[0]
            ef = lognormal_factor(energy_unc)[0]
            carbf = lognormal_factor(carbon_unc)[0]
            co2_sim.append(base_co2 * cf * carbf)
            energy_sim.append(base_energy * ef)
            cost_sim.append(base_cost * cf * sf)

        co2_sim = np.array(co2_sim)
        energy_sim = np.array(energy_sim)
        cost_sim = np.array(cost_sim)

        fig = make_subplots(rows=3, cols=1,
                           subplot_titles=('CO₂ Emissions', 'Embodied Energy', 'Total Cost'),
                           vertical_spacing=0.12)
        fig.add_trace(go.Histogram(x=co2_sim/1000, nbinsx=50, name='CO₂',
                                    marker=dict(color='rgba(200,50,50,0.6)', line=dict(color='darkred', width=1))), row=1, col=1)
        fig.add_trace(go.Histogram(x=energy_sim/1000, nbinsx=50, name='Energy',
                                    marker=dict(color='rgba(50,100,200,0.6)', line=dict(color='darkblue', width=1))), row=2, col=1)
        fig.add_trace(go.Histogram(x=cost_sim/1e6, nbinsx=50, name='Cost',
                                    marker=dict(color='rgba(50,200,50,0.6)', line=dict(color='darkgreen', width=1))), row=3, col=1)

        co2_ci = (np.percentile(co2_sim, 2.5), np.percentile(co2_sim, 97.5))
        co2_mean = np.mean(co2_sim)
        co2_cv = (np.std(co2_sim) / co2_mean) * 100

        fig.add_vline(x=co2_ci[0]/1000, line_dash="dash", line_color="red", row=1, col=1)
        fig.add_vline(x=co2_ci[1]/1000, line_dash="dash", line_color="red", row=1, col=1)
        fig.add_vline(x=co2_mean/1000, line_color="darkred", line_width=3, row=1, col=1)

        fig.update_layout(title=f'Monte Carlo ({n_simulations} Simulations)', height=900,
                         showlegend=False, paper_bgcolor='white')
        fig.update_xaxes(title_text="CO₂ (k tons)", row=1, col=1)
        fig.update_xaxes(title_text="Energy (GJ)", row=2, col=1)
        fig.update_xaxes(title_text="Cost ($M)", row=3, col=1)
        st.plotly_chart(fig, use_container_width=True)

        uc1, uc2, uc3 = st.columns(3)
        with uc1:
            st.metric("CO₂ 95% CI", f"[{co2_ci[0]/1000:.1f}k, {co2_ci[1]/1000:.1f}k]")
            st.metric("CV", f"{co2_cv:.1f}%")
        with uc2:
            e_ci = (np.percentile(energy_sim, 2.5), np.percentile(energy_sim, 97.5))
            st.metric("Energy 95% CI", f"[{e_ci[0]/1000:.1f}, {e_ci[1]/1000:.1f}] GJ")
        with uc3:
            c_ci = (np.percentile(cost_sim, 2.5), np.percentile(cost_sim, 97.5))
            st.metric("Cost 95% CI", f"[${c_ci[0]/1e6:.2f}M, ${c_ci[1]/1e6:.2f}M]")


# ═══════════════════════════════════════════════════════════════
# TAB 6: 3D SENSITIVITY SURFACE
# ═══════════════════════════════════════════════════════════════
if 'surface3d' in TABS:
    with TABS['surface3d']:
        st.markdown("### 📐 3D Sensitivity Surface: Carbon Intensity × Renewable Energy")
        st.warning("⚠️ Illustrative dashboard-only surface. Renewable share is NOT used in the core LCA "
                   "(grid carbon intensity already reflects the grid mix); this view is for visualization only.")

        if st.button("📈 Generate 3D Surface", key="surface_btn"):
            carbon_range = np.linspace(0.2, 0.8, 30)
            renew_range = np.linspace(0, 100, 30)
            X, Y = np.meshgrid(carbon_range, renew_range)
            Z = np.zeros_like(X)

            base_co2 = results['total_co2']
            for i in range(X.shape[0]):
                for j in range(X.shape[1]):
                    carbon_factor = X[i, j] / 0.5
                    renewable_factor = (100 - Y[i, j]) / (100 - 20)
                    Z[i, j] = base_co2 * carbon_factor * renewable_factor

            Z_norm = (Z - Z.min()) / (Z.max() - Z.min()) * 10

            fig = go.Figure(data=[go.Surface(
                x=X, y=Y, z=Z_norm, colorscale='RdYlGn_r',
                colorbar=dict(title="Relative<br>Impact"),
                contours=dict(z=dict(show=True, usecolormap=True, highlightcolor="limegreen", project=dict(z=True))),
                hovertemplate='Carbon: %{x:.2f}<br>Renewable: %{y:.1f}%<br>Impact: %{z:.2f}<extra></extra>'
            )])
            fig.update_layout(
                title='3D Sensitivity: Carbon Intensity vs Renewable Energy',
                scene=dict(
                    xaxis=dict(title='Carbon (kg CO₂/kWh)', backgroundcolor="rgb(230,230,230)"),
                    yaxis=dict(title='Renewable (%)', backgroundcolor="rgb(230,230,230)"),
                    zaxis=dict(title='Relative Impact', backgroundcolor="rgb(230,230,230)"),
                    camera=dict(eye=dict(x=1.5, y=1.5, z=1.3))
                ),
                height=800, paper_bgcolor='white'
            )
            st.plotly_chart(fig, use_container_width=True)

            min_idx = np.unravel_index(Z.argmin(), Z.shape)
            st.success(f"Optimal: Carbon = {X[min_idx]:.3f} kg/kWh, Renewable = {Y[min_idx]:.1f}%")


# ═══════════════════════════════════════════════════════════════
# TAB 7: ONE-AT-A-TIME SENSITIVITY ANALYSIS
# ═══════════════════════════════════════════════════════════════
with TABS['oat']:
    st.markdown("### 📊 One-at-a-Time Sensitivity Analysis")
    st.caption("Scenario-based OAT sensitivity on the gross modular LCA total (±10% per variable).")

    def one_at_a_time_sensitivity(params, variable, change_pct=0.10):
        base = run_full_assessment(params)["gross_a1_c4_tons"]
        modified = params.copy()
        modified[variable] = modified[variable] * (1 + change_pct)
        new_val = run_full_assessment(modified)["gross_a1_c4_tons"]
        if base == 0:
            return 0.0
        return ((new_val - base) / base) / change_pct

    # Renewable share is intentionally excluded: it is dashboard-only in Phase 1b
    # and does not affect core B6, so its OAT sensitivity would be a confusing zero.
    var_map = {
        'carbon_intensity': 'Grid Carbon Intensity',
        'energy_per_pax': 'Energy per pax-km',
        'daily_pax_km': 'Daily pax-km',
        'steel': 'Steel quantity',
        'aluminum': 'Aluminum quantity',
        'concrete': 'Concrete quantity'
    }

    sens = []
    for k, label in var_map.items():
        val = one_at_a_time_sensitivity(params, k, 0.10)
        sens.append((label, val))

    sens_df = pd.DataFrame(sens, columns=['Variable', 'Sensitivity Index'])
    sens_df['Abs'] = sens_df['Sensitivity Index'].abs()
    sens_df = sens_df.sort_values('Abs', ascending=False)

    fig_sens = go.Figure(go.Bar(
        x=sens_df['Sensitivity Index'],
        y=sens_df['Variable'],
        orientation='h',
        marker_color=['#ff6b6b' if v > 0 else '#64ffda' for v in sens_df['Sensitivity Index']]
    ))
    fig_sens.update_layout(title='OAT Sensitivity Index on Total Lifecycle CO₂', height=450,
                           xaxis_title='((ΔOutput/Output)/(ΔInput/Input))', yaxis_title='Variable')
    st.plotly_chart(fig_sens, use_container_width=True)
    st.dataframe(sens_df[['Variable','Sensitivity Index']], use_container_width=True, hide_index=True)

# TAB 8: URBAN ANALYTICS
# ═══════════════════════════════════════════════════════════════
if 'urban' in TABS:
    with TABS['urban']:
        st.warning("Illustrative synthetic scenario visualization; not used in the scientific LCA/LCCA results.")
        st.markdown("### 🗺️ Urban Analytics 3D: Spatial Sustainability Assessment")

        case_study = st.selectbox("Select Case Study:", ['Cairo', 'Chongqing', 'Osaka', 'Generic'], key="case_sel")

        if st.button("🗺️ Generate Urban Analytics", key="urban_btn"):
            case_data = {
                'Cairo': {'stations': 22, 'length_km': 54, 'lat_center': 30.0444, 'lon_center': 31.2357, 'population_served': 2000000},
                'Chongqing': {'stations': 45, 'length_km': 67, 'lat_center': 29.5630, 'lon_center': 106.5516, 'population_served': 5000000},
                'Osaka': {'stations': 18, 'length_km': 28, 'lat_center': 34.6937, 'lon_center': 135.5023, 'population_served': 1500000},
                'Generic': {'stations': 25, 'length_km': 40, 'lat_center': 40.7128, 'lon_center': -74.0060, 'population_served': 1000000}
            }
            data = case_data[case_study]
            n_stations = data['stations']

            np.random.seed(42)
            lats = np.linspace(data['lat_center'] - 0.2, data['lat_center'] + 0.2, n_stations) + np.random.normal(0, 0.02, n_stations)
            lons = np.linspace(data['lon_center'] - 0.2, data['lon_center'] + 0.2, n_stations) + np.random.normal(0, 0.02, n_stations)

            station_co2 = results['total_co2'] / n_stations
            co2_per_station = station_co2 * np.random.uniform(0.8, 1.2, n_stations)
            pax_per_station = (data['population_served'] / n_stations) * np.random.uniform(0.7, 1.3, n_stations)

            fig = go.Figure()
            fig.add_trace(go.Scattergeo(
                lat=lats, lon=lons, mode='markers+text',
                marker=dict(size=co2_per_station / np.max(co2_per_station) * 30 + 10,
                           color=co2_per_station, colorscale='RdYlGn_r', showscale=True,
                           colorbar=dict(title="CO₂<br>(tons/yr)"), line=dict(color='black', width=1)),
                text=[f'S{i+1}' for i in range(n_stations)], textposition='top center',
                hovertext=[f'<b>Station S{i+1}</b><br>CO₂: {co2:.0f} t/yr<br>Pax: {int(p):,}/day'
                          for i, (co2, p) in enumerate(zip(co2_per_station, pax_per_station))],
                hoverinfo='text', name='Stations'
            ))
            fig.add_trace(go.Scattergeo(lat=lats, lon=lons, mode='lines',
                                         line=dict(width=3, color='blue'), opacity=0.5, name='Route'))
            fig.update_geos(center=dict(lat=data['lat_center'], lon=data['lon_center']),
                           projection_type='natural earth', showcountries=True, showcoastlines=True,
                           showland=True, landcolor='rgb(243,243,243)')
            fig.update_layout(
                title=f'Urban Analytics: {case_study} Monorail Network ({n_stations} stations | {data["length_km"]} km)',
                height=700, showlegend=True
            )
            st.plotly_chart(fig, use_container_width=True)

            uc1, uc2, uc3 = st.columns(3)
            with uc1:
                st.metric("Total CO₂", f"{np.sum(co2_per_station):,.0f} t/yr")
                st.metric("Avg/Station", f"{np.mean(co2_per_station):,.0f} t/yr")
            with uc2:
                st.metric("Max Station", f"S{np.argmax(co2_per_station)+1} ({co2_per_station[np.argmax(co2_per_station)]:,.0f} t)")
                st.metric("Min Station", f"S{np.argmin(co2_per_station)+1} ({co2_per_station[np.argmin(co2_per_station)]:,.0f} t)")
            with uc3:
                st.metric("Per Capita", f"{np.sum(co2_per_station)/data['population_served']*1000:.2f} kg/person/yr")
                st.metric("Density", f"{n_stations/data['length_km']:.2f} stations/km")


# ═══════════════════════════════════════════════════════════════
# TAB 9: INTERACTION NETWORK
# ═══════════════════════════════════════════════════════════════
if 'interaction' in TABS:
    with TABS['interaction']:
        st.markdown("### 🔄 Illustrative Interaction Visualization")
        st.warning("This network is a heuristic visualization only. The coefficients are not validated causal effects and are not used in the core LCA/LCCA results.")

        categories_net = ['Material', 'Environmental', 'Operational', 'Economic']
        angles = np.linspace(0, 2*np.pi, 4, endpoint=False)
        node_x = np.cos(angles)
        node_y = np.sin(angles)

        interactions = [
            ('Material', 'Environmental', effects['mat_env_effect']),
            ('Environmental', 'Operational', effects['env_op_effect']),
            ('Operational', 'Economic', effects['op_econ_effect']),
            ('Economic', 'Material', effects['econ_mat_effect']),
            ('Material', 'Operational', effects['mat_op_effect']),
            ('Environmental', 'Economic', effects['env_econ_effect'])
        ]

        fig_net = go.Figure()
        for fr, to, val in interactions:
            fi = categories_net.index(fr)
            ti = categories_net.index(to)
            color = 'green' if val > 0 else 'red'
            fig_net.add_trace(go.Scatter(
                x=[node_x[fi], node_x[ti], None], y=[node_y[fi], node_y[ti], None],
                mode='lines', line=dict(width=min(abs(val)*2+1, 10), color=color),
                hoverinfo='text', hovertext=f"{fr} → {to}: {val:+.2f} ({'Synergy' if val > 0 else 'Trade-off'})",
                showlegend=False
            ))

        node_colors = ['#3498db', '#2ecc71', '#f39c12', '#e74c3c']
        scores_adj = [results['adjusted_material_score'], results['adjusted_environmental_score'],
                      results['adjusted_operational_score'], results['adjusted_economic_score']]

        fig_net.add_trace(go.Scatter(
            x=node_x, y=node_y, mode='markers+text',
            marker=dict(size=[s*0.5+20 for s in scores_adj], color=node_colors,
                       line=dict(width=3, color='white')),
            text=categories_net, textposition='middle center',
            textfont=dict(size=12, color='white', family='Arial Black'),
            hovertext=[f"<b>{c}</b><br>Score: {s:.1f}" for c, s in zip(categories_net, scores_adj)],
            hoverinfo='text', showlegend=False
        ))

        fig_net.add_trace(go.Scatter(x=[None], y=[None], mode='lines',
                                      line=dict(width=4, color='green'), name='Synergy (+)'))
        fig_net.add_trace(go.Scatter(x=[None], y=[None], mode='lines',
                                      line=dict(width=4, color='red'), name='Trade-off (-)'))

        fig_net.update_layout(
            title='Cross-Category Interaction Network',
            xaxis=dict(showgrid=False, showticklabels=False, zeroline=False, range=[-1.5, 1.5]),
            yaxis=dict(showgrid=False, showticklabels=False, zeroline=False, range=[-1.5, 1.5]),
            plot_bgcolor='#f8f9fa', paper_bgcolor='white', height=700,
            showlegend=True, legend=dict(x=0.02, y=0.98)
        )
        fig_net.add_annotation(
            text=f"<b>Stats</b><br>Synergy: {results['total_synergy']:.2f}<br>"
                 f"Trade-off: {results['total_tradeoff']:.2f}<br>Ratio: {results['synergy_ratio']:.2f}",
            xref="paper", yref="paper", x=0.98, y=0.02, xanchor='right', yanchor='bottom',
            showarrow=False, bgcolor='rgba(255,255,255,0.9)', bordercolor='black', borderwidth=1
        )
        st.plotly_chart(fig_net, use_container_width=True)


# ═══════════════════════════════════════════════════════════════
# TAB 10: ABOUT & METHODOLOGY
# ═══════════════════════════════════════════════════════════════
with TABS['about']:
    st.markdown("""
### 📖 Assessment Methodology

---

#### 1. LIFE CYCLE ASSESSMENT (LCA)
- **ISO 14040:2006** — Environmental Management Framework
- **ISO 14044:2006** — LCA Requirements and Guidelines
- **Functional Unit:** 1 passenger-kilometer over 50-year lifecycle
- **System Boundary (currently implemented):** A1-A3 materials + A4 transport + **optional A5 construction** + **activity-based B2-B5** + active B6 operation + **optional C1-C4 end-of-life**. Module D is reported separately (supplementary).

#### 2. LIFE CYCLE COST ANALYSIS (LCCA)
- **ASTM E917** — Standard Practice for Measuring Life-Cycle Costs
- **Net Present Value (NPV)** methodology
- 50-year economic assessment period

#### 3. DASHBOARD DISPLAY SCORE (non-scientific)
- Dashboard-only visualization score — **NOT** a sustainability index.
- It is not used as an ISO LCA/LCCA result.
- Scientific conclusions must be taken from the LCA and NPV-LCCA outputs only.
- Computed in `calculate_dashboard_display_scores()`, kept separate from the scientific core (`calculate_core_lca_lcc()`).

| Category | Weight | Key Components |
|---|---|---|
| Material Efficiency | 25% | 6 materials + recycling bonuses |
| Environmental | 30% | CO₂, renewable (display-only), land use, noise |
| Operational | 25% | Time savings, availability, energy efficiency |
| Economic | 20% | Jobs, lifecycle cost, economic multiplier |

#### 3b. SYSTEM DYNAMICS LAYER (Phase 2 — B6 only)
Phase 2 introduces a scenario-based system dynamics layer for B6 operational emissions.
The model represents asset condition as a stock **C(t)**, degraded by annual deterioration and
improved by delayed maintenance recovery. The condition stock feeds back into operational energy
intensity **EI(t)** and therefore annual B6 emissions. The SD parameters are scenario assumptions
unless calibrated using asset inspection, maintenance, or measured energy data.

```
dC/dt = MR(t) − DR(t)
DR_t  = min(δ, C_t)                 (constant annual degradation, capped)
MR_t  = ρ · m_(t−τ)                 (delayed maintenance recovery, capped to C ≤ 1)
EI_t  = EI₀ · [1 + α·(1 − C_t)]     (condition → energy intensity)
B6_dyn = Σ_t  EI_t · PKM_t · CI_t / 1000      (CI_t = grid only, no renewable)
```

#### 3c. MODULAR GROSS A1–C4 LCA (Phase 3A–3C)
The model reports a **gross modular A1–C4 LCA** built from separate modules:
`gross = A1–A3 + A4 + A5 + B2–B5 + B6_active + C1–C4`. Each stage is independently
toggleable; the **functional unit (kg CO₂e/pkm) uses the gross figure (never net)**.
Module D (recycling credit) is **always reported separately** as supplementary
information (`net = gross − Module D`) and is never merged into gross.

- **A5 (Phase 3A):** construction diesel + site electricity + material-waste production
  (BOQ installed/purchased mode prevents double counting) + waste transport + treatment.
- **B2–B5 (Phase 3B):** activity-based maintenance/replacement. B2 is linked to the SD
  maintenance schedule (no 'free maintenance'); B4 replacement uses a mass balance so removed
  material is handled in B4 and is **not re-counted** in C1–C4. LCCA maintenance mode
  (simple_annual vs activity_based) prevents double counting; B4 cost is added in both modes.
- **C1–C4 + Module D (Phase 3C):** end-of-life on the **remaining** masses (after B4/B5),
  with per-material treatment shares that must sum to 1. C3 processing is an **emission**
  (not a credit); recovery credits go to **Module D only**.

```
treatment shares:  s_reuse + s_recycle + s_disposal = 1   (per material)
I_C1 = [ Σ F_(f,C1) EF_f + E_C1 · CI_T ] / 1000
I_C2 = Σ_j [ (M_(j,EOL)/1000) · D · EF_tr ] / 1000
I_C3 = [ Σ_j M_(j,EOL) ( s_reuse·EF_reuse + s_recycle·EF_recycle ) ] / 1000
I_C4 = [ Σ_j M_(j,EOL) · s_disposal · EF_disposal ] / 1000
I_C1-C4 = I_C1 + I_C2 + I_C3 + I_C4
Module D = Σ_j [ M_(j,EOL)(s_reuse+s_recycle) · η_j · (EF_virgin − EF_secondary) ] / 1000   (separate)
```

All A5/B2–B5/C1–C4/Module-D factors and quantities are **scenario / user inputs**;
results are not 'validated' unless calibrated with project data. `publication_grade_full_lca`
is False if FRP lacks an EPD, if any material's treatment shares do not sum to 1, or if
Module D is reported with a missing secondary factor.

#### 3d. COMPONENT-BASED MONTE CARLO (Phase 4)
A statistical layer on top of the A1–C4 model — it changes **no** LCA equation. Each
uncertain input is sampled from its own distribution (lognormal for EFs/positive
quantities, triangular for distances, Dirichlet for treatment shares, etc.) via Latin
Hypercube sampling, and the full model is re-run, so uncertainty propagates **per
component**. The model identities hold in **every** draw:

```
θ_k ~ P(θ)
I_gross,k = I_A1-A3,k + I_A4,k + I_A5,k + I_B2-B5,k + I_B6,k + I_C1-C4,k
GWP_pkm,k = 1000 · I_gross,k / PKM_k
I_net,k   = I_gross,k − I_D,k        (Module D propagated separately, never in gross)
95% uncertainty interval = [P2.5(Y), P97.5(Y)]
```

Outputs: per-stage and metric percentiles, Spearman tornado (drivers), and convergence
diagnostics. `publication_grade_uncertainty` is True only if the full LCA is
publication-grade, the registry is complete, n ≥ 5000, and convergence is reached. The
legacy total-scaling MC is retained as **illustrative only** and is never publication-grade.
Reported ranges are **scenario-based uncertainty intervals**, not measured statistical
confidence intervals.

#### 3e. SUSTAINABILITY INDEX (Phase 5 — hybrid CRITIC–Entropy)
The Sustainability Index is a **decision-support composite index** derived from a scenario-year
matrix (n ≥ 30 for publication-grade). It **does not replace** the reported LCA/LCCA/uncertainty
outputs, and is **not** the legacy Dashboard Display Score. Indicators are non-overlapping (no gross
together with its own sub-stages); `net_with_module_d` is **never** an environmental indicator
(Module D enters only as a separate circularity ratio). Indicators are normalized with **target-based**
functions, weighted with a **hybrid Entropy–CRITIC** method, and aggregated additively (hierarchical
by pillar). Core LCA/LCCA results remain reported separately.

```
z_ij = f(x_ij) ∈ [0,1]            (target-based; higher- or lower-better)
wE  = entropy weights;  wC = CRITIC weights
w_j = λ·wE_j + (1−λ)·wC_j         (default λ = 0.5; λ-sensitivity reported)
S_(i,g) = Σ_{j∈g} (w_j|g) z_ij    (pillar score)
SI_i = Σ_g W_g · S_(i,g) ∈ [0,1]  (W: Environmental .35, Economic .25, Operational .25, Social .15)
```

`publication_grade_si` is True only if the full LCA AND Phase 4 uncertainty are publication-grade,
n_scenarios ≥ 30, indicator metadata/targets are complete, weights sum to 1, and λ-sensitivity is
computed. Reported as decision support — **not** a validation claim.

The methodology is now complete: **Gross modular A1–C4 LCA + NPV-LCCA + component-based uncertainty
+ scientific decision-support SI (CRITIC–Entropy)**. The model is **not** described as a *validated*
cradle-to-grave model unless external project calibration/verification data are later added.

#### 4. ILLUSTRATIVE INTERACTION VISUALIZATION
- The interaction network is used only for dashboard visualization.
- The coefficients are heuristic display parameters.
- They are not validated causal effects and are not part of the core LCA/LCCA results.
- SDG interaction literature is used only as conceptual background, not as a numerical source for the coefficients.

#### 5. BENCHMARK / REPRODUCTION CHECK
- **Li and Zhu (2022)** — Computational Intelligence and Neuroscience
- DOI: [10.1155/2022/3872069](https://doi.org/10.1155/2022/3872069)
- Used only as an external benchmark comparison; no Li & Zhu calibration factors are used in the core model.

---

#### SCIENTIFIC REFERENCES

1. ISO 14040:2006 — Environmental Management — Life Cycle Assessment
2. ISO 14044:2006 — Environmental Management — Life Cycle Assessment — Requirements and Guidelines
3. ASTM E917-17 — Standard Practice for Measuring Life-Cycle Costs
4. Li and Zhu (2022). Monorail transit life-cycle carbon assessment (benchmark). *Computational Intelligence and Neuroscience*, 2022, 3872069. DOI: 10.1155/2022/3872069. [confirm exact title from PDF]
5. Nilsson, M., et al. (2016). "Mapping interactions between SDGs." *Nature*, 534, 320-322. Used as conceptual background only.

---

#### DATA SOURCE HIERARCHY (per material, most-specific first)
1. **Project BOQ** quantities (user input)
2. **Local / product-specific EPD** — highest evidence; use if available
3. **ICE Database Educational V4.1 (Oct 2025)**, "ICE Summary" sheet — generic A1-A3 carbon factors
4. **Li and Zhu (2022)** — benchmark comparison ONLY; never a factor source

#### DATA SOURCES
- **Material embodied carbon (PRIMARY):** ICE Database Educational V4.1 (Oct 2025), ICE Summary sheet, A1-A3 Embodied Carbon. Each factor carries its exact `ice_name`, `dqi_score`, boundary and status in the MATERIAL_FACTOR_AUDIT table.
- **Material embodied energy (SECONDARY):** legacy Hammond & Jones (2008) / ICE v2.0 values — explicitly **not** from ICE V4.1; reported as a secondary indicator only.
- **FRP / GRP:** **UNVERIFIED placeholder** — ICE V4.1 has no published A1-A3 carbon value; a product-specific EPD is required before publication.
- **Glass mass:** geometric — area × thickness (mm) × 2.5 kg/(mm·m²) (flat-glass 2500 kg/m³).
- **Module D (recycling credit):** computed per EN 15804 and reported **separately**; it is **not** netted into A1-A3 and **not** added to the A1-C4 total.
- **Operational electricity carbon:** User-defined grid carbon intensity applied directly to B6 (Phase 1b). Renewable share is NOT applied to the core to avoid double-counting the grid mix; it is dashboard-only and deferred to Phase 2.
- **LCCA:** User-defined construction, maintenance, energy cost, residual value, and discount rate.
- **Transport A4:** Scenario-based ton-km calculation using user-selected mode and transport distance.
- **Synthetic visualizations:** Pareto, 12-element, and urban analytics tabs are illustrative only and not part of the scientific LCA/LCCA results.

---

#### HOW TO CITE

```
[Your Name]. (2025). Enhanced Monorail LCA/LCCA Assessment Tool:
Gross modular A1-C4 LCA and NPV-based LCCA Framework with Scenario-based Sensitivity Analysis.
Cairo University. Software version 2.0.
```

```bibtex
@software{monorail_lca_2025,
  author = {[Your Name]},
  title = {Enhanced Monorail LCA/LCCA Assessment Tool: Gross modular A1-C4 LCA and NPV-based LCCA Framework},
  year = {2025},
  institution = {Cairo University},
  version = {2.0}
}
```
    """)


# ═══════════════════════════════════════════════════════════════
# TAB 11: SYSTEM DYNAMICS (B6) — Phase 2
# ═══════════════════════════════════════════════════════════════
with TABS['sd']:
    st.markdown("### 🔧 System Dynamics — Asset Condition C(t) → Dynamic B6")
    st.warning(
        "Scenario-based system dynamics layer. Parameters (δ, ρ, τ, α, C₀, g) are "
        "**scenario assumptions — NOT validated** unless calibrated with asset inspection, "
        "maintenance, or measured operational-energy data. Renewable share is NOT used here."
    )
    if not results.get('sd_enabled'):
        st.info("ℹ️ Dynamic B6 is **previewed below but not applied to the headline result**. "
                "Tick *Enable dynamic B6* in the sidebar to activate it as the active result.")

    sp = results['sd_params']
    st.caption(f"Parameters — C₀={sp['C0']}, δ={sp['delta']}, interval={sp['interval']} yr, "
               f"ρ={sp['rho']}, τ={sp['tau']} yr, α={sp['alpha']}, g={sp['g_pct']:.1f}%/yr, "
               f"T={ASSESSMENT_LIFETIME_YEARS} yr (dC/dt = MR − DR).")

    sdm1, sdm2, sdm3, sdm4 = st.columns(4)
    with sdm1: st.metric("Final condition C(T)", f"{results['sd_final_condition']:.3f}")
    with sdm2: st.metric("Minimum condition", f"{results['sd_min_condition']:.3f}")
    with sdm3: st.metric("Average EI", f"{results['sd_average_EI']:.4f} kWh/pkm")
    with sdm4: st.metric("Base EI₀", f"{results['energy_per_pax_km']:.4f} kWh/pkm")

    sdb1, sdb2, sdb3, sdb4 = st.columns(4)
    with sdb1: st.metric("Static B6 (t CO₂e)", f"{results['b6_static_tons']:,.0f}")
    with sdb2: st.metric("Dynamic B6 (t CO₂e)", f"{results['b6_dynamic_tons']:,.0f}",
                         delta=f"{results['delta_b6_tons']:+,.0f}")
    with sdb3: st.metric("Dynamic total LCA (t)", f"{results['total_lifecycle_co2_dynamic']:,.0f}")
    with sdb4: st.metric("Dynamic kg CO₂e/pkm", f"{results['co2_kg_per_pkm_dynamic']:.5f}")

    sd_df = pd.DataFrame(results['sd_rows'])
    b6_df = pd.DataFrame(results['sd_b6']['yearly'])

    c_left, c_right = st.columns(2)
    with c_left:
        fig_c = go.Figure()
        fig_c.add_trace(go.Scatter(x=sd_df['year'], y=sd_df['C_end'], mode='lines+markers',
                                   line=dict(color='#64ffda', width=2), name='C(t)'))
        fig_c.update_layout(title='Asset Condition C(t)', height=360,
                            plot_bgcolor='rgba(10,25,47,0.8)', paper_bgcolor='rgba(0,0,0,0)',
                            font_color='#ccd6f6', yaxis_range=[0, 1.05],
                            xaxis_title='Year', yaxis_title='Condition (0–1)', margin=dict(t=40, b=30))
        st.plotly_chart(fig_c, use_container_width=True)
    with c_right:
        fig_ei = go.Figure()
        fig_ei.add_trace(go.Scatter(x=b6_df['year'], y=b6_df['EI_t'], mode='lines+markers',
                                    line=dict(color='#f7971e', width=2), name='EI(t)'))
        fig_ei.add_hline(y=results['energy_per_pax_km'], line_dash="dash", line_color="#6495ed")
        fig_ei.update_layout(title='Dynamic Energy Intensity EI(t)', height=360,
                             plot_bgcolor='rgba(10,25,47,0.8)', paper_bgcolor='rgba(0,0,0,0)',
                             font_color='#ccd6f6', xaxis_title='Year', yaxis_title='kWh/pkm',
                             margin=dict(t=40, b=30))
        st.plotly_chart(fig_ei, use_container_width=True)

    d_left, d_right = st.columns(2)
    with d_left:
        fig_b6 = go.Figure()
        fig_b6.add_trace(go.Bar(x=b6_df['year'], y=b6_df['B6_co2_tons'],
                                marker_color='rgba(235,51,73,0.6)', name='Annual B6'))
        fig_b6.update_layout(title='Annual Dynamic B6 (t CO₂e/yr)', height=360,
                             plot_bgcolor='rgba(10,25,47,0.8)', paper_bgcolor='rgba(0,0,0,0)',
                             font_color='#ccd6f6', xaxis_title='Year', yaxis_title='t CO₂e/yr',
                             margin=dict(t=40, b=30))
        st.plotly_chart(fig_b6, use_container_width=True)
    with d_right:
        fig_cmp = go.Figure(go.Bar(
            x=['Static B6', 'Dynamic B6'],
            y=[results['b6_static_tons'], results['b6_dynamic_tons']],
            marker_color=['#6495ed', '#64ffda'],
            text=[f"{results['b6_static_tons']:,.0f}", f"{results['b6_dynamic_tons']:,.0f}"],
            textposition='outside'))
        fig_cmp.update_layout(title='Static vs Dynamic B6 (lifetime)', height=360,
                              plot_bgcolor='rgba(10,25,47,0.8)', paper_bgcolor='rgba(0,0,0,0)',
                              font_color='#ccd6f6', yaxis_title='t CO₂e', margin=dict(t=40, b=40))
        st.plotly_chart(fig_cmp, use_container_width=True)

    with st.expander("📋 Yearly System Dynamics table", expanded=False):
        st.dataframe(sd_df, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════
# TAB 12: SUSTAINABILITY INDEX (Phase 5)
# ═══════════════════════════════════════════════════════════════
with TABS['si']:
    st.markdown("### 🏁 Scientific Sustainability Index — hybrid CRITIC–Entropy")
    st.caption("A **decision-support composite index** over a scenario-year matrix. It does NOT replace the "
               "reported gross A1–C4 LCA, GWP/pkm, Module D, LCCA or Monte Carlo uncertainty, and is NOT the "
               "legacy Dashboard Display Score. Indicators are non-overlapping; net-with-Module-D is never an "
               "environmental indicator (Module D enters only as a separate circularity ratio).")

    sic1, sic2, sic3 = st.columns(3)
    with sic1:
        si_enable = st.checkbox("Enable Phase 5 SI", value=False, key="si_enable")
        si_n = st.number_input("n scenarios", value=36, min_value=5, max_value=200, step=2, key="si_n")
    with sic2:
        si_lambda = st.slider("λ (Entropy ↔ CRITIC)", 0.0, 1.0, 0.5, 0.05, key="si_lambda")
        si_critic = st.selectbox("CRITIC correlation", ["pearson", "spearman"], index=0, key="si_critic")
    with sic3:
        si_unc_n = st.number_input("Per-scenario MC (0=skip robustness)", value=0, min_value=0, max_value=2000, step=100, key="si_unc_n")
        si_pgu = st.checkbox("Manual confirmation: Phase 4 uncertainty is publication-grade",
                             value=bool(st.session_state.get('phase4_pgu', False)), key="si_pgu",
                             help="Auto-filled from the last Phase 4 MC run (n≥5000 + convergence). Override only if confirmed independently.")

    si_source = st.selectbox("Scenario-year matrix source",
                             ["generated_demo (synthetic — not publication-grade)", "documented", "uploaded (CSV)"],
                             index=0, key="si_source")
    si_source_key = {'generated_demo (synthetic — not publication-grade)': 'generated_demo',
                     'documented': 'documented', 'uploaded (CSV)': 'uploaded'}[si_source]
    si_uploaded_df = None
    if si_source_key == 'uploaded':
        up = st.file_uploader("Upload scenario-year matrix CSV (scenario_id, year, indicator columns)", type=['csv'], key="si_csv")
        if up is not None:
            try:
                si_uploaded_df = pd.read_csv(up)
                st.success(f"Loaded uploaded matrix: {len(si_uploaded_df)} scenarios.")
            except Exception as _e:
                st.error(f"Could not read CSV: {_e}")

    if si_enable:
        def _run_si(bp, n, lam, method, unc_n, pgu, source, uploaded, seed):
            scs = generate_default_scenarios(bp, n=int(n), seed=int(seed))
            return run_phase5_si(scs, bp, lam=float(lam), critic_method=method,
                                 uncertainty_n=int(unc_n), publication_grade_uncertainty=bool(pgu),
                                 seed=int(seed), scenario_source=source, uploaded_matrix=uploaded)
        si = _run_si(dict(params), si_n, si_lambda, si_critic, si_unc_n, si_pgu, si_source_key, si_uploaded_df, 42)

        st.warning("SI is a **decision-support composite index**, not a validation claim. "
                   "Targets are scenario/literature values; intervals/weights are data-driven on the chosen matrix.")
        if si['validation']['errors']:
            st.error("Indicator matrix invalid: " + "; ".join(si['validation']['errors']))
        for w in si['warnings']:
            st.caption("ℹ️ " + w)
        flag = si['publication_grade_si']
        (st.success if flag else st.warning)(
            f"publication_grade_si = {flag} · n_scenarios = {si['n_scenarios']} · λ = {si['lambda']} · "
            f"λ-rank stability (Spearman) = {si['lambda_sensitivity']['rank_stability_spearman']:.3f}"
            + ("" if flag else " — requires full-LCA + Phase 4 publication-grade + n≥30."))

        st.markdown("#### 🏆 Ranked scenarios")
        rk = si['ranked_scenarios'][['rank', 'scenario_id', 'year', 'SI', 'SI_100']].copy()
        rk['SI'] = rk['SI'].map(lambda v: f"{v:.3f}"); rk['SI_100'] = rk['SI_100'].map(lambda v: f"{v:.1f}")
        st.dataframe(rk, use_container_width=True, hide_index=True)

        cA, cB = st.columns(2)
        with cA:
            top = si['ranked_scenarios'].head(15)
            figr = go.Figure(go.Bar(x=top['SI'], y=top['scenario_id'], orientation='h',
                                    marker_color='rgba(100,255,218,0.7)'))
            figr.update_layout(title='Top scenarios by SI', height=460, paper_bgcolor='rgba(0,0,0,0)',
                               plot_bgcolor='rgba(10,25,47,0.8)', font_color='#ccd6f6',
                               yaxis=dict(autorange='reversed'), margin=dict(t=40, b=30))
            st.plotly_chart(figr, use_container_width=True)
        with cB:
            pillars = list(si['pillar_weights'].keys())
            ps = si['pillar_scores']
            present = [p for p in pillars if p in ps.columns]
            figrad = go.Figure()
            for _, rr in si['ranked_scenarios'].head(3).iterrows():
                idx = rr['rank'] - 1
                vals = [ps.iloc[si['raw_matrix'].index[si['raw_matrix']['scenario_id'] == rr['scenario_id']][0]][p] for p in present]
                figrad.add_trace(go.Scatterpolar(r=vals + [vals[0]], theta=present + [present[0]],
                                                 fill='toself', name=rr['scenario_id']))
            figrad.update_layout(title='Pillar radar — top 3', height=460, paper_bgcolor='rgba(0,0,0,0)',
                                 polar=dict(radialaxis=dict(range=[0, 1])), font_color='#ccd6f6', margin=dict(t=40, b=30))
            st.plotly_chart(figrad, use_container_width=True)

        st.markdown("#### ⚖️ Weights (Entropy / CRITIC / Hybrid)")
        st.dataframe(si['weights_table'].round(4), use_container_width=True, hide_index=True)

        cC, cD = st.columns(2)
        with cC:
            figh = go.Figure(data=go.Heatmap(z=si['normalized_matrix'].to_numpy(),
                                             x=list(si['normalized_matrix'].columns),
                                             y=si['raw_matrix']['scenario_id'].tolist(),
                                             colorscale='Viridis'))
            figh.update_layout(title='Normalized indicators (0–1)', height=520, paper_bgcolor='rgba(0,0,0,0)',
                               font_color='#ccd6f6', margin=dict(t=40, b=30))
            st.plotly_chart(figh, use_container_width=True)
        with cD:
            lam_tab = si['lambda_sensitivity']['table']
            figl = go.Figure()
            for col in lam_tab.columns:
                figl.add_trace(go.Scatter(y=lam_tab[col].to_numpy(), mode='lines', name=col, opacity=0.5))
            figl.update_layout(title='λ sensitivity (SI per scenario)', height=520, paper_bgcolor='rgba(0,0,0,0)',
                               plot_bgcolor='rgba(10,25,47,0.8)', font_color='#ccd6f6',
                               xaxis_title='scenario index', yaxis_title='SI', margin=dict(t=40, b=30))
            st.plotly_chart(figl, use_container_width=True)

        with st.expander("🔎 SI audit table (inclusion / groups / targets)", expanded=False):
            st.dataframe(si['audit'].round(4), use_container_width=True, hide_index=True)

        d1, d2 = st.columns(2)
        with d1:
            st.download_button("📥 Download SI ranking (CSV)", si['ranked_scenarios'].to_csv(index=False),
                               file_name=f"si_ranking_{datetime.now().strftime('%Y%m%d')}.csv")
        with d2:
            si_xl = io.BytesIO()
            with pd.ExcelWriter(si_xl, engine='openpyxl') as wr:
                si['raw_matrix'].to_excel(wr, sheet_name='raw_matrix', index=False)
                si['normalized_matrix'].to_excel(wr, sheet_name='normalized', index=False)
                si['weights_table'].to_excel(wr, sheet_name='weights', index=False)
                si['ranked_scenarios'].to_excel(wr, sheet_name='SI_ranking', index=False)
                si['audit'].to_excel(wr, sheet_name='audit', index=False)
            st.download_button("📥 Download SI workbook (Excel)", si_xl.getvalue(),
                               file_name=f"si_workbook_{datetime.now().strftime('%Y%m%d')}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ═══════════════════════════════════════════════════════════════
# FOOTER
# ═══════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown(
    f"<div style='text-align:center; color:#8892b0; font-size:0.85rem;'>"
    f"🚝 Enhanced Monorail LCA/LCCA Assessment Tool v2.0 | "
    f"Cairo University | ISO 14040/14044 + ASTM E917 | "
    f"Last run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    f"</div>", unsafe_allow_html=True
)
