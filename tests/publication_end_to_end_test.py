"""End-to-end safety tests for the canonical scientific publication bundle.

This suite intentionally starts from an evidence-empty project.  The correct result is
not a plausible legacy number; it is an explicit closed publication gate.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scientific_publication_orchestrator import run_scientific_publication_bundle

ok = True


def check(name, cond):
    global ok
    print(("PASS" if cond else "FAIL"), name)
    ok = ok and bool(cond)


bundle = run_scientific_publication_bundle(
    {
        "project_name": "Cairo Monorail",
        "country": "Egypt",
        "region": "Cairo",
        "analysis_start_year": 2026,
        "assessment_lifetime": 50,
        "currency": "EGP",
        "price_base_year": 2026,
        # Deliberately no scientific evidence payloads.
    }
)

check("publication bundle returns all three domains", {bundle.lca.name, bundle.lcc.name, bundle.benefits.name} == {"LCA", "LCC", "K-Benefits"})
check("empty evidence cannot be deterministic-publication-ready", bundle.publication_gate["deterministic_publication_ready"] is False)
check("empty evidence cannot be full-Q1-ready", bundle.publication_gate["full_q1_ready"] is False)
check("uncertainty absent is named open", "Uncertainty" in bundle.publication_gate["open_domains"])
check("legacy fallback forbidden globally", bundle.publication_gate["legacy_fallback_allowed"] is False)
check("LCA legacy fallback forbidden on failure", bundle.lca.gate.get("legacy_fallback_allowed", False) is False)
check("LCC legacy fallback forbidden on failure", bundle.lcc.gate.get("legacy_fallback_allowed", False) is False)
check("Benefits legacy fallback forbidden on failure", bundle.benefits.gate.get("legacy_fallback_allowed", False) is False)

# A supplied uncertainty object cannot make the system ready when deterministic
# scientific domains are still blocked.
class DummyUncertainty:
    publication_gate = {"publication_ready": True}

bundle2 = run_scientific_publication_bundle(
    {
        "analysis_start_year": 2026,
        "assessment_lifetime": 50,
        "currency": "EGP",
        "price_base_year": 2026,
    },
    uncertainty_result=DummyUncertainty(),
)
check("uncertainty ready flag can be true independently", bundle2.publication_gate["uncertainty_ready"] is True)
check("uncertainty cannot override deterministic evidence gaps", bundle2.publication_gate["full_q1_ready"] is False)

print("\nPUBLICATION END-TO-END SAFETY TESTS PASSED" if ok else "\nPUBLICATION END-TO-END SAFETY TESTS FAILED")
sys.exit(0 if ok else 1)
