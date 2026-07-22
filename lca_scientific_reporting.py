"""Canonical scientific-engine exports.

Every publication output — the headline cards, the text report, the CSV and the Excel
workbook — is derived HERE from the single `scientific_lca` result, so they are numerically
identical by construction (export parity). The legacy engine never feeds these.
"""
from __future__ import annotations

import io
from typing import Any, Mapping

import pandas as pd


def scientific_headline(scientific_lca: Mapping[str, Any]) -> dict:
    """The canonical headline numbers used by the cards, CSV and Excel alike."""
    reported = scientific_lca.get("reported_stage_tco2e", {})
    return {
        "Gross A-C (tCO2e)": round(float(scientific_lca.get("gross_A_C_tCO2e", 0.0)), 6),
        "GWP (kgCO2e/pkm)": round(float(scientific_lca.get("GWP_kgCO2e_per_pkm", 0.0)), 9),
        "Module D (tCO2e, separate)": round(float(scientific_lca.get("module_D1_signed_tCO2e_separate", 0.0)), 6),
        "Lifetime passenger-km": round(float(scientific_lca.get("lifetime_pkm", 0.0)), 3),
        "A1-A3 (tCO2e)": round(float(reported.get("A1-A3", 0.0)), 6),
        "A4 (tCO2e)": round(float(reported.get("A4", 0.0)), 6),
        "A5 (tCO2e)": round(float(reported.get("A5", 0.0)), 6),
        "B2-B5 (tCO2e)": round(float(reported.get("B2-B5", 0.0)), 6),
        "B6 (tCO2e)": round(float(reported.get("B6", 0.0)), 6),
        "C1-C4 (tCO2e)": round(float(reported.get("C1-C4", 0.0)), 6),
    }


def scientific_csv(scientific_lca: Mapping[str, Any]) -> str:
    """CSV of the canonical headline (same numbers as the cards)."""
    h = scientific_headline(scientific_lca)
    lines = ["metric,value"]
    lines += [f"{k},{v}" for k, v in h.items()]
    return "\n".join(lines) + "\n"


def scientific_report_text(scientific_lca: Mapping[str, Any]) -> str:
    """Plain-text report; Module D is always shown SEPARATELY, never inside gross."""
    h = scientific_headline(scientific_lca)
    gate = scientific_lca.get("closure_gate", {})
    lines = [
        "MONORAIL LCA — SCIENTIFIC ENGINE (canonical report)",
        "=" * 52,
        scientific_lca.get("scope_label", ""),
        "",
        f"Gross A-C .............. {h['Gross A-C (tCO2e)']:,.3f} tCO2e",
        f"GWP per passenger-km ... {h['GWP (kgCO2e/pkm)']:.6f} kgCO2e/pkm",
        "",
        "Stage contribution (reported scope):",
    ]
    for stg in ("A1-A3", "A4", "A5", "B2-B5", "B6", "C1-C4"):
        lines.append(f"  {stg:<7} {h[stg + ' (tCO2e)']:,.3f} tCO2e")
    lines += [
        "",
        f"Module D (reported SEPARATELY, NOT in gross): {h['Module D (tCO2e, separate)']:,.3f} tCO2e",
        "",
        "Closure gate:",
        f"  full_wlca_calculation_complete      = {gate.get('full_wlca_calculation_complete')}",
        f"  standards_reporting_complete        = {gate.get('standards_reporting_complete')}",
        f"  lca_application_end_to_end_complete = {gate.get('lca_application_end_to_end_complete')}",
        f"  q1_evidence_ready                   = {gate.get('q1_evidence_ready')}",
    ]
    return "\n".join(lines) + "\n"


# The 15 Supplementary-S1 / audit sheet names (order fixed for reviewers).
S1_SHEETS = [
    "Summary", "Stage_Results", "A1_A3_Materials", "Transport_Legs", "A5_Activities",
    "B2_B5_Events", "C1_C4", "Module_D_Separate", "Mass_Balance", "Activity_Data_Audit",
    "Factor_Source_Audit", "Equation_Audit", "Open_Items", "Uncertainty", "Publication_Gates",
]


def scientific_excel_sheets(scientific_lca: Mapping[str, Any]) -> "dict[str, pd.DataFrame]":
    """Build the Supplementary-S1 sheet set as DataFrames (all from scientific_lca)."""
    mods = scientific_lca.get("modules", {})
    reported = scientific_lca.get("reported_stage_tco2e", {})
    diag = scientific_lca.get("diagnostic_stage_tco2e", {})
    sstat = scientific_lca.get("stage_status", {})
    h = scientific_headline(scientific_lca)

    def _df(rows):
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    sheets = {
        "Summary": _df([{"metric": k, "value": v} for k, v in h.items()]),
        "Stage_Results": _df([{"stage": s, "status": sstat.get(s, "?"),
                               "reported_tCO2e": reported.get(s, 0.0),
                               "diagnostic_tCO2e": diag.get(s, 0.0)} for s in diag]),
        "A1_A3_Materials": _df(mods.get("A1_A3", {}).get("by_material", [])),
        "Transport_Legs": _df(mods.get("A4", {}).get("activity_audit", [])),
        "A5_Activities": _df([{"component": k, "value": v}
                              for k, v in (mods.get("A5", {}).get("rics_subdivision", {}) or {}).items()]),
        "B2_B5_Events": _df(mods.get("B2_B5", {}).get("events", [])),
        "C1_C4": _df(mods.get("C1_C4", {}).get("treatment_rows", [])),
        "Module_D_Separate": _df(mods.get("D1", {}).get("rows", [])),
        "Mass_Balance": _df(scientific_lca.get("mass_balance", {}).get("rows", [])),
        "Activity_Data_Audit": _df(mods.get("A4", {}).get("activity_audit", [])),
        "Factor_Source_Audit": (scientific_lca.get("source_audit")
                                if isinstance(scientific_lca.get("source_audit"), pd.DataFrame)
                                else pd.DataFrame()),
        "Equation_Audit": (scientific_lca.get("equation_audit")
                           if isinstance(scientific_lca.get("equation_audit"), pd.DataFrame)
                           else pd.DataFrame()),
        "Open_Items": _df([{"item": k, "status": v.get("status"), "needed": v.get("needed")}
                           for k, v in _open_items().items()]),
        "Uncertainty": _df([{"note": "Scientific Monte Carlo re-runs the core per sample (pending wiring)."}]),
        "Publication_Gates": _df([{"gate": k, "value": v}
                                  for k, v in (scientific_lca.get("closure_gate", {}) or {}).items()]
                                 + [{"gate": k, "value": v}
                                    for k, v in (scientific_lca.get("publication_readiness", {}) or {}).items()]),
    }
    return {name: sheets.get(name, pd.DataFrame()) for name in S1_SHEETS}


def _open_items():
    try:
        from lca_scientific_core import OPEN_SOURCE_REQUIREMENTS
        return OPEN_SOURCE_REQUIREMENTS
    except Exception:
        return {}


def scientific_excel_bytes(scientific_lca: Mapping[str, Any]) -> bytes:
    """Write the S1 workbook to bytes (Summary numbers identical to the cards/CSV)."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        for name, df in scientific_excel_sheets(scientific_lca).items():
            (df if not df.empty else pd.DataFrame({"(empty)": []})).to_excel(
                xw, sheet_name=name[:31], index=False)
    return buf.getvalue()


def export_parity_ok(scientific_lca: Mapping[str, Any]) -> bool:
    """True when the headline, the CSV and the Excel Summary carry identical numbers."""
    h = scientific_headline(scientific_lca)
    # CSV parity.
    csv_map = {}
    for line in scientific_csv(scientific_lca).strip().splitlines()[1:]:
        k, v = line.rsplit(",", 1)
        csv_map[k] = float(v)
    if any(abs(csv_map.get(k, None) - float(v)) > 1e-9 for k, v in h.items()):
        return False
    # Excel Summary parity.
    summary = scientific_excel_sheets(scientific_lca)["Summary"]
    xl_map = {r["metric"]: float(r["value"]) for _, r in summary.iterrows()}
    return all(abs(xl_map.get(k, None) - float(v)) <= 1e-9 for k, v in h.items())
