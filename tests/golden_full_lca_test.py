"""Golden full cradle-to-grave fixture + export parity.

Builds ONE fully-sourced A1-C4 scenario, runs the scientific engine, and asserts:
  * every stage A1-A3 / A4 / A5 / B2-B5 / B6 / C1-C4 is connected (or declared done);
  * full_wlca_calculation_complete is True and the scope label reads FULL cradle-to-grave;
  * Module D is reported SEPARATELY (never inside gross);
  * the headline cards == CSV == Excel Summary (export parity);
  * lca_application_end_to_end_complete flips True once parity is confirmed.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lca_scientific_core import make_project_evidence
from lca_scientific_integration import run_scientific_lca_from_app_params
from lca_scientific_reporting import (scientific_headline, scientific_csv, scientific_report_text,
                                      scientific_excel_sheets, export_parity_ok, S1_SHEETS)

ok = True
def check(name, cond):
    global ok
    print(("PASS" if cond else "FAIL"), name); ok = ok and cond

_DECL = {"status": "documented_zero", "justification": "not used in this project", "source": "project brief"}
_A5_DECL = {c: "documented_zero" for c in (
    "A5.2_site_fuel", "A5.2_site_electricity", "A5.2_temporary_works",
    "A5.3_waste_generation", "A5.3_waste_transport", "A5.3_waste_treatment")}

# Fully-sourced A1-A3 + A4 + A5 + B6 + B2-B5 + C1-C4.
G = dict(
    concrete=700.0, steel=100.0, aluminum=5.0, wood=2.0, frp=0.0, glass=0.5,
    glass_thickness_mm=12.0, daily_pax_km=500.0, analysis_start_year=2026,
    # B6 denominator: an explicit sourced annual service table (never a hard-coded 365).
    # 182,500,000 pkm/yr is a deterministic TEST-FIXTURE value, labelled as such.
    b6_service_mode="annual_service_table",
    b6_annual_service_rows=[
        {
            "operating_year": y,
            "calendar_year": 2025 + y,
            "service_input_mode": "direct_annual_pkm",
            "direct_annual_pkm": 182_500_000.0,
            "demand_passengers_per_day": 0.0,
            "capacity_passengers_per_day": 0.0,
            "trip_length_km": 0.0,
            "availability_fraction": 1.0,
            "operating_days": 0.0,
            "source_file": "ridership forecast 2026 v1",
            "source_location": f"annual service table year {y}",
            "note": "golden deterministic fixture",
        }
        for y in range(1, 51)
    ],
    a4_mode="simple", transport_distance_km=50.0, transport_mode="truck",
    a4_route_source="route survey rev1", a4_scope="wtw",
    # RICS A4 route closure: the road return/empty-running journey is addressed with an
    # explicit sourced tonne-km empty-return assumption. Deterministic TEST-FIXTURE
    # values — no UK 43% default is inherited.
    a4_return_factor_unit="tonne_km", a4_return_fraction=0.40,
    a4_empty_return_factor=0.08,
    a4_return_source_file="haulier empty-running study 2026",
    a4_return_source_location="table 2, page 6 (test fixture)",
    a4_return_justification="Backhaul survey: 40% of outward road tonne-km run empty.",
    assessment_lifetime=50, assessment_lifetime_source="design-life clause 3.2",
    concrete_density_kg_m3=2400.0, concrete_density_source="EN 206 mix",
    wood_density_kg_m3=600.0, wood_density_source="timber datasheet",
    glass_density_kg_m3=2500.0, glass_density_source="glass datasheet",
    boq_source="BOQ rev A 2026-01", ridership_source="ridership forecast 2026 v1",
    grid_generation=0.40, grid_td=0.03, grid_upstream=0.05,
    grid_source="Egypt grid factor table 2025", grid_location="table 4 p5",
    grid_mode="constant_documented_scenario",
    energy_intensity_choice="uk_light_rail_weighted_proxy", project_ei=0.0, project_ei_source="",
    # A5 connected (fuel + waste sourced, other components declared documented_zero).
    include_a5=True, a5_boq_mode="installed", a5_component_declarations=_A5_DECL,
    a5_predemolition_status="not_applicable",
    a5_predemolition_note="Greenfield; no existing asset demolition in the declared boundary",
    a5_diesel_l=100000.0, a5_diesel_mode="simple", a5_diesel_scope="wtw", a5_diesel_source="site fuel log",
    a5_waste_source="waste plan", a5_waste_route_source="haul route",
    a5_waste_rates={"concrete": 0.05}, a5_waste_transport_km=30.0,
    a5_treatment_shares={"concrete": {"reuse": 0.0, "recycle": 0.0, "landfill": 1.0}},
    a5_waste_routes={"concrete": {"transport_km": 30.0}},
    # B2-B5: one sourced B4 event + the other three modules declared.
    b2b5_event_rows=[{"event_id": "E1", "module": "B4", "year": 25, "event_source": "O&M plan p4",
                      "new_material": "steel", "new_material_kg": 5000.0, "material_source": "BOQ",
                      "mass_role": "retained_in_asset",
                      "removed_material": "steel", "removed_material_kg": 5000.0,
                      "removed_material_source": "O&M removal log",
                      "transport_km": 30.0, "transport_source": "route", "transport_mode": "truck"}],
    b2b5_module_declarations={m: dict(_DECL) for m in ("B2", "B3", "B5")},
    # C1-C4 from remaining mass; C1 sourced, C2 sourced route, disposal via registry.
    include_c1c4=True, c1_diesel_l=5000.0, c1_diesel_source="demolition fuel log",
    c1c4_rows=[
        {"material": "concrete", "reuse_share": 0.0, "recycle_share": 0.0, "disposal_share": 1.0,
         "share_source": "EOL plan", "c2_distance_km": 40.0, "c2_source": "haul", "c2_mode": "truck",
         "c2_return_factor_unit": "tonne_km", "c2_return_fraction": 0.40,
         "c2_empty_return_factor": 0.08,
         "c2_return_source_file": "EOL haulier empty-running study 2026",
         "c2_return_source_location": "table 3, page 4 (test fixture)",
         "c2_return_justification": "Backhaul survey: 40% of C2 road tonne-km run empty."},
        {"material": "steel", "reuse_share": 0.0, "recycle_share": 0.0, "disposal_share": 1.0,
         "share_source": "EOL plan", "c2_distance_km": 40.0, "c2_source": "haul", "c2_mode": "truck",
         "c2_return_factor_unit": "tonne_km", "c2_return_fraction": 0.40,
         "c2_empty_return_factor": 0.08,
         "c2_return_source_file": "EOL haulier empty-running study 2026",
         "c2_return_source_location": "table 3, page 4 (test fixture)",
         "c2_return_justification": "Backhaul survey: 40% of C2 road tonne-km run empty."},
        {"material": "aluminum", "reuse_share": 0.0, "recycle_share": 0.0, "disposal_share": 1.0,
         "share_source": "EOL plan", "c2_distance_km": 40.0, "c2_source": "haul", "c2_mode": "truck",
         "c2_return_factor_unit": "tonne_km", "c2_return_fraction": 0.40,
         "c2_empty_return_factor": 0.08,
         "c2_return_source_file": "EOL haulier empty-running study 2026",
         "c2_return_source_location": "table 3, page 4 (test fixture)",
         "c2_return_justification": "Backhaul survey: 40% of C2 road tonne-km run empty."},
    ],
)

r = run_scientific_lca_from_app_params(dict(G))

for stg in ("A1-A3", "A4", "A5", "B2-B5", "B6", "C1-C4"):
    check(f"golden: {stg} is connected", r["stage_status"][stg] == "connected")
check("golden: full_wlca_calculation_complete is True",
      r["closure_gate"]["full_wlca_calculation_complete"] is True)
check("golden: scope label reads FULL cradle-to-grave",
      r["scope_label"].startswith("Scientific FULL cradle-to-grave"))
check("golden: gross == sum of reported stages",
      abs(r["gross_A_C_tCO2e"] - sum(r["reported_stage_tco2e"].values())) < 1e-6)

# Module D separate — needs C3 recovered mass, so give concrete a recycle share here.
r_d = dict(G)
r_d["c1c4_rows"] = [
    {"material": "concrete", "reuse_share": 0.0, "recycle_share": 0.5, "disposal_share": 0.5,
     "share_source": "EOL plan", "c2_distance_km": 40.0, "c2_source": "haul", "c2_mode": "truck",
         "c2_return_factor_unit": "tonne_km", "c2_return_fraction": 0.40,
         "c2_empty_return_factor": 0.08,
         "c2_return_source_file": "EOL haulier empty-running study 2026",
         "c2_return_source_location": "table 3, page 4 (test fixture)",
         "c2_return_justification": "Backhaul survey: 40% of C2 road tonne-km run empty."},
    {"material": "steel", "reuse_share": 0.0, "recycle_share": 0.0, "disposal_share": 1.0,
     "share_source": "EOL plan", "c2_distance_km": 40.0, "c2_source": "haul", "c2_mode": "truck",
         "c2_return_factor_unit": "tonne_km", "c2_return_fraction": 0.40,
         "c2_empty_return_factor": 0.08,
         "c2_return_source_file": "EOL haulier empty-running study 2026",
         "c2_return_source_location": "table 3, page 4 (test fixture)",
         "c2_return_justification": "Backhaul survey: 40% of C2 road tonne-km run empty."},
    {"material": "aluminum", "reuse_share": 0.0, "recycle_share": 0.0, "disposal_share": 1.0,
     "share_source": "EOL plan", "c2_distance_km": 40.0, "c2_source": "haul", "c2_mode": "truck",
         "c2_return_factor_unit": "tonne_km", "c2_return_fraction": 0.40,
         "c2_empty_return_factor": 0.08,
         "c2_return_source_file": "EOL haulier empty-running study 2026",
         "c2_return_source_location": "table 3, page 4 (test fixture)",
         "c2_return_justification": "Backhaul survey: 40% of C2 road tonne-km run empty."}]
r_d["module_d_rows"] = [{"material": "concrete", "recovered_output_kg": 1_000_000.0,
                         "secondary_input_kg": 0.0, "substitution_ratio": 0.9,
                         "primary_ef": 0.1034, "primary_source": "ICE concrete",
                         "recovery_ef": 0.02, "recovery_source": "recycling route",
                         "flow_source": "EOL plan", "substitution_source": "assumption"}]
rd = run_scientific_lca_from_app_params(r_d)
check("golden: Module D via UI rows is non-zero and separate from gross",
      abs(rd["module_D1_signed_tCO2e_separate"]) > 0.0
      and abs(rd["gross_A_C_tCO2e"] - sum(rd["reported_stage_tco2e"].values())) < 1e-6)

# Export parity: cards == CSV == Excel Summary.
h = scientific_headline(r)
check("export parity (cards == CSV == Excel Summary)", export_parity_ok(r) is True)
check("scientific report shows Module D separately",
      "SEPARATELY" in scientific_report_text(r))
check("Supplementary S1 has all 15 sheets",
      list(scientific_excel_sheets(r).keys()) == S1_SHEETS)
check("scientific CSV headline matches the cards",
      f"Gross A-C (tCO2e),{h['Gross A-C (tCO2e)']}" in scientific_csv(r))

# CSV is a valid 2-column file even though a metric name contains a comma.
import io as _io
import pandas as _pd
_csv_df = _pd.read_csv(_io.StringIO(scientific_csv(r)))
check("scientific CSV re-parses to exactly two columns (comma-safe)",
      list(_csv_df.columns) == ["metric", "value"])

# End-to-end gate is computed INTERNALLY (parity verified from serialized files) and only
# in publication mode — it is NOT an injected parameter.
G2 = dict(G); G2["publication_mode"] = True
r2 = run_scientific_lca_from_app_params(G2)
check("lca_application_end_to_end_complete True (internally verified, publication mode)",
      r2["closure_gate"]["lca_application_end_to_end_complete"] is True)
G3 = dict(G); G3["publication_mode"] = False
check("end-to-end gate False outside publication mode",
      run_scientific_lca_from_app_params(G3)["closure_gate"]["lca_application_end_to_end_complete"] is False)
check("injecting _export_parity_ok does NOT flip the gate",
      run_scientific_lca_from_app_params(dict(G, _export_parity_ok=True))
      ["closure_gate"]["lca_application_end_to_end_complete"] is False)

print("\nGOLDEN FULL LCA TESTS PASSED" if ok else "\nGOLDEN TESTS FAILED")
sys.exit(0 if ok else 1)
