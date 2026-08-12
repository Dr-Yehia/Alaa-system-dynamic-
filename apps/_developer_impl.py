import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import io

# ── Referenced scientific LCA core (separate, fully-sourced module) ──
# CANONICAL PUBLICATION LCA:
# `lca_scientific_core.py` + `lca_scientific_integration.py` are the ONLY scientific
# source for Publication-mode LCA cards/reports/CSV/Excel.
#
# LEGACY-DEVELOPER-ONLY:
# older constants/functions below remain only for developer comparison/backward compatibility.
# Their values MUST NOT enter Publication-mode scientific LCA or be presented as verified
# project evidence. Unknown/placeholder legacy values are SCENARIO-ONLY or SOURCE-OPEN.
try:
    from lca_scientific_core import ScientificInputError, render_lca_audit_streamlit, OPEN_SOURCE_REQUIREMENTS
    from lca_scientific_integration import add_lca_source_inputs, run_scientific_lca_from_app_params
    from lca_scientific_reporting import (scientific_report_text, scientific_csv, scientific_excel_bytes,
                                          export_parity_ok, scientific_headline)
    SCI_LCA_AVAILABLE = True
except Exception as _sci_import_err:  # pragma: no cover - defensive
    SCI_LCA_AVAILABLE = False
    _SCI_IMPORT_ERROR = str(_sci_import_err)

# ── Separated assessment domains ──────────────────────────────────────────────
# Each domain lives in its own module and none of them imports another. The neutral
# layers (project context, system dynamics state) are shared; carbon, money and
# benefits are not. See assessment_orchestrator.py for how the three are combined.
from project_context import ASSESSMENT_LIFETIME_YEARS, ProjectContext, context_from_params
from system_dynamics_core import simulate_asset_condition
from shared_activity import build_shared_activity, SharedActivity
from legacy_lca_engine import (calculate_dynamic_b6, calculate_legacy_lca,
                               MATERIAL_FACTORS, MATERIAL_KEY_MAP, MATERIALS_LIST,
                               DENSITIES, FUEL_FACTORS, TRANSPORT_EMISSION_FACTORS,
                               TRANSPORT_FACTOR_REGISTRY, RECYCLING_CREDIT_SCENARIOS,
                               compute_effective_ef, calculate_lca_summary,
                               update_lca_summary_full, update_material_mass_balance,
                               calculate_a4_transport_co2, calculate_a5_construction,
                               calculate_a5_diesel_equipment, calculate_b2_b5_use_stage,
                               calculate_c1_c4_end_of_life, calculate_module_d_from_eol,
                               build_b2_b5_activity_schedule, b6_ci_trajectory,
                               b6_served_annual_pkm, validate_eol_treatment_shares,
                               validate_a5_treatment_shares, _parse_year_list)
from legacy_lcc_engine import (b6_energy_pv_cost, calculate_lcc_npv,
                               calculate_lcc_npv_activity_based, calculate_legacy_lcc)
# LEGACY-DEVELOPER-ONLY. Kept for Developer-mode parity and the historical dashboard.
# It is NOT the Publication Benefits engine — that is benefits_scientific_* below.
from benefits_core import calculate_benefit_kpis, calculate_legacy_jobs
# ── Scientific Benefits (referenced, evidence-gated) ──────────────────────────
# The Publication Benefits engine. It computes nothing without evidence and marks
# every KPI with the provenance state that decides whether it may be published.
from benefits_reference_registry import (
    EQUATIONS as BENEFITS_EQUATIONS,
    REFERENCES as BENEFITS_REFERENCES,
    permitted_statuses_for as benefits_permitted_statuses_for,
)
from benefits_scientific_integration import (
    PUBLICATION_ELIGIBLE_STATES as BENEFITS_PUBLICATION_STATES,
    ScientificBenefitsResult,
    run_scientific_benefits_from_params,
)
from benefits_scientific_reporting import (
    export_parity_ok as benefits_export_parity_ok,
    scientific_benefits_csv,
    scientific_benefits_excel_bytes,
    scientific_benefits_source_appendix,
    scientific_benefits_table,
)
# The application NO LONGER defines the assessment engine. It calls the orchestrator,
# which runs LCA, LCC and Benefits as independent domains and assembles the combined
# dictionary the legacy dashboard expects.
from assessment_orchestrator import (run_assessment, split_params,
                                     calculate_legacy_dashboard_results,
                                     assemble_legacy_dashboard_results,
                                     run_assessment_bundle)
from uncertainty_orchestrator import evaluate_sample

# ═══════════════════════════════════════════════════════════════
# PAGE CONFIGURATION
# ═══════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Enhanced Monorail LCA/LCCA Assessment Tool",
    page_icon="🚝",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ═══════════════════════════════════════════════════════════════
# SCIENTIFIC BENEFITS — UI EVIDENCE COLLECTION HELPERS
# ───────────────────────────────────────────────────────────────
# These build the evidence envelopes the referenced Benefits core requires. They
# live in the UI layer on purpose: collecting a page number from a form is
# presentation work, not science, and putting it in the core would give the core
# a reason to know about Streamlit.
#
# A field here is deliberately more work to fill than a plain number box. That is
# the point — the extra fields ARE the difference between a value and evidence.
# ═══════════════════════════════════════════════════════════════

#: Evidence statuses a user may assign, ordered from weakest to strongest.
BENEFIT_EVIDENCE_STATUSES = [
    "SOURCE-OPEN",        # nothing supplied yet
    "METHOD-REFERENCE",   # a document that supports the FORMULA only
    "SCENARIO-ONLY",      # an explicit assumption, labelled as such
    "HISTORICAL",         # real data from an earlier period/basis
    "REF-PROXY",          # an external benchmark, transferred
    "PROJECT-SPECIFIC",   # measured or modelled for THIS project
    "OFFICIAL-PROJECT-DATA",  # stated by an official project document
]

_BENEFIT_REF_CHOICES = ["(none)"] + sorted(BENEFITS_REFERENCES)


def _benefit_status_choices(ref_id):
    """The statuses this reference can actually back, plus the project routes.

    Offering the full list beside every reference is what makes authority
    escalation a two-click mistake. A method reference can only back its own
    role; a project claim is reached by describing the project document instead,
    which the form then insists on completing.
    """
    if ref_id and ref_id != "(none)":
        permitted = list(benefits_permitted_statuses_for(ref_id))
    else:
        permitted = []
    # PROJECT-SPECIFIC is never granted by a registry document; it is granted by
    # a project source record, which the caller collects below.
    choices = ["SOURCE-OPEN"] + [s for s in permitted if s != "SOURCE-OPEN"]
    if "PROJECT-SPECIFIC" not in choices:
        choices.append("PROJECT-SPECIFIC")
    return choices


def benefit_evidence_input(label, *, key, unit, default_ref="(none)",
                           monetary=False, help_text=""):
    """Collect one numeric quantity together with the provenance that justifies it.

    Returns an evidence mapping, or ``None`` when no value was entered. Returning
    None rather than 0.0 matters: the Benefits gate distinguishes "not supplied"
    from "measured as zero", and a default of 0.0 would erase that distinction.
    """
    st.markdown(f"**{label}**" + (f"  \n_{help_text}_" if help_text else ""))
    cols = st.columns([1.1, 1.0, 1.0])
    with cols[0]:
        raw = st.text_input(f"Value ({unit})", value="", key=f"{key}_val",
                            help="Leave empty to keep this input SOURCE-OPEN.")
    with cols[1]:
        ref_id = st.selectbox("Source reference", _BENEFIT_REF_CHOICES,
                              index=_BENEFIT_REF_CHOICES.index(default_ref)
                              if default_ref in _BENEFIT_REF_CHOICES else 0,
                              key=f"{key}_ref")
    with cols[2]:
        # Only what the chosen reference can actually back. A method reference
        # cannot be relabelled into project data from this box.
        _status_choices = _benefit_status_choices(ref_id)
        status = st.selectbox("Evidence status", _status_choices,
                              index=0, key=f"{key}_status",
                              help="METHOD-REFERENCE supports the equation. "
                                   "PROJECT-SPECIFIC requires the project document "
                                   "fields below; it is never granted by citing a "
                                   "method reference.")
    cols2 = st.columns([1.2, 1.4, 1.0])
    with cols2[0]:
        source_file = st.text_input("Source file / report", value="", key=f"{key}_file")
    with cols2[1]:
        location = st.text_input("Exact page / table / section", value="", key=f"{key}_loc",
                                 help="e.g. 'Annex 4, printed pp.71-72'. A bare page "
                                      "number makes a reviewer hunt.")
    with cols2[2]:
        geography = st.text_input("Geography", value="", key=f"{key}_geo")

    # A project claim is certified by a project document, not by the registry.
    project_src = None
    if status in ("PROJECT-SPECIFIC", "OFFICIAL-PROJECT-DATA"):
        st.caption("Project numeric source — required for a project claim. "
                   "All fields must be filled or this input stays source-open.")
        pcols = st.columns([1.2, 1.0, 1.0])
        with pcols[0]:
            ps_title = st.text_input("Project document title", value="", key=f"{key}_ps_title")
        with pcols[1]:
            ps_issuer = st.text_input("Issuer / author", value="", key=f"{key}_ps_issuer")
        with pcols[2]:
            ps_date = st.text_input("Observation date", value="", key=f"{key}_ps_date",
                                    help="When the number was measured or reported.")
        pcols2 = st.columns([1.2, 1.4])
        with pcols2[0]:
            ps_file = st.text_input("Project file or URL", value="", key=f"{key}_ps_file")
        with pcols2[1]:
            ps_loc = st.text_input("Exact location in the project document",
                                   value="", key=f"{key}_ps_loc")
        project_src = {
            "title": ps_title, "issuer": ps_issuer, "file_or_url": ps_file,
            "exact_location": ps_loc, "geography": geography,
            "observation_date": ps_date, "evidence_status": status,
        }

    observation_date = None
    if project_src:
        observation_date = project_src["observation_date"] or None

    currency = price_year = None
    if monetary:
        cols3 = st.columns(2)
        with cols3[0]:
            currency = st.text_input("Currency", value="", key=f"{key}_ccy")
        with cols3[1]:
            py_raw = st.text_input("Price base year", value="", key=f"{key}_py")
        try:
            price_year = int(str(py_raw).strip()) if str(py_raw).strip() else None
        except (TypeError, ValueError):
            price_year = None

    text = str(raw or "").strip()
    if not text:
        return None
    try:
        value = float(text)
    except (TypeError, ValueError):
        st.warning(f"{label}: '{text}' is not a number; this input stays SOURCE-OPEN.")
        return None

    return {
        "value": value,
        "unit": unit,
        "source_ref_id": "" if ref_id == "(none)" else ref_id,
        "source_file": source_file,
        "source_location": location,
        "geography": geography,
        "evidence_status": status,
        "currency": currency or None,
        "price_base_year": price_year,
        "observation_date": observation_date,
        "project_source": project_src,
    }


def _benefit_area_table(label, *, key, help_text="", unit="ha", collect_evidence=True):
    """Collect land-use class areas, with the provenance of the map behind them.

    A free-text block rather than a widget grid, because the class schema itself
    is project evidence: the baseline and the project must use the SAME classes,
    and a fixed set of boxes would quietly impose a schema the maps do not have.

    The areas come back wrapped in the same evidence envelope as every other
    project number. A land-use index computed from an unattributed map is not
    publishable, and a free-text "analysis area source" line one screen away is a
    note, not an evidence record — a reviewer cannot tell from it which layer,
    which date or which classification produced the areas.
    """
    st.markdown(f"**{label}**" + (f"  \n_{help_text}_" if help_text else ""))
    raw = st.text_input(f"one 'class = area' per line, separated by ';' (areas in {unit})",
                        value="", key=key)
    areas = {}
    for line in str(raw or "").replace("\n", ";").split(";"):
        if "=" not in line:
            continue
        name, _, amount = line.partition("=")
        name = name.strip()
        try:
            areas[name] = float(amount.strip())
        except (TypeError, ValueError):
            continue
    if not areas or not collect_evidence:
        return areas or {}

    mcols = st.columns([1.2, 1.0, 1.0])
    with mcols[0]:
        map_title = st.text_input("Map / layer title", value="", key=f"{key}_m_title")
    with mcols[1]:
        map_issuer = st.text_input("Produced by", value="", key=f"{key}_m_issuer")
    with mcols[2]:
        map_date = st.text_input("Observation date", value="", key=f"{key}_m_date")
    mcols2 = st.columns([1.2, 1.4, 1.0])
    with mcols2[0]:
        map_file = st.text_input("Map file or URL", value="", key=f"{key}_m_file")
    with mcols2[1]:
        map_loc = st.text_input("Analysis extent + class schema", value="", key=f"{key}_m_loc",
                                help="e.g. 'Node-A 800 m buffer, class schema v2'.")
    with mcols2[2]:
        map_geo = st.text_input("Geography", value="", key=f"{key}_m_geo")

    project_src = {
        "title": map_title, "issuer": map_issuer, "file_or_url": map_file,
        "exact_location": map_loc, "geography": map_geo,
        "observation_date": map_date, "evidence_status": "PROJECT-SPECIFIC",
    }
    return {
        "value": areas,
        "unit": unit,
        "source_ref_id": "",
        "source_file": map_file,
        "source_location": map_loc,
        "geography": map_geo,
        "evidence_status": "PROJECT-SPECIFIC",
        "observation_date": map_date,
        "project_source": project_src,
    }


def collect_benefits_scientific_inputs():
    """Build the whole `benefits_scientific_inputs` evidence tree from the sidebar."""
    st.markdown("#### 🚈 Transport activity, modal shift and emissions")
    transport = {
        "passengers_per_day": benefit_evidence_input(
            "Passengers per day", key="sben_pax_day",
            unit="passengers/day", default_ref="REF-EGY-GB-2022"),
        "avg_distance_km": benefit_evidence_input(
            "Average passenger trip distance", key="sben_dist",
            unit="km/passenger", default_ref="REF-EGY-GB-2022"),
        "operating_days_per_year": benefit_evidence_input(
            "Operating days per year", key="sben_days",
            unit="days/year", default_ref="REF-EGY-GB-2022",
            help_text="Supply the project's own service calendar. The 365 days used "
                      "inside the green bond report is that report's assumption."),
        "modal_shift_fraction": benefit_evidence_input(
            "Modal-shift fraction", key="sben_modal",
            unit="fraction 0-1", default_ref="REF-EGY-GB-2022",
            help_text="A Cairo measurement. The report's 20-50% band and its 30% "
                      "featured case are scenarios, not project evidence."),
        "car_share_of_shift": benefit_evidence_input(
            "Car share of displaced travel", key="sben_car_share",
            unit="fraction 0-1"),
        "bus_share_of_shift": benefit_evidence_input(
            "Bus share of displaced travel", key="sben_bus_share",
            unit="fraction 0-1", help_text="Car share + bus share must equal 1."),
        "car_emission_factor": benefit_evidence_input(
            "Car emission factor", key="sben_car_ef",
            unit="kgCO2e/pkm", help_text="Already-CO2e basis. Do not enter a "
                                         "gas-specific factor here."),
        "bus_emission_factor": benefit_evidence_input(
            "Bus emission factor", key="sben_bus_ef", unit="kgCO2e/pkm"),
        "project_emission_factor": benefit_evidence_input(
            "Monorail emission factor", key="sben_proj_ef", unit="kgCO2e/pkm"),
        "annual_trips": benefit_evidence_input(
            "Annual trips (existing passengers)", key="sben_trips",
            unit="trips/year", default_ref="REF-WB-ENRRP-ICR"),
        "baseline_time_min": benefit_evidence_input(
            "Baseline journey time", key="sben_t0", unit="min"),
        "project_time_min": benefit_evidence_input(
            "Project journey time", key="sben_t1", unit="min"),
        "generated_trips": benefit_evidence_input(
            "Generated (newly induced) trips", key="sben_gen",
            unit="trips/year", default_ref="REF-WB-ENRRP-ICR",
            help_text="Only these receive the Rule of Half. Existing passengers "
                      "keep the full time benefit."),
        "value_of_time": benefit_evidence_input(
            "Value of travel time", key="sben_vot",
            unit="currency/hour", default_ref="REF-EGY-VOT-2022", monetary=True,
            help_text="Currency and price base year are required before any "
                      "monetary benefit is produced."),
    }

    st.markdown("#### 🗺️ Land use around the transit nodes")
    land_use = {
        "analysis_area_id": st.text_input("Analysis area identifier", value="", key="sben_area_id"),
        "analysis_area_source": st.text_input(
            "GIS source and date", value="", key="sben_area_src",
            help="Required before the land-use indices can be publication eligible."),
        "influence_radius_m": benefit_evidence_input(
            "TOD influence radius", key="sben_radius", unit="m",
            help_text="The Indian national TOD policy's 500-800 m band is a policy "
                      "benchmark, not the Cairo radius."),
        "baseline_area_by_class": _benefit_area_table(
            "Baseline land-use areas", key="sben_lu_base",
            help_text="e.g. residential = 42.5; commercial = 18.0"),
        "project_area_by_class": _benefit_area_table(
            "Project land-use areas", key="sben_lu_proj",
            help_text="Must use exactly the same class names as the baseline."),
    }
    _baseline_maps = land_use["baseline_area_by_class"]
    if isinstance(_baseline_maps, dict) and "value" in _baseline_maps:
        _baseline_maps = _baseline_maps.get("value") or {}
    land_use["class_schema"] = sorted(_baseline_maps)

    st.markdown("#### 🏙️ Urban growth (SDG 11.3.1)")
    gcols = st.columns(2)
    with gcols[0]:
        past_year_raw = st.text_input("Past observation year", value="", key="sben_yr_past")
    with gcols[1]:
        present_year_raw = st.text_input("Present observation year", value="", key="sben_yr_now")

    def _year(raw):
        try:
            return int(str(raw).strip()) if str(raw or "").strip() else None
        except (TypeError, ValueError):
            return None

    urban_growth = {
        "past_year": _year(past_year_raw),
        "present_year": _year(present_year_raw),
        "built_up_past": benefit_evidence_input(
            "Built-up area (past)", key="sben_bu_past", unit="m2",
            default_ref="REF-UNHABITAT-SDG1131-2025"),
        "built_up_present": benefit_evidence_input(
            "Built-up area (present)", key="sben_bu_now", unit="m2",
            default_ref="REF-UNHABITAT-SDG1131-2025"),
        "population_past": benefit_evidence_input(
            "Population (past)", key="sben_pop_past", unit="persons"),
        "population_present": benefit_evidence_input(
            "Population (present)", key="sben_pop_now", unit="persons"),
    }

    st.markdown("#### 👷 Employment")
    employment = {
        "official_construction_jobs": benefit_evidence_input(
            "Officially reported construction jobs", key="sben_jobs_con",
            unit="jobs", default_ref="REF-EGY-GB-2022",
            help_text="A reported figure. No equation is applied to it."),
        "official_operational_jobs": benefit_evidence_input(
            "Officially reported operational jobs", key="sben_jobs_ops",
            unit="jobs", default_ref="REF-EGY-GB-2022"),
        "proxy_investment_constant_2015_usd_m": benefit_evidence_input(
            "Investment on a constant-2015-USD basis", key="sben_proxy_inv",
            unit="million constant 2015 USD", default_ref="REF-MOSZORO-2024",
            help_text="The proxy study standardises money to constant 2015 USD; the "
                      "investment must match that basis."),
        "jobs_per_musd_proxy": benefit_evidence_input(
            "Benchmark jobs per US$1m", key="sben_proxy_jc",
            unit="jobs per US$1m", default_ref="REF-MOSZORO-2024",
            help_text="A cross-country benchmark. The result is never 'Cairo jobs "
                      "created' and is never added to the official figures."),
    }

    return {
        "transport": transport,
        "land_use": land_use,
        "urban_growth": urban_growth,
        "employment": employment,
        "input_output": {},
        "noise": {"rows": []},
        "formalization": {"evidence_status": "SOURCE-OPEN"},
    }


# ═══════════════════════════════════════════════════════════════
# SCIENTIFIC BENEFITS — RENDERING
# ───────────────────────────────────────────────────────────────
# Presentation only. Every number shown here was computed by the Benefits core
# and classified by the Benefits integration layer; nothing is recalculated.
# ═══════════════════════════════════════════════════════════════

#: Result-group labels, kept separate on screen for the same reason they are kept
#: separate in the result object: they are not commensurable.
_BENEFIT_GROUP_LABELS = [
    ("physical", "🌍 Physical benefits"),
    ("monetized_cba", "💰 Monetised CBA benefits"),
    ("economic_impact", "🏗️ Economic impact (activity, not welfare)"),
    ("employment", "👷 Employment"),
]

_BENEFIT_STATUS_ICON = {
    "COMPUTED": "🟢",
    "OFFICIAL-REPORTED": "🟢",
    "SCENARIO-ONLY": "🟡",
    "PROXY": "🟡",
    "SOURCE-OPEN": "🟠",
    "NOT-APPLICABLE": "⚪",
    "BLOCKED": "🔴",
}


def _benefit_value_text(row):
    """Format a KPI value without inventing precision it does not have."""
    value = row["value"]
    if value is None:
        return "—"
    if isinstance(value, dict):
        return ", ".join(f"{k}: {v:,.1f}" for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return ", ".join(f"{float(v):,.4g}" for v in value)
    if isinstance(value, (int, float)):
        return f"{value:,.4g}"
    return str(value)


def benefit_rows_dataframe(rows):
    """Reviewer-facing table: value, unit, state, and the chain back to the source."""
    return pd.DataFrame([
        {
            "": _BENEFIT_STATUS_ICON.get(r["status"], "•"),
            "KPI": r["kpi_name"],
            "Value": _benefit_value_text(r),
            "Unit": r["unit"],
            "Equation": r["equation_id"] or "—",
            "Evidence state": r["status"],
            "Method source": r["method_ref_ids"] or "—",
            "Numeric source": r["numeric_source_ref_ids"] or "—",
            "Publication eligible": "yes" if r["publication_eligible"] else "no",
        }
        for r in rows
    ])


def render_scientific_benefits_panel(container, benefits_result, *, compact=False):
    """Render the referenced Benefits result, grouped and never totalled.

    When the gate is not satisfied this still renders: it shows WHAT is missing
    rather than hiding the panel, because an empty screen tells a reviewer less
    than a list of the evidence that would close each item.
    """
    gate = benefits_result.publication_gate
    rows = benefits_result.rows

    # Three distinct states, because "one KPI is sourced" and "the Benefits
    # domain is publication-ready" are different claims and conflating them is
    # how a chapter gets written on a single closed input.
    if gate["full_publication_ready"]:
        container.success(
            "🟢 **Referenced Benefits engine — publication-ready.** Every required KPI "
            "was computed from an equation with a registered source, using inputs whose "
            "provenance passed the Benefits evidence gate."
        )
    elif gate["partial_publication_ready"]:
        container.warning(
            "🟡 **Partially sourced — NOT publication-ready as a domain.** Some KPIs "
            "are backed by project evidence, but required items are still open, so the "
            "Benefits chapter cannot yet be presented as closed. Individual eligible "
            "KPIs are marked below."
        )
        if gate["missing_required_kpis"]:
            container.markdown(
                "Required and still open: "
                + "; ".join(gate["missing_required_kpis"])
            )
    else:
        container.warning(
            "🟠 **Benefits are not publication-ready.** The referenced engine computed "
            "what the supplied evidence supports and reports the rest as source-open or "
            "blocked. Legacy Benefit KPIs are NOT shown here as a substitute — they carry "
            "no source, page or geography and are not an equivalent result."
        )

    ready_flags = [
        ("Physical", gate["physical_ready"]),
        ("Monetised time", gate["monetized_time_ready"]),
        ("Economic impact", gate["economic_impact_ready"]),
        ("Employment", gate["employment_ready"]),
        ("Noise (physical)", gate["noise_physical_ready"]),
    ]
    container.markdown(
        " · ".join(f"{'🟢' if flag else '🟠'} {label}" for label, flag in ready_flags)
    )

    for group_key, group_label in _BENEFIT_GROUP_LABELS:
        group_rows = [r for r in rows if r["result_group"] == group_key]
        if not group_rows:
            continue
        container.markdown(f"##### {group_label}")
        container.dataframe(benefit_rows_dataframe(group_rows),
                            use_container_width=True, hide_index=True)

    # No combined headline. Physical tonnes, monetised hours, gross output and job
    # counts are four different kinds of quantity; a single "Total Benefit" would
    # have no defensible unit and would invite netting against LCC or LCA.
    container.caption(
        "Reported as four separate groups. There is no combined 'Total Benefit': "
        "avoided tCO₂e, monetised hours, gross economic output and job counts are "
        "not commensurable. Benefits never reduce LCC NPV and never reduce LCA "
        "Gross A–C."
    )

    if gate["source_open_items"]:
        with container.expander(f"🟠 Source-open items ({len(gate['source_open_items'])})",
                                expanded=False):
            for item in gate["source_open_items"]:
                st.markdown(f"- {item}")
    if gate["blocked_items"]:
        with container.expander(f"🔴 Blocked until evidence closes ({len(gate['blocked_items'])})",
                                expanded=False):
            for item in gate["blocked_items"]:
                st.markdown(f"- {item}")
    if gate["warnings"] and not compact:
        with container.expander(f"🟡 Not publication-eligible ({len(gate['warnings'])})",
                                expanded=False):
            for item in gate["warnings"]:
                st.markdown(f"- {item}")

# ═══════════════════════════════════════════════════════════════
# LI & ZHU (2022) MONORAIL LCA BENCHMARK - EXTERNAL COMPARISON ONLY
# Reference: Li and Zhu (2022)
# DOI: 10.1155/2022/3872069
# Journal: Computational Intelligence and Neuroscience (Hindawi)
# Used ONLY as an external benchmark / reproduction reference.
# It is NEVER a source of material factors and NEVER a calibration input
# to the core LCA/LCCA model. The full bibliographic citation (exact title and
# any indexing/quartile claim) is given in the manuscript against the DOI below;
# the tool identifies the work by DOI to avoid carrying unverified metadata.
# ═══════════════════════════════════════════════════════════════

# LEGACY-DEVELOPER-ONLY / NOT-CANONICAL-SCIENTIFIC-LCA.
# Numerical values below are benchmark/scenario/backward-compatibility values.
# They MUST NOT feed Publication-mode LCA. Where a primary source is not fully
# verified, status remains SCENARIO-ONLY or SOURCE-OPEN — never fabricate provenance.
# Comparative benchmark figures retained for developer comparison only.
LIZHU_2022_BENCHMARK = {
    'reference': {
        'cite_as': 'Li & Zhu (2022), DOI 10.1155/2022/3872069 — full citation in manuscript',
        'authors': 'Li and Zhu',
        'journal': 'Computational Intelligence and Neuroscience (Hindawi)',
        'year': 2022,
        'doi': '10.1155/2022/3872069',
        'role': 'External benchmark / reproduction reference only — never a factor or calibration source',
        'verification': 'Peer-reviewed scientific publication (benchmark only)'
    },
    'system_parameters': {
        'length_km': 96,
        'lifetime_years': 100,
        'functional_unit': '1 passenger-km',
        'system_boundary': 'Cradle-to-grave'
    },
    'material_intensity_per_km': {
        'concrete_m3': 7291.67,
        'steel_tons': 1041.67,
        'aluminum_tons': 52.08,
        'unit': 'per km'
    },
    'embodied_impact_per_km': {
        'energy_GJ': 55982,
        'carbon_tons_CO2': 4662,
        'unit': 'per km'
    },
    'operational_performance': {
        'energy_kwh_per_pkm': 0.088,
        'carbon_kgCO2_per_pkm': 0.0352,
        'unit': 'per passenger-km'
    }
}

# ═══════════════════════════════════════════════════════════════
# REFERENCE VALUES
# ═══════════════════════════════════════════════════════════════
# LEGACY-DEVELOPER-ONLY / NOT-CANONICAL-SCIENTIFIC-LCA.
# Numerical values below are benchmark/scenario/backward-compatibility values.
# They MUST NOT feed Publication-mode LCA. Where a primary source is not fully
# verified, status remains SCENARIO-ONLY or SOURCE-OPEN — never fabricate provenance.
# Reference-project quantities used by the legacy dashboard scaling only.
REF_CONCRETE = 700000
REF_STEEL = 100000
REF_ALUMINUM = 10000
REF_WOOD = 2000
REF_FRP = 1000
REF_GLASS = 500
REF_LENGTH = 96




MATERIAL_FACTOR_AUDIT = pd.DataFrame([
    {
        "material": key,
        "ice_name": val.get("ice_name", "n/a"),
        "gwp_kgco2e_per_kg": val["gwp_kgco2e_per_kg"],
        "dqi_score": val.get("dqi_score", None),
        "ee_mj_per_kg (legacy)": val["ee_mj_per_kg"],
        "carbon_source": val["source"],
        "energy_source": val.get("ee_source", "n/a"),
        "source_id": val.get("source_id", "not specified"),
        "declared_unit": val.get("declared_unit", "1 kg"),
        "version": val["version"],
        "material_category": val["material_category"],
        "boundary": val["boundary"],
        "status": val["status"],
    }
    for key, val in MATERIAL_FACTORS.items()
])


# LEGACY-DEVELOPER-ONLY / NOT-CANONICAL-SCIENTIFIC-LCA.
# Numerical values below are benchmark/scenario/backward-compatibility values.
# They MUST NOT feed Publication-mode LCA. Where a primary source is not fully
# verified, status remains SCENARIO-ONLY or SOURCE-OPEN — never fabricate provenance.
# SCENARIO-ONLY uncertainty ranges for the legacy illustrative Monte Carlo.
UNCERTAINTY_FACTORS = {
    "concrete_factor": {"cv": 0.10, "source": "Scenario assumption; replace with EPD/database uncertainty before final statistical claims"},
    "steel_factor": {"cv": 0.08, "source": "Scenario assumption; replace with EPD/database uncertainty before final statistical claims"},
    "energy_factor": {"cv": 0.15, "source": "Scenario assumption; replace with measured operational uncertainty before final statistical claims"},
    "grid_carbon_factor": {"cv": 0.12, "source": "Scenario assumption; replace with grid-factor uncertainty before final statistical claims"}
}





# ═══════════════════════════════════════════════════════════════
# SCIENTIFIC CALCULATION FUNCTIONS
# ═══════════════════════════════════════════════════════════════


def calculate_intensity_score(value, ref_value, min_scale=0.5, max_scale=1.5):
    """Calculate intensity score based on reference value"""
    intensity = value / ref_value
    if intensity < min_scale:
        return 100 * (1 - (min_scale - intensity) / min_scale)
    elif intensity > max_scale:
        return 100 * (1 - (intensity - max_scale) / max_scale)
    else:
        return 100


def calculate_material_score_integrated(material_data):
    """Integrated material score with recycling bonuses"""
    concrete_intensity = material_data['concrete_intensity']
    steel_intensity = material_data['steel_intensity']
    aluminum_intensity = material_data['aluminum_intensity']
    wood_intensity = material_data['wood_intensity']
    frp_intensity = material_data['frp_intensity']
    glass_intensity = material_data['glass_intensity']

    steel_recycle_bonus = material_data['steel_recycle_rate'] / 100.0 * 0.05
    aluminum_recycle_bonus = material_data['aluminum_recycle_rate'] / 100.0 * 0.05
    recycling_bonus = steel_recycle_bonus + aluminum_recycle_bonus

    base_material_score = (
        0.30 * concrete_intensity +
        0.30 * steel_intensity +
        0.20 * aluminum_intensity +
        0.10 * wood_intensity +
        0.05 * frp_intensity +
        0.05 * glass_intensity
    )

    material_score = min(100.0, base_material_score * (1.0 + recycling_bonus))
    return material_score


def calculate_environmental_display_score(env_data):
    """Heuristic environmental display score (not ISO LCA result)."""
    operational_co2 = env_data['operational_co2']
    embodied_co2 = env_data['embodied_co2']
    renewable_share = env_data['renewable_share']
    noise_reduction = env_data['noise_reduction']
    land_efficiency = env_data['land_efficiency']

    renewable_mitigation_factor = 1.0 - (renewable_share / 100.0) * 0.40
    adjusted_operational_co2 = operational_co2 * renewable_mitigation_factor

    land_efficiency_bonus = (land_efficiency / 5000.0) * 0.15
    land_efficiency_bonus = np.clip(land_efficiency_bonus, 0, 0.15)
    adjusted_embodied_co2 = embodied_co2 * (1.0 - land_efficiency_bonus)

    total_co2_adjusted = adjusted_operational_co2 + adjusted_embodied_co2

    noise_quality_multiplier = 1.0 + (noise_reduction / 15.0) * 0.10
    noise_quality_multiplier = np.clip(noise_quality_multiplier, 1.0, 1.10)

    co2_normalized = (total_co2_adjusted - 5000.0) / (50000.0 - 5000.0)
    co2_normalized = np.clip(co2_normalized, 0, 1)
    co2_score = (1.0 - co2_normalized) * 100.0

    environmental_score = co2_score * noise_quality_multiplier
    environmental_score = np.clip(environmental_score, 0, 100)
    return float(environmental_score)


def calculate_operational_score_integrated(op_data):
    """Integrated operational score with internal coupling effects"""
    time_savings = op_data['time_savings']
    availability = op_data['availability']
    land_efficiency = op_data['land_efficiency']
    energy_efficiency = op_data['energy_per_pax_km']

    availability_factor = availability / 100.0
    effective_time_savings = time_savings * availability_factor
    time_score = min(100.0, (effective_time_savings / 2500.0) * 100.0)

    energy_bonus = (0.20 - energy_efficiency) / 0.20
    energy_bonus = np.clip(energy_bonus, 0, 1)

    adjusted_land_efficiency = land_efficiency * (1.0 + energy_bonus * 0.20)
    land_score = min(100.0, (adjusted_land_efficiency / 5000.0) * 100.0)

    synergy_multiplier = 1.0 + (availability_factor * float(energy_bonus) * 0.10)
    availability_score = availability * synergy_multiplier
    availability_score = min(100.0, availability_score)

    operational_score = (
        time_score * 0.40 +
        availability_score * 0.40 +
        land_score * 0.20
    )

    operational_score = np.clip(operational_score, 0, 100)
    return float(operational_score)


def calculate_economic_score_integrated(econ_data):
    """Heuristic economic display score using NPV-LCC-aware cost efficiency."""
    construction_cost = econ_data['construction_cost']
    npv_lcc_m = econ_data['npv_lcc_m']
    jobs_created = econ_data['jobs_created']
    economic_multiplier = econ_data['economic_multiplier']

    jobs_per_million = jobs_created / max(construction_cost, 1.0)
    job_efficiency_bonus = min(1.0, jobs_per_million / 2.0) * 0.15

    lcc_ratio = npv_lcc_m / max(construction_cost, 1.0)
    cost_efficiency_score = 100.0 / (1.0 + max(lcc_ratio - 1.0, 0.0))
    cost_efficiency_score = min(100.0, cost_efficiency_score * (1.0 + job_efficiency_bonus))

    total_economic_impact = jobs_created * economic_multiplier
    jobs_score = min(100.0, (total_economic_impact / 12000.0) * 100.0)

    multiplier_score = min(100.0, (economic_multiplier / 3.5) * 100.0)

    economic_score = (
        jobs_score * 0.50 +
        cost_efficiency_score * 0.30 +
        multiplier_score * 0.20
    )

    economic_score = np.clip(economic_score, 0, 100)
    return float(economic_score)


def calculate_cross_category_interactions(mat_score, env_score, op_score, econ_score):
    """Calculate cross-category interaction effects (synergies and trade-offs)"""
    mat_norm = mat_score / 100.0
    env_norm = env_score / 100.0
    op_norm = op_score / 100.0
    econ_norm = econ_score / 100.0

    # Heuristic interaction visualization only.
    # Coefficients are illustrative and are not validated causal effects.
    interaction_matrix = {
        'mat_to_env': -0.25,
        'env_to_op': 0.15,
        'op_to_econ': 0.30,
        'econ_to_mat': 0.20,
        'mat_to_op': 0.10,
        'env_to_econ': -0.15
    }

    interaction_effects = {
        'mat_env_effect': mat_norm * interaction_matrix['mat_to_env'] * 100,
        'env_op_effect': env_norm * interaction_matrix['env_to_op'] * 100,
        'op_econ_effect': op_norm * interaction_matrix['op_to_econ'] * 100,
        'econ_mat_effect': econ_norm * interaction_matrix['econ_to_mat'] * 100,
        'mat_op_effect': mat_norm * interaction_matrix['mat_to_op'] * 100,
        'env_econ_effect': env_norm * interaction_matrix['env_to_econ'] * 100
    }

    adjusted_material_score = mat_score + interaction_effects['econ_mat_effect']
    adjusted_environmental_score = env_score + interaction_effects['mat_env_effect']
    adjusted_operational_score = (op_score +
                                   interaction_effects['env_op_effect'] +
                                   interaction_effects['mat_op_effect'])
    adjusted_economic_score = (econ_score +
                                interaction_effects['op_econ_effect'] +
                                interaction_effects['env_econ_effect'])

    adjusted_material_score = float(np.clip(adjusted_material_score, 0, 100))
    adjusted_environmental_score = float(np.clip(adjusted_environmental_score, 0, 100))
    adjusted_operational_score = float(np.clip(adjusted_operational_score, 0, 100))
    adjusted_economic_score = float(np.clip(adjusted_economic_score, 0, 100))

    total_synergy = sum([abs(effect) for key, effect in interaction_effects.items() if effect > 0])
    total_tradeoff = sum([abs(effect) for key, effect in interaction_effects.items() if effect < 0])

    synergy_ratio = total_synergy / max(total_tradeoff, 0.01)

    return {
        'adjusted_material_score': adjusted_material_score,
        'adjusted_environmental_score': adjusted_environmental_score,
        'adjusted_operational_score': adjusted_operational_score,
        'adjusted_economic_score': adjusted_economic_score,
        'interaction_effects': interaction_effects,
        'total_synergy': total_synergy,
        'total_tradeoff': total_tradeoff,
        'synergy_ratio': synergy_ratio
    }










# ═══════════════════════════════════════════════════════════════
# PHASE 2 — SYSTEM DYNAMICS LAYER FOR B6 (asset condition -> energy)
# ───────────────────────────────────────────────────────────────
# SYMBOL TABLE (scenario-based; NOT validated unless calibrated)
#   t      operating year (annual step), 1..T
#   T      assessment lifetime (years) = ASSESSMENT_LIFETIME_YEARS
#   C_t    asset condition at START of year t (dimensionless 0..1) — STOCK
#   C0     initial condition (default 1.0)
#   DR_t   degradation outflow (condition/year)
#   MR_t   maintenance recovery inflow (condition/year)
#   delta  annual degradation coefficient (condition/year) — scenario
#   rho    maintenance recovery efficiency (condition/action) — scenario
#   m_t    maintenance action (0/1), 1 on maintenance years
#   tau    maintenance effect delay (years)
#   alpha  energy penalty coefficient for degradation (dimensionless) — sensitivity
#   EI0    base energy intensity (kWh/pkm) = params['energy_per_pax']
#   EI_t   dynamic energy intensity (kWh/pkm)
#   PKM_t  annual passenger-km
#   g      annual demand growth (fraction)
#   CI_t   grid carbon intensity (kgCO2/kWh) — NO renewable multiplier in Phase 2
#
# Stock-flow (continuous):   dC/dt = MR(t) - DR(t)
#   DR_t = min(delta, C_t/dt)        constant annual loss, capped so C >= 0
#   MR_t = rho * m_(t-tau)           delayed recovery, capped so C <= 1
# Euler annual step (dt=1), degradation applied BEFORE recovery.
# Coupling:  EI_t = EI0 * [1 + alpha*(1 - C_t)]  ->  dynamic B6 emissions.
# SD parameters are SCENARIO ASSUMPTIONS unless calibrated with inspection,
# maintenance, or measured operational-energy data. The model is NOT validated.
# ═══════════════════════════════════════════════════════════════





# ═══════════════════════════════════════════════════════════════
# PHASE 3 — MODULAR GROSS A1-C4 LCA (3A: A5 + full-LCA backbone)
# ───────────────────────────────────────────────────────────────
# SYMBOL TABLE (Phase 3)
#   I_A5      construction/installation emissions (tCO2e)
#   I_B2_B5   maintenance/repair/replacement/refurbishment (tCO2e) [Phase 3B]
#   I_C1_C4   end-of-life (tCO2e) [Phase 3C]
#   F_f,p     fuel of type f in stage p (L or kg);  EF_f fuel factor (kgCO2e/unit)
#   E_p       electricity in stage p (kWh);         CI_t grid carbon (kgCO2e/kWh)
#   M_j       mass of material j (kg);              EF_j material factor (kgCO2e/kg)
#   w_j       waste rate (waste / purchased, 0..1)
#   D_x       transport distance (km);              EF_tr transport factor (kgCO2e/ton-km)
#   gross A1-C4 = A1-A3 + A4 + A5 + B2-B5 + B6_active + C1-C4
#   GWP/pkm   uses GROSS (never net). Module D is reported SEPARATELY (supplementary).
# All Phase 3 factors/quantities are user inputs / scenario parameters (not validated).
# ═══════════════════════════════════════════════════════════════











# ═══════════════════════════════════════════════════════════════
# PHASE 3B — B2-B5 USE-STAGE (activity-based) + MASS BALANCE
# ───────────────────────────────────────────────────────────────
# SYMBOL TABLE (Phase 3B)
#   a        activity in {B2 maintenance, B3 repair, B4 replacement, B5 refurb}
#   n_(a,t)  count of activity a in year t
#   M_(j,a)  material j mass per activity (kg);  EF_j material factor
#   F_(f,a)  fuel per activity (L);              EF_f fuel factor
#   E_a      electricity per activity (kWh);     CI_t grid carbon
#   A_(j,t)  material added (replacement/refurb), kg/year
#   R_(j,t)  material removed (replacement/refurb), kg/year
#   M_remaining = M_initial + Σ A - Σ R   (feeds Phase 3C; removed NOT re-counted)
#   B2 schedule may be LINKED to the SD maintenance schedule (m_t) so that SD
#   condition recovery is never "free" — it incurs B2 activity emissions/cost.
# All quantities/factors are user inputs / scenario parameters (not validated).
# ═══════════════════════════════════════════════════════════════































def calculate_dashboard_display_scores(params, core):
    """DASHBOARD-ONLY — heuristic display scores and interaction visualization.
    NOT an ISO LCA/LCCA result and NOT a sustainability index. Do not publish
    these as scientific outputs; they exist purely for the interface."""
    # Heuristic material intensity scores (reference-based, not an LCA metric)
    material_data = {
        'concrete_intensity': calculate_intensity_score(core['concrete_volume'], REF_CONCRETE),
        'steel_intensity': calculate_intensity_score(core['steel_tons'], REF_STEEL),
        'aluminum_intensity': calculate_intensity_score(core['aluminum_tons'], REF_ALUMINUM),
        'wood_intensity': calculate_intensity_score(params['wood'] * 1000, REF_WOOD),
        'frp_intensity': calculate_intensity_score(core['frp_tons'], REF_FRP),
        'glass_intensity': calculate_intensity_score(params['glass'] * 1000, REF_GLASS),
        'steel_recycle_rate': params['steel_recycle'],
        'aluminum_recycle_rate': params['aluminum_recycle']
    }
    environmental_data = {
        'operational_co2': core['annual_co2_operational'],
        'embodied_co2': core['total_embodied_co2'],
        'renewable_share': core['renewable_share'],
        'noise_reduction': core['noise_reduction'],
        'land_efficiency': core['land_use_efficiency']
    }
    operational_data = {
        'time_savings': params['time_savings'] * 1000,
        'availability': params['availability'],
        'land_efficiency': core['land_use_efficiency'],
        'energy_per_pax_km': core['energy_per_pax_km']
    }
    economic_data = {
        'construction_cost': core['construction_cost'],
        'npv_lcc_m': core['npv_lcc_m'],
        'jobs_created': core['jobs_created'],
        'economic_multiplier': core['economic_multiplier']
    }

    material_score = calculate_material_score_integrated(material_data)
    environmental_score = calculate_environmental_display_score(environmental_data)
    operational_score = calculate_operational_score_integrated(operational_data)
    economic_score = calculate_economic_score_integrated(economic_data)

    interaction_results = calculate_cross_category_interactions(
        material_score, environmental_score, operational_score, economic_score
    )

    dashboard_display_score = float(np.clip(
        material_score * 0.25 + environmental_score * 0.30 +
        operational_score * 0.25 + economic_score * 0.20, 0, 100))

    return {
        'material_score': material_score,
        'environmental_score': environmental_score,
        'operational_score': operational_score,
        'economic_score': economic_score,
        'adjusted_material_score': interaction_results['adjusted_material_score'],
        'adjusted_environmental_score': interaction_results['adjusted_environmental_score'],
        'adjusted_operational_score': interaction_results['adjusted_operational_score'],
        'adjusted_economic_score': interaction_results['adjusted_economic_score'],
        'interaction_effects': interaction_results['interaction_effects'],
        'total_synergy': interaction_results['total_synergy'],
        'total_tradeoff': interaction_results['total_tradeoff'],
        'synergy_ratio': interaction_results['synergy_ratio'],
        'dashboard_display_score': dashboard_display_score,
    }


def run_full_assessment(params):
    """Orchestrator: SCIENTIFIC CORE + DASHBOARD-ONLY, kept logically separate.
    Returns a merged dict for backward-compatible UI consumption."""
    core = calculate_legacy_dashboard_results(params)
    dashboard = calculate_dashboard_display_scores(params, core)
    return {**core, **dashboard}


# ═══════════════════════════════════════════════════════════════
# PHASE 4 — COMPONENT-BASED MONTE CARLO UNCERTAINTY PROPAGATION
# ───────────────────────────────────────────────────────────────
# A statistical layer ON TOP of the A1-C4 model. It does NOT change any LCA
# equation. Each uncertain input is sampled from its own distribution and the
# full model is re-run, so uncertainty propagates per component while the model
# identities hold in EVERY draw:
#   gross = A1-A3 + A4 + A5 + B2-B5 + B6 + C1-C4
#   net   = gross - Module D            (Module D never enters gross)
#   GWP/pkm = gross * 1000 / PKM        (uses GROSS, never net)
# NO total-scaling. NO SI / CRITIC-Entropy. Treatment shares are sampled jointly
# (Dirichlet) so reuse+recycle+disposal = 1 in every draw.
# ═══════════════════════════════════════════════════════════════

def _norm_ppf(p):
    """Inverse standard-normal CDF (Acklam), numpy-only, vectorised."""
    p = np.asarray(p, dtype=float)
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    p = np.clip(p, 1e-12, 1 - 1e-12)
    x = np.zeros_like(p)
    lo = p < plow; hi = p > phigh; mid = (~lo) & (~hi)
    if np.any(lo):
        q = np.sqrt(-2 * np.log(p[lo]))
        x[lo] = (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if np.any(hi):
        q = np.sqrt(-2 * np.log(1 - p[hi]))
        x[hi] = -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if np.any(mid):
        q = p[mid] - 0.5; r = q * q
        x[mid] = (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5]) * q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)
    return x


def lhs_unit_samples(n, k, seed=42):
    """Latin Hypercube unit samples in [0,1]^(n x k)."""
    rng = np.random.default_rng(seed)
    u = np.zeros((n, k))
    for j in range(k):
        u[:, j] = (rng.permutation(n) + rng.random(n)) / n
    return u


def sample_from_distribution(u, spec):
    """Transform uniform u -> distribution. Positive quantities are clipped >= 0."""
    base = spec['base_value']; cv = spec.get('cv', 0.0); dist = spec['distribution']
    lo = spec.get('min', None); hi = spec.get('max', None)
    if dist == 'fixed' or cv <= 0 or base == 0:
        x = np.full_like(np.asarray(u, dtype=float), base)
    elif dist == 'lognormal':
        sigma = np.sqrt(np.log(1 + cv * cv)); mu = np.log(abs(base)) - 0.5 * sigma * sigma
        x = np.sign(base) * np.exp(mu + sigma * _norm_ppf(u))
    elif dist == 'normal':
        x = base + (cv * base) * _norm_ppf(u)
    elif dist == 'triangular':
        spread = min(2.0 * cv, 0.95)
        a = base * (1 - spread); cc = base; bb = base * (1 + spread)
        u = np.asarray(u, dtype=float); x = np.empty_like(u)
        fc = (cc - a) / (bb - a) if bb > a else 0.0
        left = u <= fc
        x[left] = a + np.sqrt(u[left] * (bb - a) * (cc - a))
        x[~left] = bb - np.sqrt((1 - u[~left]) * (bb - a) * (bb - cc))
    else:
        x = np.full_like(np.asarray(u, dtype=float), base)
    if lo is not None and np.isfinite(lo):
        x = np.maximum(x, lo)
    if hi is not None and np.isfinite(hi):
        x = np.minimum(x, hi)
    return x


def build_uncertainty_registry(params, results):
    """One row per uncertain input. Stage tags, distributions, CVs, bounds, quality."""
    reg = []
    def add(parameter, stage, base, dist, cv, mn, mx, unit, quality, active=True, group=None):
        reg.append({'parameter': parameter, 'stage': stage, 'base_value': base,
                    'distribution': dist, 'cv': cv, 'min': mn, 'max': mx, 'unit': unit,
                    'source_quality': quality, 'active_when': bool(active), 'correlation_group': group})
    mats = ['concrete', 'steel', 'aluminum', 'wood', 'frp', 'glass']
    ef_cv = {'concrete': 0.10, 'steel': 0.08, 'aluminum': 0.12, 'wood': 0.15, 'frp': 0.30, 'glass': 0.12}
    for m in mats:
        add(f'unc_ef_mult_{m}', 'A1-A3', 1.0, 'lognormal', ef_cv[m], 0.0, None, 'multiplier', 'ICE/EPD', True, 'material_EF')
        add(m, 'A1-A3', params.get(m, 0.0), 'normal', 0.05, 0.0, None, 'BOQ unit', 'project/BOQ', True, 'material_qty')
    add('carbon_intensity', 'B6/electricity', params.get('carbon_intensity', 0.5), 'lognormal', 0.12, 0.0, None, 'kgCO2e/kWh', 'database', True, 'grid')
    add('energy_per_pax', 'B6', params.get('energy_per_pax', 0.15), 'lognormal', 0.15, 0.0, None, 'kWh/pkm', 'scenario', True, 'B6')
    add('transport_distance_km', 'A4', params.get('transport_distance_km', 0.0), 'triangular', 0.20, 0.0, None, 'km', 'scenario', True, 'A4')
    a5_on = bool(params.get('include_a5', False))
    add('a5_diesel_l', 'A5', params.get('a5_diesel_l', 0.0), 'lognormal', 0.20, 0.0, None, 'L', 'scenario', a5_on, 'A5')
    add('a5_elec_kwh', 'A5', params.get('a5_elec_kwh', 0.0), 'lognormal', 0.20, 0.0, None, 'kWh', 'scenario', a5_on, 'A5')
    add('a5_diesel_ef', 'A5', params.get('a5_diesel_ef', FUEL_FACTORS['diesel']['ef_kgco2e_per_l']), 'lognormal', 0.08, 0.0, None, 'kgCO2e/L', 'database', a5_on, 'fuel')
    b_on = bool(params.get('include_b2b5', False))
    add('b2_material_pct', 'B2-B5', params.get('b2_material_pct', 0.0), 'triangular', 0.25, 0.0, None, '% A1-A3', 'scenario', b_on, 'B2B5')
    add('b4_frac_steel', 'B2-B5', params.get('b4_frac_steel', 0.0), 'triangular', 0.25, 0.0, 1.0, 'fraction', 'scenario', b_on, 'B2B5')
    add('b4_frac_concrete', 'B2-B5', params.get('b4_frac_concrete', 0.0), 'triangular', 0.25, 0.0, 1.0, 'fraction', 'scenario', b_on, 'B2B5')
    c_on = bool(params.get('include_c1c4', False))
    add('c1_diesel_l', 'C1-C4', params.get('c1_diesel_l', 0.0), 'lognormal', 0.20, 0.0, None, 'L', 'scenario', c_on, 'C1C4')
    add('eol_transport_km', 'C1-C4', params.get('eol_transport_km', 50.0), 'triangular', 0.20, 0.0, None, 'km', 'scenario', c_on, 'C1C4')
    add('eol_recycle_ef', 'C1-C4', params.get('eol_recycle_ef', 0.0), 'lognormal', 0.20, 0.0, None, 'kgCO2e/kg', 'scenario', c_on, 'C1C4')
    add('eol_disposal_ef', 'C1-C4', params.get('eol_disposal_ef', 0.0), 'lognormal', 0.20, 0.0, None, 'kgCO2e/kg', 'scenario', c_on, 'C1C4')
    add('eol_recovery_eta', 'Module D', params.get('eol_recovery_eta', 1.0), 'triangular', 0.10, 0.0, 1.0, 'fraction', 'scenario', c_on, 'moduleD')
    add('construction_cost', 'LCCA', params.get('construction_cost', 0.0), 'lognormal', 0.10, 0.0, None, '$M', 'project', True, 'cost')
    add('maintenance_cost', 'LCCA', params.get('maintenance_cost', 0.0), 'lognormal', 0.15, 0.0, None, '$M/yr', 'scenario', True, 'cost')
    return pd.DataFrame(reg)


def sample_uncertain_parameters(registry, n, seed=42, params=None):
    """LHS-sample active scalar parameters; sample EOL treatment shares jointly (Dirichlet)."""
    active = registry[registry['active_when']].reset_index(drop=True)
    k = len(active)
    u = lhs_unit_samples(n, k, seed) if k else np.zeros((n, 0))
    cols = {}
    for j, row in active.iterrows():
        cols[row['parameter']] = sample_from_distribution(u[:, j], row.to_dict())
    samples = pd.DataFrame(cols)
    # Treatment shares via Dirichlet (preserves reuse+recycle+disposal = 1)
    if params is not None and params.get('include_c1c4', False):
        rng = np.random.default_rng(seed + 1)
        conc = 50.0
        for m in ['concrete', 'steel', 'aluminum', 'wood', 'frp', 'glass']:
            reuse0 = params.get(f'eol_reuse_{m}', 0.0); recycle0 = params.get(f'eol_recycle_{m}', 0.0)
            disp0 = max(1.0 - reuse0 - recycle0, 0.0)
            alpha = np.array([reuse0, recycle0, disp0]) * conc + 1e-3
            draw = rng.dirichlet(alpha, size=n)
            samples[f'eol_reuse_{m}'] = draw[:, 0]
            samples[f'eol_recycle_{m}'] = draw[:, 1]
    return samples


def apply_uncertainty_sample(base_params, sample_row):
    """Return a NEW params dict with sampled overrides (base_params untouched)."""
    p = dict(base_params)
    for kk, vv in sample_row.items():
        p[kk] = float(vv)
    return p


def run_component_monte_carlo(base_params, n=5000, seed=42):
    """Component-based propagation. Returns samples/outputs/summary/drivers/convergence/quality.

    UNCERTAINTY ORCHESTRATION: each sample is evaluated by
    `uncertainty_orchestrator.evaluate_sample()`, which re-runs the SEPARATED domain
    engines (LCA, then LCC from neutral activity, then Benefits) rather than one mixed
    engine. Sampling stays here; the per-sample evaluation crosses the same domain
    boundary as a normal run, so an emission factor still cannot move a cash flow.
    """
    baseline = evaluate_sample(base_params)
    registry = build_uncertainty_registry(base_params, baseline)
    samples = sample_uncertain_parameters(registry, n, seed, params=base_params)
    rows = []
    for i in range(n):
        sp = apply_uncertainty_sample(base_params, samples.iloc[i].to_dict())
        try:
            r = run_full_assessment(sp)
            gross = r['gross_a1_c4_tons']
            stage_sum = (r['total_embodied_co2'] + r['lca_results']['a4_transport_co2_tons']
                         + r['a5']['a5_total_tons'] + r['i_b2b5_tons'] + r['active_b6_tons'] + r['i_c1c4_tons'])
            failed = abs(stage_sum - gross) > 1e-6 or not np.isfinite(gross)
            rows.append({'run_id': i, 'A1_A3_tons': r['total_embodied_co2'],
                         'A4_tons': r['lca_results']['a4_transport_co2_tons'],
                         'A5_tons': r['a5']['a5_total_tons'], 'B2_B5_tons': r['i_b2b5_tons'],
                         'B6_tons': r['active_b6_tons'], 'C1_C4_tons': r['i_c1c4_tons'],
                         'gross_a1_c4_tons': gross, 'module_d_tons': r['module_d_tons'],
                         'net_with_module_d_tons': r['net_with_module_d_tons'],
                         'gwp_pkm_gross': r['gwp_pkm_gross'], 'npv_lcc_m': r['npv_lcc_m'],
                         'failed': bool(failed), 'failure_reason': 'identity' if failed else ''})
        except Exception as e:  # noqa
            rows.append({'run_id': i, 'A1_A3_tons': np.nan, 'A4_tons': np.nan, 'A5_tons': np.nan,
                         'B2_B5_tons': np.nan, 'B6_tons': np.nan, 'C1_C4_tons': np.nan,
                         'gross_a1_c4_tons': np.nan, 'module_d_tons': np.nan,
                         'net_with_module_d_tons': np.nan, 'gwp_pkm_gross': np.nan,
                         'npv_lcc_m': np.nan, 'failed': True, 'failure_reason': str(e)[:60]})
    outputs = pd.DataFrame(rows)
    summary = summarise_mc_outputs(outputs)
    drivers = compute_uncertainty_drivers(samples, outputs, 'gross_a1_c4_tons')
    convergence = compute_mc_convergence(outputs, 'gross_a1_c4_tons')
    quality = build_uncertainty_quality_table(registry)
    n_ok = int((~outputs['failed']).sum())
    registry_complete = len(registry[registry['active_when']]) > 0
    pgu = bool(baseline.get('publication_grade_full_lca', False) and registry_complete
               and n_ok >= 5000 and convergence['convergence_ok'])
    return {'samples': samples, 'outputs': outputs, 'summary': summary, 'drivers': drivers,
            'convergence': convergence, 'quality': quality, 'n': n, 'n_ok': n_ok,
            'component_mc_used': True, 'publication_grade_uncertainty': pgu, 'baseline': baseline}


def summarise_mc_outputs(outputs_df):
    """Per-output mean/median/std/CV and percentiles (P2.5..P97.5)."""
    cols = ['A1_A3_tons', 'A4_tons', 'A5_tons', 'B2_B5_tons', 'B6_tons', 'C1_C4_tons',
            'gross_a1_c4_tons', 'module_d_tons', 'net_with_module_d_tons', 'gwp_pkm_gross', 'npv_lcc_m']
    ok = outputs_df[~outputs_df['failed']]
    out = []
    for c in cols:
        v = ok[c].to_numpy(dtype=float); v = v[np.isfinite(v)]
        if v.size == 0:
            continue
        mean = float(np.mean(v))
        out.append({'metric': c, 'mean': mean, 'median': float(np.median(v)), 'std': float(np.std(v)),
                    'CV': float(np.std(v) / mean) if mean else np.nan,
                    'P2.5': float(np.percentile(v, 2.5)), 'P5': float(np.percentile(v, 5)),
                    'P50': float(np.percentile(v, 50)), 'P95': float(np.percentile(v, 95)),
                    'P97.5': float(np.percentile(v, 97.5)), 'min': float(v.min()), 'max': float(v.max())})
    return pd.DataFrame(out)


def _spearman(x, y):
    x = np.asarray(x, dtype=float); y = np.asarray(y, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = x[mask], y[mask]
    if x.size < 3 or np.all(x == x[0]):
        return 0.0
    rx = np.argsort(np.argsort(x)).astype(float); ry = np.argsort(np.argsort(y)).astype(float)
    rx -= rx.mean(); ry -= ry.mean()
    denom = np.sqrt((rx * rx).sum() * (ry * ry).sum())
    return float((rx * ry).sum() / denom) if denom > 0 else 0.0


def compute_uncertainty_drivers(samples_df, outputs_df, target='gross_a1_c4_tons'):
    """Spearman rank correlation of each sampled input with the target output (tornado)."""
    ok = ~outputs_df['failed'].to_numpy()
    y = outputs_df[target].to_numpy(dtype=float)
    rows = []
    for col in samples_df.columns:
        rho = _spearman(samples_df[col].to_numpy()[ok], y[ok])
        rows.append({'parameter': col, 'spearman_rho': rho, 'abs_rho': abs(rho),
                     'direction': 'increases' if rho > 0 else ('decreases' if rho < 0 else 'none')})
    return pd.DataFrame(rows).sort_values('abs_rho', ascending=False).reset_index(drop=True)


def compute_mc_convergence(outputs_df, target='gross_a1_c4_tons'):
    """Running mean / P95 / CV; convergence_ok if the last 20% move <1% (mean) and <2% (P95)."""
    ok = outputs_df[~outputs_df['failed']]
    v = ok[target].to_numpy(dtype=float); v = v[np.isfinite(v)]
    n = v.size
    run_mean = np.array([v[:i + 1].mean() for i in range(n)]) if n else np.array([])
    run_p95 = np.array([np.percentile(v[:i + 1], 95) for i in range(n)]) if n else np.array([])
    mean_stable = p95_stable = False
    if n >= 50:
        cut = int(0.8 * n)
        m_final = run_mean[-1]; p_final = run_p95[-1]
        mean_stable = abs(run_mean[cut:].max() - run_mean[cut:].min()) / abs(m_final) < 0.01 if m_final else False
        p95_stable = abs(run_p95[cut:].max() - run_p95[cut:].min()) / abs(p_final) < 0.02 if p_final else False
    return {'running_mean': run_mean, 'running_p95': run_p95,
            'mean_stable': bool(mean_stable), 'p95_stable': bool(p95_stable),
            'convergence_ok': bool(mean_stable and p95_stable)}


def build_uncertainty_quality_table(registry):
    act = registry[registry['active_when']].copy()
    return act[['parameter', 'stage', 'distribution', 'cv', 'source_quality', 'correlation_group']].reset_index(drop=True)


# ═══════════════════════════════════════════════════════════════
# PHASE 5 — SCIENTIFIC SUSTAINABILITY INDEX (hybrid CRITIC-Entropy)
# ───────────────────────────────────────────────────────────────
# A decision-support composite index over a scenario-year matrix. It does NOT
# replace the reported LCA/LCCA/uncertainty outputs and is NOT the legacy
# Dashboard Display Score. Indicators are NON-OVERLAPPING (no gross + its own
# sub-stages); net-with-Module-D is NEVER an environmental indicator (Module D
# enters only as a separate circularity ratio). Target-based normalization,
# hybrid weights w = λ·wE + (1-λ)·wC, additive hierarchical aggregation.
#   z_ij = f(x_ij) ∈ [0,1];  SI_i = Σ_g W_g Σ_{j∈g} (w_j|g) z_ij ∈ [0,1]
# ═══════════════════════════════════════════════════════════════

def build_indicator_metadata():
    """One row per indicator: pillar, direction, target/worst, group, include flag."""
    rows = [
        # Environmental
        ('gwp_pkm_gross', 'Environmental', 'lower', 'kgCO2e/pkm', 0.05, 0.20, 'model', True, 'carbon_primary'),
        ('energy_per_pax_km', 'Environmental', 'lower', 'kWh/pkm', 0.05, 0.20, 'model', True, 'energy'),
        ('module_d_recovery_ratio', 'Environmental', 'higher', 'ratio', 0.30, 0.0, 'model (circularity)', True, 'circularity'),
        ('gross_uncertainty_CV', 'Environmental', 'lower', 'CV', 0.05, 0.30, 'Phase 4 MC', True, 'robustness'),
        # Economic
        ('npv_lcc_per_pkm', 'Economic', 'lower', '$/pkm', 0.05, 0.50, 'model', True, 'cost'),
        ('jobs_per_million_usd', 'Economic', 'higher', 'jobs/$M', 3.0, 0.0, 'model', True, 'econ_benefit'),
        ('lcca_uncertainty_CV', 'Economic', 'lower', 'CV', 0.05, 0.30, 'Phase 4 MC', True, 'cost_robustness'),
        # Operational
        ('availability', 'Operational', 'higher', 'fraction', 0.99, 0.85, 'input', True, 'operational'),
        # R23/R13: operational/land/social SI indicators now read the computed Benefit-KPI
        # module (not legacy manual inputs). Land is expressed as ha per million pkm (lower better).
        ('time_savings', 'Operational', 'higher', '1000h', 5.0, 0.0, 'Benefit KPI', True, 'operational_time'),
        ('land_ha_per_mpkm', 'Operational', 'lower', 'ha/Mpkm', 0.5, 5.0, 'Benefit KPI', True, 'land'),
        # Social / urban
        ('noise_reduction', 'Social', 'higher', 'dB', 15.0, 0.0, 'Benefit KPI', True, 'social'),
    ]
    return pd.DataFrame(rows, columns=['indicator', 'pillar', 'direction', 'unit', 'target',
                                       'worst', 'source', 'include_in_si', 'double_count_group'])


def _scenario_indicator_row(params, uncertainty_n=0, seed=42):
    r = run_full_assessment(params)
    pkm = r['active_total_pkm'] if r['active_total_pkm'] > 0 else np.nan
    row = {
        'gwp_pkm_gross': r['gwp_pkm_gross'],
        'energy_per_pax_km': r['energy_per_pax_km'],
        'module_d_recovery_ratio': (r['module_d_tons'] / r['gross_a1_c4_tons']) if r['gross_a1_c4_tons'] else 0.0,
        'npv_lcc_per_pkm': (r['npv_lcc_m'] * 1e6 / pkm) if pkm and np.isfinite(pkm) else np.nan,
        # R23/R13: jobs / time / land / noise come from the computed Benefit-KPI module.
        'jobs_per_million_usd': (r['benefit_kpis']['total_jobs'] / r['construction_cost']) if r['construction_cost'] else 0.0,
        'availability': params.get('availability', 0.0) / 100.0,
        'time_savings': r['benefit_kpis']['annual_hours_saved'] / 1000.0,
        'land_ha_per_mpkm': r['benefit_kpis']['land_ha_per_million_pkm'],
        'noise_reduction': r['benefit_kpis']['noise_reduction_db'],
        'gross_uncertainty_CV': np.nan,
        'lcca_uncertainty_CV': np.nan,
        'publication_grade_full_lca': r.get('publication_grade_full_lca', False),
    }
    if uncertainty_n and uncertainty_n > 0:
        mc = run_component_monte_carlo(params, n=int(uncertainty_n), seed=seed)
        sm = mc['summary'].set_index('metric')
        if 'gross_a1_c4_tons' in sm.index:
            row['gross_uncertainty_CV'] = float(sm.loc['gross_a1_c4_tons', 'CV'])
        if 'npv_lcc_m' in sm.index:
            row['lcca_uncertainty_CV'] = float(sm.loc['npv_lcc_m', 'CV'])
    return row


def generate_default_scenarios(base_params, n=36, seed=42):
    """LHS-spread scenario-year set (deterministic) for the SI matrix."""
    ranges = {'carbon_intensity': (0.2, 0.7), 'energy_per_pax': (0.08, 0.20),
              'daily_pax_km': (300.0, 800.0), 'maintenance_cost': (20.0, 100.0),
              'construction_cost': (1500.0, 3500.0), 'availability': (88.0, 99.0),
              'land_use': (2000.0, 6000.0), 'noise_reduction': (5.0, 15.0),
              'jobs_created': (3000.0, 8000.0)}
    keys = list(ranges.keys())
    u = lhs_unit_samples(n, len(keys), seed)
    scenarios = []
    for i in range(n):
        ov = {}
        for j, k in enumerate(keys):
            lo, hi = ranges[k]
            ov[k] = lo + u[i, j] * (hi - lo)
        scenarios.append({'scenario_id': f'S{i+1:02d}', 'year': 2030 + 10 * (i % 2),
                          'description': f'LHS scenario {i+1}', 'overrides': ov})
    return scenarios


def build_scenario_year_matrix(scenarios, base_params, uncertainty_n=0, seed=42):
    """One row per scenario: id/year + indicator raw values + flags."""
    rows = []
    for sc in scenarios:
        p = dict(base_params); p.update(sc.get('overrides', {}))
        ind = _scenario_indicator_row(p, uncertainty_n=uncertainty_n, seed=seed)
        ind.update({'scenario_id': sc['scenario_id'], 'year': sc.get('year', 0),
                    'description': sc.get('description', '')})
        rows.append(ind)
    cols = ['scenario_id', 'year', 'description']
    df = pd.DataFrame(rows)
    return df[cols + [c for c in df.columns if c not in cols]]


def validate_indicator_matrix(meta, raw_df):
    """Direction/target presence, double-counting, net-as-environmental, data availability."""
    errors, warnings, valid = [], [], True
    for _, m in meta.iterrows():
        if m['direction'] not in ('higher', 'lower'):
            valid = False; errors.append(f"{m['indicator']}: missing/invalid direction")
        if pd.isna(m['target']) or pd.isna(m['worst']):
            valid = False; errors.append(f"{m['indicator']}: missing target/worst")
    # No gross + its own sub-stages in the SI indicator set
    names = set(meta['indicator'])
    substages = {'A1_A3_tons', 'A4_tons', 'A5_tons', 'B2_B5_tons', 'B6_tons', 'C1_C4_tons'}
    if 'gross_a1_c4_tons' in names and (names & substages):
        valid = False; errors.append("double counting: gross + its sub-stages in SI")
    if 'net_with_module_d_tons' in names:
        valid = False; errors.append("net_with_module_d must not be an SI environmental indicator")
    # Availability of data
    for _, m in meta[meta['include_in_si']].iterrows():
        ind = m['indicator']
        if ind not in raw_df.columns or raw_df[ind].isna().all():
            warnings.append(f"{ind}: no data → excluded from SI")
    return {'valid': valid, 'errors': errors, 'warnings': warnings}


def _active_indicators(meta, raw_df):
    act = []
    for _, m in meta[meta['include_in_si']].iterrows():
        ind = m['indicator']
        if ind in raw_df.columns and not raw_df[ind].isna().all():
            act.append(m['indicator'])
    return meta[meta['indicator'].isin(act)].reset_index(drop=True)


def normalize_indicators_target_based(raw_df, meta):
    """z ∈ [0,1] via target-based functions (clipped)."""
    Z = pd.DataFrame(index=raw_df.index)
    for _, m in meta.iterrows():
        ind = m['indicator']; x = raw_df[ind].astype(float)
        T, W = float(m['target']), float(m['worst'])
        if m['direction'] == 'higher':
            z = (x - W) / (T - W) if T != W else 0.0 * x
        else:
            z = (W - x) / (W - T) if W != T else 0.0 * x
        Z[ind] = np.clip(z, 0.0, 1.0)
    return Z


def compute_entropy_weights(Z):
    A = Z.to_numpy(dtype=float); n = A.shape[0]; eps = 1e-12
    P = (A + eps) / (A + eps).sum(axis=0, keepdims=True)
    e = -(P * np.log(P)).sum(axis=0) / np.log(n) if n > 1 else np.zeros(A.shape[1])
    d = 1.0 - e
    w = d / d.sum() if d.sum() > 0 else np.full(A.shape[1], 1.0 / A.shape[1])
    return pd.Series(w, index=Z.columns)


def compute_critic_weights(Z, method='pearson'):
    A = Z.to_numpy(dtype=float); m = A.shape[1]
    sigma = A.std(axis=0, ddof=0)
    if method == 'spearman':
        A2 = np.apply_along_axis(lambda c: np.argsort(np.argsort(c)).astype(float), 0, A)
    else:
        A2 = A
    with np.errstate(invalid='ignore', divide='ignore'):
        R = np.corrcoef(A2, rowvar=False)
    R = np.atleast_2d(R)
    R = np.nan_to_num(R, nan=0.0)
    np.fill_diagonal(R, 1.0)
    C = sigma * (1.0 - R).sum(axis=1)
    w = C / C.sum() if C.sum() > 0 else np.full(m, 1.0 / m)
    return pd.Series(w, index=Z.columns)


def combine_entropy_critic_weights(wE, wC, lam=0.5):
    w = lam * wE + (1.0 - lam) * wC
    w = w / w.sum() if w.sum() > 0 else wE
    return w


def compute_pillar_scores(Z, meta, weights, pillar_weights):
    """Within-pillar weights = w_j / Σ_{j∈g} w_j; pillar score S_{i,g} = Σ w_(j|g) z_ij."""
    pillars = list(pillar_weights.keys())
    S = pd.DataFrame(index=Z.index)
    for g in pillars:
        inds = meta[meta['pillar'] == g]['indicator'].tolist()
        inds = [i for i in inds if i in Z.columns]
        if not inds:
            S[g] = 0.0; continue
        wg = weights[inds]
        wg = wg / wg.sum() if wg.sum() > 0 else pd.Series(1.0 / len(inds), index=inds)
        S[g] = (Z[inds] * wg).sum(axis=1)
    return S


def compute_sustainability_index(Z, meta, weights, pillar_weights):
    pw = pd.Series(pillar_weights, dtype=float)
    pw = pw / pw.sum() if pw.sum() > 0 else pw
    S = compute_pillar_scores(Z, meta, weights, pw.to_dict())
    present = [g for g in pw.index if g in S.columns]
    pwp = pw[present] / pw[present].sum()
    si = (S[present] * pwp).sum(axis=1)
    si = np.clip(si, 0.0, 1.0)
    flat = (Z[weights.index] * weights).sum(axis=1)
    return pd.DataFrame({'SI': si, 'SI_100': si * 100.0, 'SI_flat': np.clip(flat, 0, 1)}), S


def rank_scenarios_by_si(raw_df, si_df):
    out = pd.concat([raw_df[['scenario_id', 'year', 'description']].reset_index(drop=True),
                     si_df.reset_index(drop=True)], axis=1)
    out = out.sort_values('SI', ascending=False).reset_index(drop=True)
    out.insert(0, 'rank', np.arange(1, len(out) + 1))
    return out


def run_si_lambda_sensitivity(Z, meta, wE, wC, pillar_weights, lambdas=(0.0, 0.25, 0.5, 0.75, 1.0)):
    rankings = {}
    si_by_lambda = {}
    for lam in lambdas:
        w = combine_entropy_critic_weights(wE, wC, lam)
        si_df, _ = compute_sustainability_index(Z, meta, w, pillar_weights)
        si_by_lambda[lam] = si_df['SI'].to_numpy()
        rankings[lam] = np.argsort(np.argsort(-si_df['SI'].to_numpy()))
    # rank stability = Spearman between λ=0 and λ=1 SI
    keys = list(si_by_lambda.keys())
    stability = _spearman(si_by_lambda[keys[0]], si_by_lambda[keys[-1]])
    tab = pd.DataFrame({f'SI(λ={lam})': si_by_lambda[lam] for lam in lambdas})
    return {'table': tab, 'rank_stability_spearman': stability, 'rankings': rankings}


def build_si_audit_table(meta, active_meta, validation, weights):
    rows = []
    for _, m in meta.iterrows():
        ind = m['indicator']
        included = ind in set(active_meta['indicator'])
        rows.append({'indicator': ind, 'pillar': m['pillar'], 'direction': m['direction'],
                     'target': m['target'], 'worst': m['worst'], 'group': m['double_count_group'],
                     'included': included, 'weight': float(weights.get(ind, 0.0)),
                     'target_source': m['source']})
    return pd.DataFrame(rows)


def run_phase5_si(scenarios, base_params, lam=0.5, pillar_weights=None, critic_method='pearson',
                  uncertainty_n=0, publication_grade_uncertainty=False, seed=42,
                  scenario_source='generated_demo', uploaded_matrix=None):
    if pillar_weights is None:
        pillar_weights = {'Environmental': 0.35, 'Economic': 0.25, 'Operational': 0.25, 'Social': 0.15}
    warnings = []
    meta = build_indicator_metadata()
    if uploaded_matrix is not None and len(uploaded_matrix) > 0:
        raw = uploaded_matrix.copy()
        scenario_source = 'uploaded'
    else:
        raw = build_scenario_year_matrix(scenarios, base_params, uncertainty_n=uncertainty_n, seed=seed)
    validation = validate_indicator_matrix(meta, raw)
    warnings += validation['warnings']
    active = _active_indicators(meta, raw)
    Z = normalize_indicators_target_based(raw, active)
    wE = compute_entropy_weights(Z)
    wC = compute_critic_weights(Z, method=critic_method)
    weights = combine_entropy_critic_weights(wE, wC, lam)
    si_df, pillar_df = compute_sustainability_index(Z, active, weights, pillar_weights)
    ranked = rank_scenarios_by_si(raw, si_df)
    lambda_sens = run_si_lambda_sensitivity(Z, active, wE, wC, pillar_weights)
    audit = build_si_audit_table(meta, active, validation, weights)
    n_scen = len(raw)
    base_full = run_full_assessment(base_params).get('publication_grade_full_lca', False)
    pw_sum_ok = abs(sum(pillar_weights.values()) - 1.0) < 1e-9
    w_sum_ok = abs(float(weights.sum()) - 1.0) < 1e-9
    # Synthetic LHS demo scenarios are NOT acceptable for publication: require a
    # documented or uploaded scenario-year matrix.
    source_ok = scenario_source in ('documented', 'uploaded')
    if not source_ok:
        warnings.append("Scenario source is 'generated_demo' (synthetic LHS) → publication_grade_si = False. "
                        "Upload or document a scenario-year matrix for publication.")
    pgs = bool(base_full and publication_grade_uncertainty and n_scen >= 30 and validation['valid']
               and pw_sum_ok and w_sum_ok and len(active) >= 3 and source_ok)
    weights_df = pd.DataFrame({'indicator': weights.index, 'entropy': wE.values,
                               'critic': wC.values, 'hybrid': weights.values})
    return {'raw_matrix': raw, 'normalized_matrix': Z, 'indicator_metadata': meta,
            'active_indicators': active, 'entropy_weights': wE, 'critic_weights': wC,
            'combined_weights': weights, 'weights_table': weights_df, 'pillar_scores': pillar_df,
            'si_scores': si_df, 'ranked_scenarios': ranked, 'lambda_sensitivity': lambda_sens,
            'audit': audit, 'validation': validation, 'n_scenarios': n_scen,
            'pillar_weights': pillar_weights, 'lambda': lam, 'scenario_source': scenario_source,
            'publication_grade_si': pgs, 'warnings': warnings}


# ═══════════════════════════════════════════════════════════════
# CUSTOM CSS STYLING
# ═══════════════════════════════════════════════════════════════
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    .stApp {
        font-family: 'Inter', sans-serif;
    }

    .main-header {
        background: linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%);
        padding: 2rem 2.5rem;
        border-radius: 16px;
        margin-bottom: 1.5rem;
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
    }
    .main-header h1 {
        color: #ffffff;
        font-size: 2rem;
        font-weight: 800;
        margin: 0;
        letter-spacing: -0.5px;
    }
    .main-header p {
        color: #a8d8ea;
        font-size: 1rem;
        margin: 0.3rem 0 0 0;
        font-weight: 400;
    }

    .metric-card {
        background: linear-gradient(145deg, #1a1a2e 0%, #16213e 100%);
        border: 1px solid rgba(100, 200, 255, 0.15);
        border-radius: 14px;
        padding: 1.5rem;
        text-align: center;
        box-shadow: 0 4px 20px rgba(0,0,0,0.2);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 30px rgba(0,0,0,0.3);
    }
    .metric-card .metric-value {
        font-size: 2rem;
        font-weight: 800;
        background: linear-gradient(135deg, #00d2ff, #3a7bd5);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
    }
    .metric-card .metric-label {
        color: #8892b0;
        font-size: 0.85rem;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-top: 0.3rem;
    }
    .metric-card .metric-delta {
        color: #64ffda;
        font-size: 0.8rem;
        margin-top: 0.2rem;
    }

    .score-badge {
        display: inline-block;
        padding: 0.4rem 1.2rem;
        border-radius: 20px;
        font-weight: 700;
        font-size: 0.9rem;
    }
    .score-excellent { background: linear-gradient(135deg, #00b09b, #96c93d); color: white; }
    .score-good { background: linear-gradient(135deg, #f7971e, #ffd200); color: #1a1a2e; }
    .score-poor { background: linear-gradient(135deg, #eb3349, #f45c43); color: white; }

    .interaction-synergy { color: #64ffda; font-weight: 600; }
    .interaction-tradeoff { color: #ff6b6b; font-weight: 600; }

    .info-box {
        background: rgba(100, 255, 218, 0.05);
        border-left: 4px solid #64ffda;
        border-radius: 0 8px 8px 0;
        padding: 1rem 1.5rem;
        margin: 0.5rem 0;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        background-color: #0a192f;
        border-radius: 12px;
        padding: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: transparent;
        border-radius: 8px;
        color: #8892b0;
        font-weight: 500;
        padding: 8px 16px;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #233554, #1a365d) !important;
        color: #64ffda !important;
    }

    div[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0a192f 0%, #112240 100%);
    }
    div[data-testid="stSidebar"] .stMarkdown h1,
    div[data-testid="stSidebar"] .stMarkdown h2,
    div[data-testid="stSidebar"] .stMarkdown h3 {
        color: #ccd6f6;
    }

    .report-box {
        background: #0a192f;
        border: 1px solid #233554;
        border-radius: 12px;
        padding: 1.5rem;
        font-family: 'Consolas', 'Courier New', monospace;
        font-size: 0.85rem;
        color: #a8b2d1;
        white-space: pre-wrap;
        max-height: 600px;
        overflow-y: auto;
    }
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# HEADER
# ═══════════════════════════════════════════════════════════════
st.markdown("""
<div class="main-header">
    <h1>🚝 Enhanced Monorail LCA/LCCA Assessment Tool</h1>
    <p>Gross modular A1-C4 LCA + NPV-based LCCA Framework | ISO 14040/14044 + ASTM E917 | Cairo University</p>
</div>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# SIDEBAR - INPUT PARAMETERS (WRAPPED IN FORM TO MIMIC TKINTER RUN)
# ═══════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## ⚙️ Controls")
    publication_mode = st.checkbox("📑 Publication mode", value=True, key="publication_mode",
                                   help="Shows only the scientific tabs (LCA/LCCA/Uncertainty/SI/Benchmark/Methodology). "
                                        "Turn off (Developer mode) to also see illustrative/legacy visualizations.")

    # ── Reactive module toggles (OUTSIDE the form → conditional visibility) ──
    st.markdown("#### 🧩 Optional lifecycle modules")
    include_a5 = st.checkbox("A5 Construction", value=False, key="include_a5")
    sd_enable = st.checkbox("Dynamic B6 (System Dynamics)", value=False, key="sd_enable")
    include_b2b5 = st.checkbox("B2–B5 Maintenance & Replacement", value=False, key="include_b2b5")
    enable_b4 = st.checkbox("↳ B4 Replacement", value=False, key="enable_b4") if include_b2b5 else False
    include_c1c4 = st.checkbox("C1–C4 End-of-Life", value=False, key="include_c1c4")
    # Legacy generic recycling sliders + renewable dashboard-only are DEVELOPER-ONLY (R2/R7):
    # never shown in publication mode. A1-A3 recycled content comes from the material factor
    # mix; Module D comes from C1-C4 EOL flows only.
    show_legacy = (not publication_mode) and st.checkbox(
        "Legacy options (developer)", value=False, key="show_legacy",
        help="Legacy generic Module-D recycling scenario + renewable dashboard-only input. "
             "Hidden in publication mode by design.")

    MATERIALS_UI = ['concrete', 'steel', 'aluminum', 'wood', 'frp', 'glass']

    with st.form("assessment_form"):
        run_btn = st.form_submit_button("🚀 Run Assessment", type="primary", use_container_width=True)

        # ── R21: Project Definition (scope/metadata for the assessment & report) ──
        st.markdown("### 🧾 Project Definition")
        st.info("Sidebar follows EN 15804 lifecycle order: A1-A3 → A4 → A5 → B6 → B2-B5 → C1-C4 → Module D.")
        project_name = st.text_input("Project name", value="Cairo Monorail", key="project_name")
        route_length_km = st.number_input("Route length (km)", value=96.0, min_value=0.0, step=1.0, key="route_length")
        # P3: lifetime is shown as a fixed value (not an editable operational input) to avoid the
        # misleading case where a user enters a different life that the equations do not yet use.
        # Configurable lifetime is wired in the equations-review phase.
        assessment_lifetime = int(ASSESSMENT_LIFETIME_YEARS)
        st.caption(f"Assessment lifetime: **{assessment_lifetime} years** (fixed; configurable lifetime "
                   "is wired in the equations phase).")
        analysis_start_year = st.number_input("Analysis start year", value=2026, min_value=2000, step=1, key="start_year")
        currency = st.selectbox("Currency", ["USD", "EGP"], index=0, key="currency")
        price_year = st.number_input("Price year", value=2026, min_value=2000, step=1, key="price_year")
        functional_unit = "1 passenger-km"

        st.markdown("### 📦 Materials")
        concrete = st.number_input("Concrete (1000 m³)", value=700.0, min_value=0.0, step=10.0, key="concrete")
        steel = st.number_input("Steel (1000 tons)", value=100.0, min_value=0.0, step=5.0, key="steel")
        aluminum = st.number_input("Aluminum (1000 tons)", value=5.0, min_value=0.0, step=0.5, key="aluminum")
        wood = st.number_input("Wood (1000 m³)", value=2.0, min_value=0.0, step=0.5, key="wood")
        frp = st.number_input("FRP (1000 tons)", value=0.0, min_value=0.0, step=0.1, key="frp",
                              help="FRP/GRP has NO verified ICE V4.1 A1-A3 factor. Keep 0 for publication-grade unless a product EPD is supplied.")
        glass = st.number_input("Glass (1000 m²)", value=0.5, min_value=0.0, step=0.1, key="glass")
        glass_thickness_mm = st.number_input("Glass thickness (mm)", value=12.0, min_value=1.0, step=1.0, key="glass_thickness",
                                             help="Glass mass = area × thickness × 2.5 kg/(mm·m²).")

        # R6 recycled content → effective A1-A3 EF (EN 15804). Takes effect ONLY when a
        # material has BOTH a recycled-content fraction > 0 AND a documented secondary EF.
        # Otherwise the virgin ICE V4.1 factor is used and the EOL benefit stays in Module D.
        recycled_content_inputs, ef_secondary_inputs = {}, {}
        ef_secondary_sources, ef_secondary_basis = {}, {}
        recycled_secondary_documented_ok = True
        # Publication mode: the scientific engine governs A1-A3 via documented EPD/factor
        # overrides — the legacy generic recycled-content EF is hidden to avoid a second,
        # non-authoritative A1-A3 path. Defaults (RC=0, no secondary EF) keep params valid.
        if publication_mode:
            for _m in MATERIALS_UI:
                recycled_content_inputs[_m] = 0.0
                ef_secondary_inputs[_m] = None
                ef_secondary_sources[_m] = ""
                ef_secondary_basis[_m] = "virgin"
        else:
          with st.expander("♻️ Recycled content (effective A1-A3 EF — EN 15804)", expanded=False):
            st.caption("EF_eff = (1−RC)·EF_virgin + RC·EF_secondary. Applied per material only when "
                       "BOTH a recycled-content % AND a *documented* secondary EF (with a source) are given; "
                       "an undocumented secondary EF is ignored (virgin factor kept) and the result is flagged "
                       "not publication-grade. The end-of-life recovery benefit stays in Module D — no double counting.")
            for _m in MATERIALS_UI:
                rc_pct = st.number_input(f"{_m.capitalize()} recycled content (%)", value=0.0,
                                         min_value=0.0, max_value=100.0, step=5.0, key=f"rc_{_m}")
                sec_ef = st.number_input(f"{_m.capitalize()} secondary EF (kgCO₂e/kg, 0 = none)",
                                         value=0.0, min_value=0.0, step=0.01, format="%.4f", key=f"secef_{_m}")
                sec_src = st.text_input(f"{_m.capitalize()} secondary EF source (EPD/DB, year, boundary)",
                                        value="", key=f"secsrc_{_m}")
                sec_basis = st.selectbox(f"{_m.capitalize()} factor basis", ["virgin", "market-average"],
                                         index=0, key=f"secbasis_{_m}")
                recycled_content_inputs[_m] = rc_pct / 100.0
                ef_secondary_sources[_m] = sec_src.strip()
                ef_secondary_basis[_m] = sec_basis
                documented = (sec_ef > 0.0) and bool(sec_src.strip())
                # R27: only a documented secondary EF is allowed to drive the A1-A3 substitution.
                ef_secondary_inputs[_m] = sec_ef if documented else None
                if sec_ef > 0.0 and not sec_src.strip():
                    recycled_secondary_documented_ok = False
            if not recycled_secondary_documented_ok:
                st.warning("A secondary EF was entered without a source → it is NOT applied and the A1-A3 "
                           "recycled-content result is not publication-grade until a source is provided.")

        with st.expander("🔍 A1-A3 factor audit (ICE V4.1 traceability)", expanded=False):
            st.dataframe(MATERIAL_FACTOR_AUDIT[['material', 'gwp_kgco2e_per_kg',
                         'ee_mj_per_kg (legacy)', 'carbon_source', 'status']], use_container_width=True)
            st.caption("Each A1-A3 factor is traced to the ICE Database Educational V4.1 (Oct 2025). "
                       "FRP has NO verified ICE V4.1 value — keep qty = 0 or supply a product EPD.")

        st.markdown("### 🚚 Transport (A4)")
        a4_mode = st.selectbox("A4 method", ["simple", "advanced"], index=0, key="a4_mode",
                               help="simple: total mass × distance × mode EF. "
                                    "advanced: per-material legs (mass, distance, mode, optional documented EF).")
        transport_distance_km = st.number_input("Transport distance (km)", value=50.0, min_value=0.0, step=10.0, key="transport_distance")
        transport_mode = st.selectbox("Transport mode", ["truck", "rail", "ship"], index=0, key="transport_mode")
        a4_advanced_legs = None
        if a4_mode == "advanced":
            st.caption("↑ Distance and mode above are **default values for table prefill only**; "
                       "edit each row in the table below.")
            _pref_t = {
                'concrete': concrete * DENSITIES['concrete'], 'steel': steel * 1000.0,
                'aluminum': aluminum * 1000.0, 'wood': wood * DENSITIES['wood'],
                'frp': frp * 1000.0, 'glass': glass * glass_thickness_mm * 2.5,
            }
            a4_df0 = pd.DataFrame({
                'material': MATERIALS_UI,
                'route_id': ['1'] * len(MATERIALS_UI),
                'route_share': [1.0] * len(MATERIALS_UI),
                'segment_no': [1] * len(MATERIALS_UI),
                'mode': [transport_mode] * len(MATERIALS_UI),
                'distance_km': [transport_distance_km] * len(MATERIALS_UI),
                'distance_source': [''] * len(MATERIALS_UI),
                'mass_tonnes_legacy': [round(_pref_t[m], 3) for m in MATERIALS_UI],
                'ef_override_legacy': [0.0] * len(MATERIALS_UI),
            })
            # Route/segment model: a material's transport splits across ROUTES (route_share
            # per material must sum to 1). A route can have several SEQUENTIAL SEGMENTS
            # (e.g. ship then truck) that all carry the SAME route mass — segments are not a
            # mass split. Scientific leg mass = A1-A3 mass × route_share. mass_tonnes_legacy /
            # ef_override_legacy feed ONLY the legacy engine and are ignored by the referenced core.
            a4_edit = st.data_editor(a4_df0, hide_index=True, use_container_width=True, key="a4_editor",
                                     num_rows="dynamic",
                                     disabled=['mass_tonnes_legacy'])
            a4_advanced_legs = []
            for _, _r in pd.DataFrame(a4_edit).iterrows():
                _ef = float(_r['ef_override_legacy'])
                a4_advanced_legs.append({
                    'material': _r['material'],
                    'route_id': str(_r['route_id']),
                    'route_share': float(_r['route_share']),
                    'segment_no': int(_r['segment_no']),
                    'distance_source': str(_r['distance_source']),
                    'mass_kg': float(_r['mass_tonnes_legacy']) * 1000.0,  # legacy engine only
                    'distance_km': float(_r['distance_km']), 'mode': _r['mode'],
                    'ef': (_ef if _ef > 0.0 else None)})  # legacy engine only
            st.caption("Advanced A4 (route/segment): **route_share** = fraction of this material's sourced "
                       "A1-A3 mass on this route (shares per material must sum to 1). Same route_id + "
                       "different segment_no = SEQUENTIAL legs (e.g. ship→truck) carrying the SAME mass. "
                       "Each segment needs its own distance_source. mass_tonnes_legacy / ef_override_legacy "
                       "feed only the legacy engine. I_A4 = ΣΣ (M/1000)·D·EF / 1000 [t CO₂e].")

        # ── A5 Construction (lifecycle order: after A4, before B6) ──
        a5_boq_mode, a5_diesel_l = 'installed', 0.0
        a5_diesel_ef = FUEL_FACTORS['diesel']['ef_kgco2e_per_l']
        a5_elec_kwh, a5_waste_rate, a5_waste_transport_km, a5_waste_treatment_ef = 0.0, 0.0, 0.0, 0.0
        a5_diesel_mode, a5_equipment = 'simple', None
        a5_waste_rates, a5_treatment_shares, a5_waste_routes = None, None, None
        if include_a5:
            st.markdown("### 🏗️ A5 Construction")
            st.caption("Scenario / user inputs. A5 is reported separately from A4.")
            a5_boq_mode = st.selectbox("BOQ basis", ["installed", "purchased"], index=0, key="a5_boq_mode",
                                       help="installed: extra waste production added here. purchased: production already in A1-A3.")
            a5_diesel_ef = st.number_input("Diesel EF (kgCO₂e/L)", value=FUEL_FACTORS['diesel']['ef_kgco2e_per_l'],
                                           min_value=0.0, step=0.01, format="%.2f", key="a5_diesel_ef")
            # R11-review: equipment-fleet diesel (WBGT CCF/PL scenario) is not sourced-ready,
            # so it is disabled in publication mode until every input carries a source.
            _diesel_methods = ["simple"] if publication_mode else ["simple", "equipment"]
            a5_diesel_mode = st.selectbox("Diesel method", _diesel_methods, index=0, key="a5_diesel_mode",
                                          help="simple: total litres. equipment: Σ N·FC·LF·CCF·H·D/(1−PL) "
                                               "(developer only; the scientific engine needs total litres).")
            if publication_mode:
                st.caption("Equipment-fleet diesel (WBGT CCF/PL) is disabled in publication mode; "
                           "enter total sourced litres.")
            if a5_diesel_mode == "equipment":
                eq0 = pd.DataFrame({'equipment': ['excavator', 'crane'], 'N': [0.0, 0.0],
                                    'FC_L_per_h': [0.0, 0.0], 'LF': [0.6, 0.5], 'CCF': [1.0, 1.0],
                                    'H_per_day': [8.0, 8.0], 'days': [0.0, 0.0], 'PL': [0.0, 0.0]})
                eq_edit = st.data_editor(eq0, hide_index=True, use_container_width=True, key="a5_equipment_editor",
                                         num_rows="dynamic")
                a5_equipment = [{'N': float(_r['N']), 'FC': float(_r['FC_L_per_h']), 'LF': float(_r['LF']),
                                 'CCF': float(_r['CCF']), 'H': float(_r['H_per_day']), 'D': float(_r['days']),
                                 'PL': float(_r['PL'])} for _, _r in pd.DataFrame(eq_edit).iterrows()]
                st.caption("CCF (climate correction) and PL (heat-stress productivity loss) are WBGT "
                           "scenario parameters — not validated unless calibrated.")
            else:
                a5_diesel_l = st.number_input("Construction diesel (L)", value=0.0, min_value=0.0, step=1000.0, key="a5_diesel_l")
            a5_elec_kwh = st.number_input("Construction electricity (kWh)", value=0.0, min_value=0.0, step=1000.0, key="a5_elec_kwh")
            a5_waste_rate = st.number_input("Global waste rate w (0–1, fallback)", value=0.0, min_value=0.0, max_value=0.95, step=0.01, format="%.2f", key="a5_waste_rate",
                                            help="Used for any material without a per-material rate below.")
            a5_waste_transport_km = st.number_input("Waste transport (km, fallback)", value=0.0, min_value=0.0, step=10.0, key="a5_waste_km")
            # Unit note: the referenced scientific engine uses per-TONNE waste factors
            # (registry or a documented per-tonne override with its own source). This legacy
            # per-kg fallback feeds ONLY the legacy engine.
            a5_waste_treatment_ef = st.number_input("Waste treatment EF — legacy engine only (kgCO₂e/kg)", value=0.0, min_value=0.0, step=0.01, format="%.3f", key="a5_waste_ef",
                                                    help="Scientific engine ignores this and uses per-tonne registry/override factors.")
            a5_waste_routes = None
            with st.expander("♻️ Per-material A5 waste (rates + shares + routes/factors)", expanded=False):
                _n = len(MATERIALS_UI)
                wdf0 = pd.DataFrame({'material': MATERIALS_UI, 'waste_rate': [a5_waste_rate] * _n,
                                     'reuse': [0.0] * _n, 'recycle': [0.0] * _n, 'landfill': [1.0] * _n,
                                     'transport_km': [a5_waste_transport_km] * _n,
                                     'transport_ef': [TRANSPORT_EMISSION_FACTORS['truck']] * _n,
                                     'ef_reuse': [0.0] * _n, 'ef_recycle': [0.0] * _n,
                                     'ef_landfill': [a5_waste_treatment_ef] * _n, 'source': [''] * _n})
                wedit = st.data_editor(wdf0, hide_index=True, use_container_width=True, key="a5_waste_editor",
                                       disabled=['material'])
                a5_waste_rates, a5_treatment_shares, a5_waste_routes = {}, {}, {}
                for _, _r in pd.DataFrame(wedit).iterrows():
                    _m = _r['material']
                    a5_waste_rates[_m] = float(_r['waste_rate'])
                    a5_treatment_shares[_m] = {'reuse': float(_r['reuse']), 'recycle': float(_r['recycle']),
                                               'landfill': float(_r['landfill'])}
                    a5_waste_routes[_m] = {
                        'transport_km': float(_r['transport_km']), 'transport_ef': float(_r['transport_ef']),
                        'ef_reuse': float(_r['ef_reuse']), 'ef_recycle': float(_r['ef_recycle']),
                        'ef_landfill': float(_r['ef_landfill']), 'source': str(_r['source'])}
                st.caption("W_j = M_j·w/(1−w) [installed] or M_j·w [purchased]. "
                           "reuse + recycle + landfill must equal 1. For the scientific engine, "
                           "ef_reuse/ef_recycle/ef_landfill are **kgCO₂e/tonne of waste** and are used "
                           "as a documented override ONLY when this row's **source** is filled "
                           "(reuse needs a source even for a 0 factor). Otherwise a verified per-tonne "
                           "registry factor is used, and materials without one become incomplete_sources.")

        st.markdown("### 🌍 B6 Operation — Energy, Grid Carbon, and Service Demand")
        carbon_intensity_input = st.number_input("Grid carbon (kgCO₂/kWh)", value=0.5, min_value=0.0, step=0.05, key="carbon_int")
        # R23/R14/R15: legacy manual land-use and noise figures are developer-only. The
        # publication-grade land-use and noise co-benefits are computed in the Benefit KPI module.
        if not publication_mode:
            land_use = st.number_input("Land use (pass/ha) — legacy", value=5000.0, min_value=0.0, step=100.0, key="land_use")
            noise_reduction = st.number_input("Noise reduction (dB) — legacy", value=10.0, min_value=0.0, step=1.0, key="noise")
        else:
            land_use = 0.0
            noise_reduction = 0.0

        energy_per_pax = st.number_input("Energy (kWh/pax-km)", value=0.15, min_value=0.0, step=0.01, format="%.3f", key="energy")
        # R11: demand basis. pkm_direct keeps the legacy daily_pax_km·365 figure; daily/annual
        # compute served PKM = min(demand,capacity) · avg_trip · availability.
        b6_demand_basis = st.selectbox("B6 demand basis", ["pkm_direct", "daily", "annual"], index=0, key="b6_demand_basis",
                                       help="pkm_direct: enter passenger-km directly. daily/annual: enter demand, "
                                            "capacity and trip length; served demand is capped by capacity.")
        daily_pax_km = st.number_input("Daily pax-km (1000)", value=500.0, min_value=0.0, step=10.0, key="daily_pax")
        b6_demand, b6_capacity, b6_avg_trip_km = 0.0, 0.0, 0.0
        if b6_demand_basis != "pkm_direct":
            b6_demand = st.number_input(f"Passenger demand ({b6_demand_basis})", value=0.0, min_value=0.0, step=1000.0, key="b6_demand")
            b6_capacity = st.number_input(f"Max served capacity ({b6_demand_basis}, passengers)", value=0.0, min_value=0.0, step=1000.0, key="b6_capacity",
                                          help="served = min(demand, capacity).")
            b6_avg_trip_km = st.number_input("Average trip length (km)", value=0.0, min_value=0.0, step=1.0, key="b6_avg_trip")
        availability = st.slider("Availability (%)", 0, 100, 98, key="avail")
        # R23: legacy manual 'time savings' is developer-only; the publication-grade time
        # saving / value-of-time is computed in the Benefit KPI module.
        if not publication_mode:
            time_savings = st.number_input("Time savings (1000h) — legacy", value=2.5, min_value=0.0, step=0.1, key="time_sav")
        else:
            time_savings = 0.0
        # R8-CI: grid carbon trajectory + explicit project renewable procurement.
        b6_grid_change_pct = st.number_input("Annual grid CI change (%/yr)", value=0.0, step=0.5, format="%.2f", key="b6_grid_change",
                                             help="CI_grid,t = CI₀·(1+g)^(t-1). 0 = constant grid factor.")
        b6_project_renewable = st.checkbox("Project renewable procurement (CI_eff = (1−r)·CI_grid + r·CI_renew)", value=False, key="b6_project_renewable")
        b6_renewable_share_proj, b6_renewable_change_pct, b6_ci_renewable = 0.0, 0.0, 0.0
        if b6_project_renewable:
            b6_renewable_share_proj = st.slider("Project renewable share r₀ (%)", 0, 100, 0, key="b6_renew_share")
            b6_renewable_change_pct = st.number_input("Annual change in r (%/yr)", value=0.0, step=0.5, format="%.2f", key="b6_renew_change")
            b6_ci_renewable = st.number_input("Renewable CI (kgCO₂/kWh)", value=0.0, min_value=0.0, step=0.01, format="%.3f", key="b6_ci_renew")
        # R11: energy tariff + escalation → PV energy cost from kWh×tariff (0 = use legacy cost input).
        b6_energy_tariff = st.number_input("Energy tariff ($/kWh, 0 = off)", value=0.0, min_value=0.0, step=0.01, format="%.3f", key="b6_tariff")
        b6_energy_escalation_pct = st.number_input("Energy price escalation (%/yr)", value=0.0, step=0.5, format="%.2f", key="b6_escal")

        # ── Advanced module fields (defaults; rendered only when the module is on) ──
        sd_C0, sd_delta, sd_maint_interval = 1.0, 0.005, 5
        sd_rho, sd_tau, sd_alpha, sd_growth_pct = 0.05, 1, 0.10, 0.0
        if sd_enable:
            st.markdown("### 🔧 Dynamic B6 — System Dynamics option")
            st.caption("Scenario — not validated unless calibrated.")
            sd_C0 = st.number_input("Initial condition C₀", value=1.0, min_value=0.0, max_value=1.0, step=0.05, key="sd_C0")
            sd_delta = st.number_input("Degradation δ (/yr)", value=0.005, min_value=0.0, step=0.005, format="%.3f", key="sd_delta")
            sd_maint_interval = st.number_input("Maintenance interval (yr)", value=5, min_value=0, step=1, key="sd_maint_interval")
            sd_rho = st.number_input("Recovery ρ", value=0.05, min_value=0.0, step=0.01, format="%.3f", key="sd_rho")
            sd_tau = st.number_input("Delay τ (yr)", value=1, min_value=0, step=1, key="sd_tau")
            sd_alpha = st.number_input("Energy penalty α", value=0.10, min_value=0.0, step=0.05, format="%.2f", key="sd_alpha")
            sd_growth_pct = st.number_input("Demand growth g (%)", value=0.0, min_value=0.0, step=0.5, key="sd_growth")

        b2_use_sd_schedule, b2_interval, b2_material_pct = True, 5, 0.05
        b2_diesel_l, b2_elec_kwh, b2_transport_km, b2_cost_per_event_m = 0.0, 0.0, 0.0, 0.0
        b4_years, b4_frac_steel, b4_frac_concrete = "", 0.0, 0.0
        b4_cost_per_event_m, b4_waste_ef, b4_transport_km = 0.0, 0.0, 0.0
        b4_table = None
        lcca_maint_mode = 'simple_annual'
        b2b5_event_rows = []
        b2b5_module_declarations = {}
        if include_b2b5:
            st.markdown("### 🔁 B2–B5 Maintenance & Replacement")
            st.caption("Activity-based scenario unless project records are supplied.")
            if SCI_LCA_AVAILABLE:
                with st.expander("🔬 Scientific B2–B5 event editor (activity-based)", expanded=False):
                    st.caption("One row per material-activity within an event (same event_id groups "
                               "rows). added/removed mass are DERIVED from new_material_kg / "
                               "removed_material_kg — never free values. No %A1-A3, no cost-to-carbon. "
                               "Each B2/B3/B4/B5 gets an independent status; year must be within RSP.")
                    _b2b5_df0 = pd.DataFrame({
                        "event_id": [""], "module": ["B4"], "year": [25], "event_source": [""],
                        "asset": [""], "new_material": ["steel"], "new_material_kg": [0.0],
                        "material_source": [""], "mass_role": ["retained_in_asset"],
                        "removed_material": ["steel"], "removed_material_kg": [0.0],
                        "removed_material_source": [""],
                        # Removed mass must be ALLOCATED to a route; it does not vanish.
                        "removed_reuse_kg": [0.0], "removed_recycle_kg": [0.0],
                        "removed_disposal_kg": [0.0], "removed_other_kg": [0.0],
                        "removed_flow_source": [""],
                        "diesel_l": [0.0], "diesel_source": [""], "elec_kwh": [0.0], "elec_source": [""],
                        # Inbound new-material transport and outbound removed-material
                        # transport are DISTINCT legs carrying different masses.
                        "transport_purpose": ["new_material_inbound"],
                        "transport_km": [0.0], "transport_mode": ["truck"], "transport_source": [""],
                        "removed_transport_km": [0.0], "removed_transport_mode": ["truck"],
                        "removed_transport_source": [""],
                        "waste_kg": [0.0], "waste_factor_code": [""], "waste_source": [""]})
                    _b2b5_edit = pd.DataFrame(st.data_editor(
                        _b2b5_df0, hide_index=True, use_container_width=True,
                        key="b2b5_event_editor", num_rows="dynamic"))
                    _b2b5_num = {"year", "new_material_kg", "removed_material_kg", "diesel_l",
                                 "elec_kwh", "transport_km", "waste_kg",
                                 "removed_reuse_kg", "removed_recycle_kg", "removed_disposal_kg",
                                 "removed_other_kg", "removed_transport_km"}
                    for _, _r in _b2b5_edit.iterrows():
                        if str(_r["event_id"]).strip():
                            b2b5_event_rows.append(
                                {k: (float(_r[k] or 0.0) if k in _b2b5_num else str(_r[k]))
                                 for k in _b2b5_df0.columns})
                    st.caption(
                        "mass_role: retained_in_asset / consumable / temporary. "
                        "Removed mass is reconciled separately: removed_material_kg must equal "
                        "reuse + recycle + disposal + other within software tolerance. "
                        "Inbound new-material transport and outbound removed-material transport are distinct."
                    )
                    # Declare B2/B3/B4/B5 modules you did NOT enter as documented_zero / N-A so the
                    # stage can close (B4-only never closes the whole stage on its own).
                    _b2b5decl0 = pd.DataFrame({
                        "module": ["B2", "B3", "B4", "B5"], "declaration": [""] * 4,
                        "justification": [""] * 4, "source": [""] * 4})
                    _b2b5decl = pd.DataFrame(st.data_editor(
                        _b2b5decl0, hide_index=True, use_container_width=True,
                        key="b2b5_module_decl_editor", disabled=["module"]))
                    b2b5_module_declarations = {}
                    for _, _r in _b2b5decl.iterrows():
                        _d = str(_r["declaration"]).strip()
                        if _d in ("documented_zero", "not_applicable_with_justification") and \
                                str(_r["justification"]).strip() and str(_r["source"]).strip():
                            b2b5_module_declarations[str(_r["module"])] = {
                                "status": _d, "justification": str(_r["justification"]).strip(),
                                "source": str(_r["source"]).strip()}
            b2_use_sd_schedule = st.checkbox("Link B2 to SD schedule", value=True, key="b2_use_sd")
            b2_interval = st.number_input("B2 interval (yr)", value=5, min_value=0, step=1, key="b2_interval")
            b2_material_pct = st.number_input("B2 material/event (% A1-A3)", value=0.05, min_value=0.0, step=0.05, format="%.2f", key="b2_material_pct")
            b2_diesel_l = st.number_input("B2 diesel/event (L)", value=0.0, min_value=0.0, step=100.0, key="b2_diesel_l")
            b2_elec_kwh = st.number_input("B2 electricity/event (kWh)", value=0.0, min_value=0.0, step=100.0, key="b2_elec_kwh")
            b2_transport_km = st.number_input("B2 transport (km)", value=0.0, min_value=0.0, step=10.0, key="b2_transport_km")
            b2_cost_per_event_m = st.number_input("B2 cost/event ($M)", value=0.0, min_value=0.0, step=0.1, key="b2_cost_event")
            lcca_maint_mode = st.selectbox("LCCA maintenance mode", ["simple_annual", "activity_based"], index=0, key="lcca_maint_mode",
                                           help="simple_annual: annual maintenance only. activity_based: B2/B3/B5 activity costs only. B4 cost added in both.")
            if enable_b4:
                b4_years = st.text_input("B4 years (e.g. 25,40)", value="", key="b4_years")
                b4_cost_per_event_m = st.number_input("B4 cost/event ($M)", value=0.0, min_value=0.0, step=1.0, key="b4_cost_event")
                # R24: per-material B4 replacement table (all materials, not just steel/concrete).
                _bn = len(MATERIALS_UI)
                b4_df0 = pd.DataFrame({'material': MATERIALS_UI, 'replacement_fraction': [0.0] * _bn,
                                       'waste_ef': [0.0] * _bn, 'transport_km': [0.0] * _bn})
                b4_edit = st.data_editor(b4_df0, hide_index=True, use_container_width=True,
                                         disabled=['material'], key="b4_editor")
                b4_table = {}
                for _, _r in pd.DataFrame(b4_edit).iterrows():
                    b4_table[_r['material']] = {'replacement_fraction': float(_r['replacement_fraction']),
                                                'waste_ef': float(_r['waste_ef']),
                                                'transport_km': float(_r['transport_km'])}
                b4_frac_steel = b4_table.get('steel', {}).get('replacement_fraction', 0.0)
                b4_frac_concrete = b4_table.get('concrete', {}).get('replacement_fraction', 0.0)
                st.caption("B4 like-for-like replacement per material: added = removed = fraction × installed mass. "
                           "New-material A1-A3 + removed-material waste transport/treatment are counted; "
                           "mass balance stays neutral (added = removed).")

        c1_diesel_l, c1_elec_kwh, eol_transport_km = 0.0, 0.0, 50.0
        eol_reuse_ef, eol_recycle_ef, eol_disposal_ef = 0.0, 0.0, 0.0
        eol_recovery_eta, eol_cost_m = 1.0, 0.0
        eol_table = {m: {'reuse': 0.0, 'recycle': 0.0, 'secondary_ef': 0.0} for m in MATERIALS_UI}
        c2_routes = None
        c1c4_rows = []
        module_d_rows = []
        c1_diesel_source_sci, c1_electricity_source_sci = "", ""
        if include_c1c4:
            st.markdown("### ♻️ C1–C4 End-of-Life")
            st.caption("EOL scenario. Treatment shares must sum to 1 (uses remaining masses after B4/B5).")
            c1_diesel_l = st.number_input("C1 diesel (L)", value=0.0, min_value=0.0, step=1000.0, key="c1_diesel_l")
            c1_elec_kwh = st.number_input("C1 electricity (kWh)", value=0.0, min_value=0.0, step=1000.0, key="c1_elec_kwh")
            if SCI_LCA_AVAILABLE:
                with st.expander("🔬 Scientific C1–C4 editor (mass = remaining after B2-B5)", expanded=False):
                    st.caption("C-stage mass is the chronological remaining mass after B2-B5 (you cannot "
                               "type a free mass). Per material: reuse+recycle+disposal = 1 with a source; "
                               "C2 is a sourced route; disposal/recycle use verified per-tonne factors; C1 "
                               "electricity uses the EOL-year grid CI.")
                    c1_diesel_source_sci = st.text_input("C1 diesel source", value="", key="c1_diesel_source_sci")
                    c1_electricity_source_sci = st.text_input("C1 electricity source", value="", key="c1_elec_source_sci")
                    _c1c4_df0 = pd.DataFrame({
                        "material": MATERIALS_UI, "reuse_share": [0.0]*6, "recycle_share": [0.0]*6,
                        "disposal_share": [1.0]*6, "share_source": [""]*6,
                        "c2_distance_km": [0.0]*6, "c2_mode": ["truck"]*6, "c2_source": [""]*6,
                        # RICS C2 return / empty-running closure (road routes).
                        "c2_return_factor_unit": ["tonne_km"] * 6,
                        "c2_return_fraction": [0.0] * 6,
                        "c2_empty_return_factor": [0.0] * 6,
                        "c2_number_of_return_trips": [0.0] * 6,
                        "c2_vehicle_capacity_t": [0.0] * 6,
                        "c2_load_factor": [1.0] * 6,
                        "c2_return_source_file": [""] * 6,
                        "c2_return_source_location": [""] * 6,
                        "c2_return_justification": [""] * 6,
                        "ef_reuse": [0.0]*6, "ef_recycle": [0.0]*6, "ef_landfill": [0.0]*6, "source": [""]*6})
                    _c1c4_edit = pd.DataFrame(st.data_editor(
                        _c1c4_df0, hide_index=True, use_container_width=True,
                        key="c1c4_sci_editor", disabled=["material"]))
                    _c1c4_num = {"reuse_share", "recycle_share", "disposal_share", "c2_distance_km",
                                 "ef_reuse", "ef_recycle", "ef_landfill",
                                 "c2_return_fraction", "c2_empty_return_factor",
                                 "c2_number_of_return_trips", "c2_vehicle_capacity_t",
                                 "c2_load_factor"}
                    for _, _r in _c1c4_edit.iterrows():
                        c1c4_rows.append({k: (float(_r[k] or 0.0) if k in _c1c4_num else str(_r[k]))
                                          for k in _c1c4_df0.columns})
                    st.caption(
                        "RICS C2 route closure: road transport must address return/empty running. "
                        "No UK 43% default is automatically inserted for this Egypt project. "
                        "A documented zero/N-A requires source + justification."
                    )
                with st.expander("🔬 Module D editor (from C3 recovered flows only)", expanded=False):
                    st.caption(
                        "RICS Appendix K / EN 15804 Module D1. "
                        "substitution_ratio = quality ratio QRout/QSub; "
                        "primary_ef = EVMSub out (primary/substituted material to functional equivalence); "
                        "recovery_ef = EMR after EoW out (recovery processing after end-of-waste). "
                        "Standard signed result: negative = potential benefit; positive = potential load. "
                        "Module D remains separate from Gross A-C."
                    )
                    st.caption("Module D is derived ONLY from C3 recovered flows (RecoveredOutput_D ≤ "
                               "C3 recovered mass) — there is no independent Module-D path in Publication mode.")
                    _md0 = pd.DataFrame({
                        "material": MATERIALS_UI, "recovered_output_kg": [0.0]*6,
                        "secondary_input_kg": [0.0]*6, "substitution_ratio": [0.0]*6,
                        "primary_ef": [0.0]*6, "primary_source": [""]*6,
                        "recovery_ef": [0.0]*6, "recovery_source": [""]*6,
                        "flow_source": [""]*6, "substitution_source": [""]*6})
                    _md_edit = pd.DataFrame(st.data_editor(
                        _md0, hide_index=True, use_container_width=True,
                        key="module_d_sci_editor", disabled=["material"]))
                    _md_num = {"recovered_output_kg", "secondary_input_kg", "substitution_ratio",
                               "primary_ef", "recovery_ef"}
                    for _, _r in _md_edit.iterrows():
                        if float(_r["recovered_output_kg"] or 0.0) > 0.0:
                            module_d_rows.append({k: (float(_r[k] or 0.0) if k in _md_num else str(_r[k]))
                                                  for k in _md0.columns})
            eol_transport_km = st.number_input("EOL transport (km)", value=50.0, min_value=0.0, step=10.0, key="eol_transport_km")
            eol_reuse_ef = st.number_input("Reuse EF (kgCO₂e/kg)", value=0.0, min_value=0.0, step=0.01, format="%.3f", key="eol_reuse_ef")
            eol_recycle_ef = st.number_input("Recycle EF (kgCO₂e/kg)", value=0.0, min_value=0.0, step=0.01, format="%.3f", key="eol_recycle_ef")
            eol_disposal_ef = st.number_input("Disposal EF (kgCO₂e/kg)", value=0.0, min_value=0.0, step=0.01, format="%.3f", key="eol_disposal_ef")
            eol_recovery_eta = st.number_input("Recovery efficiency η", value=1.0, min_value=0.0, max_value=1.0, step=0.05, format="%.2f", key="eol_eta")
            eol_cost_m = st.number_input("EOL cost ($M)", value=0.0, min_value=0.0, step=10.0, key="eol_cost_m")
            st.markdown("**Per-material treatment shares + secondary EF**")
            eol_df0 = pd.DataFrame({'material': MATERIALS_UI, 'reuse': [0.0]*6, 'recycle': [0.0]*6, 'secondary_EF': [0.0]*6})
            eol_edit = st.data_editor(eol_df0, hide_index=True, use_container_width=True, key="eol_editor",
                                      disabled=['material'])
            st.caption("Disposal share = 1 − reuse − recycle (auto). Secondary EF 0 = no Module D for that material.")
            for _, _r in pd.DataFrame(eol_edit).iterrows():
                eol_table[_r['material']] = {'reuse': float(_r['reuse']), 'recycle': float(_r['recycle']),
                                             'secondary_ef': float(_r['secondary_EF'])}
            # R25: per-material / per-mode C2 transport routes (multi-leg via dynamic rows).
            with st.expander("🚛 C2 EOL transport routes (per material / per mode)", expanded=False):
                c2_df0 = pd.DataFrame({'material': MATERIALS_UI, 'mode': ['truck'] * len(MATERIALS_UI),
                                       'distance_km': [eol_transport_km] * len(MATERIALS_UI),
                                       'ef': [0.0] * len(MATERIALS_UI), 'share': [1.0] * len(MATERIALS_UI)})
                c2_edit = st.data_editor(c2_df0, hide_index=True, use_container_width=True, key="c2_editor",
                                         num_rows="dynamic")
                c2_routes = {}
                for _, _r in pd.DataFrame(c2_edit).iterrows():
                    c2_routes.setdefault(_r['material'], []).append({
                        'mode': _r['mode'], 'distance_km': float(_r['distance_km']),
                        'ef': float(_r['ef']), 'share': float(_r['share'])})
                st.caption("Add rows for multi-leg/multi-mode routes per material. EF 0 → registry mode factor. "
                           "C2 = ΣΣ (M·share/1000)·D·EF / 1000. No route → single EOL distance × truck EF.")

        # ── LCCA Costs (R18 order: after the A1-C4 stages) ──
        st.markdown("### 💰 LCCA Costs")
        construction_cost = st.number_input("Base construction CAPEX ($M)", value=2500.0, min_value=0.0, step=50.0, key="const_cost")
        # R28: contract factor scales base CAPEX → CAPEX_contract = CAPEX_base · factor.
        contract_factor = st.number_input("Contract factor", value=1.0, min_value=0.0, step=0.05, format="%.2f", key="contract_factor",
                                          help="Adjusts base CAPEX for contract conditions. CAPEX used in NPV = base × factor.")
        maintenance_cost = st.number_input("Maintenance ($M/yr)", value=50.0, min_value=0.0, step=5.0, key="maint_cost")
        economic_multiplier = st.number_input("Economic multiplier", value=2.5, min_value=1.0, step=0.1, key="econ_mult")
        discount_rate = st.number_input("Discount rate (%)", value=5.0, min_value=0.0, max_value=20.0, step=0.5, key="discount_rate")
        annual_energy_cost = st.number_input("Energy cost ($M/yr) — fallback only if tariff is 0", value=0.0, min_value=0.0, step=1.0, key="energy_cost",
                                             help="Used only when the B6 energy tariff is 0; otherwise the kWh×tariff PV is used.")
        residual_value = st.number_input("Residual value ($M)", value=0.0, min_value=0.0, step=10.0, key="residual_value")
        # R23: 'jobs created' is a legacy manual figure — developer-only. The publication-grade
        # jobs metric is computed in the Benefit KPI module.
        if not publication_mode:
            jobs_created = st.number_input("Jobs created (legacy manual)", value=5000.0, min_value=0.0, step=100.0, key="jobs")
        else:
            jobs_created = 0.0

        # ── R15: LEGACY Benefit KPI inputs — DEVELOPER MODE ONLY ──────────────
        # These fields collect a value and nothing else: no unit contract, no source
        # reference, no page, no geography, no price year. That is enough for the
        # historical dashboard and is NOT enough to publish, so Publication mode
        # never shows them and never reads their results. The Publication Benefits
        # inputs are the evidence-carrying block further down.
        if not publication_mode:
            st.markdown("### 🗄️ Legacy Benefit KPI inputs (developer only)")
            st.caption("Numeric-only legacy fields. They feed the Developer dashboard and the "
                       "parity suites. They are NOT documented evidence and are never used by "
                       "Publication mode.")
            benefit_baseline_ci_pkm = st.number_input("Displaced-mode CI (kgCO₂e/pkm)", value=0.0, min_value=0.0, step=0.01, format="%.3f", key="ben_base_ci",
                                                      help="Legacy dashboard KPI. Publication uses the referenced Benefits core instead.")
            benefit_annual_trips = st.number_input("Annual trips", value=0.0, min_value=0.0, step=1000.0, key="ben_trips")
            benefit_time_saved_min = st.number_input("Time saved per trip (min)", value=0.0, min_value=0.0, step=1.0, key="ben_dt")
            benefit_value_of_time = st.number_input("Value of time ($/h)", value=0.0, min_value=0.0, step=1.0, key="ben_vot")
            benefit_jobs_per_musd = st.number_input("Construction jobs per $M capex", value=0.0, min_value=0.0, step=0.1, key="ben_jobs_musd")
            benefit_operational_jobs = st.number_input("Operational jobs", value=0.0, min_value=0.0, step=10.0, key="ben_op_jobs")
            benefit_land_ha = st.number_input("Project land footprint (ha)", value=0.0, min_value=0.0, step=1.0, key="ben_land")
            benefit_noise_baseline_db = st.number_input("Baseline noise (dB)", value=0.0, min_value=0.0, step=1.0, key="ben_noise_base")
            benefit_noise_monorail_db = st.number_input("Monorail noise (dB)", value=0.0, min_value=0.0, step=1.0, key="ben_noise_mono")
        else:
            # Backward-compatible plumbing only. The legacy keys still exist in
            # current_params so the parameter classification and the Developer path
            # keep working, but they carry nothing in Publication mode.
            benefit_baseline_ci_pkm = 0.0
            benefit_annual_trips = 0.0
            benefit_time_saved_min = 0.0
            benefit_value_of_time = 0.0
            benefit_jobs_per_musd = 0.0
            benefit_operational_jobs = 0.0
            benefit_land_ha = 0.0
            benefit_noise_baseline_db = 0.0
            benefit_noise_monorail_db = 0.0

        steel_recycle, aluminum_recycle, recycling_scenario, renewable_share = 70, 85, 'none', 20
        if show_legacy:
            st.markdown("### 🗄️ Legacy / dashboard-only")
            st.caption("Module-D recycling scenario is used ONLY when C1–C4 is off. Renewable is dashboard-only.")
            steel_recycle = st.slider("Steel recycling (%)", 0, 100, 70, key="steel_recycle")
            aluminum_recycle = st.slider("Aluminum recycling (%)", 0, 100, 85, key="aluminum_recycle")
            recycling_scenario = st.selectbox("Legacy Module-D scenario", ["none", "conservative", "base"], index=0, key="recycling_scenario")
            renewable_share = st.slider("Renewable share (%) — dashboard-only", 0, 100, 20, key="renewable")

        # ── Referenced scientific-LCA provenance (feeds the strict, sourced core only) ──
        # These inputs do NOT change any legacy result. They supply the traceable sources
        # (densities, BOQ, ridership, Egypt grid CI, RSP) the referenced core requires
        # before it will report a publication-grade number.
        lca_provenance = {}
        if SCI_LCA_AVAILABLE:
            with st.expander("🔬 Scientific LCA provenance (referenced core)", expanded=False):
                st.caption("Fill these from project evidence to unlock the referenced Scientific LCA tab. "
                           "Empty fields keep that tab in 'source-open' mode (no fabricated numbers).")
                lca_provenance = add_lca_source_inputs(st, assessment_lifetime_default=int(ASSESSMENT_LIFETIME_YEARS))

        # ── Referenced scientific-Benefits provenance ─────────────────────────
        # Each field collects a value AND the evidence behind it. Anything left
        # empty stays SOURCE-OPEN, which is reported explicitly rather than
        # silently defaulting to zero.
        with st.expander("🌱 Scientific Benefits provenance (referenced core)", expanded=False):
            st.caption("Every Publication Benefits number is produced from these evidence "
                       "envelopes. A method reference supports the equation; only "
                       "PROJECT-SPECIFIC or OFFICIAL-PROJECT-DATA can carry a project "
                       "headline. Empty fields stay source-open — nothing is assumed.")
            benefits_scientific_inputs = collect_benefits_scientific_inputs()

        st.markdown("---")
        st.caption("↑ Use the **Run Assessment** button at the top of this panel to apply all inputs.")
    run_btn = bool(run_btn)

# Collect parameters
current_params = {
    # R21: project definition (scope/metadata)
    'project_name': project_name, 'route_length_km': route_length_km,
    'assessment_lifetime': assessment_lifetime, 'analysis_start_year': analysis_start_year,
    'currency': currency, 'price_year': price_year, 'functional_unit': functional_unit,
    'concrete': concrete, 'steel': steel, 'aluminum': aluminum,
    'wood': wood, 'frp': frp, 'glass': glass, 'glass_thickness_mm': glass_thickness_mm,
    **{f'recycled_content_{_m}': recycled_content_inputs[_m] for _m in MATERIALS_UI},
    **{f'ef_secondary_{_m}': ef_secondary_inputs[_m] for _m in MATERIALS_UI},
    **{f'ef_secondary_source_{_m}': ef_secondary_sources[_m] for _m in MATERIALS_UI},
    **{f'factor_basis_{_m}': ef_secondary_basis[_m] for _m in MATERIALS_UI},
    'recycled_secondary_documented_ok': recycled_secondary_documented_ok,
    'steel_recycle': steel_recycle, 'aluminum_recycle': aluminum_recycle, 'recycling_scenario': recycling_scenario,
    'transport_distance_km': transport_distance_km, 'transport_mode': transport_mode,
    'a4_mode': a4_mode, 'a4_advanced_legs': a4_advanced_legs,
    'carbon_intensity': carbon_intensity_input, 'renewable_share': renewable_share,
    'land_use': land_use, 'noise_reduction': noise_reduction,
    'energy_per_pax': energy_per_pax, 'daily_pax_km': daily_pax_km,
    'time_savings': time_savings, 'availability': availability,
    'benefit_baseline_ci_pkm': benefit_baseline_ci_pkm, 'benefit_annual_trips': benefit_annual_trips,
    'benefit_time_saved_min': benefit_time_saved_min, 'benefit_value_of_time': benefit_value_of_time,
    'benefit_jobs_per_musd': benefit_jobs_per_musd, 'benefit_operational_jobs': benefit_operational_jobs,
    'benefit_land_ha': benefit_land_ha, 'benefit_noise_baseline_db': benefit_noise_baseline_db,
    'benefit_noise_monorail_db': benefit_noise_monorail_db,
    'b6_demand_basis': b6_demand_basis, 'b6_demand': b6_demand, 'b6_capacity': b6_capacity,
    'b6_avg_trip_km': b6_avg_trip_km, 'b6_grid_change_pct': b6_grid_change_pct,
    'b6_project_renewable': b6_project_renewable, 'b6_renewable_share_proj': b6_renewable_share_proj,
    'b6_renewable_change_pct': b6_renewable_change_pct, 'b6_ci_renewable': b6_ci_renewable,
    'b6_energy_tariff': b6_energy_tariff, 'b6_energy_escalation_pct': b6_energy_escalation_pct,
    'construction_cost': construction_cost, 'maintenance_cost': maintenance_cost,
    'contract_factor': contract_factor,
    'jobs_created': jobs_created, 'economic_multiplier': economic_multiplier,
    'discount_rate': discount_rate, 'annual_energy_cost': annual_energy_cost,
    'residual_value': residual_value,
    'sd_enable': sd_enable, 'sd_C0': sd_C0, 'sd_delta': sd_delta,
    'sd_maint_interval': sd_maint_interval, 'sd_rho': sd_rho, 'sd_tau': sd_tau,
    'sd_alpha': sd_alpha, 'sd_growth_pct': sd_growth_pct,
    'include_a5': include_a5, 'a5_boq_mode': a5_boq_mode, 'a5_diesel_l': a5_diesel_l,
    'a5_diesel_ef': a5_diesel_ef, 'a5_elec_kwh': a5_elec_kwh, 'a5_waste_rate': a5_waste_rate,
    'a5_waste_transport_km': a5_waste_transport_km, 'a5_waste_treatment_ef': a5_waste_treatment_ef,
    'a5_diesel_mode': a5_diesel_mode, 'a5_equipment': a5_equipment,
    'a5_waste_rates': a5_waste_rates, 'a5_treatment_shares': a5_treatment_shares,
    'a5_waste_routes': a5_waste_routes,
    'include_b2b5': include_b2b5, 'b2_use_sd_schedule': b2_use_sd_schedule, 'b2_interval': b2_interval,
    'b2_material_pct': b2_material_pct, 'b2_diesel_l': b2_diesel_l, 'b2_elec_kwh': b2_elec_kwh,
    'b2_transport_km': b2_transport_km, 'b2_cost_per_event_m': b2_cost_per_event_m,
    'enable_b4': enable_b4, 'b4_years': b4_years, 'b4_frac_steel': b4_frac_steel,
    'b4_frac_concrete': b4_frac_concrete, 'b4_cost_per_event_m': b4_cost_per_event_m,
    'b4_waste_ef': b4_waste_ef, 'b4_transport_km': b4_transport_km, 'b4_table': b4_table,
    'lcca_maint_mode': lcca_maint_mode,
    'b2b5_event_rows': b2b5_event_rows, 'b2b5_module_declarations': b2b5_module_declarations,
    'include_c1c4': include_c1c4, 'c1_diesel_l': c1_diesel_l, 'c1_elec_kwh': c1_elec_kwh,
    'c1c4_rows': c1c4_rows, 'c1_diesel_source': c1_diesel_source_sci,
    'c1_electricity_source': c1_electricity_source_sci, 'module_d_rows': module_d_rows,
    'eol_transport_km': eol_transport_km, 'eol_reuse_ef': eol_reuse_ef, 'eol_recycle_ef': eol_recycle_ef,
    'eol_disposal_ef': eol_disposal_ef, 'eol_recovery_eta': eol_recovery_eta, 'eol_cost_m': eol_cost_m,
    'c2_routes': c2_routes,
    **{f'eol_reuse_{_m}': eol_table[_m]['reuse'] for _m in eol_table},
    **{f'eol_recycle_{_m}': eol_table[_m]['recycle'] for _m in eol_table},
    **{f'eol_secondary_ef_{_m}': eol_table[_m]['secondary_ef'] for _m in eol_table},
    # Referenced scientific-LCA provenance (used only by the strict sourced core; never by the legacy engine).
    **lca_provenance,
    # Referenced scientific-Benefits evidence. ONE nested key, classified
    # Benefits-only in the orchestrator, so nothing inside it can reach LCA or LCC.
    'benefits_scientific_inputs': benefits_scientific_inputs,
}

@st.cache_data
def run_full_assessment_cached(params_tuple):
    params = dict(params_tuple)
    return run_full_assessment(params)


@st.cache_data
def run_assessment_bundle_cached(params_tuple):
    """One separated domain run producing everything the main UI path needs.

    Computing the legacy dashboard and the scientific Benefits independently would
    run the LCA engine twice for a single screen. Worse, the two views could drift:
    the Benefits domain would price its activity from a SharedActivity built in a
    different pass than the one the LCC domain saw. The orchestrator's bundle runs
    the domains once and hands Benefits the very same neutral activity record.

    Returns ``(merged legacy dashboard dict, ScientificBenefitsResult)``.
    """
    params = dict(params_tuple)
    _result, legacy_dashboard, scientific_benefits = run_assessment_bundle(params)
    dashboard = calculate_dashboard_display_scores(params, legacy_dashboard)
    return {**legacy_dashboard, **dashboard}, scientific_benefits

# Run assessment on button click or auto-run for the first time
if run_btn or 'results' not in st.session_state:
    params_tuple = tuple(sorted(current_params.items()))
    _bundle_results, _bundle_benefits = run_assessment_bundle_cached(params_tuple)
    st.session_state['results'] = _bundle_results
    st.session_state['scientific_benefits'] = _bundle_benefits
    st.session_state['params'] = current_params
    # No direct st.session_state assignments for widget keys to prevent StreamlitAPIException
results = st.session_state['results']
params = st.session_state['params']
scientific_benefits = st.session_state['scientific_benefits']

# ── Central scientific result (authoritative in Publication mode) ──
# Computed ONCE and reused by the Results cards/exports and the Scientific tab. When the
# scientific engine cannot yet compute (open sources), Publication falls back to the
# legacy engine with a clear banner; the scientific engine governs whenever it computes.
scientific_pub = None
if SCI_LCA_AVAILABLE and publication_mode:
    try:
        scientific_pub = run_scientific_lca_from_app_params(params)
    except Exception:
        scientific_pub = None

if not results.get('publication_grade', True):
    st.error(
        "🚫 **NOT publication-grade:** FRP is included but has NO verified A1-A3 carbon factor. "
        f"FRP placeholder contribution = {results['carbon_frp']/1000:,.1f} t CO₂e. "
        f"**Defensible A1-A3 embodied carbon (excluding FRP) = {results['total_embodied_co2_excl_frp']:,.1f} t CO₂e** "
        f"vs {results['total_embodied_co2']:,.1f} t including the placeholder. "
        "Set FRP = 0, or supply a product-specific EPD, before reporting."
    )

with st.sidebar:
    st.markdown("#### ✅ Publication readiness")
    def _flag(label, ok):
        st.markdown(f"{'🟢' if ok else '🟡'} {label}: **{'yes' if ok else 'conditional'}**")
    _flag("Full LCA (A1–C4)", results.get('publication_grade_full_lca', False))
    _flag("Module D complete", results.get('module_d_quality_ok', True))
    st.caption("Uncertainty (Phase 4) & SI (Phase 5) readiness are shown in their tabs.")

with st.expander("🧩 LCA Stage Coverage", expanded=False):
    # Phase 3A: authoritative coverage comes from the modular stage_contribution.
    cov_df = pd.DataFrame(results['stage_contribution'])[['Stage', 'tCO2e', 'status']].copy()
    cov_df['tCO2e'] = cov_df['tCO2e'].map(lambda v: f"{v:,.1f}")
    st.dataframe(cov_df, use_container_width=True, hide_index=True)
    st.caption("Module D (recycling credit) is reported separately and is NOT part of the gross total.")

# ═══════════════════════════════════════════════════════════════
# MAIN CONTENT - TABS (Publication mode hides illustrative/legacy tabs)
# ═══════════════════════════════════════════════════════════════
_TAB_LABELS = {
    'results': "📊 Results & Analysis", 'sci_lca': "🔬 Scientific LCA (referenced)",
    'sci_benefits': "🌱 Scientific Benefits (referenced)",
    'oat': "📊 Sensitivity (OAT)",
    'uncertainty': "🎲 Uncertainty (Phase 4)", 'si': "🏁 Sustainability Index",
    'sd': "🔧 System Dynamics (B6)", 'benchmark': "🔬 External Benchmarking",
    'about': "📖 About & Methodology",
    'pareto': "🗄️ Pareto (illustrative)", 'twelve': "🗄️ 12-Element (illustrative)",
    'surface3d': "🗄️ 3D Surface (illustrative)", 'urban': "🗄️ Urban 3D (illustrative)",
    'interaction': "🗄️ Interaction Net (illustrative)",
}
# R18 final tab order: Results → Scientific LCA (referenced) → Scientific Benefits
# (referenced) → Sensitivity → System Dynamics (B6) → Uncertainty → Sustainability
# Index → External Benchmarking → Methodology.
# Scientific Benefits sits directly after Scientific LCA: the two are the referenced
# halves of the assessment, and a reviewer auditing sources reads them together.
_SCI_ORDER = ['results', 'sci_lca', 'sci_benefits', 'oat', 'sd', 'uncertainty', 'si', 'benchmark', 'about']
if not SCI_LCA_AVAILABLE:
    _SCI_ORDER = [k for k in _SCI_ORDER if k != 'sci_lca']
_LEGACY_ORDER = ['pareto', 'twelve', 'surface3d', 'urban', 'interaction']
_order = _SCI_ORDER if publication_mode else (_SCI_ORDER + _LEGACY_ORDER)
_created = st.tabs([_TAB_LABELS[k] for k in _order])
TABS = {k: _created[i] for i, k in enumerate(_order)}

# ═══════════════════════════════════════════════════════════════
# TAB 1: RESULTS & ANALYSIS
# ═══════════════════════════════════════════════════════════════
with TABS['results']:
    if scientific_pub is not None:
        # PUBLICATION: the headline cards are produced by the SCIENTIFIC engine (canonical).
        # Module D is shown SEPARATELY — there is no "Net incl. Module D" card.
        _h = scientific_headline(scientific_pub)
        st.success("🟢 **Publication mode — scientific engine is authoritative.** These headline "
                   "cards, the report, CSV and Excel below are produced by the referenced "
                   "scientific engine (identical to the 🔬 Scientific LCA tab). Legacy dashboards "
                   "are Developer-mode only.")
        m1, m2, m3, m4, m5 = st.columns(5)
        with m1:
            st.markdown(f"""<div class="metric-card"><div class="metric-value">{_h['GWP (kgCO2e/pkm)']:.4f}</div>
                <div class="metric-label">kg CO₂e / passenger-km (gross)</div>
                <div class="metric-delta">Scientific A1-C4 (connected scope)</div></div>""", unsafe_allow_html=True)
        with m2:
            st.markdown(f"""<div class="metric-card"><div class="metric-value">{_h['Gross A-C (tCO2e)']:,.0f}</div>
                <div class="metric-label">Gross A1-C4 (tCO₂e)</div>
                <div class="metric-delta">A5 {_h['A5 (tCO2e)']:,.0f}t · C1-C4 {_h['C1-C4 (tCO2e)']:,.0f}t</div></div>""", unsafe_allow_html=True)
        with m3:
            # Standard signed value, shown AS IS — no hand-written minus sign.
            st.markdown(f"""<div class="metric-card"><div class="metric-value">{_h['Module D1 standard-signed (tCO2e, separate)']:,.0f}</div>
                <div class="metric-label">Module D1 standard-signed (tCO₂e) — SEPARATE</div>
                <div class="metric-delta">negative = benefit · never inside Gross A-C</div></div>""", unsafe_allow_html=True)
        with m4:
            # PUBLICATION LCC GATE.
            # legacy_lcc_engine.py states that its scalar NPV must NOT supply a
            # Publication headline: it carries no row-level provenance and cannot pass a
            # source gate. Until lcc_scientific_integration.py exists, Publication mode
            # therefore shows the pending state instead of the legacy number, rather
            # than presenting a developer figure as a publication result.
            st.markdown("""<div class="metric-card">
                <div class="metric-value">N/A</div>
                <div class="metric-label">Scientific LCC</div>
                <div class="metric-delta">integration pending — legacy scalar NPV is
                    developer-only and is not a publication figure</div></div>""",
                unsafe_allow_html=True)
        with m5:
            _g = scientific_pub.get("closure_gate", {})
            st.markdown(f"""<div class="metric-card"><div class="metric-value">{'🟢' if _g.get('full_wlca_calculation_complete') else '🟡'}</div>
                <div class="metric-label">Full-WLCA calculation</div>
                <div class="metric-delta">{scientific_pub.get('scope_label','')[:38]}</div></div>""", unsafe_allow_html=True)
    else:
        if SCI_LCA_AVAILABLE and publication_mode:
            st.warning("🟡 **Publication mode — scientific sources still open.** The scientific engine "
                       "cannot yet report a number (fill the 🔬 provenance inputs). The cards below are "
                       "the legacy/scenario engine, shown ONLY until the scientific sources are complete.")
        elif SCI_LCA_AVAILABLE:
            st.info("ℹ️ Developer mode: legacy/scenario cards. The 🔬 Scientific LCA tab is the "
                    "authoritative publication path.")
        # Key metrics row (legacy)
        m1, m2, m3, m4, m5 = st.columns(5)
        with m1:
            co2_pkm = results['gwp_pkm_gross']
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{co2_pkm:.4f}</div>
                <div class="metric-label">kg CO₂e / passenger-km (gross)</div>
                <div class="metric-delta">A1-C4 gross · B6 {results['active_b6_mode']}</div>
            </div>""", unsafe_allow_html=True)
        with m2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{results['gross_a1_c4_tons']:,.0f}</div>
                <div class="metric-label">Gross A1-C4 LCA CO₂ (tons)</div>
                <div class="metric-delta">A5: {results['a5']['a5_total_tons']:,.0f}t · Module D separate</div>
            </div>""", unsafe_allow_html=True)
        with m3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{results['total_ee']/1000:,.0f}</div>
                <div class="metric-label">Embodied Energy (GJ)</div>
                <div class="metric-delta">Annual Op: {results['annual_operational_energy']:,.0f} kWh</div>
            </div>""", unsafe_allow_html=True)
        with m4:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">${results['npv_lcc_m']:,.0f}M</div>
                <div class="metric-label">LCC NPV Cost</div>
                <div class="metric-delta">Jobs: {results['total_jobs']:,.0f}</div>
            </div>""", unsafe_allow_html=True)
        with m5:
            if publication_mode:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-value">{results['gross_a1_c4_tons']:,.0f}</div>
                    <div class="metric-label">Gross A1-C4 (tons)</div>
                    <div class="metric-delta">Module D {results['module_d_tons']:,.0f}t reported separately</div>
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-value">{params['renewable_share']}%</div>
                    <div class="metric-label">Renewable (dashboard-only)</div>
                    <div class="metric-delta">Grid carbon: {results['effective_carbon_intensity']:.3f} kg/kWh</div>
                </div>""", unsafe_allow_html=True)

    if results.get('sd_enabled'):
        st.info(
            f"🔧 **Dynamic B6 active (scenario-based SD).** "
            f"Static B6 = {results['b6_static_tons']:,.0f} t · "
            f"Dynamic B6 = {results['b6_dynamic_tons']:,.0f} t · "
            f"ΔB6 = {results['delta_b6_tons']:+,.0f} t · "
            f"Dynamic total LCA = {results['total_lifecycle_co2_dynamic']:,.0f} t "
            f"({results['co2_kg_per_pkm_dynamic']:.5f} kg/pkm). See the System Dynamics (B6) tab."
        )

    with st.expander("🧱 Stage Contribution (gross modular A1-C4 LCA)", expanded=True):
        sc_df = pd.DataFrame(results['stage_contribution'])
        sc_df['tCO2e'] = sc_df['tCO2e'].map(lambda v: f"{v:,.1f}")
        sc_df['% of gross'] = sc_df['% of gross'].map(lambda v: f"{v:.1f}%")
        st.dataframe(sc_df, use_container_width=True, hide_index=True)
        # LEGACY-DEVELOPER-ONLY caption. In Publication mode the legacy Module-D credit and
        # the legacy net figure are both suppressed: Module D1 is reported once, by the
        # scientific engine, in the RICS/EN 15804 standard signed convention.
        _legacy_d = ("" if publication_mode else
                     f"Module D (legacy credit, separate) = −{results['module_d_tons']:,.1f} t · "
                     f"Net incl. Module D (supplementary) = {results['net_with_module_d_tons']:,.1f} t. ")
        st.caption(
            f"Gross modular A1-C4 LCA total = {results['gross_a1_c4_tons']:,.1f} t CO₂e · "
            f"GWP = {results['gwp_pkm_gross']:.5f} kg/pkm (gross, never net) · "
            + _legacy_d +
            "Each stage is independently toggleable; statuses are shown above."
        )
        if publication_mode:
            st.caption("Publication mode: Module D1 is reported separately by the scientific "
                       "engine in the RICS/EN 15804 standard signed convention (negative = "
                       "potential benefit; positive = potential load). There is no "
                       "'net incl. Module D' headline. The authoritative numbers are the "
                       "scientific-engine cards and Supplementary S1 above.")
        if not results.get('publication_grade_full_lca', True):
            st.error("🚫 Full-LCA result is NOT publication-grade (see FRP/EPD warning above).")

    if results['b2b5']['included']:
        with st.expander("🔁 B2–B5 activity & mass balance (Phase 3B)", expanded=False):
            bb = results['b2b5']
            mb1, mb2, mb3 = st.columns(3)
            with mb1: st.metric("B2 maintenance (t CO₂e)", f"{bb['b2_tons']:,.1f}")
            with mb2: st.metric("B4 replacement (t CO₂e)", f"{bb['b4_tons']:,.1f}")
            with mb3: st.metric("B2–B5 total (t CO₂e)", f"{bb['b2_b5_total_tons']:,.1f}")
            st.caption(f"LCCA maintenance mode: **{results['lcca_maint_mode']}** "
                       "(B4 replacement cost is added in both modes; routine maintenance never double-counted).")
            st.markdown("**Yearly B2–B5 activity** (years with activity only)")
            yb = pd.DataFrame(bb['yearly'])
            yb = yb[(yb['B2_count'] > 0) | (yb['B4_count'] > 0)]
            st.dataframe(yb, use_container_width=True, hide_index=True)
            st.markdown("**Material mass balance** (remaining feeds Phase 3C C1–C4; removed handled in B4/B5)")
            st.dataframe(pd.DataFrame(results['mass_balance']['mass_balance_by_material']),
                         use_container_width=True, hide_index=True)
            st.info("B2–B5 is an **activity-based scenario** and is not 'validated' unless project "
                    "maintenance/replacement records are supplied. Module D is unchanged by B2–B5 (deferred to Phase 3C).")

    if params.get('include_c1c4') and not results['eol_validation']['valid']:
        st.error("🚫 **C1–C4 not computed:** treatment shares do not sum to 1 for: "
                 + "; ".join(results['eol_validation']['errors'])
                 + ". Fix reuse/recycle shares (disposal = 1 − reuse − recycle). "
                 "publication_grade_full_lca is False.")

    if results['c1c4']['included']:
        with st.expander("♻️ C1–C4 End-of-Life & Module D (Phase 3C)", expanded=False):
            cc = results['c1c4']
            e1, e2, e3, e4, e5 = st.columns(5)
            with e1: st.metric("C1 deconstruction", f"{cc['c1_tons']:,.1f}")
            with e2: st.metric("C2 transport", f"{cc['c2_tons']:,.1f}")
            with e3: st.metric("C3 processing", f"{cc['c3_tons']:,.1f}")
            with e4: st.metric("C4 disposal", f"{cc['c4_tons']:,.1f}")
            with e5: st.metric("C1–C4 total", f"{cc['c1_c4_total_tons']:,.1f}")
            if publication_mode:
                # LEGACY-DEVELOPER-ONLY numbers. The canonical Module D1 figure is the
                # scientific standard-signed value on the Results cards (negative =
                # potential benefit); it is NOT restated here with a hand-written minus.
                g1, = st.columns(1)
                with g1: st.metric("Gross A1–C4 (legacy engine)",
                                   f"{results['gross_a1_c4_tons']:,.1f} t")
                st.caption("Legacy end-of-life view. Module D1 is reported by the scientific "
                           "engine above in the RICS/EN 15804 standard signed convention "
                           "(negative = potential benefit); it is never shown here as a "
                           "hand-signed legacy credit, and never folded into Gross A-C.")
            else:
                g1, g2, g3 = st.columns(3)
                with g1: st.metric("Gross A1–C4", f"{results['gross_a1_c4_tons']:,.1f} t")
                with g2: st.metric("Module D (legacy credit)", f"−{results['module_d_tons']:,.1f} t")
                with g3: st.metric("Net incl. Module D", f"{results['net_with_module_d_tons']:,.1f} t")
            st.markdown("**End-of-life by material** (on remaining masses after B4/B5)")
            st.dataframe(pd.DataFrame(cc['eol_by_material']), use_container_width=True, hide_index=True)
            st.markdown("**Module D by material** (recovery credit — separate, never in gross)")
            st.dataframe(pd.DataFrame(results['module_d_eol']['module_d_by_material']),
                         use_container_width=True, hide_index=True)
            if not results['module_d_quality_ok']:
                st.warning("⚠️ Module D is incomplete (a recovered material has no secondary EF). "
                           "The legacy end-of-life view is understated and is NOT publication-grade."
                           if publication_mode else
                           "⚠️ Module D is incomplete (a recovered material has no secondary EF). "
                           "Net incl. Module D is understated and is NOT publication-grade.")

    with st.expander("🏷️ Data Quality / Publication Readiness", expanded=False):
        dq = pd.DataFrame([
            {'Stage': 'A1–A3 materials', 'source': 'ICE V4.1 / EPD', 'quality': 'medium–high',
             'publication-grade': 'yes' if results.get('publication_grade', True) else 'NO (FRP w/o EPD)'},
            {'Stage': 'A4 transport', 'source': 'scenario / user input', 'quality': 'low–medium', 'publication-grade': 'conditional'},
            {'Stage': 'A5 construction', 'source': 'scenario / user input', 'quality': 'low–medium',
             'publication-grade': 'conditional' if results['a5']['included'] else 'n/a (off)'},
            {'Stage': 'B2–B5 use stage', 'source': 'activity schedule / scenario', 'quality': 'low–medium',
             'publication-grade': 'conditional' if results['b2b5']['included'] else 'n/a (off)'},
            {'Stage': 'B6 operation', 'source': f"{results['active_b6_mode']} scenario", 'quality': 'conditional',
             'publication-grade': 'not validated unless calibrated'},
            {'Stage': 'C1–C4 end-of-life', 'source': 'EOL scenario / project data', 'quality': 'low–medium',
             'publication-grade': 'conditional' if results['c1c4']['included'] else 'n/a (off)'},
            {'Stage': 'Module D', 'source': 'EOL recovery + secondary EF', 'quality': 'conditional',
             'publication-grade': 'only if secondary factors supplied'},
        ])
        st.dataframe(dq, use_container_width=True, hide_index=True)
        flag = results.get('publication_grade_full_lca', True)
        (st.success if flag else st.error)(
            f"publication_grade_full_lca = {flag} "
            + ("" if flag else "(FRP without EPD, invalid treatment shares, or incomplete Module D)."))

    # ── R15: Benefit KPIs (co-benefits) — reported SEPARATELY from the LCA ──
    # PUBLICATION SAFETY: Publication mode shows the referenced Benefits engine or it
    # shows the audit of what is missing. It NEVER falls back to the legacy KPIs,
    # because those collect a value with no unit contract, source, page or geography
    # and would appear beside sourced results as if they were equivalent.
    with st.expander("🌱 Benefit KPIs (societal co-benefits — separate from LCA carbon)", expanded=False):
        if publication_mode:
            render_scientific_benefits_panel(st, scientific_benefits, compact=True)
        else:
            bk = results['benefit_kpis']
            st.warning("🗄️ **Developer / legacy Benefit KPIs.** Numeric-only fields with no "
                       "source, page or geography behind them. They are NOT the Publication "
                       "Benefits result and must not be quoted as one.")
            st.caption(bk['note'])
            bk_df = pd.DataFrame([
                {'KPI': 'CO₂ avoided (annual)', 'Value': f"{bk['annual_co2_avoided_tons']:,.1f}", 'Unit': 't CO₂e/yr'},
                {'KPI': 'CO₂ avoided (lifetime)', 'Value': f"{bk['lifetime_co2_avoided_tons']:,.1f}", 'Unit': 't CO₂e'},
                {'KPI': 'Time saved (annual)', 'Value': f"{bk['annual_hours_saved']:,.0f}", 'Unit': 'h/yr'},
                {'KPI': 'Value of time saved (annual)', 'Value': f"{bk['annual_vots_musd']:,.2f}", 'Unit': '$M/yr'},
                {'KPI': 'Jobs supported (total)', 'Value': f"{bk['total_jobs']:,.0f}", 'Unit': 'jobs'},
                {'KPI': 'Economic impact', 'Value': f"{bk['economic_impact_musd']:,.0f}", 'Unit': '$M'},
                {'KPI': 'Land use', 'Value': f"{bk['land_ha_per_million_pkm']:,.3f}", 'Unit': 'ha / Mpkm·yr'},
                {'KPI': 'Noise reduction', 'Value': f"{bk['noise_reduction_db']:,.1f} ({bk['noise_reduction_ratio']*100:,.0f}%)", 'Unit': 'dB'},
            ])
            st.dataframe(bk_df, use_container_width=True, hide_index=True)
        st.info("These co-benefits are **not** part of the A1–C4 gross/net carbon and are never subtracted from it.")

    st.markdown("---")

    if not publication_mode:
        st.caption("Legacy dashboard scores & interaction network (interface-only) are hidden in Publication mode.")
        # Category Scores Comparison
        col_scores1, col_scores2 = st.columns(2)

        with col_scores1:
            st.markdown("#### 📊 Category Scores (Original vs Adjusted)")
            categories = ['Material', 'Environmental', 'Operational', 'Economic']
            original = [results['material_score'], results['environmental_score'],
                         results['operational_score'], results['economic_score']]
            adjusted = [results['adjusted_material_score'], results['adjusted_environmental_score'],
                         results['adjusted_operational_score'], results['adjusted_economic_score']]

            fig_scores = go.Figure()
            fig_scores.add_trace(go.Bar(name='Original', x=categories, y=original,
                                         marker_color='rgba(100, 149, 237, 0.7)',
                                         text=[f'{v:.1f}' for v in original], textposition='outside'))
            fig_scores.add_trace(go.Bar(name='Interaction-Adjusted', x=categories, y=adjusted,
                                         marker_color='rgba(100, 255, 218, 0.7)',
                                         text=[f'{v:.1f}' for v in adjusted], textposition='outside'))
            fig_scores.update_layout(
                barmode='group', height=400,
                plot_bgcolor='rgba(10,25,47,0.8)', paper_bgcolor='rgba(0,0,0,0)',
                font_color='#ccd6f6', yaxis_range=[0, 110],
                yaxis_title='Score (0-100)', margin=dict(t=30, b=30)
            )
            st.plotly_chart(fig_scores, use_container_width=True)

        with col_scores2:
            st.markdown("#### 🕸️ Dashboard Radar")
            fig_radar = go.Figure()
            fig_radar.add_trace(go.Scatterpolar(
                r=adjusted + [adjusted[0]],
                theta=categories + [categories[0]],
                fill='toself', fillcolor='rgba(100, 255, 218, 0.15)',
                line=dict(color='#64ffda', width=2), name='Adjusted'
            ))
            fig_radar.add_trace(go.Scatterpolar(
                r=original + [original[0]],
                theta=categories + [categories[0]],
                fill='toself', fillcolor='rgba(100, 149, 237, 0.1)',
                line=dict(color='#6495ed', width=2, dash='dash'), name='Original'
            ))
            fig_radar.update_layout(
                polar=dict(
                    bgcolor='rgba(10,25,47,0.8)',
                    radialaxis=dict(visible=True, range=[0, 100], gridcolor='rgba(255,255,255,0.1)'),
                    angularaxis=dict(gridcolor='rgba(255,255,255,0.1)')
                ),
                showlegend=True, height=400,
                paper_bgcolor='rgba(0,0,0,0)', font_color='#ccd6f6',
                margin=dict(t=30, b=30)
            )
            st.plotly_chart(fig_radar, use_container_width=True)

        # Interaction Analysis
        st.markdown("#### 🔄 Cross-Category Interaction Effects")
        effects = results['interaction_effects']

        int_col1, int_col2, int_col3 = st.columns(3)
        with int_col1:
            st.markdown(f"""
            <div class="info-box">
                <b>Synergy Effects</b><br>
                Total: <span class="interaction-synergy">{results['total_synergy']:.2f} pts</span><br>
                Ratio: <span class="interaction-synergy">{results['synergy_ratio']:.2f}</span>
            </div>""", unsafe_allow_html=True)
        with int_col2:
            st.markdown(f"""
            <div class="info-box">
                <b>Trade-off Effects</b><br>
                Total: <span class="interaction-tradeoff">{results['total_tradeoff']:.2f} pts</span><br>
                {"Synergies dominate ✅" if results['synergy_ratio'] > 1 else "Trade-offs dominate ⚠️"}
            </div>""", unsafe_allow_html=True)
        with int_col3:
            st.markdown(f"""
            <div class="info-box">
                <b>Dashboard Display Summary</b><br>
                Score: <b>{results['dashboard_display_score']:.1f}/100</b><br>
                {"Excellent 🎉" if results['dashboard_display_score'] >= 80 else ("Good 👍" if results['dashboard_display_score'] >= 60 else "Needs Improvement 📈")}
            </div>""", unsafe_allow_html=True)

        # Detailed interaction effects table
        with st.expander("📋 Detailed Interaction Effects", expanded=False):
            interaction_df = pd.DataFrame({
                'Interaction': ['Material → Environmental', 'Environmental → Operational',
                               'Operational → Economic', 'Economic → Material',
                               'Material → Operational', 'Environmental → Economic'],
                'Effect (pts)': [f"{effects['mat_env_effect']:+.2f}", f"{effects['env_op_effect']:+.2f}",
                                f"{effects['op_econ_effect']:+.2f}", f"{effects['econ_mat_effect']:+.2f}",
                                f"{effects['mat_op_effect']:+.2f}", f"{effects['env_econ_effect']:+.2f}"],
                'Type': ['Trade-off' if effects['mat_env_effect'] < 0 else 'Synergy',
                         'Trade-off' if effects['env_op_effect'] < 0 else 'Synergy',
                         'Trade-off' if effects['op_econ_effect'] < 0 else 'Synergy',
                         'Trade-off' if effects['econ_mat_effect'] < 0 else 'Synergy',
                         'Trade-off' if effects['mat_op_effect'] < 0 else 'Synergy',
                         'Trade-off' if effects['env_econ_effect'] < 0 else 'Synergy']
            })
            st.dataframe(interaction_df, use_container_width=True, hide_index=True)

    # Full Report Text
    with st.expander("📄 Full Assessment Report", expanded=False):
        # P2: dashboard-only renewable line is developer-only (hidden in publication mode).
        # Publication mode never emits a 'net incl. Module D' headline, even on the
        # legacy fallback path: Module D is reported separately, full stop.
        _legacy_net_line = ("" if publication_mode else
                            f"\n   • Net incl. Module D (supplementary): "
                            f"{results['net_with_module_d_tons']:.1f} tons")
        _renewable_line = ("" if publication_mode else
                           f"\n   • Renewable Share (dashboard-only, NOT applied to core LCA): {params['renewable_share']:.1f}%")
        _bk = results['benefit_kpis']
        _legacy_block = ""
        if not publication_mode:
            _legacy_block = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LEGACY DASHBOARD (non-scientific, interface-only)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Dashboard Display Score: {results['dashboard_display_score']:.1f}/100
Category (Material/Environmental/Operational/Economic): {results['material_score']:.1f} / {results['environmental_score']:.1f} / {results['operational_score']:.1f} / {results['economic_score']:.1f}
Synergy-to-Trade-off ratio: {results['synergy_ratio']:.2f}
"""
        report = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    ENHANCED MONORAIL LCA / LCCA ASSESSMENT RESULTS       ║
╚══════════════════════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🏗️ MATERIALS ASSESSMENT
   • Concrete Volume: {params['concrete']:.1f} thousand m³
   • Steel Mass: {params['steel']:.1f} thousand tons
   • Aluminum Mass: {params['aluminum']:.1f} thousand tons
   • Wood Volume: {params['wood']:.1f} thousand m³
   • FRP Mass: {params['frp']:.1f} thousand tons
   • Glass Area: {params['glass']:.1f} thousand m²
   • Steel Recycling Rate: {params['steel_recycle']:.1f}%
   • Aluminum Recycling Rate: {params['aluminum_recycle']:.1f}%

🌱 ENVIRONMENTAL ASSESSMENT
   • Annual Operational CO₂: {results['annual_co2_operational']:.1f} tons
   • Embodied CO₂ A1-A3 (GROSS): {results['total_embodied_co2']:.1f} tons
   • A4 Transport CO₂: {results['lca_results']['a4_transport_co2_tons']:.1f} tons
   • A5 Construction CO₂: {results['a5']['a5_total_tons']:.1f} tons ({'included' if results['a5']['included'] else 'not included'})
   • B2-B5 Use Stage CO₂: {results['i_b2b5_tons']:.1f} tons ({'included' if results['b2b5']['included'] else 'not included'})
   • B6 Operation ({results['active_b6_mode']}): {results['active_b6_tons']:.1f} tons
   • C1-C4 End-of-Life CO₂: {results['i_c1c4_tons']:.1f} tons ({'included' if results['c1c4']['included'] else 'not included'})
   • Gross modular A1-C4 LCA total (A1-A3 + A4 + A5 + B2-B5 + active B6 + C1-C4): {results['gross_a1_c4_tons']:.1f} tons
   • GWP per pkm (gross): {results['gwp_pkm_gross']:.6f} kg CO₂e/pkm
   • Module D recycling credit (separate, NOT in gross): -{results['module_d_tons']:.1f} tons{_legacy_net_line}
   • Grid Carbon Intensity (applied to core B6): {results['effective_carbon_intensity']:.3f} kg CO₂/kWh
   • Total Embodied Energy: {results['total_ee']:.0f} MJ{_renewable_line}

⚡ OPERATIONAL ASSESSMENT
   • Energy per Passenger-km: {params['energy_per_pax']:.3f} kWh
   • Daily Passenger-km: {params['daily_pax_km']:.1f} thousand
   • System Availability: {params['availability']:.1f}%

💰 ECONOMIC ASSESSMENT
   • Base CAPEX: ${results['construction_cost_base']:.1f} million
   • Contract factor: {results['contract_factor']:.2f}
   • CAPEX used in NPV: ${results['construction_cost']:.1f} million
   • Annual Maintenance: ${params['maintenance_cost']:.1f} million
   • Jobs supported (Benefit KPI, total): {_bk['total_jobs']:.0f}
   • 50-Year Maintenance (undiscounted): ${results['total_maintenance_cost']:.1f} million

{_legacy_block}
Assessment Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Methodology: Gross modular A1-C4 LCA (A1-A3 + A4 + optional A5 + activity-based B2-B5 + active B6 + optional C1-C4) + NPV-based LCCA.
Carbon factors: ICE Database Educational V4.1 (Oct 2025). Module D (recycling) reported separately per EN 15804. Li and Zhu (2022) is benchmark-only.
"""
        # PUBLICATION: the report + downloads are the canonical scientific output.
        if scientific_pub is not None:
            report = scientific_report_text(scientific_pub)
        st.code(report, language=None)

        # Export buttons
        exp1, exp2, exp3 = st.columns(3)
        with exp1:
            st.download_button("📥 Download Report (.txt)", report,
                              file_name=f"monorail_report_{datetime.now().strftime('%Y%m%d')}.txt",
                              mime="text/plain")
        with exp2:
            csv_rows = [
                {'Category': 'LCA', 'Metric': f"Gross modular A1-C4 LCA total (B6 {results['active_b6_mode']})", 'Value': f"{results['gross_a1_c4_tons']:.1f}", 'Unit': 'tons CO₂e'},
                {'Category': 'LCA', 'Metric': 'GWP per pkm (gross)', 'Value': f"{results['gwp_pkm_gross']:.6f}", 'Unit': 'kg CO₂e/pkm'},
                {'Category': 'LCA', 'Metric': 'Embodied CO₂ A1-A3 (gross)', 'Value': f"{results['lca_results']['embodied_co2_tons']:.1f}", 'Unit': 'tons CO₂e'},
                {'Category': 'LCA', 'Metric': 'A4 Transport CO₂', 'Value': f"{results['lca_results']['a4_transport_co2_tons']:.1f}", 'Unit': 'tons CO₂e'},
                {'Category': 'LCA', 'Metric': 'A5 Construction CO₂', 'Value': f"{results['a5']['a5_total_tons']:.1f}", 'Unit': 'tons CO₂e'},
                {'Category': 'LCA', 'Metric': 'B2-B5 Use Stage CO₂', 'Value': f"{results['i_b2b5_tons']:.1f}", 'Unit': 'tons CO₂e'},
                {'Category': 'LCA', 'Metric': 'C1-C4 End-of-Life CO₂', 'Value': f"{results['i_c1c4_tons']:.1f}", 'Unit': 'tons CO₂e'},
                {'Category': 'Module D', 'Metric': 'Recovery credit (separate)', 'Value': f"-{results['module_d_tons']:.1f}", 'Unit': 'tons CO₂e'},
                {'Category': 'LCA', 'Metric': 'Lifetime operational CO₂', 'Value': f"{results['lca_results']['lifetime_operational_co2_tons']:.1f}", 'Unit': 'tons CO₂e'},
                {'Category': 'LCA', 'Metric': 'Embodied Energy', 'Value': f"{results['total_ee']:.0f}", 'Unit': 'MJ'},
                {'Category': 'LCCA', 'Metric': 'LCC NPV Cost', 'Value': f"{results['npv_lcc_m']:.0f}", 'Unit': '$M'},
            ]
            if not publication_mode:
                csv_rows.append({'Category': 'Display-only', 'Metric': 'Dashboard Display Score', 'Value': f"{results['dashboard_display_score']:.1f}", 'Unit': '/100'})
            csv_data = (scientific_csv(scientific_pub) if scientific_pub is not None
                        else pd.DataFrame(csv_rows).to_csv(index=False))
            st.download_button("📥 Download CSV", csv_data,
                              file_name=f"monorail_data_{datetime.now().strftime('%Y%m%d')}.csv")
        with exp3:
            excel_buf = io.BytesIO()
            xl_metric = [
                f"Gross modular A1-C4 LCA total (B6 {results['active_b6_mode']})",
                'GWP per pkm (gross)', 'Embodied CO₂ A1-A3 (gross)', 'A4 Transport CO₂',
                'A5 Construction CO₂', 'B2-B5 Use Stage CO₂', 'B6 operation (active)',
                'C1-C4 End-of-Life CO₂', 'Module D (separate)',
                'Embodied Energy', 'LCC NPV Cost']
            xl_value = [
                results['gross_a1_c4_tons'], results['gwp_pkm_gross'], results['lca_results']['embodied_co2_tons'],
                results['lca_results']['a4_transport_co2_tons'], results['a5']['a5_total_tons'],
                results['i_b2b5_tons'], results['active_b6_tons'], results['i_c1c4_tons'],
                -results['module_d_tons'], results['total_ee'], results['npv_lcc_m']]
            xl_unit = ['tons CO₂e', 'kg CO₂e/pkm', 'tons CO₂e', 'tons CO₂e', 'tons CO₂e', 'tons CO₂e',
                       'tons CO₂e', 'tons CO₂e', 'tons CO₂e', 'MJ', '$M']
            # The legacy net-incl-D row is developer-only; Publication never exports it.
            if not publication_mode:
                xl_metric.insert(9, 'Net incl. Module D (supplementary)')
                xl_value.insert(9, results['net_with_module_d_tons'])
                xl_unit.insert(9, 'tons CO₂e')
            if not publication_mode:
                xl_metric.append('Dashboard Display Score'); xl_value.append(results['dashboard_display_score']); xl_unit.append('/100 display-only')
            with pd.ExcelWriter(excel_buf, engine='openpyxl') as writer:
                pd.DataFrame({'Metric': xl_metric, 'Value': xl_value, 'Unit': xl_unit}).to_excel(writer, sheet_name='Summary', index=False)
            _excel_out = (scientific_excel_bytes(scientific_pub) if scientific_pub is not None
                          else excel_buf.getvalue())
            st.download_button("📥 Download Excel", _excel_out,
                              file_name=f"monorail_report_{datetime.now().strftime('%Y%m%d')}.xlsx",
                              mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ═══════════════════════════════════════════════════════════════
# TAB: SCIENTIFIC LCA (REFERENCED, FULLY-SOURCED CORE)
# Parallel authoritative engine. Reports a publication-grade number ONLY when
# every required source is supplied; otherwise it lists the missing evidence
# instead of a fabricated value. It never overrides the legacy dashboard result.
# ═══════════════════════════════════════════════════════════════
if 'sci_lca' in TABS:
    with TABS['sci_lca']:
        st.markdown("### 🔬 Scientific LCA — fully referenced core")
        st.caption("Every factor and equation carries its source (file / row / status). "
                   "Waste factors are per-tonne, dynamic grid CI is per-year, and Module D is "
                   "reported separately. This engine runs alongside the dashboard and refuses to "
                   "report a publication-grade result while any required source is open.")
        try:
            scientific_lca = run_scientific_lca_from_app_params(params)
        except ScientificInputError as _sci_err:
            scientific_lca = None
            st.warning(f"🟡 **Source-open — no publication number yet:** {_sci_err}")
        except Exception as _sci_other:  # pragma: no cover - defensive
            scientific_lca = None
            st.error(f"Scientific core error: {_sci_other}")

        if scientific_lca is not None:
            _chk = scientific_lca.get("publication_checks", {})
            _partial = bool(scientific_lca.get("publication_grade_partial_scope", False))
            _full = bool(scientific_lca.get("publication_grade_full_wlca", False))
            _connected = scientific_lca.get("connected_stages", [])
            _unconnected = scientific_lca.get("unconnected_stages", [])
            _scope_label = scientific_lca.get("scope_label", "Scientific partial LCA")

            st.markdown(f"#### {_scope_label}")
            s1, s2, s3 = st.columns(3)
            with s1:
                st.metric("Partial LCA — connected scope (tCO₂e)",
                          f"{scientific_lca['connected_scope_tCO2e']:,.1f}")
            with s2:
                st.metric("GWP over connected scope (kgCO₂e / pkm)",
                          f"{scientific_lca['GWP_kgCO2e_per_pkm']:.5f}")
            with s3:
                st.metric("Module D (tCO₂e, separate)", f"{scientific_lca['module_D1_signed_tCO2e_separate']:,.1f}")
            _incomplete = scientific_lca.get("incomplete_source_stages", [])
            st.caption(f"**Connected stages:** {', '.join(_connected)}. "
                       f"**Not yet connected (reported as 0 because unwired, NOT because negligible):** "
                       f"{', '.join(_unconnected) if _unconnected else 'none'}. "
                       "This is NOT a full Gross A–C until every stage is wired. Module D is "
                       "supplementary and is NEVER added to or subtracted from the headline.")

            _sstat = scientific_lca.get("stage_status", {})
            _STATUS_ICON = {"connected": "🟢", "not_applicable": "⚪", "unconnected": "⚫",
                            "incomplete_sources": "🟡", "validation_failed": "🔴"}
            st.markdown("#### Stage connection status")
            _stat_df = pd.DataFrame(
                [{"stage": s, "status": _sstat[s], "": _STATUS_ICON.get(_sstat[s], "")}
                 for s in _sstat])
            st.dataframe(_stat_df, use_container_width=True, hide_index=True)
            if _incomplete:
                st.warning("🟡 **Entered but EXCLUDED for missing sources (not a measured zero):** "
                           + ", ".join(_incomplete) + ". See stage notes below.")
            for _stg in ("A4", "A5"):
                _mod = scientific_lca.get("modules", {}).get(_stg.replace("-", "_"))
                if isinstance(_mod, dict) and _mod.get("note"):
                    st.caption(f"{_stg} note: {_mod['note']}")

            # Reported vs diagnostic: computed carbon of a non-connected stage is NEVER in the headline.
            _excl = scientific_lca.get("excluded_from_reported", {})
            if _excl:
                st.error("⚠️ **Excluded from the reported headline** (computed but the stage is not "
                         "'connected', so it does NOT enter the reported total): "
                         + ", ".join(f"{k} = {v:,.1f} tCO₂e" for k, v in _excl.items()))
            with st.expander("🧪 Reported vs diagnostic per-stage totals", expanded=False):
                _diag = scientific_lca.get("diagnostic_stage_tco2e", {})
                _rep = scientific_lca.get("reported_stage_tco2e", {})
                st.dataframe(pd.DataFrame([
                    {"stage": s, "status": _sstat.get(s, "?"),
                     "diagnostic_tCO2e": _diag.get(s, 0.0), "reported_tCO2e": _rep.get(s, 0.0)}
                    for s in _diag]), use_container_width=True, hide_index=True)
            st.caption(f"**Grid CI basis:** {scientific_lca.get('grid_basis', '?')}.")

            st.markdown(f"**Partial-scope grade:** "
                        f"{'🟢 sourced' if _partial else '🟡 sources open'} (connected stages only)")
            _gate = scientific_lca.get("closure_gate", {})
            g1, g2, g3 = st.columns(3)
            with g1:
                st.markdown(f"**Full-WLCA calculation:** "
                            f"{'🟢' if _gate.get('full_wlca_calculation_complete') else '🔴'} "
                            f"{_gate.get('full_wlca_calculation_complete', False)}")
            with g2:
                st.markdown(f"**Standards reporting:** "
                            f"{'🟢' if _gate.get('standards_reporting_complete') else '🔴'} "
                            f"{_gate.get('standards_reporting_complete', False)}")
            with g3:
                st.markdown(f"**Q1 evidence ready:** "
                            f"{'🟢' if _gate.get('q1_evidence_ready') else '🔴'} "
                            f"{_gate.get('q1_evidence_ready', False)}")
            st.caption("Three-level gate: calculation-complete (all A1-C4 connected/N-A, mass "
                       "balance ok) → standards-complete (all sources documented, Module D "
                       "separate) → Q1-ready (project-specific annual data + uncertainty). Currently "
                       "False by design until B2-B5/C1-C4 are wired and project data supplied.")
            for _iss in _chk.get("issues", []):
                st.markdown(f"- 🔴 {_iss}")
            for _warn in _chk.get("warnings", []):
                st.markdown(f"- 🟠 {_warn}")

            _pr = scientific_lca.get("publication_readiness", {})
            if _pr:
                with st.expander("✅ Publication readiness gate (method / activity / factors / mass / "
                                 "applicability / project-specific / uncertainty)", expanded=False):
                    st.dataframe(pd.DataFrame(
                        [{"criterion": k, "value": v} for k, v in _pr.items()]),
                        use_container_width=True, hide_index=True)

            st.markdown("#### Stage contribution (connected scope)")
            st.dataframe(pd.DataFrame(scientific_lca['stage_contribution']),
                         use_container_width=True, hide_index=True)

            _a4mod = scientific_lca.get("modules", {}).get("A4", {})
            if _a4mod.get("by_material") or _a4mod.get("by_mode") or _a4mod.get("activity_audit"):
                with st.expander("🚚 A4 breakdown + activity-data audit", expanded=False):
                    if _a4mod.get("by_material"):
                        st.markdown("**Per material (tCO₂e)**")
                        st.dataframe(pd.DataFrame(
                            [{"material": k, "tCO2e": v} for k, v in _a4mod["by_material"].items()]),
                            use_container_width=True, hide_index=True)
                    if _a4mod.get("by_mode"):
                        st.markdown("**Per mode (tCO₂e)**")
                        st.dataframe(pd.DataFrame(
                            [{"mode": k, "tCO2e": v} for k, v in _a4mod["by_mode"].items()]),
                            use_container_width=True, hide_index=True)
                    if _a4mod.get("activity_audit"):
                        st.markdown("**Activity-data audit (per leg: mass/distance source, "
                                    "payload & return assumption)**")
                        st.dataframe(pd.DataFrame(_a4mod["activity_audit"]),
                                     use_container_width=True, hide_index=True)

            _a5mod = scientific_lca.get("modules", {}).get("A5", {})
            if _a5mod.get("total_tco2e", 0.0) or _a5mod.get("status") in ("connected", "incomplete_sources"):
                with st.expander("🏗️ A5 — RICS subdivision (A5.1–A5.4) + component detail", expanded=False):
                    _rics = _a5mod.get("rics_subdivision", {})
                    _pre = _rics.get("A5.1_preconstruction_demolition", {})
                    _wrk = _rics.get("A5.4_worker_transport", {})
                    st.dataframe(pd.DataFrame([
                        {"RICS module": "A5.1 pre-construction demolition",
                         "tCO2e / status": f"{_pre.get('status','?')} — {_pre.get('justification','')}"},
                        {"RICS module": "A5.2 construction activities (fuel + electricity)",
                         "tCO2e / status": f"{_rics.get('A5.2_construction_activities_tco2e', 0.0):,.2f}"},
                        {"RICS module": "A5.3 waste management (production + transport + treatment)",
                         "tCO2e / status": f"{_rics.get('A5.3_waste_management_tco2e', 0.0):,.2f}"},
                        {"RICS module": "A5.4 worker transport (optional)",
                         "tCO2e / status": _wrk.get("status", "?")},
                        {"RICS module": "A5 total",
                         "tCO2e / status": f"{_a5mod.get('total_tco2e', 0.0):,.2f}"},
                    ]), use_container_width=True, hide_index=True)
                    st.markdown("**Component detail (A5.2 / A5.3 breakdown)**")
                    st.dataframe(pd.DataFrame([
                        {"component": "A5.2 site fuel", "tCO2e": _a5mod.get("fuel_tco2e", 0.0)},
                        {"component": "A5.2 site electricity (construction-year CI)", "tCO2e": _a5mod.get("electricity_tco2e", 0.0)},
                        {"component": "A5.3 waste production", "tCO2e": _a5mod.get("extra_waste_product_tco2e", 0.0)},
                        {"component": "A5.3 waste transport", "tCO2e": _a5mod.get("waste_transport_tco2e", 0.0)},
                        {"component": "A5.3 waste treatment", "tCO2e": _a5mod.get("waste_treatment_tco2e", 0.0)},
                    ]), use_container_width=True, hide_index=True)
                    _a5rd = _a5mod.get("component_readiness", {})
                    if _a5rd:
                        st.markdown("**A5 component readiness**")
                        st.dataframe(pd.DataFrame(
                            [{"component": k, "readiness": v} for k, v in _a5rd.items()]),
                            use_container_width=True, hide_index=True)

            _mb = scientific_lca.get("mass_balance", {}).get("rows")
            if _mb:
                with st.expander("⚖️ Mass balance (B4/B5 → remaining for C1-C4)", expanded=False):
                    st.dataframe(pd.DataFrame(_mb), use_container_width=True, hide_index=True)

            render_lca_audit_streamlit(st, scientific_lca)

            # ── Canonical scientific exports (cards == CSV == Excel by construction) ──
            st.markdown("#### 📤 Canonical exports (scientific engine — authoritative)")
            _parity = export_parity_ok(scientific_lca)
            st.caption(f"Export parity (cards == CSV == Excel Summary): "
                       f"{'🟢 pass' if _parity else '🔴 fail'}. These downloads are the "
                       "publication record; the legacy Results tab is illustrative only.")
            st.code(scientific_report_text(scientific_lca))
            _e1, _e2 = st.columns(2)
            with _e1:
                st.download_button("📥 Scientific CSV", scientific_csv(scientific_lca),
                                   file_name=f"scientific_lca_{datetime.now().strftime('%Y%m%d')}.csv",
                                   mime="text/csv", key="sci_csv_dl")
            with _e2:
                st.download_button("📥 Supplementary S1 (Excel, 15 sheets)",
                                   scientific_excel_bytes(scientific_lca),
                                   file_name=f"supplementary_S1_{datetime.now().strftime('%Y%m%d')}.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                   key="sci_xlsx_dl")
        else:
            st.info("This referenced engine is intentionally strict. Provide the sourced inputs in the "
                    "sidebar expander **🔬 Scientific LCA provenance (referenced core)** to unlock it: "
                    "densities + sources, BOQ source, passenger-km source, RSP source, the annual "
                    "Egypt/project grid CI (generation + T&D + upstream) with its source, and the B6 "
                    "energy-intensity basis.")
            with st.expander("📋 Still-open evidence register (what unlocks a publication number)", expanded=False):
                _open_rows = [{"item": k, **v} for k, v in OPEN_SOURCE_REQUIREMENTS.items()]
                st.dataframe(pd.DataFrame(_open_rows), use_container_width=True, hide_index=True)
            st.caption("A1-A3, A4, A5 and B6 are wired to the referenced core now. B2-B5 and C1-C4 "
                       "scientific legs are the next integration increments; until then they report "
                       "0 as UNCONNECTED (not negligible), and full-WLCA grade stays False.")


# ═══════════════════════════════════════════════════════════════
# TAB: SCIENTIFIC BENEFITS (REFERENCED)
# ───────────────────────────────────────────────────────────────
# The reviewer's audit view. From any number on this tab it is possible to reach
# the equation id, the equation record, the source document, and the exact page —
# without leaving the application.
# ═══════════════════════════════════════════════════════════════
with TABS['sci_benefits']:
    st.markdown("### 🌱 Scientific Benefits (referenced core)")
    st.caption(
        "Societal co-benefits computed from equations that each carry a registered "
        "source, using inputs that each carry their own numeric evidence. A method "
        "reference authorises the formula; it never certifies a project number."
    )

    render_scientific_benefits_panel(st, scientific_benefits)

    st.markdown("---")
    st.markdown("#### 🔎 Full KPI audit")
    _all_rows = scientific_benefits.rows
    st.dataframe(benefit_rows_dataframe(_all_rows), use_container_width=True, hide_index=True)

    with st.expander("📐 Equation registry — every equation and its exact source", expanded=False):
        st.dataframe(
            pd.DataFrame([
                {
                    "Equation": eq.equation_id,
                    "Name": eq.name,
                    "Formula": eq.formula_text,
                    "Unit contract": eq.output_unit_contract,
                    "Method sources": "; ".join(eq.method_ref_ids),
                    "Exact location": " | ".join(eq.exact_source_locations),
                    "Numeric evidence required": "; ".join(eq.required_numeric_evidence),
                    "Limitations": eq.limitations,
                }
                for eq in BENEFITS_EQUATIONS.values()
            ]),
            use_container_width=True, hide_index=True,
        )

    with st.expander("📚 Reference registry — open the original document", expanded=False):
        st.dataframe(
            pd.DataFrame([
                {
                    "Ref": ref.ref_id,
                    "Title": ref.title,
                    "Authors / issuer": ref.authors_or_issuer,
                    "Year": ref.year,
                    "Exact location": ref.exact_location,
                    "DOI": ref.doi,
                    "Official URL": ref.official_url,
                    "Geography": ref.geography,
                    "Evidence role": ref.evidence_role,
                    "Limitations": ref.limitations,
                }
                for ref in BENEFITS_REFERENCES.values()
            ]),
            use_container_width=True, hide_index=True,
        )
        st.caption(
            "Evidence status here describes source AUTHORITY, geography and "
            "traceability. It is not a journal-ranking claim."
        )

    with st.expander("🧾 Double-count rules enforced by this domain", expanded=False):
        for _rule in scientific_benefits.audit["double_count_rules"]:
            st.markdown(f"- {_rule}")

    # ── Exports ───────────────────────────────────────────────────────────
    # The exports carry more provenance columns than the screen does, because a
    # reviewer working from a spreadsheet cannot click through to the registry.
    st.markdown("---")
    st.markdown("#### 📤 Traceable exports")
    _ben_parity_ok, _ben_parity_problems = benefits_export_parity_ok(scientific_benefits)
    # FAIL CLOSED. If the exports disagree with the computed result, the exports
    # are the thing that leaves the building and gets cited, so they are withheld
    # rather than offered with a warning above them.
    if _ben_parity_ok:
        st.caption("Export parity verified: every exported row matches the computed "
                   "result, and every publication-eligible value resolves to a "
                   "registered equation and a numeric source.")
        _ben_cols = st.columns(3)
        with _ben_cols[0]:
            st.download_button(
                "⬇️ Benefits CSV (full provenance)",
                data=scientific_benefits_csv(scientific_benefits),
                file_name="scientific_benefits.csv", mime="text/csv",
                key="sci_ben_csv_dl")
        with _ben_cols[1]:
            st.download_button(
                "⬇️ Benefits Excel (8 sheets)",
                data=scientific_benefits_excel_bytes(scientific_benefits),
                file_name="scientific_benefits.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="sci_ben_xlsx_dl")
        with _ben_cols[2]:
            st.download_button(
                "⬇️ Source appendix (text)",
                data=scientific_benefits_source_appendix(scientific_benefits),
                file_name="scientific_benefits_source_appendix.txt", mime="text/plain",
                key="sci_ben_appendix_dl")
    else:
        st.error("Export parity FAILED — downloads are **withheld**. The exports "
                 "disagree with the computed result, and an export is what gets "
                 "cited after it leaves this screen:")
        for _problem in _ben_parity_problems[:10]:
            st.markdown(f"- {_problem}")


# ═══════════════════════════════════════════════════════════════
# TAB 2: BENCHMARK / REPRODUCTION CHECK
# ═══════════════════════════════════════════════════════════════
with TABS['benchmark']:
    st.markdown("### 🔬 Benchmark / Reproduction Check Against Li and Zhu (2022)")
    st.markdown("""
    External comparison with a peer-reviewed monorail LCA study.
    **Benchmark:** Li and Zhu (2022) — Computational Intelligence and Neuroscience — DOI: 10.1155/2022/3872069
    """)
    st.warning(
        "⚠️ This is a **benchmark / reproduction check — NOT an independent validation.** "
        "The default material quantities reproduce the benchmark per-km intensities, so close agreement on "
        "material/energy totals is expected *by construction* and does not validate the model. "
        "Li and Zhu (2022) is used **only** as an external benchmark; it is **never** a source of material "
        "carbon factors (those come from the ICE Database Educational V4.1, Oct 2025)."
    )

    system_length_km = 96
    bench_total_concrete = LIZHU_2022_BENCHMARK['material_intensity_per_km']['concrete_m3'] * system_length_km
    bench_total_steel = LIZHU_2022_BENCHMARK['material_intensity_per_km']['steel_tons'] * system_length_km
    bench_total_aluminum = LIZHU_2022_BENCHMARK['material_intensity_per_km']['aluminum_tons'] * system_length_km
    bench_embodied_energy_total = LIZHU_2022_BENCHMARK['embodied_impact_per_km']['energy_GJ'] * system_length_km
    bench_embodied_carbon_total = LIZHU_2022_BENCHMARK['embodied_impact_per_km']['carbon_tons_CO2'] * system_length_km
    bench_operational_energy = LIZHU_2022_BENCHMARK['operational_performance']['energy_kwh_per_pkm']
    bench_operational_carbon = LIZHU_2022_BENCHMARK['operational_performance']['carbon_kgCO2_per_pkm']

    your_embodied_energy_GJ = results['total_ee'] / 1000.0
    your_operational_carbon_raw = results['energy_per_pax_km'] * results['effective_carbon_intensity']

    def get_status(your_val, bench_val):
        if bench_val == 0:
            return 'n/a (zero benchmark)', 'poor'
        err = abs((your_val - bench_val) / bench_val * 100)
        if err < 10: return '✓ Excellent', 'excellent'
        elif err < 20: return '~ Good', 'good'
        else: return '✗ Review', 'poor'

    comparisons = [
        ('Total Concrete (m³)', bench_total_concrete, results['concrete_volume']),
        ('Total Steel (tons)', bench_total_steel, results['steel_tons']),
        ('Total Aluminum (tons)', bench_total_aluminum, results['aluminum_tons']),
        ('Embodied Energy (GJ)', bench_embodied_energy_total, your_embodied_energy_GJ),
        ('Embodied Carbon (tons CO₂)', bench_embodied_carbon_total, results['total_embodied_co2']),
        ('Energy Intensity (kWh/pkm)', bench_operational_energy, results['energy_per_pax_km']),
        ('Carbon Intensity (kg CO₂/pkm)', bench_operational_carbon, your_operational_carbon_raw),
    ]

    bench_data = []
    excellent_count = good_count = review_count = 0
    for metric, bench_val, your_val in comparisons:
        error_pct = abs((your_val - bench_val) / bench_val * 100) if bench_val != 0 else 0
        status, tag = get_status(your_val, bench_val)
        if tag == 'excellent': excellent_count += 1
        elif tag == 'good': good_count += 1
        else: review_count += 1
        bench_data.append({
            'Metric': metric,
            'Li & Zhu 2022': f"{bench_val:,.2f}" if bench_val < 100 else f"{bench_val:,.0f}",
            'Your Tool': f"{your_val:,.2f}" if your_val < 100 else f"{your_val:,.0f}",
            'Difference': f"{your_val - bench_val:+,.2f}" if abs(your_val) < 100 else f"{your_val - bench_val:+,.0f}",
            'Error %': f"{error_pct:.1f}%",
            'Status': status
        })

    bench_df = pd.DataFrame(bench_data)
    st.dataframe(bench_df, use_container_width=True, hide_index=True)

    total_metrics = excellent_count + good_count + review_count
    agreement_rate = (excellent_count + good_count) / total_metrics * 100 if total_metrics > 0 else 0

    vc1, vc2, vc3, vc4 = st.columns(4)
    with vc1: st.metric("✓ Excellent (<10%)", excellent_count)
    with vc2: st.metric("~ Good (<20%)", good_count)
    with vc3: st.metric("✗ Review (>20%)", review_count)
    with vc4: st.metric("Reproduction Agreement", f"{agreement_rate:.0f}%",
                        help="Agreement with Li and Zhu (2022) totals — reproduction check, not independent validation.")


# ═══════════════════════════════════════════════════════════════
# TAB 3: PARETO OPTIMIZATION
# ═══════════════════════════════════════════════════════════════
if 'pareto' in TABS:
    with TABS['pareto']:
        st.markdown("### 🎯 Multi-Objective Optimization: Pareto Front Analysis")
        st.warning("Illustrative synthetic scenario visualization; not used in the scientific LCA/LCCA results.")
        st.markdown("Visualize trade-offs between Environmental Impact, Economic Cost, and Technical Performance.")

        if st.button("🔄 Generate Pareto Front", key="pareto_btn"):
            np.random.seed(42)
            n_solutions = 100

            base_co2 = results['total_co2']
            base_cost = results.get('total_cost', base_co2 * 0.01)
            base_score = results.get('dashboard_display_score', 75)

            co2_values = base_co2 * np.random.uniform(0.85, 1.15, n_solutions)
            cost_values = base_cost * np.random.uniform(0.80, 1.20, n_solutions)
            score_values = base_score * np.random.uniform(0.90, 1.10, n_solutions)

            # Identify Pareto-optimal
            pareto_mask = np.ones(n_solutions, dtype=bool)
            for i in range(n_solutions):
                if not pareto_mask[i]: continue
                for j in range(n_solutions):
                    if i == j: continue
                    if (co2_values[j] <= co2_values[i] and cost_values[j] <= cost_values[i] and
                        score_values[j] >= score_values[i] and
                        (co2_values[j] < co2_values[i] or cost_values[j] < cost_values[i] or score_values[j] > score_values[i])):
                        pareto_mask[i] = False
                        break

            fig = go.Figure()
            fig.add_trace(go.Scatter3d(
                x=co2_values[pareto_mask], y=cost_values[pareto_mask] / 1e6,
                z=score_values[pareto_mask], mode='markers',
                marker=dict(size=10, color=score_values[pareto_mask], colorscale='Viridis',
                           showscale=True, colorbar=dict(title="Score"), line=dict(color='gold', width=2)),
                name='Pareto Optimal',
                text=[f'CO₂: {c/1000:.1f}k<br>Cost: ${co/1e6:.2f}M<br>Score: {s:.1f}'
                      for c, co, s in zip(co2_values[pareto_mask], cost_values[pareto_mask], score_values[pareto_mask])],
                hoverinfo='text'
            ))
            fig.add_trace(go.Scatter3d(
                x=co2_values[~pareto_mask], y=cost_values[~pareto_mask] / 1e6,
                z=score_values[~pareto_mask], mode='markers',
                marker=dict(size=5, color='lightgray', opacity=0.3), name='Dominated'
            ))
            fig.add_trace(go.Scatter3d(
                x=[base_co2], y=[base_cost / 1e6], z=[base_score], mode='markers',
                marker=dict(size=15, color='red', symbol='diamond', line=dict(color='darkred', width=3)),
                name='Current Solution'
            ))
            fig.update_layout(
                title='3D Pareto Front: Environmental vs Economic vs Performance',
                scene=dict(
                    xaxis=dict(title='CO₂ (tons)', backgroundcolor='white'),
                    yaxis=dict(title='Cost ($M)', backgroundcolor='white'),
                    zaxis=dict(title='Score', backgroundcolor='white'),
                    camera=dict(eye=dict(x=1.5, y=1.5, z=1.3))
                ),
                height=700, paper_bgcolor='white', plot_bgcolor='white'
            )
            st.plotly_chart(fig, use_container_width=True)

            n_pareto = np.sum(pareto_mask)
            st.success(f"Found {n_pareto} Pareto-optimal solutions out of {n_solutions} evaluated.")


# ═══════════════════════════════════════════════════════════════
# TAB 4: 12-ELEMENT ANALYSIS (Parallel Coordinates)
# ═══════════════════════════════════════════════════════════════
if 'twelve' in TABS:
    with TABS['twelve']:
        st.warning("Illustrative synthetic scenario visualization; not used in the scientific LCA/LCCA results.")
        st.markdown("### 📈 Parallel Coordinates: 12 Illustrative Dashboard Elements")

        if st.button("📊 Generate Parallel Coordinates", key="parallel_btn"):
            np.random.seed(42)
            n_scenarios = 20
            scenarios_data = []
            for i in range(n_scenarios):
                variation = np.random.uniform(0.9, 1.1)
                scenario = {
                    'Concrete Impact': float(np.clip(100 - (results['concrete_volume'] / 10000) * variation, 0, 100)),
                    'Steel Impact': float(np.clip(100 - (results['steel_mass'] / 1500) * variation, 0, 100)),
                    'Aluminum Impact': float(np.clip(100 - (results['aluminum_mass'] / 75) * variation, 0, 100)),
                    'Embodied Energy': float(np.clip(100 - (results['total_ee'] / 100000) * variation, 0, 100)),
                    'Carbon Emissions': float(np.clip(100 - (results['total_co2'] / 4000) * variation, 0, 100)),
                    'Water Consumption': float(np.clip(np.random.uniform(60, 85) * variation, 0, 100)),
                    'Op. Efficiency': float(np.clip(np.random.uniform(70, 95) * variation, 0, 100)),
                    'Maintenance': float(np.clip(np.random.uniform(65, 90) * variation, 0, 100)),
                    'Safety Rating': float(np.clip(np.random.uniform(80, 98) * variation, 0, 100)),
                    'Economic Viability': float(np.clip(np.random.uniform(60, 85) * variation, 0, 100)),
                    'Social Impact': float(np.clip(np.random.uniform(55, 80) * variation, 0, 100)),
                    'Lifecycle Cost': float(np.clip(100 - (results.get('total_cost', 2500) / 40) * variation, 0, 100))
                }
                scenarios_data.append(scenario)

            df = pd.DataFrame(scenarios_data)
            df['Composite_Display_Score'] = df.mean(axis=1)

            dimensions = [dict(label=col, values=df[col], range=[0, 100]) for col in df.columns[:-1]]

            fig = go.Figure(data=go.Parcoords(
                line=dict(color=df['Composite_Display_Score'], colorscale='RdYlGn', showscale=True, cmin=0, cmax=100,
                         colorbar=dict(title="Composite<br>Display Score", thickness=20)),
                dimensions=dimensions
            ))
            fig.update_layout(title='12 Illustrative Dashboard Elements Across Scenarios', height=700, paper_bgcolor='white')
            st.plotly_chart(fig, use_container_width=True)

            best = df[df.columns[:-1]].mean().nlargest(3)
            worst = df[df.columns[:-1]].mean().nsmallest(3)
            bc1, bc2 = st.columns(2)
            with bc1:
                st.markdown("**🏆 Top Performing Elements:**")
                for i, (name, val) in enumerate(best.items()): st.write(f"{i+1}. {name}: {val:.1f}/100")
            with bc2:
                st.markdown("**⚠️ Needs Improvement:**")
                for i, (name, val) in enumerate(worst.items()): st.write(f"{i+1}. {name}: {val:.1f}/100")


# ═══════════════════════════════════════════════════════════════
# TAB 5: UNCERTAINTY ANALYSIS (Monte Carlo)
# ═══════════════════════════════════════════════════════════════
with TABS['uncertainty']:
    st.markdown("### 🎲 Phase 4 — Component-based Monte Carlo Uncertainty")
    st.caption("Each uncertain input is sampled from its own distribution and the full A1–C4 model is "
               "re-run, so uncertainty propagates per component while gross = Σ stages, net = gross − Module D, "
               "and GWP/pkm = gross/pkm hold in every draw. No total-scaling.")

    cmc1, cmc2, cmc3 = st.columns(3)
    with cmc1:
        mc_enable = st.checkbox("Enable Phase 4 MC", value=False, key="mc_enable")
        mc_n = st.number_input("n simulations", value=5000, min_value=100, max_value=20000, step=500, key="mc_n")
    with cmc2:
        mc_seed = st.number_input("random seed", value=42, min_value=0, step=1, key="mc_seed")
        st.caption("Sampling: Latin Hypercube + Dirichlet (shares).")
    with cmc3:
        st.caption("Publication-grade uncertainty requires n ≥ 5000 and convergence_ok.")

    if mc_enable:
        @st.cache_data(show_spinner=True)
        def _run_mc(params_tuple, n, seed):
            return run_component_monte_carlo(dict(params_tuple), n=int(n), seed=int(seed))
        mcres = _run_mc(tuple(sorted(params.items())), mc_n, mc_seed)
        st.session_state['phase4_pgu'] = bool(mcres['publication_grade_uncertainty'])
        sm = mcres['summary'].set_index('metric')
        g = sm.loc['gross_a1_c4_tons']
        st.success(f"Gross A1–C4: mean {g['mean']:,.0f} t · 95% uncertainty interval "
                   f"[{g['P2.5']:,.0f}, {g['P97.5']:,.0f}] t · CV {g['CV']*100:.1f}% "
                   f"({mcres['n_ok']}/{mcres['n']} valid runs).")
        flag = mcres['publication_grade_uncertainty']
        (st.success if flag else st.warning)(
            f"publication_grade_uncertainty = {flag}. "
            + ("" if flag else "Requires publication-grade full LCA, n ≥ 5000, and convergence_ok."))
        st.warning("Intervals are **scenario-based uncertainty intervals**, not measured statistical "
                   "confidence intervals (most distributions are scenario assumptions).")

        st.markdown("#### Stage & metric uncertainty (95% interval)")
        disp = mcres['summary'].copy()
        for c in ['mean', 'median', 'std', 'P2.5', 'P50', 'P97.5', 'min', 'max']:
            disp[c] = disp[c].map(lambda v: f"{v:,.3f}" if abs(v) < 10 else f"{v:,.0f}")
        disp['CV'] = mcres['summary']['CV'].map(lambda v: f"{v*100:.1f}%")
        st.dataframe(disp[['metric', 'mean', 'P2.5', 'P50', 'P97.5', 'CV']], use_container_width=True, hide_index=True)

        h1, h2 = st.columns(2)
        okrows = mcres['outputs'][~mcres['outputs']['failed']]
        with h1:
            fig = go.Figure(go.Histogram(x=okrows['gross_a1_c4_tons'] / 1000.0, nbinsx=50,
                                         marker=dict(color='rgba(100,255,218,0.6)')))
            fig.add_vline(x=g['P2.5']/1000, line_dash="dash", line_color="#ff6b6b")
            fig.add_vline(x=g['P97.5']/1000, line_dash="dash", line_color="#ff6b6b")
            fig.update_layout(title='Gross A1–C4 (k tCO₂e)', height=340, paper_bgcolor='rgba(0,0,0,0)',
                              plot_bgcolor='rgba(10,25,47,0.8)', font_color='#ccd6f6', margin=dict(t=40, b=30))
            st.plotly_chart(fig, use_container_width=True)
        with h2:
            fig = go.Figure(go.Histogram(x=okrows['gwp_pkm_gross'], nbinsx=50,
                                         marker=dict(color='rgba(100,149,237,0.6)')))
            fig.update_layout(title='GWP per pkm (gross)', height=340, paper_bgcolor='rgba(0,0,0,0)',
                              plot_bgcolor='rgba(10,25,47,0.8)', font_color='#ccd6f6', margin=dict(t=40, b=30))
            st.plotly_chart(fig, use_container_width=True)

        h3, h4 = st.columns(2)
        with h3:
            # LEGACY-DEVELOPER-ONLY. Publication mode never plots a net-including-D
            # distribution: Module D is reported separately, never combined into a headline.
            if not publication_mode:
                fig = go.Figure(go.Histogram(x=okrows['net_with_module_d_tons'] / 1000.0, nbinsx=50,
                                             marker=dict(color='rgba(247,151,30,0.6)')))
                fig.update_layout(title='Net incl. Module D (k tCO₂e, supplementary)', height=340,
                                  paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(10,25,47,0.8)',
                                  font_color='#ccd6f6', margin=dict(t=40, b=30))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.caption("Module D is reported separately (standard signed); no "
                           "net-including-D distribution is shown in Publication mode.")
        with h4:
            fig = go.Figure(go.Histogram(x=okrows['npv_lcc_m'], nbinsx=50,
                                         marker=dict(color='rgba(150,201,61,0.6)')))
            fig.update_layout(title='LCC NPV ($M)', height=340, paper_bgcolor='rgba(0,0,0,0)',
                              plot_bgcolor='rgba(10,25,47,0.8)', font_color='#ccd6f6', margin=dict(t=40, b=30))
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("#### Uncertainty drivers (Spearman tornado, target = gross A1–C4)")
        drv = mcres['drivers'].head(12)
        figd = go.Figure(go.Bar(x=drv['spearman_rho'], y=drv['parameter'], orientation='h',
                                marker_color=['#ff6b6b' if v > 0 else '#64ffda' for v in drv['spearman_rho']]))
        figd.update_layout(title='Top drivers (Spearman ρ)', height=420, paper_bgcolor='rgba(0,0,0,0)',
                           plot_bgcolor='rgba(10,25,47,0.8)', font_color='#ccd6f6',
                           yaxis=dict(autorange='reversed'), margin=dict(t=40, b=30))
        st.plotly_chart(figd, use_container_width=True)

        cv = mcres['convergence']
        if len(cv['running_mean']):
            figc = go.Figure(go.Scatter(y=cv['running_mean'] / 1000.0, mode='lines', line=dict(color='#64ffda')))
            figc.update_layout(title=f"Convergence — running mean (ok={cv['convergence_ok']})", height=320,
                               paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(10,25,47,0.8)',
                               font_color='#ccd6f6', xaxis_title='run', yaxis_title='mean gross (k t)', margin=dict(t=40, b=30))
            st.plotly_chart(figc, use_container_width=True)

        dl1, dl2 = st.columns(2)
        with dl1:
            st.download_button("📥 Download MC samples (CSV)", mcres['samples'].to_csv(index=False),
                               file_name=f"mc_samples_{datetime.now().strftime('%Y%m%d')}.csv")
        with dl2:
            mc_xl = io.BytesIO()
            with pd.ExcelWriter(mc_xl, engine='openpyxl') as wr:
                mcres['summary'].to_excel(wr, sheet_name='summary', index=False)
                mcres['drivers'].to_excel(wr, sheet_name='drivers', index=False)
                mcres['quality'].to_excel(wr, sheet_name='registry', index=False)
            st.download_button("📥 Download MC summary (Excel)", mc_xl.getvalue(),
                               file_name=f"mc_summary_{datetime.now().strftime('%Y%m%d')}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    if not publication_mode:
        st.markdown("---")
        st.markdown("#### 🗄️ Legacy illustrative MC (display-only, NOT publication-grade)")
        st.warning("⚠️ **Legacy total-scaling Monte Carlo — illustrative only.** It scales the *total* CO₂ by "
                   "concrete and grid factors and must NOT be used as scientific uncertainty. Superseded by the "
                   "Phase 4 component-based engine above.")

    if (not publication_mode) and st.button("🎲 Run legacy illustrative MC", key="mc_btn"):
        n_simulations = 1000
        np.random.seed(42)

        base_co2 = results['total_co2']
        base_energy = results['total_ee']
        base_cost = results.get('total_cost', base_co2 * 0.01)

        concrete_unc = UNCERTAINTY_FACTORS["concrete_factor"]["cv"]
        steel_unc = UNCERTAINTY_FACTORS["steel_factor"]["cv"]
        energy_unc = UNCERTAINTY_FACTORS["energy_factor"]["cv"]
        carbon_unc = UNCERTAINTY_FACTORS["grid_carbon_factor"]["cv"]

        co2_sim, energy_sim, cost_sim = [], [], []
        for _ in range(n_simulations):
            def lognormal_factor(cv, size=1):
                sigma = np.sqrt(np.log(1 + cv**2))
                mu = -0.5 * sigma**2
                return np.random.lognormal(mean=mu, sigma=sigma, size=size)

            cf = lognormal_factor(concrete_unc)[0]
            sf = lognormal_factor(steel_unc)[0]
            ef = lognormal_factor(energy_unc)[0]
            carbf = lognormal_factor(carbon_unc)[0]
            co2_sim.append(base_co2 * cf * carbf)
            energy_sim.append(base_energy * ef)
            cost_sim.append(base_cost * cf * sf)

        co2_sim = np.array(co2_sim)
        energy_sim = np.array(energy_sim)
        cost_sim = np.array(cost_sim)

        fig = make_subplots(rows=3, cols=1,
                           subplot_titles=('CO₂ Emissions', 'Embodied Energy', 'Total Cost'),
                           vertical_spacing=0.12)
        fig.add_trace(go.Histogram(x=co2_sim/1000, nbinsx=50, name='CO₂',
                                    marker=dict(color='rgba(200,50,50,0.6)', line=dict(color='darkred', width=1))), row=1, col=1)
        fig.add_trace(go.Histogram(x=energy_sim/1000, nbinsx=50, name='Energy',
                                    marker=dict(color='rgba(50,100,200,0.6)', line=dict(color='darkblue', width=1))), row=2, col=1)
        fig.add_trace(go.Histogram(x=cost_sim/1e6, nbinsx=50, name='Cost',
                                    marker=dict(color='rgba(50,200,50,0.6)', line=dict(color='darkgreen', width=1))), row=3, col=1)

        co2_ci = (np.percentile(co2_sim, 2.5), np.percentile(co2_sim, 97.5))
        co2_mean = np.mean(co2_sim)
        co2_cv = (np.std(co2_sim) / co2_mean) * 100

        fig.add_vline(x=co2_ci[0]/1000, line_dash="dash", line_color="red", row=1, col=1)
        fig.add_vline(x=co2_ci[1]/1000, line_dash="dash", line_color="red", row=1, col=1)
        fig.add_vline(x=co2_mean/1000, line_color="darkred", line_width=3, row=1, col=1)

        fig.update_layout(title=f'Monte Carlo ({n_simulations} Simulations)', height=900,
                         showlegend=False, paper_bgcolor='white')
        fig.update_xaxes(title_text="CO₂ (k tons)", row=1, col=1)
        fig.update_xaxes(title_text="Energy (GJ)", row=2, col=1)
        fig.update_xaxes(title_text="Cost ($M)", row=3, col=1)
        st.plotly_chart(fig, use_container_width=True)

        uc1, uc2, uc3 = st.columns(3)
        with uc1:
            st.metric("CO₂ 95% CI", f"[{co2_ci[0]/1000:.1f}k, {co2_ci[1]/1000:.1f}k]")
            st.metric("CV", f"{co2_cv:.1f}%")
        with uc2:
            e_ci = (np.percentile(energy_sim, 2.5), np.percentile(energy_sim, 97.5))
            st.metric("Energy 95% CI", f"[{e_ci[0]/1000:.1f}, {e_ci[1]/1000:.1f}] GJ")
        with uc3:
            c_ci = (np.percentile(cost_sim, 2.5), np.percentile(cost_sim, 97.5))
            st.metric("Cost 95% CI", f"[${c_ci[0]/1e6:.2f}M, ${c_ci[1]/1e6:.2f}M]")


# ═══════════════════════════════════════════════════════════════
# TAB 6: 3D SENSITIVITY SURFACE
# ═══════════════════════════════════════════════════════════════
if 'surface3d' in TABS:
    with TABS['surface3d']:
        st.markdown("### 📐 3D Sensitivity Surface: Carbon Intensity × Renewable Energy")
        st.warning("⚠️ Illustrative dashboard-only surface. Renewable share is NOT used in the core LCA "
                   "(grid carbon intensity already reflects the grid mix); this view is for visualization only.")

        if st.button("📈 Generate 3D Surface", key="surface_btn"):
            carbon_range = np.linspace(0.2, 0.8, 30)
            renew_range = np.linspace(0, 100, 30)
            X, Y = np.meshgrid(carbon_range, renew_range)
            Z = np.zeros_like(X)

            base_co2 = results['total_co2']
            for i in range(X.shape[0]):
                for j in range(X.shape[1]):
                    carbon_factor = X[i, j] / 0.5
                    renewable_factor = (100 - Y[i, j]) / (100 - 20)
                    Z[i, j] = base_co2 * carbon_factor * renewable_factor

            Z_norm = (Z - Z.min()) / (Z.max() - Z.min()) * 10

            fig = go.Figure(data=[go.Surface(
                x=X, y=Y, z=Z_norm, colorscale='RdYlGn_r',
                colorbar=dict(title="Relative<br>Impact"),
                contours=dict(z=dict(show=True, usecolormap=True, highlightcolor="limegreen", project=dict(z=True))),
                hovertemplate='Carbon: %{x:.2f}<br>Renewable: %{y:.1f}%<br>Impact: %{z:.2f}<extra></extra>'
            )])
            fig.update_layout(
                title='3D Sensitivity: Carbon Intensity vs Renewable Energy',
                scene=dict(
                    xaxis=dict(title='Carbon (kg CO₂/kWh)', backgroundcolor="rgb(230,230,230)"),
                    yaxis=dict(title='Renewable (%)', backgroundcolor="rgb(230,230,230)"),
                    zaxis=dict(title='Relative Impact', backgroundcolor="rgb(230,230,230)"),
                    camera=dict(eye=dict(x=1.5, y=1.5, z=1.3))
                ),
                height=800, paper_bgcolor='white'
            )
            st.plotly_chart(fig, use_container_width=True)

            min_idx = np.unravel_index(Z.argmin(), Z.shape)
            st.success(f"Optimal: Carbon = {X[min_idx]:.3f} kg/kWh, Renewable = {Y[min_idx]:.1f}%")


# ═══════════════════════════════════════════════════════════════
# TAB 7: ONE-AT-A-TIME SENSITIVITY ANALYSIS
# ═══════════════════════════════════════════════════════════════
with TABS['oat']:
    st.markdown("### 📊 One-at-a-Time Sensitivity Analysis")
    st.caption("Scenario-based OAT sensitivity on the gross modular LCA total (±10% per variable).")

    def one_at_a_time_sensitivity(params, variable, change_pct=0.10):
        base = run_full_assessment(params)["gross_a1_c4_tons"]
        modified = params.copy()
        modified[variable] = modified[variable] * (1 + change_pct)
        new_val = run_full_assessment(modified)["gross_a1_c4_tons"]
        if base == 0:
            return 0.0
        return ((new_val - base) / base) / change_pct

    # Renewable share is intentionally excluded: it is dashboard-only in Phase 1b
    # and does not affect core B6, so its OAT sensitivity would be a confusing zero.
    var_map = {
        'carbon_intensity': 'Grid Carbon Intensity',
        'energy_per_pax': 'Energy per pax-km',
        'daily_pax_km': 'Daily pax-km',
        'steel': 'Steel quantity',
        'aluminum': 'Aluminum quantity',
        'concrete': 'Concrete quantity'
    }

    sens = []
    for k, label in var_map.items():
        val = one_at_a_time_sensitivity(params, k, 0.10)
        sens.append((label, val))

    sens_df = pd.DataFrame(sens, columns=['Variable', 'Sensitivity Index'])
    sens_df['Abs'] = sens_df['Sensitivity Index'].abs()
    sens_df = sens_df.sort_values('Abs', ascending=False)

    fig_sens = go.Figure(go.Bar(
        x=sens_df['Sensitivity Index'],
        y=sens_df['Variable'],
        orientation='h',
        marker_color=['#ff6b6b' if v > 0 else '#64ffda' for v in sens_df['Sensitivity Index']]
    ))
    fig_sens.update_layout(title='OAT Sensitivity Index on Total Lifecycle CO₂', height=450,
                           xaxis_title='((ΔOutput/Output)/(ΔInput/Input))', yaxis_title='Variable')
    st.plotly_chart(fig_sens, use_container_width=True)
    st.dataframe(sens_df[['Variable','Sensitivity Index']], use_container_width=True, hide_index=True)

# TAB 8: URBAN ANALYTICS
# ═══════════════════════════════════════════════════════════════
if 'urban' in TABS:
    with TABS['urban']:
        st.warning("Illustrative synthetic scenario visualization; not used in the scientific LCA/LCCA results.")
        st.markdown("### 🗺️ Urban Analytics 3D: Spatial Sustainability Assessment")

        case_study = st.selectbox("Select Case Study:", ['Cairo', 'Chongqing', 'Osaka', 'Generic'], key="case_sel")

        if st.button("🗺️ Generate Urban Analytics", key="urban_btn"):
            case_data = {
                'Cairo': {'stations': 22, 'length_km': 54, 'lat_center': 30.0444, 'lon_center': 31.2357, 'population_served': 2000000},
                'Chongqing': {'stations': 45, 'length_km': 67, 'lat_center': 29.5630, 'lon_center': 106.5516, 'population_served': 5000000},
                'Osaka': {'stations': 18, 'length_km': 28, 'lat_center': 34.6937, 'lon_center': 135.5023, 'population_served': 1500000},
                'Generic': {'stations': 25, 'length_km': 40, 'lat_center': 40.7128, 'lon_center': -74.0060, 'population_served': 1000000}
            }
            data = case_data[case_study]
            n_stations = data['stations']

            np.random.seed(42)
            lats = np.linspace(data['lat_center'] - 0.2, data['lat_center'] + 0.2, n_stations) + np.random.normal(0, 0.02, n_stations)
            lons = np.linspace(data['lon_center'] - 0.2, data['lon_center'] + 0.2, n_stations) + np.random.normal(0, 0.02, n_stations)

            station_co2 = results['total_co2'] / n_stations
            co2_per_station = station_co2 * np.random.uniform(0.8, 1.2, n_stations)
            pax_per_station = (data['population_served'] / n_stations) * np.random.uniform(0.7, 1.3, n_stations)

            fig = go.Figure()
            fig.add_trace(go.Scattergeo(
                lat=lats, lon=lons, mode='markers+text',
                marker=dict(size=co2_per_station / np.max(co2_per_station) * 30 + 10,
                           color=co2_per_station, colorscale='RdYlGn_r', showscale=True,
                           colorbar=dict(title="CO₂<br>(tons/yr)"), line=dict(color='black', width=1)),
                text=[f'S{i+1}' for i in range(n_stations)], textposition='top center',
                hovertext=[f'<b>Station S{i+1}</b><br>CO₂: {co2:.0f} t/yr<br>Pax: {int(p):,}/day'
                          for i, (co2, p) in enumerate(zip(co2_per_station, pax_per_station))],
                hoverinfo='text', name='Stations'
            ))
            fig.add_trace(go.Scattergeo(lat=lats, lon=lons, mode='lines',
                                         line=dict(width=3, color='blue'), opacity=0.5, name='Route'))
            fig.update_geos(center=dict(lat=data['lat_center'], lon=data['lon_center']),
                           projection_type='natural earth', showcountries=True, showcoastlines=True,
                           showland=True, landcolor='rgb(243,243,243)')
            fig.update_layout(
                title=f'Urban Analytics: {case_study} Monorail Network ({n_stations} stations | {data["length_km"]} km)',
                height=700, showlegend=True
            )
            st.plotly_chart(fig, use_container_width=True)

            uc1, uc2, uc3 = st.columns(3)
            with uc1:
                st.metric("Total CO₂", f"{np.sum(co2_per_station):,.0f} t/yr")
                st.metric("Avg/Station", f"{np.mean(co2_per_station):,.0f} t/yr")
            with uc2:
                st.metric("Max Station", f"S{np.argmax(co2_per_station)+1} ({co2_per_station[np.argmax(co2_per_station)]:,.0f} t)")
                st.metric("Min Station", f"S{np.argmin(co2_per_station)+1} ({co2_per_station[np.argmin(co2_per_station)]:,.0f} t)")
            with uc3:
                st.metric("Per Capita", f"{np.sum(co2_per_station)/data['population_served']*1000:.2f} kg/person/yr")
                st.metric("Density", f"{n_stations/data['length_km']:.2f} stations/km")


# ═══════════════════════════════════════════════════════════════
# TAB 9: INTERACTION NETWORK
# ═══════════════════════════════════════════════════════════════
if 'interaction' in TABS:
    with TABS['interaction']:
        st.markdown("### 🔄 Illustrative Interaction Visualization")
        st.warning("This network is a heuristic visualization only. The coefficients are not validated causal effects and are not used in the core LCA/LCCA results.")

        categories_net = ['Material', 'Environmental', 'Operational', 'Economic']
        angles = np.linspace(0, 2*np.pi, 4, endpoint=False)
        node_x = np.cos(angles)
        node_y = np.sin(angles)

        interactions = [
            ('Material', 'Environmental', effects['mat_env_effect']),
            ('Environmental', 'Operational', effects['env_op_effect']),
            ('Operational', 'Economic', effects['op_econ_effect']),
            ('Economic', 'Material', effects['econ_mat_effect']),
            ('Material', 'Operational', effects['mat_op_effect']),
            ('Environmental', 'Economic', effects['env_econ_effect'])
        ]

        fig_net = go.Figure()
        for fr, to, val in interactions:
            fi = categories_net.index(fr)
            ti = categories_net.index(to)
            color = 'green' if val > 0 else 'red'
            fig_net.add_trace(go.Scatter(
                x=[node_x[fi], node_x[ti], None], y=[node_y[fi], node_y[ti], None],
                mode='lines', line=dict(width=min(abs(val)*2+1, 10), color=color),
                hoverinfo='text', hovertext=f"{fr} → {to}: {val:+.2f} ({'Synergy' if val > 0 else 'Trade-off'})",
                showlegend=False
            ))

        node_colors = ['#3498db', '#2ecc71', '#f39c12', '#e74c3c']
        scores_adj = [results['adjusted_material_score'], results['adjusted_environmental_score'],
                      results['adjusted_operational_score'], results['adjusted_economic_score']]

        fig_net.add_trace(go.Scatter(
            x=node_x, y=node_y, mode='markers+text',
            marker=dict(size=[s*0.5+20 for s in scores_adj], color=node_colors,
                       line=dict(width=3, color='white')),
            text=categories_net, textposition='middle center',
            textfont=dict(size=12, color='white', family='Arial Black'),
            hovertext=[f"<b>{c}</b><br>Score: {s:.1f}" for c, s in zip(categories_net, scores_adj)],
            hoverinfo='text', showlegend=False
        ))

        fig_net.add_trace(go.Scatter(x=[None], y=[None], mode='lines',
                                      line=dict(width=4, color='green'), name='Synergy (+)'))
        fig_net.add_trace(go.Scatter(x=[None], y=[None], mode='lines',
                                      line=dict(width=4, color='red'), name='Trade-off (-)'))

        fig_net.update_layout(
            title='Cross-Category Interaction Network',
            xaxis=dict(showgrid=False, showticklabels=False, zeroline=False, range=[-1.5, 1.5]),
            yaxis=dict(showgrid=False, showticklabels=False, zeroline=False, range=[-1.5, 1.5]),
            plot_bgcolor='#f8f9fa', paper_bgcolor='white', height=700,
            showlegend=True, legend=dict(x=0.02, y=0.98)
        )
        fig_net.add_annotation(
            text=f"<b>Stats</b><br>Synergy: {results['total_synergy']:.2f}<br>"
                 f"Trade-off: {results['total_tradeoff']:.2f}<br>Ratio: {results['synergy_ratio']:.2f}",
            xref="paper", yref="paper", x=0.98, y=0.02, xanchor='right', yanchor='bottom',
            showarrow=False, bgcolor='rgba(255,255,255,0.9)', bordercolor='black', borderwidth=1
        )
        st.plotly_chart(fig_net, use_container_width=True)


# ═══════════════════════════════════════════════════════════════
# TAB 10: ABOUT & METHODOLOGY
# ═══════════════════════════════════════════════════════════════
with TABS['about']:
    st.markdown("""
### 📖 Assessment Methodology

---

#### 1. LIFE CYCLE ASSESSMENT (LCA)
- **ISO 14040:2006** — Environmental Management Framework
- **ISO 14044:2006** — LCA Requirements and Guidelines
- **Functional Unit:** 1 passenger-kilometer over 50-year lifecycle
- **System Boundary (currently implemented):** A1-A3 materials + A4 transport + **optional A5 construction** + **activity-based B2-B5** + active B6 operation + **optional C1-C4 end-of-life**. Module D is reported separately (supplementary).

#### 2. LIFE CYCLE COST ANALYSIS (LCCA)
- **ASTM E917** — Standard Practice for Measuring Life-Cycle Costs
- **Net Present Value (NPV)** methodology
- 50-year economic assessment period

#### 3. DASHBOARD DISPLAY SCORE (non-scientific)
- Dashboard-only visualization score — **NOT** a sustainability index.
- It is not used as an ISO LCA/LCCA result.
- Scientific conclusions must be taken from the LCA and NPV-LCCA outputs only.
- Computed in `calculate_dashboard_display_scores()`, kept separate from the scientific core (`calculate_legacy_dashboard_results()`).

| Category | Weight | Key Components |
|---|---|---|
| Material Efficiency | 25% | 6 materials + recycling bonuses |
| Environmental | 30% | CO₂, renewable (display-only), land use, noise |
| Operational | 25% | Time savings, availability, energy efficiency |
| Economic | 20% | Jobs, lifecycle cost, economic multiplier |

#### 3b. SYSTEM DYNAMICS LAYER (Phase 2 — B6 only)
Phase 2 introduces a scenario-based system dynamics layer for B6 operational emissions.
The model represents asset condition as a stock **C(t)**, degraded by annual deterioration and
improved by delayed maintenance recovery. The condition stock feeds back into operational energy
intensity **EI(t)** and therefore annual B6 emissions. The SD parameters are scenario assumptions
unless calibrated using asset inspection, maintenance, or measured energy data.

```
dC/dt = MR(t) − DR(t)
DR_t  = min(δ, C_t)                 (constant annual degradation, capped)
MR_t  = ρ · m_(t−τ)                 (delayed maintenance recovery, capped to C ≤ 1)
EI_t  = EI₀ · [1 + α·(1 − C_t)]     (condition → energy intensity)
B6_dyn = Σ_t  EI_t · PKM_t · CI_t / 1000      (CI_t = grid only, no renewable)
```

#### 3c. MODULAR GROSS A1–C4 LCA (Phase 3A–3C)
The model reports a **gross modular A1–C4 LCA** built from separate modules:
`gross = A1–A3 + A4 + A5 + B2–B5 + B6_active + C1–C4`. Each stage is independently
toggleable; the **functional unit (kg CO₂e/pkm) uses the gross figure (never net)**.
Module D (recycling credit) is **always reported separately** as supplementary
information (`net = gross − Module D`) and is never merged into gross.

- **A5 (Phase 3A):** construction diesel + site electricity + material-waste production
  (BOQ installed/purchased mode prevents double counting) + waste transport + treatment.
- **B2–B5 (Phase 3B):** activity-based maintenance/replacement. B2 is linked to the SD
  maintenance schedule (no 'free maintenance'); B4 replacement uses a mass balance so removed
  material is handled in B4 and is **not re-counted** in C1–C4. LCCA maintenance mode
  (simple_annual vs activity_based) prevents double counting; B4 cost is added in both modes.
- **C1–C4 + Module D (Phase 3C):** end-of-life on the **remaining** masses (after B4/B5),
  with per-material treatment shares that must sum to 1. C3 processing is an **emission**
  (not a credit); recovery credits go to **Module D only**.

```
treatment shares:  s_reuse + s_recycle + s_disposal = 1   (per material)
I_C1 = [ Σ F_(f,C1) EF_f + E_C1 · CI_T ] / 1000
I_C2 = Σ_j [ (M_(j,EOL)/1000) · D · EF_tr ] / 1000
I_C3 = [ Σ_j M_(j,EOL) ( s_reuse·EF_reuse + s_recycle·EF_recycle ) ] / 1000
I_C4 = [ Σ_j M_(j,EOL) · s_disposal · EF_disposal ] / 1000
I_C1-C4 = I_C1 + I_C2 + I_C3 + I_C4
Module D = Σ_j [ M_(j,EOL)(s_reuse+s_recycle) · η_j · (EF_virgin − EF_secondary) ] / 1000   (separate)
```

All A5/B2–B5/C1–C4/Module-D factors and quantities are **scenario / user inputs**;
results are not 'validated' unless calibrated with project data. `publication_grade_full_lca`
is False if FRP lacks an EPD, if any material's treatment shares do not sum to 1, or if
Module D is reported with a missing secondary factor.

#### 3d. COMPONENT-BASED MONTE CARLO (Phase 4)
A statistical layer on top of the A1–C4 model — it changes **no** LCA equation. Each
uncertain input is sampled from its own distribution (lognormal for EFs/positive
quantities, triangular for distances, Dirichlet for treatment shares, etc.) via Latin
Hypercube sampling, and the full model is re-run, so uncertainty propagates **per
component**. The model identities hold in **every** draw:

```
θ_k ~ P(θ)
I_gross,k = I_A1-A3,k + I_A4,k + I_A5,k + I_B2-B5,k + I_B6,k + I_C1-C4,k
GWP_pkm,k = 1000 · I_gross,k / PKM_k
I_net,k   = I_gross,k − I_D,k        (Module D propagated separately, never in gross)
95% uncertainty interval = [P2.5(Y), P97.5(Y)]
```

Outputs: per-stage and metric percentiles, Spearman tornado (drivers), and convergence
diagnostics. `publication_grade_uncertainty` is True only if the full LCA is
publication-grade, the registry is complete, n ≥ 5000, and convergence is reached. The
legacy total-scaling MC is retained as **illustrative only** and is never publication-grade.
Reported ranges are **scenario-based uncertainty intervals**, not measured statistical
confidence intervals.

#### 3e. SUSTAINABILITY INDEX (Phase 5 — hybrid CRITIC–Entropy)
The Sustainability Index is a **decision-support composite index** derived from a scenario-year
matrix (n ≥ 30 for publication-grade). It **does not replace** the reported LCA/LCCA/uncertainty
outputs, and is **not** the legacy Dashboard Display Score. Indicators are non-overlapping (no gross
together with its own sub-stages); `net_with_module_d` is **never** an environmental indicator
(Module D enters only as a separate circularity ratio). Indicators are normalized with **target-based**
functions, weighted with a **hybrid Entropy–CRITIC** method, and aggregated additively (hierarchical
by pillar). Core LCA/LCCA results remain reported separately.

```
z_ij = f(x_ij) ∈ [0,1]            (target-based; higher- or lower-better)
wE  = entropy weights;  wC = CRITIC weights
w_j = λ·wE_j + (1−λ)·wC_j         (default λ = 0.5; λ-sensitivity reported)
S_(i,g) = Σ_{j∈g} (w_j|g) z_ij    (pillar score)
SI_i = Σ_g W_g · S_(i,g) ∈ [0,1]  (W: Environmental .35, Economic .25, Operational .25, Social .15)
```

`publication_grade_si` is True only if the full LCA AND Phase 4 uncertainty are publication-grade,
n_scenarios ≥ 30, indicator metadata/targets are complete, weights sum to 1, and λ-sensitivity is
computed. Reported as decision support — **not** a validation claim.

The methodology is now complete: **Gross modular A1–C4 LCA + NPV-LCCA + component-based uncertainty
+ scientific decision-support SI (CRITIC–Entropy)**. The model is **not** described as a *validated*
cradle-to-grave model unless external project calibration/verification data are later added.

#### 4. ILLUSTRATIVE INTERACTION VISUALIZATION
- The interaction network is used only for dashboard visualization.
- The coefficients are heuristic display parameters.
- They are not validated causal effects and are not part of the core LCA/LCCA results.
- SDG interaction literature is used only as conceptual background, not as a numerical source for the coefficients.

#### 5. BENCHMARK / REPRODUCTION CHECK
- **Li and Zhu (2022)** — Computational Intelligence and Neuroscience
- DOI: [10.1155/2022/3872069](https://doi.org/10.1155/2022/3872069)
- Used only as an external benchmark comparison; no Li & Zhu calibration factors are used in the core model.

---

#### SCIENTIFIC REFERENCES

1. ISO 14040:2006 — Environmental Management — Life Cycle Assessment
2. ISO 14044:2006 — Environmental Management — Life Cycle Assessment — Requirements and Guidelines
3. ASTM E917-17 — Standard Practice for Measuring Life-Cycle Costs
4. Li and Zhu (2022). *Computational Intelligence and Neuroscience*, 2022, 3872069. DOI: 10.1155/2022/3872069 — external benchmark only (full title/indexing cited in the manuscript).
5. Nilsson, M., et al. (2016). "Mapping interactions between SDGs." *Nature*, 534, 320-322. Used as conceptual background only.

---

#### DATA SOURCE HIERARCHY (per material, most-specific first)
1. **Project BOQ** quantities (user input)
2. **Local / product-specific EPD** — highest evidence; use if available
3. **ICE Database Educational V4.1 (Oct 2025)**, "ICE Summary" sheet — generic A1-A3 carbon factors
4. **Li and Zhu (2022)** — benchmark comparison ONLY; never a factor source

#### DATA SOURCES
- **Material embodied carbon (PRIMARY):** ICE Database Educational V4.1 (Oct 2025), ICE Summary sheet, A1-A3 Embodied Carbon. Each factor carries its exact `ice_name`, `dqi_score`, boundary and status in the MATERIAL_FACTOR_AUDIT table.
- **ICE licensing / attribution:** the ICE database (Circular Ecology, Hammond & Jones) is used under its educational terms; ICE-derived factors are attributed to Circular Ecology and remain subject to the ICE licence. Confirm the licence permits redistribution of derived values before publishing the dataset, and cite Circular Ecology accordingly.
- **Material embodied energy (SECONDARY):** legacy Hammond & Jones (2008) / ICE v2.0 values — explicitly **not** from ICE V4.1; reported as a secondary indicator only.
- **FRP / GRP:** **UNVERIFIED placeholder** — ICE V4.1 has no published A1-A3 carbon value; a product-specific EPD is required before publication.
- **Glass mass:** geometric — area × thickness (mm) × 2.5 kg/(mm·m²) (flat-glass 2500 kg/m³).
- **Module D (recycling credit):** computed per EN 15804 and reported **separately**; it is **not** netted into A1-A3 and **not** added to the A1-C4 total.
- **Operational electricity carbon:** User-defined grid carbon intensity applied directly to B6 (Phase 1b). Renewable share is NOT applied to the core to avoid double-counting the grid mix; it is dashboard-only and deferred to Phase 2.
- **LCCA:** User-defined construction, maintenance, energy cost, residual value, and discount rate.
- **Transport A4:** Scenario-based ton-km calculation using user-selected mode and transport distance.
- **Synthetic visualizations:** Pareto, 12-element, and urban analytics tabs are illustrative only and not part of the scientific LCA/LCCA results.

---

#### HOW TO CITE

```
[Your Name]. (2025). Enhanced Monorail LCA/LCCA Assessment Tool:
Gross modular A1-C4 LCA and NPV-based LCCA Framework with Scenario-based Sensitivity Analysis.
Cairo University. Software version 2.0.
```

```bibtex
@software{monorail_lca_2025,
  author = {[Your Name]},
  title = {Enhanced Monorail LCA/LCCA Assessment Tool: Gross modular A1-C4 LCA and NPV-based LCCA Framework},
  year = {2025},
  institution = {Cairo University},
  version = {2.0}
}
```
    """)


# ═══════════════════════════════════════════════════════════════
# TAB 11: SYSTEM DYNAMICS (B6) — Phase 2
# ═══════════════════════════════════════════════════════════════
with TABS['sd']:
    st.markdown("### 🔧 System Dynamics — Asset Condition C(t) → Dynamic B6")
    st.warning(
        "Scenario-based system dynamics layer. Parameters (δ, ρ, τ, α, C₀, g) are "
        "**scenario assumptions — NOT validated** unless calibrated with asset inspection, "
        "maintenance, or measured operational-energy data. Renewable share is NOT used here."
    )
    if not results.get('sd_enabled'):
        st.info("ℹ️ Dynamic B6 is **previewed below but not applied to the headline result**. "
                "Tick *Enable dynamic B6* in the sidebar to activate it as the active result.")

    sp = results['sd_params']
    st.caption(f"Parameters — C₀={sp['C0']}, δ={sp['delta']}, interval={sp['interval']} yr, "
               f"ρ={sp['rho']}, τ={sp['tau']} yr, α={sp['alpha']}, g={sp['g_pct']:.1f}%/yr, "
               f"T={ASSESSMENT_LIFETIME_YEARS} yr (dC/dt = MR − DR).")

    sdm1, sdm2, sdm3, sdm4 = st.columns(4)
    with sdm1: st.metric("Final condition C(T)", f"{results['sd_final_condition']:.3f}")
    with sdm2: st.metric("Minimum condition", f"{results['sd_min_condition']:.3f}")
    with sdm3: st.metric("Average EI", f"{results['sd_average_EI']:.4f} kWh/pkm")
    with sdm4: st.metric("Base EI₀", f"{results['energy_per_pax_km']:.4f} kWh/pkm")

    sdb1, sdb2, sdb3, sdb4 = st.columns(4)
    with sdb1: st.metric("Static B6 (t CO₂e)", f"{results['b6_static_tons']:,.0f}")
    with sdb2: st.metric("Dynamic B6 (t CO₂e)", f"{results['b6_dynamic_tons']:,.0f}",
                         delta=f"{results['delta_b6_tons']:+,.0f}")
    with sdb3: st.metric("Dynamic total LCA (t)", f"{results['total_lifecycle_co2_dynamic']:,.0f}")
    with sdb4: st.metric("Dynamic kg CO₂e/pkm", f"{results['co2_kg_per_pkm_dynamic']:.5f}")

    sd_df = pd.DataFrame(results['sd_rows'])
    b6_df = pd.DataFrame(results['sd_b6']['yearly'])

    c_left, c_right = st.columns(2)
    with c_left:
        fig_c = go.Figure()
        fig_c.add_trace(go.Scatter(x=sd_df['year'], y=sd_df['C_end'], mode='lines+markers',
                                   line=dict(color='#64ffda', width=2), name='C(t)'))
        fig_c.update_layout(title='Asset Condition C(t)', height=360,
                            plot_bgcolor='rgba(10,25,47,0.8)', paper_bgcolor='rgba(0,0,0,0)',
                            font_color='#ccd6f6', yaxis_range=[0, 1.05],
                            xaxis_title='Year', yaxis_title='Condition (0–1)', margin=dict(t=40, b=30))
        st.plotly_chart(fig_c, use_container_width=True)
    with c_right:
        fig_ei = go.Figure()
        fig_ei.add_trace(go.Scatter(x=b6_df['year'], y=b6_df['EI_t'], mode='lines+markers',
                                    line=dict(color='#f7971e', width=2), name='EI(t)'))
        fig_ei.add_hline(y=results['energy_per_pax_km'], line_dash="dash", line_color="#6495ed")
        fig_ei.update_layout(title='Dynamic Energy Intensity EI(t)', height=360,
                             plot_bgcolor='rgba(10,25,47,0.8)', paper_bgcolor='rgba(0,0,0,0)',
                             font_color='#ccd6f6', xaxis_title='Year', yaxis_title='kWh/pkm',
                             margin=dict(t=40, b=30))
        st.plotly_chart(fig_ei, use_container_width=True)

    d_left, d_right = st.columns(2)
    with d_left:
        fig_b6 = go.Figure()
        fig_b6.add_trace(go.Bar(x=b6_df['year'], y=b6_df['B6_co2_tons'],
                                marker_color='rgba(235,51,73,0.6)', name='Annual B6'))
        fig_b6.update_layout(title='Annual Dynamic B6 (t CO₂e/yr)', height=360,
                             plot_bgcolor='rgba(10,25,47,0.8)', paper_bgcolor='rgba(0,0,0,0)',
                             font_color='#ccd6f6', xaxis_title='Year', yaxis_title='t CO₂e/yr',
                             margin=dict(t=40, b=30))
        st.plotly_chart(fig_b6, use_container_width=True)
    with d_right:
        fig_cmp = go.Figure(go.Bar(
            x=['Static B6', 'Dynamic B6'],
            y=[results['b6_static_tons'], results['b6_dynamic_tons']],
            marker_color=['#6495ed', '#64ffda'],
            text=[f"{results['b6_static_tons']:,.0f}", f"{results['b6_dynamic_tons']:,.0f}"],
            textposition='outside'))
        fig_cmp.update_layout(title='Static vs Dynamic B6 (lifetime)', height=360,
                              plot_bgcolor='rgba(10,25,47,0.8)', paper_bgcolor='rgba(0,0,0,0)',
                              font_color='#ccd6f6', yaxis_title='t CO₂e', margin=dict(t=40, b=40))
        st.plotly_chart(fig_cmp, use_container_width=True)

    with st.expander("📋 Yearly System Dynamics table", expanded=False):
        st.dataframe(sd_df, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════
# TAB 12: SUSTAINABILITY INDEX (Phase 5)
# ═══════════════════════════════════════════════════════════════
with TABS['si']:
    st.markdown("### 🏁 Scientific Sustainability Index — hybrid CRITIC–Entropy")
    st.caption("A **decision-support composite index** over a scenario-year matrix. It does NOT replace the "
               "reported gross A1–C4 LCA, GWP/pkm, Module D, LCCA or Monte Carlo uncertainty, and is NOT the "
               "legacy Dashboard Display Score. Indicators are non-overlapping; net-with-Module-D is never an "
               "environmental indicator (Module D enters only as a separate circularity ratio).")

    sic1, sic2, sic3 = st.columns(3)
    with sic1:
        si_enable = st.checkbox("Enable Phase 5 SI", value=False, key="si_enable")
        si_n = st.number_input("n scenarios", value=36, min_value=5, max_value=200, step=2, key="si_n")
    with sic2:
        si_lambda = st.slider("λ (Entropy ↔ CRITIC)", 0.0, 1.0, 0.5, 0.05, key="si_lambda")
        si_critic = st.selectbox("CRITIC correlation", ["pearson", "spearman"], index=0, key="si_critic")
    with sic3:
        si_unc_n = st.number_input("Per-scenario MC (0=skip robustness)", value=0, min_value=0, max_value=2000, step=100, key="si_unc_n")
        si_pgu = st.checkbox("Manual confirmation: Phase 4 uncertainty is publication-grade",
                             value=bool(st.session_state.get('phase4_pgu', False)), key="si_pgu",
                             help="Auto-filled from the last Phase 4 MC run (n≥5000 + convergence). Override only if confirmed independently.")

    si_source = st.selectbox("Scenario-year matrix source",
                             ["generated_demo (synthetic — not publication-grade)", "documented", "uploaded (CSV)"],
                             index=0, key="si_source")
    si_source_key = {'generated_demo (synthetic — not publication-grade)': 'generated_demo',
                     'documented': 'documented', 'uploaded (CSV)': 'uploaded'}[si_source]
    si_uploaded_df = None
    if si_source_key == 'uploaded':
        up = st.file_uploader("Upload scenario-year matrix CSV (scenario_id, year, indicator columns)", type=['csv'], key="si_csv")
        if up is not None:
            try:
                si_uploaded_df = pd.read_csv(up)
                st.success(f"Loaded uploaded matrix: {len(si_uploaded_df)} scenarios.")
            except Exception as _e:
                st.error(f"Could not read CSV: {_e}")

    if si_enable:
        def _run_si(bp, n, lam, method, unc_n, pgu, source, uploaded, seed):
            scs = generate_default_scenarios(bp, n=int(n), seed=int(seed))
            return run_phase5_si(scs, bp, lam=float(lam), critic_method=method,
                                 uncertainty_n=int(unc_n), publication_grade_uncertainty=bool(pgu),
                                 seed=int(seed), scenario_source=source, uploaded_matrix=uploaded)
        si = _run_si(dict(params), si_n, si_lambda, si_critic, si_unc_n, si_pgu, si_source_key, si_uploaded_df, 42)

        st.warning("SI is a **decision-support composite index**, not a validation claim. "
                   "Targets are scenario/literature values; intervals/weights are data-driven on the chosen matrix.")
        if si['validation']['errors']:
            st.error("Indicator matrix invalid: " + "; ".join(si['validation']['errors']))
        for w in si['warnings']:
            st.caption("ℹ️ " + w)
        flag = si['publication_grade_si']
        (st.success if flag else st.warning)(
            f"publication_grade_si = {flag} · n_scenarios = {si['n_scenarios']} · λ = {si['lambda']} · "
            f"λ-rank stability (Spearman) = {si['lambda_sensitivity']['rank_stability_spearman']:.3f}"
            + ("" if flag else " — requires full-LCA + Phase 4 publication-grade + n≥30."))

        st.markdown("#### 🏆 Ranked scenarios")
        rk = si['ranked_scenarios'][['rank', 'scenario_id', 'year', 'SI', 'SI_100']].copy()
        rk['SI'] = rk['SI'].map(lambda v: f"{v:.3f}"); rk['SI_100'] = rk['SI_100'].map(lambda v: f"{v:.1f}")
        st.dataframe(rk, use_container_width=True, hide_index=True)

        cA, cB = st.columns(2)
        with cA:
            top = si['ranked_scenarios'].head(15)
            figr = go.Figure(go.Bar(x=top['SI'], y=top['scenario_id'], orientation='h',
                                    marker_color='rgba(100,255,218,0.7)'))
            figr.update_layout(title='Top scenarios by SI', height=460, paper_bgcolor='rgba(0,0,0,0)',
                               plot_bgcolor='rgba(10,25,47,0.8)', font_color='#ccd6f6',
                               yaxis=dict(autorange='reversed'), margin=dict(t=40, b=30))
            st.plotly_chart(figr, use_container_width=True)
        with cB:
            pillars = list(si['pillar_weights'].keys())
            ps = si['pillar_scores']
            present = [p for p in pillars if p in ps.columns]
            figrad = go.Figure()
            for _, rr in si['ranked_scenarios'].head(3).iterrows():
                idx = rr['rank'] - 1
                vals = [ps.iloc[si['raw_matrix'].index[si['raw_matrix']['scenario_id'] == rr['scenario_id']][0]][p] for p in present]
                figrad.add_trace(go.Scatterpolar(r=vals + [vals[0]], theta=present + [present[0]],
                                                 fill='toself', name=rr['scenario_id']))
            figrad.update_layout(title='Pillar radar — top 3', height=460, paper_bgcolor='rgba(0,0,0,0)',
                                 polar=dict(radialaxis=dict(range=[0, 1])), font_color='#ccd6f6', margin=dict(t=40, b=30))
            st.plotly_chart(figrad, use_container_width=True)

        st.markdown("#### ⚖️ Weights (Entropy / CRITIC / Hybrid)")
        st.dataframe(si['weights_table'].round(4), use_container_width=True, hide_index=True)

        cC, cD = st.columns(2)
        with cC:
            figh = go.Figure(data=go.Heatmap(z=si['normalized_matrix'].to_numpy(),
                                             x=list(si['normalized_matrix'].columns),
                                             y=si['raw_matrix']['scenario_id'].tolist(),
                                             colorscale='Viridis'))
            figh.update_layout(title='Normalized indicators (0–1)', height=520, paper_bgcolor='rgba(0,0,0,0)',
                               font_color='#ccd6f6', margin=dict(t=40, b=30))
            st.plotly_chart(figh, use_container_width=True)
        with cD:
            lam_tab = si['lambda_sensitivity']['table']
            figl = go.Figure()
            for col in lam_tab.columns:
                figl.add_trace(go.Scatter(y=lam_tab[col].to_numpy(), mode='lines', name=col, opacity=0.5))
            figl.update_layout(title='λ sensitivity (SI per scenario)', height=520, paper_bgcolor='rgba(0,0,0,0)',
                               plot_bgcolor='rgba(10,25,47,0.8)', font_color='#ccd6f6',
                               xaxis_title='scenario index', yaxis_title='SI', margin=dict(t=40, b=30))
            st.plotly_chart(figl, use_container_width=True)

        with st.expander("🔎 SI audit table (inclusion / groups / targets)", expanded=False):
            st.dataframe(si['audit'].round(4), use_container_width=True, hide_index=True)

        d1, d2 = st.columns(2)
        with d1:
            st.download_button("📥 Download SI ranking (CSV)", si['ranked_scenarios'].to_csv(index=False),
                               file_name=f"si_ranking_{datetime.now().strftime('%Y%m%d')}.csv")
        with d2:
            si_xl = io.BytesIO()
            with pd.ExcelWriter(si_xl, engine='openpyxl') as wr:
                si['raw_matrix'].to_excel(wr, sheet_name='raw_matrix', index=False)
                si['normalized_matrix'].to_excel(wr, sheet_name='normalized', index=False)
                si['weights_table'].to_excel(wr, sheet_name='weights', index=False)
                si['ranked_scenarios'].to_excel(wr, sheet_name='SI_ranking', index=False)
                si['audit'].to_excel(wr, sheet_name='audit', index=False)
            st.download_button("📥 Download SI workbook (Excel)", si_xl.getvalue(),
                               file_name=f"si_workbook_{datetime.now().strftime('%Y%m%d')}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ═══════════════════════════════════════════════════════════════
# FOOTER
# ═══════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown(
    f"<div style='text-align:center; color:#8892b0; font-size:0.85rem;'>"
    f"🚝 Enhanced Monorail LCA/LCCA Assessment Tool v2.0 | "
    f"Cairo University | ISO 14040/14044 + ASTM E917 | "
    f"Last run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    f"</div>", unsafe_allow_html=True
)
