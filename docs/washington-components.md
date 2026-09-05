# Washington components of population change

Verified September 5, 2026 against the original Office of Financial Management
(OFM) workbooks. Both files are preserved in `data/raw/wa/`; the manifest records
their original retrieval dates and SHA-256 file checks. Rebuilds need no download.

| Product | Periods served | Estimate/projection boundary | Scenario |
|---|---|---|---|
| November 2025 state components | Annual, 2010–2011 through 2049–2050 | Estimates through ending year 2025; projections from 2026 | Single series |
| 2022 GMA county components, tables dated March 2023 | Five-year totals, 1960–1965 through 2045–2050, all 39 counties | Estimates through ending year 2020; projections from period 2020–2025 | Medium only |

Sources: [state forecast](https://ofm.wa.gov/data-research/population-demographics/forecasts-projections/state/)
and [2022 county projections](https://ofm.wa.gov/data-research/population-demographics/forecasts-projections/growth-managment-act/2022-projections/).
The original downloads are `stfc_2025_components.xlsx` and
`gma_2022_components_med.xlsx`; full download URLs are in the manifest.

`get_components("WA", "King", 2025, 2025)` returns 113,170 births, 81,098 deaths,
and 75,990 net migrants for the **entire 2020–2025 period**, not for 2025 alone.
The answer includes `period_start_year=2020`, `period_end_year=2025`, and
`year=2025`. Year filters select period endings. A 2026–2029 request has no
published period ending in that range and returns `empty_range`.
Low/high county component requests return an explicit error; those scenarios
remain available for county population forecasts.

All values are whole-person counts. Negative migration is retained. County
migration is the workbook's published residual net migration: population
change minus births plus deaths. No annual counts are interpolated. State
multi-year subtotals are excluded because they overlap its annual rows.

The county component source has `base_year=2020`, reflecting the last ending
year labeled estimate in that table. The separate county population source
keeps its 2022 base year. Statewide components keep their 2025 base year.
County workbook statewide comparison rows are excluded: they belong to a
different edition from the statewide forecast.

Checks cover the published arithmetic for all 702 county periods and 40 state
periods, state population totals, county coverage, column/period labels, missing
counts, source fingerprints, representative original values, and actual MCP
client responses. No county sum is substituted for the newer statewide product.

To retrieve the component sources explicitly:

```sh
uv run python -m sdo_mcp.ingest.wa --acquire-components
```

An existing filename cannot be replaced with different bytes. A later edition
requires new snapshot names and reviewed source definitions.
