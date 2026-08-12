"""Full-separation parity: the refactor changed structure, never results.

This is the acceptance gate for the whole tranche. It re-verifies the pinned baseline
and additionally proves that the orchestrator's per-domain view reports exactly the same
numbers as the legacy combined dictionary — i.e. the separation added a boundary, not a
second implementation.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

ok = True


def check(name, cond):
    global ok
    print(("PASS" if cond else "FAIL"), name)
    ok = ok and bool(cond)


# 1) The pinned baseline must still hold, unchanged and un-regenerated.
import architecture_baseline_pin as pin  # noqa: E402

baseline_rc = pin.main()
check("pinned baseline still intact after full separation", baseline_rc == 0)

import json  # noqa: E402
with open(pin.FIXTURE, encoding="utf-8") as fh:
    baseline = json.load(fh)
check("baseline fixture still holds 2615 pinned values", len(baseline) == 2615)
check("baseline tolerance is strict (1e-9)", pin.TOL == 1e-9)

# 2) The orchestrator reports the same numbers as the legacy engine.
from _headless_app import build_ns  # noqa: E402
from assessment_orchestrator import run_assessment, split_params  # noqa: E402

ns = build_ns(publication_mode=False)
engine = ns["calculate_legacy_dashboard_results"]
params = dict(ns["params"])

direct = engine(dict(params))
assembled = run_assessment(dict(params), legacy_engine=engine)

check("orchestrator reproduces the LCC NPV exactly",
      abs(assembled.lcc["npv_lcc_m"] - direct["lcc_results"]["npv_lcc_m"]) < 1e-12)
check("orchestrator reproduces the carbon headline exactly",
      abs(assembled.lca["gross_a1_c4_tons"] - direct["gross_a1_c4_tons"]) < 1e-12)
check("orchestrator reproduces the benefit KPIs exactly",
      assembled.benefits == direct["benefit_kpis"])
check("orchestrator resolves a project context", assembled.context.country == "Egypt")

# 3) The input slices genuinely withhold foreign fields.
slices = split_params(params)
check("LCA slice cannot see the discount rate",
      "discount_rate" not in slices["lca_inputs"])
check("LCA slice cannot see construction cost",
      "construction_cost" not in slices["lca_inputs"])
check("LCA slice cannot see jobs", "jobs_created" not in slices["lca_inputs"])
check("LCC slice can see the discount rate", "discount_rate" in slices["lcc_inputs"])
check("LCC slice cannot see jobs", "jobs_created" not in slices["lcc_inputs"])
check("Benefits slice can see jobs", "jobs_created" in slices["benefits_inputs"])
check("Benefits slice cannot see the discount rate",
      "discount_rate" not in slices["benefits_inputs"])
check("shared slice holds neither cost nor benefit fields",
      "discount_rate" not in slices["shared_inputs"]
      and "jobs_created" not in slices["shared_inputs"])

# 4) The price-base-year adapter accepts the UI spelling.
from project_context import context_from_params  # noqa: E402
check("price_year is honoured when price_base_year is absent",
      context_from_params({"price_year": 2021, "analysis_start_year": 2026}
                          ).price_base_year == 2021)
check("price_base_year still wins when both are present",
      context_from_params({"price_base_year": 2019, "price_year": 2021}
                          ).price_base_year == 2019)
check("analysis_start_year remains the last resort",
      context_from_params({"analysis_start_year": 2030}).price_base_year == 2030)

print("\nFULL SEPARATION PARITY VERIFIED" if ok else "\nFULL SEPARATION PARITY VIOLATED")
sys.exit(0 if ok else 1)
