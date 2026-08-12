"""Mechanical proof that the three domains are actually separated.

A separation that is only described in docstrings decays on the next edit. This suite
enforces it from two directions:

  STRUCTURAL — no module imports across a domain boundary;
  BEHAVIOURAL — changing one domain's input cannot move another domain's result.

The behavioural half matters most. Import hygiene can be satisfied while the domains
remain coupled through a shared mutable dictionary, so the real question is the one the
project asked for: "change the discount rate, does carbon move?"
"""
import ast
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


def imports_of(path):
    """Top-level module names imported by a file."""
    src = open(os.path.join(ROOT, path), encoding="utf-8").read()
    names = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


LCA_MODULES = ["lca_scientific_core.py", "lca_scientific_integration.py",
               "lca_scientific_reporting.py", "legacy_lca_engine.py"]
LCC_MODULES = ["lcc_scientific_core.py", "legacy_lcc_engine.py"]
BENEFIT_MODULES = ["benefits_core.py"]
NEUTRAL_MODULES = ["project_context.py", "shared_activity.py", "system_dynamics_core.py"]

LCA_PREFIXES = ("lca_", "legacy_lca")
LCC_PREFIXES = ("lcc_", "legacy_lcc")
BENEFIT_PREFIXES = ("benefits",)


def _has(names, prefixes):
    return sorted(n for n in names if n.startswith(prefixes))


# ── 1. STRUCTURAL: no cross-domain imports ───────────────────────────────────
for m in LCA_MODULES:
    imps = imports_of(m)
    check(f"{m}: does not import LCC", not _has(imps, LCC_PREFIXES))
    check(f"{m}: does not import Benefits", not _has(imps, BENEFIT_PREFIXES))

for m in LCC_MODULES:
    imps = imports_of(m)
    check(f"{m}: does not import LCA", not _has(imps, LCA_PREFIXES))
    check(f"{m}: does not import Benefits", not _has(imps, BENEFIT_PREFIXES))

for m in BENEFIT_MODULES:
    imps = imports_of(m)
    check(f"{m}: does not import LCA", not _has(imps, LCA_PREFIXES))
    check(f"{m}: does not import LCC", not _has(imps, LCC_PREFIXES))

# The neutral layer must not depend on ANY domain — that is what makes it neutral.
for m in NEUTRAL_MODULES:
    imps = imports_of(m)
    check(f"{m}: neutral, imports no domain engine",
          not _has(imps, LCA_PREFIXES + LCC_PREFIXES + BENEFIT_PREFIXES))

# The orchestrator may know the neutral layer, but must not embed a domain either.
check("assessment_orchestrator.py: does not import the Streamlit app",
      "app_final_streamlit_ready" not in imports_of("assessment_orchestrator.py"))

# ── 2. STRUCTURAL: the neutral layer holds no domain equations ───────────────
CARBON_TOKENS = ("kgco2e", "co2", "carbon_intensity", "emission_factor")
MONEY_TOKENS = ("discount_rate", "present_value", "tariff", "npv", "escalation_rate")
BENEFIT_TOKENS = ("economic_multiplier", "jobs_created", "value_of_time")

for m in ("shared_activity.py", "project_context.py"):
    body = open(os.path.join(ROOT, m), encoding="utf-8").read()
    # Ignore the prohibition list in the module's own docstring.
    code = body.split('"""', 2)[-1].lower()
    for label, toks in (("carbon", CARBON_TOKENS), ("money", MONEY_TOKENS),
                        ("benefit", BENEFIT_TOKENS)):
        hit = [t for t in toks if t in code]
        check(f"{m}: neutral layer contains no {label} logic ({hit or 'clean'})", not hit)

# system_dynamics_core must be carbon-free: calculate_dynamic_b6 was moved out of it
# precisely because it consumed a grid CI and produced CO2.
sd = open(os.path.join(ROOT, "system_dynamics_core.py"), encoding="utf-8").read()
sd_code = sd.split('"""', 2)[-1]
check("system_dynamics_core.py: no CO2 result is produced",
      "co2" not in sd_code.lower() and "CI" not in sd_code.split("def ")[-1][:200])
check("system_dynamics_core.py: calculate_dynamic_b6 no longer lives here",
      "def calculate_dynamic_b6" not in sd)
check("legacy_lca_engine.py: calculate_dynamic_b6 lives in the LCA domain",
      "def calculate_dynamic_b6" in open(os.path.join(ROOT, "legacy_lca_engine.py"),
                                        encoding="utf-8").read())

# ── 3. BEHAVIOURAL: cross-domain invariance ──────────────────────────────────
from _headless_app import build_ns  # noqa: E402

ns = build_ns(publication_mode=False)
engine = ns["calculate_legacy_dashboard_results"]
base_params = dict(ns["params"])
base = engine(dict(base_params))

CARBON_KEYS = ("gross_a1_c4_tons", "total_embodied_co2", "annual_co2_operational",
               "active_b6_tons", "i_c1c4_tons", "gwp_pkm_gross")
MONEY_KEYS = ("npv_lcc_m", "total_cost", "total_maintenance_cost")
BENEFIT_KEYS = ("total_jobs",)


def run_with(**overrides):
    p = dict(base_params)
    p.update(overrides)
    return engine(p)


def same(a, b, keys):
    return all(abs(float(a[k]) - float(b[k])) < 1e-9 for k in keys if k in a and k in b)


def differs(a, b, keys):
    return any(abs(float(a[k]) - float(b[k])) > 1e-9 for k in keys if k in a and k in b)


# Changing the discount rate must not move any carbon result.
r_disc = run_with(discount_rate=float(base_params.get("discount_rate", 5.0)) + 3.0)
check("changing discount_rate does NOT change carbon", same(base, r_disc, CARBON_KEYS))
check("changing discount_rate DOES change cost", differs(base, r_disc, MONEY_KEYS))

# Changing construction cost must not move carbon.
r_capex = run_with(construction_cost=float(base_params.get("construction_cost", 0.0)) * 2 + 100.0)
check("changing construction_cost does NOT change carbon", same(base, r_capex, CARBON_KEYS))
check("changing construction_cost DOES change cost", differs(base, r_capex, MONEY_KEYS))

# Changing a benefit input must not move carbon OR cost.
r_jobs = run_with(jobs_created=float(base_params.get("jobs_created", 0.0)) + 5000.0,
                  economic_multiplier=float(base_params.get("economic_multiplier", 1.0)) + 1.0)
check("changing jobs/multiplier does NOT change carbon", same(base, r_jobs, CARBON_KEYS))
check("changing jobs/multiplier does NOT change cost", same(base, r_jobs, MONEY_KEYS))
check("changing jobs/multiplier DOES change benefits", differs(base, r_jobs, BENEFIT_KEYS))

# Changing an emission factor must not move any cash flow.
import legacy_lca_engine  # noqa: E402,F401
mat = ns.get("MATERIAL_FACTORS")


def _numeric_leaf(d):
    """Locate the A1-A3 CARBON factor specifically.

    MATERIAL_FACTORS is nested and each record also carries an ENERGY factor
    (ee_mj_per_kg). Perturbing the energy factor would not move the carbon headline, so
    the test must target gwp_kgco2e_per_kg or it proves nothing.
    """
    for _, rec in d.items():
        if isinstance(rec, dict) and "gwp_kgco2e_per_kg" in rec:
            return rec, "gwp_kgco2e_per_kg"
    return None


leaf = _numeric_leaf(mat) if isinstance(mat, dict) else None
if leaf:
    container, key = leaf
    original = container[key]
    container[key] = float(original) * 10.0 + 1.0
    try:
        r_ef = engine(dict(base_params))
        check("changing an emission factor DOES change carbon", differs(base, r_ef, CARBON_KEYS))
        check("changing an emission factor does NOT change cost", same(base, r_ef, MONEY_KEYS))
    finally:
        container[key] = original
else:
    check("MATERIAL_FACTORS reachable for the emission-factor invariance test", False)

# ── 4. The mixed engine no longer contains foreign equations ─────────────────
app = open(os.path.join(ROOT, "app_final_streamlit_ready.py"), encoding="utf-8").read()
tree = ast.parse(app)
fn = next((n for n in tree.body
           if isinstance(n, ast.FunctionDef) and n.name == "calculate_legacy_dashboard_results"),
          None)
check("the mixed calculate_core_lca_lcc name is gone",
      "def calculate_core_lca_lcc" not in app)
check("legacy dashboard engine still exists under its honest name", fn is not None)
if fn is not None:
    body = ast.get_source_segment(app, fn) or ""
    check("legacy engine contains no present-value / NPV equation",
          "1 + r" not in body and "discount_rate_pct=" not in body.replace(
              "params.get(\"discount_rate\", 5.0)", ""))
    check("legacy engine delegates cost to the LCC domain",
          "calculate_legacy_lcc(" in body)
    check("legacy engine delegates jobs to the Benefits domain",
          "calculate_legacy_jobs(" in body)
    check("legacy engine crosses the boundary with neutral activity only",
          "build_shared_activity(" in body)

print("\nDOMAIN SEPARATION VERIFIED" if ok else "\nDOMAIN SEPARATION VIOLATED")
sys.exit(0 if ok else 1)
