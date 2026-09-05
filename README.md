# SDO Forecast MCP

This package serves state demography office forecasts for population,
households, and employment where the state office publishes it. The server
reads a local SQLite database and does not download data while answering a
question.

There is no public package release or hosted database download yet. The setup
below builds a wheel from this checkout and uses either an existing database
from a trusted checkout or a fresh database rebuilt from the saved source
files.

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

## Install the database

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
