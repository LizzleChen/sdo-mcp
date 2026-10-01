"""UMass Donahue Institute Vintage 2024 published state/county totals.

The 2020 launch includes Census challenge and child-undercount adjustments.
Keep original fractional historical cells; future points are not interpolated.
"""
from __future__ import annotations

import io
import math
import sys
from datetime import date, datetime

from ..common import fetch
from ..store import REPO_ROOT, insert_observations, upsert_source
from .seed import COUNTY_FILE

RAW_DIR = REPO_ROOT / "data" / "raw" / "ma"
CATALOG_URL = "https://www.umass.edu/donahue/research-and-data/massachusetts-population-estimates-program/population-projections"
URL = "https://www.umass.edu/donahue/media/2441/download?attachment="
DETAIL_URL = "https://www.umass.edu/donahue/media/2443/download?attachment="
METHOD_URL = "https://www.umass.edu/donahue/media/2445/download?attachment="
FILE = "population_v2024.xlsx"
DETAIL_FILE = "population_age_sex_v2024.xlsx"
METHOD_FILE = "population_methods_v2024.pdf"
CATALOG_FILE = "projection_catalog_2026-10-01.html"
FILES = {FILE: URL, DETAIL_FILE: DETAIL_URL, METHOD_FILE: METHOD_URL, CATALOG_FILE: CATALOG_URL}
SOURCE_ID = "ma-pop-v2024"
AGENCY = "University of Massachusetts Donahue Institute, Population Estimates Program"
VINTAGE = "Vintage 2024 (May 2024)"
YEARS = tuple(range(2020, 2051, 5))
ALL_YEARS = (2010, *YEARS)
AGES = tuple(f"{age}-{age + 4}" for age in range(0, 85, 5)) + ("85+",)
TOTAL_SHEETS = ["Source", "CityTown Pop Totals 2010-2050", "County Pop Totals 2010-2050",
                "RPA Pop Totals 2010-2050", "State Pop Totals 2010-2050", "RPA Codes", "RPA Crosswalk"]
DETAIL_SHEETS = ["Source", "CityTown Age_Sex 2010-2050", "CityTown Age 2010-2050",
                 "County Age_Sex 2010-2050", "County Age 2010-2050", "RPA Age_Sex 2010-2050",
                 "RPA Age 2010-2050", "State Age_Sex 2010-2050", "State Age 2010-2050",
                 "RPA Codes", "RPA Crosswalk"]
SOURCE_ROWS = (("Long-Term Population Projections for Massachusetts Cities and Towns",),
               ("UMass Donahue Institute Population Estimates Program",), ("Vintage 2024",),
               ("May 9, 20204",), (None,), ("suggested citation:",),
               ("UMass Donahue Institute V2024 Population Projections",), ("May 2024",))
RPAS = {"BRPC", "CCC", "CMRPC", "FRCOG", "MAPC", "MRPC", "MVC", "MVPC", "NMCOG",
        "NPEDC", "OCPC", "PVPC", "SRPEDD"}


def _counties() -> dict[str, str]:
    counties = {}
    for line in COUNTY_FILE.read_text().splitlines()[1:]:
        fields = line.split("|")
        if fields[0] == "MA":
            counties[fields[4].removesuffix(" County")] = fields[1] + fields[2]
    if len(counties) != 14:
        raise ValueError("MA: expected 14 Census counties")
    return counties


def _number(value, year: int) -> int | float:
    if (type(value) not in (int, float) or not math.isfinite(value) or value < 0
            or (year != 2020 and int(value) != value)):
        raise ValueError(f"MA: invalid population value for {year}: {value!r}")
    return value


def _close(left, right) -> bool:
    # Summing the published adjusted 2020 cells introduces tiny binary errors.
    return math.isclose(left, right, rel_tol=0, abs_tol=1e-8)


def _grid(grid, header, count: int, label: str) -> None:
    if (len(grid) != count + 1 or tuple(grid[0]) != header
            or any(len(row) != len(header) for row in grid)):
        raise ValueError(f"MA: unexpected {label} header or shape")


def _read_workbook(body: bytes, sheets: list[str], selected: list[str]) -> dict:
    import openpyxl

    try:
        book = openpyxl.load_workbook(io.BytesIO(body), read_only=True, data_only=True)
    except Exception as exc:
        raise ValueError("MA: response is not a readable XLSX workbook") from exc
    try:
        modified = (datetime(2024, 10, 16, 17, 39, 58) if sheets == TOTAL_SHEETS
                    else datetime(2024, 10, 16, 17, 47, 14))
        if (book.sheetnames != sheets or book.properties.creator != "Denis McAuliffe"
                or book.properties.modified != modified
                or tuple(book["Source"].values) != SOURCE_ROWS):
            raise ValueError("MA: unexpected workbook sheets, producer or edition")
        return {name: list(book[name].values) for name in selected}
    finally:
        book.close()


def _parse_total_grids(grids: dict) -> list[dict]:
    counties = _counties()
    county_grid = grids["County Pop Totals 2010-2050"]
    state_grid = grids["State Pop Totals 2010-2050"]
    municipal_grid = grids["CityTown Pop Totals 2010-2050"]
    rpa_grid = grids["RPA Pop Totals 2010-2050"]
    _grid(county_grid, ("County", "County Code", *ALL_YEARS), 14, "county totals")
    _grid(state_grid, ("State", *ALL_YEARS), 1, "state totals")
    _grid(municipal_grid, ("Municipality", "MCD Code", "County", "County Code", "RPA", *ALL_YEARS),
          351, "municipal totals")
    _grid(rpa_grid, ("RPA", *ALL_YEARS), 13, "RPA totals")
    totals = {}
    for source in county_grid[1:]:
        name, code, *values = source
        if name not in counties or code != counties[name][-2:]:
            raise ValueError(f"MA: unknown county or mismatched county code {name!r}")
        if name in totals:
            raise ValueError(f"MA: duplicate county {name}")
        totals[name] = tuple(_number(value, year) for year, value in zip(ALL_YEARS, values, strict=True))
    if set(totals) != set(counties) or state_grid[1][0] != "Massachusetts":
        raise ValueError("MA: incomplete or changed state/county geography grid")
    totals["Massachusetts"] = tuple(_number(value, year)
                                    for year, value in zip(ALL_YEARS, state_grid[1][1:], strict=True))
    municipalities = {}
    codes = set()
    for source in municipal_grid[1:]:
        name, code, county, county_code, rpa, *values = source
        if (not isinstance(name, str) or not name or name in municipalities
                or type(code) is not int or code not in range(1, 352) or code in codes
                or county not in counties or county_code != counties[county][-2:] or rpa not in RPAS):
            raise ValueError("MA: invalid or duplicate municipal geography/code")
        codes.add(code)
        municipalities[name] = (county, rpa, tuple(_number(value, year)
                                   for year, value in zip(ALL_YEARS, values, strict=True)))
    if codes != set(range(1, 352)):
        raise ValueError("MA: incomplete municipal code grid")
    regional_totals = {}
    for name, *values in rpa_grid[1:]:
        if name not in RPAS or name in regional_totals:
            raise ValueError("MA: unknown or duplicate RPA")
        regional_totals[name] = tuple(_number(value, year)
                                    for year, value in zip(ALL_YEARS, values, strict=True))
    if set(regional_totals) != RPAS:
        raise ValueError("MA: incomplete RPA grid")
    for index, year in enumerate(ALL_YEARS):
        if not _close(math.fsum(totals[name][index] for name in counties), totals["Massachusetts"][index]):
            raise ValueError(f"MA: county/state totals do not reconcile in {year}")
        for name, values in totals.items():
            selected = [row[2][index] for row in municipalities.values()
                        if name == "Massachusetts" or row[0] == name]
            if not _close(math.fsum(selected), values[index]):
                raise ValueError(f"MA: municipal/county totals do not reconcile for {name}/{year}")
        for name, values in regional_totals.items():
            if not _close(math.fsum(row[2][index] for row in municipalities.values() if row[1] == name),
                          values[index]):
                raise ValueError(f"MA: municipal/RPA totals do not reconcile for {name}/{year}")
    geos = counties | {"Massachusetts": "25"}
    return [dict(state="MA", geo_level="state" if name == "Massachusetts" else "county",
                 geo_id=geos[name], year=year, variable="population", value=value,
                 datatype="estimate" if year == 2020 else "projection", source_id=SOURCE_ID)
            for name, values in totals.items()
            for year, value in zip(ALL_YEARS, values, strict=True) if year >= 2020]


def parse(body: bytes) -> list[dict]:
    """Serve the publisher's exact total cells, including fractional base values."""
    selected = [name for name in TOTAL_SHEETS if "Pop Totals" in name]
    return _parse_total_grids(_read_workbook(body, TOTAL_SHEETS, selected))


def _validate_age_grids(grids: dict, rows: list[dict]) -> None:
    """Check every served total against a separately published age/sex workbook."""
    counties = _counties()
    cells = {}
    for level in ("County", "State"):
        geos = counties if level == "County" else {"Massachusetts": "25"}
        for has_sex in (False, True):
            sheet = f"{level} {'Age_Sex' if has_sex else 'Age'} 2010-2050"
            header = (level,) + (("County Code",) if level == "County" else ())
            header += ("Age Group", "Age") + (("Sex",) if has_sex else ()) + ALL_YEARS
            _grid(grids[sheet], header, len(geos) * 18 * (2 if has_sex else 1), sheet)
            start = 2 if level == "County" else 1
            seen = set()
            for source in grids[sheet][1:]:
                name = source[0]
                if name not in geos or (level == "County" and source[1] != geos[name][-2:]):
                    raise ValueError("MA: unknown age/sex geography or county code")
                age_code, age = source[start:start + 2]
                sex = source[start + 2] if has_sex else "all"
                if (type(age_code) is not int or age_code not in range(1, 19)
                        or age != AGES[age_code - 1] or sex not in (("Male", "Female") if has_sex else ("all",))):
                    raise ValueError("MA: changed age/sex category")
                key = geos[name], age, sex
                if key in seen:
                    raise ValueError("MA: duplicate age/sex geography/category")
                seen.add(key)
                values = source[start + 2 + int(has_sex):]
                for year, value in zip(ALL_YEARS, values, strict=True):
                    cells[*key, year] = _number(value, year)
            expected = {(gid, age, sex) for gid in geos.values() for age in AGES
                        for sex in (("Male", "Female") if has_sex else ("all",))}
            if seen != expected:
                raise ValueError("MA: incomplete age/sex grid")
    geos = counties | {"Massachusetts": "25"}
    for year in ALL_YEARS:
        for gid in geos.values():
            for age in AGES:
                if not _close(cells[gid, age, "Male", year] + cells[gid, age, "Female", year],
                              cells[gid, age, "all", year]):
                    raise ValueError("MA: age/sex cells do not reconcile")
        for age in AGES:
            for sex in ("Male", "Female", "all"):
                if not _close(math.fsum(cells[gid, age, sex, year] for gid in counties.values()),
                              cells["25", age, sex, year]):
                    raise ValueError("MA: county/state age/sex cells do not reconcile")
    for row in rows:
        if not _close(math.fsum(cells[row["geo_id"], age, "all", row["year"]] for age in AGES), row["value"]):
            raise ValueError("MA: totals disagree with independent age/sex workbook")


def _validate_detail(body: bytes, rows: list[dict]) -> None:
    selected = [name for name in DETAIL_SHEETS if name.startswith(("County Age", "State Age"))]
    _validate_age_grids(_read_workbook(body, DETAIL_SHEETS, selected), rows)


def _method_pages(body: bytes) -> list[str]:
    from pypdf import PdfReader

    fetch.validate_pdf(body, "MA methodology")
    reader = PdfReader(io.BytesIO(body))
    if len(reader.pages) != 39:
        raise ValueError("MA: unexpected methodology page count")
    return [" ".join(page.extract_text().split()) for page in reader.pages]


def _validate_method(body: bytes) -> None:
    pages = _method_pages(body)
    markers = {0: ("Vintage 2024 Methodology Statement", "May 9, 2024"),
               6: ("Massachusetts Secretary of the Commonwealth", "UMass Donahue", "Vintage 2024"),
               19: ("2020 Decennial Census", "population challenges and child undercounts"),
               30: ("351 Massachusetts MCDs", "The initial launch year is 2020", "from 2025 to 2050"),
               32: ("population challenge and child undercount", "adjusted 2020 population")}
    if any(marker not in pages[index] for index, wanted in markers.items() for marker in wanted):
        raise ValueError("MA: unexpected methodology edition, producer or launch boundary")


def _validate_catalog(body: bytes) -> None:
    text = " ".join(body.decode("utf-8", "replace").lower().split())
    if any(marker not in text for marker in ("<html", "massachusetts secretary of the commonwealth",
                 "umdi vintage 2024", "/media/2441/download", "/media/2443/download", "/media/2445/download",
                 "each city, town, county, and the state total", "2020 launch populations")):
        raise ValueError("MA: invalid publisher catalog or missing selected edition links")


def _validate_all(bodies: dict[str, bytes]) -> list[dict]:
    _validate_catalog(bodies[CATALOG_FILE])
    _validate_method(bodies[METHOD_FILE])
    rows = parse(bodies[FILE])
    _validate_detail(bodies[DETAIL_FILE], rows)
    return rows


def acquire() -> None:
    if (RAW_DIR / "manifest.json").exists():
        if {entry["file"] for entry in fetch.read_manifest(RAW_DIR)} != set(FILES):
            raise ValueError("MA: incomplete saved manifest")
        _validate_all({name: (RAW_DIR / name).read_bytes() for name in FILES})
        print("MA acquire: reused validated Vintage 2024 snapshots")
        return
    bodies = {name: fetch.get_bytes(url) for name, url in FILES.items()}
    rows = _validate_all(bodies)
    entries = []
    for name, url in FILES.items():
        fetch.write_snapshot(RAW_DIR / name, bodies[name])
        entries.append(dict(file=name, source=url, retrieved_at=date.today().isoformat(),
                            sha256=fetch.sha256(bodies[name]), records=len(rows) if name == FILE else None,
                            note="Unmodified UMass Donahue Institute Vintage 2024 original or current catalog. Exact adjusted 2020 launch and five-year 2025-2050 state/county totals checked against the separately published age/sex workbook. Municipal/RPA and demographic detail archived but not served."))
    fetch.write_manifest(RAW_DIR, entries)


def load(conn) -> None:
    entries = {entry["file"]: entry for entry in fetch.read_manifest(RAW_DIR)}
    if set(entries) != set(FILES):
        raise ValueError("MA: incomplete saved manifest")
    rows = _validate_all({name: (RAW_DIR / name).read_bytes() for name in FILES})
    seeded = {(row["geo_level"], row["geo_id"]) for row in conn.execute("SELECT * FROM geographies WHERE state='MA'")}
    if seeded != {(row["geo_level"], row["geo_id"]) for row in rows}:
        raise ValueError("MA: seeded geographies differ from publication")
    upsert_source(conn, source_id=SOURCE_ID, state="MA", agency=AGENCY,
        product_name="UMDI V2024 Population Projections: Total Population; state and county totals",
        vintage=VINTAGE, base_year=2020, horizon_year=2050, source_url=URL,
        retrieved_at=entries[FILE]["retrieved_at"],
        license="No explicit data license identified; cite UMass Donahue Institute V2024 Population Projections.",
        citation="UMass Donahue Institute V2024 Population Projections. May 2024. State Pop Totals 2010-2050 and County Pop Totals 2010-2050 sheets.",
        method_notes=("Cohort-component population projections produced with support from the Massachusetts Secretary of the Commonwealth. "
            "2020 is the historical launch and carries the schema's estimate flag; 2025-2050 are projections at exact five-year points. "
            "The 2020 launch comes from Census 2020 DHC with population challenge and child-undercount adjustments; it is not the unadjusted Census count. "
            "Fractional 2020 workbook totals are preserved at source precision. The separately published state row is served directly, and its county "
            "and municipal sums reconcile within binary floating point precision. All served totals also match the independently published "
            "age/sex workbook; future total cells are integers. No intermediate years or demographic dimensions are generated. "
            "The methods cover gives May 9, 2024; the workbooks' Source tab has the literal typo 'May 9, 20204' plus the clear 'Vintage 2024' and 'May 2024' labels. "
            "Both archived workbooks were last modified October 16, 2024, but an additional revision designation was not established. "
            "UMDI cautions that small geographies and distant horizons have greater uncertainty. All 351 municipalities, 13 RPA total rows, and "
            "age/sex detail are published and archived but not loaded. Municipal MCD codes are not Census place FIPS; town identifiers require "
            "county-subdivision identifiers to be loaded. Household-count, complete future components, and eligible SDO jobs coverage remain unverified; "
            "the methodology's older MassDOT employment work is not substituted for the population series."))
    insert_observations(conn, rows)
    conn.commit()
    print(f"MA load: {len(rows)} observations")


# Independently inspected in original total-workbook XML, then corroborated by
# summing the separately published age/sex workbook (no generated fixture file).
FIXTURES = (("25", 2020, 7039146.791183238), ("25", 2025, 7078114),
            ("25", 2035, 7122364), ("25", 2050, 7021497),
            ("25001", 2020, 229215.99999999997), ("25001", 2050, 169939),
            ("25011", 2020, 71122.2067), ("25017", 2050, 1672330),
            ("25019", 2050, 15555), ("25025", 2050, 892646))


def verify(conn) -> None:
    rows = conn.execute("SELECT * FROM observations WHERE state='MA'").fetchall()
    geos = {"25", *_counties().values()}
    assert len(rows) == 105 and {(row["geo_id"], row["year"]) for row in rows} == {(gid, year) for gid in geos for year in YEARS}
    assert all(row["source_id"] == SOURCE_ID and row["variable"] == "population" and row["scenario"] == ""
               and row["age_group"] == row["sex"] == row["race"] == "all"
               and row["datatype"] == ("estimate" if row["year"] == 2020 else "projection")
               and row["geo_level"] == ("state" if row["geo_id"] == "25" else "county")
               and math.isfinite(row["value"]) and row["value"] >= 0
               and (row["year"] == 2020 or float(row["value"]).is_integer()) for row in rows)
    values = {(row["geo_id"], row["year"]): row["value"] for row in rows}
    for gid, year, value in FIXTURES:
        assert values[gid, year] == value, (gid, year, value, values[gid, year])
    for year in YEARS:
        assert _close(math.fsum(values[gid, year] for gid in geos - {"25"}), values["25", year])
    source = conn.execute("SELECT * FROM sources WHERE source_id=?", (SOURCE_ID,)).fetchone()
    assert (source["vintage"], source["base_year"], source["horizon_year"]) == (VINTAGE, 2020, 2050)
    print("MA verify: published totals, precision, flags and full geography grid passed")


if __name__ == "__main__":
    if sys.argv[1:] != ["acquire"]:
        raise SystemExit("usage: python -m sdo_mcp.ingest.ma acquire")
    acquire()
