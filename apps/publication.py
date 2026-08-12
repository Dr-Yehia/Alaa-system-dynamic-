"""Canonical publication-only Streamlit entry point.

The scientific UI implementation is preserved byte-for-byte in
``apps/_publication_impl.py``. This wrapper exposes the isolated ``compat/``
aliases needed by the frozen internal import graph, while the repository root
remains free of duplicate-looking Python modules.
"""
from __future__ import annotations

from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "compat", ROOT):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)

runpy.run_path(str(Path(__file__).with_name("_publication_impl.py")), run_name="__main__")
