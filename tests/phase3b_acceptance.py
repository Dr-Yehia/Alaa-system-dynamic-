import sys
import os as _os, sys as _sys
# The app now imports sibling domain modules; these suites exec it from tests/,
# so the repository root must be importable.
_SEP_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _SEP_ROOT not in _sys.path:
    _sys.path.insert(0, _SEP_ROOT)

HARNESS = "tests/smoke_headless.py"
src = open(HARNESS).read().split('# ---- Execute the app module ----')[0]
exec(src)  # streamlit stub
ns = {"__name__": "__main__"}
exec(compile(open("app_final_streamlit_ready.py", encoding="utf-8").read(),
             "app_final_streamlit_ready.py", "exec"), ns)
run = ns["run_full_assessment"]
base = dict(ns["current_params"])

ok = True
def check(name, cond):
    global ok
    print(("PASS" if cond else "FAIL"), name)
    ok = ok and cond

# Baseline (3A): B2-B5 off
r3a = run({**base, 'include_b2b5': False})

# T3B-1: include_b2b5=False -> gross == Phase 3A gross
check("T3B-1 B2-B5 off -> gross == Phase 3A",
      abs(run({**base, 'include_b2b5': False})['gross_a1_c4_tons'] - r3a['gross_a1_c4_tons']) < 1e-9)

# T3B-2: B2 diesel only -> raises B2-B5 only (and gross by same), other stages unchanged
rB2 = run({**base, 'include_b2b5': True, 'b2_use_sd_schedule': False, 'b2_interval': 5,
           'b2_material_pct': 0.0, 'b2_diesel_l': 1000.0})
check("T3B-2 B2 diesel only -> B2-B5 up, gross up by same",
      rB2['i_b2b5_tons'] > 0 and
      abs((rB2['gross_a1_c4_tons'] - r3a['gross_a1_c4_tons']) - rB2['i_b2b5_tons']) < 1e-6 and
      abs(rB2['a5']['a5_total_tons'] - r3a['a5']['a5_total_tons']) < 1e-9)

# T3B-3: use_sd_schedule -> B2 years == SD maintenance_action years
rSD = run({**base, 'sd_enable': True, 'sd_maint_interval': 5, 'sd_rho': 0.05,
           'include_b2b5': True, 'b2_use_sd_schedule': True, 'b2_material_pct': 0.05})
sd_maint_years = [row['year'] for row in rSD['sd_rows'] if row['maintenance_action'] == 1]
b2_years = [row['year'] for row in rSD['b2b5_schedule'] if row['B2_count'] == 1]
check("T3B-3 B2 years == SD maintenance_action years", sd_maint_years == b2_years and len(b2_years) > 0)

# T3B-4: SD maintenance is NOT free -> B2 activity emissions > 0 at SD schedule
check("T3B-4 no free maintenance (B2 emissions > 0 under SD schedule)", rSD['b2b5']['b2_tons'] > 0)

# T3B-5: B4 replacement at year 25 -> emissions appear in year 25
rB4 = run({**base, 'include_b2b5': True, 'enable_b4': True, 'b4_years': '25',
           'b4_frac_steel': 0.1, 'b4_cost_per_event_m': 10.0})
yr25 = next(y for y in rB4['b2b5']['yearly'] if y['year'] == 25)
yr24 = next(y for y in rB4['b2b5']['yearly'] if y['year'] == 24)
check("T3B-5 B4 emissions appear in replacement year 25", yr25['B4_tCO2e'] > 0 and yr24['B4_tCO2e'] == 0)

# T3B-6: B4 raises BOTH LCA and LCCA (vs no-B4)
rNoB4 = run({**base, 'include_b2b5': True, 'enable_b4': False, 'lcca_maint_mode': 'activity_based'})
rWB4 = run({**base, 'include_b2b5': True, 'enable_b4': True, 'b4_years': '25',
            'b4_frac_steel': 0.1, 'b4_cost_per_event_m': 10.0, 'lcca_maint_mode': 'activity_based'})
check("T3B-6 B4 raises LCA and LCCA",
      rWB4['i_b2b5_tons'] > rNoB4['i_b2b5_tons'] and rWB4['npv_lcc_m'] > rNoB4['npv_lcc_m'])

# T3B-7: mass balance remaining = initial + added - removed
mb = {m['material']: m for m in rB4['mass_balance']['mass_balance_by_material']}
check("T3B-7 remaining = initial + added - removed",
      all(abs(m['remaining_for_C1_C4_kg'] - (m['initial_kg'] + m['added_B4_B5_kg'] - m['removed_B4_B5_kg'])) < 1e-6
          for m in mb.values()))

# T3B-8: like-for-like replacement -> removed not increasing remaining (remaining == initial for steel)
check("T3B-8 removed material not in remaining (like-for-like -> remaining==initial)",
      abs(mb['steel']['remaining_for_C1_C4_kg'] - mb['steel']['initial_kg']) < 1e-6 and
      mb['steel']['removed_B4_B5_kg'] > 0)

# T3B-9 & T3B-11: simple_annual does NOT add B2 activity costs (vs activity mode using B2 cost)
rSimple = run({**base, 'include_b2b5': True, 'b2_use_sd_schedule': False, 'b2_interval': 5,
               'b2_cost_per_event_m': 5.0, 'lcca_maint_mode': 'simple_annual'})
rSimpleNoCost = run({**base, 'include_b2b5': True, 'b2_use_sd_schedule': False, 'b2_interval': 5,
                     'b2_cost_per_event_m': 0.0, 'lcca_maint_mode': 'simple_annual'})
check("T3B-9 simple_annual ignores B2 activity cost", abs(rSimple['npv_lcc_m'] - rSimpleNoCost['npv_lcc_m']) < 1e-9)

# T3B-10: activity_based does NOT use annual_maintenance (changing annual maint doesn't move NPV)
rActA = run({**base, 'include_b2b5': True, 'lcca_maint_mode': 'activity_based', 'maintenance_cost': 50.0})
rActB = run({**base, 'include_b2b5': True, 'lcca_maint_mode': 'activity_based', 'maintenance_cost': 200.0})
check("T3B-10 activity_based ignores annual_maintenance", abs(rActA['npv_lcc_m'] - rActB['npv_lcc_m']) < 1e-9)

# T3B-11: activity mode WITH B2 cost differs from simple -> modes are genuinely different (no merge)
rActCost = run({**base, 'include_b2b5': True, 'b2_use_sd_schedule': False, 'b2_interval': 5,
                'b2_cost_per_event_m': 5.0, 'lcca_maint_mode': 'activity_based'})
check("T3B-11 activity mode applies B2 cost (no double-count merge)", rActCost['npv_lcc_m'] != rActA['npv_lcc_m'])

# T3B-12: Module D unchanged by B2-B5
rD0 = run({**base, 'recycling_scenario': 'base', 'include_b2b5': False})
rD1 = run({**base, 'recycling_scenario': 'base', 'include_b2b5': True, 'enable_b4': True,
           'b4_years': '25', 'b4_frac_steel': 0.1})
check("T3B-12 Module D unchanged by B2-B5", abs(rD0['module_d_tons'] - rD1['module_d_tons']) < 1e-9)

# T3B-13: functional unit uses gross (incl. B2-B5)
check("T3B-13 gwp/pkm uses gross incl B2-B5",
      abs(rB4['gwp_pkm_gross'] - rB4['gross_a1_c4_tons']*1000/rB4['active_total_pkm']) < 1e-9)

# T3B-14: sum of stage contributions == gross
ssum = sum(s['tCO2e'] for s in rB4['stage_contribution'])
check("T3B-14 sum(stage contributions) == gross", abs(ssum - rB4['gross_a1_c4_tons']) < 1e-6)

# T3B-15: all B2/B4 inputs zero -> B2-B5 == 0
rZero = run({**base, 'include_b2b5': True, 'b2_use_sd_schedule': False, 'b2_interval': 0,
             'b2_material_pct': 0.0, 'b2_diesel_l': 0.0, 'b2_elec_kwh': 0.0, 'enable_b4': False})
check("T3B-15 all-zero inputs -> B2-B5 == 0", abs(rZero['i_b2b5_tons']) < 1e-12)

print("\nALL PHASE 3B ACCEPTANCE TESTS PASSED" if ok else "\nSOME TESTS FAILED")
sys.exit(0 if ok else 1)
