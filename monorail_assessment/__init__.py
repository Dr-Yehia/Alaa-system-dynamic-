"""Monorail scientific assessment package.

Canonical scientific source lives under this package. Historical top-level module
names are isolated in ``compat/`` rather than cluttering the repository root.
Importing the package exposes that compatibility directory only to the Python import
system; it does not make compatibility aliases canonical source files.
"""
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[1]
_COMPAT = _ROOT / "compat"
if _COMPAT.is_dir() and str(_COMPAT) not in sys.path:
    sys.path.insert(0, str(_COMPAT))

__all__ = ["lca", "lcc", "benefits", "publication", "common", "legacy"]
