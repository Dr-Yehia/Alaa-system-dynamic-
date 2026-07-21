# Monorail LCA - Inline Reference Map and Future-Update Register

This file accompanies `lca_scientific_core_v5_referenced_clean.py`.

## Comment labels used in the code

- `# REF-VERIFIED`: number copied from an uploaded primary source with file and row/page.
- `# REF-PROXY`: source is documented, but geography/technology is not project-specific.
- `# REF-DERIVED`: arithmetic combination derived from verified source values.
- `# METHOD-REFERENCE`: source of the equation/method; it is not a universal numeric value.
- `# PROJECT-SOURCE-REQUIRED`: project quantity must carry its BOQ/design/O&M source.
- `# SOURCE-OPEN`: no acceptable numeric source is currently available; publication mode must block it.
- `# SCENARIO-ONLY`: permitted only as a disclosed scenario or sensitivity value.
- `# FUTURE-REPLACEMENT`: exact evidence that must replace a proxy/open value later.
- `# UNIT-DEFINITION`: exact unit conversion or accounting identity; no empirical reference is needed.

## Equations and source locations

| ID | Equation | Code function | Uploaded source / status |
|---|---|---|---|
| E1 | `I_A1-A3,j = M_j * EF_j / 1000` | `calculate_a1_a3` | `Whole_life_carbon_assessment_PS_Sept23.pdf`; `lca_q1_closed_numbers_from_uploaded_files.xlsx`, Equations E1; numeric EFs conditional on ICE/EPD |
| E2 | `EF_eff=(1-RC)EF_virgin+RC EF_secondary` | `calculate_effective_ef` | Audit workbook, Equations E2 / Closed_Factors; only with matched virgin and secondary A1-A3 factors |
| E3 | `I=(M_kg/1000)*D*EF_tkm/1000` | `calculate_transport_legs` | RICS A4/C2; `ghg-conversion-factors-2025-full-set.xlsx`, Freighting goods and WTT freight sheets |
| E4 | `I_fuel=Litres*EF/1000` | `calculate_fuel` | `2025-GHG-CF-methodology-paper.pdf`; GHG workbook Fuels and WTT-fuels |
| E5 | `I_electricity,t=E_t*CI_t/1000` | `calculate_electricity`, `calculate_b6` | RICS/IEA methodology; Egypt numeric CI remains open |
| E6 | `E_t=PKM_t*EI_t` | `calculate_b6` | `2025-GHG-CF-methodology-paper.pdf`, Table 27 p.79; NTD proxies available |
| E7 | `I_waste=(W_kg/1000)*EF_per_tonne/1000` | `calculate_waste_treatment`, C3/C4 | GHG workbook, Waste disposal; unit is per tonne, not per kg |
| E8 | `W_extra=M_installed*WR/(1-WR)` | `derive_waste_mass_from_installed` | RICS waste-rate definition; only when BOQ is installed mass |
| E9 | event carbon = materials + fuel + electricity + transport + waste | `calculate_b2_b5` | RICS B2-B5 activity inventory; event schedule must be project-sourced |
| E10 | `C1-C4=C1+C2+C3+C4` | `calculate_c1_c4` | RICS end-of-life modules |
| E11 | `D1=Q_net*q_sub*(EF_primary-EF_recovery)/1000` | `calculate_module_d1` | RICS section 5.7 / Appendix K; separate from gross A-C |
| E12 | `Gross A-C=A1-A3+A4+A5+B2-B5+B6+C1-C4` | `combine_lca_modules` | RICS modular reporting; Module D excluded |
| E13 | `GWP=Gross_A-C*1000/Lifetime_PKM` | `combine_lca_modules` | Functional-unit reporting; PKM must be sourced |

## Fixed numbers with source records

| Parameter | Value | Source |
|---|---:|---|
| Concrete UK average proxy | 0.10336134453781512 kgCO2e/kg | Audit workbook -> ICE V4.1, ICE Summary row 277; primary ICE workbook still required |
| Steel section | 1.61 kgCO2e/kg | Audit workbook -> ICE V4.1, row 893; primary ICE workbook still required |
| Aluminium worldwide market average | 13.055539991305551 kgCO2e/kg | Audit workbook -> ICE V4.1 rows 47/58; do not apply extra recycled-content mixing |
| Timber no-carbon-storage proxy | 0.49282614286872206 kgCO2e/kg | Audit workbook -> ICE V4.1 row 926 |
| Glass general | 1.4369670638496768 kgCO2e/kg | Audit workbook -> ICE V4.1 row 618 |
| FRP | OPEN | Product-specific EPD required or mass = 0 |
| Truck direct / WTT / WTW | 0.10163 / 0.02359 / 0.12522 kgCO2e/tkm | GHG workbook rows 63 and WTT row 57 |
| Rail direct / WTT / WTW | 0.02779 / 0.00691 / 0.03470 kgCO2e/tkm | GHG workbook rows 106 and WTT row 100 |
| Ship direct / WTT / WTW | 0.01321 / 0.00300 / 0.01621 kgCO2e/tkm | GHG workbook rows 152 and WTT row 146 |
| Diesel direct / WTT / WTW | 2.57082 / 0.61101 / 3.18183 kgCO2e/L | GHG workbook Fuels row 72 and WTT-fuels row 71 |
| Mineral recycling / landfill | 1.00835 / 1.26338 kgCO2e/tonne waste | GHG workbook Waste disposal rows 24/27/29 |
| Metals landfill | 1.26435 kgCO2e/tonne waste | GHG workbook Waste disposal row 31 |
| Polymer landfill proxy | 8.98311 kgCO2e/tonne waste | GHG workbook Waste disposal rows 74-82; scenario only for FRP/polymer |
| UK light-rail EI proxy | 0.124 kWh/pkm | GHG methodology, Table 27 p.79 |
| NTD light-rail proxy | 0.3031307255338944 kWh/pkm | Derived from 2024 NTD Energy + TS2.1 PMT |
| NTD automated-guideway proxy | 0.7844814382730434 kWh/pkm | Derived from 2024 NTD Energy + TS2.1 PMT |

## Still open - future modifications

1. `EGYPT_GRID_CI_T`: attach official annual Egypt/project electricity factors. The uploaded IEA PDF is methodology only.
2. `FRP_A1_A3_EF`: attach product-specific EPD or set FRP mass to zero.
3. `ICE_PRIMARY`: attach the original ICE V4.1 workbook or replace generic factors with product EPDs.
4. `A4_ROUTES`: enter source for every material route, distance, mode, payload/return assumption.
5. `A5_ACTIVITY`: enter contractor/site diesel, electricity, waste generation and routes.
6. `B2_B5_EVENTS`: enter each maintenance, repair, replacement and refurbishment event with O&M source.
7. `C1_C4_PLAN`: enter material-specific EOL shares, routes and processing/disposal factors.
8. `PASSENGER_KM`: enter forecast/measured passenger-km source.
9. `RSP`: enter project design-life/reference study period source.
10. Densities and geometry: use direct project mass where possible; otherwise source each density, thickness and material specification.

## Publication rule

The program may calculate a documented scenario before all open items are closed, but it must not label the result `publication_grade` while any required source is open, any FRP mass has no EPD, annual grid records are missing, or project activity quantities are unsourced.
