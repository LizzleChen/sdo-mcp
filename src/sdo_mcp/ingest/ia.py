"""Iowa state demographer's archival July 1984 population projections, 1980-2000.

The original scanned government report is selected deliberately. Newer linked
Census and licensed commercial projections are separate, ineligible candidates.
"""
from __future__ import annotations

import io
import json
import re
import sys
from datetime import date
from html.parser import HTMLParser

from ..common import fetch
from ..store import REPO_ROOT, insert_observations, upsert_source
from .seed import COUNTY_FILE

RAW_DIR = REPO_ROOT / "data" / "raw" / "ia"
URL = "https://publications.iowa.gov/21195/1/Iowa%20Population%20projections.pdf"
CATALOG_URL = "https://publications.iowa.gov/21195/"
FILE = "iowa_population_projections_july1984_1980-2000.pdf"
FILES = {
    FILE: URL,
    "state_report_archive_catalog_2026-10-02.html": CATALOG_URL,
    "state_publications_archive_home_2026-10-02.html": "https://publications.iowa.gov/",
    "legacy_projection_catalog_2026-10-02.html": "https://www.iowadatacenter.org/browse/projections.html",
}
SOURCE_ID = "ia-pop-july1984"
AGENCY = "Office of the State Demographer, Iowa Office for Planning and Programming"
VINTAGE = "July 1984 (archival edition)"
YEARS = (1980, 1985, 1990, 1995, 2000)
STATE_VALUES = (2913808, 2905400, 2913500, 2931800, 2965000)
COUNTY_SUM_DIFFERENCES = (0, 500, -300, 400, 100)
# Entire 100-geography x five-year summary checked against rendered original
# PDF page 5, including every source-specific OCR correction below. Poppler's
# separate layout extraction was reconciled to the same reviewed grid.
GRID_SHA256 = "faa246fabd7b4f3e9da94c38b33ad182f32eec7e118fde5b8c50220527de09d0"
OCR_NAMES = {
    "S T A T E": "STATE", "Cll NTON": "CLINTON", "POHESHIEK": "POWESHIEK",
    "HAPELLO": "WAPELLO", "HARREN": "WARREN", "HAYNE": "WAYNE", "HEBSTER": "WEBSTER",
    "HINNEBAGO": "WINNEBAGO", "HINNESHIEK": "WINNESHIEK", "HOODBURY": "WOODBURY",
    "HORTH": "WORTH", "FRANKL! N": "FRANKLIN", "HAM·ILTON": "HAMILTON", "I<EOKUK": "KEOKUK",
    "REGION 138": "REGION 13B",
}
# These are repairs to the archive's OCR text, never changes to the printed
# source numbers. They apply only to the named row and exact original glyphs.
OCR_CELLS = {
    "ADAIR": {"8,:wo": "8,300"}, "ADAMS": {"5, :~oo": "5,200"},
    "APPANOOSE": {"14,1100": "14,400"}, "AUDUBON": {"8, ~100": "8,100"},
    "BENTON": {"23,6119": "23,649", "22, LIQO": "22,400"},
    "BLACK HAWK": {"137,1100": "137,400", "139,1100": "139,400"},
    "BOONE": {"25, ~~00": "25,500"}, "BREMER": {"211' 820": "24,820"},
    "BUENA VISTA": {"20,7711": "20,774"}, "CASS": {"'1 7' 5·00": "17,500"},
    "SHELBY": {"15,0113": "15,043"}, "UNION": {"ll~, 100": "14,100"},
    "EMMET": {"13plt00": "13,400"}, "WAPELLO": {"40,2111": "40,241"},
    "FAYETTE": {"211,000": "24,000"}, "GUTHRIE": {"1 1 • 1 00": "11,100"},
    "MITCHELL": {"1 1. 400": "11,400", "1 1' 300": "11,300"},
    "WINNEBAGO": {"1 1. 500": "11,500"},
}


def _counties() -> dict[str, str]:
    counties = {}
    for line in COUNTY_FILE.read_text().splitlines()[1:]:
        fields = line.split("|")
        if fields[0] == "IA":
            counties[fields[4].removesuffix(" County").upper()] = fields[1] + fields[2]
    if len(counties) != 99:
        raise ValueError("IA: expected all 99 Iowa counties")
    return counties


def _values(raw: str, name: str) -> tuple[int, ...]:
    for printed_ocr, corrected in OCR_CELLS.get(name, {}).items():
        if raw.count(printed_ocr) != 1:
            raise ValueError(f"IA: reviewed OCR cell changed for {name}")
        raw = raw.replace(printed_ocr, corrected)
    # Original OCR sometimes reads a printed comma as another punctuation
    # mark. Strip only separators between digits; never guess missing digits.
    raw = re.sub(r"(?<=\d)\s*[,'.;·•]\s*(?=\d)", "", raw)
    tokens = raw.split()
    if len(tokens) != len(YEARS) or any(not re.fullmatch(r"\d+", token) for token in tokens):
        raise ValueError("IA: invalid population integer or incomplete year grid")
    return tuple(map(int, tokens))


def parse_summary(text: str) -> dict[str, tuple[int, ...]]:
    counties = _counties()
    regions = {f"REGION {i}" for i in range(1, 17) if i != 13} | {"REGION 13A", "REGION 13B"}
    names = set(counties) | {"STATE"} | regions
    text = " ".join(text.split())
    prefix = ("IOWA POPIULATION PROJECTIONS JULY 1984 "
              "AREA 1980 1985 1990 1995 2000 AREA 1980 1985 1990 1995 2000 ")
    if not text.startswith(prefix):
        raise ValueError("IA: unexpected summary title, edition or year header")
    text = text.removeprefix(prefix)
    pattern = re.compile("|".join(re.escape(name) for name in sorted(names | set(OCR_NAMES), key=lambda n: (-len(n), n))))
    matches = list(pattern.finditer(text))
    totals = {}
    if not matches or matches[0].start() != 0:
        raise ValueError("IA: unexpected summary geography grid")
    for index, match in enumerate(matches):
        name = OCR_NAMES.get(match[0], match[0])
        if name in totals:
            raise ValueError("IA: duplicate summary geography")
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        totals[name] = _values(text[match.end():end].strip(), name)
    if set(totals) != names:
        raise ValueError("IA: incomplete state, county or region grid")
    # Only the publisher's statewide and county totals are loaded. No county
    # sum or region construction is used to invent a statewide series.
    selected = {name: totals[name] for name in ("STATE", *sorted(counties))}
    fingerprint = fetch.sha256(json.dumps(selected, sort_keys=True, separators=(",", ":")).encode())
    if fingerprint != GRID_SHA256:
        raise ValueError("IA: totals differ from independently reviewed original summary")
    if selected["STATE"] != STATE_VALUES:
        raise ValueError("IA: reviewed statewide total changed")
    differences = tuple(sum(selected[name][i] for name in counties) - STATE_VALUES[i] for i in range(len(YEARS)))
    if differences != COUNTY_SUM_DIFFERENCES:
        raise ValueError("IA: published state/county differences changed")
    return selected


def parse(body: bytes) -> list[dict]:
    from pypdf import PdfReader

    fetch.validate_pdf(body, "IA state demographer report")
    reader = PdfReader(io.BytesIO(body))
    if len(reader.pages) != 122:
        raise ValueError("IA: unexpected original report page count")
    cover = " ".join((reader.pages[0].extract_text() or "").split())
    methods = " ".join((reader.pages[2].extract_text() or "").split())
    if any(marker not in cover for marker in ("POPULATION PROJECTIONS: 1980 - 2000", "July 1984",
                                               "Office of the State Demographer", "Office for Planning and Programming")):
        raise ValueError("IA: unexpected government producer or report edition")
    if any(marker not in methods for marker in ("Methodology and Assumptions July 1984", "base population of April 1, 1980",
                                                 "each county was projected separately", "independently projected state total")):
        raise ValueError("IA: unexpected population base or projection methods")
    totals = parse_summary(reader.pages[4].extract_text() or "")
    counties = _counties()
    return [dict(state="IA", geo_level="state" if name == "STATE" else "county",
                 geo_id="19" if name == "STATE" else counties[name], year=year, variable="population", value=value,
                 datatype="estimate" if year == 1980 else "projection", source_id=SOURCE_ID)
            for name, values in totals.items() for year, value in zip(YEARS, values, strict=True)]


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def _validate(bodies: dict[str, bytes]) -> list[dict]:
    markers = {
        "state_report_archive_catalog_2026-10-02.html": ("Iowa population projections, 1980-2000, 1984", "Governor's Office", "21195"),
        "state_publications_archive_home_2026-10-02.html": ("State Library of Iowa", "documents produced by Iowa state agencies", "intended for use by the general public"),
        "legacy_projection_catalog_2026-10-02.html": ("U.S. Census Bureau - Interim Projections", "Woods & Poole Economics, Inc.", "2010-2040"),
    }
    for name, required in markers.items():
        page = bodies[name].decode("utf-8", "replace")
        parser = _Text()
        parser.feed(page)
        text = " ".join(" ".join(parser.parts).split())
        if "<html" not in page.lower() or any(marker not in text for marker in required):
            raise ValueError(f"IA: invalid original source evidence {name}")
    return parse(bodies[FILE])


def acquire() -> None:
    if (RAW_DIR / "manifest.json").exists():
        entries = fetch.read_manifest(RAW_DIR)
        if {entry["file"] for entry in entries} != set(FILES):
            raise ValueError("IA: incomplete saved snapshot manifest")
        _validate({name: (RAW_DIR / name).read_bytes() for name in FILES})
        print("IA acquire: reused validated original July 1984 snapshots")
        return
    bodies = {name: fetch.get_bytes(url) for name, url in FILES.items()}
    _validate(bodies)
    entries = []
    for name, body in bodies.items():
        fetch.write_snapshot(RAW_DIR / name, body)
        entries.append(dict(file=name, source=FILES[name], retrieved_at=date.today().isoformat(), sha256=fetch.sha256(body),
                            records=500 if name == FILE else None,
                            note="Original publisher bytes. Archival July 1984 state-demographer edition, horizon 2000. PDF page 5 summary totals were checked against rendered original; source-specific OCR repairs do not alter original PDF."))
    fetch.write_manifest(RAW_DIR, entries)


def load(conn) -> None:
    entries = {entry["file"]: entry for entry in fetch.read_manifest(RAW_DIR)}
    if set(entries) != set(FILES):
        raise ValueError("IA: incomplete saved snapshot manifest")
    rows = _validate({name: (RAW_DIR / name).read_bytes() for name in FILES})
    upsert_source(conn, source_id=SOURCE_ID, state="IA", agency=AGENCY,
        product_name="Iowa Population Projections: 1980-2000, statewide and county summary",
        vintage=VINTAGE, base_year=1980, horizon_year=2000, source_url=URL,
        retrieved_at=entries[FILE]["retrieved_at"],
        license="No explicit data license identified in the original government report or archive catalog. State Library archive describes state-agency documents as intended for general public use. Cite the Iowa Office of the State Demographer.",
        citation="Office of the State Demographer, Iowa Office for Planning and Programming. Iowa Population Projections: 1980-2000. July 1984. Original report PDF page 5, statewide/county summary; methods on PDF page 3. State Library of Iowa, Iowa Publications Online item 21195.",
        method_notes=("Selected archival July 1984 state-produced forecast, whose entire projected 1985-2000 horizon is in the past. It supplies no projection after 2000 and is not presented as the latest Iowa edition. "
            "The source's April 1, 1980 Census base count is served as estimate/history; 1985, 1990, 1995 and 2000 remain projections. "
            "base_year=1980 identifies the explicit population launch base; auxiliary migration inputs from Census P-26 82-19-C do not establish a later population rebase. "
            "The projected reference day is unstated. Own cohort-component projections use fertility, survival and migration assumptions; county populations were adjusted to an independently projected state total. "
            "Published summary totals for the state and all 99 counties are retained exactly. Projection totals are displayed in hundreds; county sums minus the state total are 0, +500, -300, +400 and +100 across 1980/1985/1990/1995/2000. They are not forced to agree. "
            "The original scanned PDF is unchanged. Explicit row-specific OCR repairs are checked against its rendered summary and a complete-grid fingerprint. "
            "The summary is selected consistently; no age/sex or regional figures are substituted. Those separately published detail tables are not loaded. "
            "A federal 1990 report identifies a newer December 1989 Iowa state-agency projection, but original successor tables were not recovered. "
            "Current State Data Center legacy links identify federal interim and Woods & Poole commercial products; neither is rebranded or substituted. "
            "Household, projected-component, place and eligible SDO employment publication coverage remains unresolved."))
    insert_observations(conn, rows)
    conn.commit()
    verify(conn)


def verify(conn) -> None:
    expected = parse((RAW_DIR / FILE).read_bytes())
    actual = conn.execute("SELECT state,geo_level,geo_id,year,variable,value,datatype,source_id FROM observations WHERE state='IA' ORDER BY geo_level,geo_id,year").fetchall()
    fields = ("state", "geo_level", "geo_id", "year", "variable", "value", "datatype", "source_id")
    order = lambda row: (row["geo_level"], row["geo_id"], row["year"])
    if [tuple(row[field] for field in fields) for row in actual] != [tuple(row[field] for field in fields) for row in sorted(expected, key=order)]:
        raise ValueError("IA: loaded observations differ from selected published summary")
    print("IA verify: 500 published state/county totals; 1980 history and four projections through 2000")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "acquire":
        acquire()
    else:
        raise SystemExit("usage: python -m sdo_mcp.ingest.ia acquire")
