"""ARCHITECTURE BASELINE PIN — the reference point for the LCA / LCC / Benefits separation.

WHY THIS EXISTS
---------------
The three domains are about to be pulled apart into separate modules. A refactor of that
size cannot be checked by eye, and the existing suites only assert that the app still RUNS
after an `exec` — they do not assert that every number is unchanged.

So this file freezes a canonical numeric fingerprint of the CURRENT engine BEFORE anything
moves. Once code starts moving, "before" no longer exists; the fingerprint is the only
remaining proof that the separation preserved behaviour.

CONTRACT
--------
Run with `--write` to regenerate the fixture. Run with no arguments to VERIFY that the
current engine still reproduces it exactly.

    python tests/architecture_baseline_pin.py --write     # only at the pinned baseline
    python tests/architecture_baseline_pin.py             # every commit thereafter

The fixture must NOT be regenerated to make a failing separation pass. A diff here means
the move changed a result, which is exactly what the pin is for. Regenerate ONLY when a
scientific change is intended, reviewed and described in the commit message.

SCOPE
-----
Covers the legacy dashboard engine (`calculate_legacy_dashboard_results`), the frozen scientific LCA
engine, and the deterministic scientific LCC core — the three things the separation touches.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

FIXTURE = os.path.join(HERE, "fixtures", "pre_separation_3708f9e.json")

# Absolute tolerance for float comparison. A pure code MOVE must reproduce bit-identical
# arithmetic, so this is deliberately tight: it catches a reordered sum, not just a typo.
TOL = 1e-9


def _flatten(obj, prefix=""):
    """Flatten a result object to {dotted_path: number}. Only numbers are pinned."""
    out = {}
    if isinstance(obj, bool):
        out[prefix] = int(obj)
    elif isinstance(obj, (int, float)):
        out[prefix] = float(obj) if math.isfinite(float(obj)) else None
    elif isinstance(obj, dict):
        for k, v in obj.items():
            out.update(_flatten(v, f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            out.update(_flatten(v, f"{prefix}[{i}]"))
    return out


def _legacy_fingerprint():
    from _headless_app import build_ns
    fp = {}
    for mode in (False, True):
        ns = build_ns(publication_mode=mode)
        result = ns["calculate_legacy_dashboard_results"](dict(ns["params"]))
        tag = "publication" if mode else "developer"
        fp.update({f"legacy.{tag}.{k}": v for k, v in _flatten(result).items()})
    return fp


def _scientific_lca_fingerprint():
    """The frozen golden LCA fixture, re-run through the scientific engine."""
    from lca_scientific_integration import run_scientific_lca_from_app_params
    src = open(os.path.join(HERE, "golden_full_lca_test.py"), encoding="utf-8").read()
    ns = {"__file__": os.path.join(HERE, "golden_full_lca_test.py")}
    exec(src.split("r = run_scientific_lca_from_app_params")[0], ns)
    params = dict(ns["G"])
    params["publication_mode"] = True
    result = run_scientific_lca_from_app_params(params)
    keep = ("gross_A_C_tCO2e", "GWP_kgCO2e_per_pkm", "lifetime_pkm",
            "module_D1_signed_tCO2e_separate", "reported_stage_tco2e",
            "diagnostic_stage_tco2e", "closure_gate")
    return {f"lca.{k}": v
            for k, v in _flatten({k: result[k] for k in keep if k in result}).items()}


def _scientific_lcc_fingerprint():
    """The deterministic LCC golden ledger (identity 100+20+30+10-5 = 155)."""
    from lcc_scientific_core import CostRow, ResidualRow, LCCModel, calculate_lcc

    def cost(cid, phase, year, amount):
        return CostRow(cid, phase, "test_category", "test_asset", "test_activity", year,
                       2026 + year, 1.0, "lump_sum", amount, "EGP", 2026, 0.0,
                       "golden_fixture.xlsx", f"Costs!{cid}", "Egypt", "PROJECT-SPECIFIC")

    model = LCCModel(
        analysis_base_year=2026, analysis_period_years=20, currency="EGP",
        discount_rate=0.0, discount_basis="real",
        discount_source_file="economic_assumptions.xlsx",
        discount_source_location="Rates!B2", discount_evidence_status="PROJECT-SPECIFIC",
        cost_rows=(cost("C", "construction", 0, 100.0), cost("O", "operation", 1, 20.0),
                   cost("M", "maintenance_renewal", 5, 30.0),
                   cost("E", "end_of_life", 20, 10.0)),
        residual_rows=(ResidualRow("R", "test_asset", "salvage", 20, 2046, 5.0, "EGP", 2026,
                                   0.0, "golden_fixture.xlsx", "Residual!R", "Egypt",
                                   "PROJECT-SPECIFIC"),),
        discount_source_geography="Egypt",
        analysis_period_source_file="design_brief.pdf",
        analysis_period_source_location="clause 3.2 design life",
        analysis_period_evidence_status="PROJECT-SPECIFIC",
        analysis_period_geography="Egypt")
    result = calculate_lcc(model)
    keep = ("lcc_npv", "pv_construction", "pv_operation", "pv_maintenance_renewal",
            "pv_end_of_life", "pv_residual", "publication_source_gate")
    return {f"lcc.{k}": v for k, v in _flatten({k: result[k] for k in keep}).items()}


def build_fingerprint():
    fp = {}
    fp.update(_legacy_fingerprint())
    fp.update(_scientific_lca_fingerprint())
    fp.update(_scientific_lcc_fingerprint())
    return fp


def main():
    write = "--write" in sys.argv
    current = build_fingerprint()

    if write:
        os.makedirs(os.path.dirname(FIXTURE), exist_ok=True)
        with open(FIXTURE, "w", encoding="utf-8") as fh:
            json.dump(current, fh, indent=1, sort_keys=True)
        print(f"WROTE baseline fingerprint: {len(current)} pinned values")
        print(f"  -> {os.path.relpath(FIXTURE, ROOT)}")
        return 0

    if not os.path.exists(FIXTURE):
        print("FAIL baseline fixture missing; run with --write at the pinned baseline")
        return 1

    with open(FIXTURE, encoding="utf-8") as fh:
        baseline = json.load(fh)

    missing = sorted(set(baseline) - set(current))
    added = sorted(set(current) - set(baseline))
    drifted = []
    for key in sorted(set(baseline) & set(current)):
        a, b = baseline[key], current[key]
        if a is None or b is None:
            if a is not b:
                drifted.append((key, a, b))
        elif abs(a - b) > TOL:
            drifted.append((key, a, b))

    print(f"pinned values: {len(baseline)}   compared: {len(set(baseline) & set(current))}")
    ok = True
    if missing:
        ok = False
        print(f"\nFAIL {len(missing)} pinned value(s) DISAPPEARED — a move dropped an output:")
        for k in missing[:15]:
            print("   -", k)
    if drifted:
        ok = False
        print(f"\nFAIL {len(drifted)} pinned value(s) CHANGED — a move altered arithmetic:")
        for k, a, b in drifted[:15]:
            print(f"   - {k}\n       baseline={a!r}  now={b!r}")
    if added:
        # New outputs are allowed: separation may expose more, it must not change what exists.
        print(f"\nNOTE {len(added)} new output(s) appeared (allowed):")
        for k in added[:10]:
            print("   +", k)

    print("\nARCHITECTURE BASELINE INTACT" if ok else "\nARCHITECTURE BASELINE VIOLATED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
