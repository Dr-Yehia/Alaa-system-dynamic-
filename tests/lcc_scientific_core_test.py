"""Acceptance tests for the referenced deterministic scientific LCC core.

Covers:
  * present-value, escalation and base-cost identities;
  * the real/nominal firewall and the real-basis price-year rebasing rule;
  * the golden deterministic fixture  100 + 20 + 30 + 10 - 5 = 155;
  * the discounted fixture            100 + 21/1.05 = 120;
  * the residual double-counting regression (net EOL at r=0 must be +5, not 0);
  * the METHOD vs NUMERIC evidence split — a standard or a foreign Q1 paper can
    never certify a Cairo number;
  * strict integer years and the calendar/project-year identity;
  * analysis-period and discount-rate provenance;
  * descriptor/geography/uniqueness gates;
  * the LCC reference catalog and equation registry.

Fixture numbers are TEST-ONLY software-correctness values, not project evidence.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from monorail_assessment.lcc.core import (
    CostRow,
    ResidualRow,
    LCCModel,
    ScientificLCCInputError,
    LCC_REFERENCE_CATALOG,
    LCC_EQUATIONS,
    METHOD_EVIDENCE_CLASSES,
    PUBLICATION_ACCEPTABLE_NUMERIC_EVIDENCE,
    present_value,
    escalate_cost,
    calculate_lcc,
    lcc_reference_integrity_check,
)


ok = True

BASE_YEAR = 2026


def check(name, cond):
    global ok
    print(("PASS" if cond else "FAIL"), name)
    ok = ok and bool(cond)


def _cal(year):
    """Consistent calendar year, tolerant of the deliberately invalid years used to
    prove that the CORE rejects them (the helper must not fail first)."""
    try:
        return BASE_YEAR + year
    except TypeError:
        return BASE_YEAR


def cost_row(cost_id, phase, year, amount, **kw):
    base = dict(
        cost_id=cost_id,
        phase=phase,
        category="test_category",
        asset="test_asset",
        activity="test_activity",
        project_year=year,
        calendar_year=_cal(year),
        quantity=1.0,
        unit="lump_sum",
        unit_cost_base=amount,
        currency="EGP",
        price_base_year=BASE_YEAR,
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
        calendar_year=_cal(year),
        amount_base=amount,
        currency="EGP",
        price_base_year=BASE_YEAR,
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
        analysis_base_year=BASE_YEAR,
        analysis_period_years=20,
        currency="EGP",
        discount_rate=0.0,
        discount_basis="real",
        discount_source_file="economic_assumptions.xlsx",
        discount_source_location="Rates!B2",
        discount_evidence_status="PROJECT-SPECIFIC",
        discount_source_geography="Egypt",
        analysis_period_source_file="design_brief.pdf",
        analysis_period_source_location="clause 3.2 design life",
        analysis_period_evidence_status="PROJECT-SPECIFIC",
        analysis_period_geography="Egypt",
        cost_rows=tuple(cost_rows),
        residual_rows=tuple(residual_rows),
    )
    base.update(kw)
    return LCCModel(**base)


def raises(fn):
    try:
        fn()
    except ScientificLCCInputError:
        return True
    return False


# ── 1. Present value ──────────────────────────────────────────────────────────
check("PV year 0 identity", present_value(1000.0, 0, 0.05) == 1000.0)
check("PV formula",
      abs(present_value(1000.0, 10, 0.05) - 1000.0 / (1.05 ** 10)) < 1e-12)

# ── 2. Escalation and the real/nominal firewall ───────────────────────────────
check("Nominal escalation formula",
      abs(escalate_cost(1000.0, 0.03, 5, "nominal") - 1000.0 * (1.03 ** 5)) < 1e-12)
check("Real mode blocks nominal escalation",
      raises(lambda: escalate_cost(1000.0, 0.03, 5, "real")))
check("Real mode passes constant-price cost through unchanged",
      escalate_cost(1000.0, 0.0, 5, "real") == 1000.0)
check("Unknown discount basis rejected",
      raises(lambda: escalate_cost(1000.0, 0.0, 1, "mixed")))

# ── 3. Golden deterministic fixture ───────────────────────────────────────────
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
check("equation ids recorded", "LCC-NPV-01" in r["equation_ids"])

# ── 4. Analysis period is the single source of truth ──────────────────────────
check("year outside N fails",
      raises(lambda: calculate_lcc(model_with((cost_row("OUT", "operation", 21, 1.0),)))))
check("analysis_period_years <= 0 fails",
      raises(lambda: calculate_lcc(
          model_with((cost_row("C", "construction", 0, 1.0),), analysis_period_years=0))))

# ── 5. Discounted fixture ─────────────────────────────────────────────────────
disc = calculate_lcc(model_with(
    (cost_row("C", "construction", 0, 100.0), cost_row("O", "operation", 1, 21.0)),
    discount_rate=0.05,
))
check("discounted fixture: PV operation = 21/1.05 = 20",
      abs(disc["pv_operation"] - 20.0) < 1e-12)
check("discounted fixture: LCC = 120", abs(disc["lcc_npv"] - 120.0) < 1e-12)

# ── 6. Residual double-counting regression ────────────────────────────────────
net_eol = calculate_lcc(model_with(
    (cost_row("E", "end_of_life", 20, 10.0),), (residual_row("R", 20, 5.0),)))
check("residual credited exactly once (net EOL = +5, not 0)",
      net_eol["lcc_npv"] == 5.0 and net_eol["pv_end_of_life"] == 10.0
      and net_eol["pv_residual"] == 5.0)
check("negative residual amount rejected",
      raises(lambda: calculate_lcc(model_with((), (residual_row("R", 1, -5.0),)))))

# ── 7. Currency rule ──────────────────────────────────────────────────────────
check("mixed currency rejected, never silently converted",
      raises(lambda: calculate_lcc(
          model_with((cost_row("USD", "construction", 0, 10.0, currency="USD"),)))))

# ── 8. METHOD vs NUMERIC evidence split (reviewer blocker 1) ──────────────────
# A standard describes HOW to discount; it cannot certify a Cairo unit cost.
method_num = calculate_lcc(model_with(
    (cost_row("MR", "construction", 0, 5000.0, evidence_status="METHOD-REFERENCE"),)))
check("METHOD-REFERENCE cannot certify a numerical cost",
      method_num["publication_source_gate"] is False
      and any("METHOD/EQUATION only" in i for i in method_num["open_items"]))

# A foreign Q1 paper proves the method or offers a disclosed proxy — never a Cairo number.
q1_num = calculate_lcc(model_with(
    (cost_row("Q1", "construction", 0, 5000.0, evidence_status="REF-VERIFIED-Q1"),)))
check("foreign REF-VERIFIED-Q1 cannot certify a numerical cost",
      q1_num["publication_source_gate"] is False
      and any("METHOD/EQUATION only" in i for i in q1_num["open_items"]))

check("method classes are disjoint from numeric-acceptable classes",
      not (METHOD_EVIDENCE_CLASSES & PUBLICATION_ACCEPTABLE_NUMERIC_EVIDENCE))

# The discount rate is subject to the same rule.
disc_method = calculate_lcc(model_with(
    (cost_row("C", "construction", 0, 100.0),),
    discount_evidence_status="METHOD-REFERENCE"))
check("METHOD-REFERENCE cannot certify the discount rate",
      disc_method["publication_source_gate"] is False
      and disc_method["discount_source_complete"] is False)

official = calculate_lcc(model_with(
    (cost_row("OD", "operation", 1, 10.0, evidence_status="OFFICIAL-PROJECT-DATA"),)))
check("OFFICIAL-PROJECT-DATA is accepted for a numerical value",
      official["publication_source_gate"] is True)

for status in ("REF-PROXY", "SOURCE-OPEN", "SCENARIO-ONLY"):
    res = calculate_lcc(model_with(
        (cost_row("D", "construction", 0, 100.0, evidence_status=status),)))
    check(f"{status} computes but fails the publication gate",
          res["lcc_npv"] == 100.0 and res["publication_source_gate"] is False)

# ── 9. Strict integer years (reviewer blocker 2) ──────────────────────────────
check("fractional project_year rejected, never truncated",
      raises(lambda: calculate_lcc(model_with((cost_row("F", "operation", 5.8, 1.0,
                                                        calendar_year=BASE_YEAR + 5),)))))
check("fractional calendar_year rejected",
      raises(lambda: calculate_lcc(model_with(
          (cost_row("F2", "operation", 5, 1.0, calendar_year=2031.4),)))))
check("fractional price_base_year rejected",
      raises(lambda: calculate_lcc(model_with(
          (cost_row("F3", "construction", 0, 1.0, price_base_year=2026.5),)))))
check("fractional analysis_period_years rejected",
      raises(lambda: calculate_lcc(model_with(
          (cost_row("C", "construction", 0, 1.0),), analysis_period_years=20.5))))
check("fractional analysis_base_year rejected",
      raises(lambda: calculate_lcc(model_with(
          (cost_row("C", "construction", 0, 1.0),), analysis_base_year=2026.5))))
check("non-numeric year rejected",
      raises(lambda: calculate_lcc(model_with(
          (cost_row("F4", "operation", "five", 1.0),)))))

# ── 10. calendar_year == analysis_base_year + project_year (blocker 3) ────────
check("calendar/project year mismatch rejected for a cost row",
      raises(lambda: calculate_lcc(model_with(
          (cost_row("MM", "operation", 5, 1.0, calendar_year=2050),)))))
check("calendar/project year mismatch rejected for a residual row",
      raises(lambda: calculate_lcc(model_with(
          (), (residual_row("MMR", 5, 1.0, calendar_year=2050),)))))
check("consistent calendar year accepted",
      calculate_lcc(model_with(
          (cost_row("OKY", "operation", 5, 1.0, calendar_year=BASE_YEAR + 5),)
      ))["lcc_npv"] == 1.0)

# ── 11. Real-basis price-year rebasing rule (blocker 4) ───────────────────────
check("real basis rejects a price_base_year that differs from the analysis base year",
      raises(lambda: calculate_lcc(model_with(
          (cost_row("RB", "construction", 0, 100.0, price_base_year=2020),)))))
# Nominal basis may legitimately escalate from an earlier price base year.
nominal = calculate_lcc(model_with(
    (cost_row("NB", "operation", 1, 100.0, price_base_year=2020, escalation_rate=0.03),),
    discount_basis="nominal", discount_rate=0.0))
check("nominal basis escalates from an earlier price base year",
      abs(nominal["pv_operation"] - 100.0 * (1.03 ** 7)) < 1e-9)

# ── 12. Analysis-period provenance (blocker 5) ────────────────────────────────
no_n_src = calculate_lcc(model_with(
    (cost_row("C", "construction", 0, 100.0),),
    analysis_period_source_file="", analysis_period_evidence_status="SOURCE-OPEN"))
check("analysis period without a source blocks the publication gate",
      no_n_src["publication_source_gate"] is False
      and no_n_src["analysis_period_source_complete"] is False
      and any("Analysis period" in i for i in no_n_src["open_items"]))
check("analysis-period provenance defaults to blocked, never assumed",
      LCCModel.__dataclass_fields__["analysis_period_evidence_status"].default
      == "SOURCE-OPEN")
check("sourced analysis period passes", r["analysis_period_source_complete"] is True)

no_disc_src = calculate_lcc(model_with(
    (cost_row("C", "construction", 0, 100.0),),
    discount_source_file="", discount_evidence_status="SOURCE-OPEN"))
check("discount rate without a source blocks the publication gate",
      no_disc_src["publication_source_gate"] is False
      and any("Discount rate" in i for i in no_disc_src["open_items"]))
check("discount geography is required",
      calculate_lcc(model_with((cost_row("C", "construction", 0, 100.0),),
                               discount_source_geography=""))["discount_source_complete"]
      is False)

# ── 13. Descriptors, geography and uniqueness (blocker 6) ─────────────────────
for field in ("unit", "category", "asset", "activity", "geography"):
    res = calculate_lcc(model_with((cost_row("DSC", "construction", 0, 100.0, **{field: ""}),)))
    check(f"blank {field} blocks the publication gate",
          res["publication_source_gate"] is False
          and any(f"missing {field}" in i for i in res["open_items"]))

check("missing source_location blocks the publication gate",
      calculate_lcc(model_with((cost_row("L", "construction", 0, 100.0, source_location=""),)
                               ))["publication_source_gate"] is False)

check("duplicate cost_id rejected inside the core",
      raises(lambda: calculate_lcc(model_with(
          (cost_row("DUP", "construction", 0, 1.0), cost_row("DUP", "operation", 1, 1.0))))))
check("duplicate residual_id rejected inside the core",
      raises(lambda: calculate_lcc(model_with(
          (), (residual_row("DR", 1, 1.0), residual_row("DR", 2, 1.0))))))

# ── 14. Structural validation ─────────────────────────────────────────────────
check("invalid phase rejected",
      raises(lambda: calculate_lcc(model_with((cost_row("B", "operations", 0, 1.0),)))))
check("missing cost_id rejected",
      raises(lambda: calculate_lcc(model_with((cost_row("", "construction", 0, 1.0),)))))
check("negative quantity rejected",
      raises(lambda: calculate_lcc(model_with(
          (cost_row("N", "construction", 0, 1.0, quantity=-1.0),)))))

# ── 15. Source audit completeness ─────────────────────────────────────────────
_audit_fields = {
    "cost_id", "phase", "category", "asset", "activity", "project_year",
    "calendar_year", "quantity", "unit", "unit_cost_base", "currency",
    "price_base_year", "escalation_rate", "base_amount", "future_amount",
    "present_value", "source_file", "source_location", "geography",
    "evidence_status", "source_complete", "note",
}
check("cost-row audit carries every required provenance field",
      _audit_fields <= set(r["cost_rows"][0]))
check("cost-row audit explains WHY a row is not publication-grade",
      "evidence_issues" in r["cost_rows"][0]
      and method_num["cost_rows"][0]["evidence_issues"])

# ── 16. Benefits never enter LCC ──────────────────────────────────────────────
check("LCC identity is exactly phases minus residual (no benefit term)",
      abs(r["lcc_npv"] - (r["pv_construction"] + r["pv_operation"]
                          + r["pv_maintenance_renewal"] + r["pv_end_of_life"]
                          - r["pv_residual"])) < 1e-12)

# ── 17. Empty phase is not a fabricated zero ──────────────────────────────────
check("empty phases are listed, not silently treated as documented zero",
      net_eol["empty_phases"] == ["construction", "maintenance_renewal", "operation"])
check("phase declarations are declared NOT yet implemented",
      r["phase_declarations_implemented"] is False)

# ── 18. Reference catalog + equation registry (blocker 7) ─────────────────────
integrity = lcc_reference_integrity_check()
check("LCC reference integrity has no structural issues", integrity["ok"] is True)
for issue in integrity["issues"]:
    print("   -", issue)

for eid in ("LCC-PV-01", "LCC-ESC-01", "LCC-BASE-01", "LCC-RESIDUAL-01", "LCC-NPV-01"):
    check(f"equation registry contains {eid}", eid in LCC_EQUATIONS)
for eid, eq in LCC_EQUATIONS.items():
    for sid in eq["source_ids"]:
        check(f"{eid}: source_id {sid} resolves", sid in LCC_REFERENCE_CATALOG)
    check(f"{eid}: states a limitation", bool(eq["limitation"].strip()))

check("present_value carries a Q1 companion alongside the standards",
      "ABOUHAMAD_2019_LCC_MC" in LCC_EQUATIONS["LCC-PV-01"]["source_ids"]
      and "ASTM_E917_2023" in LCC_EQUATIONS["LCC-PV-01"]["source_ids"]
      and "ISO_15686_5_2017" in LCC_EQUATIONS["LCC-PV-01"]["source_ids"])
check("PV equation is classified derived+method+Q1-supported, not 'a Q1 formula'",
      LCC_EQUATIONS["LCC-PV-01"]["reference_class"]
      == "REF-DERIVED | METHOD-REFERENCE | Q1-SUPPORTED")
check("canonical identity states that no single work prints it verbatim",
      "verbatim" in LCC_EQUATIONS["LCC-NPV-01"]["limitation"])

# Quartile wording: SCImago must be named; JCR must not be claimed.
_q1_records = [k for k, v in LCC_REFERENCE_CATALOG.items()
               if v["evidence_class"] == "REF-VERIFIED-Q1"]
check("Q1 records exist", len(_q1_records) >= 5)
for k in _q1_records:
    check(f"{k}: quartile stated as SJR 2024 Q1 (SCImago; Scopus-based data)",
          LCC_REFERENCE_CATALOG[k]["quartile_note"]
          == "SJR 2024 Q1 (SCImago; Scopus-based data)")
_src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "monorail_assessment/lcc/core.py"), encoding="utf-8").read()
check("no 'SJR/Scopus' wording remains anywhere in the core", "SJR/Scopus" not in _src)
check("no JCR quartile is claimed anywhere in the core", "JCR Q1" not in _src)
check("standards are never labelled Q1",
      LCC_REFERENCE_CATALOG["ASTM_E917_2023"]["evidence_class"] == "METHOD-REFERENCE"
      and LCC_REFERENCE_CATALOG["ISO_15686_5_2017"]["evidence_class"] == "METHOD-REFERENCE")

print("\nALL LCC SCIENTIFIC CORE TESTS PASSED" if ok else "\nSOME LCC CORE TESTS FAILED")
sys.exit(0 if ok else 1)
