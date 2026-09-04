"""Hand-curated per-state metadata, from the verified findings in plan/RESEARCH.md
(all six pilot states verified 2026-08-07) and plan/EXPANSION.md (expansion
states, verified 2026-08-10).

This is the prose side of the server: agency stories, product names, caveats,
links. The machine-readable availability matrix lives in the `coverage` table;
numbers live in `observations`. Nothing here is ever a substitute for data —
if it isn't in the store, the answer is "not published" or "not loaded".
"""

STATES = {
    "CO": {
        "name": "Colorado",
        "agency": "Colorado State Demography Office, Department of Local Affairs (DOLA)",
        "producer_type": "state agency",
        "current_vintage": (
            "2024 estimate cycle: estimates through 2024, forecasts from 2025 "
            "(population to 2060, households to 2050, jobs to 2050). "
            "Next annual cycle expected late October 2026."
        ),
        "geography_floor": (
            "county (64 counties + statewide). Municipal figures are estimates "
            "only — DOLA publishes no municipal forecast."
        ),
        "scenarios": [],
        "default_scenario": None,
        "products": [
            "Population estimates & forecasts with components of change "
            "(births/deaths/net migration), 1970–2060, annual",
            "Household forecasts by type, 2010–2050, annual",
            "Total jobs estimates & forecast, 2000–2050, annual "
            "(the SDO's own jobs series — distinct from CDLE occupational projections)",
        ],
        "methodology": (
            "Cohort-component model maintained by the State Demography Office; "
            "served through the live JSON API behind DOLA's lookup apps "
            "(gis.dola.colorado.gov/lookups), the only live API among the pilot "
            "states. Also mirrored on Socrata (data.colorado.gov, q5vp-adf3), "
            "which this project uses as an ingest-time cross-check."
        ),
        "employment_note": (
            "Colorado is the reference case for SDO employment: DOLA itself "
            "publishes a total-jobs forecast (county, to 2050). Occupational "
            "detail belongs to CDLE (labor department) and is out of scope."
        ),
        "license": "Public data, API openly served. Cite the State Demography Office.",
        "caveats": [
            "API errors arrive as HTTP 200 with a plain-text body; responses are "
            "validated by parsing, never by status code.",
            "The household endpoint carries no estimate/projection flag; the "
            "boundary year is borrowed from the population series (2024/2025).",
            "Jobs forecast horizon is 2050, not 2060 like population.",
        ],
        "links": {
            "agency": "https://demography.dola.colorado.gov/",
            "api_base": "https://gis.dola.colorado.gov/lookups/",
            "socrata_mirror": "https://data.colorado.gov/resource/q5vp-adf3",
        },
    },
    "TX": {
        "name": "Texas",
        "agency": "Texas Demographic Center (TDC), University of Texas at San Antonio",
        "producer_type": "university (home of the State Demographer)",
        "current_vintage": (
            "Population Projections Vintage 2024 (released 2025-09-30, ~biennial), "
            "annual 2020–2060, three migration scenarios."
        ),
        "geography_floor": (
            "county (254), plus MSAs, COGs, Comptroller regions, and TxDOT "
            "districts. MSA/COG/TxDOT totals are served at decade resolution "
            "(2020, 2030-2060); annual detail stays county-only. No place/city "
            "projections (places get estimates only)."
        ),
        "scenarios": ["mid", "high", "low"],
        "default_scenario": "mid",
        "products": [
            "Population projections 2020–2060, single year of age × sex × 5 "
            "race/ethnicity groups, Mid/High/Low migration scenarios",
        ],
        "methodology": (
            "Cohort-component, aligned to Census Vintage 2024 estimates. TDC "
            "recommends the Mid scenario."
        ),
        "employment_note": (
            "TDC publishes no employment forecast. Texas Workforce Commission "
            "occupational projections are a different product and out of scope."
        ),
        "license": (
            "No stated terms; public data. Downloads sit behind a registration "
            "survey (skippable); non-commercial use per project decision 2026-08-07."
        ),
        "caveats": [
            "Households: no current product — the last was a Vintage-2018 special "
            "(2010–2050), since withdrawn from the site.",
            "Only the current vintage stays online; publishing Vintage 2024 "
            "deleted the 2022 files. This server serves committed snapshots.",
            "Dead legacy URLs return HTTP 200 with the current HTML page.",
        ],
        "links": {
            "agency": "https://demographics.texas.gov/",
        },
    },
    "CA": {
        "name": "California",
        "agency": (
            "California Department of Finance — Demographic Research Unit (DRU; "
            "statutory state demographer) for population and households, sibling "
            "Economic Research Unit (ERU) for the county economic forecast"
        ),
        "producer_type": "state agency",
        "current_vintage": (
            "P-series Baseline 2024, Vintage 2026 (released 2026-03-13): "
            "population 2020–2070 annual. Households (P-4) still Vintage 2025, "
            "projections to 2040. LRCF county forecast Jan 2026, to 2055."
        ),
        "geography_floor": "county (58 counties + state). No sub-county projections.",
        "scenarios": [],
        "default_scenario": None,
        "products": [
            "P-series population projections 2020–2070 (state + county; single "
            "age × sex × 7 race groups in the P3 file)",
            "P-4 household projections to 2040 (county totals, Vintage 2025)",
            "LRCF — Long-Run County Level Forecasts (ERU + Caltrans): farm + "
            "total nonfarm jobs, households, income, to 2055",
            "PCC components of change",
        ],
        "methodology": (
            "Cohort-component person-level microsimulation (Stata), Lee-Carter "
            "mortality; foreign immigration assumption reduced to 2018–19 levels; "
            "group quarters held at 2020 Census."
        ),
        "employment_note": (
            "DOF's own ERU publishes a county jobs forecast (LRCF, farm + total "
            "nonfarm, to 2055) — in scope because it comes from the same "
            "department as the demographer. Industry/occupation detail is EDD "
            "(labor department), out of scope."
        ),
        "license": (
            "Standard California conditions of use; public data. Cite baseline + "
            "vintage as embedded in the files."
        ),
        "caveats": [
            "Stable filenames, mutable content: DOF overwrites files in place on "
            "vintage refresh — figures are tied to recorded retrieval dates.",
            "Mixed vintages across products: population Vintage 2026, households "
            "Vintage 2025, LRCF Jan 2026. LRCF also carries county household "
            "forecasts past P-4's horizon; the two products disagree and are "
            "labeled separately, never merged.",
            "Mixed reference dates: P-series July 1; P-4/E-5 January 1.",
        ],
        "links": {
            "agency": "https://dof.ca.gov/forecasting/demographics/",
        },
    },
    "TN": {
        "name": "Tennessee",
        "agency": (
            "Boyd Center for Business and Economic Research, University of "
            "Tennessee Knoxville — disseminated via the Tennessee State Data "
            "Center (no separate state-government demography office)"
        ),
        "producer_type": "university",
        "current_vintage": (
            "2022 vintage (released Aug 2024, ~2-year cadence): base July 1 2022 "
            "estimate, projections 2023–2070 annual."
        ),
        "geography_floor": (
            "county (95 counties + state). No place projections (municipal "
            "certified estimates only)."
        ),
        "scenarios": [],
        "default_scenario": None,
        "products": [
            "Population projections 2023–2070 (state + county; 18 five-year age "
            "groups, sex, 4 race/Hispanic groups — one dimension at a time, "
            "never crossed in the summary files)",
            "Crossed age × sex × race county detail 2022–2070 (same product, "
            "from the Boyd Center's own ArcGIS feature service; county only — "
            "no state-level crossed detail is published)",
        ],
        "methodology": "Cohort-component (Boyd Center).",
        "employment_note": (
            "Boyd's annual Economic Report to the Governor contains a state-level "
            "jobs forecast, but as a narrative PDF only — not a serveable "
            "dataset. Jobs4TN (labor department) is out of scope."
        ),
        "license": "CC0 public domain — the cleanest redistribution position of the six.",
        "caveats": [
            "No household projections at any geography.",
            "Crossed age×sex×race detail comes from the Boyd Center's ArcGIS "
            "service (the flat-file host tndata.utk.edu was down at ingest "
            "time). County only — no state-level crossed detail is published; "
            "state figures come from the state summary product.",
            "Archive filenames don't match vintages (TN_CoPopProj_2021.xlsx is "
            "the 2020 vintage).",
        ],
        "links": {
            "agency": "https://tnsdc.utk.edu/",
            "crossed_detail_service": (
                "https://services1.arcgis.com/HLC8bAygObK4fhPW/arcgis/rest/"
                "services/TN_CoPopProj_2022_alldata/FeatureServer/0"
            ),
        },
    },
    "GA": {
        "name": "Georgia",
        "agency": (
            "Governor's Office of Planning and Budget (OPB, publisher of record); "
            "produced since the 2024 vintage by the Applied Demography Program at "
            "UGA's Carl Vinson Institute of Government — cite both"
        ),
        "producer_type": "state agency + university producer",
        "current_vintage": (
            "2026 vintage (released 2026-07-21, annual cadence): 2026–2065 in "
            "single-year steps, base = Census Vintage 2025 estimates."
        ),
        "geography_floor": "county (159 counties + state). No sub-county.",
        "scenarios": [],
        "default_scenario": None,
        "products": [
            "Long-Term Population Projections 2026–2065 (total; 5-year age "
            "groups; sex; 4 collapsed race/ethnicity groups)",
        ],
        "methodology": (
            "Cohort-component with Gaussian Process Regression for rates; "
            "COVID-era (2020–21) mortality excluded from fitting."
        ),
        "employment_note": (
            "No employment product from the demography producer. Georgia DOL's "
            "Labor Market Explorer projections are a different product, out of scope."
        ),
        "license": (
            "No stated terms; public data, non-commercial use per project "
            "decision 2026-08-07."
        ),
        "caveats": [
            "No household projections — population only.",
            "County files carry names only, no FIPS (joined via the Census "
            "county list at ingest).",
            "Everything OPB publishes is projection — the base comes from Census "
            "vintages, there is no OPB estimates series.",
        ],
        "links": {
            "agency": "https://opb.georgia.gov/census-data/population-projections",
        },
    },
    "FL": {
        "name": "Florida",
        "agency": (
            "BEBR (Bureau of Economic and Business Research, University of "
            "Florida) produces county estimates and projections under continuous "
            "state contract; EDR (the legislature's Office of Economic and "
            "Demographic Research) convenes the conference that adopts the "
            "official state-level forecast, to which BEBR calibrates"
        ),
        "producer_type": "university + legislative office",
        "current_vintage": (
            "BEBR 2026 edition (Feb 2026): base April 1 2025 estimate, "
            "projections 2030–2050 in 5-year steps, Low/Medium/High scenarios."
        ),
        "geography_floor": (
            "county (67 counties + state). Cities get estimates only — no "
            "municipal forecast."
        ),
        "scenarios": ["low", "medium", "high"],
        "default_scenario": "medium",
        "products": [
            "County population projections 2030–2050, L/M/H scenarios (BEBR)",
            "Age×sex×race detail 2025–2050, medium scenario only",
            "State-level household forecast (FDEC conference packet, PDF)",
            "State-level jobs forecast (EDR long-run tables, PDF)",
        ],
        "methodology": (
            "BEBR county projections calibrated to the state forecast adopted by "
            "the Demographic Estimating Conference (s. 186.901 F.S. makes BEBR "
            "estimates official)."
        ),
        "employment_note": (
            "EDR publishes a state-level nonfarm jobs forecast (long-run tables, "
            "PDF, ~FY2036). No county employment forecast from BEBR/EDR — county "
            "level is FloridaCommerce (labor department), out of scope."
        ),
        "license": (
            "BEBR free tier; no license text published (permission email open, "
            "non-blocking). EDR side is Florida public records."
        ),
        "caveats": [
            "BEBR county Excel values are rounded to the nearest 100, so county "
            "sums don't equal the state total; EDR's PDF carries unrounded "
            "medium values.",
            "Vintage skew: the Feb 2026 county files calibrate to the Dec 2025 "
            "conference; the Jun 2026 conference revised the state forecast down.",
            "No FIPS anywhere in the files — names joined via the Census county "
            "list at ingest.",
            "EDR conference URLs are fixed filenames overwritten each conference.",
        ],
        "links": {
            "bebr": "https://bebr.ufl.edu/population/",
            "edr": "http://edr.state.fl.us/Content/population-demographics/",
        },
    },
    "NC": {
        "name": "North Carolina",
        "agency": (
            "North Carolina Office of State Budget and Management (OSBM), "
            "State Demographer's Office (Demographic and Economic Analysis Section)"
        ),
        "producer_type": "state agency",
        "current_vintage": (
            "Vintage 2025B (2025 released 2026-01-15; the 2025B errata updated "
            "Brunswick, Columbus, Jackson, Orange + the state row): estimates "
            "2010-2024, projections 2025-2060, annual, July 1."
        ),
        "geography_floor": (
            "county (100 counties + state). Municipal figures are certified "
            "estimates only — no municipal projections."
        ),
        "scenarios": [],
        "default_scenario": None,
        "products": [
            "County/State Population Projections 2010-2060 (total; sex x single "
            "year of age; sex x race x age groups; Hispanic origin x race x sex x "
            "5-year age groups — totals served in v1)",
        ],
        "methodology": (
            "Cohort-component, July 1 reference, derived from Vintage 2024 "
            "estimates (2020-rebased)."
        ),
        "employment_note": (
            "The State Demographer's Office publishes no employment forecast. NC "
            "Commerce (labor department) projections are a different product, "
            "out of scope."
        ),
        "license": "Public Domain (per the OSBM data catalog); nc.gov terms apply.",
        "caveats": [
            "Files are overwritten in place with no vintage in the filename — "
            "the same URLs served Vintage 2024 in Sept 2025 (Wayback-verified) "
            "and 2025B now. Figures are tied to the recorded retrieval date; "
            "the keyless Opendatasoft API serves as the live vintage-change probe.",
            "The state row carries a pseudo-FIPS 37000 in the CSV, not 37.",
            "No household forecast at any level; no components-of-change product.",
            "v1 serves totals only — the sex x single-age detail sits in the "
            "committed snapshot, not yet loaded.",
        ],
        "links": {
            "agency": "https://www.osbm.nc.gov/demog/population-projections",
            "api_base": "https://demography.osbm.nc.gov/api/explore/v2.1/catalog/datasets",
        },
    },
    "MN": {
        "name": "Minnesota",
        "agency": (
            "Minnesota State Demographic Center, Minnesota Department of "
            "Administration"
        ),
        "producer_type": "state agency",
        "current_vintage": (
            "May 2024 (corrected July 1, 2024): state population and components "
            "2024-2075; county population 2024-2055."
        ),
        "geography_floor": (
            "county (87 counties + state). City and township figures are estimates "
            "only; the State Demographic Center does not project them."
        ),
        "scenarios": [],
        "default_scenario": None,
        "products": [
            "Long-Term Population Projections for Minnesota (state and county "
            "totals; age by sex; statewide race; statewide components of change)",
        ],
        "methodology": (
            "Cohort-component projections based on Census Vintage 2022 estimates."
        ),
        "employment_note": (
            "The State Demographic Center publishes no employment forecast. "
            "Minnesota DEED labor projections are a different product and are "
            "outside this server's scope."
        ),
        "license": (
            "No separate license statement; public government data under the "
            "Minnesota Government Data Practices Act."
        ),
        "caveats": [
            "The 2024 launch year is a projection, not an estimate. The last "
            "underlying estimate year is 2022, and every served point is labeled "
            "projection.",
            "County detail stops at 2055; the state series continues to 2075.",
            "County totals are summed from the workbook's age-by-sex rows because "
            "there is no county totals sheet.",
            "No household or employment forecast is published.",
        ],
        "links": {
            "agency": "https://mn.gov/admin/demography/data-by-topic/population-data/our-projections/",
        },
    },
    "AZ": {
        "name": "Arizona",
        "agency": "Arizona Office of Economic Opportunity (OEO), State Demographer",
        "producer_type": "state agency",
        "current_vintage": (
            "2025 edition: annual July 1 population and components, 2025-2060, "
            "with Low/Medium/High scenarios."
        ),
        "geography_floor": (
            "county (15 counties + state). The available place product uses an "
            "older, 2022-consistent county vintage and is not mixed into this series."
        ),
        "scenarios": ["low", "medium", "high"],
        "default_scenario": "medium",
        "products": [
            "Arizona State and County Population Projections, 2025-2060 "
            "(population, components, age/sex, and race/origin)",
        ],
        "methodology": (
            "Cohort-component projections with separate low, medium, and high "
            "assumptions. The 2025 launch population equals OEO's official estimate."
        ),
        "employment_note": (
            "OEO's industry and occupation projections are its labor-market product, "
            "not a State Demographer jobs forecast, and are outside this server's scope."
        ),
        "license": (
            "No separate license statement; official public statistics under az.gov terms."
        ),
        "caveats": [
            "The download site uses a browser challenge. Saved source files are "
            "validated as workbooks; an HTML challenge page is never accepted as data.",
            "Old vintages are removed from the site, so the committed snapshot and "
            "retrieval date are the reproducibility record.",
            "Detailed workbooks contain fractional modeled values. Totals and "
            "components are served as whole persons; the separately rounded-to-100 "
            "summary sheet is not used.",
            "Yuma County has one small published scenario crossover in 2026: "
            "Low is 61 people above Medium. The expected Low-Medium-High order "
            "holds from 2027 onward.",
            "No household forecast is published.",
        ],
        "links": {
            "agency": "https://oeo.az.gov/population/projections",
        },
    },
    "WA": {
        "name": "Washington",
        "agency": (
            "Washington State Office of Financial Management, Forecasting and "
            "Research Division"
        ),
        "producer_type": "state agency",
        "current_vintage": (
            "November 2025 state forecast (estimates through 2025, projections "
            "2026-2050) and separate 2022 GMA county Low/Medium/High projections."
        ),
        "geography_floor": (
            "county (39 counties + state). OFM publishes city and town estimates "
            "but does not develop sub-county projections."
        ),
        "scenarios": ["low", "medium", "high"],
        "default_scenario": "medium",
        "scenario_geo_levels": ["county"],
        "products": [
            "Forecast of the State Population by Age and Sex, November 2025",
            "2022 Growth Management Act County Population Projections, "
            "Low/Medium/High",
            "Long-Term Economic Forecast, state nonfarm employment (PDF only)",
        ],
        "methodology": (
            "OFM publishes separate statewide and GMA county projection products. "
            "The GMA range is required by state growth-management law."
        ),
        "employment_note": (
            "The same OFM division publishes a state-level Long-Term Economic "
            "Forecast with nonfarm jobs through 2050, but only in PDF tables. "
            "No county jobs forecast is published by OFM."
        ),
        "license": (
            "OFM permits use, sharing, and copying with attribution; its liability "
            "disclaimer applies."
        ),
        "caveats": [
            "The statewide and county series are different products and vintages. "
            "Their statewide 2050 comparison values disagree by construction, so "
            "they are never merged.",
            "Low/Medium/High scenarios apply only to counties. The current state "
            "forecast is a single series.",
            "The GMA county series has estimates for 2020-2022, no values for "
            "2023-2024, and projections for 2025-2050. Missing years are not filled.",
            "No household forecast is published. Components exist in separate "
            "workbooks that are not in the current committed snapshots.",
        ],
        "links": {
            "agency": "https://ofm.wa.gov/washington-data-research/population-demographics/",
        },
    },
    "OR": {
        "name": "Oregon",
        "agency": (
            "Portland State University Population Research Center, Oregon "
            "Population Forecast Program"
        ),
        "producer_type": "university (official state population research center)",
        "current_vintage": (
            "Latest county-specific regional releases as of 2026-09-04: 10 counties "
            "from 2023, 8 from 2024, 6 from 2025, and 11 from 2026."
        ),
        "geography_floor": (
            "county (35 counties; Multnomah is handled by Metro). No official "
            "statewide OPFP forecast. The source workbooks also include urban growth "
            "boundaries, which are not incorporated places and are not served here."
        ),
        "scenarios": [],
        "default_scenario": None,
        "products": [
            "Oregon Population Forecast Program rolling regional county forecasts, "
            "2023-2026 releases with horizons from 2073 through 2076",
        ],
        "methodology": (
            "County cohort-component forecasts from PSU PRC. The 2025 and 2026 "
            "workbooks label estimate and forecast rows. The 2023 and 2024 total "
            "tables are forecast-only; their methods documents identify the base years."
        ),
        "employment_note": "PSU PRC publishes no employment forecast.",
        "license": (
            "Archived forecast reports are CC BY 4.0; live workbooks carry no "
            "separate license statement."
        ),
        "caveats": [
            "No statewide official OPFP forecast exists. The OHNA statewide pilot "
            "explicitly says it does not replace OPFP and is not served.",
            "Multnomah County is outside PSU PRC's county series because Metro "
            "handles its forecasting; requests receive an explicit refusal.",
            "Oregon is a rolling-vintage dataset, not a single statewide snapshot. "
            "County release years, base years, and horizons differ, so county values "
            "must not be summed as though they came from one common vintage.",
            "The 2023 and 2024 county tables contain only forecast years. Their "
            "unpublished base-year values are not filled from another source.",
            "Workbook model results are stored with decimals and served as the "
            "nearest whole person, matching PSU's displayed tables.",
            "No household, employment, or components forecast is served.",
        ],
        "geo_exceptions": {
            ("population", "county", "41051"): {
                "status": "not_published",
                "reason": (
                    "Multnomah County is outside PSU PRC's county forecast series "
                    "because Metro handles forecasting for the county. "
                    "No value is substituted from another source."
                ),
            },
        },
        "links": {
            "agency": "https://www.pdx.edu/population-research/population-forecasts",
        },
    },
}
