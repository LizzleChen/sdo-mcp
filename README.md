# SDO Forecast MCP

This package serves state demography office forecasts for population,
households, and employment where the state office publishes it. The server
reads a local SQLite database and does not download data while answering a
question.

Coverage now includes **21 recognized states, all with loaded population
forecasts**. The newest addition is **Delaware**, using the
[Delaware Population Consortium's 2024 tables](https://stateplanning.delaware.gov/demography/dpc-projection-data.shtml),
which were readopted in December 2025. The state and all three counties have
five-year population, household-count, and jobs-by-place-of-work totals from
2020 through 2050. The 2020 historical rows are labelled estimates; 2025 onward
are projections. Municipal and seasonal population products are published but
not loaded. The original `.xls` workbook and adoption pages are archived.

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

There is no public package release or hosted database download yet. You can
install a checked compressed database release shared by the maintainer, or
build from the saved source files in this checkout.

Before starting, install [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
and use Python 3.12 or newer. The checked development setup uses Python
3.12.14 with SQLite 3.51.0; `.python-version` pins that version for `uv` in
this checkout. If `uv python install 3.12.14` has no build for your platform,
install that version separately with [pyenv](https://github.com/pyenv/pyenv)
and its required build tools, or use another supported, patched Python 3.12+
interpreter. An installed wheel needs only that supported patched interpreter.

## Install from this checkout

Run these commands from the repository. `uv build` makes the install file and
`uv tool install` puts its two commands in your user tool environment.

```sh
uv build --wheel
uv tool install --force dist/sdo_mcp-*.whl
uv tool update-shell
```

Restart your shell after `uv tool update-shell` if it does not find
`sdo-mcp` immediately. Some desktop MCP clients do not inherit your shell’s
PATH. For those clients, run `uv tool dir --bin` and use the full path to
`sdo-mcp` in the client’s private configuration; the checked-in `.mcp.json`
keeps the portable command name.

The wheel contains the server code and database schema. It does not contain
the large research database or source snapshots.

## Install a compressed database release

Obtain the versioned `.sqlite.gz` file and its `manifest.json` from a trusted
maintainer. Read `sha256` from that manifest and use it in this command:

```sh
sdo-mcp-install-data /path/to/sdo-2026-09-05.sqlite.gz --sha256 PASTE_THE_64_CHARACTER_SHA256_HERE
```

The fingerprint must come from a trusted source. A fingerprint bundled with
an untrusted download does not establish who published it. Installation checks
the compressed file before opening it, limits the expanded size, validates the
database, and replaces the installed copy only after all checks pass. No source
checkout or state workbooks are needed to install this release.

The release contains every observation the current tools can serve, every
source record, and all geography and coverage information. Age, sex, and race
detail remains in the full research database. The release version is retained
in the database's `release_metadata` table and in the accompanying manifest.

## Install the full database

If you already have a working database, install a copy of it with the command
created by the wheel:

```sh
sdo-mcp-install-data /path/to/sdo-mcp/data/sdo.sqlite
```

The command checks that the file is a readable SQLite database, passes SQLite
integrity and foreign-key checks, and has the tables and columns this server
needs. It then validates a temporary copy before replacing the installed copy
in one final step. The source file is never changed.

By default, the installed copy is stored here:

* macOS: `~/Library/Application Support/sdo-mcp/sdo.sqlite`
* Linux and other Unix systems: `$XDG_DATA_HOME/sdo-mcp/sdo.sqlite`, or
  `~/.local/share/sdo-mcp/sdo.sqlite` when `XDG_DATA_HOME` is not set
* Windows: `%LOCALAPPDATA%\\sdo-mcp\\sdo.sqlite`

To make a full database from the saved source files, run this from the
repository instead:

```sh
uv sync --group ingest
uv run python -m sdo_mcp.ingest.build /path/to/sdo-mcp/data/sdo.sqlite
sdo-mcp-install-data /path/to/sdo-mcp/data/sdo.sqlite
```

The build reads `data/raw/` and is offline with respect to the state agencies.
It verifies the fingerprints of every registered input before and after loading.
A failed load or changed fingerprint leaves the existing database untouched.
Successful replacement keeps the old file beside it as
`sdo.sqlite.previous-<unique-id>`; retain or remove these recovery copies as needed.
To recover, install a copy using `sdo-mcp-install-data PATH_TO_RECOVERY_COPY`.
Saved source files cannot be overwritten with different contents. New editions
need new filenames, manifest entries, and an updated `ingest/inputs.json` list.
Reusing a saved file preserves its recorded retrieval date.
With no path, the build command writes the repository artifact at
`data/sdo.sqlite`. It does not use the installed serving location. A different
serving database can always be selected with `SDO_DB`.

## Use it with an MCP client

After installing the wheel and database, run `sdo-mcp` from any folder. The
included `.mcp.json` uses that command name and contains no machine-specific
checkout path. Copy its `mcpServers.sdo-forecast` entry into the client’s
configuration if needed.

To choose a database explicitly for one launch:

```sh
SDO_DB=/path/to/sdo.sqlite sdo-mcp
```

The repository’s saved `.mcp.json` is intended for an installed command. A
developer working directly from the checkout can continue to use:

```sh
SDO_DB=/path/to/sdo-mcp/data/sdo.sqlite uv run python -m sdo_mcp.server
```

after building `data/sdo.sqlite`, or set `SDO_DB` to an installed database.

## Development checks

```sh
uv run pytest
```

The checks rebuild from saved sources, confirm failed builds and changed file
fingerprints preserve the previous database, and compare the compact release
with the full data. They also build a wheel, install it in a fresh environment
outside the checkout, install a verified compressed database, and exercise all
four tools over MCP 2026-07-28 and 2025-11-25 connections. The installation check
needs `uv` and access to its package cache or the package index; state agency
downloads are never needed. GitHub runs the same checks on pushes and pull
requests through `.github/workflows/checks.yml`.

## Tool results

All four tools describe their returned fields and provide both structured data
and a matching JSON text copy. They advertise that they only read local data;
the serving database connection also prevents writes. MCP reports the package
version, while `list_states.database_release` identifies the installed compact
release (`null` for a full build without release metadata).

Forecast and component requests distinguish these outcomes:

| Status | Meaning |
| --- | --- |
| `ok` | The requested observations are returned with their source and estimate/projection labels. |
| `error` | An argument is invalid, such as a misspelled geography level, unknown county, or reversed year range. MCP also marks the result as an error. |
| `empty_range` | The series is loaded, but no observations fall in these years. The answer includes the first and last available years. |
| `not_loaded` | Coverage records say the product is published, but the requested series is absent from this database. |
| `not_published` | The coverage record explicitly says no product is published for this request. |
| `pdf_only` / `state_level_only` | The coverage record describes a publication or geography limitation. |
| `coverage_unknown` | This server has no coverage record for the requested combination and cannot establish publication status. |

Missing-data outcomes are normal answers, not MCP errors. Execution failures
are MCP errors; missing databases include installation guidance without exposing
local file paths. Unknown tool names are protocol errors, separate from tool
results. These distinctions follow the
[MCP tool error rules](https://modelcontextprotocol.io/specification/2026-07-28/server/tools).

## Prepare a database release

After rebuilding the full database, run:

```sh
uv run python -m sdo_mcp.release data/sdo.sqlite --version 2026-09-05
```

This writes `data/releases/2026-09-05/sdo-2026-09-05.sqlite.gz` and
`manifest.json`. An existing release folder is never replaced. The command
compares all served observations and all source, geography, and coverage records
in both directions before creating the archive. The manifest records the
release version, full database fingerprint, compressed and expanded fingerprints,
file sizes, creation time, and record counts. Source retrieval dates stay intact.

These files are local and excluded from Git. Share both files through your
chosen trusted distribution channel when ready; the command does not publish
or upload them.

Source review schedules and publication-versus-loading status are available
through `list_states`, `describe_source`, and the local report command:
`uv run python -m sdo_mcp.monitoring --database data/sdo.sqlite`.
See [source review instructions](docs/source-reviews.md) for all 21 states.
