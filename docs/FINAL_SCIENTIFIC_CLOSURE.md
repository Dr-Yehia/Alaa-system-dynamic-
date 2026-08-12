# Final Scientific Software Closure

## Purpose

This document freezes the publication architecture after the LCA/LCC/K-Benefits
separation and the final evidence-gate hardening.  It distinguishes two states that
must never be conflated:

1. **Software/code closure** — the scientific calculation, evidence gates, reporting,
   uncertainty plumbing and fail-closed publication UI exist and are tested.
2. **Project-evidence closure** — the Cairo/project numeric inputs required by those
   gates have actually been supplied from auditable sources.

The first can be closed in code.  The second cannot be manufactured by software.
A missing project document remains `SOURCE-OPEN` or `BLOCKED` rather than being replaced
by a literature value or a legacy dashboard default.

## Canonical publication entry point

Run:

```bash
streamlit run app_scientific_publication.py
```

`app_scientific_publication.py` is the **publication-only** UI.  It imports no legacy
engine and exposes no legacy fallback.

`app_final_streamlit_ready.py` remains the broad **Developer / historical dashboard**.
It is retained for regression, scenario exploration and comparison.  Its legacy cards
must not be cited as publication results when a scientific gate is closed.

## Canonical scientific domains

### LCA

- `lca_scientific_core.py`
- `lca_scientific_integration.py`
- `lca_scientific_reporting.py`

The deterministic scientific LCA remains source-gated.  Existing open evidence is
recorded in `docs/LCA_REFERENCE_MAP_AND_OPEN_ITEMS.md`.

### LCC

- `lcc_scientific_core.py`
- `lcc_scientific_integration.py`
- `lcc_scientific_reporting.py`

The core remains the sole owner of present-value, escalation and NPV equations.
Integration adds the missing **phase-completeness gate** without reimplementing those
equations.  Every phase must be either:

- `HAS_ROWS`, or
- `DOCUMENTED_ZERO` with project/official evidence, or
- `NOT_APPLICABLE` with project/official evidence and justification.

An empty phase is never silently interpreted as zero.

### K-Benefits

- `benefits_reference_registry.py`
- `benefits_scientific_core.py`
- `benefits_scientific_integration.py`
- `benefits_scientific_reporting.py`

The Benefits handoff and the later five-item evidence-gate hardening are treated as
closed code.  Remaining project evidence is listed in
`docs/BENEFITS_SOURCE_OPEN_LEDGER.md`.

## Cross-domain publication path

- `scientific_publication_orchestrator.py` — runs scientific domains only and contains
  no scientific equation.
- `scientific_publication_reporting.py` — serializes already-computed scientific
  outputs and fails closed when gates are shut.
- `scientific_uncertainty.py` — sourced Monte Carlo propagation.  It supplies **no
  default distribution, CV, bound or correlation assumption**.  Each uncertainty spec
  must identify the source of its distribution parameters.

The publication orchestrator never imports or substitutes:

- `legacy_lca_engine.py`
- `legacy_lcc_engine.py`
- `benefits_core.py`

## Publication gates

The system distinguishes:

- `deterministic_publication_ready` — LCA, LCC and K-Benefits deterministic scientific
  paths are all ready and their export parity checks pass.
- `uncertainty_ready` — sourced scientific uncertainty propagation is ready.
- `full_q1_ready` — both deterministic and uncertainty gates are ready.

A full-Q1 export is refused until `full_q1_ready=True`.

## Uncertainty evidence rule

`scientific_uncertainty.py` intentionally has no universal sample count or default
coefficient of variation.  The study supplies:

- uncertain parameter path;
- distribution family;
- distribution parameters;
- unit;
- source file;
- exact source location;
- geography;
- evidence status;
- uncertainty protocol/sample-size source.

Weak or missing evidence may still be used for exploratory propagation, but the result
cannot carry a publication-ready uncertainty claim.

## Reproducibility

`requirements-publication.txt` pins the direct publication-path runtime dependencies.
The final tagged release should additionally archive the complete `pip freeze` output
from the successful CI environment so transitive dependency versions are auditable.

CI is split deliberately:

- `.github/workflows/tests.yml` protects the historical 27-suite regression baseline
  and the original Streamlit dashboard.
- `.github/workflows/final-scientific-closure.yml` protects the new scientific LCC,
  publication orchestrator/reporting, uncertainty engine and publication-only
  Streamlit app.

## Evidence that software cannot invent

The following examples remain evidence tasks when not supplied by project/official
sources:

### LCA

- official/project annual Egypt electricity factors;
- FRP product-specific EPD when FRP mass is non-zero;
- primary ICE row recheck or replacement by product EPDs;
- material transport routes, distances, payload and return/empty-running closure;
- site fuel/electricity/waste activity;
- maintenance/replacement/refurbishment events;
- end-of-life treatment routes/shares/factors;
- annual passenger-service table;
- project RSP/design-life evidence;
- unsourced geometry/density conversions.

### LCC

- project BOQ/contract/tender/O&M cost rows;
- unit costs and quantities;
- discount rate and its official/project basis;
- price-base-year/index/escalation evidence;
- residual/recovery values;
- documented zero/not-applicable phase declarations.

### K-Benefits

- Cairo modal-shift fraction;
- car/bus split of displaced travel;
- project/geography-appropriate displaced-mode emission factors;
- value of travel time at the appraisal price year plus official escalation/index;
- Cairo TOD influence radius;
- dated baseline/project GIS land-use maps;
- current Egyptian I-O/SUT/SAM if economic impact is to be a main-case result.

Formalization, carbon monetisation and noise monetisation remain blocked until the
closing evidence/method conditions in the Benefits ledger are satisfied.

## Phase 5 / composite sustainability index

The historical Phase-5 SI remains a **Developer / exploratory decision-support**
feature.  It is not part of the canonical publication gate because its current scenario
matrix is built from historical dashboard paths.  This closure deliberately does not
create a new SI scientific engine merely to expand scope.  A future SI publication
would require its own referenced core/integration/reporting contract.

## Closure definition

The software project is considered **code-closed** when:

1. the historical regression workflow remains green;
2. the final-scientific-closure workflow is green;
3. the publication-only Streamlit health check passes;
4. no publication module imports a legacy engine;
5. LCC phase completeness, source completeness and export parity are tested;
6. scientific uncertainty has no unsourced default distributions;
7. publication exports fail closed;
8. all remaining missing project numbers are reported as evidence gaps, not replaced.

At that point further work is **evidence population / research data collection**, not
software completion.
