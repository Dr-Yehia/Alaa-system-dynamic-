"""Societal co-benefit KPIs — a domain that is deliberately SEPARATE from LCA and LCC.

ARCHITECTURAL CONTRACT
----------------------
Benefits are reported ALONGSIDE the environmental and economic results, never inside
them:

  * a benefit NEVER reduces Gross A-C carbon;
  * a benefit NEVER reduces LCC_NPV;
  * this module imports neither the LCA engines nor the LCC engines, and neither of
    them imports this module.

Combining costs and benefits into a single figure is a Cost-Benefit Analysis, which is
a different study type with its own conventions. If that is wanted later it belongs in
a separately named CBA module that consumes all three domain results — it must not be
smuggled in by letting a benefit offset a cost or an emission here.

Extracted verbatim from app_final_streamlit_ready.py during the architectural
separation. The equations, defaults and units are unchanged.
"""

from __future__ import annotations

from project_context import ASSESSMENT_LIFETIME_YEARS


def calculate_benefit_kpis(params, annual_pkm, lifetime_years=ASSESSMENT_LIFETIME_YEARS):
    """R15: SEPARATE societal co-benefit KPIs. These are reported ALONGSIDE the LCA
    and are NEVER subtracted from gross or net LCA carbon. Every KPI is a documented
    equation rather than a hand-entered figure. All defaults are 0 → no co-benefit
    claimed unless inputs are supplied."""
    # 1) Operational CO2 avoided vs a displaced baseline mode (car/bus), per pkm.
    ef_base = float(params.get('benefit_baseline_ci_pkm', 0.0))            # kgCO2e/pkm displaced mode
    ef_mono = float(params.get('energy_per_pax', 0.0)) * float(params.get('carbon_intensity', 0.0))  # kgCO2e/pkm monorail B6
    annual_co2_avoided_t = max(ef_base - ef_mono, 0.0) * annual_pkm / 1000.0
    lifetime_co2_avoided_t = annual_co2_avoided_t * lifetime_years

    # 2) Time saving + value of time saved (VoTS).
    annual_trips = float(params.get('benefit_annual_trips', 0.0))          # trips/yr
    dt_min = float(params.get('benefit_time_saved_min', 0.0))             # minutes saved per trip vs baseline
    annual_hours_saved = annual_trips * dt_min / 60.0
    vot = float(params.get('benefit_value_of_time', 0.0))                 # $/h
    annual_vots_m = annual_hours_saved * vot / 1e6
    lifetime_vots_m = annual_vots_m * lifetime_years

    # 3) Jobs supported (capex-driven construction jobs + operational jobs).
    capex = float(params.get('construction_cost', 0.0))                   # $M
    jobs_construction = float(params.get('benefit_jobs_per_musd', 0.0)) * capex
    jobs_operational = float(params.get('benefit_operational_jobs', 0.0))
    total_jobs = jobs_construction + jobs_operational

    # 4) Economic impact (output multiplier on capital investment).
    economic_impact_m = capex * float(params.get('economic_multiplier', 1.0))

    # 5) Land-use efficiency (project footprint per million pkm/yr).
    land_ha = float(params.get('benefit_land_ha', 0.0))
    land_ha_per_mpkm = (land_ha / (annual_pkm / 1e6)) if annual_pkm > 0 else float('nan')

    # 6) Noise reduction ratio vs baseline mode.
    n_base = float(params.get('benefit_noise_baseline_db', 0.0))
    n_mono = float(params.get('benefit_noise_monorail_db', 0.0))
    noise_reduction_db = n_base - n_mono
    noise_reduction_ratio = (noise_reduction_db / n_base) if n_base > 0 else 0.0

    return {
        'note': 'Co-benefits reported SEPARATELY (EN 15804 module-independent); never netted into LCA gross/net.',
        'annual_co2_avoided_tons': annual_co2_avoided_t,
        'lifetime_co2_avoided_tons': lifetime_co2_avoided_t,
        'baseline_ci_pkm': ef_base, 'monorail_ci_pkm': ef_mono,
        'annual_hours_saved': annual_hours_saved,
        'annual_vots_musd': annual_vots_m, 'lifetime_vots_musd': lifetime_vots_m,
        'jobs_construction': jobs_construction, 'jobs_operational': jobs_operational,
        'total_jobs': total_jobs, 'economic_impact_musd': economic_impact_m,
        'land_ha_per_million_pkm': land_ha_per_mpkm,
        'noise_reduction_db': noise_reduction_db, 'noise_reduction_ratio': noise_reduction_ratio,
    }