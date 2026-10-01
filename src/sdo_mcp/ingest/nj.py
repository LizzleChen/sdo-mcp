"""New Jersey DOL's published 2014–2034 state models and county population.

The current catalog still serves this older series. State totals come from the
state workbook, including its four named models; county totals have one model.
Labor force and occupational employment are separate, unserved products.
"""

from __future__ import annotations

import io
import math
import struct
import sys
import zipfile
from datetime import date, datetime
from xml.etree import ElementTree as ET

from ..common import fetch
from ..store import REPO_ROOT, insert_observations, upsert_source
from .seed import COUNTY_FILE

RAW_DIR = REPO_ROOT / "data" / "raw" / "nj"
CATALOG_URL = "https://www.nj.gov/labor/labormarketinformation/demographics/population-labor-projections/"
DOWNLOAD_BASE = "https://www.nj.gov/labor/labormarketinformation/assets/PDFs/dmograph/lfproj/"
STATE_URL = DOWNLOAD_BASE + "sptab1.xlsx"
COUNTY_URL = DOWNLOAD_BASE + "table1.xlsx"
METHOD_URL = DOWNLOAD_BASE + "method24.doc"
INTRO_URL = DOWNLOAD_BASE + "county_intro2034.doc"
REPORT_URL = DOWNLOAD_BASE + "PopLFProj.pptx"
STATE_FILE = "state_population_models_2014-2034_may2017.xlsx"
COUNTY_FILE_NAME = "county_population_2014-2034_may2017.xlsx"
METHOD_FILE = "population_methodology_2014-2034.doc"
INTRO_FILE = "county_introduction_2014-2034.doc"
REPORT_FILE = "population_labor_force_summary_2014-2034.pptx"
CATALOG_FILE = "projection_catalog_2026-10-01.html"
FILES = {STATE_FILE: STATE_URL, COUNTY_FILE_NAME: COUNTY_URL,
         METHOD_FILE: METHOD_URL, INTRO_FILE: INTRO_URL,
         REPORT_FILE: REPORT_URL, CATALOG_FILE: CATALOG_URL}
STATE_SOURCE_ID = "nj-pop-state-2014-2034"
COUNTY_SOURCE_ID = "nj-pop-county-2014-2034"
AGENCY = "New Jersey Department of Labor and Workforce Development, Division of Economic and Demographic Research"
VINTAGE = "2014–2034 series (May 2017 XLSX edition)"
LICENSE = "No explicit data license identified; cite the New Jersey Department of Labor and Workforce Development."
YEARS = (2014, 2019, 2024, 2029, 2034)
TABLE_YEARS = (2010, *YEARS)
MODELS = {
    "Economic-Demographic": "economic_demographic",
    "Zero Migration": "zero_migration",
    "Historical Migration": "historical_migration",
    "Linear Regression": "linear_regression",
}
# The summary chart uses these publisher abbreviations rather than FIPS.
COUNTY_ABBREVIATIONS = {
    "ATL": "Atlantic", "BER": "Bergen", "BUR": "Burlington", "CAM": "Camden",
    "CAP": "Cape May", "CUM": "Cumberland", "ESS": "Essex", "GLO": "Gloucester",
    "HUD": "Hudson", "HUN": "Hunterdon", "MER": "Mercer", "MID": "Middlesex",
    "MON": "Monmouth", "MOR": "Morris", "OCE": "Ocean", "PAS": "Passaic",
    "SAL": "Salem", "SOM": "Somerset", "SUS": "Sussex", "UNI": "Union", "WAR": "Warren",
}


def _counties() -> dict[str, str]:
    counties = {}
    for line in COUNTY_FILE.read_text().splitlines()[1:]:
        fields = line.split("|")
        if fields[0] == "NJ":
            counties[fields[4].removesuffix(" County")] = fields[1] + fields[2]
    if len(counties) != 21 or set(counties) != set(COUNTY_ABBREVIATIONS.values()):
        raise ValueError("NJ: expected all 21 Census counties")
    return counties


def _number(value, context: str) -> int:
    if (type(value) not in (int, float) or not math.isfinite(value)
            or value < 0 or int(value) != value):
        raise ValueError(f"NJ: invalid population value at {context}")
    return int(value)


def _workbook(body: bytes, kind: str):
    import openpyxl

    try:
        book = openpyxl.load_workbook(io.BytesIO(body), read_only=True, data_only=True)
    except Exception as exc:
        raise ValueError(f"NJ: response is not a readable {kind} population XLSX") from exc
    modified = (datetime(2017, 5, 11, 14, 49, 29) if kind == "state"
                else datetime(2017, 5, 11, 15, 2, 43))
    if book.sheetnames != ["Table 1"] or book.properties.modified != modified:
        book.close()
        raise ValueError(f"NJ: unexpected {kind} population workbook edition or sheets")
    return book


def parse_state_workbook(body: bytes) -> list[dict]:
    """Require all four published models, labels, anchors and exact year points."""
    book = _workbook(body, "state")
    try:
        grid = list(book.active.values)
        if (len(grid) != 25 or len(grid[0]) != 7
                or grid[0] != ("Table 1. Projections of Total Population by Projection Model",) + (None,) * 6
                or grid[1] != ("             New Jersey: 2014 to 2034",) + (None,) * 6
                or grid[4] != ("Projection", "Census", "Estimates ", "Projections to July 1,", None, None, None)
                or grid[5] != ("Model", "4/1/2010", "7/1/2014", 2019, 2024, 2029, 2034)):
            raise ValueError("NJ: unexpected state title, year grid or estimate/projection labels")
        notes = (
            'Note: The Economic-Demographic Model is designated "preferred" due to its greater scope ',
            "          of input information and its consistency with the year 2024 employment projections ",
            "          prepared by the New Jersey Department of Labor.  Other models are included  ",
            "          mainly for illustrative purpose.  Population and labor force projections by age, race, ",
            "          sex and Hispanic origin presented in subsequent tables were based on the ",
            "          Economic-Demographic model.",
        )
        if any(row != (text,) + (None,) * 6 for row, text in zip(grid[19:], notes)):
            raise ValueError("NJ: changed preferred-model footnote")
        totals = {}
        for row in grid[6:19]:
            if all(value is None for value in row):
                continue
            label = row[0]
            if label not in MODELS or label in totals:
                raise ValueError(f"NJ: unknown or duplicate state model {label!r}")
            values = tuple(_number(v, label) for v in row[1:])
            if values[:2] != (8791894, 8938200) or any(v % 100 for v in values[1:]):
                raise ValueError("NJ: changed historical anchors or population rounding")
            totals[label] = values
        if set(totals) != set(MODELS):
            raise ValueError("NJ: incomplete state model grid")
        # Blank title/header separators cannot contain unnoticed extra data.
        if any(any(v is not None for v in grid[i]) for i in (2, 3)):
            raise ValueError("NJ: unexpected state table content")
        return [dict(state="NJ", geo_level="state", geo_id="34", year=year,
                     variable="population", value=value, scenario=MODELS[label],
                     datatype="estimate" if year == 2014 else "projection",
                     source_id=STATE_SOURCE_ID)
                for label, values in totals.items()
                for year, value in zip(TABLE_YEARS, values) if year >= 2014]
    finally:
        book.close()


def _county_workbook(body: bytes) -> tuple[list[dict], dict[int, int]]:
    book = _workbook(body, "county")
    try:
        grid = list(book.active.values)
        if (len(grid) != 219 or len(grid[0]) != 8
                or grid[0] != ("Table 1. Projections of Total Population by County: New Jersey, 2014 to 2034",) + (None,) * 7
                or grid[2] != (None, "Census", "Estimates ", None, "Projections to July 1,", None, None, None)
                or grid[3] != ("County", "4/1/2010", "7/1/2014", None, 2019, 2024, 2029, 2034)
                or grid[35] != ("Note: Numbers may not add due to rounding.",) + (None,) * 7):
            raise ValueError("NJ: unexpected county title, year grid or estimate/projection labels")
        # The immutable workbook includes unused #REF! cells in H198:H219.
        # They are outside the published table; no error-valued data is served.
        for i, row in enumerate(grid[36:], 37):
            expected = (None,) * 7 + ("#REF!",) if 198 <= i <= 219 else (None,) * 8
            if row != expected:
                raise ValueError("NJ: unexpected content outside published county table")
        if any(any(v is not None for v in grid[i]) for i in (1, 4)):
            raise ValueError("NJ: unexpected county table content")
        counties = _counties()
        totals = {}
        for row in grid[5:35]:
            if all(value is None for value in row):
                continue
            name = row[0]
            if (name not in counties and name != "New Jersey") or name in totals:
                raise ValueError(f"NJ: unknown or duplicate county geography {name!r}")
            if row[3] is not None:
                raise ValueError("NJ: unexpected extra county value")
            values = tuple(_number(row[i], name) for i in (1, 2, 4, 5, 6, 7))
            if any(v % 100 for v in values[1:]):
                raise ValueError("NJ: unexpected county population rounding")
            totals[name] = values
        if set(totals) != set(counties) | {"New Jersey"}:
            raise ValueError("NJ: incomplete county geography grid")
        for i, (year, difference) in enumerate(zip(TABLE_YEARS, (0, 100, 0, -300, 0, 100))):
            if totals["New Jersey"][i] - sum(totals[name][i] for name in counties) != difference:
                raise ValueError(f"NJ: changed published county/state reconciliation in {year}")
        rows = [dict(state="NJ", geo_level="county", geo_id=counties[name], year=year,
                     variable="population", value=value,
                     datatype="estimate" if year == 2014 else "projection",
                     source_id=COUNTY_SOURCE_ID)
                for name, values in totals.items() if name != "New Jersey"
                for year, value in zip(TABLE_YEARS, values) if year >= 2014]
        return rows, dict(zip(TABLE_YEARS, totals["New Jersey"]))
    finally:
        book.close()


def parse_county_workbook(body: bytes) -> list[dict]:
    """Return only the 21 published county series; never sum a state forecast."""
    return _county_workbook(body)[0]


def _doc_text(body: bytes) -> str:
    """Read the binary Word text piece table, without desktop Word or conversion.

    xlrd provides the compound-file reader already used by other ingest code.
    The FIB/CLX/PCD text locations follow Microsoft's MS-DOC section 2.4.1.
    Only these archived Word 97-format files are accepted here.
    """
    from xlrd.compdoc import CompDoc

    try:
        compound = CompDoc(body, logfile=io.StringIO())
        document = compound.get_named_stream("WordDocument")
        if document is None or struct.unpack_from("<HH", document) != (0xA5EC, 0x00C1):
            raise ValueError("unexpected Word file-information block")
        flags = struct.unpack_from("<H", document, 10)[0]
        if flags & 0x0100:
            raise ValueError("encrypted Word document")
        table = compound.get_named_stream("1Table" if flags & 0x0200 else "0Table")
        if table is None:
            raise ValueError("missing Word table stream")
        word_count = struct.unpack_from("<H", document, 32)[0]
        offset = 34 + word_count * 2
        long_count = struct.unpack_from("<H", document, offset)[0]
        offset += 2 + long_count * 4
        pair_count = struct.unpack_from("<H", document, offset)[0]
        if pair_count < 34:
            raise ValueError("incomplete Word file-information block")
        # fcClx/lcbClx are the 34th offset/length pair in FibRgFcLcb97.
        start, length = struct.unpack_from("<II", document, offset + 2 + 33 * 8)
        clx = table[start:start + length]
        if len(clx) != length:
            raise ValueError("truncated Word piece table")
        pos = 0
        while clx[pos] == 1:
            pos += 3 + struct.unpack_from("<H", clx, pos + 1)[0]
        if clx[pos] != 2:
            raise ValueError("missing Word text-piece descriptor")
        size = struct.unpack_from("<I", clx, pos + 1)[0]
        pieces = clx[pos + 5:pos + 5 + size]
        if len(pieces) != size or size < 16 or (size - 4) % 12:
            raise ValueError("invalid Word text-piece grid")
        count = (size - 4) // 12
        positions = struct.unpack_from(f"<{count + 1}I", pieces)
        if positions[0] != 0 or any(a >= b for a, b in zip(positions, positions[1:])):
            raise ValueError("invalid Word character positions")
        text = []
        for i in range(count):
            descriptor = 4 * (count + 1) + i * 8
            location = struct.unpack_from("<I", pieces, descriptor + 2)[0]
            compressed = bool(location & 0x40000000)
            start = location & 0x3FFFFFFF
            if compressed:
                start //= 2
            length = (positions[i + 1] - positions[i]) * (1 if compressed else 2)
            segment = document[start:start + length]
            if len(segment) != length:
                raise ValueError("truncated Word text")
            text.append(segment.decode("cp1252" if compressed else "utf-16-le"))
        return " ".join("".join(text).split())
    except Exception as exc:
        raise ValueError("NJ: response is not a readable binary Word methodology/introduction") from exc


def _validate_doc(body: bytes, name: str) -> None:
    text = _doc_text(body)
    markers = {
        METHOD_FILE: ("METHODOLOGY - THE PROJECTION MODELS", "cohort-component method",
                      "2014 estimates", "vintage 2014", "Economic-Demographic Model",
                      "Historical Migration Model", "Zero Migration Model", "Linear Regression Model",
                      "CIVILIAN LABOR FORCE PROJECTIONS"),
        INTRO_FILE: ("21 counties", "2014 to 2019, 2024, 2029 and 2034",
                     "Division of Economic and Demographic Research", "Economic-Demographic projection model",
                     "not forecasts or predictions", "not designated", "only available online",
                     "Because of rounding"),
    }[name]
    if any(marker not in text for marker in markers):
        raise ValueError(f"NJ: changed model, base year or cautions in {name}")


def parse_report(body: bytes) -> dict[tuple[str, int], int]:
    """Cross-check separate publisher charts, keeping source table precision."""
    namespaces = {"c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
                  "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
                  "p": "http://schemas.openxmlformats.org/presentationml/2006/main"}
    try:
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            if archive.testzip() is not None:
                raise ValueError("corrupt presentation archive")
            presentation = ET.fromstring(archive.read("ppt/presentation.xml"))
            if len(presentation.findall(".//p:sldId", namespaces)) != 35:
                raise ValueError("unexpected summary presentation edition")
            slide = ET.fromstring(archive.read("ppt/slides/slide1.xml"))
            title = " ".join(" ".join(n.text or "" for n in slide.findall(".//a:t", namespaces)).split())
            if "Population and Labor Force Projections for New Jersey: 2014 to 2034" not in title:
                raise ValueError("unexpected summary presentation title")
            counties = _counties()
            checks = {}
            county_chart = ET.fromstring(archive.read("ppt/charts/chart3.xml"))
            series = county_chart.findall(".//c:ser", namespaces)
            if len(series) != 2:
                raise ValueError("unexpected county chart series")
            for item, year in zip(series, (2014, 2034)):
                name = item.find("c:tx/c:strRef/c:strCache/c:pt/c:v", namespaces)
                if name is None or name.text != str(year):
                    raise ValueError("unexpected county chart year")
                labels = [n.text for n in item.findall("c:cat/c:strRef/c:strCache/c:pt/c:v", namespaces)]
                numbers = [n.text for n in item.findall("c:val/c:numRef/c:numCache/c:pt/c:v", namespaces)]
                if (len(labels) != 21 or len(numbers) != 21
                        or set(labels) != set(COUNTY_ABBREVIATIONS)):
                    raise ValueError("incomplete county chart geography grid")
                for label, number in zip(labels, numbers):
                    checks[counties[COUNTY_ABBREVIATIONS[label]], year] = _number(float(number), label)
            state_chart = ET.fromstring(archive.read("ppt/charts/chart1.xml"))
            item = state_chart.findall(".//c:ser", namespaces)[0]
            years = [n.text for n in item.findall("c:cat/c:numRef/c:numCache/c:pt/c:v", namespaces)]
            numbers = [n.text for n in item.findall("c:val/c:numRef/c:numCache/c:pt/c:v", namespaces)]
            if len(years) != 26 or len(numbers) != 26 or years[-3:] != ["2019", "2029", "2034"]:
                raise ValueError("unexpected state chart year grid")
            for year, number in zip(years[-3:], numbers[-3:]):
                value = _number(float(number), year)
                # The chart preserves unrounded model output; the served XLSX
                # totals are published at hundreds, and take precedence.
                checks["34", int(year)] = ((value + 50) // 100) * 100
            return checks
    except Exception as exc:
        raise ValueError("NJ: response is not the expected readable population summary PPTX") from exc


def _validate_catalog(body: bytes) -> None:
    text = " ".join(body.decode("utf-8", "replace").lower().split())
    if any(marker not in text for marker in (
            "<html", "population and labor force projections", "2014 to 2019, 2024, 2029 and 2034",
            "sptab1.xlsx", "table1.xlsx", "method24.doc", "county_intro2034.doc", "poplfproj.pptx")):
        raise ValueError("NJ: unexpected projection catalog or edition")


def _validate_all(bodies: dict[str, bytes]) -> list[dict]:
    _validate_catalog(bodies[CATALOG_FILE])
    for name in (METHOD_FILE, INTRO_FILE):
        _validate_doc(bodies[name], name)
    state = parse_state_workbook(bodies[STATE_FILE])
    counties, county_state = _county_workbook(bodies[COUNTY_FILE_NAME])
    preferred = {r["year"]: r["value"] for r in state if r["scenario"] == "economic_demographic"}
    for year in YEARS:
        if preferred[year] - county_state[year] != (300 if year == 2029 else 0):
            raise ValueError("NJ: changed state/county workbook discrepancy")
    checks = parse_report(bodies[REPORT_FILE])
    rows = state + counties
    selected = {(r["geo_id"], r["year"]): r["value"] for r in rows
                if r.get("scenario", "economic_demographic") == "economic_demographic"}
    if any(selected[key] != value for key, value in checks.items()):
        raise ValueError("NJ: population workbook and independent presentation disagree")
    return rows


def acquire() -> None:
    """Archive original validated bytes; reuse saved files without re-retrieval."""
    if (RAW_DIR / "manifest.json").exists():
        if {e["file"] for e in fetch.read_manifest(RAW_DIR)} != set(FILES):
            raise ValueError("NJ: incomplete saved snapshot manifest")
        _validate_all({name: (RAW_DIR / name).read_bytes() for name in FILES})
        print("NJ acquire: reused validated 2014–2034 snapshots")
        return
    bodies = {name: fetch.get_bytes(url) for name, url in FILES.items()}
    _validate_all(bodies)
    entries = []
    for name, url in FILES.items():
        fetch.write_snapshot(RAW_DIR / name, bodies[name])
        entries.append(dict(file=name, source=url, retrieved_at=date.today().isoformat(),
                            sha256=fetch.sha256(bodies[name]),
                            records={STATE_FILE: 20, COUNTY_FILE_NAME: 105}.get(name),
                            note="Original NJDOL 2014–2034 source. XLSX modified May 11, 2017; methodology/introduction saved November 2016. Source series/vintage is distinct from the 2026 catalog retrieval. State/county table 2029 discrepancy and rounding retained. Labor force is not served as employment."))
    fetch.write_manifest(RAW_DIR, entries)


def load(conn) -> None:
    entries = {e["file"]: e for e in fetch.read_manifest(RAW_DIR)}
    if set(entries) != set(FILES):
        raise ValueError("NJ: incomplete saved snapshot manifest")
    rows = _validate_all({name: (RAW_DIR / name).read_bytes() for name in FILES})
    for kind, source_id, filename, url, title in (
        ("state", STATE_SOURCE_ID, STATE_FILE, STATE_URL,
         "Projections of Total Population by Projection Model: New Jersey, 2014 to 2034"),
        ("county", COUNTY_SOURCE_ID, COUNTY_FILE_NAME, COUNTY_URL,
         "Projections of Total Population by County: New Jersey, 2014 to 2034"),
    ):
        upsert_source(
            conn, source_id=source_id, state="NJ", agency=AGENCY, product_name=title,
            vintage=VINTAGE, base_year=2014, horizon_year=2034,
            source_url=url, retrieved_at=entries[filename]["retrieved_at"], license=LICENSE,
            citation=f"{AGENCY}. {title}. 2014–2034 series; original May 2017 XLSX.",
            method_notes=(
                "July 1, 2014 estimates from Census Vintage 2014 are the historical base; "
                "July 1, 2019/2024/2029/2034 remain projections, including years already past "
                "at retrieval. The April 2010 Census column is archived only. Original totals "
                "are rounded to hundreds; no annual interpolation or updated estimates are "
                "substituted. The preferred Economic-Demographic model is a cohort-component "
                "model whose under-65 migration responds to labor demand. Historical Migration "
                "uses historical migration rates; Zero Migration assumes none; Linear Regression "
                "extrapolates 1900–2014 history. The latter two are illustrative models. "
                + ("All four state models are selectable; default is economic_demographic. "
                   if kind == "state" else
                   "All 21 counties have one Economic-Demographic series; state scenarios do not apply. ")
                + "The state workbook's preferred 2029 total is 9,531,200; the county workbook "
                "state row and county sum are 9,530,900. The state workbook takes precedence "
                "for state queries; published county values and other rounding differences "
                "are preserved. The unused county H198:H219 #REF! cells are outside the "
                "published table. Workbook dates identify these files, not a claimed model "
                "release date. No newer NJDOL demographic series was found on the current "
                "catalog. The publisher calls these projections, not predictions or policy "
                "targets. Civilian labor force is employed plus job-seeking residents and is "
                "not a jobs forecast; industry/occupational and MPO products are not substituted."
            ),
        )
    insert_observations(conn, rows)
    conn.commit()
    print(f"NJ load: {len(rows)} observations")


def verify(conn) -> None:
    # County endpoints are independently repeated in the publisher PPTX chart3.
    # Preferred state 2019/2029/2034 are checked against chart1 at XLSX precision.
    fixtures = (
        ("34", 2014, "economic_demographic", 8938200, "estimate"),
        ("34", 2019, "economic_demographic", 9132700, "projection"),
        ("34", 2029, "economic_demographic", 9531200, "projection"),
        ("34", 2034, "economic_demographic", 9733400, "projection"),
        ("34", 2034, "zero_migration", 9342500, "projection"),
        ("34", 2034, "historical_migration", 9522200, "projection"),
        ("34", 2034, "linear_regression", 10374700, "projection"),
        ("34003", 2014, "", 933600, "estimate"),
        ("34003", 2034, "", 1065500, "projection"),
        ("34009", 2034, "", 93400, "projection"),
        ("34017", 2034, "", 766500, "projection"),
        ("34033", 2034, "", 59800, "projection"),
    )
    for gid, year, scenario, value, datatype in fixtures:
        row = conn.execute("SELECT value,datatype FROM observations WHERE state='NJ' "
                           "AND variable='population' AND geo_id=? AND year=? AND scenario=?",
                           (gid, year, scenario)).fetchone()
        assert tuple(row) == (value, datatype), f"NJ fixture {gid}/{year}/{scenario}"
    shape = conn.execute("SELECT COUNT(*),COUNT(DISTINCT geo_id),COUNT(DISTINCT year),"
                         "MIN(year),MAX(year),SUM(datatype='estimate') FROM observations WHERE state='NJ'").fetchone()
    assert tuple(shape) == (125, 22, 5, 2014, 2034, 25)
    assert conn.execute("SELECT COUNT(*) FROM observations WHERE state='NJ' AND "
                        "(variable!='population' OR (geo_level='county' AND scenario!=''))").fetchone()[0] == 0
    print("NJ verify: four state models, 21 counties and independent chart anchors ok")


if __name__ == "__main__":
    if "--acquire" in sys.argv:
        acquire()
