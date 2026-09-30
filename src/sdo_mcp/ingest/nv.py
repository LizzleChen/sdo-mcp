"""Nevada State Demographer October 2025 population totals, checked from PDF.

The summary tables (printed pages 2-3) and all detailed tables (pages 4-8)
must agree before any of the 378 published cells can enter the offline build.
"""

from __future__ import annotations

import io
import re
import sys
from datetime import date

from ..common import fetch
from ..store import REPO_ROOT, insert_observations, upsert_source
from .seed import COUNTY_FILE

RAW_DIR = REPO_ROOT / "data" / "raw" / "nv"
CATALOG_URL = "https://tax.nv.gov/news-publications/demographics/"
PDF_URL = "https://tax.nv.gov/wp-content/uploads/2025/09/Nevada-County-Population-Projections-2025-to-2044.pdf"
PDF_FILE = "population_2025-2044_oct2025.pdf"
CATALOG_FILE = "demographics_catalog_2026-09-30.html"
FILES = {PDF_FILE: PDF_URL, CATALOG_FILE: CATALOG_URL}
SOURCE_ID = "nv-pop-oct2025"
AGENCY = "Nevada Department of Taxation, Office of the State Demographer"
TITLE = "Nevada County Population Projections 2025 to 2044"
YEARS = tuple(range(2024, 2045))
NAMES = ("Carson City", "Churchill", "Clark", "Douglas", "Elko", "Esmeralda",
         "Eureka", "Humboldt", "Lander", "Lincoln", "Lyon", "Mineral", "Nye",
         "Pershing", "Storey", "Washoe", "White Pine", "State Total*")
NUMBER = r"(?:0|[1-9]\d{0,2}(?:,\d{3})*|[1-9]\d*)"


def _geographies() -> dict[str, str]:
    counties = {}
    for line in COUNTY_FILE.read_text().splitlines()[1:]:
        fields = line.split("|")
        if fields[0] == "NV":
            counties[fields[4].removesuffix(" County")] = fields[1] + fields[2]
    if set(counties) != set(NAMES[:-1]):
        raise ValueError("NV: unexpected Census county-equivalent set")
    return counties | {"State Total*": "32"}


def parse_pages(pages: list[str]) -> list[dict]:
    """Parse a reviewed page layout; reject changed units, edition and grids."""
    if len(pages) != 9 or "October 1, 2025" not in pages[0]:
        raise ValueError("NV: unexpected PDF edition or page count")
    intro = " ".join(pages[1].split())
    if not all(marker in intro for marker in (
        "2025 edition", "population estimates for July 1, 2024",
        "REMI) model v3.3.0", "Nevada State Demographer",
    )):
        raise ValueError("NV: unexpected methodology or estimate boundary")
    geos = _geographies()
    summary = {}
    for page_index, bands in ((2, (YEARS[:7], YEARS[7:14])), (3, (YEARS[14:],))):
        lines = [line.strip() for line in pages[page_index].splitlines() if line.strip()]
        title = "20-Year Population Projections Summary" + (" (cont'd)" if page_index == 3 else "")
        expected_lines = 1 + len(bands) * (1 + len(NAMES)) + 3
        if len(lines) != expected_lines:
            raise ValueError("NV: incomplete summary geography/year grid")
        if lines[0] != title or not all(marker in pages[page_index] for marker in (
            "*Totals may not sum precisely due to rounding",
            "†2024 Governor's Certified Series Population Estimates", TITLE,
        )):
            raise ValueError("NV: unexpected summary heading or estimate footnote")
        position = 1
        for years in bands:
            expected_header = " ".join(f"{year}†" if year == 2024 else str(year) for year in years)
            if lines[position] != expected_header:
                raise ValueError("NV: unexpected summary year header")
            position += 1
            for name in NAMES:
                match = re.fullmatch(re.escape(name) + r" " +
                                     " ".join([f"({NUMBER})"] * len(years)), lines[position])
                if match is None:
                    raise ValueError(f"NV: missing/duplicate geography or invalid population row: {name}")
                for year, value in zip(years, match.groups()):
                    summary[geos[name], year] = int(value.replace(",", ""))
                position += 1
        # Unexpected extra table rows may not be silently skipped.
        if lines[position:] != ["*Totals may not sum precisely due to rounding",
                                "†2024 Governor's Certified Series Population Estimates",
                                f"{TITLE} {page_index}"]:
            raise ValueError("NV: unexpected summary rows or footer")

    detail = {}
    for page_index in range(4, 9):
        text = pages[page_index]
        names = NAMES[(page_index - 4) * 4: (page_index - 3) * 4]
        for name in names:
            heading = name.removesuffix("*") + (" County" if name not in ("Carson City", "State Total*") else "")
            if f"20-Year Population Projections: {heading}" not in text:
                raise ValueError("NV: missing detailed geography heading")
        if "†2024 Governor's Certified Series Population Estimates" not in text:
            raise ValueError("NV: missing detailed estimate footnote")
        value_lines = [line.split() for line in text.splitlines()
                       if re.match(r"^202[4-9]†? |^20[34]\d ", line)]
        if len(value_lines) != len(names) // 2 * len(YEARS):
            raise ValueError("NV: incomplete detailed year grid")
        for pair_index in range(len(names) // 2):
            for year, tokens in zip(YEARS, value_lines[pair_index * 21: (pair_index + 1) * 21]):
                width = 2 if year == 2024 else 4
                year_label = "2024†" if year == 2024 else str(year)
                if (len(tokens) != width * 2 or tokens[0] != year_label
                        or tokens[width] != year_label
                        or not re.fullmatch(NUMBER, tokens[1])
                        or not re.fullmatch(NUMBER, tokens[width + 1])):
                    raise ValueError("NV: malformed detailed population/year row")
                for side in (0, 1):
                    name = names[pair_index * 2 + side]
                    detail[geos[name], year] = int(tokens[side * width + 1].replace(",", ""))
    if summary != detail:
        raise ValueError("NV: summary and detailed tables disagree")
    return [{"state": "NV", "geo_level": "state" if gid == "32" else "county",
             "geo_id": gid, "year": year, "variable": "population", "value": value,
             "datatype": "estimate" if year == 2024 else "projection", "source_id": SOURCE_ID}
            for (gid, year), value in summary.items()]


def parse_pdf(body: bytes) -> list[dict]:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(body))
        pages = [page.extract_text() for page in reader.pages]
    except Exception as exc:
        raise ValueError("NV: response is not a readable population PDF") from exc
    return parse_pages(pages)


def _validate_catalog(body: bytes) -> None:
    page = body.decode("utf-8", "replace")
    if not all(marker in page for marker in (
        "<html", "Nevada-County-Population-Projections-2025-to-2044.pdf",
        "March 2026 Five Year Projections", "Age, Sex, Race and Hispanic Origin",
    )):
        raise ValueError("NV: unexpected demographic publication catalog")


def _validate_all(bodies: dict[str, bytes]) -> list[dict]:
    _validate_catalog(bodies[CATALOG_FILE])
    return parse_pdf(bodies[PDF_FILE])


def acquire() -> None:
    if (RAW_DIR / "manifest.json").exists():
        entries = {e["file"] for e in fetch.read_manifest(RAW_DIR)}
        if entries != set(FILES):
            raise ValueError("NV: incomplete saved snapshot manifest")
        _validate_all({name: (RAW_DIR / name).read_bytes() for name in FILES})
        print("NV acquire: reused validated snapshots")
        return
    bodies = {name: fetch.get_bytes(url, timeout=60) for name, url in FILES.items()}
    rows = _validate_all(bodies)
    entries = []
    for name, url in FILES.items():
        fetch.write_snapshot(RAW_DIR / name, bodies[name])
        entries.append({"file": name, "source": url, "retrieved_at": date.today().isoformat(),
                        "sha256": fetch.sha256(bodies[name]),
                        "records": len(rows) if name == PDF_FILE else None,
                        "note": "Original October 2025 long-range population PDF and source catalog. Printed pages 2-3 summary and pages 4-8 details agree at every served cell. March 2026 near-term series is a separate product, not merged."})
    fetch.write_manifest(RAW_DIR, entries)


def load(conn) -> None:
    entries = {e["file"]: e for e in fetch.read_manifest(RAW_DIR)}
    rows = _validate_all({name: (RAW_DIR / name).read_bytes() for name in FILES})
    upsert_source(
        conn, source_id=SOURCE_ID, state="NV", agency=AGENCY,
        product_name="Nevada state and county 20-year population projections",
        vintage="October 2025", base_year=2024, horizon_year=2044, source_url=PDF_URL,
        retrieved_at=entries[PDF_FILE]["retrieved_at"],
        license="No explicit data license identified; cite the Nevada State Demographer.",
        citation=f"{AGENCY}. Nevada County Population Projections 2025 to 2044. October 1, 2025.",
        method_notes=(
            "REMI v3.3.0 demographic/economic model adjusted with QCEW employment growth, "
            "GOED development-project inputs, and Census migration information. The model launches "
            "from July 1, 2024 Governor-certified state/county estimates (certified March 1, 2025). "
            "2024 is an estimate; every 2025-2044 row is a projection. Summary tables on printed "
            "pages 2-3 are cross-checked against all detailed tables on pages 4-8. Carson City is "
            "county equivalent 32510. Separately published state totals are preserved: rounded "
            "county sums can differ. The catalog's March 2026 five-year product and separate "
            "age/sex/race/Hispanic-origin report are not merged into this selected long-range edition. "
            "Employment assumptions are model inputs, not published job totals for this tool. "
            "Households, eligible jobs, components and place forecast publication coverage remains unverified."
        ),
    )
    insert_observations(conn, rows)
    conn.commit()
    print(f"NV load: {len(rows)} observations")


def verify(conn) -> None:
    # Checked visually against the original PDF summary, printed pages 2-3.
    for gid, year, value, datatype in (
        ("32", 2024, 3282911, "estimate"), ("32", 2025, 3326902, "projection"),
        ("32", 2044, 3699248, "projection"), ("32003", 2044, 2726185, "projection"),
        ("32009", 2025, 1081, "projection"), ("32009", 2044, 1205, "projection"),
        ("32510", 2044, 64275, "projection"),
    ):
        row = conn.execute("SELECT value,datatype FROM observations WHERE state='NV' "
                           "AND geo_id=? AND year=? AND variable='population'", (gid, year)).fetchone()
        assert tuple(row) == (value, datatype)
    shape = conn.execute("SELECT COUNT(*),COUNT(DISTINCT geo_id),COUNT(DISTINCT year),"
                         "MIN(year),MAX(year) FROM observations WHERE state='NV'").fetchone()
    assert tuple(shape) == (378, 18, 21, 2024, 2044)
    print("NV verify: state/17 county-equivalent annual grid and PDF anchors ok")


if __name__ == "__main__":
    if "--acquire" in sys.argv:
        acquire()
    else:
        print("usage: python -m sdo_mcp.ingest.nv --acquire")
