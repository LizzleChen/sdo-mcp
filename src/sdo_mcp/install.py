"""Install a checked database for use by an installed SDO Forecast MCP.

This command moves only a copy of the database. It never changes the source
file, and it replaces an existing installed copy in one final operation after
the copied file has passed the same checks.

Usage::

    sdo-mcp-install-data /path/to/sdo.sqlite
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import re
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

from . import store


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


def install_database(
    source: Path | str,
    destination: Path | str | None = None,
) -> Path:
    """Validate and atomically install a database in the user data folder."""
    source_path = validate_database(source)
    destination_path = (
        Path(destination).expanduser() if destination else store.installed_db_path()
    )
    destination_path.parent.mkdir(parents=True, exist_ok=True)

    # A source and destination can be the same path when a user reruns the
    # command. Validation above is enough; there is nothing to copy.
    try:
        same_file = source_path.resolve() == destination_path.resolve()
    except OSError:
        same_file = False
    if same_file:
        return destination_path

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=destination_path.parent,
            prefix=f".{destination_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            with source_path.open("rb") as source_file:
                shutil.copyfileobj(source_file, temporary)
            temporary.flush()
            os.fsync(temporary.fileno())
        validate_database(temporary_path)
        os.replace(temporary_path, destination_path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass
    return destination_path


MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
MAX_DATABASE_BYTES = 512 * 1024 * 1024


def install_release(source: Path | str, expected_sha256: str,
                    destination: Path | str | None = None) -> Path:
    """Verify the trusted archive fingerprint before bounded decompression."""
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
        raise DatabaseValidationError("expected SHA-256 must contain 64 hexadecimal characters")
    source = Path(source)
    with tempfile.TemporaryDirectory(prefix="sdo-install-") as folder:
        archive = Path(folder) / "release.gz"
        digest = hashlib.sha256()
        size = 0
        with source.open("rb") as incoming, archive.open("wb") as outgoing:
            while chunk := incoming.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_ARCHIVE_BYTES:
                    raise DatabaseValidationError("compressed release exceeds size limit")
                digest.update(chunk)
                outgoing.write(chunk)
        if digest.hexdigest() != expected_sha256.lower():
            raise DatabaseValidationError("release fingerprint mismatch")
        database = Path(folder) / "sdo.sqlite"
        size = 0
        try:
            with gzip.open(archive, "rb") as incoming, database.open("wb") as outgoing:
                while chunk := incoming.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_DATABASE_BYTES:
                        raise DatabaseValidationError("expanded release exceeds size limit")
                    outgoing.write(chunk)
        except (OSError, EOFError) as exc:
            raise DatabaseValidationError("invalid compressed database release") from exc
        return install_database(database, destination)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate and install an SDO Forecast SQLite database."
    )
    parser.add_argument("source", type=Path, help="existing full or compatible SDO SQLite database")
    parser.add_argument(
        "--destination",
        type=Path,
        help="override the per-user destination (normally platform-specific)",
    )
    parser.add_argument("--sha256", help="trusted SHA-256 fingerprint of a compressed release")
    args = parser.parse_args(argv)
    try:
        if args.sha256:
            installed = install_release(args.source, args.sha256, args.destination)
        elif args.source.suffix == ".gz":
            raise DatabaseValidationError("compressed releases require --sha256 from a trusted publisher")
        else:
            installed = install_database(args.source, args.destination)
    except (DatabaseValidationError, OSError) as exc:
        parser.error(str(exc))
    print(f"installed {installed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
