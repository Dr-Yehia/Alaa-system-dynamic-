import types, sys
# build the same streamlit stub by importing the smoke harness machinery
HARNESS="/tmp/claude-0/-home-user-Alaa-system-dynamic-/929ac78a-f3ba-50be-8f38-ed4bf8142a8b/scratchpad/smoke.py"
src = open(HARNESS).read().split('# ---- Execute the app module ----')[0]
exec(src)  # defines st stub and registers sys.modules['streamlit']

app = open("app_final_streamlit_ready.py", encoding="utf-8").read()
ns = {"__name__": "__main__"}
exec(compile(app, "app_final_streamlit_ready.py", "exec"), ns)

sim = ns["simulate_asset_condition"]
dynb6 = ns["calculate_dynamic_b6"]
run = ns["run_full_assessment"]
base = dict(ns["current_params"])
T = ns["ASSESSMENT_LIFETIME_YEARS"]

def cond_series(**kw):
    rows, cs = sim(lifetime_years=T, **kw)
    return rows, cs

ok=True
def check(name, cond):
    global ok
    print(("PASS" if cond else "FAIL"), name)
    ok = ok and cond

# T1: delta=0, rho=0 -> C constant
rows,cs = cond_series(C0=1.0, delta=0.0, maintenance_interval=0, rho=0.0, tau=1)
check("T1 delta=0,no-maint -> C constant=1", all(abs(r['C_end']-1.0)<1e-9 for r in rows))

# T2: delta>0, no maintenance -> monotonic decrease
rows,cs = cond_series(C0=1.0, delta=0.01, maintenance_interval=0, rho=0.0, tau=1)
ends=[r['C_end'] for r in rows]
check("T2 delta>0,no-maint -> monotonic decreasing", all(ends[i+1] <= ends[i]+1e-12 for i in range(len(ends)-1)) and ends[-1] < 1.0)

# T3: maintenance every 5 yrs, tau=1 -> recovery appears the year AFTER a maintenance year
rows,cs = cond_series(C0=1.0, delta=0.01, maintenance_interval=5, rho=0.05, tau=1)
# maintenance action at year 5; delayed recovery should register at year 6
rec_year6 = rows[5]['maintenance_recovery_flow']   # year 6 (index 5)
rec_year5 = rows[4]['maintenance_recovery_flow']   # year 5 (index 4)
check("T3 delayed recovery shows at t=6 (tau=1) not t=5", rec_year6 > 0 and rec_year5 == 0)

# T4: alpha=0 -> dynamic B6 == static B6
rows,cs = cond_series(C0=1.0, delta=0.02, maintenance_interval=5, rho=0.05, tau=1)
b6 = dynb6(cs, EI0=0.15, daily_pkm=5e5, CI=0.5, lifetime_years=T, alpha=0.0, g=0.0)
check("T4 alpha=0 -> dyn==static", abs(b6['b6_dynamic_tons']-b6['b6_static_tons'])<1e-6)

# T5: C in [0,1] always (aggressive params)
rows,cs = cond_series(C0=1.0, delta=0.5, maintenance_interval=2, rho=0.9, tau=1)
check("T5 C in [0,1] for all t", all(0.0-1e-12 <= r['C_end'] <= 1.0+1e-12 for r in rows))

# T6: lower condition -> higher EI (alpha>0): degraded run has > average EI than perfect run
rows0,cs0 = cond_series(C0=1.0, delta=0.0, maintenance_interval=0, rho=0.0, tau=1)   # perfect
rowsD,csD = cond_series(C0=1.0, delta=0.02, maintenance_interval=0, rho=0.0, tau=1)  # degrading
b6_perfect = dynb6(cs0, 0.15, 5e5, 0.5, T, alpha=0.2, g=0.0)
b6_degrade = dynb6(csD, 0.15, 5e5, 0.5, T, alpha=0.2, g=0.0)
check("T6 lower C -> higher EI/B6", b6_degrade['average_EI'] > b6_perfect['average_EI'] and b6_degrade['b6_dynamic_tons'] > b6_perfect['b6_dynamic_tons'])

# T7: full pipeline keeps C bounded
r = run({**base, 'sd_enable':True, 'sd_delta':0.05, 'sd_rho':0.1, 'sd_alpha':0.2})
check("T7 pipeline C bounded", all(0<=row['C_end']<=1 for row in r['sd_rows']))

# T8: renewable share does NOT change core B6 (static or dynamic)
rA = run({**base, 'sd_enable':True, 'renewable_share':0})
rB = run({**base, 'sd_enable':True, 'renewable_share':80})
check("T8 renewable doesn't affect core B6", abs(rA['b6_dynamic_tons']-rB['b6_dynamic_tons'])<1e-6 and abs(rA['b6_static_tons']-rB['b6_static_tons'])<1e-6)

# T9: increasing alpha increases delta_b6 (more penalty)
r_lo = run({**base, 'sd_enable':True, 'sd_delta':0.02, 'sd_rho':0.05, 'sd_alpha':0.1})
r_hi = run({**base, 'sd_enable':True, 'sd_delta':0.02, 'sd_rho':0.05, 'sd_alpha':0.3})
check("T9 higher alpha -> higher deltaB6", r_hi['delta_b6_tons'] > r_lo['delta_b6_tons'])

# T10: stronger maintenance recovery -> better final condition and smaller deltaB6
r_weak = run({**base, 'sd_enable':True, 'sd_delta':0.03, 'sd_rho':0.02, 'sd_alpha':0.2})
r_strong = run({**base, 'sd_enable':True, 'sd_delta':0.03, 'sd_rho':0.15, 'sd_alpha':0.2})
check("T10 stronger maintenance -> better C(T) & smaller deltaB6",
      r_strong['sd_final_condition'] > r_weak['sd_final_condition'] and r_strong['delta_b6_tons'] < r_weak['delta_b6_tons'])

# Consistency: with default-ish params, static B6 from SD == lca lifetime operational (g=0)
r = run({**base, 'sd_enable':True, 'sd_growth_pct':0.0})
lca_static = r['lca_results']['lifetime_operational_co2_tons']
check("Consistency static B6 == lca lifetime operational (g=0)", abs(r['b6_static_tons']-lca_static) < 1.0)

print("\nALL ACCEPTANCE TESTS PASSED" if ok else "\nSOME TESTS FAILED")
sys.exit(0 if ok else 1)
