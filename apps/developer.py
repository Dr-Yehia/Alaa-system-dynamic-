"""Developer / historical Streamlit entry point.

    streamlit run apps/developer.py

The dashboard implementation lives in ``apps/_developer_impl.py``. This wrapper
only puts the repository root on ``sys.path`` so ``monorail_assessment`` is
importable when Streamlit is launched from anywhere, then executes it.

It deliberately does NOT add ``compat/``. The implementation imports every
domain by its package path, so the compatibility aliases are not needed to run
the application — and silently adding them would hide that fact.
"""
from __future__ import annotations

from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

runpy.run_path(str(Path(__file__).with_name("_developer_impl.py")), run_name="__main__")
