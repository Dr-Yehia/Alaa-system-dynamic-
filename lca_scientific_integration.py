"""Integration patch for app_final_streamlit_ready (17).py.

Use this file as a guide for replacing the existing LCA core. It assumes that
lca_scientific_core.py is in the same directory as the Streamlit app.
"""

import math

import pandas as pd

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

    st.markdown("#### A1-A3 material EPD overrides (win over the ICE proxy)")
    st.caption("Supply a product/project EPD to override the generic ICE factor for any material. "
               "FRP has NO verified ICE factor → it needs an EPD here (or FRP mass = 0), otherwise "
               "the A1-A3 result is blocked. Each row needs a value + source_file + source_location.")
    _mats6 = ["concrete", "steel", "aluminum", "wood", "frp", "glass"]
    _epd0 = pd.DataFrame({
        "material": _mats6, "gwp_value": [0.0] * 6,
        "factor_unit": ["kgCO2e/kg"] * 6, "conversion_factor_to_kg_basis": [0.0] * 6,
        "conversion_source": [""] * 6,
        "declared_unit": [""] * 6, "declared_boundary": [""] * 6,
        "source_file": [""] * 6, "source_location": [""] * 6,
        "manufacturer": [""] * 6, "product_name": [""] * 6, "epd_number": [""] * 6,
        "programme_operator": [""] * 6, "issue_date": [""] * 6, "expiry_date": [""] * 6,
        "geography": [""] * 6,
        "verification_status": [""] * 6, "factor_basis": ["project_specific"] * 6})
    st.caption("gwp_value is in factor_unit. If factor_unit ≠ kgCO2e/kg, a NUMERIC "
               "conversion_factor_to_kg_basis + source are required (per tonne → 0.001; per m³ → "
               "1/density). verification_status: third_party_verified / programme_operator_verified.")
    _epd_edit = st.data_editor(_epd0, hide_index=True, use_container_width=True,
                               key="lca_material_epd_editor", disabled=["material"])
    _num = {"gwp_value", "conversion_factor_to_kg_basis"}
    material_epd_overrides = []
    for _, _r in pd.DataFrame(_epd_edit).iterrows():
        if float(_r["gwp_value"] or 0.0) > 0.0:
            _row = {k: (float(_r[k]) if k in _num else str(_r[k])) for k in _epd0.columns}
            _row["gwp_kgco2e_per_kg"] = _row.pop("gwp_value")  # value in factor_unit; converted downstream
            material_epd_overrides.append(_row)

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
    grid_annual_series = {}
    grid_annual_duplicate_years = []
    grid_annual_invalid_years = False
    if grid_mode == "annual_official_series":
        _rsp = int(st.session_state.get("lca_rsp_years", assessment_lifetime_default) or
                   assessment_lifetime_default)
        _sy = int(st.session_state.get("start_year", 2026) or 2026)
        _gdf0 = pd.DataFrame({
            "calendar_year": [_sy + i for i in range(_rsp)],
            "generation": [0.0] * _rsp, "td": [0.0] * _rsp, "upstream": [0.0] * _rsp,
            "source_file": [""] * _rsp, "source_location": [""] * _rsp,
            "geography": ["Egypt"] * _rsp})
        _gedit = pd.DataFrame(st.data_editor(_gdf0, hide_index=True, use_container_width=True,
                                             key="lca_grid_annual_editor", num_rows="dynamic"))
        # Detect duplicate / invalid years in the UI BEFORE collapsing to a dict (a dict
        # would silently overwrite a repeated year).
        _years = []
        for _v in _gedit["calendar_year"].tolist():
            try:
                _f = float(_v)
                # A non-integer year (e.g. 2026.5) must be REJECTED, not silently truncated.
                _years.append(int(_f) if math.isfinite(_f) and _f.is_integer() else None)
            except (TypeError, ValueError):
                _years.append(None)
        grid_annual_duplicate_years = sorted({y for y in _years if y is not None and _years.count(y) > 1})
        grid_annual_invalid_years = any(y is None for y in _years)
        for _, _r in _gedit.iterrows():
            try:
                _yr = int(_r["calendar_year"])
            except (TypeError, ValueError):
                continue
            grid_annual_series[_yr] = {
                "generation": float(_r["generation"]), "td": float(_r["td"]),
                "upstream": float(_r["upstream"]), "source_file": str(_r["source_file"]),
                "source_location": str(_r["source_location"]), "geography": str(_r["geography"])}
        st.caption("Every study year needs a row with its OWN source_file + source_location. "
                   "A missing year, a duplicate year, or an unsourced row blocks the result.")

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
    st.caption("Road return trip (RICS): outward-laden + documented empty-running. Applied to road "
               "only. No hard-coded 0.5. Unit-aware: a tonne-km factor multiplies the load mass; a "
               "vehicle-km factor multiplies the number of empty vehicle trips (never the payload).")
    a4_return_factor_unit = st.selectbox(
        "A4 return-factor unit", ["tonne_km", "vehicle_km"], index=0, key="lca_a4_return_unit")
    a4_return_fraction = st.number_input(
        "A4 empty-return fraction — tonne_km only (0 = off)", value=0.0, min_value=0.0, max_value=1.0,
        step=0.05, format="%.2f", key="lca_a4_return_fraction")
    a4_empty_return_factor = st.number_input(
        "A4 empty-running EF (per tonne.km OR per vehicle.km, 0 = off)", value=0.0, min_value=0.0,
        step=0.001, format="%.5f", key="lca_a4_empty_return_factor")
    a4_number_of_trips = st.number_input(
        "A4 number of empty return trips — vehicle_km only", value=0.0, min_value=0.0,
        step=1.0, key="lca_a4_number_of_trips")
    a4_vehicle_capacity = st.number_input(
        "A4 vehicle capacity (tonnes) — vehicle_km, derives trips", value=0.0, min_value=0.0,
        step=1.0, key="lca_a4_vehicle_capacity",
        help="If given (and trips left 0), trips = ceil(route mass / (capacity × load factor)). "
             "Do not give both capacity and an explicit trip count.")
    a4_load_factor = st.number_input(
        "A4 load factor (0–1) — vehicle_km derivation", value=1.0, min_value=0.01, max_value=1.0,
        step=0.05, format="%.2f", key="lca_a4_load_factor")
    a4_return_source = st.text_input(
        "A4 return-assumption source (file + location)", value="", key="lca_a4_return_source")

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
    st.caption("A5 component declarations: mark any component you did NOT enter as documented_zero "
               "/ not_applicable_with_justification / optional_not_reported (with a justification + "
               "source). A blank 'not_entered' keeps A5 incomplete.")
    _a5comps = ["A5.2_site_fuel", "A5.2_site_electricity", "A5.2_temporary_works",
                "A5.3_waste_generation", "A5.3_waste_transport", "A5.3_waste_treatment"]
    _a5decl0 = pd.DataFrame({
        "component": _a5comps, "declaration": [""] * len(_a5comps),
        "justification": [""] * len(_a5comps), "source": [""] * len(_a5comps)})
    _a5decl_edit = pd.DataFrame(st.data_editor(
        _a5decl0, hide_index=True, use_container_width=True,
        key="lca_a5_component_decl_editor", disabled=["component"]))
    a5_component_declarations = {}
    for _, _r in _a5decl_edit.iterrows():
        _decl = str(_r["declaration"]).strip()
        _just = str(_r["justification"]).strip()
        _src = str(_r["source"]).strip()
        if _decl not in ("documented_zero", "not_applicable_with_justification", "optional_not_reported"):
            continue
        # documented_zero and N-A must carry BOTH a justification and a source; optional
        # only needs a disclosure note. Store the FULL record so it reaches audit/gate.
        if _decl in ("documented_zero", "not_applicable_with_justification") and not (_just and _src):
            continue
        a5_component_declarations[str(_r["component"])] = {
            "status": _decl, "justification": _just, "source": _src}

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
        "grid_annual_series": grid_annual_series,
        "grid_annual_duplicate_years": grid_annual_duplicate_years,
        "grid_annual_invalid_years": grid_annual_invalid_years,
        "material_epd_overrides": material_epd_overrides,
        "energy_intensity_choice": energy_intensity_choice,
        "project_ei": project_ei,
        "project_ei_source": project_ei_source,
        "a4_route_source": a4_route_source,
        "a4_scope": a4_scope,
        "a4_payload_assumption": a4_payload_assumption,
        "a4_return_fraction": a4_return_fraction,
        "a4_empty_return_factor": a4_empty_return_factor,
        "a4_return_source": a4_return_source,
        "a4_return_factor_unit": a4_return_factor_unit,
        "a4_number_of_trips": a4_number_of_trips,
        "a4_vehicle_capacity": a4_vehicle_capacity,
        "a4_load_factor": a4_load_factor,
        "a5_diesel_scope": a5_diesel_scope,
        "a5_diesel_source": a5_diesel_source,
        "a5_electricity_source": a5_electricity_source,
        "a5_waste_source": a5_waste_source,
        "a5_waste_route_source": a5_waste_route_source,
        "a5_construction_year": int(a5_construction_year),
        "a5_component_declarations": a5_component_declarations,
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


def _boundary_covers_a1a3(boundary):
    """True only when the declared boundary covers the FULL A1-A3 product stage."""
    s = str(boundary).lower().replace("–", "-").replace("—", "-").replace(" ", "")
    if any(tok in s for tok in ("a1-a3", "a1toa3", "a1+a2+a3", "cradletogate", "cradle-to-gate")):
        return True
    return ("a1" in s) and ("a2" in s) and ("a3" in s)


def build_material_factor_overrides(params):
    """Build A1-A3 factor overrides from a per-material EPD editor.

    Each row (params['material_epd_overrides']) must carry: material, gwp value,
    declared unit, source_file, source_location. The EPD override takes priority over
    the ICE proxy. factor_basis defaults to project_specific; set 'virgin' only when the
    EPD is an explicitly virgin-route product (enables the recycled-content mix).
    """
    rows = params.get("material_epd_overrides") or []
    overrides = {}
    for row in rows:
        material = str(row.get("material", "")).strip().lower()
        val = row.get("gwp_kgco2e_per_kg")
        if not material or val in (None, "") or float(val) <= 0.0:
            continue  # row not started
        src = str(row.get("source_file", "")).strip()
        loc = str(row.get("source_location", "")).strip()
        declared_unit = str(row.get("declared_unit", "")).strip()
        boundary = str(row.get("declared_boundary", row.get("boundary", "")).strip() or "").strip()
        # A row with a value BUT incomplete provenance must NOT silently fall back to ICE.
        missing = [k for k, v in (("source_file", src), ("source_location", loc),
                                  ("declared_unit", declared_unit), ("declared_boundary", boundary))
                   if not v]
        if missing:
            raise ScientificInputError(
                f"EPD entered for {material} but excluded because {', '.join(missing)} is "
                "incomplete; the ICE proxy was NOT silently substituted.")
        # The declared boundary must actually cover A1-A3 (not just mention A1).
        if not _boundary_covers_a1a3(boundary):
            raise ScientificInputError(
                f"EPD for {material} declared_boundary '{boundary}' must cover the FULL A1-A3 "
                "(e.g. 'A1-A3', 'A1 + A2 + A3', or 'cradle-to-gate including A1, A2 and A3').")
        # UNIT CONVERSION — applied NUMERICALLY, never assumed. EF_kg = EF_declared × conv.
        factor_unit = str(row.get("factor_unit", "kgCO2e/kg")).strip() or "kgCO2e/kg"
        original_val = float(val)
        if factor_unit == "kgCO2e/kg":
            ef_kg = original_val
            conv_note = "already per kg"
        else:
            conv = float(row.get("conversion_factor_to_kg_basis", 0.0) or 0.0)
            conv_src = str(row.get("conversion_source", "")).strip()
            if conv <= 0.0 or not conv_src:
                raise ScientificInputError(
                    f"EPD for {material} is in {factor_unit}; it needs a positive numeric "
                    "conversion_factor_to_kg_basis and a conversion_source (e.g. per tonne → "
                    "×0.001; per m³ → ×1/density).")
            ef_kg = original_val * conv
            conv_note = (f"converted {original_val} {factor_unit} × {conv} = {ef_kg} kgCO2e/kg "
                         f"(source: {conv_src})")
        # Verification status → evidence status (enum-driven, not text-presence).
        vstat = str(row.get("verification_status", "")).strip().lower()
        if vstat == "third_party_verified":
            status = "project_specific_verified"
        elif vstat == "programme_operator_verified":
            status = "project_specific_documented"
        else:
            status = "project_specific_user_supplied"
        overrides[material] = make_project_evidence(
            code=f"EPD-{material}", value=ef_kg, unit="kgCO2e/kg", stage="A1-A3",
            source_file=src, location=loc, boundary_scope=boundary,
            note=f"EPD override; declared_unit={declared_unit}; {conv_note}; "
                 f"geography={row.get('geography', 'n/a')}; "
                 f"validity={row.get('expiry_date', row.get('validity', 'n/a'))}",
            factor_basis=str(row.get("factor_basis", "project_specific")), status=status)
    return overrides


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
    # Unit-aware: tonne_km multiplies load mass; vehicle_km multiplies empty vehicle trips.
    return_fraction = float(params.get("a4_return_fraction", 0.0))
    empty_return_ef = float(params.get("a4_empty_return_factor", 0.0))
    return_source = str(params.get("a4_return_source", "")).strip()
    return_unit = str(params.get("a4_return_factor_unit", "tonne_km")).lower()
    return_trips = float(params.get("a4_number_of_trips", 0.0))
    vehicle_capacity_t = float(params.get("a4_vehicle_capacity", 0.0))
    return_load_factor = float(params.get("a4_load_factor", 1.0)) or 1.0
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

    # In ADVANCED mode a single GLOBAL explicit trip count would be applied to every
    # material/segment → double counting. Advanced vehicle-km must derive trips per segment
    # from vehicle capacity; an explicit global trip count is only allowed in simple mode.
    if advanced_present and return_unit == "vehicle_km" and return_trips > 0.0:
        return ([], "validation_failed",
                "A4 advanced + vehicle-km: a global number_of_trips would be double-counted across "
                "segments. Use vehicle_capacity (per-segment derivation) instead.", [])

    legs, audit = [], []
    return_leg_added = False
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
                # Unit-aware: a tonne-km factor multiplies the load mass; a vehicle-km factor
                # multiplies the number of (empty) vehicle trips, never the payload mass.
                if mode == "truck" and empty_return_ef > 0.0 and return_source:
                    if return_unit == "vehicle_km":
                        route_mass_t = route_mass / 1000.0  # kg → tonnes
                        # Trips are either explicitly counted OR derived from vehicle
                        # capacity × load factor — never both (that would double-specify).
                        if return_trips > 0.0 and vehicle_capacity_t > 0.0:
                            return ([], "validation_failed",
                                    "A4 vehicle-km return: give EITHER number_of_trips OR "
                                    "vehicle_capacity (+load factor), not both.", [])
                        trips = return_trips
                        if trips <= 0.0 and vehicle_capacity_t > 0.0 and route_mass_t > 0.0:
                            trips = math.ceil(route_mass_t / (vehicle_capacity_t * return_load_factor))
                        if trips > 0.0 and route_mass_t > 0.0:
                            # Express the vehicle-km return exactly through the tonne-km core by
                            # using an equivalent per-tonne.km factor for this leg only.
                            ef_eq = trips * empty_return_ef / route_mass_t
                            ret_ev = make_project_evidence(
                                code=f"A4-ROAD-RETURN-VEH-{material}-{rid}-{seg['segment_no']}",
                                value=ef_eq, unit="kgCO2e/tonne.km", stage="A4",
                                source_file=return_source,
                                location=f"vehicle-km empty-return: trips={trips}, "
                                         f"EF_vehicle_km={empty_return_ef}",
                                boundary_scope="A4 road empty-return (vehicle-km basis)",
                                note=payload or "documented vehicle-km return-trip assumption")
                            legs.append({
                                "material": material, "mass_kg": route_mass,
                                "distance_km": distance_km, "mode": mode, "scope": scope,
                                "mass_source": mass_src, "distance_source": return_source,
                                "factor_override": ret_ev})
                            audit.append({
                                "stage": "A4", "material": material, "route_id": rid,
                                "route_share": route["share"], "segment_no": seg["segment_no"],
                                "leg": "return", "mass_kg": route_mass, "mass_source": mass_src,
                                "distance_km": distance_km, "distance_source": return_source,
                                "mode": mode, "scope": scope, "payload_assumption": payload or "not stated",
                                "return_assumption": f"vehicle-km trips={trips}, "
                                                     f"EF_vehicle_km={empty_return_ef}"})
                            return_leg_added = True
                    elif return_fraction > 0.0:  # tonne_km basis (default)
                        ret_ev = make_project_evidence(
                            code=f"A4-ROAD-RETURN-{material}-{rid}-{seg['segment_no']}",
                            value=empty_return_ef, unit="kgCO2e/tonne.km", stage="A4",
                            source_file=return_source,
                            location=f"documented empty-return: fraction={return_fraction}",
                            boundary_scope="A4 road empty-return running",
                            note=payload or "documented road return-trip assumption")
                        legs.append({
                            "material": material, "mass_kg": route_mass,
                            "distance_km": distance_km * return_fraction, "mode": mode, "scope": scope,
                            "mass_source": mass_src, "distance_source": return_source,
                            "factor_override": ret_ev})
                        audit.append({
                            "stage": "A4", "material": material, "route_id": rid,
                            "route_share": route["share"], "segment_no": seg["segment_no"],
                            "leg": "return", "mass_kg": route_mass, "mass_source": mass_src,
                            "distance_km": distance_km * return_fraction, "distance_source": return_source,
                            "mode": mode, "scope": scope, "payload_assumption": payload or "not stated",
                            "return_assumption": f"tonne-km empty-return fraction={return_fraction}, "
                                                 f"EF={empty_return_ef}"})
                        return_leg_added = True

    # Every segment must carry its own distance source (per-route/segment, not one global).
    if any(a.get("distance_source") in (None, "", "MISSING") for a in audit):
        return ([], "incomplete_sources",
                "A4 has a route segment without a distance source → A4 excluded.", audit)

    note = ""
    road_present = any(s["mode"] == "truck" for mr in routes.values() for r in mr.values()
                       for s in r["segments"])
    # Outward-only note keys off whether a return leg was ACTUALLY added (tonne-km OR
    # vehicle-km), not off return_fraction alone.
    if road_present and not return_leg_added:
        note = ("Road legs are outward-only (average-laden factor); a documented empty-return "
                "assumption (empty-running EF + source, and fraction or vehicle trips) is required "
                "to add the return trip.")
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

    # A5.2 temporary works — a scope component that must be addressed (declared or computed).
    readiness.setdefault("A5.2_temporary_works", "not_entered")

    # Per-component declarations let the user mark an un-entered component as documented_zero
    # or not_applicable (with reason) or optional_not_reported. A bare 'not_entered' is NOT
    # a completed state.
    declarations = params.get("a5_component_declarations") or {}
    _ALLOWED_DECL = {"documented_zero", "not_applicable_with_justification", "optional_not_reported"}
    for comp, st_val in list(readiness.items()):
        if st_val == "not_entered":
            _d = declarations.get(comp, "")
            decl = str(_d.get("status", "") if isinstance(_d, dict) else _d).strip()
            if decl in _ALLOWED_DECL:
                readiness[comp] = decl

    if not entered:
        return (None, "unconnected", "A5 module on but no fuel/electricity/waste entered.",
                readiness)

    # A5 is 'connected' only when NO component is still not_entered or incomplete_sources.
    _bad = [c for c, v in readiness.items() if v in ("not_entered", "incomplete_sources")]
    if _bad and status == "connected":
        status = "incomplete_sources"
        notes.append("A5 components not fully addressed (declare documented_zero / N-A / "
                     f"optional, or complete them): {', '.join(sorted(_bad))}.")

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


def build_module_d_rows_from_c3(c1_c4_result, cfg):
    """Derive Module D substitution rows from C3 recovered flows.

    RecoveredOutput_D must NOT exceed the C3 recovered mass (reuse+recycle) of the
    material. Module D stays separate from Gross A-C. cfg is a mapping:
      {material: {recovered_output_kg, secondary_input_kg, substitution_ratio,
                  flow_source, substitution_source, primary_factor, recovery_factor}}.
    """
    rows = []
    per_material_recovered = {}
    for r in c1_c4_result.get("treatment_rows", []):
        m = r.get("material", "not specified")
        recovered = float(r.get("mass_kg", 0.0)) * (
            float(r.get("reuse_share", 0.0)) + float(r.get("recycle_share", 0.0)))
        per_material_recovered[m] = per_material_recovered.get(m, 0.0) + recovered
    for material, row in (cfg or {}).items():
        recovered_output = float(row.get("recovered_output_kg", 0.0))
        c3_recovered = per_material_recovered.get(material, 0.0)
        if recovered_output > c3_recovered + 1e-6:
            raise ScientificInputError(
                f"Module D recovered output for {material} ({recovered_output} kg) exceeds the "
                f"C3 recovered mass ({c3_recovered} kg).")
        rows.append({
            "material": material,
            "recovered_output_kg": recovered_output,
            "secondary_input_kg": float(row.get("secondary_input_kg", 0.0)),
            "substitution_ratio": float(row.get("substitution_ratio", 0.0)),
            "flow_source": row.get("flow_source", ""),
            "substitution_source": row.get("substitution_source", ""),
            "primary_factor": row.get("primary_factor"),
            "recovery_to_substitution_factor": row.get("recovery_factor"),
        })
    return rows


_B2B5_MODULES = ("B2", "B3", "B4", "B5")
_A1A3_MATERIALS = ("concrete", "steel", "aluminum", "wood", "frp", "glass")
_TRANSPORT_MODES = ("truck", "rail", "ship")
# removed_same_event is intentionally NOT allowed yet (needs removed-flow reconciliation).
_MASS_ROLES = ("retained_in_asset", "consumable", "temporary")


def _valid_module_declaration(decl):
    """A module declaration counts only with status + justification + source (file)."""
    if not isinstance(decl, dict):
        return None
    status = str(decl.get("status", "")).strip()
    if status not in ("documented_zero", "not_applicable_with_justification"):
        return None
    just = str(decl.get("justification", "")).strip()
    src = str(decl.get("source", "") or decl.get("source_file", "")).strip()
    return status if (just and src) else None


def _pos_int_year(raw):
    """Return an int year only if raw is a finite integer value; else None."""
    try:
        f = float(raw)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f) or not f.is_integer():
        return None
    return int(f)


def build_b2b5_events_from_rows(rows, rsp, module_declarations=None):
    """Build validated B2-B5 events from a flat editor (one material-activity per row).

    Returns (events, module_status, note). Activity-based (NOT a % of A1-A3, NOT
    cost-to-carbon). Hardened rules:
      * module ∈ {B2,B3,B4,B5}; integer 1 ≤ year ≤ RSP (a fractional year is rejected).
      * all rows of one event_id must agree on module / year / asset / event_source.
      * per-material / diesel / electricity are SUMMED across rows (never overwritten);
        the carbon mass and the mass-balance mass are the same.
      * ANY positive value missing its source (material, removed, diesel, electricity,
        transport, waste) marks the module incomplete — never silently ignored.
      * mass_role governs the mass balance: only 'retained_in_asset' new material enters
        the remaining mass; consumables/temporary do not. Removed mass needs its own source.
      * each of B2/B3/B4/B5 has an INDEPENDENT status; the stage is closed only when all
        four are connected / documented_zero / not_applicable_with_justification.
    """
    module_declarations = module_declarations or {}
    by_event = {}
    order = []
    for r in rows or []:
        eid = str(r.get("event_id", "")).strip()
        if not eid:
            continue
        if eid not in by_event:
            order.append(eid)
        by_event.setdefault(eid, []).append(r)

    events = []
    module_seen, module_bad = set(), set()
    notes = []
    for eid in order:
        erows = by_event[eid]
        head = erows[0]
        module = str(head.get("module", "")).strip().upper()
        esrc = str(head.get("event_source", "")).strip()
        asset = str(head.get("asset", "")).strip()
        year = _pos_int_year(head.get("year", None))
        if module not in _B2B5_MODULES:
            notes.append(f"Event {eid}: module must be B2/B3/B4/B5."); continue
        module_seen.add(module)
        # All rows of the event must agree on the identifying fields.
        for r in erows:
            if (str(r.get("module", "")).strip().upper() != module
                    or _pos_int_year(r.get("year", None)) != year
                    or str(r.get("event_source", "")).strip() != esrc
                    or str(r.get("asset", "")).strip() != asset):
                module_bad.add(module)
                notes.append(f"Event {eid}: rows disagree on module/year/asset/source.")
                break
        else:
            if year is None or not (1 <= year <= rsp):
                module_bad.add(module); notes.append(f"Event {eid}: integer year within 1..{rsp} required."); continue
            if not esrc:
                module_bad.add(module); notes.append(f"Event {eid}: event_source required."); continue

            new_materials_kg_sum, added, removed = {}, {}, {}
            diesel_total, diesel_srcs = 0.0, []
            elec_total, elec_srcs = 0.0, []
            transport_legs, waste_items = [], []
            has_activity, bad = False, False

            def _num(v):
                try:
                    f = float(v or 0.0)
                    return f if math.isfinite(f) and f >= 0.0 else None
                except (TypeError, ValueError):
                    return None

            for r in erows:
                mat = str(r.get("new_material", "")).strip().lower()
                nkg = _num(r.get("new_material_kg"))
                if mat or (r.get("new_material_kg") not in (None, "", 0, 0.0)):
                    if nkg is None:
                        bad = True; notes.append(f"Event {eid}: invalid new_material_kg.")
                    elif nkg > 0.0:
                        role = str(r.get("mass_role", "retained_in_asset")).strip() or "retained_in_asset"
                        if mat not in _A1A3_MATERIALS:
                            bad = True; notes.append(f"Event {eid}: unknown new_material '{mat}'.")
                        elif role not in _MASS_ROLES:
                            bad = True; notes.append(f"Event {eid}: invalid mass_role '{role}'.")
                        elif not str(r.get("material_source", "")).strip():
                            bad = True; notes.append(f"Event {eid} {mat}: new material without source.")
                        else:
                            new_materials_kg_sum[mat] = new_materials_kg_sum.get(mat, 0.0) + nkg
                            if role == "retained_in_asset":
                                added[mat] = added.get(mat, 0.0) + nkg
                            has_activity = True
                rmat = str(r.get("removed_material", "")).strip().lower()
                rkg = _num(r.get("removed_material_kg"))
                if rmat or (r.get("removed_material_kg") not in (None, "", 0, 0.0)):
                    if rkg is None:
                        bad = True; notes.append(f"Event {eid}: invalid removed_material_kg.")
                    elif rkg > 0.0:
                        if not str(r.get("removed_material_source", "")).strip():
                            bad = True; notes.append(f"Event {eid} {rmat}: removed mass without source.")
                        else:
                            removed[rmat] = removed.get(rmat, 0.0) + rkg
                            has_activity = True
                dl = _num(r.get("diesel_l"))
                if dl is None:
                    bad = True; notes.append(f"Event {eid}: invalid diesel_l.")
                elif dl > 0.0:
                    if not str(r.get("diesel_source", "")).strip():
                        bad = True; notes.append(f"Event {eid}: diesel without source.")
                    else:
                        diesel_total += dl; diesel_srcs.append(str(r.get("diesel_source")).strip()); has_activity = True
                ek = _num(r.get("elec_kwh"))
                if ek is None:
                    bad = True; notes.append(f"Event {eid}: invalid elec_kwh.")
                elif ek > 0.0:
                    if not str(r.get("elec_source", "")).strip():
                        bad = True; notes.append(f"Event {eid}: electricity without source.")
                    else:
                        elec_total += ek; elec_srcs.append(str(r.get("elec_source")).strip()); has_activity = True
                tkm = _num(r.get("transport_km"))
                if tkm is None:
                    bad = True; notes.append(f"Event {eid}: invalid transport_km.")
                elif tkm > 0.0:
                    _tmode = str(r.get("transport_mode", "truck")).strip().lower() or "truck"
                    if not (str(r.get("transport_source", "")).strip() and mat and nkg):
                        bad = True; notes.append(f"Event {eid}: transport without source/material.")
                    elif _tmode not in _TRANSPORT_MODES:
                        bad = True; notes.append(f"Event {eid}: unknown transport mode '{_tmode}'.")
                    else:
                        transport_legs.append({
                            "material": mat, "mass_kg": nkg, "distance_km": tkm, "mode": _tmode,
                            "scope": "wtw", "mass_source": esrc,
                            "distance_source": str(r.get("transport_source")).strip()})
                        has_activity = True
                wkg = _num(r.get("waste_kg"))
                wcode = str(r.get("waste_factor_code", "")).strip()
                if wkg is None:
                    bad = True; notes.append(f"Event {eid}: invalid waste_kg.")
                elif wkg > 0.0:
                    if not (wcode in WASTE_EF and str(r.get("waste_source", "")).strip()):
                        bad = True; notes.append(f"Event {eid}: waste needs a known factor_code + source.")
                    else:
                        waste_items.append({"material": rmat or mat or "not specified", "waste_kg": wkg,
                                            "waste_source": str(r.get("waste_source")).strip(),
                                            "factor_code": wcode})
                        has_activity = True

            if bad or not has_activity:
                module_bad.add(module)
                if not has_activity and not bad:
                    notes.append(f"Event {eid} ({module}): no real activity → not complete.")
                continue

            new_materials = {m: ProjectQuantity(v, "kg", esrc, f"{module} new material (summed)")
                             for m, v in new_materials_kg_sum.items()}
            diesel = ProjectQuantity(diesel_total, "L", "; ".join(diesel_srcs), f"{module} diesel (summed)") \
                if diesel_total > 0.0 else None
            elec = ProjectQuantity(elec_total, "kWh", "; ".join(elec_srcs), f"{module} electricity (summed)") \
                if elec_total > 0.0 else None
            events.append({
                "event_id": eid, "asset": asset, "module": module, "year": year,
                "event_sequence": _pos_int_year(head.get("event_sequence", 1)) or 1,
                "event_source": esrc,
                "new_materials_kg": new_materials, "diesel_litres": diesel, "diesel_scope": "wtw",
                "electricity_kwh": elec, "transport_legs": transport_legs, "waste_items": waste_items,
                "added_mass_kg": added, "removed_mass_kg": removed})

    # Per-module status; a seen-but-not-bad module with at least one event is connected.
    # A module declaration only counts when it carries status + justification + source.
    _has_event = {m: any(e["module"] == m for e in events) for m in _B2B5_MODULES}
    module_status = {}
    for m in _B2B5_MODULES:
        decl_status = _valid_module_declaration(module_declarations.get(m))
        if m in module_bad:
            module_status[m] = "incomplete_sources"
        elif _has_event[m]:
            module_status[m] = "connected"
        elif decl_status:
            module_status[m] = decl_status
        else:
            module_status[m] = "unconnected"
    return events, module_status, " ".join(notes)


def chronological_mass_balance(initial_masses, events):
    """Apply B4/B5 add/remove event-by-event in YEAR order; the mass must stay ≥ 0 after
    EACH event (not only at the end). Returns (remaining_masses, rows, ok, error)."""
    running = {m: float(q.value) for m, q in initial_masses.items()}
    src = {m: q.source for m, q in initial_masses.items()}
    rows = []
    # Order within the same year is defined by event_sequence, then event_id (deterministic).
    for e in sorted(events, key=lambda x: (int(x.get("year", 0)),
                                           int(x.get("event_sequence", 1)),
                                           str(x.get("event_id", "")))):
        for mat, kg in (e.get("removed_mass_kg") or {}).items():
            running[mat] = running.get(mat, 0.0) - float(kg)
        for mat, kg in (e.get("added_mass_kg") or {}).items():
            running[mat] = running.get(mat, 0.0) + float(kg)
        for mat, val in running.items():
            if val < -1e-6:
                return (initial_masses, rows, False,
                        f"Mass of {mat} goes negative ({val:.1f} kg) after event "
                        f"{e.get('event_id', '?')} in year {e.get('year')}.")
        rows.append({"event_id": e.get("event_id"), "year": e.get("year"),
                     "running_mass_kg": dict(running)})
    remaining = {m: ProjectQuantity(max(v, 0.0), "kg",
                                    f"chronological mass balance from {src.get(m, 'initial')}",
                                    "after B2-B5 events")
                 for m, v in running.items()}
    return remaining, rows, True, ""


def build_module_d_cfg_from_rows(rows):
    """Build the Module-D-from-C3 config from editor rows (numeric factors → Evidence)."""
    cfg = {}
    for r in rows or []:
        mat = str(r.get("material", "")).strip().lower()
        recovered = float(r.get("recovered_output_kg", 0.0) or 0.0)
        if not mat or recovered <= 0.0:
            continue
        prim = float(r.get("primary_ef", 0.0) or 0.0)
        rec = float(r.get("recovery_ef", 0.0) or 0.0)
        psrc = str(r.get("primary_source", "")).strip()
        rsrc = str(r.get("recovery_source", "")).strip()
        if prim <= 0.0 or not psrc or not rsrc:
            raise ScientificInputError(
                f"Module D {mat}: primary EF (+source) and recovery EF source are required.")
        cfg[mat] = {
            "recovered_output_kg": recovered,
            "secondary_input_kg": float(r.get("secondary_input_kg", 0.0) or 0.0),
            "substitution_ratio": float(r.get("substitution_ratio", 0.0) or 0.0),
            "flow_source": str(r.get("flow_source", "")).strip() or psrc,
            "substitution_source": str(r.get("substitution_source", "")).strip() or psrc,
            "primary_factor": make_project_evidence(
                f"D-PRIM-{mat}", prim, "kgCO2e/kg", "D1", psrc, "Module D primary factor", "A1-A3"),
            "recovery_factor": make_project_evidence(
                f"D-REC-{mat}", rec, "kgCO2e/kg", "D1", rsrc, "Module D recovery factor", "recovery"),
        }
    return cfg


def build_c1c4_scientific_inputs(params, remaining_masses, grid_eol):
    """Build calculate_c1_c4 inputs from the C-stage editor, using the REMAINING mass
    after B2-B5 (the user cannot type a free C-stage mass).

    Returns (c_inputs_or_None, status, note, recovered_by_material). Per material:
    reuse+recycle+disposal shares must sum to 1 with a share source; C2 is a sourced
    route leg; disposal/recycle use verified per-tonne registry codes (or a documented
    override), reuse needs a documented (even 0) processing EF. C1 uses the EOL-year grid.
    """
    if not bool(params.get("include_c1c4", False)):
        return None, "unconnected", "C1-C4 module off.", {}, {}
    rows = params.get("c1c4_rows") or []
    if not rows:
        return None, "unconnected", "C1-C4 on but no rows entered.", {}, {}

    status, notes = "connected", []
    # C1 deconstruction fuel/electricity (EOL-year grid).
    c1_diesel = None
    dl = float(params.get("c1_diesel_l", 0.0) or 0.0)
    if dl > 0.0:
        if str(params.get("c1_diesel_source", "")).strip():
            c1_diesel = ProjectQuantity(dl, "L", str(params.get("c1_diesel_source")).strip(), "C1 diesel")
        else:
            status = "incomplete_sources"; notes.append("C1 diesel without source → excluded.")
    c1_elec = None
    ek = float(params.get("c1_elec_kwh", 0.0) or 0.0)
    if ek > 0.0:
        if str(params.get("c1_electricity_source", "")).strip() and grid_eol is not None:
            c1_elec = ProjectQuantity(ek, "kWh", str(params.get("c1_electricity_source")).strip(), "C1 electricity")
        else:
            status = "incomplete_sources"; notes.append("C1 electricity without source → excluded.")

    c2_legs, treatment_rows, recovered = [], [], {}
    for row in rows:
        mat = str(row.get("material", "")).strip().lower()
        if mat not in remaining_masses:
            continue
        mass = float(remaining_masses[mat].value)
        if mass <= 0.0:
            continue
        reuse = float(row.get("reuse_share", 0.0) or 0.0)
        recycle = float(row.get("recycle_share", 0.0) or 0.0)
        disposal = float(row.get("disposal_share", 0.0) or 0.0)
        share_src = str(row.get("share_source", "")).strip()
        if not share_src:
            status = "incomplete_sources"
            notes.append(f"C1-C4 {mat}: EOL shares need a source → excluded."); continue
        if min(reuse, recycle, disposal) < 0.0 or abs(reuse + recycle + disposal - 1.0) > 1e-9:
            status = "validation_failed"
            notes.append(f"C1-C4 {mat}: reuse+recycle+disposal must equal 1."); continue

        # C2 transport of the remaining mass (route/segment-style single leg).
        dist = float(row.get("c2_distance_km", 0.0) or 0.0)
        if dist > 0.0:
            if str(row.get("c2_source", "")).strip():
                c2_legs.append({"material": mat, "mass_kg": mass, "distance_km": dist,
                                "mode": str(row.get("c2_mode", "truck")).strip().lower() or "truck",
                                "scope": "wtw", "mass_source": remaining_masses[mat].source,
                                "distance_source": str(row.get("c2_source")).strip()})
            else:
                status = "incomplete_sources"; notes.append(f"C1-C4 {mat}: C2 distance without source.")

        route_codes = _A5_WASTE_ROUTE.get(mat, {})
        reuse_f = recycle_f = disposal_f = None
        row_bad = False
        if reuse > 0.0:
            ov, doc = _a5_treatment_override(mat, "reuse", {mat: row})
            if doc:
                reuse_f = ov
            else:
                status = "incomplete_sources"; row_bad = True
                notes.append(f"C1-C4 {mat}: reuse processing EF (even 0) needs a documented source.")
        if recycle > 0.0:
            ov, doc = _a5_treatment_override(mat, "recycle", {mat: row})
            if doc:
                recycle_f = ov
            elif route_codes.get("recycle"):
                recycle_f = WASTE_EF[route_codes["recycle"]]
            else:
                status = "incomplete_sources"; row_bad = True
                notes.append(f"C1-C4 {mat}: no verified recycle factor (no fallback).")
        if disposal > 0.0:
            ov, doc = _a5_treatment_override(mat, "landfill", {mat: row})
            if doc:
                disposal_f = ov
            elif route_codes.get("landfill"):
                disposal_f = WASTE_EF[route_codes["landfill"]]
            else:
                status = "incomplete_sources"; row_bad = True
                notes.append(f"C1-C4 {mat}: no verified disposal factor (no fallback).")

        # An incomplete treatment row is EXCLUDED (not passed to the core, which would raise).
        if row_bad:
            recovered.pop(mat, None)
            continue

        treatment_rows.append({
            "material": mat, "mass_kg": mass, "mass_source": remaining_masses[mat].source,
            "reuse_share": reuse, "recycle_share": recycle, "disposal_share": disposal,
            "share_source": share_src, "reuse_factor": reuse_f, "recycle_factor": recycle_f,
            "disposal_factor": disposal_f})
        recovered[mat] = mass * (reuse + recycle)

    # Independent C1/C2/C3/C4 statuses. C1 (fuel/elec) and C2 (transport) that are zero
    # must be DECLARED (documented_zero / N-A), not silently zero.
    decls = params.get("c1c4_submodule_declarations") or {}
    def _sub_status(entered, decl_key):
        if entered:
            return "connected"
        d = _valid_module_declaration(decls.get(decl_key))
        return d or "unconnected"
    c1_entered = (c1_diesel is not None) or (c1_elec is not None)
    c2_entered = bool(c2_legs)
    c3_entered = any(float(t.get("reuse_share", 0)) + float(t.get("recycle_share", 0)) > 0
                     for t in treatment_rows)
    c4_entered = any(float(t.get("disposal_share", 0)) > 0 for t in treatment_rows)
    # C3/C4 shares always carry a source (share_source enforced above), so a 0 reuse/
    # recycle or 0 disposal is a documented zero, not a silent one.
    sub_status = {
        "C1": _sub_status(c1_entered, "C1"),
        "C2": _sub_status(c2_entered, "C2"),
        "C3": "connected" if c3_entered else "documented_zero",
        "C4": "connected" if c4_entered else "documented_zero",
    }
    # C3/C4 are inherent to the treatment rows; C1/C2 must be connected or declared.
    if status == "connected":
        if sub_status["C1"] == "unconnected" or sub_status["C2"] == "unconnected":
            status = "incomplete_sources"
            notes.append("C1 or C2 is zero without a documented_zero / N-A declaration.")
    c_inputs = dict(
        c1_diesel_litres=c1_diesel, c1_diesel_scope="wtw", c1_electricity_kwh=c1_elec,
        c1_grid=grid_eol if c1_elec is not None else None,
        c2_transport_legs=c2_legs, treatment_rows=treatment_rows)
    return c_inputs, status, " ".join(notes), recovered, sub_status


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
    material_overrides = build_material_factor_overrides(params)
    # A1-A3 with per-material EPD overrides (EPD wins over the ICE proxy). FRP with a
    # non-zero mass and NO override raises inside calculate_a1_a3 (factor value is None).
    a1_a3 = calculate_a1_a3(masses, factor_overrides=material_overrides or None)

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
    start_year = int(params.get("analysis_start_year", 1))
    # Grid mode: an ANNUAL official series (a real per-calendar-year table) is project-
    # specific; a CONSTANT value repeated across years is only a documented scenario and
    # must never be described as an annual measured series.
    grid_mode = str(params.get("grid_mode", "constant_documented_scenario")).lower()
    grid_annual_series = params.get("grid_annual_series") or {}  # {calendar_year: {gen,td,up}}
    # The GLOBAL grid source is required only for the constant scenario; in annual mode
    # each row is its own source, so a global source is not demanded.
    if grid_mode != "annual_official_series" and (not grid_source or not grid_location):
        raise ScientificInputError(
            "Egypt/project grid CI is still OPEN. Supply the official source file and table/page."
        )
    if grid_mode == "annual_official_series":
        if params.get("grid_annual_duplicate_years"):
            raise ScientificInputError(
                f"Annual grid has duplicate calendar years: {params['grid_annual_duplicate_years']}.")
        if params.get("grid_annual_invalid_years"):
            raise ScientificInputError("Annual grid has a missing/invalid calendar year value.")
        if not grid_annual_series:
            raise ScientificInputError("annual_official_series selected but no grid rows were provided.")

    def _grid_for_calendar_year(cal_year, operating_year):
        if grid_mode == "annual_official_series":
            row = grid_annual_series.get(cal_year) or grid_annual_series.get(str(cal_year))
            if row is None:
                raise ScientificInputError(
                    f"grid_mode=annual_official_series but no grid row for calendar year {cal_year}.")
            gen = float(row.get("generation", 0.0))
            td = float(row.get("td", 0.0))
            up = float(row.get("upstream", 0.0))
            # Each annual row must carry its OWN source (file + location) — a single global
            # source cannot attest a per-year table it does not actually contain.
            row_src = str(row.get("source_file", "")).strip()
            row_loc = str(row.get("source_location", "")).strip()
            if not row_src or not row_loc:
                raise ScientificInputError(
                    f"Annual grid row for calendar year {cal_year} needs its own source_file "
                    "and source_location.")
            if not all(math.isfinite(x) and x >= 0.0 for x in (gen, td, up)):
                raise ScientificInputError(
                    f"Annual grid row {cal_year} has a non-finite or negative CI component.")
            if (gen + td + up) <= 0.0:
                raise ScientificInputError(
                    f"Annual grid row {cal_year} total CI must be > 0 (a zero grid needs explicit "
                    "official evidence, not a blank row).")
            return GridCarbonYear(
                year=operating_year, generation_kgco2e_per_kwh=gen, td_kgco2e_per_kwh=td,
                upstream_kgco2e_per_kwh=up, source_file=row_src,
                location=f"{row_loc}; calendar year {cal_year}",
                geographic_scope=str(row.get("geography", "Egypt/project electricity supply")),
                note="Annual official grid series (project-specific).")
        gen = float(params.get("grid_generation", 0.0))
        td = float(params.get("grid_td", 0.0))
        up = float(params.get("grid_upstream", 0.0))
        return GridCarbonYear(
            year=operating_year, generation_kgco2e_per_kwh=gen, td_kgco2e_per_kwh=td,
            upstream_kgco2e_per_kwh=up, source_file=grid_source,
            location=f"{grid_location}; calendar year {cal_year}",
            geographic_scope="Egypt/project electricity supply",
            note="Constant-grid documented scenario (single factor repeated; NOT an annual series).")

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

    # B2-B5: prebuilt events win (dev/test); otherwise build from the flat event editor rows.
    _DONE_MOD = {"connected", "documented_zero", "not_applicable_with_justification"}
    b2b5_module_status = {m: "unconnected" for m in _B2B5_MODULES}
    b2b5_note = ""
    b_prebuilt = params.get("b2_b5_scientific_events")
    if b_prebuilt is not None:
        b_events = b_prebuilt
        _bad_year = [int(e.get("year", 0)) for e in b_events
                     if not (1 <= int(e.get("year", 0)) <= rsp)]
        if _bad_year:
            b2b5_status = "validation_failed"
            b2b5_note = f"B2-B5 event year(s) outside 1..{rsp}: {_bad_year}."
            b2_b5 = {"stage": "B2-B5", "total_tco2e": 0.0, "source_audit": [],
                     "material_added_kg": {}, "material_removed_kg": {}}
            b_events = []
        else:
            b2_b5 = calculate_b2_b5(b_events, grid_by_year, material_overrides or None) if b_events else {
                "stage": "B2-B5", "total_tco2e": 0.0, "source_audit": [],
                "material_added_kg": {}, "material_removed_kg": {}}
            b2b5_status = "connected" if b_events else "unconnected"
    else:
        _rows = params.get("b2b5_event_rows") or []
        _decls = params.get("b2b5_module_declarations")
        # Always evaluate declarations, even with NO event rows, so a fully-declared
        # (documented_zero / N-A) B2-B5 closes at a documented zero.
        b_events, b2b5_module_status, b2b5_note = build_b2b5_events_from_rows(_rows, rsp, _decls)
        b2_b5 = calculate_b2_b5(b_events, grid_by_year, material_overrides or None) if b_events else {
            "stage": "B2-B5", "total_tco2e": 0.0, "source_audit": [],
            "material_added_kg": {}, "material_removed_kg": {}}
        # The STAGE closes only when ALL FOUR modules are done (connected / documented_zero
        # / N-A). A single B4 event no longer makes the whole stage 'connected'; and an
        # all-declared-zero stage closes even with no events.
        if any(b2b5_module_status[m] == "incomplete_sources" for m in _B2B5_MODULES):
            b2b5_status = "incomplete_sources"
        elif all(b2b5_module_status[m] in _DONE_MOD for m in _B2B5_MODULES):
            b2b5_status = "connected"
        elif any(b2b5_module_status[m] != "unconnected" for m in _B2B5_MODULES):
            b2b5_status = "incomplete_sources"  # some module still unconnected/undeclared
        else:
            b2b5_status = "unconnected"  # nothing entered or declared at all
    # Chronological mass balance: mass must stay ≥ 0 after EACH event, not only at the end.
    _remaining, _chrono_rows, _chrono_ok, _chrono_err = chronological_mass_balance(masses, b_events)
    if not _chrono_ok:
        b2b5_status = "validation_failed"
        b2b5_note = (b2b5_note + " " + _chrono_err).strip()
    b2b5_connected = (b2b5_status == "connected")
    b2_b5["status"] = b2b5_status
    b2_b5["note"] = b2b5_note
    b2_b5["module_status"] = b2b5_module_status
    b2_b5["chronological_rows"] = _chrono_rows
    # Keep the aggregate view too (for display), but C-stage uses the chronological remaining.
    mass_balance = update_mass_balance(
        masses,
        b2_b5.get("material_added_kg", {}),
        b2_b5.get("material_removed_kg", {}),
    )
    # Remaining masses after chronological B4/B5 events — the ONLY mass C1-C4 may use.
    remaining_masses = _remaining if _chrono_ok else mass_balance.get("remaining_masses_kg", masses)

    c1c4_note = ""
    c_prebuilt = params.get("c1_c4_scientific_inputs")
    # EOL-year grid (C1 electricity uses the grid CI at end of life, not year 1). Built
    # only when C1-C4 is active so an annual series need only cover the years it actually uses.
    grid_eol = None
    c1c4_sub_status = {"C1": "unconnected", "C2": "unconnected", "C3": "unconnected", "C4": "unconnected"}
    _c3_recovered = {}
    if bool(params.get("include_c1c4", False)) or c_prebuilt:
        grid_eol = _grid_for_calendar_year(start_year + rsp, rsp)
    if c_prebuilt:
        c1_c4 = calculate_c1_c4(**c_prebuilt)
        c1c4_status = "connected"
    else:
        c_inputs, c1c4_status, c1c4_note, _c3_recovered, c1c4_sub_status = build_c1c4_scientific_inputs(
            params, remaining_masses, grid_eol)
        if c_inputs is None:
            c1_c4 = {"stage": "C1-C4", "total_tco2e": 0.0, "source_audit": []}
        else:
            try:
                c1_c4 = calculate_c1_c4(**c_inputs)
            except ScientificInputError as _ce:
                c1_c4 = {"stage": "C1-C4", "total_tco2e": 0.0, "source_audit": []}
                c1c4_status = "validation_failed"
                c1c4_note = (c1c4_note + " " + str(_ce)).strip()
    c1c4_connected = (c1c4_status == "connected")
    c1_c4["status"] = c1c4_status
    c1_c4["note"] = c1c4_note
    c1_c4["submodule_status"] = c1c4_sub_status

    # Module D: derive from C3 recovered flows only (RecoveredOutput_D ≤ C3 recovered mass);
    # never from independent free rows in publication. Built from the Module-D editor rows.
    module_d_cfg = params.get("module_d_from_c3")
    if module_d_cfg is None and params.get("module_d_rows"):
        module_d_cfg = build_module_d_cfg_from_rows(params.get("module_d_rows"))
    d_rows = []
    module_d_note = ""
    if module_d_cfg and c1c4_connected:
        try:
            d_rows = build_module_d_rows_from_c3(c1_c4, module_d_cfg)
        except ScientificInputError as _de:
            d_rows = []; module_d_note = str(_de)
    elif module_d_cfg and not c1c4_connected:
        module_d_note = "Module D needs a connected C1-C4 (C3 recovered flows) to derive from."
    module_d1 = calculate_module_d1(d_rows) if d_rows else {
        "stage": "D1", "signed_tco2e": 0.0, "source_audit": [],
        "reporting_note": module_d_note or "Module D not calculated."
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
        "B2-B5": b2b5_status,
        "B6": "connected",      # reached here only if grid + ridership + RSP sourced
        "C1-C4": c1c4_status,
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
    # Any user-supplied (unverified) factor was used → not standards-reporting-complete.
    _aud = final_lca.get("source_audit")
    proxy_used = False
    user_supplied_used = False
    try:
        if hasattr(_aud, "empty") and not _aud.empty and "status" in _aud.columns:
            _stat = _aud["status"].astype(str)
            proxy_used = _stat.str.contains("proxy", case=False, na=False).any()
            user_supplied_used = _stat.str.contains("user_supplied", case=False, na=False).any()
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
        "user_supplied_evidence_used": bool(user_supplied_used),
        "uncertainty_complete": False,  # Phase-4 MC wiring for the scientific engine is pending
    }

    # ── Three-level closure gate (replaces the single misleading boolean) ────────
    # 1) full_wlca_calculation_complete: every applicable A1-C4 stage connected or
    #    justified N/A, mass balance valid, no validation failures.
    full_wlca_calculation_complete = bool(
        publication_grade_partial_scope and _all_stages_done
        and _no_validation_failed and mass_balance_valid)
    # 2) standards_reporting_complete: also all factor/activity sources documented
    #    (no OPEN factor / no open issues) AND no unverified user-supplied factor,
    #    Module D kept separate.
    standards_reporting_complete = bool(
        full_wlca_calculation_complete and not checks.get("issues")
        and not user_supplied_used)
    # 3) q1_evidence_ready: also project-specific (annual grid, no undisclosed proxy)
    #    and uncertainty complete.
    q1_evidence_ready = bool(
        standards_reporting_complete
        and publication_readiness["project_specific_data_complete"]
        and publication_readiness["uncertainty_complete"])
    # 2b) lca_application_end_to_end_complete: the scientific engine governs the reported
    #     outputs and the exports are parity-checked. This is set by the caller/exporter
    #     when it confirms cards == CSV == Excel from the scientific core; default False.
    lca_application_end_to_end_complete = bool(
        full_wlca_calculation_complete and params.get("_export_parity_ok", False))
    closure_gate = {
        "full_wlca_calculation_complete": full_wlca_calculation_complete,
        "standards_reporting_complete": standards_reporting_complete,
        "lca_application_end_to_end_complete": lca_application_end_to_end_complete,
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
    # drift from what was actually summed. Once every stage is done it is a FULL WLCA.
    _all_done = all(stage_status[s] in _DONE for s in stage_status)
    final_lca["scope_label"] = (
        "Scientific FULL cradle-to-grave LCA (A1-C4): " if _all_done
        else "Scientific partial LCA: ") + " + ".join(scope_included)
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
