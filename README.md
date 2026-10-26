# SDO Forecast MCP

This is an MCP server (Model Context Protocol, a standard way for AI
assistants to use outside tools). It is a convenient one-stop source of state
demographic forecasts that you can use from your preferred AI assistant or
large language model (LLM) app. Ask how many people a US county is expected to
have in 2050, and get the official state forecast, with its source attached.

> **Check the numbers yourself.** The data may be out of date or wrong. States
> publish new editions without notice, files can change, and mistakes can slip
> in when this project collects and converts them. Treat every answer as a
> starting point, not a final figure. Before you rely on a number, confirm it
> with the original source or with the state's demography office. The Census
> Bureau lists each state's contacts on its
> [FSCPE contacts page](https://www.census.gov/programs-surveys/popest/about/fscpe/contacts.html)
> (Federal-State Cooperative for Population Estimates).

Population forecasts for counties and cities don't come from the federal
government. Each state has its own State Demography Office (SDO), often called
the "state demographer", that publishes them. Each one uses a different website, file format, set of
geographies and timeline. This server gathers those forecasts into one place
and answers questions about them in the same way for every state. It works
with Claude and other apps that support MCP.

- **49 states loaded**: population forecasts for all of them, plus households,
  jobs, or births, deaths and migration where the state publishes them.
- **Honest answers**: every number says whether it is a measured estimate or a
  forecast, and which agency and edition it came from. If a state doesn't
  publish something, the server says so instead of guessing.
- **Runs on your computer**: the data comes inside the package. Nothing is
  downloaded while you ask questions.

## Get started

**1. Install uv**, a small tool that installs Python programs. Follow
[uv's install guide](https://docs.astral.sh/uv/getting-started/installation/).

**2. Download and install the server.** Releases are in a private GitHub
repository, so you need access to it and the
[GitHub CLI](https://cli.github.com/) signed in (`gh auth login`). Then run:

```sh
gh release download --repo LizzleChen/sdo-mcp --pattern '*.whl'
uv tool install --force ./sdo_mcp-*.whl
uv tool update-shell
```

Open a new terminal window afterwards so it can find the `sdo-mcp` command.

**3. Connect it to your AI app.**

- **Claude Code:** run `claude mcp add sdo-forecast -- sdo-mcp`
- **Claude Desktop or another MCP app:** add this to the app's MCP settings
  file:

  ```json
  { "mcpServers": { "sdo-forecast": { "command": "sdo-mcp" } } }
  ```

Restart the app. You should see four new tools from `sdo-forecast`.

**To update**, repeat step 2 with the newer release.

### Or run it with Docker

If you use [Docker](https://www.docker.com/), you can skip uv and Python. Each
release also publishes an image with the same data. The repository is private,
so sign in first with a GitHub token that can read packages:

```sh
docker login ghcr.io -u YOUR_GITHUB_USER
docker pull ghcr.io/lizzlechen/sdo-mcp:latest
```

Then use this in your app's MCP settings:

```json
{
  "mcpServers": {
    "sdo-forecast": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "--network", "none", "ghcr.io/lizzlechen/sdo-mcp:latest"]
    }
  }
}
```

The server never needs the internet, so `--network none` is safe.

## What you can ask

Just ask in plain language. For example:

- "What is the projected 2050 population of Douglas County, Colorado?"
- "Which states publish household forecasts?"
- "Show Texas's low, mid and high population scenarios for Harris County."
- "Does Colorado's state demographer publish a jobs forecast?"
- "Births, deaths and migration for King County, Washington."
- "Where does Utah's forecast come from, and how old is it?"

Behind the scenes, the assistant uses four tools:

| Tool | What it does |
| --- | --- |
| `list_states` | What each state publishes, and what is loaded here. A good place to start. |
| `get_forecast` | Population, household or jobs numbers for a state, county or other area, year by year. |
| `get_components` | Births, deaths and net migration, where the state publishes them. |
| `describe_source` | The full story for one state: agency, edition, method, caveats and links. |

## What's covered

Every state below has population forecasts for the state and all its counties
unless noted. "Forecast years" runs from the first forecast year to the last
year in the edition.

| State | Also includes | Areas | Forecast years |
| --- | --- | --- | --- |
| Alabama | | | 2030–2050 |
| Alaska | Low/middle/high (state) | Boroughs and census areas | 2026–2055 |
| Arizona | Births, deaths, migration; low/medium/high | | 2026–2060 |
| Arkansas | | | 2014–2065 |
| California | Households, jobs, births, deaths, migration | | 2025–2070 |
| Colorado | Households, jobs, births, deaths, migration | | 2025–2060 |
| Connecticut | | Historical counties and 9 regional councils | 2015–2040 |
| Delaware | Households, jobs | | 2025–2050 |
| Florida | Low/medium/high | | 2030–2050 |
| Georgia | | | 2026–2065 |
| Hawaii | Jobs | Maui and Kalawao combined | 2030–2050 |
| Idaho | | | 2024–2034 |
| Illinois | | | 2025–2035 |
| Indiana | | | 2025–2060 |
| Iowa | | Older edition | 1985–2000 |
| Kansas | | Counties only; older edition | 2010–2021 |
| Kentucky | Households | | 2025–2050 |
| Louisiana | Low/middle/high | Parishes | 2010–2030 |
| Maine | | | 2027–2042 |
| Maryland | Households, jobs | Includes Baltimore City | 2025–2055 |
| Massachusetts | | | 2025–2050 |
| Michigan | Alternative migration scenario | | 2025–2050 |
| Minnesota | Births, deaths, migration | | 2024–2075 |
| Mississippi | | State only | 2020–2050 |
| Missouri | | Includes St. Louis city | 2005–2030 |
| Montana | Not loaded yet: the source's edition and sharing rights are unresolved | | |
| Nebraska | | | 2030–2050 |
| Nevada | | | 2025–2044 |
| New Hampshire | | | 2025–2050 |
| New Jersey | Four model variants (state) | | 2019–2034 |
| New Mexico | | | 2025–2050 |
| New York | Low/middle/high (state) | | 2016–2050 |
| North Carolina | | | 2025–2060 |
| North Dakota | | | 2025–2050 |
| Ohio | | | 2025–2050 |
| Oklahoma | | | 2025–2070 |
| Oregon | | 35 counties only; no state total | 2023–2076 |
| Pennsylvania | | | 2025–2050 |
| Rhode Island | | 39 cities and towns | 2025–2050 |
| South Carolina | | | 2024–2043 |
| South Dakota | | | 2015–2035 |
| Tennessee | | | 2023–2070 |
| Texas | Low/mid/high | Also metro areas, regional councils, TxDOT districts | 2025–2060 |
| Utah | Households, jobs, births, deaths, migration | | 2025–2065 |
| Vermont | Scenarios differ for state and counties | | 2020–2050 |
| Virginia | | Counties and independent cities | 2030–2055 |
| Washington | Births, deaths, migration; low/medium/high | | 2025–2050 |
| West Virginia | | | 2025–2040 |
| Wisconsin | Households | | 2030–2050 |
| Wyoming | | | 2024–2050 |

Some states' newest available forecast is old. Iowa's ends in 2000 and
Kansas's in 2021. Those years are still labelled as forecasts, and nothing is
extended past the year the state stopped. Cities, towns and age/sex/race detail
are mostly not loaded yet.

For edition choices and known quirks, see the
[state-by-state notes](docs/state-notes.md) and
[source reviews](docs/source-reviews.md).

## Reading the answers

- **Estimate or projection.** Every number is marked `estimate` (based on
  counts of what already happened) or `projection` (a forecast). The
  `base_year` is the last year the forecast was built from real counts. It is
  blank when the state doesn't say.
- **Scenarios.** Some states publish more than one forecast, such as low,
  medium and high growth. If you don't pick one, the server uses a stated
  default and tells you which one it used.
- **Sources.** Each answer names the agency, edition, retrieval date and a
  link, so you can check the original.

When the server can't give numbers, it explains why instead of guessing:

| Status | Meaning |
| --- | --- |
| `ok` | Here are the numbers. |
| `error` | Something in the question didn't match, such as a misspelled county or a reversed year range. |
| `empty_range` | The series exists, but not for those years. The answer gives the years that are available. |
| `not_published` | The state does not publish this. |
| `not_loaded` | The state publishes this, but it isn't in this server yet. |
| `pdf_only` / `state_level_only` | The state publishes it only as a PDF, or only for the whole state. |
| `coverage_unknown` | It isn't yet known whether the state publishes this. |

The server never fills gaps: it won't estimate between published years, borrow
a number from a larger area, or swap in another agency's product. Population
and jobs forecasts usually come from different agencies. This server only
carries a jobs forecast when the state demography office publishes one itself.

## Troubleshooting

- **`sdo-mcp: command not found`.** Open a new terminal window, or run
  `uv tool update-shell` again.
- **The app can't start the server, but the terminal can.** Some desktop apps
  don't search the same folders as your terminal. Run `uv tool dir --bin` to
  see the folder, then use the full path as the `command`, such as
  `/Users/you/.local/bin/sdo-mcp`.
- **"Forecast database is missing".** Reinstall the release (step 2). If you
  set `SDO_DB`, check that it points to a real file.
- **Using a different database.** Set `SDO_DB` to its path, for example
  `SDO_DB=/path/to/sdo.sqlite sdo-mcp`.

## Next steps

- **Confirm the data sources.** Go through each state's source one by one and
  check that it is the right agency, the newest edition, and that our copy
  matches what the state publishes. Record what was checked and when.
- **Create a data retrieval and refresh routine.** Set up a repeatable process
  that fetches each state's files on a schedule, spots new editions or changed
  numbers, and rebuilds the data for a new release. Today this is done by hand.

## For maintainers

Rebuilding the data from the saved state files, running the checks and
publishing a release are covered in [DEPLOYMENT.md](DEPLOYMENT.md).
