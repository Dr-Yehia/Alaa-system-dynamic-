"""Mechanical purity contract for the publication-only Streamlit app."""
import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "app_scientific_publication.py")
src = open(APP, encoding="utf-8").read()
tree = ast.parse(src)

ok = True


def check(name, cond):
    global ok
    print(("PASS" if cond else "FAIL"), name)
    ok = ok and bool(cond)


imports = set()
for node in ast.walk(tree):
    if isinstance(node, ast.ImportFrom) and node.module:
        imports.add(node.module.split(".")[0])
    elif isinstance(node, ast.Import):
        imports.update(alias.name.split(".")[0] for alias in node.names)

for forbidden in (
    "legacy_lca_engine",
    "legacy_lcc_engine",
    "benefits_core",
    "assessment_orchestrator",
    "uncertainty_orchestrator",
):
    check(f"publication app does not import {forbidden}", forbidden not in imports)

for required in (
    "scientific_publication_orchestrator",
    "scientific_publication_reporting",
    "scientific_uncertainty",
):
    check(f"publication app imports {required}", required in imports)

check("publication app explicitly states no legacy fallback", "No legacy fallback" in src)
check("publication app contains no run_full_assessment call", "run_full_assessment(" not in src)
check("publication app contains no calculate_legacy call", "calculate_legacy" not in src)
check("publication exports are gated", "deterministic_publication_ready" in src and "deterministic_export_parity_ok" in src)
check("full Q1 export is separately gated", "full_q1_ready" in src and "full_q1_excel_bytes" in src)

# Presentation code may READ canonical result keys such as GWP_kgCO2e_per_pkm.
# Therefore purity is tested against actual arithmetic signatures, not scientific
# vocabulary appearing in a display label/key.
for fragment in (
    "np.linalg",
    "math.log(",
    "** project_year",
    "* carbon_intensity",
    "* emission_factor",
    "/ lifetime_pkm",
    "0.5 * generated",
):
    check(f"publication app contains no scientific arithmetic fragment {fragment!r}", fragment not in src.lower())

print("\nPUBLICATION APP PURITY VERIFIED" if ok else "\nPUBLICATION APP PURITY VIOLATED")
sys.exit(0 if ok else 1)
