"""Acceptance tests for the referenced scientific LCA core + app integration.

Verifies the invariants the Q1 review required of the new core:
  - strict sourcing (blocks unsourced inputs instead of fabricating numbers);
  - per-tonne waste factor unit (the ×1000 fix);
  - WTW = direct + WTT for transport and diesel;
  - Module D is separate from gross A-C;
  - FRP mass>0 without an EPD is NOT publication-grade;
  - effective-EF rejects market-average factors (no recycled-content double count);
  - Gross A-C = Σ stages and GWP = gross·1000 / lifetime PKM;
  - the app integration blocks unsourced params and computes fully-sourced params.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lca_scientific_core import (
    ProjectQuantity, GridCarbonYear, Evidence, ScientificInputError,
    TRANSPORT_EF, DIESEL_EF, WASTE_EF, MATERIAL_EF, B6_ENERGY_INTENSITY,
    calculate_a1_a3, calculate_transport_legs, calculate_waste_treatment,
    calculate_b6, calculate_module_d1, calculate_effective_ef,
    combine_lca_modules, publication_checks, make_project_evidence,
)
from lca_scientific_integration import run_scientific_lca_from_app_params

ok = True
def check(name, cond):
    global ok
    print(("PASS" if cond else "FAIL"), name); ok = ok and cond

# ── 1. Strict sourcing: unsourced mass/leg must raise ──────────────────────────
try:
    calculate_a1_a3({"steel": ProjectQuantity(1000.0, "kg", "")})  # empty source
    check("A1-A3 blocks unsourced mass", False)
except ScientificInputError:
    check("A1-A3 blocks unsourced mass", True)

try:
    calculate_transport_legs([{"mass_kg": 1000.0, "distance_km": 10.0,
                               "mass_source": "", "distance_source": "x"}], "A4")
    check("A4 blocks unsourced leg", False)
except ScientificInputError:
    check("A4 blocks unsourced leg", True)

# ── 2. WTW = direct + WTT (transport + diesel) ─────────────────────────────────
for mode in ("truck", "rail", "ship"):
    d = TRANSPORT_EF[mode]["direct"].value
    w = TRANSPORT_EF[mode]["wtt"].value
    wtw = TRANSPORT_EF[mode]["wtw"].value
    check(f"{mode} WTW == direct+WTT", abs(wtw - (d + w)) < 1e-9)
check("diesel WTW == direct+WTT",
      abs(DIESEL_EF["wtw"].value - (DIESEL_EF["direct"].value + DIESEL_EF["wtt"].value)) < 1e-9)

# ── 3. Waste factor is per-tonne (the ×1000 fix) ───────────────────────────────
# 1000 kg waste at 1.26338 kgCO2e/tonne = 1.26338 kgCO2e = 0.00126338 tCO2e.
w = calculate_waste_treatment(
    [{"waste_kg": 1000.0, "waste_source": "site log", "factor_code": "mineral_landfill"}], "A5.3")
check("waste per-tonne unit (1 t → 1.26338 kg → 0.00126338 t)",
      abs(w["total_tco2e"] - (1.26338 / 1000.0)) < 1e-12)

# ── 4. Transport identity: I = (M/1000)*D*EF/1000 ──────────────────────────────
leg = calculate_transport_legs(
    [{"mass_kg": 1_000_000.0, "distance_km": 100.0, "mode": "truck", "scope": "wtw",
      "mass_source": "BOQ", "distance_source": "route"}], "A4")
expected = (1_000_000.0 / 1000.0) * 100.0 * TRANSPORT_EF["truck"]["wtw"].value / 1000.0
check("A4 transport identity", abs(leg["total_tco2e"] - expected) < 1e-9)

# ── 5. Module D is separate from gross ─────────────────────────────────────────
masses = {
    "concrete": ProjectQuantity(700_000 * 2400.0, "kg", "BOQ", "vol*density"),
    "steel": ProjectQuantity(100_000 * 1000.0, "kg", "BOQ", "kt->kg"),
    "frp": ProjectQuantity(0.0, "kg", "BOQ", "excluded"),
}
a1 = calculate_a1_a3(masses)
grid = {y: GridCarbonYear(y, 0.40, 0.03, 0.05, "Egypt table", f"p5 y{y}", "Egypt") for y in range(1, 51)}
pkm = {y: ProjectQuantity(500 * 1000 * 365.0, "passenger-km/year", "ridership", "d*1000*365") for y in range(1, 51)}
b6 = calculate_b6(pkm, grid, B6_ENERGY_INTENSITY["uk_light_rail_weighted_proxy"])
zero = lambda s: {"stage": s, "total_tco2e": 0.0, "source_audit": []}
prim = make_project_evidence("PRIM", 1.61, "kgCO2e/kg", "D1", "ICE", "row", "A1-A3")
rec = make_project_evidence("REC", 0.40, "kgCO2e/kg", "D1", "ICE", "row", "recovery")
d1 = calculate_module_d1([{"material": "steel", "recovered_output_kg": 1e6, "secondary_input_kg": 0.0,
                           "substitution_ratio": 0.9, "flow_source": "eol plan",
                           "substitution_source": "assumption", "primary_factor": prim,
                           "recovery_to_substitution_factor": rec}])
final = combine_lca_modules(a1, zero("A4"), zero("A5"), zero("B2-B5"), b6, zero("C1-C4"), d1)
gross_sum = (a1["total_tco2e"] + b6["total_tco2e"])
check("gross A-C == Σ stages", abs(final["gross_A_C_tCO2e"] - gross_sum) < 1e-6)
check("Module D reported separately (not in gross)",
      final["module_D1_signed_tCO2e_separate"] != 0.0 and
      abs(final["gross_A_C_tCO2e"] - gross_sum) < 1e-6)
check("GWP == gross*1000/lifetime_pkm",
      abs(final["GWP_kgCO2e_per_pkm"] - final["gross_A_C_tCO2e"] * 1000.0 / final["lifetime_pkm"]) < 1e-9)

# ── 6. FRP mass>0 without EPD → not publication-grade ──────────────────────────
frp_masses = dict(masses)
frp_masses["frp"] = ProjectQuantity(1000.0, "kg", "BOQ", "included")
chk = publication_checks(frp_masses, grid, final["source_audit"], 50)
check("FRP>0 without EPD → not publication-grade", chk["publication_grade"] is False)

# ── 7. Effective EF rejects market-average base factor ─────────────────────────
try:
    calculate_effective_ef(MATERIAL_EF["aluminum"], 0.3, MATERIAL_EF["aluminum"])
    check("effective-EF rejects market-average base", False)
except ScientificInputError:
    check("effective-EF rejects market-average base", True)

# ── 8. App integration: blocks unsourced, computes fully-sourced ───────────────
base = dict(concrete=700.0, steel=100.0, aluminum=5.0, wood=2.0, frp=0.0, glass=0.5,
            glass_thickness_mm=12.0, daily_pax_km=500.0, analysis_start_year=2026)
try:
    run_scientific_lca_from_app_params(base)
    check("integration blocks unsourced params", False)
except ScientificInputError:
    check("integration blocks unsourced params", True)

full = dict(base)
full.update({
    "assessment_lifetime": 50, "assessment_lifetime_source": "design-life clause 3.2",
    "concrete_density_kg_m3": 2400.0, "concrete_density_source": "EN 206 mix",
    "wood_density_kg_m3": 600.0, "wood_density_source": "timber datasheet",
    "glass_density_kg_m3": 2500.0, "glass_density_source": "glass datasheet",
    "boq_source": "BOQ rev A 2026-01", "ridership_source": "forecast 2026 v1",
    "grid_generation": 0.40, "grid_td": 0.03, "grid_upstream": 0.05,
    "grid_source": "Egypt grid table 2025", "grid_location": "table 4 p5",
    "energy_intensity_choice": "uk_light_rail_weighted_proxy",
    "project_ei": 0.0, "project_ei_source": "",
})
res = run_scientific_lca_from_app_params(full)
check("integration computes sourced gross > 0", res["gross_A_C_tCO2e"] > 0.0)
check("integration GWP > 0", res["GWP_kgCO2e_per_pkm"] > 0.0)
check("integration partial-scope grade True when A1-A3+B6 sourced",
      res["publication_grade_partial_scope"] is True)

# ── 9. Two-level publication grade + A4 wiring ─────────────────────────────────
# A4 has no route source in `full` → A4 UNCONNECTED, partial True, full_wlca False.
check("A4 unconnected without a route source", res["scope_connected"]["A4"] is False)
check("A4 tCO2e == 0 while unconnected", abs(res["modules"]["A4"]["total_tco2e"]) < 1e-12)
check("full_wlca False while A4/A5/B2-B5/C1-C4 unconnected",
      res["publication_grade_full_wlca"] is False)
check("unconnected stages reported (not silently negligible)",
      set(res["unconnected_stages"]) == {"A4", "A5", "B2-B5", "C1-C4"})

a4full = dict(full)
a4full.update({"a4_mode": "simple", "transport_distance_km": 50.0,
               "transport_mode": "truck", "a4_route_source": "route survey rev1", "a4_scope": "wtw"})
res_a4 = run_scientific_lca_from_app_params(a4full)
check("A4 connects with a route source", res_a4["scope_connected"]["A4"] is True)
check("A4 contributes > 0 once connected", res_a4["modules"]["A4"]["total_tco2e"] > 0.0)
check("scope label names connected stages A1-A3 + A4 + B6",
      res_a4["scope_label"] == "Scientific partial LCA: A1-A3 + A4 + B6")
check("full_wlca STILL False (A5/B2-B5/C1-C4 not wired)",
      res_a4["publication_grade_full_wlca"] is False)

# A4 leg identities: zero distance → 0, zero mass → 0.
from lca_scientific_core import calculate_transport_legs as _ctl
z_dist = _ctl([{"material": "steel", "mass_kg": 1e6, "distance_km": 0.0, "mode": "truck",
                "scope": "wtw", "mass_source": "BOQ", "distance_source": "route"}], "A4")
check("A4 zero distance → zero carbon", abs(z_dist["total_tco2e"]) < 1e-12)
z_mass = _ctl([{"material": "steel", "mass_kg": 0.0, "distance_km": 100.0, "mode": "truck",
                "scope": "wtw", "mass_source": "BOQ", "distance_source": "route"}], "A4")
check("A4 zero mass → zero carbon", abs(z_mass["total_tco2e"]) < 1e-12)

# A4 entered but no route source → incomplete_sources (NOT a silent measured zero).
a4_nosrc = dict(full)
a4_nosrc.update({"a4_mode": "simple", "transport_distance_km": 50.0, "transport_mode": "truck"})
r_ns = run_scientific_lca_from_app_params(a4_nosrc)
check("A4 entered w/o source → incomplete_sources",
      r_ns["stage_status"]["A4"] == "incomplete_sources")
check("A4 incomplete listed (not counted as measured zero)",
      "A4" in r_ns["incomplete_source_stages"])

# Advanced rows do not double-count the simple route.
from lca_scientific_integration import build_a4_scientific_legs as _b4a
_masses_stub = {"steel": ProjectQuantity(1e6, "kg", "BOQ", "x")}
adv_params = {"a4_route_source": "route", "a4_scope": "wtw", "boq_source": "BOQ",
              "transport_distance_km": 50.0, "transport_mode": "truck", "a4_mode": "advanced",
              "a4_advanced_legs": [{"material": "steel", "mass_kg": 5e5, "distance_km": 20.0, "mode": "rail"}]}
_legs, _st, _ = _b4a(adv_params, _masses_stub)
check("advanced A4 rows used, simple route NOT added (no double count)",
      len(_legs) == 1 and _legs[0]["mode"] == "rail" and abs(_legs[0]["distance_km"] - 20.0) < 1e-9)

# ── 10. A5 five-component wiring ───────────────────────────────────────────────
from lca_scientific_core import calculate_a5 as _ca5, calculate_fuel as _cf

# diesel direct vs wtw
_dl = ProjectQuantity(100000.0, "L", "site fuel log", "diesel")
_fd = _cf(_dl, "A5", "direct")["tco2e"]
_fw = _cf(_dl, "A5", "wtw")["tco2e"]
check("A5 diesel direct = L*2.57082/1000", abs(_fd - 100000.0 * 2.57082 / 1000.0) < 1e-6)
check("A5 diesel wtw = L*3.18183/1000", abs(_fw - 100000.0 * 3.18183 / 1000.0) < 1e-6)

# tonne-based treatment + transport conversion via calculate_a5
grid1 = GridCarbonYear(1, 0.40, 0.03, 0.05, "Egypt table", "y1", "Egypt")
a5r = _ca5(
    diesel_litres=_dl, diesel_scope="wtw",
    electricity_kwh=ProjectQuantity(2_000_000.0, "kWh", "site meter", "elec"), grid=grid1,
    extra_waste_materials_kg={"concrete": ProjectQuantity(1_000_000.0, "kg", "waste plan", "W")},
    waste_factor_overrides=None,
    waste_delivery_legs=[{"material": "concrete", "mass_kg": 1_000_000.0, "distance_km": 30.0,
                          "mode": "truck", "scope": "wtw", "mass_source": "wp", "distance_source": "haul"}],
    waste_treatment_items=[{"material": "concrete", "waste_kg": 1_000_000.0, "waste_source": "wp",
                            "factor_code": "mineral_landfill"}])
check("A5 electricity uses supplied grid CI (0.48)",
      abs(a5r["electricity_tco2e"] - 2_000_000.0 * 0.48 / 1000.0) < 1e-6)
# treatment: 1e6 kg = 1000 t * 1.26338 kgCO2e/t = 1263.38 kg = 1.26338 t
check("A5 treatment per-tonne (1000 t * 1.26338 → 1.26338 t)",
      abs(a5r["waste_treatment_tco2e"] - (1_000_000.0 / 1000.0) * 1.26338 / 1000.0) < 1e-9)
# transport: (1e6/1000) t * 30 km * 0.12522 / 1000
check("A5 waste transport conversion",
      abs(a5r["waste_transport_tco2e"] - (1_000_000.0 / 1000.0) * 30.0 * 0.12522 / 1000.0) < 1e-9)
_sum5 = (a5r["fuel_tco2e"] + a5r["electricity_tco2e"] + a5r["extra_waste_product_tco2e"]
         + a5r["waste_transport_tco2e"] + a5r["waste_treatment_tco2e"])
check("A5 total == sum of five components", abs(_sum5 - a5r["total_tco2e"]) < 1e-9)

# installed vs purchased waste formula + no double counting
from lca_scientific_integration import _a5_waste_mass_kg as _wm
check("A5 installed waste W = M*WR/(1-WR)",
      abs(_wm(1_000_000.0, 0.05, "installed") - 1_000_000.0 * 0.05 / 0.95) < 1e-6)
check("A5 purchased waste W = M*WR",
      abs(_wm(1_000_000.0, 0.05, "purchased") - 1_000_000.0 * 0.05) < 1e-6)

# integration-level A5: on/off, missing source, purchased no-production, unsupported route
_a5base = dict(full)
_a5base.update({"a4_route_source": "route survey"})  # A4 connected too
_a5on = dict(_a5base)
_a5on.update(include_a5=True, a5_boq_mode="installed",
             a5_diesel_l=100000.0, a5_diesel_mode="simple", a5_diesel_scope="wtw",
             a5_diesel_source="fuel log", a5_elec_kwh=2_000_000.0, a5_electricity_source="meter",
             a5_waste_rates={"concrete": 0.05}, a5_waste_routes={"concrete": {"transport_km": 30.0}},
             a5_treatment_shares={"concrete": {"reuse": 0.0, "recycle": 0.0, "landfill": 1.0}},
             a5_waste_transport_km=30.0, a5_waste_source="waste plan", a5_waste_route_source="haul")
_r_on = run_scientific_lca_from_app_params(_a5on)
check("A5 connects when fully sourced", _r_on["stage_status"]["A5"] == "connected")
check("A5 in connected scope label", "A5" in _r_on["connected_stages"])

_r_off = run_scientific_lca_from_app_params(dict(_a5base))
check("A5 off → unconnected", _r_off["stage_status"]["A5"] == "unconnected")

_a5_missrc = dict(_a5on); _a5_missrc["a5_diesel_source"] = ""
_r_ms = run_scientific_lca_from_app_params(_a5_missrc)
check("A5 missing diesel source → incomplete_sources",
      _r_ms["stage_status"]["A5"] == "incomplete_sources")

_a5_pur = dict(_a5on); _a5_pur["a5_boq_mode"] = "purchased"
_r_pur = run_scientific_lca_from_app_params(_a5_pur)
check("A5 purchased basis → no waste-production double count",
      abs(_r_pur["modules"]["A5"]["extra_waste_product_tco2e"]) < 1e-9)

_a5_glass = dict(_a5on)
_a5_glass["a5_waste_rates"] = {"glass": 0.05}  # glass has NO verified waste factor
_r_gl = run_scientific_lca_from_app_params(_a5_glass)
check("A5 unsupported treatment route (glass) → incomplete_sources",
      _r_gl["stage_status"]["A5"] == "incomplete_sources")

check("full_wlca STILL False after A4+A5 (B2-B5/C1-C4 unwired)",
      _r_on["publication_grade_full_wlca"] is False)

print("\nALL SCIENTIFIC CORE TESTS PASSED" if ok else "\nSOME TESTS FAILED")
sys.exit(0 if ok else 1)
