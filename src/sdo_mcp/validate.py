"""Check that a SQLite file is a usable SDO Forecast database."""

from __future__ import annotations

import sqlite3
from pathlib import Path


class DatabaseValidationError(ValueError):
    """The file is not a usable SDO Forecast database."""


# These checks catch a copied text/HTML error page and databases from an
# unrelated SQLite application, while remaining compatible with this schema's
# current user_version value.
REQUIRED_COLUMNS = {
    "sources": {
        "source_id", "state", "agency", "product_name", "vintage",
        "base_year", "horizon_year", "source_url", "retrieved_at",
        "license", "citation", "method_notes",
    },
    "observations": {
        "state", "geo_level", "geo_id", "year", "variable", "value",
        "datatype", "scenario", "age_group", "sex", "race", "source_id",
    },
    "geographies": {"geo_id", "geo_level", "state", "name"},
    "coverage": {"state", "variable", "geo_level", "status", "detail"},
}


def validate_database(path: Path | str) -> Path:
    """Validate an existing SQLite database without opening it for writing."""
    p = Path(path).expanduser()
    if not p.is_file():
        raise DatabaseValidationError(f"database file not found: {p}")

    try:
        conn = sqlite3.connect(
            f"{p.resolve().as_uri()}?mode=ro", uri=True,
        )
    except sqlite3.Error as exc:
        raise DatabaseValidationError(f"cannot open SQLite database {p}: {exc}") from exc

    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()
        if not integrity or integrity[0] != "ok":
            detail = integrity[0] if integrity else "no result"
            raise DatabaseValidationError(f"SQLite integrity check failed for {p}: {detail}")

        foreign_keys = conn.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_keys:
            raise DatabaseValidationError(
                f"SQLite foreign-key check failed for {p}: {len(foreign_keys)} issue(s)"
            )

        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        missing_tables = sorted(set(REQUIRED_COLUMNS) - tables)
        if missing_tables:
            raise DatabaseValidationError(
                f"database {p} is missing required table(s): {', '.join(missing_tables)}"
            )
        for table, required in REQUIRED_COLUMNS.items():
            actual = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            missing = sorted(required - actual)
            if missing:
                raise DatabaseValidationError(
                    f"database {p} table {table!r} is missing column(s): {', '.join(missing)}"
                )
        mixed_source = conn.execute(
            "SELECT state, geo_level, geo_id, variable, scenario FROM observations "
            "WHERE variable IN ('population', 'households', 'employment') "
            "AND age_group='all' AND sex='all' AND race='all' "
            "GROUP BY state, geo_level, geo_id, variable, scenario "
            "HAVING COUNT(DISTINCT source_id) > 1 LIMIT 1"
        ).fetchone()
        if mixed_source:
            raise DatabaseValidationError(
                f"database {p} mixes sources within one forecast series: {mixed_source}"
            )
        sources = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        observations = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
        geographies = conn.execute("SELECT COUNT(*) FROM geographies").fetchone()[0]
        coverage = conn.execute("SELECT COUNT(*) FROM coverage").fetchone()[0]
        serviceable = conn.execute(
            "SELECT 1 FROM observations AS o "
            "JOIN sources AS s ON s.source_id=o.source_id "
            "JOIN geographies AS g ON g.state=o.state AND g.geo_level=o.geo_level "
            " AND g.geo_id=o.geo_id "
            "JOIN coverage AS c ON c.state=o.state AND c.variable=o.variable "
            " AND c.geo_level=o.geo_level AND c.status='available' "
            "WHERE o.variable IN ('population', 'households', 'employment') "
            "AND o.age_group='all' AND o.sex='all' AND o.race='all' LIMIT 1"
        ).fetchone()
        if not sources or not observations or not geographies or not coverage or not serviceable:
            raise DatabaseValidationError(
                f"database {p} has no serviceable forecast data "
                f"(sources={sources}, observations={observations}, "
                f"geographies={geographies}, coverage={coverage})"
            )
    except sqlite3.DatabaseError as exc:
        raise DatabaseValidationError(f"cannot read SQLite database {p}: {exc}") from exc
    finally:
        conn.close()
    return p
