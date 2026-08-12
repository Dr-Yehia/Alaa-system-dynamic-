# Compatibility aliases

This directory contains symbolic aliases for the frozen historical regression suite and legacy developer dashboard.

Canonical production code lives under `monorail_assessment/` and `apps/`.
New scientific code must never be added here.

CI adds this directory to `PYTHONPATH` only for backward-compatible historical imports.
