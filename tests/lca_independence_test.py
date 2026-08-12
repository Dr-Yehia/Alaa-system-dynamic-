"""LCA runs on its own — no LCC, no Benefits, no Streamlit.

A domain is only independent if it can be imported and exercised in a process where
the other domains were never loaded. This suite proves that directly, rather than
through an exec of the whole application.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

ok = True


def check(name, cond):
    global ok
    print(("PASS" if cond else "FAIL"), name)
    ok = ok and bool(cond)


for forbidden in ("lcc_scientific_core", "legacy_lcc_engine", "benefits_core",
                  "streamlit", "app_final_streamlit_ready"):
    sys.modules.pop(forbidden, None)

from lca_scientific_core import calculate_module_d1, make_project_evidence  # noqa: E402
from lca_scientific_integration import run_scientific_lca_from_app_params  # noqa: E402
import legacy_lca_engine  # noqa: E402

check("scientific LCA imports with no LCC module loaded",
      "lcc_scientific_core" not in sys.modules and "legacy_lcc_engine" not in sys.modules)
check("scientific LCA imports with no Benefits module loaded",
      "benefits_core" not in sys.modules)
check("LCA does not pull in Streamlit", "streamlit" not in sys.modules)

# The engine computes a real result without any economic input whatsoever.
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "golden_full_lca_test.py"), encoding="utf-8").read()
ns = {"__file__": os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "golden_full_lca_test.py")}
exec(src.split("r = run_scientific_lca_from_app_params")[0], ns)
G = dict(ns["G"])
for economic in ("construction_cost", "maintenance_cost", "discount_rate",
                 "residual_value", "jobs_created", "economic_multiplier"):
    G.pop(economic, None)
result = run_scientific_lca_from_app_params(G)
check("LCA computes a full cradle-to-grave result with NO economic inputs present",
      result["gross_A_C_tCO2e"] > 0.0 and result["stage_status"]["C1-C4"] == "connected")
check("LCA result carries no cost field",
      not any("cost" in k.lower() or "npv" in k.lower() for k in result))
check("LCA result carries no benefit field",
      not any(t in k.lower() for k in result for t in ("jobs", "multiplier")))

check("legacy LCA engine exposes the dynamic B6 carbon function",
      hasattr(legacy_lca_engine, "calculate_dynamic_b6"))

print("\nLCA INDEPENDENCE VERIFIED" if ok else "\nLCA INDEPENDENCE VIOLATED")
sys.exit(0 if ok else 1)
