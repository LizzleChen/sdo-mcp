# Source reviews and loading status

Run `uv run python -m sdo_mcp.monitoring --database data/sdo.sqlite`
for a JSON report of all 11 states. Omit `--database` to inspect the installed
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
| Minnesota | 90 days | State/county files and projected launch year |
| North Carolina | 90 days | Edition, base year, and components |
| Oregon | 30 days | Every regional/county edition and exclusions |
| Tennessee | 90 days | Boyd Center releases and county detail service |
| Texas | 90 days | Edition, scenarios, and regional products |
| Washington | 90 days | State, GMA population, GMA components, economic PDF |

The report supplies each state's existing agency links and the exact source
editions and retrieval dates in the selected database. `current_vintage` in
the existing tools remains hand-curated background information; it is not a
live claim about the agency's newest release.

## Recording a review

`src/sdo_mcp/source_reviews.json` is a committed review log with one latest
review per state. It starts empty: earlier downloads and the Washington
component validation do not establish that all of a state's products are
current. Missing reviews show `never_reviewed` and need an initial review;
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
state employment remains a published PDF without loaded numbers. Other
published gaps, including Florida PDF products, remain visible in the report;
this monitoring step does not fill them or select the next expansion states.
