"""Integration patch for app_final_streamlit_ready (17).py.

Use this file as a guide for replacing the existing LCA core. It assumes that
lca_scientific_core.py is in the same directory as the Streamlit app.
"""

import math

from lca_scientific_core import (
    B6_ENERGY_INTENSITY,
    WASTE_EF,
    Evidence,
    GridCarbonYear,
    ProjectQuantity,
    ScientificInputError,
    calculate_a1_a3,
    calculate_a5,
    calculate_b2_b5,
    calculate_b6,
    calculate_c1_c4,
    calculate_module_d1,
    calculate_transport_legs,
    combine_lca_modules,
    make_project_evidence,
    publication_checks,
    render_lca_audit_streamlit,
    update_mass_balance,
)


# Add these Streamlit inputs in the sidebar. Numeric defaults are intentionally
# zero/blank because an unsourced density or grid factor must not be treated as
# scientific evidence.
def add_lca_source_inputs(st, assessment_lifetime_default=50):
    st.markdown("### Scientific LCA provenance")

    assessment_lifetime = st.number_input(
        "Reference study period / RSP (years)",
        min_value=1,
        value=int(assessment_lifetime_default),
        step=1,
        help="Project-defined study period. Cite the project brief/design-life document.",
        key="lca_rsp_years",
    )
    assessment_lifetime_source = st.text_input(
        "RSP source",
        value="",
        placeholder="Project brief / design-life report, page or clause",
        key="lca_rsp_source",
    )

    st.markdown("#### Quantity-to-mass conversions")
    concrete_density = st.number_input(
        "Concrete density (kg/m3)", value=0.0, min_value=0.0, key="lca_concrete_density"
    )
    concrete_density_source = st.text_input(
        "Concrete density source", value="", key="lca_concrete_density_source"
    )
    wood_density = st.number_input(
        "Wood density (kg/m3)", value=0.0, min_value=0.0, key="lca_wood_density"
    )
    wood_density_source = st.text_input(
        "Wood density source", value="", key="lca_wood_density_source"
    )
    glass_density = st.number_input(
        "Glass density (kg/m3)", value=0.0, min_value=0.0, key="lca_glass_density"
    )
    glass_density_source = st.text_input(
        "Glass density source", value="", key="lca_glass_density_source"
    )

    st.markdown("#### Project-data sources")
    boq_source = st.text_input(
        "Material quantities / BOQ source",
        value="",
        placeholder="BOQ revision, date, worksheet/rows",
        key="lca_boq_source",
    )
    ridership_source = st.text_input(
        "Passenger-km source",
        value="",
        placeholder="Ridership forecast or measured operations dataset",
        key="lca_ridership_source",
    )

    st.markdown("#### B6 electricity carbon factor")
    st.caption(
        "Enter the annual Egypt/project electricity factors from an official table. "
        "Do not use 0.5 as a publication default. Generation, T&D and upstream/WTT "
        "are separate so the scope is auditable."
    )
    grid_generation = st.number_input(
        "Grid generation factor (kgCO2e/kWh)", value=0.0, min_value=0.0,
        format="%.6f", key="lca_grid_generation"
    )
    grid_td = st.number_input(
        "Grid T&D factor (kgCO2e/kWh)", value=0.0, min_value=0.0,
        format="%.6f", key="lca_grid_td"
    )
    grid_upstream = st.number_input(
        "Grid upstream/WTT factor (kgCO2e/kWh)", value=0.0, min_value=0.0,
        format="%.6f", key="lca_grid_upstream"
    )
    grid_source = st.text_input(
        "Grid-factor source file/database", value="", key="lca_grid_source"
    )
    grid_location = st.text_input(
        "Grid-factor table/page/year", value="", key="lca_grid_location"
    )
    grid_mode = st.selectbox(
        "Grid CI mode",
        ["constant_documented_scenario", "annual_official_series"], index=0,
        help="constant = one documented factor repeated across years (a SCENARIO, not an annual "
             "series). annual = a real per-calendar-year official table (project-specific).",
        key="lca_grid_mode")
    st.caption("A single factor repeated across 50 years is a constant-grid scenario, not an "
               "annual measured series — it is labelled as such and does not claim project-specific "
               "annual data.")

    energy_intensity_choice = st.selectbox(
        "B6 energy-intensity basis",
        [
            "project_specific",
            "uk_light_rail_weighted_proxy",
            "ntd_light_rail_proxy",
            "ntd_automated_guideway_proxy",
        ],
        key="lca_ei_basis",
    )
    project_ei = st.number_input(
        "Project energy intensity (kWh/pkm; used only for project_specific)",
        value=0.0,
        min_value=0.0,
        format="%.6f",
        key="lca_project_ei",
    )
    project_ei_source = st.text_input(
        "Project energy-intensity source", value="", key="lca_project_ei_source"
    )

    st.markdown("#### A4 transport-to-site provenance")
    st.caption(
        "A4 legs are built from the material masses and the A4 distance/mode set in the "
        "main sidebar. The route distance needs its own source; without it A4 stays "
        "unconnected (not a fabricated 50 km). WTW is preferred for whole-life carbon."
    )
    a4_route_source = st.text_input(
        "A4 route/distance source",
        value="",
        placeholder="Route survey / logistics plan: origin, distance, payload, return assumption",
        key="lca_a4_route_source",
    )
    a4_scope = st.selectbox(
        "A4 emission-factor scope",
        ["wtw", "direct", "wtt"],
        index=0,
        help="wtw = direct + upstream/WTT (preferred for whole-life carbon).",
        key="lca_a4_scope",
    )
    a4_payload_assumption = st.text_input(
        "A4 payload / return-trip assumption",
        value="",
        placeholder="e.g. average laden HGV; empty return not separately counted",
        key="lca_a4_payload",
    )
    st.caption("Road return trip (RICS): outward-laden + fraction·empty-running. Applied to road "
               "only, and only with a documented empty-running factor + fraction + source. No "
               "hard-coded 0.5. Leave the factor at 0 to report outward-only.")
    a4_return_fraction = st.number_input(
        "A4 road empty-return fraction (0 = off)", value=0.0, min_value=0.0, max_value=1.0,
        step=0.05, format="%.2f", key="lca_a4_return_fraction")
    a4_empty_return_factor = st.number_input(
        "A4 empty-running EF (kgCO2e/tonne.km, 0 = off)", value=0.0, min_value=0.0,
        step=0.001, format="%.5f", key="lca_a4_empty_return_factor")
    a4_return_source = st.text_input(
        "A4 return-assumption source", value="", key="lca_a4_return_source")

    st.markdown("#### A5 construction provenance")
    st.caption(
        "A5 uses the A5 editor quantities (diesel, site electricity, per-material waste "
        "rates/routes). Each non-zero part needs its own source. Waste treatment uses the "
        "verified per-tonne GHG-2025 factors; the construction-year grid CI drives A5 electricity."
    )
    a5_diesel_scope = st.selectbox(
        "A5 diesel scope", ["wtw", "direct", "wtt"], index=0, key="lca_a5_diesel_scope",
        help="wtw = 3.18183, direct = 2.57082 kgCO2e/L (GHG 2025).")
    a5_diesel_source = st.text_input(
        "A5 site-diesel quantity source", value="", key="lca_a5_diesel_source")
    a5_electricity_source = st.text_input(
        "A5 site-electricity quantity source", value="", key="lca_a5_electricity_source")
    a5_waste_source = st.text_input(
        "A5 waste-generation source (rates/quantities)", value="", key="lca_a5_waste_source")
    a5_waste_route_source = st.text_input(
        "A5 waste-transport route/distance source", value="", key="lca_a5_waste_route_source")
    a5_construction_year = st.number_input(
        "A5 construction year (drives A5 electricity grid CI)",
        value=int(assessment_lifetime and 0) or 0, min_value=0, step=1,
        help="0 = use the analysis start year. A5 electricity uses THIS year's grid CI, not B6 year 1.",
        key="lca_a5_construction_year")
    # A5.1/A5.4 have no calculator yet, so 'included' is intentionally NOT offered.
    a5_predemolition_status = st.selectbox(
        "A5.1 pre-construction demolition", ["not_applicable", "not_yet_modelled"], index=0,
        help="No demolition calculator yet → choose N/A (with justification) or not_yet_modelled. "
             "Both keep A5 out of full-WLCA until modelled.",
        key="lca_a5_1_status")
    a5_predemolition_note = st.text_input(
        "A5.1 justification (required if N/A)", value="",
        placeholder="e.g. Greenfield project; no existing asset demolition in the declared boundary.",
        key="lca_a5_1_note")
    a5_worker_transport_status = st.selectbox(
        "A5.4 worker transport (optional in RICS)",
        ["optional_not_reported", "not_applicable"], index=0,
        help="Worker transport has no calculator yet → optional_not_reported or N/A only.",
        key="lca_a5_4_status")

    return {
        "assessment_lifetime": int(assessment_lifetime),
        "assessment_lifetime_source": assessment_lifetime_source,
        "concrete_density_kg_m3": concrete_density,
        "concrete_density_source": concrete_density_source,
        "wood_density_kg_m3": wood_density,
        "wood_density_source": wood_density_source,
        "glass_density_kg_m3": glass_density,
        "glass_density_source": glass_density_source,
        "boq_source": boq_source,
        "ridership_source": ridership_source,
        "grid_generation": grid_generation,
        "grid_td": grid_td,
        "grid_upstream": grid_upstream,
        "grid_source": grid_source,
        "grid_location": grid_location,
        "grid_mode": grid_mode,
        "energy_intensity_choice": energy_intensity_choice,
        "project_ei": project_ei,
        "project_ei_source": project_ei_source,
        "a4_route_source": a4_route_source,
        "a4_scope": a4_scope,
        "a4_payload_assumption": a4_payload_assumption,
        "a4_return_fraction": a4_return_fraction,
        "a4_empty_return_factor": a4_empty_return_factor,
        "a4_return_source": a4_return_source,
        "a5_diesel_scope": a5_diesel_scope,
        "a5_diesel_source": a5_diesel_source,
        "a5_electricity_source": a5_electricity_source,
        "a5_waste_source": a5_waste_source,
        "a5_waste_route_source": a5_waste_route_source,
        "a5_construction_year": int(a5_construction_year),
        "a5_predemolition_status": a5_predemolition_status,
        "a5_predemolition_note": a5_predemolition_note,
        "a5_worker_transport_status": a5_worker_transport_status,
    }


def _require_positive(value, source, label):
    if float(value) <= 0.0:
        raise ScientificInputError(f"{label} must be positive.")
    if not str(source).strip():
        raise ScientificInputError(f"{label} requires a source.")
    return float(value)


def build_material_masses_from_app_params(params):
    """Convert the current UI units to kg with sourced densities.

    Current app units:
      concrete and wood: thousand m3
      steel, aluminium and FRP: thousand tonnes
      glass: thousand m2 plus thickness in mm
    """
    boq_source = str(params.get("boq_source", "")).strip()
    if not boq_source:
        raise ScientificInputError("Material quantities require a BOQ source.")

    concrete_density = _require_positive(
        params.get("concrete_density_kg_m3", 0.0),
        params.get("concrete_density_source", ""),
        "Concrete density",
    )
    wood_density = _require_positive(
        params.get("wood_density_kg_m3", 0.0),
        params.get("wood_density_source", ""),
        "Wood density",
    )
    glass_density = _require_positive(
        params.get("glass_density_kg_m3", 0.0),
        params.get("glass_density_source", ""),
        "Glass density",
    )

    # UNIT-DEFINITION: UI concrete is in thousand m3; multiply by 1000.
    # PROJECT-SOURCE-REQUIRED: quantity source = BOQ revision/worksheet/row.
    concrete_m3 = float(params["concrete"]) * 1000.0
    # UNIT-DEFINITION: UI wood is in thousand m3; multiply by 1000.
    wood_m3 = float(params["wood"]) * 1000.0
    # UNIT-DEFINITION: UI glass is in thousand m2; multiply by 1000.
    # PROJECT-SOURCE-REQUIRED: glass thickness and density must be sourced.
    glass_m2 = float(params["glass"]) * 1000.0
    # UNIT-DEFINITION: millimetres to metres = /1000.
    glass_thickness_m = float(params.get("glass_thickness_mm", 0.0)) / 1000.0

    return {
        "concrete": ProjectQuantity(
            # MASS EQUATION: M_concrete = V_concrete * sourced density.
            # FUTURE-REPLACEMENT: use direct project mass if available, avoiding generic density.
            concrete_m3 * concrete_density, "kg", boq_source,
            "concrete volume x sourced density"
        ),
        "steel": ProjectQuantity(
            # UNIT-DEFINITION: thousand tonnes -> tonnes (*1000) -> kg (*1000).
            float(params["steel"]) * 1000.0 * 1000.0, "kg", boq_source,
            "thousand tonnes to kg"
        ),
        "aluminum": ProjectQuantity(
            # UNIT-DEFINITION: thousand tonnes -> kg.
            float(params["aluminum"]) * 1000.0 * 1000.0, "kg", boq_source,
            "thousand tonnes to kg"
        ),
        "wood": ProjectQuantity(
            # MASS EQUATION: M_wood = V_wood * sourced density.
            wood_m3 * wood_density, "kg", boq_source,
            "wood volume x sourced density"
        ),
        "frp": ProjectQuantity(
            # UNIT-DEFINITION: thousand tonnes -> kg. SOURCE-OPEN: FRP EF requires EPD or FRP=0.
            float(params["frp"]) * 1000.0 * 1000.0, "kg", boq_source,
            "thousand tonnes to kg"
        ),
        "glass": ProjectQuantity(
            # MASS EQUATION: M_glass = area * thickness * sourced density.
            glass_m2 * glass_thickness_m * glass_density, "kg", boq_source,
            "area x thickness x sourced density"
        ),
    }


def build_a4_scientific_legs(params, masses):
    """Build A4 transport legs from the existing app A4 editor / simple inputs.

    Returns (legs, status, note) where status is one of:
      "connected"          route source present → legs built from the sourced masses;
      "incomplete_sources" the user set A4 distance/mode but gave no route/distance
                           source → A4 is EXCLUDED (not a silent measured zero);
      "unconnected"        no A4 transport was entered at all.

    Rules enforced:
      * Advanced multi-leg rows take priority; the simple route is NOT added on top
        (no double counting).
      * Leg masses come from the scientific A1-A3 masses (same masses as A1-A3).
      * No fabricated 50 km distance in publication: a distance is used only with a
        route source that attests it. WTW is preferred and is a single factor (the
        core never adds WTT twice).
    """
    scope = str(params.get("a4_scope", "wtw")).lower()
    boq_source = str(params.get("boq_source", "")).strip()
    mode_default = str(params.get("transport_mode", "truck")).lower()
    dist_default = float(params.get("transport_distance_km", 0.0))
    a4_mode = str(params.get("a4_mode", "simple")).lower()
    advanced = params.get("a4_advanced_legs")
    advanced_present = (a4_mode == "advanced") and bool(advanced)
    simple_entered = dist_default > 0.0
    entered = advanced_present or simple_entered

    # Documented road empty-return assumption (no hard-coded 0.5). Applied to road only.
    return_fraction = float(params.get("a4_return_fraction", 0.0))
    empty_return_ef = float(params.get("a4_empty_return_factor", 0.0))
    return_source = str(params.get("a4_return_source", "")).strip()
    payload = str(params.get("a4_payload_assumption", "")).strip()
    route_source = str(params.get("a4_route_source", "")).strip()

    # In SIMPLE mode the single global route source attests the one distance. In ADVANCED
    # mode there is NO global fallback — every segment must carry its own distance source.
    if not advanced_present:
        if not route_source:
            if simple_entered:
                return ([], "incomplete_sources",
                        "A4 distance/mode were set but no route/distance source was given → "
                        "A4 is EXCLUDED from the result (not counted as a measured zero).", [])
            return [], "unconnected", "No A4 transport entered.", []

    # Assemble routes. A material's transport is split across one or more ROUTES
    # (route_share per route must sum to 1). Each route can have several SEQUENTIAL
    # SEGMENTS (e.g. ship then truck) that all carry the SAME route mass — segments are
    # NOT a mass split. Structure: routes[material][route_id] = {"share", "segments":[...]}.
    routes = {}
    if advanced_present:
        for row in advanced:
            m = row.get("material", "not specified")
            rid = str(row.get("route_id", "1"))
            rs = float(row.get("route_share", 1.0))
            # route_share must be within [0,1] (so -0.2 + 1.2 = 1 cannot pass).
            if not (0.0 <= rs <= 1.0):
                return ([], "validation_failed",
                        f"A4 route_share for '{m}' route {rid} = {rs} is outside [0,1].", [])
            seg_no = int(row.get("segment_no", 1))
            if seg_no <= 0:
                return ([], "validation_failed",
                        f"A4 segment_no for '{m}' route {rid} must be positive (got {seg_no}).", [])
            dist = float(row.get("distance_km", 0.0))
            if not math.isfinite(dist) or dist < 0.0:
                return ([], "validation_failed",
                        f"A4 distance for '{m}' route {rid} seg {seg_no} must be finite and ≥ 0.", [])
            rec = routes.setdefault(m, {}).setdefault(rid, {"share": None, "segments": [], "seg_nos": set()})
            # route_share must be IDENTICAL across all segments of the same route.
            if rec["share"] is None:
                rec["share"] = rs
            elif abs(rec["share"] - rs) > 1e-9:
                return ([], "validation_failed",
                        f"A4 route_share differs between segments of '{m}' route {rid} "
                        f"({rec['share']} vs {rs}); it must be identical.", [])
            if seg_no in rec["seg_nos"]:
                return ([], "validation_failed",
                        f"A4 duplicate segment_no {seg_no} in '{m}' route {rid}.", [])
            rec["seg_nos"].add(seg_no)
            rec["segments"].append({
                "segment_no": seg_no,
                "mode": str(row.get("mode", mode_default)).lower(),
                "distance_km": dist,
                # NO global fallback in advanced mode.
                "distance_source": str(row.get("distance_source", "")).strip(),
            })
    else:
        for material, quantity in masses.items():
            if float(quantity.value) > 0.0:
                routes[material] = {"1": {"share": 1.0, "segments": [
                    {"segment_no": 1, "mode": mode_default, "distance_km": dist_default,
                     "distance_source": route_source}]}}

    # MASS RECONCILIATION: for every material with A1-A3 mass, Σ route_share must equal 1.
    for material, quantity in masses.items():
        mat_mass = float(quantity.value)
        if mat_mass <= 0.0:
            continue
        mat_routes = routes.get(material)
        if not mat_routes:
            return ([], "validation_failed",
                    f"A4 mass reconciliation failed: material '{material}' has A1-A3 mass but no "
                    "A4 route. Every transported material needs route_shares summing to 1.", [])
        share_sum = sum(float(r["share"] or 0.0) for r in mat_routes.values())
        if abs(share_sum - 1.0) > 1e-6:
            return ([], "validation_failed",
                    f"A4 mass reconciliation failed for '{material}': Σ route_share = {share_sum:.6f} "
                    "(must equal 1).", [])

    legs, audit = [], []
    for material, quantity in masses.items():
        mat_mass = float(quantity.value)
        if mat_mass <= 0.0:
            continue
        mass_src = boq_source or quantity.source
        for rid, route in routes[material].items():
            route_mass = mat_mass * float(route["share"] or 0.0)
            if route_mass <= 0.0:
                continue
            for seg in sorted(route["segments"], key=lambda s: s["segment_no"]):
                mode = seg["mode"]
                distance_km = seg["distance_km"]
                dist_src = seg["distance_source"]
                # Every sequential segment carries the SAME route mass (not a split).
                legs.append({
                    "material": material, "mass_kg": route_mass, "distance_km": distance_km,
                    "mode": mode, "scope": scope,
                    "mass_source": mass_src, "distance_source": dist_src,
                })
                audit.append({
                    "stage": "A4", "material": material, "route_id": rid,
                    "route_share": route["share"], "segment_no": seg["segment_no"], "leg": "outward",
                    "mass_kg": route_mass, "mass_source": mass_src, "distance_km": distance_km,
                    "distance_source": dist_src or "MISSING", "mode": mode, "scope": scope,
                    "payload_assumption": payload or "not stated",
                    "return_assumption": "none (outward only)",
                })
                # RICS road return journey — road only, only with a documented assumption.
                if mode == "truck" and return_fraction > 0.0 and empty_return_ef > 0.0 and return_source:
                    ret_ev = make_project_evidence(
                        code=f"A4-ROAD-RETURN-{material}-{rid}-{seg['segment_no']}",
                        value=empty_return_ef, unit="kgCO2e/tonne.km", stage="A4",
                        source_file=return_source,
                        location=f"documented empty-return: fraction={return_fraction}",
                        boundary_scope="A4 road empty-return running",
                        note=payload or "documented road return-trip assumption",
                    )
                    legs.append({
                        "material": material, "mass_kg": route_mass,
                        "distance_km": distance_km * return_fraction, "mode": mode, "scope": scope,
                        "mass_source": mass_src, "distance_source": return_source,
                        "factor_override": ret_ev,
                    })
                    audit.append({
                        "stage": "A4", "material": material, "route_id": rid,
                        "route_share": route["share"], "segment_no": seg["segment_no"], "leg": "return",
                        "mass_kg": route_mass, "mass_source": mass_src,
                        "distance_km": distance_km * return_fraction, "distance_source": return_source,
                        "mode": mode, "scope": scope, "payload_assumption": payload or "not stated",
                        "return_assumption": f"empty-return fraction={return_fraction}, EF={empty_return_ef}",
                    })

    # Every segment must carry its own distance source (per-route/segment, not one global).
    if any(a.get("distance_source") in (None, "", "MISSING") for a in audit):
        return ([], "incomplete_sources",
                "A4 has a route segment without a distance source → A4 excluded.", audit)

    note = ""
    road_present = any(s["mode"] == "truck" for mr in routes.values() for r in mr.values()
                       for s in r["segments"])
    if road_present and not (return_fraction > 0.0 and empty_return_ef > 0.0 and return_source):
        note = ("Road legs are outward-only (average-laden factor); a documented empty-return "
                "assumption (fraction + empty-running EF + source) is required to add the return trip.")
    return legs, "connected", note, audit


def _a4_breakdown(a4_result):
    """Aggregate A4 legs into per-material and per-mode tCO2e for reviewer audit."""
    by_material, by_mode = {}, {}
    for leg in a4_result.get("legs", []):
        by_material[leg["material"]] = by_material.get(leg["material"], 0.0) + float(leg["tCO2e"])
        by_mode[leg["mode"]] = by_mode.get(leg["mode"], 0.0) + float(leg["tCO2e"])
    return by_material, by_mode


# ── A5 construction: verified per-tonne waste routes by material class ─────────
# Only materials with a defensible verified GHG-2025 waste factor are auto-routed.
# glass and wood have NO verified waste factor in the uploaded set → their waste
# treatment must be supplied as a documented override, otherwise it is flagged
# incomplete (never silently mapped to a mineral/metal factor).
_A5_WASTE_ROUTE = {
    "concrete": {"landfill": "mineral_landfill", "recycle": "mineral_open_loop"},
    "steel":    {"landfill": "metal_landfill",   "recycle": None},
    "aluminum": {"landfill": "metal_landfill",   "recycle": None},
    "frp":      {"landfill": "plastic_landfill_proxy", "recycle": None},
}


def _a5_treatment_override(material, route_name, routes_ui):
    """Build a documented per-tonne treatment factor Evidence from the A5 editor row.

    Returns (evidence_or_None, documented_bool). A row qualifies only with an explicit
    per-row source. For reuse the value may be 0 (e.g. a documented clean-reuse route)
    but a source is still required — a zero is a number that needs evidence, not an
    absence of one. Values are interpreted as kgCO2e/tonne of waste (never per kg).
    """
    r = routes_ui.get(material)
    if not isinstance(r, dict):
        return None, False
    src = str(r.get("source", "")).strip()
    if not src:
        return None, False
    key = {"landfill": "ef_landfill", "recycle": "ef_recycle", "reuse": "ef_reuse"}[route_name]
    val = float(r.get(key, 0.0) or 0.0)
    if val < 0.0:
        return None, False
    if route_name != "reuse" and val <= 0.0:
        # landfill/recycle need a positive documented factor to be an override.
        return None, False
    ev = make_project_evidence(
        code=f"A5-WASTE-{material}-{route_name}", value=val, unit="kgCO2e/tonne waste",
        stage="A5", source_file=src,
        location=f"A5 documented {route_name} treatment factor (per tonne)",
        boundary_scope="A5.3 waste treatment")
    return ev, True


def _a5_waste_mass_kg(installed_or_purchased_mass_kg, waste_rate, boq_basis):
    """E8 / purchased-basis waste mass.

    installed basis: W = M_installed * WR / (1 - WR)  (extra purchased over installed)
    purchased basis: W = M_purchased * WR             (already inside A1-A3)
    """
    wr = float(waste_rate)
    m = float(installed_or_purchased_mass_kg)
    if wr <= 0.0 or m <= 0.0:
        return 0.0
    if wr >= 1.0:
        raise ScientificInputError("A5 waste rate must satisfy 0 <= WR < 1.")
    if boq_basis == "installed":
        return m * wr / (1.0 - wr)
    return m * wr


def build_a5_scientific_activity(params, masses, grid_construction):
    """Build the arguments for calculate_a5 from the existing app A5 editors.

    Returns (a5_kwargs_or_None, status, note). A5 is made of five separate parts:
    fuel, site electricity, production of wasted material, waste transport and waste
    treatment. Every non-zero part must carry its own source; an entered-but-unsourced
    part is EXCLUDED and sets status="incomplete_sources" (never a silent zero).

    Key accounting rule: production of wasted material is added ONLY when the BOQ is
    on an *installed* basis (A1-A3 did not yet include the waste). On a *purchased*
    basis the waste material is already inside A1-A3, so it is NOT added again.
    """
    if not bool(params.get("include_a5", False)):
        return None, "unconnected", "A5 module is off.", {}

    boq_basis = str(params.get("a5_boq_mode", "installed")).lower()
    diesel_l = float(params.get("a5_diesel_l", 0.0))
    diesel_mode = str(params.get("a5_diesel_mode", "simple")).lower()
    diesel_scope = str(params.get("a5_diesel_scope", "wtw")).lower()
    diesel_source = str(params.get("a5_diesel_source", "")).strip()
    elec_kwh = float(params.get("a5_elec_kwh", 0.0))
    elec_source = str(params.get("a5_electricity_source", "")).strip()
    waste_source = str(params.get("a5_waste_source", "")).strip()
    waste_route_source = str(params.get("a5_waste_route_source", "")).strip()
    waste_rates = params.get("a5_waste_rates") or {}
    global_rate = float(params.get("a5_waste_rate", 0.0))
    routes_ui = params.get("a5_waste_routes") or {}
    shares_ui = params.get("a5_treatment_shares") or {}
    default_dist = float(params.get("a5_waste_transport_km", 0.0))

    status = "connected"
    notes = []
    entered = False
    readiness = {}

    # ── A5.2 site fuel ─────────────────────────────────────────────────────────
    diesel_litres = None
    if diesel_mode == "equipment":
        if params.get("a5_equipment"):
            entered = True
            status = "incomplete_sources"
            readiness["A5.2_site_fuel"] = "incomplete_sources"
            notes.append("A5 diesel is in equipment-fleet mode; the scientific core needs total "
                         "litres. Provide simple total litres or the litres are excluded.")
        else:
            readiness["A5.2_site_fuel"] = "not_entered"
    elif diesel_l > 0.0:
        entered = True
        if diesel_source:
            diesel_litres = ProjectQuantity(diesel_l, "L", diesel_source, "site diesel")
            readiness["A5.2_site_fuel"] = "included_and_sourced"
        else:
            status = "incomplete_sources"
            readiness["A5.2_site_fuel"] = "incomplete_sources"
            notes.append("A5 site diesel entered without a source → excluded.")
    else:
        readiness["A5.2_site_fuel"] = "not_entered"

    # ── A5.2 site electricity (construction-year CI) ───────────────────────────
    electricity_kwh = None
    if elec_kwh > 0.0:
        entered = True
        if elec_source and grid_construction is not None:
            electricity_kwh = ProjectQuantity(elec_kwh, "kWh", elec_source, "site electricity")
            readiness["A5.2_site_electricity"] = "included_and_sourced"
        else:
            status = "incomplete_sources"
            readiness["A5.2_site_electricity"] = "incomplete_sources"
            notes.append("A5 site electricity entered without a source (or no construction-year "
                         "grid CI) → excluded.")
    else:
        readiness["A5.2_site_electricity"] = "not_entered"

    # ── A5.3–A5.6 waste: production + transport + treatment ─────────────────────
    extra_waste_materials_kg = {}
    waste_delivery_legs = []
    waste_treatment_items = []
    any_waste_entered = False

    for material, quantity in masses.items():
        wr = float(waste_rates.get(material, global_rate))
        mass_kg = float(quantity.value)
        if wr <= 0.0 or mass_kg <= 0.0:
            continue
        any_waste_entered = True
        entered = True
        if not waste_source:
            status = "incomplete_sources"
            notes.append(f"A5 waste for {material} entered without a waste-generation source → excluded.")
            continue

        w_kg = _a5_waste_mass_kg(mass_kg, wr, boq_basis)
        if w_kg <= 0.0:
            continue

        # A5.3 production of wasted material — installed basis only (no double count).
        if boq_basis == "installed":
            extra_waste_materials_kg[material] = ProjectQuantity(
                w_kg, "kg", waste_source, "installed-basis waste production (E8)")

        # A5.3 waste transport.
        route = routes_ui.get(material, {})
        dist = float(route.get("transport_km", default_dist))
        if dist > 0.0:
            if waste_route_source:
                waste_delivery_legs.append({
                    "material": material, "mass_kg": w_kg, "distance_km": dist,
                    "mode": "truck", "scope": "wtw",
                    "mass_source": waste_source, "distance_source": waste_route_source,
                })
            else:
                status = "incomplete_sources"
                notes.append(f"A5 waste transport for {material} has a distance but no route source → excluded.")

        # A5.3 waste treatment — verified per-tonne factors only; shares must be valid;
        # NO landfill-as-recycling fallback (a missing recycling factor → incomplete_sources).
        shares = shares_ui.get(material, {"landfill": 1.0, "recycle": 0.0, "reuse": 0.0})
        lf = float(shares.get("landfill", 0.0))
        rc = float(shares.get("recycle", 0.0))
        ru = float(shares.get("reuse", 0.0))
        if min(lf, rc, ru) < 0.0 or max(lf, rc, ru) > 1.0 or abs(lf + rc + ru - 1.0) > 1e-9:
            status = "validation_failed"
            notes.append(f"A5 {material} treatment shares invalid: reuse+recycle+landfill must "
                         "equal 1 and each be within 0..1.")
            continue
        route_codes = _A5_WASTE_ROUTE.get(material, {})
        for route_name, share in (("landfill", lf), ("recycle", rc), ("reuse", ru)):
            if share <= 0.0:
                continue
            w_route = w_kg * share
            override, documented = _a5_treatment_override(material, route_name, routes_ui)
            if documented:
                # A documented per-tonne factor from the editor (used as Evidence override).
                waste_treatment_items.append({
                    "material": material, "waste_kg": w_route, "waste_source": waste_source,
                    "route": route_name, "factor_override": override})
                continue
            code = route_codes.get(route_name)
            if code:
                waste_treatment_items.append({
                    "material": material, "waste_kg": w_route, "waste_source": waste_source,
                    "route": route_name, "factor_code": code})
            elif route_name == "reuse":
                # Reuse EF (even 0) is a NUMBER that needs evidence, not an absence of one.
                status = "incomplete_sources"
                notes.append(f"A5 {material} reuse: a reuse processing EF (0 is allowed) requires a "
                             "documented source → EXCLUDED until supplied. Recovery credit is Module D.")
            else:
                status = "incomplete_sources"
                notes.append(f"A5 {material} {route_name}: no verified per-tonne factor → EXCLUDED "
                             "(no landfill fallback). Supply a documented per-tonne override.")

    # A5.3 component readiness (waste generation / transport / treatment).
    if not any_waste_entered:
        readiness["A5.3_waste_generation"] = "not_entered"
        readiness["A5.3_waste_transport"] = "not_entered"
        readiness["A5.3_waste_treatment"] = "not_entered"
    else:
        readiness["A5.3_waste_generation"] = (
            "included_and_sourced" if waste_source else "incomplete_sources")
        readiness["A5.3_waste_transport"] = (
            "included_and_sourced" if waste_delivery_legs else
            ("incomplete_sources" if status == "incomplete_sources" else "documented_zero"))
        readiness["A5.3_waste_treatment"] = (
            "included_and_sourced" if waste_treatment_items and status == "connected" else
            ("incomplete_sources" if status in ("incomplete_sources", "validation_failed")
             else "documented_zero"))

    if not entered:
        return (None, "unconnected", "A5 module on but no fuel/electricity/waste entered.",
                readiness)

    a5_kwargs = dict(
        diesel_litres=diesel_litres,
        diesel_scope=diesel_scope,
        electricity_kwh=electricity_kwh,
        grid=grid_construction if electricity_kwh is not None else None,
        extra_waste_materials_kg=extra_waste_materials_kg or None,
        waste_factor_overrides=None,
        waste_delivery_legs=waste_delivery_legs,
        waste_treatment_items=waste_treatment_items,
    )
    return a5_kwargs, status, " ".join(notes), readiness


def run_scientific_lca_from_app_params(params):
    """Replacement for the scientific LCA part of calculate_core_lca_lcc().

    Connected now: A1-A3, A4 (from the app editor), B6. A5/B2-B5/C1-C4 accept
    optional pre-built scientific inputs and otherwise report 0 as UNCONNECTED
    (not negligible). publication_grade_full_wlca stays False until every stage is
    connected and sourced.
    """
    rsp = int(params.get("assessment_lifetime", 0))
    if rsp <= 0 or not str(params.get("assessment_lifetime_source", "")).strip():
        raise ScientificInputError("RSP/assessment lifetime requires a project source.")

    masses = build_material_masses_from_app_params(params)
    a1_a3 = calculate_a1_a3(masses)

    # A4 wired from the app editors. Explicit pre-built legs win; otherwise build from UI.
    a4_legs = params.get("a4_scientific_legs")
    if a4_legs:
        a4_status, a4_note, a4_activity_audit = "connected", "", []
    else:
        a4_legs, a4_status, a4_note, a4_activity_audit = build_a4_scientific_legs(params, masses)
    a4 = calculate_transport_legs(a4_legs, "A4", default_scope="wtw") if a4_legs else {
        "stage": "A4", "total_tco2e": 0.0, "source_audit": [], "legs": []
    }
    a4_by_material, a4_by_mode = _a4_breakdown(a4)
    a4["by_material"] = a4_by_material
    a4["by_mode"] = a4_by_mode
    a4["status"] = a4_status
    a4["note"] = a4_note
    a4["activity_audit"] = a4_activity_audit
    a4["equation_id"] = "E3_A4_C2"

    grid_source = str(params.get("grid_source", "")).strip()
    grid_location = str(params.get("grid_location", "")).strip()
    if not grid_source or not grid_location:
        raise ScientificInputError(
            "Egypt/project grid CI is still OPEN. Supply the official source file and table/page."
        )
    start_year = int(params.get("analysis_start_year", 1))
    # Grid mode: an ANNUAL official series (a real per-calendar-year table) is project-
    # specific; a CONSTANT value repeated across years is only a documented scenario and
    # must never be described as an annual measured series.
    grid_mode = str(params.get("grid_mode", "constant_documented_scenario")).lower()
    grid_annual_series = params.get("grid_annual_series") or {}  # {calendar_year: {gen,td,up}}

    def _grid_for_calendar_year(cal_year, operating_year):
        if grid_mode == "annual_official_series":
            row = grid_annual_series.get(cal_year) or grid_annual_series.get(str(cal_year))
            if row is None:
                raise ScientificInputError(
                    f"grid_mode=annual_official_series but no grid row for calendar year {cal_year}.")
            gen = float(row.get("generation", 0.0))
            td = float(row.get("td", 0.0))
            up = float(row.get("upstream", 0.0))
            note = "Annual official grid series (project-specific)."
        else:
            gen = float(params.get("grid_generation", 0.0))
            td = float(params.get("grid_td", 0.0))
            up = float(params.get("grid_upstream", 0.0))
            note = "Constant-grid documented scenario (single factor repeated; NOT an annual series)."
        return GridCarbonYear(
            year=operating_year, generation_kgco2e_per_kwh=gen, td_kgco2e_per_kwh=td,
            upstream_kgco2e_per_kwh=up, source_file=grid_source,
            location=f"{grid_location}; calendar year {cal_year}",
            geographic_scope="Egypt/project electricity supply", note=note)

    grid_by_year = {}
    for offset in range(rsp):
        operating_year = offset + 1
        calendar_year = start_year + offset
        grid_by_year[operating_year] = _grid_for_calendar_year(calendar_year, operating_year)

    choice = str(params.get("energy_intensity_choice", "project_specific"))
    if choice == "project_specific":
        from lca_scientific_core import make_project_evidence
        energy_intensity = make_project_evidence(
            code="PROJECT-B6-EI",
            value=float(params.get("project_ei", 0.0)),
            unit="kWh/passenger.km",
            stage="B6",
            source_file=str(params.get("project_ei_source", "")),
            location="Measured/modelled monorail energy-intensity dataset",
            boundary_scope="B6 traction/operational electricity as defined by project",
        )
    else:
        energy_intensity = B6_ENERGY_INTENSITY[choice]

    daily_pkm_thousand = float(params.get("daily_pax_km", 0.0))
    ridership_source = str(params.get("ridership_source", "")).strip()
    if not ridership_source:
        raise ScientificInputError("Passenger-km requires a forecast/measurement source.")
    # FUNCTIONAL-UNIT DENOMINATOR: annual PKM = daily thousand-PKM * 1000 * 365.
    # PROJECT-SOURCE-REQUIRED: ridership forecast/measurement; 365 is calendar-day definition.
    annual_pkm = daily_pkm_thousand * 1000.0 * 365.0
    annual_pkm_by_year = {
        year: ProjectQuantity(
            annual_pkm,
            "passenger-km/year",
            ridership_source,
            "daily thousand passenger-km x 1000 x 365",
        )
        for year in range(1, rsp + 1)
    }
    b6 = calculate_b6(annual_pkm_by_year, grid_by_year, energy_intensity)

    # Independent construction-year grid record (A5 electricity uses the CONSTRUCTION year's
    # grid CI). With an annual series it reads THAT calendar year's row; with a constant
    # scenario it uses the documented single value.
    construction_year = int(params.get("a5_construction_year", 0)) or start_year
    grid_construction = _grid_for_calendar_year(construction_year, 0)

    # A5 wired from the app editors (fuel + electricity + waste production/transport/treatment).
    a5_prebuilt = params.get("a5_scientific_inputs")
    a5_readiness = {}
    if a5_prebuilt:
        a5 = calculate_a5(**a5_prebuilt)
        a5_status, a5_note = "connected", ""
    else:
        a5_kwargs, a5_status, a5_note, a5_readiness = build_a5_scientific_activity(
            params, masses, grid_construction)
        if a5_kwargs is not None:
            a5 = calculate_a5(**a5_kwargs)
        else:
            a5 = {"stage": "A5", "total_tco2e": 0.0, "source_audit": []}
    a5["status"] = a5_status
    a5["note"] = a5_note
    # RICS official A5 subdivision. A5.1 pre-construction demolition and A5.4 worker
    # transport have NO calculator yet, so "included" is not an allowed choice; the only
    # valid choices are not_applicable (with justification) or not_yet_modelled — both of
    # which keep A5 out of full-WLCA until modelled. Computed components map onto A5.2/A5.3.
    _predemo_status = str(params.get("a5_predemolition_status", "not_applicable"))
    _predemo_note = str(params.get("a5_predemolition_note", "")).strip()
    _worker_status = str(params.get("a5_worker_transport_status", "optional_not_reported"))
    _a5_notes = [a5["note"]] if a5["note"] else []
    # A5.1 gating.
    if _predemo_status == "not_applicable" and not _predemo_note:
        if a5_status == "connected":
            a5_status = "incomplete_sources"
        _a5_notes.append("A5.1 marked not_applicable but no justification was given.")
    elif _predemo_status == "not_yet_modelled":
        if a5_status == "connected":
            a5_status = "incomplete_sources"
        _a5_notes.append("A5.1 pre-construction demolition is not_yet_modelled → A5 scope incomplete.")
    elif _predemo_status == "included":
        # No demolition calculator exists → 'included' cannot be substantiated.
        if a5_status == "connected":
            a5_status = "incomplete_sources"
        _a5_notes.append("A5.1 'included' has no demolition calculation → incomplete_sources.")
    # A5.4 gating: worker transport has no calculator; 'included' cannot be substantiated.
    if _worker_status == "included":
        if a5_status == "connected":
            a5_status = "incomplete_sources"
        _a5_notes.append("A5.4 'included' has no worker-transport calculation → incomplete_sources.")
    a5["status"] = a5_status
    a5["note"] = " ".join(_a5_notes)
    a5_readiness["A5.1_preconstruction_demolition"] = _predemo_status
    a5_readiness["A5.4_worker_transport"] = _worker_status
    a5["component_readiness"] = a5_readiness
    a5["rics_subdivision"] = {
        "A5.1_preconstruction_demolition": {
            "status": _predemo_status, "justification": _predemo_note or "(none)"},
        "A5.2_construction_activities_tco2e": (
            float(a5.get("fuel_tco2e", 0.0)) + float(a5.get("electricity_tco2e", 0.0))),
        "A5.3_waste_management_tco2e": (
            float(a5.get("extra_waste_product_tco2e", 0.0))
            + float(a5.get("waste_transport_tco2e", 0.0))
            + float(a5.get("waste_treatment_tco2e", 0.0))),
        "A5.4_worker_transport": {"status": _worker_status},
    }

    b_events = params.get("b2_b5_scientific_events") or []
    b2b5_connected = bool(b_events)
    b2_b5 = calculate_b2_b5(b_events, grid_by_year) if b_events else {
        "stage": "B2-B5", "total_tco2e": 0.0, "source_audit": [],
        "material_added_kg": {}, "material_removed_kg": {}
    }
    mass_balance = update_mass_balance(
        masses,
        b2_b5.get("material_added_kg", {}),
        b2_b5.get("material_removed_kg", {}),
    )

    c_inputs = params.get("c1_c4_scientific_inputs") or {}
    c1c4_connected = bool(c_inputs)
    c1_c4 = calculate_c1_c4(**c_inputs) if c_inputs else {
        "stage": "C1-C4", "total_tco2e": 0.0, "source_audit": []
    }

    d_rows = params.get("module_d1_scientific_rows") or []
    module_d1 = calculate_module_d1(d_rows) if d_rows else {
        "stage": "D1", "signed_tco2e": 0.0, "source_audit": [],
        "reporting_note": "Module D not calculated."
    }

    # ── Per-stage status vocabulary ──────────────────────────────────────────
    # A zero total is NOT the same as "done": distinguish connected / not_applicable /
    # unconnected / incomplete_sources / validation_failed so a 0 is never mistaken
    # for a completed, sourced stage.
    def _optional_status(connected_flag):
        return "connected" if connected_flag else "unconnected"

    stage_status = {
        "A1-A3": "connected",   # reached here only if masses were sourced
        "A4": a4_status,
        "A5": a5_status,
        "B2-B5": _optional_status(b2b5_connected),
        "B6": "connected",      # reached here only if grid + ridership + RSP sourced
        "C1-C4": _optional_status(c1c4_connected),
    }
    _DONE = {"connected", "not_applicable"}
    scope_connected = {s: (st == "connected") for s, st in stage_status.items()}

    # ── REPORTED vs DIAGNOSTIC totals ────────────────────────────────────────
    # A stage whose status is not "connected" (incomplete_sources / validation_failed /
    # unconnected) must NOT contribute its partially-computed carbon to the reported
    # headline. We combine a REPORTED set (non-connected stages zeroed) for the published
    # number, and keep the raw computed value only in a diagnostic table.
    def _zero_module(stage):
        return {"stage": stage, "total_tco2e": 0.0, "source_audit": []}

    def _reported(module, stage_key, stage_name):
        return module if stage_status[stage_key] == "connected" else _zero_module(stage_name)

    rep_a4 = _reported(a4, "A4", "A4")
    rep_a5 = _reported(a5, "A5", "A5")
    rep_b2b5 = _reported(b2_b5, "B2-B5", "B2-B5")
    rep_c1c4 = _reported(c1_c4, "C1-C4", "C1-C4")

    final_lca = combine_lca_modules(a1_a3, rep_a4, rep_a5, rep_b2b5, b6, rep_c1c4, module_d1)
    checks = publication_checks(
        masses,
        grid_by_year,
        final_lca["source_audit"],
        assessment_period_years=rsp,
    )

    # Diagnostic table: what each stage computed vs what was reported.
    diagnostic_stage_tco2e = {
        "A1-A3": float(a1_a3.get("total_tco2e", 0.0)),
        "A4": float(a4.get("total_tco2e", 0.0)),
        "A5": float(a5.get("total_tco2e", 0.0)),
        "B2-B5": float(b2_b5.get("total_tco2e", 0.0)),
        "B6": float(b6.get("total_tco2e", 0.0)),
        "C1-C4": float(c1_c4.get("total_tco2e", 0.0)),
    }
    reported_stage_tco2e = {
        s: (diagnostic_stage_tco2e[s] if stage_status[s] == "connected" else 0.0)
        for s in diagnostic_stage_tco2e
    }
    final_lca["diagnostic_stage_tco2e"] = diagnostic_stage_tco2e
    final_lca["reported_stage_tco2e"] = reported_stage_tco2e
    final_lca["excluded_from_reported"] = {
        s: diagnostic_stage_tco2e[s] for s in diagnostic_stage_tco2e
        if stage_status[s] != "connected" and abs(diagnostic_stage_tco2e[s]) > 0.0
    }

    # partial-scope grade = the CONNECTED stages are fully sourced (no OPEN factor,
    # FRP handled, one grid record per year). This is what publication_checks verifies.
    publication_grade_partial_scope = bool(checks.get("publication_grade", False))
    # full whole-life grade additionally requires EVERY optional stage done (connected
    # or justified not_applicable). incomplete_sources / unconnected keep it False.
    required_full = ["A4", "A5", "B2-B5", "C1-C4"]
    _all_stages_done = all(stage_status[s] in _DONE for s in required_full)
    _no_validation_failed = "validation_failed" not in stage_status.values()

    connected = [s for s, st in stage_status.items() if st == "connected"]
    scope_included = [s for s, st in stage_status.items() if st in _DONE]
    unconnected = [s for s, st in stage_status.items() if st not in _DONE]
    incomplete = [s for s, st in stage_status.items() if st == "incomplete_sources"]

    # ── Expanded publication readiness gate (method + activity + factor + mass +
    #    applicability + project/proxy + grid-mode) ────────────────────────────
    grid_project_specific = (grid_mode == "annual_official_series")
    mass_balance_valid = all(r.get("remaining_for_C1_C4_kg", 0.0) >= -1e-9
                             for r in mass_balance.get("rows", []))
    activity_data_complete = ("incomplete_sources" not in stage_status.values()
                              and "validation_failed" not in stage_status.values())
    stage_applicability_complete = all(stage_status[s] in _DONE for s in required_full)
    # Any verified-proxy factor was used → not fully project-specific.
    _aud = final_lca.get("source_audit")
    proxy_used = False
    try:
        if hasattr(_aud, "empty") and not _aud.empty and "status" in _aud.columns:
            proxy_used = _aud["status"].astype(str).str.contains("proxy", case=False, na=False).any()
    except Exception:
        proxy_used = False
    publication_readiness = {
        "method_complete": True,  # equations closed for the connected stages
        "activity_data_complete": bool(activity_data_complete),
        "factor_sources_complete": bool(not checks.get("issues")),
        "mass_balance_valid": bool(mass_balance_valid),
        "stage_applicability_complete": bool(stage_applicability_complete),
        "project_specific_data_complete": bool(grid_project_specific and not proxy_used),
        "grid_mode": grid_mode,
        "grid_is_project_specific_annual": bool(grid_project_specific),
        "proxy_factors_used": bool(proxy_used),
        "uncertainty_complete": False,  # Phase-4 MC wiring for the scientific engine is pending
    }

    # ── Three-level closure gate (replaces the single misleading boolean) ────────
    # 1) full_wlca_calculation_complete: every applicable A1-C4 stage connected or
    #    justified N/A, mass balance valid, no validation failures.
    full_wlca_calculation_complete = bool(
        publication_grade_partial_scope and _all_stages_done
        and _no_validation_failed and mass_balance_valid)
    # 2) standards_reporting_complete: also all factor/activity sources documented
    #    (no OPEN factor / no open issues), Module D kept separate.
    standards_reporting_complete = bool(
        full_wlca_calculation_complete and not checks.get("issues"))
    # 3) q1_evidence_ready: also project-specific (annual grid, no undisclosed proxy)
    #    and uncertainty complete.
    q1_evidence_ready = bool(
        standards_reporting_complete
        and publication_readiness["project_specific_data_complete"]
        and publication_readiness["uncertainty_complete"])
    closure_gate = {
        "full_wlca_calculation_complete": full_wlca_calculation_complete,
        "standards_reporting_complete": standards_reporting_complete,
        "q1_evidence_ready": q1_evidence_ready,
    }
    # Backward-compatible alias: the old boolean now means "calculation complete", and
    # it can only be True when the calculation really is complete (never on proxy/scope gaps).
    publication_grade_full_wlca = full_wlca_calculation_complete

    final_lca["publication_checks"] = checks
    final_lca["publication_readiness"] = publication_readiness
    final_lca["closure_gate"] = closure_gate
    final_lca["publication_grade_partial_scope"] = publication_grade_partial_scope
    final_lca["publication_grade_full_wlca"] = publication_grade_full_wlca
    final_lca["stage_status"] = stage_status
    final_lca["scope_connected"] = scope_connected
    final_lca["connected_stages"] = connected
    final_lca["unconnected_stages"] = unconnected
    final_lca["incomplete_source_stages"] = incomplete
    final_lca["grid_mode"] = grid_mode
    final_lca["grid_basis"] = ("annual_official_series (project-specific)"
                               if grid_project_specific else "constant_documented_scenario")
    # Alias: the combined value is a PARTIAL, connected-scope total until every stage is wired.
    final_lca["connected_scope_tCO2e"] = final_lca["gross_A_C_tCO2e"]
    # Scope label is generated from the status map, never hand-written, so it can never
    # drift from what was actually summed.
    final_lca["scope_label"] = "Scientific partial LCA: " + " + ".join(scope_included)
    final_lca["a4_note"] = a4_note
    final_lca["mass_balance"] = mass_balance
    final_lca["modules"] = {
        "A1_A3": a1_a3,
        "A4": a4,
        "A5": a5,
        "B2_B5": b2_b5,
        "B6": b6,
        "C1_C4": c1_c4,
        "D1": module_d1,
    }
    return final_lca


# In the main app, after results are calculated:
#
#   scientific_lca = run_scientific_lca_from_app_params(current_params)
#   render_lca_audit_streamlit(st, scientific_lca)
#
# Use these headline values:
#   scientific_lca['gross_A_C_tCO2e']
#   scientific_lca['GWP_kgCO2e_per_pkm']
#   scientific_lca['module_D1_signed_tCO2e_separate']
#
# Never use the legacy RECYCLING_CREDIT_SCENARIOS result as scientific Module D.
