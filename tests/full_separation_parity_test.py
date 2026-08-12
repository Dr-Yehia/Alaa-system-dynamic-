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

# The combined view is now ASSEMBLED by the orchestrator from three independent domain
# runs. This proves the assembly reproduces exactly what each domain computed, rather
# than the previous weaker test which merely re-ran one combined engine twice.
combined = engine(dict(params))
assembled = run_assessment(dict(params))

check("assembled LCC NPV equals the LCC domain result",
      abs(combined["npv_lcc_m"] - assembled.lcc["lcc_results"]["npv_lcc_m"]) < 1e-12)
check("assembled carbon headline equals the LCA domain result",
      abs(combined["gross_a1_c4_tons"] - assembled.lca["gross_a1_c4_tons"]) < 1e-12)
check("assembled benefit KPIs equal the Benefits domain result",
      combined["benefit_kpis"] == assembled.benefits["kpis"])
check("assembled jobs equal the Benefits domain result",
      combined["total_jobs"] == assembled.benefits["total_jobs"])
check("orchestrator resolves a project context", assembled.context.country == "Egypt")
check("the LCA domain result alone carries no cost",
      "npv_lcc_m" not in assembled.lca and "lcc_results" not in assembled.lca)
check("the LCC domain result alone carries no carbon",
      not any(t in k.lower() for k in assembled.lcc for t in ("co2", "gwp")))

# 3) The input slices genuinely withhold foreign fields.
slices = split_params(params)
check("LCA slice cannot see the discount rate",
      "discount_rate" not in slices["lca_inputs"])
check("LCA slice cannot see construction cost",
      "construction_cost" not in slices["lca_inputs"])
check("LCA slice cannot see jobs", "jobs_created" not in slices["lca_inputs"])
check("LCC slice can see the discount rate", "discount_rate" in slices["lcc_inputs"])
check("LCC slice cannot see jobs", "jobs_created" not in slices["lcc_inputs"])
# The defect the review found: an emission factor must not reach the economic slice.
check("LCC slice CANNOT see carbon_intensity (emission factor)",
      "carbon_intensity" not in slices["lcc_inputs"])
check("LCC slice cannot see material quantities",
      "concrete" not in slices["lcc_inputs"] and "steel" not in slices["lcc_inputs"])
check("Benefits slice can see the real benefit_* fields",
      "benefit_time_saved_min" in slices["benefits_inputs"]
      or "benefit_annual_trips" in slices["benefits_inputs"])
check("Benefits slice can see construction_cost (declared multi-domain)",
      "construction_cost" in slices["benefits_inputs"])
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
