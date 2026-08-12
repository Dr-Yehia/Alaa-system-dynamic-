"""Evidence-awareness tests for the scientific Benefits integration layer.

The core can compute. This layer must decide whether the computed number is
allowed to be a project finding. These tests pin that judgement:

  * a missing numeric source produces SOURCE-OPEN, never a silent zero;
  * a METHOD-REFERENCE cannot certify a project number — it supports the formula;
  * OFFICIAL-PROJECT-DATA passes the data gate;
  * REF-PROXY stays proxy-labelled however complete the rest of the evidence is;
  * monetisation without a currency and a price base year does not compute;
  * the layer consumes a SharedActivity without importing any LCA module;
  * the result carries four separate groups and no combined total.

Fixture numbers are TEST-ONLY software-correctness values, not project evidence.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# Prove the domain boundary by starting from a clean slate: if the integration
# layer pulled in an LCA or LCC module, it would show up in sys.modules below.
for forbidden in (
    "lca_scientific_core",
    "lca_scientific_integration",
    "legacy_lca_engine",
    "lcc_scientific_core",
    "legacy_lcc_engine",
    "assessment_orchestrator",
    "streamlit",
):
    sys.modules.pop(forbidden, None)

from benefits_scientific_integration import (  # noqa: E402
    STATUS_BLOCKED,
    STATUS_COMPUTED,
    STATUS_NOT_APPLICABLE,
    STATUS_OFFICIAL_REPORTED,
    STATUS_PROXY,
    STATUS_SCENARIO_ONLY,
    STATUS_SOURCE_OPEN,
    ScientificBenefitsResult,
    evidence_from_dict,
    run_scientific_benefits_from_params,
)
from shared_activity import build_shared_activity  # noqa: E402
from project_context import ProjectContext  # noqa: E402

ok = True


def check(name, cond):
    global ok
    print(("PASS" if cond else "FAIL"), name)
    ok = ok and bool(cond)


def row_by_id(result, kpi_id):
    for row in result.rows:
        if row["kpi_id"] == kpi_id:
            return row
    return None


# ---------------------------------------------------------------------------
# Domain independence
# ---------------------------------------------------------------------------

check(
    "integration imports no LCA module",
    "lca_scientific_core" not in sys.modules and "legacy_lca_engine" not in sys.modules,
)
check(
    "integration imports no LCC module",
    "lcc_scientific_core" not in sys.modules and "legacy_lcc_engine" not in sys.modules,
)
check("integration pulls in no Streamlit", "streamlit" not in sys.modules)

src = open(os.path.join(ROOT, "benefits_scientific_integration.py"), encoding="utf-8").read()
for forbidden in ("lca_scientific", "lcc_scientific", "legacy_lca", "legacy_lcc", "import streamlit"):
    check(f"integration source does not reference {forbidden!r}", forbidden not in src)

# ---------------------------------------------------------------------------
# Empty input: explicit states, not zeros
# ---------------------------------------------------------------------------

empty = run_scientific_benefits_from_params(params={}, shared_activity=None, project_context=None)
check("empty input still returns a result object", isinstance(empty, ScientificBenefitsResult))
check("empty input is not publication ready", empty.publication_gate["publication_ready"] is False)
check("empty input reports source-open items", bool(empty.publication_gate["source_open_items"]))

pkm_row = row_by_id(empty, "BEN-KPI-PKM")
check("a missing numeric source produces SOURCE-OPEN", pkm_row["status"] == STATUS_SOURCE_OPEN)
check("a missing value is None, never 0", pkm_row["value"] is None)
check("a missing value is not publication eligible", pkm_row["publication_eligible"] is False)
check("the source-open row names its gaps", bool(pkm_row["evidence_gaps"]))

check(
    "no result group contains a combined 'total benefits' figure",
    not any(
        "total_benefit" in str(k).lower()
        for group in (empty.physical, empty.monetized_cba, empty.economic_impact, empty.employment)
        for k in group
    ),
)
check(
    "the result exposes four separate groups",
    all(
        isinstance(g, dict)
        for g in (empty.physical, empty.monetized_cba, empty.economic_impact, empty.employment)
    ),
)

# ---------------------------------------------------------------------------
# Evidence helpers
# ---------------------------------------------------------------------------

check("evidence_from_dict returns None for None", evidence_from_dict(None) is None)
check("evidence_from_dict returns None for a valueless dict", evidence_from_dict({"unit": "km"}) is None)
check("evidence_from_dict refuses a bare number", evidence_from_dict(42.0) is None)
ev = evidence_from_dict({"value": 1.0, "unit": "km", "source_ref_id": "REF-EGY-GB-2022"})
check("evidence_from_dict builds an EvidenceValue", ev is not None and ev.unit == "km")


def project_ev(value, unit, **kw):
    """A complete, project-specific evidence envelope for test purposes."""
    base = dict(
        value=value,
        unit=unit,
        source_ref_id="REF-EGY-GB-2022",
        source_file="project-file.pdf",
        source_location="test fixture, section 1",
        geography="Cairo, Egypt",
        evidence_status="PROJECT-SPECIFIC",
    )
    base.update(kw)
    return base


def method_ev(value, unit, **kw):
    """Evidence whose status is a METHOD reference — supports a formula only."""
    return project_ev(value, unit, evidence_status="METHOD-REFERENCE", **kw)


# ---------------------------------------------------------------------------
# Method evidence cannot certify a project number
# ---------------------------------------------------------------------------

method_only = run_scientific_benefits_from_params(
    params={
        "benefits_scientific_inputs": {
            "transport": {
                "passengers_per_day": method_ev(300_000.0, "passengers/day"),
                "avg_distance_km": method_ev(10.0, "km"),
                "operating_days_per_year": method_ev(350.0, "days/year"),
            }
        }
    },
    shared_activity=None,
    project_context=None,
)
m_row = row_by_id(method_only, "BEN-KPI-PKM")
check("a method-only source still computes a number", m_row["value"] is not None)
check("a method-only source yields SCENARIO-ONLY", m_row["status"] == STATUS_SCENARIO_ONLY)
check(
    "a method-only source is NOT publication eligible",
    m_row["publication_eligible"] is False,
)
check(
    "the gate warns that a scenario value cannot carry a headline",
    any("BEN-KPI-PKM" in w for w in method_only.publication_gate["warnings"]),
)

# ---------------------------------------------------------------------------
# Project-specific evidence passes; the chain propagates its weakest link
# ---------------------------------------------------------------------------

full_transport = {
    "passengers_per_day": project_ev(300_000.0, "passengers/day"),
    "avg_distance_km": project_ev(10.0, "km"),
    "operating_days_per_year": project_ev(350.0, "days/year"),
    "modal_shift_fraction": project_ev(0.3, "fraction"),
    "car_share_of_shift": project_ev(0.6, "fraction"),
    "bus_share_of_shift": project_ev(0.4, "fraction"),
    "car_emission_factor": project_ev(0.15, "kgCO2e/pkm", factor_basis="already CO2e"),
    "bus_emission_factor": project_ev(0.05, "kgCO2e/pkm", factor_basis="already CO2e"),
    "project_emission_factor": project_ev(0.02, "kgCO2e/pkm", factor_basis="already CO2e"),
    "annual_trips": project_ev(100_000_000.0, "trips/year"),
    "baseline_time_min": project_ev(45.0, "min"),
    "project_time_min": project_ev(25.0, "min"),
    "generated_trips": project_ev(5_000_000.0, "trips/year"),
    "value_of_time": project_ev(
        20.0, "EGP/hour", currency="EGP", price_base_year=2026,
        source_ref_id="REF-EGY-VOT-2022",
    ),
}

good = run_scientific_benefits_from_params(
    params={"benefits_scientific_inputs": {"transport": full_transport}},
    shared_activity=None,
    project_context=ProjectContext(),
)

g_pkm = row_by_id(good, "BEN-KPI-PKM")
check("project-specific evidence computes", g_pkm["status"] == STATUS_COMPUTED)
check("project-specific evidence is publication eligible", g_pkm["publication_eligible"] is True)
check("annual pkm arithmetic", abs(good.physical["annual_passenger_km"] - 1.05e9) < 1e-6)

check("shifted pkm computed", row_by_id(good, "BEN-KPI-MODAL")["status"] == STATUS_COMPUTED)
check(
    "avoided emissions computed and signed",
    row_by_id(good, "BEN-KPI-GHG-AVOIDED")["status"] == STATUS_COMPUTED
    and good.physical["avoided_co2e_t"] is not None,
)
check(
    "avoided emissions carry an explicit direction",
    good.physical["avoided_benefit_direction"] in {"benefit", "disbenefit", "neutral"},
)

# Passenger-hours: 100e6 trips x (45-25)/60 h = 33,333,333.33 h
check(
    "passenger-hours saved arithmetic",
    abs(good.physical["passenger_hours_saved"] - 100_000_000.0 * (20.0 / 60.0)) < 1e-3,
)
check(
    "time monetisation computed with currency and price year",
    row_by_id(good, "BEN-KPI-TIME-VALUE")["status"] == STATUS_COMPUTED
    and good.monetized_cba["currency"] == "EGP"
    and good.monetized_cba["price_base_year"] == 2026,
)

# The Rule of Half must reach generated traffic ONLY.
gen_value = good.monetized_cba["generated_traffic_value"]
expected_gen = 0.5 * 5_000_000.0 * (20.0 / 60.0) * 20.0
check("generated-traffic benefit uses the Rule of Half", abs(gen_value - expected_gen) < 1e-6)
check(
    "existing-passenger benefit is NOT halved",
    abs(good.monetized_cba["time_saving_value"] - 100_000_000.0 * (20.0 / 60.0) * 20.0) < 1e-3,
)

# Weakest-link propagation: downgrade one upstream input and the derived KPI
# must not claim stronger evidence than its own input.
mixed_transport = dict(full_transport)
mixed_transport["modal_shift_fraction"] = method_ev(0.3, "fraction")
mixed = run_scientific_benefits_from_params(
    params={"benefits_scientific_inputs": {"transport": mixed_transport}},
    shared_activity=None,
    project_context=None,
)
check(
    "a scenario modal-shift downgrades the shifted-pkm KPI",
    row_by_id(mixed, "BEN-KPI-MODAL")["status"] == STATUS_SCENARIO_ONLY,
)
check(
    "the downgrade propagates to avoided emissions",
    row_by_id(mixed, "BEN-KPI-GHG-AVOIDED")["status"] == STATUS_SCENARIO_ONLY,
)

# ---------------------------------------------------------------------------
# Monetisation requires currency and price base year
# ---------------------------------------------------------------------------

no_currency = dict(full_transport)
no_currency["value_of_time"] = project_ev(20.0, "EGP/hour", source_ref_id="REF-EGY-VOT-2022")
unpriced = run_scientific_benefits_from_params(
    params={"benefits_scientific_inputs": {"transport": no_currency}},
    shared_activity=None,
    project_context=None,
)
v_row = row_by_id(unpriced, "BEN-KPI-TIME-VALUE")
check("VOT without currency/price year does not monetise", v_row["status"] == STATUS_SOURCE_OPEN)
check("unmonetised time value is None", v_row["value"] is None)
check(
    "the gap names currency and price base year",
    "currency" in v_row["evidence_gaps"] and "price base year" in v_row["evidence_gaps"],
)
check(
    "the physical time saving is unaffected by the monetisation gap",
    row_by_id(unpriced, "BEN-KPI-TIME-SAVED")["status"] == STATUS_COMPUTED,
)

# ---------------------------------------------------------------------------
# SharedActivity is consumed without importing LCA
# ---------------------------------------------------------------------------

shared = build_shared_activity(served_annual_pkm=8.5e8, lifetime_pkm=4.25e10)
from_shared = run_scientific_benefits_from_params(
    params={}, shared_activity=shared, project_context=ProjectContext()
)
s_row = row_by_id(from_shared, "BEN-KPI-PKM")
check("SharedActivity passenger-km is used when no evidence is supplied", s_row["value"] == 8.5e8)
check(
    "SharedActivity-derived activity is NOT publication eligible",
    s_row["publication_eligible"] is False and s_row["status"] == STATUS_SCENARIO_ONLY,
)
check(
    "the audit exposes that the value came from the neutral activity layer",
    "SharedActivity" in s_row["note"],
)
check(
    "the audit records the shared activity value it consumed",
    from_shared.audit["shared_activity_annual_pkm"] == 8.5e8,
)
check(
    "consuming SharedActivity still loads no LCA module",
    "lca_scientific_core" not in sys.modules and "legacy_lca_engine" not in sys.modules,
)

# ---------------------------------------------------------------------------
# Employment: official data vs proxy benchmark
# ---------------------------------------------------------------------------

jobs = run_scientific_benefits_from_params(
    params={
        "benefits_scientific_inputs": {
            "employment": {
                "official_construction_jobs": project_ev(
                    4000.0, "jobs", evidence_status="OFFICIAL-PROJECT-DATA"
                ),
                "official_operational_jobs": project_ev(
                    450.0, "jobs", evidence_status="OFFICIAL-PROJECT-DATA"
                ),
                "proxy_investment_constant_2015_usd_m": project_ev(
                    500.0, "million constant 2015 USD",
                    evidence_status="REF-PROXY", source_ref_id="REF-MOSZORO-2024",
                ),
                "jobs_per_musd_proxy": project_ev(
                    13.0, "jobs per US$1m",
                    evidence_status="REF-PROXY", source_ref_id="REF-MOSZORO-2024",
                ),
            }
        }
    },
    shared_activity=None,
    project_context=None,
)

check(
    "official project data passes the data gate",
    row_by_id(jobs, "BEN-KPI-JOBS-OFFICIAL-CONSTRUCTION")["status"] == STATUS_OFFICIAL_REPORTED,
)
check(
    "official reported jobs are publication eligible",
    row_by_id(jobs, "BEN-KPI-JOBS-OFFICIAL-CONSTRUCTION")["publication_eligible"] is True,
)
check(
    "official jobs carry no equation id (they are reported, not computed)",
    row_by_id(jobs, "BEN-KPI-JOBS-OFFICIAL-OPERATIONAL")["equation_id"] == "",
)

proxy_row = row_by_id(jobs, "BEN-KPI-JOBS-PROXY")
check("proxy jobs compute", proxy_row["value"] == 6500.0)
check("REF-PROXY stays proxy-labelled", proxy_row["status"] == STATUS_PROXY)
check("proxy jobs are not publication eligible", proxy_row["publication_eligible"] is False)
check(
    "the proxy label never says 'Cairo jobs created'",
    "created" not in jobs.employment["proxy_jobs_label"].lower(),
)
check(
    "official and proxy jobs are never summed",
    not any("total" in k.lower() for k in jobs.employment if k != "no_total_reason"),
)
check(
    "the employment group states why there is no total",
    bool(jobs.employment["no_total_reason"]),
)

# ---------------------------------------------------------------------------
# Blocked topics appear as blocked, not as missing
# ---------------------------------------------------------------------------

blocked_rows = [r for r in empty.rows if r["status"] == STATUS_BLOCKED]
check("blocked topics are reported", len(blocked_rows) == 3)
check("every blocked row explains what would close it", all(len(r["note"]) > 40 for r in blocked_rows))
check(
    "the gate lists blocked items separately from source-open ones",
    len(empty.publication_gate["blocked_items"]) == 3,
)
check(
    "no blocked topic is publication eligible",
    not any(r["publication_eligible"] for r in blocked_rows),
)

# ---------------------------------------------------------------------------
# Noise
# ---------------------------------------------------------------------------

no_noise_row = row_by_id(empty, "BEN-KPI-NOISE-PHYS")
check("absent acoustic study is NOT-APPLICABLE, not zero", no_noise_row["status"] == STATUS_NOT_APPLICABLE)

noise = run_scientific_benefits_from_params(
    params={
        "benefits_scientific_inputs": {
            "noise": {
                "rows": [
                    {
                        "receptor_id": "R1",
                        "metric": "Lden",
                        "assessment_period": "annual",
                        "baseline_db": project_ev(68.0, "dB"),
                        "project_db": project_ev(63.0, "dB"),
                    }
                ]
            }
        }
    },
    shared_activity=None,
    project_context=None,
)
check("receptor noise delta computed", noise.physical["noise"]["receptors"][0]["noise_delta_db"] == 5.0)
check(
    "the noise group carries no aggregate dB and no percentage",
    not any(k in noise.physical["noise"] for k in ("mean_db", "total_db", "reduction_pct")),
)
check(
    "the noise group states the aggregation rule",
    "not averaged" in noise.physical["noise"]["aggregation_note"],
)

# ---------------------------------------------------------------------------
# Audit completeness
# ---------------------------------------------------------------------------

for row in good.rows:
    if row["publication_eligible"]:
        check(
            f"{row['kpi_id']}: an eligible row resolves to a method source",
            bool(row["method_ref_ids"]) or row["equation_id"] == "",
        )
        check(
            f"{row['kpi_id']}: an eligible row names its numeric source",
            bool(row["numeric_source_ref_ids"]),
        )
        check(f"{row['kpi_id']}: an eligible row states a unit", bool(row["unit"]))

check("audit records the double-count rules", len(good.audit["double_count_rules"]) == 4)
check("audit counts KPI states", bool(good.audit["status_counts"]))
check(
    "no KPI row reduces an LCC or LCA total",
    not any(k in str(good.physical) + str(good.monetized_cba) for k in ("npv_lcc", "gross_a1_c4")),
)

print()
print("RESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
