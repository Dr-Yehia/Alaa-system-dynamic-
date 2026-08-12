"""Evidence-aware integration for the canonical scientific LCC core.

This module is the publication boundary between the UI/project payload and
``lcc_scientific_core``.  It performs no life-cycle-cost arithmetic itself: all
money equations remain in the core.  Its responsibilities are deliberately
limited to:

* converting structured project inputs into ``CostRow`` / ``ResidualRow`` /
  ``LCCModel`` objects;
* enforcing the distinction between method evidence and project numeric evidence;
* closing phase completeness explicitly instead of treating an empty phase as zero;
* exposing a fail-closed publication gate and a machine-readable audit trail.

A phase is complete only when one of the following is true:

1. ``HAS_ROWS`` — at least one sourced cost row exists in that phase;
2. ``DOCUMENTED_ZERO`` — an authoritative project source states the phase cost is
   zero in the declared scope;
3. ``NOT_APPLICABLE`` — an authoritative project source plus justification states
   the phase does not apply.

Anything else remains ``SOURCE-OPEN``.  A method paper or standard can support an
LCC equation, but it can never certify a Cairo project cost or a zero-cost phase.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

from lcc_scientific_core import (
    ALLOWED_PHASES,
    PUBLICATION_ACCEPTABLE_NUMERIC_EVIDENCE,
    CostRow,
    LCCModel,
    ResidualRow,
    ScientificLCCInputError,
    calculate_lcc,
    lcc_reference_integrity_check,
)
from project_context import ProjectContext, context_from_params


PHASE_HAS_ROWS = "HAS_ROWS"
PHASE_DOCUMENTED_ZERO = "DOCUMENTED_ZERO"
PHASE_NOT_APPLICABLE = "NOT_APPLICABLE"
PHASE_SOURCE_OPEN = "SOURCE-OPEN"
ALLOWED_PHASE_DECLARATIONS = {
    PHASE_HAS_ROWS,
    PHASE_DOCUMENTED_ZERO,
    PHASE_NOT_APPLICABLE,
    PHASE_SOURCE_OPEN,
}


@dataclass(frozen=True)
class PhaseDeclaration:
    """Evidence that explains why a life-cycle phase has no ledger rows."""

    phase: str
    status: str = PHASE_SOURCE_OPEN
    source_file: str = ""
    source_location: str = ""
    geography: str = ""
    evidence_status: str = "SOURCE-OPEN"
    justification: str = ""


@dataclass(frozen=True)
class ScientificLCCResult:
    """Canonical LCC result plus integration/publication audit metadata."""

    result: dict = field(default_factory=dict)
    publication_gate: dict = field(default_factory=dict)
    audit: dict = field(default_factory=dict)

    @property
    def lcc_npv(self) -> float | None:
        value = self.result.get("lcc_npv")
        return None if value is None else float(value)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _exact_int(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise ScientificLCCInputError(f"{label} must be an integer")
    try:
        f = float(value)
    except (TypeError, ValueError):
        raise ScientificLCCInputError(f"{label} must be an integer") from None
    if not f.is_integer():
        raise ScientificLCCInputError(f"{label} must be an exact integer")
    return int(f)


def _cost_row(raw: Mapping[str, Any], *, context: ProjectContext) -> CostRow:
    project_year = _exact_int(raw.get("project_year", 0), "cost_row.project_year")
    calendar_year = raw.get("calendar_year")
    if calendar_year is None:
        calendar_year = context.calendar_year(project_year)
    return CostRow(
        cost_id=_text(raw.get("cost_id")),
        phase=_text(raw.get("phase")),
        category=_text(raw.get("category")),
        asset=_text(raw.get("asset")),
        activity=_text(raw.get("activity")),
        project_year=project_year,
        calendar_year=_exact_int(calendar_year, "cost_row.calendar_year"),
        quantity=float(raw.get("quantity", 0.0)),
        unit=_text(raw.get("unit")),
        unit_cost_base=float(raw.get("unit_cost_base", 0.0)),
        currency=_text(raw.get("currency") or context.currency),
        price_base_year=_exact_int(
            raw.get("price_base_year", context.price_base_year),
            "cost_row.price_base_year",
        ),
        escalation_rate=float(raw.get("escalation_rate", 0.0)),
        source_file=_text(raw.get("source_file")),
        source_location=_text(raw.get("source_location")),
        geography=_text(raw.get("geography") or context.geography),
        evidence_status=_text(raw.get("evidence_status") or "SOURCE-OPEN"),
        note=_text(raw.get("note")),
    )


def _residual_row(raw: Mapping[str, Any], *, context: ProjectContext) -> ResidualRow:
    project_year = _exact_int(raw.get("project_year", 0), "residual_row.project_year")
    calendar_year = raw.get("calendar_year")
    if calendar_year is None:
        calendar_year = context.calendar_year(project_year)
    return ResidualRow(
        residual_id=_text(raw.get("residual_id")),
        asset=_text(raw.get("asset")),
        activity=_text(raw.get("activity")),
        project_year=project_year,
        calendar_year=_exact_int(calendar_year, "residual_row.calendar_year"),
        amount_base=float(raw.get("amount_base", 0.0)),
        currency=_text(raw.get("currency") or context.currency),
        price_base_year=_exact_int(
            raw.get("price_base_year", context.price_base_year),
            "residual_row.price_base_year",
        ),
        escalation_rate=float(raw.get("escalation_rate", 0.0)),
        source_file=_text(raw.get("source_file")),
        source_location=_text(raw.get("source_location")),
        geography=_text(raw.get("geography") or context.geography),
        evidence_status=_text(raw.get("evidence_status") or "SOURCE-OPEN"),
        note=_text(raw.get("note")),
    )


def _phase_declaration(
    phase: str,
    raw: Mapping[str, Any] | None,
    *,
    context: ProjectContext,
) -> PhaseDeclaration:
    raw = dict(raw or {})
    status = _text(raw.get("status") or PHASE_SOURCE_OPEN).upper()
    if status not in ALLOWED_PHASE_DECLARATIONS:
        raise ScientificLCCInputError(
            f"{phase}: invalid phase declaration status {status!r}"
        )
    return PhaseDeclaration(
        phase=phase,
        status=status,
        source_file=_text(raw.get("source_file")),
        source_location=_text(raw.get("source_location")),
        geography=_text(raw.get("geography") or context.geography),
        evidence_status=_text(raw.get("evidence_status") or "SOURCE-OPEN"),
        justification=_text(raw.get("justification")),
    )


def _declaration_issues(decl: PhaseDeclaration, *, has_rows: bool) -> list[str]:
    issues: list[str] = []
    if has_rows:
        if decl.status not in {PHASE_HAS_ROWS, PHASE_SOURCE_OPEN}:
            issues.append(
                f"{decl.phase}: phase has ledger rows but declaration is {decl.status}"
            )
        return issues

    if decl.status == PHASE_HAS_ROWS:
        issues.append(f"{decl.phase}: declared HAS_ROWS but no cost rows exist")
        return issues

    if decl.status == PHASE_SOURCE_OPEN:
        issues.append(
            f"{decl.phase}: no cost rows and no documented zero/not-applicable declaration"
        )
        return issues

    # Empty phases may be closed only by project/official numeric evidence.
    if decl.evidence_status not in PUBLICATION_ACCEPTABLE_NUMERIC_EVIDENCE:
        issues.append(
            f"{decl.phase}: {decl.status} requires PROJECT-SPECIFIC or "
            "OFFICIAL-PROJECT-DATA evidence"
        )
    if not decl.source_file:
        issues.append(f"{decl.phase}: declaration missing source_file")
    if not decl.source_location:
        issues.append(f"{decl.phase}: declaration missing source_location")
    if not decl.geography:
        issues.append(f"{decl.phase}: declaration missing geography")
    if not decl.justification:
        issues.append(f"{decl.phase}: declaration missing justification")
    return issues


def run_scientific_lcc_from_params(
    params: Mapping[str, Any] | None,
    *,
    project_context: ProjectContext | None = None,
) -> ScientificLCCResult:
    """Build and evaluate one publication-path LCC assessment.

    Expected payload lives under ``params['lcc_scientific_inputs']``::

        {
          "model": {... discount-rate provenance ...},
          "cost_rows": [{...}],
          "residual_rows": [{...}],
          "phase_declarations": {
             "construction": {"status": "HAS_ROWS"},
             "operation": {"status": "DOCUMENTED_ZERO", ...},
             ...
          }
        }

    Missing data never falls back to the legacy scalar LCC.  The core may still
    calculate a diagnostic NPV, but ``publication_ready`` remains false until both
    the numeric-source gate and the phase-completeness gate are closed.
    """
    params = dict(params or {})
    context = project_context or context_from_params(params)
    payload = params.get("lcc_scientific_inputs") or {}
    if not isinstance(payload, Mapping):
        payload = {}

    model_raw = payload.get("model") or {}
    cost_raw = list(payload.get("cost_rows") or [])
    residual_raw = list(payload.get("residual_rows") or [])
    declarations_raw = payload.get("phase_declarations") or {}

    cost_rows = tuple(_cost_row(r, context=context) for r in cost_raw)
    residual_rows = tuple(_residual_row(r, context=context) for r in residual_raw)

    analysis_base_year = _exact_int(
        model_raw.get("analysis_base_year", context.analysis_base_year),
        "analysis_base_year",
    )
    analysis_period_years = _exact_int(
        model_raw.get("analysis_period_years", context.analysis_period_years),
        "analysis_period_years",
    )
    currency = _text(model_raw.get("currency") or context.currency)

    model = LCCModel(
        analysis_base_year=analysis_base_year,
        analysis_period_years=analysis_period_years,
        currency=currency,
        discount_rate=float(model_raw.get("discount_rate", 0.0)),
        discount_basis=_text(model_raw.get("discount_basis") or "real"),
        discount_source_file=_text(model_raw.get("discount_source_file")),
        discount_source_location=_text(model_raw.get("discount_source_location")),
        discount_evidence_status=_text(
            model_raw.get("discount_evidence_status") or "SOURCE-OPEN"
        ),
        discount_source_geography=_text(
            model_raw.get("discount_source_geography") or context.geography
        ),
        analysis_period_source_file=_text(
            model_raw.get("analysis_period_source_file")
        ),
        analysis_period_source_location=_text(
            model_raw.get("analysis_period_source_location")
        ),
        analysis_period_evidence_status=_text(
            model_raw.get("analysis_period_evidence_status") or "SOURCE-OPEN"
        ),
        analysis_period_geography=_text(
            model_raw.get("analysis_period_geography") or context.geography
        ),
        cost_rows=cost_rows,
        residual_rows=residual_rows,
    )

    core_result = calculate_lcc(model)

    declarations: dict[str, PhaseDeclaration] = {}
    phase_issues: list[str] = []
    for phase in sorted(ALLOWED_PHASES):
        decl = _phase_declaration(
            phase,
            declarations_raw.get(phase),
            context=context,
        )
        declarations[phase] = decl
        phase_issues.extend(
            _declaration_issues(
                decl,
                has_rows=bool(core_result.get("phase_has_rows", {}).get(phase)),
            )
        )

    reference_integrity = lcc_reference_integrity_check()
    reference_issues = list(reference_integrity.get("issues") or [])
    numeric_source_ready = bool(core_result.get("publication_source_gate"))
    phase_complete = not phase_issues
    reference_ready = bool(reference_integrity.get("ok"))
    publication_ready = numeric_source_ready and phase_complete and reference_ready

    gate = {
        "publication_ready": bool(publication_ready),
        "numeric_source_ready": bool(numeric_source_ready),
        "phase_complete": bool(phase_complete),
        "reference_integrity_ready": bool(reference_ready),
        "phase_issues": phase_issues,
        "numeric_source_issues": list(core_result.get("open_items") or []),
        "reference_issues": reference_issues,
        "legacy_fallback_allowed": False,
    }

    # The core's old marker is deliberately superseded here by an explicit,
    # evidence-audited phase gate.  We do not mutate the core calculation; we add
    # the stronger publication interpretation at the integration boundary.
    result = dict(core_result)
    result["phase_declarations_implemented"] = True
    result["phase_declarations"] = {
        phase: asdict(decl) for phase, decl in declarations.items()
    }
    result["phase_completeness_gate"] = bool(phase_complete)
    result["publication_ready"] = bool(publication_ready)

    audit = {
        "project_geography": context.geography,
        "project_currency": currency,
        "analysis_base_year": analysis_base_year,
        "analysis_period_years": analysis_period_years,
        "cost_row_count": len(cost_rows),
        "residual_row_count": len(residual_rows),
        "phase_declarations": result["phase_declarations"],
        "core_open_items": list(core_result.get("open_items") or []),
        "phase_issues": phase_issues,
        "reference_integrity": reference_integrity,
        "double_count_rules": [
            "Benefits never reduce LCC NPV.",
            "Residual/recovery value is credited exactly once.",
            "An empty phase is never silently interpreted as zero.",
            "Mixed currencies are rejected by the scientific core.",
        ],
    }

    return ScientificLCCResult(result=result, publication_gate=gate, audit=audit)
