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

print("\nBENEFITS INDEPENDENCE VERIFIED" if ok else "\nBENEFITS INDEPENDENCE VIOLATED")
sys.exit(0 if ok else 1)
