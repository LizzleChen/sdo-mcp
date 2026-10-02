"""Oklahoma Commerce March 2023 report: exact 2025-2070 published totals."""
from __future__ import annotations

import io
import re
import sys
from datetime import date

from ..common import fetch
from ..store import REPO_ROOT, insert_observations, upsert_source
from .seed import COUNTY_FILE

RAW_DIR = REPO_ROOT / "data" / "raw" / "ok"
CATALOG_URL = "https://www.okcommerce.gov/doing-business/data-reports/census-2030-demographics/"
URL = "https://www.okcommerce.gov/wp-content/uploads/Oklahoma-State-and-County-Population-Projections-Through-2070.pdf"
FILE = "population_2020-2070_march2023.pdf"
CATALOG_FILE = "demographics_catalog_2026-10-02.html"
LEGAL_FILE = "publisher_terms_2026-10-02.html"
FILES = {FILE: URL, CATALOG_FILE: CATALOG_URL,
         LEGAL_FILE: "https://www.okcommerce.gov/privacy-policy-legal-notice/"}
SOURCE_ID = "ok-pop-march2023"
AGENCY = "Oklahoma Department of Commerce, Research and Economic Analysis Division"
VINTAGE = "March 2023"
YEARS = tuple(range(2025, 2071, 5))
STATE_VALUES = (4005315, 4094815, 4149670, 4235079, 4279804, 4376036, 4430463, 4547687, 4621172, 4741439)
COUNTY_STATE_DIFFERENCES = (-1, 0, -3, 7, 1, -1, 2, 3, 2, -2)
# Independent readings of rendered original pp21/47/77/131.
FIXTURES = (("40", 2025, 4005315), ("40", 2030, 4094815), ("40", 2070, 4741439),
            ("40109", 2025, 819801), ("40109", 2030, 854619), ("40109", 2070, 1145555),
            ("40025", 2025, 2092), ("40025", 2030, 1987), ("40025", 2070, 1356),
            ("40055", 2025, 5652), ("40055", 2070, 5159))


def _geographies() -> dict[str, str]:
    counties = {p[4].removesuffix(" County"): p[1] + p[2]
                for line in COUNTY_FILE.read_text().splitlines()[1:]
                if (p := line.split("|"))[0] == "OK"}
    if len(counties) != 77:
        raise ValueError("OK: expected complete 77-county FIPS roster")
    return {"Oklahoma Statewide": "40"} | counties


def _integer(token: str) -> int:
    if not re.fullmatch(r"(?:0|[1-9]\d{0,2}(?:,\d{3})*|[1-9]\d*)", token):
        raise ValueError("OK: invalid or suppressed integer population")
    return int(token.replace(",", ""))


def _parse_table(text: str, name: str, page_number: int) -> dict[int, int]:
    lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
    if (not lines or lines[0] != f"{page_number} | Page"
            or lines.count("Population Projections") != 1
            or lines.count("Annual Population Estimates") != (0 if name == "Carter" else 1)):
        raise ValueError("OK: unexpected page number or population table headings")
    start = lines.index("Population Projections") + 1
    table = lines[start:]
    # The original Beckham page puts its source footer before the table.
    if name == "Beckham":
        if table[:1] != ["Source: Oklahoma Department of Commerce"]:
            raise ValueError("OK: changed Beckham source placement")
        table = table[1:]
    label = "Cimmaron" if name == "Cimarron" else name
    if table[:1] != [label]:
        raise ValueError("OK: unknown, duplicate or changed geography label")
    table = table[1:]
    data = table[:5]
    if len(data) != 5:
        raise ValueError("OK: incomplete population year grid")
    values = {}
    for index, line in enumerate(data):
        cells = line.split()
        years = (2000 + index * 5, 2025 + index * 5, 2050 + index * 5)
        if len(cells) != 6 or tuple(cells[::2]) != tuple(map(str, years)):
            raise ValueError("OK: incomplete or changed population year grid")
        for year, cell in zip(years, cells[1::2], strict=True):
            values[year] = _integer(cell)
    remainder = table[5:]
    # Five county footers misattribute the projections to Decennial Census;
    # the report and headings establish Commerce authorship. Preserve values.
    footer = ("Source: US Census Bureau, Decennial Census" if name in
              {"Le Flore", "Lincoln", "Logan", "Love", "McClain"}
              else "Source: Oklahoma Department of Commerce")
    if name == "Beckham":
        if remainder:
            raise ValueError("OK: unexpected extra Beckham cells")
    elif not remainder or remainder.pop(0) != footer:
        raise ValueError("OK: changed table source footer")
    # Greer and Harmon physically repeat the same table below its source.
    if name in {"Greer", "Harmon"}:
        expected = list(data)
        if name == "Greer":
            expected[0] = "P" + expected[0]
        if remainder != expected:
            raise ValueError("OK: changed duplicated county table")
    elif name == "Atoka":
        # Atoka's annual estimate cells follow the projection footer in PDF
        # reading order. They are deliberately not part of the selected table.
        if len(remainder) != 16 or any(line.split()[0] != str(1960 + i)
                                        for i, line in enumerate(remainder)):
            raise ValueError("OK: changed Atoka annual-estimate reading order")
    elif name != "Beckham" and remainder:
        raise ValueError("OK: duplicate or extra projection rows")
    return {year: values[year] for year in YEARS}


def _validate_edition(reader) -> None:
    if len(reader.pages) != 195:
        raise ValueError("OK: unexpected report page count")
    title = " ".join((reader.pages[0].extract_text() or "").split())
    methods = " ".join(" ".join((reader.pages[i].extract_text() or "").split()) for i in (16, 17, 18, 19))
    if any(marker not in title for marker in ("Oklahoma Population Projection 2020-2070", "Published March 2023", "Jon Chiappe")):
        raise ValueError("OK: unexpected report edition")
    if any(marker not in methods for marker in ("2010 Decennial Census", "aging forward the 2020 population", "2019 ACS data", "sum of population projections for all 77", "Armed Forces", "incarcerated")):
        raise ValueError("OK: changed producer, model anchor or population universe")


def parse(body: bytes) -> list[dict]:
    from pypdf import PdfReader
    fetch.validate_pdf(body, "OK population report")
    reader = PdfReader(io.BytesIO(body))
    _validate_edition(reader)
    rows = []
    for index, (name, gid) in enumerate(_geographies().items()):
        page_index = 20 + index * 2
        values = _parse_table(reader.pages[page_index].extract_text() or "", name, page_index + 1)
        rows.extend(dict(state="OK", geo_level="state" if gid == "40" else "county", geo_id=gid,
                         year=year, variable="population", value=values[year], datatype="projection",
                         source_id=SOURCE_ID) for year in YEARS)
    _check_values(rows)
    return rows


def _check_values(rows: list[dict]) -> None:
    values = {(r["geo_id"], r["year"]): r["value"] for r in rows}
    if tuple(values["40", year] for year in YEARS) != STATE_VALUES:
        raise ValueError("OK: state totals disagree with rendered original")
    for gid, year, value in FIXTURES:
        if values[gid, year] != value:
            raise ValueError("OK: rendered independent fixture disagrees")
    for year, difference in zip(YEARS, COUNTY_STATE_DIFFERENCES, strict=True):
        if sum(r["value"] for r in rows if r["geo_level"] == "county" and r["year"] == year) - values["40", year] != difference:
            raise ValueError("OK: published county/state difference changed")


def _validate(bodies: dict[str, bytes]) -> list[dict]:
    for name, markers in ((CATALOG_FILE, ("<html", "Oklahoma state and county population projections through 2070", "Oklahoma-State-and-County-Population-Projections-Through-2070.pdf")),
                          (LEGAL_FILE, ("<html", "Privacy Notice", "Oklahoma Department of Commerce", "Open Records"))):
        text = " ".join(bodies[name].decode("utf-8", "replace").split())
        if any(marker not in text for marker in markers):
            raise ValueError("OK: invalid catalog or publisher terms")
    return parse(bodies[FILE])


def acquire() -> None:
    if (RAW_DIR / "manifest.json").exists():
        entries = fetch.read_manifest(RAW_DIR)
        if {e["file"] for e in entries} != set(FILES):
            raise ValueError("OK: incomplete saved manifest")
        _validate({name: (RAW_DIR / name).read_bytes() for name in FILES})
        print("OK acquire: reused validated March 2023 snapshots")
        return
    bodies = {name: fetch.get_bytes(url) for name, url in FILES.items()}
    rows = _validate(bodies)
    entries = []
    for name, body in bodies.items():
        fetch.write_snapshot(RAW_DIR / name, body)
        entries.append(dict(file=name, source=FILES[name], retrieved_at=date.today().isoformat(), sha256=fetch.sha256(body),
                            records=len(rows) if name == FILE else None,
                            note="Original publisher bytes. March 2023 report; selected 2025-2070 state/all 77-county totals checked against rendered original and independent Poppler extraction. No ambiguous historical cells or 2012 archived edition selected."))
    fetch.write_manifest(RAW_DIR, entries)


def load(conn) -> None:
    entries = {e["file"]: e for e in fetch.read_manifest(RAW_DIR)}
    if set(entries) != set(FILES):
        raise ValueError("OK: incomplete saved manifest")
    rows = _validate({name: (RAW_DIR / name).read_bytes() for name in FILES})
    if {(r["geo_level"], r["geo_id"]) for r in conn.execute("SELECT * FROM geographies WHERE state='OK'")} != {(r["geo_level"], r["geo_id"]) for r in rows}:
        raise ValueError("OK: seeded geographies differ from publication")
    upsert_source(conn, source_id=SOURCE_ID, state="OK", agency=AGENCY,
        product_name="Oklahoma State and County Population Projections Through 2070: published 2025-2070 totals",
        vintage=VINTAGE, base_year=None, horizon_year=2070, source_url=URL, retrieved_at=entries[FILE]["retrieved_at"],
        license="No explicit data license or copying restriction identified in the current publisher report/catalog/terms; cite Oklahoma Department of Commerce.",
        citation="Oklahoma Department of Commerce, Research and Economic Analysis Division. Oklahoma State and County Population Projections Through 2070. Published March 2023. Population Projections tables, printed pp21-175 (alternate pages).",
        method_notes=("The current official Commerce catalog links the March 2023 report, replacing the old 2012/2075 research lead. "
            "Load exact published integer-person totals for state and all 77 counties at five-year points 2025-2070. Every selected point remains a projection, including past 2025. "
            "The last underlying estimate input is unstated, so base_year is null. Operational p19 methods age forward the 2020 Census population with 2019 ACS/2010 age-distribution inputs; generic p17 methods instead say state models start Census 2010. "
            "Historical estimate tables through 2022 statewide and 2021 counties do not establish use as model inputs. The ambiguous 2000-2020 columns under Population Projections are archived but not loaded; no base row is fabricated. "
            "Population includes civilian residents, stationed Armed Forces and incarcerated residents. Future exact reference day is unstated. "
            "The report describes cohort-component/Hamilton-Perry calculations; alternative random-forest/exponential methods are proposed future work, not selected scenarios. "
            "Printed p20 says the state is a sum of county forecasts, but independently rounded tables differ by -1,0,-3,+7,+1,-1,+2,+3,+2,-2 persons across selected years; preserve both products without adjustment. "
            "Cimarron's page 47 table is misspelled Cimmaron; its checked page and roster resolve to FIPS 40025. Greer and Harmon physically repeat identical tables; each is loaded once after checking that its duplicates agree. "
            "Five county projection footers mistakenly cite Decennial Census; Commerce report authorship and projection headings establish the selected product. The table values are retained. "
            "Despite narrative promises, no complete future age/sex table was found in this report; Appendix 1 contains fertility rates, Appendix 2 mortality rates and Appendix 3 historical components. "
            "Municipal, household-count, future-component and eligible SDO jobs publication coverage remains unverified; OESC industry/occupational projections are not substituted."))
    insert_observations(conn, rows)
    conn.commit()
    print(f"OK load: {len(rows)} observations")


def verify(conn) -> None:
    rows = [dict(r) for r in conn.execute("SELECT * FROM observations WHERE state='OK'")]
    ids = set(_geographies().values())
    assert len(rows) == 780 and {(r["geo_id"], r["year"]) for r in rows} == {(gid, year) for gid in ids for year in YEARS}
    assert all(r["datatype"] == "projection" and r["source_id"] == SOURCE_ID and r["scenario"] == ""
               and r["variable"] == "population" and r["age_group"] == r["sex"] == r["race"] == "all"
               and r["geo_level"] == ("state" if r["geo_id"] == "40" else "county")
               and r["value"] >= 0 and float(r["value"]).is_integer() for r in rows)
    _check_values(rows)
    source = conn.execute("SELECT * FROM sources WHERE source_id=?", (SOURCE_ID,)).fetchone()
    assert source["base_year"] is None and source["horizon_year"] == 2070 and source["vintage"] == VINTAGE
    print("OK verify: March2023 state/all77counties, exact projections, rendered fixtures and published differences ok")


if __name__ == "__main__":
    if "--acquire" in sys.argv:
        acquire()
    else:
        print("usage: python -m sdo_mcp.ingest.ok --acquire")
