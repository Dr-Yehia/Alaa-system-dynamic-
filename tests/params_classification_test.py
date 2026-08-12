"""Every real parameter is classified — no key crosses a boundary by default.

The previous "unknown key is neutral" policy meant an unclassified field was handed to
ALL domains. That is how `carbon_intensity` reached the LCC slice while the real
`benefit_*` fields were visible to everyone. This suite runs against the ACTUAL
current_params the application builds, not a hand-written sample.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

ok = True


def check(name, cond):
    global ok
    print(("PASS" if cond else "FAIL"), name)
    ok = ok and bool(cond)


from _headless_app import build_ns  # noqa: E402
from assessment_orchestrator import (split_params, unclassified_params,  # noqa: E402
                                     LCA_PARAM_KEYS, LCC_PARAM_KEYS, BENEFITS_PARAM_KEYS,
                                     MULTI_DOMAIN_PARAM_KEYS, CONTEXT_PARAM_KEYS)
import benefits_core  # noqa: E402

ns = build_ns(publication_mode=False)
params = dict(ns["params"])
check("the application builds a non-trivial parameter set", len(params) > 40)

slices = split_params(params)

# ── Every benefit_* field the Benefits engine reads must be classified Benefits ──
ben_src = open(os.path.join(ROOT, "benefits_core.py"), encoding="utf-8").read()
import re  # noqa: E402
read_by_benefits = sorted(set(re.findall(r"params(?:\.get\(|\[)'([a-z0-9_]+)'", ben_src))
                          | set(re.findall(r'params(?:\.get\(|\[)"([a-z0-9_]+)"', ben_src)))
check("benefits_core reads at least one parameter", bool(read_by_benefits))
for key in read_by_benefits:
    if key not in params:
        continue
    check(f"benefits input {key!r} reaches the Benefits slice",
          key in slices["benefits_inputs"])

# ── An emission factor must never reach the economic slice ──────────────────
for ef in ("carbon_intensity", "energy_per_pax", "steel_recycle", "aluminum_recycle",
           "concrete", "steel", "aluminum", "renewable_share"):
    if ef in params:
        check(f"{ef!r} does NOT leak into the LCC slice", ef not in slices["lcc_inputs"])

# ── A price/rate must never reach the environmental slice ───────────────────
for money in ("discount_rate", "construction_cost", "maintenance_cost",
              "residual_value", "b6_energy_tariff", "eol_cost_m"):
    if money in params:
        check(f"{money!r} does NOT leak into the LCA slice", money not in slices["lca_inputs"])

# ── A benefit input must never reach LCA or LCC unless declared multi-domain ─
for b in sorted(k for k in params if k.startswith("benefit_")):
    check(f"{b!r} does not leak into the LCA slice", b not in slices["lca_inputs"])
    check(f"{b!r} does not leak into the LCC slice", b not in slices["lcc_inputs"])

# ── Classification completeness against the REAL parameter set ──────────────
unclassified = unclassified_params(params)
if unclassified:
    print(f"   {len(unclassified)} unclassified key(s):")
    for k in unclassified:
        print("     -", k)
check(f"every real parameter is classified ({len(unclassified)} unclassified)",
      not unclassified)

# ── Declared multi-domain keys are intentional, not accidental ──────────────
for key, domains in MULTI_DOMAIN_PARAM_KEYS.items():
    if key not in params:
        continue
    for d, slice_name in (("lca", "lca_inputs"), ("lcc", "lcc_inputs"),
                          ("benefits", "benefits_inputs")):
        present = key in slices[slice_name]
        check(f"multi-domain {key!r} reaches {d} = {d in domains}",
              present == (d in domains))

# ── The classification sets do not silently overlap ─────────────────────────
overlap = (LCA_PARAM_KEYS & LCC_PARAM_KEYS) - set(MULTI_DOMAIN_PARAM_KEYS)
check(f"LCA and LCC sets do not overlap outside MULTI_DOMAIN ({sorted(overlap)})",
      not overlap)

print("\nPARAMS CLASSIFICATION VERIFIED" if ok else "\nPARAMS CLASSIFICATION VIOLATED")
sys.exit(0 if ok else 1)
