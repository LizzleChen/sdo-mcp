"""UNM Geospatial and Population Studies spring-2024 county totals."""

from __future__ import annotations

import io
import re
import sys
import unicodedata
from datetime import date

from ..common import fetch
from ..store import REPO_ROOT, insert_observations, upsert_source
from .seed import COUNTY_FILE

RAW_DIR = REPO_ROOT / "data" / "raw" / "nm"
CATALOG_URL = "https://gps.unm.edu/pop/population-projections.html"
WORKBOOK_URL = "https://gps.unm.edu/assets/documents/census/new-mexico-county-projections-total-and-by-agesex-xlsx.xlsx"
PDF_URL = "https://gps.unm.edu/assets/documents/census/nmcountyprojections_v2024.pdf"
METHOD_URL = "https://gps.unm.edu/assets/documents/census/2024-gps-projections-methodology.pdf"
FILES = {
    "projection_catalog_2026-09-30.html": CATALOG_URL,
    "county_totals_spring2024.xlsx": WORKBOOK_URL,
    "county_projections_spring2024.pdf": PDF_URL,
    "methodology_spring2024.pdf": METHOD_URL,
}
SOURCE_ID = "nm-pop-spring2024"
YEARS = (2010, 2020, 2025, 2030, 2035, 2040, 2045, 2050)
HEADERS = ("County", "Census2010", "Census2020", "Projected2025", "Projected2030",
           "Projected2035", "Projected2040", "Projected2045", "Projected2050")
NUMBER = re.compile(r"(?:0|[1-9]\d{0,2}(?:,\d{3})*)\Z")


def _key(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", value)
                   if not unicodedata.combining(c)).removesuffix(" County")


def _counties() -> dict[str, str]:
    result = {}
    for line in COUNTY_FILE.read_text().splitlines()[1:]:
        parts = line.split("|")
        if parts[0] == "NM":
            result[_key(parts[4])] = parts[1] + parts[2]
    if len(result) != 33:
        raise ValueError("NM: expected 33 Census counties")
    return result


def parse_workbook(body: bytes) -> list[dict]:
    import openpyxl

    try:
        book = openpyxl.load_workbook(io.BytesIO(body), read_only=True, data_only=True)
    except Exception as exc:
        raise ValueError("NM: response is not a readable XLSX workbook") from exc
    try:
        if not book.sheetnames or book.sheetnames[0] != "CountyTotals_v2024":
            raise ValueError("NM: unexpected workbook summary sheet")
        sheet = book.worksheets[0]
        # The publisher workbook incorrectly declares A1 as its entire used
        # range. openpyxl otherwise hides the 36 remaining summary rows.
        sheet.reset_dimensions()
        grid = list(sheet.iter_rows(values_only=True))
        if len(grid) != 37 or any(len(row) != 9 for row in grid):
            raise ValueError("NM: unexpected county totals layout")
        if (grid[0][0] != "Population Projections for New Mexico Counties, 2010-2050"
                or tuple(grid[1]) != HEADERS
                or grid[36][1] != "Produced by Geospatial and Population Studies (UNM-GPS). Vintage: Spring 2024"):
            raise ValueError("NM: unexpected title, year header or edition")
        counties = _counties()
        names = [row[0] for row in grid[2:35]]
        if (len(set(names)) != 33 or {_key(name) for name in names} != set(counties)
                or set(book.sheetnames[1:]) != set(names) or len(book.sheetnames) != 34):
            raise ValueError("NM: missing or duplicate county geography")
        if grid[35][0] != "NM Total":
            raise ValueError("NM: missing published state total")
        rows = []
        values = {}
        for row in grid[2:36]:
            name = row[0]
            gid = "35" if name == "NM Total" else counties[_key(name)]
            if any(not isinstance(v, str) or not NUMBER.fullmatch(v) for v in row[1:]):
                raise ValueError(f"NM: invalid population value for {name}")
            numbers = tuple(int(v.replace(",", "")) for v in row[1:])
            values[gid] = numbers
            rows.extend({
                "state": "NM", "geo_level": "state" if gid == "35" else "county",
                "geo_id": gid, "year": year, "variable": "population", "value": number,
                "datatype": "estimate" if year == 2020 else "projection",
                "source_id": SOURCE_ID,
            } for year, number in zip(YEARS, numbers) if year >= 2020)
        # County and state totals are independently rounded. The largest
        # published difference is five people; never change either value.
        differences = tuple(values["35"][i] - sum(v[i] for gid, v in values.items() if gid != "35")
                            for i in range(len(YEARS)))
        if differences != (0, 0, 1, -2, 0, 2, 2, -5):
            raise ValueError(f"NM: unexpected county/state rounding pattern: {differences}")
        return rows
    finally:
        book.close()


def _validate_catalog(body: bytes) -> None:
    page = " ".join(body.decode("utf-8", "replace").lower().split())
    for marker in ("<html", "population projections", "new-mexico-county-projections-total-and-by-agesex-xlsx.xlsx",
                   "2024-gps-projections-methodology.pdf", "nm population projections, 2023"):
        if marker not in page:
            raise ValueError(f"NM: invalid projection catalog; missing {marker!r}")


def _validate_pdf(body: bytes, *, method: bool) -> None:
    from pypdf import PdfReader

    fetch.validate_pdf(body, "NM methodology" if method else "NM county projections")
    reader = PdfReader(io.BytesIO(body))
    text = " ".join((" ".join(page.extract_text() for page in reader.pages[:2])).split())
    markers = (("Methodology Statement", "2022 population estimates", "33 counties") if method
               else ("Population Projections for New Mexico Counties", "Bernalillo", "2,098,886", "164,745"))
    for marker in markers:
        if marker not in text:
            raise ValueError(f"NM: invalid publisher PDF; missing {marker!r}")


def _validate_file(name: str, body: bytes) -> None:
    if name.endswith(".xlsx"):
        parse_workbook(body)
    elif name.endswith(".html"):
        _validate_catalog(body)
    else:
        _validate_pdf(body, method=name.startswith("methodology"))


def acquire() -> None:
    if (RAW_DIR / "manifest.json").exists():
        entries = {e["file"] for e in fetch.read_manifest(RAW_DIR)}
        if entries != set(FILES):
            raise ValueError("NM: incomplete saved snapshot manifest")
        for name in FILES:
            _validate_file(name, (RAW_DIR / name).read_bytes())
        print("NM acquire: reused validated snapshots")
        return
    snapshots = []
    for name, url in FILES.items():
        body = fetch.get_bytes(url)
        _validate_file(name, body)
        snapshots.append((name, url, body))
    entries = []
    for name, url, body in snapshots:
        fetch.write_snapshot(RAW_DIR / name, body)
        entries.append({"file": name, "source": url, "retrieved_at": date.today().isoformat(),
                        "sha256": fetch.sha256(body), "records": 238 if name.endswith(".xlsx") else None,
                        "note": "Original UNM-GPS spring-2024 publication; workbook and PDF totals were cross-checked."})
    fetch.write_manifest(RAW_DIR, entries)


def load(conn) -> None:
    entries = {e["file"]: e for e in fetch.read_manifest(RAW_DIR)}
    for name in FILES:
        _validate_file(name, (RAW_DIR / name).read_bytes())
    rows = parse_workbook((RAW_DIR / "county_totals_spring2024.xlsx").read_bytes())
    upsert_source(
        conn, source_id=SOURCE_ID, state="NM", agency="University of New Mexico Geospatial and Population Studies",
        product_name="New Mexico state and county population projections", vintage="Spring 2024",
        base_year=2022, horizon_year=2050, source_url=WORKBOOK_URL,
        retrieved_at=entries["county_totals_spring2024.xlsx"]["retrieved_at"],
        license="No explicit data license identified; cite UNM Geospatial and Population Studies.",
        citation="UNM Geospatial and Population Studies. NM Population Projections, 2023-2050. 2024.",
        method_notes=(
            "The Spring 2024 methodology identifies 2022 population estimates as the model launch "
            "population. The selected county workbook publishes 2020 Census history and projections "
            "at five-year points from 2025 to 2050; it does not publish 2022 or 2023 totals in this "
            "summary. State totals are read from its NM Total row, not constructed from counties. "
            "County/state sums differ by at most five people from rounding; values are preserved. "
            "The companion publisher PDF agrees with the workbook. The HTML page differs in at "
            "least one displayed cell (Santa Fe 2030), so it is not used as the data source. "
            "Age/sex and annual state detail are archived or linked but not served."
        ),
    )
    insert_observations(conn, rows)
    conn.commit()
    print(f"NM load: {len(rows)} observations")


def verify(conn) -> None:
    fixtures = {("35", 2020): (2117527, "estimate"),
                ("35", 2025): (2143658, "projection"),
                ("35", 2050): (2098886, "projection"),
                ("35001", 2050): (681386, "projection"),
                ("35021", 2050): (471, "projection"),
                ("35049", 2030): (164745, "projection")}
    for (gid, year), expected in fixtures.items():
        row = conn.execute("SELECT value, datatype FROM observations WHERE "
                           "state='NM' AND variable='population' AND geo_id=? AND year=?",
                           (gid, year)).fetchone()
        assert tuple(row) == expected
    shape = conn.execute("SELECT COUNT(*),COUNT(DISTINCT geo_id),COUNT(DISTINCT year),"
                         "MIN(year),MAX(year) FROM observations WHERE state='NM'").fetchone()
    assert tuple(shape) == (238, 34, 7, 2020, 2050)
    print("NM verify: publisher PDF fixtures, complete grid and boundary ok")


if __name__ == "__main__":
    if "--acquire" in sys.argv:
        acquire()
    else:
        print("usage: python -m sdo_mcp.ingest.nm --acquire")
