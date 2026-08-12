"""Canonical reporting/export layer for the scientific LCC domain.

No LCC arithmetic is performed here.  Every value is read from the
``ScientificLCCResult`` produced by ``lcc_scientific_integration``.  Publication
exports fail closed: callers receive no publication artifact unless the LCC
publication gate is open and the serialized CSV/Excel values round-trip to the same
headline numbers.
"""

from __future__ import annotations

import io
from typing import Any

import pandas as pd

from lcc_scientific_integration import ScientificLCCResult
from lcc_scientific_core import LCC_EQUATIONS, LCC_REFERENCE_CATALOG


SUMMARY_FIELDS = (
    ("LCC NPV", "lcc_npv"),
    ("PV Construction", "pv_construction"),
    ("PV Operation", "pv_operation"),
    ("PV Maintenance & Renewal", "pv_maintenance_renewal"),
    ("PV End of Life", "pv_end_of_life"),
    ("PV Residual / Recovery", "pv_residual"),
)


def _coerce(result: ScientificLCCResult | dict[str, Any]) -> ScientificLCCResult:
    if isinstance(result, ScientificLCCResult):
        return result
    if isinstance(result, dict) and {"result", "publication_gate", "audit"} <= set(result):
        return ScientificLCCResult(
            result=dict(result["result"]),
            publication_gate=dict(result["publication_gate"]),
            audit=dict(result["audit"]),
        )
    raise TypeError("scientific LCC reporting requires ScientificLCCResult")


def scientific_lcc_headline(result: ScientificLCCResult | dict[str, Any]) -> dict[str, Any]:
    r = _coerce(result)
    values = r.result
    out: dict[str, Any] = {
        "Currency": values.get("currency", ""),
        "Analysis Base Year": values.get("analysis_base_year"),
        "Analysis Period (years)": values.get("analysis_period_years"),
        "Discount Basis": values.get("discount_basis", ""),
        "Discount Rate": values.get("discount_rate"),
        "Publication Ready": bool(r.publication_gate.get("publication_ready")),
    }
    for label, key in SUMMARY_FIELDS:
        value = values.get(key)
        out[label] = None if value is None else round(float(value), 6)
    return out


def scientific_lcc_table(result: ScientificLCCResult | dict[str, Any]) -> pd.DataFrame:
    h = scientific_lcc_headline(result)
    return pd.DataFrame({"metric": list(h.keys()), "value": list(h.values())})


def scientific_lcc_csv(result: ScientificLCCResult | dict[str, Any]) -> str:
    r = _coerce(result)
    if not r.publication_gate.get("publication_ready"):
        raise ValueError("Scientific LCC publication gate is closed; CSV export refused")
    return scientific_lcc_table(r).to_csv(index=False)


def _phase_table(r: ScientificLCCResult) -> pd.DataFrame:
    rows = []
    counts = r.result.get("phase_row_count", {}) or {}
    declarations = r.result.get("phase_declarations", {}) or {}
    for phase in sorted(set(counts) | set(declarations)):
        d = declarations.get(phase, {}) or {}
        rows.append(
            {
                "phase": phase,
                "row_count": counts.get(phase, 0),
                "declaration_status": d.get("status", ""),
                "evidence_status": d.get("evidence_status", ""),
                "source_file": d.get("source_file", ""),
                "source_location": d.get("source_location", ""),
                "geography": d.get("geography", ""),
                "justification": d.get("justification", ""),
            }
        )
    return pd.DataFrame(rows)


def _equation_table() -> pd.DataFrame:
    rows = []
    for eq_id, eq in LCC_EQUATIONS.items():
        rows.append(
            {
                "equation_id": eq_id,
                "name": eq.get("name", ""),
                "equation": eq.get("equation", ""),
                "unit_check": eq.get("unit_check", ""),
                "reference_class": eq.get("reference_class", ""),
                "source_ids": "; ".join(eq.get("source_ids") or []),
                "role": eq.get("role", ""),
                "limitation": eq.get("limitation", ""),
            }
        )
    return pd.DataFrame(rows)


def _reference_table() -> pd.DataFrame:
    rows = []
    for source_id, rec in LCC_REFERENCE_CATALOG.items():
        rows.append({"source_id": source_id, **rec})
    return pd.DataFrame(rows)


def scientific_lcc_excel_sheets(
    result: ScientificLCCResult | dict[str, Any],
) -> dict[str, pd.DataFrame]:
    r = _coerce(result)
    values = r.result
    gate = r.publication_gate
    return {
        "Summary": scientific_lcc_table(r),
        "Cost_Ledger": pd.DataFrame(values.get("cost_rows") or []),
        "Residual_Ledger": pd.DataFrame(values.get("residual_rows") or []),
        "Phase_Declarations": _phase_table(r),
        "Publication_Gate": pd.DataFrame(
            [{"gate": k, "value": v} for k, v in gate.items() if not isinstance(v, list)]
        ),
        "Open_Items": pd.DataFrame(
            [{"type": "numeric_source", "item": x} for x in gate.get("numeric_source_issues", [])]
            + [{"type": "phase", "item": x} for x in gate.get("phase_issues", [])]
            + [{"type": "reference", "item": x} for x in gate.get("reference_issues", [])]
        ),
        "Equation_Audit": _equation_table(),
        "Reference_Registry": _reference_table(),
    }


def scientific_lcc_excel_bytes(result: ScientificLCCResult | dict[str, Any]) -> bytes:
    r = _coerce(result)
    if not r.publication_gate.get("publication_ready"):
        raise ValueError("Scientific LCC publication gate is closed; Excel export refused")
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for name, df in scientific_lcc_excel_sheets(r).items():
            if df.empty:
                df = pd.DataFrame({"(empty)": []})
            df.to_excel(writer, sheet_name=name[:31], index=False)
    return buf.getvalue()


def export_parity_ok(result: ScientificLCCResult | dict[str, Any]) -> bool:
    """Verify the actual serialized CSV and Excel Summary match the headline."""
    r = _coerce(result)
    if not r.publication_gate.get("publication_ready"):
        return False
    headline = scientific_lcc_headline(r)
    try:
        csv_df = pd.read_csv(io.StringIO(scientific_lcc_csv(r)))
        csv_map = {str(row["metric"]): row["value"] for _, row in csv_df.iterrows()}
        xls = pd.read_excel(io.BytesIO(scientific_lcc_excel_bytes(r)), sheet_name="Summary")
        xls_map = {str(row["metric"]): row["value"] for _, row in xls.iterrows()}
    except Exception:
        return False

    for label, key in SUMMARY_FIELDS:
        expected = headline[label]
        try:
            cv = float(csv_map[label])
            xv = float(xls_map[label])
        except (KeyError, TypeError, ValueError):
            return False
        if expected is None:
            return False
        if abs(cv - float(expected)) > 1e-9 or abs(xv - float(expected)) > 1e-9:
            return False
    return True


def scientific_lcc_report_text(result: ScientificLCCResult | dict[str, Any]) -> str:
    r = _coerce(result)
    h = scientific_lcc_headline(r)
    gate = r.publication_gate
    lines = [
        "MONORAIL LIFE-CYCLE COST — SCIENTIFIC ENGINE",
        "=" * 48,
        f"Currency: {h['Currency']}",
        f"Analysis base year: {h['Analysis Base Year']}",
        f"Analysis period: {h['Analysis Period (years)']} years",
        f"Discount basis/rate: {h['Discount Basis']} / {h['Discount Rate']}",
        "",
        f"LCC NPV: {h['LCC NPV']}",
        f"PV Construction: {h['PV Construction']}",
        f"PV Operation: {h['PV Operation']}",
        f"PV Maintenance & Renewal: {h['PV Maintenance & Renewal']}",
        f"PV End of Life: {h['PV End of Life']}",
        f"PV Residual / Recovery (subtracted once): {h['PV Residual / Recovery']}",
        "",
        f"publication_ready = {gate.get('publication_ready')}",
        f"numeric_source_ready = {gate.get('numeric_source_ready')}",
        f"phase_complete = {gate.get('phase_complete')}",
        f"reference_integrity_ready = {gate.get('reference_integrity_ready')}",
        "Benefits are excluded from LCC NPV by design.",
    ]
    if not gate.get("publication_ready"):
        lines.append("OPEN ITEMS:")
        for item in (
            list(gate.get("numeric_source_issues", []))
            + list(gate.get("phase_issues", []))
            + list(gate.get("reference_issues", []))
        ):
            lines.append(f"- {item}")
    return "\n".join(lines) + "\n"
