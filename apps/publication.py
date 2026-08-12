"""Canonical publication-only Streamlit entry point.

    streamlit run apps/publication.py

The scientific UI implementation lives in ``apps/_publication_impl.py``. This
wrapper only puts the repository root on ``sys.path`` so ``monorail_assessment``
is importable when Streamlit is launched from anywhere, then executes it.

It deliberately does NOT add ``compat/``. The publication path imports the
scientific package directly and must never reach a legacy engine, so the
compatibility aliases have no business being on the path here.
"""
from __future__ import annotations

from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

runpy.run_path(str(Path(__file__).with_name("_publication_impl.py")), run_name="__main__")
