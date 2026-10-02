"""Louisiana's state-commissioned LSU 2009 parish projections, archived originals.

The archive's indirectly inferred 2007 publication date is contradicted by the
original report and author's LSU publication record. Storm-adjusted parishes
have a later estimate anchor than the other parishes of this same edition.
"""
from __future__ import annotations

import csv
import io
import math
import re
import sys
from datetime import date
from zipfile import BadZipFile, ZipFile

from ..common import fetch
from ..store import REPO_ROOT, insert_observations, upsert_source

RAW_DIR = REPO_ROOT / "data" / "raw" / "la"
CATALOG_URL = "https://www.louisiana.gov/demographics-and-geography/"
ORIGINAL_URL = "http://louisiana.gov/Explore/Population_Projections/"
URL = "https://drive.google.com/uc?export=download&id=14faiyMSCeQV9Yx3J7-Sj7DzLzpIGXRXj"
FILE = "lsu_state_parish_projections_2009_archived20210415.zip"
REPORT = "LA Projections Technical Report.pdf"
FILES = {
    FILE: URL,
    "official_projection_catalog_archived20180809.html": "https://web.archive.org/web/20180809115850id_/http://louisiana.gov/Explore/Population_Projections/",
    "demographics_catalog_2026-10-02.html": CATALOG_URL,
    "author_publication_record_2018.pdf": "https://www.lsu.edu/hss/sociology/people/faculty/profiles/cvs/blanchard_cv_fall_2018.pdf",
    "official_state_middle_archived20170131.xls": "https://web.archive.org/web/20170131013214id_/http://louisiana.gov/PopProjections/ExcelFiles/Statewide%20Middle%20Series.xls",
    "official_jefferson_davis_archived20171028.xls": "https://web.archive.org/web/20171028054405id_/http://louisiana.gov/PopProjections/ExcelFiles/Jefferson%20Davis%20Parish.xls",
}
AGENCY = "Louisiana State University Sociology, for Louisiana Division of Administration, Office of Electronic Services"
VINTAGE = "2009 (exact release date unstated)"
YEARS = (2005, 2010, 2015, 2020, 2025, 2030)
SCENARIOS = ("Middle", "Low", "High")
AGES = tuple(f"{i}-{i + 4}" for i in range(0, 85, 5)) + ("85+",)
# Report p22 explicitly lists these 22 storm-adjusted parishes. Source records
# expose the last underlying estimate year, while retaining the 2005 launch.
REBASED_IDS = frozenset(f"22{code:03d}" for code in (
    3, 5, 15, 23, 33, 51, 55, 63, 71, 75, 77, 87, 89, 91, 93, 95, 97, 99, 103, 105, 115, 121))
SOURCE_IDS = {2005: "la-pop-lsu-2009-anchor2005", 2007: "la-pop-lsu-2009-anchor2007"}
STATE_VALUES = {
    "Middle": (4510170, 4369760, 4477680, 4588310, 4699260, 4813420),
    "Low": (4510170, 4265140, 4359240, 4439500, 4506060, 4560230),
    "High": (4510170, 4474930, 4601700, 4758690, 4942340, 5161800),
}
# Original XLS versus report Table 1: the cause/revision date is unstated.
# Preserve the selected published workbook, and reject any new discrepancy.
REPORT_DIFFERENCES = {"22053": (0, 90, 180, 300, 400, 530)}


def roster() -> dict[str, str]:
    with (REPO_ROOT / "data" / "raw" / "census_national_county2020.txt").open() as source:
        rows = {r["STATEFP"] + r["COUNTYFP"]: r["COUNTYNAME"]
                for r in csv.DictReader(source, delimiter="|") if r["STATE"] == "LA"}
    if set(rows) != {f"22{code:03d}" for code in range(1, 128, 2)}:
        raise ValueError("LA: incomplete parish FIPS reference")
    return rows


def _filename(name: str) -> str:
    return name.replace("De Soto", "DeSoto").replace("St.", "St").replace("Catahoula Parish", "Catahoula Parsih") + ".xls"


def _source_id(geo_id: str) -> str:
    return SOURCE_IDS[2007 if geo_id == "22" or geo_id in REBASED_IDS else 2005]


def _number(cell) -> int:
    import xlrd
    value = cell.value
    if cell.ctype != xlrd.XL_CELL_NUMBER or isinstance(value, bool) or not isinstance(value, (int, float)) or \
            not math.isfinite(value) or value < 0 or value % 10:
        raise ValueError("LA: invalid nonnegative population rounded to ten persons")
    return int(value)


def _parse_sheet(sheet, name: str) -> tuple[int, ...]:
    if sheet.nrows != 139 or sheet.ncols != 17:
        raise ValueError("LA: changed worksheet dimensions or year grid")
    allowed_names = {name.replace("De Soto", "DeSoto")}
    if name == "Ascension Parish":
        allowed_names.add("Ascension")  # Original Low/High title omits Parish.
    if sheet.cell_value(0, 0) not in allowed_names:
        raise ValueError("LA: changed parish title")
    note = sheet.cell_value(1, 0)
    if "rounded to the nearest ten persons" not in note or "zeros indicate fewer than 10" not in note:
        raise ValueError("LA: changed precision statement")
    values = []
    for index, year in enumerate(YEARS):
        start = 2 + index * 23
        if sheet.cell_value(start, 0) != f"Detailed {year}" or sheet.cell_value(start, 10) != f"Summary {year}":
            raise ValueError("LA: changed year grid")
        if [sheet.cell_value(start + 1, c) for c in (1, 4, 7)] != ["White", "Black", "Other"] or \
                sheet.row_values(start + 1)[11:] != ["Total"] * 6 or \
                sheet.row_values(start + 2)[11:] != ["Population", "Male", "Female", "White", "Black", "Other"] or \
                [sheet.cell_value(start + 2, c) for c in (1, 2, 4, 5, 7, 8)] != ["Male", "Female"] * 3:
            raise ValueError("LA: changed race, sex or population column header")
        detail = []
        summaries = []
        for offset, age in enumerate(AGES):
            row = start + 3 + offset
            if sheet.cell_value(row, 0) != age or sheet.cell_value(row, 10) != age:
                raise ValueError("LA: missing or changed age grid")
            d = tuple(_number(sheet.cell(row, c)) for c in (1, 2, 4, 5, 7, 8))
            s = tuple(_number(sheet.cell(row, c)) for c in range(11, 17))
            if s != (sum(d), d[0] + d[2] + d[4], d[1] + d[3] + d[5],
                     d[0] + d[1], d[2] + d[3], d[4] + d[5]):
                raise ValueError("LA: detailed and summary cells disagree")
            detail.append(d)
            summaries.append(s)
        total_row = start + 21
        if sheet.cell_value(total_row, 10) != "Total":
            raise ValueError("LA: missing population total row")
        total = tuple(_number(sheet.cell(total_row, c)) for c in range(11, 17))
        if total != tuple(sum(s[c] for s in summaries) for c in range(6)):
            raise ValueError("LA: age cells and published total disagree")
        values.append(total[0])
        if index < 5 and any(sheet.row_values(start + 22)):
            raise ValueError("LA: unexpected extra row between year blocks")
    return tuple(values)


def _report_totals(body: bytes, names: dict[str, str]) -> dict[str, tuple[int, ...]]:
    from pypdf import PdfReader
    fetch.validate_pdf(body, "LA technical report")
    reader = PdfReader(io.BytesIO(body))
    if len(reader.pages) != 23:
        raise ValueError("LA: changed technical report page grid")
    text = " ".join(" ".join((p.extract_text() or "").split()) for p in reader.pages)
    markers = ("developed for the State of Louisiana", "Office of Electronic Services",
               "by Louisiana State University", "January 13th, 2009", "August, 2009",
               "2005 (launch year)", "the 2007 population estimate", "High Series", "through 2020")
    if any(marker not in text for marker in markers):
        raise ValueError("LA: changed producer, edition or estimate anchor methods")
    totals = {}
    pdf_names = {"22031": "DeSoto", "22059": "LaSalle", "22077": "Point Coupee", "22113": "Vermillion"}
    for page in reader.pages[5:7]:
        page_text = page.extract_text() or ""
        if "Projected Total Population for Louisiana Parishes" not in page_text or "2005 2010 2015 2020 2025 2030" not in page_text:
            raise ValueError("LA: changed Table 1 total/year header")
        for line in page_text.splitlines():
            match = re.fullmatch(r"(22\d{3})\s+(.+?)\s*([\d, ]+)", line.strip())
            if not match:
                continue
            fips, label, counts = match.groups()
            geo_id = "22" if fips == "22000" else fips
            expected = "Louisiana" if geo_id == "22" else pdf_names.get(geo_id, names.get(geo_id, "").removesuffix(" Parish"))
            if label.strip() != expected:
                raise ValueError("LA: changed report FIPS/parish roster")
            tokens = re.findall(r"\d{1,3}(?:,\d{3})+", counts)
            if len(tokens) != 6 or re.sub(r"\d{1,3}(?:,\d{3})+|\s+", "", counts):
                raise ValueError("LA: invalid report total/year grid")
            values = tuple(int(token.replace(",", "")) for token in tokens)
            if geo_id in totals:
                if geo_id != "22" or totals[geo_id] != values:
                    raise ValueError("LA: duplicate report parish total")
            totals[geo_id] = values
    if set(totals) != {"22", *names}:
        raise ValueError("LA: incomplete report parish grid")
    return totals


def parse(body: bytes) -> list[dict]:
    import xlrd
    names = roster()
    expected = {REPORT, *(_filename(name) for name in names.values()),
                *(f"Statewide {scenario} Series.xls" for scenario in SCENARIOS)}
    try:
        archive = ZipFile(io.BytesIO(body))
        if set(archive.namelist()) != expected or len(archive.namelist()) != len(expected):
            raise ValueError("LA: incomplete, duplicate or unexpected archive members")
        report = _report_totals(archive.read(REPORT), names)
        rows = []
        for geo_id, name in [("22", "Louisiana"), *names.items()]:
            for scenario in SCENARIOS:
                member = f"Statewide {scenario} Series.xls" if geo_id == "22" else _filename(name)
                workbook = xlrd.open_workbook(file_contents=archive.read(member))
                sheets = [f"Tables-{scenario} Series"] if geo_id == "22" else [f"Tables-{s} Series" for s in SCENARIOS]
                if workbook.sheet_names() != sheets:
                    raise ValueError("LA: changed scenario sheet grid")
                values = _parse_sheet(workbook.sheet_by_name(f"Tables-{scenario} Series"), name)
                if scenario == "Middle" and tuple(v - p for v, p in zip(values, report[geo_id], strict=True)) != REPORT_DIFFERENCES.get(geo_id, (0,) * 6):
                    raise ValueError("LA: workbook differs from original report Table 1")
                if geo_id == "22" and values != STATE_VALUES[scenario]:
                    raise ValueError("LA: changed independently checked state scenario totals")
                rows.extend(dict(state="LA", geo_level="state" if geo_id == "22" else "county", geo_id=geo_id,
                    year=year, variable="population", value=value, datatype="estimate" if year == 2005 else "projection",
                    scenario=scenario.lower(), source_id=_source_id(geo_id)) for year, value in zip(YEARS, values, strict=True))
    except (BadZipFile, xlrd.XLRDError, KeyError) as exc:
        raise ValueError("LA: unreadable original ZIP/XLS projection product") from exc
    # Repeated 2005 estimates should be identical across scenarios.
    for geo_id in ("22", *names):
        if len({r["value"] for r in rows if r["geo_id"] == geo_id and r["year"] == 2005}) != 1:
            raise ValueError("LA: inconsistent 2005 estimate across scenarios")
    return rows


def _validate_all(bodies: dict[str, bytes]) -> list[dict]:
    from pypdf import PdfReader
    import xlrd
    rows = parse(bodies[FILE])
    catalog = bodies["official_projection_catalog_archived20180809.html"].decode("utf-8", "replace")
    if "<html" not in catalog.lower() or any(marker not in catalog for marker in (
        "Population Projections", "LA Projections Technical Report.pdf", "Statewide Middle Series.xls", "Winn Parish.xls")):
        raise ValueError("LA: invalid original official projection catalog")
    current = bodies["demographics_catalog_2026-10-02.html"].decode("utf-8", "replace")
    if "<html" not in current.lower() or "Historical population estimates" not in current or "Louisiana State Census Data Center" not in current:
        raise ValueError("LA: invalid current demographics directory")
    record = bodies["author_publication_record_2018.pdf"]
    fetch.validate_pdf(record, "LA author publication record")
    text = " ".join(" ".join((p.extract_text() or "").split()) for p in PdfReader(io.BytesIO(record)).pages)
    if not re.search(r'Blanchard, Troy C\. 2009\. .Population Projections of Louisiana Parishes through 2030', text):
        raise ValueError("LA: missing author's 2009 publication evidence")
    # Binary workbook metadata differs across mirrors, but every source cell in
    # these two independently archived government-hosted workbooks agrees.
    with ZipFile(io.BytesIO(bodies[FILE])) as archive:
        for saved, member in (("official_state_middle_archived20170131.xls", "Statewide Middle Series.xls"),
                              ("official_jefferson_davis_archived20171028.xls", "Jefferson Davis Parish.xls")):
            try:
                mirror = xlrd.open_workbook(file_contents=archive.read(member))
                original = xlrd.open_workbook(file_contents=bodies[saved])
                if mirror.sheet_names() != original.sheet_names() or any(
                    (a.nrows, a.ncols) != (b.nrows, b.ncols) or
                    any(a.row_values(i) != b.row_values(i) for i in range(a.nrows))
                    for a, b in zip(mirror.sheets(), original.sheets(), strict=True)):
                    raise ValueError("LA: archive mirror differs from original official workbook cells")
            except xlrd.XLRDError as exc:
                raise ValueError("LA: unreadable archived official XLS") from exc
    return rows


def acquire() -> None:
    if (RAW_DIR / "manifest.json").exists():
        entries = fetch.read_manifest(RAW_DIR)
        if {e["file"] for e in entries} != set(FILES):
            raise ValueError("LA: incomplete saved manifest")
        _validate_all({name: (RAW_DIR / name).read_bytes() for name in FILES})
        print("LA acquire: reused validated original 2009 archived snapshots")
        return
    bodies = {name: fetch.get_bytes(url) for name, url in FILES.items()}
    rows = _validate_all(bodies)
    entries = []
    for name, url in FILES.items():
        fetch.write_snapshot(RAW_DIR / name, bodies[name])
        entries.append(dict(file=name, source=url, retrieved_at=date.today().isoformat(), sha256=fetch.sha256(bodies[name]),
            records=len(rows) if name == FILE else None,
            note="Original 2009 state-commissioned LSU product recovered from Applied Demography Toolbox archive; original archived official catalog establishes state publication. Archive's indirect 2007 edition label is superseded by original methods and author's 2009 publication record."))
    fetch.write_manifest(RAW_DIR, entries)


def load(conn) -> None:
    entries = {e["file"]: e for e in fetch.read_manifest(RAW_DIR)}
    if set(entries) != set(FILES):
        raise ValueError("LA: incomplete saved manifest")
    rows = _validate_all({name: (RAW_DIR / name).read_bytes() for name in FILES})
    geographies = {r["geo_id"]: r["name"] for r in conn.execute("SELECT geo_id,name FROM geographies WHERE state='LA' AND geo_level='county'")}
    if geographies != roster() or not conn.execute("SELECT 1 FROM geographies WHERE state='LA' AND geo_level='state' AND geo_id='22'").fetchone():
        raise ValueError("LA: parish/state geography is not seeded correctly")
    for base, source_id in SOURCE_IDS.items():
        upsert_source(conn, source_id=source_id, state="LA", agency=AGENCY,
            product_name="Louisiana Parish Population Projections 2010-2030: published statewide and parish population totals",
            vintage=VINTAGE, base_year=base, horizon_year=2030, source_url=URL,
            retrieved_at=entries[FILE]["retrieved_at"],
            license="No explicit data license identified in the original report or public archive entry; cite LSU, Troy C. Blanchard and Louisiana Division of Administration.",
            citation="Troy C. Blanchard, Louisiana State University. Population Projections of Louisiana Parishes through 2030 (2009), for Louisiana Division of Administration, Office of Electronic Services. Original XLS summary Total/Population cells and report Table 1, pp6-7; recovered archived official catalog and Applied Demography Toolbox ZIP.",
            method_notes=(
                "This is an older 2009 state-commissioned LSU edition, not a current rebase. The author's LSU publication record establishes 2009; the archive's indirectly inferred 2007 publication label is incorrect. Exact release/adoption dates are unstated. "
                "The original report and 2018 archived Louisiana.gov catalog establish state publication. The technical report is byte-identical to the archived government original; statewide Middle and all Jefferson Davis scenario worksheet cells match separately recovered government-hosted originals despite binary workbook metadata differences. Original XLS/report bytes are retrieved from an attributed public archive, not endorsed as current by the state. No successor eligible product was verified. "
                "The model's original launch is 2005. Report p22 rebases 22 storm-affected parishes to July 1, 2007 estimates, projects them annually to 2010, then uses five-year intervals. Source metadata separates those parishes and the state (base_year 2007) from the other 42 (base_year 2005). No 2007 row is fabricated. "
                "The explicit 2005 historical row is a July 1 population estimate; every 2010-2030 row remains a projection, including past projection years. Units are persons rounded to tens; published totals are retained. Detailed age/sex/race cells are not served. "
                "Scenarios are migration multipliers: Middle 1.0, Low 0.5, High 1.5 of 2000-2005 net migration. Orleans, Jefferson and St. Bernard use 2006-2007 migration for repopulation. Low and High are not ordered population bounds when migration is negative. "
                "The report explicitly excludes accepted January 2009 upward revisions to Orleans, Jefferson and St. Bernard 2007 estimates. It recommends High through 2020 then Middle for 2025/2030 for those parishes and the state, and Middle elsewhere. The server's Middle default selects a consistent named scenario; it does not splice that recommendation. "
                "All 64 parishes retain source FIPS, with state 22000 normalized to 22. Historical spelling variants are checked against Census 2020 names without geographic boundary conversion. State totals are independently published; no county sum replaces them. "
                "The Jefferson Davis Middle XLS differs from report Table 1 by 0, 90, 180, 300, 400, 530 persons in 2005, 2010, 2015, 2020, 2025, 2030; its original published XLS totals are retained (2030: 29,720 versus report 29,190). All other 64 geography Middle grids agree. The discrepancy's cause or revision date is unstated. "
                "Municipal, household, complete future components and eligible SDO jobs products remain unverified. LSU Economics quarterly economic forecasts and commercial Moody's budget forecasts are outside this selected demographic product."))
    insert_observations(conn, rows)
    conn.commit()
    print(f"LA load: {len(rows)} observations")


def verify(conn) -> None:
    rows = conn.execute("SELECT * FROM observations WHERE state='LA'").fetchall()
    expected = {(g, y, s.lower()) for g in ("22", *roster()) for y in YEARS for s in SCENARIOS}
    assert len(rows) == 1170 and {(r["geo_id"], r["year"], r["scenario"]) for r in rows} == expected
    assert all(r["variable"] == "population" and r["age_group"] == r["sex"] == r["race"] == "all"
        and r["geo_level"] == ("state" if r["geo_id"] == "22" else "county")
        and r["datatype"] == ("estimate" if r["year"] == 2005 else "projection")
        and r["source_id"] == _source_id(r["geo_id"]) and r["value"] >= 0 and r["value"] % 10 == 0 for r in rows)
    for scenario, values in STATE_VALUES.items():
        actual = {r["year"]: r["value"] for r in rows if r["geo_id"] == "22" and r["scenario"] == scenario.lower()}
        assert tuple(actual[y] for y in YEARS) == values
    for base, source_id in SOURCE_IDS.items():
        source = conn.execute("SELECT * FROM sources WHERE source_id=?", (source_id,)).fetchone()
        assert source["base_year"] == base and source["vintage"] == VINTAGE and source["horizon_year"] == 2030
    print("LA verify: 65 geographies, six years, three migration scenarios, 2005/2007 anchors and original Middle report totals ok")


if __name__ == "__main__":
    if "--acquire" in sys.argv:
        acquire()
    else:
        print("usage: python -m sdo_mcp.ingest.la --acquire")
