# Deployment and maintenance

This guide is for people who rebuild the data and publish new releases. To
install and use the server, see the [README](README.md).

## How the pieces fit

```
data/raw/            saved government files (committed, never edited)
   │  uv run python -m sdo_mcp.ingest.build
   ▼
data/sdo.sqlite      full research database, ~200 MB (not committed)
   │  uv run python -m sdo_mcp.bundle
   ▼
src/sdo_mcp/data/sdo.sqlite   served rows only, ~19 MB (not committed)
   │  uv build --wheel
   ▼
dist/sdo_mcp-<version>-py3-none-any.whl   code + data, ~2.4 MB
   │  attach to a GitHub release
   ▼
users: uv tool install ./sdo_mcp-<version>-py3-none-any.whl
```

The full database keeps age, sex and race detail that no tool serves. The
bundled copy keeps every value the tools can return, every source record, and
all geography and coverage information.

## Setup

Install [`uv`](https://docs.astral.sh/uv/getting-started/installation/). The
checkout pins Python 3.12 in `.python-version`; any patched Python 3.12 or newer
works. Install the extra libraries used to read state workbooks and PDFs:

```sh
uv sync --group ingest
```

## Rebuild the data

```sh
uv run python -m sdo_mcp.ingest.build
```

This writes `data/sdo.sqlite` from the saved files in `data/raw/`. It does not
contact any state agency.

- **Source checks.** Every saved file has a recorded SHA-256 fingerprint and
  retrieval date. The build checks the fingerprints before and after loading,
  so a changed or replaced government file stops the build.
- **Safe replacement.** A failed build leaves the existing database untouched.
  A successful one keeps the old file beside it as
  `sdo.sqlite.previous-<unique-id>`. These are about 200 MB each; delete them
  once the new build looks right. To go back, set `SDO_DB` to a recovery copy
  or rename it to `data/sdo.sqlite`.
- **New editions.** Saved files cannot be overwritten with different contents.
  A new edition needs a new filename, a manifest entry in its state folder, and
  an entry in `src/sdo_mcp/ingest/inputs.json`. Reusing a saved file keeps its
  original retrieval date.
- **Fixing data.** The database is a built file. If a value is wrong, fix the
  state's adapter in `src/sdo_mcp/ingest/` and rebuild; never edit the
  database by hand.

With a path argument, the build writes somewhere else instead:
`uv run python -m sdo_mcp.ingest.build /path/to/sdo.sqlite`.

## Run from the checkout

Serve the full build directly while developing:

```sh
SDO_DB=data/sdo.sqlite uv run python -m sdo_mcp.server
```

To try it in Claude Code without installing, add it with the full path:

```sh
claude mcp add sdo-dev --env SDO_DB=$PWD/data/sdo.sqlite -- uv run --directory $PWD python -m sdo_mcp.server
```

## Run the checks

```sh
uv run pytest
```

The checks rebuild from saved sources, confirm that failed builds and changed
fingerprints keep the previous database, and compare the bundled data with the
full build. They also build a package with its data, install it in a fresh
environment outside the checkout, and call all four tools over MCP with no
`SDO_DB` set. They need `uv` and access to its package cache or the package
index, but never download from a state agency. GitHub runs the same checks on
every push and pull request (`.github/workflows/checks.yml`).

## Publish a release

1. Raise `version` in `pyproject.toml`, then run `uv lock`.
2. Rebuild the data and run the checks, as above.
3. Put the served rows into the package and build it:

   ```sh
   uv run python -m sdo_mcp.bundle
   uv build --wheel
   ```

4. Publish the single file (change both version numbers to match):

   ```sh
   gh release create v0.2.0 dist/sdo_mcp-0.2.0-py3-none-any.whl --repo LizzleChen/sdo-mcp --title v0.2.0 --notes "What changed in the data"
   ```

The bundle step writes `src/sdo_mcp/data/sdo.sqlite`, which Git ignores. Before
writing it, it compares every served value and every source, geography and
coverage record with the full build in both directions. It also stamps the
package version into the data, so `list_states` reports the same version as
the server. `uv build` refuses to make a package if the bundled file is
missing.

## Source reviews

Each state has a review schedule. To see what is due and what is published but
not yet loaded:

```sh
uv run python -m sdo_mcp.monitoring --database data/sdo.sqlite
```

See [docs/source-reviews.md](docs/source-reviews.md) for the schedule and the
open questions for each state.
