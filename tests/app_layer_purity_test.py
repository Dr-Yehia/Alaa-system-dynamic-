"""The application is UI + orchestration — it holds no domain science.

The earlier claim "the app delegates and does not calculate" was false: the whole
legacy LCA body still lived inside app_final_streamlit_ready.py. This suite makes the
claim checkable, so it cannot silently become false again.
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


APP = os.path.join(ROOT, "app_final_streamlit_ready.py")
src = open(APP, encoding="utf-8").read()
tree = ast.parse(src)
funcs = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
consts = {t.id for n in tree.body if isinstance(n, ast.Assign)
          for t in n.targets if isinstance(t, ast.Name)}

# ── The engine and its registries are no longer defined here ────────────────
check("app does not define the assessment engine",
      "calculate_legacy_dashboard_results" not in funcs)
check("the mixed calculate_core_lca_lcc is gone", "calculate_core_lca_lcc" not in funcs)

for name in ("calculate_lca_summary", "update_lca_summary_full", "compute_effective_ef",
             "calculate_a4_transport_co2", "calculate_a5_construction",
             "calculate_b2_b5_use_stage", "calculate_c1_c4_end_of_life",
             "calculate_module_d_from_eol", "b6_ci_trajectory", "b6_served_annual_pkm",
             "build_b2_b5_activity_schedule", "update_material_mass_balance",
             "calculate_lcc_npv", "calculate_lcc_npv_activity_based", "b6_energy_pv_cost",
             "calculate_benefit_kpis", "calculate_legacy_jobs",
             "simulate_asset_condition", "calculate_dynamic_b6"):
    check(f"app does not define {name}()", name not in funcs)

for name in ("MATERIAL_FACTORS", "MATERIAL_KEY_MAP", "MATERIALS_LIST", "DENSITIES",
             "FUEL_FACTORS", "TRANSPORT_EMISSION_FACTORS", "TRANSPORT_FACTOR_REGISTRY",
             "RECYCLING_CREDIT_SCENARIOS", "ASSESSMENT_LIFETIME_YEARS"):
    check(f"app does not define the {name} registry/constant", name not in consts)

# ── It imports the separated architecture instead ───────────────────────────
imports = set()
for node in ast.walk(tree):
    if isinstance(node, ast.ImportFrom) and node.module:
        imports.add(node.module.split(".")[0])
    elif isinstance(node, ast.Import):
        imports.update(a.name.split(".")[0] for a in node.names)

for mod in ("assessment_orchestrator", "uncertainty_orchestrator", "legacy_lca_engine",
            "legacy_lcc_engine", "benefits_core", "shared_activity", "project_context",
            "system_dynamics_core"):
    check(f"app imports {mod}", mod in imports)

# ── Monte Carlo evaluates through the separated engines ─────────────────────
check("Monte Carlo evaluates samples via the uncertainty orchestrator",
      "evaluate_sample(" in src)
check("Monte Carlo no longer evaluates samples through a mixed engine",
      "run_full_assessment(p_i)" not in src)

# ── Publication mode does not present the legacy scalar as scientific LCC ───
check("publication card does not label the legacy NPV as the LCC headline",
      "\"metric-label\">LCC NPV Cost</div>\n                <div class=\"metric-delta\">LCCA"
      not in src)
check("publication card states the scientific LCC is pending",
      "integration pending" in src)

# The prohibition legacy_lcc_engine declares must actually hold in the app.
legacy_lcc = open(os.path.join(ROOT, "legacy_lcc_engine.py"), encoding="utf-8").read()
check("legacy_lcc_engine still declares the publication prohibition",
      "MUST NOT supply Publication-mode LCC" in legacy_lcc)

# ── The app shrank substantially ────────────────────────────────────────────
size = os.path.getsize(APP)
check(f"app is materially smaller than the 295,551-byte baseline ({size:,} bytes)",
      size < 240_000)

print("\nAPP LAYER PURITY VERIFIED" if ok else "\nAPP LAYER PURITY VIOLATED")
sys.exit(0 if ok else 1)
