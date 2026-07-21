"""Integration patch for app_final_streamlit_ready (17).py.

Use this file as a guide for replacing the existing LCA core. It assumes that
lca_scientific_core.py is in the same directory as the Streamlit app.
"""

from lca_scientific_core import (
    B6_ENERGY_INTENSITY,
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

    Returns (legs, connected, note). A4 only connects when an A4 route/distance
    source is supplied: in publication we never invent an unsourced 50 km distance.
    The distance value itself is attested by the route source; masses reuse the BOQ
    source. EF comes from the registry mode/scope factor (WTW preferred).
    """
    route_source = str(params.get("a4_route_source", "")).strip()
    if not route_source:
        return [], False, "A4 route/distance source is open → A4 not connected (no fabricated distance)."

    scope = str(params.get("a4_scope", "wtw")).lower()
    boq_source = str(params.get("boq_source", "")).strip()
    mode_default = str(params.get("transport_mode", "truck")).lower()
    dist_default = float(params.get("transport_distance_km", 0.0))
    a4_mode = str(params.get("a4_mode", "simple")).lower()

    legs = []
    advanced = params.get("a4_advanced_legs")
    if a4_mode == "advanced" and advanced:
        # Per-material / multi-leg rows from the advanced editor. A float ef override
        # in the UI is intentionally NOT used as a scientific factor (no source); the
        # sourced registry mode/scope factor is used instead.
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
    return legs, True, ""


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
        a4_connected, a4_note = True, ""
    else:
        a4_legs, a4_connected, a4_note = build_a4_scientific_legs(params, masses)
    a4 = calculate_transport_legs(a4_legs, "A4", default_scope="wtw") if a4_legs else {
        "stage": "A4", "total_tco2e": 0.0, "source_audit": [], "legs": []
    }

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

    a5_inputs = params.get("a5_scientific_inputs") or {}
    a5_connected = bool(a5_inputs)
    a5 = calculate_a5(**a5_inputs) if a5_inputs else {
        "stage": "A5", "total_tco2e": 0.0, "source_audit": []
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

    final_lca = combine_lca_modules(a1_a3, a4, a5, b2_b5, b6, c1_c4, module_d1)
    checks = publication_checks(
        masses,
        grid_by_year,
        final_lca["source_audit"],
        assessment_period_years=rsp,
    )

    # ── Two-level publication grade ──────────────────────────────────────────
    # A1-A3 and B6 always reach this point sourced (else the run raised earlier).
    scope_connected = {
        "A1-A3": True,
        "A4": bool(a4_connected),
        "A5": a5_connected,
        "B2-B5": b2b5_connected,
        "B6": True,
        "C1-C4": c1c4_connected,
    }
    # partial-scope grade = the CONNECTED stages are fully sourced (no OPEN factor,
    # FRP handled, one grid record per year). This is what publication_checks verifies.
    publication_grade_partial_scope = bool(checks.get("publication_grade", False))
    # full whole-life grade additionally requires EVERY optional stage connected.
    required_full = ["A4", "A5", "B2-B5", "C1-C4"]
    publication_grade_full_wlca = (
        publication_grade_partial_scope
        and all(scope_connected[s] for s in required_full)
    )

    connected = [s for s, v in scope_connected.items() if v]
    unconnected = [s for s, v in scope_connected.items() if not v]

    final_lca["publication_checks"] = checks
    final_lca["publication_grade_partial_scope"] = publication_grade_partial_scope
    final_lca["publication_grade_full_wlca"] = publication_grade_full_wlca
    final_lca["scope_connected"] = scope_connected
    final_lca["connected_stages"] = connected
    final_lca["unconnected_stages"] = unconnected
    # Alias: the combined value is a PARTIAL, connected-scope total until every stage is wired.
    final_lca["connected_scope_tCO2e"] = final_lca["gross_A_C_tCO2e"]
    final_lca["scope_label"] = "Scientific partial LCA: " + " + ".join(connected)
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
