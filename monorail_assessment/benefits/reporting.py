"""Traceable exports for the scientific Benefits domain.

WHY THE EXPORTS ARE VERBOSE
---------------------------
A reviewer working from a spreadsheet cannot click through the application. So
every exported row carries the whole chain in line: the KPI, the equation id,
the value and unit, the result group, the evidence state, the method reference
that authorises the formula, the numeric reference that certifies the project
number, the exact page, the DOI or official URL, the geography, the currency and
price base year where money is involved, and the limitation that stops the source
being over-claimed.

That is deliberately more columns than a summary table needs. The target is the
reviewer's question — "where did this number come from?" — answered without a
follow-up email.

WHAT THIS MODULE NEVER DOES
---------------------------
It recomputes nothing. Every value here was produced by `benefits_scientific_core`
and classified by `benefits_scientific_integration`; this module formats. If a
number could be produced here that does not exist there, the audit chain would
have a link with no equation behind it.

It also never invents a total. There is no "Total Benefits" row in any sheet,
for the same reason there is none in the result object.

Imports: pandas, the Benefits registry, and nothing else. No LCA engine, no LCC
engine, no Streamlit.
"""

from __future__ import annotations

import io
from typing import Any

import pandas as pd

from monorail_assessment.benefits.references import (
    BLOCKED_TOPICS,
    EQUATIONS,
    REFERENCES,
    equation_audit_rows,
    reference_registry_rows,
)


# ---------------------------------------------------------------------------
# Column contract
# ---------------------------------------------------------------------------

#: Every exported KPI row carries exactly these columns, in this order. The order
#: is part of the contract: a reviewer scanning several exports should find the
#: provenance columns in the same place every time.
EXPORT_COLUMNS = [
    "kpi_id",
    "equation_id",
    "kpi_name",
    "value",
    "unit",
    "result_group",
    "status",
    "evidence_status",
    "method_ref_ids",
    "numeric_source_ref_ids",
    "source_title",
    "source_file",
    "source_location",
    "doi",
    "official_url",
    "geography",
    "currency",
    "price_base_year",
    "limitations",
    "publication_eligible",
]

_GROUP_SHEETS = [
    ("physical", "Physical_Benefits"),
    ("monetized_cba", "Monetized_CBA"),
    ("economic_impact", "Economic_Impact"),
    ("employment", "Employment"),
]


def _scalar(value: Any) -> Any:
    """Flatten a composite KPI value into something a spreadsheet cell can hold.

    A dict or list value (a mode split, a vector of multipliers) is rendered as
    readable text rather than dropped, because losing it would leave a blank cell
    that reads as "not computed".
    """
    if value is None:
        return None
    if isinstance(value, dict):
        return "; ".join(f"{k}={v}" for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return "; ".join(str(v) for v in value)
    return value


def scientific_benefits_table(result) -> pd.DataFrame:
    """All KPI rows, one per line, with the full provenance chain."""
    rows = []
    for row in result.rows:
        rows.append({col: _scalar(row.get(col)) for col in EXPORT_COLUMNS})
    return pd.DataFrame(rows, columns=EXPORT_COLUMNS)


def scientific_benefits_group_table(result, group: str) -> pd.DataFrame:
    """The KPI rows belonging to one result group."""
    table = scientific_benefits_table(result)
    if table.empty:
        return table
    return table[table["result_group"] == group].reset_index(drop=True)


def scientific_benefits_summary_table(result) -> pd.DataFrame:
    """Gate state per group, plus the counts a reviewer checks first."""
    gate = result.publication_gate
    rows = result.rows
    summary = []
    for group_key, label in _GROUP_SHEETS:
        group_rows = [r for r in rows if r["result_group"] == group_key]
        summary.append(
            {
                "result_group": group_key,
                "sheet": label,
                "kpi_count": len(group_rows),
                "computed": sum(1 for r in group_rows if r["status"] == "COMPUTED"),
                "publication_eligible": sum(
                    1 for r in group_rows if r["publication_eligible"]
                ),
                "source_open": sum(1 for r in group_rows if r["status"] == "SOURCE-OPEN"),
                "blocked": sum(1 for r in group_rows if r["status"] == "BLOCKED"),
            }
        )
    summary.append(
        {
            "result_group": "GATE",
            "sheet": "publication_gate",
            "kpi_count": len(rows),
            "computed": int(gate["publication_ready"]),
            "publication_eligible": len(gate["eligible_kpi_ids"]),
            "source_open": len(gate["source_open_items"]),
            "blocked": len(gate["blocked_items"]),
        }
    )
    return pd.DataFrame(summary)


def scientific_benefits_source_open_table(result) -> pd.DataFrame:
    """What is missing, and what would close it.

    Exported as its own sheet because the open items are the actionable half of
    the result: they tell the project team which document to obtain next.
    """
    gate = result.publication_gate
    rows = []
    for item in gate["source_open_items"]:
        rows.append({"kind": "SOURCE-OPEN", "item": item, "closes_with": ""})
    for item in gate["blocked_items"]:
        topic = item.split(":", 1)[0].strip()
        rows.append(
            {
                "kind": "BLOCKED",
                "item": item,
                "closes_with": BLOCKED_TOPICS.get(topic, ""),
            }
        )
    for item in gate["warnings"]:
        rows.append({"kind": "NOT-ELIGIBLE", "item": item, "closes_with": ""})
    if not rows:
        rows.append({"kind": "NONE", "item": "no open or blocked items", "closes_with": ""})
    return pd.DataFrame(rows)


def scientific_benefits_equation_audit_table() -> pd.DataFrame:
    """The equation registry, flattened."""
    return pd.DataFrame(equation_audit_rows())


def scientific_benefits_reference_table() -> pd.DataFrame:
    """The reference registry, flattened."""
    return pd.DataFrame(reference_registry_rows())


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------


def scientific_benefits_csv(result) -> str:
    """One CSV holding every KPI row and its full provenance chain."""
    return scientific_benefits_table(result).to_csv(index=False)


# ---------------------------------------------------------------------------
# Source appendix
# ---------------------------------------------------------------------------


def scientific_benefits_source_appendix(result) -> str:
    """A plain-text appendix that walks a reviewer from each KPI to its source.

    Written as prose because it is meant to be pasted into a manuscript appendix,
    where a reader has no spreadsheet and no application.
    """
    gate = result.publication_gate
    lines: list[str] = []
    lines.append("SCIENTIFIC BENEFITS — SOURCE APPENDIX")
    lines.append("=" * 72)
    lines.append("")
    lines.append(
        "Every value below was produced by a registered equation from inputs whose "
        "provenance was checked separately. A method reference authorises the "
        "formula; it never certifies a project number."
    )
    lines.append("")
    lines.append(
        f"Publication-ready: {'YES' if gate['publication_ready'] else 'NO'}   "
        f"(eligible KPIs: {len(gate['eligible_kpi_ids'])}, "
        f"source-open: {len(gate['source_open_items'])}, "
        f"blocked: {len(gate['blocked_items'])})"
    )
    lines.append("")

    for group_key, label in _GROUP_SHEETS:
        group_rows = [r for r in result.rows if r["result_group"] == group_key]
        if not group_rows:
            continue
        lines.append("-" * 72)
        lines.append(label.replace("_", " ").upper())
        lines.append("-" * 72)
        for row in group_rows:
            value = _scalar(row["value"])
            lines.append(f"[{row['kpi_id']}] {row['kpi_name']}")
            lines.append(f"    value            : {'—' if value is None else value} {row['unit']}")
            lines.append(f"    equation         : {row['equation_id'] or 'n/a (reported figure)'}")
            if row["equation_id"] and row["equation_id"] in EQUATIONS:
                eq = EQUATIONS[row["equation_id"]]
                lines.append(f"    formula          : {eq.formula_text}")
                lines.append(f"    unit contract    : {eq.output_unit_contract}")
            lines.append(f"    evidence state   : {row['status']}"
                         f" (publication eligible: {'yes' if row['publication_eligible'] else 'no'})")
            if row["method_ref_ids"]:
                lines.append(f"    method source    : {row['method_ref_ids']}")
                lines.append(f"                       {row['method_source_title']}")
                lines.append(f"                       {row['method_source_location']}")
            if row["numeric_source_ref_ids"]:
                lines.append(f"    numeric source   : {row['numeric_source_ref_ids']}")
                lines.append(f"                       {row['source_title']}")
                lines.append(f"                       {row['source_location']}")
                if row["source_file"]:
                    lines.append(f"                       file: {row['source_file']}")
            if row["doi"]:
                lines.append(f"    DOI              : {row['doi']}")
            if row["official_url"]:
                lines.append(f"    URL              : {row['official_url']}")
            if row["geography"]:
                lines.append(f"    geography        : {row['geography']}")
            if row["currency"] or row["price_base_year"] is not None:
                lines.append(f"    monetary basis   : {row['currency'] or '?'}"
                             f", price base year {row['price_base_year'] if row['price_base_year'] is not None else '?'}")
            if row["evidence_gaps"]:
                lines.append(f"    evidence gaps    : {row['evidence_gaps']}")
            if row["limitations"]:
                lines.append(f"    limitations      : {row['limitations']}")
            if row["double_count_rule"]:
                lines.append(f"    double-count rule: {row['double_count_rule']}")
            if row["note"]:
                lines.append(f"    note             : {row['note']}")
            lines.append("")

    lines.append("-" * 72)
    lines.append("REFERENCE REGISTRY")
    lines.append("-" * 72)
    for ref in REFERENCES.values():
        lines.append(f"[{ref.ref_id}] {ref.title}")
        lines.append(f"    {ref.authors_or_issuer}, {ref.year} — {ref.document_type}")
        lines.append(f"    exact location : {ref.exact_location}")
        lines.append(f"    DOI            : {ref.doi}")
        lines.append(f"    URL            : {ref.official_url}")
        if ref.local_source_file and ref.local_source_file != "n/a":
            lines.append(f"    reviewed file  : {ref.local_source_file}")
        lines.append(f"    geography      : {ref.geography}")
        lines.append(f"    evidence role  : {ref.evidence_role}")
        if ref.limitations:
            lines.append(f"    limitations    : {ref.limitations}")
        lines.append("")

    lines.append("-" * 72)
    lines.append("DELIBERATELY ABSENT")
    lines.append("-" * 72)
    for topic, reason in BLOCKED_TOPICS.items():
        lines.append(f"[{topic}] {reason}")
        lines.append("")

    lines.append("-" * 72)
    lines.append("DOUBLE-COUNT RULES")
    lines.append("-" * 72)
    for rule in result.audit["double_count_rules"]:
        lines.append(f"  * {rule}")
    lines.append("")
    lines.append(
        "There is no combined 'Total Benefits' figure. Avoided tCO2e, monetised "
        "hours, gross economic output and job counts are not commensurable."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Excel
# ---------------------------------------------------------------------------

#: Sheet order, chosen so a reviewer reads outward from the summary to the raw
#: registries rather than having to assemble the picture themselves.
EXCEL_SHEETS = [
    "Benefits_Summary",
    "Physical_Benefits",
    "Monetized_CBA",
    "Economic_Impact",
    "Employment",
    "Equation_Audit",
    "Reference_Registry",
    "Source_Open_Items",
]


def scientific_benefits_excel_bytes(result) -> bytes:
    """The eight-sheet workbook, in the order declared by EXCEL_SHEETS."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        scientific_benefits_summary_table(result).to_excel(
            writer, sheet_name="Benefits_Summary", index=False
        )
        for group_key, sheet in _GROUP_SHEETS:
            table = scientific_benefits_group_table(result, group_key)
            if table.empty:
                # An empty group still gets its sheet, carrying the column
                # contract, so a reader can tell "no rows" from "sheet missing".
                table = pd.DataFrame(columns=EXPORT_COLUMNS)
            table.to_excel(writer, sheet_name=sheet, index=False)
        scientific_benefits_equation_audit_table().to_excel(
            writer, sheet_name="Equation_Audit", index=False
        )
        scientific_benefits_reference_table().to_excel(
            writer, sheet_name="Reference_Registry", index=False
        )
        scientific_benefits_source_open_table(result).to_excel(
            writer, sheet_name="Source_Open_Items", index=False
        )
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Export parity
# ---------------------------------------------------------------------------


def export_parity_ok(result) -> tuple[bool, list[str]]:
    """Confirm the exports say exactly what the result object says.

    Exports drift. A column gets renamed, a filter is added "temporarily", and a
    spreadsheet starts telling a slightly different story from the screen. This
    check compares the two directly and returns the mismatches.
    """
    problems: list[str] = []

    table = scientific_benefits_table(result)
    if len(table) != len(result.rows):
        problems.append(
            f"CSV table has {len(table)} rows for {len(result.rows)} KPI rows"
        )

    for column in EXPORT_COLUMNS:
        if column not in table.columns:
            problems.append(f"export is missing the {column!r} column")

    by_id = {r["kpi_id"]: r for r in result.rows}
    for _, exported in table.iterrows():
        source = by_id.get(exported["kpi_id"])
        if source is None:
            problems.append(f"exported KPI {exported['kpi_id']!r} is not in the result")
            continue
        if _scalar(source["value"]) != exported["value"] and not (
            source["value"] is None and pd.isna(exported["value"])
        ):
            problems.append(
                f"{exported['kpi_id']}: exported value {exported['value']!r} != "
                f"result value {source['value']!r}"
            )
        if source["publication_eligible"] != bool(exported["publication_eligible"]):
            problems.append(
                f"{exported['kpi_id']}: exported eligibility disagrees with the result"
            )
        if source["status"] != exported["status"]:
            problems.append(f"{exported['kpi_id']}: exported status disagrees with the result")

    # No export may contain a scientific number without a resolvable equation and
    # an evidence chain. The chain is normally a registered REF-* id, but some
    # project evidence has no registry entry by nature — a GIS layer or a survey
    # is project data, not a method document — so a declared source file and
    # exact location satisfies it equally. What is never acceptable is an
    # eligible value whose only provenance is the method reference behind its
    # equation, because that would be a method source certifying a number.
    for row in result.rows:
        if row["value"] is None or not row["publication_eligible"]:
            continue
        if row["equation_id"] and row["equation_id"] not in EQUATIONS:
            problems.append(f"{row['kpi_id']}: cites unregistered equation {row['equation_id']!r}")

        has_numeric_ref = bool(str(row["numeric_source_ref_ids"]).strip())
        declared_location = str(row["source_location"]).strip()
        has_declared_source = bool(
            str(row["source_file"]).strip()
            or (declared_location and declared_location != str(row["method_source_location"]).strip())
        )
        if not (has_numeric_ref or has_declared_source):
            problems.append(
                f"{row['kpi_id']}: publication-eligible with no numeric source and no "
                "declared project source"
            )
        for ref_id in filter(None, str(row["numeric_source_ref_ids"]).split("; ")):
            if ref_id not in REFERENCES:
                problems.append(f"{row['kpi_id']}: cites unregistered reference {ref_id!r}")

    appendix = scientific_benefits_source_appendix(result)
    for row in result.rows:
        if row["kpi_id"] not in appendix:
            problems.append(f"{row['kpi_id']} is absent from the source appendix")

    return (not problems), problems
