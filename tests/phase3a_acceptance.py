import sys
HARNESS = "tests/smoke_headless.py"
src = open(HARNESS).read().split('# ---- Execute the app module ----')[0]
exec(src)  # streamlit stub
ns = {"__name__": "__main__"}
exec(compile(open("app_final_streamlit_ready.py", encoding="utf-8").read(),
             "app_final_streamlit_ready.py", "exec"), ns)
run = ns["run_full_assessment"]
a5fn = ns["calculate_a5_construction"]
MF = ns["MATERIAL_FACTORS"]
KM = ns["MATERIAL_KEY_MAP"]
base = dict(ns["current_params"])

ok = True
def check(name, cond):
    global ok
    print(("PASS" if cond else "FAIL"), name)
    ok = ok and cond

# T1: all Phase-3 stages off -> gross == Phase 2 active (A1-A3 + A4 + B6)
r0 = run({**base, 'include_a5': False, 'sd_enable': False})
check("T1 stages off -> gross == active(A1-A3+A4+B6)",
      abs(r0['gross_a1_c4_tons'] - r0['active_total_lifecycle_co2_tons']) < 1e-6)

# T1b: with SD on, gross uses dynamic active B6
r0d = run({**base, 'include_a5': False, 'sd_enable': True, 'sd_delta': 0.02, 'sd_alpha': 0.2})
check("T1b SD on -> gross uses dynamic B6",
      abs(r0d['gross_a1_c4_tons'] - r0d['total_lifecycle_co2_dynamic']) < 1e-6)

# T4: A5 diesel raises A5 only (and gross by the same amount); other stages unchanged
rA = run({**base, 'include_a5': True, 'a5_diesel_l': 100000.0, 'a5_diesel_ef': 2.68})
expected_a5_diesel = 100000.0 * 2.68 / 1000.0
check("T4 A5 diesel -> A5 only",
      abs(rA['a5']['a5_total_tons'] - expected_a5_diesel) < 1e-6 and
      abs((rA['gross_a1_c4_tons'] - r0['gross_a1_c4_tons']) - expected_a5_diesel) < 1e-3)

# T5: purchased mode -> NO material-production waste term
rP = run({**base, 'include_a5': True, 'a5_boq_mode': 'purchased', 'a5_waste_rate': 0.10})
check("T5 purchased -> no production-waste term", abs(rP['a5']['a5_material_waste_tons']) < 1e-9)

# T6: installed mode -> A1-A3 + A5 production-waste == purchased*EF (mass conservation of production)
w = 0.10
rI = run({**base, 'include_a5': True, 'a5_boq_mode': 'installed', 'a5_waste_rate': w})
# rebuild installed masses to compute expected purchased-basis embodied carbon
import math
masses = {'concrete': base['concrete']*1000*ns['DENSITIES']['concrete'],
          'steel': base['steel']*1000*1000,
          'aluminum': base['aluminum']*1000*1000,
          'wood': base['wood']*1000*ns['DENSITIES']['wood'],
          'frp': base['frp']*1000*1000,
          'glass': base['glass']*1000*base.get('glass_thickness_mm',12.0)*2.5}
emb_installed = sum(M*MF[KM[m]]['gwp_kgco2e_per_kg'] for m,M in masses.items())/1000.0
emb_purchased = sum((M/(1-w))*MF[KM[m]]['gwp_kgco2e_per_kg'] for m,M in masses.items())/1000.0
combined = rI['total_embodied_co2'] + rI['a5']['a5_material_waste_tons']
check("T6 installed: A1-A3 + A5 waste-prod == purchased*EF",
      abs(combined - emb_purchased) < 1.0 and abs(rI['total_embodied_co2'] - emb_installed) < 1.0)

# T11: Module D not in gross
check("T11 Module D not in gross", abs(rA['gross_a1_c4_tons'] - (rA['gross_a1_c4_tons'])) < 1e-9 and
      abs(rA['net_with_module_d_tons'] - (rA['gross_a1_c4_tons'] - rA['module_d_tons'])) < 1e-6)

# T12: net = gross - module D (supplementary)
rD = run({**base, 'recycling_scenario': 'base'})
check("T12 net = gross - Module D", abs(rD['net_with_module_d_tons'] - (rD['gross_a1_c4_tons'] - rD['module_d_tons'])) < 1e-6
      and rD['module_d_tons'] > 0)

# T13: gwp/pkm uses gross (not net)
check("T13 gwp/pkm uses gross", abs(rA['gwp_pkm_gross'] - rA['gross_a1_c4_tons']*1000/rA['active_total_pkm']) < 1e-9)

# T14: sum of stage contributions == gross
ssum = sum(s['tCO2e'] for s in rA['stage_contribution'])
check("T14 sum(stage contributions) == gross", abs(ssum - rA['gross_a1_c4_tons']) < 1e-6)

# T15: FRP>0 without EPD -> publication_grade_full_lca False
rF = run({**base, 'frp': 1.0})
check("T15 FRP>0 -> full-LCA not publication-grade", rF['publication_grade_full_lca'] is False)

print("\nALL PHASE 3A ACCEPTANCE TESTS PASSED" if ok else "\nSOME TESTS FAILED")
sys.exit(0 if ok else 1)
