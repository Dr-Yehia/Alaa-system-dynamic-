"""LEGACY-DEVELOPER-ONLY economic engine — the scalar LCC that predates the ledger.

ARCHITECTURAL CONTRACT
----------------------
This module is the LCC domain's LEGACY half. It exists so the developer dashboard and
the historical regression suites keep working while the referenced scientific LCC
ledger (`lcc_scientific_core.py` + its integration) becomes the publication path.

Rules:
  * it MUST NOT supply Publication-mode LCC headline/report/CSV/Excel values;
  * it does not import the LCA engines, and the LCA engines do not import it;
  * it computes money only — no carbon, no benefits.

Why it is not the canonical path: these helpers take scalar/dictionary costs with no
row-level provenance — no cost_id, source file, source location, geography, price base
year or evidence status — so they cannot satisfy a publication source gate.

METHOD-REFERENCE for the replacement scientific path:
  ASTM International, "Standard Practice for Measuring Life-Cycle Costs of Buildings
  and Building Systems", ASTM E917-17(2023), DOI 10.1520/E0917-17R23.
  ISO, "Buildings and constructed assets — Service life planning — Part 5: Life-cycle
  costing", ISO 15686-5:2017, Edition 2.
REF-VERIFIED-Q1 support for LRT:
  Kim, G.-T.; Kim, K.-T.; Lee, D.-H.; Han, C.-H.; Kim, H.-B.; Jun, J.-T.,
  "Development of a life cycle cost estimate system for structures of light rail
  transit infrastructure", Automation in Construction 19(3), 308-325 (2010),
  DOI 10.1016/j.autcon.2009.12.001.

Extracted verbatim from app_final_streamlit_ready.py during the architectural
separation. No formula, default or sign convention was changed.
"""

from __future__ import annotations

from monorail_assessment.common.project_context import ASSESSMENT_LIFETIME_YEARS


def b6_energy_pv_cost(annual_kwh, tariff_per_kwh, escalation_pct, discount_pct, years):
    """R11: PV of B6 energy cost from energy × tariff.
        PV = Σ_t (annual_kwh · tariff · (1+esc)^(t-1)) / (1+disc)^t
    Returns (pv_cost, undiscounted_cost). With tariff 0 → (0, 0)."""
    pv = 0.0
    undisc = 0.0
    for t in range(1, int(years) + 1):
        cost_t = annual_kwh * tariff_per_kwh * (1.0 + escalation_pct / 100.0) ** (t - 1)
        undisc += cost_t
        pv += cost_t / (1.0 + discount_pct / 100.0) ** t
    return pv, undisc


def calculate_lcc_npv(construction_cost_m, annual_maintenance_m, annual_energy_cost_m=0.0,
                      replacement_costs=None, end_of_life_cost_m=0.0, residual_value_m=0.0,
                      discount_rate_pct=5.0, lifetime_years=50, energy_pv_cost_override_m=None):
    r = discount_rate_pct / 100.0
    n = lifetime_years
    replacement_costs = replacement_costs or {}

    def pv_single(cost, year):
        return cost / ((1 + r) ** year) if r > 0 else cost

    upv = (1 - (1 + r) ** (-n)) / r if r > 0 else n

    pv_maintenance = annual_maintenance_m * upv
    # R17-energycost: prefer the tariff-based escalating energy PV when supplied.
    pv_energy = energy_pv_cost_override_m if energy_pv_cost_override_m is not None else annual_energy_cost_m * upv
    pv_replacement = sum(pv_single(cost, year) for year, cost in replacement_costs.items())
    pv_end_of_life = pv_single(end_of_life_cost_m, n)
    pv_residual = pv_single(residual_value_m, n)

    npv_lcc = construction_cost_m + pv_maintenance + pv_energy + pv_replacement + pv_end_of_life - pv_residual

    return {"npv_lcc_m": npv_lcc, "discount_rate_pct": discount_rate_pct, "lifetime_years": n}


def calculate_lcc_npv_activity_based(construction_cost_m, annual_energy_cost_m, maintenance_mode,
                                     annual_maintenance_m, b2b3b5_costs_by_year, replacement_costs_by_year,
                                     end_of_life_cost_m=0.0, residual_value_m=0.0,
                                     discount_rate_pct=5.0, lifetime_years=ASSESSMENT_LIFETIME_YEARS,
                                     energy_pv_cost_override_m=None):
    """LCCA with a maintenance mode that prevents double counting:
      simple_annual : routine cost = annual_maintenance (NO activity routine costs)
      activity_based: routine cost = Σ B2/B3/B5 activity costs (NO annual_maintenance)
    B4 replacement cost is a discrete capital event added in BOTH modes (so B4 LCA
    emissions always have a matching LCCA cost)."""
    r = discount_rate_pct / 100.0
    n = int(lifetime_years)

    def pv(cost, year):
        return cost / ((1 + r) ** year) if r > 0 else cost

    upv = (1 - (1 + r) ** (-n)) / r if r > 0 else n
    # R17-energycost: when a tariff-based escalating energy PV is supplied (kWh×tariff),
    # use it instead of the flat annual_energy_cost·UPV (mutually exclusive — no double count).
    pv_energy = energy_pv_cost_override_m if energy_pv_cost_override_m is not None else annual_energy_cost_m * upv
    if maintenance_mode == 'activity_based':
        pv_routine = sum(pv(c, y) for y, c in (b2b3b5_costs_by_year or {}).items())
    else:
        pv_routine = annual_maintenance_m * upv
    pv_replacement = sum(pv(c, y) for y, c in (replacement_costs_by_year or {}).items())
    pv_eol = pv(end_of_life_cost_m, n)
    pv_residual = pv(residual_value_m, n)
    npv = construction_cost_m + pv_routine + pv_energy + pv_replacement + pv_eol - pv_residual
    return {'npv_lcc_m': npv, 'discount_rate_pct': discount_rate_pct, 'lifetime_years': n,
            'maintenance_mode': maintenance_mode, 'pv_routine_m': pv_routine,
            'pv_replacement_m': pv_replacement}

def calculate_legacy_lcc(params, shared):
    """Legacy economic result, computed from PROJECT PARAMS + NEUTRAL SHARED ACTIVITY.

    This is the separation boundary for the LCC domain. The signature is the contract:
    it receives `shared` — a `SharedActivity` carrying physical facts only (annual kWh,
    the dated intervention schedule, scope flags) — and NEVER an LCA result. No carbon
    value can therefore reach a cash flow.

    Note that the B6 energy present value is computed HERE, not on the environmental
    side. It is money (kWh x tariff, escalated and discounted), so it belongs to this
    domain; only the kWh crosses the boundary. Arithmetic is unchanged from the monolith.

    Returns the same keys the legacy dashboard has always consumed.
    """
    schedule_rows = shared.schedule_as_rows()
    include_c1c4 = bool(shared.end_of_life_included)

    # R11: PV of B6 energy cost from energy x tariff (0 tariff -> 0). Moved verbatim
    # from the environmental block, where it never belonged.
    b6_energy_pv_cost_m, b6_energy_undisc_cost_m = b6_energy_pv_cost(
        shared.annual_operational_kwh, float(params.get('b6_energy_tariff', 0.0)),
        float(params.get('b6_energy_escalation_pct', 0.0)),
        float(params.get('discount_rate', 5.0)), ASSESSMENT_LIFETIME_YEARS)

    # R28: contract factor adjusts the base CAPEX before it enters the NPV
    # (CAPEX_contract = CAPEX_base x contract_factor). Default 1.0 -> no change.
    contract_factor = float(params.get('contract_factor', 1.0))
    construction_cost_base = params['construction_cost']
    construction_cost = construction_cost_base * contract_factor
    annual_maintenance = params['maintenance_cost']
    total_maintenance_cost = annual_maintenance * ASSESSMENT_LIFETIME_YEARS

    # LCCA — when B2-B5 is active, use the mode-aware activity LCCA (prevents
    # double counting); B4 replacement cost is a discrete capital event in BOTH modes.
    lcca_maint_mode = params.get('lcca_maint_mode', 'simple_annual')
    b4_cost_per_event = params.get('b4_cost_per_event_m', 0.0)
    b2_cost_per_event = params.get('b2_cost_per_event_m', 0.0)
    replacement_costs_by_year = {row['year']: b4_cost_per_event
                                 for row in schedule_rows if row['B4_count'] and b4_cost_per_event}
    b2b3b5_costs_by_year = {row['year']: row['B2_count'] * b2_cost_per_event
                            for row in schedule_rows if row['B2_count'] and b2_cost_per_event}
    # EOL cost enters the LCCA exactly once (only when C1-C4 is included).
    eol_cost_m = params.get('eol_cost_m', 0.0) if include_c1c4 else 0.0
    # R17-energycost: a B6 energy tariff (>0) replaces the flat annual energy cost with the
    # escalating, discounted PV from kWh x tariff (the two are mutually exclusive).
    use_energy_tariff = float(params.get('b6_energy_tariff', 0.0)) > 0.0
    energy_pv_override = (b6_energy_pv_cost_m / 1e6) if use_energy_tariff else None  # $ -> $M
    annual_energy_cost_m = 0.0 if use_energy_tariff else params.get("annual_energy_cost", 0.0)
    if shared.use_stage_included:
        lcc_results = calculate_lcc_npv_activity_based(
            construction_cost_m=construction_cost,
            annual_energy_cost_m=annual_energy_cost_m,
            maintenance_mode=lcca_maint_mode,
            annual_maintenance_m=annual_maintenance,
            b2b3b5_costs_by_year=b2b3b5_costs_by_year,
            replacement_costs_by_year=replacement_costs_by_year,
            end_of_life_cost_m=eol_cost_m,
            residual_value_m=params.get("residual_value", 0.0),
            discount_rate_pct=params.get("discount_rate", 5.0),
            lifetime_years=ASSESSMENT_LIFETIME_YEARS,
            energy_pv_cost_override_m=energy_pv_override)
    else:
        lcc_results = calculate_lcc_npv(
            construction_cost_m=construction_cost,
            annual_maintenance_m=annual_maintenance,
            annual_energy_cost_m=annual_energy_cost_m,
            end_of_life_cost_m=eol_cost_m,
            residual_value_m=params.get("residual_value", 0.0),
            discount_rate_pct=params.get("discount_rate", 5.0),
            lifetime_years=ASSESSMENT_LIFETIME_YEARS,
            energy_pv_cost_override_m=energy_pv_override)

    return {
        'contract_factor': contract_factor,
        'construction_cost_base': construction_cost_base,
        'construction_cost': construction_cost,
        'annual_maintenance': annual_maintenance,
        'total_maintenance_cost': total_maintenance_cost,
        'lcca_maint_mode': lcca_maint_mode,
        'lcc_results': lcc_results,
        'b6_energy_pv_cost_m': b6_energy_pv_cost_m,
        'b6_energy_undisc_cost_m': b6_energy_undisc_cost_m,
    }
