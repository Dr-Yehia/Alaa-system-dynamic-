"""Deterministic, source-locked scientific Benefits calculations.

WHAT THIS MODULE IS
-------------------
Pure functions. Each one implements exactly one registered equation, and each
arithmetic line carries an inline `#` comment naming the document, the exact
page or annex, and the DOI or official URL that authorises it. A reviewer
reading a number in the app can follow it to a function here, read the equation
line, and open the source from the comment without leaving the code.

WHAT THIS MODULE IS NOT
-----------------------
It is not the place where Cairo's numbers live. Nothing here has a default
value: there is no fallback modal-shift fraction, no assumed 365 operating days,
no built-in value of time. Every quantity arrives as an argument, and the
integration layer is responsible for proving that quantity has its own numeric
evidence. That separation is the whole point:

    THE SOURCE OF AN EQUATION IS NOT THE SOURCE OF A NUMERICAL VALUE.

It imports no LCA engine, no LCC engine, no legacy engine and no Streamlit. It
holds no state. Given the same arguments it returns the same result, which is
what makes the Benefits domain independently testable.

DELIBERATE ABSENCES
-------------------
There is no formalization benefit, no carbon monetisation and no noise
monetisation in this module. Those are recorded in
`benefits_reference_registry.BLOCKED_TOPICS` with the evidence that would close
each one. An absent function is an honest statement that the evidence is not
there; a plausible-looking function with an invented coefficient is not.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence


class ScientificBenefitInputError(ValueError):
    """Raised when an input cannot support the equation being asked for.

    Every raise in this module names the equation and what was wrong, because a
    silent coercion — a clamp, an epsilon, a substituted zero — is precisely how
    an unsupportable number reaches a manuscript.
    """


# ---------------------------------------------------------------------------
# Evidence schema
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProjectNumericSource:
    """A project document that measures or reports a number for THIS project.

    This exists because the registry cannot hold it. The registry catalogues
    method documents — standards, metadata sheets, journal articles — and none of
    them can certify a Cairo quantity. A project number's provenance is a survey,
    a demand model, a GIS layer or an official project report, and it enters the
    system here rather than by relabelling a method reference as project data.

    Every field is required for a publication claim. A title with no location, or
    a file with no date, leaves a reviewer unable to find the number again.
    """

    title: str
    issuer: str
    file_or_url: str
    exact_location: str
    geography: str
    observation_date: str
    evidence_status: str = "PROJECT-SPECIFIC"
    note: str = ""

    def missing_fields(self) -> list[str]:
        """Which required fields are blank. Empty list means complete."""
        required = (
            "title",
            "issuer",
            "file_or_url",
            "exact_location",
            "geography",
            "observation_date",
        )
        return [f for f in required if not str(getattr(self, f, "") or "").strip()]


@dataclass(frozen=True)
class EvidenceValue:
    """A number together with everything a reviewer needs to check it.

    A bare float cannot be audited: 18.3 is meaningless without knowing that it
    is EGP per hour, from an Egyptian logit study, at that study's price year.
    Publication inputs are carried in this envelope so the gate can refuse a
    value whose provenance is a method reference rather than project data.

    `source_ref_id` cites a registry document and establishes what METHOD the
    number belongs to. `project_source` carries the project document that
    actually measured it. A publication claim needs the second; citing only the
    first and typing a stronger status beside it is authority escalation, and the
    integration layer rejects it.
    """

    value: object
    unit: str
    source_ref_id: str
    source_file: str
    source_location: str
    geography: str
    evidence_status: str
    price_base_year: Optional[int] = None
    currency: Optional[str] = None
    factor_basis: Optional[str] = None
    observation_date: Optional[str] = None
    project_source: Optional[ProjectNumericSource] = None
    note: str = ""


# ---------------------------------------------------------------------------
# Shared numeric guards
# ---------------------------------------------------------------------------


def _require_number(value, *, equation_id: str, name: str) -> float:
    """Coerce to float, rejecting None, NaN, Inf and non-numeric types."""
    if value is None:
        raise ScientificBenefitInputError(
            f"{equation_id}: {name} is None; a required project quantity has no "
            "value. Supply evidence or leave the KPI unreported."
        )
    if isinstance(value, bool):
        raise ScientificBenefitInputError(
            f"{equation_id}: {name} is a bool, not a measured quantity"
        )
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ScientificBenefitInputError(
            f"{equation_id}: {name} is not numeric (got {type(value).__name__})"
        ) from None
    if not math.isfinite(number):
        raise ScientificBenefitInputError(
            f"{equation_id}: {name} is not finite (got {value!r})"
        )
    return number


def _require_non_negative(value, *, equation_id: str, name: str) -> float:
    number = _require_number(value, equation_id=equation_id, name=name)
    if number < 0.0:
        raise ScientificBenefitInputError(
            f"{equation_id}: {name} must be >= 0 (got {number})"
        )
    return number


def _require_positive(value, *, equation_id: str, name: str) -> float:
    number = _require_number(value, equation_id=equation_id, name=name)
    if number <= 0.0:
        raise ScientificBenefitInputError(
            f"{equation_id}: {name} must be > 0 (got {number})"
        )
    return number


def _require_fraction(value, *, equation_id: str, name: str) -> float:
    number = _require_number(value, equation_id=equation_id, name=name)
    if not (0.0 <= number <= 1.0):
        raise ScientificBenefitInputError(
            f"{equation_id}: {name} must lie in [0, 1] (got {number})"
        )
    return number


#: Tolerance for share/split closure checks. Tight enough that a genuine
#: bookkeeping error fails, loose enough to absorb float representation.
SHARE_SUM_TOLERANCE = 1e-9

#: Below this magnitude a population growth rate is treated as indistinguishable
#: from zero, which makes LCR/PGR undefined rather than enormous.
PGR_ZERO_THRESHOLD = 1e-12


# ---------------------------------------------------------------------------
# Transport activity
# ---------------------------------------------------------------------------


def annual_passenger_km(
    passengers_per_day, avg_distance_km, operating_days_per_year
) -> float:
    """BEN-PKM-01 — annual passenger-km from ridership, trip length and service days.

    Operating days is a required argument on purpose. The green bond report uses
    365 days for its own calculation; that is its assumption, not a property of
    this project, and substituting it silently would launder a report assumption
    into a project result.
    """
    eq = "BEN-PKM-01"
    passengers_per_day = _require_non_negative(
        passengers_per_day, equation_id=eq, name="passengers_per_day"
    )
    avg_distance_km = _require_non_negative(
        avg_distance_km, equation_id=eq, name="avg_distance_km"
    )
    operating_days_per_year = _require_positive(
        operating_days_per_year, equation_id=eq, name="operating_days_per_year"
    )

    annual_pkm = passengers_per_day * avg_distance_km * operating_days_per_year  # EQ=BEN-PKM-01 | REF=REF-EGY-GB-2022 | TITLE=Egypt Sovereign Green Bond Allocation & Impact Report - 2022 | ISSUER=Ministry of Finance, Government of Egypt | YEAR=2022 | LOC=Annex 1, GHG Methodology Used for Monorail, printed pp.30-31 | DOI=n/a | URL=https://assets.mof.gov.eg/files/2022-12/d3dec230-8900-11ed-ad5c-d5697d806e26.pdf
    return annual_pkm


def shifted_passenger_km(annual_pkm, modal_shift_fraction) -> float:
    """BEN-MODAL-01 — the share of annual passenger-km drawn from other modes.

    The fraction is bounded to [0, 1] because a modal shift above unity would
    mean more travel is displaced than exists.
    """
    eq = "BEN-MODAL-01"
    annual_pkm = _require_non_negative(annual_pkm, equation_id=eq, name="annual_pkm")
    modal_shift_fraction = _require_fraction(
        modal_shift_fraction, equation_id=eq, name="modal_shift_fraction"
    )

    shifted_pkm = annual_pkm * modal_shift_fraction  # EQ=BEN-MODAL-01 | REF=REF-EGY-GB-2022;REF-TRD-MODAL-2024 | TITLE=Egypt Sovereign Green Bond Allocation & Impact Report - 2022; Using different transport modes: An opportunity to reduce UK passenger transport emissions? | ISSUER=Ministry of Finance, Government of Egypt; Thomas & Cabrera Serrenho | LOC=Egypt report Annex 1 modal-shift methodology, printed pp.30-31; TRD Part D vol.126 (2024) art.103989 modal-shift method | DOI=10.1016/j.trd.2023.103989 | URL=https://assets.mof.gov.eg/files/2022-12/d3dec230-8900-11ed-ad5c-d5697d806e26.pdf
    return shifted_pkm


def allocate_shifted_pkm(shifted_pkm, car_share, bus_share) -> dict:
    """BEN-MODE-SPLIT-01 — split displaced passenger-km between car and bus.

    The shares must close to 1. A split that does not close either loses or
    invents displaced travel, and the downstream avoided-emission figure would
    inherit the error invisibly.
    """
    eq = "BEN-MODE-SPLIT-01"
    shifted_pkm = _require_non_negative(shifted_pkm, equation_id=eq, name="shifted_pkm")
    car_share = _require_fraction(car_share, equation_id=eq, name="car_share")
    bus_share = _require_fraction(bus_share, equation_id=eq, name="bus_share")

    if abs(car_share + bus_share - 1.0) > SHARE_SUM_TOLERANCE:
        raise ScientificBenefitInputError(
            f"{eq}: car_share + bus_share must equal 1 within "
            f"{SHARE_SUM_TOLERANCE} (got {car_share + bus_share})"
        )

    pkm_car = shifted_pkm * car_share  # EQ=BEN-MODE-SPLIT-01 | REF=REF-EGY-GB-2022;REF-TRD-MODAL-2024 | TITLE=Egypt Sovereign Green Bond Allocation & Impact Report - 2022; Using different transport modes: An opportunity to reduce UK passenger transport emissions? | LOC=Egypt report Annex 1 car/bus-to-rail switching basis, printed pp.30-31; TRD Part D vol.126 (2024) art.103989 mode-specific emission accounting | DOI=10.1016/j.trd.2023.103989 | URL=https://assets.mof.gov.eg/files/2022-12/d3dec230-8900-11ed-ad5c-d5697d806e26.pdf
    pkm_bus = shifted_pkm * bus_share  # EQ=BEN-MODE-SPLIT-01 | REF=REF-EGY-GB-2022;REF-TRD-MODAL-2024 | TITLE=Egypt Sovereign Green Bond Allocation & Impact Report - 2022; Using different transport modes: An opportunity to reduce UK passenger transport emissions? | LOC=Egypt report Annex 1 car/bus-to-rail switching basis, printed pp.30-31; TRD Part D vol.126 (2024) art.103989 mode-specific emission accounting | DOI=10.1016/j.trd.2023.103989 | URL=https://assets.mof.gov.eg/files/2022-12/d3dec230-8900-11ed-ad5c-d5697d806e26.pdf
    return {"car_pkm": pkm_car, "bus_pkm": pkm_bus}


# ---------------------------------------------------------------------------
# Greenhouse gases
# ---------------------------------------------------------------------------


def emissions_from_gas_factor(activity, emission_factor_gas, gwp) -> float:
    """BEN-GHG-GAS-01 — emissions where the factor is per unit mass of one gas.

    Use this route ONLY when the factor is gas-specific (e.g. kgCH4 per unit).
    An already-CO2e factor has the warming potential baked in, and sending it
    through here multiplies it a second time.
    """
    eq = "BEN-GHG-GAS-01"
    activity = _require_non_negative(activity, equation_id=eq, name="activity")
    emission_factor_gas = _require_non_negative(
        emission_factor_gas, equation_id=eq, name="emission_factor_gas"
    )
    gwp = _require_positive(gwp, equation_id=eq, name="gwp")

    emissions_co2e = activity * emission_factor_gas * gwp  # EQ=BEN-GHG-GAS-01 | REF=REF-EGY-GB-2022 | TITLE=Egypt Sovereign Green Bond Allocation & Impact Report - 2022 | ISSUER=Ministry of Finance, Government of Egypt | YEAR=2022 | LOC=Annex 1, GHG Methodology Used for Monorail, printed pp.30-31, Emissions = Activity Data x Emission Factor x Global Warming Potential | DOI=n/a | URL=https://assets.mof.gov.eg/files/2022-12/d3dec230-8900-11ed-ad5c-d5697d806e26.pdf
    return emissions_co2e


def emissions_from_co2e_factor(activity, emission_factor_co2e) -> float:
    """BEN-GHG-CO2E-01 — emissions where the factor already includes the GWP.

    The caller must have established the factor's unit, basis, mode, year and
    geography; this function cannot tell a Cairo factor from a UK one.
    """
    eq = "BEN-GHG-CO2E-01"
    activity = _require_non_negative(activity, equation_id=eq, name="activity")
    emission_factor_co2e = _require_non_negative(
        emission_factor_co2e, equation_id=eq, name="emission_factor_co2e"
    )

    emissions_co2e = activity * emission_factor_co2e  # EQ=BEN-GHG-CO2E-01 | REF=REF-EGY-GB-2022;REF-TRD-MODAL-2024 | TITLE=Egypt Sovereign Green Bond Allocation & Impact Report - 2022; Using different transport modes: An opportunity to reduce UK passenger transport emissions? | LOC=Egypt report Annex 1 activity-data x emission-factor structure, printed pp.30-31; TRD Part D vol.126 (2024) art.103989 distance x conversion-factor logic | DOI=10.1016/j.trd.2023.103989 | URL=https://assets.mof.gov.eg/files/2022-12/d3dec230-8900-11ed-ad5c-d5697d806e26.pdf
    return emissions_co2e


def avoided_emissions(baseline_co2e, project_co2e) -> dict:
    """BEN-GHG-AVOID-01 — signed avoided emissions, with no truncation.

    The sign is the finding. `max(delta, 0)` would convert a project that emits
    more than the baseline into a project that appears neutral, which is the
    single most consequential way an environmental result can be misreported.
    """
    eq = "BEN-GHG-AVOID-01"
    baseline_co2e = _require_number(
        baseline_co2e, equation_id=eq, name="baseline_co2e"
    )
    project_co2e = _require_number(project_co2e, equation_id=eq, name="project_co2e")

    avoided_co2e = baseline_co2e - project_co2e  # EQ=BEN-GHG-AVOID-01 | REF=REF-EGY-GB-2022;REF-TRD-MODAL-2024 | TITLE=Egypt Sovereign Green Bond Allocation & Impact Report - 2022; Using different transport modes: An opportunity to reduce UK passenger transport emissions? | LOC=Egypt Annex 1 avoided-emission modal-shift method, printed pp.30-31; TRD Part D vol.126 (2024) art.103989 modal-shift emissions method | DOI=10.1016/j.trd.2023.103989 | URL=https://assets.mof.gov.eg/files/2022-12/d3dec230-8900-11ed-ad5c-d5697d806e26.pdf
    if avoided_co2e > 0.0:
        direction = "benefit"
    elif avoided_co2e < 0.0:
        direction = "disbenefit"
    else:
        direction = "neutral"
    return {
        "avoided_co2e": avoided_co2e,
        "benefit_direction": direction,
        "baseline_co2e": baseline_co2e,
        "project_co2e": project_co2e,
    }


# ---------------------------------------------------------------------------
# Travel time
# ---------------------------------------------------------------------------


def minutes_to_hours(minutes, *, equation_id: str = "BEN-TIME-01") -> float:
    """Explicit unit conversion, named so a reviewer can see it happened.

    Time inputs arrive from surveys in minutes and value of time is per hour.
    Converting inside the multiplication line would hide a factor of 60 in the
    middle of an equation that the source states in consistent units.
    """
    minutes = _require_number(minutes, equation_id=equation_id, name="minutes")
    return minutes / 60.0


def passenger_hours_saved(annual_passengers, baseline_time_h, project_time_h) -> float:
    """BEN-TIME-01 — annual passenger-hours saved, signed.

    A negative result means the project is slower than the baseline. That is a
    legitimate outcome for some corridors and is reported as it stands.
    """
    eq = "BEN-TIME-01"
    annual_passengers = _require_non_negative(
        annual_passengers, equation_id=eq, name="annual_passengers"
    )
    baseline_time_h = _require_non_negative(
        baseline_time_h, equation_id=eq, name="baseline_time_h"
    )
    project_time_h = _require_non_negative(
        project_time_h, equation_id=eq, name="project_time_h"
    )

    hours_saved = annual_passengers * (baseline_time_h - project_time_h)  # EQ=BEN-TIME-01 | REF=REF-WB-ENRRP-ICR | TITLE=Egypt National Railways Restructuring Project (P101103) - Implementation Completion and Results Report | ISSUER=World Bank | REPORT=ICR00005398 | LOC=Annex 4 Efficiency Analysis, printed pp.71-72 | DOI=n/a | URL=https://documents1.worldbank.org/curated/en/367961628584958285/pdf/Egypt-Railways-Restructuring-Project.pdf
    return hours_saved


def monetize_time_saving(passenger_hours_saved_value, value_of_time) -> float:
    """BEN-TIME-MONEY-01 — money value of time savings.

    The caller must have attached currency and price base year to the VOT. This
    function multiplies; it cannot detect that an EGP-2022 rate has been applied
    to a 2026 appraisal without adjustment.
    """
    eq = "BEN-TIME-MONEY-01"
    passenger_hours_saved_value = _require_number(
        passenger_hours_saved_value, equation_id=eq, name="passenger_hours_saved"
    )
    value_of_time = _require_non_negative(
        value_of_time, equation_id=eq, name="value_of_time"
    )

    time_benefit = passenger_hours_saved_value * value_of_time  # EQ=BEN-TIME-MONEY-01 | REF=REF-WB-ENRRP-ICR | TITLE=Egypt National Railways Restructuring Project (P101103) - Implementation Completion and Results Report | ISSUER=World Bank | REPORT=ICR00005398 | LOC=Annex 4 Efficiency Analysis, printed pp.71-72, time savings valued as traffic x time difference x value of time | DOI=n/a | URL=https://documents1.worldbank.org/curated/en/367961628584958285/pdf/Egypt-Railways-Restructuring-Project.pdf
    return time_benefit


def generated_traffic_benefit_rule_of_half(
    generated_passengers, time_saved_h, value_of_time
) -> float:
    """BEN-GEN-TRAFFIC-01 — Rule of Half, for GENERATED traffic only.

    Newly generated trips did not exist in the baseline, so their users are
    assumed to gain on average half the full saving. Existing passengers were
    already travelling and receive the whole saving through
    `monetize_time_saving`; applying the half here to them would understate a
    real benefit by 50%.
    """
    eq = "BEN-GEN-TRAFFIC-01"
    generated_passengers = _require_non_negative(
        generated_passengers, equation_id=eq, name="generated_passengers"
    )
    time_saved_h = _require_number(time_saved_h, equation_id=eq, name="time_saved_h")
    value_of_time = _require_non_negative(
        value_of_time, equation_id=eq, name="value_of_time"
    )

    generated_traffic_benefit = 0.5 * generated_passengers * time_saved_h * value_of_time  # EQ=BEN-GEN-TRAFFIC-01 | REF=REF-WB-ENRRP-ICR | TITLE=Egypt National Railways Restructuring Project (P101103) - Implementation Completion and Results Report | ISSUER=World Bank | REPORT=ICR00005398 | LOC=Annex 4, Rule-of-Half treatment for generated traffic, printed p.72 | DOI=n/a | URL=https://documents1.worldbank.org/curated/en/367961628584958285/pdf/Egypt-Railways-Restructuring-Project.pdf
    return generated_traffic_benefit


def vot_from_logit_coefficients(beta_time, beta_cost) -> float:
    """BEN-VOT-01 — value of travel time from a fitted binary logit model.

    The x60 encodes the source's per-minute to per-hour convention. The ratio is
    taken as the source defines it; the caller owns the sign convention of the
    fitted coefficients and the currency they are expressed in.
    """
    eq = "BEN-VOT-01"
    beta_time = _require_number(beta_time, equation_id=eq, name="beta_time")
    beta_cost = _require_number(beta_cost, equation_id=eq, name="beta_cost")
    if beta_cost == 0.0:
        raise ScientificBenefitInputError(
            f"{eq}: beta_cost is zero; the coefficient ratio that defines VOT is "
            "undefined for a model with no cost sensitivity"
        )

    vot_per_hour = (beta_time / beta_cost) * 60.0  # EQ=BEN-VOT-01 | REF=REF-EGY-VOT-2022 | TITLE=Estimation of Cross Classified Value of Travel Time Using Binary Logit Model on Egyptian Roads | AUTHORS=Bakry, Elgohary, Farag & Ramadan | YEAR=2022 | LOC=Theoretical Framework, reviewed PDF pp.3-4, VOT coefficient-ratio equation | DOI=10.2174/18744478-v16-e2209140 | URL=https://opentransportationjournal.com/VOLUME/16/ELOCATOR/e187444782209140/FULLTEXT/
    return vot_per_hour


# ---------------------------------------------------------------------------
# Land use
# ---------------------------------------------------------------------------


def land_use_shares(area_by_class: dict) -> dict:
    """BEN-LU-SHARE-01 — convert class areas to shares that sum to 1."""
    eq = "BEN-LU-SHARE-01"
    if not isinstance(area_by_class, dict) or not area_by_class:
        raise ScientificBenefitInputError(
            f"{eq}: area_by_class must be a non-empty mapping of class -> area"
        )

    areas = {
        str(name): _require_non_negative(
            area, equation_id=eq, name=f"area of class {name!r}"
        )
        for name, area in area_by_class.items()
    }
    total_area = sum(areas.values())
    if total_area <= 0.0:
        raise ScientificBenefitInputError(
            f"{eq}: total area must be > 0 (got {total_area})"
        )

    shares = {}
    for name, class_area in areas.items():
        shares[name] = class_area / total_area  # EQ=BEN-LU-SHARE-01 | REF=REF-PLOS-TOD-2023 | TITLE=A framework to measure transit-oriented development around transit nodes: Case study of a mass rapid transit system in Dhaka, Bangladesh | AUTHORS=Uddin et al. | YEAR=2023 | LOC=p.9, Land use diversity, Eq.(2) | DOI=10.1371/journal.pone.0280275 | URL=https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0280275
    return shares


def normalized_land_use_diversity(shares: dict) -> float:
    """BEN-LUD-01 — normalised Shannon land-use diversity in [0, 1].

    Two details decide whether this is right or subtly wrong:

    * the LEADING MINUS SIGN, which the rendered PLOS equation carries and which
      plain-text extraction of the PDF drops. Without it the index comes out
      negative and its interpretation inverts;
    * classes with zero share, which contribute zero by the limit p ln p -> 0 as
      p -> 0. Filtering them is not a convenience, it avoids log(0).
    """
    eq = "BEN-LUD-01"
    if not isinstance(shares, dict) or not shares:
        raise ScientificBenefitInputError(
            f"{eq}: shares must be a non-empty mapping of class -> share"
        )

    n_classes = len(shares)
    if n_classes < 2:
        raise ScientificBenefitInputError(
            f"{eq}: diversity requires at least 2 land-use classes (got {n_classes}); "
            "ln(1) = 0 makes the normalisation undefined"
        )

    values = [
        _require_fraction(share, equation_id=eq, name=f"share of class {name!r}")
        for name, share in shares.items()
    ]
    total = sum(values)
    if abs(total - 1.0) > 1e-6:
        raise ScientificBenefitInputError(
            f"{eq}: land-use shares must sum to 1 (got {total})"
        )

    lud = -sum(p * math.log(p) for p in values if p > 0.0) / math.log(n_classes)  # EQ=BEN-LUD-01 | REF=REF-PLOS-TOD-2023 | TITLE=A framework to measure transit-oriented development around transit nodes: Case study of a mass rapid transit system in Dhaka, Bangladesh | AUTHORS=Uddin et al. | YEAR=2023 | LOC=p.9, Land use diversity, Eq.(1); leading minus sign visually verified in the rendered PDF | DOI=10.1371/journal.pone.0280275 | URL=https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0280275
    return lud


def land_use_diversity_delta(lud_project, lud_baseline) -> float:
    """BEN-LUD-DELTA-01 — change in diversity, project minus baseline.

    A derived comparison, not a printed equation from the PLOS paper. Both
    values must come from the same class schema over the same analysis area or
    the difference measures the schema, not the project.
    """
    eq = "BEN-LUD-DELTA-01"
    lud_project = _require_number(lud_project, equation_id=eq, name="lud_project")
    lud_baseline = _require_number(lud_baseline, equation_id=eq, name="lud_baseline")

    lud_delta = lud_project - lud_baseline  # EQ=BEN-LUD-DELTA-01 | REF=REF-PLOS-TOD-2023 | TITLE=A framework to measure transit-oriented development around transit nodes: Case study of a mass rapid transit system in Dhaka, Bangladesh | AUTHORS=Uddin et al. | YEAR=2023 | LOC=p.9, Land use diversity, Eq.(1) applied to two states; DERIVED-FROM-METHOD, this delta is not printed in the source | DOI=10.1371/journal.pone.0280275 | URL=https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0280275
    return lud_delta


# ---------------------------------------------------------------------------
# Urban growth — SDG 11.3.1
# ---------------------------------------------------------------------------


def built_up_change_pct(built_up_past, built_up_current) -> float:
    """BEN-BUILTUP-CHANGE-01 — total percentage change in built-up area."""
    eq = "BEN-BUILTUP-CHANGE-01"
    built_up_past = _require_positive(
        built_up_past, equation_id=eq, name="built_up_past"
    )
    built_up_current = _require_non_negative(
        built_up_current, equation_id=eq, name="built_up_current"
    )

    change_pct = 100.0 * (built_up_current - built_up_past) / built_up_past  # EQ=BEN-BUILTUP-CHANGE-01 | REF=REF-UNHABITAT-SDG1131-2025 | TITLE=Metadata for SDG Indicator 11.3.1 - Ratio of land consumption rate to population growth rate | ISSUER=UN-Habitat / UN SDG metadata | VERSION=2025-04-23 | LOC=reviewed p.9, Total change in built-up area | DOI=n/a | URL=https://unstats.un.org/sdgs/metadata/files/Metadata-11-03-01.pdf
    return change_pct


def land_consumption_rate(v_past, v_present, period_years) -> float:
    """BEN-LCR-01 — annualised land consumption rate over a real elapsed period.

    `period_years` must be actual elapsed time between two observations. A
    baseline-versus-design scenario difference has no elapsed time and is not an
    SDG 11.3.1 land consumption rate however similar the arithmetic looks.
    """
    eq = "BEN-LCR-01"
    v_past = _require_positive(v_past, equation_id=eq, name="v_past")
    v_present = _require_non_negative(v_present, equation_id=eq, name="v_present")
    period_years = _require_positive(period_years, equation_id=eq, name="period_years")

    lcr = ((v_present - v_past) / v_past) * (1.0 / period_years)  # EQ=BEN-LCR-01 | REF=REF-UNHABITAT-SDG1131-2025 | TITLE=Metadata for SDG Indicator 11.3.1 - Ratio of land consumption rate to population growth rate | ISSUER=UN-Habitat / UN SDG metadata | VERSION=2025-04-23 | LOC=reviewed pp.7-8, Spatial analysis and computation of the land consumption rate | DOI=n/a | URL=https://unstats.un.org/sdgs/metadata/files/Metadata-11-03-01.pdf
    return lcr


def population_growth_rate(pop_initial, pop_final, period_years) -> float:
    """BEN-PGR-01 — continuous annual population growth rate."""
    eq = "BEN-PGR-01"
    pop_initial = _require_positive(pop_initial, equation_id=eq, name="pop_initial")
    pop_final = _require_positive(pop_final, equation_id=eq, name="pop_final")
    period_years = _require_positive(period_years, equation_id=eq, name="period_years")

    pgr = math.log(pop_final / pop_initial) / period_years  # EQ=BEN-PGR-01 | REF=REF-UNHABITAT-SDG1131-2025 | TITLE=Metadata for SDG Indicator 11.3.1 - Ratio of land consumption rate to population growth rate | ISSUER=UN-Habitat / UN SDG metadata | VERSION=2025-04-23 | LOC=reviewed p.8, Population Growth Rate formula | DOI=n/a | URL=https://unstats.un.org/sdgs/metadata/files/Metadata-11-03-01.pdf
    return pgr


def lcr_pgr_ratio(
    lcr, pgr, *, lcr_period_years=None, pgr_period_years=None
) -> dict:
    """BEN-LCRPGR-01 — ratio of land consumption to population growth.

    Two guards define this function. The periods must be identical, because the
    indicator compares two rates over one span of time. And when growth is
    numerically zero the ratio is UNDEFINED — it is not zero, and it is not
    obtained by dividing through an epsilon, which would manufacture an
    arbitrarily large number that looks like a finding.
    """
    eq = "BEN-LCRPGR-01"
    lcr = _require_number(lcr, equation_id=eq, name="lcr")
    pgr = _require_number(pgr, equation_id=eq, name="pgr")

    if lcr_period_years is not None and pgr_period_years is not None:
        lcr_years = _require_positive(
            lcr_period_years, equation_id=eq, name="lcr_period_years"
        )
        pgr_years = _require_positive(
            pgr_period_years, equation_id=eq, name="pgr_period_years"
        )
        if abs(lcr_years - pgr_years) > 1e-9:
            raise ScientificBenefitInputError(
                f"{eq}: LCR and PGR must span the identical analysis period "
                f"(got {lcr_years} vs {pgr_years} years)"
            )

    if abs(pgr) <= PGR_ZERO_THRESHOLD:
        return {
            "lcr_pgr": None,
            "status": "UNDEFINED",
            "diagnostic": (
                "population growth rate is numerically zero, so the LCR/PGR ratio "
                "is undefined; it is not reported as zero and no epsilon "
                "substitution is applied"
            ),
            "lcr": lcr,
            "pgr": pgr,
        }

    lcrpgr = lcr / pgr  # EQ=BEN-LCRPGR-01 | REF=REF-UNHABITAT-SDG1131-2025 | TITLE=Metadata for SDG Indicator 11.3.1 - Ratio of land consumption rate to population growth rate | ISSUER=UN-Habitat / UN SDG metadata | VERSION=2025-04-23 | LOC=reviewed pp.7-8, ratio of land consumption rate to population growth rate | DOI=n/a | URL=https://unstats.un.org/sdgs/metadata/files/Metadata-11-03-01.pdf
    return {
        "lcr_pgr": lcrpgr,
        "status": "COMPUTED",
        "diagnostic": "",
        "lcr": lcr,
        "pgr": pgr,
    }


def built_up_area_per_capita(built_up_area_m2, population) -> float:
    """BEN-BUILTUP-PC-01 — built-up area per person, in m2/person."""
    eq = "BEN-BUILTUP-PC-01"
    built_up_area_m2 = _require_non_negative(
        built_up_area_m2, equation_id=eq, name="built_up_area_m2"
    )
    population = _require_positive(population, equation_id=eq, name="population")

    per_capita = built_up_area_m2 / population  # EQ=BEN-BUILTUP-PC-01 | REF=REF-UNHABITAT-SDG1131-2025 | TITLE=Metadata for SDG Indicator 11.3.1 - Ratio of land consumption rate to population growth rate | ISSUER=UN-Habitat / UN SDG metadata | VERSION=2025-04-23 | LOC=reviewed p.9, built-up area per capita | DOI=n/a | URL=https://unstats.un.org/sdgs/metadata/files/Metadata-11-03-01.pdf
    return per_capita


# ---------------------------------------------------------------------------
# Input-output economics
# ---------------------------------------------------------------------------


def _as_square_matrix(matrix, *, equation_id: str, name: str) -> list[list[float]]:
    if matrix is None:
        raise ScientificBenefitInputError(f"{equation_id}: {name} is None")
    try:
        rows = [list(row) for row in matrix]
    except TypeError:
        raise ScientificBenefitInputError(
            f"{equation_id}: {name} is not a matrix"
        ) from None
    if not rows:
        raise ScientificBenefitInputError(f"{equation_id}: {name} is empty")
    n = len(rows)
    clean: list[list[float]] = []
    for i, row in enumerate(rows):
        if len(row) != n:
            raise ScientificBenefitInputError(
                f"{equation_id}: {name} must be square; row {i} has {len(row)} "
                f"entries for {n} sectors"
            )
        clean.append(
            [
                _require_number(v, equation_id=equation_id, name=f"{name}[{i}][{j}]")
                for j, v in enumerate(row)
            ]
        )
    return clean


def technical_coefficients(transactions, total_output) -> list[list[float]]:
    """BEN-IO-A-01 — technical coefficients a_ij = x_ij / X_j.

    Column j is normalised by sector j's total output, so a zero-output sector
    is rejected rather than silently producing infinities.
    """
    eq = "BEN-IO-A-01"
    x = _as_square_matrix(transactions, equation_id=eq, name="transactions")
    n = len(x)
    outputs = [
        _require_positive(v, equation_id=eq, name=f"total_output[{j}]")
        for j, v in enumerate(list(total_output))
    ]
    if len(outputs) != n:
        raise ScientificBenefitInputError(
            f"{eq}: total_output has {len(outputs)} entries for {n} sectors"
        )

    a = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            a[i][j] = x[i][j] / outputs[j]  # EQ=BEN-IO-A-01 | REF=REF-EGY-IO-ALAYOUTY-2022 | TITLE=Identifying Activities for Greater Employment Generation in Egypt: An Input-Output Analysis | AUTHOR=Iman Al-Ayouty | SERIES=AERC GSYE Working Paper GSYE-007 | YEAR=2022 | LOC=methodology p.11, technical coefficients | DOI=n/a | URL=https://publication.aercafricalibrary.org/items/035e42e5-5fbb-416e-932a-494a2fd50965
    return a


def leontief_inverse(a_matrix, *, condition_limit: float = 1e12) -> list[list[float]]:
    """BEN-IO-L-01 — total-requirements matrix L = (I - A)^-1.

    A near-singular I - A means the economy described by A absorbs its own
    output without limit; the inverse then amplifies rounding error into
    plausible-looking multipliers. That raises rather than falling back to a
    pseudo-inverse, which no source here authorises.
    """
    eq = "BEN-IO-L-01"
    a = _as_square_matrix(a_matrix, equation_id=eq, name="A_matrix")
    n = len(a)

    try:
        import numpy as np
    except ImportError:  # pragma: no cover - numpy is a declared dependency
        raise ScientificBenefitInputError(
            f"{eq}: numpy is required for the Leontief inverse"
        ) from None

    A = np.asarray(a, dtype=float)
    i_minus_a = np.eye(n) - A
    condition = float(np.linalg.cond(i_minus_a))
    if not math.isfinite(condition) or condition > condition_limit:
        raise ScientificBenefitInputError(
            f"{eq}: (I - A) is singular or ill-conditioned (condition number "
            f"{condition:.3e} exceeds {condition_limit:.0e}); no source here "
            "authorises a pseudo-inverse fallback"
        )

    leontief = np.linalg.inv(np.eye(n) - A)  # EQ=BEN-IO-L-01 | REF=REF-EGY-IO-ALAYOUTY-2022 | TITLE=Identifying Activities for Greater Employment Generation in Egypt: An Input-Output Analysis | AUTHOR=Iman Al-Ayouty | SERIES=AERC GSYE Working Paper GSYE-007 | YEAR=2022 | LOC=methodology p.11, Leontief inverse / total requirements matrix | DOI=n/a | URL=https://publication.aercafricalibrary.org/items/035e42e5-5fbb-416e-932a-494a2fd50965
    return [[float(v) for v in row] for row in leontief]


def io_output_response(leontief, final_demand_change) -> list[float]:
    """BEN-IO-DELTA-01 — output response dx = L dy.

    The demand change must be in the price basis of the I-O table. This result
    is economic ACTIVITY, not a welfare benefit, and must never be added to a
    monetised CBA total.
    """
    eq = "BEN-IO-DELTA-01"
    l_matrix = _as_square_matrix(leontief, equation_id=eq, name="leontief")
    n = len(l_matrix)
    dy = [
        _require_number(v, equation_id=eq, name=f"final_demand_change[{i}]")
        for i, v in enumerate(list(final_demand_change))
    ]
    if len(dy) != n:
        raise ScientificBenefitInputError(
            f"{eq}: final_demand_change has {len(dy)} entries for {n} sectors"
        )

    dx: list[float] = []
    for i in range(n):
        dx.append(sum(l_matrix[i][j] * dy[j] for j in range(n)))  # EQ=BEN-IO-DELTA-01 | REF=REF-EGY-IO-ALAYOUTY-2022 | TITLE=Identifying Activities for Greater Employment Generation in Egypt: An Input-Output Analysis | AUTHOR=Iman Al-Ayouty | SERIES=AERC GSYE Working Paper GSYE-007 | YEAR=2022 | LOC=methodology pp.11-12, application of the Leontief inverse to a final-demand change; DERIVED/APPLIED-METHOD | DOI=n/a | URL=https://publication.aercafricalibrary.org/items/035e42e5-5fbb-416e-932a-494a2fd50965
    return dx


def output_multiplier(leontief) -> list[float]:
    """BEN-IO-OMULT-01 — column sums of the total-requirements matrix."""
    eq = "BEN-IO-OMULT-01"
    l_matrix = _as_square_matrix(leontief, equation_id=eq, name="leontief")
    n = len(l_matrix)

    multipliers: list[float] = []
    for j in range(n):
        multipliers.append(sum(l_matrix[i][j] for i in range(n)))  # EQ=BEN-IO-OMULT-01 | REF=REF-EGY-IO-ALAYOUTY-2022 | TITLE=Identifying Activities for Greater Employment Generation in Egypt: An Input-Output Analysis | AUTHOR=Iman Al-Ayouty | SERIES=AERC GSYE Working Paper GSYE-007 | YEAR=2022 | LOC=methodology pp.11-12, output multiplier as the column sum of the Leontief inverse | DOI=n/a | URL=https://publication.aercafricalibrary.org/items/035e42e5-5fbb-416e-932a-494a2fd50965
    return multipliers


def employment_multiplier(leontief, employment_coefficients) -> list[float]:
    """BEN-IO-EMULT-01 — employment multiplier per sector.

    The result is a RATIO: total employment response per unit of direct
    employment. It is not jobs per EGP and not jobs per USD, so multiplying a
    capital cost by a value of this kind is a category error.
    """
    eq = "BEN-IO-EMULT-01"
    l_matrix = _as_square_matrix(leontief, equation_id=eq, name="leontief")
    n = len(l_matrix)
    w = [
        _require_number(v, equation_id=eq, name=f"employment_coefficient[{i}]")
        for i, v in enumerate(list(employment_coefficients))
    ]
    if len(w) != n:
        raise ScientificBenefitInputError(
            f"{eq}: employment_coefficients has {len(w)} entries for {n} sectors"
        )

    multipliers: list[float] = []
    for j in range(n):
        if w[j] == 0.0:
            raise ScientificBenefitInputError(
                f"{eq}: employment coefficient for sector {j} is zero; the "
                "multiplier is undefined for a sector with no direct employment"
            )
        multipliers.append(sum(w[i] * l_matrix[i][j] for i in range(n)) / w[j])  # EQ=BEN-IO-EMULT-01 | REF=REF-EGY-IO-ALAYOUTY-2022 | TITLE=Identifying Activities for Greater Employment Generation in Egypt: An Input-Output Analysis | AUTHOR=Iman Al-Ayouty | SERIES=AERC GSYE Working Paper GSYE-007 | YEAR=2022 | LOC=methodology p.12, employment multiplier | DOI=n/a | URL=https://publication.aercafricalibrary.org/items/035e42e5-5fbb-416e-932a-494a2fd50965
    return multipliers


def jobs_proxy(investment_million_constant_2015_usd, job_content_per_musd) -> float:
    """BEN-JOBS-PROXY-01 — benchmark jobs supported per unit of investment.

    A cross-country emerging-market benchmark on a constant-2015-USD basis. The
    result is labelled as a proxy everywhere it appears, is never described as
    Cairo jobs created, and is never added to officially reported project jobs —
    the two answer different questions from different evidence.
    """
    eq = "BEN-JOBS-PROXY-01"
    investment = _require_non_negative(
        investment_million_constant_2015_usd,
        equation_id=eq,
        name="investment_million_constant_2015_usd",
    )
    job_content = _require_non_negative(
        job_content_per_musd, equation_id=eq, name="job_content_per_musd"
    )

    proxy_jobs = investment * job_content  # EQ=BEN-JOBS-PROXY-01 | REF=REF-MOSZORO-2024 | TITLE=The direct employment impact of public investment | AUTHOR=Marian W. Moszoro | JOURNAL=International Journal of Management and Economics 60(1), 59-74 | YEAR=2024 | LOC=results tables reporting jobs per US$1 million; monetary data standardised to constant 2015 USD using GDP deflators | DOI=10.2478/ijme-2023-0020 | URL=https://reference-global.com/article/10.2478/ijme-2023-0020
    return proxy_jobs


# ---------------------------------------------------------------------------
# Noise
# ---------------------------------------------------------------------------


def physical_noise_delta(
    *,
    receptor_id: str,
    metric: str,
    assessment_period: str,
    baseline_db,
    project_db,
) -> dict:
    """BEN-NOISE-PHYS-01 — signed dB difference at ONE receptor, one metric.

    Deliberately absent from the return value: any percentage. dB is a
    logarithmic scale, so `delta / baseline` is not a percentage reduction in
    sound energy or in perceived loudness — it is a ratio of two numbers on a
    scale where that ratio has no acoustic meaning.

    Also deliberately absent: any cross-receptor aggregate. Arithmetic averaging
    of decibel values across receptors understates the loud ones.
    """
    eq = "BEN-NOISE-PHYS-01"
    if not str(receptor_id).strip():
        raise ScientificBenefitInputError(f"{eq}: receptor_id is required")
    if not str(metric).strip():
        raise ScientificBenefitInputError(
            f"{eq}: metric is required (e.g. Lden or Lnight per Directive 2002/49/EC)"
        )
    if not str(assessment_period).strip():
        raise ScientificBenefitInputError(f"{eq}: assessment_period is required")

    baseline_db = _require_number(baseline_db, equation_id=eq, name="baseline_db")
    project_db = _require_number(project_db, equation_id=eq, name="project_db")

    noise_delta_db = baseline_db - project_db  # EQ=BEN-NOISE-PHYS-01 | REF=REF-EU-NOISE-2002;REF-EU-CNOSSOS-2015 | TITLE=Directive 2002/49/EC relating to the assessment and management of environmental noise; Commission Directive (EU) 2015/996 establishing common noise assessment methods | ISSUER=European Parliament and Council; European Commission | LOC=same-indicator baseline/project comparison at one receptor using a documented Lden/Lnight or explicitly sourced metric | DOI=n/a | URL=https://eur-lex.europa.eu/eli/dir/2002/49/oj/eng
    if noise_delta_db > 0.0:
        direction = "benefit"
    elif noise_delta_db < 0.0:
        direction = "disbenefit"
    else:
        direction = "neutral"
    return {
        "receptor_id": str(receptor_id),
        "metric": str(metric),
        "assessment_period": str(assessment_period),
        "baseline_db": baseline_db,
        "project_db": project_db,
        "noise_delta_db": noise_delta_db,
        "benefit_direction": direction,
    }


def physical_noise_deltas(rows: Sequence[dict]) -> list[dict]:
    """Apply BEN-NOISE-PHYS-01 receptor by receptor, with no aggregation.

    Returns one row per receptor. There is no mean, no total and no "overall
    reduction", because none of those has a defensible definition on a
    logarithmic scale without exposed-population weighting that the evidence
    does not yet supply.
    """
    eq = "BEN-NOISE-PHYS-01"
    if rows is None:
        return []
    results: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ScientificBenefitInputError(
                f"{eq}: noise row {index} is not a mapping"
            )
        key = (
            str(row.get("receptor_id", "")),
            str(row.get("metric", "")),
            str(row.get("assessment_period", "")),
        )
        if key in seen:
            raise ScientificBenefitInputError(
                f"{eq}: duplicate receptor/metric/period {key}; a receptor may "
                "appear once per metric and period"
            )
        seen.add(key)
        results.append(
            physical_noise_delta(
                receptor_id=row.get("receptor_id", ""),
                metric=row.get("metric", ""),
                assessment_period=row.get("assessment_period", ""),
                baseline_db=row.get("baseline_db"),
                project_db=row.get("project_db"),
            )
        )
    return results
