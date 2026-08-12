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


APP = os.path.join(ROOT, "apps/_developer_impl.py")
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
    # Full dotted paths, not just the first segment: every domain now lives under
    # the one `monorail_assessment` package, so a first-segment-only check would
    # collapse LCA, LCC and Benefits into a single indistinguishable name.
    if isinstance(node, ast.ImportFrom) and node.module:
        imports.add(node.module)
    elif isinstance(node, ast.Import):
        imports.update(a.name for a in node.names)

for mod in ("monorail_assessment.legacy.assessment_orchestrator", "monorail_assessment.legacy.uncertainty_orchestrator", "monorail_assessment.legacy.lca_engine",
            "monorail_assessment.legacy.lcc_engine", "monorail_assessment.legacy.benefits_core", "monorail_assessment.common.shared_activity", "monorail_assessment.common.project_context",
            "monorail_assessment.common.system_dynamics", "monorail_assessment.benefits.integration",
            "monorail_assessment.benefits.references"):
    check(f"app imports {mod}", mod in imports)

# ── The app collects Benefits EVIDENCE but defines no Benefits SCIENCE ──────
# The UI may build a form and render a table. The moment it computes a diversity
# index or an avoided-emission figure itself, the source-traceability contract is
# broken: an equation in the app carries no registry record and no audit row.
for name in ("annual_passenger_km", "shifted_passenger_km", "allocate_shifted_pkm",
             "emissions_from_gas_factor", "emissions_from_co2e_factor", "avoided_emissions",
             "passenger_hours_saved", "monetize_time_saving",
             "generated_traffic_benefit_rule_of_half", "vot_from_logit_coefficients",
             "land_use_shares", "normalized_land_use_diversity", "land_use_diversity_delta",
             "built_up_change_pct", "land_consumption_rate", "population_growth_rate",
             "lcr_pgr_ratio", "built_up_area_per_capita", "technical_coefficients",
             "leontief_inverse", "io_output_response", "output_multiplier",
             "employment_multiplier", "jobs_proxy", "physical_noise_delta"):
    check(f"app does not define the Benefits equation {name}()", name not in funcs)

check("app defines no Benefits equation registry", "BEN_EQUATIONS" not in consts)
# Signature fragments of the Benefits equations. Any of these appearing in the app
# would mean the science was reimplemented in the presentation layer.
for fragment in ("math.log(n_classes)", "* 60.0", "0.5 * generated",
                 "np.linalg.inv(np.eye"):
    check(f"app source contains no Benefits arithmetic fragment {fragment!r}",
          fragment not in src)
check("app carries no EQ= source comment (those belong to the scientific cores)",
      "# EQ=BEN-" not in src)

# ── Publication mode cannot present legacy Benefits as scientific output ────
check("the Results Benefits panel branches on publication mode",
      "if publication_mode:\n            render_scientific_benefits_panel" in src)
check("the legacy Benefit KPI table is labelled Developer/legacy",
      "Developer / legacy Benefit KPIs" in src)
check("legacy Benefit KPI inputs are collected in Developer mode only",
      "Legacy Benefit KPI inputs (developer only)" in src)
check("the scientific Benefits tab exists",
      "'sci_benefits'" in src and "Scientific Benefits (referenced)" in src)
check("the app runs the domains once via the orchestrator bundle",
      "run_assessment_bundle(params)" in src)

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
legacy_lcc = open(os.path.join(ROOT, "monorail_assessment/legacy/lcc_engine.py"), encoding="utf-8").read()
check("legacy_lcc_engine still declares the publication prohibition",
      "MUST NOT supply Publication-mode LCC" in legacy_lcc)

# ── The app stays materially smaller than the pre-separation monolith ───────
# The ceiling exists to stop domain science drifting back into the app. It is a
# blunt proxy, so it moves when the app legitimately gains PRESENTATION code —
# the Benefits evidence-collection forms are a large block of pure UI. The
# substantive guarantee is the equation-absence block above, which fails on the
# actual science rather than on a byte count.
size = os.path.getsize(APP)
check(f"app is materially smaller than the 295,551-byte pre-separation baseline ({size:,} bytes)",
      size < 270_000)

print("\nAPP LAYER PURITY VERIFIED" if ok else "\nAPP LAYER PURITY VIOLATED")
sys.exit(0 if ok else 1)
