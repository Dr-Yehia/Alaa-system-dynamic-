"""What Publication mode must refuse to present as a project finding.

Every case below is a number that a careless implementation would happily
display. The gate exists to stop each one:

  * a 30% modal shift taken from the green bond report's own scenario;
  * a car/bus split with no travel survey behind it;
  * an emission factor with no documented source, year or geography;
  * a value of time carried into a later appraisal year with no index;
  * 2016-2017 Egyptian input-output multipliers dressed as current project truth;
  * a monetary noise benefit with no exposure or valuation evidence;
  * a formalization benefit, for which no defensible formula exists;
  * officially reported jobs added to benchmark proxy jobs;
  * gross economic output folded into a welfare benefit total.

Fixture numbers are TEST-ONLY software-correctness values, not project evidence.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from benefits_reference_registry import BLOCKED_TOPICS, EQUATIONS  # noqa: E402
from benefits_scientific_integration import (  # noqa: E402
    PUBLICATION_ELIGIBLE_STATES,
    STATUS_BLOCKED,
    STATUS_COMPUTED,
    STATUS_PROXY,
    STATUS_SCENARIO_ONLY,
    STATUS_SOURCE_OPEN,
    run_scientific_benefits_from_params,
)

ok = True


def check(name, cond):
    global ok
    print(("PASS" if cond else "FAIL"), name)
    ok = ok and bool(cond)


def run(inputs, **kw):
    return run_scientific_benefits_from_params(
        params={"benefits_scientific_inputs": inputs},
        shared_activity=kw.get("shared_activity"),
        project_context=kw.get("project_context"),
    )


def row_by_id(result, kpi_id):
    for row in result.rows:
        if row["kpi_id"] == kpi_id:
            return row
    return None


def ev(value, unit, status="PROJECT-SPECIFIC", **kw):
    base = dict(
        value=value,
        unit=unit,
        source_ref_id=kw.pop("source_ref_id", "REF-EGY-GB-2022"),
        source_file=kw.pop("source_file", "project-file.pdf"),
        source_location=kw.pop("source_location", "test fixture"),
        geography=kw.pop("geography", "Cairo, Egypt"),
        evidence_status=status,
    )
    base.update(kw)
    return base


def bare(value, unit):
    """A value with no source, no location and no geography — the common failure."""
    return {"value": value, "unit": unit}


ACTIVITY = {
    "passengers_per_day": ev(300_000.0, "passengers/day"),
    "avg_distance_km": ev(10.0, "km"),
    "operating_days_per_year": ev(350.0, "days/year"),
}

# ---------------------------------------------------------------------------
# 1. A 30% modal shift with no Cairo evidence
# ---------------------------------------------------------------------------

# The green bond report discusses a 30% car/bus-to-rail switching scenario. That
# is the report's assumption for its own accounting, not a measured Cairo
# fraction, so it must not carry a project headline.
scenario_shift = run(
    {
        "transport": dict(
            ACTIVITY,
            modal_shift_fraction=ev(
                0.30, "fraction", status="METHOD-REFERENCE",
                source_location="Annex 1, 20-50% modal-shift scenario discussion",
            ),
        )
    }
)
r = row_by_id(scenario_shift, "BEN-KPI-MODAL")
check("a report-scenario modal shift is not publication eligible", r["publication_eligible"] is False)
check("a report-scenario modal shift is labelled SCENARIO-ONLY", r["status"] == STATUS_SCENARIO_ONLY)

bare_shift = run({"transport": dict(ACTIVITY, modal_shift_fraction=bare(0.30, "fraction"))})
r = row_by_id(bare_shift, "BEN-KPI-MODAL")
check("an unsourced modal shift does not compute at all", r["value"] is None)
check("an unsourced modal shift is SOURCE-OPEN", r["status"] == STATUS_SOURCE_OPEN)
check("the gate lists the unsourced modal shift", any("BEN-KPI-MODAL" in s for s in bare_shift.publication_gate["source_open_items"]))

# ---------------------------------------------------------------------------
# 2. Car/bus split with no travel survey
# ---------------------------------------------------------------------------

split_unsourced = run(
    {
        "transport": dict(
            ACTIVITY,
            modal_shift_fraction=ev(0.30, "fraction"),
            car_share_of_shift=bare(0.6, "fraction"),
            bus_share_of_shift=bare(0.4, "fraction"),
        )
    }
)
r = row_by_id(split_unsourced, "BEN-KPI-MODE-SPLIT")
check("an unsourced car/bus split does not compute", r["value"] is None)
check("an unsourced car/bus split is SOURCE-OPEN", r["status"] == STATUS_SOURCE_OPEN)

# A split that does not close to 1 is a bookkeeping error, not a scenario.
split_broken = run(
    {
        "transport": dict(
            ACTIVITY,
            modal_shift_fraction=ev(0.30, "fraction"),
            car_share_of_shift=ev(0.6, "fraction"),
            bus_share_of_shift=ev(0.5, "fraction"),
        )
    }
)
r = row_by_id(split_broken, "BEN-KPI-MODE-SPLIT")
check("a split that does not sum to 1 is rejected, not rescaled", r["value"] is None)
check("the rejection reason is reported", "must equal 1" in r["note"])

# ---------------------------------------------------------------------------
# 3. Unsourced emission factors
# ---------------------------------------------------------------------------

ef_unsourced = run(
    {
        "transport": dict(
            ACTIVITY,
            modal_shift_fraction=ev(0.30, "fraction"),
            car_share_of_shift=ev(0.6, "fraction"),
            bus_share_of_shift=ev(0.4, "fraction"),
            car_emission_factor=bare(0.15, "kgCO2e/pkm"),
            bus_emission_factor=bare(0.05, "kgCO2e/pkm"),
            project_emission_factor=bare(0.02, "kgCO2e/pkm"),
        )
    }
)
r = row_by_id(ef_unsourced, "BEN-KPI-GHG-AVOIDED")
check("unsourced emission factors produce no avoided-emissions figure", r["value"] is None)
check("unsourced emission factors are SOURCE-OPEN", r["status"] == STATUS_SOURCE_OPEN)

# A UK factor is a method demonstration, not an Egyptian project factor.
ef_uk = run(
    {
        "transport": dict(
            ACTIVITY,
            modal_shift_fraction=ev(0.30, "fraction"),
            car_share_of_shift=ev(0.6, "fraction"),
            bus_share_of_shift=ev(0.4, "fraction"),
            car_emission_factor=ev(
                0.15, "kgCO2e/pkm", status="METHOD-REFERENCE",
                source_ref_id="REF-TRD-MODAL-2024", geography="United Kingdom",
            ),
            bus_emission_factor=ev(
                0.05, "kgCO2e/pkm", status="METHOD-REFERENCE",
                source_ref_id="REF-TRD-MODAL-2024", geography="United Kingdom",
            ),
            project_emission_factor=ev(
                0.02, "kgCO2e/pkm", status="METHOD-REFERENCE",
                source_ref_id="REF-TRD-MODAL-2024", geography="United Kingdom",
            ),
        )
    }
)
r = row_by_id(ef_uk, "BEN-KPI-GHG-AVOIDED")
check("a foreign method factor cannot certify a project emission figure", r["publication_eligible"] is False)
check("a foreign method factor yields SCENARIO-ONLY", r["status"] == STATUS_SCENARIO_ONLY)

# ---------------------------------------------------------------------------
# 4. Value of time carried forward without a documented escalation
# ---------------------------------------------------------------------------

TIME_INPUTS = {
    "annual_trips": ev(100_000_000.0, "trips/year"),
    "baseline_time_min": ev(45.0, "min"),
    "project_time_min": ev(25.0, "min"),
}

vot_no_basis = run({"transport": dict(ACTIVITY, **TIME_INPUTS, value_of_time=bare(24.5, "EGP/hour"))})
r = row_by_id(vot_no_basis, "BEN-KPI-TIME-VALUE")
check("a VOT with no currency or price year does not monetise", r["value"] is None)
check("the missing monetary basis is named", "currency" in r["evidence_gaps"])

# The study's own 2022 figure, correctly labelled, supports the METHOD but is
# not a project appraisal value for a later price year.
vot_study = run(
    {
        "transport": dict(
            ACTIVITY,
            **TIME_INPUTS,
            value_of_time=ev(
                18.3, "EGP/hour", status="METHOD-REFERENCE",
                source_ref_id="REF-EGY-VOT-2022", geography="Egypt",
                currency="EGP", price_base_year=2022,
            ),
        )
    }
)
r = row_by_id(vot_study, "BEN-KPI-TIME-VALUE")
check("a study VOT computes but is not publication eligible", r["value"] is not None and r["publication_eligible"] is False)
check("a study VOT is SCENARIO-ONLY", r["status"] == STATUS_SCENARIO_ONLY)
check("the monetised row records the price base year it used", r["price_base_year"] == 2022)
check(
    "the gate does not mark monetised time as ready on a method-only VOT",
    vot_study.publication_gate["monetized_time_ready"] is False,
)

# ---------------------------------------------------------------------------
# 5. Historical input-output multipliers presented as current project truth
# ---------------------------------------------------------------------------

io_historical = run(
    {
        "input_output": {
            "A_matrix": ev(
                [[0.2, 0.1], [0.3, 0.4]], "coefficient matrix", status="HISTORICAL",
                source_ref_id="REF-EGY-IO-ALAYOUTY-2022", geography="Egypt",
                source_location="methodology pp.11-12, Egypt 2016-2017 I-O table",
            ),
            "final_demand_change": ev(
                [1000.0, 0.0], "million EGP", status="HISTORICAL",
                source_ref_id="REF-EGY-IO-ALAYOUTY-2022", geography="Egypt",
            ),
            "sector_labels": ["construction", "services"],
        }
    }
)
r = row_by_id(io_historical, "BEN-KPI-IO-OUTPUT")
check("historical I-O data still computes an output response", r["value"] is not None)
check("historical I-O data is not publication eligible", r["publication_eligible"] is False)
check("historical I-O data is labelled SCENARIO-ONLY", r["status"] == STATUS_SCENARIO_ONLY)
check(
    "the economic-impact group states that output is not a welfare benefit",
    "NOT a welfare benefit" in io_historical.economic_impact["basis_note"],
)
check(
    "the economic-impact gate is not ready on historical multipliers",
    io_historical.publication_gate["economic_impact_ready"] is False,
)

# ---------------------------------------------------------------------------
# 6. Monetary noise, formalization and carbon money stay blocked
# ---------------------------------------------------------------------------

result = run({})
blocked = {r["kpi_id"]: r for r in result.rows if r["status"] == STATUS_BLOCKED}

check("noise monetisation is blocked", "BEN-NOISE-MONEY" in blocked)
check("carbon monetisation is blocked", "BEN-CARBON-MONEY" in blocked)
check("formalization is blocked", "BEN-FORMALIZATION" in blocked)
check("no blocked topic is publication eligible", not any(r["publication_eligible"] for r in blocked.values()))
check("no blocked topic carries a value", all(r["value"] is None for r in blocked.values()))
check(
    "each blocked topic names the evidence that would close it",
    all(len(BLOCKED_TOPICS[k]) > 40 for k in blocked),
)
check("no formalization equation is registered", not any("FORMALIZ" in k for k in EQUATIONS))
check(
    "no monetisation equation exists for carbon or noise",
    not any(
        "MONEY" in k and ("CARBON" in k or "NOISE" in k) for k in EQUATIONS
    ),
)

# Supplying receptor levels yields a physical dB result only — never money.
noise_result = run(
    {
        "noise": {
            "rows": [
                {
                    "receptor_id": "R1",
                    "metric": "Lden",
                    "assessment_period": "annual",
                    "baseline_db": ev(68.0, "dB"),
                    "project_db": ev(63.0, "dB"),
                }
            ]
        }
    }
)
noise_rows = [r for r in noise_result.rows if r["equation_id"] == "BEN-NOISE-PHYS-01"]
check("a computed noise result stays in dB", all(r["unit"].startswith("dB") for r in noise_rows))
check(
    "no noise row is expressed as a currency",
    not any(r["result_group"] == "monetized_cba" for r in noise_rows),
)
check(
    "noise monetisation remains blocked even with receptor data present",
    any(r["kpi_id"] == "BEN-NOISE-MONEY" and r["status"] == STATUS_BLOCKED for r in noise_result.rows),
)

# ---------------------------------------------------------------------------
# 7. Official jobs and proxy jobs are never added
# ---------------------------------------------------------------------------

jobs = run(
    {
        "employment": {
            "official_construction_jobs": ev(4000.0, "jobs", status="OFFICIAL-PROJECT-DATA"),
            "official_operational_jobs": ev(450.0, "jobs", status="OFFICIAL-PROJECT-DATA"),
            "proxy_investment_constant_2015_usd_m": ev(
                500.0, "million constant 2015 USD", status="REF-PROXY",
                source_ref_id="REF-MOSZORO-2024",
            ),
            "jobs_per_musd_proxy": ev(
                13.0, "jobs per US$1m", status="REF-PROXY", source_ref_id="REF-MOSZORO-2024",
            ),
        }
    }
)

official_total = 4000.0 + 450.0
proxy_total = 6500.0
forbidden_sum = official_total + proxy_total

employment_values = [v for v in jobs.employment.values() if isinstance(v, (int, float))]
check(
    "the employment group contains no official+proxy sum",
    forbidden_sum not in employment_values,
)
check(
    "no KPI row carries the forbidden official+proxy sum",
    not any(r["value"] == forbidden_sum for r in jobs.rows),
)
check(
    "official and proxy jobs remain separately addressable",
    jobs.employment["official_reported_construction_jobs"] == 4000.0
    and jobs.employment["proxy_jobs_supported"] == 6500.0,
)
check(
    "the proxy row is never publication eligible alongside official data",
    row_by_id(jobs, "BEN-KPI-JOBS-PROXY")["status"] == STATUS_PROXY
    and row_by_id(jobs, "BEN-KPI-JOBS-PROXY")["publication_eligible"] is False,
)

# ---------------------------------------------------------------------------
# 8. Economic output never enters a welfare benefit total
# ---------------------------------------------------------------------------

combined = run(
    {
        "transport": dict(
            ACTIVITY,
            **TIME_INPUTS,
            value_of_time=ev(
                20.0, "EGP/hour", source_ref_id="REF-EGY-VOT-2022",
                currency="EGP", price_base_year=2026,
            ),
        ),
        "input_output": {
            "A_matrix": ev([[0.2, 0.1], [0.3, 0.4]], "coefficient matrix"),
            "final_demand_change": ev([1000.0, 0.0], "million EGP"),
            "sector_labels": ["construction", "services"],
        },
    }
)

time_value = combined.monetized_cba["time_saving_value"]
output_value = combined.economic_impact["total_output_response"]
check("both a monetised benefit and an output response exist", time_value and output_value)
check(
    "the CBA group contains no economic output figure",
    output_value not in [v for v in combined.monetized_cba.values() if isinstance(v, (int, float))],
)
check(
    "no row carries the sum of monetised time and economic output",
    not any(
        isinstance(r["value"], (int, float)) and abs(r["value"] - (time_value + output_value)) < 1e-6
        for r in combined.rows
    ),
)
check(
    "the groups stay separate: output is in economic_impact, money is in monetized_cba",
    row_by_id(combined, "BEN-KPI-IO-OUTPUT")["result_group"] == "economic_impact"
    and row_by_id(combined, "BEN-KPI-TIME-VALUE")["result_group"] == "monetized_cba",
)
check(
    "the audit states the no-adding rule explicitly",
    any("never added to" in rule for rule in combined.audit["double_count_rules"]),
)

# ---------------------------------------------------------------------------
# 9. Benefits never touch LCA or LCC totals
# ---------------------------------------------------------------------------

serialised = str(combined.physical) + str(combined.monetized_cba) + str(combined.economic_impact) + str(combined.employment)
for forbidden in ("npv_lcc", "gross_a1_c4", "total_cost", "module_d"):
    check(f"no Benefits field is named {forbidden!r}", forbidden not in serialised.lower())

check(
    "the audit records that Benefits never reduce LCC NPV",
    any("LCC NPV" in rule for rule in combined.audit["double_count_rules"]),
)
check(
    "the audit records that Benefits never reduce LCA Gross A-C",
    any("Gross A-C" in rule for rule in combined.audit["double_count_rules"]),
)

# ---------------------------------------------------------------------------
# 10. Gate contract
# ---------------------------------------------------------------------------

check(
    "only COMPUTED and OFFICIAL-REPORTED states may carry a headline",
    PUBLICATION_ELIGIBLE_STATES == frozenset({STATUS_COMPUTED, "OFFICIAL-REPORTED"}),
)
check("SCENARIO-ONLY is not an eligible state", STATUS_SCENARIO_ONLY not in PUBLICATION_ELIGIBLE_STATES)
check("PROXY is not an eligible state", STATUS_PROXY not in PUBLICATION_ELIGIBLE_STATES)
check("SOURCE-OPEN is not an eligible state", STATUS_SOURCE_OPEN not in PUBLICATION_ELIGIBLE_STATES)
check("BLOCKED is not an eligible state", STATUS_BLOCKED not in PUBLICATION_ELIGIBLE_STATES)

for gate_field in (
    "publication_ready",
    "physical_ready",
    "monetized_time_ready",
    "economic_impact_ready",
    "employment_ready",
    "noise_physical_ready",
    "blocked_items",
    "warnings",
    "source_open_items",
):
    check(f"gate exposes {gate_field!r}", gate_field in result.publication_gate)

check(
    "an all-open run is not publication ready",
    result.publication_gate["publication_ready"] is False,
)

print()
print("RESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
