import sys
import os as _os, sys as _sys
# The app now imports sibling domain modules; these suites exec it from tests/,
# so the repository root must be importable.
_SEP_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _SEP_ROOT not in _sys.path:
    _sys.path.insert(0, _SEP_ROOT)

import numpy as np
HARNESS = "tests/smoke_headless.py"
src = open(HARNESS).read().split('# ---- Execute the app module ----')[0]
exec(src)
ns = {"__name__": "__main__"}
exec(compile(open("apps/_developer_impl.py", encoding="utf-8").read(),
             "apps/_developer_impl.py", "exec"), ns)
run = ns["run_full_assessment"]; mc = ns["run_component_monte_carlo"]
sfd = ns["sample_from_distribution"]; build_reg = ns["build_uncertainty_registry"]
base = dict(ns["current_params"])

ok = True
def check(name, cond):
    global ok
    print(("PASS" if cond else "FAIL"), name); ok = ok and cond

# A representative "full" config (A5+B2B5+C1C4 on) for engine tests
full = {**base, 'include_a5': True, 'a5_diesel_l': 50000.0,
        'include_b2b5': True, 'b2_material_pct': 0.05, 'enable_b4': True, 'b4_years': '25', 'b4_frac_steel': 0.1,
        'include_c1c4': True, 'eol_recycle_steel': 0.9, 'eol_secondary_ef_steel': 0.5,
        'eol_disposal_ef': 0.02, 'eol_recycle_ef': 0.05}
R = mc(full, n=300, seed=42); O = R['outputs']; OK = O[~O['failed']]

# T4-1: cv=0 -> sampled == base
u = np.linspace(0.01, 0.99, 7)
check("T4-1 cv=0 -> base", all(np.allclose(sfd(u, {'base_value': 5.0, 'distribution': d, 'cv': 0.0}), 5.0)
                               for d in ['lognormal', 'normal', 'triangular']))
# T4-2: gross == Σ stages every run
ssum = OK['A1_A3_tons']+OK['A4_tons']+OK['A5_tons']+OK['B2_B5_tons']+OK['B6_tons']+OK['C1_C4_tons']
check("T4-2 gross == Σ stages", bool(((ssum - OK['gross_a1_c4_tons']).abs() < 1e-6).all()))
# T4-3: net = gross - Module D
check("T4-3 net = gross - D", bool(((OK['net_with_module_d_tons'] - (OK['gross_a1_c4_tons'] - OK['module_d_tons'])).abs() < 1e-6).all()))
# T4-4: GWP/pkm uses gross (pkm constant since daily_pax_km not sampled)
pkm = R['baseline']['active_total_pkm']
check("T4-4 GWP/pkm uses gross", bool(((OK['gwp_pkm_gross'] - OK['gross_a1_c4_tons']*1000/pkm).abs() < 1e-6).all()))
# T4-5: Module D not in gross (deterministic)
g0 = run({**full, 'eol_secondary_ef_steel': 0.1})['gross_a1_c4_tons']
g1 = run({**full, 'eol_secondary_ef_steel': 0.9})['gross_a1_c4_tons']
check("T4-5 Module D not in gross", abs(g0 - g1) < 1e-9)
# T4-6: fixed seed deterministic
R2 = mc(full, n=120, seed=42); Rb = mc(full, n=120, seed=42)
check("T4-6 fixed seed deterministic", bool((R2['outputs']['gross_a1_c4_tons'].fillna(-1) == Rb['outputs']['gross_a1_c4_tons'].fillna(-1)).all()))
# T4-7: no negative emissions
check("T4-7 no negative emissions", bool((OK[['A1_A3_tons','A4_tons','A5_tons','B2_B5_tons','B6_tons','C1_C4_tons','gross_a1_c4_tons']] >= -1e-9).all().all()))
# T4-8: treatment shares sum to 1 (reuse+recycle <= 1 each run)
share_cols = [c for c in R['samples'].columns if c.startswith('eol_reuse_') or c.startswith('eol_recycle_')]
steel_ok = (R['samples']['eol_reuse_steel'] + R['samples']['eol_recycle_steel'] <= 1.0 + 1e-9).all()
check("T4-8 shares sum<=1 (Dirichlet)", bool(steel_ok) and len(share_cols) > 0)
# T4-9 & T4-10: C1-C4 uses remaining (deterministic, like-for-like remaining==initial)
rmb = run({**full, 'b4_frac_steel': 0.2})
steel_rem = next(m['remaining_for_C1_C4_kg'] for m in rmb['mass_balance']['mass_balance_by_material'] if m['material'] == 'steel')
steel_eol = next(e['remaining_kg'] for e in rmb['c1c4']['eol_by_material'] if e['material'] == 'steel')
check("T4-9/10 C1-C4 uses remaining masses", abs(steel_eol - steel_rem) < 1e-6)
# T4-11: A1-A3 EF uncertainty affects A1-A3 only (other stages OFF)
p_off = {**base, 'include_a5': False, 'include_b2b5': False, 'include_c1c4': False, 'sd_enable': False}
b = run(p_off); e = run({**p_off, 'unc_ef_mult_concrete': 1.5})
check("T4-11 EF mult -> A1-A3 only", e['total_embodied_co2'] > b['total_embodied_co2'] and
      abs(e['active_b6_tons'] - b['active_b6_tons']) < 1e-9 and
      abs(e['lca_results']['a4_transport_co2_tons'] - b['lca_results']['a4_transport_co2_tons']) < 1e-9)
# T4-12: grid CI affects B6 only (stages off)
e2 = run({**p_off, 'carbon_intensity': p_off['carbon_intensity']*1.5})
check("T4-12 grid CI -> B6 only", e2['active_b6_tons'] > b['active_b6_tons'] and
      abs(e2['total_embodied_co2'] - b['total_embodied_co2']) < 1e-9)
# T4-13/14/15: inactive stages have no active uncertainty rows
reg_off = build_reg(p_off, b)
act_stages = set(reg_off[reg_off['active_when']]['stage'])
check("T4-13 A5 off -> no A5 uncertainty", 'A5' not in act_stages)
check("T4-14 B2-B5 off -> no B2-B5 uncertainty", 'B2-B5' not in act_stages)
check("T4-15 C1-C4 off -> no C1-C4 uncertainty + no shares", 'C1-C4' not in act_stages and
      not any(c.startswith('eol_reuse_') for c in ns["sample_uncertain_parameters"](reg_off, 5, 42, params=p_off).columns))
# T4-16: no legacy total-scaling -> outputs use gross, not total_co2
check("T4-16 no total-scaling (gross used)", 'gross_a1_c4_tons' in O.columns and 'total_co2' not in O.columns)
# T4-17: summary percentiles ordered
srow = R['summary'].set_index('metric').loc['gross_a1_c4_tons']
check("T4-17 percentiles ordered", srow['P2.5'] <= srow['P50'] <= srow['P97.5'])
# T4-18: convergence diagnostics present
check("T4-18 convergence diagnostics", set(['mean_stable','p95_stable','convergence_ok']).issubset(R['convergence'].keys()))
# T4-19: drivers table present
check("T4-19 drivers table", len(R['drivers']) > 0 and 'spearman_rho' in R['drivers'].columns)
# T4-20: exportable frames
import pandas as pd
check("T4-20 exportable frames", all(isinstance(R[k], pd.DataFrame) and len(R[k]) > 0 for k in ['samples','outputs','summary','drivers','quality']))
# T4-21: n<5000 -> publication_grade_uncertainty False
check("T4-21 n<5000 -> pgu False", R['publication_grade_uncertainty'] is False)
# T4-22: tiny n -> convergence not ok -> pgu False
Rt = mc(full, n=30, seed=42)
check("T4-22 convergence fail -> pgu False", Rt['convergence']['convergence_ok'] is False and Rt['publication_grade_uncertainty'] is False)
# T4-23: MC does not mutate baseline deterministic result
det_before = run(full)['gross_a1_c4_tons']; _ = mc(full, n=50, seed=7); det_after = run(full)['gross_a1_c4_tons']
check("T4-23 baseline unchanged by MC", abs(det_before - det_after) < 1e-9)
# T4-24: LCCA uncertainty <-> CO2 separation
check("T4-24 cost !-> gross, qty !-> npv",
      abs(run({**full, 'construction_cost': full['construction_cost']*2})['gross_a1_c4_tons'] - run(full)['gross_a1_c4_tons']) < 1e-9 and
      abs(run({**full, 'concrete': full['concrete']*1.2})['npv_lcc_m'] - run(full)['npv_lcc_m']) < 1e-9)
# T4-25: no failed runs for valid config
check("T4-25 no failed runs (valid config)", R['n_ok'] == R['n'])

print("\nALL PHASE 4 ACCEPTANCE TESTS PASSED" if ok else "\nSOME TESTS FAILED")
sys.exit(0 if ok else 1)
