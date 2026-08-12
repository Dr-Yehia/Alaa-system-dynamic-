"""LEGACY-DEVELOPER-ONLY environmental engine — the LCA domain's legacy half.

ARCHITECTURAL CONTRACT
----------------------
This is the environmental counterpart of `legacy_lcc_engine.py`. It exists so the
developer dashboard and the historical regression suites keep working while the frozen
referenced engines (`lca_scientific_core` + `lca_scientific_integration` +
`lca_scientific_reporting`) remain the ONLY publication path.

Rules:
  * it computes carbon and energy only — no money, no benefits;
  * it does not import the LCC engines or benefits_core, and neither imports it;
  * Publication-mode LCA never routes through here.

WHY calculate_dynamic_b6 LIVES HERE AND NOT IN system_dynamics_core
-------------------------------------------------------------------
System Dynamics is a neutral state/activity producer shared by every domain. But
`calculate_dynamic_b6()` accepts a grid carbon intensity and returns B6_co2_tons /
b6_dynamic_tons, which is LCA carbon. Leaving it in the shared layer would have parked
a piece of the environmental domain inside neutral territory, so it belongs here.
The condition trajectory it consumes still comes from `system_dynamics_core`, which
remains carbon-free: SD produces state, this module turns state into carbon.

Moved verbatim during the architectural separation; no equation, factor, default or
unit was changed.
"""

from __future__ import annotations

import math

import numpy as np

from monorail_assessment.common.project_context import ASSESSMENT_LIFETIME_YEARS
from monorail_assessment.common.shared_activity import build_shared_activity
from monorail_assessment.common.system_dynamics import simulate_asset_condition


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
# LEGACY-DEVELOPER-ONLY / NOT-CANONICAL-SCIENTIFIC-LCA.
# Numerical values below are benchmark/scenario/backward-compatibility values.
# They MUST NOT feed Publication-mode LCA. Where a primary source is not fully
# verified, status remains SCENARIO-ONLY or SOURCE-OPEN — never fabricate provenance.
# Superseded by lca_scientific_core.MATERIAL_EF, which carries full provenance.
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


# LEGACY-DEVELOPER-ONLY / NOT-CANONICAL-SCIENTIFIC-LCA.
# Numerical values below are benchmark/scenario/backward-compatibility values.
# They MUST NOT feed Publication-mode LCA. Where a primary source is not fully
# verified, status remains SCENARIO-ONLY or SOURCE-OPEN — never fabricate provenance.
# SCENARIO-ONLY recycling-credit fractions. These are NOT Module D and must never be
# surfaced as scientific Module D in Publication mode.
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


# ═══════════════════════════════════════════════════════════════
# A4 TRANSPORT FACTOR REGISTRY — every mode carries unit / boundary /
# vehicle / energy scope / source / status (like MATERIAL_FACTORS).
# Values are scenario/defaults. Do NOT silently change the truck EF (e.g. to
# 0.062) without a documented source, unit, boundary, vehicle class and a
# stated WTW/TTW scope — otherwise the result is not publication-grade.
# ═══════════════════════════════════════════════════════════════
# LEGACY-DEVELOPER-ONLY / NOT-CANONICAL-SCIENTIFIC-LCA.
# Numerical values below are benchmark/scenario/backward-compatibility values.
# They MUST NOT feed Publication-mode LCA. Where a primary source is not fully
# verified, status remains SCENARIO-ONLY or SOURCE-OPEN — never fabricate provenance.
# Superseded by lca_scientific_core.TRANSPORT_EF (sourced DESNZ 2025 rows).
TRANSPORT_FACTOR_REGISTRY = {
    "truck": {
        "ef_kgco2e_per_tkm": 0.10, "unit": "kgCO2e/tonne-km",
        "vehicle": "generic road HGV (payload unspecified)", "energy_scope": "TTW (tank-to-wheel)",
        "boundary": "A4 transport (gate-to-site)",
        "source": "scenario/default — replace with documented local factor (source, vehicle, payload, WTW/TTW) before publication",
        "status": "scenario/default",
    },
    "rail": {
        "ef_kgco2e_per_tkm": 0.03, "unit": "kgCO2e/tonne-km",
        "vehicle": "generic freight rail", "energy_scope": "TTW (tank-to-wheel)",
        "boundary": "A4 transport (gate-to-site)",
        "source": "scenario/default — replace with documented local factor before publication",
        "status": "scenario/default",
    },
    "ship": {
        "ef_kgco2e_per_tkm": 0.015, "unit": "kgCO2e/tonne-km",
        "vehicle": "generic bulk/cargo vessel", "energy_scope": "TTW (tank-to-wheel)",
        "boundary": "A4 transport (gate-to-site)",
        "source": "scenario/default — replace with documented local factor before publication",
        "status": "scenario/default",
    },
}


# Backward-compatible flat view (EF only) used by the simple A4 path.
TRANSPORT_EMISSION_FACTORS = {k: v["ef_kgco2e_per_tkm"] for k, v in TRANSPORT_FACTOR_REGISTRY.items()}


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


def calculate_a4_transport_co2(material_masses_kg, distance_km, mode, advanced_legs=None):
    """A4 transport emissions (tonnes CO2e), reported separately from A1-A3.

    Simple mode:   I_A4 = (Σ M_j / 1000) · D · EF_mode / 1000
    Advanced mode: I_A4 = ΣΣ_legs (M_j / 1000) · D_jm · EF_m / 1000

    `advanced_legs` (when given) is a list of dicts with keys
    {material, mass_kg, distance_km, mode, ef}. A per-leg `ef` (kgCO2e/tonne-km)
    overrides the registry; if None/blank/non-finite the mode's registry EF is used.
    Mass is converted kg→tonne, distance is tonne-km, EF is kgCO2e/tonne-km, and
    the final /1000 converts kgCO2e→tonnes CO2e.
    """
    if advanced_legs:
        total = 0.0
        for leg in advanced_legs:
            m_kg = float(leg.get('mass_kg', 0.0) or 0.0)
            d = float(leg.get('distance_km', 0.0) or 0.0)
            lm = leg.get('mode', 'truck')
            ef = leg.get('ef', None)
            if ef is None or not np.isfinite(float(ef)) or float(ef) <= 0.0:
                ef = TRANSPORT_FACTOR_REGISTRY.get(lm, TRANSPORT_FACTOR_REGISTRY["truck"])["ef_kgco2e_per_tkm"]
            total += (m_kg / 1000.0) * d * float(ef) / 1000.0
        return total
    ef = TRANSPORT_FACTOR_REGISTRY.get(mode, TRANSPORT_FACTOR_REGISTRY["truck"])["ef_kgco2e_per_tkm"]
    total_mass_tons = sum(material_masses_kg.values()) / 1000.0
    return total_mass_tons * distance_km * ef / 1000.0


def calculate_lca_summary(embodied_co2_tons, annual_operational_co2_tons, embodied_energy_mj,
                          annual_operational_energy_kwh, daily_pax_km, lifetime_years,
                          a4_transport_co2_tons=0.0,
                          module_d_carbon_credit_tons=0.0, module_d_energy_credit_mj=0.0,
                          lifetime_operational_co2_tons_override=None):
    # R8-CI: when a CI_t-trajectory lifetime is supplied, use it instead of the flat
    # annual×years product (the two coincide when CI_t is constant → baseline unchanged).
    if lifetime_operational_co2_tons_override is not None:
        lifetime_operational_co2_tons = lifetime_operational_co2_tons_override
    else:
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


# Map core mass keys -> MATERIAL_FACTORS keys (for reusing A1-A3 carbon factors)
MATERIAL_KEY_MAP = {
    'concrete': 'concrete_32_40', 'steel': 'steel_section', 'aluminum': 'aluminum_general',
    'wood': 'wood_general', 'frp': 'frp_general', 'glass': 'glass_primary',
}


def compute_effective_ef(virgin_ef, recycled_content, secondary_ef):
    """R6 / EN 15804 recycled-content as an *effective* A1-A3 emission factor.

        EF_eff = (1 - RC)·EF_virgin + RC·EF_secondary

    Applied ONLY when BOTH a recycled-content fraction (RC > 0) AND a documented
    secondary (recycled-route) EF are supplied. Otherwise the virgin EF is used
    unchanged — recycled content is NOT credited inside A1-A3, because the
    end-of-life recovery benefit is reported separately in Module D (EN 15804).
    Keeping the two mechanisms mutually exclusive prevents double counting.

    Returns (ef_effective, applied: bool).
    """
    rc = float(recycled_content or 0.0)
    if rc <= 0.0 or secondary_ef is None or not np.isfinite(float(secondary_ef)):
        return float(virgin_ef), False
    rc = min(max(rc, 0.0), 1.0)
    return float((1.0 - rc) * float(virgin_ef) + rc * float(secondary_ef)), True


def calculate_a5_diesel_equipment(equipment_list, diesel_ef):
    """R9 equipment-based A5 diesel (mutually exclusive with the simple total-litres mode):

        L = Σ_i  N_i · FC_i · LF_i · CCF_i · H_i · D_i / (1 - PL_i)
        CO2 = L · EF_diesel               [kgCO2e → tonnes]

    N number of units, FC rated fuel consumption (L/h), LF load factor, CCF climate
    correction factor (WBGT-driven — scenario unless calibrated), H hours/day, D days,
    PL productivity-loss fraction (heat-stress downtime). Returns (tonnes CO2e, litres).
    """
    total_l = 0.0
    for e in (equipment_list or []):
        N = float(e.get('N', 0.0) or 0.0); FC = float(e.get('FC', 0.0) or 0.0)
        LF = float(e.get('LF', 1.0) or 0.0); CCF = float(e.get('CCF', 1.0) or 0.0)
        H = float(e.get('H', 0.0) or 0.0); D = float(e.get('D', 0.0) or 0.0)
        PL = float(e.get('PL', 0.0) or 0.0)
        denom = (1.0 - PL) if PL < 1.0 else 1.0
        total_l += N * FC * LF * CCF * H * D / denom
    return total_l * float(diesel_ef) / 1000.0, total_l


def validate_a5_treatment_shares(shares):
    """R10: per-material A5 waste treatment shares reuse + recycle + landfill = 1.
    `shares` is a dict material -> {reuse, recycle, landfill}. Returns valid flag,
    errors and a normalised view (landfill defaults to 1 - reuse - recycle)."""
    errors, table, valid = [], [], True
    for mat, s in (shares or {}).items():
        reuse = float(s.get('reuse', 0.0)); recycle = float(s.get('recycle', 0.0))
        landfill = float(s.get('landfill', 1.0 - reuse - recycle))
        total = reuse + recycle + landfill
        ok = (reuse >= 0 and recycle >= 0 and landfill >= -1e-9 and abs(total - 1.0) <= 1e-6)
        if not ok:
            valid = False
            errors.append(f"{mat}: reuse+recycle+landfill = {total:.3f} ≠ 1")
        table.append({'material': mat, 'reuse': reuse, 'recycle': recycle,
                      'landfill': max(landfill, 0.0), 'sum': total})
    return {'valid': valid, 'errors': errors, 'share_table': table}


def calculate_a5_construction(masses_kg, params, CI0):
    """A5 construction/installation emissions (tCO2e), reported SEPARATELY from A4.

    Diesel (R9): mutually-exclusive simple (total litres) OR equipment-based fleet.
    Waste (R10): per-material waste rates w_j, per-material treatment shares
    (reuse+recycle+landfill=1) and per-material transport/treatment routes.
    BOQ mode prevents double counting of material-production waste:
      - 'installed' : core masses are installed quantities; extra purchased waste
                      W_j = M_j·w_j/(1-w_j) is produced and its A1-A3 production IS added here.
      - 'purchased' : core masses are purchased quantities; production already in A1-A3,
                      so NO production term is added (W_j = M_j·w_j; only transport + treatment).
    """
    if not params.get('include_a5', False):
        return {'included': False, 'a5_total_tons': 0.0, 'a5_fuel_tons': 0.0,
                'a5_electricity_tons': 0.0, 'a5_material_waste_tons': 0.0,
                'a5_waste_transport_tons': 0.0, 'a5_waste_treatment_tons': 0.0,
                'waste_mass_total_kg': 0.0, 'a5_diesel_mode': 'simple', 'a5_diesel_litres': 0.0,
                'a5_waste_by_material': [], 'a5_treatment_shares_valid': True}

    mode = params.get('a5_boq_mode', 'installed')
    w_global = float(params.get('a5_waste_rate', 0.0))
    waste_rates = params.get('a5_waste_rates') or {}
    treat_shares = params.get('a5_treatment_shares') or {}
    routes = params.get('a5_waste_routes') or {}
    truck_ef = TRANSPORT_EMISSION_FACTORS['truck']

    diesel_ef = params.get('a5_diesel_ef', FUEL_FACTORS['diesel']['ef_kgco2e_per_l'])
    # R9: simple total-litres mode vs equipment-fleet mode (mutually exclusive).
    diesel_mode = params.get('a5_diesel_mode', 'simple')
    if diesel_mode == 'equipment':
        diesel_t, diesel_l = calculate_a5_diesel_equipment(params.get('a5_equipment', []), diesel_ef)
    else:
        diesel_l = float(params.get('a5_diesel_l', 0.0))
        diesel_t = diesel_l * diesel_ef / 1000.0
    elec_t = params.get('a5_elec_kwh', 0.0) * CI0 / 1000.0

    shares_valid = validate_a5_treatment_shares(treat_shares)['valid'] if treat_shares else True

    waste_prod_kg = 0.0
    waste_transport_kgco2 = 0.0
    waste_treatment_kgco2 = 0.0
    waste_mass_total_kg = 0.0
    by_material = []
    for mat, M in masses_kg.items():
        w_j = float(waste_rates.get(mat, w_global))
        if mode == 'installed':
            Wj = M * (w_j / (1.0 - w_j)) if 0.0 <= w_j < 1.0 else 0.0
            # Production of the EXTRA waste is NOT yet in A1-A3 (which used installed mass)
            prod = Wj * MATERIAL_FACTORS[MATERIAL_KEY_MAP[mat]]['gwp_kgco2e_per_kg'] * params.get(f'unc_ef_mult_{mat}', 1.0)
            waste_prod_kg += prod
        else:  # purchased: production already counted in A1-A3 -> no production term
            Wj = M * w_j
        route = routes.get(mat, {})
        t_km = float(route.get('transport_km', params.get('a5_waste_transport_km', 0.0)))
        t_ef = float(route.get('transport_ef', truck_ef))
        trans = (Wj / 1000.0) * t_km * t_ef  # kgCO2e
        # Treatment: per-material shares × per-route EFs, else a single per-material/global EF.
        s = treat_shares.get(mat)
        if s:
            reuse = float(s.get('reuse', 0.0)); recycle = float(s.get('recycle', 0.0))
            landfill = float(s.get('landfill', 1.0 - reuse - recycle))
            treat_ef = (reuse * float(route.get('ef_reuse', 0.0))
                        + recycle * float(route.get('ef_recycle', 0.0))
                        + landfill * float(route.get('ef_landfill', params.get('a5_waste_treatment_ef', 0.0))))
        else:
            treat_ef = float(route.get('treatment_ef', params.get('a5_waste_treatment_ef', 0.0)))
        treat = Wj * treat_ef  # kgCO2e
        waste_transport_kgco2 += trans
        waste_treatment_kgco2 += treat
        waste_mass_total_kg += Wj
        by_material.append({'material': mat, 'waste_rate': w_j, 'waste_kg': Wj,
                            'transport_tco2': trans / 1000.0, 'treatment_tco2': treat / 1000.0})

    waste_prod_t = waste_prod_kg / 1000.0
    waste_transport_t = waste_transport_kgco2 / 1000.0
    waste_treatment_t = waste_treatment_kgco2 / 1000.0

    a5_total = diesel_t + elec_t + waste_prod_t + waste_transport_t + waste_treatment_t
    return {'included': True, 'a5_total_tons': a5_total, 'a5_fuel_tons': diesel_t,
            'a5_electricity_tons': elec_t, 'a5_material_waste_tons': waste_prod_t,
            'a5_waste_transport_tons': waste_transport_t, 'a5_waste_treatment_tons': waste_treatment_t,
            'waste_mass_total_kg': waste_mass_total_kg, 'a5_diesel_mode': diesel_mode,
            'a5_diesel_litres': diesel_l, 'a5_waste_by_material': by_material,
            'a5_treatment_shares_valid': shares_valid}


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
    # R24: B4 replacement is now per material. A b4_table {material: {replacement_fraction,
    # waste_ef, transport_km}} covers every material; if absent, fall back to the legacy
    # steel/concrete fractions so existing scenarios are unchanged.
    b4_table = params.get('b4_table')
    if not b4_table:
        b4_table = {
            'steel': {'replacement_fraction': params.get('b4_frac_steel', 0.0),
                      'waste_ef': params.get('b4_waste_ef', 0.0), 'transport_km': params.get('b4_transport_km', 0.0)},
            'concrete': {'replacement_fraction': params.get('b4_frac_concrete', 0.0),
                         'waste_ef': params.get('b4_waste_ef', 0.0), 'transport_km': params.get('b4_transport_km', 0.0)},
        }
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
        # B4 replacement (like-for-like): new material production + removed-material waste,
        # summed over every material in the per-material B4 table.
        b4_kg = 0.0
        if row['B4_count']:
            new_mat = waste_treat = waste_trans = 0.0
            for _mat, _spec in b4_table.items():
                frac = float(_spec.get('replacement_fraction', 0.0) or 0.0)
                if frac <= 0.0 or _mat not in masses_kg:
                    continue
                r_j = frac * masses_kg.get(_mat, 0.0)
                ef_j = MATERIAL_FACTORS[MATERIAL_KEY_MAP[_mat]]['gwp_kgco2e_per_kg'] * params.get(f'unc_ef_mult_{_mat}', 1.0)
                new_mat += r_j * ef_j
                waste_treat += r_j * float(_spec.get('waste_ef', 0.0) or 0.0)
                waste_trans += (r_j / 1000.0) * float(_spec.get('transport_km', 0.0) or 0.0) * truck_ef
                added[_mat] += row['B4_count'] * r_j
                removed[_mat] += row['B4_count'] * r_j
            b4_kg = row['B4_count'] * (new_mat + waste_treat + waste_trans)
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


# LEGACY-DEVELOPER-ONLY / NOT-CANONICAL-SCIENTIFIC-LCA.
# Numerical values below are benchmark/scenario/backward-compatibility values.
# They MUST NOT feed Publication-mode LCA. Where a primary source is not fully
# verified, status remains SCENARIO-ONLY or SOURCE-OPEN — never fabricate provenance.
# The corrected scientific C1-C4 implementation lives ONLY in lca_scientific_core.py /
# lca_scientific_integration.py. Do NOT 'fix' this function — doing so would create a
# second, competing scientific implementation.
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
    # R25: per-material / per-mode C2 routes. c2_routes maps material → list of legs
    # [{mode, distance_km, ef, share}]; C2 = ΣΣ (M_j·share/1000)·D_jm·EF_m / 1000.
    # If a material has no route, the single legacy distance × truck EF is used.
    c2_routes = params.get('c2_routes') or {}
    c2 = c3 = c4 = 0.0
    rows = []
    for m in materials:
        M = remaining_masses.get(m, 0.0)
        reuse = params.get(f'eol_reuse_{m}', 0.0)
        recycle = params.get(f'eol_recycle_{m}', 0.0)
        disposal = max(1.0 - reuse - recycle, 0.0)
        legs = c2_routes.get(m)
        if legs:
            c2_m = 0.0
            for leg in legs:
                d = float(leg.get('distance_km', 0.0) or 0.0)
                sh = float(leg.get('share', 1.0) or 0.0)
                ef = float(leg.get('ef', 0.0) or 0.0)
                if ef <= 0.0:
                    ef = TRANSPORT_FACTOR_REGISTRY.get(leg.get('mode', 'truck'),
                                                       TRANSPORT_FACTOR_REGISTRY['truck'])['ef_kgco2e_per_tkm']
                c2_m += (M * sh / 1000.0) * d * ef / 1000.0
        else:
            c2_m = (M / 1000.0) * km * truck_ef / 1000.0
        c3_m = M * (reuse * reuse_ef + recycle * recycle_ef) / 1000.0
        c4_m = M * disposal * disposal_ef / 1000.0
        c2 += c2_m; c3 += c3_m; c4 += c4_m
        rows.append({'material': m, 'remaining_kg': M, 'reuse': reuse, 'recycle': recycle,
                     'disposal': disposal, 'C2_tCO2e': c2_m, 'C3_tCO2e': c3_m, 'C4_tCO2e': c4_m})
    return {'included': True, 'c1_tons': c1, 'c2_tons': c2, 'c3_tons': c3, 'c4_tons': c4,
            'c1_c4_total_tons': c1 + c2 + c3 + c4, 'eol_by_material': rows}


# LEGACY-DEVELOPER-ONLY / NOT-CANONICAL-SCIENTIFIC-LCA.
# Numerical values below are benchmark/scenario/backward-compatibility values.
# They MUST NOT feed Publication-mode LCA. Where a primary source is not fully
# verified, status remains SCENARIO-ONLY or SOURCE-OPEN — never fabricate provenance.
# The corrected RICS Appendix K / EN 15804 Module D1 lives ONLY in lca_scientific_core.py.
# Do NOT 'fix' this legacy credit function — the standard-signed equation has exactly one
# implementation, and it is not here.
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


def b6_ci_trajectory(ci_grid0, grid_change_pct, years,
                     project_renewable=False, r_proj0=0.0, r_proj_change_pct=0.0, ci_renewable=0.0):
    """R8-CI: annual grid carbon-intensity trajectory (kgCO2e/kWh).

    CI_grid,t = CI_grid,0 · (1 + g_grid)^(t-1)

    Renewable is applied ONLY as explicit *project* procurement:
        CI_eff,t = (1 - r_proj,t)·CI_grid,t + r_proj,t·CI_renewable,t
    Without project procurement r_proj,t = 0 and CI_eff,t = CI_grid,t — the
    (1 - renewable_share) grid shortcut is never used.
    """
    traj = []
    for t in range(1, int(years) + 1):
        ci_grid_t = ci_grid0 * (1.0 + grid_change_pct / 100.0) ** (t - 1)
        if project_renewable:
            r_t = min(max(r_proj0 * (1.0 + r_proj_change_pct / 100.0) ** (t - 1), 0.0), 1.0)
            ci_eff = (1.0 - r_t) * ci_grid_t + r_t * ci_renewable
        else:
            r_t = 0.0
            ci_eff = ci_grid_t
        traj.append({'year': t, 'ci_grid': ci_grid_t, 'r_proj': r_t, 'ci_eff': ci_eff})
    return traj


def b6_served_annual_pkm(params):
    """R11: served annual passenger-km.

    - 'pkm_direct' (default): annual PKM = daily_pax_km · 365 (unchanged baseline).
    - 'daily'/'annual' demand basis: served passengers are capped by capacity,
        served = min(Demand, Capacity);
      PKM = served · avg_trip_km · availability  (×365 if the demand is daily).
    Returns (annual_pkm, meta).
    """
    basis = params.get('b6_demand_basis', 'pkm_direct')
    avail = float(params.get('availability', 100.0)) / 100.0
    if basis == 'pkm_direct':
        # R22: availability now scales delivered service in pkm_direct too, so the
        # operating fraction is applied consistently in every B6 demand mode.
        annual_pkm = params['daily_pax_km'] * 1000 * 365 * avail
        return annual_pkm, {'basis': basis, 'availability': avail}
    demand = float(params.get('b6_demand', 0.0))
    capacity = float(params.get('b6_capacity', 0.0))
    served = min(demand, capacity) if capacity > 0 else demand
    trip = float(params.get('b6_avg_trip_km', 0.0))
    pkm = served * trip * avail
    if basis == 'daily':
        pkm *= 365.0
    return pkm, {'basis': basis, 'demand': demand, 'capacity': capacity, 'served': served,
                 'avg_trip_km': trip, 'availability': avail, 'capacity_binding': capacity > 0 and demand > capacity}


def calculate_legacy_lca(params):
    """LEGACY environmental result — LCA ONLY.

    Returns ``(lca_result, shared_activity)``.

    This function computes carbon and energy and NOTHING else. It prices no cash flow
    and values no co-benefit, so it imports neither the LCC engine nor benefits_core.
    What it does produce is the NEUTRAL activity record the other domains need —
    served PKM, annual kWh, the dated intervention schedule and the scope flags —
    which `assessment_orchestrator` passes on to them.

    The combined dashboard dictionary the legacy UI expects is assembled by the
    orchestrator, not here: assembling all three domains is exactly the job this
    module must not do.
    """
    """LEGACY-DEVELOPER dashboard result set — NOT the Publication path.

    Formerly `calculate_core_lca_lcc()`. The name was the clearest symptom of the
    problem: one function owning both domains. It no longer contains any economic or
    benefit equation — those are delegated across the neutral activity boundary to
    `legacy_lcc_engine` and `benefits_core`. What remains is the legacy environmental
    computation plus assembly of the historical result dictionary the dashboard and the
    regression suites expect.

    Publication-mode LCA comes from the frozen scientific engines; Publication-mode LCC
    will come from `lcc_scientific_core`. Neither routes through here.
    """
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
    a4_mode = params.get("a4_mode", "simple")
    a4_legs = params.get("a4_advanced_legs") if a4_mode == "advanced" else None
    a4_transport_co2_tons = calculate_a4_transport_co2(
        material_masses_kg, params.get("transport_distance_km", 0.0),
        params.get("transport_mode", "truck"), advanced_legs=a4_legs)

    # Operational Energy & Carbon (B6)
    energy_per_pax_km = params['energy_per_pax']
    carbon_intensity = params['carbon_intensity']
    renewable_share = params['renewable_share']  # dashboard-only (see note)

    # R11: served annual PKM (demand capped by capacity, availability applied).
    # 'pkm_direct' default reproduces the legacy daily_pax_km·365 figure exactly.
    annual_pkm, b6_demand_meta = b6_served_annual_pkm(params)
    daily_pax_km = annual_pkm / 365.0  # effective daily PKM (keeps downstream semantics)
    annual_operational_energy = energy_per_pax_km * annual_pkm

    # R8-CI: annual grid carbon-intensity trajectory. Renewable enters ONLY as explicit
    # project procurement (CI_eff,t = (1-r)·CI_grid,t + r·CI_renewable,t); the grid
    # carbon intensity already reflects the grid mix, so no (1-renewable_share) shortcut.
    ci_trajectory = b6_ci_trajectory(
        carbon_intensity, params.get('b6_grid_change_pct', 0.0), ASSESSMENT_LIFETIME_YEARS,
        project_renewable=bool(params.get('b6_project_renewable', False)),
        r_proj0=float(params.get('b6_renewable_share_proj', 0.0)) / 100.0,
        r_proj_change_pct=float(params.get('b6_renewable_change_pct', 0.0)),
        ci_renewable=float(params.get('b6_ci_renewable', 0.0)))
    effective_carbon_intensity = ci_trajectory[0]['ci_eff']
    operational_carbon_intensity = energy_per_pax_km * effective_carbon_intensity
    annual_co2_operational = operational_carbon_intensity * annual_pkm / 1000
    # Lifetime B6 CO2 via the CI_t trajectory (Σ_t energy·CI_eff,t). With flat defaults
    # this equals annual_co2_operational · lifetime, so the baseline is unchanged.
    lifetime_b6_co2_traj = sum(energy_per_pax_km * annual_pkm * y['ci_eff'] for y in ci_trajectory) / 1000.0
    # NOTE: the B6 energy PRESENT VALUE used to be computed here. It is money, so it
    # moved to legacy_lcc_engine.calculate_legacy_lcc(); only the kWh crosses the
    # domain boundary now. See the DOMAIN BOUNDARY block below.

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
    # R6 recycled content → effective A1-A3 EF (EN 15804). Per material, the virgin
    # ICE V4.1 factor is replaced by EF_eff = (1-RC)·EF_virgin + RC·EF_secondary ONLY
    # when both a recycled-content fraction and a documented secondary EF are supplied;
    # otherwise the virgin factor is used and recycled content is left to Module D.
    _virgin_ef = {m: MATERIAL_FACTORS[MATERIAL_KEY_MAP[m]]['gwp_kgco2e_per_kg']
                  for m in ('concrete', 'steel', 'aluminum', 'wood', 'frp', 'glass')}
    eff_ef, rc_applied, rc_fraction = {}, {}, {}
    rc_basis_conflict = False
    for m in ('concrete', 'steel', 'aluminum', 'wood', 'frp', 'glass'):
        rc = params.get(f'recycled_content_{m}', 0.0)
        sec = params.get(f'ef_secondary_{m}', None)
        # P1/R27: the recycled-content substitution is valid ONLY on a virgin EF basis.
        # A market-average factor already embeds recycled/scrap content, so applying RC
        # again would double-count → block the adjustment and flag not publication-grade.
        basis = params.get(f'factor_basis_{m}', 'virgin')
        if basis != 'virgin' and float(rc or 0.0) > 0.0:
            sec = None
            rc_basis_conflict = True
        e, applied = compute_effective_ef(_virgin_ef[m], rc, sec)
        eff_ef[m], rc_applied[m], rc_fraction[m] = e, applied, (float(rc or 0.0) if applied else 0.0)
    carbon_concrete = concrete_kg * eff_ef['concrete'] * ef_mult['concrete']
    carbon_steel = steel_kg * eff_ef['steel'] * ef_mult['steel']
    carbon_aluminum = aluminum_kg * eff_ef['aluminum'] * ef_mult['aluminum']
    carbon_wood = wood_kg * eff_ef['wood'] * ef_mult['wood']
    carbon_frp = frp_kg * eff_ef['frp'] * ef_mult['frp']
    carbon_glass = glass_kg * eff_ef['glass'] * ef_mult['glass']

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
        module_d_energy_credit_mj=module_d_energy_credit_mj,
        lifetime_operational_co2_tons_override=lifetime_b6_co2_traj
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
    # publication_grade_full_lca: False if FRP lacks EPD, shares don't sum to 1,
    # Module D is reported with a missing secondary factor, or a recycled-content
    # secondary EF was supplied without a source (R27).
    recycled_secondary_ok = bool(params.get('recycled_secondary_documented_ok', True))
    publication_grade_full_lca = bool(publication_grade and shares_ok and module_d_ok
                                      and recycled_secondary_ok and not rc_basis_conflict)

    # NEUTRAL ACTIVITY handed to the other domains. Only physical facts cross this
    # line: no carbon result leaves, and no price enters.
    _shared = build_shared_activity(
        served_annual_pkm=annual_pkm,
        lifetime_pkm=annual_pkm * ASSESSMENT_LIFETIME_YEARS,
        annual_operational_kwh=annual_operational_energy,
        schedule_rows=b2b5_schedule,
        use_stage_included=b2b5['included'],
        end_of_life_included=include_c1c4,
    )
    return {
        'total_co2': total_co2,
        'annual_co2_operational': annual_co2_operational,
        'total_embodied_co2': total_embodied_co2,
        'total_embodied_co2_excl_frp': total_embodied_co2_excl_frp,
        'publication_grade': publication_grade,
        'recycled_content_applied': rc_applied,
        'recycled_content_fraction': rc_fraction,
        'recycled_basis_conflict': rc_basis_conflict,
        'effective_a1a3_ef': eff_ef,
        'virgin_a1a3_ef': _virgin_ef,
        'module_d_carbon_credit_tons': module_d_carbon_credit_tons,
        'module_d_energy_credit_mj': module_d_energy_credit_mj,
        'effective_carbon_intensity': effective_carbon_intensity,
        'total_ee': total_ee,
        'annual_operational_energy': annual_operational_energy,
        'concrete_volume': concrete_m3,
        'steel_mass': steel_kg,
        'aluminum_mass': aluminum_kg,
        'steel_tons': steel_tons,
        'aluminum_tons': aluminum_tons,
        'frp_tons': frp_tons,
        'energy_per_pax_km': energy_per_pax_km,
        'operational_carbon_intensity': operational_carbon_intensity,
        'daily_pax_km': daily_pax_km,
        'steel_recycle_rate': steel_recycle_rate * 100,
        'aluminum_recycle_rate': aluminum_recycle_rate * 100,
        'renewable_share': renewable_share,
        'noise_reduction': params['noise_reduction'],
        'land_use_efficiency': params['land_use'],
        'lca_results': lca_results,
        'total_lifecycle_co2': lca_results['total_lifecycle_co2_tons'],
        'co2_kg_per_pkm': lca_results['co2_kg_per_pkm'],
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
        # ── R15: societal co-benefit KPIs (separate; never netted into LCA) ──
        # ── R11 / R8-CI: static B6 demand basis, CI_t trajectory, energy-cost PV ──
        'b6_demand_meta': b6_demand_meta,
        'b6_annual_pkm': annual_pkm,
        'b6_ci_trajectory': ci_trajectory,
        'b6_lifetime_co2_traj_tons': lifetime_b6_co2_traj,
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
    }, _shared
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