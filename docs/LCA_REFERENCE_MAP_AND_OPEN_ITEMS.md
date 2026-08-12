# Monorail LCA - Inline Reference Map and Future-Update Register

This file accompanies the canonical scientific engine `lca_scientific_core.py`.
Reference baseline for this freeze: commit 5ff6d956c8075cb027813173140d728ed7569b6f.

The tables below are generated from, and must stay identical to, `REFERENCE_CATALOG`
and `EQUATIONS` in `lca_scientific_core.py`. `tests/lca_reference_integrity_test.py`
fails the build if a source or equation loses its provenance.

## Comment labels used in the code

- `# REF-VERIFIED`: number copied from an uploaded primary source with file and row/page.
- `# REF-PROXY`: source is documented, but geography/technology is not project-specific.
- `# REF-DERIVED`: arithmetic combination derived from verified source values.
- `# METHOD-REFERENCE`: source of the equation/method; it is not a universal numeric value.
- `# ACCOUNTING-IDENTITY`: bookkeeping identity (sum, mass balance); needs no empirical source.
- `# PROJECT-SOURCE-REQUIRED`: project quantity must carry its BOQ/design/O&M source.
- `# SOURCE-OPEN`: no acceptable numeric source is currently available; publication mode must block it.
- `# SCENARIO-ONLY`: permitted only as a disclosed scenario or sensitivity value.
- `# SOFTWARE-TOLERANCE`: numerical comparison tolerance only; not a scientific input.
- `# FUTURE-REPLACEMENT`: exact evidence that must replace a proxy/open value later.
- `# UNIT-DEFINITION`: exact unit conversion or dimensional identity; no empirical reference is needed.

## Bibliography (from `REFERENCE_CATALOG`)

| Source ID | Organization | Exact title | Identifier | Edition/version | Date | Local file | Role | Status |
|---|---|---|---|---|---|---|---|---|
| `RICS_WLCA_2024` | Royal Institution of Chartered Surveyors (RICS) | Whole life carbon assessment for the built environment | RICS Professional Standard, Global | 2nd edition, September 2023 / Version 3, August 2024 | 2024-08 (effective 2024-07-01) | `Whole_life_carbon_assessment_PS_Sept23.pdf` | Primary method source for A1-C4 modular reporting, A4/A5/C2 and Module D guidance | REF-VERIFIED-METHOD |
| `ISO_14040_2006` | International Organization for Standardization (ISO) | Environmental management — Life cycle assessment — Principles and framework | ISO 14040:2006 | Edition 2 / 2006 | 2006-07 | official ISO standard / licensed copy if available | Goal/scope, functional unit and LCA framework | METHOD-REFERENCE |
| `ISO_14044_2006` | International Organization for Standardization (ISO) | Environmental management — Life cycle assessment — Requirements and guidelines | ISO 14044:2006 | Edition 1 / 2006 | 2006-07 | official ISO standard / licensed copy if available | LCA requirements and reporting framework | METHOD-REFERENCE |
| `BS_EN_15804_A2` | British Standards Institution (BSI) / CEN | Sustainability of construction works. Environmental product declarations. Core rules for the product category of construction products | BS EN 15804:2012+A2:2019 | A2:2019 / EN 15804:2012+A2:2019/AC:2021 aligned | 2019 | licensed standard if available; equation reproduced through RICS Appendix K | EPD/PCR framework and Module D net-flow principle | METHOD-REFERENCE |
| `BS_EN_17472_2022` | British Standards Institution (BSI) / CEN | Sustainability of construction works. Sustainability assessment of civil engineering works. Calculation methods | BS EN 17472:2022 | 2022 | 2022-03-31 | licensed standard if available | Infrastructure/civil-engineering assessment context for the monorail project | METHOD-REFERENCE |
| `UK_GHG_2025_METHOD` | UK Department for Energy Security and Net Zero (DESNZ) | 2025 Government greenhouse gas conversion factors for company reporting: Methodology paper | Greenhouse gas reporting: conversion factors 2025 | 2025 / 2025 final methodology | 2025-06-10 | `2025-GHG-CF-methodology-paper.pdf` | Fuel, freight, electricity, passenger rail and waste factor methodology | REF-VERIFIED-METHOD |
| `UK_GHG_2025_DATA` | UK Department for Energy Security and Net Zero (DESNZ) | Conversion factors 2025: full set (for advanced users) | Greenhouse gas reporting: conversion factors 2025 | 2025 / Full set | 2025-06-10 | `ghg-conversion-factors-2025-full-set.xlsx` | Numeric freight, fuel and waste factors; factor year intentionally pinned to 2025 | REF-PROXY-UK |
| `ICE_V4_1_2025` | Circular Ecology | Inventory of Carbon & Energy (ICE) Database v4.1 | ICE Database v4.1 | Educational V4.1 / October 2025 | 2025-10 | `ICE DB Educational V4.1 - Oct 2025.xlsx` | Generic A1-A3 embodied-carbon factors | REF-PROXY-PRIMARY-RECHECK-REQUIRED |
| `NTD_2024_ENERGY` | U.S. Department of Transportation, Federal Transit Administration | 2024 Annual Database Energy Consumption | National Transit Database (NTD) | 2024 / 2024 Annual Database | 2025 | `2024 Energy Consumption_250812.xlsx` | Used with NTD service/PMT data to derive kWh/passenger-km proxies | REF-DERIVED-PROXY-US |
| `NTD_2024_SERVICE` | U.S. Department of Transportation, Federal Transit Administration | TS2.1 - Service Data and Operating Expenses Time Series by Mode | National Transit Database (NTD) | 2024 / 2024 update | 2025 | `2024 TS2.1 Service Data and Operating Expenses Time Series by Mode.xlsx` | Passenger-mile/service denominator for derived NTD energy-intensity proxies | REF-DERIVED-PROXY-US |
| `IEA_EF_2025` | International Energy Agency (IEA) | Emissions Factors 2025 | IEA data product | 2025 | 2025-09 | IEA Emissions Factors 2025 database/table — numeric Egypt series not yet supplied | Country annual electricity/heat direct emission factors | SOURCE-OPEN-NUMERIC-EGYPT |
| `IEA_LC_UPSTREAM_2025` | International Energy Agency (IEA) | Life Cycle Upstream Emissions Factors 2025 | IEA data product | 2025 | 2025-10 | IEA Life Cycle Upstream Emissions Factors 2025 database/table | Upstream/life-cycle electricity supply factors when used | SOURCE-OPEN-NUMERIC-EGYPT |
| `CLOSED_FACTOR_AUDIT` | Project internal audit | `lca_q1_closed_numbers_from_uploaded_files.xlsx` | Internal traceability index | Project audit workbook / current uploaded audit | not applicable | `lca_q1_closed_numbers_from_uploaded_files.xlsx` | Maps factors to claimed primary rows | INTERNAL-AUDIT-NOT-PRIMARY-SOURCE |

**`CLOSED_FACTOR_AUDIT` is never a primary scientific source.** It is a traceability
index. A number is not "verified" because the audit workbook lists it.

### Factor-year pin

`ASSESSMENT_FACTOR_YEAR = 2025`. DESNZ 2026 conversion factors exist, and 2025 is
**intentionally frozen** for this study so results stay reproducible. Migrating to 2026
is a separate, controlled change with its own regression review — not a silent update.

## Equations and source locations

| ID | Equation | Classification | Code function | Sources |
|---|---|---|---|---|
| `E1_A1_A3` | `I_A1-A3,j = M_j * EF_j / 1000` | METHOD-REFERENCE | `calculate_a1_a3` | `RICS_WLCA_2024` s.5.1.2; `ISO_14040_2006`; `ISO_14044_2006` |
| `E2_EFFECTIVE_EF` | `EF_eff = (1-RC)*EF_virgin + RC*EF_secondary` | REF-DERIVED-INPUT-CONDITIONAL | `calculate_effective_ef` | `BS_EN_15804_A2`; `RICS_WLCA_2024`. **Not** a universal credit equation; never apply to a market-average EF |
| `E3_TRANSPORT_LEG` | `I_leg = (M_kg/1000)*D_km*EF_tkm/1000` | ACCOUNTING-IDENTITY-METHOD-IMPLEMENTATION | `calculate_transport_legs` | `RICS_WLCA_2024` s.5.1.3 / s.5.6.3; `UK_GHG_2025_DATA`. **One leg only** — it is not the whole RICS A4/C2 |
| `E3A_RICS_A4` | `A4 = M*D*[EF_outward + empty_running_factor*EF_return]` | METHOD-REFERENCE | A4 route closure in `build_a4_scientific_legs` | `RICS_WLCA_2024` s.5.1.3 Transport impacts (A4) |
| `E3C_RICS_C2` | `C2 = M*D*[EF_outward + empty_running_factor*EF_return]` | METHOD-REFERENCE | C2 route closure in `_c2_return_closure` / `calculate_c1_c4` | `RICS_WLCA_2024` s.5.6.3 Transport impacts (C2) |
| `E4_FUEL` | `I_fuel = Litres * EF_per_L / 1000` | METHOD-REFERENCE | `calculate_fuel` | `UK_GHG_2025_METHOD`; `UK_GHG_2025_DATA` (Fuels, WTT-fuels) |
| `E5_ELECTRICITY` | `I_electricity,t = E_t * CI_t / 1000` | METHOD-REFERENCE-NUMERIC-SOURCE-CONDITIONAL | `calculate_electricity`, `calculate_b6` | `RICS_WLCA_2024`; `IEA_EF_2025`; `IEA_LC_UPSTREAM_2025`. Egypt numeric CI remains SOURCE-OPEN |
| `E6_B6_ENERGY` | `E_t = PKM_t * EI_t` | METHOD-REFERENCE | `calculate_b6` | `UK_GHG_2025_METHOD`, Table 27 p.79 |
| `E6A_ANNUAL_SERVICE` | `Served_day = min(Demand_day, Capacity_day); PKM_t = Served_day * TripLength * Availability * OperatingDays` | REF-DERIVED-PROJECT-SERVICE-MODEL | `build_annual_pkm_by_year` | `ISO_14040_2006`; `ISO_14044_2006`. Declared project service model, **not** a universal standard equation. No hard-coded 365 |
| `E7_WASTE` | `I_waste = (W_kg/1000)*EF_per_tonne/1000` | METHOD-IMPLEMENTATION | `calculate_waste_treatment`, C3/C4 | `UK_GHG_2025_METHOD`; `UK_GHG_2025_DATA`; `RICS_WLCA_2024`. Unit is per tonne, never per kg |
| `E8_WASTE_FROM_INSTALLED` | `W_extra = M_installed*WR/(1-WR)` | REF-DERIVED-ALGEBRAIC | `derive_waste_mass_from_installed` | `RICS_WLCA_2024` defines WR; the algebraic form for an installed-mass BOQ is derived, not quoted verbatim |
| `E9_B2_B5` | `I_event = materials + fuel + electricity + transport + waste; I_B2-B5 = Σ events` | REF-DERIVED-ACTIVITY-INVENTORY | `calculate_b2_b5` | `RICS_WLCA_2024`; `BS_EN_17472_2022`. Not cost-to-carbon, not %-of-A1-A3; carbon is never discounted |
| `E10_C1_C4` | `I_C1-C4 = C1 + C2 + C3 + C4` | METHOD-REFERENCE | `calculate_c1_c4` | `RICS_WLCA_2024` s.5.6; `BS_EN_17472_2022`. Mass comes from the post-B2-B5 balance |
| `E11_MODULE_D` | `D1_standard_signed = Q_net * (EF_recovery_after_EoW - q_quality * EF_primary_substituted) / 1000`, `Q_net = Q_recovered_out - Q_secondary_in` | METHOD-REFERENCE | `calculate_module_d1` | `RICS_WLCA_2024` Appendix K; `BS_EN_15804_A2` |
| `E12_GROSS` | `Gross A-C = A1-A3 + A4 + A5 + B2-B5 + B6 + C1-C4` | METHOD-REFERENCE-MODULAR-SUM | `combine_lca_modules` | `RICS_WLCA_2024`; `BS_EN_17472_2022`. Module D excluded |
| `E13_FUNCTIONAL_UNIT` | `GWP = Gross_A-C * 1000 / Lifetime_PKM` | REF-DERIVED-FUNCTIONAL-UNIT-REPORTING | `combine_lca_modules` | `ISO_14040_2006`; `ISO_14044_2006`; `BS_EN_17472_2022` |

### Module D sign convention (E11)

RICS Appendix K reproduces the EN 15804 net-flow structure:

```
D1 = (MMR_out - MMR_in) * [EMR_after_EoW_out - EVMSub_out * (QR_out / QSub)]
```

which in the code's variable names is:

```
D1_standard_signed = Q_net * (EF_recovery_after_EoW - q_quality * EF_primary_substituted) / 1000
```

- **negative = potential benefit**
- **positive = potential load**

The quality ratio multiplies the **substituted primary-material term only**; it must not
also scale the recovery burden. The superseded implementation used
`Q_net * q * (EF_primary - EF_recovery)`, which is not algebraically equivalent whenever
`q != 1` and also used the opposite display convention.
`tests/lca_scientific_core_test.py` pins the exact regression: for `Q_net = 1000 kg`,
`q = 0.8`, `EF_primary = 2.0`, `EF_recovery = 0.5`, `D1 = -1.1 tCO2e`.

No minus sign is ever added by hand in the UI, and Module D is never folded into
Gross A-C. There is no canonical field named "net".

### A4 / C2 route closure

`E3_TRANSPORT_LEG` is one computational leg. RICS A4 (s.5.1.3) and C2 (s.5.6.3)
additionally require the return / empty-running journey to be addressed. In Publication
mode a road route is **not** reported as connected until it is closed by one of:

1. a tonne-km return (return fraction + its own empty-running EF + source);
2. a vehicle-km return (measured trips, or trips derived from vehicle capacity x load
   factor, + its own EF + source);
3. a documented zero / not-applicable declaration carrying source file, exact location
   and justification.

The RICS UK default of **43% empty running is a UK figure and is never auto-filled** for
this Egypt project. It may be quoted in a methodology note only.

## Fixed numbers with source records

| Parameter | Value | Source |
|---|---:|---|
| Concrete UK average proxy | 0.10336134453781512 kgCO2e/kg | `ICE_V4_1_2025`, ICE Summary row 277 (via internal audit index; primary workbook recheck required) |
| Steel section | 1.61 kgCO2e/kg | `ICE_V4_1_2025`, ICE Summary row 893 (same caveat) |
| Aluminium worldwide market average | 13.055539991305551 kgCO2e/kg | `ICE_V4_1_2025`, rows 47/58 (same caveat); do not apply extra recycled-content mixing |
| Timber no-carbon-storage proxy | 0.49282614286872206 kgCO2e/kg | `ICE_V4_1_2025`, row 926 (same caveat) |
| Glass general | 1.4369670638496768 kgCO2e/kg | `ICE_V4_1_2025`, row 618 (same caveat) |
| FRP | OPEN | Product-specific EPD required or mass = 0 |
| Truck direct / WTT / WTW | 0.10163 / 0.02359 / 0.12522 kgCO2e/tkm | `UK_GHG_2025_DATA`, Freighting goods row 63; WTT - delivery vehicles & freight row 57; WTW derived = direct + WTT |
| Rail direct / WTT / WTW | 0.02779 / 0.00691 / 0.03470 kgCO2e/tkm | `UK_GHG_2025_DATA`, Freighting goods row 106; WTT row 100; WTW derived |
| Ship direct / WTT / WTW | 0.01321 / 0.00300 / 0.01621 kgCO2e/tkm | `UK_GHG_2025_DATA`, Freighting goods row 152; WTT row 146; WTW derived |
| Diesel direct / WTT / WTW | 2.57082 / 0.61101 / 3.18183 kgCO2e/L | `UK_GHG_2025_DATA`, Fuels row 72; WTT - fuels row 71; WTW derived |
| Diesel biogenic, outside scopes | 0.14 kgCO2e/L | `UK_GHG_2025_DATA`, Outside of scopes row 22; disclosed separately, never in gross A-C |
| Mineral recycling / landfill | 1.00835 / 1.26338 kgCO2e/tonne waste | `UK_GHG_2025_DATA`, Waste disposal rows 24/27/29 |
| Metals landfill | 1.26435 kgCO2e/tonne waste | `UK_GHG_2025_DATA`, Waste disposal row 31 |
| Polymer landfill proxy | 8.98311 kgCO2e/tonne waste | `UK_GHG_2025_DATA`, Waste disposal rows 74-82; SCENARIO/PROXY substitute for FRP/polymer only |
| UK light-rail EI proxy | 0.124 kWh/pkm | `UK_GHG_2025_METHOD`, Table 27 p.79 |
| NTD light-rail proxy | 0.3031307255338944 kWh/pkm | Derived from `NTD_2024_ENERGY` / `NTD_2024_SERVICE` (2024 PMT denominator) |
| NTD automated-guideway proxy | 0.7844814382730434 kWh/pkm | Derived from `NTD_2024_ENERGY` / `NTD_2024_SERVICE`; only if the MG mode mapping is accepted and disclosed |
| RICS A5.3 waste rates | 1%–10% by material | `RICS_WLCA_2024`, Table 18, page 83. UK **defaults**, never project-specific facts |

### ICE verification limit

ICE numeric rows in this freeze are traceable through the internal audit workbook, but
the primary ICE V4.1 workbook must be reopened and row-checked before changing status to
direct-primary verified. Until then every ICE record carries
`status="verified_via_internal_audit_proxy_primary_recheck_required"` and the catalog
entry is flagged `REF-PROXY-PRIMARY-RECHECK-REQUIRED`.

### Non-scientific numbers

- `1000` (kg↔tonne, kgCO2e↔tCO2e): `UNIT-DEFINITION`, exact metric conversion.
- `1e-9`, `1e-6`, `1e-12`: `SOFTWARE-TOLERANCE`, numerical comparison only.
- UI defaults such as a 50-year RSP: `SCENARIO-ONLY UI DEFAULT` — they never become a
  project fact without a source.
- `365` is **not** used as an operational fact anywhere in the scientific path. Operating
  days are an explicit sourced input in both B6 service bases.

## Still open - future modifications

1. `EGYPT_GRID_CI_T`: attach official annual Egypt/project electricity factors. Only the IEA methodology reference is known; the numeric Egypt series is still SOURCE-OPEN.
2. `FRP_A1_A3_EF`: attach product-specific EPD or set FRP mass to zero.
3. `ICE_PRIMARY`: reopen the original ICE V4.1 workbook and row-check it, or replace generic factors with product EPDs.
4. `A4_ROUTES`: enter source for every material route, distance, mode, payload assumption **and the return/empty-running closure**.
5. `A5_ACTIVITY`: enter contractor/site diesel, electricity, waste generation and routes.
6. `B2_B5_EVENTS`: enter each maintenance, repair, replacement and refurbishment event with its O&M source, **and reconcile every removed flow** to reuse/recycle/disposal/other.
7. `C1_C4_PLAN`: enter material-specific EOL shares, routes, **C2 return closure** and processing/disposal factors.
8. `PASSENGER_KM`: enter the sourced annual service table (direct annual PKM, or demand/capacity/trip length/availability/operating days per year).
9. `RSP`: enter project design-life/reference study period source.
10. Densities and geometry: use direct project mass where possible; otherwise source each density, thickness and material specification.

## Publication rule

The program may calculate a documented scenario before all open items are closed, but it
must not label the result `publication_grade` while any required source is open, any FRP
mass has no EPD, annual grid records are missing, project activity quantities are
unsourced, a road A4/C2 route has an unresolved return journey, a B2-B5 removed flow is
unreconciled, or any equation/factor fails
`scientific_reference_integrity_check()`.
