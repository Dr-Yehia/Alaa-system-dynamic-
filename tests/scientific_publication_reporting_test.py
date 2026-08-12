"""Acceptance tests for cross-domain scientific publication reporting."""
import io
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from monorail_assessment.common.project_context import ProjectContext
from monorail_assessment.lcc.integration import ScientificLCCResult
from monorail_assessment.publication.orchestrator import DomainRun, ScientificPublicationBundle
from monorail_assessment.publication.reporting import (
    deterministic_export_parity_ok,
    deterministic_headline,
    deterministic_publication_csv,
    deterministic_publication_excel_bytes,
)

ok = True


def check(name, cond):
    global ok
    print(("PASS" if cond else "FAIL"), name)
    ok = ok and bool(cond)


class Ben:
    rows = []
    publication_gate = {"full_publication_ready": True}


ctx = ProjectContext(
    project_name="Fixture",
    country="Egypt",
    region="Cairo",
    analysis_base_year=2026,
    analysis_period_years=20,
    currency="EGP",
    price_base_year=2026,
)
lca_result = {
    "gross_A_C_tCO2e": 100.0,
    "GWP_kgCO2e_per_pkm": 0.05,
    "module_D1_signed_tCO2e_separate": -2.0,
    "reported_stage_tco2e": {"A1-A3": 40.0, "A4": 10.0, "A5": 5.0, "B2-B5": 5.0, "B6": 30.0, "C1-C4": 10.0},
    "stage_status": {"A1-A3": "connected", "A4": "connected", "A5": "connected", "B2-B5": "connected", "B6": "connected", "C1-C4": "connected"},
    "modules": {},
    "mass_balance": {},
    "closure_gate": {},
    "publication_readiness": {},
}
lcc_result = ScientificLCCResult(
    result={
        "currency": "EGP",
        "analysis_base_year": 2026,
        "analysis_period_years": 20,
        "discount_basis": "real",
        "discount_rate": 0.05,
        "lcc_npv": 500.0,
        "pv_construction": 400.0,
        "pv_operation": 60.0,
        "pv_maintenance_renewal": 30.0,
        "pv_end_of_life": 20.0,
        "pv_residual": 10.0,
        "cost_rows": [],
        "residual_rows": [],
        "phase_row_count": {},
        "phase_declarations": {},
    },
    publication_gate={"publication_ready": True},
    audit={},
)

bundle = ScientificPublicationBundle(
    context=ctx,
    lca=DomainRun("LCA", lca_result, True, True, "", {}),
    lcc=DomainRun("LCC", lcc_result, True, True, "", {}),
    benefits=DomainRun("K-Benefits", Ben(), True, True, "", {}),
    uncertainty=None,
    publication_gate={
        "deterministic_publication_ready": True,
        "uncertainty_ready": False,
        "full_q1_ready": False,
    },
)

h = deterministic_headline(bundle)
check("headline reads LCA", h["LCA Gross A-C (tCO2e)"] == 100.0)
check("headline reads LCC", h["LCC NPV"] == 500.0)
check("deterministic export parity", deterministic_export_parity_ok(bundle) is True)

csv = pd.read_csv(io.StringIO(deterministic_publication_csv(bundle)))
check("system CSV has metric/value", list(csv.columns) == ["metric", "value"])
xl = pd.ExcelFile(io.BytesIO(deterministic_publication_excel_bytes(bundle)))
check("system Excel contains summary/gates", {"System_Summary", "System_Gates"} <= set(xl.sheet_names))

blocked = ScientificPublicationBundle(
    context=ctx,
    lca=bundle.lca,
    lcc=bundle.lcc,
    benefits=bundle.benefits,
    uncertainty=None,
    publication_gate={"deterministic_publication_ready": False, "full_q1_ready": False},
)
check("blocked parity false", deterministic_export_parity_ok(blocked) is False)
refused = False
try:
    deterministic_publication_csv(blocked)
except ValueError:
    refused = True
check("blocked deterministic export refused", refused)

print("\nSCIENTIFIC PUBLICATION REPORTING TESTS PASSED" if ok else "\nSCIENTIFIC PUBLICATION REPORTING TESTS FAILED")
sys.exit(0 if ok else 1)
