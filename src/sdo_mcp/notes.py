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
            "November 2025 State Components of April 1 Population Change, annual",
            "2022 GMA County Components of Population Change, medium five-year totals",
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
            "No household forecast is published. State components are annual "
            "April-to-April totals ending 2011-2050. County components are medium-only "
            "five-year totals ending 1965-2050, not annual values; year filters use "
            "the period end. County component estimates end in 2020; the period "
            "2020-2025 is labeled projection in its separate 2022 GMA workbook.",
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
    "PA": {
        "name": "Pennsylvania",
        "agency": "Pennsylvania State Data Center, Penn State Harrisburg, for the Center for Rural Pennsylvania",
        "producer_type": "university (state legislative agency contractor)",
        "current_vintage": "2023 edition: workbook prepared September 5, released October 4; methodology December 2023. July 2020 estimates and five-year projections 2025-2050.",
        "geography_floor": "county (67 counties + state) for loaded totals. Place projection publication status is unverified.",
        "scenarios": [],
        "default_scenario": None,
        "products": [
            "State and county population totals, 2020-2050 in five-year steps (loaded)",
            "Age/sex detail in the same workbook (archived but not served)",
            "Statewide five-year components of change in methodology Table 3 (PDF, not loaded)",
        ],
        "methodology": "Cohort-component projections start with July 1, 2020 estimates from Census Vintage 2022, applying fertility, survival and migration assumptions to five-year age/sex cohorts with separate group-quarters treatment.",
        "employment_note": "The reviewed PaSDC product is a demographic population projection. Eligible SDO employment coverage has not been established; labor-department occupational projections are not substituted.",
        "license": "No explicit data license identified in the reviewed products; cite the Pennsylvania State Data Center and Center for Rural Pennsylvania.",
        "caveats": [
            "The population base year is 2020; Census Vintage 2022 is the edition of those estimates, not their observation year.",
            "2020 rows are estimates and all 2025-2050 rows remain projections regardless of retrieval date. No annual points or years beyond 2050 are generated.",
            "Published county totals sum exactly to the state totals in this workbook. Original totals are served directly.",
            "Philadelphia is served as a county geography; its county series is not relabelled as a municipal forecast.",
            "The state components report contains five-year period totals, not annual values, and is not loaded. County components, place, household and eligible employment publication coverage remains unknown.",
        ],
        "links": {
            "agency": "https://pasdc.hbg.psu.edu/data/resources/pennsylvania-county-population-projections-2020-2050",
            "data": "https://www.rural.pa.gov/data/population-projections",
            "methodology": "https://www.rural.pa.gov/getfile.cfm?file=Resources%2Freports%2Fassets%2F260%2FPennsylvania+Population+Projections+for+the+Next+30+Years+Web.pdf",
            "release": "https://www.rural.pa.gov/getfile.cfm?file=Resources%2FPDFs%2FPennsylvania+Population+Projections+Press+Release.pdf",
        },
    },
    "MI": {
        "name": "Michigan",
        "agency": "Michigan Center for Data and Analytics (MCDA), State Demographer, Department of Technology, Management and Budget",
        "producer_type": "state agency",
        "current_vintage": "Vintage 2024: state release April 2024, county release March 2025. Loaded workbook supplies five-year population projections from 2025 through 2050.",
        "geography_floor": "county (83 counties + state) for loaded totals. Ten prosperity regions and age/sex detail are archived but not served. Place projection publication status is unverified.",
        "scenarios": ["net_positive_migration", "zero_migration"],
        "default_scenario": "net_positive_migration",
        "scenario_geo_levels": ["state"],
        "products": [
            "State and county population totals, 2025-2050 in five-year steps (loaded)",
            "Age/sex detail and ten prosperity-region totals in the same workbook (not served)",
            "Illustrative statewide zero-migration scenario and components in MCDA reports (not loaded)",
        ],
        "methodology": "MCDA cohort-component projections use changing fertility, survival and migration assumptions. County methods apply statewide trends to county-specific rates and migration patterns. The state report explicitly identifies the 2022 estimate base; county methodology does not explicitly name its population base year.",
        "employment_note": "MCDA also publishes labor-market industry/occupational projections. Those products are not substituted for an SDO demographic jobs forecast; eligible employment forecast coverage remains unverified.",
        "license": "No explicit data license identified in the reviewed products; cite Michigan Center for Data and Analytics.",
        "caveats": [
            "Every loaded point is a projection, including 2025. The workbook has no estimates or annual intermediate points; none are generated.",
            "State base_year is 2022. County base_year is NULL because the county methodology does not explicitly identify its population base; the state base is not borrowed.",
            "The main statewide net-positive-migration scenario is loaded. The illustrative zero-migration scenario returns not_loaded and does not apply to county requests.",
            "Fractional modeled totals retain the workbook's numeric precision. County sums differ from state totals by at most 0.03 persons; both are preserved.",
            "Prosperity regions are not Census metro areas or incorporated places and are not relabelled as those geographies.",
            "Place, household, eligible employment and complete components publication coverage has not been fully audited and remains coverage-unknown. Reports discuss components, but complete queryable series have not been established or loaded.",
        ],
        "links": {
            "agency": "https://www.michigan.gov/mcda/population",
            "data": "https://milmi.org/DataSearch/POPPROJ",
            "state_report": "https://www.michigan.gov/mcda/reports/michigan-statewide-population-projections-through-2050-report",
            "county_report": "https://www.michigan.gov/mcda/insights/2025/03/06/mich-county-popproj-2050",
            "county_methodology": "https://www.michigan.gov/-/media/Project/Websites/mcda/assets/Insight-Media-Files/Mi-County-Proj/Methodology---MiCtyPopProj.pdf?hash=396E088A6297591C3644528592AA07AA&rev=d93f987a0828444eade6640080b280e4",
        },
    },
    "IN": {
        "name": "Indiana",
        "agency": "Indiana Business Research Center, Kelley School of Business, Indiana University (STATS Indiana)",
        "producer_type": "university (official state population projections)",
        "current_vintage": "July 2024: 2020 estimates and five-year projections from 2025; state through 2060, counties through 2050.",
        "geography_floor": "county (92 counties + state). City/town projections are explicitly unavailable. Published metro/region aggregations are not loaded.",
        "scenarios": [],
        "default_scenario": None,
        "products": [
            "State and county population totals: 2020 estimates, five-year projections from 2025",
            "Age/sex detail and metro/region aggregations (published but not loaded)",
            "Separate IBRC labor-force projections (not employment, not loaded)",
        ],
        "methodology": "State: 2020 population anchor updated with estimates and components through 2023, followed by cohort-component projections. Counties: 2023 estimate base for 2025, then mixed projection methods and state controls. Both sources record 2023 as the last underlying estimate year, with separate horizons and methodology notes.",
        "employment_note": "IBRC labor-force projections count workers, not jobs. STATS Indiana also links IU's separate Center for Econometric Model Research economic forecasts; an eligible SDO jobs series has not been established here. Employment coverage remains unknown.",
        "license": "No explicit data license identified on the reviewed pages; cite IBRC and STATS Indiana.",
        "caveats": [
            "2020 is explicitly a Census Vintage 2022 estimate; 2025 remains a projection even when retrieved after that year.",
            "Both sources use base_year=2023 for the last underlying estimate year. The state model's population anchor is 2020, with estimates and components through 2023; the county model launches from 2023 estimates. The source table contains no 2023 observations.",
            "County sums exceed the published state projections by 55 to 130 people; the table does not explain the discrepancy. Original values are preserved.",
            "Only published five-year points are served. County forecasts stop at 2050; no annual interpolation or extension to the state horizon is performed.",
            "Household, employment, and components publication status remains coverage-unknown. Population tables alone do not establish their availability.",
        ],
        "links": {
            "agency": "https://www.stats.indiana.edu/topic/projections.asp",
            "data": "https://www.stats.indiana.edu/pop_proj/",
            "methodology": "https://www.stats.indiana.edu/about/pop-projections-2025-60.asp",
            "population_coverage": "https://www.stats.indiana.edu/topic/population.asp",
            "households": "https://www.stats.indiana.edu/topic/households.asp",
            "economic_forecasts": "https://www.stats.indiana.edu/topic/forecasts.asp",
            "labor_force": "https://www.stats.indiana.edu/topic/laus.asp",
        },
    },
    "VA": {
        "name": "Virginia",
        "agency": "University of Virginia Weldon Cooper Center for Public Service, Demographics Research Group",
        "producer_type": "university (Commonwealth contractor)",
        "current_vintage": "July 2025 Virginia Population Projections: 2030-2055, with 2024 estimate base.",
        "geography_floor": "county-equivalent locality (95 counties + 38 independent cities). Cooper also publishes a separate large-town product not loaded here.",
        "scenarios": [],
        "default_scenario": None,
        "products": [
            "Total population projections for Virginia and 133 county-equivalent localities, 2030-2055",
            "Age/sex and large-town projection workbooks (published by Cooper Center, not ingested in this pass)",
        ],
        "methodology": "Cooper Center's July 2025 methodology applies a uniform demographic/statistical projection process to all localities using 2024 estimates; the workbook provides direct and publisher-interpolated mid-decade outputs.",
        "employment_note": "The loaded Cooper source is a population product; an agency-wide SDO employment forecast was not verified in this review.",
        "license": "Public University of Virginia data; cite the Weldon Cooper Center.",
        "caveats": [
            "Virginia independent cities are county equivalents and remain separate FIPS geographies; Fairfax County and Fairfax city, and Roanoke County and Roanoke city, are distinct rows.",
            "The 2035/2045/2055 values are explicitly labelled interpolated in the source workbook and are loaded as publisher-provided outputs; this server does not generate additional years.",
            "Population totals are fractional model outputs and retain source numeric precision.",
            "Household, employment, and components publication status was not established by the population-product review and remains coverage-unknown.",
        ],
        "links": {
            "agency": "https://www.coopercenter.org/virginia-population-projections",
            "methodology": "https://www.coopercenter.org/sites/default/files/2025-07/VAPopProjMethodology_2025_FINAL_accessible_protected.docx",
        },
    },
    "WI": {
        "name": "Wisconsin",
        "agency": "Wisconsin Department of Administration, Division of Intergovernmental Relations, Demographic Services Center",
        "producer_type": "state agency",
        "current_vintage": "Population Vintage 2024 (December 2024); separate 2020-2050 household series with no edition date stated in the workbook.",
        "geography_floor": "county (72 counties + state) for loaded totals; minor-civil-division and municipal population/household projections are published but not ingested.",
        "scenarios": [],
        "default_scenario": None,
        "products": [
            "State and county population totals, 2020, 2030, 2040, 2050",
            "State and county household totals, 2020, 2030, 2040, 2050",
            "Minor civil division and municipal population/household projections (available from DOA, not loaded)",
        ],
        "methodology": "DOA uses a modified Hamilton-Perry cohort-change-ratio method for county age-sex projections, with state control totals; household projections are anchored to those population cohorts and age-specific household rates.",
        "employment_note": "The reviewed DOA population and household products do not include employment; an agency-wide SDO employment product was not separately verified.",
        "license": "Public Wisconsin state government statistics; cite the Department of Administration.",
        "caveats": [
            "2020 is the Census-based estimate; 2030-2050 are projections. Population county totals sum exactly to published state totals; household sums can differ by up to two from state values because of rounding.",
            "Only state and county totals are loaded; published subcounty products remain available but return not_loaded until separately ingested.",
            "The household workbook does not state an edition date; its source metadata is recorded as a 2020-2050 series. Employment and components publication status remains coverage-unknown.",
        ],
        "links": {
            "agency": "https://doa.wi.gov/Pages/LocalGovtsGrants/Population_Projections.aspx",
            "population_methodology": "https://doa.wi.gov/DIR/Method_Pop_Proj_2020_2050.pdf",
            "household_methodology": "https://doa.wi.gov/DIR/Method_HH_Proj_Co_2020-2050.pdf",
        },
    },
    "UT": {
        "name": "Utah",
        "agency": "Kem C. Gardner Policy Institute, University of Utah",
        "producer_type": "university policy institute (Utah Population Committee)",
        "current_vintage": "2025-2065 baseline projections (November 2025; current workbook has an August 2026 asset URL).",
        "geography_floor": "county (29 counties + state) for population, households, employment, and components. Gardner publishes a separate 2025 subcounty estimates product; no subcounty projections are loaded.",
        "scenarios": ["baseline", "high", "low"],
        "default_scenario": "baseline",
        "scenario_geo_levels": ["state", "county"],
        "products": [
            "Annual July 1 population, households, and components projections, 2025-2065",
            "Annual total employment projections for state and counties, 2025-2065",
            "High/Low scenario workbook and subcounty estimates are published separately but not loaded in this pass",
        ],
        "methodology": "Gardner's long-term planning baseline uses demographic and economic projection models; the official workbook publishes annual population, births, deaths, net migration, households, and total jobs. Employment includes wage-and-salary and self-employment under the BEA definition described in the methods report.",
        "employment_note": "The Gardner Policy Institute itself publishes total-jobs projections by state and county; labor-department occupational projections are not substituted.",
        "license": "Public University of Utah data; cite the Kem C. Gardner Policy Institute.",
        "caveats": [
            "All served points, including the 2025 launch row, are labelled projections. The workbook does not identify a last underlying estimate year, so source base_year is NULL rather than inferred.",
            "County totals differ from state rows by a few people/jobs because of independent rounding; published state and county values are retained without reconciliation.",
            "The separate scenario workbook publishes High/Low population, household, and employment totals for 2030-2065, which return not_loaded. It does not contain components; loaded components are baseline-only. Subcounty estimates are a separate product and do not establish forecast coverage.",
        ],
        "links": {
            "agency": "https://gardner.utah.edu/utah-demographics/population-projections/utah-2065-long-term-vintage-2025/",
            "workbook": "https://d36oiwf74r1rap.cloudfront.net/wp-content/uploads/2026/08/Gardner-Policy-Institute-State-and-County-Projections-2025-2065-Data.xlsx",
            "report": "https://d36oiwf74r1rap.cloudfront.net/wp-content/uploads/2026/03/ProjectionsSummary-Mar2026.pdf",
            "scenarios": "https://d36oiwf74r1rap.cloudfront.net/wp-content/uploads/2026/08/Gardner-Policy-Institute-State-and-County-Projection-Scenarios-2030-2065.xlsx",
        },
    },
}
