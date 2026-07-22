"""End-to-end: in Publication mode with sources filled, the MAIN report/CSV come from the
scientific engine (not legacy). Execs the real app top-to-bottom against a stub that fills
the scientific provenance so run_scientific_lca_from_app_params() computes."""
import sys, os, types, numpy as np, pandas as pd

# Run from anywhere: put the repo root on sys.path so the app's local imports
# (lca_scientific_*) resolve even when this file is launched as tests/<name>.py.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
_APP = os.path.join(_ROOT, "app_final_streamlit_ready.py")


def build(captured):
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
        key = str(k.get("key", ""))
        if key == "mc_n": return 150
        if key == "si_n": return 30
        if key == "si_unc_n": return 0
        # Scientific provenance numbers.
        if key == "lca_rsp_years": return 50
        if key == "lca_concrete_density": return 2400.0
        if key == "lca_wood_density": return 600.0
        if key == "lca_glass_density": return 2500.0
        if key == "lca_grid_generation": return 0.40
        if key == "lca_grid_td": return 0.03
        if key == "lca_grid_upstream": return 0.05
        return value

    def slider(label, mn=0, mx=100, value=0, *a, **k): return value

    def selectbox(label, options, index=0, **k):
        key = str(k.get("key", ""))
        if key == "grid_mode" or key == "lca_grid_mode":
            return "constant_documented_scenario"
        if key == "lca_ei_basis":
            return "uk_light_rail_weighted_proxy"
        return options[index]

    def checkbox(label, value=False, **k):
        if k.get("key") == "publication_mode": return True
        return False  # keep optional modules off → A1-A3 + A4 + B6 scientific partial

    def button(*a, **k): return True
    def form_submit_button(*a, **k): return True

    def text_input(label, value="", **k):
        key = str(k.get("key", ""))
        # Fill every scientific SOURCE field so A1-A3 / A4 / B6 connect.
        source_like = any(t in key for t in ("source", "location", "route", "ridership",
                                             "boq", "rsp", "grid"))
        if key.startswith("lca_") and source_like:
            return "PROJECT EVIDENCE: file rev A, table 4, p5"
        return value

    def data_editor(data, **k): return data
    def file_uploader(*a, **k): return None
    def columns(n, **k):
        n = n if isinstance(n, int) else len(n)
        return [_Ctx() for _ in range(n)]
    def tabs(labels): return [_Ctx() for _ in labels]
    def code(body, **k): captured["code"].append(str(body))
    def download_button(label, data=None, **k): captured["dl"].append((str(label), str(data)))
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
    exec(compile(open(_APP,encoding="utf-8").read(),
                 "app_final_streamlit_ready.py","exec"), ns)
    return ns


ok = True
def check(name, cond):
    global ok; print(("PASS" if cond else "FAIL"), name); ok = ok and cond

cap = {"code": [], "dl": []}
ns = build(cap)
check("app runs end-to-end in publication with sources filled", True)
check("central scientific_pub computed (not None)", ns.get("scientific_pub") is not None)

report_blob = " ".join(cap["code"])
csv_blob = " ".join(d for _, d in cap["dl"])
check("MAIN report is the SCIENTIFIC engine report",
      "SCIENTIFIC ENGINE (canonical report)" in report_blob)
check("MAIN report shows Module D SEPARATELY", "reported SEPARATELY" in report_blob or "SEPARATELY" in report_blob)
check("MAIN report is NOT the legacy report", "ENHANCED MONORAIL LCA / LCCA ASSESSMENT RESULTS" not in report_blob)
check("no 'Net A1-C4 incl. Module D' headline in publication", "Net A1-C4 incl. Module D" not in report_blob)
check("scientific CSV header present in a download", "Gross A-C (tCO2e)" in csv_blob)

print("\nPUBLICATION SCIENTIFIC E2E PASSED" if ok else "\nFAILED")
sys.exit(0 if ok else 1)
