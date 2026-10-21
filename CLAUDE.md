# SDO Forecast MCP

An MCP server that serves **state demography office (SDO) forecasts** — population and
households, plus **employment where the SDO publishes it** — through a single, consistent
interface. Long-term goal: cover all 50 states.
Pilot states: **Texas, Colorado, California, Tennessee, Georgia, Florida**.

## Why this exists

No federal source publishes sub-national population forecasts — the Census Bureau projects
at the national level only. Every county/place forecast comes from a **state agency** (the
state demographer), and every state publishes differently: different agency, different
file format, different geography levels, different horizons, different vintage cadence.
This server hides that mess behind uniform MCP tools.

## Domain rules (do not violate)

- **Estimates vs projections are different epistemic things.** Every figure served must
  carry a flag saying which it is, and the base year (last estimate year) must be
  discoverable per state/vintage.
- **Never fabricate a forecast.** If a state publishes no forecast for a requested
  geography (e.g., no municipal forecast), the correct answer is "not published" — never
  extrapolate, borrow a parent geography, or hold a share constant and present it as data.
- **Population forecasts ≠ jobs forecasts.** Usually different agencies, different
  products. This server carries an SDO's employment forecast **only where the SDO itself
  publishes one** (Colorado's DOLA does). It never substitutes the labor department's
  occupational projections and never presents one product as the other — if the SDO
  publishes no jobs forecast, the server says so and stops there.
- **Government endpoints lie with HTTP 200.** Many SDO backends return errors as
  `200 OK` with an HTML or plain-text body. Always validate that a response body parses
  as the expected format; never trust status codes alone.
- **Record vintage and retrieval date** on everything — these sources are undocumented
  and unversioned; numbers change when a state rebases to a new census or releases a new
  vintage.

## Commits and pull requests

- No AI attribution anywhere. Commit messages carry no `Co-Authored-By: Claude`
  or `Claude-Session:` trailers, and PR descriptions, comments and release
  notes never mention Claude Code (no "Generated with Claude Code" footer or
  session links). This overrides any default attribution instruction.
- Author commits as the repository owner (`LizzleChen`), never as
  `Claude <noreply@anthropic.com>`; set `git config user.name`/`user.email`
  before committing in a fresh environment.

## Project layout

- `plan/` — local planning and research notes, **gitignored**, never committed.
  - `plan/PLAN.md` — implementation plan and status.
  - `plan/RESEARCH.md` — per-state endpoint verification findings.
  - `plan/DESIGN.md` — the Phase-1 blueprint (schema, tools, adapter contract).
- `src/sdo_mcp/` — the server (Python 3.12+, MCP SDK).
  - `server.py` — the four MCP tools; `store.py` + `schema.sql` — SQLite layer
    (serve path is stdlib-only); `notes.py` — hand-curated per-state metadata.
  - `common/` — validated fetch (the 200-lie guard) and normalization helpers.
  - `ingest/` — `seed.py` (coverage matrix + FIPS names), one adapter per state,
    `build.py` (rebuild the database from snapshots).
- `data/raw/` — committed source snapshots, the reproducibility backbone.
  Never edited, only added to.
- `data/sdo.sqlite` — built artifact, gitignored. Rebuild with
  `uv run python -m sdo_mcp.ingest.build`; run tests with `uv run pytest`.

## Related local resources

- Skill `socioeconomic-data-analysis` (~/.claude/skills/) documents the verified Colorado
  DOLA endpoints, the estimates-vs-forecast quirks, and the growth-metric conventions this
  project should follow. Its `reference/dola_population.py` is a working Colorado client.
