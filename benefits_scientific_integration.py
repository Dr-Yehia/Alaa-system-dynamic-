"""Evidence-aware orchestration inside the Benefits domain.

WHAT THIS LAYER DECIDES
-----------------------
`benefits_scientific_core` knows how to compute. It does not know whether the
numbers it was handed are allowed to be published. That judgement lives here.

For every KPI this module asks two separate questions:

  1. Do I have the quantities the equation needs?  -> computed / SOURCE-OPEN
  2. Is each quantity backed by evidence that can carry a project claim?
                                                   -> eligible / SCENARIO-ONLY /
                                                      PROXY / OFFICIAL-REPORTED

The second question is the one that matters, because a value can be perfectly
computable and still unpublishable. The green bond report's 30% modal-shift
scenario produces a number; it does not produce a Cairo measurement. A UK
emission factor multiplies cleanly; it is still not an Egyptian factor. So each
input arrives wrapped in an `EvidenceValue` and is checked against its declared
status before its result may be labelled a project finding.

    METHOD-REFERENCE supports the formula. It never certifies the number.

WHAT THIS LAYER NEVER DOES
--------------------------
It contains no equation — every arithmetic operation is a call into the core.
It never substitutes a default for a missing value: an absent quantity produces
an explicit SOURCE-OPEN state, never a zero that looks like a measurement. It
never sums across evidence classes, so officially reported project jobs and
proxy benchmark jobs stay in separate fields with no total. And it produces no
single "Total Benefits" figure, because physical tonnes, monetised hours,
economic output and job counts are four different kinds of thing.

It imports the Benefits core and registry, plus the neutral `project_context`
and `shared_activity` layers. It imports no LCA engine, no LCC engine and no
Streamlit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import benefits_scientific_core as core
from benefits_reference_registry import (
    BLOCKED_TOPICS,
    EQUATIONS,
    METHOD_EVIDENCE_CLASSES,
    PUBLICATION_ACCEPTABLE_NUMERIC_EVIDENCE,
    REFERENCES,
)
from benefits_scientific_core import EvidenceValue, ScientificBenefitInputError


# ---------------------------------------------------------------------------
# KPI states
# ---------------------------------------------------------------------------

#: The quantities exist and are backed by project or official project data.
STATUS_COMPUTED = "COMPUTED"
#: Computable, but at least one input rests on a method or scenario source.
STATUS_SCENARIO_ONLY = "SCENARIO-ONLY"
#: Computable, but the basis is an external benchmark rather than this project.
STATUS_PROXY = "PROXY"
#: Reported directly by an official project document; no equation involved.
STATUS_OFFICIAL_REPORTED = "OFFICIAL-REPORTED"
#: At least one required quantity has no evidence at all.
STATUS_SOURCE_OPEN = "SOURCE-OPEN"
#: The KPI does not apply to this run (e.g. no noise study was carried out).
STATUS_NOT_APPLICABLE = "NOT-APPLICABLE"
#: Deliberately not implemented; the evidence to define it does not exist yet.
STATUS_BLOCKED = "BLOCKED"

#: Only these states may carry a project headline in Publication mode.
PUBLICATION_ELIGIBLE_STATES = frozenset({STATUS_COMPUTED, STATUS_OFFICIAL_REPORTED})


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScientificBenefitsResult:
    """Four separate result groups, plus the audit and the gate.

    The groups are not merged on purpose. Avoided tonnes, monetised time, gross
    economic output and job counts answer different questions from different
    evidence, and adding them would produce a number with no defensible unit.
    """

    physical: dict = field(default_factory=dict)
    monetized_cba: dict = field(default_factory=dict)
    economic_impact: dict = field(default_factory=dict)
    employment: dict = field(default_factory=dict)
    audit: dict = field(default_factory=dict)
    publication_gate: dict = field(default_factory=dict)

    @property
    def rows(self) -> list[dict]:
        """Flat KPI rows, ready for tables and exports."""
        return list(self.audit.get("kpi_rows", []))


# ---------------------------------------------------------------------------
# Evidence coercion and checking
# ---------------------------------------------------------------------------

_EVIDENCE_FIELDS = (
    "value",
    "unit",
    "source_ref_id",
    "source_file",
    "source_location",
    "geography",
    "evidence_status",
    "price_base_year",
    "currency",
    "factor_basis",
    "note",
)


def evidence_from_dict(raw: Any) -> Optional[EvidenceValue]:
    """Accept an EvidenceValue, a plain mapping, or nothing.

    The UI collects evidence as a dictionary because that is what a form
    produces. A bare number is deliberately NOT accepted: a value without a unit
    and a source is exactly the thing this whole layer exists to refuse.
    """
    if raw is None:
        return None
    if isinstance(raw, EvidenceValue):
        return raw
    if isinstance(raw, dict):
        if raw.get("value") is None:
            return None
        return EvidenceValue(
            value=raw.get("value"),
            unit=str(raw.get("unit", "") or ""),
            source_ref_id=str(raw.get("source_ref_id", "") or ""),
            source_file=str(raw.get("source_file", "") or ""),
            source_location=str(raw.get("source_location", "") or ""),
            geography=str(raw.get("geography", "") or ""),
            evidence_status=str(raw.get("evidence_status", "") or "SOURCE-OPEN"),
            price_base_year=raw.get("price_base_year"),
            currency=raw.get("currency"),
            factor_basis=raw.get("factor_basis"),
            note=str(raw.get("note", "") or ""),
        )
    return None


@dataclass
class _EvidenceCheck:
    """The verdict on one set of inputs feeding one KPI."""

    missing: list[str] = field(default_factory=list)
    incomplete: list[str] = field(default_factory=list)
    method_only: list[str] = field(default_factory=list)
    proxy: list[str] = field(default_factory=list)
    historical: list[str] = field(default_factory=list)
    refs: list[str] = field(default_factory=list)
    titles: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    geographies: list[str] = field(default_factory=list)
    statuses: list[str] = field(default_factory=list)
    currency: Optional[str] = None
    price_base_year: Optional[int] = None
    notes: list[str] = field(default_factory=list)

    @property
    def usable(self) -> bool:
        """True when every required input has a value that can be computed with."""
        return not self.missing and not self.incomplete

    def status(self) -> str:
        if not self.usable:
            return STATUS_SOURCE_OPEN
        if self.proxy:
            return STATUS_PROXY
        if self.method_only or self.historical:
            return STATUS_SCENARIO_ONLY
        return STATUS_COMPUTED


def _check_evidence(named_inputs: dict, *, require_money: bool = False) -> _EvidenceCheck:
    """Inspect a KPI's inputs and classify the evidence behind each one.

    `named_inputs` maps a human-readable input name to an `EvidenceValue` or
    None. Completeness is judged on what a reviewer would need to check the
    number: a value, a unit, a reference id, an exact location and a geography.
    """
    result = _EvidenceCheck()

    for name, ev in named_inputs.items():
        if ev is None or ev.value is None:
            result.missing.append(name)
            continue

        gaps = []
        if not str(ev.unit).strip():
            gaps.append("unit")
        if not str(ev.source_ref_id).strip():
            gaps.append("source reference")
        if not str(ev.source_location).strip():
            gaps.append("exact source location")
        if not str(ev.geography).strip():
            gaps.append("geography")
        if require_money:
            if not (ev.currency and str(ev.currency).strip()):
                gaps.append("currency")
            if ev.price_base_year is None:
                gaps.append("price base year")
        if gaps:
            result.incomplete.append(f"{name} (missing {', '.join(gaps)})")
            continue

        status = str(ev.evidence_status).strip().upper()
        result.statuses.append(status)
        if status in METHOD_EVIDENCE_CLASSES:
            result.method_only.append(name)
        elif status == "REF-PROXY":
            result.proxy.append(name)
        elif status in {"HISTORICAL", "SCENARIO-ONLY"}:
            result.historical.append(name)
        elif status not in PUBLICATION_ACCEPTABLE_NUMERIC_EVIDENCE:
            # SOURCE-OPEN, BLOCKED or an unrecognised label: not usable evidence.
            result.incomplete.append(f"{name} (evidence status {status})")
            continue

        ref_id = str(ev.source_ref_id).strip()
        result.refs.append(ref_id)
        record = REFERENCES.get(ref_id)
        result.titles.append(record.title if record else ref_id)
        result.files.append(str(ev.source_file or (record.local_source_file if record else "")))
        result.locations.append(str(ev.source_location))
        result.geographies.append(str(ev.geography))
        if ev.currency and result.currency is None:
            result.currency = str(ev.currency)
        if ev.price_base_year is not None and result.price_base_year is None:
            result.price_base_year = int(ev.price_base_year)
        if ev.note:
            result.notes.append(f"{name}: {ev.note}")

    return result


def _value(ev: Optional[EvidenceValue]):
    return None if ev is None else ev.value


# ---------------------------------------------------------------------------
# Audit row assembly
# ---------------------------------------------------------------------------


def _equation_meta(equation_id: Optional[str]) -> dict:
    if not equation_id or equation_id not in EQUATIONS:
        return {
            "method_ref_ids": "",
            "method_titles": "",
            "method_locations": "",
            "method_doi": "",
            "method_url": "",
            "limitations": "",
            "double_count_rule": "",
        }
    eq = EQUATIONS[equation_id]
    records = [REFERENCES[r] for r in eq.method_ref_ids if r in REFERENCES]
    return {
        "method_ref_ids": "; ".join(eq.method_ref_ids),
        "method_titles": "; ".join(r.title for r in records),
        "method_locations": " | ".join(eq.exact_source_locations),
        "method_doi": "; ".join(r.doi for r in records),
        "method_url": "; ".join(r.official_url for r in records),
        "limitations": eq.limitations,
        "double_count_rule": eq.double_count_rule,
    }


def _row(
    *,
    kpi_id: str,
    kpi_name: str,
    equation_id: Optional[str],
    value,
    unit: str,
    result_group: str,
    status: str,
    check: Optional[_EvidenceCheck] = None,
    note: str = "",
    currency: Optional[str] = None,
    price_base_year: Optional[int] = None,
) -> dict:
    """Build one fully traceable KPI row.

    Every column a reviewer needs to walk from the displayed number back to the
    original document is populated here, so the exports never have to guess.
    """
    meta = _equation_meta(equation_id)
    check = check or _EvidenceCheck()
    eligible = status in PUBLICATION_ELIGIBLE_STATES and value is not None

    gaps = list(check.missing) + list(check.incomplete)
    return {
        "kpi_id": kpi_id,
        "kpi_name": kpi_name,
        "equation_id": equation_id or "",
        "value": value,
        "unit": unit,
        "result_group": result_group,
        "status": status,
        "evidence_status": "; ".join(sorted(set(check.statuses))) if check.statuses else status,
        "method_ref_ids": meta["method_ref_ids"],
        "numeric_source_ref_ids": "; ".join(sorted(set(check.refs))),
        "source_title": "; ".join(sorted(set(check.titles))) or meta["method_titles"],
        "source_file": "; ".join(sorted({f for f in check.files if f})),
        "source_location": " | ".join(sorted(set(check.locations))) or meta["method_locations"],
        "method_source_title": meta["method_titles"],
        "method_source_location": meta["method_locations"],
        "doi": meta["method_doi"],
        "official_url": meta["method_url"],
        "geography": "; ".join(sorted(set(check.geographies))),
        "currency": currency or check.currency or "",
        "price_base_year": price_base_year if price_base_year is not None else check.price_base_year,
        "limitations": meta["limitations"],
        "double_count_rule": meta["double_count_rule"],
        "publication_eligible": bool(eligible),
        "evidence_gaps": "; ".join(gaps),
        "note": "; ".join([n for n in ([note] + check.notes) if n]),
    }


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------


def _section_transport_physical(transport: dict, shared, rows: list[dict]) -> dict:
    """Passenger activity, modal shift and avoided emissions — physical only."""
    out: dict = {}

    passengers = evidence_from_dict(transport.get("passengers_per_day"))
    distance = evidence_from_dict(transport.get("avg_distance_km"))
    days = evidence_from_dict(transport.get("operating_days_per_year"))

    pkm_check = _check_evidence(
        {
            "passengers_per_day": passengers,
            "avg_distance_km": distance,
            "operating_days_per_year": days,
        }
    )

    annual_pkm = None
    pkm_status = pkm_check.status()
    pkm_note = ""

    if pkm_check.usable:
        try:
            annual_pkm = core.annual_passenger_km(
                _value(passengers), _value(distance), _value(days)
            )
        except ScientificBenefitInputError as exc:
            pkm_status = STATUS_SOURCE_OPEN
            pkm_note = str(exc)
    else:
        # The neutral activity layer may already carry passenger-km computed
        # upstream. Using it is allowed, but its provenance did not pass through
        # this evidence gate, so it can never be publication-eligible here.
        shared_pkm = float(getattr(shared, "served_annual_pkm", 0.0) or 0.0)
        if shared_pkm > 0.0:
            annual_pkm = shared_pkm
            pkm_status = STATUS_SCENARIO_ONLY
            pkm_note = (
                "taken from the neutral SharedActivity layer, not from Benefits "
                "evidence; the upstream ridership, trip length and operating-day "
                "provenance was not supplied to this gate"
            )

    out["annual_passenger_km"] = annual_pkm
    out["annual_passenger_km_status"] = pkm_status
    rows.append(
        _row(
            kpi_id="BEN-KPI-PKM",
            kpi_name="Annual passenger-km",
            equation_id="BEN-PKM-01",
            value=annual_pkm,
            unit="passenger-km/year",
            result_group="physical",
            status=pkm_status,
            check=pkm_check,
            note=pkm_note,
        )
    )

    # --- modal shift -------------------------------------------------------
    modal = evidence_from_dict(transport.get("modal_shift_fraction"))
    modal_check = _check_evidence({"modal_shift_fraction": modal})
    shifted = None
    modal_status = modal_check.status()
    modal_note = ""
    if annual_pkm is not None and modal_check.usable:
        try:
            shifted = core.shifted_passenger_km(annual_pkm, _value(modal))
        except ScientificBenefitInputError as exc:
            modal_status, modal_note = STATUS_SOURCE_OPEN, str(exc)
        # A shifted figure can never be stronger evidence than the activity it
        # was derived from.
        if pkm_status != STATUS_COMPUTED and modal_status == STATUS_COMPUTED:
            modal_status = STATUS_SCENARIO_ONLY
            modal_note = modal_note or "inherits the weaker evidence state of annual passenger-km"
    elif annual_pkm is None:
        modal_status = STATUS_SOURCE_OPEN
        modal_note = "annual passenger-km is not available"

    out["shifted_passenger_km"] = shifted
    out["shifted_passenger_km_status"] = modal_status
    rows.append(
        _row(
            kpi_id="BEN-KPI-MODAL",
            kpi_name="Shifted passenger-km",
            equation_id="BEN-MODAL-01",
            value=shifted,
            unit="passenger-km/year",
            result_group="physical",
            status=modal_status,
            check=modal_check,
            note=modal_note,
        )
    )

    # --- car/bus allocation ------------------------------------------------
    car_share = evidence_from_dict(transport.get("car_share_of_shift"))
    bus_share = evidence_from_dict(transport.get("bus_share_of_shift"))
    split_check = _check_evidence(
        {"car_share_of_shift": car_share, "bus_share_of_shift": bus_share}
    )
    car_pkm = bus_pkm = None
    split_status = split_check.status()
    split_note = ""
    if shifted is not None and split_check.usable:
        try:
            split = core.allocate_shifted_pkm(shifted, _value(car_share), _value(bus_share))
            car_pkm, bus_pkm = split["car_pkm"], split["bus_pkm"]
        except ScientificBenefitInputError as exc:
            split_status, split_note = STATUS_SOURCE_OPEN, str(exc)
        if modal_status != STATUS_COMPUTED and split_status == STATUS_COMPUTED:
            split_status = STATUS_SCENARIO_ONLY
            split_note = split_note or "inherits the weaker evidence state of shifted passenger-km"
    elif shifted is None:
        split_status = STATUS_SOURCE_OPEN
        split_note = "shifted passenger-km is not available"

    out["car_displaced_pkm"] = car_pkm
    out["bus_displaced_pkm"] = bus_pkm
    out["mode_split_status"] = split_status
    rows.append(
        _row(
            kpi_id="BEN-KPI-MODE-SPLIT",
            kpi_name="Displaced passenger-km by mode (car / bus)",
            equation_id="BEN-MODE-SPLIT-01",
            value=None if car_pkm is None else {"car_pkm": car_pkm, "bus_pkm": bus_pkm},
            unit="passenger-km/year",
            result_group="physical",
            status=split_status,
            check=split_check,
            note=split_note,
        )
    )

    # --- avoided emissions -------------------------------------------------
    car_ef = evidence_from_dict(transport.get("car_emission_factor"))
    bus_ef = evidence_from_dict(transport.get("bus_emission_factor"))
    project_ef = evidence_from_dict(transport.get("project_emission_factor"))
    ef_check = _check_evidence(
        {
            "car_emission_factor": car_ef,
            "bus_emission_factor": bus_ef,
            "project_emission_factor": project_ef,
        }
    )

    avoided = None
    direction = ""
    ghg_status = ef_check.status()
    ghg_note = ""
    if car_pkm is not None and ef_check.usable:
        try:
            # Each factor is already expressed in CO2e per passenger-km, so the
            # CO2e route is used and no warming potential is applied a second time.
            baseline = core.emissions_from_co2e_factor(
                car_pkm, _value(car_ef)
            ) + core.emissions_from_co2e_factor(bus_pkm, _value(bus_ef))
            project = core.emissions_from_co2e_factor(shifted, _value(project_ef))
            result = core.avoided_emissions(baseline, project)
            avoided = result["avoided_co2e"]
            direction = result["benefit_direction"]
        except ScientificBenefitInputError as exc:
            ghg_status, ghg_note = STATUS_SOURCE_OPEN, str(exc)
        if split_status != STATUS_COMPUTED and ghg_status == STATUS_COMPUTED:
            ghg_status = STATUS_SCENARIO_ONLY
            ghg_note = ghg_note or "inherits the weaker evidence state of the displaced-mode split"
    elif car_pkm is None:
        ghg_status = STATUS_SOURCE_OPEN
        ghg_note = "displaced passenger-km by mode is not available"

    out["avoided_co2e_kg"] = avoided
    out["avoided_co2e_t"] = None if avoided is None else avoided / 1000.0
    out["avoided_benefit_direction"] = direction
    out["avoided_co2e_status"] = ghg_status
    rows.append(
        _row(
            kpi_id="BEN-KPI-GHG-AVOIDED",
            kpi_name="Avoided greenhouse-gas emissions (signed)",
            equation_id="BEN-GHG-AVOID-01",
            value=None if avoided is None else avoided / 1000.0,
            unit="tCO2e/year (positive = avoided, negative = disbenefit)",
            result_group="physical",
            status=ghg_status,
            check=ef_check,
            note="; ".join(x for x in [ghg_note, f"direction: {direction}" if direction else ""] if x),
        )
    )

    return out


def _section_time(transport: dict, rows: list[dict]) -> tuple[dict, dict]:
    """Passenger-hours saved (physical) and its monetary value (CBA)."""
    physical: dict = {}
    monetized: dict = {}

    trips = evidence_from_dict(transport.get("annual_trips"))
    base_min = evidence_from_dict(transport.get("baseline_time_min"))
    proj_min = evidence_from_dict(transport.get("project_time_min"))

    time_check = _check_evidence(
        {"annual_trips": trips, "baseline_time_min": base_min, "project_time_min": proj_min}
    )

    hours = None
    time_status = time_check.status()
    time_note = ""
    baseline_h = project_h = None
    if time_check.usable:
        try:
            # Surveys report minutes; value of time is per hour. The conversion is
            # a named step so it cannot hide inside the multiplication.
            baseline_h = core.minutes_to_hours(_value(base_min))
            project_h = core.minutes_to_hours(_value(proj_min))
            hours = core.passenger_hours_saved(_value(trips), baseline_h, project_h)
        except ScientificBenefitInputError as exc:
            time_status, time_note = STATUS_SOURCE_OPEN, str(exc)

    physical["passenger_hours_saved"] = hours
    physical["passenger_hours_saved_status"] = time_status
    rows.append(
        _row(
            kpi_id="BEN-KPI-TIME-SAVED",
            kpi_name="Passenger-hours saved (signed)",
            equation_id="BEN-TIME-01",
            value=hours,
            unit="passenger-hours/year",
            result_group="physical",
            status=time_status,
            check=time_check,
            note=time_note,
        )
    )

    # --- monetisation ------------------------------------------------------
    vot = evidence_from_dict(transport.get("value_of_time"))
    # Money needs more than a source: it needs a currency and a price base year,
    # or the result silently mixes price levels.
    vot_check = _check_evidence({"value_of_time": vot}, require_money=True)

    time_money = None
    money_status = vot_check.status()
    money_note = ""
    if hours is not None and vot_check.usable:
        try:
            time_money = core.monetize_time_saving(hours, _value(vot))
        except ScientificBenefitInputError as exc:
            money_status, money_note = STATUS_SOURCE_OPEN, str(exc)
        if time_status != STATUS_COMPUTED and money_status == STATUS_COMPUTED:
            money_status = STATUS_SCENARIO_ONLY
            money_note = money_note or "inherits the weaker evidence state of passenger-hours saved"
    elif hours is None:
        money_status = STATUS_SOURCE_OPEN
        money_note = "passenger-hours saved is not available"

    monetized["time_saving_value"] = time_money
    monetized["time_saving_value_status"] = money_status
    monetized["currency"] = vot_check.currency
    monetized["price_base_year"] = vot_check.price_base_year
    rows.append(
        _row(
            kpi_id="BEN-KPI-TIME-VALUE",
            kpi_name="Value of time savings (existing passengers, full benefit)",
            equation_id="BEN-TIME-MONEY-01",
            value=time_money,
            unit=f"{vot_check.currency or 'currency'}/year",
            result_group="monetized_cba",
            status=money_status,
            check=vot_check,
            note=money_note,
        )
    )

    # --- generated traffic, Rule of Half -----------------------------------
    generated = evidence_from_dict(transport.get("generated_trips"))
    gen_check = _check_evidence({"generated_trips": generated})
    gen_value = None
    gen_status = gen_check.status()
    gen_note = ""
    if gen_check.usable and vot_check.usable and baseline_h is not None:
        try:
            gen_value = core.generated_traffic_benefit_rule_of_half(
                _value(generated), baseline_h - project_h, _value(vot)
            )
        except ScientificBenefitInputError as exc:
            gen_status, gen_note = STATUS_SOURCE_OPEN, str(exc)
        if money_status != STATUS_COMPUTED and gen_status == STATUS_COMPUTED:
            gen_status = STATUS_SCENARIO_ONLY
            gen_note = gen_note or "inherits the weaker evidence state of the time valuation"
    elif not gen_check.usable:
        gen_status = STATUS_SOURCE_OPEN
        gen_note = "no generated-traffic estimate supplied"
    else:
        gen_status = STATUS_SOURCE_OPEN
        gen_note = "value of time or travel-time evidence is not available"

    monetized["generated_traffic_value"] = gen_value
    monetized["generated_traffic_value_status"] = gen_status
    rows.append(
        _row(
            kpi_id="BEN-KPI-GEN-TRAFFIC",
            kpi_name="Generated-traffic benefit (Rule of Half — generated trips only)",
            equation_id="BEN-GEN-TRAFFIC-01",
            value=gen_value,
            unit=f"{vot_check.currency or 'currency'}/year",
            result_group="monetized_cba",
            status=gen_status,
            check=gen_check,
            currency=vot_check.currency,
            price_base_year=vot_check.price_base_year,
            note="; ".join(
                x
                for x in [
                    gen_note,
                    "the half applies to generated trips only; existing passengers "
                    "receive the full benefit through BEN-TIME-MONEY-01",
                ]
                if x
            ),
        )
    )

    return physical, monetized


def _section_land_use(land_use: dict, rows: list[dict]) -> dict:
    """Shannon land-use diversity for the baseline and project states."""
    out: dict = {}

    baseline_areas = land_use.get("baseline_area_by_class") or {}
    project_areas = land_use.get("project_area_by_class") or {}
    schema = list(land_use.get("class_schema") or [])

    status = STATUS_SOURCE_OPEN
    note = ""
    lud_base = lud_proj = lud_delta = None

    if not baseline_areas or not project_areas:
        note = "baseline and/or project land-use areas were not supplied"
    elif set(baseline_areas) != set(project_areas):
        status = STATUS_SOURCE_OPEN
        note = (
            "baseline and project use different land-use classes; the difference "
            f"would measure the schema, not the project (baseline: "
            f"{sorted(baseline_areas)}, project: {sorted(project_areas)})"
        )
    elif schema and set(schema) != set(baseline_areas):
        status = STATUS_SOURCE_OPEN
        note = "the declared class schema does not match the supplied area classes"
    else:
        try:
            lud_base = core.normalized_land_use_diversity(core.land_use_shares(baseline_areas))
            lud_proj = core.normalized_land_use_diversity(core.land_use_shares(project_areas))
            lud_delta = core.land_use_diversity_delta(lud_proj, lud_base)
            # Land-use maps are project spatial data; they are project-specific
            # only when their source and date are declared.
            source = str(land_use.get("analysis_area_source", "") or "")
            status = STATUS_COMPUTED if source.strip() else STATUS_SCENARIO_ONLY
            if not source.strip():
                note = "no GIS source and date declared for the land-use maps"
        except ScientificBenefitInputError as exc:
            status, note = STATUS_SOURCE_OPEN, str(exc)

    out["lud_baseline"] = lud_base
    out["lud_project"] = lud_proj
    out["lud_delta"] = lud_delta
    out["lud_status"] = status
    out["analysis_area_id"] = land_use.get("analysis_area_id", "")
    out["analysis_area_source"] = land_use.get("analysis_area_source", "")

    check = _EvidenceCheck()
    if status != STATUS_SOURCE_OPEN:
        check.geographies.append(str(land_use.get("analysis_area_id", "") or "project analysis area"))
        check.locations.append(str(land_use.get("analysis_area_source", "") or ""))

    for kpi_id, name, eq_id, val in (
        ("BEN-KPI-LUD-BASE", "Land-use diversity — baseline", "BEN-LUD-01", lud_base),
        ("BEN-KPI-LUD-PROJ", "Land-use diversity — project", "BEN-LUD-01", lud_proj),
        ("BEN-KPI-LUD-DELTA", "Land-use diversity change", "BEN-LUD-DELTA-01", lud_delta),
    ):
        rows.append(
            _row(
                kpi_id=kpi_id,
                kpi_name=name,
                equation_id=eq_id,
                value=val,
                unit="dimensionless index (0-1)",
                result_group="physical",
                status=status,
                check=check,
                note=note,
            )
        )

    # The influence radius is a policy benchmark elsewhere; here it must be
    # project evidence or it stays open.
    radius = evidence_from_dict(land_use.get("influence_radius_m"))
    radius_check = _check_evidence({"influence_radius_m": radius})
    out["influence_radius_m"] = _value(radius)
    out["influence_radius_status"] = radius_check.status()
    rows.append(
        _row(
            kpi_id="BEN-KPI-TOD-RADIUS",
            kpi_name="TOD influence radius",
            equation_id=None,
            value=_value(radius),
            unit="m",
            result_group="physical",
            status=radius_check.status(),
            check=radius_check,
            note=(
                "the 500-800 m band in the Indian national TOD policy is a policy "
                "benchmark, not the Cairo project radius; project planning or GIS "
                "evidence is required"
            ),
        )
    )

    return out


def _section_urban_growth(urban: dict, rows: list[dict]) -> dict:
    """SDG 11.3.1 land consumption, population growth and their ratio."""
    out: dict = {}

    bu_past = evidence_from_dict(urban.get("built_up_past"))
    bu_present = evidence_from_dict(urban.get("built_up_present"))
    pop_past = evidence_from_dict(urban.get("population_past"))
    pop_present = evidence_from_dict(urban.get("population_present"))

    past_year = urban.get("past_year")
    present_year = urban.get("present_year")
    period_years = None
    if past_year is not None and present_year is not None:
        try:
            period_years = float(int(present_year) - int(past_year))
        except (TypeError, ValueError):
            period_years = None

    bu_check = _check_evidence({"built_up_past": bu_past, "built_up_present": bu_present})
    pop_check = _check_evidence(
        {"population_past": pop_past, "population_present": pop_present}
    )

    change_pct = lcr = pgr = None
    ratio_value = None
    ratio_status_text = ""

    bu_status = bu_check.status()
    bu_note = ""
    if bu_check.usable:
        try:
            change_pct = core.built_up_change_pct(_value(bu_past), _value(bu_present))
        except ScientificBenefitInputError as exc:
            bu_status, bu_note = STATUS_SOURCE_OPEN, str(exc)

    lcr_status = bu_status
    lcr_note = bu_note
    if bu_check.usable and period_years and period_years > 0:
        try:
            lcr = core.land_consumption_rate(_value(bu_past), _value(bu_present), period_years)
        except ScientificBenefitInputError as exc:
            lcr_status, lcr_note = STATUS_SOURCE_OPEN, str(exc)
    elif bu_check.usable:
        lcr_status = STATUS_SOURCE_OPEN
        lcr_note = (
            "no real elapsed analysis period was supplied; SDG 11.3.1 is defined "
            "over actual years, so a scenario difference cannot stand in for one"
        )

    pgr_status = pop_check.status()
    pgr_note = ""
    if pop_check.usable and period_years and period_years > 0:
        try:
            pgr = core.population_growth_rate(
                _value(pop_past), _value(pop_present), period_years
            )
        except ScientificBenefitInputError as exc:
            pgr_status, pgr_note = STATUS_SOURCE_OPEN, str(exc)
    elif pop_check.usable:
        pgr_status = STATUS_SOURCE_OPEN
        pgr_note = "no real elapsed analysis period was supplied"

    ratio_status = STATUS_SOURCE_OPEN
    ratio_note = "land consumption rate and/or population growth rate unavailable"
    if lcr is not None and pgr is not None:
        ratio = core.lcr_pgr_ratio(
            lcr, pgr, lcr_period_years=period_years, pgr_period_years=period_years
        )
        ratio_value = ratio["lcr_pgr"]
        ratio_status_text = ratio["status"]
        if ratio["status"] == "UNDEFINED":
            ratio_status = STATUS_NOT_APPLICABLE
            ratio_note = ratio["diagnostic"]
        else:
            ratio_status = STATUS_COMPUTED if (
                lcr_status == STATUS_COMPUTED and pgr_status == STATUS_COMPUTED
            ) else STATUS_SCENARIO_ONLY
            ratio_note = ""

    per_capita = None
    pc_status = STATUS_SOURCE_OPEN
    pc_note = "built-up area and/or present population unavailable"
    if bu_check.usable and pop_check.usable:
        try:
            per_capita = core.built_up_area_per_capita(
                _value(bu_present), _value(pop_present)
            )
            pc_status = (
                STATUS_COMPUTED
                if bu_status == STATUS_COMPUTED and pgr_status != STATUS_SOURCE_OPEN
                else STATUS_SCENARIO_ONLY
            )
            pc_note = ""
        except ScientificBenefitInputError as exc:
            pc_status, pc_note = STATUS_SOURCE_OPEN, str(exc)

    out.update(
        {
            "built_up_change_pct": change_pct,
            "built_up_change_status": bu_status,
            "land_consumption_rate": lcr,
            "land_consumption_rate_status": lcr_status,
            "population_growth_rate": pgr,
            "population_growth_rate_status": pgr_status,
            "lcr_pgr": ratio_value,
            "lcr_pgr_status": ratio_status,
            "lcr_pgr_definition_state": ratio_status_text,
            "built_up_per_capita_m2": per_capita,
            "built_up_per_capita_status": pc_status,
            "analysis_period_years": period_years,
        }
    )

    rows.append(_row(kpi_id="BEN-KPI-BUILTUP-CHANGE", kpi_name="Total built-up area change",
                     equation_id="BEN-BUILTUP-CHANGE-01", value=change_pct, unit="%",
                     result_group="physical", status=bu_status, check=bu_check, note=bu_note))
    rows.append(_row(kpi_id="BEN-KPI-LCR", kpi_name="Land consumption rate",
                     equation_id="BEN-LCR-01", value=lcr, unit="per year",
                     result_group="physical", status=lcr_status, check=bu_check, note=lcr_note))
    rows.append(_row(kpi_id="BEN-KPI-PGR", kpi_name="Population growth rate",
                     equation_id="BEN-PGR-01", value=pgr, unit="per year",
                     result_group="physical", status=pgr_status, check=pop_check, note=pgr_note))
    rows.append(_row(kpi_id="BEN-KPI-LCRPGR", kpi_name="Ratio of land consumption to population growth",
                     equation_id="BEN-LCRPGR-01", value=ratio_value, unit="dimensionless ratio",
                     result_group="physical", status=ratio_status, check=bu_check, note=ratio_note))
    rows.append(_row(kpi_id="BEN-KPI-BUILTUP-PC", kpi_name="Built-up area per capita",
                     equation_id="BEN-BUILTUP-PC-01", value=per_capita, unit="m2/person",
                     result_group="physical", status=pc_status, check=pop_check, note=pc_note))

    return out


def _section_input_output(io_inputs: dict, rows: list[dict]) -> dict:
    """Leontief output response — economic ACTIVITY, never a welfare benefit."""
    out: dict = {}

    a_ev = evidence_from_dict(io_inputs.get("A_matrix"))
    demand_ev = evidence_from_dict(io_inputs.get("final_demand_change"))
    labels = list(io_inputs.get("sector_labels") or [])

    io_check = _check_evidence({"A_matrix": a_ev, "final_demand_change": demand_ev})

    output_response = None
    multipliers = None
    total_output_response = None
    status = io_check.status()
    note = ""

    if io_check.usable:
        try:
            leontief = core.leontief_inverse(_value(a_ev))
            output_response = core.io_output_response(leontief, _value(demand_ev))
            multipliers = core.output_multiplier(leontief)
            total_output_response = sum(output_response)
            if labels and len(labels) != len(output_response):
                status = STATUS_SOURCE_OPEN
                note = (
                    f"{len(labels)} sector labels for {len(output_response)} sectors; "
                    "an unlabelled response cannot be interpreted"
                )
                output_response = multipliers = total_output_response = None
        except ScientificBenefitInputError as exc:
            status, note = STATUS_SOURCE_OPEN, str(exc)

    # The reviewed Egyptian table is 2016-2017. Presenting its multipliers as a
    # 2026 project fact is exactly the over-claim the registry warns about.
    if status == STATUS_COMPUTED and any(
        s in {"HISTORICAL", "REF-PROXY"} for s in io_check.statuses
    ):
        status = STATUS_SCENARIO_ONLY

    out.update(
        {
            "sector_labels": labels,
            "output_response": output_response,
            "output_multipliers": multipliers,
            "total_output_response": total_output_response,
            "status": status,
            "basis_note": (
                "Leontief output response measures economic activity generated by a "
                "final-demand change. It is NOT a welfare benefit and is never added "
                "to monetised time savings."
            ),
        }
    )

    rows.append(
        _row(
            kpi_id="BEN-KPI-IO-OUTPUT",
            kpi_name="Total output response to the final-demand change",
            equation_id="BEN-IO-DELTA-01",
            value=total_output_response,
            unit="monetary units in the price basis of the input-output table",
            result_group="economic_impact",
            status=status,
            check=io_check,
            note="; ".join(
                x
                for x in [
                    note,
                    "economic activity, not a CBA welfare benefit",
                ]
                if x
            ),
        )
    )
    rows.append(
        _row(
            kpi_id="BEN-KPI-IO-OMULT",
            kpi_name="Sector output multipliers",
            equation_id="BEN-IO-OMULT-01",
            value=multipliers,
            unit="dimensionless multiplier per sector",
            result_group="economic_impact",
            status=status,
            check=io_check,
            note=note,
        )
    )

    return out


def _section_employment(employment: dict, rows: list[dict]) -> dict:
    """Official reported jobs and benchmark proxy jobs — kept strictly apart."""
    out: dict = {}

    official_con = evidence_from_dict(employment.get("official_construction_jobs"))
    official_ops = evidence_from_dict(employment.get("official_operational_jobs"))
    con_check = _check_evidence({"official_construction_jobs": official_con})
    ops_check = _check_evidence({"official_operational_jobs": official_ops})

    def _official_status(check: _EvidenceCheck) -> str:
        if not check.usable:
            return STATUS_SOURCE_OPEN
        if any(s == "OFFICIAL-PROJECT-DATA" for s in check.statuses):
            return STATUS_OFFICIAL_REPORTED
        return STATUS_SCENARIO_ONLY

    con_status = _official_status(con_check)
    ops_status = _official_status(ops_check)

    out["official_reported_construction_jobs"] = _value(official_con)
    out["official_reported_construction_jobs_status"] = con_status
    out["official_reported_operational_jobs"] = _value(official_ops)
    out["official_reported_operational_jobs_status"] = ops_status

    rows.append(
        _row(
            kpi_id="BEN-KPI-JOBS-OFFICIAL-CONSTRUCTION",
            kpi_name="Officially reported construction jobs",
            equation_id=None,
            value=_value(official_con),
            unit="jobs",
            result_group="employment",
            status=con_status,
            check=con_check,
            note="reported figure from an official project document; no equation applied",
        )
    )
    rows.append(
        _row(
            kpi_id="BEN-KPI-JOBS-OFFICIAL-OPERATIONAL",
            kpi_name="Officially reported operational jobs",
            equation_id=None,
            value=_value(official_ops),
            unit="jobs",
            result_group="employment",
            status=ops_status,
            check=ops_check,
            note="reported figure from an official project document; no equation applied",
        )
    )

    # --- proxy benchmark ---------------------------------------------------
    investment = evidence_from_dict(employment.get("proxy_investment_constant_2015_usd_m"))
    job_content = evidence_from_dict(employment.get("jobs_per_musd_proxy"))
    proxy_check = _check_evidence(
        {
            "proxy_investment_constant_2015_usd_m": investment,
            "jobs_per_musd_proxy": job_content,
        }
    )

    proxy_value = None
    proxy_status = STATUS_SOURCE_OPEN
    proxy_note = "no proxy investment and job-content evidence supplied"
    if proxy_check.usable:
        try:
            proxy_value = core.jobs_proxy(_value(investment), _value(job_content))
            # A cross-country benchmark stays a benchmark whatever else is true.
            proxy_status = STATUS_PROXY
            proxy_note = ""
        except ScientificBenefitInputError as exc:
            proxy_status, proxy_note = STATUS_SOURCE_OPEN, str(exc)

    out["proxy_jobs_supported"] = proxy_value
    out["proxy_jobs_supported_status"] = proxy_status
    out["proxy_jobs_label"] = "Model benchmark / proxy jobs supported"

    rows.append(
        _row(
            kpi_id="BEN-KPI-JOBS-PROXY",
            kpi_name="Model benchmark / proxy jobs supported",
            equation_id="BEN-JOBS-PROXY-01",
            value=proxy_value,
            unit="jobs (constant 2015 USD investment basis)",
            result_group="employment",
            status=proxy_status,
            check=proxy_check,
            note="; ".join(
                x
                for x in [
                    proxy_note,
                    "cross-country benchmark; not Cairo jobs created, and never "
                    "added to officially reported project jobs",
                ]
                if x
            ),
        )
    )

    # There is deliberately no total. The two figures answer different questions
    # from different evidence, so a sum would have no defensible meaning.
    out["no_total_reason"] = (
        "Officially reported project jobs and benchmark proxy jobs are separate "
        "evidence products measuring different things. They are reported side by "
        "side and never summed."
    )

    return out


def _section_noise(noise_inputs: dict, rows: list[dict]) -> dict:
    """Physical, per-receptor dB differences. Monetisation stays blocked."""
    out: dict = {}
    raw_rows = list(noise_inputs.get("rows") or [])

    if not raw_rows:
        out["receptors"] = []
        out["status"] = STATUS_NOT_APPLICABLE
        out["note"] = "no acoustic study rows supplied for this assessment"
        rows.append(
            _row(
                kpi_id="BEN-KPI-NOISE-PHYS",
                kpi_name="Receptor noise difference",
                equation_id="BEN-NOISE-PHYS-01",
                value=None,
                unit="dB",
                result_group="physical",
                status=STATUS_NOT_APPLICABLE,
                note="no acoustic study rows supplied for this assessment",
            )
        )
        return out

    prepared = []
    checks: list[_EvidenceCheck] = []
    for row in raw_rows:
        baseline = evidence_from_dict(row.get("baseline_db"))
        project = evidence_from_dict(row.get("project_db"))
        check = _check_evidence({"baseline_db": baseline, "project_db": project})
        checks.append(check)
        prepared.append(
            {
                "receptor_id": str(row.get("receptor_id", "")),
                "metric": row.get("metric", ""),
                "assessment_period": row.get("assessment_period", ""),
                "baseline_db": _value(baseline),
                "project_db": _value(project),
                "_check": check,
            }
        )
    # Each receptor's audit row must cite that receptor's own evidence. Reusing
    # one check for all of them would let a well-sourced receptor vouch for a
    # poorly-sourced one.
    check_by_receptor = {r["receptor_id"]: r["_check"] for r in prepared}

    usable = [r for r in prepared if r["_check"].usable]
    status = STATUS_SOURCE_OPEN
    note = "receptor levels lack complete acoustic evidence"
    receptors: list[dict] = []

    if usable:
        try:
            receptors = core.physical_noise_deltas(
                [{k: v for k, v in r.items() if k != "_check"} for r in usable]
            )
            status = (
                STATUS_COMPUTED
                if all(c.status() == STATUS_COMPUTED for c in checks if c.usable)
                else STATUS_SCENARIO_ONLY
            )
            note = "" if len(usable) == len(prepared) else (
                f"{len(prepared) - len(usable)} receptor row(s) lacked complete evidence "
                "and were not computed"
            )
        except ScientificBenefitInputError as exc:
            status, note = STATUS_SOURCE_OPEN, str(exc)

    out["receptors"] = receptors
    out["status"] = status
    out["note"] = note
    # Deliberately absent: any aggregate level, mean or percentage. dB is
    # logarithmic, so neither an arithmetic mean across receptors nor a
    # delta-over-baseline ratio carries acoustic meaning.
    out["aggregation_note"] = (
        "Per-receptor differences only. Decibel values are not averaged across "
        "receptors and no percentage reduction is derived from a dB difference."
    )

    for receptor in receptors:
        rows.append(
            _row(
                kpi_id=f"BEN-KPI-NOISE-{receptor['receptor_id']}",
                kpi_name=(
                    f"Noise difference at {receptor['receptor_id']} "
                    f"({receptor['metric']}, {receptor['assessment_period']})"
                ),
                equation_id="BEN-NOISE-PHYS-01",
                value=receptor["noise_delta_db"],
                unit="dB (positive = quieter than baseline)",
                result_group="physical",
                status=status,
                check=check_by_receptor.get(receptor["receptor_id"]),
                note=note,
            )
        )

    return out


def _blocked_rows(rows: list[dict]) -> None:
    """Record the deliberately absent KPIs so a reviewer sees why they are missing."""
    for topic_id, reason in BLOCKED_TOPICS.items():
        rows.append(
            _row(
                kpi_id=topic_id,
                kpi_name={
                    "BEN-FORMALIZATION": "Informal-sector formalization benefit",
                    "BEN-CARBON-MONEY": "Monetary value of avoided carbon",
                    "BEN-NOISE-MONEY": "Monetary value of noise reduction",
                }.get(topic_id, topic_id),
                equation_id=None,
                value=None,
                unit="n/a",
                result_group={
                    "BEN-FORMALIZATION": "employment",
                    "BEN-CARBON-MONEY": "monetized_cba",
                    "BEN-NOISE-MONEY": "monetized_cba",
                }.get(topic_id, "monetized_cba"),
                status=STATUS_BLOCKED,
                note=reason,
            )
        )


# ---------------------------------------------------------------------------
# Publication gate
# ---------------------------------------------------------------------------


def _build_gate(rows: list[dict]) -> dict:
    """Decide, per result group, whether anything may carry a project headline."""
    by_group: dict[str, list[dict]] = {}
    for row in rows:
        by_group.setdefault(row["result_group"], []).append(row)

    def group_ready(group: str, kpi_ids: tuple[str, ...] = ()) -> bool:
        candidates = [
            r
            for r in by_group.get(group, [])
            if (not kpi_ids or r["kpi_id"] in kpi_ids)
        ]
        return bool(candidates) and any(r["publication_eligible"] for r in candidates)

    blocked_items = [
        f"{r['kpi_id']}: {r['note']}" for r in rows if r["status"] == STATUS_BLOCKED
    ]
    source_open_items = [
        f"{r['kpi_id']} ({r['kpi_name']}): "
        + (r["evidence_gaps"] or r["note"] or "no evidence supplied")
        for r in rows
        if r["status"] == STATUS_SOURCE_OPEN
    ]
    warnings = [
        f"{r['kpi_id']} ({r['kpi_name']}) is {r['status']} and cannot carry a "
        "project headline"
        for r in rows
        if r["status"] in {STATUS_SCENARIO_ONLY, STATUS_PROXY}
    ]

    physical_ready = group_ready("physical")
    monetized_time_ready = group_ready("monetized_cba", ("BEN-KPI-TIME-VALUE",))
    economic_impact_ready = group_ready("economic_impact")
    employment_ready = group_ready("employment")
    noise_rows = [r for r in rows if r["equation_id"] == "BEN-NOISE-PHYS-01"]
    noise_physical_ready = any(r["publication_eligible"] for r in noise_rows)

    return {
        # The headline gate: at least the physical core must stand on project
        # evidence before Benefits can be presented as a project finding.
        "publication_ready": bool(physical_ready),
        "physical_ready": bool(physical_ready),
        "monetized_time_ready": bool(monetized_time_ready),
        "economic_impact_ready": bool(economic_impact_ready),
        "employment_ready": bool(employment_ready),
        "noise_physical_ready": bool(noise_physical_ready),
        "blocked_items": blocked_items,
        "warnings": warnings,
        "source_open_items": source_open_items,
        "eligible_kpi_ids": [r["kpi_id"] for r in rows if r["publication_eligible"]],
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run_scientific_benefits_from_params(
    *,
    params: dict,
    shared_activity=None,
    project_context=None,
) -> ScientificBenefitsResult:
    """Evaluate the scientific Benefits domain for one assessment run.

    Reads exactly one key from `params`: `benefits_scientific_inputs`. Everything
    else in the application's parameter dictionary belongs to another domain and
    is deliberately not consulted here.

    Never raises on incomplete input. A missing quantity produces an explicit
    SOURCE-OPEN state, because a Benefits panel that vanishes on an empty form
    tells a reviewer less than one that names what is missing.
    """
    params = params or {}
    inputs = params.get("benefits_scientific_inputs") or {}
    if not isinstance(inputs, dict):
        inputs = {}

    rows: list[dict] = []

    transport = inputs.get("transport") or {}
    land_use = inputs.get("land_use") or {}
    urban_growth = inputs.get("urban_growth") or {}
    employment_inputs = inputs.get("employment") or {}
    io_inputs = inputs.get("input_output") or {}
    noise_inputs = inputs.get("noise") or {}

    physical = _section_transport_physical(transport, shared_activity, rows)
    time_physical, monetized = _section_time(transport, rows)
    physical.update(time_physical)
    physical.update(_section_land_use(land_use, rows))
    physical.update(_section_urban_growth(urban_growth, rows))
    physical["noise"] = _section_noise(noise_inputs, rows)

    economic_impact = _section_input_output(io_inputs, rows)
    employment = _section_employment(employment_inputs, rows)

    _blocked_rows(rows)

    gate = _build_gate(rows)

    geography = ""
    currency = ""
    price_base_year = None
    if project_context is not None:
        geography = getattr(project_context, "geography", "") or ""
        currency = getattr(project_context, "currency", "") or ""
        price_base_year = getattr(project_context, "price_base_year", None)

    audit = {
        "kpi_rows": rows,
        "project_geography": geography,
        "project_currency": currency,
        "project_price_base_year": price_base_year,
        "shared_activity_annual_pkm": float(
            getattr(shared_activity, "served_annual_pkm", 0.0) or 0.0
        ),
        "blocked_topics": dict(BLOCKED_TOPICS),
        "status_counts": {
            status: sum(1 for r in rows if r["status"] == status)
            for status in sorted({r["status"] for r in rows})
        },
        "double_count_rules": [
            "Benefits never reduce LCA Gross A-C.",
            "Benefits never reduce LCC NPV.",
            "Economic output is not a welfare benefit and is never added to "
            "monetised time savings.",
            "Officially reported jobs and proxy benchmark jobs are never summed.",
        ],
    }

    return ScientificBenefitsResult(
        physical=physical,
        monetized_cba=monetized,
        economic_impact=economic_impact,
        employment=employment,
        audit=audit,
        publication_gate=gate,
    )
