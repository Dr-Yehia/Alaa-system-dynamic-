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
BENEFIT_MODULES = ["benefits_core.py", "benefits_reference_registry.py",
                   "benefits_scientific_core.py", "benefits_scientific_integration.py",
                   "benefits_scientific_reporting.py"]
BENEFIT_MODULES = [m for m in BENEFIT_MODULES if os.path.exists(os.path.join(ROOT, m))]
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

# ── 4. The application is UI/orchestration only ──────────────────────────────
app = open(os.path.join(ROOT, "app_final_streamlit_ready.py"), encoding="utf-8").read()
app_tree = ast.parse(app)
app_funcs = {n.name for n in app_tree.body if isinstance(n, ast.FunctionDef)}

check("the mixed calculate_core_lca_lcc name is gone",
      "def calculate_core_lca_lcc" not in app)
check("the app does not DEFINE the assessment engine",
      "def calculate_legacy_dashboard_results" not in app)
check("the app imports the orchestrator", "assessment_orchestrator" in app)

# No domain calculation may be DEFINED in the application any more.
FORBIDDEN_IN_APP = [
    "calculate_lca_summary", "calculate_a4_transport_co2", "calculate_a5_construction",
    "calculate_b2_b5_use_stage", "calculate_c1_c4_end_of_life",
    "calculate_module_d_from_eol", "compute_effective_ef", "b6_ci_trajectory",
    "calculate_lcc_npv", "calculate_lcc_npv_activity_based", "b6_energy_pv_cost",
    "calculate_benefit_kpis", "calculate_dynamic_b6", "simulate_asset_condition",
]
for name in FORBIDDEN_IN_APP:
    check(f"app does not define {name}()", name not in app_funcs)

for const in ("MATERIAL_FACTORS", "EMISSION_FACTORS", "DENSITIES",
              "TRANSPORT_EMISSION_FACTORS", "RECYCLING_CREDIT_SCENARIOS"):
    check(f"app does not define the {const} registry",
          not any(isinstance(n, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == const for t in n.targets)
                  for n in app_tree.body))

# ── 5. The orchestrator owns assembly and holds no equation ──────────────────
orch = open(os.path.join(ROOT, "assessment_orchestrator.py"), encoding="utf-8").read()
orch_code = orch.split('"""', 2)[-1]
check("orchestrator defines calculate_legacy_dashboard_results",
      "def calculate_legacy_dashboard_results" in orch)
check("orchestrator runs the three domains separately",
      "calculate_legacy_lca(" in orch and "calculate_legacy_lcc(" in orch
      and "calculate_benefit_kpis(" in orch)
for tok in ("kgco2e", "* 1000", "/ 1000", "(1 + r)", "1.05 **"):
    check(f"orchestrator contains no arithmetic token {tok!r}", tok not in orch_code)

# The bundle must run the domains ONCE and hand Benefits the activity record the
# other domains already produced — not trigger a second full evaluation.
check("orchestrator exposes the single-run bundle", "def run_assessment_bundle" in orch)
check("the bundle reuses the AssessmentResult's shared activity",
      "shared_activity=result.shared" in orch)
check("the bundle calls run_assessment exactly once",
      orch.split("def run_assessment_bundle")[1].count("run_assessment(params)") == 1)
check("the bundle assembles the dashboard from the same result",
      "assemble_legacy_dashboard_results(result)" in orch)
check("orchestrator contains no Benefits equation id", "EQ=BEN-" not in orch)

# ── 5b. The scientific Benefits domain is reachable and self-contained ───────
ben_int = open(os.path.join(ROOT, "benefits_scientific_integration.py"), encoding="utf-8").read()
check("scientific Benefits integration calls the Benefits core", "core." in ben_int)
check("scientific Benefits integration defines no equation of its own",
      "# EQ=BEN-" not in ben_int)

# ── 6. Per-domain results carry no foreign fields ────────────────────────────
from assessment_orchestrator import run_assessment  # noqa: E402

res = run_assessment(dict(base_params))
check("AssessmentResult.lca contains no NPV/cost field",
      not any(t in k.lower() for k in res.lca for t in ("npv", "lcc_results", "total_cost")))
check("AssessmentResult.lca contains no jobs field",
      not any("jobs" in k.lower() for k in res.lca))
check("AssessmentResult.lcc contains no CO2/GWP field",
      not any(t in k.lower() for k in res.lcc for t in ("co2", "gwp", "carbon")))
check("AssessmentResult.lcc contains no jobs field",
      not any("jobs" in k.lower() for k in res.lcc))
check("AssessmentResult.benefits contains no NPV field",
      not any("npv" in k.lower() for k in res.benefits))
check("AssessmentResult.shared is a neutral activity record",
      hasattr(res.shared, "annual_operational_kwh") and hasattr(res.shared, "served_annual_pkm"))
check("shared activity exposes no carbon or price attribute",
      not any(t in a.lower() for a in dir(res.shared)
              for t in ("co2", "carbon", "tariff", "cost", "npv")))

# ── 7. Scientific Benefits are behaviourally independent too ─────────────────
# Changing a Benefits evidence input must not move carbon or cost, and changing a
# discount rate must not move a Benefits result.
from assessment_orchestrator import run_assessment_bundle  # noqa: E402


def _sci_evidence(value):
    return {
        "value": value, "unit": "passengers/day", "source_ref_id": "REF-EGY-GB-2022",
        "source_file": "test.pdf", "source_location": "test fixture",
        "geography": "Cairo, Egypt", "evidence_status": "PROJECT-SPECIFIC",
    }


_p_base = dict(base_params)
_p_base["benefits_scientific_inputs"] = {
    "transport": {
        "passengers_per_day": _sci_evidence(300_000.0),
        "avg_distance_km": dict(_sci_evidence(10.0), unit="km"),
        "operating_days_per_year": dict(_sci_evidence(350.0), unit="days/year"),
    }
}
_r0, _d0, _b0 = run_assessment_bundle(dict(_p_base))

_p_ben = dict(_p_base)
_p_ben["benefits_scientific_inputs"] = {
    "transport": {
        "passengers_per_day": _sci_evidence(600_000.0),
        "avg_distance_km": dict(_sci_evidence(10.0), unit="km"),
        "operating_days_per_year": dict(_sci_evidence(350.0), unit="days/year"),
    }
}
_r1, _d1, _b1 = run_assessment_bundle(_p_ben)

check("changing scientific Benefits evidence DOES change Benefits",
      _b0.physical["annual_passenger_km"] != _b1.physical["annual_passenger_km"])
check("changing scientific Benefits evidence does NOT change carbon",
      same(_d0, _d1, CARBON_KEYS))
check("changing scientific Benefits evidence does NOT change cost",
      same(_d0, _d1, MONEY_KEYS))

_p_rate = dict(_p_base)
_p_rate["discount_rate"] = float(base_params.get("discount_rate", 5.0)) + 3.0
_r2, _d2, _b2 = run_assessment_bundle(_p_rate)
check("changing the discount rate does NOT change scientific Benefits",
      _b2.physical["annual_passenger_km"] == _b0.physical["annual_passenger_km"])
check("changing the discount rate DOES change cost", differs(_d0, _d2, MONEY_KEYS))

print("\nDOMAIN SEPARATION VERIFIED" if ok else "\nDOMAIN SEPARATION VIOLATED")
sys.exit(0 if ok else 1)
