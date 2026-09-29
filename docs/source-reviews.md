# Source reviews and loading status

Run `uv run python -m sdo_mcp.monitoring --database data/sdo.sqlite`
for a JSON report of all 17 states. Omit `--database` to inspect the installed
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
| Indiana | 90 days | IBRC edition, POST query, state/county bases and horizons; separate regional, labor-force, household and economic products |
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
