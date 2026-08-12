"""Acceptance tests for the deterministic scientific Benefits core.

These tests are about scientific correctness, not coverage. Each one pins a
place where a plausible-looking implementation would be wrong:

  * unit contracts on passenger-km and passenger-hours;
  * modal-shift bounds and the car/bus split closing to 1;
  * signed avoided emissions INCLUDING the negative case;
  * the gas-specific route versus the already-CO2e route, and no double GWP;
  * the Rule of Half reaching generated traffic only;
  * the Shannon LUD leading minus sign, uniform = 1, dominance -> 0, and p = 0
    never reaching log(0);
  * UN-Habitat LCR/PGR arithmetic, same-period enforcement, PGR = 0 undefined;
  * a known 2x2 Leontief inverse and rejection of a singular I - A;
  * the jobs proxy basis;
  * signed physical noise deltas and the absence of any dB percentage.

Fixture numbers are TEST-ONLY software-correctness values. They are not project
evidence and must never be copied into the app as defaults.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benefits_scientific_core import (
    EvidenceValue,
    ScientificBenefitInputError,
    allocate_shifted_pkm,
    annual_passenger_km,
    avoided_emissions,
    built_up_area_per_capita,
    built_up_change_pct,
    emissions_from_co2e_factor,
    emissions_from_gas_factor,
    employment_multiplier,
    generated_traffic_benefit_rule_of_half,
    io_output_response,
    jobs_proxy,
    land_consumption_rate,
    land_use_diversity_delta,
    land_use_shares,
    lcr_pgr_ratio,
    leontief_inverse,
    minutes_to_hours,
    monetize_time_saving,
    normalized_land_use_diversity,
    output_multiplier,
    passenger_hours_saved,
    physical_noise_delta,
    physical_noise_deltas,
    population_growth_rate,
    shifted_passenger_km,
    technical_coefficients,
    vot_from_logit_coefficients,
)

ok = True


def check(name, cond):
    global ok
    print(("PASS" if cond else "FAIL"), name)
    ok = ok and bool(cond)


def rejects(name, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except ScientificBenefitInputError:
        check(name, True)
        return
    except Exception as exc:  # wrong exception type is still a failure
        check(f"{name} (raised {type(exc).__name__}, expected ScientificBenefitInputError)", False)
        return
    check(f"{name} (no error raised)", False)


def close(a, b, tol=1e-9):
    return abs(a - b) <= tol


# ---------------------------------------------------------------------------
# BEN-PKM-01 / BEN-MODAL-01 / BEN-MODE-SPLIT-01
# ---------------------------------------------------------------------------

pkm = annual_passenger_km(100_000.0, 12.0, 350.0)
check("BEN-PKM-01 unit contract: pax/day x km x days = pkm/yr", close(pkm, 420_000_000.0))
rejects("BEN-PKM-01 rejects a missing operating-days input", annual_passenger_km, 100.0, 10.0, None)
rejects("BEN-PKM-01 rejects zero operating days", annual_passenger_km, 100.0, 10.0, 0.0)
rejects("BEN-PKM-01 rejects negative ridership", annual_passenger_km, -1.0, 10.0, 350.0)
rejects("BEN-PKM-01 rejects NaN distance", annual_passenger_km, 100.0, float("nan"), 350.0)

check("BEN-MODAL-01 applies the fraction", close(shifted_passenger_km(1000.0, 0.3), 300.0))
rejects("BEN-MODAL-01 rejects a fraction above 1", shifted_passenger_km, 1000.0, 1.5)
rejects("BEN-MODAL-01 rejects a negative fraction", shifted_passenger_km, 1000.0, -0.1)

split = allocate_shifted_pkm(1000.0, 0.6, 0.4)
check("BEN-MODE-SPLIT-01 car leg", close(split["car_pkm"], 600.0))
check("BEN-MODE-SPLIT-01 bus leg", close(split["bus_pkm"], 400.0))
check(
    "BEN-MODE-SPLIT-01 partition never exceeds the whole",
    close(split["car_pkm"] + split["bus_pkm"], 1000.0),
)
rejects("BEN-MODE-SPLIT-01 rejects shares that do not sum to 1", allocate_shifted_pkm, 1000.0, 0.6, 0.5)
rejects("BEN-MODE-SPLIT-01 rejects a short split", allocate_shifted_pkm, 1000.0, 0.6, 0.3)

# ---------------------------------------------------------------------------
# Greenhouse gases
# ---------------------------------------------------------------------------

gas = emissions_from_gas_factor(1000.0, 0.002, 25.0)
check("BEN-GHG-GAS-01 activity x EF x GWP", close(gas, 50.0))

co2e = emissions_from_co2e_factor(1000.0, 0.05)
check("BEN-GHG-CO2E-01 activity x CO2e factor", close(co2e, 50.0))

# The two routes must NOT be composable: an already-CO2e factor sent through the
# gas route would be multiplied by the warming potential a second time.
double_counted = emissions_from_gas_factor(1000.0, 0.05, 25.0)
check(
    "no double GWP: the CO2e route is 25x smaller than mistakenly re-applying GWP",
    close(double_counted, co2e * 25.0) and not close(double_counted, co2e),
)
rejects("BEN-GHG-GAS-01 rejects a zero GWP", emissions_from_gas_factor, 1000.0, 0.002, 0.0)

benefit = avoided_emissions(120.0, 100.0)
check("BEN-GHG-AVOID-01 positive case", close(benefit["avoided_co2e"], 20.0))
check("BEN-GHG-AVOID-01 labels a benefit", benefit["benefit_direction"] == "benefit")

disbenefit = avoided_emissions(100.0, 130.0)
check(
    "BEN-GHG-AVOID-01 negative case is NOT truncated to zero",
    close(disbenefit["avoided_co2e"], -30.0),
)
check("BEN-GHG-AVOID-01 labels a disbenefit", disbenefit["benefit_direction"] == "disbenefit")
check("BEN-GHG-AVOID-01 neutral case", avoided_emissions(50.0, 50.0)["benefit_direction"] == "neutral")

# ---------------------------------------------------------------------------
# Time
# ---------------------------------------------------------------------------

check("minutes -> hours is an explicit named conversion", close(minutes_to_hours(90.0), 1.5))

hours = passenger_hours_saved(1_000_000.0, 0.75, 0.5)
check("BEN-TIME-01 passenger-hours", close(hours, 250_000.0))
check(
    "BEN-TIME-01 preserves a negative saving when the project is slower",
    close(passenger_hours_saved(100.0, 0.5, 0.75), -25.0),
)

money = monetize_time_saving(250_000.0, 20.0)
check("BEN-TIME-MONEY-01 hours x VOT", close(money, 5_000_000.0))

# Rule of half — the central prohibition.
generated = generated_traffic_benefit_rule_of_half(1000.0, 0.5, 20.0)
check("BEN-GEN-TRAFFIC-01 halves the generated-traffic benefit", close(generated, 5_000.0))
existing_full = monetize_time_saving(passenger_hours_saved(1000.0, 0.5, 0.0), 20.0)
check(
    "Rule of Half reaches generated traffic ONLY: existing passengers keep the full benefit",
    close(existing_full, 10_000.0) and close(generated, existing_full * 0.5),
)

vot = vot_from_logit_coefficients(0.05, 0.15)
check("BEN-VOT-01 coefficient ratio x 60", close(vot, (0.05 / 0.15) * 60.0))
rejects("BEN-VOT-01 rejects a zero cost coefficient", vot_from_logit_coefficients, 0.05, 0.0)

# ---------------------------------------------------------------------------
# Land use
# ---------------------------------------------------------------------------

shares = land_use_shares({"residential": 40.0, "commercial": 30.0, "green": 30.0})
check("BEN-LU-SHARE-01 shares sum to 1", close(sum(shares.values()), 1.0))
check("BEN-LU-SHARE-01 share value", close(shares["residential"], 0.4))
rejects("BEN-LU-SHARE-01 rejects a negative area", land_use_shares, {"a": -1.0, "b": 2.0})
rejects("BEN-LU-SHARE-01 rejects a zero total area", land_use_shares, {"a": 0.0, "b": 0.0})

uniform = normalized_land_use_diversity({"a": 0.25, "b": 0.25, "c": 0.25, "d": 0.25})
check("BEN-LUD-01 uniform distribution gives exactly 1", close(uniform, 1.0))

dominant = normalized_land_use_diversity({"a": 0.999999, "b": 0.000001})
check("BEN-LUD-01 single-class dominance approaches 0", 0.0 < dominant < 1e-3)

with_zero = normalized_land_use_diversity({"a": 0.5, "b": 0.5, "c": 0.0})
check("BEN-LUD-01 a zero share does not call log(0)", math.isfinite(with_zero))
check(
    "BEN-LUD-01 a zero share contributes zero to the sum",
    close(with_zero, math.log(2.0) / math.log(3.0)),
)

# The leading minus sign. Without it every non-degenerate result is negative.
check("BEN-LUD-01 carries the leading minus sign: the index is non-negative", with_zero > 0.0)
check("BEN-LUD-01 index stays within [0, 1]", 0.0 <= uniform <= 1.0 and 0.0 <= with_zero <= 1.0)

rejects("BEN-LUD-01 rejects a single class (ln(1) = 0)", normalized_land_use_diversity, {"a": 1.0})
rejects(
    "BEN-LUD-01 rejects shares that do not sum to 1",
    normalized_land_use_diversity,
    {"a": 0.5, "b": 0.2},
)

delta = land_use_diversity_delta(0.82, 0.61)
check("BEN-LUD-DELTA-01 project minus baseline", close(delta, 0.21))
check("BEN-LUD-DELTA-01 keeps a negative change", close(land_use_diversity_delta(0.4, 0.6), -0.2))

# ---------------------------------------------------------------------------
# Urban growth — SDG 11.3.1
# ---------------------------------------------------------------------------

check("BEN-BUILTUP-CHANGE-01 known arithmetic", close(built_up_change_pct(200.0, 250.0), 25.0))
rejects("BEN-BUILTUP-CHANGE-01 rejects a zero past area", built_up_change_pct, 0.0, 250.0)

# 100 -> 150 over 10 years: (50/100) * (1/10) = 0.05 per year.
lcr = land_consumption_rate(100.0, 150.0, 10.0)
check("BEN-LCR-01 known arithmetic", close(lcr, 0.05))
rejects("BEN-LCR-01 rejects a zero period", land_consumption_rate, 100.0, 150.0, 0.0)

# ln(1.2)/10 per year.
pgr = population_growth_rate(1_000_000.0, 1_200_000.0, 10.0)
check("BEN-PGR-01 known arithmetic", close(pgr, math.log(1.2) / 10.0))
rejects("BEN-PGR-01 rejects a zero initial population", population_growth_rate, 0.0, 1000.0, 10.0)

ratio = lcr_pgr_ratio(lcr, pgr, lcr_period_years=10.0, pgr_period_years=10.0)
check("BEN-LCRPGR-01 computes over an identical period", ratio["status"] == "COMPUTED")
check("BEN-LCRPGR-01 ratio value", close(ratio["lcr_pgr"], lcr / pgr))

rejects(
    "BEN-LCRPGR-01 rejects mismatched analysis periods",
    lcr_pgr_ratio,
    lcr,
    pgr,
    lcr_period_years=10.0,
    pgr_period_years=15.0,
)

undefined = lcr_pgr_ratio(0.05, 0.0)
check("BEN-LCRPGR-01 PGR = 0 is UNDEFINED", undefined["status"] == "UNDEFINED")
check("BEN-LCRPGR-01 PGR = 0 does not return zero", undefined["lcr_pgr"] is None)
check("BEN-LCRPGR-01 PGR = 0 carries a diagnostic", bool(undefined["diagnostic"]))

check("BEN-BUILTUP-PC-01 m2 per person", close(built_up_area_per_capita(5_000_000.0, 250_000.0), 20.0))
rejects("BEN-BUILTUP-PC-01 rejects a zero population", built_up_area_per_capita, 100.0, 0.0)

# ---------------------------------------------------------------------------
# Input-output
# ---------------------------------------------------------------------------

A = technical_coefficients([[20.0, 30.0], [40.0, 10.0]], [100.0, 200.0])
check("BEN-IO-A-01 normalises by column total output", close(A[0][0], 0.2) and close(A[0][1], 0.15))
rejects(
    "BEN-IO-A-01 rejects a zero-output sector",
    technical_coefficients,
    [[1.0, 1.0], [1.0, 1.0]],
    [100.0, 0.0],
)
rejects(
    "BEN-IO-A-01 rejects a non-square transactions matrix",
    technical_coefficients,
    [[1.0, 1.0, 1.0], [1.0, 1.0, 1.0]],
    [1.0, 1.0],
)

# Known 2x2: A = [[0.2,0.1],[0.3,0.4]] -> I-A = [[0.8,-0.1],[-0.3,0.6]], det = 0.45
# L = (1/0.45) * [[0.6,0.1],[0.3,0.8]]
L = leontief_inverse([[0.2, 0.1], [0.3, 0.4]])
check("BEN-IO-L-01 known 2x2 inverse [0][0]", close(L[0][0], 0.6 / 0.45, 1e-12))
check("BEN-IO-L-01 known 2x2 inverse [0][1]", close(L[0][1], 0.1 / 0.45, 1e-12))
check("BEN-IO-L-01 known 2x2 inverse [1][0]", close(L[1][0], 0.3 / 0.45, 1e-12))
check("BEN-IO-L-01 known 2x2 inverse [1][1]", close(L[1][1], 0.8 / 0.45, 1e-12))

# I - A singular: A = [[1,0],[0,1]] -> I-A = 0 matrix.
rejects("BEN-IO-L-01 rejects a singular I - A", leontief_inverse, [[1.0, 0.0], [0.0, 1.0]])
rejects(
    "BEN-IO-L-01 rejects an ill-conditioned I - A",
    leontief_inverse,
    [[1.0 - 1e-15, 0.0], [0.0, 0.5]],
)

dx = io_output_response(L, [1.0, 0.0])
check("BEN-IO-DELTA-01 dx = L dy picks the first column", close(dx[0], L[0][0]) and close(dx[1], L[1][0]))
rejects("BEN-IO-DELTA-01 rejects a mismatched demand vector", io_output_response, L, [1.0])

omult = output_multiplier(L)
check("BEN-IO-OMULT-01 column sums", close(omult[0], L[0][0] + L[1][0]) and close(omult[1], L[0][1] + L[1][1]))

emult = employment_multiplier(L, [0.5, 0.25])
check(
    "BEN-IO-EMULT-01 weighted column sum over the direct coefficient",
    close(emult[0], (0.5 * L[0][0] + 0.25 * L[1][0]) / 0.5),
)
rejects("BEN-IO-EMULT-01 rejects a zero employment coefficient", employment_multiplier, L, [0.5, 0.0])

# ---------------------------------------------------------------------------
# Jobs proxy
# ---------------------------------------------------------------------------

proxy = jobs_proxy(500.0, 13.0)
check("BEN-JOBS-PROXY-01 investment(m const-2015-USD) x job content", close(proxy, 6500.0))
rejects("BEN-JOBS-PROXY-01 rejects a negative investment", jobs_proxy, -1.0, 13.0)

# The prohibited composite: officially reported jobs and proxy jobs are two
# different evidence products and the core offers no function that adds them.
import benefits_scientific_core as _core

check(
    "core exposes no function that totals official jobs with proxy jobs",
    not any(
        name
        for name in dir(_core)
        if "total" in name.lower() and "job" in name.lower()
    ),
)

# ---------------------------------------------------------------------------
# Noise
# ---------------------------------------------------------------------------

noise = physical_noise_delta(
    receptor_id="R1",
    metric="Lden",
    assessment_period="annual",
    baseline_db=68.0,
    project_db=63.0,
)
check("BEN-NOISE-PHYS-01 signed dB difference", close(noise["noise_delta_db"], 5.0))
check("BEN-NOISE-PHYS-01 labels a benefit", noise["benefit_direction"] == "benefit")

worse = physical_noise_delta(
    receptor_id="R2",
    metric="Lnight",
    assessment_period="night",
    baseline_db=55.0,
    project_db=60.0,
)
check("BEN-NOISE-PHYS-01 keeps a negative delta", close(worse["noise_delta_db"], -5.0))
check("BEN-NOISE-PHYS-01 labels a disbenefit", worse["benefit_direction"] == "disbenefit")

check(
    "BEN-NOISE-PHYS-01 result carries NO percentage of a dB value",
    not any("pct" in k or "percent" in k or "ratio" in k for k in noise),
)

rejects(
    "BEN-NOISE-PHYS-01 rejects a missing metric",
    physical_noise_delta,
    receptor_id="R1",
    metric="",
    assessment_period="annual",
    baseline_db=68.0,
    project_db=63.0,
)
rejects(
    "BEN-NOISE-PHYS-01 rejects a missing receptor id",
    physical_noise_delta,
    receptor_id="",
    metric="Lden",
    assessment_period="annual",
    baseline_db=68.0,
    project_db=63.0,
)

rows = physical_noise_deltas(
    [
        {"receptor_id": "R1", "metric": "Lden", "assessment_period": "annual", "baseline_db": 68.0, "project_db": 63.0},
        {"receptor_id": "R2", "metric": "Lden", "assessment_period": "annual", "baseline_db": 70.0, "project_db": 69.0},
    ]
)
check("BEN-NOISE-PHYS-01 returns one row per receptor", len(rows) == 2)
check(
    "BEN-NOISE-PHYS-01 does not average dB across receptors",
    not any("mean" in k or "average" in k or "total" in k for row in rows for k in row),
)
rejects(
    "BEN-NOISE-PHYS-01 rejects a duplicated receptor/metric/period",
    physical_noise_deltas,
    [
        {"receptor_id": "R1", "metric": "Lden", "assessment_period": "annual", "baseline_db": 68.0, "project_db": 63.0},
        {"receptor_id": "R1", "metric": "Lden", "assessment_period": "annual", "baseline_db": 60.0, "project_db": 59.0},
    ],
)

# ---------------------------------------------------------------------------
# Evidence schema
# ---------------------------------------------------------------------------

ev = EvidenceValue(
    value=18.3,
    unit="EGP/hour",
    source_ref_id="REF-EGY-VOT-2022",
    source_file="n/a",
    source_location="Theoretical Framework, reviewed PDF pp.3-4",
    geography="Egypt",
    evidence_status="METHOD-REFERENCE",
    price_base_year=2022,
    currency="EGP",
)
check("EvidenceValue carries currency and price base year for money", ev.currency == "EGP" and ev.price_base_year == 2022)
try:
    ev.value = 99.0  # type: ignore[misc]
    check("EvidenceValue is frozen", False)
except Exception:
    check("EvidenceValue is frozen", True)

# ---------------------------------------------------------------------------
# Domain purity
# ---------------------------------------------------------------------------

core_src = open(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "benefits_scientific_core.py"),
    encoding="utf-8",
).read()
for forbidden in ("import streamlit", "lca_scientific", "lcc_scientific", "legacy_lca", "legacy_lcc"):
    check(f"core does not reference {forbidden!r}", forbidden not in core_src)

print()
print("RESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
