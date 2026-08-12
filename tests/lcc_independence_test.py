"""LCC runs on its own — no LCA, no Benefits, no Streamlit."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

ok = True


def check(name, cond):
    global ok
    print(("PASS" if cond else "FAIL"), name)
    ok = ok and bool(cond)


for forbidden in ("monorail_assessment.lca.core", "monorail_assessment.lca.integration",
                  "monorail_assessment.legacy.lca_engine", "monorail_assessment.legacy.benefits_core", "streamlit"):
    sys.modules.pop(forbidden, None)

from monorail_assessment.lcc.core import CostRow, ResidualRow, LCCModel, calculate_lcc  # noqa: E402
import monorail_assessment.legacy.lcc_engine as legacy_lcc_engine  # noqa: E402
from monorail_assessment.common.shared_activity import build_shared_activity  # noqa: E402

check("scientific LCC imports with no LCA module loaded",
      "monorail_assessment.lca.core" not in sys.modules and "monorail_assessment.legacy.lca_engine" not in sys.modules)
check("scientific LCC imports with no Benefits module loaded",
      "monorail_assessment.legacy.benefits_core" not in sys.modules)
check("LCC does not pull in Streamlit", "streamlit" not in sys.modules)


def cost(cid, phase, year, amount):
    return CostRow(cid, phase, "test_category", "test_asset", "test_activity", year,
                   2026 + year, 1.0, "lump_sum", amount, "EGP", 2026, 0.0,
                   "golden_fixture.xlsx", f"Costs!{cid}", "Egypt", "PROJECT-SPECIFIC")


model = LCCModel(
    analysis_base_year=2026, analysis_period_years=20, currency="EGP",
    discount_rate=0.0, discount_basis="real",
    discount_source_file="economic_assumptions.xlsx",
    discount_source_location="Rates!B2", discount_evidence_status="PROJECT-SPECIFIC",
    cost_rows=(cost("C", "construction", 0, 100.0), cost("O", "operation", 1, 20.0),
               cost("M", "maintenance_renewal", 5, 30.0), cost("E", "end_of_life", 20, 10.0)),
    residual_rows=(ResidualRow("R", "test_asset", "salvage", 20, 2046, 5.0, "EGP", 2026, 0.0,
                               "golden_fixture.xlsx", "Residual!R", "Egypt",
                               "PROJECT-SPECIFIC"),),
    discount_source_geography="Egypt", analysis_period_source_file="design_brief.pdf",
    analysis_period_source_location="clause 3.2", analysis_period_evidence_status="PROJECT-SPECIFIC",
    analysis_period_geography="Egypt")
r = calculate_lcc(model)
check("LCC computes the golden identity with no LCA present", r["lcc_npv"] == 155.0)
check("LCC result carries no carbon field",
      not any(t in k.lower() for k in r for t in ("co2", "carbon", "gwp")))
check("LCC result carries no benefit field",
      not any(t in k.lower() for k in r for t in ("jobs", "multiplier")))

# The legacy economic engine consumes NEUTRAL activity, never an LCA result.
shared = build_shared_activity(served_annual_pkm=1.0e6, annual_operational_kwh=8.0e6,
                               schedule_rows=[{"year": 10, "B2_count": 1, "B4_count": 1}],
                               use_stage_included=True, end_of_life_included=True)
legacy = legacy_lcc_engine.calculate_legacy_lcc(
    {"construction_cost": 100.0, "maintenance_cost": 2.0, "discount_rate": 5.0,
     "residual_value": 1.0, "eol_cost_m": 3.0}, shared)
check("legacy LCC runs from shared activity alone", legacy["lcc_results"]["npv_lcc_m"] > 0.0)
check("legacy LCC signature takes activity, not an LCA result",
      "shared" in legacy_lcc_engine.calculate_legacy_lcc.__code__.co_varnames)

print("\nLCC INDEPENDENCE VERIFIED" if ok else "\nLCC INDEPENDENCE VIOLATED")
sys.exit(0 if ok else 1)
