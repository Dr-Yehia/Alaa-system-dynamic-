# K-Benefits Q1 Scientific Upgrade — Programmer Handoff

> **Repository:** `Dr-Yehia/Alaa-system-dynamic-`  
> **Target branch reviewed:** `claude/lcc-q1-scientific-core`  
> **Pinned starting SHA for this handoff:** `19005f62b69aff7a649fb2ca8493be2277ada06b`  
> **Pinned tree:** `424091a9bb7c9112b01afcf92ec0e09d6da03f61`  
> **Verified GitHub Actions run:** `31573100778` — completed / success  
> **Intended repository location for this handoff:** `docs/K_BENEFITS_Q1_SCIENTIFIC_PROGRAMMER_HANDOFF.md`  
> **Scope:** scientific Benefits / co-benefits / transport CBA support only.  
> **Source/link verification date:** 2026-08-12  
> **Do not change scientific LCA equations or scientific LCC equations as part of this work.**

---

## 0. READ THIS FIRST — NON-NEGOTIABLE SCIENTIFIC CONTRACT

This document is not a suggestion list. It is the implementation contract for upgrading the current legacy Benefits calculations into a traceable scientific K-Benefits subsystem suitable for a manuscript intended for a high-quality Q1 journal submission.

The most important rule is:

> **NO SCIENTIFIC EQUATION MAY EXIST IN THE CODE WITHOUT AN IMMEDIATELY TRACEABLE METHOD SOURCE.**

For every equation implemented in Python, the programmer must provide **both**:

1. a compact but complete source comment **on the same code line after `#`**, and  
2. a full machine-readable record in `benefits_reference_registry.py` and `BENEFIT_EQUATIONS`.

A reviewer must be able to travel this path without guessing:

**UI/result → KPI ID → Equation ID → exact Python line → Reference ID → full source title → author/issuer → year → DOI/official URL → exact page/annex/equation/table → evidence role → limitations.**

A second equally important rule is:

> **THE SOURCE OF AN EQUATION IS NOT THE SOURCE OF A NUMERICAL VALUE.**

Example: the World Bank may support the time-saving valuation method, but that does **not** automatically validate a 2026 Cairo value of time. A numerical VOT must have its own evidence record, geography, unit, price base year, and source location.

### 0.1 Evidence roles that must be kept separate

Use these statuses consistently:

- `METHOD-REFERENCE` — supports a method/equation only.
- `PROJECT-SPECIFIC` — project-specific evidence supplied for this assessment.
- `OFFICIAL-PROJECT-DATA` — official project report/data.
- `REF-PROXY` — literature/reference proxy; useful for comparison or sensitivity, not project truth.
- `SOURCE-OPEN` — required source not yet supplied/verified.
- `SCENARIO-ONLY` — explicit scenario assumption, never a publication fact.

### 0.2 Prohibited scientific shortcuts

The programmer must **not**:

- invent a missing source;
- invent a page number, DOI, report number, title, geography, price year, or unit;
- treat a journal method paper as evidence for a Cairo project number;
- treat an official project number as a universal parameter;
- use a `SCENARIO-ONLY` or `SOURCE-OPEN` value in a Publication headline;
- silently convert currency or price year;
- silently clamp a negative “benefit” to zero;
- add official reported jobs to model-estimated jobs;
- convert dB differences into percentages by simple division;
- add jobs, gross economic output, land-use diversity, or physical CO2 savings into one monetary total;
- subtract any Benefit from `LCC_NPV`;
- subtract any Benefit from LCA Gross A-C carbon;
- add scientific equations to `assessment_orchestrator.py`, `shared_activity.py`, or `project_context.py`.

---

# 1. WHAT WAS VERIFIED IN THE CURRENT CODE BEFORE WRITING THIS HANDOFF

The repository was reviewed at SHA:

`19005f62b69aff7a649fb2ca8493be2277ada06b`

The current architecture is already much cleaner than the old monolith.

## 1.1 Current relevant files

At the pinned SHA the relevant root files are:

- `app_final_streamlit_ready.py`
- `assessment_orchestrator.py`
- `benefits_core.py`
- `shared_activity.py`
- `project_context.py`
- `uncertainty_orchestrator.py`
- `legacy_lca_engine.py`
- `legacy_lcc_engine.py`
- `lca_scientific_core.py`
- `lca_scientific_integration.py`
- `lca_scientific_reporting.py`
- `lcc_scientific_core.py`
- `.github/workflows/tests.yml`

Relevant tests already include:

- `tests/benefits_independence_test.py`
- `tests/domain_dependency_test.py`
- `tests/params_classification_test.py`
- `tests/app_layer_purity_test.py`
- `tests/full_separation_parity_test.py`
- `tests/architecture_baseline_pin.py`

The branch-head commit states that the app is now primarily UI/orchestration, legacy LCA was extracted, parameter ownership is explicit, Monte Carlo uses separated evaluation, and legacy LCC is no longer shown as a Publication headline. The current workflow passed at the reviewed head.

## 1.2 `benefits_core.py` is NOT yet a scientific publication engine

Current file:

`benefits_core.py`

Current purpose is legacy/extracted arithmetic with domain independence.

Its module docstring explicitly states that the equations/defaults/units were moved unchanged from the old monolith. That is useful for architectural separation and backward compatibility, but it does **not** make the calculations scientifically sourced.

Current function:

`calculate_benefit_kpis(params, annual_pkm, lifetime_years=...)`

currently performs approximately:

- avoided CO2 from a baseline intensity minus monorail intensity;
- time saving from trips × minutes;
- VOT monetization;
- jobs from jobs-per-$M × CAPEX;
- economic impact from CAPEX × a scalar multiplier;
- land footprint per million passenger-km;
- dB reduction and a dB “ratio”.

These are precisely the calculations that need a new scientific path.

### 1.2.1 Scientific issues in the current legacy Benefits code

The new scientific engine must correct these issues without changing the legacy parity path:

1. `max(ef_base - ef_mono, 0.0)` hides a negative avoided-emission result.  
   **Scientific result must preserve the signed difference.**

2. `ef_mono = energy_per_pax * carbon_intensity` uses generic shared/legacy fields without Benefits-specific evidence.  
   Scientific Benefits must require a documented factor route and must never import an LCA result.

3. VOT output is currently labelled in `$` without a complete currency/price-base contract.  
   Scientific monetization must carry currency and price base year.

4. `jobs_per_musd * capex` is only defensible as a proxy if the monetary basis matches the proxy study, e.g. constant 2015 USD for the Moszoro benchmark. It is not automatically “Cairo jobs”.

5. `capex * economic_multiplier` is too weak for a main scientific input-output claim. It may remain a legacy display/proxy, but the scientific pathway should implement or accept the Leontief structure.

6. `land_ha / Mpkm` is a descriptive ratio, not the TOD entropy/LUD or UN-Habitat land-consumption method.

7. `noise_reduction_ratio = delta_dB / baseline_dB` must **not** be used as a scientific percentage reduction because decibels are logarithmic.

8. Current Benefits inputs contain numbers but do not require exact source page/table/URL/geography.

## 1.3 `assessment_orchestrator.py` has the correct architectural role

Current architecture is:

`ProjectContext + SharedActivity → LCA / LCC / Benefits → assessment_orchestrator → UI`

This is correct.

`assessment_orchestrator.py` must remain an **assembly/call-sequence module**, not a scientific-math module.

It currently has explicit ownership sets:

- `LCA_PARAM_KEYS`
- `LCC_PARAM_KEYS`
- `BENEFITS_PARAM_KEYS`
- `MULTI_DOMAIN_PARAM_KEYS`
- `CONTEXT_PARAM_KEYS`

and `unclassified_params()` catches future keys that were not deliberately classified.

This behavior must be preserved.

## 1.4 `shared_activity.py` is the correct neutral physical layer

The current `SharedActivity` contains neutral physical facts such as:

- `served_annual_pkm`
- `lifetime_pkm`
- `annual_operational_kwh`
- intervention schedule
- use-stage/EOL scope flags
- condition trajectory

It explicitly forbids:

- carbon factors;
- tariffs;
- discounting;
- costs;
- jobs;
- time valuation;
- economic multiplier.

**Do not put Benefits equations or Benefit valuations in this file.**

Scientific Benefits may **consume** neutral physical activity from `SharedActivity`.

## 1.5 `project_context.py` is metadata, not evidence

Current defaults such as Cairo/Egypt, 2026, EGP, and 50 years are scenario/UI defaults.

They must never be treated as proof that a publication input is sourced.

The scientific Benefits gate must still require evidence where required.

## 1.6 Current app Benefits UI is not sufficient for Publication

Stable search anchor in `app_final_streamlit_ready.py`:

`# ── R15: Benefit (co-benefit) KPIs — reported SEPARATELY, never netted into LCA ──`

Current inputs include:

- `benefit_baseline_ci_pkm`
- `benefit_annual_trips`
- `benefit_time_saved_min`
- `benefit_value_of_time`
- `benefit_jobs_per_musd`
- `benefit_operational_jobs`
- `benefit_land_ha`
- `benefit_noise_baseline_db`
- `benefit_noise_monorail_db`

They currently have no complete provenance form.

Another stable search anchor:

`with st.expander("🌱 Benefit KPIs (societal co-benefits — separate from LCA carbon)"`

The current result expander displays legacy Benefits values even in the main Results path.

**This must change.**

Publication mode must never silently show these legacy numbers as scientific Benefits.

---

# 2. TARGET ARCHITECTURE

The target architecture is:

```text
ProjectContext                 SharedActivity
    |                               |
    +---------------+---------------+
                    |
          benefits_scientific_inputs
                    |
                    v
      benefits_scientific_integration.py
                    |
                    v
          benefits_scientific_core.py
                    |
                    v
        benefits_scientific_reporting.py
                    |
                    v
                 UI / Export
```

References are provided by:

```text
benefits_reference_registry.py
      |                |
      |                +--> BENEFIT_EQUATIONS
      +-------------------> BENEFIT_REFERENCES
```

### Strict dependency rule

`benefits_scientific_core.py` must import:

- Python standard library;
- `numpy` only if needed for I-O matrix operations;
- Benefits-owned schemas/registry.

It must **not** import:

- `lca_scientific_core`
- `lca_scientific_integration`
- `legacy_lca_engine`
- `lcc_scientific_core`
- `legacy_lcc_engine`
- `streamlit`

Scientific Benefits may receive a `SharedActivity` object through integration, but must never ask LCA for a result.

---

# 3. FILES TO CREATE

Create these new root files first; keep the current flat repository layout.

## 3.1 `benefits_reference_registry.py`

Purpose:

- canonical source registry;
- canonical equation registry;
- exact traceability metadata;
- no UI;
- no calculations other than registry validation helpers.

## 3.2 `benefits_scientific_core.py`

Purpose:

- pure deterministic scientific Benefits calculations;
- no Streamlit;
- no LCA/LCC engine imports;
- no hidden default values;
- no unsourced project numbers.

## 3.3 `benefits_scientific_integration.py`

Purpose:

- adapt app/project evidence into typed scientific Benefits inputs;
- validate evidence completeness;
- connect `ProjectContext` and `SharedActivity`;
- call scientific core;
- produce the publication gate and audit;
- no Streamlit import.

## 3.4 `benefits_scientific_reporting.py`

Purpose:

- result tables;
- CSV;
- Excel;
- reviewer/source appendix;
- equation/source audit export;
- no scientific recomputation.

## 3.5 New tests

Create:

- `tests/benefits_scientific_core_test.py`
- `tests/benefits_reference_integrity_test.py`
- `tests/benefits_scientific_integration_test.py`
- `tests/benefits_publication_gate_test.py`

Also update existing:

- `tests/benefits_independence_test.py`
- `tests/domain_dependency_test.py`
- `tests/params_classification_test.py`
- `tests/app_layer_purity_test.py`
- `.github/workflows/tests.yml`

---

# 4. FILES THAT MUST NOT BE SCIENTIFICALLY MODIFIED IN THIS BENEFITS TASK

Do **not** change formulas/factors/meaning in:

- `lca_scientific_core.py`
- `lca_scientific_integration.py`
- `lca_scientific_reporting.py`
- `lcc_scientific_core.py`

Do not refactor them “for consistency” during this work.

Do not alter the existing pinned legacy LCA/LCC outputs merely to make Benefits integration easier.

If a neutral field is genuinely needed, modify the neutral boundary explicitly and add tests; do not import another domain.

---

# 5. WHAT TO DO WITH CURRENT `benefits_core.py`

Do **not** delete it now.

Keep it as:

**LEGACY / DEVELOPER / BACKWARD-COMPATIBILITY ONLY**

Add a stronger module warning near the top, but do not change legacy arithmetic in the same commit as the scientific implementation.

Required wording concept:

```python
# LEGACY-DEVELOPER-ONLY.
# This module preserves historical dashboard arithmetic and parity.
# It is NOT the Publication scientific Benefits engine.
# Publication Benefits must come only from benefits_scientific_core.py +
# benefits_scientific_integration.py + benefits_scientific_reporting.py.
```

Later, after scientific Benefits passes all gates and the legacy UI is fully gated, a separate cleanup commit may rename it to `legacy_benefits_engine.py`.

**Do not rename it in the first scientific commit.**

---

# 6. TWO-LEVEL TRACEABILITY CONTRACT

## 6.1 Level A — source after `#` on the equation line

Every scientific equation line must use this general pattern:

```python
result = expression  # EQ=BEN-XXXX-01 | REF=REF-... | TITLE=Full source title | ISSUER/AUTHORS=... | YEAR=... | LOC=exact page/annex/equation/table | DOI=... | URL=...
```

If a DOI does not exist, write `DOI=n/a`.

If the source is an official report, use its official URL.

Never write only:

```python
# World Bank
```

or:

```python
# literature
```

or:

```python
# Q1 source
```

Those are unacceptable.

## 6.2 Level B — full registry

Every `REF-*` must have a full record.

Every `BEN-*` equation must have a full equation record.

The inline comment is for immediate human inspection. The registry is for complete auditability and automated testing.

---

# 7. REQUIRED REFERENCE SCHEMA

In `benefits_reference_registry.py`, implement at minimum:

```python
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class ReferenceRecord:
    ref_id: str
    title: str
    authors_or_issuer: str
    year: int
    document_type: str
    doi: str
    official_url: str
    local_source_file: str
    exact_location: str
    geography: str
    evidence_role: str
    units_or_basis: str
    price_base_year: Optional[int] = None
    evidence_status: str = "METHOD-REFERENCE"
    limitations: str = ""
    notes: str = ""

@dataclass(frozen=True)
class EquationRecord:
    equation_id: str
    name: str
    formula_text: str
    output_unit_contract: str
    method_ref_ids: tuple[str, ...]
    exact_source_locations: tuple[str, ...]
    evidence_role: str
    geography_rule: str
    publication_status: str
    required_numeric_evidence: tuple[str, ...]
    limitations: str = ""
    double_count_rule: str = ""
```

Also implement integrity checks:

- every equation Ref ID exists;
- every reference has title;
- every reference has official URL or DOI;
- every equation has exact location;
- every equation has a unit contract;
- no reference has `Q1=True` or a hard-coded quartile claim;
- `SOURCE-OPEN` equations cannot be marked Publication-ready.

---

# 8. CANONICAL REFERENCES TO REGISTER

The records below are the minimum set already reviewed for this phase.

## REF-EGY-GB-2022

**Title:** Egypt Sovereign Green Bond Allocation & Impact Report - 2022  
**Issuer:** Ministry of Finance / Government of Egypt  
**Year:** 2022  
**Type:** Official government impact report  
**Official PDF:**  
`https://assets.mof.gov.eg/files/2022-12/d3dec230-8900-11ed-ad5c-d5697d806e26.pdf`  
**Local reviewed file:** `d3dec230-8900-11ed-ad5c-d5697d806e26-1.pdf`  
**Exact method location:** Annex 1: Impact Reporting Methodology, printed pp. 30-31, GHG Methodology Used for Monorail  
**Geography:** Egypt / Cairo Monorail  
**Role:** method + official project context/data where explicitly stated  
**Key methodological support:**

- Emissions = Activity Data × Emissions Factor × Global Warming Potential.
- projected ridership + average passenger distance are used to derive annual passenger travel.
- report assumes 365 operating days for its own calculation.
- avoided emissions are assessed from modal shift from car/bus to monorail.
- report discusses 20-50% modal-shift scenarios.
- featured project page reports a 30% expected car/bus-to-rail switching scenario weighted to green bond finance.
- featured project page reports up to 4,000 construction jobs and approximately 450 operational jobs.

**Critical limitation:**  
20-50%, 30%, 365 days, and UK emission factors in that report are **not universal constants**. They may not be hard-coded as present Cairo evidence unless the exact assessment uses that official scenario intentionally and labels it correctly.

---

## REF-TRD-MODAL-2024

**Title:** Using different transport modes: An opportunity to reduce UK passenger transport emissions?  
**Authors:** Hugh Thomas; André Cabrera Serrenho  
**Journal:** Transportation Research Part D: Transport and Environment  
**Volume/Article:** 126 (2024), 103989  
**DOI:** `10.1016/j.trd.2023.103989`  
**DOI URL:** `https://doi.org/10.1016/j.trd.2023.103989`  
**Role:** METHOD-REFERENCE  
**Geography:** United Kingdom  
**Use:** supports distance/activity × emissions conversion-factor logic and modal-shift avoided-emissions methodology.  
**Limitation:** UK numerical factors must not be treated as Cairo project factors.

---

## REF-WB-ENRRP-ICR

**Title:** Egypt National Railways Restructuring Project (P101103) — Implementation Completion and Results Report  
**Issuer:** The World Bank  
**Report No.:** ICR00005398  
**Project ID:** P101103  
**Official PDF:**  
`https://documents1.worldbank.org/curated/en/367961628584958285/pdf/Egypt-Railways-Restructuring-Project.pdf`  
**Local reviewed file:** `Egypt-Railways-Restructuring-Project.pdf`  
**Exact method location:** Annex 4, Efficiency Analysis, printed pp. 71-72  
**Role:** METHOD-REFERENCE, Egyptian rail context  
**Key support:**

- time savings are valued using time difference, traffic and value of time;
- generated traffic uses the Rule of Half;
- diverted traffic/generalized-cost logic is described;
- economic analysis is explicit about time horizon and assumptions.

**Critical rule:**  
Rule-of-half applies to **generated traffic**, not all existing passengers.

---

## REF-EGY-VOT-2022

**Title:** Estimation of Cross Classified Value of Travel Time Using Binary Logit Model on Egyptian Roads  
**Authors:** Heba M. Bakry; Yusra M. H. Elgohary; Aya Farag; Ibrahim M. I. Ramadan  
**Journal:** The Open Transportation Journal  
**Year/Volume:** 2022, Volume 16  
**Article:** e187444782209140  
**DOI:** `10.2174/18744478-v16-e2209140`  
**Publisher URL:**  
`https://opentransportationjournal.com/VOLUME/16/ELOCATOR/e187444782209140/FULLTEXT/`  
**Exact equation location:** theoretical framework, formula defining VOT from the ratio of time and cost coefficients; reviewed PDF pp. 3-4  
**Geography:** Egypt  
**Role:** METHOD-REFERENCE; historical numeric evidence only when price-year basis is respected  
**Equation:** VOT = (beta_time / beta_cost) × 60, with the source’s unit convention.

**Reported study values include:** private car 32.5 LE/h and public transport 18.3 LE/h.

**Critical limitation:**  
Do not mechanically escalate these values to 2026 until the source price year and the selected official price index / deflator methodology are explicitly documented.

---

## REF-PLOS-TOD-2023

**Title:** A framework to measure transit-oriented development around transit nodes: Case study of a mass rapid transit system in Dhaka, Bangladesh  
**Authors:** Md. Anwar Uddin; Md. Shamsul Hoque; Tahsin Tamanna; Saima Adiba; Shah Md. Muniruzzaman; Mohammad Shahriyar Parvez  
**Journal:** PLOS ONE  
**Year:** 2023  
**Volume:** 18(1)  
**Article:** e0280275  
**DOI:** `10.1371/journal.pone.0280275`  
**Official URL:**  
`https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0280275`  
**Exact location:** paper page 9, Land use diversity (LUD), Equations (1) and (2)  
**Role:** METHOD-REFERENCE  
**Geography:** Dhaka, Bangladesh

**CRITICAL VISUAL VERIFICATION:**  
The actual rendered equation contains a **leading minus sign**:

LUD = - Σ p_i ln(p_i) / ln(n)

The plain text extraction can lose this sign. The implementation must use the minus sign.

---

## REF-INDIA-TOD-POLICY-2017

**Title:** National Transit Oriented Development (TOD) Policy  
**Issuer:** Government of India, Ministry responsible for Housing and Urban Affairs / Urban Development  
**Year:** 2017  
**Official PDF:**  
`https://mohua.gov.in/upload/whatsnew/59a4070e85256Transit_Oriented_Developoment_Policy.pdf`  
**Exact location:** influence-zone discussion; policy describes approximately 500-800 m walking-distance influence zones  
**Role:** METHOD/POLICY REFERENCE  
**Geography:** India

**Critical limitation:**  
500-800 m is a policy benchmark. It is **not automatically the Cairo project influence radius**.

---

## REF-UNHABITAT-SDG1131-2025

**Title:** Metadata for SDG Indicator 11.3.1 — Ratio of land consumption rate to population growth rate  
**Custodian/Issuer:** UN-Habitat / UN SDG metadata system  
**Reviewed version date:** 2025-04-23  
**Official metadata PDF URL:**  
`https://unstats.un.org/sdgs/metadata/files/Metadata-11-03-01.pdf`  
**Official UN-Habitat learning/landing support:**  
`https://learn.unhabitat.org/enrol/index.php?id=35`  
**Local reviewed file:** `Metadata-11-03-01.pdf`  
**Exact locations:** reviewed pp. 7-9  
**Role:** METHOD-REFERENCE  
**Geography:** global SDG methodology

Supports:

- annual Land Consumption Rate;
- annual Population Growth Rate;
- LCR/PGR ratio;
- built-up area per capita;
- total built-up area change.

**Critical rule:**  
LCR and PGR must use the same analysis years/period.

---

## REF-EGY-IO-ALAYOUTY-2022

**Title:** Identifying Activities for Greater Employment Generation in Egypt: An Input-Output Analysis  
**Author:** Iman Al-Ayouty  
**Publisher/Series:** African Economic Research Consortium, GSYE Working Paper GSYE-007  
**Year:** 2022  
**Official item page:**  
`https://publication.aercafricalibrary.org/items/035e42e5-5fbb-416e-932a-494a2fd50965`  
**Official PDF/download:**  
`https://publication.aercafricalibrary.org/bitstreams/a9dd0022-4282-48dd-94f9-4f9f29c8f2c6/download`  
**Local reviewed file:** `Identifying-activities-for-greater-employment-generation-in-Egypt-An-input-output-analysis.pdf`  
**Exact locations:** methodology pp. 11-12; results tables later in paper  
**Role:** METHOD-REFERENCE + HISTORICAL/REF-PROXY numerical evidence  
**Data basis:** Egypt 2016-2017 input-output table.

Supports:

- technical coefficients;
- Leontief inverse;
- output multiplier;
- employment multiplier;
- employment-effect statistic.

**Critical limitation:**  
The numerical multipliers are historical. The paper itself discusses a limited typical stability window. Do not label the 2016-2017 multipliers as current 2026 Cairo project truth.

---

## REF-MOSZORO-2024

**Title:** The direct employment impact of public investment  
**Author:** Marian W. Moszoro  
**Journal:** International Journal of Management and Economics  
**Year:** 2024  
**Volume/Issue:** 60(1)  
**Pages:** 59-74  
**DOI:** `10.2478/ijme-2023-0020`  
**Official article:**  
`https://reference-global.com/article/10.2478/ijme-2023-0020`  
**Official PDF:**  
`https://reference-global.com/download/article/10.2478/ijme-2023-0020.pdf`  
**Role:** REF-PROXY  
**Data basis:** firm-level infrastructure-construction data across countries; study values are stated in US$1 million investment terms.

The reviewed paper reports approximately 10-17 jobs per US$1m in emerging market economies, with detailed scenario ranges in its tables.

**Critical basis rule:**  
The paper standardizes revenue to constant 2015 USD using GDP deflators. A model using this proxy must match or transparently convert to the same monetary basis.

---

## REF-RAIL-CBA-2026

**Title:** Cost-Benefit Analysis of Regional Railway Modernization with Emphasis on Investment Costs and Electrification  
**Authors:** Brumercik et al.  
**Journal:** Applied Sciences  
**Year:** 2026  
**Volume/Issue:** 16(9)  
**Article:** 4222  
**DOI:** `10.3390/app16094222`  
**Official URL:**  
`https://www.mdpi.com/2076-3417/16/9/4222`  
**Role:** METHOD-REFERENCE / supplementary rail CBA support  
**Geography:** Slovakia  
**Limitation:** do not transfer Slovak numerical values to Cairo.

---

## REF-EU-NOISE-2002

**Title:** Directive 2002/49/EC relating to the assessment and management of environmental noise  
**Issuer:** European Parliament and Council  
**Official URL:**  
`https://eur-lex.europa.eu/eli/dir/2002/49/oj/eng`  
**Role:** METHOD/STANDARD-REFERENCE  
**Support:** use of Lden for overall annoyance and Lnight for sleep disturbance.

---

## REF-EU-CNOSSOS-2015

**Title:** Commission Directive (EU) 2015/996 establishing common noise assessment methods according to Directive 2002/49/EC  
**Issuer:** European Commission  
**Official URL:**  
`https://eur-lex.europa.eu/eli/dir/2015/996/oj/eng`  
**Role:** METHOD/STANDARD-REFERENCE

---

## REF-EU-EXTCOST-2019

**Title:** Handbook on the external costs of transport  
**Issuer:** European Commission, DG MOVE / Publications Office of the European Union  
**Year:** 2019  
**DOI:** `10.2832/27212`  
**Official URL:**  
`https://op.europa.eu/en/publication-detail/-/publication/e021854b-a451-11e9-9d01-01aa75ed71a1`  
**Role:** METHOD-REFERENCE for external-cost valuation framework  
**Critical limitation:** no Cairo noise monetization may be produced until exposure, population and valuation transfer/basis are explicitly supported.

---

# 9. EQUATION REGISTRY — MINIMUM REQUIRED SET

The scientific registry must contain at least these IDs:

| Equation ID | Name | Publication status now |
|---|---|---|
| `BEN-PKM-01` | Annual passenger-km | method ready; numeric evidence required |
| `BEN-MODAL-01` | Shifted passenger-km | method ready; modal-shift fraction evidence required |
| `BEN-MODE-SPLIT-01` | Car/bus shifted allocation | method algebra ready; split evidence required |
| `BEN-GHG-GAS-01` | gas-specific activity × EF × GWP | method ready |
| `BEN-GHG-CO2E-01` | activity × CO2e factor | method ready |
| `BEN-GHG-AVOID-01` | baseline minus project emissions | method ready |
| `BEN-TIME-01` | passenger-hours saved | method ready |
| `BEN-TIME-MONEY-01` | monetary time benefit | method ready; VOT evidence required |
| `BEN-GEN-TRAFFIC-01` | generated-traffic Rule of Half | method ready; only generated traffic |
| `BEN-VOT-01` | VOT from logit coefficients | method ready |
| `BEN-LU-SHARE-01` | land-use share | method ready |
| `BEN-LUD-01` | normalized Shannon land-use diversity | method ready |
| `BEN-LUD-DELTA-01` | project minus baseline LUD | derived comparison |
| `BEN-BUILTUP-CHANGE-01` | total built-up area change | method ready |
| `BEN-LCR-01` | land consumption rate | method ready |
| `BEN-PGR-01` | population growth rate | method ready |
| `BEN-LCRPGR-01` | ratio LCR/PGR | method ready |
| `BEN-BUILTUP-PC-01` | built-up area per capita | method ready |
| `BEN-IO-A-01` | technical coefficients | method ready |
| `BEN-IO-L-01` | Leontief inverse | method ready |
| `BEN-IO-DELTA-01` | output response | method ready |
| `BEN-IO-OMULT-01` | output multiplier | method ready |
| `BEN-IO-EMULT-01` | employment multiplier | method ready |
| `BEN-JOBS-PROXY-01` | jobs-per-investment proxy | proxy only |
| `BEN-NOISE-PHYS-01` | same-metric receptor noise difference | conditional |
| `BEN-FORMALIZATION-*` | formalization | **DO NOT IMPLEMENT — SOURCE-OPEN** |

---

# 10. EQUATION-BY-EQUATION IMPLEMENTATION CONTRACT

## 10.1 `BEN-PKM-01` — Annual passenger-km

Scientific equation:

\( PKM_y = P_{day,y} \times d_{avg,y} \times D_y \)

Where:

- \(P_{day,y}\) = passengers/day in year y
- \(d_{avg,y}\) = average passenger distance, km/passenger
- \(D_y\) = operating days/year
- result = passenger-km/year

### Source

`REF-EGY-GB-2022`  
Annex 1, GHG Methodology Used for Monorail, printed pp. 30-31.

### Inline code comment required

```python
annual_pkm = passengers_per_day * avg_distance_km * operating_days_per_year  # EQ=BEN-PKM-01 | REF=REF-EGY-GB-2022 | TITLE=Egypt Sovereign Green Bond Allocation & Impact Report - 2022 | ISSUER=Ministry of Finance, Government of Egypt | LOC=Annex 1, GHG Methodology Used for Monorail, printed pp.30-31 | DOI=n/a | URL=https://assets.mof.gov.eg/files/2022-12/d3dec230-8900-11ed-ad5c-d5697d806e26.pdf
```

### Publication rules

- all three numerical inputs require evidence;
- do not silently use 365;
- if `SharedActivity.served_annual_pkm` is used, its provenance must be exposed through integration/audit.

---

## 10.2 `BEN-MODAL-01` — Shifted passenger-km

\( PKM_{shift,y} = PKM_y \times MS_y \)

Where \(MS_y\) is a fraction in [0,1].

Source context: `REF-EGY-GB-2022` + `REF-TRD-MODAL-2024`.

Required comment:

```python
shifted_pkm = annual_pkm * modal_shift_fraction  # EQ=BEN-MODAL-01 | REF=REF-EGY-GB-2022;REF-TRD-MODAL-2024 | TITLE=Egypt Sovereign Green Bond Allocation & Impact Report - 2022; Using different transport modes: An opportunity to reduce UK passenger transport emissions? | LOC=Egypt report Annex 1 modal-shift methodology; TRD modal-shift method | DOI=10.1016/j.trd.2023.103989 | URL=https://assets.mof.gov.eg/files/2022-12/d3dec230-8900-11ed-ad5c-d5697d806e26.pdf
```

Do not hard-code 0.30.

---

## 10.3 `BEN-MODE-SPLIT-01` — shifted car/bus allocation

\( PKM_{car}=PKM_{shift}s_{car} \)

\( PKM_{bus}=PKM_{shift}s_{bus} \)

with:

\( s_{car}+s_{bus}=1 \)

This is an algebraic allocation supporting the source-backed modal-shift framework.

The **shares are numerical project/scenario inputs** and require their own evidence.

The core must reject a sum outside a small tolerance such as `1e-9`.

---

## 10.4 `BEN-GHG-GAS-01` — gas-specific emissions

When the factor is gas-specific rather than already CO2e:

\( E = Activity \times EF_{gas} \times GWP_{gas} \)

Source: `REF-EGY-GB-2022`, Annex 1.

Required comment:

```python
emissions_co2e = activity * emission_factor_gas * gwp  # EQ=BEN-GHG-GAS-01 | REF=REF-EGY-GB-2022 | TITLE=Egypt Sovereign Green Bond Allocation & Impact Report - 2022 | ISSUER=Ministry of Finance, Government of Egypt | LOC=Annex 1, GHG Methodology Used for Monorail, printed pp.30-31 | DOI=n/a | URL=https://assets.mof.gov.eg/files/2022-12/d3dec230-8900-11ed-ad5c-d5697d806e26.pdf
```

### Critical double-count prevention

If EF is already in `kgCO2e/pkm`, `kgCO2e/vehicle-km`, etc., **do not multiply by GWP again.**

---

## 10.5 `BEN-GHG-CO2E-01` — direct CO2e-factor route

When EF already includes GWP:

\( E_{CO2e}=Activity\times EF_{CO2e} \)

Required metadata on the factor:

- factor value;
- unit;
- factor basis;
- mode;
- year;
- geography;
- source;
- exact table/row/location.

---

## 10.6 `BEN-GHG-AVOID-01` — signed avoided GHG

\( \Delta E = E_{baseline}-E_{project} \)

**Do not use `max(delta, 0)` in the scientific core.**

If result < 0, report:

- signed value;
- `benefit_direction = "disbenefit"` or equivalent;
- no hidden truncation.

Required comment:

```python
avoided_co2e = baseline_co2e - project_co2e  # EQ=BEN-GHG-AVOID-01 | REF=REF-EGY-GB-2022;REF-TRD-MODAL-2024 | TITLE=Egypt Sovereign Green Bond Allocation & Impact Report - 2022; Using different transport modes: An opportunity to reduce UK passenger transport emissions? | LOC=Egypt Annex 1 avoided-emission modal-shift method; TRD modal-shift emissions method | DOI=10.1016/j.trd.2023.103989 | URL=https://assets.mof.gov.eg/files/2022-12/d3dec230-8900-11ed-ad5c-d5697d806e26.pdf
```

---

## 10.7 `BEN-TIME-01` — passenger-hours saved

\( H_{saved,y}=Q_y(t_{0,y}-t_{1,y}) \)

Use hours consistently. If input times are minutes, convert explicitly before multiplication.

Source: `REF-WB-ENRRP-ICR`, Annex 4.

Required comment:

```python
passenger_hours_saved = annual_passengers * (baseline_time_h - project_time_h)  # EQ=BEN-TIME-01 | REF=REF-WB-ENRRP-ICR | TITLE=Egypt National Railways Restructuring Project (P101103) - Implementation Completion and Results Report | ISSUER=World Bank | REPORT=ICR00005398 | LOC=Annex 4 Efficiency Analysis, printed pp.71-72 | DOI=n/a | URL=https://documents1.worldbank.org/curated/en/367961628584958285/pdf/Egypt-Railways-Restructuring-Project.pdf
```

Preserve sign. If project time is worse, the result is negative.

---

## 10.8 `BEN-TIME-MONEY-01` — monetary time-saving benefit

\( B_{time,y}=H_{saved,y}\times VOT_y \)

Source: World Bank Egyptian rail appraisal method.

Required comment:

```python
time_benefit = passenger_hours_saved * value_of_time  # EQ=BEN-TIME-MONEY-01 | REF=REF-WB-ENRRP-ICR | TITLE=Egypt National Railways Restructuring Project (P101103) - Implementation Completion and Results Report | ISSUER=World Bank | REPORT=ICR00005398 | LOC=Annex 4 Efficiency Analysis, printed pp.71-72 | DOI=n/a | URL=https://documents1.worldbank.org/curated/en/367961628584958285/pdf/Egypt-Railways-Restructuring-Project.pdf
```

### Mandatory monetary metadata

VOT must carry:

- currency;
- currency basis;
- price base year;
- source geography;
- source exact location;
- escalation/conversion source if converted.

---

## 10.9 `BEN-GEN-TRAFFIC-01` — Rule of Half

For **generated traffic only**:

\( B_{generated,y}=0.5\times Q_{generated,y}\times \Delta t_y\times VOT_y \)

Source: `REF-WB-ENRRP-ICR`, Annex 4.

Required comment:

```python
generated_traffic_benefit = 0.5 * generated_passengers * time_saved_h * value_of_time  # EQ=BEN-GEN-TRAFFIC-01 | REF=REF-WB-ENRRP-ICR | TITLE=Egypt National Railways Restructuring Project (P101103) - Implementation Completion and Results Report | ISSUER=World Bank | REPORT=ICR00005398 | LOC=Annex 4, Rule-of-Half treatment for generated traffic, printed p.72 | DOI=n/a | URL=https://documents1.worldbank.org/curated/en/367961628584958285/pdf/Egypt-Railways-Restructuring-Project.pdf
```

### Hard test

A unit test must prove that existing/base passengers are **not** multiplied by 0.5.

---

## 10.10 `BEN-VOT-01` — VOT from logit model

\( VOT=(\beta_{time}/\beta_{cost})\times60 \)

Use the sign convention and units exactly as defined by the fitted model.

Source: `REF-EGY-VOT-2022`.

Required comment:

```python
vot_per_hour = (beta_time / beta_cost) * 60.0  # EQ=BEN-VOT-01 | REF=REF-EGY-VOT-2022 | TITLE=Estimation of Cross Classified Value of Travel Time Using Binary Logit Model on Egyptian Roads | AUTHORS=Bakry et al. | YEAR=2022 | LOC=Theoretical Framework, reviewed PDF pp.3-4, VOT coefficient-ratio equation | DOI=10.2174/18744478-v16-e2209140 | URL=https://opentransportationjournal.com/VOLUME/16/ELOCATOR/e187444782209140/FULLTEXT/
```

### Do not implement an unsourced 2026 escalation

Do not hard-code:

`18.3 × CPI_2026 / CPI_2022`

until the price-year and official escalation method are documented.

---

## 10.11 `BEN-LU-SHARE-01` — land-use class share

\( p_i=A_i/A_{total} \)

Source: `REF-PLOS-TOD-2023`, Eq. (2).

Required comment:

```python
p_i = class_area / total_area  # EQ=BEN-LU-SHARE-01 | REF=REF-PLOS-TOD-2023 | TITLE=A framework to measure transit-oriented development around transit nodes: Case study of a mass rapid transit system in Dhaka, Bangladesh | AUTHORS=Uddin et al. | LOC=p.9, Land use diversity, Eq.(2) | DOI=10.1371/journal.pone.0280275 | URL=https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0280275
```

Validate:

- areas >= 0;
- total area > 0;
- class definitions stable between baseline and project.

---

## 10.12 `BEN-LUD-01` — normalized Shannon land-use diversity

**Correct equation:**

\( LUD=-\frac{\sum_{i=1}^{n}p_i\ln(p_i)}{\ln(n)} \)

Source: `REF-PLOS-TOD-2023`, p. 9, Eq. (1).

### CRITICAL

The source-rendered equation contains the leading negative sign.

Required comment:

```python
lud = -sum(p * math.log(p) for p in shares if p > 0.0) / math.log(n_classes)  # EQ=BEN-LUD-01 | REF=REF-PLOS-TOD-2023 | TITLE=A framework to measure transit-oriented development around transit nodes: Case study of a mass rapid transit system in Dhaka, Bangladesh | AUTHORS=Uddin et al. | LOC=p.9, Land use diversity, Eq.(1); minus sign visually verified in rendered PDF | DOI=10.1371/journal.pone.0280275 | URL=https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0280275
```

Rules:

- `n_classes >= 2`;
- \(p=0\) contributes zero by the mathematical limit; do not call `log(0)`;
- shares must sum to 1 within tolerance;
- same class schema for baseline/project comparisons.

---

## 10.13 `BEN-LUD-DELTA-01`

\( \Delta LUD=LUD_{project}-LUD_{baseline} \)

This is a **derived comparison** based on the source-backed LUD definition.

Required registry status:

`DERIVED-FROM-METHOD`

Do not imply that this exact delta equation is printed in the PLOS paper.

---

## 10.14 `BEN-BUILTUP-CHANGE-01`

\( \Delta BU\% = 100\times(BU_{current}-BU_{past})/BU_{past} \)

Source: `REF-UNHABITAT-SDG1131-2025`, reviewed p. 9.

Required comment:

```python
built_up_change_pct = 100.0 * (built_up_current - built_up_past) / built_up_past  # EQ=BEN-BUILTUP-CHANGE-01 | REF=REF-UNHABITAT-SDG1131-2025 | TITLE=Metadata for SDG Indicator 11.3.1 - Ratio of land consumption rate to population growth rate | ISSUER=UN-Habitat / UN SDG metadata | VERSION=2025-04-23 | LOC=reviewed p.9, Total change in built-up area | DOI=n/a | URL=https://unstats.un.org/sdgs/metadata/files/Metadata-11-03-01.pdf
```

---

## 10.15 `BEN-LCR-01` — annual land consumption rate

\( LCR=((V_{present}-V_{past})/V_{past})\times(1/t) \)

Source: UN-Habitat metadata, reviewed pp. 7-8.

Required comment:

```python
lcr = ((v_present - v_past) / v_past) * (1.0 / years)  # EQ=BEN-LCR-01 | REF=REF-UNHABITAT-SDG1131-2025 | TITLE=Metadata for SDG Indicator 11.3.1 - Ratio of land consumption rate to population growth rate | ISSUER=UN-Habitat / UN SDG metadata | VERSION=2025-04-23 | LOC=reviewed pp.7-8, Spatial analysis and computation of the land consumption rate | DOI=n/a | URL=https://unstats.un.org/sdgs/metadata/files/Metadata-11-03-01.pdf
```

Do not call a baseline-vs-design scenario difference “SDG LCR” unless actual temporal periods satisfy the method.

---

## 10.16 `BEN-PGR-01`

\( PGR=\ln(Pop_{t+n}/Pop_t)/y \)

Source: same UN-Habitat metadata.

Required comment:

```python
pgr = math.log(pop_final / pop_initial) / years  # EQ=BEN-PGR-01 | REF=REF-UNHABITAT-SDG1131-2025 | TITLE=Metadata for SDG Indicator 11.3.1 - Ratio of land consumption rate to population growth rate | ISSUER=UN-Habitat / UN SDG metadata | VERSION=2025-04-23 | LOC=reviewed p.8, Population Growth Rate formula | DOI=n/a | URL=https://unstats.un.org/sdgs/metadata/files/Metadata-11-03-01.pdf
```

Validate both populations > 0.

---

## 10.17 `BEN-LCRPGR-01`

\( LCRPGR=LCR/PGR \)

Source: UN-Habitat metadata.

If PGR = 0 or numerically near zero:

- result = undefined / `None` / `NaN` with explicit diagnostic;
- never replace with zero;
- never divide using epsilon and pretend it is valid.

---

## 10.18 `BEN-BUILTUP-PC-01`

\( BuiltUpPerCapita=UrBU_t/Pop_t \)

Source: UN-Habitat metadata reviewed p. 9.

Units must be explicit, e.g. m2/person.

---

## 10.19 `BEN-IO-A-01` — technical coefficients

\( a_{ij}=x_{ij}/X_j \)

Source: `REF-EGY-IO-ALAYOUTY-2022`, methodology p. 11.

Required comment:

```python
a_ij = x_ij / output_j  # EQ=BEN-IO-A-01 | REF=REF-EGY-IO-ALAYOUTY-2022 | TITLE=Identifying Activities for Greater Employment Generation in Egypt: An Input-Output Analysis | AUTHOR=Iman Al-Ayouty | SERIES=AERC GSYE-007 | YEAR=2022 | LOC=methodology p.11, technical coefficients | DOI=n/a | URL=https://publication.aercafricalibrary.org/items/035e42e5-5fbb-416e-932a-494a2fd50965
```

---

## 10.20 `BEN-IO-L-01` — Leontief inverse

\( L=(I-A)^{-1} \)

Source: same paper, methodology p. 11.

Required comment:

```python
leontief_inverse = np.linalg.inv(np.eye(n) - A)  # EQ=BEN-IO-L-01 | REF=REF-EGY-IO-ALAYOUTY-2022 | TITLE=Identifying Activities for Greater Employment Generation in Egypt: An Input-Output Analysis | AUTHOR=Iman Al-Ayouty | SERIES=AERC GSYE-007 | YEAR=2022 | LOC=methodology p.11, Leontief inverse / total requirements matrix | DOI=n/a | URL=https://publication.aercafricalibrary.org/items/035e42e5-5fbb-416e-932a-494a2fd50965
```

Before inverse:

- dimensions must be square;
- finite values only;
- test singularity/condition;
- fail with a scientific input error rather than silently use pseudo-inverse unless a method explicitly authorizes it.

---

## 10.21 `BEN-IO-DELTA-01` — output response

\( \Delta x=L\Delta y \)

Treat this as the standard direct application of the source-defined Leontief inverse.

Registry must say `DERIVED/APPLIED-METHOD`, not pretend the exact symbol arrangement was quoted from the Egyptian paper.

---

## 10.22 `BEN-IO-OMULT-01`

\( OMULT_j=\sum_i l_{ij} \)

Source: Egyptian I-O paper, methodology pp. 11-12.

---

## 10.23 `BEN-IO-EMULT-01`

\( EMULT_j=(\sum_i w_i l_{ij})/w_j \)

Source: Egyptian I-O paper, p. 12.

### Hard prohibition

Do not implement:

`jobs = CAPEX * 1.44`

The reported 1.44-type value is an employment multiplier under the paper’s definition, not jobs per EGP or jobs per USD.

---

## 10.24 `BEN-JOBS-PROXY-01`

\( Jobs_{proxy}=Investment_{million,constant2015USD}\times JobContent \)

Source: `REF-MOSZORO-2024`.

Required comment:

```python
jobs_proxy = investment_million_constant_2015_usd * job_content_per_musd  # EQ=BEN-JOBS-PROXY-01 | REF=REF-MOSZORO-2024 | TITLE=The direct employment impact of public investment | AUTHOR=Marian W. Moszoro | JOURNAL=International Journal of Management and Economics 60(1), 59-74 | YEAR=2024 | LOC=results/tables reporting jobs per US$1 million; monetary data standardized to constant 2015 USD | DOI=10.2478/ijme-2023-0020 | URL=https://reference-global.com/article/10.2478/ijme-2023-0020
```

### Result label

Never label this result:

`Cairo jobs created`

Use:

`Model benchmark / proxy jobs supported`

Evidence status:

`REF-PROXY`

---

## 10.25 Official Cairo Monorail jobs — NO EQUATION

The Egypt Sovereign Green Bond report states up to:

- 4,000 construction jobs;
- approximately 450 operation jobs.

Store as separate evidence-backed fields:

- `official_reported_construction_jobs`
- `official_reported_operational_jobs`

with `OFFICIAL-PROJECT-DATA`.

Never compute:

`official_jobs + proxy_jobs`

as a total.

They are two different evidence products.

---

## 10.26 `BEN-NOISE-PHYS-01` — physical noise difference

For the same receptor and the same acoustic metric/time basis:

\( \Delta L_r=L_{baseline,r}-L_{project,r} \)

This is a comparison operator, conditional on a proper acoustic study.

Required comment:

```python
noise_delta_db = baseline_db - project_db  # EQ=BEN-NOISE-PHYS-01 | REF=REF-EU-NOISE-2002;REF-EU-CNOSSOS-2015 | TITLE=Directive 2002/49/EC relating to environmental noise; Commission Directive (EU) 2015/996 establishing common noise assessment methods | LOC=same-indicator baseline/project comparison; use documented Lden/Lnight or explicitly sourced metric | DOI=n/a | URL=https://eur-lex.europa.eu/eli/dir/2002/49/oj/eng
```

### Required input keys

- `receptor_id`
- `metric`
- `assessment_period`
- `baseline_db`
- `project_db`
- baseline source
- project source
- geography

### Prohibited

Do not calculate:

`noise_delta_db / baseline_db`

as a scientific percentage.

Do not average dB values arithmetically across receptors.

---

# 11. FORMALIZATION — BLOCKED

Do not create a scientific `formalization_benefit` equation in this phase.

Current evidence supports qualitative concepts around informal-sector integration, but the reviewed corpus does not provide a defensible quantitative causal formula for this project.

Registry entry:

- KPI: Formalization
- `evidence_status = SOURCE-OPEN`
- `publication_numeric_allowed = False`

If the UI shows it, display:

`SOURCE-OPEN — no quantitative method/source approved`

---

# 12. CARBON MONETIZATION — BLOCKED UNTIL NUMERIC VALUATION SOURCE IS CLOSED

Physical avoided tCO2e can be calculated when activity and factors are sourced.

Monetary carbon benefit needs a separate valuation source:

- social cost / shadow price / appraisal carbon value;
- geography/appraisal jurisdiction;
- year;
- currency;
- price basis;
- escalation convention.

Do not assume a carbon price.

Until closed:

`monetized_ghg_benefit = SOURCE-OPEN`

---

# 13. NOISE MONETIZATION — BLOCKED UNTIL EXPOSURE + VALUE SOURCE IS CLOSED

The EU external-cost handbook can support methodology framing, but it does not automatically produce a Cairo number.

Before monetization require:

- exposed population or receptor weights;
- metric;
- noise bands;
- baseline and project exposure;
- transfer/valuation method;
- currency;
- price year;
- geography rationale.

Until then:

- physical noise difference may be reported;
- monetary noise benefit = `SOURCE-OPEN`.

---

# 14. SCIENTIFIC BENEFITS RESULT MUST HAVE FOUR SEPARATE GROUPS

Do not create one undifferentiated “Total Benefits” number.

Use:

```python
{
    "physical": {...},
    "monetized_cba": {...},
    "economic_impact": {...},
    "employment": {...},
    "audit": {...},
    "publication_gate": {...},
}
```

## 14.1 Physical Benefits

Examples:

- annual passenger-km;
- shifted pkm;
- signed tCO2e avoided;
- passenger-hours saved;
- LUD baseline/project/delta;
- built-up/LCR/PGR indicators;
- physical noise delta.

## 14.2 Monetized CBA Benefits

Currently allowed when evidence is closed:

- time savings value.

Conditionally later:

- GHG monetary benefit;
- noise monetary benefit.

## 14.3 Economic Impact

Separate:

- I-O direct/indirect output response;
- output multipliers;
- other economy-wide impact.

**Economic output is not automatically welfare benefit.**

## 14.4 Employment

Separate:

- official reported project jobs;
- model/proxy job estimate;
- I-O employment measures.

Never sum evidence types merely because they are all “jobs”.

---

# 15. NEW EVIDENCE VALUE SCHEMA

Implement in `benefits_scientific_core.py` or a Benefits-owned schema module:

```python
@dataclass(frozen=True)
class EvidenceValue:
    value: object
    unit: str
    source_ref_id: str
    source_file: str
    source_location: str
    geography: str
    evidence_status: str
    price_base_year: int | None = None
    currency: str | None = None
    factor_basis: str | None = None
    note: str = ""
```

For a numeric Publication input, require:

- value;
- unit;
- reference ID;
- exact file/report;
- exact page/table/section;
- geography;
- allowed evidence status.

For money also require:

- currency;
- price base year.

---

# 16. RECOMMENDED TOP-LEVEL PARAMETER STRATEGY

Do not add 100 new flat scientific Benefits keys to the app’s global parameter dictionary.

Add one nested object:

`benefits_scientific_inputs`

and classify that key as Benefits-only.

In `assessment_orchestrator.py`, add:

```python
BENEFITS_PARAM_KEYS = {
    ...
    "benefits_scientific_inputs",
}
```

Do **not** add it to `MULTI_DOMAIN_PARAM_KEYS`.

Neutral facts that genuinely belong to `SharedActivity` remain neutral and do not need duplication.

---

# 17. RECOMMENDED `benefits_scientific_inputs` STRUCTURE

Example structure:

```python
benefits_scientific_inputs = {
    "transport": {
        "passengers_per_day": evidence_value_or_none,
        "avg_distance_km": evidence_value_or_none,
        "operating_days_per_year": evidence_value_or_none,
        "modal_shift_fraction": evidence_value_or_none,
        "car_share_of_shift": evidence_value_or_none,
        "bus_share_of_shift": evidence_value_or_none,
        "car_emission_factor": evidence_value_or_none,
        "bus_emission_factor": evidence_value_or_none,
        "project_emission_factor": evidence_value_or_none,
        "annual_trips": evidence_value_or_none,
        "baseline_time_min": evidence_value_or_none,
        "project_time_min": evidence_value_or_none,
        "generated_trips": evidence_value_or_none,
        "value_of_time": evidence_value_or_none,
    },
    "land_use": {
        "analysis_area_id": "...",
        "analysis_area_source": "...",
        "influence_radius_m": evidence_value_or_none,
        "class_schema": [...],
        "baseline_area_by_class": {...},
        "project_area_by_class": {...},
        "baseline_label": "...",
        "project_label": "...",
    },
    "urban_growth": {
        "built_up_past": evidence_value_or_none,
        "built_up_present": evidence_value_or_none,
        "population_past": evidence_value_or_none,
        "population_present": evidence_value_or_none,
        "past_year": ...,
        "present_year": ...,
    },
    "employment": {
        "official_construction_jobs": evidence_value_or_none,
        "official_operational_jobs": evidence_value_or_none,
        "jobs_per_musd_proxy": evidence_value_or_none,
        "proxy_investment_constant_2015_usd_m": evidence_value_or_none,
    },
    "input_output": {
        "A_matrix": evidence_value_or_none,
        "final_demand_change": evidence_value_or_none,
        "sector_labels": [...],
    },
    "noise": {
        "rows": [
            {
                "receptor_id": "...",
                "metric": "Lden",
                "assessment_period": "...",
                "baseline_db": evidence_value_or_none,
                "project_db": evidence_value_or_none,
            }
        ]
    },
    "formalization": {
        "evidence_status": "SOURCE-OPEN"
    }
}
```

---

# 18. `benefits_scientific_core.py` — REQUIRED FUNCTION SET

At minimum expose pure functions similar to:

```python
class ScientificBenefitInputError(ValueError):
    pass

def annual_passenger_km(...): ...
def shifted_passenger_km(...): ...
def allocate_shifted_pkm(...): ...
def emissions_from_gas_factor(...): ...
def emissions_from_co2e_factor(...): ...
def avoided_emissions(...): ...
def passenger_hours_saved(...): ...
def monetize_time_saving(...): ...
def generated_traffic_benefit_rule_of_half(...): ...
def vot_from_logit_coefficients(...): ...
def land_use_shares(...): ...
def normalized_land_use_diversity(...): ...
def land_use_diversity_delta(...): ...
def built_up_change_pct(...): ...
def land_consumption_rate(...): ...
def population_growth_rate(...): ...
def lcr_pgr_ratio(...): ...
def built_up_area_per_capita(...): ...
def technical_coefficients(...): ...
def leontief_inverse(...): ...
def io_output_response(...): ...
def output_multiplier(...): ...
def employment_multiplier(...): ...
def jobs_proxy(...): ...
def physical_noise_delta(...): ...
```

Each actual arithmetic line must carry the source comment described above.

---

# 19. CORE VALIDATION RULES

## 19.1 General

Reject:

- `None` where required;
- NaN/Inf;
- wrong dimensions;
- invalid units;
- missing source IDs when called through publication integration.

## 19.2 Fractions

Require 0 <= fraction <= 1 for:

- modal shift;
- car/bus split.

## 19.3 Modal split

Require:

`abs(car_share + bus_share - 1) <= tolerance`

## 19.4 Time

Require explicit units.

Convert minutes → hours in a visibly named line.

## 19.5 VOT

Require:

- nonzero cost coefficient;
- known source unit convention;
- currency/base year for a monetized result.

## 19.6 Land use

Require:

- same class list baseline/project;
- nonnegative areas;
- total > 0;
- shares sum to 1;
- `n >= 2`.

## 19.7 LCR/PGR

Require identical period.

If PGR≈0:

- mark ratio undefined.

## 19.8 Input-output

Require:

- square A matrix;
- matching labels;
- compatible final-demand vector;
- invertible I-A;
- source basis/date.

## 19.9 Noise

Require same:

- receptor;
- metric;
- assessment period;
- method/basis.

---

# 20. `benefits_scientific_integration.py` — RESPONSIBILITY

This file performs evidence-aware orchestration **within the Benefits domain**.

Recommended result object:

```python
@dataclass(frozen=True)
class ScientificBenefitsResult:
    physical: dict
    monetized_cba: dict
    economic_impact: dict
    employment: dict
    audit: dict
    publication_gate: dict
```

Expose:

```python
def run_scientific_benefits_from_params(
    *,
    params: dict,
    shared_activity,
    project_context,
) -> ScientificBenefitsResult:
    ...
```

### Integration must decide whether a KPI is:

- computed;
- not applicable;
- source-open;
- scenario-only;
- proxy;
- official reported;
- blocked.

Do not make a missing value look like zero.

Use explicit states.

---

# 21. PUBLICATION GATE

Create a Benefits gate independent from LCA and LCC.

Suggested fields:

```python
{
    "publication_ready": False,
    "physical_ready": False,
    "monetized_time_ready": False,
    "economic_impact_ready": False,
    "employment_ready": False,
    "noise_physical_ready": False,
    "blocked_items": [...],
    "warnings": [...],
    "source_open_items": [...],
}
```

## 21.1 Publication-ready input status

A project number may pass only if its evidence status is one of:

- `PROJECT-SPECIFIC`
- `OFFICIAL-PROJECT-DATA`

A `METHOD-REFERENCE` supports the formula, not the project number.

A `REF-PROXY` can be displayed only with explicit proxy labeling.

`SOURCE-OPEN` and `SCENARIO-ONLY` do not pass a project-publication headline gate.

---

# 22. EXACT CHANGES IN `assessment_orchestrator.py`

Do not put an equation here.

## 22.1 Add scientific Benefits key classification

Add:

```python
"benefits_scientific_inputs",
```

to `BENEFITS_PARAM_KEYS`.

## 22.2 Preserve existing legacy path

Current:

`run_assessment()` → legacy LCA + legacy LCC + legacy Benefits.

Do not destroy that immediately because parity tests and developer UI depend on it.

## 22.3 Avoid evaluating LCA twice when adding Scientific Benefits

Refactor assembly minimally:

Create:

```python
def assemble_legacy_dashboard_results(result: AssessmentResult) -> dict:
    ...
```

Move the current dictionary-assembly body from `calculate_legacy_dashboard_results()` into it.

Then:

```python
def calculate_legacy_dashboard_results(params: dict) -> dict:
    return assemble_legacy_dashboard_results(run_assessment(params))
```

Then add an orchestration helper that performs only one separated domain run:

```python
def run_assessment_bundle(params: dict):
    result = run_assessment(params)

    from benefits_scientific_integration import run_scientific_benefits_from_params

    scientific_benefits = run_scientific_benefits_from_params(
        params=params,
        shared_activity=result.shared,
        project_context=result.context,
    )

    legacy_dashboard = assemble_legacy_dashboard_results(result)
    return result, legacy_dashboard, scientific_benefits
```

This helper must receive the original `params` exactly once, use the already-created `result.shared`, and must not call the LCA engine a second time.

**Important:** orchestrator calls; core calculates.

No Benefits formula may be written in the orchestrator.

---

# 23. EXACT CHANGES IN `app_final_streamlit_ready.py`

Use literal search anchors instead of relying on line numbers, because line numbers move after every edit.

## 23.1 Imports

Near:

`from benefits_core import calculate_benefit_kpis, calculate_legacy_jobs`

keep the legacy import for Developer compatibility.

Add scientific imports:

```python
from benefits_scientific_integration import run_scientific_benefits_from_params
from benefits_scientific_reporting import (
    scientific_benefits_table,
    scientific_benefits_csv,
    scientific_benefits_excel_bytes,
    scientific_benefits_source_appendix,
)
```

If the implementation uses `run_assessment_bundle`, import that from the orchestrator instead of directly rerunning integration in the app.

## 23.2 Current legacy Benefits input block

Find:

`# ── R15: Benefit (co-benefit) KPIs — reported SEPARATELY, never netted into LCA ──`

The current numeric-only block must become **Developer mode only**.

Wrap legacy inputs with:

```python
if not publication_mode:
    st.markdown("### 🗄️ Legacy Benefit KPI inputs (developer only)")
    ...
else:
    # Keep legacy variables initialized to zero only for backward-compatible plumbing.
    ...
```

Do not describe them in Publication mode as “documented equations” because they do not collect complete evidence.

## 23.3 Add Scientific Benefits provenance UI

After the legacy block and near the current Scientific LCA provenance expander, add:

`🌱 Scientific Benefits provenance (referenced core)`

This should collect structured evidence, not just values.

For every numerical field include at least:

- value;
- unit;
- source title/ref selection;
- source file/report;
- exact page/table/section;
- geography;
- evidence status;
- price base year/currency if monetary.

Prefer reusable helper functions in the app UI layer, not in the scientific core.

## 23.4 `current_params`

Add exactly one new top-level key:

```python
"benefits_scientific_inputs": benefits_scientific_inputs,
```

Do not remove legacy flat `benefit_*` keys yet; they are needed for parity/Developer mode until migration closes.

## 23.5 Add a Scientific Benefits tab

Current `_TAB_LABELS` includes `results`, `sci_lca`, etc.

Add:

```python
"sci_benefits": "🌱 Scientific Benefits (referenced)",
```

Insert into `_SCI_ORDER`, preferably after `sci_lca` and before generic sensitivity/uncertainty tabs, or near the future scientific LCC placement.

Publication should have a clear dedicated audit view.

## 23.6 Fix the current Results Benefits expander

Find:

`with st.expander("🌱 Benefit KPIs (societal co-benefits — separate from LCA carbon)"`

Current behavior displays legacy values.

Replace with logic:

```python
if publication_mode:
    # scientific only
    if scientific_benefits.publication_gate["publication_ready"]:
        render scientific tables
    else:
        show source-open / blocked audit
        DO NOT show legacy benefit_kpis as a fallback
else:
    show legacy benefit_kpis and clearly label "Developer / legacy"
```

This is a mandatory publication-safety fix.

## 23.7 Never show one combined Benefits headline

In Publication mode do not display:

`Total Benefit = ...`

unless a future CBA module is formally defined.

Show separate groups and evidence states.

---

# 24. REPORTING AND EXPORT CONTRACT

`benefits_scientific_reporting.py` must make reviewer traceability easier than the UI.

Every exported result row should include:

- `kpi_id`
- `equation_id`
- `kpi_name`
- `value`
- `unit`
- `result_group`
- `evidence_status`
- `method_ref_ids`
- `numeric_source_ref_ids`
- `source_title`
- `source_file`
- `source_location`
- `doi`
- `official_url`
- `geography`
- `currency`
- `price_base_year`
- `limitations`
- `publication_eligible`

### Excel recommended sheets

1. `Benefits_Summary`
2. `Physical_Benefits`
3. `Monetized_CBA`
4. `Economic_Impact`
5. `Employment`
6. `Equation_Audit`
7. `Reference_Registry`
8. `Source_Open_Items`

No export should contain a scientific number without a resolvable equation and evidence chain.

---

# 25. REVIEWER TRACEABILITY EXAMPLE

Suppose the UI shows:

`Annual passenger-hours saved = 12,345,678 h/year`

The reviewer should be able to:

1. click/view `KPI=BEN-TIME-SAVED`;
2. see `EQ=BEN-TIME-01`;
3. inspect the Python equation line;
4. read the full `#` source comment;
5. open `benefits_reference_registry.py`;
6. find `REF-WB-ENRRP-ICR`;
7. open the official World Bank PDF;
8. jump to Annex 4, pp. 71-72;
9. inspect the numeric evidence records for annual passengers and baseline/project time;
10. see their project source pages;
11. reproduce the calculation.

If any link in that chain is missing, it is not publication-ready.

---

# 26. TESTS — REQUIRED BEFORE PUBLICATION UI CONNECTION

## 26.1 `tests/benefits_scientific_core_test.py`

At minimum test:

- passenger-km units;
- modal-shift bounds;
- car+bus split = 1;
- signed avoided GHG including negative case;
- gas-specific vs already-CO2e factor routes;
- no double GWP;
- passenger-hours;
- VOT coefficient ratio;
- rule of half only for generated traffic;
- LUD uniform distribution = 1;
- LUD single-class dominance approaches 0;
- zero shares do not call log(0);
- LUD uses leading negative sign;
- UN-Habitat LCR known arithmetic;
- PGR known arithmetic;
- LCR/PGR same-period enforcement;
- PGR zero -> undefined;
- Leontief inverse known 2×2 test;
- singular I-A rejection;
- jobs proxy basis check;
- physical noise signed delta;
- no scientific noise ratio.

## 26.2 `tests/benefits_reference_integrity_test.py`

Fail if:

- equation lacks Ref ID;
- Ref ID missing;
- title blank;
- URL/DOI blank without explicit `n/a`;
- exact location blank;
- equation has no unit contract;
- PLOS LUD formula lacks leading `-`;
- source comment marker absent in core for registered equation;
- hard-coded quartile/JCR claim exists.

## 26.3 `tests/benefits_scientific_integration_test.py`

Test:

- missing numeric source => source-open;
- method-only source cannot certify a project number;
- official project data passes appropriate data gate;
- REF-PROXY remains proxy-labelled;
- currency/base year required for monetization;
- scientific engine does not import LCA/LCC;
- same `SharedActivity` can be consumed without importing LCA.

## 26.4 `tests/benefits_publication_gate_test.py`

Test that Publication blocks:

- 30% hard-coded modal shift without evidence;
- car/bus split with no evidence;
- unsourced EF;
- unsourced 2026 VOT;
- historical I-O multiplier presented as current project truth;
- monetary noise with no exposure/valuation evidence;
- formalization number;
- adding official jobs + proxy jobs;
- `economic_output` inserted into welfare benefit total.

## 26.5 Extend `tests/benefits_independence_test.py`

Add scientific module names.

Confirm:

- no LCA engine imported;
- no LCC engine imported;
- no Streamlit imported;
- no `npv_lcc` output;
- no `gross_a1_c4` mutation.

## 26.6 Extend `tests/params_classification_test.py`

Confirm:

`benefits_scientific_inputs`

- reaches Benefits slice;
- does not reach LCA;
- does not reach LCC;
- is not multi-domain.

## 26.7 Extend `tests/app_layer_purity_test.py`

Confirm app does not define the scientific Benefits equations.

The UI may collect data and render results, but science belongs in the scientific core.

---

# 27. CI UPDATE

In `.github/workflows/tests.yml`, add new suites to the main test loop:

```text
tests/benefits_scientific_core_test.py
tests/benefits_reference_integrity_test.py
tests/benefits_scientific_integration_test.py
tests/benefits_publication_gate_test.py
```

Do not remove current 23 suites.

CI acceptance:

- all previous suites pass;
- all new Benefits suites pass;
- real Streamlit smoke passes;
- frozen LCA scientific files remain unchanged unless a separately approved task says otherwise.

---

# 28. MONTE CARLO — DO NOT ADD SCIENTIFIC BENEFITS DISTRIBUTIONS YET

Current `uncertainty_orchestrator.py` correctly contains call sequencing rather than distributions.

Keep it that way.

Scientific Benefits Monte Carlo must be deferred until deterministic evidence is closed.

Do not invent distributions for:

- modal shift;
- VOT;
- emission factors;
- jobs per investment;
- economic multipliers;
- noise;
- land-use change.

When future uncertainty is added, every distribution must have:

- source;
- variable;
- distribution type rationale;
- parameter basis;
- geography;
- year;
- evidence status.

---

# 29. ECONOMIC IMPACT IS NOT THE SAME AS CBA BENEFIT

This distinction must be encoded in result structure and UI.

Do not calculate:

`Total monetized benefit = time benefit + economic output + jobs + ...`

Input-output output response is an **economic activity/impact measure**, not automatically a welfare benefit.

Jobs are employment outcomes, not automatically additional monetary welfare.

LUD is a spatial indicator, not money.

Physical CO2 avoided is tCO2e, not money until a separately sourced carbon valuation is applied.

---

# 30. LCA / LCC / BENEFITS DOUBLE-COUNT RULE

Hard architecture rules:

1. Benefits never reduce `Gross A-C`.
2. Benefits never reduce `LCC_NPV`.
3. `LCC_NPV` remains cost-side.
4. If a future economic CBA is required, create a separately named module, e.g. `cba_scientific_core.py`.
5. That future CBA may consume:
   - scientific LCC results;
   - monetized Benefits results;
   - explicit appraisal rules.
6. It must not rewrite LCA or LCC.

---

# 31. SOURCE-OPEN LEDGER AT THIS STAGE

The scientific UI/report should explicitly show at least these open items when not supplied:

| Item | Current status | What closes it |
|---|---|---|
| Current Cairo modal-shift fraction | SOURCE-OPEN unless official scenario deliberately used | project/transport study exact source |
| Car/bus split of displaced travel | SOURCE-OPEN | project travel survey/model |
| Current mode EFs | SOURCE-OPEN unless factor source supplied | documented factor table/year/basis |
| 2026 VOT escalation | SOURCE-OPEN | price year + official index/deflator method |
| Current Egypt I-O matrix/multiplier | historical proxy only | newer official I-O/SUT/SAM |
| Carbon monetary value | SOURCE-OPEN | official appraisal value, price year |
| Noise monetization | SOURCE-OPEN | exposure + valuation source |
| Formalization | SOURCE-OPEN | validated quantitative methodology |
| Cairo TOD influence radius | project evidence required | planning/GIS/project source |
| Baseline/project land-use maps | SOURCE-OPEN until supplied | GIS source + date + class schema |

---

# 32. COMMIT SEQUENCE — DO NOT MIX EVERYTHING INTO ONE COMMIT

## Commit B0 — Freeze/document

Suggested message:

`docs(benefits): pin Q1 scientific method and source contract`

Actions:

- add this handoff to `docs/`;
- no runtime change.

## Commit B1 — Registry + pure core

Suggested message:

`feat(benefits): add sourced deterministic scientific core`

Actions:

- add `benefits_reference_registry.py`;
- add `benefits_scientific_core.py`;
- add core and reference tests;
- no app connection.

Acceptance:

- direct unit tests pass;
- no LCA/LCC imports.

## Commit B2 — Evidence integration + gate

Suggested message:

`feat(benefits): add evidence-aware integration and publication gate`

Actions:

- add `benefits_scientific_integration.py`;
- nested evidence schema;
- classification update;
- integration/gate tests.

## Commit B3 — Publication UI integration

Suggested message:

`feat(benefits): connect sourced Benefits to Publication UI`

Actions:

- scientific provenance expander;
- scientific Benefits tab;
- Publication Results uses only scientific Benefits;
- current legacy Benefits becomes Developer-only;
- no legacy fallback in Publication.

## Commit B4 — Reporting/export

Suggested message:

`feat(benefits): add traceable scientific Benefits exports`

Actions:

- `benefits_scientific_reporting.py`;
- CSV/Excel/source appendix;
- export parity tests.

## Commit B5 — CI and closure

Suggested message:

`test(benefits): enforce source traceability and domain independence`

Actions:

- CI suite;
- architecture checks;
- source integrity;
- final run.

---

# 33. DEFINITION OF DONE

The Benefits scientific upgrade is **not finished** until all of the following are true:

- [ ] `benefits_reference_registry.py` exists.
- [ ] `benefits_scientific_core.py` exists.
- [ ] `benefits_scientific_integration.py` exists.
- [ ] `benefits_scientific_reporting.py` exists.
- [ ] Every scientific equation has an Equation ID.
- [ ] Every scientific equation line has a source comment after `#`.
- [ ] Every source comment contains a Reference ID.
- [ ] Every Reference ID resolves to full title + issuer/authors + year + exact location + DOI/official URL.
- [ ] Every project numerical value has separate numerical evidence.
- [ ] No equation method source is misused as a numerical data source.
- [ ] PLOS LUD equation contains the leading negative sign.
- [ ] p=0 is handled correctly.
- [ ] avoided emissions remain signed.
- [ ] GWP is not double-counted for already-CO2e factors.
- [ ] generated traffic alone receives Rule of Half.
- [ ] VOT has currency and price-year provenance.
- [ ] current 2016-2017 Egypt I-O multipliers are not labelled 2026 project facts.
- [ ] Moszoro jobs remain REF-PROXY.
- [ ] official monorail jobs remain OFFICIAL-PROJECT-DATA.
- [ ] official jobs and proxy jobs are not added together.
- [ ] scientific noise result has no simple percentage-of-dB reduction.
- [ ] noise monetization is blocked until evidence closes.
- [ ] formalization is blocked.
- [ ] no Benefit reduces LCC NPV.
- [ ] no Benefit reduces LCA Gross A-C.
- [ ] Publication mode never falls back to legacy Benefits values.
- [ ] Developer mode can still reproduce legacy dashboard behavior.
- [ ] all existing tests still pass.
- [ ] all new Benefits tests pass.
- [ ] GitHub Actions success on final SHA.
- [ ] frozen LCA scientific files remain scientifically unchanged.
- [ ] source appendix can take a reviewer from each output to the original document in a few clicks.

---

# 34. FINAL PROGRAMMER CHECKPOINT TO RETURN TO THE REVIEWER

After each Benefits commit, report:

1. Commit SHA.
2. Files created.
3. Files modified.
4. Equations added, by Equation ID.
5. References added, by Ref ID.
6. Which numerical sources remain SOURCE-OPEN.
7. Tests added.
8. Number of passing suites.
9. GitHub Actions run ID and conclusion.
10. Confirmation that:
    - LCA scientific files were not changed scientifically;
    - LCC scientific core was not changed scientifically;
    - Benefits imports neither LCA nor LCC engines;
    - Publication mode cannot expose legacy Benefits as scientific output.

At final closure also provide a table:

| KPI | Equation ID | Method source | Numeric source | Evidence status | Publication eligible |
|---|---|---|---|---|---|

---

# 35. EXAMPLE OF THE REQUIRED REVIEWER-FRIENDLY SOURCE COMMENT STYLE

Bad:

```python
# source: World Bank
time_benefit = q * dt * vot
```

Bad:

```python
# Q1 paper
lud = ...
```

Good:

```python
time_benefit = passenger_hours_saved * value_of_time  # EQ=BEN-TIME-MONEY-01 | REF=REF-WB-ENRRP-ICR | TITLE=Egypt National Railways Restructuring Project (P101103) - Implementation Completion and Results Report | ISSUER=World Bank | REPORT=ICR00005398 | LOC=Annex 4 Efficiency Analysis, printed pp.71-72 | DOI=n/a | URL=https://documents1.worldbank.org/curated/en/367961628584958285/pdf/Egypt-Railways-Restructuring-Project.pdf
```

Good:

```python
lud = -sum(p * math.log(p) for p in shares if p > 0.0) / math.log(n_classes)  # EQ=BEN-LUD-01 | REF=REF-PLOS-TOD-2023 | TITLE=A framework to measure transit-oriented development around transit nodes: Case study of a mass rapid transit system in Dhaka, Bangladesh | AUTHORS=Uddin et al. | LOC=p.9, Eq.(1), leading minus sign visually verified | DOI=10.1371/journal.pone.0280275 | URL=https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0280275
```

This level of traceability is intentionally verbose. It is a scientific audit feature, not code decoration.

---

# 36. IMPORTANT NOTE ABOUT “Q1”

Do not write a source record like:

`quartile = "Q1"`

unless the specific journal/year/quartile has been independently verified from the intended ranking system at manuscript submission time.

The code’s scientific validity should be based on:

- correct method;
- appropriate source authority;
- exact traceability;
- correct geography and data basis;
- transparent limitations;
- reproducibility.

An official World Bank, UN-Habitat, Ministry, or regulatory source can be the correct source even though it is not a journal article.

The manuscript’s “Q1 target” is a publication strategy, not an evidence-status label.

---

# 37. FINAL ARCHITECTURAL STATE EXPECTED

After this handoff is implemented, the repository should conceptually be:

```text
project_context.py              shared_activity.py
       |                               |
       +---------------+---------------+
                       |
       +---------------+---------------+
       |               |               |
Scientific LCA    Scientific LCC   Scientific Benefits
       |               |               |
       |               |        benefits_reference_registry.py
       |               |               |
       +---------------+---------------+
                       |
             assessment_orchestrator.py
                       |
             app_final_streamlit_ready.py
                       |
          publication reports / exports
```

With the strict rule:

**LCA does not call LCC.**  
**LCC does not call LCA.**  
**Benefits calls neither.**  
**The orchestrator contains no scientific equation.**  
**The UI contains no scientific equation.**  
**Every scientific equation is source-traceable.**  
**Every numerical publication value has independent evidence provenance.**

---

# 38. ONE-SENTENCE IMPLEMENTATION PRIORITY

> First build and test a source-locked deterministic `benefits_scientific_core.py` + registry; then connect evidence-aware integration; only after that replace Publication Benefits output, while keeping the current `benefits_core.py` and its legacy dashboard values strictly Developer-only until migration is proven by tests and CI.

---

# 39. PINNED STARTING STATE FOR REGRESSION REVIEW

This handoff was prepared against:

- Repo: `Dr-Yehia/Alaa-system-dynamic-`
- Branch: `claude/lcc-q1-scientific-core`
- SHA: `19005f62b69aff7a649fb2ca8493be2277ada06b`
- Tree: `424091a9bb7c9112b01afcf92ec0e09d6da03f61`
- GitHub Actions run: `31573100778`
- Workflow conclusion: `success`

Before the programmer begins, confirm the branch still points to this SHA. If not, rebase/review this handoff against the newer head before implementing structural changes.

---

## End of handoff

**Document target path in repository:**  
`docs/K_BENEFITS_Q1_SCIENTIFIC_PROGRAMMER_HANDOFF.md`
