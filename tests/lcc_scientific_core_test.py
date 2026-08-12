"""Acceptance tests for the referenced deterministic scientific LCC core.

Covers:
  * present-value and escalation identities;
  * the real/nominal mixing block;
  * the golden deterministic fixture  100 + 20 + 30 + 10 - 5 = 155;
  * the discounted fixture            100 + 21/1.05 = 120;
  * the residual double-counting regression (net EOL at r=0 must be +5, not 0);
  * analysis-period, currency, evidence and discount-source gates.

Fixture numbers are TEST-ONLY software-correctness values, not project evidence.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lcc_scientific_core import (
    CostRow,
    ResidualRow,
    LCCModel,
    ScientificLCCInputError,
    present_value,
    escalate_cost,
    calculate_lcc,
)


ok = True


def check(name, cond):
    global ok
    print(("PASS" if cond else "FAIL"), name)
    ok = ok and bool(cond)


def cost_row(cost_id, phase, year, amount, **kw):
    base = dict(
        cost_id=cost_id,
        phase=phase,
        category="test",
        asset="test_asset",
        activity="test_activity",
        project_year=year,
        calendar_year=2026 + year,
        quantity=1.0,
        unit="lump_sum",
        unit_cost_base=amount,
        currency="EGP",
        price_base_year=2026,
        escalation_rate=0.0,
        source_file="golden_fixture.xlsx",
        source_location=f"Costs!{cost_id}",
        geography="Egypt",
        evidence_status="PROJECT-SPECIFIC",
    )
    base.update(kw)
    return CostRow(**base)


def residual_row(rid, year, amount, **kw):
    base = dict(
        residual_id=rid,
        asset="test_asset",
        activity="salvage",
        project_year=year,
        calendar_year=2026 + year,
        amount_base=amount,
        currency="EGP",
        price_base_year=2026,
        escalation_rate=0.0,
        source_file="golden_fixture.xlsx",
        source_location=f"Residual!{rid}",
        geography="Egypt",
        evidence_status="PROJECT-SPECIFIC",
    )
    base.update(kw)
    return ResidualRow(**base)


def model_with(cost_rows, residual_rows=(), **kw):
    base = dict(
        analysis_base_year=2026,
        analysis_period_years=20,
        currency="EGP",
        discount_rate=0.0,
        discount_basis="real",
        discount_source_file="economic_assumptions.xlsx",
        discount_source_location="Rates!B2",
        discount_evidence_status="PROJECT-SPECIFIC",
        cost_rows=tuple(cost_rows),
        residual_rows=tuple(residual_rows),
    )
    base.update(kw)
    return LCCModel(**base)


# ── 1. Present value ──────────────────────────────────────────────────────────
check(
    "PV year 0 identity",
    present_value(1000.0, 0, 0.05) == 1000.0,
)

check(
    "PV formula",
    abs(
        present_value(1000.0, 10, 0.05)
        - 1000.0 / (1.05 ** 10)
    ) < 1e-12,
)

# ── 2. Escalation and the real/nominal firewall ───────────────────────────────
check(
    "Nominal escalation formula",
    abs(
        escalate_cost(1000.0, 0.03, 5, "nominal")
        - 1000.0 * (1.03 ** 5)
    ) < 1e-12,
)

real_mix_blocked = False
try:
    escalate_cost(1000.0, 0.03, 5, "real")
except ScientificLCCInputError:
    real_mix_blocked = True
check("Real mode blocks nominal escalation", real_mix_blocked)

check("Real mode passes constant-price cost through unchanged",
      escalate_cost(1000.0, 0.0, 5, "real") == 1000.0)

bad_basis = False
try:
    escalate_cost(1000.0, 0.0, 1, "mixed")
except ScientificLCCInputError:
    bad_basis = True
check("Unknown discount basis rejected", bad_basis)

# ── 3. Golden deterministic fixture (handoff section 48) ──────────────────────
# Construction y0 100 + Operation y1 20 + Maintenance y5 30 + EOL y20 10
#   - Residual y20 5  =  155, at discount 0 and escalation 0.
model = model_with(
    (
        cost_row("C", "construction", 0, 100.0),
        cost_row("O", "operation", 1, 20.0),
        cost_row("M", "maintenance_renewal", 5, 30.0),
        cost_row("E", "end_of_life", 20, 10.0),
    ),
    (residual_row("R", 20, 5.0),),
)

r = calculate_lcc(model)

check("PV construction = 100", r["pv_construction"] == 100.0)
check("PV operation = 20", r["pv_operation"] == 20.0)
check("PV maintenance = 30", r["pv_maintenance_renewal"] == 30.0)
check("PV EOL = 10", r["pv_end_of_life"] == 10.0)
check("PV residual = 5", r["pv_residual"] == 5.0)
check("GOLDEN LCC exact identity = 155", r["lcc_npv"] == 155.0)
check("source gate passes golden fixture", r["publication_source_gate"] is True)
check("golden fixture has no open items", r["open_items"] == [])
check("equation id recorded", r["equation_id"] == "LCC-NPV-01")

# ── 4. Analysis period is the single source of truth ──────────────────────────
out_of_period = False
try:
    calculate_lcc(model_with((cost_row("OUT", "operation", 21, 1.0),)))
except ScientificLCCInputError:
    out_of_period = True
check("year outside N fails", out_of_period)

bad_period = False
try:
    calculate_lcc(model_with((cost_row("C", "construction", 0, 1.0),), analysis_period_years=0))
except ScientificLCCInputError:
    bad_period = True
check("analysis_period_years <= 0 fails", bad_period)

# ── 5. Discounted fixture (handoff section 49) ────────────────────────────────
# Construction y0 = 100, Operation y1 = 21, r = 5% -> PV operation = 20, LCC = 120.
disc = calculate_lcc(model_with(
    (
        cost_row("C", "construction", 0, 100.0),
        cost_row("O", "operation", 1, 21.0),
    ),
    discount_rate=0.05,
))
check("discounted fixture: PV operation = 21/1.05 = 20",
      abs(disc["pv_operation"] - 20.0) < 1e-12)
check("discounted fixture: LCC = 120", abs(disc["lcc_npv"] - 120.0) < 1e-12)

# ── 6. Residual double-counting regression (handoff section 50) ───────────────
# EOL cost 10 and residual revenue 5 at r=0 must net to +5, NOT 0.
# A result of 0 would mean the residual had been subtracted twice.
net_eol = calculate_lcc(model_with(
    (cost_row("E", "end_of_life", 20, 10.0),),
    (residual_row("R", 20, 5.0),),
))
check("residual credited exactly once (net EOL = +5, not 0)",
      net_eol["lcc_npv"] == 5.0 and net_eol["pv_end_of_life"] == 10.0
      and net_eol["pv_residual"] == 5.0)

# A residual entered as a negative amount is rejected: it must be a positive revenue,
# so it can never masquerade as a negative cost row and be counted twice.
neg_residual = False
try:
    calculate_lcc(model_with((), (residual_row("R", 1, -5.0),)))
except ScientificLCCInputError:
    neg_residual = True
check("negative residual amount rejected", neg_residual)

# ── 7. Currency rule (handoff section 51) ─────────────────────────────────────
fx_blocked = False
try:
    calculate_lcc(model_with((cost_row("USD", "construction", 0, 10.0, currency="USD"),)))
except ScientificLCCInputError:
    fx_blocked = True
check("mixed currency rejected, never silently converted", fx_blocked)

# ── 8. Source gate (handoff sections 22, 23, 45) ──────────────────────────────
open_row = calculate_lcc(model_with(
    (cost_row("X", "construction", 0, 100.0, source_file="", evidence_status="SOURCE-OPEN"),)
))
check("SOURCE-OPEN row blocks the publication gate",
      open_row["publication_source_gate"] is False and open_row["open_items"])
check("SOURCE-OPEN row still computes diagnostically",
      open_row["lcc_npv"] == 100.0)

scenario_row = calculate_lcc(model_with(
    (cost_row("S", "construction", 0, 100.0, evidence_status="SCENARIO-ONLY"),)
))
check("SCENARIO-ONLY row blocks the publication gate",
      scenario_row["publication_source_gate"] is False)

proxy_row = calculate_lcc(model_with(
    (cost_row("P", "construction", 0, 100.0, evidence_status="REF-PROXY"),)
))
check("REF-PROXY row computes but does not satisfy the publication gate",
      proxy_row["lcc_npv"] == 100.0 and proxy_row["publication_source_gate"] is False)

no_location = calculate_lcc(model_with(
    (cost_row("L", "construction", 0, 100.0, source_location=""),)
))
check("missing source_location blocks the publication gate",
      no_location["publication_source_gate"] is False)

# Section 23: the model-level discount rate carries its own provenance.
no_disc_src = calculate_lcc(model_with(
    (cost_row("C", "construction", 0, 100.0),),
    discount_source_file="", discount_evidence_status="SOURCE-OPEN",
))
check("discount rate without a source blocks the publication gate",
      no_disc_src["publication_source_gate"] is False
      and any("Discount rate" in i for i in no_disc_src["open_items"]))
check("discount source completeness is reported explicitly",
      no_disc_src["discount_source_complete"] is False
      and r["discount_source_complete"] is True)

# ── 9. Structural validation ──────────────────────────────────────────────────
bad_phase = False
try:
    calculate_lcc(model_with((cost_row("B", "operations", 0, 1.0),)))
except ScientificLCCInputError:
    bad_phase = True
check("invalid phase rejected", bad_phase)

no_id = False
try:
    calculate_lcc(model_with((cost_row("", "construction", 0, 1.0),)))
except ScientificLCCInputError:
    no_id = True
check("missing cost_id rejected", no_id)

neg_qty = False
try:
    calculate_lcc(model_with((cost_row("N", "construction", 0, 1.0, quantity=-1.0),)))
except ScientificLCCInputError:
    neg_qty = True
check("negative quantity rejected", neg_qty)

back_dated = False
try:
    calculate_lcc(model_with((cost_row("BD", "construction", 0, 1.0, price_base_year=2030),)))
except ScientificLCCInputError:
    back_dated = True
check("calendar_year before price_base_year rejected", back_dated)

# ── 10. Source audit completeness (handoff section 44) ────────────────────────
_audit_fields = {
    "cost_id", "phase", "category", "asset", "activity", "project_year",
    "calendar_year", "quantity", "unit", "unit_cost_base", "currency",
    "price_base_year", "escalation_rate", "base_amount", "future_amount",
    "present_value", "source_file", "source_location", "geography",
    "evidence_status", "source_complete", "note",
}
check("cost-row audit carries every required provenance field",
      _audit_fields <= set(r["cost_rows"][0]))

# ── 11. Benefits never enter LCC ──────────────────────────────────────────────
check("LCC identity is exactly phases minus residual (no benefit term)",
      abs(r["lcc_npv"] - (r["pv_construction"] + r["pv_operation"]
                          + r["pv_maintenance_renewal"] + r["pv_end_of_life"]
                          - r["pv_residual"])) < 1e-12)

# ── 12. Empty phase is not a fabricated zero (handoff section 46) ─────────────
check("empty phases are reported as having no rows, not as documented zero",
      net_eol["phase_has_rows"] == {"construction": False, "operation": False,
                                    "maintenance_renewal": False, "end_of_life": True})

print("\nALL LCC SCIENTIFIC CORE TESTS PASSED" if ok else "\nSOME LCC CORE TESTS FAILED")
sys.exit(0 if ok else 1)
