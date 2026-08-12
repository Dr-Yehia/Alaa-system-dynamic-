"""Benefits run on their own, and can never reduce a cost or an emission."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

ok = True


def check(name, cond):
    global ok
    print(("PASS" if cond else "FAIL"), name)
    ok = ok and bool(cond)


for forbidden in ("lca_scientific_core", "lca_scientific_integration", "legacy_lca_engine",
                  "lcc_scientific_core", "legacy_lcc_engine", "streamlit"):
    sys.modules.pop(forbidden, None)

import benefits_core  # noqa: E402

check("Benefits import with no LCA module loaded",
      "lca_scientific_core" not in sys.modules and "legacy_lca_engine" not in sys.modules)
check("Benefits import with no LCC module loaded",
      "lcc_scientific_core" not in sys.modules and "legacy_lcc_engine" not in sys.modules)
check("Benefits do not pull in Streamlit", "streamlit" not in sys.modules)

kpis = benefits_core.calculate_benefit_kpis(
    {"benefit_baseline_ci_pkm": 0.12, "energy_per_pax": 0.05, "carbon_intensity": 0.4},
    annual_pkm=1.0e8)
check("Benefit KPIs compute standalone", isinstance(kpis, dict) and kpis)
check("Benefit result carries no NPV/cost field",
      not any(t in k.lower() for k in kpis for t in ("npv", "lcc")))

jobs = benefits_core.calculate_legacy_jobs({"jobs_created": 100.0, "economic_multiplier": 2.5})
check("jobs are a benefit, computed outside the LCC domain", jobs["total_jobs"] == 250.0)

# Structural: the avoided-CO2 KPI is a REPORTED comparison, never a deduction. It must
# not be capable of reaching the LCA gross total, which is why no LCA import exists.
src = open(os.path.join(ROOT, "benefits_core.py"), encoding="utf-8").read()
check("benefits_core imports no LCA/LCC engine",
      "lca_scientific" not in src and "lcc_scientific" not in src
      and "legacy_lca" not in src and "legacy_lcc" not in src)


# ── The SCIENTIFIC Benefits modules obey the same boundary ──────────────────
# The legacy module was already independent. The referenced modules must be too,
# or the new Publication path would reintroduce the coupling the separation removed.
for forbidden in ("lca_scientific_core", "lca_scientific_integration", "legacy_lca_engine",
                  "lcc_scientific_core", "legacy_lcc_engine", "streamlit"):
    sys.modules.pop(forbidden, None)

import benefits_reference_registry  # noqa: E402
import benefits_scientific_core  # noqa: E402
import benefits_scientific_integration  # noqa: E402

check("scientific Benefits import with no LCA module loaded",
      "lca_scientific_core" not in sys.modules and "legacy_lca_engine" not in sys.modules)
check("scientific Benefits import with no LCC module loaded",
      "lcc_scientific_core" not in sys.modules and "legacy_lcc_engine" not in sys.modules)
check("scientific Benefits do not pull in Streamlit", "streamlit" not in sys.modules)

for module_name in ("benefits_reference_registry", "benefits_scientific_core",
                    "benefits_scientific_integration"):
    module_src = open(os.path.join(ROOT, f"{module_name}.py"), encoding="utf-8").read()
    check(f"{module_name} imports no LCA engine",
          "lca_scientific" not in module_src and "legacy_lca" not in module_src)
    check(f"{module_name} imports no LCC engine",
          "lcc_scientific" not in module_src and "legacy_lcc" not in module_src)
    check(f"{module_name} imports no Streamlit", "import streamlit" not in module_src)

result = benefits_scientific_integration.run_scientific_benefits_from_params(
    params={}, shared_activity=None, project_context=None)
check("scientific Benefits compute standalone", bool(result.rows))

# A Benefits result may never carry a cost or a carbon TOTAL. It reports its own
# avoided emissions as a separate physical quantity and touches neither total.
serialised = (str(result.physical) + str(result.monetized_cba)
              + str(result.economic_impact) + str(result.employment)).lower()
check("scientific Benefits produce no npv_lcc output", "npv_lcc" not in serialised)
check("scientific Benefits produce no gross_a1_c4 field", "gross_a1_c4" not in serialised)
check("scientific Benefits produce no module-D field", "module_d" not in serialised)
check("scientific Benefits expose no combined total",
      "total_benefit" not in serialised)

# Structural: nothing in the Benefits domain can mutate an LCA or LCC result,
# because it never receives one. The only inputs are params, the neutral activity
# record and the project context.
import inspect  # noqa: E402
sig = inspect.signature(benefits_scientific_integration.run_scientific_benefits_from_params)
check("scientific Benefits receive only params, shared activity and context",
      set(sig.parameters) == {"params", "shared_activity", "project_context"})

print("\nBENEFITS INDEPENDENCE VERIFIED" if ok else "\nBENEFITS INDEPENDENCE VIOLATED")
sys.exit(0 if ok else 1)
