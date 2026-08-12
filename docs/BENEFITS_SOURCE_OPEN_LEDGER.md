# Scientific Benefits — SOURCE-OPEN ledger

What the referenced Benefits engine cannot yet certify, and what would close each
item. Everything listed here is reported by the application as an explicit
`SOURCE-OPEN` or `BLOCKED` state — never as a zero, and never filled in from a
method reference.

The rule behind the whole table:

> **The source of an equation is not the source of a numerical value.**
> A standard, a metadata sheet or a foreign journal article can establish that a
> formula is correct. None of them can establish what Cairo's number is.

## Open numerical evidence

| Item | Current status | What closes it |
|---|---|---|
| Cairo modal-shift fraction | `SOURCE-OPEN` unless the official scenario is deliberately adopted and labelled `SCENARIO-ONLY` | A project or transport study stating the fraction, with its exact source location |
| Car/bus split of displaced travel | `SOURCE-OPEN` | A project travel survey or demand model |
| Displaced-mode emission factors | `SOURCE-OPEN` unless a factor source is supplied | A documented factor table with year, basis, mode and geography |
| Value of travel time at the appraisal price year | `SOURCE-OPEN` | The source price year plus the official index or deflator method used to escalate |
| Egyptian input-output multipliers | `HISTORICAL` (2016-2017 table) — never a current project fact | A newer official I-O / SUT / SAM release |
| Monetary value of carbon | `BLOCKED` | An official appraisal carbon value with declared currency and price base year |
| Noise monetisation | `BLOCKED` | Exposed population, exposure levels, and an explicit value-transfer basis for Cairo |
| Informal-sector formalization | `BLOCKED` | A validated quantitative causal methodology; the reviewed corpus supports only the qualitative concept |
| Cairo TOD influence radius | `SOURCE-OPEN` | Project planning or GIS evidence — the Indian policy's 500-800 m band is a benchmark, not this project's radius |
| Baseline / project land-use maps | `SOURCE-OPEN` until supplied | A GIS source with its date and its class schema |

## Reported physical quantities that are not money

These are computed when evidence allows, and they stay in their own units:

- avoided greenhouse gases are signed **tCO₂e**, not currency;
- receptor noise differences are signed **dB** at one receptor, with no
  percentage and no cross-receptor average;
- land-use diversity is a **dimensionless index**;
- Leontief output response is **economic activity**, not a welfare benefit.

## Employment evidence is not one quantity

Officially reported project jobs (`OFFICIAL-PROJECT-DATA`) and the cross-country
benchmark proxy (`REF-PROXY`) are reported side by side and are never summed.
They answer different questions from different evidence.

## Where this is enforced

- `benefits_reference_registry.py` — every source states what it cannot certify.
- `benefits_scientific_integration.py` — every KPI carries an explicit state.
- `tests/benefits_publication_gate_test.py` — the nine cases Publication refuses.
- The application's Scientific Benefits tab and the `Source_Open_Items` export
  sheet render this ledger from the live result.
