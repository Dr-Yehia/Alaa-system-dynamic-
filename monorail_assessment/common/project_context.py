"""Neutral project metadata shared by every assessment domain.

ARCHITECTURAL ROLE
------------------
This is the topmost neutral layer of the separated architecture:

    project_context  +  shared_activity        (neutral facts)
            |                  |
       +----+---------+--------+----+
       |              |             |
      LCA            LCC        BENEFITS      (independent domains)
       |              |             |
       +--------------+-------------+
                      |
            assessment_orchestrator          (assembly only)
                      |
                     UI

It holds ONLY facts that describe the project itself: who/where/when/in what
currency. It deliberately contains:

  * no emission factor and no carbon equation      -> those belong to the LCA domain
  * no tariff, discount rate or present-value logic -> those belong to the LCC domain
  * no jobs, time-saving or valuation logic         -> those belong to Benefits

Anything that is a *result* of one domain must never be stored here, otherwise the
domains become coupled again through this module.

NOTE ON PROVENANCE
------------------
The values below are the application's SCENARIO DEFAULTS, not project evidence.
A publication-grade run gets its reference study period, base year, currency and
geography from sourced project documents through the domain-specific scientific
engines, which enforce their own provenance gates. Nothing here certifies a number.
"""

from __future__ import annotations

from dataclasses import dataclass


# SCENARIO-ONLY UI DEFAULT — the reference study period used by the legacy dashboard.
# It is NOT a universal standard constant: RSP is project-defined, and the scientific
# LCA/LCC engines each require their own sourced analysis period.
# Moved verbatim from app_final_streamlit_ready.py during the architectural separation;
# the value is unchanged.
ASSESSMENT_LIFETIME_YEARS = 50


@dataclass(frozen=True)
class ProjectContext:
    """Identity, place, time and money units for one assessment run.

    Every field is a description of the project, never a computed result. The three
    domains read this; none of them writes it.
    """

    project_name: str = "Monorail"
    project_id: str = ""
    country: str = "Egypt"
    region: str = "Cairo"
    # Calendar year that project_year 0 corresponds to.
    analysis_base_year: int = 2026
    # Reference study period / analysis period N, in years.
    analysis_period_years: int = ASSESSMENT_LIFETIME_YEARS
    currency: str = "EGP"
    # Year in which monetary values are expressed before escalation.
    price_base_year: int = 2026

    @property
    def geography(self) -> str:
        """Geography label used by provenance gates (e.g. 'Cairo, Egypt')."""
        return f"{self.region}, {self.country}" if self.region else self.country

    def calendar_year(self, project_year: int) -> int:
        """Map a project year onto its calendar year."""
        return int(self.analysis_base_year) + int(project_year)


def context_from_params(params: dict) -> ProjectContext:
    """Build a ProjectContext from the application's parameter dictionary.

    This is one of the boundary adapters of the separation: the UI may still collect a
    single wide dictionary, but each domain receives only its own typed slice.
    """
    params = params or {}
    return ProjectContext(
        project_name=str(params.get("project_name", "Monorail")),
        project_id=str(params.get("project_id", "")),
        country=str(params.get("country", "Egypt")),
        region=str(params.get("region", "Cairo")),
        analysis_base_year=int(params.get("analysis_start_year", 2026) or 2026),
        analysis_period_years=int(
            params.get("assessment_lifetime", ASSESSMENT_LIFETIME_YEARS)
            or ASSESSMENT_LIFETIME_YEARS),
        currency=str(params.get("currency", "EGP") or "EGP"),
        # Boundary mapping, not a scientific choice. The UI collects this field as
        # `price_year`, while the LCC ledger names it `price_base_year`. Both spellings
        # are accepted, in that order of precedence, so a project whose price base year
        # differs from its analysis start year cannot lose it silently:
        #     price_base_year -> price_year -> analysis_start_year
        price_base_year=int(
            params.get("price_base_year")
            or params.get("price_year")
            or params.get("analysis_start_year", 2026)
            or 2026),
    )
