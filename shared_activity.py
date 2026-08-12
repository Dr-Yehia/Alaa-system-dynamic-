"""Neutral physical activity shared by the assessment domains.

ARCHITECTURAL ROLE
------------------
This is the second neutral layer, beneath `project_context`. It answers one question:
*what does the asset physically do, and when?*

The point of the whole separation is that the same physical fact is consumed twice for
different purposes, and neither consumer should have to ask the other for it:

    shared:   8,000,000 kWh in operating year 12
                    |
        +-----------+------------+
        |                        |
      LCA: kWh x kgCO2e/kWh    LCC: kWh x EGP/kWh

If annual energy lived inside the LCA engine, then the LCC engine would have to import
LCA merely to price electricity — and a change to an emission factor could then move a
cash flow. Routing both through this layer makes that impossible by construction.

STRICTLY FORBIDDEN HERE
-----------------------
  * carbon intensity, emission factors, CO2 of any kind   -> LCA domain
  * tariffs, discount rates, present value, cost          -> LCC domain
  * jobs, time savings, valuation, economic multiplier    -> Benefits domain

`tests/domain_dependency_test.py` enforces these prohibitions mechanically; this module
must never import a domain engine.

WHAT BELONGS HERE
-----------------
Only physical facts that MORE THAN ONE domain actually consumes today:
  * served annual passenger-km          (LCA functional unit; LCC service basis)
  * annual operational electricity kWh  (LCA B6 carbon;       LCC energy cost)
  * the dated B2/B4 intervention schedule (LCA event carbon;  LCC event cost)
  * asset condition state from System Dynamics, when it drives the above

Nothing is invented: every value is derived from the same inputs the monolith already
used, so the separation is behaviour-preserving.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class InterventionEvent:
    """One dated physical intervention on the asset.

    LCA turns it into materials/waste/transport carbon; LCC turns it into money. The
    event itself is neither — it is a fact about what happens in a given year.
    """

    year: int
    b2_count: float = 0.0
    b4_count: float = 0.0
    note: str = ""


@dataclass(frozen=True)
class SharedActivity:
    """The neutral physical activity series for one assessment run.

    Every field is a quantity or a count. There is no factor, price or valuation
    anywhere in this structure — that is what makes it safe for all three domains.
    """

    # Service delivered.
    served_annual_pkm: float = 0.0
    lifetime_pkm: float = 0.0
    # Operational electricity actually consumed per year (kWh/year).
    annual_operational_kwh: float = 0.0
    # Dated physical interventions (maintenance / replacement).
    intervention_schedule: tuple[InterventionEvent, ...] = ()
    # Whether the use-stage and end-of-life scopes are active for this run. These are
    # scope flags, not results: both domains need to know which stages exist.
    use_stage_included: bool = False
    end_of_life_included: bool = False
    # Asset condition trajectory from System Dynamics, when enabled.
    condition_trajectory: tuple[float, ...] = ()
    # Free-form provenance/diagnostic notes.
    meta: dict = field(default_factory=dict)

    def schedule_as_rows(self) -> list[dict]:
        """The schedule in the legacy row shape, for engines that still expect dicts."""
        return [{"year": e.year, "B2_count": e.b2_count, "B4_count": e.b4_count}
                for e in self.intervention_schedule]


def build_shared_activity(
    *,
    served_annual_pkm: float = 0.0,
    lifetime_pkm: float = 0.0,
    annual_operational_kwh: float = 0.0,
    schedule_rows: Any = (),
    use_stage_included: bool = False,
    end_of_life_included: bool = False,
    condition_trajectory: Any = (),
    meta: dict | None = None,
) -> SharedActivity:
    """Assemble the neutral activity record from already-computed physical quantities.

    This function performs no science. It normalises shapes so that both domains read
    the same structure, which is precisely why it must contain no factor of any kind.
    """
    events = []
    for row in (schedule_rows or ()):
        if isinstance(row, InterventionEvent):
            events.append(row)
            continue
        events.append(InterventionEvent(
            year=int(row.get("year", 0)),
            b2_count=float(row.get("B2_count", 0.0) or 0.0),
            b4_count=float(row.get("B4_count", 0.0) or 0.0),
        ))
    return SharedActivity(
        served_annual_pkm=float(served_annual_pkm or 0.0),
        lifetime_pkm=float(lifetime_pkm or 0.0),
        annual_operational_kwh=float(annual_operational_kwh or 0.0),
        intervention_schedule=tuple(events),
        use_stage_included=bool(use_stage_included),
        end_of_life_included=bool(end_of_life_included),
        condition_trajectory=tuple(float(c) for c in (condition_trajectory or ())),
        meta=dict(meta or {}),
    )
