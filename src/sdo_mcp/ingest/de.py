"""Delaware Population Consortium 2024 state and county summary tables."""

from __future__ import annotations

import math
import sys
from datetime import date

from ..common import fetch
from ..store import REPO_ROOT, insert_observations, upsert_source

RAW_DIR = REPO_ROOT / "data" / "raw" / "de"
CATALOG_URL = "https://stateplanning.delaware.gov/demography/dpc-projection-data.shtml"
EDITION_URL = "https://stateplanning.delaware.gov/demography/dpc-projection-info.shtml"
WORKBOOK_URL = "https://stateplanning.delaware.gov/demography/documents/dpc/DPC-2024v0-report.xls"
FILES = {
    "projection_catalog_2026-09-30.html": CATALOG_URL,
    "edition_catalog_2026-09-30.html": EDITION_URL,
    "DPC-2024v0-report.xls": WORKBOOK_URL,
}
AGENCY = "Delaware Population Consortium, Office of State Planning Coordination"
YEARS = tuple(range(2010, 2051, 5))
# First row of each jurisdiction's top-line table in the publisher's report.
TABLES = {"10": (13, "State of Delaware"), "10001": (752, "Kent County"),
          "10003": (1625, "New Castle County"), "10005": (3166, "Sussex County")}
PRODUCTS = {
    "population": (6, "Population", "de-pop-2024", "Total population"),
    "households": (8, "Households", "de-households-2024", "Household counts"),
    "employment": (38, "Jobs by Place of Work", "de-jobs-2024", "Jobs by place of work"),
}


def parse_workbook(body: bytes) -> dict[str, list[dict]]:
    """Read only the four published jurisdiction summary tables, not model cells."""
    import xlrd

    try:
        book = xlrd.open_workbook(file_contents=body, on_demand=True)
    except Exception as exc:
        raise ValueError("DE: response is not a readable XLS workbook") from exc
    try:
        if book.sheet_names() != ["DPC_2024-V0"]:
            raise ValueError("DE: unexpected workbook edition or sheets")
        sheet = book.sheet_by_index(0)
        if sheet.nrows != 3887 or sheet.ncols != 19:
            raise ValueError("DE: unexpected report table layout")
        rows = {variable: [] for variable in PRODUCTS}
        totals = {variable: {} for variable in PRODUCTS}
        for geo_id, (start, name) in TABLES.items():
            base = start - 1
            if (sheet.cell_value(base - 2, 2) != "October 14, 2024"
                    or sheet.cell_value(base, 2) != name
                    or sheet.cell_value(base + 1, 2) != "Total Population"
                    or sheet.cell_value(base + 2, 2) != "[As of July 1]"
                    or tuple(sheet.row_values(base + 4, 2, 11)) != YEARS):
                raise ValueError(f"DE: unexpected {name} title, edition or year header")
            for variable, (offset, label, source_id, _) in PRODUCTS.items():
                cells = sheet.row_values(base + offset, 0, 11)
                if cells[:2] != [label, ""]:
                    raise ValueError(f"DE: unexpected {name} {variable} row label")
                values = cells[2:]
                if any(not isinstance(v, (int, float)) or isinstance(v, bool)
                       or not math.isfinite(v) or v < 0 or int(v) != v for v in values):
                    raise ValueError(f"DE: invalid {name} {variable} value")
                totals[variable][geo_id] = tuple(map(int, values))
                rows[variable].extend({
                    "state": "DE", "geo_level": "state" if geo_id == "10" else "county",
                    "geo_id": geo_id, "year": year, "variable": variable, "value": int(value),
                    "datatype": "estimate" if year == 2020 else "projection",
                    "source_id": source_id,
                } for year, value in zip(YEARS, values) if year >= 2020)
        for variable, by_geo in totals.items():
            for index, year in enumerate(YEARS):
                if by_geo["10"][index] != sum(by_geo[gid][index] for gid in TABLES if gid != "10"):
                    raise ValueError(f"DE: {variable} county sum differs from state in {year}")
        return rows
    finally:
        book.release_resources()


def _validate_page(filename: str, body: bytes) -> None:
    page = " ".join(body.decode("utf-8", "replace").lower().split())
    markers = ("<html", "delaware population consortium", "2024 population projections")
    if filename.startswith("projection_"):
        markers += ("december 11, 2025", "dpc-2024v0-report.xls")
    else:
        markers += ("readopt", "no new projections for 2025")
    for marker in markers:
        if marker not in page:
            raise ValueError(f"DE: invalid {filename}; missing {marker!r}")


def acquire() -> None:
    if (RAW_DIR / "manifest.json").exists():
        entries = {e["file"] for e in fetch.read_manifest(RAW_DIR)}
        if entries != set(FILES):
            raise ValueError("DE: saved snapshot manifest is incomplete")
        parse_workbook((RAW_DIR / "DPC-2024v0-report.xls").read_bytes())
        for name in FILES:
            if name.endswith(".html"):
                _validate_page(name, (RAW_DIR / name).read_bytes())
        print("DE acquire: reused validated snapshots")
        return
    snapshots = []
    for filename, url in FILES.items():
        body = fetch.get_bytes(url)
        if filename.endswith(".xls"):
            parse_workbook(body)
        else:
            _validate_page(filename, body)
        snapshots.append((filename, url, body))
    entries = []
    for filename, url, body in snapshots:
        fetch.write_snapshot(RAW_DIR / filename, body)
        entries.append({"file": filename, "source": url, "retrieved_at": date.today().isoformat(),
                        "sha256": fetch.sha256(body), "records": 84 if filename.endswith(".xls") else None,
                        "note": "Original DPC 2024 table or current catalog; 2025 readoption is not a new model edition."})
    fetch.write_manifest(RAW_DIR, entries)


def load(conn) -> None:
    entries = {e["file"]: e for e in fetch.read_manifest(RAW_DIR)}
    for filename in FILES:
        if filename.endswith(".html"):
            _validate_page(filename, (RAW_DIR / filename).read_bytes())
    data = parse_workbook((RAW_DIR / "DPC-2024v0-report.xls").read_bytes())
    for variable, (_, _, source_id, product_name) in PRODUCTS.items():
        upsert_source(
            conn, source_id=source_id, state="DE", agency=AGENCY,
            product_name=product_name, vintage="October 2024 (readopted December 2025)",
            base_year=2020, horizon_year=2050, source_url=WORKBOOK_URL,
            retrieved_at=entries["DPC-2024v0-report.xls"]["retrieved_at"],
            license="No explicit data license identified; cite the Delaware Population Consortium.",
            citation=f"{AGENCY}. Annual Population Projections, October 14, 2024.",
            method_notes=(
                "The last historical point published in these five-year summary tables is 2020; "
                "2025-2050 are projections. Model benchmarking uses later inputs, but the report "
                "does not publish a later estimate in these tables. The 2024 edition was readopted "
                "in December 2025 without a new projection. State and all three counties are "
                "loaded at five-year points; municipal, race/age and seasonal series are excluded. "
                + ("This is the Consortium's jobs by place of work product, not resident "
                   "employment, labor force, or occupational projections." if variable == "employment"
                   else "Publisher household counts are distinct from population and housing units."
                   if variable == "households" else "Resident population only, not seasonal population.")
            ),
        )
        insert_observations(conn, data[variable])
    conn.commit()
    print("DE load: 84 observations")


def verify(conn) -> None:
    expected = {("population", "10", 2050): 1171796,
                ("population", "10001", 2025): 191801,
                ("population", "10005", 2050): 369545,
                ("households", "10", 2050): 438806,
                ("employment", "10", 2050): 494222,
                ("employment", "10003", 2025): 296178}
    for (variable, gid, year), value in expected.items():
        row = conn.execute("SELECT value, datatype, source_id FROM observations WHERE "
                           "state='DE' AND variable=? AND geo_id=? AND year=?",
                           (variable, gid, year)).fetchone()
        assert tuple(row) == (value, "projection", PRODUCTS[variable][2])
    for variable in PRODUCTS:
        shape = conn.execute("SELECT COUNT(*),COUNT(DISTINCT geo_id),COUNT(DISTINCT year),"
                             "MIN(year),MAX(year) FROM observations WHERE state='DE' AND variable=?",
                             (variable,)).fetchone()
        assert tuple(shape) == (28, 4, 7, 2020, 2050)
    print("DE verify: fixtures, product labels and grids ok")


if __name__ == "__main__":
    if "--acquire" in sys.argv:
        acquire()
    else:
        print("usage: python -m sdo_mcp.ingest.de --acquire")
