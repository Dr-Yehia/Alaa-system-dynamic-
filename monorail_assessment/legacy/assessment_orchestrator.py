"""The single assembly point for the three independent assessment domains.

ARCHITECTURAL ROLE
------------------
                project_context  +  shared_activity        (neutral facts)
                        |                  |
              +---------+---------+--------+--------+
              |                   |                 |
             LCA                 LCC            BENEFITS     (independent domains)
              |                   |                 |
              +---------+---------+--------+--------+
                                  |
                    assessment_orchestrator  <-- this module
                                  |
                                 UI

This module CALLS the domains and COLLECTS their results. It deliberately contains no
scientific equation of any kind: no emission factor, no present value, no valuation.
If an equation ever appears here, the separation has been undone, because the
orchestrator is the one place that can see all three domains at once.

The domains do not know about each other. They know only about the neutral layers.
`tests/domain_dependency_test.py` enforces that mechanically.

INPUT SLICING
-------------
The UI may still gather one wide dictionary, but each engine receives only its own
slice. `split_params()` performs that cut, so no engine can read another domain's
fields even by accident.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from monorail_assessment.common.project_context import ProjectContext, context_from_params


# ── EXPLICIT domain ownership ─────────────────────────────────────────────────
# Every key is classified deliberately. There is NO "unknown key is neutral" rule:
# that policy silently leaked `carbon_intensity` into the LCC slice and left the real
# `benefit_*` fields visible to every domain. An unclassified key is now reported by
# `unclassified_params()` and fails tests/params_classification_test.py instead of
# quietly crossing a boundary.

# Environmental inputs — quantities, factors, grid, stage toggles.
LCA_PARAM_KEYS = {
    "concrete", "steel", "aluminum", "wood", "frp", "glass", "glass_thickness",
    "steel_recycle", "aluminum_recycle", "energy_per_pax", "carbon_intensity",
    "renewable_share", "daily_pax_km", "include_a5", "include_b2b5", "include_c1c4",
    "enable_b4", "sd_enable", "grid_decarb_rate", "grid_ci_mode", "grid_ci_series",
    "a5_diesel_l", "a5_waste_rates", "a5_treatment_shares", "a5_waste_transport_km",
    "transport_distance_km", "transport_mode", "eol_reuse", "eol_recycle",
    "eol_recovery_eta", "eol_secondary_ef", "b2_interval", "b4_interval",
    "b2_material_kg", "b4_material_kg", "demand_growth_pct", "capacity_pax_day",
    "availability_pct", "trip_length_km",

    "a4_advanced_legs",
    "a4_empty_return_factor",
    "a4_load_factor",
    "a4_mode",
    "a4_number_of_trips",
    "a4_payload_assumption",
    "a4_return_factor_unit",
    "a4_return_fraction",
    "a4_return_justification",
    "a4_return_source_file",
    "a4_return_source_location",
    "a4_route_source",
    "a4_scope",
    "a4_vehicle_capacity",
    "a5_boq_mode",
    "a5_component_declarations",
    "a5_construction_year",
    "a5_diesel_ef",
    "a5_diesel_mode",
    "a5_diesel_scope",
    "a5_diesel_source",
    "a5_elec_kwh",
    "a5_electricity_source",
    "a5_equipment",
    "a5_predemolition_note",
    "a5_predemolition_status",
    "a5_waste_rate",
    "a5_waste_route_source",
    "a5_waste_routes",
    "a5_waste_source",
    "a5_waste_treatment_ef",
    "a5_worker_transport_status",
    "availability",
    "b2_diesel_l",
    "b2_elec_kwh",
    "b2_material_pct",
    "b2_transport_km",
    "b2_use_sd_schedule",
    "b2b5_event_rows",
    "b2b5_module_declarations",
    "b4_frac_concrete",
    "b4_frac_steel",
    "b4_table",
    "b4_transport_km",
    "b4_waste_ef",
    "b4_years",
    "b6_annual_service_rows",
    "b6_avg_trip_km",
    "b6_capacity",
    "b6_ci_renewable",
    "b6_constant_operating_days",
    "b6_demand",
    "b6_demand_basis",
    "b6_grid_change_pct",
    "b6_project_renewable",
    "b6_renewable_change_pct",
    "b6_renewable_share_proj",
    "b6_service_mode",
    "boq_source",
    "c1_diesel_l",
    "c1_diesel_source",
    "c1_elec_kwh",
    "c1_electricity_source",
    "c1c4_rows",
    "c2_routes",
    "concrete_density_kg_m3",
    "concrete_density_source",
    "ef_secondary_aluminum",
    "ef_secondary_concrete",
    "ef_secondary_frp",
    "ef_secondary_glass",
    "ef_secondary_source_aluminum",
    "ef_secondary_source_concrete",
    "ef_secondary_source_frp",
    "ef_secondary_source_glass",
    "ef_secondary_source_steel",
    "ef_secondary_source_wood",
    "ef_secondary_steel",
    "ef_secondary_wood",
    "energy_intensity_choice",
    "eol_disposal_ef",
    "eol_recycle_aluminum",
    "eol_recycle_concrete",
    "eol_recycle_ef",
    "eol_recycle_frp",
    "eol_recycle_glass",
    "eol_recycle_steel",
    "eol_recycle_wood",
    "eol_reuse_aluminum",
    "eol_reuse_concrete",
    "eol_reuse_ef",
    "eol_reuse_frp",
    "eol_reuse_glass",
    "eol_reuse_steel",
    "eol_reuse_wood",
    "eol_secondary_ef_aluminum",
    "eol_secondary_ef_concrete",
    "eol_secondary_ef_frp",
    "eol_secondary_ef_glass",
    "eol_secondary_ef_steel",
    "eol_secondary_ef_wood",
    "eol_transport_km",
    "factor_basis_aluminum",
    "factor_basis_concrete",
    "factor_basis_frp",
    "factor_basis_glass",
    "factor_basis_steel",
    "factor_basis_wood",
    "glass_density_kg_m3",
    "glass_density_source",
    "glass_thickness_mm",
    "grid_annual_duplicate_years",
    "grid_annual_invalid_years",
    "grid_annual_series",
    "grid_generation",
    "grid_location",
    "grid_mode",
    "grid_source",
    "grid_td",
    "grid_upstream",
    "material_epd_overrides",
    "module_d_rows",
    "project_ei",
    "project_ei_source",
    "recycled_content_aluminum",
    "recycled_content_concrete",
    "recycled_content_frp",
    "recycled_content_glass",
    "recycled_content_steel",
    "recycled_content_wood",
    "recycled_secondary_documented_ok",
    "recycling_scenario",
    "ridership_source",
    "route_length_km",
    "sd_C0",
    "sd_alpha",
    "sd_delta",
    "sd_growth_pct",
    "sd_maint_interval",
    "sd_rho",
    "sd_tau",
    "wood_density_kg_m3",
    "wood_density_source",
}

# Economic inputs — money, timing, rates.
LCC_PARAM_KEYS = {
    "construction_cost", "contract_factor", "maintenance_cost", "discount_rate",
    "annual_energy_cost", "residual_value", "eol_cost_m", "b2_cost_per_event_m",
    "b4_cost_per_event_m", "lcca_maint_mode", "b6_energy_tariff",
    "b6_energy_escalation_pct", "price_year", "price_base_year", "currency",
    "lcc_analysis_base_year", "lcc_analysis_period_years", "lcc_currency",
    "lcc_discount_basis", "lcc_discount_rate", "lcc_discount_source_file",
    "lcc_discount_source_location", "lcc_cost_rows", "lcc_residual_rows",
}

# Societal co-benefit inputs — the ACTUAL field names the app collects.
BENEFITS_PARAM_KEYS = {
    "benefit_annual_trips", "benefit_time_saved_min", "benefit_value_of_time",
    "benefit_jobs_per_musd", "benefit_operational_jobs", "benefit_land_ha",
    "benefit_noise_baseline_db", "benefit_noise_monorail_db",
    "benefit_baseline_ci_pkm", "benefit_source",
    "jobs_created", "economic_multiplier",

    "land_use",
    "noise_reduction",
    "time_savings",

    # The scientific Benefits evidence tree. ONE nested key rather than a hundred
    # flat ones, so the parameter dictionary does not grow a scientific vocabulary
    # that the other two domains would then have to ignore by name. Benefits-only
    # on purpose: nothing inside it is meaningful to LCA or LCC.
    "benefits_scientific_inputs",
}

# Inputs legitimately needed by MORE THAN ONE domain. These are declared shared on
# purpose — that is different from leakage, because the sharing is explicit and tested.
# `construction_cost` is the clearest case: it drives the LCC capital flow AND the
# Benefits construction-jobs KPI, so Benefits must receive it deliberately.
MULTI_DOMAIN_PARAM_KEYS = {
    "construction_cost": ("lcc", "benefits"),
    "daily_pax_km": ("lca", "benefits"),
    "assessment_lifetime": ("lca", "lcc", "benefits"),
    "analysis_start_year": ("lca", "lcc", "benefits"),
    "energy_per_pax": ("lca", "benefits"),
    "carbon_intensity": ("lca", "benefits"),
}

# Project identity/context — safe for everyone, carries no domain semantics.
CONTEXT_PARAM_KEYS = {
    "project_name", "project_id", "country", "region", "functional_unit",
    "publication_mode", "show_legacy", "assessment_lifetime", "analysis_start_year",

    "assessment_lifetime_source",
}


@dataclass(frozen=True)
class AssessmentResult:
    """The three domain results, side by side and never merged.

    They are kept as separate attributes on purpose: there is no combined headline
    number here, because combining a cost with a benefit is a Cost-Benefit Analysis and
    combining a cost with carbon is not meaningful at all.
    """

    context: ProjectContext
    lca: Any = None
    lcc: Any = None
    benefits: Any = None
    shared: Any = None
    notes: dict = field(default_factory=dict)


def _slice_for(params: dict, domain: str) -> dict:
    """Keys this domain owns, plus keys explicitly declared multi-domain, plus context."""
    owned = {"lca": LCA_PARAM_KEYS, "lcc": LCC_PARAM_KEYS,
             "benefits": BENEFITS_PARAM_KEYS}[domain]
    out = {}
    for k, v in params.items():
        if k in CONTEXT_PARAM_KEYS:
            out[k] = v
        elif k in MULTI_DOMAIN_PARAM_KEYS and domain in MULTI_DOMAIN_PARAM_KEYS[k]:
            out[k] = v
        elif k in owned and k not in MULTI_DOMAIN_PARAM_KEYS:
            out[k] = v
    return out


def unclassified_params(params: dict) -> list:
    """Keys that belong to no declared set.

    Under the previous "unknown key is neutral" policy these were handed to every
    domain, which is how an emission factor could reach the LCC slice. They are now
    surfaced so a reviewer must classify them deliberately.
    """
    known = (LCA_PARAM_KEYS | LCC_PARAM_KEYS | BENEFITS_PARAM_KEYS
             | set(MULTI_DOMAIN_PARAM_KEYS) | CONTEXT_PARAM_KEYS)
    return sorted(k for k in (params or {}) if k not in known)


def split_params(params: dict) -> dict:
    """Cut one wide UI dictionary into per-domain input slices.

    Returns ``{"context", "lca_inputs", "lcc_inputs", "benefits_inputs",
    "shared_inputs", "unclassified"}``.

    A key reaches a domain only if that domain OWNS it, or it is declared multi-domain
    for that domain, or it is project context. Nothing arrives by default. This is what
    makes "the LCC slice cannot read an emission factor" a fact rather than a hope.
    """
    params = dict(params or {})
    return {
        "context": context_from_params(params),
        "lca_inputs": _slice_for(params, "lca"),
        "lcc_inputs": _slice_for(params, "lcc"),
        "benefits_inputs": _slice_for(params, "benefits"),
        "shared_inputs": {k: v for k, v in params.items() if k in CONTEXT_PARAM_KEYS},
        "unclassified": unclassified_params(params),
    }


def run_assessment(params: dict) -> AssessmentResult:
    """Run the three domains INDEPENDENTLY and collect their separate results.

    This is the real execution point. The order is dictated by data, not by hierarchy:
    the environmental engine is what currently derives the physical activity series, so
    it runs first and yields the NEUTRAL `SharedActivity`. The economic engine then
    prices that activity, and Benefits values it — neither ever receives an LCA result.

    `result.lca` is an LCA-ONLY dictionary: it contains no NPV, no cost and no jobs.
    """
    from monorail_assessment.legacy.lca_engine import calculate_legacy_lca
    from monorail_assessment.legacy.lcc_engine import calculate_legacy_lcc
    from monorail_assessment.legacy.benefits_core import calculate_benefit_kpis, calculate_legacy_jobs

    params = dict(params or {})
    context = context_from_params(params)

    # 1) Environmental domain -> LCA-only result + neutral activity.
    lca_result, shared = calculate_legacy_lca(params)

    # 2) Economic domain -> money, from NEUTRAL ACTIVITY only.
    lcc_result = calculate_legacy_lcc(params, shared)

    # 3) Benefits domain -> co-benefits, valued independently.
    # `kpis` is the KPI table (it carries its own employment figure); `legacy_jobs` is
    # the separate dashboard jobs scalar. They are kept as distinct sub-results so the
    # combined view can reproduce both without either overwriting the other.
    kpis = dict(calculate_benefit_kpis(params, shared.served_annual_pkm))
    legacy_jobs = calculate_legacy_jobs(params)
    benefits_result = {"kpis": kpis, **legacy_jobs}

    return AssessmentResult(
        context=context,
        lca=lca_result,
        lcc=lcc_result,
        benefits=benefits_result,
        shared=shared,
        notes={"unclassified_params": unclassified_params(params)},
    )


def assemble_legacy_dashboard_results(result: AssessmentResult) -> dict:
    """Flatten an already-computed AssessmentResult into the legacy dashboard shape.

    Split out from `calculate_legacy_dashboard_results` so that a caller which
    already holds an AssessmentResult can reuse it instead of triggering a second
    full domain run. The assembly is pure dictionary work: no engine is called
    and no arithmetic is performed beyond the unit conversions the legacy
    dashboard has always carried.
    """
    combined = dict(result.lca)
    combined.update(result.lcc)
    combined["npv_lcc_m"] = result.lcc["lcc_results"]["npv_lcc_m"]
    combined["total_cost"] = result.lcc["lcc_results"]["npv_lcc_m"] * 1e6
    combined["benefit_kpis"] = result.benefits["kpis"]
    combined["jobs_created"] = result.benefits["jobs_created"]
    combined["economic_multiplier"] = result.benefits["economic_multiplier"]
    combined["total_jobs"] = result.benefits["total_jobs"]
    return combined


def calculate_legacy_dashboard_results(params: dict) -> dict:
    """Backward-compatible combined dictionary, ASSEMBLED from the separate domains.

    The historical dashboard and the regression suites expect one flat dictionary. That
    shape is preserved here, but it is now a VIEW built by the orchestrator rather than
    the product of one mixed engine: every number in it was computed by exactly one
    domain. Assembling the three is the orchestrator's job and no one else's.
    """
    return assemble_legacy_dashboard_results(run_assessment(params))


def run_assessment_bundle(params: dict):
    """One separated domain run, returned in all three shapes the app needs.

    The app needs the typed per-domain result, the flat legacy dashboard view and
    the scientific Benefits result. Computing them independently would run the LCA
    engine three times over and — worse — could let the three views drift apart if
    any of them re-derived a quantity slightly differently.

    So `params` is consumed exactly once, `run_assessment` is called exactly once,
    and the scientific Benefits domain is handed the SAME neutral `SharedActivity`
    the economic domain was priced from. That is what keeps the physical activity
    behind a carbon figure and behind a benefit figure literally the same object.

    Returns `(result, legacy_dashboard, scientific_benefits)`.
    """
    result = run_assessment(params)

    # Imported here rather than at module scope: the orchestrator must remain
    # importable by the domain-dependency test without dragging in every domain.
    from monorail_assessment.benefits.integration import run_scientific_benefits_from_params

    scientific_benefits = run_scientific_benefits_from_params(
        params=params,
        shared_activity=result.shared,
        project_context=result.context,
    )

    legacy_dashboard = assemble_legacy_dashboard_results(result)
    return result, legacy_dashboard, scientific_benefits
