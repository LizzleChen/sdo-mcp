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
    "IL": "Illinois",
    "KY": "Kentucky",
    "MD": "Maryland",
    "DE": "Delaware",
    "NM": "New Mexico",
    "SC": "South Carolina",
    "AL": "Alabama",
    "WY": "Wyoming",
    "MI": "Michigan",
    "PA": "Pennsylvania",
    "AK": "Alaska",
    "HI": "Hawaii",
    "ME": "Maine",
    "NE": "Nebraska",
    "NH": "New Hampshire",
    "NV": "Nevada",
    "OH": "Ohio",
    'CT': 'Connecticut',
    'MA': 'Massachusetts',
    'NJ': 'New Jersey',
    'NY': 'New York',
    'RI': 'Rhode Island',
    'ID': 'Idaho',
    'ND': 'North Dakota',
    'MS': 'Mississippi',
    'SD': 'South Dakota',
    'KS': 'Kansas',
    'MO': 'Missouri',
    'IA': 'Iowa',
    'MT': 'Montana',
    'WV': 'West Virginia',
    'AR': 'Arkansas',
    'LA': 'Louisiana',
    'OK': 'Oklahoma',
    'VT': 'Vermont',
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

    # ---- Illinois: IDPH 2023 edition, released May 2024
    ("IL", "population", "state", "available",
     "IDPH 2023 edition, Table 3: July 2020 estimate and July 2025, 2030, 2035 "
     "projections. The separate April 2020 Census column is not served."),
    ("IL", "population", "county", "available",
     "IDPH Table 3: all 102 counties, July 2020 estimates and five-year "
     "projections 2025-2035. Source DeWitt maps to Census De Witt County."),
    ("IL", "population", "place", "available",
     "IDPH Table 2 publishes Chicago population projections through 2035. "
     "Chicago is archived but not loaded; this does not establish coverage for other cities."),
    ("IL", "components", "state", "pdf_only",
     "IDPH Tables A-2, A-4 and A-5 publish births, deaths and net migration "
     "for five-year periods 2020-2025, 2025-2030 and 2030-2035. Not loaded."),
    ("IL", "components", "county", "pdf_only",
     "IDPH Tables A-2, A-4 and A-5 publish county births, deaths and net "
     "migration as five-year period totals through 2035. Not loaded."),

    # ---- Kentucky: KSDC Vintage 2022, retrieved 2026-09-29
    ("KY", "population", "state", "available",
     "KSDC Vintage 2022: 2020 historical total and five-year projections 2025-2050; "
     "last underlying estimate input 2021, Census anchor 2020."),
    ("KY", "population", "county", "available",
     "KSDC Vintage 2022: all 120 counties, 2020 historical totals and five-year "
     "projections 2025-2050. Population totals are aggregated from published "
     "age-by-sex rows; Area Development District totals are published but not served."),
    ("KY", "population", "place", "not_published",
     "The Vintage 2022 product publishes state, county, and Area Development "
     "District projections; it has no city/place projection series."),
    ("KY", "households", "state", "available",
     "KSDC Vintage 2022: 2020 historical total and five-year household projections 2025-2050; "
     "household-count anchor 2020, last underlying population estimate input 2021."),
    ("KY", "households", "county", "available",
     "KSDC Vintage 2022: all 120 counties, 2020 historical totals and five-year "
     "household projections 2025-2050. Area Development District totals are "
     "published but not served."),
    ("KY", "households", "place", "not_published",
     "The Vintage 2022 product publishes state, county, and Area Development "
     "District projections; it has no city/place household projection series."),

    # ---- Maryland: separate population/household and preliminary jobs editions
    ("MD", "population", "state", "available",
     "November 2025: 2020 Census anchor and five-year projections 2025-2055."),
    ("MD", "population", "county", "available",
     "November 2025: 2020 Census anchor and five-year projections 2025-2055 for "
     "23 counties and Baltimore City (24510), distinct from Baltimore County (24005)."),
    ("MD", "households", "state", "available",
     "November 2025: 2020 Census household counts and five-year projections 2025-2055."),
    ("MD", "households", "county", "available",
     "November 2025: household counts for all 24 county equivalents, 2020-2055. "
     "These are households, not household population or housing units."),
    ("MD", "employment", "state", "available",
     "Preliminary October 2022 MDP total jobs by place of work: BEA 2020 history "
     "and five-year projections 2025-2050. Separate vintage from population/households."),
    ("MD", "employment", "county", "available",
     "Preliminary October 2022 MDP total jobs for all 24 county equivalents, "
     "2020-2050 in five-year steps; not labor force or occupational projections."),

    # ---- Delaware: DPC 2024 edition, readopted for 2025
    ("DE", "population", "state", "available",
     "DPC October 2024 resident population: 2020 history and 2025-2050 five-year projections; readopted December 2025."),
    ("DE", "population", "county", "available",
     "DPC October 2024 resident population for all three counties, 2020-2050."),
    ("DE", "population", "place", "available",
     "DPC publishes separate municipal projections; not loaded. Seasonal population is a distinct product."),
    ("DE", "households", "state", "available",
     "DPC 2024 household counts, 2020 history and 2025-2050 projections."),
    ("DE", "households", "county", "available",
     "DPC 2024 household counts for all three counties, 2020-2050."),
    ("DE", "employment", "state", "available",
     "DPC 2024 jobs by place of work, 2020 history and 2025-2050 projections; not resident employment."),
    ("DE", "employment", "county", "available",
     "DPC 2024 jobs by place of work for all three counties, 2020-2050."),

    # ---- New Mexico: UNM-GPS spring 2024 edition
    ("NM", "population", "state", "available",
     "UNM-GPS Spring 2024: 2020 Census history and five-year projections 2025-2050, with a 2022 estimate model launch."),
    ("NM", "population", "county", "available",
     "UNM-GPS Spring 2024: all 33 counties, 2020 Census history and 2025-2050 five-year projections."),

    # ---- South Carolina: RFA Vintage 2023, 2019-2023 estimate base
    ("SC", "population", "state", "available",
     "RFA Vintage 2023: July 2023 estimate and annual projections 2024-2043."),
    ("SC", "population", "county", "available",
     "RFA Vintage 2023: 2023 estimate and annual projections 2024-2043 for all 46 counties."),

    # ---- Alabama: CBER/ASDC 2025 estimates and 2030-2050 projections
    ("AL", "population", "state", "available",
     "CBER 2025-based Fall 2026 file: 2025 estimate and five-year projections 2030-2050."),
    ("AL", "population", "county", "available",
     "CBER 2025-based file: all 67 counties, 2025 estimate and five-year projections 2030-2050."),

    # ---- Wyoming: EAD February 2025 population, 2023 estimate boundary
    ("WY", "population", "state", "available",
     "EAD February 2025: 2020 Census and 2021-2023 estimates, then annual forecasts 2024-2050."),
    ("WY", "population", "county", "available",
     "EAD February 2025: all 23 counties, 2020-2023 history and annual forecasts 2024-2050."),
    ("WY", "population", "place", "available",
     "EAD publishes municipal forecasts based on place/county ratios; archived but not loaded."),

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

    # ---- Pennsylvania: 2023 PaSDC edition, checked 2026-09-29
    ("PA", "population", "state", "available",
     "PaSDC 2023 edition: July 1, 2020 estimate (Census Vintage 2022) plus "
     "five-year projections 2025-2050. Population base year is 2020."),
    ("PA", "population", "county", "available",
     "PaSDC 2023 edition: all 67 counties, 2020 estimates plus five-year "
     "projections 2025-2050. Age/sex detail is archived but not served."),
    ("PA", "components", "state", "pdf_only",
     "The December 2023 methodology report, Table 3, publishes statewide births, "
     "deaths, domestic and overseas migration for five-year periods 2020-2025 "
     "through 2045-2050. These period totals are not loaded."),

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

    # ---- Batch two: selected published products
    ("AK", "population", "state", "available",
     "September 2026: July 1, 2025 estimate plus annual 2026–2055 projections, Low/Middle/High; mid maps to Middle."),
    ("AK", "population", "county", "available",
     "All 30 current boroughs/census areas: 2025 estimate and five-year 2030–2055 projections in a single series aligned to statewide Middle."),
    ("AK", "components", "state", "available",
     "September 2026 publication has annual births/deaths/net migration under each state scenario; archived but not loaded."),
    ("AK", "components", "county", "available",
     "September 2026 county tables publish components as five-year-period average annual quantities; archived but not loaded."),
    ("HI", "population", "state", "available",
     "DBEDT April 2024: July 1, 2020 estimate and 2030/2040/2050 resident-population projections. Model base 2020; estimate edition Census Vintage 2022."),
    ("HI", "population", "county", "available",
     "DBEDT state and four county groups at 2020/2030/2040/2050. Maui/Kalawao is one combined series under hi-maui-kalawao; individual 15005/15009 are not populated."),
    ("HI", "employment", "state", "available",
     "DBEDT April 2024 civilian total jobs: BEA/DBEDT 2022 estimates and 2030/2040/2050 projections; wage/salary plus proprietors, military excluded."),
    ("HI", "employment", "county", "available",
     "DBEDT civilian total jobs for four county groups, 2022/2030/2040/2050, rounded to tens. Maui/Kalawao combined under hi-maui-kalawao."),
    ("HI", "components", "state", "pdf_only",
     "April 2024 report Table 2 publishes average annual births, deaths and natural changes for decadal periods through 2050; not loaded."),
    ("ME", "population", "state", "available",
     "OSE April 2025: 2022 historical estimate and exact five-year projection points 2027, 2032, 2037 and 2042; fractional workbook totals retained."),
    ("ME", "population", "county", "available",
     "OSE April 2025: 2022 historical estimate and exact five-year projection points 2027, 2032, 2037 and 2042; fractional workbook totals retained."),
    ("ME", "population", "place", "available",
     "OSE publishes city/town projections for 2027, 2032, 2037 and 2042, archived but not loaded. Publisher suppresses locations with fewer than 10 people in any projected year."),
    ("NE", "population", "state", "available",
     "UNO CPAR August 2022 adopted Hauer/SEDAC regional-rivalry product: 2020 Census counts and projections for 2030, 2040 and 2050; published state row and all 93 counties loaded."),
    ("NE", "population", "county", "available",
     "UNO CPAR August 2022 adopted Hauer/SEDAC regional-rivalry product: 2020 Census counts and projections for 2030, 2040 and 2050; published state row and all 93 counties loaded."),
    ("NH", "population", "state", "available",
     "OPD September 2022 Table 1: 2020 Census-based history and five-year projections 2025-2050; checked PDF totals loaded."),
    ("NH", "population", "county", "available",
     "All 10 counties, seven exact points 2020-2050. Table 1 and Appendix A checked; the 2030 state/county one-person discrepancy is preserved."),
    ("NH", "population", "place", "available",
     "OPD Appendix B publishes city and town population projections 2020-2050; published cities are deferred place data. Towns require county-subdivision support; none are loaded."),
    ("NH", "components", "state", "pdf_only",
     "Appendix A Tables 1-3 publish five-year projected births, deaths and net migration for 2020-2025 through 2045-2050; not loaded or annualized."),
    ("NH", "components", "county", "pdf_only",
     "Appendix A Tables 1-3 publish five-year projected components for all 10 counties; not loaded or annualized."),
    ("NV", "population", "state", "available",
     "October 2025 long-range edition: 2024 Governor-certified estimate and annual projections 2025-2044; state and all 17 county equivalents including Carson City."),
    ("NV", "population", "county", "available",
     "October 2025 long-range edition: 2024 Governor-certified estimate and annual projections 2025-2044; state and all 17 county equivalents including Carson City."),
    ("OH", "population", "state", "available",
     "Research Office Report 2023 edition: 2020 estimates and exact five-year projections 2025-2050; published workbook totals loaded."),
    ("OH", "population", "county", "available",
     "All 88 counties at seven five-year points 2020-2050. County totals reconcile exactly to the separately published state row; workbook Ottawa 2050 is retained despite an overview-map discrepancy."),
    # ---- Batch three: selected demographic editions and municipal geography
    ('MA', 'population', 'state', 'available',
     'UMass Donahue Institute Vintage 2024 (May 2024): exact adjusted 2020 historical launch and '
     'five-year projections 2025-2050; fractional historical total retained.'),
    ('MA', 'population', 'county', 'available',
     'All 14 counties at seven published points 2020-2050. Totals checked against the independently '
     'published age/sex workbook and municipal/RPA sums.'),
    ('MA', 'population', 'place', 'available',
     'Vintage 2024 publishes municipal population projections, including cities; city/place '
     'identifiers and totals are deferred and not loaded. Published MCD codes are not Census place '
     'FIPS.'),
    ('MA', 'population', 'county_subdivision', 'available',
     'Vintage 2024 publishes all 351 city/town MCD population projections at 2020 and five-year points '
     '2025-2050. Municipal county-subdivision identifier loading is deferred; originals are archived '
     'but not loaded.'),
    ('NJ', 'population', 'state', 'available',
     'NJDOL 2014–2034 series: July 1, 2014 estimate and 2019/2024/2029/2034 projections, four state '
     'models. Preferred Economic-Demographic is the default; old projection dates do not become '
     'estimates.'),
    ('NJ', 'population', 'county', 'available',
     'All 21 counties: July 1, 2014 estimate and exact five-year 2019/2024/2029/2034 projections under '
     'one Economic-Demographic model. State-only alternatives do not apply; published rounding and the '
     '2029 state/county discrepancy are retained.'),
    ('NY', 'population', 'state', 'available',
     'Cornell PAD October 2024 state-only edition: July 2022 estimate base and annual 2023-2050 '
     'projections; all Middle/High/Low scenarios loaded. Published fractional counts preserved.'),
    ('NY', 'population', 'county', 'available',
     'Cornell PAD September 21, 2018 county edition: 2015 estimate base and annual 2016-2040 '
     'projections, all 62 counties, one series. This older product is separate from the 2024 statewide '
     'scenarios.'),
    ('NY', 'population', 'economic_region', 'available',
     'The 2018 county explorer and user guide publish 10 economic-region population series, 2015-2040; '
     'these aggregates are not loaded.'),
    ('NY', 'components', 'state', 'available',
     'All three October 2024 state scenario workbooks publish annual 2023-2050 births, deaths and '
     'domestic/international migration flows in Components; archived, not loaded.'),
    ('NY', 'components', 'county', 'available',
     'The 2018 county chart JSON publishes annual 2016-2040 births, deaths, net migration, natural '
     'increase and special population change; archived, not loaded.'),
    ('CT', 'population', 'state', 'available',
     'Revised September 2017 edition: exact five-year resident population projections 2015-2040; 2010 '
     'Census anchor.'),
    ('CT', 'population', 'county', 'available',
     'June 2018 release based on the 2017 model, all eight historical counties at six points '
     '2015-2040. Modern planning-region county equivalents are not substituted.'),
    ('CT', 'population', 'cog', 'available',
     'Nine 2018 regional councils of government at six points 2015-2040, separate prefixed IDs and no '
     'mapping to modern county-equivalent FIPS.'),
    ('CT', 'population', 'county_subdivision', 'available',
     'Official SDC town projections are documented in the archived DSS report; town identifiers and '
     'observations remain deferred.'),
    ('RI', 'population', 'state', 'available',
     'Official February 27, 2026 revised table Total row, exact five-year projections 2025-2050; base '
     'year unconfirmed.'),
    ('RI', 'population', 'county_subdivision', 'available',
     'All 39 cities/towns at six points 2025-2050. Ten-digit Census county-subdivision GEOIDs, '
     'distinct from Census places.'),
    # ---- Batch four: verified population products and unresolved source findings
    ('ID', 'population', 'state', 'available',
     'Revised August 7, 2025 edition: exact annual 2024–2034 projections, explicit statewide Total '
     'row. ACS inputs; last estimate year unconfirmed.'),
    ('ID', 'population', 'county', 'available',
     'All 44 counties in six original regional workbooks; 11 annual 2024–2034 population Total rows, '
     'all projections.'),
    ('ID', 'population', 'economic_region', 'available',
     'Six regional Total series 2024–2034 published in original workbooks; region '
     'observations/identifiers deferred and not loaded.'),
    ('ID', 'population', 'place', 'not_published',
     'The currently linked 2017 Department of Labor general population methods identify county as its '
     'most detailed modeled geography; no municipal series is substituted.'),
    ('ND', 'population', 'state', 'available',
     'February 6, 2024 report, pp 10–11 summary: 2020 Census anchor and exact five-year 2025–2050 '
     'projections; published state 2050=957194 differs from executive/catalog 957124.'),
    ('ND', 'population', 'county', 'available',
     'All 53 counties at seven exact points 2020–2050, pp 10–11 summary; published county/state '
     'discrepancies 0,-1, 0,+1,+4,+2,+2 preserved.'),
    ('ND', 'population', 'economic_region', 'available',
     'Eight economic-planning region series at five-year 2020–2050 points published on p 9; '
     'identifiers/observations deferred.'),
    ('ND', 'components', 'state', 'pdf_only',
     'Printed page 6 publishes six five-year natural-change, net-migration and total-expected-change '
     'intervals 2020–2025 through 2045–2050; not separate births/deaths, not loaded or annualized.'),
    ('SD', 'population', 'state', 'available',
     'Preliminary 2012 Medium Series: exact 2010 Census base and five-year 2015–2035 projections. '
     'Original workbook precision preserved.'),
    ('SD', 'population', 'county', 'available',
     'All 66 source-era counties, 2010–2035 five-year points, Medium Series. Shannon uses historical '
     'name/FIPS 46113; modern Oglala Lakota 46102 is not substituted.'),
    ('MS', 'population', 'state', 'available',
     'May 2, 2019 preliminary state release, exact five-year 2020–2050 projections from 2010 launch; '
     'seven published rounded totals.'),
    ('MS', 'population', 'county', 'available',
     'The original State Data Center catalog explicitly offers county projections upon request; no '
     'county numeric table is loaded and no correspondence was undertaken.'),
    ('MS', 'population', 'place', 'available',
     'The original State Data Center catalog explicitly offers place-based projections upon request; '
     'place identifiers and numeric data remain deferred.'),
    ('KS', 'population', 'county', 'available',
     'November 2006 projections commissioned by the Division of the Budget, published January 2010: '
     'all 105 counties, annual 2010-2021. The entire horizon is in the past; last estimate base is '
     'unknown. Newer CEDBR 2024 authority/adoption is unconfirmed.'),
    ('MO', 'population', 'state', 'available',
     'Old March 2008 Preferred Series: April 1 totals at five-year points 2000-2030. Last estimate '
     'input is 2007; Census 2000 anchor and explicit 2005 projection labels are preserved.'),
    ('MO', 'population', 'county', 'available',
     'Old March 2008 Preferred Series: all 114 counties plus independent St. Louis city, five-year '
     'points 2000-2030. Current official catalog still links this edition; no successor was '
     'established.'),
    ('MO', 'components', 'state', 'available',
     'March 2008 Preferred Series publishes births, deaths and net migration for previous five-year '
     'intervals ending 2005-2030. Published in the state age PDF, but not loaded; interval-aware '
     'ingestion is deferred.'),
    ('MO', 'components', 'county', 'available',
     'The official 2000-2030 catalog publishes county components over previous five-year intervals. '
     'Not loaded; complete county extraction and interval-aware ingestion are deferred.'),
    # ---- Batch five: selected editions and unresolved publication findings
    ('IA', 'population', 'state', 'available',
     'Selected archival July 1984 original state-demographer summary: 1980 Census history and exact '
     'five-year projections 1985/1990/1995/2000. Entire projected horizon is past; no later values or '
     'federal/commercial substitutes.'),
    ('IA', 'population', 'county', 'available',
     'Selected archival July 1984 original state-demographer summary, all 99 counties: 1980 Census '
     'history and exact five-year projections 1985/1990/1995/2000. Original displayed precision and '
     'independent state/county differences retained.'),
    ('WV', 'population', 'state', 'available',
     'October 2022 BBER edition: 2020 Census history, five-year July projections 2025-2040; published '
     'totals for state and all 55 counties. Last underlying estimate year unknown.'),
    ('WV', 'population', 'county', 'available',
     'October 2022 BBER edition: 2020 Census history, five-year July projections 2025-2040; published '
     'totals for state and all 55 counties. Last underlying estimate year unknown.'),
    # ---- Batch five: selected editions and unresolved publication findings
    ('AR', 'population', 'state', 'available',
     'Older February 2015 UALR/Arkansas SDC edition: state and all 75 counties, annual History '
     'estimates 1980–2013 and Point forecasts 2014–2065. Confidence limits and fitted values are '
     'deferred.'),
    ('AR', 'population', 'county', 'available',
     'Older February 2015 UALR/Arkansas SDC edition: state and all 75 counties, annual History '
     'estimates 1980–2013 and Point forecasts 2014–2065. Confidence limits and fitted values are '
     'deferred.'),
    ('LA', 'population', 'state', 'available',
     'Older 2009 state-commissioned LSU edition: state and all 64 parishes, 2005 July 1 estimates and '
     'five-year projections 2010–2030, three migration scenarios. Middle default is a consistent '
     'server scenario choice.'),
    ('LA', 'population', 'county', 'available',
     'Older 2009 state-commissioned LSU edition: state and all 64 parishes, 2005 July 1 estimates and '
     'five-year projections 2010–2030, three migration scenarios. Middle default is a consistent '
     'server scenario choice.'),
    # ---- Batch five: selected editions and unresolved publication findings
    ('OK', 'population', 'state', 'available',
     'March 2023 Commerce report: exact published five-year totals for 2025-2070, all projections. '
     'Last underlying estimate input is unstated; ambiguous historical cells are not loaded.'),
    ('OK', 'population', 'county', 'available',
     'March 2023 Commerce report: all 77 counties, published five-year totals for 2025-2070 in integer '
     'persons, all projections.'),
    ('VT', 'population', 'state', 'available',
     'Adopted March 10, 2025 VHFA/DHCD current-trends state population chart: 2030/2040/2050; 18 '
     'exhaustive age groups normalized to exact totals. Base year is unknown.'),
    ('VT', 'population', 'county', 'available',
     'Archived August 2013 ACCD product: all 14 counties, 2010 Census history and 2020/2030 '
     'projections, source scenarios A/B. Separate from the newer state product.'),
    ('VT', 'population', 'county_subdivision', 'pdf_only',
     'Archived August 2013 ACCD town, city, grant and gore projections, source scenarios A/B; not '
     'loaded pending a historical geography crosswalk.'),
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
