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

# ── R1/R20: per-material A1-A3 metadata present in the audit table ──
audit_cols = set(ns["MATERIAL_FACTOR_AUDIT"].columns)
check("R1 audit has dqi/source/declared_unit/boundary/status",
      {'dqi_score', 'carbon_source', 'declared_unit', 'boundary', 'status'} <= audit_cols)

print("\nQ1 UPGRADE TESTS PASSED" if ok else "\nQ1 UPGRADE TESTS FAILED")
sys.exit(0 if ok else 1)
