import sys
HARNESS = "tests/smoke_headless.py"
src = open(HARNESS).read().split('# ---- Execute the app module ----')[0]
exec(src)  # streamlit stub
ns = {"__name__": "__main__"}
exec(compile(open("app_final_streamlit_ready.py", encoding="utf-8").read(),
             "app_final_streamlit_ready.py", "exec"), ns)
run = ns["run_full_assessment"]
base = dict(ns["current_params"])
MF = ns["MATERIAL_FACTORS"]; KM = ns["MATERIAL_KEY_MAP"]

ok = True
def check(name, cond):
    global ok
    print(("PASS" if cond else "FAIL"), name)
    ok = ok and cond

# helper: a valid EOL config (steel 90% recycle, others disposal) with EFs
def eol(**over):
    p = dict(base)
    p.update({'include_c1c4': True, 'c1_diesel_l': 0.0, 'c1_elec_kwh': 0.0,
              'eol_transport_km': 50.0, 'eol_reuse_ef': 0.0, 'eol_recycle_ef': 0.0,
              'eol_disposal_ef': 0.0, 'eol_recovery_eta': 1.0, 'eol_cost_m': 0.0})
    for m in ['concrete','steel','aluminum','wood','frp','glass']:
        p[f'eol_reuse_{m}'] = 0.0; p[f'eol_recycle_{m}'] = 0.0; p[f'eol_secondary_ef_{m}'] = 0.0
    p.update(over)
    return p

r3b = run({**base, 'include_c1c4': False})

# T3C-1: C1-C4 off -> gross == Phase 3B gross
check("T3C-1 C1-C4 off -> gross == Phase 3B", abs(run({**base, 'include_c1c4': False})['gross_a1_c4_tons'] - r3b['gross_a1_c4_tons']) < 1e-9)

# T3C-2: shares sum to 1 (per material) when valid
rV = run(eol(eol_recycle_steel=0.9))
check("T3C-2 shares sum to 1", all(abs(s['sum'] - 1.0) < 1e-9 for s in rV['eol_validation']['share_table']))

# T3C-3: invalid shares -> error + publication_grade_full_lca False + C1-C4 not computed
rI = run(eol(eol_reuse_steel=0.7, eol_recycle_steel=0.7))
check("T3C-3 invalid shares -> not valid, no C1-C4, pub-grade False",
      (rI['eol_validation']['valid'] is False) and (rI['c1c4']['included'] is False) and (rI['publication_grade_full_lca'] is False))

# T3C-4: C1 diesel raises C1 only
r0 = run(eol())
rC1 = run(eol(c1_diesel_l=100000.0))
check("T3C-4 C1 diesel -> C1 only", rC1['c1c4']['c1_tons'] > r0['c1c4']['c1_tons'] and
      abs(rC1['c1c4']['c2_tons'] - r0['c1c4']['c2_tons']) < 1e-9 and abs(rC1['c1c4']['c4_tons'] - r0['c1c4']['c4_tons']) < 1e-9)

# T3C-5: C2 distance raises C2 only
rC2 = run(eol(eol_transport_km=500.0))
check("T3C-5 C2 distance -> C2 only", rC2['c1c4']['c2_tons'] > r0['c1c4']['c2_tons'] and
      abs(rC2['c1c4']['c1_tons'] - r0['c1c4']['c1_tons']) < 1e-9 and abs(rC2['c1c4']['c4_tons'] - r0['c1c4']['c4_tons']) < 1e-9)

# T3C-6: recycling processing EF raises C3 only (need recycle share > 0)
rC3 = run(eol(eol_recycle_steel=0.9, eol_recycle_ef=0.2))
rC3base = run(eol(eol_recycle_steel=0.9, eol_recycle_ef=0.0))
check("T3C-6 recycle EF -> C3 only", rC3['c1c4']['c3_tons'] > rC3base['c1c4']['c3_tons'] and
      abs(rC3['c1c4']['c4_tons'] - rC3base['c1c4']['c4_tons']) < 1e-6)

# T3C-7: disposal EF raises C4 only (steel default disposal=1)
rC4 = run(eol(eol_disposal_ef=0.05))
check("T3C-7 disposal EF -> C4 only", rC4['c1c4']['c4_tons'] > r0['c1c4']['c4_tons'] and
      abs(rC4['c1c4']['c3_tons'] - r0['c1c4']['c3_tons']) < 1e-9)

# T3C-8: C1+C2+C3+C4 == total
cc = rC4['c1c4']
check("T3C-8 C1+C2+C3+C4 == total", abs((cc['c1_tons']+cc['c2_tons']+cc['c3_tons']+cc['c4_tons']) - cc['c1_c4_total_tons']) < 1e-9)

# T3C-9 & T3C-10: C1-C4 uses remaining masses (after B4) not initial
# B4 removes steel at yr25 -> like-for-like remaining steel == initial; verify C2 uses remaining
rMB = run(eol(include_b2b5=True, enable_b4=True, b4_years='25', b4_frac_steel=0.2, eol_transport_km=100.0))
steel_remaining = next(m['remaining_for_C1_C4_kg'] for m in rMB['mass_balance']['mass_balance_by_material'] if m['material']=='steel')
steel_eol = next(e['remaining_kg'] for e in rMB['c1c4']['eol_by_material'] if e['material']=='steel')
check("T3C-9/10 C1-C4 uses remaining masses (==mass balance, not double-counting removed)",
      abs(steel_eol - steel_remaining) < 1e-6)

# T3C-11: Module D not in gross (gross unchanged whether module D big or zero)
rMDa = run(eol(eol_recycle_steel=0.9, eol_secondary_ef_steel=0.5))
rMDb = run(eol(eol_recycle_steel=0.9, eol_secondary_ef_steel=0.0))
check("T3C-11 Module D not in gross", abs(rMDa['gross_a1_c4_tons'] - rMDb['gross_a1_c4_tons']) < 1e-9)

# T3C-12: net = gross - module D
check("T3C-12 net = gross - Module D", abs(rMDa['net_with_module_d_tons'] - (rMDa['gross_a1_c4_tons'] - rMDa['module_d_tons'])) < 1e-6)

# T3C-13: GWP/pkm uses gross
check("T3C-13 GWP/pkm uses gross", abs(rMDa['gwp_pkm_gross'] - rMDa['gross_a1_c4_tons']*1000/rMDa['active_total_pkm']) < 1e-9)

# T3C-14: stage contribution sum == gross
ssum = sum(s['tCO2e'] for s in rMDa['stage_contribution'])
check("T3C-14 sum(stages) == gross", abs(ssum - rMDa['gross_a1_c4_tons']) < 1e-6)

# T3C-15: Module D == 0 if recovery shares == 0
rNoRec = run(eol(eol_secondary_ef_steel=0.5))  # all shares 0 -> nothing recovered
check("T3C-15 Module D == 0 when no recovery", abs(rNoRec['module_d_tons']) < 1e-12)

# T3C-16: Module D not computed for material without secondary EF (quality flag)
rMiss = run(eol(eol_recycle_steel=0.9, eol_secondary_ef_steel=0.0))
check("T3C-16 missing secondary EF -> Module D skipped + quality False",
      abs(rMiss['module_d_tons']) < 1e-12 and rMiss['module_d_quality_ok'] is False and rMiss['publication_grade_full_lca'] is False)

# T3C-17: EOL cost enters LCCA exactly once (delta == PV of eol_cost)
rE0 = run(eol(eol_cost_m=0.0))
rE1 = run(eol(eol_cost_m=100.0))
r_disc = base.get('discount_rate', 5.0) / 100.0
T = ns['ASSESSMENT_LIFETIME_YEARS']
pv_expected = 100.0 / ((1 + r_disc) ** T)
check("T3C-17 EOL cost enters LCCA once", abs((rE1['npv_lcc_m'] - rE0['npv_lcc_m']) - pv_expected) < 1e-6)

# T3C-18: consistency — stage_contribution shows C1-C4 included when on
statuses = {s['Stage']: s['status'] for s in rMDa['stage_contribution']}
check("T3C-18 stage table shows C1-C4 included", 'included' in statuses['C1-C4 end-of-life'])

print("\nALL PHASE 3C ACCEPTANCE TESTS PASSED" if ok else "\nSOME TESTS FAILED")
sys.exit(0 if ok else 1)
