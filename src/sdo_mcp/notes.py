"""Hand-curated per-state metadata, from the verified findings in plan/RESEARCH.md
(all six pilot states verified 2026-08-07).

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
}
