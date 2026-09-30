"""New Hampshire OPD September 2022 state and county population totals.

Checked PDF Table 1, independently compared with Appendix A total rows.
"""
from __future__ import annotations

import io
import re
import sys
from datetime import date

from ..common import fetch
from ..store import REPO_ROOT, insert_observations, upsert_source
from .seed import COUNTY_FILE

RAW_DIR = REPO_ROOT / "data" / "raw" / "nh"
URL = "https://www.nheconomy.com/getmedia/0205c62d-9c30-4b00-9c9e-d81d8f17b8b3/NH-Population-Projections-2020-2050-Final-Report-092022.pdf"
CATALOG_URL = "https://www.nheconomy.com/office-of-planning-and-development/what-we-do/state-data-center-(census-data)/population-projections"
FILE = "population_2020-2050_sep2022.pdf"
CATALOG_FILE = "projection_catalog_2026-09-30.html"
FILES = {FILE: URL, CATALOG_FILE: CATALOG_URL}
SOURCE_ID = "nh-pop-sep2022-table1"
AGENCY = "New Hampshire Office of Planning and Development, Department of Business and Economic Affairs"
VINTAGE = "September 2022"
YEARS = tuple(range(2020, 2051, 5))
TABLE_TITLE = "Table 1: Summary of Projected Total Population for New Hampshire and Counties"
# PDF page indices: Table 1 is printed page 3; Appendix A Tables 6-16 are A24-A34.
TABLE_PAGE = 5
CHECK_PAGES = tuple(range(51, 62))
COUNTY_STATE_DIFFERENCES = (0, 0, -1, 0, 0, 0, 0)


def _geographies() -> dict[str, str]:
    geos = {"New Hampshire": "33"}
    for line in COUNTY_FILE.read_text().splitlines()[1:]:
        fields = line.split("|")
        if fields[0] == "NH":
            geos[fields[4].removesuffix(" County")] = fields[1] + fields[2]
    if len(geos) != 11:
        raise ValueError("NH: expected state and all 10 counties")
    return geos


def _integer(token: str) -> int:
    if not re.fullmatch(r"(?:0|[1-9]\d{0,2}(?:,\d{3})*|[1-9]\d*)", token):
        raise ValueError(f"NH: invalid integer population {token!r}")
    return int(token.replace(",", ""))


def _parse_table(text: str) -> list[dict]:
    lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
    if (not lines or lines[0] != "Page 3" or TABLE_TITLE not in lines
            or "State/County 2020" not in lines
            or "Census 2025 2030 2035 2040 2045 2050" not in lines):
        raise ValueError("NH: unexpected Table 1 header or year grid")
    start = lines.index("Census 2025 2030 2035 2040 2045 2050") + 1
    data = lines[start:]
    if len(data) != 11:
        raise ValueError("NH: incomplete Table 1 geography grid")
    geos = _geographies()
    seen = set()
    rows = []
    for line in data:
        parts = line.rsplit(" ", 7)
        if len(parts) != 8:
            raise ValueError("NH: malformed Table 1 population row")
        name, *cells = parts
        if name not in geos:
            raise ValueError(f"NH: unknown geography {name!r}")
        if name in seen:
            raise ValueError(f"NH: duplicate geography {name}")
        seen.add(name)
        values = [_integer(cell) for cell in cells]
        rows.extend(dict(state="NH", geo_level="state" if geos[name] == "33" else "county",
                         geo_id=geos[name], year=year, variable="population", value=value,
                         datatype="estimate" if year == 2020 else "projection", source_id=SOURCE_ID)
                    for year, value in zip(YEARS, values, strict=True))
    if seen != set(geos):
        raise ValueError("NH: incomplete geography grid")
    for year, difference in zip(YEARS, COUNTY_STATE_DIFFERENCES, strict=True):
        state = next(row["value"] for row in rows if row["geo_id"] == "33" and row["year"] == year)
        county = sum(row["value"] for row in rows if row["geo_level"] == "county" and row["year"] == year)
        if county - state != difference:
            raise ValueError(f"NH: unexpected county/state difference in {year}")
    return rows


def _parse_appendix(pages: list[str]) -> dict[tuple[str, int], int]:
    geos = _geographies()
    if len(pages) != 11:
        raise ValueError("NH: incomplete Appendix A check pages")
    check = {}
    for i, (name, gid) in enumerate(geos.items()):
        text = "\n".join(" ".join(line.split()) for line in pages[i].splitlines() if line.strip())
        label = name if i == 0 else name + " County"
        title = f"Table {i + 6}: Projected Populations for {label} by Age Groups and Sex"
        if (title not in text or "2020 2025 2030 2035" not in text
                or "2040 2045 2050" not in text):
            raise ValueError("NH: unexpected Appendix A table or year header")
        totals = re.findall(r"^Total (.+)$", text, re.M)
        if len(totals) != 2:
            raise ValueError("NH: missing or duplicate Appendix A total rows")
        for total, years in zip(totals, (YEARS[:4], YEARS[4:]), strict=True):
            cells = [_integer(token) for token in total.split()]
            if len(cells) != 3 * len(years):
                raise ValueError("NH: incomplete Appendix A population total")
            for year, (male, female, value) in zip(years, zip(cells[::3], cells[1::3], cells[2::3]), strict=True):
                if male + female != value:
                    raise ValueError("NH: Appendix A sex totals do not reconcile")
                check[gid, year] = value
    return check


def _validate_edition(cover: str, foreword: str) -> None:
    cover = " ".join(cover.split())
    foreword = " ".join(foreword.split())
    if ("September 2022" not in cover or "Population Projections: 2020-2050" not in cover
            or "Office of Planning and Development" not in cover or "RLS Demographics, Inc." not in cover
            or "based on the 2020 U.S. Census" not in foreword
            or "prepared by OPD’s consultant, Robert Scardamalia of RLS Demographics" not in foreword):
        raise ValueError("NH: unexpected report edition, producer or base year")


def parse(body: bytes) -> list[dict]:
    from pypdf import PdfReader
    fetch.validate_pdf(body, "NH population")
    reader = PdfReader(io.BytesIO(body))
    if len(reader.pages) != 71:
        raise ValueError("NH: unexpected report page count")
    _validate_edition(reader.pages[0].extract_text(), reader.pages[1].extract_text())
    rows = _parse_table(reader.pages[TABLE_PAGE].extract_text())
    checks = _parse_appendix([reader.pages[i].extract_text() for i in CHECK_PAGES])
    if any(checks[row["geo_id"], row["year"]] != row["value"] for row in rows):
        raise ValueError("NH: Table 1 and Appendix A totals disagree")
    return rows


def _validate_catalog(body: bytes) -> None:
    page = " ".join(body.decode("utf-8", "replace").lower().split())
    if any(marker not in page for marker in ("<html", "population projections", "portable document format",
                    "0205c62d-9c30-4b00-9c9e-d81d8f17b8b3", "2020-2050")):
        raise ValueError("NH: invalid publisher catalog or missing selected edition")


def _validate_all(bodies: dict[str, bytes]) -> list[dict]:
    _validate_catalog(bodies[CATALOG_FILE])
    return parse(bodies[FILE])


def acquire() -> None:
    if (RAW_DIR / "manifest.json").exists():
        entries = fetch.read_manifest(RAW_DIR)
        if {e["file"] for e in entries} != set(FILES):
            raise ValueError("NH: incomplete saved manifest")
        _validate_all({name: (RAW_DIR / name).read_bytes() for name in FILES})
        print("NH acquire: reused validated September 2022 snapshots")
        return
    bodies = {name: fetch.get_bytes(url) for name, url in FILES.items()}
    rows = _validate_all(bodies)
    entries = []
    for name, url in FILES.items():
        fetch.write_snapshot(RAW_DIR / name, bodies[name])
        entries.append(dict(file=name, source=url, retrieved_at=date.today().isoformat(), sha256=fetch.sha256(bodies[name]),
                            records=len(rows) if name == FILE else None,
                            note="Original OPD September 2022 publication or current PDF-only catalog. Table 1 state/county totals compared with Appendix A Tables 6-16. Municipal and components tables archived but not served."))
    fetch.write_manifest(RAW_DIR, entries)


def load(conn) -> None:
    entries = {e["file"]: e for e in fetch.read_manifest(RAW_DIR)}
    rows = _validate_all({name: (RAW_DIR / name).read_bytes() for name in FILES})
    geos = {(r["geo_level"], r["geo_id"]) for r in rows}
    seeded = {(r["geo_level"], r["geo_id"]) for r in conn.execute("SELECT * FROM geographies WHERE state='NH'")}
    if seeded != geos:
        raise ValueError("NH: seeded geographies differ from publication")
    upsert_source(conn, source_id=SOURCE_ID, state="NH", agency=AGENCY,
        product_name="State, County, and Municipal Population Projections: 2020-2050; Table 1 totals",
        vintage=VINTAGE, base_year=2020, horizon_year=2050, source_url=URL,
        retrieved_at=entries[FILE]["retrieved_at"],
        license="No explicit data license identified; cite the New Hampshire Office of Planning and Development.",
        citation="New Hampshire Office of Planning and Development / RLS Demographics. State, County, and Municipal Population Projections: 2020-2050. September 2022. Table 1, printed page 3 (PDF page 6).",
        method_notes=("Table 1 publishes population in persons for the state and all 10 counties at five-year points. "
          "The 2020 Census-based values are marked estimate under this schema; base_year=2020 records the historical boundary. "
          "2025-2050 remain projections, with no interpolation. Appendix A Tables 6-16 independently repeat every loaded total. "
          "The cohort-component model was prepared by OPD's consultant RLS Demographics and officially published by OPD. "
          "Table 1 and Appendix A show 2030 state population 1,473,286, one above its county sum and the executive summary's 1,473,285; "
          "published table values are preserved. Appendix B's 2020 Carroll county row is 50,107, four below Table 1 and Appendix A's 50,111; "
          "this adapter consistently selects Table 1. Municipal totals and five-year births/deaths/net migration are archived but not served. "
          "Household population in the methods counts persons and is not a household forecast. No household-count or eligible OPD jobs forecast was established."))
    insert_observations(conn, rows)
    conn.commit()
    print(f"NH load: {len(rows)} observations")


# Independently read from rendered Table 1 and Appendix A.
FIXTURES = (("33", 2020, 1377533), ("33", 2025, 1430601), ("33", 2030, 1473286),
            ("33", 2050, 1501909), ("33001", 2050, 70103), ("33003", 2020, 50111),
            ("33007", 2050, 27428), ("33011", 2050, 471369), ("33019", 2050, 42141))


def verify(conn) -> None:
    rows = conn.execute("SELECT * FROM observations WHERE state='NH'").fetchall()
    expected = {(gid, year) for gid in _geographies().values() for year in YEARS}
    assert len(rows) == 77 and {(r["geo_id"], r["year"]) for r in rows} == expected
    assert all(r["source_id"] == SOURCE_ID and r["variable"] == "population" and r["scenario"] == ""
               and r["age_group"] == r["sex"] == r["race"] == "all"
               and r["datatype"] == ("estimate" if r["year"] == 2020 else "projection")
               and r["geo_level"] == ("state" if r["geo_id"] == "33" else "county")
               and r["value"] >= 0 and float(r["value"]).is_integer() for r in rows)
    values = {(r["geo_id"], r["year"]): r["value"] for r in rows}
    for gid, year, value in FIXTURES:
        assert values[gid, year] == value
    for year, difference in zip(YEARS, COUNTY_STATE_DIFFERENCES, strict=True):
        assert sum(r["value"] for r in rows if r["geo_level"] == "county" and r["year"] == year) - values["33", year] == difference
    print("NH verify: 77 complete totals and rendered fixtures ok")


if __name__ == "__main__":
    if "--acquire" in sys.argv:
        acquire()
    else:
        print("usage: python -m sdo_mcp.ingest.nh --acquire")
