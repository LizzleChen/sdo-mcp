# State-by-state notes

Detailed caveats for the states added most recently, newest first. They explain
which edition was chosen, where published numbers disagree with each other,
and what is deliberately left out. These notes were written as each batch was
added, so counts such as "49 with loaded population projections" describe the
database at that time.

For any state, the `describe_source` tool gives the full, current sourcing
story, and [source-reviews.md](source-reviews.md) lists open questions and the
review schedule.

## Batch five: Arkansas, Iowa, Louisiana, Oklahoma, Vermont, West Virginia (and Montana)

Coverage now includes **50 recognized states, 49 with loaded population
projections**. Batch five adds **Arkansas, Iowa, Louisiana, Oklahoma, Vermont,
and West Virginia**, with 9,353 published population points. Montana is
recognized with source findings, but no forecast is loaded while its current
commercial source's edition, redistribution permission and complete export
remain unresolved. Montana requests return `coverage_unknown`.

| State | Published points served | Geography coverage |
| --- | --- | --- |
| Arkansas | 1980–2013 estimates; annual 2014–2065 projections from the recovered February 2015 edition | State and all 75 counties; original fractional forecast values |
| Iowa | 1980 Census history; five-year projections 1985–2000 from the archival July 1984 state-demographer report | State and all 99 counties; the entire forecast horizon is past |
| Louisiana | 2005 estimates; five-year projections 2010–2030 from the state-commissioned 2009 LSU edition | State and all 64 parishes, Middle/Low/High migration scenarios; estimate inputs differ by parish |
| Oklahoma | Five-year projections 2025–2070 from Commerce's March 2023 report; last estimate input unconfirmed | State and all 77 counties; ambiguous historical columns remain unloaded |
| Vermont | State: 2030/2040/2050 from the adopted March 2025 housing assessment; counties: 2010 Census history and 2020/2030 projections from August 2013 | Newer statewide current-trends population; all 14 counties with older A/B migration scenarios |
| West Virginia | 2020 Census history; five-year projections 2025–2040, October 2022 edition | State and all 55 counties; every selected total matches the companion age/sex tables |
| Montana | No selected serveable edition | Metadata only; current eREMI authority, rights and export checks remain open |

These are source editions, including older forecasts, rather than a promise of
current forecasts for every state. Iowa ends in 2000; its newer December 1989
state-agency edition remains unrecovered. Arkansas and Louisiana use archived
originals whose successor searches remain open. Past projection years retain
projection labels. Oklahoma, Vermont's newer state product and West Virginia
have a null `base_year` because the last underlying estimate input is unstated.
No year is interpolated and no forecast is extended beyond its published horizon.

Vermont's state totals sum 18 exhaustive published age cells, checked against
the original chart and an independent extraction. Its state and county editions
have different scenario meanings, defaults and horizons. `list_states` exposes
`scenario_settings_by_geo` for these products. For example:
`get_forecast(state="VT", geo_level="state", geo="VT", variable="population")`
selects `current_trends`; a county request defaults to `b`, this server's choice
for the older 2000–2010 migration assumptions. The publisher names no preferred
county scenario. Housing targets are not served as household forecasts.
Louisiana's consistent Middle default is also a server choice; it does not
splice the publisher's geographically varying scenario recommendations.

Published source discrepancies remain visible. Louisiana's Jefferson Davis
2030 Middle workbook value is 29,720, while its report gives 29,190. West
Virginia's Roane 2035 combined total is 12,173, one less than its sex totals.
Independent county/state rounding differences in Iowa and Oklahoma remain
unchanged. No household or jobs series is added in this batch. Municipal,
regional and demographic detail remains deferred or unverified as documented
in the [source checks and limitations](source-reviews.md). Broad product
reviews remain `never_reviewed`.

## Batch four: Idaho, Kansas, North Dakota, South Dakota, Mississippi, Missouri

Batch four added **Idaho, Kansas, North Dakota, South Dakota,
Mississippi, and Missouri**, with 3,354 published population points. Kansas's
selected official county forecast ends in 2021; loading an old forecast does
not extend its horizon.

| State | Published points served | Geography coverage |
| --- | --- | --- |
| Idaho | Annual projections 2024–2034, revised August 2025; last estimate year unconfirmed | State and all 44 counties |
| North Dakota | 2020 Census history; five-year projections 2025–2050, 2024 edition | State and all 53 counties |
| South Dakota | 2010 Census history; five-year projections 2015–2035, 2012 Medium Series | State and all 66 source-era counties, including Shannon County under historical FIPS 46113 |
| Mississippi | Five-year projections 2020–2050, preliminary May 2019 edition with a 2010 launch | State only; county and place data are offered on request and remain unloaded |
| Missouri | 2000 Census history; five-year projections 2005–2030, March 2008 Preferred Series | State, all 114 counties and independent St. Louis city |
| Kansas | Annual projections 2010–2021, official November 2006 product published in January 2010; last estimate year unconfirmed | All 105 counties; no statewide total is derived. CEDBR's newer product has unconfirmed official demographic status |

These additions preserve the source editions, even where their projection years
are now past. Idaho's and Kansas's `base_year` is null. Missouri's last
estimate input is 2007, while its 2005 point is explicitly a projection. South Dakota retains
fractional workbook values and the original Shannon County name and code;
modern Oglala Lakota identifiers are not substituted. North Dakota's selected
table gives 957,194 for 2050, while its catalog and executive summary give
957,124; the discrepancy is recorded. No new household or jobs series is loaded.
See the [source checks and limitations](source-reviews.md).

## Batch three: Connecticut, Massachusetts, New Jersey, New York, Rhode Island

Batch three added **Connecticut, Massachusetts, New Jersey,
New York, and Rhode Island**, with 2,277 published population points. Illinois,
the sixth state in the batch plan, was already loaded.

| State | Published points served | Geography coverage |
| --- | --- | --- |
| Connecticut | Five-year projections 2015–2040; revised 2017/2018 edition with a 2010 Census anchor | State, eight historical counties and nine separately identified regional councils of government |
| Massachusetts | Adjusted 2020 historical launch; five-year projections 2025–2050, Vintage 2024 | State and all 14 counties |
| New Jersey | 2014 estimate; 2019, 2024, 2029 and 2034 projections from the older 2014–2034 series | State with four models; all 21 counties under the preferred model |
| New York | 2022 estimate and annual state projections through 2050, October 2024 edition; separate 2018 county edition from 2015 through 2040 | State with Middle/High/Low scenarios; all 62 counties with one series |
| Rhode Island | Five-year projections 2025–2050, revised February 2026; base year unconfirmed | Published state Total row and all 39 cities/towns |

Rhode Island municipalities use `geo_level="county_subdivision"` and ten-digit
Census GEOIDs. For example:
`get_forecast(state="RI", geo_level="county_subdivision", geo="Providence", variable="population")`.
Connecticut's historical counties retain their old FIPS codes; the 2018
councils use `geo_level="cog"` and separate IDs. Their values are never remapped
to modern county-equivalent planning regions. New York and New Jersey scenarios
apply only to their state products. New York's Middle default is this server's
central choice; Cornell does not recommend a scenario.

These additions serve exact publisher values, including fractional Massachusetts
historical and New York forecast cells. Past projection years retain projection
labels. Rhode Island's table does not confirm its last underlying estimate year,
so `base_year` is null. New York state/county editions and New Jersey's 2029
state/county discrepancy remain separate and visible. No new household or jobs
series is loaded. Other municipal and demographic detail remains deferred; broad
product reviews remain open.

## Batch two: Alaska, Hawaii, Maine, Nebraska, New Hampshire, Ohio, Nevada

Batch two added **Alaska, Hawaii, Maine, Nebraska, New Hampshire, Ohio and
Nevada**, with 1,862 population totals and 20 Hawaii jobs totals:

| State | Published points served | County coverage |
| --- | --- | --- |
| Alaska | 2025 estimate; annual state projections through 2055 under Low/Middle/High, and five-year county points | All 30 boroughs and census areas; county series follows Middle |
| Hawaii | 2020 estimate; 2030, 2040 and 2050 resident population | Three individual counties plus combined Maui/Kalawao |
| Maine | 2022 estimate; 2027, 2032, 2037 and 2042 | All 16 counties |
| Nebraska | 2020 Census history; 2030, 2040 and 2050 | All 93 counties |
| New Hampshire | 2020 Census-based history; five-year projections through 2050 | All 10 counties |
| Ohio | 2020 estimate; five-year projections through 2050 | All 88 counties |
| Nevada | 2024 estimate; annual projections 2025–2044 | All 17 county equivalents, including Carson City |

Hawaii also serves DBEDT's civilian total jobs: 2022 estimates and
2030/2040/2050 projections, including wage/salary and proprietors' jobs.
Use county ID `hi-maui-kalawao` for the combined population or jobs series.
Separate Maui or Kalawao requests return `not_published` for this selected
product; the combined value is never assigned to either county.

The original files and supporting methods are archived with fingerprints and
retrieval dates. Published values and source discrepancies are preserved,
including Hawaii's Maui/Kalawao 2030 workbook/PDF difference and Ohio's Ottawa
2050 map/workbook difference. Nebraska's producer explicitly adopted a
Hauer/SEDAC model; that provenance is visible in its source notes. Maine's
publisher cautions against use beyond 2032. Batch two's municipal forecasts and additional
components remain deferred; household and other eligible jobs coverage is
unverified. No years are interpolated. See the
[source checks and limitations](source-reviews.md) for each edition.

## Wyoming

The preceding addition was **Wyoming**, using the
[Economic Analysis Division's February 2025 population publication](https://ai.wyo.gov/divisions/economic-analysis/demographic-information/projections).
The state and all 23 counties have annual 2020–2050 totals: 2020 Census
history, 2021–2023 estimates, and 2024–2050 forecasts. All 744 loaded values
match the separate publisher PDF. The three abbreviated county names are
matched to Census FIPS. Municipal forecasts are archived but not yet served.

## Alabama

**Alabama** uses the
[CBER/State Data Center county workbook](https://cber.culverhouse.ua.edu/resources/alabama-demographics/).
The state and all 67 counties have a 2025 estimate and five-year projections
from 2030 through 2050. The workbook displays whole-person counts, which are
served without forcing rounded county totals to match the state row. Its Box
filename says Fall 2026 and its file metadata was modified that September;
the older October 2024 footer credit is documented in the source notes.

## South Carolina

**South Carolina** uses
[RFA's Vintage 2023 population projections](https://www.rfa.sc.gov/programs/census-state-liaison-and-data-center/search-and-download-population-data/rfa-population-projections).
The 2023 estimate and annual 2024-2043 projections cover the state and all 46
counties. Every displayed forecast total matches the publisher's separate
age-group workbook. County sums differ from state totals by up to five people
because of rounding, so both published values are preserved.

## New Mexico

**New Mexico** uses
[UNM Geospatial and Population Studies' Spring 2024 projections](https://gps.unm.edu/pop/population-projections.html).
The state and all 33 counties have a 2020 Census historical total and
five-year projections from 2025 through 2050. The model's last stated estimate
input is 2022. The archived workbook and companion PDF agree on the loaded
values; the HTML page has a Santa Fe 2030 typo. Publisher state and county
values are retained even where independent rounding makes their sums differ.

## Delaware

**Delaware** uses the
[Delaware Population Consortium's 2024 tables](https://stateplanning.delaware.gov/demography/dpc-projection-data.shtml),
which were readopted in December 2025. The state and all three counties have
five-year population, household-count, and jobs-by-place-of-work totals from
2020 through 2050. The 2020 historical rows are labelled estimates; 2025 onward
are projections. Municipal and seasonal population products are published but
not loaded. The original `.xls` workbook and adoption pages are archived.

## Maryland

The preceding addition was **Maryland**, using
[Maryland Department of Planning projections](https://planning.maryland.gov/MSDC/Pages/s3_projection.aspx):
575 population, household and employment totals for the state and all 24
county equivalents (23 counties and Baltimore City). Population and households
use the November 2025 edition through 2055. Preliminary jobs by place of work
use a separate October 2022 edition through 2050. Each series starts with 2020
history, labelled estimate, followed by five-year projections from 2025.
The base year is 2020; no annual values are generated.
For example:
`get_forecast(state="MD", geo_level="county", geo="Baltimore City", variable="population")`.
Baltimore City (24510) is distinct from Baltimore County (24005). Original
workbooks, catalog and methodology are archived with retrieval dates and
fingerprints. Municipal and projected components publication coverage remains
unverified; those requests return `coverage_unknown`.
