"""Acceptance tests for scientific LCC integration and phase closure."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from monorail_assessment.lcc.integration import run_scientific_lcc_from_params

ok = True


def check(name, cond):
    global ok
    print(("PASS" if cond else "FAIL"), name)
    ok = ok and bool(cond)


def base_payload():
    return {
        "project_name": "Cairo Monorail",
        "country": "Egypt",
        "region": "Cairo",
        "analysis_start_year": 2026,
        "assessment_lifetime": 20,
        "currency": "EGP",
        "price_base_year": 2026,
        "lcc_scientific_inputs": {
            "model": {
                "analysis_base_year": 2026,
                "analysis_period_years": 20,
                "currency": "EGP",
                "discount_rate": 0.05,
                "discount_basis": "real",
                "discount_source_file": "economic_assumptions.pdf",
                "discount_source_location": "Table 2, discount rate",
                "discount_evidence_status": "PROJECT-SPECIFIC",
                "discount_source_geography": "Cairo, Egypt",
                "analysis_period_source_file": "design_brief.pdf",
                "analysis_period_source_location": "Clause 3.2 design life",
                "analysis_period_evidence_status": "PROJECT-SPECIFIC",
                "analysis_period_geography": "Cairo, Egypt",
            },
            "cost_rows": [
                {
                    "cost_id": "CAPEX-001",
                    "phase": "construction",
                    "category": "civil works",
                    "asset": "monorail system",
                    "activity": "construction",
                    "project_year": 0,
                    "quantity": 1.0,
                    "unit": "lump_sum",
                    "unit_cost_base": 1000.0,
                    "currency": "EGP",
                    "price_base_year": 2026,
                    "escalation_rate": 0.0,
                    "source_file": "boq.xlsx",
                    "source_location": "Summary!B2",
                    "geography": "Cairo, Egypt",
                    "evidence_status": "PROJECT-SPECIFIC",
                },
                {
                    "cost_id": "OPEX-001",
                    "phase": "operation",
                    "category": "operations",
                    "asset": "monorail system",
                    "activity": "annual operations",
                    "project_year": 1,
                    "quantity": 1.0,
                    "unit": "year",
                    "unit_cost_base": 105.0,
                    "currency": "EGP",
                    "price_base_year": 2026,
                    "escalation_rate": 0.0,
                    "source_file": "om_budget.xlsx",
                    "source_location": "OPEX!C5",
                    "geography": "Cairo, Egypt",
                    "evidence_status": "PROJECT-SPECIFIC",
                },
            ],
            "residual_rows": [],
            "phase_declarations": {
                "construction": {"status": "HAS_ROWS"},
                "operation": {"status": "HAS_ROWS"},
                "maintenance_renewal": {
                    "status": "DOCUMENTED_ZERO",
                    "source_file": "scope_note.pdf",
                    "source_location": "Section 4",
                    "geography": "Cairo, Egypt",
                    "evidence_status": "PROJECT-SPECIFIC",
                    "justification": "Fixture declares no maintenance cost within the test scope.",
                },
                "end_of_life": {
                    "status": "NOT_APPLICABLE",
                    "source_file": "scope_note.pdf",
                    "source_location": "Section 5",
                    "geography": "Cairo, Egypt",
                    "evidence_status": "PROJECT-SPECIFIC",
                    "justification": "Fixture excludes end-of-life from this scoped test by documented declaration.",
                },
            },
        },
    }


r = run_scientific_lcc_from_params(base_payload())
check("complete fixture publication-ready", r.publication_gate["publication_ready"] is True)
check("numeric source gate ready", r.publication_gate["numeric_source_ready"] is True)
check("phase gate ready", r.publication_gate["phase_complete"] is True)
check("reference integrity ready", r.publication_gate["reference_integrity_ready"] is True)
check("integration supersedes old phase marker", r.result["phase_declarations_implemented"] is True)
check("phase declarations serialized", set(r.result["phase_declarations"]) == {"construction", "operation", "maintenance_renewal", "end_of_life"})
check("legacy fallback explicitly forbidden", r.publication_gate["legacy_fallback_allowed"] is False)

# Empty phase with no declaration must remain open.
p = base_payload()
p["lcc_scientific_inputs"]["phase_declarations"].pop("end_of_life")
r2 = run_scientific_lcc_from_params(p)
check("undeclared empty phase blocks publication", r2.publication_gate["publication_ready"] is False)
check("undeclared empty phase named", any("end_of_life" in x for x in r2.publication_gate["phase_issues"]))

# A method reference/status cannot certify a documented-zero project claim.
p = base_payload()
p["lcc_scientific_inputs"]["phase_declarations"]["maintenance_renewal"]["evidence_status"] = "METHOD-REFERENCE"
r3 = run_scientific_lcc_from_params(p)
check("method evidence cannot close numeric phase claim", r3.publication_gate["publication_ready"] is False)
check("authority problem named", any("PROJECT-SPECIFIC" in x for x in r3.publication_gate["phase_issues"]))

# Missing discount provenance remains blocked by the core numeric-source gate.
p = base_payload()
p["lcc_scientific_inputs"]["model"]["discount_source_file"] = ""
r4 = run_scientific_lcc_from_params(p)
check("missing discount source blocks publication", r4.publication_gate["publication_ready"] is False)
check("numeric source issue exposed", any("Discount rate" in x for x in r4.publication_gate["numeric_source_issues"]))

print("\nSCIENTIFIC LCC INTEGRATION TESTS PASSED" if ok else "\nSCIENTIFIC LCC INTEGRATION TESTS FAILED")
sys.exit(0 if ok else 1)
