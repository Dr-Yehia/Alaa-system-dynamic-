"""LEGACY-DEVELOPER-ONLY environmental engine — the LCA domain's legacy half.

ARCHITECTURAL CONTRACT
----------------------
This is the environmental counterpart of `legacy_lcc_engine.py`. It exists so the
developer dashboard and the historical regression suites keep working while the frozen
referenced engines (`lca_scientific_core` + `lca_scientific_integration` +
`lca_scientific_reporting`) remain the ONLY publication path.

Rules:
  * it computes carbon and energy only — no money, no benefits;
  * it does not import the LCC engines or benefits_core, and neither imports it;
  * Publication-mode LCA never routes through here.

WHY calculate_dynamic_b6 LIVES HERE AND NOT IN system_dynamics_core
-------------------------------------------------------------------
System Dynamics is a neutral state/activity producer shared by every domain. But
`calculate_dynamic_b6()` accepts a grid carbon intensity and returns B6_co2_tons /
b6_dynamic_tons, which is LCA carbon. Leaving it in the shared layer would have parked
a piece of the environmental domain inside neutral territory, so it belongs here.
The condition trajectory it consumes still comes from `system_dynamics_core`, which
remains carbon-free: SD produces state, this module turns state into carbon.

Moved verbatim during the architectural separation; no equation, factor, default or
unit was changed.
"""

from __future__ import annotations

from project_context import ASSESSMENT_LIFETIME_YEARS


def calculate_dynamic_b6(condition_start, EI0, daily_pkm, CI,
                         lifetime_years=ASSESSMENT_LIFETIME_YEARS, alpha=0.10, g=0.0):
    """Condition-dependent dynamic B6 operational carbon vs static baseline.
    EI_t = EI0*(1+alpha*(1-C_t)); PKM_t = daily_pkm*365*(1+g)^(t-1); CI_t = CI (no renewable)."""
    yearly, b6_dyn, b6_static, ei_sum, pkm_sum = [], 0.0, 0.0, 0.0, 0.0
    for idx, t in enumerate(range(1, int(lifetime_years) + 1)):
        C_t = condition_start[idx]
        EI_t = EI0 * (1.0 + alpha * (1.0 - C_t))
        # (1+g)^(t-1): the first operating year (t=1) is the baseline (no growth yet)
        PKM_t = daily_pkm * 365.0 * ((1.0 + g) ** (t - 1))
        co2_dyn = EI_t * PKM_t * CI / 1000.0
        co2_static = EI0 * PKM_t * CI / 1000.0
        b6_dyn += co2_dyn
        b6_static += co2_static
        ei_sum += EI_t
        pkm_sum += PKM_t
        yearly.append({'year': t, 'C_t': C_t, 'EI_t': EI_t, 'PKM_t': PKM_t, 'B6_co2_tons': co2_dyn})
    n = int(lifetime_years) if lifetime_years else 1
    return {
        'yearly': yearly,
        'b6_dynamic_tons': b6_dyn,
        'b6_static_tons': b6_static,
        'delta_b6_tons': b6_dyn - b6_static,
        'average_EI': ei_sum / n,
        'total_pkm': pkm_sum,
    }