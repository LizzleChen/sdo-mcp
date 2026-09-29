"""Seed the store's lookup tables: geographies (from the committed Census 2020
county list snapshot) and the hand-curated coverage matrix.

The coverage rows are the machine-readable form of the cross-state synthesis
in plan/RESEARCH.md (pilot states, verified 2026-08-07) and plan/EXPANSION.md
(expansion states, verified 2026-08-10). They are what make "not published"
answers structural: refusals come from here, never from absence of data.
"""

from __future__ import annotations

import sqlite3

from ..store import REPO_ROOT

COUNTY_FILE = REPO_ROOT / "data" / "raw" / "census_national_county2020.txt"

# Renamed from PILOT_STATES when coverage grew past the six pilots
# (Phase 3.1, 2026-08): this is the list of states the server covers.
COVERED_STATES = {
    "CO": "Colorado",
    "TX": "Texas",
    "CA": "California",
    "TN": "Tennessee",
    "GA": "Georgia",
    "FL": "Florida",
    "NC": "North Carolina",
    "MN": "Minnesota",
    "AZ": "Arizona",
    "WA": "Washington",
    "OR": "Oregon",
    "VA": "Virginia",
    "WI": "Wisconsin",
    "UT": "Utah",
    "IN": "Indiana",
    "MI": "Michigan",
}

# (state, variable, geo_level, status, detail)
COVERAGE = [
    # ---- Colorado: the reference state — pop, HH, and an SDO jobs forecast
    ("CO", "population", "state", "available",
     "Estimates 1970-2024 + forecast 2025-2060, annual (DOLA components endpoint)."),
    ("CO", "population", "county", "available",
     "Estimates 1970-2024 + forecast 2025-2060, annual, all 64 counties."),
    ("CO", "population", "place", "not_published",
     "DOLA publishes municipal population estimates (2010-2024) only — no municipal "
     "forecast. County is the smallest forecast geography."),
    ("CO", "households", "state", "available",
     "2010-2050 annual. Source carries no estimate/projection flag; the boundary "
     "(2024/2025) is borrowed from the population series."),
    ("CO", "households", "county", "available",
     "2010-2050 annual, all 64 counties. Boundary borrowed from the population series."),
    ("CO", "households", "place", "not_published",
     "No municipal household forecast."),
    ("CO", "employment", "state", "available",
     "DOLA's own total-jobs series: estimates + forecast 2000-2050, annual."),
    ("CO", "employment", "county", "available",
     "Total county jobs 2000-2050, annual. Horizon 2050, not 2060 like population."),
    ("CO", "components", "state", "available",
     "Births, deaths, net migration 1970-2060, annual."),
    ("CO", "components", "county", "available",
     "Births, deaths, net migration 1970-2060, annual, all 64 counties."),

    # ---- Texas
    ("TX", "population", "state", "available",
     "Vintage 2024 (released 2025-09-30): annual 2020-2060, Mid/High/Low scenarios."),
    ("TX", "population", "county", "available",
     "Vintage 2024: all 254 counties, annual 2020-2060, Mid/High/Low scenarios."),
    ("TX", "population", "msa", "available",
     "Vintage 2024 MSA totals via the TDC Totals API, decade years "
     "(2020, 2030, 2040, 2050, 2060), Mid/High/Low scenarios."),
    ("TX", "population", "cog", "available",
     "Vintage 2024 COG totals via the TDC Totals API, decade years "
     "(2020, 2030, 2040, 2050, 2060), Mid/High/Low scenarios."),
    ("TX", "population", "txdot_district", "available",
     "Vintage 2024 TxDOT district totals via the TDC Totals API, decade years "
     "(2020, 2030, 2040, 2050, 2060), Mid/High/Low scenarios."),
    ("TX", "population", "place", "not_published",
     "TDC publishes place estimates only — no place/city projections. County is the "
     "smallest projected geography."),
    ("TX", "households", "state", "not_published",
     "No current product. The last household projection was a Vintage-2018 special "
     "(2010-2050), since withdrawn from the site."),
    ("TX", "households", "county", "not_published",
     "No current product. The last household projection was a Vintage-2018 special "
     "(2010-2050), since withdrawn from the site."),
    ("TX", "employment", "state", "not_published",
     "TDC publishes no employment forecast. TWC (labor department) occupational "
     "projections are a different product, out of scope."),
    ("TX", "employment", "county", "not_published",
     "TDC publishes no employment forecast. TWC (labor department) occupational "
     "projections are a different product, out of scope."),
    ("TX", "components", "county", "not_published",
     "No components-of-change forecast product verified for TDC."),

    # ---- California
    ("CA", "population", "state", "available",
     "P-series Baseline 2024 Vintage 2026: 2020-2070 annual."),
    ("CA", "population", "county", "available",
     "P-series Baseline 2024 Vintage 2026: all 58 counties, 2020-2070 annual."),
    ("CA", "population", "place", "not_published",
     "DOF publishes no sub-county projections (E-series city figures are estimates)."),
    ("CA", "households", "state", "available",
     "P-4 (Vintage 2025): state household totals, estimates 2010-2025 + "
     "projections 2026-2040."),
    ("CA", "households", "county", "available",
     "P-4 (Vintage 2025, lags the population series): county household totals, "
     "projections 2026-2040. The LRCF product separately carries county households "
     "to 2055 — the two disagree and are never merged."),
    ("CA", "households", "place", "not_published",
     "E-5 city household figures are estimates, not projections."),
    ("CA", "employment", "state", "available",
     "LRCF (DOF Economic Research Unit + Caltrans, Jan 2026): statewide farm + "
     "total nonfarm jobs 2000-2055, annual, forecast from 2025."),
    ("CA", "employment", "county", "available",
     "LRCF (DOF Economic Research Unit + Caltrans, Jan 2026): farm + total nonfarm "
     "jobs to 2055, annual. No industry detail (that is EDD, out of scope)."),
    ("CA", "components", "state", "available",
     "P-CC components of change (births, deaths, net migration), periods "
     "2020-21 through 2069-70."),
    ("CA", "components", "county", "available",
     "PCC components of change file (births, deaths, migration)."),

    # ---- Tennessee
    ("TN", "population", "state", "available",
     "2022 vintage (Aug 2024): base 2022 estimate, projections 2023-2070 annual."),
    ("TN", "population", "county", "available",
     "2022 vintage: all 95 counties, projections 2023-2070 annual; crossed "
     "age x sex x race detail available (from the Boyd Center ArcGIS service)."),
    ("TN", "population", "place", "not_published",
     "Municipal certified estimates only — no place projections."),
    ("TN", "households", "state", "not_published",
     "The Boyd Center publishes no household projections at any geography."),
    ("TN", "households", "county", "not_published",
     "The Boyd Center publishes no household projections at any geography."),
    ("TN", "employment", "state", "pdf_only",
     "State jobs forecast exists only inside the Economic Report to the Governor "
     "(narrative PDF, short horizon) — not a serveable dataset."),
    ("TN", "employment", "county", "not_published",
     "No county employment forecast from the Boyd Center. Jobs4TN (labor "
     "department) is out of scope."),
    ("TN", "components", "county", "not_published",
     "No components-of-change product in the published summary files."),

    # ---- Georgia
    ("GA", "population", "state", "available",
     "2026 vintage (released 2026-07-21): 2026-2065, single-year steps."),
    ("GA", "population", "county", "available",
     "2026 vintage: all 159 counties, 2026-2065, single-year steps."),
    ("GA", "population", "place", "not_published",
     "OPB/UGA publish no sub-county projections."),
    ("GA", "households", "state", "not_published",
     "OPB/UGA publish population only — no household projections."),
    ("GA", "households", "county", "not_published",
     "OPB/UGA publish population only — no household projections."),
    ("GA", "employment", "state", "not_published",
     "No employment product from the demography producer. GA DOL projections are "
     "a different product, out of scope."),
    ("GA", "employment", "county", "not_published",
     "No employment product from the demography producer. GA DOL projections are "
     "a different product, out of scope."),
    ("GA", "components", "county", "not_published",
     "No components-of-change product published."),

    # ---- Florida
    ("FL", "population", "state", "available",
     "BEBR 2026 edition: base April 1 2025, projections 2030-2050 in 5-year steps, "
     "Low/Medium/High scenarios."),
    ("FL", "population", "county", "available",
     "BEBR 2026 edition: all 67 counties, 2030-2050 in 5-year steps, L/M/H "
     "scenarios. Values rounded to the nearest 100."),
    ("FL", "population", "place", "not_published",
     "BEBR city figures are estimates only — no municipal forecast."),
    ("FL", "households", "state", "pdf_only",
     "State household forecast (incl. household size) exists in the FDEC "
     "conference packet PDF — not yet a serveable dataset."),
    ("FL", "households", "county", "state_level_only",
     "No county household projection published (county household *estimates* "
     "only). A state-level forecast exists in the FDEC conference packet (PDF)."),
    ("FL", "employment", "state", "pdf_only",
     "EDR long-run tables (PDF): nonfarm employment total + by industry, horizon "
     "~FY2036 — not yet a serveable dataset."),
    ("FL", "employment", "county", "state_level_only",
     "No county employment forecast from BEBR/EDR (county level belongs to "
     "FloridaCommerce, the labor department — out of scope). A state-level "
     "forecast exists in EDR's long-run tables (PDF)."),
    ("FL", "components", "county", "not_published",
     "No components-of-change product published."),

    # ---- North Carolina
    ("NC", "population", "state", "available",
     "Vintage 2025B (errata release): estimates 2010-2024 + projections "
     "2025-2060, annual, July 1."),
    ("NC", "population", "county", "available",
     "Vintage 2025B: all 100 counties, estimates 2010-2024 + projections "
     "2025-2060, annual."),
    ("NC", "population", "place", "not_published",
     "OSBM publishes municipal estimates only (certified 2024) — no municipal "
     "projections. County is the smallest projected geography."),
    ("NC", "households", "state", "not_published",
     "OSBM publishes no household forecast; household population is an "
     "internal model step only."),
    ("NC", "households", "county", "not_published",
     "OSBM publishes no household forecast; household population is an "
     "internal model step only."),
    ("NC", "employment", "state", "not_published",
     "The State Demographer's Office publishes no employment forecast. NC "
     "Commerce labor projections are a different product, out of scope."),
    ("NC", "employment", "county", "not_published",
     "The State Demographer's Office publishes no employment forecast. NC "
     "Commerce labor projections are a different product, out of scope."),
    ("NC", "components", "state", "not_published",
     "No components-of-change product published."),
    ("NC", "components", "county", "not_published",
     "No components-of-change product published."),

    # ---- Minnesota
    ("MN", "population", "state", "available",
     "May 2024 vintage: 2024-2075 annual. Every point is a projection — the "
     "2024 launch value itself is projected (last underlying estimate is "
     "Census Vintage 2022)."),
    ("MN", "population", "county", "available",
     "May 2024 vintage: all 87 counties, 2024-2055 annual (county detail ends "
     "20 years before the state series). All projection, incl. 2024."),
    ("MN", "population", "place", "not_published",
     "SDC publishes city/township estimates only (PopFinder) — no municipal "
     "projections."),
    ("MN", "households", "state", "not_published",
     "No household projections — the methodology is only 'being drafted' per "
     "the Dec 2024 projections plan."),
    ("MN", "households", "county", "not_published",
     "No household projections — the methodology is only 'being drafted' per "
     "the Dec 2024 projections plan."),
    ("MN", "employment", "state", "not_published",
     "The SDC publishes no employment forecast. DEED (labor department) "
     "projections are a different product, out of scope."),
    ("MN", "employment", "county", "not_published",
     "The SDC publishes no employment forecast. DEED (labor department) "
     "projections are a different product, out of scope."),
    ("MN", "components", "state", "available",
     "Births, deaths, net migration 2024-2075, annual, from the same workbook "
     "(all projection)."),
    ("MN", "components", "county", "not_published",
     "Components of change are published statewide only."),

    # ---- Arizona
    ("AZ", "population", "state", "available",
     "2025 edition: July 1 2025 launch (equals the official estimate) + "
     "projections 2026-2060, annual, Low/Medium/High scenarios."),
    ("AZ", "population", "county", "available",
     "2025 edition: all 15 counties, 2025-2060 annual, Low/Medium/High "
     "scenarios."),
    ("AZ", "population", "place", "not_published",
     "OEO's only place-level product sits on a stale 2022-consistent vintage "
     "(Maricopa/Pinal places from MAG, Pima from PAG) and is deliberately not "
     "served; the 2025-series place projections are due Sept 2026."),
    ("AZ", "households", "state", "not_published",
     "OEO publishes no household forecast (MAG is the household source for "
     "metro Phoenix)."),
    ("AZ", "households", "county", "not_published",
     "OEO publishes no household forecast (MAG is the household source for "
     "metro Phoenix)."),
    ("AZ", "employment", "state", "not_published",
     "No SDO jobs forecast. OEO's industry/occupation projections are the "
     "labor-market product (labor-department equivalent), out of scope."),
    ("AZ", "employment", "county", "not_published",
     "No SDO jobs forecast. OEO's industry/occupation projections are the "
     "labor-market product (labor-department equivalent), out of scope."),
    ("AZ", "components", "state", "available",
     "Births, deaths, total net migration 2025-2060, per scenario, from the "
     "projection workbooks (domestic/foreign split in source)."),
    ("AZ", "components", "county", "available",
     "Births, deaths, total net migration 2025-2060, per scenario, from the "
     "projection workbooks (domestic/foreign split in source)."),

    # ---- Washington
    ("WA", "population", "state", "available",
     "November 2025 state forecast: estimates through 2025 and projections "
     "2026-2050, annual, single series."),
    ("WA", "population", "county", "available",
     "2022 GMA projections: all 39 counties, estimates 2020-2022 and "
     "projections 2025-2050, annual after 2025, Low/Medium/High scenarios."),
    ("WA", "population", "place", "not_published",
     "OFM publishes city and town estimates only and does not develop "
     "sub-county population projections."),
    ("WA", "households", "state", "not_published",
     "OFM publishes no household projection product."),
    ("WA", "households", "county", "not_published",
     "OFM publishes no household projection product."),
    ("WA", "employment", "state", "pdf_only",
     "OFM's Forecasting and Research Division publishes a state Long-Term "
     "Economic Forecast with nonfarm jobs through 2050 in PDF tables; it is "
     "not loaded as a serveable series."),
    ("WA", "employment", "county", "state_level_only",
     "OFM publishes no county jobs forecast. A state-level forecast exists in "
     "the separate Long-Term Economic Forecast PDF."),
    ("WA", "components", "state", "available",
     "November 2025 OFM components: annual April-to-April totals ending "
     "2011-2050; estimates through 2025, projections from 2026. Loaded."),
    ("WA", "components", "county", "available",
     "2022 GMA components: medium scenario only, all 39 counties, five-year "
     "April-to-April totals ending 1965-2050. Estimates through ending year "
     "2020; projections from period 2020-2025. Loaded; no annual interpolation."),

    # ---- Oregon
    ("OR", "population", "state", "not_published",
     "PSU PRC publishes no official statewide Oregon Population Forecast Program "
     "series. The OHNA statewide pilot explicitly does not replace OPFP."),
    ("OR", "population", "county", "available",
     "Latest rolling regional releases cover 35 counties: 2023, 2024, 2025, and "
     "2026 vintages with county-specific base years and horizons. Multnomah County "
     "is excluded and handled by Metro."),
    ("OR", "population", "place", "not_published",
     "OPFP regional products forecast urban growth boundaries, which are not the "
     "same as incorporated places. No place forecast is served."),
    ("OR", "households", "state", "not_published",
     "PSU PRC publishes no household forecast; household size and vacancy are "
     "model inputs, not forecast outputs."),
    ("OR", "households", "county", "not_published",
     "PSU PRC publishes no household forecast; household size and vacancy are "
     "model inputs, not forecast outputs."),
    ("OR", "employment", "state", "not_published",
     "PSU PRC publishes no employment forecast."),
    ("OR", "employment", "county", "not_published",
     "PSU PRC publishes no employment forecast."),
    ("OR", "components", "state", "not_published",
     "No official statewide components forecast is published."),
    ("OR", "components", "county", "not_published",
     "The regional county workbooks publish population detail, not components of change."),

    # ---- Virginia
    ("VA", "population", "state", "available",
     "Cooper Center July 2025 baseline projections: 2030, 2035, 2040, 2045, 2050, and 2055. "
     "All points are projections from a 2024 estimate base."),
    ("VA", "population", "county", "available",
     "Cooper Center July 2025 totals for all 133 county-equivalent localities (95 counties + 38 independent cities), "
     "six published years 2030-2055. The separate age/sex and large-town products are not ingested."),
    ("VA", "population", "place", "available",
     "Cooper Center publishes a separate large-town projection product; it is available from the source page but not ingested in this pass."),

    # ---- Wisconsin
    ("WI", "population", "state", "available",
     "Wisconsin DOA Vintage 2024 totals: 2020 estimate plus 2030, 2040, and 2050 projections."),
    ("WI", "population", "county", "available",
     "Wisconsin DOA Vintage 2024 totals for all 72 counties: 2020 estimate plus 2030, 2040, and 2050 projections."),
    ("WI", "population", "place", "available",
     "DOA publishes minor-civil-division and municipal population projections 2020-2050; those subcounty tables are available but not ingested in this pass."),
    ("WI", "households", "state", "available",
     "DOA publishes state household totals for 2020, 2030, 2040, and 2050; 2020 is the estimate/base and later points are projections."),
    ("WI", "households", "county", "available",
     "DOA publishes all 72 county household totals for 2020, 2030, 2040, and 2050; county sums can differ from the state by rounding."),
    ("WI", "households", "place", "available",
     "DOA publishes minor-civil-division and municipal household projections 2020-2050; those subcounty tables are available but not ingested in this pass."),

    # ---- Indiana: July 2024 IBRC edition, verified 2026-09-28
    ("IN", "population", "state", "available",
     "IBRC July 2024: 2020 estimate plus projections 2025-2060 in five-year steps. "
     "State methodology uses a 2020 population anchor with estimates and components through 2023; "
     "the last underlying estimate year is 2023."),
    ("IN", "population", "county", "available",
     "IBRC July 2024: all 92 counties, 2020 estimates plus projections 2025-2050 "
     "in five-year steps. County methodology uses 2023 estimates as its projection base; "
     "2023 values are not included in the published table."),
    ("IN", "population", "place", "not_published",
     "STATS Indiana's population catalog marks city/town projections unavailable; "
     "place figures are Census counts and estimates only."),
    ("IN", "population", "msa", "available",
     "The IBRC query tool publishes metro-area aggregations, including only Indiana "
     "counties in interstate metros. These region totals are not ingested."),

    # ---- Michigan: MCDA Vintage 2024, checked 2026-09-29
    ("MI", "population", "state", "available",
     "MCDA Vintage 2024 main net-positive-migration scenario: five-year points "
     "2025-2050, all projections, from the documented 2022 estimate base. "
     "The report's illustrative zero-migration scenario is not loaded."),
    ("MI", "population", "county", "available",
     "MCDA Vintage 2024: all 83 counties, six published points 2025-2050, "
     "all projections. Fractional model totals are preserved. County methodology "
     "does not explicitly identify the population base year; it remains unknown. "
     "Prosperity-region and age/sex detail is archived but not served."),

    # ---- Utah
    ("UT", "population", "state", "available",
     "Gardner Policy Institute 2025-2065 baseline: annual July 1 state projections, all points projection-labelled."),
    ("UT", "population", "county", "available",
     "Gardner Policy Institute 2025-2065 baseline: annual July 1 projections for all 29 counties."),
    ("UT", "households", "state", "available",
     "Gardner Policy Institute workbook: annual state household projections 2025-2065."),
    ("UT", "households", "county", "available",
     "Gardner Policy Institute workbook: annual household projections 2025-2065 for all 29 counties."),
    ("UT", "employment", "state", "available",
     "Gardner Policy Institute workbook: annual state total-jobs projections 2025-2065 (wage/salary plus self-employment)."),
    ("UT", "employment", "county", "available",
     "Gardner Policy Institute workbook: annual county total-jobs projections 2025-2065 for all 29 counties."),
    ("UT", "components", "state", "available",
     "Gardner Policy Institute workbook publishes annual births, deaths, and net migration 2025-2065; loaded."),
    ("UT", "components", "county", "available",
     "Gardner Policy Institute workbook publishes annual births, deaths, and net migration 2025-2065 for all 29 counties; loaded."),
]


def load_geographies(conn: sqlite3.Connection) -> int:
    """State + county rows for the covered states, Census 2020 spelling."""
    abbrev_by_name = {}
    rows = []
    seen_states = set()
    for line in COUNTY_FILE.read_text().splitlines()[1:]:
        parts = line.split("|")
        if len(parts) < 5:
            continue
        st, statefp, countyfp, _ns, name = parts[:5]
        if st not in COVERED_STATES:
            continue
        if st not in seen_states:
            seen_states.add(st)
            rows.append((statefp, "state", st, COVERED_STATES[st]))
            abbrev_by_name[st] = statefp
        rows.append((statefp + countyfp, "county", st, name))
    conn.executemany(
        "INSERT OR REPLACE INTO geographies (geo_id, geo_level, state, name)"
        " VALUES (?,?,?,?)",
        rows,
    )
    return len(rows)


def load_coverage(conn: sqlite3.Connection) -> int:
    conn.executemany(
        "INSERT OR REPLACE INTO coverage (state, variable, geo_level, status, detail)"
        " VALUES (?,?,?,?,?)",
        COVERAGE,
    )
    return len(COVERAGE)


def load(conn: sqlite3.Connection) -> None:
    n_geo = load_geographies(conn)
    n_cov = load_coverage(conn)
    conn.commit()
    print(f"seed: {n_geo} geography rows, {n_cov} coverage rows")
