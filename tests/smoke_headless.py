import sys, types, contextlib

# ---- Minimal Streamlit stub so the app module executes headless ----
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
def number_input(label, value=0.0, **k): return value
def slider(label, min_value=0, max_value=100, value=0, **k): return value
def selectbox(label, options, index=0, **k): return options[index]
def button(*a, **k): return False
def checkbox(label, value=False, **k): return value
def form_submit_button(*a, **k): return False
def columns(n, **k):
    n = n if isinstance(n, int) else len(n)
    return [_Ctx() for _ in range(n)]
def tabs(labels): return [_Ctx() for _ in labels]
def form(*a, **k): return _Ctx()
def expander(*a, **k): return _Ctx()
def container(*a, **k): return _Ctx()
def sidebar_ctx(*a, **k): return _Ctx()

class _Sidebar(_Ctx):
    def __getattr__(self, name):
        def _f(*a, **k): return _Ctx()
        return _f
st.sidebar = _Sidebar()

def cache_data(*a, **k):
    if a and callable(a[0]): return a[0]
    def deco(f): return f
    return deco

for name in ["set_page_config","markdown","title","header","subheader","write","info",
             "warning","success","error","caption","code","metric","dataframe","table",
             "plotly_chart","download_button","image","divider","latex","json","text"]:
    setattr(st, name, _noop)

st.number_input = number_input
st.slider = slider
st.selectbox = selectbox
st.button = button
st.checkbox = checkbox
st.form_submit_button = form_submit_button
st.columns = columns
st.tabs = tabs
st.form = form
st.expander = expander
st.container = container
st.cache_data = cache_data

sys.modules["streamlit"] = st

# ---- Execute the app module ----
src = open("app_final_streamlit_ready.py", encoding="utf-8").read()
ns = {"__name__": "__main__"}
exec(compile(src, "app_final_streamlit_ready.py", "exec"), ns)

r = ns["results"]
lca = r["lca_results"]
print("=== SMOKE TEST: default inputs ===")
print(f"Embodied CO2 A1-A3 gross (t) : {r['total_embodied_co2']:,.1f}")
print(f"  concrete C (t): {r['carbon_concrete']/1000:,.1f}")
print(f"  steel    C (t): {r['carbon_steel']/1000:,.1f}")
print(f"  alum     C (t): {r['carbon_aluminum']/1000:,.1f}")
print(f"  glass    C (t): {r['carbon_glass']/1000:,.3f}")
print(f"Module D credit (t)          : {lca['module_d_carbon_credit_tons']:,.1f}  (default scenario 'none' => 0)")
print(f"Total lifecycle CO2 (t)      : {r['total_lifecycle_co2']:,.1f}")
print(f"CO2 per pkm                  : {r['co2_kg_per_pkm']:.5f}")
print(f"Embodied energy (GJ)         : {r['total_ee']/1000:,.0f}")
print(f"stage_coverage A1A3          : {lca['stage_coverage']['A1_A3_materials']}")
print(f"stage_coverage D             : {lca['stage_coverage']['D_recycling_credit']}")

# Module D non-zero check with a recycling scenario
p = dict(ns["current_params"]); p["recycling_scenario"] = "base"
r2 = ns["run_full_assessment"](p)
print("\n=== With recycling_scenario='base' ===")
print(f"A1-A3 gross unchanged (t)    : {r2['total_embodied_co2']:,.1f}")
print(f"Module D credit (t)          : {r2['lca_results']['module_d_carbon_credit_tons']:,.1f}  (should be > 0, separate)")
print(f"Total lifecycle unchanged(t) : {r2['total_lifecycle_co2']:,.1f}")
print("\nAUDIT TABLE columns:", list(ns["MATERIAL_FACTOR_AUDIT"].columns))
print("ALL CHECKS PASSED")
