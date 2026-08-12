# Monorail Life-Cycle Scientific Assessment

A source-gated research software system for monorail infrastructure assessment across three independent scientific domains:

- **LCA** — whole-life carbon assessment
- **LCC** — life-cycle cost assessment
- **K-Benefits** — transport, environmental and economic co-benefits

The publication path is deliberately fail-closed: missing project evidence remains `SOURCE-OPEN` or `BLOCKED`; it is never replaced by a legacy default or an unsourced literature value.

## Canonical repository structure

```text
apps/
  publication.py          # Canonical publication-only Streamlit entry point
  _publication_impl.py    # Publication UI implementation
  developer.py            # Historical/developer entry point
  _developer_impl.py      # Frozen historical dashboard implementation

monorail_assessment/
  lca/
    core.py               # Scientific LCA equations and references
    integration.py        # Project evidence + publication gating
    reporting.py          # LCA reports and exports
  lcc/
    core.py               # Scientific LCC equations and references
    integration.py        # Cost ledger + phase/evidence gating
    reporting.py          # LCC reports and exports
  benefits/
    references.py         # K-Benefits source/equation registry
    core.py               # Deterministic scientific equations
    integration.py        # Numeric evidence and publication gate
    reporting.py          # Benefits reports and exports
  publication/
    orchestrator.py       # Cross-domain scientific assembly only
    reporting.py          # Cross-domain publication exports
    uncertainty.py        # Source-gated uncertainty propagation
  common/
    project_context.py
    shared_activity.py
    system_dynamics.py
  legacy/
    ...                   # Historical engines retained for regression only

compat/                   # Historical import aliases only; never canonical science
tests/                    # Scientific, architecture and regression suites
docs/                     # Active scientific evidence and closure documentation
docs/archive/             # Historical implementation handoffs / explanatory files
```

The repository root intentionally contains no duplicate-looking LCA/LCC/Benefits Python modules. Historical aliases are isolated under `compat/`.

## Run the scientific publication application

```bash
python -m pip install -r requirements-publication.txt
streamlit run apps/publication.py
```

The publication application imports no legacy LCA, LCC or Benefits engine as a publication fallback.

## Developer / historical dashboard

```bash
python -m pip install -r requirements.txt
streamlit run apps/developer.py
```

This application is retained for regression comparison, historical scenarios and development. Its legacy values are not publication results when a scientific evidence gate is closed.

## Scientific ownership

Each domain follows the same separation:

```text
core -> integration/evidence gate -> reporting
```

Scientific arithmetic belongs in `core.py`. Integration modules validate project inputs and evidence authority. Reporting modules serialize already-computed results and must not recompute scientific equations.

The publication orchestrator contains no scientific equation and never substitutes a legacy result.

## Evidence governance

A method source is not a numeric project source. Project claims require explicit evidence for the actual project value, including source identity, exact location, geography, units and relevant date/price basis.

Important active evidence ledgers:

- `docs/LCA_REFERENCE_MAP_AND_OPEN_ITEMS.md`
- `docs/BENEFITS_SOURCE_OPEN_LEDGER.md`
- `docs/FINAL_SCIENTIFIC_CLOSURE.md`

Historical implementation instructions are stored under `docs/archive/` and are not part of the active publication contract.

## Compatibility policy

The frozen historical tests and developer dashboard still use some old module names internally. Those aliases now live only under `compat/`, not in the repository root. CI adds `compat/` to the import path for historical regression. Importing the canonical `monorail_assessment` package also exposes the isolated compatibility directory internally so package modules remain operational during this frozen transition.

New scientific code must use the canonical package layout and must never be added to `compat/`.

## Quality assurance

GitHub Actions protects both:

1. the historical regression baseline; and
2. the scientific publication path, including LCC integration/reporting, source-gated uncertainty, export parity and a real Streamlit health probe.

No scientific equation or numeric evidence is changed by repository-structure cleanup.
