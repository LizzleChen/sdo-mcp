"""SQLite layer. The serve path uses stdlib sqlite3 only — no heavy imports here."""

from __future__ import annotations

import os
import platform
import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = Path(__file__).with_name("schema.sql")
REPOSITORY_DB = REPO_ROOT / "data" / "sdo.sqlite"


def user_data_dir() -> Path:
    """Return the per-user folder used by an installed server."""
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "sdo-mcp"
    if system == "Windows":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "sdo-mcp"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "sdo-mcp"


def installed_db_path() -> Path:
    return user_data_dir() / "sdo.sqlite"


# Kept as a public name for callers that imported it before the installed
# default was introduced. It is evaluated once, like the old repository path.
DEFAULT_DB = installed_db_path()


def db_path() -> Path:
    configured = os.environ.get("SDO_DB")
    return Path(configured).expanduser() if configured else installed_db_path()


def connect(path: Path | str | None = None, create: bool = False) -> sqlite3.Connection:
    p = Path(path) if path else db_path()
    if not create and not p.exists():
        raise FileNotFoundError(
            f"database not found at {p} — install one with: "
            "sdo-mcp-install-data PATH_TO_SDO_SQLITE"
        )
    if create:
        p.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(p)
    else:
        conn = sqlite3.connect(f"{p.resolve().as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_PATH.read_text())


# ----------------------------------------------------------------- read layer

def coverage_row(conn, state: str, variable: str, geo_level: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM coverage WHERE state=? AND variable=? AND geo_level=?",
        (state, variable, geo_level),
    ).fetchone()


def coverage_pointers(conn, state: str, variable: str) -> list[dict]:
    """Where this variable IS published, for a refusal's closest_published block.

    Pointers only — geography levels and prose, never numbers.
    """
    rows = conn.execute(
        "SELECT geo_level, status, detail FROM coverage"
        " WHERE state=? AND variable=? AND status != 'not_published'"
        " ORDER BY CASE geo_level WHEN 'county' THEN 0 WHEN 'msa' THEN 1"
        "                         WHEN 'state' THEN 3 ELSE 2 END",
        (state, variable),
    ).fetchall()
    return [dict(r) for r in rows]


def state_fips(conn, state: str) -> str | None:
    row = conn.execute(
        "SELECT geo_id FROM geographies WHERE state=? AND geo_level='state'", (state,)
    ).fetchone()
    return row["geo_id"] if row else None


def _name_key(name: str, geo_level: str | None = None) -> str:
    key = " ".join(name.lower().split())
    for suffix in (" county", " parish", " borough", " census area"):
        key = key.removesuffix(suffix)
    if geo_level == "county_subdivision":
        for suffix in (" town", " city"):
            key = key.removesuffix(suffix)
    return key


def resolve_geo(conn, state: str, geo_level: str, geo: str) -> dict:
    """Resolve a FIPS code or a name to a geo_id. Never guesses: ambiguous or
    unknown names return candidates, not a pick."""
    g = str(geo).strip()
    rows = conn.execute(
        "SELECT geo_id, name FROM geographies WHERE state=? AND geo_level=?",
        (state, geo_level),
    ).fetchall()
    if not rows:
        return {"error": f"no {geo_level} geography list loaded for {state}"}

    # Prefixed ids are ids, not names: a geo_id returned by a previous query
    # (e.g. TX 'tx-cog-18') must be re-queryable verbatim.
    by_id = {r["geo_id"]: r["name"] for r in rows}
    if g in by_id:
        return {"geo_id": g, "name": by_id[g]}

    if g.isdigit():
        if geo_level == "county" and len(g) <= 3:
            sf = state_fips(conn, state) or ""
            gid = sf + g.zfill(3)
        elif geo_level == "state":
            gid = g.zfill(2)
        else:
            gid = g
        if gid in by_id:
            return {"geo_id": gid, "name": by_id[gid]}
        # TX COG/TxDOT ids are TDC's own integers stored prefixed
        # ('tx-cog-18'); a bare int is accepted as shorthand. MSA ids are
        # already the bare 5-digit CBSA FIPS, covered by the direct match.
        if state == "TX" and geo_level in ("cog", "txdot_district"):
            prefixed = {"cog": "tx-cog-", "txdot_district": "tx-txdot-"}[geo_level] + g
            if prefixed in by_id:
                return {"geo_id": prefixed, "name": by_id[prefixed]}
        return {"error": f"FIPS {geo!r} is not a {state} {geo_level}"}

    key = _name_key(g, geo_level)
    if geo_level == "state" and g.upper() == state:
        r = rows[0]
        return {"geo_id": r["geo_id"], "name": r["name"]}
    exact = [r for r in rows if _name_key(r["name"], geo_level) == key]
    if len(exact) == 1:
        return {"geo_id": exact[0]["geo_id"], "name": exact[0]["name"]}
    matches = [r for r in rows if key and key in _name_key(r["name"], geo_level)]
    if len(matches) == 1:
        return {"geo_id": matches[0]["geo_id"], "name": matches[0]["name"]}
    if matches:
        return {
            "error": f"{geo!r} is ambiguous in {state}",
            "candidates": [{"geo_id": r["geo_id"], "name": r["name"]} for r in matches],
        }
    return {"error": f"no {geo_level} named {geo!r} found in {state}"}


def get_series(
    conn,
    state: str,
    geo_level: str,
    geo_id: str,
    variable: str,
    start_year: int | None = None,
    end_year: int | None = None,
    scenario: str = "",
) -> list[sqlite3.Row]:
    """Totals only (v1): detail dimensions pinned to 'all'."""
    q = (
        "SELECT year, value, datatype, source_id FROM observations"
        " WHERE state=? AND geo_level=? AND geo_id=? AND variable=? AND scenario=?"
        " AND age_group='all' AND sex='all' AND race='all'"
    )
    params: list = [state, geo_level, geo_id, variable, scenario]
    if start_year is not None:
        q += " AND year >= ?"
        params.append(start_year)
    if end_year is not None:
        q += " AND year <= ?"
        params.append(end_year)
    return conn.execute(q + " ORDER BY year", params).fetchall()


def get_source(conn, source_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM sources WHERE source_id=?", (source_id,)
    ).fetchone()


def sources_for_state(conn, state: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM sources WHERE state=? ORDER BY source_id", (state,)
    ).fetchall()


def state_has_data(conn, state: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM observations WHERE state=? LIMIT 1", (state,)
        ).fetchone()
        is not None
    )


# ---------------------------------------------------------------- write layer
# Used by ingest only; the server never writes.

def upsert_source(conn, **fields) -> None:
    cols = ",".join(fields)
    ph = ",".join("?" * len(fields))
    conn.execute(
        f"INSERT OR REPLACE INTO sources ({cols}) VALUES ({ph})",
        list(fields.values()),
    )


def insert_observations(conn, rows) -> int:
    """rows: iterable of dicts with observation columns (defaults applied here)."""
    prepared = [
        (
            r["state"],
            r["geo_level"],
            r["geo_id"],
            r["year"],
            r["variable"],
            r["value"],
            r["datatype"],
            r.get("scenario", ""),
            r.get("age_group", "all"),
            r.get("sex", "all"),
            r.get("race", "all"),
            r["source_id"],
        )
        for r in rows
    ]
    conn.executemany(
        "INSERT INTO observations"
        " (state, geo_level, geo_id, year, variable, value, datatype,"
        "  scenario, age_group, sex, race, source_id)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        prepared,
    )
    return len(prepared)
