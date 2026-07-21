"""Integration patch for app_final_streamlit_ready (17).py.

Use this file as a guide for replacing the existing LCA core. It assumes that
lca_scientific_core.py is in the same directory as the Streamlit app.
"""

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
        "energy_intensity_choice": energy_intensity_choice,
        "project_ei": project_ei,
        "project_ei_source": project_ei_source,
        "a4_route_source": a4_route_source,
        "a4_scope": a4_scope,
        "a4_payload_assumption": a4_payload_assumption,
        "a5_diesel_scope": a5_diesel_scope,
        "a5_diesel_source": a5_diesel_source,
        "a5_electricity_source": a5_electricity_source,
        "a5_waste_source": a5_waste_source,
        "a5_waste_route_source": a5_waste_route_source,
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

    route_source = str(params.get("a4_route_source", "")).strip()
    if not route_source:
        if entered:
            return ([], "incomplete_sources",
                    "A4 distance/mode were set but no route/distance source was given → "
                    "A4 is EXCLUDED from the result (not counted as a measured zero).")
        return [], "unconnected", "No A4 transport entered."

    legs = []
    if advanced_present:
        # Advanced rows win; simple route is ignored → no double counting.
        for row in advanced:
            legs.append({
                "material": row.get("material", "not specified"),
                "mass_kg": float(row.get("mass_kg", 0.0)),
                "distance_km": float(row.get("distance_km", 0.0)),
                "mode": str(row.get("mode", mode_default)).lower(),
                "scope": scope,
                "mass_source": boq_source,
                "distance_source": route_source,
            })
    else:
        # Simple mode: one leg per material using the sourced A1-A3 masses.
        for material, quantity in masses.items():
            mass_kg = float(quantity.value)
            if mass_kg <= 0.0:
                continue
            legs.append({
                "material": material,
                "mass_kg": mass_kg,
                "distance_km": dist_default,
                "mode": mode_default,
                "scope": scope,
                "mass_source": boq_source or quantity.source,
                "distance_source": route_source,
            })
    return legs, "connected", ""


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
        return None, "unconnected", "A5 module is off."

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

    # ── A5.1 fuel ──────────────────────────────────────────────────────────────
    diesel_litres = None
    if diesel_mode == "equipment":
        if params.get("a5_equipment"):
            entered = True
            status = "incomplete_sources"
            notes.append("A5 diesel is in equipment-fleet mode; the scientific core needs total "
                         "litres. Provide simple total litres or the litres are excluded.")
    elif diesel_l > 0.0:
        entered = True
        if diesel_source:
            diesel_litres = ProjectQuantity(diesel_l, "L", diesel_source, "site diesel")
        else:
            status = "incomplete_sources"
            notes.append("A5 site diesel entered without a source → excluded.")

    # ── A5.2 electricity (construction-year CI) ────────────────────────────────
    electricity_kwh = None
    if elec_kwh > 0.0:
        entered = True
        if elec_source and grid_construction is not None:
            electricity_kwh = ProjectQuantity(elec_kwh, "kWh", elec_source, "site electricity")
        else:
            status = "incomplete_sources"
            notes.append("A5 site electricity entered without a source (or no construction-year "
                         "grid CI) → excluded.")

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

        # A5.4 production of wasted material — installed basis only (no double count).
        if boq_basis == "installed":
            extra_waste_materials_kg[material] = ProjectQuantity(
                w_kg, "kg", waste_source, "installed-basis waste production (E8)")

        # A5.5 waste transport.
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

        # A5.6 waste treatment (per-tonne verified factors; shares honoured where verified).
        route_codes = _A5_WASTE_ROUTE.get(material)
        if route_codes is None:
            status = "incomplete_sources"
            notes.append(f"A5 waste treatment for {material} has no verified GHG-2025 factor "
                         "(supply a documented override) → excluded.")
            continue
        shares = shares_ui.get(material, {"landfill": 1.0, "recycle": 0.0, "reuse": 0.0})
        landfill_kg = w_kg * float(shares.get("landfill", 1.0))
        recycle_kg = w_kg * float(shares.get("recycle", 0.0))
        # reuse share → no processing emission in A5 (documented); recovery benefit is Module D.
        if landfill_kg > 0.0:
            waste_treatment_items.append({
                "material": material, "waste_kg": landfill_kg, "waste_source": waste_source,
                "route": "landfill", "factor_code": route_codes["landfill"]})
        if recycle_kg > 0.0:
            code = route_codes["recycle"] or route_codes["landfill"]
            if route_codes["recycle"] is None:
                notes.append(f"A5 {material} recycling has no verified processing factor; "
                             "conservatively charged at the landfill factor.")
            waste_treatment_items.append({
                "material": material, "waste_kg": recycle_kg, "waste_source": waste_source,
                "route": "recycle", "factor_code": code})

    if not entered:
        return None, "unconnected", "A5 module on but no fuel/electricity/waste entered."

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
    return a5_kwargs, status, " ".join(notes)


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
        a4_status, a4_note = "connected", ""
    else:
        a4_legs, a4_status, a4_note = build_a4_scientific_legs(params, masses)
    a4 = calculate_transport_legs(a4_legs, "A4", default_scope="wtw") if a4_legs else {
        "stage": "A4", "total_tco2e": 0.0, "source_audit": [], "legs": []
    }
    a4_by_material, a4_by_mode = _a4_breakdown(a4)
    a4["by_material"] = a4_by_material
    a4["by_mode"] = a4_by_mode
    a4["status"] = a4_status
    a4["note"] = a4_note
    a4["equation_id"] = "E3_A4_C2"

    grid_source = str(params.get("grid_source", "")).strip()
    grid_location = str(params.get("grid_location", "")).strip()
    if not grid_source or not grid_location:
        raise ScientificInputError(
            "Egypt/project grid CI is still OPEN. Supply the official source file and table/page."
        )
    start_year = int(params.get("analysis_start_year", 1))
    grid_by_year = {}
    for offset in range(rsp):
        operating_year = offset + 1
        calendar_year = start_year + offset
        grid_by_year[operating_year] = GridCarbonYear(
            year=operating_year,
            generation_kgco2e_per_kwh=float(params.get("grid_generation", 0.0)),
            td_kgco2e_per_kwh=float(params.get("grid_td", 0.0)),
            upstream_kgco2e_per_kwh=float(params.get("grid_upstream", 0.0)),
            source_file=grid_source,
            location=f"{grid_location}; calendar year {calendar_year}",
            geographic_scope="Egypt/project electricity supply",
            note="Flat trajectory only if the source supports a constant factor; otherwise upload annual values.",
        )

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

    # A5 wired from the app editors (fuel + electricity + waste production/transport/treatment).
    a5_prebuilt = params.get("a5_scientific_inputs")
    if a5_prebuilt:
        a5 = calculate_a5(**a5_prebuilt)
        a5_status, a5_note = "connected", ""
    else:
        a5_kwargs, a5_status, a5_note = build_a5_scientific_activity(
            params, masses, grid_by_year.get(1))
        if a5_kwargs is not None:
            a5 = calculate_a5(**a5_kwargs)
        else:
            a5 = {"stage": "A5", "total_tco2e": 0.0, "source_audit": []}
    a5["status"] = a5_status
    a5["note"] = a5_note

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

    final_lca = combine_lca_modules(a1_a3, a4, a5, b2_b5, b6, c1_c4, module_d1)
    checks = publication_checks(
        masses,
        grid_by_year,
        final_lca["source_audit"],
        assessment_period_years=rsp,
    )

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
    # A stage is part of the reported partial number only when it is actually connected.
    scope_connected = {s: (st == "connected") for s, st in stage_status.items()}

    # partial-scope grade = the CONNECTED stages are fully sourced (no OPEN factor,
    # FRP handled, one grid record per year). This is what publication_checks verifies.
    publication_grade_partial_scope = bool(checks.get("publication_grade", False))
    # full whole-life grade additionally requires EVERY optional stage done (connected
    # or justified not_applicable). incomplete_sources / unconnected keep it False.
    required_full = ["A4", "A5", "B2-B5", "C1-C4"]
    publication_grade_full_wlca = (
        publication_grade_partial_scope
        and all(stage_status[s] in _DONE for s in required_full)
    )

    connected = [s for s, st in stage_status.items() if st == "connected"]
    scope_included = [s for s, st in stage_status.items() if st in _DONE]
    unconnected = [s for s, st in stage_status.items() if st not in _DONE]
    incomplete = [s for s, st in stage_status.items() if st == "incomplete_sources"]

    final_lca["publication_checks"] = checks
    final_lca["publication_grade_partial_scope"] = publication_grade_partial_scope
    final_lca["publication_grade_full_wlca"] = publication_grade_full_wlca
    final_lca["stage_status"] = stage_status
    final_lca["scope_connected"] = scope_connected
    final_lca["connected_stages"] = connected
    final_lca["unconnected_stages"] = unconnected
    final_lca["incomplete_source_stages"] = incomplete
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
