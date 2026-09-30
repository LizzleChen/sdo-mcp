# Source reviews and loading status

Run `uv run python -m sdo_mcp.monitoring --database data/sdo.sqlite`
for a JSON report of all 20 states. Omit `--database` to inspect the installed
copy (or the file selected by `SDO_DB`). The command reads local files only.
It neither checks websites nor changes the database. Save its output when
preparing a data release. `list_states` and `describe_source` expose the same
review reminders and publication/loading distinctions.

## Review schedule

These are this project's maintenance intervals, not agency release promises.
Check sooner when an agency announces a revision or a source check fails.

| State | Review every | What needs separate attention |
| --- | --- | --- |
| Arizona | 90 days | Three scenarios and components |
| California | 30 days | Population, households, jobs; replaced files |
| Colorado | 30 days | Population, households, jobs; autumn updates |
| Florida | 90 days | Population workbook and household/jobs PDFs |
| Georgia | 90 days | OPB edition and county workbook |
| Illinois | 90 days | IDPH edition/release, April/July base columns and Table 1/Table 3 differences; Chicago, five-year components, households and eligible jobs |
| Indiana | 90 days | IBRC edition, POST query, state/county bases and horizons; separate regional, labor-force, household and economic products |
| Kentucky | 90 days | KSDC population/household editions, Census anchor and estimate inputs, age/sex codebook and county codes; regional, place, projected components and eligible jobs coverage |
| Maryland | 90 days | Workbook/catalog date mismatch; Census anchor and auxiliary inputs; separate preliminary jobs vintage; Baltimore City/county codes, regions, municipalities and projected components |
| Michigan | 90 days | MCDA state/county editions, workbook codes, base years and scenarios; regional, place, household, components and eligible jobs coverage |
| Minnesota | 90 days | State/county files and projected launch year |
| North Carolina | 90 days | Edition, base year, and components |
| Oregon | 30 days | Every regional/county edition and exclusions |
| Pennsylvania | 90 days | PaSDC edition, estimate labels, state components PDF; place, household and eligible jobs coverage |
| Tennessee | 90 days | Boyd Center releases and county detail service |
| Texas | 90 days | Edition, scenarios, and regional products |
| Utah | 90 days | Gardner baseline and separate High/Low scenario workbooks; no base year stated |
| Virginia | 90 days | Cooper Center population workbook, methodology, independent-city rows, and separate town product |
| Washington | 90 days | State, GMA population, GMA components, economic PDF |
| Wisconsin | 90 days | DOA population and household workbooks; separate subcounty products and household edition date |

The expansion snapshot checks below describe what is loaded and what remains
uncertain. They are evidence about the saved files, not completed review dates;
the manifests retain each file's retrieval date and fingerprint.

| State and agency evidence | Loaded coverage in this checkout | Known limits and uncertainty |
| --- | --- | --- |
| [Maryland — Department of Planning](https://planning.maryland.gov/MSDC/Pages/s3_projection.aspx) | November 2025 population/households through 2055; preliminary October 2022 jobs through 2050. State and all 24 county equivalents, 2020 history plus five-year projections (575 totals) | Catalog population/household date lags the files. Baltimore City is separate from Baltimore County. Regional totals are archived only; municipalities and projected components remain unverified |
| [Illinois — IDPH](https://dph.illinois.gov/data-statistics/public-data-assets/illinois-population-projections.html) | 2023 edition, released May 2024: Table 3 July 2020 estimates and July 2025/2030/2035 projections for the state and all 102 counties (412 totals); base year 2020 | April 2020 Census column excluded. Table 3 state totals exceed Table 1 by 11 in 2025 and 3 in 2030. Chicago, age/sex and five-year components are archived but not loaded. Household and eligible jobs coverage is unknown |
| [Kentucky — KSDC / University of Louisville](https://centers.louisville.edu/kentucky-state-data-center/data-downloads) | Vintage 2022 population and households: 2020 historical totals and five-year projections 2025–2050 for the state and all 120 counties (1,694 totals). Model anchor 2020; last underlying population estimate input 2021 | Age/sex and 15 Area Development Districts are archived but not served; no city/place projections in this edition. Eligible jobs and projected components coverage is unverified |
| [Pennsylvania — PaSDC / Center for Rural Pennsylvania](https://www.rural.pa.gov/data/population-projections) | 2023 population edition: 2020 estimates and five-year projections 2025–2050 for the state and all 67 counties (476 totals); base year 2020, from Census Vintage 2022 | Age/sex detail is archived but not served. State components appear as five-year period totals in methodology Table 3 and are not loaded. Place, household, eligible jobs and county components coverage is unverified |
| [Michigan — MCDA](https://www.michigan.gov/mcda/population) | Vintage 2024 population totals: six five-year points 2025–2050 for the state and all 83 counties (504 totals), all projections, retaining source decimals. State estimate base is 2022 | County base year is not explicitly identified and remains null. State main net-positive-migration scenario is loaded; illustrative zero-migration scenario is not loaded. Ten prosperity regions and age/sex detail are archived but not served. Place, household, eligible jobs and complete components coverage is unverified |
| [Indiana — IBRC/STATS Indiana](https://www.stats.indiana.edu/topic/projections.asp) | July 2024 population edition: 2020 estimates and five-year projections from 2025, state through 2060 and all 92 counties through 2050 (653 totals); last underlying estimate year 2023 | State population anchor 2020 with estimates/components through 2023; county model starts from 2023 estimates. Neither table contains a 2023 row. County sums differ from state by 55–130 in projection years. Cities have no projections; metro/age/sex products are not loaded; household, jobs and components status is unknown |
| [Virginia — Cooper Center](https://www.coopercenter.org/virginia-population-projections) | Population for the state and 133 county-equivalent localities (95 counties + 38 independent cities), six publisher-provided points in 2030–2055; base year 2024 | Large-town and age/sex products are published but not loaded; household, employment, and components publication status is unknown |
| [Wisconsin — DOA](https://doa.wi.gov/Pages/LocalGovtsGrants/Population_Projections.aspx) | Population and households for the state and 72 counties at 2020, 2030, 2040, and 2050; base year 2020 | Minor-civil-division and municipal products are published but not loaded; household workbook has no edition date; employment/components status is unknown |
| [Utah — Gardner Policy Institute](https://gardner.utah.edu/utah-demographics/population-projections/utah-2065-long-term-vintage-2025/) | Baseline population, households, total jobs, births, deaths, and net migration for the state and 29 counties annually from 2025–2065; base year is not stated | High/Low scenario workbook contains totals for 2030–2065 but is not loaded and contains no components; subcounty estimates are a separate product, not forecasts |

The three expansion-state snapshots were checked for format, workbook shape,
and adapter fixture values during the September 22, 2026 build. That check did
not cover every product on each agency landing page, so it is not recorded as a
completed source review in `src/sdo_mcp/source_reviews.json`.

Indiana's population tables and supporting pages were checked on September 28,
2026. The original HTML, exact POST form, retrieval dates, and fingerprints are
saved in `data/raw/in/`. The adapter validates the table header, Census county
names, every geography/year pair, numeric values, and the estimate footnote.
HTTP success or an arbitrary HTML body does not pass validation. Its acquire
command reuses validated saved responses because live pages contain generation
timestamps; new editions require new filenames. Other products were not fully
audited, so Indiana also has no completed source-review date.

Michigan's workbook, state report, county methodology, county release page,
and download catalog were checked on September 29, 2026. Originals and their
fingerprints are saved in `data/raw/mi/`. The adapter validates the sheet,
column names, geography codes and names, complete geography/year grid, and
finite nonnegative numbers before accepting the source. The file contains
564 rows: 504 state/county totals are loaded and 60 prosperity-region rows are
retained only in the original. These regions are not Census metro areas.
Published county totals differ from the state by at most 0.03 persons;
the adapter preserves both. The state report explicitly names its 2022 base,
but the county methodology does not explicitly name a county population base.
No completed source-review date is recorded because the other products have
not been fully audited. Reacquisition reuses validated originals; new editions
require new filenames and metadata.

Pennsylvania's original workbook, methodology report, release notice, and
download catalog were checked on September 29, 2026, and saved with fingerprints
in `data/raw/pa/`. The workbook is dated September 5, 2023; the release notice is
October 4, 2023, and the methodology is December 2023. The adapter checks the
edition date, 2020 estimate base note, year/type headers, Census codes and names,
complete geography/age grid, and nonnegative integer values. It serves published
totals directly, and county sums match the state at all seven dates. Fixtures
were cross-checked against the report's Table 4. No annual values are generated.
Philadelphia remains a county geography. Other products have not been fully
audited, so no completed source-review date is recorded. Reacquisition reuses
validated originals; a new edition requires new filenames and metadata.

Kentucky's two original workbooks, codebook and catalog were checked on
September 29, 2026, and archived in `data/raw/ky/`. The adapter validates
headers, county codes and names, complete age/sex and geography grids, numeric
totals, and supporting evidence. It aggregates population across the 36
published age/sex rows and reads household totals directly from the separate
workbook. Household county codes need the Kentucky prefix; population county
codes already include it. County sums match the state for both products.
The [August 2022 report](https://louisville.widen.net/s/qlgpqnkcdd/projection-report-2022)
was also reviewed: pages 9–11 identify the 2020 Census anchor and household
method, and page 13 confirms state totals. That 140 MiB report is linked,
not archived in Git. The catalog additionally identifies 2021 Population
Estimates as base inputs. `base_year=2021` records this last underlying
population estimate year for the edition, including the population inputs
used to project households; it does not replace the 2020 Census or household
anchor or create a 2021 row. Historical 2020 totals use the MCP `estimate`
label, while all 2025–2050 points remain projections. Regional and city
geographies are never substituted. Other products were not fully audited, so
no completed source-review date is recorded. Reacquisition reuses validated
originals; a new edition requires new filenames and metadata.

Illinois's original 132-page IDPH report and two catalogs were checked on
September 29, 2026, and archived in `data/raw/il/`. The report cover establishes
the 2023 edition and May 2024 release; methods page 1 establishes IDPH authorship
for the state's Certificate of Need program and the July 2020 estimate base.
The catalogs link this edition and older products; no successor was identified.
No explicit data license or redistribution restriction was identified in these
reviewed products; attribution to IDPH is retained.

The adapter extracts Table 3 directly from the original PDF: printed pages
8–10, PDF pages 11–13. All three pages were rendered and inspected, including
state, Cook, Hardin, DeWitt, Jo Daviess, St. Clair and Woodford fixtures. It
checks the title, reference dates, estimate/projection headers, 102-county
roster, integer values, source footnote and complete four-year grid. Source
DeWitt is explicitly mapped to Census De Witt County (17039); the saved
Census-2020 reference remains unchanged. April 1, 2020 Census counts are
excluded in favor of the July 1 estimate column. Table 3 county sums equal
its own published state totals. Table 1's state totals are 11 lower in 2025
and 3 lower in 2030; the adapter uses Table 3 consistently and preserves this
documented discrepancy instead of adjusting published values.

Chicago is separately published in Table 2 and returns `not_loaded`; Cook
County is never substituted. Tables A-2, A-4 and A-5 contain five-year births,
deaths and net migration, recorded as `pdf_only` pending checked component
extraction. Household and eligible IDPH jobs coverage remains unknown.
The separate [IDES industry and occupational projections](https://ides.illinois.gov/resources/labor-market-information/employment-projections)
are outside this project's employment scope. No completed source-review date
is recorded because the broader household/jobs audit remains open. Repeat
acquisition validates and reuses saved files without changing retrieval dates.

Maryland's three original workbooks, projection catalog and population
methodology were checked on September 29, 2026, and archived in `data/raw/md/`.
Population and households are dated November 2025 in the files and their
preparation footnotes, although the catalog still says October 2025. The
separate total jobs by place of work workbook is revised October 2022; the
catalog labels it preliminary. It explicitly credits MDP for 2025–2050
projections and BEA CA25/CA25N for historical data. It qualifies as an SDO jobs
product and is not a labor-force or occupational projection series.

The adapter serves 2020 history and five-year points from 2025, through 2055
for population/households and 2050 for jobs: 575 observations in total. The
2020 Census counts use the MCP `estimate` label. `base_year=2020` is the last
historical observation in each table; the population methodology describes
a 2020–2055 model span but does not date the latest auxiliary rate inputs.
All later points retain the `projection` label regardless of retrieval date.
Households come from the household-count workbook, not household population.

It validates workbook identity, edition, year headers, source footnotes,
the full Census county roster, finite nonnegative integer values and exact
county/state reconciliation. The first table supplies levels; subsequent
change and growth-rate tables are excluded. State and Baltimore City/county
fixtures were cross-checked against the matching publisher PDFs, page 1:
[population](https://planning.maryland.gov/MSDC/Documents/popproj/TotalPopProj.pdf),
[households](https://planning.maryland.gov/MSDC/Documents/popproj/HouseholdProj.pdf),
and [jobs](https://planning.maryland.gov/MSDC/Documents/projection/Jobs/Summary_TotalJobs.pdf).
Baltimore City is county equivalent 24510, separate from Baltimore County
24005. Six regional totals and history before 2020 remain archived only.
Municipal and projected components publication coverage has not been fully
audited and remains unknown. No completed statewide review date is recorded.
Repeat acquisition validates and reuses saved originals without changing
their retrieval dates; new editions require new filenames and metadata.

Database validation rejects a population, household or employment series
that mixes source IDs across years. Different geographies, variables and
scenarios may still use separate products. This prevents a returned series
from attributing mixed editions to its first observation's source.

The report supplies each state's existing agency links and the exact source
editions and retrieval dates in the selected database. `current_vintage` in
the existing tools remains hand-curated background information; it is not a
live claim about the agency's newest release.

## Recording a review

`src/sdo_mcp/source_reviews.json` is a committed review log with one latest
review per state. It currently remains empty: a snapshot download, adapter
validation, or a check of only one product does not establish that all of a
state's products are current. Missing reviews show `never_reviewed` and need an initial review;
they do not acquire a fabricated date. Once recorded, a review is `due` on
its review date plus the interval above. `not_due` means only that the next
scheduled check has not arrived, not that an edition is guaranteed current.

For each review:

1. Follow the agency links and check each product listed in the state's
   review focus. Oregon needs a county-by-county edition check; Washington
   state and GMA products have independent editions.
2. Compare the published edition, base year, horizon, scenarios, and file
   contents with the loaded sources. Keep publication and retrieval dates
   separate. A successful web response alone proves nothing: downloaded
   files must parse as the expected format. An unchanged URL does not prove
   unchanged contents.
3. Record the date, evidence links, and findings for every product. Say which
   editions are published, which are loaded, and what remains unresolved.
   If a check is blocked or incomplete, leave the completed-review date
   unchanged and record the failed attempt in local planning notes.
4. Add new originals and their fingerprints/retrieval dates to `data/raw/`
   through the existing snapshot process. Never overwrite archived originals.
   Validate any adapter changes, rebuild, compare the results, and prepare a
   release separately. Recording a review does not update served numbers.

Entry shape (replace all placeholders with verified facts):

```json
{
  "WA": {
    "reviewed_on": "YYYY-MM-DD",
    "evidence": ["official product page URL", "official file URL"],
    "findings": "State: published edition ...; loaded ... . GMA population: ... . GMA components: ... . Economic PDF: ... . Remaining work: ... ."
  }
}
```

Keep earlier reviews in Git history. Review findings describe the database
examined at that time; the live inventory always describes the selected copy.
No automatic website checker or background scheduler is installed by this step.

## Delaware batch-one source check

The [Delaware Population Consortium catalog](https://stateplanning.delaware.gov/demography/dpc-projection-data.shtml)
links the original October 14, 2024 `.xls` report. The
[edition page](https://stateplanning.delaware.gov/demography/dpc-projection-info.shtml)
says the Consortium readopted that edition in 2025 without new projections.
Both pages and the workbook were retrieved September 30, 2026, and archived
with SHA-256 fingerprints in `data/raw/de/`.

The report's top-line state and three county tables publish 2020 history and
2025-2050 five-year forecasts for resident population, household counts, and
jobs by place of work. All three variables are loaded; the county rows add to
each state row exactly. The last historical point **in these summary tables**
is 2020, recorded as `base_year=2020`. Later known inputs may inform the model,
so that field does not claim all model inputs stopped in 2020. The jobs row is
the DPC's own place-of-work series, distinct from labor force and employed
residents. Municipal and seasonal products are published separately and are
not loaded. Other product coverage remains unknown; this is not a completed
statewide review.

## Reading the status

`status` retains the publication facts: `available`, `pdf_only`,
`state_level_only`, or `not_published`. The separate `load_status` reports
`loaded`, `partially_loaded`, or `not_loaded` from the selected database.
An absent series never turns a published product into “not published.”

`loaded` means queryable total rows exist, not that every year, county, or
scenario is present. For components, all three variables must have totals;
otherwise the entry is `partially_loaded`. `loaded_series` lists row counts,
year bounds, and source IDs separately for each variable/source. Counts are
observations, not counties or distinct years. Year bounds do not promise
continuous annual data; Washington county components are five-year totals.
Demographic detail rows that the tools cannot serve do not count as totals.
Use individual forecast requests and source caveats to assess specific coverage.

Washington components now have loaded state and county totals. Washington
state employment remains a published PDF without loaded numbers. Virginia's
large-town product and Wisconsin's subcounty products are published but not
loaded. Utah's baseline components are loaded, while its separate High/Low
workbook contains totals only and remains not loaded. Other published gaps,
including Florida PDF products, remain visible in the report; this monitoring
step does not fill them or select the next expansion states.
