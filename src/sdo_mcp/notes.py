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
    "IL": {
        "name": "Illinois",
        "agency": "Illinois Department of Public Health, Office of Policy, Planning and Statistics, Division of Health Data and Policy",
        "producer_type": "state agency (official demographic projections for the Certificate of Need program)",
        "current_vintage": "2023 edition, released May 2024: July 2020 estimates and July 2025, 2030, 2035 projections. Selected from the current IDPH catalog on September 29, 2026.",
        "geography_floor": "county (102 counties + state) for loaded totals. Chicago is separately published in Table 2 but not loaded; other cities are unverified.",
        "scenarios": [],
        "default_scenario": None,
        "products": [
            "State and county population totals, Table 3, printed pages 8-10 (loaded)",
            "Chicago population, Table 2, and state/county age/sex detail (archived but not served)",
            "Births, deaths and net migration, Tables A-2/A-4/A-5, five-year periods 2020-2025, 2025-2030, 2030-2035 (PDF, not loaded)",
        ],
        "methodology": "State totals use linear regression; county age/sex cohort-component projections are controlled to state totals by sex. The population base is July 1, 2020 Census estimates derived from the April 1 Census. IDPH prepared this product for the Illinois Health Facilities and Services Review Board's Certificate of Need program.",
        "employment_note": "Eligible IDPH jobs forecast coverage remains unverified. IDES occupational and industry projections are a separate labor-market product and are not substituted.",
        "license": "No explicit data license identified in the reviewed products; cite the Illinois Department of Public Health.",
        "caveats": [
            "2023 is the edition; May 2024 is the release date; 2020 is the estimate base. Retrieval dates do not change those labels.",
            "Only July 1 values are served. The separate April 1, 2020 Census column is archived but excluded because the series supports one point per year.",
            "Table 3 state totals are 11 higher in 2025 and 3 higher in 2030 than Table 1. Table 3 is selected consistently for state and county totals; its county sums equal its published state row exactly. No values are adjusted.",
            "All 2025-2035 points remain projections regardless of retrieval date. No annual interpolation or years beyond 2035 are generated.",
            "Source DeWitt maps to Census De Witt County (17039). Chicago is a distinct place, not Cook County; its published series is not loaded.",
            "Components are five-year period totals, not annual values, and are not loaded. Household and eligible jobs publication coverage remains unknown; the product survey is not a completed source review.",
        ],
        "links": {
            "agency": "https://dph.illinois.gov/data-statistics/vital-statistics/illinois-population-data.html",
            "data": "https://dph.illinois.gov/data-statistics/public-data-assets/illinois-population-projections.html",
            "methodology": "https://dph.illinois.gov/content/dam/soi/en/web/idph/publications/idph/data-and-statistics/vital-statistics/illinois-population-data/population-projections_202035.pdf",
            "excluded_labor_projections": "https://ides.illinois.gov/resources/labor-market-information/employment-projections",
        },
    },
    "MD": {
        "name": "Maryland",
        "agency": "Maryland Department of Planning, State Data and Analysis Center",
        "producer_type": "state agency",
        "current_vintage": "Population and households: November 2025, through 2055. Total jobs: preliminary October 2022, through 2050. Each loaded table has 2020 history and five-year projections from 2025.",
        "geography_floor": "county equivalents: 23 counties and Baltimore City, plus the state. Regional totals are archived but not served. Municipal publication coverage remains unverified.",
        "scenarios": [],
        "default_scenario": None,
        "products": [
            "State and county total population and households, 2020-2055 (loaded)",
            "State and county preliminary total jobs by place of work, 2020-2050 (loaded)",
            "Six regional totals and earlier history (archived but not served)",
            "Separate population age/sex/race, household population, household size, labor-force and industry products (not loaded)",
        ],
        "methodology": "MDP describes five-year cohort-component population projections aggregated from its 24 jurisdictions. Baltimore and Washington region population/household totals incorporate BMC and MWCOG cooperative forecasts. Household counts are read directly from the separate household workbook. Historical jobs are BEA CA25/CA25N totals; job projections are prepared by MDP.",
        "employment_note": "MDP's own preliminary October 2022 total jobs by place of work product is loaded. It has an independent edition and horizon and is not labor force, employed residents, or labor-department occupational projections.",
        "license": "No explicit data license identified; cite the Maryland Department of Planning.",
        "caveats": [
            "Population/household workbooks and their preparation footnotes say November 2025, although the catalog says October 2025. Workbook dates are authoritative for the loaded edition.",
            "base_year=2020 records the last historical point in each table: Census population/household counts or BEA historical jobs. The population method spans 2020-2055 but does not date the latest auxiliary rate inputs.",
            "Census 2020 counts use the MCP estimate label. All 2025 and later points remain projections regardless of retrieval date. No annual interpolation or extension beyond each product's horizon is performed.",
            "Population and household projections are rounded by the publisher to the nearest 10. All three products' county totals sum exactly to their respective state totals; published values are retained.",
            "Baltimore City (24510) is an independent county equivalent, distinct from Baltimore County (24005). Request it with geo_level=county; no county total is substituted for a place query.",
            "Regional totals are not Census metro areas. Municipal and projected components coverage remains unknown; use of components in a model does not establish a published components series. This product check is not a completed statewide source review.",
        ],
        "links": {
            "agency": "https://planning.maryland.gov/MSDC/Pages/s3_projection.aspx",
            "population": "https://planning.maryland.gov/MSDC/Documents/popproj/TotalPopProj.xlsx",
            "households": "https://planning.maryland.gov/MSDC/Documents/popproj/HouseholdProj.xlsx",
            "employment": "https://planning.maryland.gov/MSDC/Documents/projection/Jobs/Summary_TotalJobs.xlsx",
            "methodology": "https://planning.maryland.gov/MSDC/Documents/popproj/PopProjMethod-text.pdf",
        },
    },
    "DE": {
        "name": "Delaware",
        "agency": "Delaware Population Consortium, Office of State Planning Coordination",
        "producer_type": "state planning consortium",
        "current_vintage": "October 14, 2024 edition, readopted December 11, 2025 instead of a new 2025 edition; five-year projections through 2050.",
        "geography_floor": "All three counties and the state are loaded. DPC also publishes municipal projections in a separate product; they are not loaded.",
        "scenarios": [],
        "default_scenario": None,
        "products": [
            "Resident population and household-count summaries, 2020-2050 (loaded)",
            "Jobs by place of work, 2020-2050 (loaded)",
            "Municipal population, seasonal population, and age/race/sex detail (published separately, not loaded)",
        ],
        "methodology": "DPC's cohort model links population and jobs through migration and labor-force assumptions. The loaded report summary is published at five-year points. The latest historical point in those tables is 2020; 2025-2050 are projections. The December 2025 vote readopted the October 2024 edition.",
        "employment_note": "The DPC publishes its own jobs-by-place-of-work series. This is distinct from employed residents, labor force, and labor-department occupational forecasts.",
        "license": "No explicit data license identified; cite the Delaware Population Consortium.",
        "caveats": [
            "base_year=2020 is the last historical point in the loaded five-year summary tables. Later data inputs may inform the model, but the report does not provide a later estimate in these tables.",
            "All three counties sum exactly to the published state row for population, households, and jobs at every published point. No interpolation is performed.",
            "The municipal and seasonal products make different assumptions; neither is substituted for resident state/county population. Only the report's jobs-by-place-of-work row is loaded as employment.",
            "No completed statewide source review date is recorded.",
        ],
        "links": {
            "agency": "https://stateplanning.delaware.gov/demography/dpc.shtml",
            "catalog": "https://stateplanning.delaware.gov/demography/dpc-projection-data.shtml",
            "edition": "https://stateplanning.delaware.gov/demography/dpc-projection-info.shtml",
            "workbook": "https://stateplanning.delaware.gov/demography/documents/dpc/DPC-2024v0-report.xls",
        },
    },
    "NM": {
        "name": "New Mexico",
        "agency": "University of New Mexico Geospatial and Population Studies",
        "producer_type": "university population program used by state agencies",
        "current_vintage": "Spring 2024, cited as NM Population Projections 2023-2050; selected totals are published for 2020 and 2025-2050.",
        "geography_floor": "All 33 counties and the publisher's separate state total are loaded. The selected county workbook has no subcounty projections.",
        "scenarios": [],
        "default_scenario": None,
        "products": [
            "State and 33-county population totals, 2020 Census and 2025-2050 projections (loaded)",
            "County age/sex detail and long-format state age/sex data (published separately, not loaded)",
        ],
        "methodology": "UNM-GPS uses a cohort-component state model launched from its 2022 population estimates. Counties use a composite small-area method and are controlled to the state. The published county and state totals are separately rounded.",
        "employment_note": "An eligible UNM-GPS jobs forecast was not established during this population-source check; labor-department projections are not substituted.",
        "license": "No explicit data license identified; cite UNM Geospatial and Population Studies.",
        "caveats": [
            "base_year=2022 identifies the last estimate input stated in the Spring 2024 method; no 2022 observation appears in the selected totals workbook. Its 2020 Census history is labelled estimate and 2025-2050 rows are labelled projection.",
            "County sums differ from the published state row by at most five people due to rounding. The state value comes from the workbook, not a county sum.",
            "The publisher PDF confirms the workbook's Santa Fe 2030 value of 164,745. The HTML table shows 164,754, so its numeric table is not loaded.",
            "No annual values are inferred between the published five-year points. Household, components, subcounty and eligible jobs coverage remains unverified, and no completed statewide review is recorded.",
        ],
        "links": {
            "agency": "https://gps.unm.edu/",
            "catalog": "https://gps.unm.edu/pop/population-projections.html",
            "workbook": "https://gps.unm.edu/assets/documents/census/new-mexico-county-projections-total-and-by-agesex-xlsx.xlsx",
            "publisher_pdf": "https://gps.unm.edu/assets/documents/census/nmcountyprojections_v2024.pdf",
            "methodology": "https://gps.unm.edu/assets/documents/census/2024-gps-projections-methodology.pdf",
        },
    },
    "SC": {
        "name": "South Carolina",
        "agency": "South Carolina Revenue and Fiscal Affairs Office",
        "producer_type": "state agency and Census State Data Center",
        "current_vintage": "Vintage 2023, with 2023 estimates and annual population projections for 2024-2043.",
        "geography_floor": "All 46 counties plus the separately published state total are loaded.",
        "scenarios": [],
        "default_scenario": None,
        "products": [
            "State and county total population, 2023-2043 (loaded)",
            "Five-year age-group and sex detail, 2024-2043 (archived but not served)",
            "Natural change and net migration from the totals workbook (published, not served as MCP components)",
        ],
        "methodology": "RFA's workbook identifies a 2019-2023 population base period using Vintage 2023 postcensal estimates for 2020-2023. The selected 2023 row is an estimate; 2024-2043 are annual projections. All displayed population totals match rounded all-ages rows from the separate age-group workbook.",
        "employment_note": "An RFA employment forecast was not established during this population-source check; labor-department occupational projections are not substituted.",
        "license": "No explicit data license identified; cite the South Carolina RFA.",
        "caveats": [
            "The source files are stored under a 2026-08 URL, but their titles and workbook contents identify Vintage 2023. The URL directory is not treated as a new model edition.",
            "Publisher county and state totals can differ by up to five people because of rounding. Published values are retained without adjustment.",
            "The totals workbook has natural-change and net-migration columns, but no separately verified births/deaths totals for the MCP components tool. Components publication and interval semantics need a separate audit before loading.",
            "Household, place, and eligible jobs publication coverage remains unverified; no completed statewide review is recorded.",
        ],
        "links": {
            "agency": "https://www.rfa.sc.gov/",
            "overview": "https://www.rfa.sc.gov/programs/census-state-liaison-and-data-center/population-projections",
            "catalog": "https://www.rfa.sc.gov/programs/census-state-liaison-and-data-center/search-and-download-population-data/rfa-population-projections",
            "totals": "https://www.rfa.sc.gov/sites/rfa/files/2026-08/Vintage%202023%20RFA%20Population%20Projections%20-%20Total%20Population%2C%20Population%20Change%2C%20and%20Components%20of%20Change%20by%20Sex%20and%20County%202024-2043.xlsx",
        },
    },
    "AL": {
        "name": "Alabama",
        "agency": "University of Alabama Center for Business and Economic Research, Alabama State Data Center",
        "producer_type": "university center serving as the state data center",
        "current_vintage": "2025 estimate base with projections to 2050 in a Box file labelled ReleasedFall2026; workbook modified September 24, 2026.",
        "geography_floor": "All 67 counties plus the workbook's explicit state row are loaded.",
        "scenarios": [],
        "default_scenario": None,
        "products": [
            "State and county population, 2025 estimates and 2030-2050 five-year projections (loaded)",
            "Earlier 1990-2024 Census/estimate history and percentage-change formulas (archived but not served)",
        ],
        "methodology": "CBER, the Alabama State Data Center lead agency, describes a cohort-component model for state and county projections. The selected workbook stores fractional projected model values but displays whole-person counts; served values use the workbook's displayed rounding.",
        "employment_note": "An eligible CBER demography-office jobs forecast has not been established. CBER's economic outlooks and labor-market products are not substituted for this population series.",
        "license": "No explicit data license identified; cite the University of Alabama CBER.",
        "caveats": [
            "The Box filename labels the file ReleasedFall2026 and workbook metadata was modified September 24, 2026. Its bottom source line still says October 2024, so the exact formal release date is uncertain; the 2025 estimate base and file identity are recorded separately.",
            "The 2025 estimates remain estimates. All 2030-2050 points remain projections even though the download was retrieved in 2026.",
            "The workbook's raw county values add to the state row. Rounding each displayed county value can leave a difference of up to three people from the displayed state total; the published state row is not replaced by a computed sum.",
            "CBER's catalog links an original county workbook; no separate health-planning agency short-term projections are loaded. Household, place, components and eligible jobs publication coverage remains unverified, and no completed statewide review is recorded.",
        ],
        "links": {
            "agency": "https://cber.culverhouse.ua.edu/",
            "catalog": "https://cber.culverhouse.ua.edu/resources/alabama-demographics/",
            "workbook": "https://alabama.box.com/s/991v89cfqpkukoa2o7c6eh2wr57elo1t",
            "estimate_context": "https://cber.culverhouse.ua.edu/2026/04/24/migration-is-the-primary-driver-of-alabamas-uneven-growth-findings-from-u-s-census-vintage-2020-2025-estimates/",
        },
    },
    "WY": {
        "name": "Wyoming",
        "agency": "Wyoming Department of Administration & Information, Economic Analysis Division",
        "producer_type": "state agency",
        "current_vintage": "February 2025 edition: 2020 Census history, 2021-2023 estimates, and annual forecasts for 2024-2050.",
        "geography_floor": "The state and all 23 counties are loaded. Municipal forecasts are published and archived but not served.",
        "scenarios": [],
        "default_scenario": None,
        "products": [
            "State and county population, 2020-2050 (loaded)",
            "Cities and towns, 2020-2050 (published and archived but not served)",
        ],
        "methodology": "The February 2025 source says EAD forecast state and county population from demographic and economic trends. It calculates municipal forecasts by applying place/county ratios to the appropriate county forecasts. The workbook and separate PDF agree at every state and county point.",
        "employment_note": "An eligible EAD jobs forecast was not established during this population-source check. Labor-department occupational projections are not substituted.",
        "license": "No explicit data license identified; cite the Wyoming Economic Analysis Division.",
        "caveats": [
            "The 2020 Census counts use the MCP estimate label, as do 2021-2023 Census Bureau estimates. All 2024-2050 values remain projections regardless of retrieval date; base_year=2023 identifies the last estimate year.",
            "Johnson, Laramie, and Lincoln appear as 'Cnty' in the workbook and are matched to their Census county FIPS identifiers. All 23 county totals add exactly to the separately published state row in every year.",
            "Municipal forecasts are published, but the current place geography and identifier support has not been checked for these rows. They are not substituted with county values. Household, components, and eligible jobs publication coverage requires further review; no completed statewide review date is recorded.",
        ],
        "links": {
            "agency": "https://ai.wyo.gov/divisions/economic-analysis",
            "catalog": "https://ai.wyo.gov/divisions/economic-analysis/demographic-information/projections",
            "workbook": "https://docs.google.com/spreadsheets/d/19ooDLwh4bIXnGUcaVr95CQ_cCXvypcFa/edit",
            "pdf": "https://drive.google.com/file/d/1w7y6YRfgZ3k9voPjqw0dlJkUiwwiYlEd/view",
        },
    },
    "KY": {
        "name": "Kentucky",
        "agency": "Kentucky State Data Center, University of Louisville",
        "producer_type": "university (state data center)",
        "current_vintage": "Vintage 2022, released August 2022: 2020 historical totals and five-year population and household projections from 2025 through 2050.",
        "geography_floor": "county (120 counties + state). Area Development District projections are archived but not served; this edition has no city/place projections.",
        "scenarios": [],
        "default_scenario": None,
        "products": [
            "State and county population totals aggregated from published age/sex rows, 2020-2050 (loaded)",
            "State and county household totals, 2020-2050 (loaded)",
            "Age/sex, household-population, group-quarters and Area Development District detail (archived but not served)",
            "Separate race/ethnicity projections for the state and Area Development Districts (not loaded)",
        ],
        "methodology": "County cohort-component population projections are aggregated to the state. The report uses a 2020 Census anchor; the catalog also names 2021 Population Estimates as inputs. Households use 2020 ACS headship rates calibrated to 2020 Census household counts and applied to projected household population.",
        "employment_note": "The reviewed KSDC edition covers population and households. Eligible SDO employment forecast coverage remains unverified; labor-department occupational projections are not substituted.",
        "license": "No explicit data license identified; cite the Kentucky State Data Center.",
        "caveats": [
            "base_year=2021 records the last underlying population estimate input named by the catalog for this edition, including the population inputs to household projections. The model and household-count anchor is 2020. No 2021 observations are published in these workbooks.",
            "The historical 2020 Census-based totals use the MCP estimate label; all 2025-2050 rows remain projections regardless of retrieval date. No annual points or years beyond 2050 are generated.",
            "Population totals sum the 36 published sex/age categories per geography. Household totals come directly from the separate workbook, not its population-in-households columns. Both county series sum exactly to their state totals.",
            "Population county codes contain five digits; household codes contain only the three-digit county part. Both resolve to Census county geographies. Jefferson and Fayette counties are not relabelled as municipal forecasts.",
            "The 15 Area Development Districts are not Census metro areas and are not relabelled as places or metros. The historical 2010 columns are archived but not served.",
            "The report uses demographic rates from before COVID-19. Employment and projected components publication coverage has not been fully audited and remains coverage-unknown; historical components are not forecast components.",
        ],
        "links": {
            "agency": "https://centers.louisville.edu/kentucky-state-data-center",
            "data": "https://centers.louisville.edu/kentucky-state-data-center/data-downloads",
            "methodology": "https://louisville.widen.net/s/qlgpqnkcdd/projection-report-2022",
            "population": "https://louisville.widen.net/s/rzn2jnhjph/population-projections-by-sex-and-five-year-age-group",
            "households": "https://louisville.widen.net/s/hbwbqlghqh/household-projections",
            "codebook": "https://louisville.widen.net/s/qmpwfcwwzr/population-projections-by-sex-and-five-year-age-group",
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
    "AK": {
        "name": "Alaska",
        "agency": "Alaska Department of Labor and Workforce Development, Research and Analysis Section",
        "producer_type": "state agency",
        "current_vintage": "September 2026 edition: 2025 July 1 estimate base; state annual 2025–2055, county five-year 2025–2055.",
        "geography_floor": "All 30 current borough/census-area county equivalents plus state. Economic regions and Alaska Native detail are published but not loaded.",
        "scenarios": [
            "mid",
            "low",
            "high",
        ],
        "default_scenario": "mid",
        "scenario_geo_levels": [
            "state",
        ],
        "products": [
            "Resident population: statewide annual Low/Middle/High scenarios 2025–2055; borough/census-area single series at five-year points.",
            "State annual and county five-year components and age/sex detail, published but not loaded.",
        ],
        "methodology": "Cohort-component model with fertility, mortality and migration assumptions. July 1, 2025 is the estimate base. State Middle is served as mid. Publisher fits county totals to statewide Middle; no fitting occurs in this server. Every loaded total agrees with PDF Tables 1.4 and 3.1.",
        "employment_note": "No eligible demographer jobs product was established. Catalog-linked industry and occupational forecasts are a separate QCEW/staffing-pattern labor-market product and are not substituted; employment coverage remains unknown.",
        "license": "No explicit data license identified; cite Alaska Research and Analysis.",
        "caveats": [
            "County totals are five-year points and a single series; state scenarios do not imply county Low/High forecasts.",
            "Chugach 02063 and Copper River 02066 are current separate census areas already in the 2020 Census geography list; former Valdez-Cordova is not substituted.",
            "Regional, Alaska Native, age/sex and components detail is published but not loaded.",
            "Household and place projection publication status remains unknown.",
        ],
        "links": {
            "agency": "https://live.laborstats.alaska.gov/article/alaska-population-projections",
            "report": "https://live.laborstats.alaska.gov/pop/projections/pub/popproj.pdf",
            "state_workbook": "https://live.laborstats.alaska.gov/sites/default/files/2026-09/StateProjections.xlsx",
            "county_workbook": "https://live.laborstats.alaska.gov/sites/default/files/2026-09/Boroughs%20and%20Census%20Areas.xlsx",
            "geography": "https://tigerweb.geo.census.gov/tigerwebmain/Files/acs26/tigerweb_acs26_county_2020_tab20_ak.html",
        },
    },
    "HI": {
        "name": "Hawaii",
        "agency": "Hawaii Department of Business, Economic Development and Tourism, Research and Economic Analysis Division",
        "producer_type": "state agency",
        "current_vintage": "DBEDT 2050 Series, April 2024: resident population 2020/2030/2040/2050; civilian total jobs 2022/2030/2040/2050.",
        "geography_floor": "State and four modeled county groups: Hawaii, Honolulu, Kauai, and combined Maui/Kalawao. Combined county ID hi-maui-kalawao is distinct from individual Census Maui 15009 and Kalawao 15005.",
        "scenarios": [],
        "default_scenario": None,
        "products": [
            "Resident population, July 1 2020 estimates and 2030/2040/2050 projections.",
            "Civilian total jobs, 2022 estimates and 2030/2040/2050 projections, wage/salary plus proprietors, military excluded.",
            "Separate de facto population, age/sex, labor-force and sector economics archived but not served.",
        ],
        "methodology": "Resident population uses a cohort-component model explicitly launched in 2020. Census Vintage 2022 is the estimate edition, not the population base year. The inter-industry Hawaii Economic Projection and Simulation Model supplies jobs with BEA 2022 base data and productivity assumptions. Original XLSX cached model precision is preserved.",
        "employment_note": "DBEDT itself publishes eligible civilian total jobs for state/four county groups, including proprietors and excluding military. Jobs differ from employed residents and labor force. Appendix totals are rounded to tens; the 2022 county sum differs by ten from the independently published state.",
        "license": "No explicit data license identified; cite Hawaii DBEDT Research and Economic Analysis.",
        "caveats": [
            "Maui includes Kalawao in the source. Request hi-maui-kalawao for the combined series; no isolated Maui/Kalawao forecast is substituted.",
            "Resident population includes military/dependents and excludes visitors. Separate de facto population is not used as resident population.",
            "Only exact published decade points are loaded; no annual interpolation.",
            "Population workbook retains model decimals. Combined Maui/Kalawao 2030 is 173620.30660481827 in XLSX A-6/A-19 but 173520 in companion PDF/Data Book; XLSX is the numeric authority and the discrepancy is preserved.",
            "Population model base is 2020; jobs base is 2022. Census Vintage 2022 identifies the population estimate edition.",
            "State components are period-average annual quantities in a report table and are not loaded. Household and subcounty publication coverage remains unknown.",
        ],
        "links": {
            "agency": "https://dbedt.hawaii.gov/economic/economic-forecast/long-range-projections/",
            "workbook": "https://files.hawaii.gov/dbedt/economic/data_reports/LRF/2050-long-range-projections-appendices.xlsx",
            "report": "https://files.hawaii.gov/dbedt/economic/data_reports/LRF/2050-long-range-projections.pdf",
            "population_geography": "https://files.hawaii.gov/dbedt/economic/databook/2024-individual/01/012324.pdf",
            "jobs_geography": "https://www.bea.gov/sites/default/files/methodologies/BEA-Local-Area-Personal-Income-and-Employment-Concepts-and-Methods.pdf",
        },
        "geo_exceptions": {
            ("population", "county", "15005"): {
                "status": "not_published",
                "reason": "DBEDT publishes Maui and Kalawao only as one combined county group. An isolated county forecast is not published in this series. Request county ID hi-maui-kalawao for the combined series; its value is not substituted for either individual county.",
            },
            ("population", "county", "15009"): {
                "status": "not_published",
                "reason": "DBEDT publishes Maui and Kalawao only as one combined county group. An isolated county forecast is not published in this series. Request county ID hi-maui-kalawao for the combined series; its value is not substituted for either individual county.",
            },
            ("employment", "county", "15005"): {
                "status": "not_published",
                "reason": "DBEDT publishes Maui and Kalawao only as one combined county group. An isolated county forecast is not published in this series. Request county ID hi-maui-kalawao for the combined series; its value is not substituted for either individual county.",
            },
            ("employment", "county", "15009"): {
                "status": "not_published",
                "reason": "DBEDT publishes Maui and Kalawao only as one combined county group. An isolated county forecast is not published in this series. Request county ID hi-maui-kalawao for the combined series; its value is not substituted for either individual county.",
            },
        },
    },
    "ME": {
        "name": "Maine",
        "agency": "Maine Department of Administrative and Financial Services, Office of the State Economist",
        "producer_type": "state agency",
        "current_vintage": "April 2025 edition, replacing June 2023: 2022 estimate base and exact population projection points 2027, 2032, 2037 and 2042.",
        "geography_floor": "The state and all 16 counties are loaded. City/town projections are published and archived but not loaded.",
        "scenarios": [],
        "default_scenario": None,
        "products": [
            "State/county population totals, 2022 estimate and 2027/2032/2037/2042 projections (loaded)",
            "State/county five-year age and sex cohorts (archived but not served)",
            "City/town population projections (archived but not served)",
        ],
        "methodology": "OSE cohort-component model with a 2022 base. Most county migration rates average 2013-2017 and 2018-2022; Androscoggin, Kennebec, Knox, Somerset and Waldo use 2015-2019, and Piscataquis uses 2019-2023. Survival rates account for excess COVID-19 deaths. Published workbook totals reconcile with age/sex cells and the separate rounded PDF table.",
        "employment_note": "The demographic catalog links Maine DOL employment and occupational outlooks, which are outside the OSE scope. The economic catalog also publishes a wage/salary employment forecast authored by the independent Consensus Economic Forecasting Commission, with DAFS staff support. That commission product is not loaded or substituted for an OSE jobs series; eligible OSE jobs coverage remains unknown.",
        "license": "No explicit data license identified; cite the Maine Office of the State Economist.",
        "caveats": [
            "Only 2022, 2027, 2032, 2037 and 2042 are served. The workbook retains fractional model totals; the companion PDF and outlook report round to whole persons. No annual values are interpolated.",
            "OSE encourages limiting use of projections beyond 2032. The April 2025 model replaces the June 2023 edition. Later Census estimates do not change projection flags or the 2022 model base.",
            "Published municipal rows require checked county-subdivision identifiers; locations with fewer than 10 residents in any projection year are suppressed by the publisher, so municipal sums may not equal county totals.",
            "Household forecasts, eligible OSE employment forecasts and future component totals were not established in this source survey. The outlook contains historical component charts, not a loaded forecast series. No completed statewide review date is recorded.",
        ],
        "links": {
            "agency": "https://www11.maine.gov/dafs/economist",
            "catalog": "https://www11.maine.gov/dafs/economist/demographic-projections",
            "workbook": "https://www11.maine.gov/dafs/economist/sites/maine.gov.dafs.economist/files/inline-files/MaineStateCountyPopulationProjections2042.xlsx",
            "pdf": "https://www11.maine.gov/dafs/economist/sites/maine.gov.dafs.economist/files/inline-files/MaineStateCountyPopulationProjections2042.pdf",
            "methodology": "https://www11.maine.gov/dafs/economist/sites/maine.gov.dafs.economist/files/inline-files/Maine%20Population%20Outlook%20to%202032.pdf",
            "municipal": "https://www11.maine.gov/dafs/economist/sites/maine.gov.dafs.economist/files/inline-files/MaineCityTownPopulationProjection2042.xlsx",
            "economic_forecasting": "https://www1.maine.gov/dafs/economist/economic-forecasting",
        },
    },
    "NE": {
        "name": "Nebraska",
        "agency": "University of Nebraska at Omaha, Center for Public Affairs Research (Nebraska State Data Center)",
        "producer_type": "university (State Data Center lead; legislature-requested adopted product)",
        "current_vintage": "August 2022 edition: 2020 Census history and population projections at 2030, 2040 and 2050. The current publisher catalog still lists this update.",
        "geography_floor": "The separately published state total and all 93 counties are loaded. Subcounty projection publication was not established.",
        "scenarios": [],
        "default_scenario": None,
        "products": [
            "Nebraska and county total population, 2020/2030/2040/2050 (loaded)",
        ],
        "methodology": "At the Nebraska legislature's request, UNO CPAR evaluated six models and explicitly adopted Hauer/SEDAC's regional-rivalry model as best fitting Nebraska population dynamics. These are the producer's adopted national-model figures, not a newly generated CPAR cohort-component forecast. Only the report's published state/county rows and year points are served.",
        "employment_note": "The current CPAR demographic report and program catalog did not establish an eligible CPAR jobs forecast. Workforce research and labor-department occupational projections are not substituted. Employment publication coverage remains unknown.",
        "license": "No explicit data license identified; cite UNO CPAR and its cited Hauer/SEDAC model.",
        "caveats": [
            "The 2020 Census counts use MCP's estimate label; all 2030/2040/2050 figures remain projections regardless of retrieval date. base_year=2020 identifies the historical base supplied with this adopted product.",
            "The published state total exceeds rounded county sums by 2 people in 2030, 1 in 2040 and 3 in 2050. Both source values are retained; no unpublished state total or annual interpolation is generated.",
            "BoxButte and KeyaPaha are joined in the PDF and mapped to Census Box Butte and Keya Paha county FIPS identifiers. The June 2025 PDF modification metadata does not identify a new model vintage; the catalog and repository identify August 2022.",
            "The old university PDF address returns 404, and direct SharePoint/DigitalCommons PDF requests returned 403. The immutable report was acquired using the current catalog's public SharePoint browser download.",
            "Household, eligible jobs, future components and subcounty publication coverage remain unknown after this catalog/report survey. No completed statewide review date is recorded.",
        ],
        "links": {
            "agency": "https://www.unomaha.edu/college-of-public-affairs-and-community-service/center-for-public-affairs-research/",
            "catalog": "https://www.unomaha.edu/college-of-public-affairs-and-community-service/center-for-public-affairs-research/programs/data-for-policy-and-decision-makers.php",
            "pdf": "https://uofnebraska.sharepoint.com/:b:/s/UNOCenterforPublicAffairsResearch2/IQArysrd74RcR7lkqZFVHOVBAa7xSaM0iYr5KGXLHaEKDU4",
            "repository": "https://digitalcommons.unomaha.edu/cparpubarchives/643/",
            "state_data_center": "https://www.unomaha.edu/college-of-public-affairs-and-community-service/center-for-public-affairs-research/programs/nebraska-state-data-center.php",
        },
    },
    "NH": {
        "name": "New Hampshire",
        "agency": "New Hampshire Office of Planning and Development, Department of Business and Economic Affairs",
        "producer_type": "state agency (official projections prepared by consultant RLS Demographics)",
        "current_vintage": "September 2022: 2020 Census-based history and five-year projections 2025–2050.",
        "geography_floor": "State and all 10 counties loaded; published municipal projections archived but not loaded.",
        "scenarios": [],
        "default_scenario": None,
        "products": [
            "State, County, and Municipal Population Projections: 2020-2050, September 2022",
            "Five-year projected births, deaths and net migration in Appendix A (published but not loaded)",
        ],
        "methodology": "Official OPD publication prepared by RLS Demographics using a county cohort-component model. 2020 age/sex estimates are adjusted to Census county totals; demographic rates and special populations are documented in the report. Table 1 supplies loaded totals and Appendix A Tables 6-16 repeat every value.",
        "employment_note": "No eligible OPD jobs forecast was established during this audit. New Hampshire Employment Security occupational/industry projections are a separate labor product and are not substituted.",
        "license": "No explicit data license identified; cite the New Hampshire Office of Planning and Development.",
        "caveats": [
            "Population is served at exact five-year points, with no interpolation. The 2020 historical Census-based totals use the estimate flag.",
            "The 2030 Table 1 and Appendix A state total is 1,473,286, one above the county sum and executive summary prose; values are preserved.",
            "Appendix B Carroll county 2020 is 50,107, four below Table 1 and Appendix A's 50,111; Table 1 is selected consistently.",
            "Municipal forecasts and five-year components remain archived but not served. Household population in the methods is persons, not household counts.",
            "Current publisher catalog still links the September 2022 PDF; no table export or replacement edition was located on 2026-09-30.",
            "Appendix B towns need Census county-subdivision identifiers; city/place and town geographies are not interchangeable.",
        ],
        "links": {
            "agency": "https://www.nheconomy.com/office-of-planning-and-development",
            "population_projections": "https://www.nheconomy.com/office-of-planning-and-development/what-we-do/state-data-center-(census-data)/population-projections",
            "population_report": "https://www.nheconomy.com/getmedia/0205c62d-9c30-4b00-9c9e-d81d8f17b8b3/NH-Population-Projections-2020-2050-Final-Report-092022.pdf",
        },
    },
    "OH": {
        "name": "Ohio",
        "agency": "Ohio Department of Development, Office of Research",
        "producer_type": "state agency",
        "current_vintage": "2023 edition: 2020 estimate base and five-year population projections 2025–2050. The current catalog links Report 2023; the overview cites 2022.",
        "geography_floor": "State and all 88 counties loaded. Subcounty forecast publication coverage remains unverified.",
        "scenarios": [],
        "default_scenario": None,
        "products": [
            "Projections by County, 2020 to 2050: state and county population totals (loaded)",
            "Population Projections Report 2023 and Population Projections Overview: 2020 to 2050 (archived)",
        ],
        "methodology": (
            "Research Office cohort-component model using 2016–2020 demographic rates. "
            "Report endnote 2 identifies 2020 population estimates as the base, rather than "
            "unadjusted Census age/sex counts. County projections are controlled to the "
            "separately projected state total. Every county sum equals the workbook state row."
        ),
        "employment_note": "No eligible Research Office jobs forecast was established. Labor-department occupational forecasts are not substituted; employment publication coverage remains unknown.",
        "license": "No explicit data license identified; cite the Ohio Department of Development Research Office.",
        "caveats": [
            "Only seven exact five-year points 2020–2050 are served. The 2020 estimate label comes from report endnote 2; 2025 onward remains projection. No annual values are generated.",
            "The overview map prints Ottawa 2050 as 31,374, while the selected original workbook publishes 31,371. Workbook totals are retained consistently.",
            "State 2020 male/female age sums differ from separately published both-sex age cells by offsets summing zero. All total populations reconcile; the both-sex ages match the independent report.",
            "The workbook was modified January 6, 2023 and the catalog labels Report 2023, while the overview cites 2022. The report's October 2025 PDF modification timestamp does not establish a new model vintage.",
            "The report discusses conditional revisions after 2025 estimates; the current catalog still links this edition. Its demographic assumptions exclude economic and policy changes.",
            "The canonical static workbook link fails direct HTTP acquisition. Original workbook bytes were acquired from the publisher's DAM raw asset; a browser-rendered catalog excerpt records the visible canonical link.",
            "Statewide projected deaths, ten-year net migration and demographic detail are archived but not served. Household population counts persons, not households. Complete components, household-count, subcounty and eligible jobs publication coverage remains unknown.",
        ],
        "links": {
            "agency": "https://development.ohio.gov/about-us/research",
            "catalog": "https://development.ohio.gov/about-us/research/population",
            "workbook": "https://development.ohio.gov/static/research/pop1/Projections-by-County.xlsx",
            "download": "https://dam.assets.ohio.gov/raw/upload/development.ohio.gov/research/pop1/Projections-by-County.xlsx",
            "report": "https://dam.assets.ohio.gov/image/upload/development.ohio.gov/research/pop1/State-of-Ohio-Population-Projections-Report-2023.pdf",
            "overview": "https://dam.assets.ohio.gov/image/upload/development.ohio.gov/research/pop1/State-of-Ohio-Population-Projections-Overview-2020-to-2050.pdf",
        },
    },
    "NV": {
        "name": "Nevada",
        "agency": "Nevada Department of Taxation, Office of the State Demographer",
        "producer_type": "state agency",
        "current_vintage": "October 2025 long-range edition: 2024 certified estimate base and annual 2025-2044 projections.",
        "geography_floor": "State and all 17 county equivalents, including Carson City (32510).",
        "scenarios": [],
        "default_scenario": None,
        "products": [
            "State and county annual population totals, 2024-2044 (loaded)",
            "March 2026 near-term population forecast and separate age/sex/race/Hispanic-origin detail (published but not loaded)",
        ],
        "methodology": "REMI v3.3.0 demographic/economic model adjusted with QCEW employment change, GOED projects and Census migration inputs. July 2024 Governor-certified population estimates form the base.",
        "employment_note": "Employment forecasts discussed in the methods are model inputs. An eligible published SDO jobs series has not been established; employment coverage remains unknown.",
        "license": "No explicit data license identified; cite the Nevada State Demographer.",
        "caveats": [
            "Summary tables on printed pages 2-3 agree with all detailed tables on pages 4-8. 2024 is an estimate, every 2025-2044 row is a projection.",
            "State totals are independently published. Rounded county sums can differ; no values are adjusted.",
            "The March 2026 five-year product is a separate edition and is not combined with this long-range series. The September 2026 catalog still lists the October 2025 long-range edition.",
            "Place, households, components and eligible employment publication coverage remains unverified.",
        ],
        "links": {
            "agency": "https://tax.nv.gov/news-publications/demographics/",
            "report": "https://tax.nv.gov/wp-content/uploads/2025/09/Nevada-County-Population-Projections-2025-to-2044.pdf",
            "near_term": "https://tax.nv.gov/wp-content/uploads/2026/02/FINAL-March-2026-Five-Year-Projections.pdf",
        },
    },
    'MA': {'name': 'Massachusetts',
     'agency': 'University of Massachusetts Donahue Institute, Population Estimates Program',
     'producer_type': 'university (official population projections supported by the Massachusetts Secretary '
                      'of the Commonwealth)',
     'current_vintage': 'UMDI Vintage 2024 (May 2024), launch 2020, exact five-year projections 2025-2050. '
                        'Workbooks last modified October 16, 2024; no separate revision label established.',
     'geography_floor': '351 municipalities (MCD identifiers) are published, plus 14 counties, 13 Regional '
                        'Planning Agency total rows, and the state. Only state and county totals are '
                        'loaded; municipal county-subdivision identifier loading is deferred.',
     'scenarios': [],
     'default_scenario': None,
     'products': ['V2024 state/county/municipal/RPA total population at 2010, 2020 and five-year points '
                  '2025-2050; state/county 2020-2050 totals loaded',
                  'V2024 population by 18 five-year age groups and sex; archived for checks but not served'],
     'methodology': 'Cohort-component projections with a 2020 Census DHC launch adjusted for Census '
                    'challenges and child undercounts. Regional gross age-specific migration uses ACS PUMS '
                    '2012-2019; county/municipal residual net migration uses Census 2010-2020 and vital '
                    'statistics. Municipality cohorts are controlled to regional projections, with '
                    'documented Suffolk exceptions. Population forecasts reflect historical trend '
                    'assumptions.',
     'employment_note': 'Eligible current SDO employment forecast coverage remains unverified. The V2024 '
                        'methods mention older UMDI employment work under MassDOT for regional '
                        'transportation plans; it is not merged with population or treated as a verified '
                        'current SDO jobs product.',
     'license': 'No explicit data license identified; cite UMass Donahue Institute V2024 Population '
                'Projections.',
     'caveats': ['2020 totals are adjusted historical launch values, not unadjusted Census totals. '
                 'Fractional workbook cells are retained at source precision.',
                 'The Source tab typo May 9, 20204 is corroborated by its Vintage 2024/May 2024 labels and '
                 'the methods cover dated May 9, 2024.',
                 'No intermediate years are generated. The publisher warns that small geographies and '
                 'distant horizons have greater uncertainty.',
                 'All 351 municipal rows and 13 RPA total rows are published and archived but not loaded. '
                 'MCD codes are not Census place FIPS; municipal county-subdivision identifier loading is '
                 'deferred.',
                 'Household-count, complete future components, and eligible current SDO jobs coverage '
                 'remain unverified; absence of coverage is unknown, not not_published.'],
     'links': {'agency': 'https://www.umass.edu/donahue/research-and-data/massachusetts-population-estimates-program',
               'population_catalog': 'https://www.umass.edu/donahue/research-and-data/massachusetts-population-estimates-program/population-projections',
               'population_totals': 'https://www.umass.edu/donahue/media/2441/download?attachment=',
               'population_age_sex': 'https://www.umass.edu/donahue/media/2443/download?attachment=',
               'population_methodology': 'https://www.umass.edu/donahue/media/2445/download?attachment='}},
    'NJ': {'name': 'New Jersey',
     'agency': 'New Jersey Department of Labor and Workforce Development, Division of Economic and '
               'Demographic Research',
     'producer_type': 'state agency (NJDOL demographic research program)',
     'current_vintage': '2014–2034 series: Census Vintage 2014 estimate base and four five-year projection '
                        'points, distributed in May 2017 XLSX files. The current NJDOL catalog still serves '
                        'this older series; no newer NJDOL demographic successor was found.',
     'geography_floor': 'State and all 21 counties loaded. Four models apply at state level only; counties '
                        'have one preferred Economic-Demographic series. Other geography publication '
                        'coverage remains unknown.',
     'scenarios': ['economic_demographic', 'zero_migration', 'historical_migration', 'linear_regression'],
     'default_scenario': 'economic_demographic',
     'scenario_geo_levels': ['state'],
     'products': ['Total population by four statewide projection models, 2014/2019/2024/2029/2034 (loaded)',
                  'Total population for all 21 counties, preferred Economic-Demographic model at the same '
                  'exact points (loaded)',
                  'Civilian labor force and age/sex/race/Hispanic-origin demographic tables (published but '
                  'not loaded)'],
     'methodology': 'The preferred Economic-Demographic model uses cohort-component demographic '
                    'calculations and migration under age 65 linked to labor demand. Historical Migration '
                    'replaces that migration assumption with historical rates. Zero Migration is an '
                    'illustrative cohort-component model without net migration; Linear Regression is an '
                    'illustrative extrapolation of state total population history from 1900 through 2014. '
                    'The county introduction identifies its single series as Economic-Demographic.',
     'employment_note': 'This demographic product publishes civilian labor force, which includes employed '
                        'and job-seeking residents and is not employment or a count of jobs. NJDOL '
                        'industry/occupational projections and newer MPO planning products are separate '
                        'products and are not substituted. An eligible demographic-program jobs forecast '
                        'was not established; employment coverage remains unknown.',
     'license': 'No explicit data license identified; cite the New Jersey Department of Labor and Workforce '
                'Development.',
     'caveats': ['2014 is the last estimate year in this product. The 2019 and 2024 values remain '
                 'projections even though their years are past at retrieval. The April 2010 Census column '
                 'is archived only; no later estimates, annual interpolation or rebasing are inserted.',
                 'The preferred state 2029 total is 9,531,200 in the state workbook and its independent '
                 'summary chart at table precision; the county workbook state row and county sum are '
                 '9,530,900. State queries consistently use the state workbook and county queries use '
                 'published county values.',
                 'The independently published tables round estimates and projections to hundreds. Preferred '
                 'state minus county sum is +100 in 2014, 0 in 2019, -300 in 2024, +300 in 2029 and +100 in '
                 '2034. Differences are retained rather than forcing equality.',
                 'The source designates Economic-Demographic as preferred. Zero Migration and Linear '
                 'Regression are chiefly illustrative; alternatives are state-only and are not substituted '
                 'for county data.',
                 'The XLSX files were last modified May 11, 2017; the archived methodology and county '
                 'introduction were saved November 2016. File timestamps identify the archived edition and '
                 'do not establish an exact model release date. October 2026 is retrieval, not projection '
                 'vintage.',
                 'The publisher describes these as projections rather than predictions or policy targets '
                 'and cautions that long-term economic assumptions may not hold. Unused #REF! cells at '
                 'H198:H219 are outside the county data table and remain only in the archived original.',
                 'Household counts, future components, subcounty population and eligible '
                 'demographic-program jobs publication coverage were not established by this '
                 'catalog/methods survey and remain unknown. No completed statewide review date is '
                 'recorded.'],
     'links': {'agency': 'https://www.nj.gov/labor/labormarketinformation/demographics/',
               'catalog': 'https://www.nj.gov/labor/labormarketinformation/demographics/population-labor-projections/',
               'state_workbook': 'https://www.nj.gov/labor/labormarketinformation/assets/PDFs/dmograph/lfproj/sptab1.xlsx',
               'county_workbook': 'https://www.nj.gov/labor/labormarketinformation/assets/PDFs/dmograph/lfproj/table1.xlsx',
               'methodology': 'https://www.nj.gov/labor/labormarketinformation/assets/PDFs/dmograph/lfproj/method24.doc',
               'county_introduction': 'https://www.nj.gov/labor/labormarketinformation/assets/PDFs/dmograph/lfproj/county_intro2034.doc',
               'summary_presentation': 'https://www.nj.gov/labor/labormarketinformation/assets/PDFs/dmograph/lfproj/PopLFProj.pptx'}},
    'NY': {'name': 'New York',
     'agency': "Cornell University Program on Applied Demographics (New York's Federal-State population "
               'projections representative)',
     'producer_type': "university (New York's Federal-State population estimates/projections representative "
                      'and State Data Center coordinating agency)',
     'current_vintage': 'State: October 2024 provisional edition, base 2022, horizon 2050. Counties: '
                        'September 21, 2018 edition, base 2015, horizon 2040; catalog reviewed October 1, '
                        '2026 still lists these distinct products.',
     'geography_floor': 'All 62 counties are loaded from the 2018 product. State scenarios come from the '
                        'separate 2024 product. Ten economic-region series are published in the older '
                        'county explorer and remain deferred; smaller-area forecast coverage is unverified.',
     'scenarios': ['middle', 'high', 'low'],
     'default_scenario': 'middle',
     'scenario_geo_levels': ['state'],
     'default_scenario_note': "defaulted to this server's central scenario (middle); Cornell PAD describes "
                              'Middle as pre-Covid demographic change',
     'products': ['New York State Population Projections 2022-2050, October 2024, annual Middle/High/Low '
                  'scenarios',
                  '2018 County Population Projections, 2015-2040, annual, 62 counties, single series',
                  'State scenario components 2023-2050 and county components 2016-2040, archived but not '
                  'loaded',
                  '2018 economic-region population projections 2015-2040, published but not loaded'],
     'methodology': 'Separate cohort-component products. The 2024 state model starts July 1, 2022 from '
                    'Census Vintage 2023 estimates. The 2018 county model starts in 2015 from Vintage 2017 '
                    'Bridged-Race Postcensal Population Estimates through CDC-Wonder, with fertility, '
                    'mortality and adjusted migration assumptions. Base years are not publication years or '
                    'estimate vintages. Only source-published totals are served; county aggregates never '
                    'replace the newer statewide forecast.',
     'employment_note': 'The reviewed population catalogs do not establish whether Cornell PAD publishes a '
                        'current eligible jobs forecast. Employment coverage remains unknown; labor-force '
                        'or New York labor-department occupational projections are not substituted.',
     'license': 'No explicit data license identified in the reviewed products; cite Cornell Program on '
                'Applied Demographics.',
     'caveats': ['State and county products have different editions, bases, horizons and scenario support; '
                 'the 2018 counties are not consistent with the newer state controls.',
                 '2023-2050 state and 2016-2040 county points remain projections even for years preceding '
                 'retrieval.',
                 'State workbook totals are fractional; their published precision is preserved. Age/sex and '
                 'median-age detail is archived only.',
                 'The 2024 statewide edition is labeled provisional and planned updates are not evidence of '
                 'a newer released edition.',
                 'The county source spells St. Lawrence as St Lawrence; full Census FIPS and Census names '
                 'are used for queries.',
                 'Household, municipal and eligible employment products have not been established by the '
                 'reviewed population catalogs; coverage stays unknown.',
                 'State/county components and ten economic-region population series are demonstrably '
                 'published but remain un-ingested.'],
     'links': {'agency': 'https://pad.human.cornell.edu/people.cfm',
               'state_catalog': 'https://pad.human.cornell.edu/state_projections/',
               'state_data': 'https://pad.human.cornell.edu/state_projections/datatools.cfm',
               'state_base': 'https://pad.human.cornell.edu/state_projections/meth_base.cfm',
               'state_scenarios': 'https://pad.human.cornell.edu/state_projections/meth_scenarios.cfm',
               'county_catalog': 'https://pad.human.cornell.edu/counties/index.cfm',
               'county_explorer': 'https://pad.human.cornell.edu/counties/projections.cfm',
               'county_methods': 'https://pad.human.cornell.edu/counties/downloads/2018Methodology.pdf',
               'county_guide': 'https://pad.human.cornell.edu/counties/downloads/ProjectionsUserManual.pdf'}},
    'CT': {'name': 'Connecticut',
     'agency': 'Connecticut State Data Center, University of Connecticut',
     'producer_type': 'university state data center; officially published by the State of Connecticut',
     'current_vintage': 'Revised September 2017 state model; June 2018 county/COG release, five-year '
                        'projections 2015-2040. Catalog metadata updated in 2023; no newer eligible model '
                        'established.',
     'geography_floor': 'State, all eight historical counties, and nine separately identified 2018 regional '
                        'councils of government loaded. Modern county-equivalent planning regions are not '
                        'substituted. Town projections remain deferred.',
     'scenarios': [],
     'default_scenario': None,
     'products': ['Resident population 2015-2040: state, eight historical counties and nine COG totals '
                  '(loaded)',
                  'Town population projections and age/sex detail (published but not loaded)'],
     'methodology': 'Demographic projections based on Census population, state birth/mortality data and '
                    'Census migration inputs. The DSS 2019 report reproduces the SDC methodology and '
                    'identifies the 2010 Census as the starting point. Every published 2015-2040 point '
                    'remains a projection; values represent annual-average residents.',
     'employment_note': 'No eligible SDO jobs forecast was established. Publication coverage remains '
                        'unknown; occupational, regional and health-service forecasts are not substituted.',
     'license': 'CC BY-SA 3.0 for Connecticut open-data dataset pv2w-k7qu; cite the Connecticut State Data '
                'Center.',
     'caveats': ['This is an older forecast, not a 2023 vintage. Past projection years retain projection '
                 'labels.',
                 'The eight historical counties use Census 2020 FIPS 09001-09015. The 2018 COGs use '
                 'separate prefixed IDs at geo_level=cog, not modern county-equivalent FIPS or county '
                 'values.',
                 'Published county and COG sums differ slightly from independently rounded state totals. No '
                 'balancing or interpolation is applied.',
                 'The source misspells Metropolitan as Metropolitian; the display name is corrected without '
                 'changing its data.',
                 'The original UConn methods URL now redirects to CTData. The archived state DSS report '
                 'reproduces the methods; 2010 records the historical Census anchor, and no estimate rows '
                 'are loaded.',
                 'Households, complete components and eligible SDO jobs publication coverage remains '
                 'unverified. Town identifier/data loading is deferred.'],
     'links': {'agency': 'https://www.ctdata.org/',
               'population_dataset': 'https://data.ct.gov/d/pv2w-k7qu',
               'population_download': 'https://data.ct.gov/api/views/pv2w-k7qu/rows.csv?accessType=DOWNLOAD',
               'release': 'https://blogs.lib.uconn.edu/outsidetheneatline/2017/07/30/connecticuts-population-is-expected-to-grow-slowly-connecticut-state-data-center-reports/',
               'adopted_methods': 'https://portal.ct.gov/-/media/Departments-and-Agencies/DSS/Health-and-Home-Care/Medicaid-Long-Term-Care-Demand-Projections/Main-report--CT-LTC-Demand-Report-Narrative.pdf',
               'geography_guidance': 'https://portal.ct.gov/dph/resources-and-records/data-research/vital-statistics-and-population-data/population-statistics'}},
    'RI': {'name': 'Rhode Island',
     'agency': 'Rhode Island Division of Statewide Planning, Department of Administration',
     'producer_type': 'state agency and State Data Center',
     'current_vintage': 'Revised February 27, 2026: published five-year projections 2025-2050. Last '
                        'underlying estimate year is unconfirmed.',
     'geography_floor': 'State Total row and all 39 cities/towns loaded as county_subdivision with '
                        'ten-digit Census 2025 GEOIDs. No county forecasts are derived from municipalities.',
     'scenarios': [],
     'default_scenario': None,
     'products': ['Population Projections 2025-2050: state and all 39 municipalities (loaded)'],
     'methodology': 'The FY2026 RIDSP work program describes a statewide cohort-component model guiding '
                    'municipal projections and municipal input. The current revised table is officially '
                    'linked by the agency. Completed methods confirming the model base and detailed '
                    'assumptions were not located.',
     'employment_note': 'RIDSP planned a separate jobs projection project in its FY2026 work program, but a '
                        'released eligible jobs series was not established. Employment publication coverage '
                        'remains unknown.',
     'license': 'No explicit data license identified; cite the Rhode Island Division of Statewide Planning.',
     'caveats': ['Every 2025-2050 value is labeled projection. The table does not identify a last estimate '
                 'year; base_year is null. A proposed 2020 base in the work program is not confirmation for '
                 'the revised product.',
                 'The agency states that projections are subject to future revision and correction based on '
                 'available data and municipal input.',
                 'The statewide Total row is published directly; municipal sums differ by -3 to +1 persons '
                 'and are preserved.',
                 'All cities/towns use county_subdivision GEOIDs. Census place IDs, full town/city GEOIDs, '
                 'and counties are distinct. One undefined Newport County water subdivision has no forecast '
                 'and is excluded.',
                 'The selected table has no county rows. Earlier county products are not mixed into this '
                 'edition; households, components and released SDO employment remain unverified.'],
     'links': {'agency': 'https://planning.ri.gov/',
               'population_table': 'https://planning.ri.gov/sites/g/files/xkgbur826/files/2026-02/Municipal%20Projections%20%2002272026.pdf',
               'geography_reference': 'https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer/2025_gaz_cousubs_44.txt',
               'work_program': 'https://planning.ri.gov/sites/g/files/xkgbur826/files/2025-09/FY26_UPWP_FINAL_06.12.2025%20%285%29.pdf'}},
    'ID': {'name': 'Idaho',
     'agency': 'Idaho Department of Labor, Labor Market Information',
     'producer_type': 'state agency; demographic population forecast producer',
     'current_vintage': 'Revised August 7, 2025: annual projections 2024-2034; underlying last ACS estimate '
                        'year unconfirmed.',
     'geography_floor': 'State and all 44 counties loaded; six economic-region products deferred. County is '
                        'the smallest modeled geography in the linked methods.',
     'scenarios': [],
     'default_scenario': None,
     'products': ['Ten-Year Population Forecast 2024-2034: state and all 44 county Total rows (loaded)',
                  'Six regional population series, age/sex detail and potential labor-force counts '
                  '(published but not loaded)'],
     'methodology': 'County/age cohort model of births, deaths, aging and net migration; current catalog '
                    'identifies American Community Survey estimate inputs. The last underlying estimate '
                    'year and population reference day are unstated, so base_year is null and all 2024-2034 '
                    'points remain projections.',
     'employment_note': 'Workbook Labor Force measures the potential labor pool, not jobs. Separate '
                        'industry/occupational projections are outside this demographic product; no '
                        'eligible demographic jobs forecast was established.',
     'license': 'No explicit data license identified; cite the Idaho Department of Labor.',
     'caveats': ['Annual 2024-2034 points are explicitly cataloged projections. 2024 is not inferred to be '
                 'an estimate; the last underlying ACS estimate year remains unknown.',
                 'The September 2025 URL directory and workbook metadata dates are not model vintage; '
                 'selected catalog revision is August 7, 2025.',
                 'Published state, region and county Total rows reconcile exactly. All values retain '
                 'integer-person precision; no interpolation or balancing.',
                 'Regional worksheets contain all 44 counties once. Census 2020 names/FIPS match the '
                 'publication. The currently linked 2017 general methods identify county as the most '
                 'detailed model geography; no place values are derived.',
                 'Age/sex detail and potential Labor Force are archived but not served. Household counts, '
                 'published component tables and eligible demographic jobs publication coverage remain '
                 'unverified.'],
     'links': {'population_catalog': 'https://lmi.idaho.gov/data-tools/population-projections/',
               'state_workbook': 'https://lmi.idaho.gov/wp-content/uploads/2025/09/Population_Statewide.xlsx',
               'methods': 'https://lmi.idaho.gov/wp-content/uploads/publications/2017/PopulationProjections/Population-Forecast-Methodology.pdf?ver=2017-05-31-171419-813',
               'industry_occupation_catalog': 'https://lmi.idaho.gov/data-tools/occupational-industry-projections/'}},
    'ND': {'name': 'North Dakota',
     'agency': 'North Dakota Department of Commerce, State Data Center',
     'producer_type': 'state agency and official State Data Center',
     'current_vintage': 'Prepared February 6, 2024: 2020 Census anchor and five-year population projections '
                        '2025-2050.',
     'geography_floor': 'State and all 53 counties loaded from printed pp10-11; eight economic-planning '
                        'regions remain deferred. Subcounty publication coverage is unverified.',
     'scenarios': [],
     'default_scenario': None,
     'products': ['2024 Population Projections of the State, Regions, and Counties: state and all 53 county '
                  'summary totals (loaded)',
                  'Eight economic-planning region totals and state age/sex detail (published but not '
                  'loaded)',
                  'Five-year natural-change/net-migration components (PDF-only, not loaded)'],
     'methodology': 'Modified cohort-survival-component model based on Census 2020 county age/sex '
                    'populations, state vital statistics, CDC survival inputs and adjusted migration '
                    'patterns; historical 2020 Census counts are marked estimate under the common schema. '
                    'Future projection reference day is unstated.',
     'employment_note': 'No eligible State Data Center jobs forecast was established. Workforce-age '
                        'population is persons, not jobs, and labor-agency occupational forecasts are not '
                        'substituted.',
     'license': 'No explicit data license identified; cite the North Dakota Department of Commerce State '
                'Data Center.',
     'caveats': ['State 2050 is 957,194 in the selected p11 North Dakota Totals row and p14 Both Sexes '
                 'Total. Executive summary and catalog instead say 957,124; the explicit numeric table '
                 'series is retained.',
                 'County sums minus state totals are 0,-1,0,+1,+4,+2,+2 persons for '
                 '2020/2025/2030/2035/2040/2045/2050. No balancing is applied despite methods describing '
                 'county-to-region-to-state aggregation.',
                 'Exact five-year points only; past projection years retain projection labels. Census 2020 '
                 'is the historical model anchor, not a generated base row.',
                 'Age/sex detail contains historical and rounding differences and is not substituted for '
                 'summary Total rows. Regions and demographic detail remain deferred.',
                 'Five-year natural change means births minus deaths; p6 does not separately publish '
                 'births/deaths. Components remain PDF-only and unannualized.',
                 'Subcounty population, household-count and eligible SDC jobs coverage remain unverified.'],
     'links': {'agency': 'https://www.commerce.nd.gov/economic-development-finance/state-data-center',
               'population_report': 'https://www.medialibrary.nd.gov/assetbank-nd/assetfile/137073.pdf'}},
    'SD': {'name': 'South Dakota',
     'agency': 'South Dakota State Data Center / State Demographer, South Dakota State University',
     'producer_type': 'university State Data Center / State Demographer, jointly funded with state Labor '
                      'Market Information Center',
     'current_vintage': '2012 preliminary Medium Series, 2010–2035. Original workbook survives at a '
                        'migrated university URL; no newer eligible all-county release was established.',
     'geography_floor': 'State and all 66 source-era counties loaded. Shannon County uses historical FIPS '
                        '46113; modern Oglala Lakota 46102 is not substituted.',
     'scenarios': ['medium'],
     'default_scenario': 'medium',
     'products': ['Population 2010–2035: state and 66 source-era counties, Medium Series (loaded)',
                  'Age/sex population detail (archived, not served)'],
     'methodology': 'The State Demographer’s 2013 presentation identifies this as the 2012 project and '
                    'explicitly uses trends and population existing April 1, 2010. The cohort model uses '
                    'birth, mortality and migration assumptions. All county base totals independently match '
                    'Census 2010; no later estimate calibration was established.',
     'employment_note': 'No eligible SDO jobs forecast was established. Publication coverage remains '
                        'unknown; DLR occupational forecasts and potential-workforce age counts are not '
                        'substituted.',
     'license': 'No explicit data license identified; cite the South Dakota State Data Center, South Dakota '
                'State University.',
     'caveats': ['This older preliminary product uses a 2010 Census base. 2010 is marked estimate under the '
                 'common schema; 2015–2035 remain projections, even in past years.',
                 'Original cached Excel numeric precision is preserved, including fractional persons that '
                 'Excel displays rounded. DLR independently repeats all rounded state totals.',
                 'County sums differ from the separately published state forecast by up to about 9,003 '
                 'persons; no balancing, interpolation or derived totals are applied.',
                 'Shannon was renamed Oglala Lakota in 2015 with unchanged boundaries and FIPS changed '
                 '46113 to 46102. Queries must use the original source name/code; no alias or modern-code '
                 'values are fabricated. The national Census 2020 snapshot remains unchanged.',
                 'Only the published Medium Series is recovered. No low/high data are invented. Household '
                 'counts, complete components, subcounty forecasts and eligible SDO jobs publication '
                 'coverage remain unverified.'],
     'links': {'agency': 'https://www.sdstate.edu/school-psychology-sociology-and-rural-studies/census-data-center',
               'state_referral': 'https://dlr.sd.gov/lmic/menu_population.aspx',
               'population_workbook': 'https://www.sdstate.edu/sites/default/files/soc/rlcdc/generaldemographicdata/upload/Projections-with-Pyramids2.xlsx',
               'methods_catalog': 'https://openprairie.sdstate.edu/sd_demography_conference/2013/presentations/1/',
               'archived_methods': 'https://web.archive.org/web/20210101000000id_/https://openprairie.sdstate.edu/cgi/viewcontent.cgi?article=1000&context=sd_demography_conference',
               'historical_geography': 'https://www2.census.gov/geo/docs/maps-data/data/gazetteer/Gaz_counties_national.zip',
               'name_change': 'https://www.weather.gov/media/notification/pdfs/scn15-31shannon_oglalacty_cca.pdf',
               'independent_state_table': 'https://dlr.sd.gov/lmic/publications/labor_market_reports/workforce_report_2020.pdf'}},
    'MS': {'name': 'Mississippi',
     'agency': 'State Data Center of Mississippi, Center for Population Studies, University of Mississippi',
     'producer_type': 'university State Data Center, collaborative University/state/Census program',
     'current_vintage': 'May 2, 2019 preliminary state release. Current download is byte-identical to '
                        'archived original 2019 PDF; 2020–2050 projections from 2010 launch.',
     'geography_floor': 'State totals loaded; county and place-based forecasts are explicitly offered upon '
                        'request but their numeric data are not loaded.',
     'scenarios': [],
     'default_scenario': None,
     'products': ['State population 2020–2050 at five-year points (loaded)',
                  'County/place-based population projections upon request (published but not loaded)',
                  'Age/sex and source-specific white/nonwhite population detail (archived, not served)'],
     'methodology': 'Original May 2, 2019 methods identify a 2010 launch and 2000–2010 Census base period. '
                    'Cohort-component projections use fixed fertility/survival rates and gross migration '
                    'assumptions. Current file retains the original 2019 figures; it is not rebased to '
                    'Census 2020.',
     'employment_note': 'No eligible SDO jobs forecast was established. Publication coverage remains '
                        'unknown; labor-department occupational forecasts are not substituted.',
     'license': 'No explicit data license identified; cite the State Data Center of Mississippi, University '
                'of Mississippi.',
     'caveats': ['All 2020–2050 points are projections, including past years. base_year=2010 records the '
                 'launch; no 2010 observation is fabricated.',
                 'Only the statewide TOTAL race / BOTH SEXES column and TOTAL row is served. Counts are '
                 'rounded whole persons, with published age/sex/race sum differences up to three persons '
                 'preserved.',
                 'County and place coverage is known from the publisher’s original catalog, but numeric '
                 'loading is deferred. No agency correspondence was undertaken.',
                 'Household counts, complete future components and eligible SDO jobs publication coverage '
                 'remains unverified. Housing-unit estimates and cohort-model inputs are not forecasts of '
                 'those products.'],
     'links': {'agency': 'https://olemiss.edu/departments/libarts/population-studies/statedatacenterofmississippi/',
               'population_pdf': 'https://www.dropbox.com/scl/fi/z6fsf9i8vdd4kya20eqzt/State-of-Mississippi-Population-Projections-2020-2050.pdf?dl=1&rlkey=j2au553lzdzbtu0mdf7njflt7',
               'archived_methods': 'https://web.archive.org/web/20190917012609id_/https://sdc.olemiss.edu/wp-content/uploads/sites/143/2019/05/Mississippi-Population-Projection-Methodology-2.pdf',
               'archived_catalog': 'https://web.archive.org/web/20190501000000id_/http://sdc.olemiss.edu/population-projections/'}},
    'KS': {'name': 'Kansas',
     'agency': "Kansas Division of the Budget (commissioned from Moody's Economy.com)",
     'producer_type': 'state budget demographic program; explicitly commissioned and officially published '
                      'projections',
     'current_vintage': 'Loaded: November 2006 official commissioned forecast, published January 2010; '
                        'annual county projections 2010-2021 only. The entire horizon is in the past. Newer '
                        'CEDBR 2024 university forecasts have unconfirmed official state '
                        'authority/adoption.',
     'geography_floor': 'All 105 counties loaded. Appendix L has no published statewide Total Population '
                        'row. Its narrative mentions Kansas and all counties ambiguously; state population '
                        'coverage remains unknown and no county sum is served as a state forecast.',
     'scenarios': [],
     'default_scenario': None,
     'products': ['County population 2010-2021, November 2006 Budget-commissioned forecasts, Appendix L '
                  '(loaded)',
                  'County age-cohort projections, same official Appendix L (published but not loaded)',
                  'CEDBR 2024 population and component dashboards (candidate; official state '
                  'authority/adoption unconfirmed; not loaded)',
                  'CEDBR 2026 employment forecasts (separate candidate; eligible SDO status unconfirmed; '
                  'not loaded)'],
     'methodology': 'The official report p. 56 explicitly identifies the Kansas Division of the Budget '
                    "commissioning Moody's Economy.com in November 2006. Appendix L, pp. 139-178, contains "
                    '105 county Total Population rows at 12 annual points 2010-2021. The last estimate year '
                    'and detailed model method are unstated; base_year is null. Every value remains a '
                    'projection.',
     'employment_note': 'CEDBR publishes separate employment forecasts, but its official state demographic '
                        'role or adoption has not been established. The Budget report contains employment '
                        'history and economic commentary; no separately verified eligible SDO jobs series '
                        'is loaded. Labor force and occupational projections are not substituted.',
     'license': 'No explicit data license identified in the public state report; cite Kansas Division of '
                "the Budget and Moody's Economy.com.",
     'caveats': ['This old forecast ends in 2021. No population forecast for 2022 or later is served. Past '
                 'projection years remain projections.',
                 'November 2006 is the forecast vintage; January 2010 is the selected report publication '
                 'date. The current catalog says this report is no longer produced and FY2012 onward '
                 'demographic appendices contain Census estimates.',
                 'base_year is null: Census 2000 references and newer historical estimates elsewhere in the '
                 'report do not identify the forecast model’s last estimate input. No 2006 or Census 2010 '
                 'base row is fabricated.',
                 'The selected Appendix L contains all 105 counties, but no statewide total. Its narrative '
                 'does not establish a recoverable statewide Total Population row. State coverage stays '
                 'unknown; no aggregate is invented.',
                 'Newer CEDBR 2024 dashboards remain candidates. University affiliation, the Census FSCPP '
                 'directory, private Patterson Family Foundation sponsorship and incidental government '
                 'citations do not establish official state demographic authority or adoption.',
                 'KDOC 2022 testimony and the Kansas DOT freight plan use older CEDBR editions; neither '
                 'establishes adoption of the 2024 forecast. Older 1992 Budget and 1999 Budget/Water Office '
                 'products are historical leads and are not mixed into the selected series.',
                 'All 1,260 totals match independent Poppler text extraction and rendered original '
                 'fixtures. Several cells omit commas, including Bourbon County’s 2016 population 14846.',
                 'Age-cohort detail is deferred. Household, component, subcounty and eligible SDO jobs '
                 'publication coverage remains unverified.'],
     'links': {'agency': 'https://budget.kansas.gov/population/',
               'official_population_report': 'https://budget.kansas.gov/wp-content/uploads/fy2011-2009-2010-econ-demo-rpt.pdf',
               'historical_catalog': 'https://budget.kansas.gov/population/historic/',
               'population_candidate': 'https://cedbr.org/data-portal/population-and-demographics/population-forecast/',
               'candidate_sponsorship': 'https://cedbr.org/data-portal/',
               'employment_candidate': 'https://cedbr.org/data-portal/employment/',
               'census_fscpp_directory': 'https://www.census.gov/programs-surveys/popproj/about/fscpp/contacts.html',
               'kdoc_older_use': 'https://www.kslegislature.gov/li_2022/b2021_22/committees/ctte_jt_cjjo_1/documents/testimony/20221128_16.pdf',
               'kdot_older_use': 'https://www.ksdot.gov/home/showpublisheddocument/472/638943023665770000'}},
    'MO': {'name': 'Missouri',
     'agency': 'Missouri Office of Administration, Division of Budget and Planning',
     'producer_type': 'state demography office within the Office of Administration',
     'current_vintage': 'Old March 2008 Preferred Series, still linked by the current official catalog: '
                        'exact five-year points 2000-2030. No newer eligible OA edition was established. '
                        'Last estimate input is 2007; corrected Census 2000 anchor.',
     'geography_floor': 'State and all 114 counties plus independent St. Louis city (county equivalent) '
                        'loaded. St. Louis County 29189 and independent city 29510 are distinct. No '
                        'subcounty forecast is derived.',
     'scenarios': [],
     'default_scenario': None,
     'products': ['Population 2000-2030, state and 115 county-equivalent totals, March 2008 Preferred '
                  'Series (loaded)',
                  'Age/sex detail and five-year birth/death/net migration components (published but not '
                  'loaded)'],
     'methodology': 'OA credits the Missouri State Demographers with producing the Preferred Series. '
                    'Independent county cohort-component models launch from corrected April 1 Census 2000 '
                    'counts, then use estimate inputs through 2007 for migration controls. base_year=2007 '
                    'records the last estimate input. Methods explicitly call 2005 projected even though it '
                    'precedes 2007; all 2005-2030 remain projections. The 2000 history uses the MCP '
                    'estimate label.',
     'employment_note': 'No eligible OA/SDO jobs forecast was established. MERIC links this same old '
                        'population product; labor-department occupational projections and regional MPO '
                        'forecasts are not substituted. Eligible jobs publication coverage remains unknown.',
     'license': 'No explicit data license identified; cite the Missouri Office of Administration.',
     'caveats': ['This is an old March 2008 forecast ending in 2030. The 2024/03 download URL is a hosting '
                 'path, not a new vintage. No 2031 or later forecast is generated.',
                 'All 2005-2030 points remain projections, including past years. The corrected Census 2000 '
                 'point uses the MCP estimate label. Five-year gaps are not interpolated.',
                 'base_year=2007 follows the operational migration methods’ latest estimate input. The '
                 'model launches from Census 2000. Methods explicitly use 2000-2005 controls to project '
                 '2005, then 2000-2007 controls starting in the 2005-2010 cycle. No 2007 row is fabricated.',
                 'The data-source list cites estimates through 2006 while the operational discussion '
                 'explicitly identifies 2007. The latter defines the recorded last estimate year.',
                 'All 114 counties plus independent St. Louis city use distinct FIPS. Displayed county '
                 'totals exactly sum to the independently published state row at all seven points.',
                 'Every original XLS total matches the three-page county PDF and the state age PDF Total '
                 'row. The rendered state PDF footer dates the edition March 2008.',
                 'Preferred is the sole selected series; no alternative scenarios are exposed. Age/sex '
                 'detail and previous-five-year components are not loaded. Components return not_loaded.',
                 'Household, subcounty and eligible SDO jobs coverage remains unverified. The broader '
                 'product audit is unfinished and review status remains never_reviewed.'],
     'links': {'agency': 'https://budplan.oa.mo.gov',
               'population_catalog': 'https://budplan.oa.mo.gov/demographic-info/population-projections/2000-2030-projections',
               'population_table': 'https://budplan.oa.mo.gov/sites/g/files/zuston231/files/media/file/2024/03/total-pop-all-counties.xls',
               'methods': 'https://budplan.oa.mo.gov/demographic-info/population-projections/methodology',
               'producer': 'https://budplan.oa.mo.gov/demographic-info/population-projections',
               'state_age_components': 'https://budplan.oa.mo.gov/sites/g/files/zuston231/files/media/pdf/2024/03/pop-projections-by-age-state-totals.pdf',
               'county_pdf': 'https://budplan.oa.mo.gov/sites/g/files/zuston231/files/media/pdf/2024/03/total-pop-all-counties_0.pdf',
               'meric_crosslink': 'https://meric.mo.gov/data/population/new-population-projections'}},
}
