"""The single assembly point for the three independent assessment domains.

ARCHITECTURAL ROLE
------------------
                project_context  +  shared_activity        (neutral facts)
                        |                  |
              +---------+---------+--------+--------+
              |                   |                 |
             LCA                 LCC            BENEFITS     (independent domains)
              |                   |                 |
              +---------+---------+--------+--------+
                                  |
                    assessment_orchestrator  <-- this module
                                  |
                                 UI

This module CALLS the domains and COLLECTS their results. It deliberately contains no
scientific equation of any kind: no emission factor, no present value, no valuation.
If an equation ever appears here, the separation has been undone, because the
orchestrator is the one place that can see all three domains at once.

The domains do not know about each other. They know only about the neutral layers.
`tests/domain_dependency_test.py` enforces that mechanically.

INPUT SLICING
-------------
The UI may still gather one wide dictionary, but each engine receives only its own
slice. `split_params()` performs that cut, so no engine can read another domain's
fields even by accident.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from project_context import ProjectContext, context_from_params


# Which parameter keys belong to which domain. A key that is not listed is treated as
# neutral/shared configuration and offered to every slice, so the split can never drop
# an input silently.
LCC_PARAM_KEYS = {
    "construction_cost", "contract_factor", "maintenance_cost", "discount_rate",
    "annual_energy_cost", "residual_value", "eol_cost_m", "b2_cost_per_event_m",
    "b4_cost_per_event_m", "lcca_maint_mode", "b6_energy_tariff",
    "b6_energy_escalation_pct", "price_year", "price_base_year", "currency",
    "lcc_analysis_base_year", "lcc_analysis_period_years", "lcc_currency",
    "lcc_discount_basis", "lcc_discount_rate", "lcc_discount_source_file",
    "lcc_discount_source_location", "lcc_cost_rows", "lcc_residual_rows",
}

BENEFITS_PARAM_KEYS = {
    "jobs_created", "economic_multiplier", "benefit_baseline_ci_pkm",
    "time_saving_min_per_trip", "value_of_time_per_hour", "trips_per_day",
    "land_take_ha", "noise_reduction_db", "benefit_source",
}


@dataclass(frozen=True)
class AssessmentResult:
    """The three domain results, side by side and never merged.

    They are kept as separate attributes on purpose: there is no combined headline
    number here, because combining a cost with a benefit is a Cost-Benefit Analysis and
    combining a cost with carbon is not meaningful at all.
    """

    context: ProjectContext
    lca: Any = None
    lcc: Any = None
    benefits: Any = None
    shared: Any = None
    notes: dict = field(default_factory=dict)


def split_params(params: dict) -> dict:
    """Cut one wide UI dictionary into per-domain input slices.

    Returns ``{"context", "lca_inputs", "lcc_inputs", "benefits_inputs", "shared_inputs"}``.

    Domain-owned keys go ONLY to their owner; every remaining key is shared
    configuration (material quantities, ridership, scope toggles) and is passed to all
    slices so nothing is lost. The guarantee this provides is one-directional but it is
    the one that matters: an LCA engine handed `lca_inputs` cannot read a discount rate,
    and an LCC engine handed `lcc_inputs` cannot read an emission factor.
    """
    params = dict(params or {})
    neutral = {k: v for k, v in params.items()
               if k not in LCC_PARAM_KEYS and k not in BENEFITS_PARAM_KEYS}

    lca_inputs = dict(neutral)
    lcc_inputs = {**neutral, **{k: v for k, v in params.items() if k in LCC_PARAM_KEYS}}
    benefits_inputs = {**neutral,
                       **{k: v for k, v in params.items() if k in BENEFITS_PARAM_KEYS}}

    return {
        "context": context_from_params(params),
        "lca_inputs": lca_inputs,
        "lcc_inputs": lcc_inputs,
        "benefits_inputs": benefits_inputs,
        "shared_inputs": neutral,
    }


def run_assessment(params: dict, *, legacy_engine=None) -> AssessmentResult:
    """Run the domains and collect their results.

    `legacy_engine` is the callable that produces the historical dashboard result set
    (the app's `calculate_legacy_dashboard_results`). It is injected rather than
    imported so this module never depends on the Streamlit application — importing the
    app would execute a UI at import time and re-couple everything.
    """
    slices = split_params(params)
    result = AssessmentResult(context=slices["context"])

    if legacy_engine is not None:
        legacy = legacy_engine(dict(params))
        # The legacy engine still returns one combined dictionary for backward
        # compatibility. The orchestrator presents it as three separate views; it does
        # not recompute anything.
        object.__setattr__(result, "lca", legacy)
        object.__setattr__(result, "lcc", legacy.get("lcc_results"))
        object.__setattr__(result, "benefits", legacy.get("benefit_kpis"))
        object.__setattr__(result, "notes", {"source": "legacy_dashboard_engine"})

    return result
