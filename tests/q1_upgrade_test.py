"""Acceptance tests for the R0-R20 Q1 upgrade package.
Builds a headless app namespace (Streamlit stubbed) and exercises the
scientific-boundary rules sprint by sprint. Grows as sprints land."""
import sys, types, numpy as np


def build_ns(publication_mode=True):
    st = types.ModuleType("streamlit")

    class _Ctx:
        def __enter__(self): return self
        def __exit__(self, *a): return False

    class _SS(dict):
        def __getattr__(self, k):
            try: return self[k]
            except KeyError: raise AttributeError(k)
        def __setattr__(self, k, v): self[k] = v
    st.session_state = _SS()

    def _noop(*a, **k): return None
    st.number_input = lambda l, value=0.0, **k: value
    st.slider = lambda l, mn=0, mx=100, value=0, *a, **k: value
    st.selectbox = lambda l, o, index=0, **k: o[index]
    st.checkbox = lambda l, value=False, **k: (publication_mode if k.get('key') == 'publication_mode' else value)
    st.button = lambda *a, **k: False
    st.form_submit_button = lambda *a, **k: False
    st.text_input = lambda l, value="", **k: value
    st.data_editor = lambda d, **k: d
    st.file_uploader = lambda *a, **k: None
    st.columns = lambda n, **k: [_Ctx() for _ in range(n if isinstance(n, int) else len(n))]
    st.tabs = lambda labels: [_Ctx() for _ in labels]
    st.cache_data = lambda *a, **k: (a[0] if a and callable(a[0]) else (lambda f: f))

    class _Sb(_Ctx):
        def __getattr__(self, n): return lambda *a, **k: _Ctx()
    st.sidebar = _Sb()
    for n in ["set_page_config", "markdown", "title", "header", "subheader", "write", "info",
              "warning", "success", "error", "caption", "code", "metric", "dataframe", "table",
              "plotly_chart", "download_button", "image", "divider", "latex", "json", "text", "stop"]:
        setattr(st, n, _noop)
    st.form = lambda *a, **k: _Ctx(); st.expander = lambda *a, **k: _Ctx(); st.container = lambda *a, **k: _Ctx()
    sys.modules["streamlit"] = st
    ns = {"__name__": "__main__"}
    exec(compile(open("app_final_streamlit_ready.py", encoding="utf-8").read(),
                 "app_final_streamlit_ready.py", "exec"), ns)
    return ns


ok = True
def check(name, cond):
    global ok; print(("PASS" if cond else "FAIL"), name); ok = ok and cond


ns = build_ns()
rfa = ns["run_full_assessment"]
base = dict(ns["current_params"])
r0 = rfa(base)

# ── Sprint 2 / R6: recycled content as effective A1-A3 EF (no double counting) ──
ef_eff_fn = ns["compute_effective_ef"]
e, applied = ef_eff_fn(1.61, 0.5, 0.40)
check("R6 EF_eff = (1-RC)·virgin + RC·secondary", abs(e - (0.5*1.61 + 0.5*0.40)) < 1e-9 and applied)
e2, a2 = ef_eff_fn(1.61, 0.5, None)
check("R6 blocked when secondary EF undocumented (virgin kept)", abs(e2 - 1.61) < 1e-9 and not a2)
e3, a3 = ef_eff_fn(1.61, 0.0, 0.40)
check("R6 blocked when recycled content is 0", abs(e3 - 1.61) < 1e-9 and not a3)

p = dict(base); p['recycled_content_steel'] = 0.5; p['ef_secondary_steel'] = 0.40
r1 = rfa(p)
check("R6 documented RC lowers A1-A3 gross", r1['total_embodied_co2'] < r0['total_embodied_co2'])
check("R6 steel effective EF substituted", abs(r1['effective_a1a3_ef']['steel'] - 1.005) < 1e-9)
check("R6 NO double counting: Module D unchanged by A1-A3 RC path",
      r0['lca_results']['module_d_carbon_credit_tons'] == r1['lca_results']['module_d_carbon_credit_tons'])

p2 = dict(base); p2['recycled_content_steel'] = 0.5; p2['ef_secondary_steel'] = None
r2 = rfa(p2)
check("R6 undocumented secondary EF leaves A1-A3 unchanged",
      abs(r2['total_embodied_co2'] - r0['total_embodied_co2']) < 1e-6)

# ── Sprint 3 / R8+R16: A4 transport simple vs advanced + registry ──
a4fn = ns["calculate_a4_transport_co2"]
reg = ns["TRANSPORT_FACTOR_REGISTRY"]
check("R16 transport registry carries unit/source/scope/status",
      all({'ef_kgco2e_per_tkm', 'unit', 'source', 'energy_scope', 'status'} <= set(reg[m]) for m in reg))
check("R8 truck EF not silently changed (still 0.10 default)", reg['truck']['ef_kgco2e_per_tkm'] == 0.10)
# simple: 1000 t over 100 km by truck = 1000 * 100 * 0.10 / 1000 = 10 t
simple = a4fn({'x': 1000_000.0}, 100.0, 'truck')
check("R8 simple A4 = mass·dist·EF", abs(simple - 10.0) < 1e-9)
# advanced single leg identical inputs → identical result
adv = a4fn(None, 0.0, 'truck', advanced_legs=[{'material': 'x', 'mass_kg': 1000_000.0, 'distance_km': 100.0, 'mode': 'truck'}])
check("R8 advanced single-leg == simple", abs(adv - simple) < 1e-9)
# advanced sum over legs: two legs add
adv2 = a4fn(None, 0.0, 'truck', advanced_legs=[
    {'material': 'a', 'mass_kg': 1000_000.0, 'distance_km': 100.0, 'mode': 'truck'},
    {'material': 'b', 'mass_kg': 500_000.0, 'distance_km': 200.0, 'mode': 'rail'}])
check("R16 advanced = ΣΣ legs", abs(adv2 - (10.0 + (500.0 * 200.0 * 0.03 / 1000.0))) < 1e-9)
# per-leg EF override beats registry
adv_ef = a4fn(None, 0.0, 'truck', advanced_legs=[{'material': 'a', 'mass_kg': 1000_000.0, 'distance_km': 100.0, 'mode': 'truck', 'ef': 0.062}])
check("R8 documented per-leg EF override applied", abs(adv_ef - (1000.0 * 100.0 * 0.062 / 1000.0)) < 1e-9)
# end-to-end: advanced mode routes through run_full_assessment
pa = dict(base); pa['a4_mode'] = 'advanced'
pa['a4_advanced_legs'] = [{'material': 'steel', 'mass_kg': 1000_000.0, 'distance_km': 100.0, 'mode': 'truck'}]
ra = rfa(pa)
check("R8 advanced A4 flows into LCA result", abs(ra['lca_results']['a4_transport_co2_tons'] - 10.0) < 1e-9)

# ── Sprint 4 / R9: A5 diesel simple vs equipment (mutually exclusive) ──
a5fn = ns["calculate_a5_construction"]
eqfn = ns["calculate_a5_diesel_equipment"]
diesel_ef = ns["FUEL_FACTORS"]["diesel"]["ef_kgco2e_per_l"]
# equipment: 2 units, 10 L/h, LF 0.5, CCF 1, 8 h/day, 10 days, PL 0 → 2*10*0.5*1*8*10 = 800 L
t_eq, l_eq = eqfn([{'N': 2, 'FC': 10, 'LF': 0.5, 'CCF': 1.0, 'H': 8, 'D': 10, 'PL': 0.0}], diesel_ef)
check("R9 equipment litres = ΣN·FC·LF·CCF·H·D/(1-PL)", abs(l_eq - 800.0) < 1e-9)
check("R9 equipment CO2 = litres·EF", abs(t_eq - 800.0 * diesel_ef / 1000.0) < 1e-9)
# PL raises consumption: PL=0.2 → /0.8
_, l_pl = eqfn([{'N': 1, 'FC': 10, 'LF': 1.0, 'CCF': 1.0, 'H': 1, 'D': 1, 'PL': 0.2}], diesel_ef)
check("R9 productivity loss inflates fuel (1/(1-PL))", abs(l_pl - (10.0 / 0.8)) < 1e-9)
masses = {m: 1000_000.0 for m in ['concrete', 'steel', 'aluminum', 'wood', 'frp', 'glass']}
a5_simple = a5fn(masses, {'include_a5': True, 'a5_diesel_mode': 'simple', 'a5_diesel_l': 1000.0}, 0.5)
a5_equip = a5fn(masses, {'include_a5': True, 'a5_diesel_mode': 'equipment',
                         'a5_equipment': [{'N': 1, 'FC': 1000, 'LF': 1.0, 'CCF': 1.0, 'H': 1, 'D': 1, 'PL': 0.0}]}, 0.5)
check("R9 simple uses litres only (equipment ignored)", abs(a5_simple['a5_fuel_tons'] - 1000.0 * diesel_ef / 1000.0) < 1e-9)
check("R9 equipment mode flagged + fuel from fleet", a5_equip['a5_diesel_mode'] == 'equipment' and abs(a5_equip['a5_diesel_litres'] - 1000.0) < 1e-9)

# ── Sprint 4 / R10: per-material waste shares sum to 1 + W_j formula ──
valfn = ns["validate_a5_treatment_shares"]
check("R10 valid shares (0.2+0.3+0.5=1)", valfn({'steel': {'reuse': 0.2, 'recycle': 0.3, 'landfill': 0.5}})['valid'])
check("R10 invalid shares (sum≠1) rejected", not valfn({'steel': {'reuse': 0.5, 'recycle': 0.6, 'landfill': 0.0}})['valid'])
# installed waste W = M·w/(1-w); purchased W = M·w
inst = a5fn({'steel': 1000.0}, {'include_a5': True, 'a5_boq_mode': 'installed',
            'a5_waste_rates': {'steel': 0.1}, 'a5_waste_treatment_ef': 0.0}, 0.5)
check("R10 installed waste = M·w/(1-w)", abs(inst['waste_mass_total_kg'] - 1000.0 * (0.1 / 0.9)) < 1e-6)
purch = a5fn({'steel': 1000.0}, {'include_a5': True, 'a5_boq_mode': 'purchased',
             'a5_waste_rates': {'steel': 0.1}}, 0.5)
check("R10 purchased waste = M·w", abs(purch['waste_mass_total_kg'] - 100.0) < 1e-6)
check("R10 purchased adds no production term", abs(purch['a5_material_waste_tons']) < 1e-12)

# ── Sprint 5 / R11: served demand capacity cap + availability into PKM ──
pkmfn = ns["b6_served_annual_pkm"]
# pkm_direct reproduces legacy daily_pax_km·365·1000
pk_direct, _ = pkmfn({'b6_demand_basis': 'pkm_direct', 'daily_pax_km': 500.0})
check("R11 pkm_direct == daily_pax_km·1000·365", abs(pk_direct - 500.0 * 1000 * 365) < 1e-6)
# demand capped by capacity: demand 1000 > capacity 600 → served 600
pk_cap, meta = pkmfn({'b6_demand_basis': 'daily', 'b6_demand': 1000.0, 'b6_capacity': 600.0,
                      'b6_avg_trip_km': 10.0, 'availability': 100.0})
check("R11 served demand capped by capacity (min(D,C))", meta['served'] == 600.0 and meta['capacity_binding'])
check("R11 PKM = served·trip·avail·365", abs(pk_cap - 600.0 * 10.0 * 1.0 * 365) < 1e-6)
# availability scales PKM
pk_av, _ = pkmfn({'b6_demand_basis': 'annual', 'b6_demand': 1000.0, 'b6_capacity': 2000.0,
                  'b6_avg_trip_km': 10.0, 'availability': 90.0})
check("R11 availability reduces PKM", abs(pk_av - 1000.0 * 10.0 * 0.90) < 1e-6)

# ── Sprint 5 / R8-CI: annual CI_t trajectory; renewable only as project procurement ──
cifn = ns["b6_ci_trajectory"]
flat = cifn(0.5, 0.0, 3)
check("R8-CI flat grid → CI_eff constant", all(abs(y['ci_eff'] - 0.5) < 1e-12 for y in flat))
grow = cifn(0.5, 10.0, 3)
check("R8-CI grid grows (1+g)^(t-1)", abs(grow[2]['ci_grid'] - 0.5 * 1.1 ** 2) < 1e-12)
noproj = cifn(0.5, 0.0, 2, project_renewable=False)
check("R8-CI no (1-renewable) shortcut when no project procurement", all(y['r_proj'] == 0.0 for y in noproj))
proj = cifn(0.5, 0.0, 1, project_renewable=True, r_proj0=0.4, ci_renewable=0.0)
check("R8-CI project renewable: CI_eff=(1-r)·CI_grid+r·CI_renew", abs(proj[0]['ci_eff'] - (0.6 * 0.5 + 0.4 * 0.0)) < 1e-12)

# CI_t feeds lifetime B6: growing grid raises lifetime operational CO2
pg = dict(base); pg['b6_grid_change_pct'] = 5.0
rg = rfa(pg)
check("R8-CI growing grid raises lifetime B6 vs flat",
      rg['lca_results']['lifetime_operational_co2_tons'] > r0['lca_results']['lifetime_operational_co2_tons'])
# project renewable lowers it
pr = dict(base); pr['b6_project_renewable'] = True; pr['b6_renewable_share_proj'] = 50.0; pr['b6_ci_renewable'] = 0.0
rr = rfa(pr)
check("R8-CI project renewable lowers lifetime B6",
      rr['lca_results']['lifetime_operational_co2_tons'] < r0['lca_results']['lifetime_operational_co2_tons'])

# ── Sprint 5 / R11: PV energy cost from kWh × tariff ──
ecfn = ns["b6_energy_pv_cost"]
pv, undisc = ecfn(1000.0, 0.10, 0.0, 0.0, 3)
check("R11 energy cost = kWh·tariff (no esc/disc) ×years", abs(undisc - 3 * 100.0) < 1e-9 and abs(pv - 300.0) < 1e-9)
pv0, _ = ecfn(1000.0, 0.0, 0.0, 5.0, 50)
check("R11 zero tariff → zero energy cost", pv0 == 0.0)

# ── Sprint 6 / R12: B2-B5 carbon separate from LCCA PV cost + mass balance ──
pm = dict(base)
pm.update({'include_b2b5': True, 'enable_b4': True, 'b4_years': '25', 'b4_frac_steel': 0.1,
           'b4_frac_concrete': 0.1, 'b2_cost_per_event_m': 2.0, 'b4_cost_per_event_m': 50.0,
           'lcca_maint_mode': 'activity_based', 'include_c1c4': True,
           'eol_recycle_steel': 0.5, 'eol_secondary_ef_steel': 0.4})
r_lo = rfa({**pm, 'discount_rate': 3.0})
r_hi = rfa({**pm, 'discount_rate': 12.0})
check("R12 B2-B5 carbon is invariant to discount rate (CO2≠f(PV cost))",
      abs(r_lo['i_b2b5_tons'] - r_hi['i_b2b5_tons']) < 1e-9)
check("R12 LCCA NPV does change with discount rate", abs(r_lo['npv_lcc_m'] - r_hi['npv_lcc_m']) > 1e-9)
r_nocost = rfa({**pm, 'b2_cost_per_event_m': 0.0, 'b4_cost_per_event_m': 0.0})
check("R12 B2-B5 carbon is invariant to cost inputs", abs(r_nocost['i_b2b5_tons'] - r_lo['i_b2b5_tons']) < 1e-9)
mb = r_lo['mass_balance']['mass_balance_by_material']
check("R12 mass balance: remaining = initial + added - removed",
      all(abs(x['remaining_for_C1_C4_kg'] - (x['initial_kg'] + x['added_B4_B5_kg'] - x['removed_B4_B5_kg'])) < 1e-6 for x in mb))
mbfn = ns["update_material_mass_balance"]
mbr = mbfn({'steel': 1000.0}, {'steel': 200.0}, {'steel': 50.0})
check("R12 mass-balance helper arithmetic", abs(mbr['remaining_masses_for_c1_c4']['steel'] - 1150.0) < 1e-9)

# ── Sprint 6 / R13: C1-C4 consumes remaining masses (not initial) ──
c1c4fn = ns["calculate_c1_c4_end_of_life"]
cp = {'include_c1c4': True, 'c1_diesel_l': 0.0, 'c1_elec_kwh': 0.0,
      'eol_transport_km': 100.0, 'eol_disposal_ef': 0.02}
small = c1c4fn({'steel': 1000.0}, cp, 0.5, 2.68, 0.10)
big = c1c4fn({'steel': 2000.0}, cp, 0.5, 2.68, 0.10)
check("R13 C1-C4 scales with the remaining mass it is given",
      big['c1_c4_total_tons'] > small['c1_c4_total_tons'] > 0)

# ── Sprint 6 / R14: gross/net strictly separated; GWP/pkm on gross only ──
check("R14 GWP/pkm uses GROSS (not net)",
      abs(r_lo['gwp_pkm_gross'] - r_lo['gross_a1_c4_tons'] * 1000 / r_lo['active_total_pkm']) < 1e-6)
check("R14 Module D never inside gross (net = gross - D)",
      abs(r_lo['net_with_module_d_tons'] - (r_lo['gross_a1_c4_tons'] - r_lo['module_d_tons'])) < 1e-6)
check("R14 gross = Σ stages (A1A3+A4+A5+B2B5+B6+C1C4)",
      abs(r_lo['gross_a1_c4_tons'] - (r_lo['total_embodied_co2'] + r_lo['lca_results']['a4_transport_co2_tons']
          + r_lo['a5']['a5_total_tons'] + r_lo['i_b2b5_tons'] + r_lo['active_b6_tons'] + r_lo['i_c1c4_tons'])) < 1e-6)

# ── Sprint 7 / R15: benefit KPIs separate, computed, never netted into LCA ──
bkfn = ns["calculate_benefit_kpis"]
bp = {'energy_per_pax': 0.15, 'carbon_intensity': 0.5, 'benefit_baseline_ci_pkm': 0.20,
      'benefit_annual_trips': 1_000_000.0, 'benefit_time_saved_min': 12.0, 'benefit_value_of_time': 10.0,
      'benefit_jobs_per_musd': 2.0, 'construction_cost': 2500.0, 'benefit_operational_jobs': 500.0,
      'economic_multiplier': 2.5, 'benefit_land_ha': 50.0,
      'benefit_noise_baseline_db': 80.0, 'benefit_noise_monorail_db': 65.0}
bk = bkfn(bp, 3_650_000_000.0, 50)
# CO2 avoided = max(0.20 - 0.15*0.5, 0)·PKM/1000 = 0.125·3.65e9/1000
check("R15 CO2 avoided = (EF_base - EF_mono)·PKM", abs(bk['annual_co2_avoided_tons'] - 0.125 * 3_650_000_000.0 / 1000.0) < 1e-3)
check("R15 hours saved = trips·min/60", abs(bk['annual_hours_saved'] - 1_000_000.0 * 12.0 / 60.0) < 1e-6)
check("R15 VoTS = hours·VoT", abs(bk['annual_vots_musd'] - (200000.0 * 10.0 / 1e6)) < 1e-9)
check("R15 jobs = per_musd·capex + operational", abs(bk['total_jobs'] - (2.0 * 2500.0 + 500.0)) < 1e-9)
check("R15 economic impact = capex·multiplier", abs(bk['economic_impact_musd'] - 2500.0 * 2.5) < 1e-9)
check("R15 noise reduction ratio = (base-mono)/base", abs(bk['noise_reduction_ratio'] - (15.0 / 80.0)) < 1e-9)
# never subtracted from LCA: enabling benefits leaves gross/net unchanged
rb = rfa({**base, 'benefit_baseline_ci_pkm': 0.20, 'benefit_annual_trips': 1e6, 'benefit_value_of_time': 10.0})
check("R15 benefits do NOT change gross LCA", abs(rb['gross_a1_c4_tons'] - r0['gross_a1_c4_tons']) < 1e-9)
check("R15 benefits do NOT change net LCA", abs(rb['net_with_module_d_tons'] - r0['net_with_module_d_tons']) < 1e-9)
check("R15 benefit KPIs exposed separately in results", 'benefit_kpis' in rb and rb['benefit_kpis']['annual_co2_avoided_tons'] > 0)
check("R15 zero inputs → zero co-benefits", bkfn({}, 1e6, 50)['total_jobs'] == 0.0)

# ── Sprint 8 / R17-energycost: tariff-based energy PV flows into LCCA NPV ──
r_notariff = rfa(base)
r_tariff = rfa({**base, 'b6_energy_tariff': 0.10})
check("R17 energy tariff raises LCCA NPV", r_tariff['npv_lcc_m'] > r_notariff['npv_lcc_m'])
check("R17 tariff energy PV exposed (kWh×tariff)", r_tariff['b6_energy_pv_cost_m'] > 0)
# escalation increases it further
r_escal = rfa({**base, 'b6_energy_tariff': 0.10, 'b6_energy_escalation_pct': 3.0})
check("R17 energy escalation raises energy PV", r_escal['b6_energy_pv_cost_m'] > r_tariff['b6_energy_pv_cost_m'])

# ── Sprint 8 / R18: final tab order ends Uncertainty→SI→Benchmark→Methodology ──
sci = ns["_SCI_ORDER"]
check("R18 tab order ends with uncertainty/si/benchmark/about",
      sci[-4:] == ['uncertainty', 'si', 'benchmark', 'about'])

# ── Sprint 8 / R14+R19: Module D always separate (never inside gross) ──
rmod = rfa({**base, 'include_c1c4': True, 'eol_recycle_steel': 0.6, 'eol_secondary_ef_steel': 0.4})
check("R19 Module D > 0 yet excluded from gross", rmod['module_d_tons'] > 0
      and abs(rmod['gross_a1_c4_tons'] - (rmod['total_embodied_co2'] + rmod['lca_results']['a4_transport_co2_tons']
              + rmod['a5']['a5_total_tons'] + rmod['i_b2b5_tons'] + rmod['active_b6_tons'] + rmod['i_c1c4_tons'])) < 1e-6)

# ── R1/R20: per-material A1-A3 metadata present in the audit table ──
audit_cols = set(ns["MATERIAL_FACTOR_AUDIT"].columns)
check("R1 audit has dqi/source/declared_unit/boundary/status",
      {'dqi_score', 'carbon_source', 'declared_unit', 'boundary', 'status'} <= audit_cols)

# ── R0/R2/R19: publication mode hides illustrative/legacy tabs ──
ns_pub = build_ns(publication_mode=True)
ns_dev = build_ns(publication_mode=False)
legacy = set(ns_pub["_LEGACY_ORDER"])
check("R0 publication mode excludes all legacy/illustrative tabs",
      not (legacy & set(ns_pub["_order"])) and legacy <= set(ns_dev["_order"]))

print("\nQ1 UPGRADE TESTS PASSED" if ok else "\nQ1 UPGRADE TESTS FAILED")
sys.exit(0 if ok else 1)
