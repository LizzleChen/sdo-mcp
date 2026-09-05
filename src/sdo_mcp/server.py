"""The four MCP tools. Serve path is stdlib-only (sqlite3 via store).

Shared rule: every data response carries vintage, base year, retrieval date,
citation, and a per-point estimate/projection flag. Where a state publishes
nothing, the answer is a structured refusal looked up in the coverage table —
never an extrapolation, never a borrowed geography.
"""

from __future__ import annotations

import json
from importlib.metadata import version

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError, UnexpectedToolError
from mcp.shared.exceptions import MCPError
from mcp.types import INVALID_PARAMS, CallToolResult, ToolAnnotations

from . import monitoring, notes, store
from .results import ComponentsResult, ForecastResult, SourceResult, StatesResult


class ForecastServer(MCPServer):
    async def call_tool(self, name, arguments, context=None):
        # Unknown names are request errors, distinct from a known tool failing.
        if name not in {tool.name for tool in await self.list_tools()}:
            raise MCPError(code=INVALID_PARAMS, message=f"Unknown tool: {name}")
        try:
            result = await super().call_tool(name, arguments, context)
        except UnexpectedToolError as exc:
            if isinstance(exc.__cause__, FileNotFoundError):
                raise ToolError(
                    "Forecast database is missing. Install it with "
                    "sdo-mcp-install-data PATH_TO_SDO_SQLITE or check SDO_DB."
                ) from exc
            raise
        if isinstance(result, CallToolResult) and result.structured_content:
            result.is_error = result.structured_content.get("status") == "error"
        return result


mcp = ForecastServer(
    "sdo-forecast",
    version=version("sdo-mcp"),
    instructions=(
        "State demography office (SDO) forecasts — population, households, and "
        "(where the SDO itself publishes one) employment. Figures are flagged "
        "estimate vs projection per point. If a state publishes no forecast for "
        "a requested geography or variable, the server says so; it never "
        "extrapolates or substitutes another agency's product."
    ),
)

FORECAST_VARIABLES = ("population", "households", "employment")
GEO_LEVELS = ("state", "county", "place", "msa", "cog", "txdot_district")
READ_ONLY = ToolAnnotations(
    read_only_hint=True, destructive_hint=False,
    idempotent_hint=True, open_world_hint=False,
)


def _num(v: float):
    f = float(v)
    return int(f) if f.is_integer() else f


def _source_block(row) -> dict | None:
    if row is None:
        return None
    return {
        "agency": row["agency"],
        "product": row["product_name"],
        "vintage": row["vintage"],
        "base_year": row["base_year"],
        "horizon_year": row["horizon_year"],
        "retrieved_at": row["retrieved_at"],
        "citation": row["citation"],
        "license": row["license"],
        "url": row["source_url"],
        "method_notes": row["method_notes"],
    }


def _refusal(conn, state: str, variable: str, geo_level: str, cov) -> dict:
    status = cov["status"] if cov else "coverage_unknown"
    reason = (cov["detail"] if cov else None) or (
        f"This server has no coverage record for {state} {variable} at the "
        f"{geo_level} level; publication status is unknown."
    )
    pointers = [
        p
        for p in store.coverage_pointers(conn, state, variable)
        if p["geo_level"] != geo_level
    ]
    return {
        "status": status,
        "state": state,
        "variable": variable,
        "geo_level": geo_level,
        "reason": reason,
        # Pointers to where the variable IS published — levels and prose only,
        # never numbers borrowed from another geography.
        "closest_published": pointers or None,
    }


def _error(message: str, **extra) -> dict:
    return {"status": "error", "error": message, **extra}


def _year_error(start_year, end_year):
    if start_year is not None and end_year is not None and start_year > end_year:
        return _error("start_year must be less than or equal to end_year")
    return None


def _empty_range(state, variable, rows):
    years = [r["year"] for r in rows]
    return {
        "status": "empty_range", "state": state, "variable": variable,
        "reason": "No observations fall in the requested year range.",
        "available_start_year": min(years), "available_end_year": max(years),
    }


def _geo_exception(state: str, variable: str, geo_level: str, resolved: dict) -> dict | None:
    """Return an explicit refusal for a known hole inside an otherwise
    published geography level, such as Oregon's excluded Multnomah County."""
    exception = notes.STATES[state].get("geo_exceptions", {}).get(
        (variable, geo_level, resolved["geo_id"])
    )
    if exception is None:
        return None
    return {
        "status": exception.get("status", "not_published"),
        "state": state,
        "variable": variable,
        "geo": {
            "level": geo_level,
            "id": resolved["geo_id"],
            "name": resolved["name"],
        },
        "reason": exception["reason"],
        "closest_published": None,
    }


def _resolve_scenario(
    state: str, scenario: str | None, geo_level: str | None = None
) -> tuple[str | None, dict]:
    meta = notes.STATES[state]
    published = meta["scenarios"]
    scenario_levels = meta.get("scenario_geo_levels")
    if scenario_levels is not None and geo_level not in scenario_levels:
        published = []
    if scenario:
        s = scenario.strip().lower()
        if s not in published:
            if published:
                return None, _error(
                    f"{state} scenarios are: {', '.join(published)} "
                    f"(default: {meta['default_scenario']})"
                )
            return None, _error(
                f"{state} publishes a single series — there are no scenarios to pick"
            )
        return s, {}
    return (meta["default_scenario"] if published else "") or "", {}


@mcp.tool(annotations=READ_ONLY)
def list_states() -> StatesResult:
    """What each covered state's demography office publishes: agency, current
    vintage, horizon, geography floor, scenarios, and per-variable availability
    (population / households / employment), including explicit "not published"
    entries. Loading status and review reminders are separate from publication
    status; loaded means totals exist, not complete coverage. Start here."""
    conn = store.connect()
    try:
        out = {}
        for state, meta in notes.STATES.items():
            cov = conn.execute(
                "SELECT variable, geo_level, status, detail FROM coverage"
                " WHERE state=? ORDER BY variable, geo_level",
                (state,),
            ).fetchall()
            variables = monitoring.coverage_inventory(conn, state)
            scenario_levels = None
            if meta["scenarios"]:
                scenario_levels = meta.get("scenario_geo_levels") or [
                    r["geo_level"]
                    for r in cov
                    if r["variable"] == "population" and r["status"] == "available"
                ]
            out[state] = {
                "name": meta["name"],
                "agency": meta["agency"],
                "current_vintage": meta["current_vintage"],
                "geography_floor": meta["geography_floor"],
                "scenarios": meta["scenarios"] or None,
                "default_scenario": meta["default_scenario"],
                "scenario_geo_levels": scenario_levels,
                "employment_note": meta["employment_note"],
                "variables": variables,
                "data_loaded": store.state_has_data(conn, state),
                "review": monitoring.review_status(state),
            }
        has_release = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='release_metadata'"
        ).fetchone()
        release = conn.execute("SELECT metadata FROM release_metadata").fetchone() if has_release else None
        return {"states": out, "database_release": (
            json.loads(release[0])["release_version"] if release else None
        )}
    finally:
        conn.close()


@mcp.tool(annotations=READ_ONLY)
def get_forecast(
    state: str,
    geo_level: str,
    geo: str,
    variable: str,
    start_year: int | None = None,
    end_year: int | None = None,
    scenario: str | None = None,
) -> ForecastResult:
    """Population, household, or employment forecast series from a state
    demography office.

    `state` is a 2-letter code; `geo_level` is 'state' or 'county' everywhere,
    plus TX's 'msa', 'cog', and 'txdot_district' (decade totals). `geo`
    accepts a FIPS code, a bare TDC id for TX COG/TxDOT levels ('18'), or a
    name (unknown or ambiguous names return candidates, never a guess);
    `variable` is 'population', 'households', or 'employment'. `scenario`
    only applies where the selected product publishes scenarios (TX
    Mid/High/Low; AZ and FL Low/Medium/High; WA county Low/Medium/High) and
    defaults to the state's recommended one. Every point is flagged estimate
    or projection; if the state publishes nothing for the request, a
    structured refusal explains why and points to the closest published
    geography (pointer only, no numbers)."""
    state = state.strip().upper()
    variable = variable.strip().lower()
    geo_level = geo_level.strip().lower()
    if state not in notes.STATES:
        return _error(
            f"unknown or unsupported state {state!r}; covered states: "
            + ", ".join(notes.STATES)
        )
    if variable not in FORECAST_VARIABLES:
        return _error(
            f"unknown variable {variable!r}; one of: {', '.join(FORECAST_VARIABLES)}. "
            "Births/deaths/migration are served by get_components."
        )
    if geo_level not in GEO_LEVELS:
        return _error(f"unknown geography level {geo_level!r}; one of: {', '.join(GEO_LEVELS)}")
    if err := _year_error(start_year, end_year):
        return err
    conn = store.connect()
    try:
        cov = store.coverage_row(conn, state, variable, geo_level)
        if cov is None or cov["status"] != "available":
            return _refusal(conn, state, variable, geo_level, cov)

        scen, err = _resolve_scenario(state, scenario, geo_level)
        if scen is None:
            return err

        resolved = store.resolve_geo(conn, state, geo_level, geo)
        if "error" in resolved:
            return _error(resolved["error"], candidates=resolved.get("candidates"))
        exception = _geo_exception(state, variable, geo_level, resolved)
        if exception is not None:
            return exception

        rows = store.get_series(
            conn, state, geo_level, resolved["geo_id"], variable,
            start_year, end_year, scenario=scen,
        )
        if not rows:
            # Distinct from "not published": the state publishes this, but the
            # adapter hasn't been ingested (or the year range is off the ends).
            full = store.get_series(conn, state, geo_level, resolved["geo_id"], variable, scenario=scen)
            if full:
                return _empty_range(state, variable, full)
            return {
                "status": "not_loaded",
                "state": state,
                "variable": variable,
                "reason": (
                    f"{state} publishes this series ({cov['detail']}) but its "
                    "requested series has not been ingested into this server yet."
                ),
            }

        return {
            "status": "ok",
            "state": state,
            "variable": variable,
            "geo": {"level": geo_level, "id": resolved["geo_id"], "name": resolved["name"]},
            "scenario": scen or None,
            "scenario_note": (
                f"defaulted to the state's recommended scenario ({scen})"
                if scenario is None and scen
                else None
            ),
            "series": [
                {"year": r["year"], "value": _num(r["value"]), "datatype": r["datatype"]}
                for r in rows
            ],
            "source": _source_block(store.get_source(conn, rows[0]["source_id"])),
        }
    finally:
        conn.close()


@mcp.tool(annotations=READ_ONLY)
def get_components(
    state: str,
    geo: str,
    start_year: int | None = None,
    end_year: int | None = None,
    scenario: str | None = None,
) -> ComponentsResult:
    """Components of population change — births, deaths, net migration — where
    the state demography office publishes them. ``scenario`` applies where
    components accompany scenario forecasts (Arizona Low/Medium/High).
    `geo` accepts a county FIPS/name, or the state code/name for the statewide
    series. Washington county components are medium-only five-year totals;
    their year is the period end, with explicit period start/end fields.
    Year filters select ending years. States without a components product
    return a structured refusal."""
    state = state.strip().upper()
    if err := _year_error(start_year, end_year):
        return err
    if state not in notes.STATES:
        return _error(
            f"unknown or unsupported state {state!r}; covered states: "
            + ", ".join(notes.STATES)
        )
    conn = store.connect()
    try:
        g = str(geo).strip()
        meta = notes.STATES[state]
        is_state = g.upper() == state or g.lower() == meta["name"].lower() or (
            g.isdigit() and len(g) == 2
        )
        geo_level = "state" if is_state else "county"

        cov = store.coverage_row(conn, state, "components", geo_level)
        if cov is None or cov["status"] != "available":
            return _refusal(conn, state, "components", geo_level, cov)

        scen, err = _resolve_scenario(state, scenario, geo_level)
        if scen is None:
            return err

        resolved = store.resolve_geo(conn, state, geo_level, g)
        if "error" in resolved:
            return _error(resolved["error"], candidates=resolved.get("candidates"))

        series: dict[int, dict] = {}
        if state == "WA" and geo_level == "county" and scen != "medium":
            return _error("Washington publishes county components only for the medium scenario; request medium.")
        source_id = None
        for var in ("births", "deaths", "net_migration"):
            rows = store.get_series(
                conn, state, geo_level, resolved["geo_id"], var, start_year, end_year,
                scenario=scen,
            )
            for r in rows:
                point = series.setdefault(
                    r["year"], {"year": r["year"], "datatype": r["datatype"]}
                )
                point[var] = _num(r["value"])
                if state == "WA":
                    point["period_start_year"] = r["year"] - (5 if geo_level == "county" else 1)
                    point["period_end_year"] = r["year"]
                source_id = source_id or r["source_id"]
        if not series:
            full = [
                row
                for var in ("births", "deaths", "net_migration")
                for row in store.get_series(
                    conn, state, geo_level, resolved["geo_id"], var, scenario=scen,
                )
            ]
            if full:
                return _empty_range(state, "components", full)
            return {
                "status": "not_loaded",
                "state": state,
                "variable": "components",
                "reason": (
                    f"{state} publishes components ({cov['detail']}) but its "
                    "requested series has not been ingested into this server yet."
                ),
            }
        return {
            "status": "ok",
            "state": state,
            "geo": {"level": geo_level, "id": resolved["geo_id"], "name": resolved["name"]},
            "scenario": scen or None,
            "scenario_note": (
                f"defaulted to the state's recommended scenario ({scen})"
                if scenario is None and scen
                else None
            ),
            "series": [series[y] for y in sorted(series)],
            "source": _source_block(store.get_source(conn, source_id)),
        }
    finally:
        conn.close()


@mcp.tool(annotations=READ_ONLY)
def describe_source(state: str) -> SourceResult:
    """The full sourcing story for one state: agency (including two-agency
    arrangements), products, methodology, licensing, known caveats, links, and
    the vintages actually loaded in this server."""
    state = state.strip().upper()
    if state not in notes.STATES:
        return _error(
            f"unknown or unsupported state {state!r}; covered states: "
            + ", ".join(notes.STATES)
        )
    meta = notes.STATES[state]
    conn = store.connect()
    try:
        loaded = [_source_block(r) for r in store.sources_for_state(conn, state)]
        variables = monitoring.coverage_inventory(conn, state)
    finally:
        conn.close()
    return {
        "state": state,
        "name": meta["name"],
        "agency": meta["agency"],
        "producer_type": meta["producer_type"],
        "current_vintage": meta["current_vintage"],
        "geography_floor": meta["geography_floor"],
        "products": meta["products"],
        "methodology": meta["methodology"],
        "employment_note": meta["employment_note"],
        "license": meta["license"],
        "caveats": meta["caveats"],
        "links": meta["links"],
        "sources_loaded": loaded or None,
        "variables": variables,
        "review": monitoring.review_status(state),
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
