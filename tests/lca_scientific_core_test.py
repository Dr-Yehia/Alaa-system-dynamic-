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

# Advanced route/segment model; masses come from A1-A3 masses via route_share.
from lca_scientific_integration import build_a4_scientific_legs as _b4a
_masses_stub = {"steel": ProjectQuantity(1e6, "kg", "BOQ", "x")}
adv_params = {"a4_route_source": "route", "a4_scope": "wtw", "boq_source": "BOQ",
              "transport_distance_km": 50.0, "transport_mode": "truck", "a4_mode": "advanced",
              "a4_advanced_legs": [{"material": "steel", "route_id": "1", "route_share": 1.0,
                                    "segment_no": 1, "distance_km": 20.0, "mode": "rail",
                                    "distance_source": "rail sheet"}]}
_legs, _st, _note, _aud = _b4a(adv_params, _masses_stub)
check("advanced A4 route used, simple route NOT added (no double count)",
      len(_legs) == 1 and _legs[0]["mode"] == "rail" and abs(_legs[0]["distance_km"] - 20.0) < 1e-9)
check("advanced A4 leg mass = A1-A3 mass × route_share (NOT a free-typed mass)",
      abs(_legs[0]["mass_kg"] - 1e6 * 1.0) < 1e-6)

# ── A4 mass reconciliation (route_share) ──────────────────────────────────────
bad_recon = dict(adv_params)
bad_recon["a4_advanced_legs"] = [{"material": "steel", "route_id": "1", "route_share": 0.5,
                                  "segment_no": 1, "distance_km": 20.0, "mode": "rail",
                                  "distance_source": "s"}]
_bl, _bst, _bn, _ba = _b4a(bad_recon, _masses_stub)
check("A4 Σ route_share ≠ 1 → validation_failed", _bst == "validation_failed" and _bl == [])
# Two ROUTES (different route_id) split the mass; masses sum to the full A1-A3 mass.
split_recon = dict(adv_params)
split_recon["a4_advanced_legs"] = [
    {"material": "steel", "route_id": "1", "route_share": 0.6, "segment_no": 1,
     "distance_km": 20.0, "mode": "ship", "distance_source": "s1"},
    {"material": "steel", "route_id": "2", "route_share": 0.4, "segment_no": 1,
     "distance_km": 5.0, "mode": "truck", "distance_source": "s2"}]
_ol, _ost, _on, _oa = _b4a(split_recon, _masses_stub)
check("A4 two routes Σ share = 1 → connected, masses reconcile",
      _ost == "connected" and abs(sum(l["mass_kg"] for l in _ol) - 1e6) < 1e-6)
# SEQUENTIAL segments (same route_id) carry the SAME mass — not a split.
seq = dict(adv_params)
seq["a4_advanced_legs"] = [
    {"material": "steel", "route_id": "1", "route_share": 1.0, "segment_no": 1,
     "distance_km": 1000.0, "mode": "ship", "distance_source": "port"},
    {"material": "steel", "route_id": "1", "route_share": 1.0, "segment_no": 2,
     "distance_km": 50.0, "mode": "truck", "distance_source": "haul"}]
_sl, _sst, _sn, _sa = _b4a(seq, _masses_stub)
check("A4 sequential segments carry the SAME route mass (not split)",
      _sst == "connected" and len(_sl) == 2 and all(abs(l["mass_kg"] - 1e6) < 1e-6 for l in _sl))
# per-segment distance source required.
nosrc_seg = dict(adv_params)
nosrc_seg["a4_route_source"] = ""
nosrc_seg["a4_advanced_legs"] = [{"material": "steel", "route_id": "1", "route_share": 1.0,
                                  "segment_no": 1, "distance_km": 20.0, "mode": "rail",
                                  "distance_source": ""}]
_nl, _nst, _nn, _naud = _b4a(nosrc_seg, _masses_stub)
check("A4 segment without a distance source → incomplete_sources",
      _nst == "incomplete_sources")

# ── A4 road return journey (documented) ───────────────────────────────────────
ret_params = {"a4_route_source": "route", "a4_scope": "wtw", "boq_source": "BOQ",
              "transport_distance_km": 100.0, "transport_mode": "truck", "a4_mode": "simple",
              "a4_return_fraction": 0.5, "a4_empty_return_factor": 0.08,
              "a4_return_source": "RICS assumption doc", "a4_payload_assumption": "avg laden"}
_rl, _rst, _rn, _ra = _b4a(ret_params, _masses_stub)
check("A4 road return adds a return leg only with documented assumption",
      any(a["leg"] == "return" for a in _ra))
# rail leg never gets a return leg.
rail_ret = dict(ret_params); rail_ret["transport_mode"] = "rail"
_rl2, _, _, _ra2 = _b4a(rail_ret, _masses_stub)
check("A4 rail has no return leg (return is road-only)",
      not any(a["leg"] == "return" for a in _ra2))
# no hard-coded 0.5: without a documented return assumption, road is outward-only.
noret = dict(ret_params); noret["a4_return_fraction"] = 0.0; noret["a4_empty_return_factor"] = 0.0
_nl, _, _nn, _na = _b4a(noret, _masses_stub)
check("A4 no hard-coded return: outward-only without documented assumption",
      not any(a["leg"] == "return" for a in _na) and "outward-only" in _nn)
check("A4 activity audit carries mass_source + distance_source + payload/return",
      all({"mass_source", "distance_source", "payload_assumption", "return_assumption"} <= set(a)
          for a in _ra))

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
# Declare the A5 components not exercised by a given fixture as documented_zero so the
# component-gating (not_entered ≠ connected) does not block those fixtures.
_A5_DECL = {"A5.2_site_fuel": "documented_zero", "A5.2_site_electricity": "documented_zero",
            "A5.2_temporary_works": "documented_zero", "A5.3_waste_generation": "documented_zero",
            "A5.3_waste_transport": "documented_zero", "A5.3_waste_treatment": "documented_zero"}
_a5base = dict(full)
_a5base.update({"a4_route_source": "route survey"})  # A4 connected too
_a5on = dict(_a5base)
_a5on.update(include_a5=True, a5_boq_mode="installed", a5_component_declarations=_A5_DECL,
             a5_predemolition_status="not_applicable",
             a5_predemolition_note="Greenfield; no demolition in boundary",
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

# ── 11. A5 critical review items ──────────────────────────────────────────────
_a5crit = dict(_a5base)
_a5crit.update(include_a5=True, a5_boq_mode="installed", a5_component_declarations=_A5_DECL,
               a5_predemolition_status="not_applicable",
               a5_predemolition_note="Greenfield; no demolition in boundary",
               a5_waste_source="waste plan", a5_waste_route_source="haul",
               a5_waste_rates={"steel": 0.01}, a5_waste_transport_km=30.0,
               a5_waste_routes={"steel": {"transport_km": 30.0}})

# recycling with no verified factor → incomplete_sources, NOT landfill fallback.
_a5_rec = dict(_a5crit)
_a5_rec["a5_treatment_shares"] = {"steel": {"reuse": 0.0, "recycle": 0.5, "landfill": 0.5}}
_r_rec = run_scientific_lca_from_app_params(_a5_rec)
check("A5 recycle w/o verified factor → incomplete_sources (no landfill fallback)",
      _r_rec["stage_status"]["A5"] == "incomplete_sources"
      and "no landfill fallback" in _r_rec["modules"]["A5"]["note"])

# invalid treatment shares (do not sum to 1) → validation_failed.
_a5_bad = dict(_a5crit)
_a5_bad["a5_treatment_shares"] = {"steel": {"reuse": 0.0, "recycle": 0.3, "landfill": 0.3}}
_r_bad = run_scientific_lca_from_app_params(_a5_bad)
check("A5 treatment shares ≠ 1 → validation_failed",
      _r_bad["stage_status"]["A5"] == "validation_failed")

# 100% landfill of steel (verified metal factor) → connected + RICS subdivision present.
_a5_lf = dict(_a5crit)
_a5_lf["a5_treatment_shares"] = {"steel": {"reuse": 0.0, "recycle": 0.0, "landfill": 1.0}}
_r_lf = run_scientific_lca_from_app_params(_a5_lf)
_a5m = _r_lf["modules"]["A5"]
check("A5 verified landfill route → connected", _r_lf["stage_status"]["A5"] == "connected")
check("A5 RICS subdivision has A5.1–A5.4 keys",
      {"A5.1_preconstruction_demolition", "A5.2_construction_activities_tco2e",
       "A5.3_waste_management_tco2e", "A5.4_worker_transport"} <= set(_a5m["rics_subdivision"]))
check("A5.1 N/A carries a justification",
      _a5m["rics_subdivision"]["A5.1_preconstruction_demolition"]["justification"] != "(none)")

# A5.1 N/A without justification → incomplete_sources (never silent).
_a5_nojust = dict(_a5_lf); _a5_nojust["a5_predemolition_note"] = ""
_r_nj = run_scientific_lca_from_app_params(_a5_nojust)
check("A5.1 N/A without justification → incomplete_sources",
      _r_nj["stage_status"]["A5"] == "incomplete_sources")

# construction-year grid is independent of B6 year 1.
_a5_cy = dict(_a5_lf); _a5_cy["a5_construction_year"] = 2024
_r_cy = run_scientific_lca_from_app_params(_a5_cy)
check("A5 accepts an explicit construction year", _r_cy["stage_status"]["A5"] == "connected")

# ── 12. Foundational: reported-vs-diagnostic, overrides, reuse, grid mode ──────
# A5 incomplete (recycle w/o factor) but diesel sourced: diesel is computed (diagnostic>0)
# yet the reported headline must EXCLUDE it because A5 is not connected.
_a5_excl = dict(_a5crit)
_a5_excl.update(a5_diesel_l=100000.0, a5_diesel_mode="simple", a5_diesel_scope="wtw",
                a5_diesel_source="fuel log",
                a5_treatment_shares={"steel": {"reuse": 0.0, "recycle": 0.5, "landfill": 0.5}})
_r_excl = run_scientific_lca_from_app_params(_a5_excl)
check("incomplete A5 diesel is computed (diagnostic > 0)",
      _r_excl["diagnostic_stage_tco2e"]["A5"] > 0.0)
check("incomplete A5 is EXCLUDED from the reported total (reported == 0)",
      abs(_r_excl["reported_stage_tco2e"]["A5"]) < 1e-9)
check("excluded stage listed in excluded_from_reported", "A5" in _r_excl["excluded_from_reported"])
check("connected_scope headline excludes the incomplete A5 carbon",
      abs(_r_excl["connected_scope_tCO2e"]
          - (_r_excl["reported_stage_tco2e"]["A1-A3"] + _r_excl["reported_stage_tco2e"]["A4"]
             + _r_excl["reported_stage_tco2e"]["B6"])) < 1e-6)

# documented per-tonne recycle override → A5 connects (uses the row's ef_recycle + source).
_a5_ovr = dict(_a5_excl)
_a5_ovr["a5_waste_routes"] = {"steel": {"transport_km": 30.0, "ef_recycle": 0.9,
                                        "ef_landfill": 1.26435, "source": "EPD recycle route"}}
_r_ovr = run_scientific_lca_from_app_params(_a5_ovr)
check("documented per-tonne treatment override → A5 connected",
      _r_ovr["stage_status"]["A5"] == "connected")

# reuse share needs an Evidence source even for a 0 factor.
_a5_reuse = dict(_a5crit)
_a5_reuse["a5_treatment_shares"] = {"steel": {"reuse": 0.5, "recycle": 0.0, "landfill": 0.5}}
_r_reuse = run_scientific_lca_from_app_params(_a5_reuse)
check("A5 reuse without a documented source → incomplete_sources",
      _r_reuse["stage_status"]["A5"] == "incomplete_sources")
_a5_reuse_ok = dict(_a5_reuse)
_a5_reuse_ok["a5_waste_routes"] = {"steel": {"transport_km": 30.0, "ef_reuse": 0.0,
                                             "ef_landfill": 1.26435, "source": "reuse route doc"}}
_r_reuse_ok = run_scientific_lca_from_app_params(_a5_reuse_ok)
check("A5 reuse WITH a documented (even 0) source → connected",
      _r_reuse_ok["stage_status"]["A5"] == "connected")

# A5.1 not_yet_modelled → A5 incomplete (scope not closed).
_a5_nym = dict(_a5_lf); _a5_nym["a5_predemolition_status"] = "not_yet_modelled"
_r_nym = run_scientific_lca_from_app_params(_a5_nym)
check("A5.1 not_yet_modelled → A5 incomplete_sources",
      _r_nym["stage_status"]["A5"] == "incomplete_sources")

# A5 component-readiness matrix present.
check("A5 component_readiness matrix present",
      {"A5.2_site_fuel", "A5.3_waste_treatment", "A5.1_preconstruction_demolition",
       "A5.4_worker_transport"} <= set(_r_lf["modules"]["A5"]["component_readiness"]))

# grid mode: constant scenario vs annual official series.
check("constant grid → not project-specific annual",
      _r_lf["publication_readiness"]["grid_is_project_specific_annual"] is False
      and "constant" in _r_lf["grid_basis"])
_ann = dict(_a5_lf); _ann["grid_mode"] = "annual_official_series"
_ann["grid_annual_series"] = {2026 + i: {"generation": 0.40, "td": 0.03, "upstream": 0.05,
                                         "source_file": "Egypt grid 2025", "source_location": f"row {i}"}
                              for i in range(50)}
_r_ann = run_scientific_lca_from_app_params(_ann)
check("annual official series → project-specific annual flagged",
      _r_ann["publication_readiness"]["grid_is_project_specific_annual"] is True)

# expanded publication_readiness gate present.
check("publication_readiness has the 7 required criteria",
      {"method_complete", "activity_data_complete", "factor_sources_complete", "mass_balance_valid",
       "stage_applicability_complete", "project_specific_data_complete", "uncertainty_complete"}
      <= set(_r_lf["publication_readiness"]))

# ── 13. A4 validation hardening (acceptance tests 1,3,4,5) + closure gate ──────
def _a4leg(**k):
    d = {"material": "steel", "route_id": "1", "route_share": 1.0, "segment_no": 1,
         "distance_km": 10.0, "mode": "rail", "distance_source": "s"}
    d.update(k); return d
_a4base = {"a4_scope": "wtw", "boq_source": "BOQ", "a4_mode": "advanced"}
_ms1 = {"steel": ProjectQuantity(1e6, "kg", "BOQ", "x")}
check("A4 route_share outside 0..1 fails (−0.2+1.2 must NOT pass)",
      _b4a({**_a4base, "a4_advanced_legs": [_a4leg(route_id="1", route_share=-0.2),
            _a4leg(route_id="2", route_share=1.2, segment_no=1)]}, _ms1)[1] == "validation_failed")
check("A4 inconsistent route_share across a route's segments fails",
      _b4a({**_a4base, "a4_advanced_legs": [_a4leg(route_id="1", route_share=1.0, segment_no=1),
            _a4leg(route_id="1", route_share=0.9, segment_no=2)]}, _ms1)[1] == "validation_failed")
check("A4 duplicate segment_no fails",
      _b4a({**_a4base, "a4_advanced_legs": [_a4leg(segment_no=1), _a4leg(segment_no=1)]},
           _ms1)[1] == "validation_failed")
check("A4 advanced has NO global source fallback (empty segment source → incomplete)",
      _b4a({**_a4base, "a4_advanced_legs": [_a4leg(distance_source="")]}, _ms1)[1] == "incomplete_sources")
check("A4 negative distance fails",
      _b4a({**_a4base, "a4_advanced_legs": [_a4leg(distance_km=-5.0)]}, _ms1)[1] == "validation_failed")

# closure gate: three levels, all False in the current (B2-B5/C1-C4 unwired) state.
_gate = _r_lf["closure_gate"]
check("closure gate has three levels",
      {"full_wlca_calculation_complete", "standards_reporting_complete", "q1_evidence_ready"} == set(_gate))
check("full_wlca_calculation_complete False while B2-B5/C1-C4 unwired",
      _gate["full_wlca_calculation_complete"] is False)
check("q1_evidence_ready False (constant grid + uncertainty pending)",
      _gate["q1_evidence_ready"] is False)
check("old boolean aliases calculation-complete (not proxy/scope-blind True)",
      _r_lf["publication_grade_full_wlca"] == _gate["full_wlca_calculation_complete"])

# acceptance: reported gross == Σ reported stages; GWP == gross*1000/PKM.
_repsum = sum(_r_lf["reported_stage_tco2e"].values())
check("gross == Σ reported stage totals",
      abs(_r_lf["gross_A_C_tCO2e"] - _repsum) < 1e-6)
check("GWP == gross*1000/lifetime_pkm (reported)",
      abs(_r_lf["GWP_kgCO2e_per_pkm"] - _r_lf["gross_A_C_tCO2e"] * 1000.0 / _r_lf["lifetime_pkm"]) < 1e-9)

# ── 14. EPD overrides (14,15,16), annual-grid guards (10,11), empty-return unit,
#        B2-B5 year (17), Module D from C3 (21) ──────────────────────────────────
from lca_scientific_integration import (build_material_factor_overrides as _bmo,
                                        build_a4_scientific_legs as _b4b,
                                        build_module_d_rows_from_c3 as _bmd)
from lca_scientific_core import ScientificInputError as _SIE, make_project_evidence as _mpe

# FRP > 0 with an EPD override → passes; without → fails.
_frp = dict(full); _frp["frp"] = 2.0  # 2 thousand tonnes FRP
_r_frp_no = None
try:
    run_scientific_lca_from_app_params(dict(_frp)); _r_frp_no = "ran"
except _SIE:
    _r_frp_no = "blocked"
check("FRP>0 without EPD → blocked", _r_frp_no == "blocked")
_frp_ok = dict(_frp)
_frp_ok["material_epd_overrides"] = [{"material": "frp", "gwp_kgco2e_per_kg": 6.5,
                                      "source_file": "FRP EPD 2024", "source_location": "p3 tbl1",
                                      "declared_unit": "kgCO2e/kg", "declared_boundary": "A1-A3",
                                      "geography": "EU", "validity": "2029"}]
_r_frp_ok = run_scientific_lca_from_app_params(_frp_ok)
check("FRP>0 WITH EPD override → runs", _r_frp_ok["gross_A_C_tCO2e"] > 0.0)
_ovr = _bmo(_frp_ok)
check("EPD override built as Evidence for FRP", "frp" in _ovr and abs(_ovr["frp"].value - 6.5) < 1e-9)

# recycled content on a market-average ICE factor must fail (E2 guard).
from lca_scientific_core import calculate_effective_ef as _cee, MATERIAL_EF as _MEF
try:
    _cee(_MEF["steel"], 0.3, _MEF["steel"]); check("recycled-content on market-average fails", False)
except _SIE:
    check("recycled-content on market-average fails", True)

# annual grid: missing year fails; row without source fails.
_ann_miss = dict(_a5_lf); _ann_miss["grid_mode"] = "annual_official_series"
_ann_miss["grid_annual_series"] = {2026: {"generation": 0.4, "td": 0.03, "upstream": 0.05,
                                          "source_file": "s", "source_location": "r"}}
try:
    run_scientific_lca_from_app_params(_ann_miss); check("annual grid missing year fails", False)
except _SIE:
    check("annual grid missing year fails", True)
_ann_nosrc = dict(_a5_lf); _ann_nosrc["grid_mode"] = "annual_official_series"
_ann_nosrc["grid_annual_series"] = {2026 + i: {"generation": 0.4, "td": 0.03, "upstream": 0.05}
                                    for i in range(50)}
try:
    run_scientific_lca_from_app_params(_ann_nosrc); check("annual grid row without source fails", False)
except _SIE:
    check("annual grid row without source fails", True)

# A4 empty-return unit-aware: vehicle-km uses trips, not payload mass.
_veh = {"a4_scope": "wtw", "boq_source": "BOQ", "a4_mode": "simple", "transport_mode": "truck",
        "transport_distance_km": 100.0, "a4_route_source": "route",
        "a4_empty_return_factor": 0.9, "a4_return_source": "veh doc",
        "a4_return_factor_unit": "vehicle_km", "a4_number_of_trips": 40.0}
_vl, _vst, _vn, _vaud = _b4b(_veh, {"steel": ProjectQuantity(1e6, "kg", "BOQ", "x")})
check("A4 vehicle-km return leg present (trips-based)",
      _vst == "connected" and any(a["leg"] == "return" for a in _vaud))

# B2-B5 event year outside 1..RSP fails.
_b2 = dict(_a5_lf)
_b2["b2_b5_scientific_events"] = [{"module": "B2", "year": 999, "event_source": "OM plan"}]
_r_b2 = run_scientific_lca_from_app_params(_b2)
check("B2-B5 event year > RSP → validation_failed",
      _r_b2["stage_status"]["B2-B5"] == "validation_failed")

# Module D from C3: recovered output must not exceed C3 recovered mass.
_c3res = {"treatment_rows": [{"material": "steel", "mass_kg": 1000.0,
                             "reuse_share": 0.0, "recycle_share": 0.5, "disposal_share": 0.5}]}
_prim = _mpe("PRIM", 1.61, "kgCO2e/kg", "D1", "ICE", "row", "A1-A3")
_rec = _mpe("REC", 0.4, "kgCO2e/kg", "D1", "ICE", "row", "recovery")
_ok_cfg = {"steel": {"recovered_output_kg": 400.0, "secondary_input_kg": 0.0,
                     "substitution_ratio": 0.9, "flow_source": "eol", "substitution_source": "a",
                     "primary_factor": _prim, "recovery_factor": _rec}}
check("Module D from C3 within recovered mass builds a row", len(_bmd(_c3res, _ok_cfg)) == 1)
_bad_cfg = dict(_ok_cfg); _bad_cfg["steel"] = dict(_ok_cfg["steel"], recovered_output_kg=900.0)
try:
    _bmd(_c3res, _bad_cfg); check("Module D recovered > C3 recovered fails", False)
except _SIE:
    check("Module D recovered > C3 recovered fails", True)

# evidence granularity: default status is user-supplied, not 'verified'.
check("make_project_evidence default status is user_supplied (not verified)",
      _mpe("X", 1.0, "kgCO2e/kg", "A1-A3", "f", "l", "A1-A3").status == "project_specific_user_supplied")

# ── 15. Tranche-3 corrections: A5 gating, EPD partial, annual global-source, evidence gate
# A5 with un-declared not_entered components → incomplete (not connected).
_a5_gap = dict(_a5on); _a5_gap.pop("a5_component_declarations", None)
_a5_gap["a5_elec_kwh"] = 0.0  # electricity now not_entered and undeclared
_r_gap = run_scientific_lca_from_app_params(_a5_gap)
check("A5 not_entered component (undeclared) → incomplete_sources",
      _r_gap["stage_status"]["A5"] == "incomplete_sources")

# EPD row with a value but missing source → raises (no silent ICE fallback).
_epd_partial = dict(full); _epd_partial["frp"] = 0.0
_epd_partial["material_epd_overrides"] = [{"material": "steel", "gwp_kgco2e_per_kg": 1.5}]
try:
    run_scientific_lca_from_app_params(_epd_partial); check("partial EPD row → blocked (no silent fallback)", False)
except _SIE:
    check("partial EPD row → blocked (no silent fallback)", True)

# Annual mode does NOT require the global grid source.
_ann_noglobal = dict(_a5_lf)
_ann_noglobal.update(grid_mode="annual_official_series", grid_source="", grid_location="",
                     grid_annual_series={2026 + i: {"generation": 0.4, "td": 0.03, "upstream": 0.05,
                                         "source_file": "Egypt grid", "source_location": f"r{i}"}
                                         for i in range(50)})
_r_ang = run_scientific_lca_from_app_params(_ann_noglobal)
check("annual mode runs without a global grid source", _r_ang["stage_status"]["B6"] == "connected")

# Annual duplicate years flagged → fails.
_ann_dup = dict(_ann_noglobal); _ann_dup["grid_annual_duplicate_years"] = [2030]
try:
    run_scientific_lca_from_app_params(_ann_dup); check("annual duplicate years → fails", False)
except _SIE:
    check("annual duplicate years → fails", True)

# Annual row with CI total 0 → fails.
_ann_zero = dict(_ann_noglobal)
_ann_zero["grid_annual_series"] = dict(_ann_noglobal["grid_annual_series"])
_ann_zero["grid_annual_series"][2026] = {"generation": 0.0, "td": 0.0, "upstream": 0.0,
                                         "source_file": "x", "source_location": "y"}
try:
    run_scientific_lca_from_app_params(_ann_zero); check("annual row CI total 0 → fails", False)
except _SIE:
    check("annual row CI total 0 → fails", True)

# user-supplied EPD evidence blocks standards_reporting_complete (but calc can still run).
_us = dict(_a5_lf)
_us["material_epd_overrides"] = [{"material": "steel", "gwp_kgco2e_per_kg": 1.5,
                                  "source_file": "note", "source_location": "email",
                                  "declared_unit": "kgCO2e/kg", "declared_boundary": "A1-A3"}]
_r_us = run_scientific_lca_from_app_params(_us)
check("user-supplied EPD → user_supplied_evidence_used flagged",
      _r_us["publication_readiness"]["user_supplied_evidence_used"] is True)
check("user-supplied evidence blocks standards_reporting_complete",
      _r_us["closure_gate"]["standards_reporting_complete"] is False)

print("\nALL SCIENTIFIC CORE TESTS PASSED" if ok else "\nSOME TESTS FAILED")
sys.exit(0 if ok else 1)
