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

## Project layout

- `plan/` — local planning and research notes, **gitignored**, never committed.
  - `plan/PLAN.md` — implementation plan and status.
  - `plan/RESEARCH.md` — per-state endpoint verification findings.
- (Server code layout TBD — see plan/PLAN.md.)

## Related local resources

- Skill `socioeconomic-data-analysis` (~/.claude/skills/) documents the verified Colorado
  DOLA endpoints, the estimates-vs-forecast quirks, and the growth-metric conventions this
  project should follow. Its `reference/dola_population.py` is a working Colorado client.
