"""The Publication app renders end-to-end with every control exercised.

The previous Publication app had no such test, which is how it could ship as a
JSON textarea with five raw `st.json` dumps and still be called done. This suite
executes the real application file against a Streamlit stub with EVERY button
pressed, so a form that raises, a missing import or a branch that only runs
after "Run" is clicked all fail here rather than in front of a reviewer.

It also pins the properties that make the app a publication app rather than a
dashboard: real forms instead of a JSON payload, readable tables instead of raw
gate dumps, no legacy engine anywhere, and exports that stay shut while the
gates are open.
"""
import ast
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

APP = os.path.join(ROOT, "apps", "_publication_impl.py")

ok = True


def check(name, cond):
    global ok
    print(("PASS" if cond else "FAIL"), name)
    ok = ok and bool(cond)


def build_stub():
    """A Streamlit stub that says yes to everything.

    Buttons return True so the run branch, the uncertainty branch and the export
    branch all execute in one pass. A stub that returned False would exercise
    only the empty screen, which is the half that already worked.
    """
    st = types.ModuleType("streamlit")

    class _Ctx:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def __getattr__(self, n):
            return lambda *a, **k: _Ctx()

    class _SS(dict):
        def __getattr__(self, k):
            try:
                return self[k]
            except KeyError:
                raise AttributeError(k)

        def __setattr__(self, k, v):
            self[k] = v

    def _noop(*a, **k):
        return None

    st.session_state = _SS()
    st.number_input = lambda l, mn=0, mx=0, value=0, step=1, **k: value
    st.selectbox = lambda l, o, index=0, **k: (o[index] if o else None)
    st.checkbox = lambda l, value=False, **k: value
    st.text_input = lambda l, value="", **k: value
    st.text_area = lambda l, value="", **k: value
    st.data_editor = lambda d, **k: d
    st.file_uploader = lambda *a, **k: None
    st.columns = lambda n, **k: [_Ctx() for _ in range(n if isinstance(n, int) else len(n))]
    st.tabs = lambda labels: [_Ctx() for _ in labels]
    st.expander = lambda *a, **k: _Ctx()
    st.container = lambda *a, **k: _Ctx()
    st.empty = lambda *a, **k: _Ctx()
    st.form = lambda *a, **k: _Ctx()
    st.sidebar = _Ctx()
    st.cache_data = lambda *a, **k: (a[0] if a and callable(a[0]) else (lambda f: f))
    st.rerun = _noop
    st.button = lambda *a, **k: True
    st.download_button = _noop
    for n in ("set_page_config", "markdown", "title", "header", "subheader", "write",
              "info", "warning", "success", "error", "caption", "code", "metric",
              "dataframe", "table", "plotly_chart", "image", "divider", "latex",
              "json", "text", "stop"):
        setattr(st, n, _noop)
    return st


sys.modules["streamlit"] = build_stub()

ns = {"__name__": "__main__"}
src = open(APP, encoding="utf-8").read()
try:
    exec(compile(src, APP, "exec"), ns)
    check("publication app executes with every control exercised", True)
except Exception as exc:  # noqa: BLE001 - the failure IS the finding
    check(f"publication app executes with every control exercised ({type(exc).__name__}: {exc})", False)
    print("\nRESULT: FAIL")
    sys.exit(1)

bundle = ns.get("bundle")
check("pressing Run produces a scientific bundle", bundle is not None)

if bundle is not None:
    gate = bundle.publication_gate
    # With every evidence field empty, nothing may be publication-ready and the
    # app must say so rather than showing a number from somewhere else.
    check("an empty run is not deterministically publication-ready",
          gate.get("deterministic_publication_ready") is False)
    check("an empty run is not full-Q1 ready", gate.get("full_q1_ready") is False)
    check("the gate names its open domains", bool(gate.get("open_domains")))
    check("no legacy fallback is ever allowed", gate.get("legacy_fallback_allowed") is False)

    # The Benefits domain must still RUN on empty input and report explicit
    # states, because a panel that vanishes tells a reviewer less than one that
    # names what is missing.
    check("the Benefits domain runs on empty evidence", bundle.benefits.available)
    if bundle.benefits.available:
        rows = bundle.benefits.result.rows
        check("Benefits reports every KPI with an explicit state", len(rows) >= 20)
        check("no Benefits KPI is publication-eligible without evidence",
              not any(r["publication_eligible"] for r in rows))
        check("blocked topics are reported, not hidden",
              any(r["status"] == "BLOCKED" for r in rows))

    # A domain that cannot compute must explain itself.
    for run, label in ((bundle.lca, "LCA"), (bundle.lcc, "LCC"), (bundle.benefits, "K-Benefits")):
        if not run.available:
            check(f"{label} states why it is blocked", bool(run.error.strip()))

# ---------------------------------------------------------------------------
# The app is a publication app, not a dashboard and not a JSON form
# ---------------------------------------------------------------------------

tree = ast.parse(src)
imports = set()
for node in ast.walk(tree):
    if isinstance(node, ast.ImportFrom) and node.module:
        imports.add(node.module)
    elif isinstance(node, ast.Import):
        imports.update(a.name for a in node.names)

for forbidden in ("monorail_assessment.legacy.lca_engine",
                  "monorail_assessment.legacy.lcc_engine",
                  "monorail_assessment.legacy.benefits_core",
                  "monorail_assessment.legacy.assessment_orchestrator",
                  "monorail_assessment.legacy.uncertainty_orchestrator"):
    check(f"publication app does not import {forbidden.split('.')[-1]}", forbidden not in imports)

check("publication app runs the scientific orchestrator",
      "monorail_assessment.publication.orchestrator" in imports)
check("publication app uses the sourced uncertainty module",
      "monorail_assessment.publication.uncertainty" in imports)

# Real forms, not a JSON payload as the primary path.
check("the app collects evidence through real form fields",
      src.count("st.text_input") >= 25)
check("the app offers the domain tabs a reviewer expects",
      all(t in src for t in ("LCA inputs & evidence", "LCC inputs & evidence",
                             "K-Benefits inputs & evidence", "Uncertainty",
                             "Results", "Audit & references", "Exports")))
check("JSON is demoted to an Advanced import/export control",
      "Advanced — JSON import / export" in src)
check("the JSON payload is no longer the primary input surface",
      "Paste or upload the scientific parameter payload" not in src)

# Gates are rendered as tables, not dumped as raw JSON.
check("gate dictionaries are rendered as readable tables", "def gate_table" in src)
check("no raw st.json dump of a domain gate remains",
      "st.json(bundle.lca.gate)" not in src
      and "st.json(bundle.lcc.gate)" not in src
      and "st.json(bundle.benefits.gate)" not in src)

# Traceability the old publication app did not have.
check("the reference registry is displayed", "BENEFITS_REFERENCES" in src)
check("the equation registry is displayed", "BENEFITS_EQUATIONS" in src)
check("the Benefits source appendix is downloadable",
      "scientific_benefits_source_appendix" in src)

# Exports fail closed.
export_block = src.split("with T_EXPORT:")[1]
check("exports are withheld until the deterministic gate closes",
      "withheld" in export_block and "deterministic_publication_ready" in export_block)
check("export parity is checked before any download is offered",
      export_block.index("deterministic_export_parity_ok")
      < export_block.index("st.download_button"))

# Presentation only: the app must not carry a scientific equation.
for fragment in ("np.linalg", "math.log(", "* emission_factor", "0.5 * generated",
                 "# EQ=BEN-", "/ lifetime_pkm"):
    check(f"app source contains no scientific fragment {fragment!r}", fragment not in src)

print()
print("RESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
