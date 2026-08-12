"""Monorail scientific assessment package.

Canonical scientific source lives under this package:

    lca/         environmental domain
    lcc/         economic domain
    benefits/    societal co-benefit domain
    publication/ cross-domain publication orchestration and uncertainty
    common/      neutral layers shared by all three domains
    legacy/      historical engines, kept for Developer parity only

The three scientific domains do not import one another. Every module here
imports by its package path, so the package is self-contained: importing it
requires nothing on ``sys.path`` beyond the repository root.

``compat/`` holds historical top-level aliases for anyone with older scripts.
It is genuinely optional — nothing in this package or in ``apps/`` needs it, and
it is never added to ``sys.path`` implicitly. A package that quietly rewrites
the import path hides exactly the coupling this layout exists to remove.
"""

__all__ = ["lca", "lcc", "benefits", "publication", "common", "legacy"]
