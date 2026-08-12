"""Sourced Monte Carlo propagation for the scientific publication path.

This module contains no empirical default distribution, coefficient of variation,
bound or correlation assumption.  Every sampled parameter is supplied through an
``UncertaintySpec`` carrying its own provenance.  Missing/weak provenance does not
prevent exploratory sampling, but it keeps ``publication_ready`` false.

The evaluator re-runs the scientific LCA, LCC and K-Benefits integrations.  It never
calls a legacy engine.  Distribution sampling is delegated to NumPy's documented RNG
implementations; no custom probability-density equation is reimplemented here.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from monorail_assessment.common.project_context import context_from_params


PUBLICATION_NUMERIC_EVIDENCE = {"PROJECT-SPECIFIC", "OFFICIAL-PROJECT-DATA"}
SUPPORTED_DISTRIBUTIONS = {"normal", "lognormal", "triangular", "uniform"}


@dataclass(frozen=True)
class UncertaintySpec:
    """One uncertain numeric input and the evidence for its distribution parameters."""

    parameter_path: str
    distribution: str
    parameters: Mapping[str, float]
    unit: str
    source_file: str
    source_location: str
    geography: str
    evidence_status: str
    note: str = ""


@dataclass(frozen=True)
class ScientificUncertaintyResult:
    samples: pd.DataFrame
    outputs: pd.DataFrame
    summary: pd.DataFrame
    audit: pd.DataFrame
    publication_gate: dict = field(default_factory=dict)


def _spec_issues(spec: UncertaintySpec) -> list[str]:
    issues: list[str] = []
    if not spec.parameter_path.strip():
        issues.append("uncertainty spec missing parameter_path")
    if spec.distribution not in SUPPORTED_DISTRIBUTIONS:
        issues.append(
            f"{spec.parameter_path}: unsupported distribution {spec.distribution!r}"
        )
    if not spec.unit.strip():
        issues.append(f"{spec.parameter_path}: missing unit")
    if not spec.source_file.strip():
        issues.append(f"{spec.parameter_path}: missing source_file")
    if not spec.source_location.strip():
        issues.append(f"{spec.parameter_path}: missing source_location")
    if not spec.geography.strip():
        issues.append(f"{spec.parameter_path}: missing geography")
    if spec.evidence_status not in PUBLICATION_NUMERIC_EVIDENCE:
        issues.append(
            f"{spec.parameter_path}: distribution parameters are {spec.evidence_status or 'SOURCE-OPEN'}; "
            "publication uncertainty requires PROJECT-SPECIFIC or OFFICIAL-PROJECT-DATA evidence"
        )

    p = dict(spec.parameters or {})
    required = {
        "normal": {"mean", "sd"},
        "lognormal": {"meanlog", "sdlog"},
        "triangular": {"left", "mode", "right"},
        "uniform": {"low", "high"},
    }.get(spec.distribution, set())
    missing = sorted(k for k in required if k not in p)
    if missing:
        issues.append(f"{spec.parameter_path}: missing distribution parameters {missing}")
    try:
        vals = [float(p[k]) for k in required if k in p]
        if not all(np.isfinite(vals)):
            issues.append(f"{spec.parameter_path}: non-finite distribution parameter")
    except (TypeError, ValueError):
        issues.append(f"{spec.parameter_path}: distribution parameters must be numeric")
    if spec.distribution in {"normal", "lognormal"} and "sd" in p:
        if float(p["sd"]) < 0:
            issues.append(f"{spec.parameter_path}: sd must be >= 0")
    if spec.distribution == "lognormal" and "sdlog" in p:
        if float(p["sdlog"]) < 0:
            issues.append(f"{spec.parameter_path}: sdlog must be >= 0")
    if spec.distribution == "triangular" and required <= set(p):
        left, mode, right = float(p["left"]), float(p["mode"]), float(p["right"])
        if not (left <= mode <= right and left < right):
            issues.append(f"{spec.parameter_path}: triangular requires left <= mode <= right and left < right")
    if spec.distribution == "uniform" and required <= set(p):
        if not float(p["low"]) < float(p["high"]):
            issues.append(f"{spec.parameter_path}: uniform requires low < high")
    return issues


def _draw(rng: np.random.Generator, spec: UncertaintySpec, n: int) -> np.ndarray:
    p = {k: float(v) for k, v in dict(spec.parameters).items()}
    if spec.distribution == "normal":
        return rng.normal(loc=p["mean"], scale=p["sd"], size=n)
    if spec.distribution == "lognormal":
        return rng.lognormal(mean=p["meanlog"], sigma=p["sdlog"], size=n)
    if spec.distribution == "triangular":
        return rng.triangular(left=p["left"], mode=p["mode"], right=p["right"], size=n)
    if spec.distribution == "uniform":
        return rng.uniform(low=p["low"], high=p["high"], size=n)
    raise ValueError(f"unsupported distribution {spec.distribution!r}")


def _path_child(container: Any, token: str, full_path: str) -> Any:
    """Resolve one dotted-path token through a mapping or a list/tuple index."""
    if isinstance(container, dict):
        if token not in container:
            raise KeyError(f"{full_path}: key {token!r} does not exist")
        return container[token]
    if isinstance(container, (list, tuple)):
        try:
            index = int(token)
        except ValueError:
            raise KeyError(
                f"{full_path}: {token!r} must be an integer list index"
            ) from None
        if index < 0 or index >= len(container):
            raise KeyError(f"{full_path}: list index {index} is out of range")
        return container[index]
    raise KeyError(
        f"{full_path}: cannot traverse token {token!r} through "
        f"{type(container).__name__}"
    )


def _set_path(mapping: dict, path: str, value: float) -> None:
    """Set a dotted path through mappings and indexed ledger lists.

    Examples::

        lcc_scientific_inputs.model.discount_rate
        lcc_scientific_inputs.cost_rows.0.unit_cost_base
        benefits_scientific_inputs.transport.modal_shift_fraction.value

    List indices are explicit decimal path tokens.  Existing keys/indices only are
    accepted: uncertainty propagation never creates a new scientific input silently.
    """
    parts = [p for p in path.split(".") if p]
    if not parts:
        raise KeyError("empty parameter path")

    cur: Any = mapping
    for token in parts[:-1]:
        cur = _path_child(cur, token, path)

    last = parts[-1]
    if isinstance(cur, dict):
        if last not in cur:
            raise KeyError(f"{path}: final key {last!r} does not exist")
        cur[last] = float(value)
        return
    if isinstance(cur, list):
        try:
            index = int(last)
        except ValueError:
            raise KeyError(f"{path}: final token {last!r} must be an integer list index") from None
        if index < 0 or index >= len(cur):
            raise KeyError(f"{path}: final list index {index} is out of range")
        # Direct scalar list elements are supported, although the common LCC use is a
        # dictionary field inside a ledger row (cost_rows.0.unit_cost_base).
        cur[index] = float(value)
        return
    raise KeyError(f"{path}: final container {type(cur).__name__} is not assignable")


def evaluate_scientific_metrics(params: Mapping[str, Any]) -> dict[str, float]:
    """Run scientific domains only and return scalar outputs suitable for propagation."""
    p = dict(params)
    p["publication_mode"] = True
    context = context_from_params(p)
    metrics: dict[str, float] = {}

    from monorail_assessment.lca.integration import run_scientific_lca_from_app_params
    lca = run_scientific_lca_from_app_params(p)
    metrics["lca_gross_A_C_tCO2e"] = float(lca["gross_A_C_tCO2e"])
    metrics["lca_GWP_kgCO2e_per_pkm"] = float(lca["GWP_kgCO2e_per_pkm"])

    from monorail_assessment.lcc.integration import run_scientific_lcc_from_params
    lcc = run_scientific_lcc_from_params(p, project_context=context)
    metrics["lcc_npv"] = float(lcc.result["lcc_npv"])

    from monorail_assessment.benefits.integration import run_scientific_benefits_from_params
    ben = run_scientific_benefits_from_params(
        params=p, shared_activity=None, project_context=context
    )
    for row in ben.rows:
        value = row.get("value")
        if isinstance(value, (int, float)) and np.isfinite(float(value)):
            metrics[f"benefits::{row['kpi_id']}"] = float(value)
    return metrics


def _deterministic_gate_ready(params: Mapping[str, Any]) -> bool:
    from monorail_assessment.publication.orchestrator import run_scientific_publication_bundle
    bundle = run_scientific_publication_bundle(params)
    return bool(bundle.publication_gate.get("deterministic_publication_ready"))


def run_scientific_uncertainty(
    base_params: Mapping[str, Any],
    specs: Sequence[UncertaintySpec],
    *,
    n: int = 5000,
    seed: int = 42,
    protocol_source_file: str = "",
    protocol_source_location: str = "",
    protocol_evidence_status: str = "SOURCE-OPEN",
) -> ScientificUncertaintyResult:
    """Propagate sourced uncertain inputs through all scientific domains.

    ``n`` is a study-protocol choice, not a universal scientific constant.  Therefore
    publication readiness requires the protocol itself to be documented; this module
    does not invent a minimum sample size on the user's behalf.
    """
    if int(n) != n or n <= 0:
        raise ValueError("n must be a positive integer")
    n = int(n)
    specs = list(specs)
    if not specs:
        raise ValueError("at least one UncertaintySpec is required")

    spec_issues = {s.parameter_path: _spec_issues(s) for s in specs}
    rng = np.random.default_rng(int(seed))
    draws = {s.parameter_path: _draw(rng, s, n) for s in specs}
    samples = pd.DataFrame(draws)

    output_rows: list[dict[str, Any]] = []
    for i in range(n):
        p = copy.deepcopy(dict(base_params))
        failed = False
        error = ""
        try:
            for spec in specs:
                _set_path(p, spec.parameter_path, samples.iloc[i][spec.parameter_path])
            metrics = evaluate_scientific_metrics(p)
        except Exception as exc:
            metrics = {}
            failed = True
            error = str(exc)
        output_rows.append({"sample": i, "failed": failed, "error": error, **metrics})
    outputs = pd.DataFrame(output_rows)

    valid = outputs[~outputs["failed"]].copy()
    metric_cols = [c for c in valid.columns if c not in {"sample", "failed", "error"}]
    summary_rows = []
    for col in metric_cols:
        x = pd.to_numeric(valid[col], errors="coerce").dropna().to_numpy(dtype=float)
        if not len(x):
            continue
        # SOFTWARE-STATISTICAL-IDENTITY: descriptive sample summaries only; no
        # empirical project coefficient or scientific default is introduced here.
        mean = float(np.mean(x))
        sd = float(np.std(x, ddof=1)) if len(x) > 1 else 0.0
        cv = float(sd / abs(mean)) if mean != 0 else float("nan")
        summary_rows.append(
            {
                "metric": col,
                "n_valid": len(x),
                "mean": mean,
                "median": float(np.median(x)),
                "std": sd,
                "CV": cv,
                "P2.5": float(np.percentile(x, 2.5)),
                "P50": float(np.percentile(x, 50.0)),
                "P97.5": float(np.percentile(x, 97.5)),
            }
        )
    summary = pd.DataFrame(summary_rows)

    audit_rows = []
    for s in specs:
        audit_rows.append(
            {
                "parameter_path": s.parameter_path,
                "distribution": s.distribution,
                "parameters": dict(s.parameters),
                "unit": s.unit,
                "source_file": s.source_file,
                "source_location": s.source_location,
                "geography": s.geography,
                "evidence_status": s.evidence_status,
                "issues": "; ".join(spec_issues[s.parameter_path]),
                "note": s.note,
            }
        )
    audit = pd.DataFrame(audit_rows)

    protocol_ready = bool(
        protocol_source_file.strip()
        and protocol_source_location.strip()
        and protocol_evidence_status in PUBLICATION_NUMERIC_EVIDENCE
    )
    distributions_ready = not any(spec_issues.values())
    deterministic_ready = _deterministic_gate_ready(base_params)
    all_samples_valid = bool(len(outputs) == n and not outputs["failed"].any())
    publication_ready = bool(
        deterministic_ready and distributions_ready and protocol_ready and all_samples_valid
    )

    gate = {
        "publication_ready": publication_ready,
        "deterministic_publication_ready": deterministic_ready,
        "distribution_evidence_ready": distributions_ready,
        "protocol_ready": protocol_ready,
        "all_samples_valid": all_samples_valid,
        "n_requested": n,
        "n_valid": int((~outputs["failed"]).sum()),
        "seed": int(seed),
        "protocol_source_file": protocol_source_file,
        "protocol_source_location": protocol_source_location,
        "protocol_evidence_status": protocol_evidence_status,
        "open_items": [issue for issues in spec_issues.values() for issue in issues]
        + ([] if protocol_ready else ["uncertainty protocol/sample-size basis lacks publication-grade provenance"])
        + ([] if deterministic_ready else ["deterministic scientific domains are not publication-ready"])
        + ([] if all_samples_valid else ["one or more scientific Monte Carlo evaluations failed"]),
        "legacy_fallback_allowed": False,
    }

    return ScientificUncertaintyResult(
        samples=samples,
        outputs=outputs,
        summary=summary,
        audit=audit,
        publication_gate=gate,
    )
