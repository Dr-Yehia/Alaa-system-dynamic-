"""Publication Streamlit application — the rich UI over the scientific engines only.

WHAT THIS FILE IS
-----------------
The Publication interface. It carries the appearance and workflow of the
Developer dashboard — the styling, the sidebar, the tabbed layout, the metric
cards, the evidence forms, the tables and the downloads — but everything behind
it is the referenced scientific path and nothing else.

    apps/publication.py                (Streamlit entry point, never changes)
        -> apps/_publication_impl.py       (this file: collect inputs, render results)
            -> run_scientific_publication_bundle(params)
                -> LCA / LCC / K-Benefits integration -> their cores
                -> the reporting modules for every export

WHAT IT MUST NEVER DO
---------------------
It imports no legacy engine: not the legacy LCA or LCC engines, not the legacy
benefits module, not the legacy assessment or uncertainty orchestrators. There
is no fallback path. When evidence is missing the gate stays closed, the reason
is shown, and no substitute number appears — because a Publication screen that
quietly falls back to an unsourced value is worse than one that shows nothing:
the reader cannot tell the difference, and the number still gets cited.

It performs no science and builds no export by hand. Forms collect, the
orchestrator computes, the reporting modules export, this file presents.

The JSON payload survives as an Advanced import/export control. It is how a
prepared evidence file is loaded or saved, not how the application is driven.
"""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

# ── Scientific engines — the ONLY execution path in this application ─────────
from monorail_assessment.common.project_context import ASSESSMENT_LIFETIME_YEARS
from monorail_assessment.publication.orchestrator import run_scientific_publication_bundle
from monorail_assessment.publication.reporting import (
    deterministic_export_parity_ok,
    deterministic_headline,
    deterministic_publication_csv,
    deterministic_publication_excel_bytes,
    full_q1_excel_bytes,
    publication_status_table,
)
from monorail_assessment.publication.uncertainty import (
    UncertaintySpec, run_scientific_uncertainty)

# Provenance forms and exports. These are presentation and reporting helpers;
# every equation stays behind them in the cores.
from monorail_assessment.lca.integration import add_lca_source_inputs
from monorail_assessment.lcc.reporting import scientific_lcc_table
from monorail_assessment.benefits.references import (
    EQUATIONS as BENEFITS_EQUATIONS,
    REFERENCES as BENEFITS_REFERENCES,
    permitted_statuses_for as benefits_permitted_statuses_for,
)
from monorail_assessment.benefits.reporting import (
    export_parity_ok as benefits_export_parity_ok,
    scientific_benefits_csv,
    scientific_benefits_excel_bytes,
    scientific_benefits_source_appendix,
)

st.set_page_config(
    page_title="Monorail Scientific Publication Assessment",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ═══════════════════════════════════════════════════════════════
# CUSTOM CSS STYLING
# ───────────────────────────────────────────────────────────────
# Ported from the Developer dashboard so the two applications read as one
# system. Presentation only — it touches no number.
# ═══════════════════════════════════════════════════════════════
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    .stApp {
        background: linear-gradient(135deg, #0a192f 0%, #112240 50%, #0a192f 100%);
        font-family: 'Inter', sans-serif;
    }
    .main-header {
        background: linear-gradient(90deg, rgba(100,255,218,0.10) 0%, rgba(100,149,237,0.10) 100%);
        border-left: 4px solid #64ffda;
        border-radius: 12px;
        padding: 1.4rem 1.6rem;
        margin-bottom: 1.2rem;
    }
    .main-header h1 { color: #e6f1ff; font-weight: 800; font-size: 1.9rem; margin: 0; }
    .main-header p  { color: #8892b0; margin: 0.35rem 0 0 0; font-size: 0.95rem; }

    .metric-card {
        background: rgba(17, 34, 64, 0.85);
        border: 1px solid rgba(100, 255, 218, 0.20);
        border-radius: 12px;
        padding: 1.1rem 1rem;
        text-align: center;
        height: 100%;
    }
    .metric-value { color: #64ffda; font-size: 1.6rem; font-weight: 700; line-height: 1.2; }
    .metric-label {
        color: #8892b0; font-size: 0.78rem; text-transform: uppercase;
        letter-spacing: 0.06em; margin-top: 0.35rem;
    }
    .metric-delta { color: #ccd6f6; font-size: 0.72rem; margin-top: 0.25rem; }
    .metric-card.blocked { border-color: rgba(255, 138, 128, 0.45); }
    .metric-card.blocked .metric-value { color: #ff8a80; }
    .metric-card.ready   { border-color: rgba(105, 240, 174, 0.45); }
    .metric-card.ready   .metric-value { color: #69f0ae; }

    h2, h3, h4 { color: #e6f1ff !important; }
    .stTabs [data-baseweb="tab-list"] { gap: 0.35rem; }
    .stTabs [data-baseweb="tab"] {
        background: rgba(17,34,64,0.6); border-radius: 8px 8px 0 0; color: #8892b0;
    }
    .stTabs [aria-selected="true"] { background: rgba(100,255,218,0.12); color: #64ffda; }
    section[data-testid="stSidebar"] { background: rgba(10,25,47,0.96); }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="main-header">
  <h1>🔬 Monorail Scientific Publication Assessment</h1>
  <p>LCA · LCC · K-Benefits · sourced uncertainty — fail-closed.
     Every headline requires evidence. No legacy fallback exists in this application.</p>
</div>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
# EVIDENCE COLLECTION HELPERS
# ───────────────────────────────────────────────────────────────
# A field here is deliberately more work to fill than a plain number box. The
# extra fields ARE the difference between a value and evidence: without a unit,
# a source, an exact location and a geography, nobody can check the number
# again and the gate has nothing to judge.
# ═══════════════════════════════════════════════════════════════

EVIDENCE_STATUSES = [
    "SOURCE-OPEN",            # nothing supplied yet
    "METHOD-REFERENCE",       # a document supporting the FORMULA only
    "SCENARIO-ONLY",          # an explicit assumption, labelled as such
    "HISTORICAL",             # real data from an earlier period or basis
    "REF-PROXY",              # an external benchmark, transferred
    "PROJECT-SPECIFIC",       # measured or modelled for THIS project
    "OFFICIAL-PROJECT-DATA",  # stated by an official project document
]

_REF_CHOICES = ["(none)"] + sorted(BENEFITS_REFERENCES)


def _status_choices(ref_id):
    """The statuses a chosen reference can actually back, plus the project route.

    Offering the whole list beside every reference is what makes authority
    escalation a two-click mistake. A method reference can back only its own
    role; a project claim is reached by describing the project document, which
    the form then insists on completing.
    """
    permitted = list(benefits_permitted_statuses_for(ref_id)) if ref_id and ref_id != "(none)" else []
    choices = ["SOURCE-OPEN"] + [s for s in permitted if s != "SOURCE-OPEN"]
    if "PROJECT-SPECIFIC" not in choices:
        choices.append("PROJECT-SPECIFIC")
    return choices


def evidence_input(label, *, key, unit, default_ref="(none)", monetary=False, help_text=""):
    """Collect one numeric quantity together with the provenance that justifies it.

    Returns an evidence mapping, or None when nothing was entered. None rather
    than 0.0 matters: the gate distinguishes "not supplied" from "measured as
    zero", and a default of 0.0 would erase that distinction silently.
    """
    st.markdown(f"**{label}**" + (f"  \n_{help_text}_" if help_text else ""))
    c = st.columns([1.1, 1.0, 1.0])
    with c[0]:
        raw = st.text_input(f"Value ({unit})", value="", key=f"{key}_val",
                            help="Leave empty to keep this input SOURCE-OPEN.")
    with c[1]:
        ref_id = st.selectbox("Source reference", _REF_CHOICES,
                              index=_REF_CHOICES.index(default_ref)
                              if default_ref in _REF_CHOICES else 0, key=f"{key}_ref")
    with c[2]:
        status = st.selectbox("Evidence status", _status_choices(ref_id), index=0,
                              key=f"{key}_status",
                              help="METHOD-REFERENCE supports the equation. "
                                   "PROJECT-SPECIFIC requires the project document fields.")
    c2 = st.columns([1.2, 1.4, 1.0])
    with c2[0]:
        source_file = st.text_input("Source file / report", value="", key=f"{key}_file")
    with c2[1]:
        location = st.text_input("Exact page / table / section", value="", key=f"{key}_loc",
                                 help="e.g. 'Annex 4, printed pp.71-72'. A bare page "
                                      "number makes a reviewer hunt.")
    with c2[2]:
        geography = st.text_input("Geography", value="", key=f"{key}_geo")

    project_src = None
    observation_date = None
    if status in ("PROJECT-SPECIFIC", "OFFICIAL-PROJECT-DATA"):
        st.caption("Project numeric source — required for a project claim. All fields "
                   "must be filled or this input stays source-open.")
        p = st.columns([1.2, 1.0, 1.0])
        with p[0]:
            ps_title = st.text_input("Project document title", value="", key=f"{key}_ps_title")
        with p[1]:
            ps_issuer = st.text_input("Issuer / author", value="", key=f"{key}_ps_issuer")
        with p[2]:
            ps_date = st.text_input("Observation date", value="", key=f"{key}_ps_date")
        p2 = st.columns([1.2, 1.4])
        with p2[0]:
            ps_file = st.text_input("Project file or URL", value="", key=f"{key}_ps_file")
        with p2[1]:
            ps_loc = st.text_input("Exact location in the project document", value="",
                                   key=f"{key}_ps_loc")
        project_src = {
            "title": ps_title, "issuer": ps_issuer, "file_or_url": ps_file,
            "exact_location": ps_loc, "geography": geography,
            "observation_date": ps_date, "evidence_status": status,
        }
        observation_date = ps_date or None

    currency_v = price_year = None
    if monetary:
        m = st.columns(2)
        with m[0]:
            currency_v = st.text_input("Currency", value="", key=f"{key}_ccy")
        with m[1]:
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
        "value": value, "unit": unit,
        "source_ref_id": "" if ref_id == "(none)" else ref_id,
        "source_file": source_file, "source_location": location,
        "geography": geography, "evidence_status": status,
        "currency": currency_v or None, "price_base_year": price_year,
        "observation_date": observation_date, "project_source": project_src,
    }


def area_table(label, *, key, help_text="", unit="ha"):
    """Collect land-use class areas together with the provenance of the map.

    Free text rather than a widget grid, because the class schema is itself
    project evidence: baseline and project must use the SAME classes, and a
    fixed set of boxes would quietly impose a schema the maps do not have.
    """
    st.markdown(f"**{label}**" + (f"  \n_{help_text}_" if help_text else ""))
    raw = st.text_input(f"one 'class = area' entry per line or separated by ';' (areas in {unit})",
                        value="", key=key)
    areas = {}
    for line in str(raw or "").replace("\n", ";").split(";"):
        if "=" not in line:
            continue
        name, _, amount = line.partition("=")
        try:
            areas[name.strip()] = float(amount.strip())
        except (TypeError, ValueError):
            continue
    if not areas:
        return {}

    m = st.columns([1.2, 1.0, 1.0])
    with m[0]:
        map_title = st.text_input("Map / layer title", value="", key=f"{key}_m_title")
    with m[1]:
        map_issuer = st.text_input("Produced by", value="", key=f"{key}_m_issuer")
    with m[2]:
        map_date = st.text_input("Observation date", value="", key=f"{key}_m_date")
    m2 = st.columns([1.2, 1.4, 1.0])
    with m2[0]:
        map_file = st.text_input("Map file or URL", value="", key=f"{key}_m_file")
    with m2[1]:
        map_loc = st.text_input("Analysis extent + class schema", value="", key=f"{key}_m_loc")
    with m2[2]:
        map_geo = st.text_input("Geography", value="", key=f"{key}_m_geo")

    return {
        "value": areas, "unit": unit, "source_ref_id": "",
        "source_file": map_file, "source_location": map_loc, "geography": map_geo,
        "evidence_status": "PROJECT-SPECIFIC", "observation_date": map_date,
        "project_source": {
            "title": map_title, "issuer": map_issuer, "file_or_url": map_file,
            "exact_location": map_loc, "geography": map_geo,
            "observation_date": map_date, "evidence_status": "PROJECT-SPECIFIC",
        },
    }


# ═══════════════════════════════════════════════════════════════
# RENDERING HELPERS
# ═══════════════════════════════════════════════════════════════

STATUS_ICON = {
    "COMPUTED": "🟢", "OFFICIAL-REPORTED": "🟢", "SCENARIO-ONLY": "🟡",
    "PROXY": "🟡", "SOURCE-OPEN": "🟠", "NOT-APPLICABLE": "⚪", "BLOCKED": "🔴",
}


def metric_card(value, label, delta="", state=""):
    st.markdown(
        f'<div class="metric-card {state}"><div class="metric-value">{value}</div>'
        f'<div class="metric-label">{label}</div>'
        f'<div class="metric-delta">{delta}</div></div>',
        unsafe_allow_html=True,
    )


def gate_table(gate) -> pd.DataFrame:
    """A gate dictionary as a readable table rather than a raw JSON dump.

    A reviewer should not have to parse a JSON blob to learn which condition is
    open. Booleans become a state column; lists become one row per open item.
    """
    rows = []
    for key, value in dict(gate or {}).items():
        label = key.replace("_", " ")
        if isinstance(value, bool):
            rows.append({"Condition": label, "State": "🟢 yes" if value else "🟠 no", "Detail": ""})
        elif isinstance(value, (list, tuple)):
            if not value:
                rows.append({"Condition": label, "State": "🟢 none", "Detail": ""})
            for item in value:
                rows.append({"Condition": label, "State": "🟠 open", "Detail": str(item)})
        elif isinstance(value, dict):
            for k2, v2 in value.items():
                rows.append({"Condition": f"{label} · {k2}",
                             "State": "🟢 yes" if v2 else "🟠 no", "Detail": ""})
        else:
            rows.append({"Condition": label, "State": "", "Detail": str(value)})
    return pd.DataFrame(rows)


def benefit_rows_dataframe(rows):
    """Reviewer-facing KPI table: value, unit, state and the chain to the source."""
    def fmt(r):
        v = r["value"]
        if v is None:
            return "—"
        if isinstance(v, dict):
            return ", ".join(f"{k}: {x:,.1f}" for k, x in v.items())
        if isinstance(v, (list, tuple)):
            return ", ".join(f"{float(x):,.4g}" for x in v)
        if isinstance(v, (int, float)):
            return f"{v:,.4g}"
        return str(v)

    return pd.DataFrame([{
        "": STATUS_ICON.get(r["status"], "•"),
        "KPI": r["kpi_name"], "Value": fmt(r), "Unit": r["unit"],
        "Equation": r["equation_id"] or "—",
        "Evidence state": r["status"],
        "Method source": r["method_ref_ids"] or "—",
        "Numeric source": r["numeric_source_ref_ids"] or "—",
        "Publication eligible": "yes" if r["publication_eligible"] else "no",
    } for r in rows])


def domain_blocked(run, what):
    """One consistent way to say a domain is closed, and why."""
    if run.error:
        st.error(f"Scientific {what} blocked: {run.error}")
    else:
        st.warning(f"{what} headline withheld until its scientific gate closes. "
                   "No legacy value is substituted.")


# ═══════════════════════════════════════════════════════════════
# SIDEBAR — PROJECT CONTEXT, READINESS, ADVANCED PAYLOAD
# ═══════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("### 🏗️ Project")
    project_name = st.text_input("Project name", "Cairo Monorail", key="p_name")
    c = st.columns(2)
    with c[0]:
        country = st.text_input("Country", "Egypt", key="p_country")
    with c[1]:
        region = st.text_input("Region", "Cairo", key="p_region")
    c = st.columns(2)
    with c[0]:
        analysis_start_year = st.number_input("Analysis base year", 1900, 2200, 2026, 1,
                                              key="p_base_year")
    with c[1]:
        assessment_lifetime = st.number_input("Analysis period (years)", 1, 200,
                                              int(ASSESSMENT_LIFETIME_YEARS), 1, key="p_period")
    c = st.columns(2)
    with c[0]:
        currency = st.text_input("Currency", "EGP", key="p_ccy")
    with c[1]:
        price_base_year = st.number_input("Price base year", 1900, 2200, 2026, 1,
                                          key="p_price_year")
    assessment_lifetime_source = st.text_input(
        "Analysis-period source", "", key="p_period_src",
        help="Exact document and location fixing the reference study period.")

    st.markdown("---")
    st.markdown("### ✅ Publication readiness")
    _gate_slot = st.empty()

    st.markdown("---")
    with st.expander("⚙️ Advanced — JSON import / export", expanded=False):
        st.caption("For loading a prepared evidence file or saving the current one. "
                   "The forms in the tabs are the intended way to drive the app.")
        up = st.file_uploader("Import evidence JSON", type=["json"], key="p_upload")
        if up is not None:
            try:
                st.session_state["imported_payload"] = json.loads(up.getvalue().decode("utf-8"))
                st.success("Payload imported. It is merged beneath the form inputs.")
            except Exception as exc:
                st.error(f"Invalid JSON upload: {exc}")
        if st.session_state.get("scientific_payload"):
            st.download_button(
                "⬇️ Export current evidence JSON",
                data=json.dumps(st.session_state["scientific_payload"], indent=2,
                                ensure_ascii=False, default=str),
                file_name="monorail_scientific_payload.json",
                mime="application/json", key="p_export_json")

    st.markdown("---")
    run_clicked = st.button("▶️ Run Scientific Assessment", type="primary",
                            use_container_width=True, key="p_run")

# ═══════════════════════════════════════════════════════════════
# TABS — LCA → LCC → K-Benefits → Uncertainty → Results
#        → Audit & references → Exports
# ═══════════════════════════════════════════════════════════════
T_LCA, T_LCC, T_BEN, T_UQ, T_RESULTS, T_AUDIT, T_EXPORT = st.tabs([
    "🔬 LCA inputs & evidence",
    "💰 LCC inputs & evidence",
    "🌱 K-Benefits inputs & evidence",
    "🎲 Uncertainty",
    "📊 Results",
    "📚 Audit & references",
    "📤 Exports",
])

# ── LCA ──────────────────────────────────────────────────────────────────────
with T_LCA:
    st.markdown("### 🔬 Scientific LCA provenance")
    st.caption("Every field feeds the referenced LCA core. Empty fields keep the domain "
               "source-open — nothing is assumed and no default factor is applied.")
    lca_inputs = add_lca_source_inputs(st, assessment_lifetime_default=int(assessment_lifetime))

# ── LCC ──────────────────────────────────────────────────────────────────────
with T_LCC:
    st.markdown("### 💰 Scientific LCC model")
    st.caption("The discount rate and the analysis period each need their own documented "
               "source before any NPV can carry a project headline.")

    c = st.columns(3)
    with c[0]:
        discount_rate = st.number_input("Discount rate (fraction)", 0.0, 1.0, 0.0, 0.001,
                                        format="%.4f", key="l_rate")
    with c[1]:
        discount_basis = st.selectbox("Discount basis", ["real", "nominal"], key="l_basis")
    with c[2]:
        discount_status = st.selectbox("Discount evidence status", EVIDENCE_STATUSES,
                                       key="l_rate_status")
    c = st.columns(2)
    with c[0]:
        discount_src_file = st.text_input("Discount source file", "", key="l_rate_file")
    with c[1]:
        discount_src_loc = st.text_input("Discount exact location", "", key="l_rate_loc")

    c = st.columns(3)
    with c[0]:
        period_status = st.selectbox("Analysis-period evidence status", EVIDENCE_STATUSES,
                                     key="l_per_status")
    with c[1]:
        period_src_file = st.text_input("Analysis-period source file", "", key="l_per_file")
    with c[2]:
        period_src_loc = st.text_input("Analysis-period exact location", "", key="l_per_loc")

    st.markdown("#### 💵 Cost rows")
    st.caption("One row per dated cash flow, each with its own unit, price base year, "
               "escalation, exact source and evidence status.")
    cost_rows_df = st.data_editor(
        pd.DataFrame([{
            "cost_id": "", "phase": "construction", "category": "", "asset": "", "activity": "",
            "project_year": 0, "quantity": 0.0, "unit": "", "unit_cost_base": 0.0,
            "price_base_year": int(price_base_year), "escalation_rate": 0.0,
            "source_file": "", "source_location": "", "evidence_status": "SOURCE-OPEN", "note": "",
        }]), num_rows="dynamic", use_container_width=True, key="l_cost_rows")

    st.markdown("#### ♻️ Residual value rows")
    residual_rows_df = st.data_editor(
        pd.DataFrame([{
            "residual_id": "", "asset": "", "activity": "",
            "project_year": int(assessment_lifetime), "amount_base": 0.0,
            "price_base_year": int(price_base_year), "escalation_rate": 0.0,
            "source_file": "", "source_location": "", "evidence_status": "SOURCE-OPEN", "note": "",
        }]), num_rows="dynamic", use_container_width=True, key="l_residual_rows")

    st.markdown("#### 📋 Phase declarations")
    st.caption("Every phase must be declared. A phase with no rows is not silently zero — "
               "it is a documented zero, out of scope, or still source-open.")
    phase_declarations = {}
    for phase in ("construction", "operation", "maintenance_renewal", "end_of_life"):
        with st.expander(f"Phase: {phase.replace('_', ' ')}", expanded=False):
            pc = st.columns([1.0, 1.2, 1.2])
            with pc[0]:
                p_status = st.selectbox(
                    "Declaration",
                    ["SOURCE-OPEN", "HAS_ROWS", "DOCUMENTED_ZERO", "NOT_APPLICABLE"],
                    key=f"l_ph_{phase}_status")
            with pc[1]:
                p_file = st.text_input("Source file", "", key=f"l_ph_{phase}_file")
            with pc[2]:
                p_loc = st.text_input("Exact location", "", key=f"l_ph_{phase}_loc")
            p_just = st.text_input("Justification", "", key=f"l_ph_{phase}_just")
            p_ev = st.selectbox("Evidence status", EVIDENCE_STATUSES, key=f"l_ph_{phase}_ev")
        phase_declarations[phase] = {
            "status": p_status, "source_file": p_file, "source_location": p_loc,
            "evidence_status": p_ev, "justification": p_just,
        }

# ── K-Benefits ───────────────────────────────────────────────────────────────
with T_BEN:
    st.markdown("### 🌱 Scientific K-Benefits evidence")
    st.caption("A method reference authorises an equation; only PROJECT-SPECIFIC or "
               "OFFICIAL-PROJECT-DATA can carry a project headline. Empty fields stay "
               "source-open.")

    with st.expander("🚈 Transport activity, modal shift and emissions", expanded=True):
        transport = {
            "passengers_per_day": evidence_input(
                "Passengers per day", key="b_pax", unit="passengers/day",
                default_ref="REF-EGY-GB-2022"),
            "avg_distance_km": evidence_input(
                "Average passenger trip distance", key="b_dist", unit="km",
                default_ref="REF-EGY-GB-2022"),
            "operating_days_per_year": evidence_input(
                "Operating days per year", key="b_days", unit="days/year",
                default_ref="REF-EGY-GB-2022",
                help_text="The project's own service calendar. The 365 days inside the "
                          "green bond report is that report's assumption."),
            "modal_shift_fraction": evidence_input(
                "Modal-shift fraction", key="b_modal", unit="fraction",
                default_ref="REF-EGY-GB-2022",
                help_text="A Cairo measurement. The report's 20-50% band and its 30% "
                          "featured case are scenarios, not project evidence."),
            "car_share_of_shift": evidence_input(
                "Car share of displaced travel", key="b_car_share", unit="fraction"),
            "bus_share_of_shift": evidence_input(
                "Bus share of displaced travel", key="b_bus_share", unit="fraction",
                help_text="Car share + bus share must equal 1."),
            "car_emission_factor": evidence_input(
                "Car emission factor", key="b_car_ef", unit="kgCO2e/pkm",
                help_text="Already-CO2e basis; not a gas-specific factor."),
            "bus_emission_factor": evidence_input(
                "Bus emission factor", key="b_bus_ef", unit="kgCO2e/pkm"),
            "project_emission_factor": evidence_input(
                "Monorail emission factor", key="b_proj_ef", unit="kgCO2e/pkm"),
            "annual_trips": evidence_input(
                "Annual trips (existing passengers)", key="b_trips", unit="trips/year",
                default_ref="REF-WB-ENRRP-ICR"),
            "baseline_time_min": evidence_input(
                "Baseline journey time", key="b_t0", unit="min"),
            "project_time_min": evidence_input(
                "Project journey time", key="b_t1", unit="min"),
            "generated_trips": evidence_input(
                "Generated (newly induced) trips", key="b_gen", unit="trips/year",
                default_ref="REF-WB-ENRRP-ICR",
                help_text="Only these receive the Rule of Half; existing passengers keep "
                          "the full time benefit."),
            "value_of_time": evidence_input(
                "Value of travel time", key="b_vot", unit="currency/hour",
                default_ref="REF-EGY-VOT-2022", monetary=True,
                help_text="Currency and price base year are required before any monetary "
                          "benefit is produced."),
        }

    with st.expander("🗺️ Land use around the transit nodes", expanded=False):
        land_use = {
            "analysis_area_id": st.text_input("Analysis area identifier", "", key="b_area_id"),
            "influence_radius_m": evidence_input(
                "TOD influence radius", key="b_radius", unit="m",
                help_text="The Indian national TOD policy's 500-800 m band is a benchmark, "
                          "not the Cairo radius."),
            "baseline_area_by_class": area_table(
                "Baseline land-use areas", key="b_lu_base",
                help_text="e.g. residential = 42.5; commercial = 18.0"),
            "project_area_by_class": area_table(
                "Project land-use areas", key="b_lu_proj",
                help_text="Must use exactly the same class names as the baseline."),
        }
        _base_areas = land_use["baseline_area_by_class"]
        if isinstance(_base_areas, dict) and "value" in _base_areas:
            _base_areas = _base_areas.get("value") or {}
        land_use["class_schema"] = sorted(_base_areas)

    with st.expander("🏙️ Urban growth (SDG 11.3.1)", expanded=False):
        g = st.columns(2)
        with g[0]:
            past_year = st.text_input("Past observation year", "", key="b_yr_past")
        with g[1]:
            present_year = st.text_input("Present observation year", "", key="b_yr_now")

        def _year(v):
            try:
                return int(str(v).strip()) if str(v or "").strip() else None
            except (TypeError, ValueError):
                return None

        urban_growth = {
            "past_year": _year(past_year), "present_year": _year(present_year),
            "built_up_past": evidence_input("Built-up area (past)", key="b_bu_past",
                                            unit="m2", default_ref="REF-UNHABITAT-SDG1131-2025"),
            "built_up_present": evidence_input("Built-up area (present)", key="b_bu_now",
                                               unit="m2", default_ref="REF-UNHABITAT-SDG1131-2025"),
            "population_past": evidence_input("Population (past)", key="b_pop_past",
                                              unit="persons"),
            "population_present": evidence_input("Population (present)", key="b_pop_now",
                                                 unit="persons"),
        }

    with st.expander("👷 Employment", expanded=False):
        employment = {
            "official_construction_jobs": evidence_input(
                "Officially reported construction jobs", key="b_jobs_con", unit="jobs",
                default_ref="REF-EGY-GB-2022",
                help_text="A reported figure. No equation is applied to it."),
            "official_operational_jobs": evidence_input(
                "Officially reported operational jobs", key="b_jobs_ops", unit="jobs",
                default_ref="REF-EGY-GB-2022"),
            "proxy_investment_constant_2015_usd_m": evidence_input(
                "Investment on a constant-2015-USD basis", key="b_proxy_inv",
                unit="million constant 2015 USD", default_ref="REF-MOSZORO-2024",
                help_text="The proxy study standardises money to constant 2015 USD."),
            "jobs_per_musd_proxy": evidence_input(
                "Benchmark jobs per US$1m", key="b_proxy_jc", unit="jobs per US$1m",
                default_ref="REF-MOSZORO-2024",
                help_text="A cross-country benchmark; never 'Cairo jobs created', and never "
                          "added to the official figures."),
        }

    with st.expander("🔊 Noise receptors", expanded=False):
        st.caption("One row per receptor, per metric, per assessment period. Decibel values "
                   "are never averaged across receptors and no percentage is derived from a "
                   "dB difference.")
        noise_df = st.data_editor(
            pd.DataFrame([{"receptor_id": "", "metric": "Lden", "assessment_period": "annual",
                           "baseline_db": 0.0, "project_db": 0.0, "source_file": "",
                           "source_location": "", "geography": ""}]),
            num_rows="dynamic", use_container_width=True, key="b_noise")

# ── Uncertainty ──────────────────────────────────────────────────────────────
with T_UQ:
    st.markdown("### 🎲 Sourced uncertainty propagation")
    st.caption("No default CV or distribution is supplied. Each uncertain parameter must "
               "cite the source of its distribution parameters; dotted paths address the "
               "existing evidence fields.")
    c = st.columns(3)
    with c[0]:
        uq_n = st.number_input("Monte Carlo samples", 1, 200000, 5000, 100, key="u_n")
    with c[1]:
        uq_seed = st.number_input("Random seed", 0, 2_147_483_647, 42, 1, key="u_seed")
    with c[2]:
        proto_status = st.selectbox("Protocol evidence status",
                                    ["SOURCE-OPEN", "PROJECT-SPECIFIC", "OFFICIAL-PROJECT-DATA"],
                                    key="u_status")
    c = st.columns(2)
    with c[0]:
        proto_file = st.text_input("Uncertainty protocol source file", "", key="u_file")
    with c[1]:
        proto_loc = st.text_input("Protocol exact section / table", "", key="u_loc")
    uq_text = st.text_area("Uncertainty specs (JSON list)", "[]", height=200, key="u_specs")
    run_uq = st.button("Run scientific uncertainty", key="u_run")


# ═══════════════════════════════════════════════════════════════
# ASSEMBLE PARAMS AND RUN — the single execution path
# ═══════════════════════════════════════════════════════════════

def _clean_rows(df):
    """Drop template rows the user never filled in.

    An empty editor row is not a zero-cost cash flow; it is an artefact of the
    widget, and treating it as data would put a phantom row in the audit.
    """
    if df is None or getattr(df, "empty", True):
        return []
    out = []
    for row in df.to_dict("records"):
        ident = str(row.get("cost_id") or row.get("residual_id") or "").strip()
        try:
            amount = float(row.get("unit_cost_base") or row.get("amount_base") or 0.0)
        except (TypeError, ValueError):
            amount = 0.0
        if not ident and amount == 0.0:
            continue
        out.append({k: (None if pd.isna(v) else v) for k, v in row.items()})
    return out


def _noise_rows(df):
    """Wrap each receptor level in the evidence envelope the Benefits gate expects."""
    if df is None or getattr(df, "empty", True):
        return []
    rows = []
    for row in df.to_dict("records"):
        rid = str(row.get("receptor_id") or "").strip()
        if not rid:
            continue
        common = {
            "source_file": row.get("source_file", ""),
            "source_location": row.get("source_location", ""),
            "geography": row.get("geography", ""),
            "evidence_status": "PROJECT-SPECIFIC",
        }
        rows.append({
            "receptor_id": rid,
            "metric": row.get("metric", "Lden"),
            "assessment_period": row.get("assessment_period", "annual"),
            "baseline_db": {"value": float(row.get("baseline_db") or 0.0), "unit": "dB", **common},
            "project_db": {"value": float(row.get("project_db") or 0.0), "unit": "dB", **common},
        })
    return rows


def build_params():
    """Collect every form into one scientific payload.

    An imported JSON payload is merged UNDERNEATH the form values, so a stale
    file can never silently override what is on screen.
    """
    params = {
        "project_name": project_name, "country": country, "region": region,
        "analysis_start_year": int(analysis_start_year),
        "assessment_lifetime": int(assessment_lifetime),
        "assessment_lifetime_source": assessment_lifetime_source,
        "currency": currency, "price_base_year": int(price_base_year),
        "publication_mode": True,
        "lcc_scientific_inputs": {
            "model": {
                "discount_rate": float(discount_rate),
                "discount_basis": discount_basis,
                "discount_source_file": discount_src_file,
                "discount_source_location": discount_src_loc,
                "discount_evidence_status": discount_status,
                "analysis_period_source_file": period_src_file,
                "analysis_period_source_location": period_src_loc,
                "analysis_period_evidence_status": period_status,
            },
            "cost_rows": _clean_rows(cost_rows_df),
            "residual_rows": _clean_rows(residual_rows_df),
            "phase_declarations": phase_declarations,
        },
        "benefits_scientific_inputs": {
            "transport": transport,
            "land_use": land_use,
            "urban_growth": urban_growth,
            "employment": employment,
            "input_output": {},
            "noise": {"rows": _noise_rows(noise_df)},
            "formalization": {"evidence_status": "SOURCE-OPEN"},
        },
    }
    params.update(lca_inputs or {})

    imported = st.session_state.get("imported_payload")
    if isinstance(imported, dict):
        merged = dict(imported)
        merged.update({k: v for k, v in params.items() if v not in (None, "", {}, [])})
        return merged
    return params


if run_clicked:
    try:
        payload = build_params()
        st.session_state["scientific_payload"] = payload
        st.session_state["bundle"] = run_scientific_publication_bundle(payload)
        st.session_state.pop("uncertainty", None)
    except Exception as exc:
        st.error(f"Assessment payload error: {exc}")

if run_uq:
    if st.session_state.get("scientific_payload") is None:
        st.warning("Run the scientific assessment first, then propagate uncertainty over it.")
    else:
        try:
            specs = [UncertaintySpec(**x) for x in json.loads(uq_text or "[]")]
            uq = run_scientific_uncertainty(
                st.session_state["scientific_payload"], specs,
                n=int(uq_n), seed=int(uq_seed),
                protocol_source_file=proto_file,
                protocol_source_location=proto_loc,
                protocol_evidence_status=proto_status,
            )
            st.session_state["uncertainty"] = uq
            st.session_state["bundle"] = run_scientific_publication_bundle(
                st.session_state["scientific_payload"], uncertainty_result=uq)
        except Exception as exc:
            st.error(f"Scientific uncertainty blocked: {exc}")

bundle = st.session_state.get("bundle")

# ── Sidebar readiness flags ──────────────────────────────────────────────────
with _gate_slot.container():
    if bundle is None:
        st.caption("Not run yet.")
    else:
        _g = bundle.publication_gate
        for _label, _key in (("LCA", "lca_ready"), ("LCC", "lcc_ready"),
                             ("K-Benefits", "benefits_ready"),
                             ("Uncertainty", "uncertainty_ready"),
                             ("Full Q1 package", "full_q1_ready")):
            st.markdown(f"{'🟢' if _g.get(_key) else '🟠'} {_label}: "
                        f"**{'ready' if _g.get(_key) else 'open'}**")

# ── Results ──────────────────────────────────────────────────────────────────
with T_RESULTS:
    if bundle is None:
        st.info("Fill the evidence tabs, then press **▶️ Run Scientific Assessment** in the "
                "sidebar. Nothing is computed until you do, and nothing is assumed when a "
                "field is left empty.")
    else:
        gate = bundle.publication_gate
        c = st.columns(3)
        with c[0]:
            metric_card("READY" if gate.get("deterministic_publication_ready") else "BLOCKED",
                        "Deterministic domains", "LCA · LCC · K-Benefits",
                        "ready" if gate.get("deterministic_publication_ready") else "blocked")
        with c[1]:
            metric_card("READY" if gate.get("uncertainty_ready") else "OPEN",
                        "Scientific uncertainty", "sourced distributions only",
                        "ready" if gate.get("uncertainty_ready") else "blocked")
        with c[2]:
            metric_card("READY" if gate.get("full_q1_ready") else "BLOCKED",
                        "Full Q1 package", "deterministic + uncertainty",
                        "ready" if gate.get("full_q1_ready") else "blocked")

        if gate.get("open_domains"):
            st.warning("Open domains: " + ", ".join(gate["open_domains"])
                       + " — no legacy value is substituted for any of them.")

        st.markdown("#### System gates")
        st.dataframe(publication_status_table(bundle), use_container_width=True, hide_index=True)

        r_lca, r_lcc, r_ben = st.tabs(["🔬 LCA", "💰 LCC", "🌱 K-Benefits"])

        with r_lca:
            if not bundle.lca.available:
                domain_blocked(bundle.lca, "LCA")
            else:
                if bundle.lca.publication_ready:
                    res = bundle.lca.result
                    m = st.columns(3)
                    with m[0]:
                        metric_card(f"{float(res['gross_A_C_tCO2e']):,.1f}", "Gross A–C",
                                    "tCO₂e", "ready")
                    with m[1]:
                        metric_card(f"{float(res['GWP_kgCO2e_per_pkm']):.5f}", "GWP",
                                    "kgCO₂e/pkm", "ready")
                    with m[2]:
                        metric_card(
                            f"{float(res.get('module_D1_signed_tCO2e_separate', 0.0)):,.1f}",
                            "Module D1", "tCO₂e — reported separately", "ready")
                    st.caption("Module D is reported separately and is never inside the gross total.")
                else:
                    domain_blocked(bundle.lca, "LCA")
                st.markdown("##### Gate detail")
                st.dataframe(gate_table(bundle.lca.gate), use_container_width=True, hide_index=True)

        with r_lcc:
            if not bundle.lcc.available:
                domain_blocked(bundle.lcc, "LCC")
            else:
                if bundle.lcc.publication_ready:
                    rr = bundle.lcc.result.result
                    m = st.columns(2)
                    with m[0]:
                        metric_card(f"{float(rr['lcc_npv']):,.1f}", "LCC NPV",
                                    f"{rr.get('currency', currency)} — cost side only", "ready")
                    with m[1]:
                        metric_card(f"{len(rr.get('cost_rows') or [])}", "Priced cash flows",
                                    "each with its own source", "ready")
                    st.dataframe(pd.DataFrame(rr.get("cost_rows") or []),
                                 use_container_width=True, hide_index=True)
                    st.caption("Benefits never reduce this NPV. Any netting belongs to a "
                               "separately defined CBA module.")
                else:
                    domain_blocked(bundle.lcc, "LCC")
                st.markdown("##### Gate detail")
                st.dataframe(gate_table(bundle.lcc.gate), use_container_width=True, hide_index=True)

        with r_ben:
            if not bundle.benefits.available:
                domain_blocked(bundle.benefits, "K-Benefits")
            else:
                result = bundle.benefits.result
                bgate = result.publication_gate
                if bgate.get("full_publication_ready"):
                    st.success("🟢 Every required Benefits KPI is backed by project evidence.")
                elif bgate.get("partial_publication_ready"):
                    st.warning("🟡 Partially sourced — not publication-ready as a domain. "
                               "Required and still open: "
                               + "; ".join(bgate.get("missing_required_kpis", [])))
                else:
                    st.warning("🟠 Benefits are not publication-ready. What the evidence "
                               "supports was computed; the rest is source-open or blocked.")

                for group, label in (("physical", "🌍 Physical benefits"),
                                     ("monetized_cba", "💰 Monetised CBA benefits"),
                                     ("economic_impact", "🏗️ Economic impact (activity, not welfare)"),
                                     ("employment", "👷 Employment")):
                    rows = [r for r in result.rows if r["result_group"] == group]
                    if rows:
                        st.markdown(f"##### {label}")
                        st.dataframe(benefit_rows_dataframe(rows),
                                     use_container_width=True, hide_index=True)
                st.caption("Four separate groups and no combined 'Total Benefit': avoided "
                           "tCO₂e, monetised hours, gross economic output and job counts are "
                           "not commensurable. Benefits never reduce LCC NPV or LCA Gross A–C.")

                if bgate.get("source_open_items"):
                    with st.expander(f"🟠 Source-open items ({len(bgate['source_open_items'])})"):
                        for item in bgate["source_open_items"]:
                            st.markdown(f"- {item}")
                if bgate.get("blocked_items"):
                    with st.expander(f"🔴 Blocked until evidence closes ({len(bgate['blocked_items'])})"):
                        for item in bgate["blocked_items"]:
                            st.markdown(f"- {item}")

        if st.session_state.get("uncertainty") is not None:
            uq = st.session_state["uncertainty"]
            st.markdown("#### 🎲 Uncertainty")
            st.dataframe(gate_table(uq.publication_gate), use_container_width=True, hide_index=True)
            st.dataframe(uq.summary, use_container_width=True, hide_index=True)

# ── Audit & references ───────────────────────────────────────────────────────
with T_AUDIT:
    st.markdown("### 📚 Audit and references")
    st.caption("From any number on the Results tab: read its equation id here, then the "
               "equation record, then the source document with its exact location and DOI.")

    if bundle is not None and bundle.benefits.available:
        st.markdown("#### Full Benefits KPI audit")
        st.dataframe(benefit_rows_dataframe(bundle.benefits.result.rows),
                     use_container_width=True, hide_index=True)

    with st.expander("📐 Benefits equation registry", expanded=False):
        st.dataframe(pd.DataFrame([{
            "Equation": eq.equation_id, "Name": eq.name, "Formula": eq.formula_text,
            "Unit contract": eq.output_unit_contract,
            "Method sources": "; ".join(eq.method_ref_ids),
            "Exact location": " | ".join(eq.exact_source_locations),
            "Numeric evidence required": "; ".join(eq.required_numeric_evidence),
            "Limitations": eq.limitations,
        } for eq in BENEFITS_EQUATIONS.values()]), use_container_width=True, hide_index=True)

    with st.expander("📚 Reference registry — open the original document", expanded=False):
        st.dataframe(pd.DataFrame([{
            "Ref": r.ref_id, "Title": r.title, "Authors / issuer": r.authors_or_issuer,
            "Year": r.year, "Exact location": r.exact_location, "DOI": r.doi,
            "Official URL": r.official_url, "Geography": r.geography,
            "May back": "; ".join(r.permitted_evidence_statuses),
            "Limitations": r.limitations,
        } for r in BENEFITS_REFERENCES.values()]), use_container_width=True, hide_index=True)
        st.caption("Evidence status describes source authority, geography and traceability. "
                   "It is not a journal-ranking claim.")

    if bundle is not None and bundle.lcc.available:
        with st.expander("💰 LCC cost and residual audit", expanded=False):
            try:
                st.dataframe(scientific_lcc_table(bundle.lcc.result),
                             use_container_width=True, hide_index=True)
            except Exception as exc:
                st.info(f"LCC audit table unavailable: {exc}")

# ── Exports ──────────────────────────────────────────────────────────────────
with T_EXPORT:
    st.markdown("### 📤 Publication exports")
    if bundle is None:
        st.info("Run the assessment first.")
    else:
        gate = bundle.publication_gate
        if not gate.get("deterministic_publication_ready"):
            st.error("Deterministic publication exports are **withheld**. Close the LCA, LCC "
                     "and K-Benefits gates first — an export is what gets cited after it "
                     "leaves this screen.")
        elif not deterministic_export_parity_ok(bundle):
            st.error("Serialized publication export parity failed; downloads **withheld**.")
        else:
            st.success("Deterministic scientific export parity verified.")
            st.dataframe(
                pd.DataFrame(list(deterministic_headline(bundle).items()),
                             columns=["metric", "value"]),
                use_container_width=True, hide_index=True)
            c = st.columns(2)
            with c[0]:
                st.download_button("⬇️ Deterministic scientific CSV",
                                   deterministic_publication_csv(bundle),
                                   file_name="monorail_scientific_deterministic.csv",
                                   mime="text/csv", key="e_csv")
            with c[1]:
                st.download_button(
                    "⬇️ Deterministic scientific Excel",
                    deterministic_publication_excel_bytes(bundle),
                    file_name="monorail_scientific_deterministic.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="e_xlsx")

        if gate.get("full_q1_ready"):
            st.download_button(
                "⬇️ Full Q1 scientific package", full_q1_excel_bytes(bundle),
                file_name="monorail_scientific_full_q1.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="e_q1")
        else:
            st.info("The full Q1 package stays withheld until sourced scientific "
                    "uncertainty is ready.")

        # Per-domain exports carry more provenance columns than the screen does,
        # because a reviewer working from a spreadsheet cannot click through.
        st.markdown("#### Per-domain traceable exports")
        if bundle.benefits.available:
            _ok, _problems = benefits_export_parity_ok(bundle.benefits.result)
            if _ok:
                c = st.columns(3)
                with c[0]:
                    st.download_button("⬇️ Benefits CSV",
                                       scientific_benefits_csv(bundle.benefits.result),
                                       file_name="scientific_benefits.csv",
                                       mime="text/csv", key="e_ben_csv")
                with c[1]:
                    st.download_button(
                        "⬇️ Benefits Excel (8 sheets)",
                        scientific_benefits_excel_bytes(bundle.benefits.result),
                        file_name="scientific_benefits.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="e_ben_xlsx")
                with c[2]:
                    st.download_button(
                        "⬇️ Benefits source appendix",
                        scientific_benefits_source_appendix(bundle.benefits.result),
                        file_name="benefits_source_appendix.txt",
                        mime="text/plain", key="e_ben_app")
            else:
                st.error("Benefits export parity failed; downloads withheld:")
                for _p in _problems[:10]:
                    st.markdown(f"- {_p}")
