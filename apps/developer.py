"""Developer/historical Streamlit entry point.

The legacy dashboard implementation is preserved byte-for-byte in
``apps/_developer_impl.py``. This wrapper only exposes the isolated ``compat/``
module aliases before executing it, keeping the repository root clean.
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

runpy.run_path(str(Path(__file__).with_name("_developer_impl.py")), run_name="__main__")
