"""Comprehensive end-to-end UI test: enable every module, 'press' every button,
run the full app top-to-bottom in BOTH Publication and Developer mode, and verify
no exceptions + scientific identities + no dashboard leakage in publication exports."""
import sys, types, numpy as np, pandas as pd
import os as _os, sys as _sys
# The app now imports sibling domain modules; these suites exec it from tests/,
# so the repository root must be importable.
_SEP_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _SEP_ROOT not in _sys.path:
    _sys.path.insert(0, _SEP_ROOT)


def build_app_namespace(publication_mode, captured):
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
    def number_input(label, value=0.0, **k):
        key = k.get('key')
        if key == 'mc_n': return 150
        if key == 'si_n': return 30
        if key == 'si_unc_n': return 0
        return value
    def slider(label, mn=0, mx=100, value=0, *a, **k): return value
    def selectbox(label, options, index=0, **k): return options[index]
    def checkbox(label, value=False, **k):
        if k.get('key') == 'publication_mode': return publication_mode
        return True  # enable every module / engine
    def button(*a, **k): return True  # press every button
    def form_submit_button(*a, **k): return True
    def text_input(label, value="", **k):
        return "25,40" if k.get('key') == 'b4_years' else value
    def data_editor(data, **k): return data
    def file_uploader(*a, **k): return None
    def columns(n, **k):
        n = n if isinstance(n, int) else len(n)
        return [_Ctx() for _ in range(n)]
    def tabs(labels): return [_Ctx() for _ in labels]
    def code(body, **k): captured['code'].append(str(body))
    def download_button(label, data=None, **k): captured['downloads'].append((str(label), str(data)))
    def cache_data(*a, **k):
        if a and callable(a[0]): return a[0]
        def deco(f): return f
        return deco

    class _Sidebar(_Ctx):
        def __getattr__(self, name):
            def _f(*a, **k): return _Ctx()
            return _f
    st.sidebar = _Sidebar()
    for name in ["set_page_config","markdown","title","header","subheader","write","info","warning",
                 "success","error","caption","metric","dataframe","table","plotly_chart","image",
                 "divider","latex","json","text","stop"]:
        setattr(st, name, _noop)
    st.number_input=number_input; st.slider=slider; st.selectbox=selectbox; st.checkbox=checkbox
    st.button=button; st.form_submit_button=form_submit_button; st.text_input=text_input
    st.data_editor=data_editor; st.file_uploader=file_uploader; st.columns=columns; st.tabs=tabs
    st.code=code; st.download_button=download_button; st.cache_data=cache_data
    st.form=lambda *a,**k:_Ctx(); st.expander=lambda *a,**k:_Ctx(); st.container=lambda *a,**k:_Ctx()
    sys.modules["streamlit"]=st
    ns={"__name__":"__main__"}
    exec(compile(open("app_final_streamlit_ready.py",encoding="utf-8").read(),
                 "app_final_streamlit_ready.py","exec"), ns)
    return ns

ok=True
def check(name, cond):
    global ok; print(("PASS" if cond else "FAIL"), name); ok = ok and cond

for pub in (True, False):
    mode = "PUBLICATION" if pub else "DEVELOPER"
    cap={'code':[], 'downloads':[]}
    try:
        ns=build_app_namespace(pub, cap)
        ran=True; err=""
    except Exception as e:
        import traceback; traceback.print_exc(); ran=False; err=str(e)
    check(f"[{mode}] app runs end-to-end (all modules on, all buttons pressed)", ran)
    if not ran: continue
    r=ns['results']
    # identity checks on the live result
    ssum=(r['total_embodied_co2']+r['lca_results']['a4_transport_co2_tons']+r['a5']['a5_total_tons']
          +r['i_b2b5_tons']+r['active_b6_tons']+r['i_c1c4_tons'])
    check(f"[{mode}] gross == Σ stages", abs(ssum-r['gross_a1_c4_tons'])<1e-6)
    check(f"[{mode}] net == gross - Module D", abs(r['net_with_module_d_tons']-(r['gross_a1_c4_tons']-r['module_d_tons']))<1e-6)
    check(f"[{mode}] GWP/pkm uses gross", abs(r['gwp_pkm_gross']-r['gross_a1_c4_tons']*1000/r['active_total_pkm'])<1e-6)
    check(f"[{mode}] modules active (A5/B2B5/C1C4 on)", r['a5']['included'] and r['b2b5']['included'] and r['c1c4']['included'])
    check(f"[{mode}] B4 replacement applied (year 25 in schedule)", any(row['B4_count']==1 and row['year']==25 for row in r['b2b5_schedule']))
    # report + exports captured
    report_txt=" ".join(cap['code'])
    csv_txt=" ".join(d for _,d in cap['downloads'])
    has_report="MONORAIL LCA" in report_txt
    check(f"[{mode}] report generated", has_report)
    if pub:
        check("[PUBLICATION] report has NO dashboard score", "DASHBOARD DISPLAY SCORE" not in report_txt and "Dashboard Display Score" not in report_txt)
        check("[PUBLICATION] exports have NO dashboard score", "Dashboard Display Score" not in csv_txt)
        check("[PUBLICATION] report has NO heuristic category scores", "INTEGRATED SCORING" not in report_txt and "Material Efficiency Score" not in report_txt)
        # P2: report cleanup
        check("[PUBLICATION] report has NO renewable dashboard-only line", "Renewable Share" not in report_txt)
        check("[PUBLICATION] report shows base CAPEX + contract factor + CAPEX in NPV",
              "Base CAPEX" in report_txt and "Contract factor" in report_txt and "CAPEX used in NPV" in report_txt)
        check("[PUBLICATION] report jobs come from Benefit KPI", "Jobs supported (Benefit KPI" in report_txt)
    else:
        check("[DEVELOPER] legacy dashboard appendix present", "LEGACY DASHBOARD" in report_txt)
        check("[DEVELOPER] export includes dashboard score", "Dashboard Display Score" in csv_txt)
        check("[DEVELOPER] report keeps renewable dashboard-only line", "Renewable Share" in report_txt)

print("\nALL COMPREHENSIVE TESTS PASSED" if ok else "\nSOME TESTS FAILED")
sys.exit(0 if ok else 1)
