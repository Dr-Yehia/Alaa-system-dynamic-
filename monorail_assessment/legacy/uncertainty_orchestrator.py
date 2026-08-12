"""Uncertainty orchestration — one sample, three separated domains.

ARCHITECTURAL ROLE
------------------
Monte Carlo used to call one mixed engine that computed carbon and money together.
That re-coupled the domains at exactly the point where independence matters most: if a
single sampled emission factor could shift a cash flow, the uncertainty result would
attribute economic variance to an environmental cause.

So sampling stays where the sampler lives, and EVALUATION happens here, crossing the
same domain boundary as an ordinary run:

    sample -> LCA engine        -> carbon + NEUTRAL activity
           -> LCC engine        -> money, priced from that activity only
           -> Benefits engine   -> co-benefits, valued independently

This module holds no distribution, no equation and no factor. It is a call sequence.
The per-domain evaluators are exposed separately so a future LCA-only or LCC-only
uncertainty run needs no new plumbing.
"""

from __future__ import annotations

from typing import Any

from monorail_assessment.legacy.assessment_orchestrator import run_assessment, calculate_legacy_dashboard_results


def evaluate_sample(params: dict) -> dict:
    """Evaluate ONE Monte-Carlo sample through the separated engines.

    Returns the combined dashboard dictionary the existing sampler consumes, so the
    uncertainty machinery is unchanged numerically — but every number in it now comes
    from exactly one domain.
    """
    return calculate_legacy_dashboard_results(params)


def evaluate_sample_by_domain(params: dict) -> Any:
    """Same evaluation, returned as three separate domain results.

    Preferred for new uncertainty work: it keeps environmental and economic variance
    attributable to their own inputs instead of flattening them into one dictionary.
    """
    return run_assessment(params)


def evaluate_lca_only(params: dict) -> dict:
    """Environmental result for one sample, with no economic evaluation performed."""
    from monorail_assessment.legacy.lca_engine import calculate_legacy_lca
    lca_result, _shared = calculate_legacy_lca(params)
    return lca_result


def evaluate_lcc_only(params: dict, shared) -> dict:
    """Economic result for one sample, priced from NEUTRAL activity only."""
    from monorail_assessment.legacy.lcc_engine import calculate_legacy_lcc
    return calculate_legacy_lcc(params, shared)
