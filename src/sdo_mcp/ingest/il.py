"""Illinois IDPH 2023 edition (released May 2024), Table 3 population totals.

Read the original PDF offline. Select July 2020 estimates and 2025/2030/2035
projections, preserving Table 3's state row rather than mixing tables.
"""

from __future__ import annotations

import io
import re
import sys
from datetime import date

from ..common import fetch
from ..store import REPO_ROOT, insert_observations, upsert_source
from .seed import COUNTY_FILE

RAW_DIR = REPO_ROOT / "data" / "raw" / "il"
FILE = "population_2023.pdf"
URL = "https://dph.illinois.gov/content/dam/soi/en/web/idph/publications/idph/data-and-statistics/vital-statistics/illinois-population-data/population-projections_202035.pdf"
CATALOG_URL = "https://dph.illinois.gov/data-statistics/public-data-assets/illinois-population-projections.html"
POPULATION_URL = "https://dph.illinois.gov/data-statistics/vital-statistics/illinois-population-data.html"
REFERENCES = (
    ("projection_catalog_2026-09-29.html", CATALOG_URL, "Illinois Population Projections"),
    ("population_catalog_2026-09-29.html", POPULATION_URL, "Illinois Population Data"),
)
SOURCE_ID = "il-pop-2023-table3"
AGENCY = "Illinois Department of Public Health, Office of Policy, Planning and Statistics, Division of Health Data and Policy"
VINTAGE = "2023 edition (released May 2024)"
LICENSE = "No explicit data license identified in the reviewed products; cite the Illinois Department of Public Health."
YEARS = (2020, 2025, 2030, 2035)
TABLE_PAGES = (10, 11, 12)  # Zero-based PDF pages; printed pages 8-10.
TABLE_HEADER = (
    "Table 3. Population Projections for Illinois Counties: 2020 to 2035",
    "(as of July 1 of the specified years, except as noted)",
    "Census1 Estimate1 Projections",
    "State/County April 1, 2020 2020 2025 2030 2035",
)
FOOTER = ("1U.S. Census Bureau", "Source: Illinois Department of Public Health, 2023")


def _geographies() -> dict[str, str]:
    """Map source names to the saved Census-2020 state/county identifiers."""
    geos = {"Illinois": "17"}
    for line in COUNTY_FILE.read_text().splitlines()[1:]:
        parts = line.split("|")
        if parts[0] == "IL":
            name = parts[4].removesuffix(" County")
            if name == "De Witt":
                name = "DeWitt"  # Explicit IDPH spelling; not another county.
            geos[name] = parts[1] + parts[2]
    if len(geos) != 103 or geos.get("DeWitt") != "17039":
        raise ValueError("IL: expected Illinois and 102 Census counties")
    return geos


def _parse_table3(pages: list[str]) -> list[dict]:
    """Strict row/header parsing, isolated so malformed extractions are testable."""
    if len(pages) != 3:
        raise ValueError("IL: expected all three Table 3 pages")
    geos = _geographies()
    seen = set()
    rows = []
    for offset, text in enumerate(pages):
        lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
        if lines[:5] != [str(8 + offset), *TABLE_HEADER]:
            raise ValueError(f"IL: unexpected Table 3 header/reference dates on page {8 + offset}")
        data = lines[5:]
        if offset == 2:
            if tuple(data[-2:]) != FOOTER:
                raise ValueError("IL: missing Table 3 source/estimate footnote")
            data = data[:-2]
        for line in data:
            match = re.fullmatch(r"(.+?)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)", line)
            if not match:
                raise ValueError(f"IL: malformed population row: {line!r}")
            name, *cells = match.groups()
            if name not in geos:
                raise ValueError(f"IL: unknown geography or malformed row: {name!r}")
            if name in seen:
                raise ValueError(f"IL: duplicate geography: {name}")
            seen.add(name)
            # Every cell, including the excluded Census column, must be a
            # nonnegative integer. Blanks/suppression never become zeros.
            if any(not re.fullmatch(r"(?:0|[1-9]\d{0,2}(?:,\d{3})*)", cell) for cell in cells):
                raise ValueError(f"IL: invalid integer population for {name}: {cells}")
            census, *values = (int(cell.replace(",", "")) for cell in cells)
            for year, value in zip(YEARS, values, strict=True):
                rows.append(dict(
                    state="IL", geo_level="state" if name == "Illinois" else "county",
                    geo_id=geos[name], year=year, variable="population", value=value,
                    datatype="estimate" if year == 2020 else "projection", source_id=SOURCE_ID,
                ))
        if len(data) != (41, 41, 21)[offset]:
            raise ValueError(f"IL: incomplete Table 3 page {8 + offset}")
    if seen != geos.keys():
        raise ValueError(f"IL: incomplete geography grid: {sorted(geos.keys() - seen)}")
    # Methods say counties are controlled to the state. Table 3 reconciles
    # exactly; no adjustment or tolerance is needed for this selected table.
    for year in YEARS:
        state = next(r["value"] for r in rows if r["geo_id"] == "17" and r["year"] == year)
        counties = sum(r["value"] for r in rows if r["geo_level"] == "county" and r["year"] == year)
        if counties != state:
            raise ValueError(f"IL: Table 3 county/state totals differ in {year}")
    return rows


def _validate_edition(cover: str, methods: str) -> None:
    cover = " ".join(cover.split())
    methods = " ".join(methods.split())
    if ("(2023 Edition)" not in cover or not re.search(r"R\s*eleased May 2024", cover)
            or "Illinois Department of Public Health" not in cover
            or "July 1, 2020 to July 1, 2035" not in cover):
        raise ValueError("IL: unexpected report edition or producer")
    for marker in (
        "Certificate of Need (CON) Program",
        "These projections began with the July 1, 2020 population estimates",
        "County projected population by age and sex were controlled to state projected totals by sex.",
    ):
        if marker not in methods:
            raise ValueError(f"IL: unexpected methodology/base year; missing {marker!r}")


def parse(body: bytes) -> list[dict]:
    from pypdf import PdfReader

    fetch.validate_pdf(body, "IL population")
    reader = PdfReader(io.BytesIO(body))
    if len(reader.pages) != 132:
        raise ValueError("IL: unexpected report page count")
    _validate_edition(reader.pages[0].extract_text(), reader.pages[3].extract_text())
    return _parse_table3([reader.pages[i].extract_text() for i in TABLE_PAGES])


def _validate_catalog(body: bytes, marker: str) -> None:
    text = body.decode("utf-8-sig")
    if ("<html" not in text.lower() or marker not in text
            or "population-projections_202035.pdf" not in text):
        raise ValueError("IL: unexpected catalog or missing selected edition link")


def acquire() -> None:
    """Validate all downloads before saving; reuse immutable saved snapshots."""
    required = {FILE} | {name for name, _, _ in REFERENCES}
    if (RAW_DIR / "manifest.json").exists():
        entries = fetch.read_manifest(RAW_DIR)
        if not required <= {entry["file"] for entry in entries}:
            raise ValueError("IL: incomplete saved manifest")
        parse((RAW_DIR / FILE).read_bytes())
        for name, _, marker in REFERENCES:
            _validate_catalog((RAW_DIR / name).read_bytes(), marker)
        print("IL acquire: reused validated 2023 edition snapshots")
        return
    body = fetch.get_bytes(URL)
    rows = parse(body)
    downloads = [(FILE, URL, body, len(rows))]
    for name, url, marker in REFERENCES:
        body = fetch.get_bytes(url)
        _validate_catalog(body, marker)
        downloads.append((name, url, body, None))
    entries = []
    for name, url, body, count in downloads:
        fetch.write_snapshot(RAW_DIR / name, body)
        entries.append(dict(
            file=name, source=url, retrieved_at=date.today().isoformat(),
            sha256=fetch.sha256(body), records=count,
            note="Original IDPH 2023 edition (released May 2024) or supporting catalog. Table 3, printed pages 8-10 (PDF pages 11-13), supplies 412 state/county totals. July 2020 estimates selected; April Census, Chicago, age/sex and five-year components retained only in the PDF.",
        ))
    fetch.write_manifest(RAW_DIR, entries)
    print(f"IL acquire: {len(rows)} totals and two reference catalogs")


def load(conn) -> None:
    entries = fetch.read_manifest(RAW_DIR)
    retrieved = next(e["retrieved_at"] for e in entries if e["file"] == FILE)
    for name, _, marker in REFERENCES:
        _validate_catalog((RAW_DIR / name).read_bytes(), marker)
    rows = parse((RAW_DIR / FILE).read_bytes())
    actual = {(r["geo_level"], r["geo_id"]) for r in conn.execute(
        "SELECT geo_level, geo_id FROM geographies WHERE state='IL'"
    )}
    if actual != {(r["geo_level"], r["geo_id"]) for r in rows}:
        raise ValueError("IL: seeded geographies do not match the source")
    upsert_source(
        conn, source_id=SOURCE_ID, state="IL", agency=AGENCY,
        product_name="Population Projections: Illinois, Chicago and Illinois Counties by Age and Sex, 2020-2035; Table 3 totals",
        vintage=VINTAGE, base_year=2020, horizon_year=2035,
        source_url=URL, retrieved_at=retrieved, license=LICENSE,
        citation="Illinois Department of Public Health. Population Projections, 2023 Edition, released May 2024. Table 3, printed pages 8-10 (PDF pages 11-13).",
        method_notes=(
            "Table 3 supplies population totals in persons for Illinois and all 102 counties. "
            "All selected values refer to July 1: 2020 estimates and 2025, 2030, 2035 projections. "
            "The separate April 1, 2020 Census column is archived but excluded to avoid two points for one year. "
            "base_year=2020 is the last estimate year named by the methods. "
            "State totals use linear regression; county age/sex cohort-component projections are controlled "
            "to state totals by sex. Table 3 county sums equal its state row exactly. "
            "The separate Table 1 state totals are 11 lower in 2025 and 3 lower in 2030; this source "
            "discrepancy is preserved by selecting Table 3 consistently, without adjusting published values. "
            "Source DeWitt maps to Census De Witt County (17039); all counties use the saved Census-2020 roster. "
            "No annual interpolation or extrapolation. 2025 remains a projection after that year. "
            "Chicago (Table 2), age/sex detail and five-year components (Tables A-2/A-4/A-5) are archived but not served."
        ),
    )
    count = insert_observations(conn, rows)
    conn.commit()
    print(f"IL load: {count} observations")


# Independently read from rendered Table 3, printed pages 8, 9 and 10.
FIXTURES = (
    ("17", 2020, 12785245), ("17", 2025, 12780256), ("17", 2030, 12775248),
    ("17", 2035, 12770245), ("17031", 2020, 5262741), ("17031", 2025, 5148792),
    ("17031", 2035, 4900208), ("17069", 2020, 3634), ("17069", 2025, 3455),
    ("17069", 2035, 3076), ("17039", 2035, 13679), ("17085", 2035, 20533),
    ("17163", 2035, 246323), ("17203", 2035, 40490),
)


def verify(conn) -> None:
    rows = conn.execute("SELECT * FROM observations WHERE state='IL'").fetchall()
    actual = {(r["geo_id"], r["year"]) for r in rows}
    expected = {(gid, year) for gid in _geographies().values() for year in YEARS}
    assert len(rows) == 412 and actual == expected, "IL: incomplete or duplicate grid"
    assert all(
        r["variable"] == "population" and r["source_id"] == SOURCE_ID
        and r["scenario"] == "" and r["age_group"] == r["sex"] == r["race"] == "all"
        and r["geo_level"] == ("state" if r["geo_id"] == "17" else "county")
        and r["datatype"] == ("estimate" if r["year"] == 2020 else "projection")
        and r["value"] >= 0 and float(r["value"]).is_integer()
        for r in rows
    ), "IL: invalid observation semantics"
    values = {(r["geo_id"], r["year"]): r["value"] for r in rows}
    for gid, year, value in FIXTURES:
        assert values[gid, year] == value, f"IL fixture: {gid}/{year}"
    for year in YEARS:
        assert sum(r["value"] for r in rows if r["year"] == year and r["geo_level"] == "county") == values["17", year]
    print(f"IL verify: {len(FIXTURES)} fixtures and 103 complete geography series ok")


if __name__ == "__main__":
    if "--acquire" in sys.argv:
        acquire()
    else:
        print("usage: python -m sdo_mcp.ingest.il --acquire")
