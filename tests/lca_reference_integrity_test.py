"""Citation-freeze integrity suite.

Proves MECHANICALLY — not by prose assertion — that:
  * every REFERENCE_CATALOG record carries a full bibliographic identity;
  * every EQUATIONS entry is classified and resolves to real catalog sources;
  * every fixed empirical/derived factor names its source_id, file and exact location;
  * derived factors name their parent factors;
  * the internal project-audit workbook is never the sole basis of a direct-primary
    verification claim, and the ICE rows are not overstated as directly re-verified.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from lca_scientific_core import (
    ASSESSMENT_FACTOR_YEAR,
    REFERENCE_CATALOG,
    EQUATIONS,
    equation_registry_dataframe,
    factor_registry_dataframe,
    scientific_reference_integrity_check,
)

ok = True


def check(name, cond):
    global ok
    print(("PASS" if cond else "FAIL"), name)
    ok = ok and cond


integrity = scientific_reference_integrity_check()
check("reference integrity has no structural issues", integrity["ok"] is True)
if not integrity["ok"]:
    for issue in integrity["issues"]:
        print("  -", issue)

# ── The named sources the freeze requires, with full formal records ───────────
REQUIRED_SOURCES = [
    "RICS_WLCA_2024", "ISO_14040_2006", "ISO_14044_2006", "BS_EN_15804_A2",
    "BS_EN_17472_2022", "UK_GHG_2025_METHOD", "UK_GHG_2025_DATA", "ICE_V4_1_2025",
    "NTD_2024_ENERGY", "NTD_2024_SERVICE", "IEA_EF_2025", "IEA_LC_UPSTREAM_2025",
    "CLOSED_FACTOR_AUDIT",
]
for sid in REQUIRED_SOURCES:
    check(f"catalog contains {sid}", sid in REFERENCE_CATALOG)
for sid, rec in REFERENCE_CATALOG.items():
    for field in ("organization", "title", "identifier", "publisher", "evidence_status"):
        check(f"{sid}: has {field}", bool(str(rec.get(field, "")).strip()))

# The factor year is pinned on purpose; DESNZ 2026 must not silently replace 2025.
check("assessment factor year is pinned to 2025", ASSESSMENT_FACTOR_YEAR == 2025)
check("no 2026 DESNZ factor package is wired in as a used source",
      "UK_GHG_2026_DATA" not in REFERENCE_CATALOG)

# ── Equations ─────────────────────────────────────────────────────────────────
for equation_id, eq in EQUATIONS.items():
    check(f"{equation_id}: has reference_class", bool(eq.get("reference_class")))
    for sid in eq.get("source_ids", []):
        check(f"{equation_id}: source_id {sid} resolves", sid in REFERENCE_CATALOG)

# The E3 split must exist: one computational leg, plus the two RICS route equations.
for eid in ("E3_TRANSPORT_LEG", "E3A_RICS_A4", "E3C_RICS_C2"):
    check(f"equation registry contains {eid}", eid in EQUATIONS)
check("the superseded combined E3_A4_C2 id is gone", "E3_A4_C2" not in EQUATIONS)
check("E3_TRANSPORT_LEG is classified as an implementation identity, not RICS A4/C2",
      "ACCOUNTING-IDENTITY" in EQUATIONS["E3_TRANSPORT_LEG"]["reference_class"])
check("E2 is classified derived/conditional, not a verbatim universal standard formula",
      "REF-DERIVED" in EQUATIONS["E2_EFFECTIVE_EF"]["reference_class"])
check("E8 is classified as an algebraic derivation, not a verbatim RICS equation",
      "REF-DERIVED" in EQUATIONS["E8_WASTE_FROM_INSTALLED"]["reference_class"])
check("E6A annual-service model is registered and marked project-derived",
      "REF-DERIVED" in EQUATIONS["E6A_ANNUAL_SERVICE"]["reference_class"])
check("E11 Module D states the standard signed convention",
      "negative = potential benefit" in EQUATIONS["E11_MODULE_D"]["note"])
check("E11 Module D equation is the RICS Appendix K net-flow form",
      "EF_recovery_after_EoW - q_quality * EF_primary_substituted"
      in EQUATIONS["E11_MODULE_D"]["equation"])
check("E12 gross excludes Module D", "Module D is excluded" in EQUATIONS["E12_GROSS"]["note"])

# The equation audit that ships in S1 must carry the resolved bibliography.
_eq_df = equation_registry_dataframe()
for col in ("source_ids", "source_organizations", "source_titles", "source_identifiers",
            "source_editions_versions"):
    check(f"equation audit exposes {col}", col in _eq_df.columns)
check("equation audit resolves organizations for every equation",
      all(str(v).strip() for v in _eq_df["source_organizations"]))

# ── Factors ───────────────────────────────────────────────────────────────────
factors = factor_registry_dataframe()
check("factor registry is not empty", not factors.empty)
for col in ("source_id", "source_kind", "reference_class", "parent_factor_codes"):
    check(f"factor registry exposes {col}", col in factors.columns)

for _, row in factors.iterrows():
    value = row.get("value")
    kind = str(row.get("source_kind", ""))
    code = str(row.get("code", "?"))
    try:
        has_value = value is not None and float(value) == float(value)  # NaN-safe
    except (TypeError, ValueError):
        has_value = False
    if has_value and kind in {"empirical_factor", "default_rate", "derived_factor"}:
        check(f"{code}: has source_id", bool(str(row.get("source_id", "")).strip()))
        check(f"{code}: has source_file", bool(str(row.get("source_file", "")).strip()))
        check(f"{code}: has location", bool(str(row.get("location", "")).strip()))

# Derived factors must name their parents (WTW = direct + WTT, NTD = energy / service).
for _, row in factors.iterrows():
    if "derived" in str(row.get("source_kind", "")).lower():
        check(f"{row.get('code')}: derived factor names its parent factors",
              bool(row.get("parent_factor_codes")))

# Internal audit must never be the sole source of a direct-primary verified claim.
for _, row in factors.iterrows():
    direct_verified = "direct_primary_verified" in str(row.get("status", "")).lower()
    check(
        f"{row.get('code')}: internal audit not sole direct-primary source",
        not (direct_verified and row.get("source_id") == "CLOSED_FACTOR_AUDIT"),
    )

# ICE rows are traceable through the internal audit index only, and must say so.
_ice = factors[factors["source_id"] == "ICE_V4_1_2025"]
check("ICE factors are present", not _ice.empty)
for _, row in _ice.iterrows():
    check(f"{row['code']}: ICE status does not overstate direct-primary verification",
          str(row["status"]) == "verified_via_internal_audit_proxy_primary_recheck_required")
check("ICE catalog record flags the required primary recheck",
      REFERENCE_CATALOG["ICE_V4_1_2025"]["evidence_status"]
      == "REF-PROXY-PRIMARY-RECHECK-REQUIRED")
check("internal audit workbook is labelled not-a-primary-source",
      REFERENCE_CATALOG["CLOSED_FACTOR_AUDIT"]["evidence_status"]
      == "INTERNAL-AUDIT-NOT-PRIMARY-SOURCE")

print("\nREFERENCE INTEGRITY TESTS PASSED" if ok else "\nREFERENCE INTEGRITY TESTS FAILED")
sys.exit(0 if ok else 1)
