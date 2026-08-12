"""System Dynamics — a NEUTRAL state/activity producer.

ARCHITECTURAL CONTRACT
----------------------
System Dynamics sits with the shared layer, not inside LCA and not inside LCC.

The reason is concrete: the SD model produces an asset-condition trajectory and a
maintenance/renewal schedule, and the SAME schedule is consumed twice — the LCA domain
turns each intervention into materials/waste/transport carbon, while the LCC domain
turns the same intervention into money. If SD lived inside LCA, then LCC would have to
reach into LCA to obtain its own cost timing, and the two domains would be coupled
again through the back door.

So this module returns physical state and dated activity ONLY:
  * no emission factor and no carbon result;
  * no tariff, discount rate or present value;
  * no benefit valuation.

Extracted verbatim from app_final_streamlit_ready.py during the architectural
separation. The dynamics, defaults and units are unchanged.
"""

from __future__ import annotations

import numpy as np

from project_context import ASSESSMENT_LIFETIME_YEARS


def simulate_asset_condition(C0=1.0, delta=0.005, maintenance_interval=5,
                             rho=0.05, tau=1, lifetime_years=ASSESSMENT_LIFETIME_YEARS, dt=1.0):
    """Stock-flow simulation of asset condition C(t).
    Returns (rows, condition_start) where condition_start[t-1] = C at start of year t.
    Degradation is applied first, then delayed maintenance recovery, each capped."""
    def is_maint_year(yr):
        return bool(maintenance_interval) and maintenance_interval > 0 and yr >= 1 and (yr % maintenance_interval == 0)

    rows, condition_start = [], []
    C = float(np.clip(C0, 0.0, 1.0))
    for t in range(1, int(lifetime_years) + 1):
        C_start = C
        condition_start.append(C_start)
        # Outflow: degradation (constant annual loss, capped so condition stays >= 0)
        DR = min(delta, C_start / dt) if dt > 0 else 0.0
        C_pre = max(0.0, C_start - dt * DR)
        # Inflow: delayed maintenance recovery (capped so condition stays <= 1)
        m_action = 1 if is_maint_year(t) else 0
        src_year = t - tau
        delayed = 1 if (src_year >= 1 and is_maint_year(src_year)) else 0
        MR_request = rho * delayed
        MR_actual = max(0.0, min(MR_request, (1.0 - C_pre) / dt)) if dt > 0 else 0.0
        C_end = float(np.clip(C_pre + dt * MR_actual, 0.0, 1.0))
        rows.append({
            'year': t, 'C_start': C_start,
            'maintenance_action': m_action, 'delayed_maintenance': delayed,
            'degradation_flow': dt * DR, 'maintenance_recovery_flow': dt * MR_actual,
            'C_end': C_end,
        })
        C = C_end
    return rows, condition_start


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