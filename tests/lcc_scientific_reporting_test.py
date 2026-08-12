"""Acceptance tests for scientific LCC reporting/export parity."""
import io
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from monorail_assessment.lcc.integration import run_scientific_lcc_from_params
from monorail_assessment.lcc.reporting import (
    export_parity_ok,
    scientific_lcc_csv,
    scientific_lcc_excel_bytes,
    scientific_lcc_headline,
    scientific_lcc_report_text,
)

ok = True


def check(name, cond):
    global ok
    print(("PASS" if cond else "FAIL"), name)
    ok = ok and bool(cond)


def payload(complete=True):
    decl = {
        phase: {
            "status": "DOCUMENTED_ZERO",
            "source_file": "scope.pdf",
            "source_location": f"Section {phase}",
            "geography": "Cairo, Egypt",
            "evidence_status": "PROJECT-SPECIFIC",
            "justification": f"Test-only documented zero for {phase}",
        }
        for phase in ("operation", "maintenance_renewal", "end_of_life")
    }
    decl["construction"] = {"status": "HAS_ROWS"}
    if not complete:
        decl.pop("end_of_life")
    return {
        "analysis_start_year": 2026,
        "assessment_lifetime": 10,
        "currency": "EGP",
        "price_base_year": 2026,
        "country": "Egypt",
        "region": "Cairo",
        "lcc_scientific_inputs": {
            "model": {
                "discount_rate": 0.0,
                "discount_basis": "real",
                "discount_source_file": "econ.pdf",
                "discount_source_location": "p.2",
                "discount_evidence_status": "PROJECT-SPECIFIC",
                "discount_source_geography": "Cairo, Egypt",
                "analysis_period_source_file": "design.pdf",
                "analysis_period_source_location": "p.3",
                "analysis_period_evidence_status": "PROJECT-SPECIFIC",
                "analysis_period_geography": "Cairo, Egypt",
            },
            "cost_rows": [
                {
                    "cost_id": "C1",
                    "phase": "construction",
                    "category": "civil",
                    "asset": "system",
                    "activity": "build",
                    "project_year": 0,
                    "quantity": 2.0,
                    "unit": "item",
                    "unit_cost_base": 50.0,
                    "currency": "EGP",
                    "price_base_year": 2026,
                    "escalation_rate": 0.0,
                    "source_file": "boq.xlsx",
                    "source_location": "A1",
                    "geography": "Cairo, Egypt",
                    "evidence_status": "PROJECT-SPECIFIC",
                }
            ],
            "residual_rows": [],
            "phase_declarations": decl,
        },
    }


r = run_scientific_lcc_from_params(payload())
check("fixture publication-ready", r.publication_gate["publication_ready"] is True)
check("headline LCC exact", scientific_lcc_headline(r)["LCC NPV"] == 100.0)
check("serialized export parity", export_parity_ok(r) is True)

csv_df = pd.read_csv(io.StringIO(scientific_lcc_csv(r)))
check("CSV has metric/value", list(csv_df.columns) == ["metric", "value"])

xls = pd.ExcelFile(io.BytesIO(scientific_lcc_excel_bytes(r)))
needed = {"Summary", "Cost_Ledger", "Residual_Ledger", "Phase_Declarations", "Publication_Gate", "Open_Items", "Equation_Audit", "Reference_Registry"}
check("Excel contains audit sheets", needed <= set(xls.sheet_names))
check("report states publication ready", "publication_ready = True" in scientific_lcc_report_text(r))
check("report states benefits excluded", "Benefits are excluded" in scientific_lcc_report_text(r))

blocked = run_scientific_lcc_from_params(payload(complete=False))
check("blocked fixture parity false", export_parity_ok(blocked) is False)

csv_refused = False
try:
    scientific_lcc_csv(blocked)
except ValueError:
    csv_refused = True
check("blocked CSV refused", csv_refused)

excel_refused = False
try:
    scientific_lcc_excel_bytes(blocked)
except ValueError:
    excel_refused = True
check("blocked Excel refused", excel_refused)

print("\nSCIENTIFIC LCC REPORTING TESTS PASSED" if ok else "\nSCIENTIFIC LCC REPORTING TESTS FAILED")
sys.exit(0 if ok else 1)
