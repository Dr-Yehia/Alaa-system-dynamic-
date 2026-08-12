"""Shared headless harness: execute the Streamlit app against a stub and return its namespace.

Importing this module has NO side effects — unlike the acceptance suites, which run their
checks at import time. It exists so several tools (the architecture baseline pin, future
separation-parity tests) can obtain the app namespace without executing another test file.
"""
import os
import os as _os, sys as _sys
# The app now imports sibling domain modules; these suites exec it from tests/,
# so the repository root must be importable.
_SEP_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _SEP_ROOT not in _sys.path:
    _sys.path.insert(0, _SEP_ROOT)

import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "app_final_streamlit_ready.py")


def build_ns(publication_mode=False):
    """Exec the real app top-to-bottom with Streamlit stubbed; return the module namespace."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    st = types.ModuleType("streamlit")

    class _Ctx:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class _SS(dict):
        def __getattr__(self, k):
            try:
                return self[k]
            except KeyError:
                raise AttributeError(k)

        def __setattr__(self, k, v):
            self[k] = v

    st.session_state = _SS()

    def _noop(*a, **k):
        return None

    st.number_input = lambda l, value=0.0, **k: value
    st.slider = lambda l, mn=0, mx=100, value=0, *a, **k: value
    st.selectbox = lambda l, o, index=0, **k: o[index]
    st.checkbox = lambda l, value=False, **k: (
        publication_mode if k.get("key") == "publication_mode" else value)
    st.button = lambda *a, **k: False
    st.form_submit_button = lambda *a, **k: False
    st.text_input = lambda l, value="", **k: value
    st.data_editor = lambda d, **k: d
    st.file_uploader = lambda *a, **k: None
    st.columns = lambda n, **k: [_Ctx() for _ in range(n if isinstance(n, int) else len(n))]
    st.tabs = lambda labels: [_Ctx() for _ in labels]
    st.cache_data = lambda *a, **k: (a[0] if a and callable(a[0]) else (lambda f: f))
    st.form = lambda *a, **k: _Ctx()
    st.expander = lambda *a, **k: _Ctx()
    st.container = lambda *a, **k: _Ctx()

    class _Sb(_Ctx):
        def __getattr__(self, n):
            return lambda *a, **k: _Ctx()

    st.sidebar = _Sb()
    for n in ["set_page_config", "markdown", "title", "header", "subheader", "write", "info",
              "warning", "success", "error", "caption", "code", "metric", "dataframe", "table",
              "plotly_chart", "download_button", "image", "divider", "latex", "json", "text",
              "stop"]:
        setattr(st, n, _noop)

    sys.modules["streamlit"] = st
    ns = {"__name__": "__main__"}
    exec(compile(open(APP, encoding="utf-8").read(), "app_final_streamlit_ready.py", "exec"), ns)
    return ns
