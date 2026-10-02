"""Missouri OA's March 2008 Preferred Series, preserved through its 2030 horizon."""

from __future__ import annotations

import io
import math
import re
import sys
from datetime import date
from html.parser import HTMLParser

from ..common import fetch
from ..store import REPO_ROOT, insert_observations, upsert_source
from .seed import COUNTY_FILE

RAW_DIR = REPO_ROOT / "data" / "raw" / "mo"
ROOT_URL = "https://budplan.oa.mo.gov"
TABLE_URL = ROOT_URL + "/sites/g/files/zuston231/files/media/file/2024/03/total-pop-all-counties.xls"
CATALOG_URL = ROOT_URL + "/demographic-info/population-projections/2000-2030-projections"
METHODS_URL = ROOT_URL + "/demographic-info/population-projections/methodology"
FILES = {
    "total_population_preferred_march2008.xls": TABLE_URL,
    "total_population_preferred_march2008.pdf": ROOT_URL + "/sites/g/files/zuston231/files/media/pdf/2024/03/total-pop-all-counties_0.pdf",
    "state_age_components_preferred_march2008.pdf": ROOT_URL + "/sites/g/files/zuston231/files/media/pdf/2024/03/pop-projections-by-age-state-totals.pdf",
    "projection_catalog_2026-10-02.html": CATALOG_URL,
    "projection_methods_2026-10-02.html": METHODS_URL,
    "producer_acknowledgements_2026-10-02.html": ROOT_URL + "/demographic-info/population-projections",
    "demographic_catalog_2026-10-02.html": ROOT_URL + "/demographic-information",
    "meric_population_catalog_2026-10-02.html": "https://meric.mo.gov/data/population/new-population-projections",
}
FILE = next(iter(FILES))
SOURCE_ID = "mo-pop-preferred-2008"
AGENCY = "Missouri Office of Administration, Division of Budget and Planning"
YEARS = tuple(range(2000, 2031, 5))
BASE_YEAR = 2007  # Last population-estimate input; the model launches from Census 2000.
VINTAGE = "March 2008 Preferred Series"
STATE_TOTALS = (5596687, 5781293, 5979344, 6184390, 6389850, 6580868, 6746762)


def _counties() -> dict[str, str]:
    result = {}
    for line in COUNTY_FILE.read_text().splitlines()[1:]:
        fields = line.split("|")
        if fields[0] == "MO":
            name = fields[4].removesuffix(" County")
            # The original tables capitalize City and mark the independent city
            # with an asterisk. St. Louis County has its own distinct row.
            if name == "St. Louis city":
                name = "St. Louis City*"
            result[name] = fields[1] + fields[2]
    if len(result) != 115 or result.get("St. Louis City*") != "29510" or result.get("St. Louis") != "29189":
        raise ValueError("MO: expected 114 counties and independent St. Louis city")
    return result


def parse_grid(grid: list[list]) -> list[dict]:
    """Validate the original XLS layout, roster and numeric population cells."""
    if (len(grid) != 120 or any(len(row) != 8 for row in grid)
            or grid[0] != ["Population Projections - Total Population", *([""] * 7)]
            or grid[1] != ["Missouri Counties: 2000 through 2030", *([""] * 7)]
            or grid[2] != ["County", *YEARS] or grid[118] != [""] * 8):
        raise ValueError("MO: unexpected population table headers, years or layout")
    roster = _counties() | {"Statewide Total": "29"}
    totals = {}
    for row in [*grid[3:118], grid[119]]:
        name = row[0].strip() if isinstance(row[0], str) else None
        if name not in roster:
            raise ValueError(f"MO: unknown geography {name!r}")
        gid = roster[name]
        if gid in totals:
            raise ValueError(f"MO: duplicate geography {name}")
        values = row[1:]
        if any(isinstance(value, bool) or not isinstance(value, (int, float))
               or not math.isfinite(value) or value < 0 or int(value) != value for value in values):
            raise ValueError(f"MO: invalid population value for {name}")
        totals[gid] = tuple(map(int, values))
    if set(totals) != set(roster.values()):
        raise ValueError("MO: incomplete state/county population grid")
    if totals["29"] != STATE_TOTALS:
        raise ValueError("MO: published statewide totals changed")
    # Methods explicitly describe the state as the sum of 115 independent
    # county-equivalent models; all displayed XLS/PDF integers reconcile exactly.
    for index, year in enumerate(YEARS):
        if sum(values[index] for gid, values in totals.items() if gid != "29") != totals["29"][index]:
            raise ValueError(f"MO: county/state totals disagree in {year}")
    return [dict(state="MO", geo_level="state" if gid == "29" else "county", geo_id=gid,
                 year=year, variable="population", value=value,
                 datatype="estimate" if year == 2000 else "projection", source_id=SOURCE_ID)
            for gid, values in totals.items() for year, value in zip(YEARS, values, strict=True)]


def parse(body: bytes) -> list[dict]:
    import xlrd

    try:
        book = xlrd.open_workbook(file_contents=body)
    except Exception as exc:
        raise ValueError("MO: response is not a readable original XLS workbook") from exc
    try:
        if book.sheet_names() != ["Sheet1", "Sheet2", "Sheet3"] or any(
                sheet.nrows or sheet.ncols for sheet in book.sheets()[1:]):
            raise ValueError("MO: unexpected workbook sheets")
        sheet = book.sheet_by_index(0)
        if any(sheet.cell_type(i, j) != xlrd.XL_CELL_NUMBER for i in [*range(3, 118), 119]
               for j in range(1, min(sheet.ncols, 8))):
            raise ValueError("MO: invalid numeric population cell type")
        return parse_grid([sheet.row_values(i) for i in range(sheet.nrows)])
    finally:
        book.release_resources()


def _pdf_text(body: bytes, expected_pages: int) -> list[str]:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(body))
        if len(reader.pages) != expected_pages:
            raise ValueError("unexpected PDF page count")
        return [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:
        raise ValueError("MO: response is not the expected readable population PDF") from exc


def _pdf_values(tokens: list[str]) -> tuple[int, ...]:
    if len(tokens) != len(YEARS) or any(not re.fullmatch(r"(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)", token) for token in tokens):
        raise ValueError("MO: invalid PDF population integer")
    return tuple(int(token.replace(",", "")) for token in tokens)


def parse_companion_texts(texts: list[str]) -> dict[tuple[str, int], int]:
    """All 812 displayed cells independently cross-check the original XLS."""
    if len(texts) != 3:
        raise ValueError("MO: unexpected companion PDF page count")
    roster = _counties() | {"Statewide Total": "29"}
    result = {}
    for index, text in enumerate(texts, 1):
        header = ("Population Projections - Total Population", "Missouri Counties: 2000 through 2030",
                  "County 2000 2005 2010 2015 2020 2025 2030", f"Page {index} of 3")
        normalized = " ".join(text.split())
        if any(marker not in normalized for marker in header):
            raise ValueError("MO: unexpected companion PDF header or years")
        for line in text.splitlines():
            line = " ".join(line.split())
            if not line or line in header[:3] or line == header[3]:
                continue
            match = re.fullmatch(r"(.+?)\s+((?:\S+\s+){6}\S+)", line)
            if not match or match[1] not in roster:
                raise ValueError("MO: unknown or malformed companion PDF geography")
            gid = roster[match[1]]
            for year, value in zip(YEARS, _pdf_values(match[2].split()), strict=True):
                if (gid, year) in result:
                    raise ValueError("MO: duplicate companion PDF geography")
                result[gid, year] = value
    if set(result) != {(gid, year) for gid in roster.values() for year in YEARS}:
        raise ValueError("MO: incomplete companion PDF grid")
    return result


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def _validate_page(name: str, body: bytes) -> None:
    page = body.decode("utf-8", "replace")
    parser = _Text()
    parser.feed(page)
    text = " ".join(" ".join(parser.parts).split())
    markers = {
        "projection_catalog": ("Missouri Population Projections", "2000 to 2030", "Total Population for All Counties Excel", "Components of Change"),
        "projection_methods": ("2000 Census counts", "project 2005 area populations", "2000-2007", "post-census population estimates", "all 114 counties and St. Louis City", "April 1"),
        "producer_acknowledgements": ("Missouri Population Projections - Preferred Series", "Missouri State Demographer", "Division of Budget and Planning"),
        "demographic_catalog": ("Demographic Information", "2020 Census Data", "Population Projections"),
        "meric_population_catalog": ("Missouri Office of Administration", "2030", "2000", "For detailed Missouri Population Projections"),
    }
    key = next((key for key in markers if name.startswith(key)), None)
    if "<html" not in page.lower() or key is None or any(marker not in text for marker in markers[key]):
        raise ValueError(f"MO: invalid publisher evidence {name}")


def _validate(bodies: dict[str, bytes]) -> list[dict]:
    for name in FILES:
        if name.endswith(".html"):
            _validate_page(name, bodies[name])
    rows = parse(bodies[FILE])
    companion = parse_companion_texts(_pdf_text(bodies["total_population_preferred_march2008.pdf"], 3))
    if {(row["geo_id"], row["year"]): row["value"] for row in rows} != companion:
        raise ValueError("MO: original XLS and companion PDF disagree")
    state_text = _pdf_text(bodies["state_age_components_preferred_march2008.pdf"], 1)[0]
    normalized = " ".join(state_text.split())
    if ("Prepared by the Missouri Office of Administration - March, 2008" not in normalized
            or "Components of Change - Total Over the Previous Five Years" not in normalized
            or "2000 2005 2010 2015 2020 2025 2030" not in normalized):
        raise ValueError("MO: unexpected state PDF edition, years or component units")
    total = re.findall(r"^Statewide Total\s+Total\s+(.+)$", state_text, re.MULTILINE)
    if len(total) != 1 or _pdf_values(total[0].split()) != STATE_TOTALS:
        raise ValueError("MO: state age PDF and totals workbook disagree")
    return rows


def acquire() -> None:
    if (RAW_DIR / "manifest.json").exists():
        entries = fetch.read_manifest(RAW_DIR)
        if {entry["file"] for entry in entries} != set(FILES):
            raise ValueError("MO: incomplete snapshot manifest")
        _validate({name: (RAW_DIR / name).read_bytes() for name in FILES})
        print("MO acquire: reused validated snapshots")
        return
    bodies = {name: fetch.get_bytes(url) for name, url in FILES.items()}
    _validate(bodies)
    entries = []
    for name, body in bodies.items():
        fetch.write_snapshot(RAW_DIR / name, body)
        entries.append(dict(file=name, source=FILES[name], retrieved_at=date.today().isoformat(),
                            sha256=fetch.sha256(body), records=812 if name == FILE else None,
                            note="Original March 2008 Preferred Series; 2024 URL path is an upload date, not model vintage."))
    fetch.write_manifest(RAW_DIR, entries)


def load(conn) -> None:
    entries = {entry["file"]: entry for entry in fetch.read_manifest(RAW_DIR)}
    if set(entries) != set(FILES):
        raise ValueError("MO: incomplete snapshot manifest")
    rows = _validate({name: (RAW_DIR / name).read_bytes() for name in FILES})
    upsert_source(conn, source_id=SOURCE_ID, state="MO", agency=AGENCY,
        product_name="Missouri population projections: March 2008 Preferred Series, state and county totals",
        vintage=VINTAGE, base_year=BASE_YEAR, horizon_year=2030, source_url=TABLE_URL,
        retrieved_at=entries[FILE]["retrieved_at"],
        license="No explicit data license identified; cite the Missouri Office of Administration.",
        citation=f"{AGENCY}. Missouri Population Projections, Preferred Series: 2000 to 2030. March 2008.",
        method_notes=("This is an old March 2008 forecast ending in 2030, still linked by the current official catalog; "
            "no newer eligible OA edition was established in the source audit. The 2024/03 URL folder records hosting, not a revised vintage. "
            "The model launches from corrected April 1, 2000 Census counts; that historical anchor uses the MCP estimate label. "
            "base_year=2007 records the last underlying post-census population-estimate input named by the methods, used to calibrate migration. "
            "All 2005-2030 points remain projections: methods explicitly describe using 2000-2005 controls to project 2005 populations, "
            "then 2000-2007 controls starting in the 2005-2010 cycle. The datatype is not inferred from year <= base_year. No 2007 row is generated. "
            "The methods' data-source list cites estimates through 2006, while its operational migration discussion explicitly identifies 2007; "
            "the latter defines the last estimate input recorded here. "
            "Exact April 1 five-year points are loaded, with no interpolation. State and all 114 counties plus independent St. Louis city are published directly. "
            "County models are independent and their displayed totals exactly sum to the published state row. St. Louis county (29189) and city (29510) are distinct. "
            "The XLS totals are independently checked against every displayed cell of the three-page county PDF and the statewide age PDF Total row. "
            "The state age PDF dates the edition March 2008. Preferred is the sole selected series; no alternatives are exposed as scenarios. "
            "The catalog also publishes age/sex detail and births, deaths and net migration for previous five-year intervals; these are not loaded. "
            "Households, subcounty projections and eligible SDO jobs were not established; their publication coverage remains unknown."))
    insert_observations(conn, rows)
    conn.commit()
    print(f"MO load: {len(rows)} observations")


# Independently read from the rendered original county/state PDF tables.
FIXTURES = (("29", 2000, 5596687), ("29", 2005, 5781293), ("29", 2030, 6746762),
            ("29189", 2005, 1004004), ("29189", 2030, 956817),
            ("29510", 2005, 352136), ("29510", 2030, 349004),
            ("29095", 2030, 714467), ("29227", 2005, 2139), ("29227", 2030, 1826))


def verify(conn) -> None:
    rows = conn.execute("SELECT * FROM observations WHERE state='MO'").fetchall()
    ids = set(_counties().values()) | {"29"}
    assert len(rows) == 812 and {(row["geo_id"], row["year"]) for row in rows} == {(gid, year) for gid in ids for year in YEARS}
    assert all(row["geo_level"] == ("state" if row["geo_id"] == "29" else "county")
               and row["datatype"] == ("estimate" if row["year"] == 2000 else "projection")
               and row["variable"] == "population" and row["source_id"] == SOURCE_ID
               and row["scenario"] == "" and row["age_group"] == row["sex"] == row["race"] == "all" for row in rows)
    values = {(row["geo_id"], row["year"]): row["value"] for row in rows}
    for gid, year, value in FIXTURES:
        assert values[gid, year] == value
    source = conn.execute("SELECT vintage,base_year,horizon_year FROM sources WHERE source_id=?", (SOURCE_ID,)).fetchone()
    assert tuple(source) == (VINTAGE, 2007, 2030)
    print("MO verify: all 115 county-equivalent grids, source labels and rendered fixtures ok")


if __name__ == "__main__":
    if "--acquire" in sys.argv:
        acquire()
    else:
        print("usage: python -m sdo_mcp.ingest.mo --acquire")
