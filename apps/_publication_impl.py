"""Publication-only Streamlit entry point for the scientific monorail assessment.

This app intentionally does not import any legacy engine.  It is a thin presentation
layer over the scientific publication orchestrator.  Missing evidence produces a
blocked gate and an audit message; it never produces a substitute legacy headline.

The existing ``app_final_streamlit_ready.py`` remains the Developer/dashboard entry
point for historical comparisons and broad scenario exploration.
"""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from scientific_publication_orchestrator import run_scientific_publication_bundle
from scientific_publication_reporting import (
    deterministic_export_parity_ok,
    deterministic_headline,
    deterministic_publication_csv,
    deterministic_publication_excel_bytes,
    full_q1_excel_bytes,
    publication_status_table,
)
from scientific_uncertainty import UncertaintySpec, run_scientific_uncertainty


st.set_page_config(
    page_title="Monorail Scientific Publication Assessment",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🔬 Monorail Scientific Publication Assessment")
st.caption(
    "Fail-closed scientific path: LCA + LCC + K-Benefits + sourced uncertainty. "
    "No legacy fallback is available in this application."
)

with st.sidebar:
    st.header("Project context")
    project_name = st.text_input("Project name", "Cairo Monorail")
    country = st.text_input("Country", "Egypt")
    region = st.text_input("Region", "Cairo")
    analysis_start_year = st.number_input("Analysis base year", 1900, 2200, 2026, 1)
    assessment_lifetime = st.number_input("Analysis period (years)", 1, 200, 50, 1)
    currency = st.text_input("Currency", "EGP")
    price_base_year = st.number_input("Price base year", 1900, 2200, 2026, 1)

DEFAULT_PAYLOAD = {
    "assessment_lifetime_source": "",
    "lcc_scientific_inputs": {
        "model": {
            "discount_rate": 0.0,
            "discount_basis": "real",
            "discount_source_file": "",
            "discount_source_location": "",
            "discount_evidence_status": "SOURCE-OPEN",
            "analysis_period_source_file": "",
            "analysis_period_source_location": "",
            "analysis_period_evidence_status": "SOURCE-OPEN",
        },
        "cost_rows": [],
        "residual_rows": [],
        "phase_declarations": {},
    },
    "benefits_scientific_inputs": {},
}

st.subheader("Scientific evidence payload")
st.info(
    "Paste or upload the scientific parameter payload. Empty fields remain SOURCE-OPEN. "
    "The application does not invent project values."
)
up = st.file_uploader("Upload JSON payload", type=["json"])
if up is not None:
    try:
        uploaded_payload = json.loads(up.getvalue().decode("utf-8"))
        st.session_state["publication_payload_json"] = json.dumps(
            uploaded_payload, indent=2, ensure_ascii=False
        )
    except Exception as exc:
        st.error(f"Invalid JSON upload: {exc}")

payload_text = st.text_area(
    "Scientific payload JSON",
    value=st.session_state.get(
        "publication_payload_json", json.dumps(DEFAULT_PAYLOAD, indent=2)
    ),
    height=420,
)

run_clicked = st.button("Run deterministic scientific assessment", type="primary")
if run_clicked:
    try:
        payload = json.loads(payload_text or "{}")
        if not isinstance(payload, dict):
            raise ValueError("payload root must be a JSON object")
        payload.update(
            {
                "project_name": project_name,
                "country": country,
                "region": region,
                "analysis_start_year": int(analysis_start_year),
                "assessment_lifetime": int(assessment_lifetime),
                "currency": currency,
                "price_base_year": int(price_base_year),
                "publication_mode": True,
            }
        )
        st.session_state["scientific_payload"] = payload
        st.session_state["scientific_bundle"] = run_scientific_publication_bundle(payload)
        st.session_state.pop("scientific_uncertainty", None)
    except Exception as exc:
        st.error(f"Assessment payload error: {exc}")

bundle = st.session_state.get("scientific_bundle")
if bundle is None:
    st.stop()

st.divider()
st.subheader("Publication gates")
st.dataframe(publication_status_table(bundle), use_container_width=True, hide_index=True)

gate = bundle.publication_gate
c1, c2, c3 = st.columns(3)
c1.metric("Deterministic scientific domains", "READY" if gate.get("deterministic_publication_ready") else "BLOCKED")
c2.metric("Scientific uncertainty", "READY" if gate.get("uncertainty_ready") else "OPEN")
c3.metric("Full Q1 package", "READY" if gate.get("full_q1_ready") else "BLOCKED")

if gate.get("open_domains"):
    st.warning("Open domains: " + ", ".join(gate["open_domains"]))

T_LCA, T_LCC, T_BEN, T_UQ, T_EXPORT = st.tabs(
    ["LCA", "LCC", "K-Benefits", "Uncertainty", "Publication exports"]
)

with T_LCA:
    if not bundle.lca.available:
        st.error("Scientific LCA blocked: " + bundle.lca.error)
    else:
        st.json(bundle.lca.gate)
        if bundle.lca.publication_ready:
            r = bundle.lca.result
            m1, m2, m3 = st.columns(3)
            m1.metric("Gross A-C", f"{float(r['gross_A_C_tCO2e']):,.3f} tCO₂e")
            m2.metric("GWP", f"{float(r['GWP_kgCO2e_per_pkm']):.6f} kgCO₂e/pkm")
            m3.metric("Module D1", f"{float(r.get('module_D1_signed_tCO2e_separate', 0.0)):,.3f} tCO₂e")
        else:
            st.warning("LCA headline withheld until its scientific gate closes.")

with T_LCC:
    if not bundle.lcc.available:
        st.error("Scientific LCC blocked: " + bundle.lcc.error)
    else:
        st.json(bundle.lcc.gate)
        if bundle.lcc.publication_ready:
            rr = bundle.lcc.result.result
            st.metric("LCC NPV", f"{float(rr['lcc_npv']):,.3f} {rr.get('currency', currency)}")
            st.dataframe(pd.DataFrame(rr.get("cost_rows") or []), use_container_width=True)
        else:
            st.warning("LCC headline withheld until numeric evidence and phase declarations close.")

with T_BEN:
    if not bundle.benefits.available:
        st.error("Scientific K-Benefits blocked: " + bundle.benefits.error)
    else:
        st.json(bundle.benefits.gate)
        rows = list(getattr(bundle.benefits.result, "rows", []) or [])
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        if not bundle.benefits.publication_ready:
            st.warning("Benefits domain is not fully publication-ready; non-eligible rows remain clearly labelled.")

with T_UQ:
    st.markdown("### Sourced uncertainty propagation")
    st.caption(
        "No default CV/distribution is supplied. Each uncertain parameter must cite the source "
        "of its distribution parameters. Dotted paths address existing JSON fields."
    )
    uq_text = st.text_area("Uncertainty specs JSON", "[]", height=220)
    uq_n = st.number_input("Monte Carlo samples", 1, 200000, 5000, 100)
    uq_seed = st.number_input("Random seed", 0, 2_147_483_647, 42, 1)
    proto_file = st.text_input("Uncertainty protocol source file")
    proto_loc = st.text_input("Uncertainty protocol exact section/table")
    proto_status = st.selectbox(
        "Protocol evidence status",
        ["SOURCE-OPEN", "PROJECT-SPECIFIC", "OFFICIAL-PROJECT-DATA"],
    )
    if st.button("Run scientific uncertainty"):
        try:
            raw_specs = json.loads(uq_text or "[]")
            specs = [UncertaintySpec(**x) for x in raw_specs]
            uq = run_scientific_uncertainty(
                st.session_state["scientific_payload"],
                specs,
                n=int(uq_n),
                seed=int(uq_seed),
                protocol_source_file=proto_file,
                protocol_source_location=proto_loc,
                protocol_evidence_status=proto_status,
            )
            st.session_state["scientific_uncertainty"] = uq
            st.session_state["scientific_bundle"] = run_scientific_publication_bundle(
                st.session_state["scientific_payload"], uncertainty_result=uq
            )
            st.rerun()
        except Exception as exc:
            st.error(f"Scientific uncertainty blocked: {exc}")

    uq = st.session_state.get("scientific_uncertainty")
    if uq is not None:
        st.json(uq.publication_gate)
        st.dataframe(uq.summary, use_container_width=True, hide_index=True)
        st.dataframe(uq.audit, use_container_width=True, hide_index=True)

with T_EXPORT:
    if not bundle.publication_gate.get("deterministic_publication_ready"):
        st.error(
            "Deterministic publication exports are withheld. Close LCA, LCC and K-Benefits gates first."
        )
    else:
        parity = deterministic_export_parity_ok(bundle)
        if not parity:
            st.error("Serialized publication export parity failed; downloads withheld.")
        else:
            st.success("Deterministic scientific export parity verified.")
            st.json(deterministic_headline(bundle))
            st.download_button(
                "Download deterministic scientific CSV",
                deterministic_publication_csv(bundle),
                file_name="monorail_scientific_deterministic.csv",
                mime="text/csv",
            )
            st.download_button(
                "Download deterministic scientific Excel",
                deterministic_publication_excel_bytes(bundle),
                file_name="monorail_scientific_deterministic.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    if bundle.publication_gate.get("full_q1_ready"):
        st.download_button(
            "Download full Q1 scientific package",
            full_q1_excel_bytes(bundle),
            file_name="monorail_scientific_full_q1.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    else:
        st.info("Full Q1 package remains withheld until sourced scientific uncertainty is ready.")
