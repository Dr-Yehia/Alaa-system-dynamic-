"""Fail-closed master orchestrator for publication-path assessment.

The historical dashboard orchestrator is intentionally retained for Developer mode.
This module is the canonical publication assembly point and imports only scientific
engines plus neutral project context.  It contains no scientific equation.

A domain may fail because evidence is open.  That is returned as an explicit blocked
state; the orchestrator never substitutes a legacy number.  Consequently a
publication export can only be created from scientific domain results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from project_context import ProjectContext, context_from_params


@dataclass(frozen=True)
class DomainRun:
    name: str
    result: Any = None
    available: bool = False
    publication_ready: bool = False
    error: str = ""
    gate: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ScientificPublicationBundle:
    context: ProjectContext
    lca: DomainRun
    lcc: DomainRun
    benefits: DomainRun
    uncertainty: DomainRun | None = None
    publication_gate: dict = field(default_factory=dict)


def _run_lca(params: dict) -> DomainRun:
    try:
        from lca_scientific_integration import run_scientific_lca_from_app_params

        result = run_scientific_lca_from_app_params(params)
        gate = dict(result.get("closure_gate") or {})
        readiness = dict(result.get("publication_readiness") or {})
        # Deterministic publication readiness deliberately excludes the still-separate
        # uncertainty condition.  The system-level gate below adds uncertainty once a
        # scientific uncertainty result is supplied.
        deterministic_ready = bool(
            gate.get("standards_reporting_complete")
            and gate.get("lca_application_end_to_end_complete")
            and readiness.get("project_specific_data_complete")
        )
        return DomainRun(
            name="LCA",
            result=result,
            available=True,
            publication_ready=deterministic_ready,
            gate={**gate, "deterministic_publication_ready": deterministic_ready},
        )
    except Exception as exc:
        return DomainRun(name="LCA", error=str(exc), gate={"legacy_fallback_allowed": False})


def _run_lcc(params: dict, context: ProjectContext) -> DomainRun:
    try:
        from lcc_scientific_integration import run_scientific_lcc_from_params
        from lcc_scientific_reporting import export_parity_ok

        result = run_scientific_lcc_from_params(params, project_context=context)
        gate = dict(result.publication_gate)
        parity = bool(export_parity_ok(result)) if gate.get("publication_ready") else False
        ready = bool(gate.get("publication_ready") and parity)
        gate["export_parity_ready"] = parity
        gate["deterministic_publication_ready"] = ready
        return DomainRun(
            name="LCC",
            result=result,
            available=True,
            publication_ready=ready,
            gate=gate,
        )
    except Exception as exc:
        return DomainRun(name="LCC", error=str(exc), gate={"legacy_fallback_allowed": False})


def _run_benefits(params: dict, context: ProjectContext, shared_activity=None) -> DomainRun:
    try:
        from benefits_scientific_integration import run_scientific_benefits_from_params
        from benefits_scientific_reporting import export_parity_ok

        result = run_scientific_benefits_from_params(
            params=params,
            shared_activity=shared_activity,
            project_context=context,
        )
        gate = dict(result.publication_gate)
        parity = bool(export_parity_ok(result)) if gate.get("publication_ready") else False
        ready = bool(gate.get("publication_ready") and parity)
        gate["export_parity_ready"] = parity
        gate["deterministic_publication_ready"] = ready
        return DomainRun(
            name="K-Benefits",
            result=result,
            available=True,
            publication_ready=ready,
            gate=gate,
        )
    except Exception as exc:
        return DomainRun(
            name="K-Benefits",
            error=str(exc),
            gate={"legacy_fallback_allowed": False},
        )


def run_scientific_publication_bundle(
    params: Mapping[str, Any] | None,
    *,
    shared_activity=None,
    uncertainty_result: Any = None,
) -> ScientificPublicationBundle:
    """Run all three scientific domains and assemble their gates without fallback."""
    params = dict(params or {})
    # The LCA integration uses this flag when proving application/export parity.
    # A scientific publication bundle is, by definition, a publication-mode run.
    params["publication_mode"] = True
    context = context_from_params(params)

    lca = _run_lca(params)
    lcc = _run_lcc(params, context)
    benefits = _run_benefits(params, context, shared_activity=shared_activity)

    uncertainty_domain: DomainRun | None = None
    uncertainty_ready = False
    if uncertainty_result is not None:
        if isinstance(uncertainty_result, DomainRun):
            uncertainty_domain = uncertainty_result
        else:
            gate = dict(getattr(uncertainty_result, "publication_gate", {}) or {})
            uncertainty_ready = bool(gate.get("publication_ready"))
            uncertainty_domain = DomainRun(
                name="Uncertainty",
                result=uncertainty_result,
                available=True,
                publication_ready=uncertainty_ready,
                gate=gate,
            )
        uncertainty_ready = bool(uncertainty_domain.publication_ready)

    deterministic_ready = bool(
        lca.publication_ready and lcc.publication_ready and benefits.publication_ready
    )
    full_q1_ready = bool(deterministic_ready and uncertainty_ready)

    open_domains = [
        d.name for d in (lca, lcc, benefits) if not d.publication_ready
    ]
    if uncertainty_result is None:
        open_domains.append("Uncertainty")
    elif not uncertainty_ready:
        open_domains.append("Uncertainty")

    gate = {
        "deterministic_publication_ready": deterministic_ready,
        "uncertainty_ready": uncertainty_ready,
        "full_q1_ready": full_q1_ready,
        "lca_ready": lca.publication_ready,
        "lcc_ready": lcc.publication_ready,
        "benefits_ready": benefits.publication_ready,
        "legacy_fallback_allowed": False,
        "open_domains": open_domains,
    }

    return ScientificPublicationBundle(
        context=context,
        lca=lca,
        lcc=lcc,
        benefits=benefits,
        uncertainty=uncertainty_domain,
        publication_gate=gate,
    )
