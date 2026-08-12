"""Cross-domain publication reporting for the scientific assessment bundle.

This module performs no LCA, LCC, Benefits or uncertainty science.  It serializes
already-computed scientific results and refuses to export when the relevant gate is
closed.  It is the final guard against accidental publication of a legacy/scenario
fallback.
"""

from __future__ import annotations

import io
from typing import Any

import pandas as pd

from scientific_publication_orchestrator import ScientificPublicationBundle


def publication_status_table(bundle: ScientificPublicationBundle) -> pd.DataFrame:
    rows = [
        {"domain": "LCA", "available": bundle.lca.available,
         "publication_ready": bundle.lca.publication_ready, "error": bundle.lca.error},
        {"domain": "LCC", "available": bundle.lcc.available,
         "publication_ready": bundle.lcc.publication_ready, "error": bundle.lcc.error},
        {"domain": "K-Benefits", "available": bundle.benefits.available,
         "publication_ready": bundle.benefits.publication_ready, "error": bundle.benefits.error},
    ]
    if bundle.uncertainty is not None:
        rows.append(
            {"domain": "Uncertainty", "available": bundle.uncertainty.available,
             "publication_ready": bundle.uncertainty.publication_ready,
             "error": bundle.uncertainty.error}
        )
    else:
        rows.append(
            {"domain": "Uncertainty", "available": False,
             "publication_ready": False, "error": "not supplied"}
        )
    return pd.DataFrame(rows)


def deterministic_headline(bundle: ScientificPublicationBundle) -> dict[str, Any]:
    if not bundle.publication_gate.get("deterministic_publication_ready"):
        raise ValueError("Deterministic scientific publication gate is closed")

    lca = bundle.lca.result
    lcc = bundle.lcc.result.result
    ben = bundle.benefits.result
    return {
        "Project": bundle.context.project_name,
        "Geography": bundle.context.geography,
        "Currency": bundle.context.currency,
        "Analysis base year": bundle.context.analysis_base_year,
        "Analysis period years": bundle.context.analysis_period_years,
        "LCA Gross A-C (tCO2e)": round(float(lca["gross_A_C_tCO2e"]), 6),
        "LCA GWP (kgCO2e/pkm)": round(float(lca["GWP_kgCO2e_per_pkm"]), 9),
        "LCA Module D1 standard-signed (tCO2e, separate)": round(
            float(lca.get("module_D1_signed_tCO2e_separate", 0.0)), 6
        ),
        "LCC NPV": round(float(lcc["lcc_npv"]), 6),
        "Benefits full publication ready": bool(ben.publication_gate.get("full_publication_ready")),
    }


def deterministic_publication_csv(bundle: ScientificPublicationBundle) -> str:
    h = deterministic_headline(bundle)
    return pd.DataFrame({"metric": list(h.keys()), "value": list(h.values())}).to_csv(index=False)


def _benefits_rows(bundle: ScientificPublicationBundle) -> pd.DataFrame:
    rows = []
    if bundle.benefits.result is not None:
        rows = list(getattr(bundle.benefits.result, "rows", []) or [])
    return pd.DataFrame(rows)


def _lca_stage_rows(bundle: ScientificPublicationBundle) -> pd.DataFrame:
    result = bundle.lca.result or {}
    reported = result.get("reported_stage_tco2e", {}) or {}
    status = result.get("stage_status", {}) or {}
    return pd.DataFrame(
        [
            {"stage": stage, "status": status.get(stage, ""), "reported_tCO2e": value}
            for stage, value in reported.items()
        ]
    )


def deterministic_publication_excel_bytes(bundle: ScientificPublicationBundle) -> bytes:
    if not bundle.publication_gate.get("deterministic_publication_ready"):
        raise ValueError("Deterministic scientific publication gate is closed")

    from lcc_scientific_reporting import scientific_lcc_excel_sheets
    from lca_scientific_reporting import scientific_excel_sheets

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        h = deterministic_headline(bundle)
        pd.DataFrame({"metric": list(h.keys()), "value": list(h.values())}).to_excel(
            writer, sheet_name="System_Summary", index=False
        )
        publication_status_table(bundle).to_excel(
            writer, sheet_name="System_Gates", index=False
        )
        _lca_stage_rows(bundle).to_excel(writer, sheet_name="LCA_Stages", index=False)
        _benefits_rows(bundle).to_excel(writer, sheet_name="Benefits_KPIs", index=False)

        for name, df in scientific_lcc_excel_sheets(bundle.lcc.result).items():
            sheet = ("LCC_" + name)[:31]
            (df if not df.empty else pd.DataFrame({"(empty)": []})).to_excel(
                writer, sheet_name=sheet, index=False
            )

        # Include the most reviewer-useful LCA audit sheets while avoiding Excel's
        # 31-character sheet-name limit and duplicate names.
        for name, df in scientific_excel_sheets(bundle.lca.result).items():
            sheet = ("LCA_" + name)[:31]
            if sheet in writer.sheets:
                continue
            (df if not df.empty else pd.DataFrame({"(empty)": []})).to_excel(
                writer, sheet_name=sheet, index=False
            )

    return buf.getvalue()


def full_q1_excel_bytes(bundle: ScientificPublicationBundle) -> bytes:
    """Full package including uncertainty; refuses export until full_q1_ready."""
    if not bundle.publication_gate.get("full_q1_ready"):
        raise ValueError("Full Q1 publication gate is closed")
    data = io.BytesIO(deterministic_publication_excel_bytes(bundle))
    # Rebuild into a new workbook so uncertainty sheets can be added without mutating
    # any domain-specific artifact.
    existing = pd.read_excel(data, sheet_name=None)
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        for name, df in existing.items():
            df.to_excel(writer, sheet_name=name[:31], index=False)
        u = bundle.uncertainty.result
        u.summary.to_excel(writer, sheet_name="Uncertainty_Summary", index=False)
        u.audit.to_excel(writer, sheet_name="Uncertainty_Audit", index=False)
        pd.DataFrame(
            [{"gate": k, "value": v} for k, v in u.publication_gate.items()
             if not isinstance(v, (list, dict))]
        ).to_excel(writer, sheet_name="Uncertainty_Gate", index=False)
    return out.getvalue()


def deterministic_export_parity_ok(bundle: ScientificPublicationBundle) -> bool:
    if not bundle.publication_gate.get("deterministic_publication_ready"):
        return False
    try:
        h = deterministic_headline(bundle)
        csv_df = pd.read_csv(io.StringIO(deterministic_publication_csv(bundle)))
        csv_map = {str(r["metric"]): str(r["value"]) for _, r in csv_df.iterrows()}
        xls = pd.read_excel(
            io.BytesIO(deterministic_publication_excel_bytes(bundle)),
            sheet_name="System_Summary",
        )
        xls_map = {str(r["metric"]): str(r["value"]) for _, r in xls.iterrows()}
    except Exception:
        return False
    for key, expected in h.items():
        if key not in csv_map or key not in xls_map:
            return False
        # Numeric fields are compared numerically; text/bool fields textually.
        if isinstance(expected, (int, float)) and not isinstance(expected, bool):
            try:
                if abs(float(csv_map[key]) - float(expected)) > 1e-9:
                    return False
                if abs(float(xls_map[key]) - float(expected)) > 1e-9:
                    return False
            except ValueError:
                return False
        else:
            if str(csv_map[key]) != str(expected) or str(xls_map[key]) != str(expected):
                return False
    return True
