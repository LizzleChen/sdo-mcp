"""Kansas Budget's adopted November 2006 county projections, ending in 2021.

The newer CEDBR university forecast is a separately documented candidate;
official state adoption or demographic authority for that product is unresolved.
"""

from __future__ import annotations

import io
import re
import sys
from datetime import date
from html.parser import HTMLParser

from ..common import fetch
from ..store import REPO_ROOT, insert_observations, upsert_source
from .seed import COUNTY_FILE

RAW_DIR = REPO_ROOT / "data" / "raw" / "ks"
URL = "https://budget.kansas.gov/wp-content/uploads/fy2011-2009-2010-econ-demo-rpt.pdf"
CATALOG_URL = "https://budget.kansas.gov/population/"
FILES = {
    "economic_demographic_report_january2010.pdf": URL,
    "population_catalog_2026-10-02.html": CATALOG_URL,
    "historical_report_catalog_2026-10-02.html": "https://budget.kansas.gov/population/historic/",
    "cedbr_population_candidate_2026-10-02.html": "https://cedbr.org/data-portal/population-and-demographics/population-forecast/",
    "cedbr_portal_sponsorship_2026-10-02.html": "https://cedbr.org/data-portal/",
    "cedbr_jobs_candidate_2026-10-02.html": "https://cedbr.org/data-portal/employment/",
}
FILE = next(iter(FILES))
SOURCE_ID = "ks-pop-adopted-2006"
AGENCY = "Kansas Division of the Budget (commissioned from Moody's Economy.com)"
VINTAGE = "November 2006 (published January 2010)"
YEARS = tuple(range(2010, 2022))
AGE_LABELS = (*[f"Age {start} thru {start + 4}" for start in range(0, 65, 5)], "Age 65 thru 84", "Age 85 & Older")


def _counties() -> dict[str, str]:
    result = {}
    for line in COUNTY_FILE.read_text().splitlines()[1:]:
        fields = line.split("|")
        if fields[0] == "KS":
            result[fields[4]] = fields[1] + fields[2]
    if len(result) != 105:
        raise ValueError("KS: expected all 105 Census counties")
    return result


def _values(tokens: list[str]) -> tuple[int, ...]:
    # The publisher omits commas in several four/five-digit cells. Both
    # spellings are valid; suppression, signs, fractions and missing values are not.
    if len(tokens) != len(YEARS) or any(not re.fullmatch(r"(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)", token) for token in tokens):
        raise ValueError("KS: invalid population integer or missing year cell")
    return tuple(int(token.replace(",", "")) for token in tokens)


def parse_texts(texts: list[str]) -> list[dict]:
    """Parse Appendix L's 40 pages with explicit county and age continuation checks."""
    if len(texts) != 40:
        raise ValueError("KS: unexpected Appendix L page count")
    counties = _counties()
    totals = {}
    ages = {}
    current = None
    for index, text in enumerate(texts):
        lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
        appendix = "Appendix L" if index == 0 else "Appendix L (cont'd)"
        if (lines[:3] != [appendix, "Kansas Population Projections, by County, by Age Cohort for 2010 through 2021",
                          " ".join(map(str, YEARS))] or lines[-1] != str(139 + index)):
            raise ValueError("KS: unexpected Appendix L title, year header or printed page")
        for line in lines[3:-1]:
            if index == 39 and line == "Source: Moody's Economy.com":
                continue
            heading = re.fullmatch(r"(.+ County)( \(cont'd\))?", line)
            if heading:
                name, continued = heading.groups()
                if name not in counties:
                    raise ValueError(f"KS: unknown county {name!r}")
                if continued:
                    if name != current or name not in totals:
                        raise ValueError("KS: invalid county continuation")
                else:
                    if name in totals or (current is not None and len(ages.get(current, {})) != len(AGE_LABELS)):
                        raise ValueError("KS: duplicate county or incomplete previous age grid")
                    current = name
                    ages[name] = {}
                continue
            if current is None:
                raise ValueError("KS: numeric row has no county heading")
            if line.startswith("Total Population "):
                if current in totals or ages[current]:
                    raise ValueError("KS: duplicate or misplaced county total")
                totals[current] = _values(line.removeprefix("Total Population ").split())
                continue
            age = next((label for label in AGE_LABELS if line.startswith(label + " ")), None)
            if age is None or current not in totals:
                raise ValueError("KS: unknown table row or missing county total")
            if age in ages[current] or age != AGE_LABELS[len(ages[current])]:
                raise ValueError("KS: duplicate or misplaced age row")
            ages[current][age] = _values(line.removeprefix(age + " ").split())
    if (set(totals) != set(counties) or set(ages) != set(counties)
            or any(tuple(values) != AGE_LABELS for values in ages.values())):
        raise ValueError("KS: incomplete county, age or year grid")
    if "Source: Moody's Economy.com" not in " ".join(texts[-1].split()):
        raise ValueError("KS: missing original Appendix L source attribution")
    return [dict(state="KS", geo_level="county", geo_id=counties[name], year=year, variable="population",
                 value=value, datatype="projection", source_id=SOURCE_ID)
            for name, values in totals.items() for year, value in zip(YEARS, values, strict=True)]


def _reader(body: bytes):
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(body))
        if len(reader.pages) != 186:
            raise ValueError("unexpected original report page count")
        return reader
    except Exception as exc:
        raise ValueError("KS: response is not the readable 186-page original report PDF") from exc


def parse(body: bytes) -> list[dict]:
    reader = _reader(body)
    title = " ".join((reader.pages[2].extract_text() or "").split())
    methods = " ".join((reader.pages[63].extract_text() or "").split())
    if ("The Governor’s Economic and Demographic Report 2009-2010" not in title
            or "Kansas Division of the Budget January 2010" not in title
            or "The most recent set was produced in November 2006" not in methods
            or "with Moody’s Economy.com to produce population projections" not in methods
            or "2010 through 2021" not in methods):
        raise ValueError("KS: unexpected original report edition or official adoption evidence")
    return parse_texts([page.extract_text() or "" for page in reader.pages[146:186]])


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
        "population_catalog": ("Kansas Certified Population Data", "no longer published", "FY 2012", "population estimates"),
        "historical_report_catalog": ("Past Governor’s Economic and Demographic Reports", "2009-2010", "2008-2009"),
        "cedbr_population_candidate": ("Population Forecast", "Explore Components on Tableau"),
        "cedbr_portal_sponsorship": ("Population Forecast", "next 50 years", "Patterson Family Foundation"),
        "cedbr_jobs_candidate": ("Economic Forecasts", "2026 Kansas Employment Forecast", "By CEDBR"),
    }
    key = next((key for key in markers if name.startswith(key)), None)
    if "<html" not in page.lower() or key is None or any(marker not in text for marker in markers[key]):
        raise ValueError(f"KS: invalid publisher evidence {name}")
    if name.startswith("cedbr_population_candidate") and "2024PopulationForecastDashboard" not in page:
        raise ValueError("KS: unexpected candidate dashboard edition")


def _validate(bodies: dict[str, bytes]) -> list[dict]:
    for name in FILES:
        if name.endswith(".html"):
            _validate_page(name, bodies[name])
    return parse(bodies[FILE])


def acquire() -> None:
    if (RAW_DIR / "manifest.json").exists():
        entries = fetch.read_manifest(RAW_DIR)
        if {entry["file"] for entry in entries} != set(FILES):
            raise ValueError("KS: incomplete snapshot manifest")
        _validate({name: (RAW_DIR / name).read_bytes() for name in FILES})
        print("KS acquire: reused validated snapshots")
        return
    bodies = {name: fetch.get_bytes(url) for name, url in FILES.items()}
    _validate(bodies)
    entries = []
    for name, body in bodies.items():
        fetch.write_snapshot(RAW_DIR / name, body)
        entries.append(dict(file=name, source=FILES[name], retrieved_at=date.today().isoformat(),
                            sha256=fetch.sha256(body), records=1260 if name == FILE else None,
                            note="Selected original November 2006 state-commissioned forecast, published January 2010. CEDBR pages are adoption-unconfirmed candidate evidence only."))
    fetch.write_manifest(RAW_DIR, entries)


def load(conn) -> None:
    entries = {entry["file"]: entry for entry in fetch.read_manifest(RAW_DIR)}
    if set(entries) != set(FILES):
        raise ValueError("KS: incomplete snapshot manifest")
    rows = _validate({name: (RAW_DIR / name).read_bytes() for name in FILES})
    upsert_source(conn, source_id=SOURCE_ID, state="KS", agency=AGENCY,
        product_name="Officially commissioned county population projections, Appendix L: 2010-2021",
        vintage=VINTAGE, base_year=None, horizon_year=2021, source_url=URL,
        retrieved_at=entries[FILE]["retrieved_at"],
        license="No explicit data license identified in the public state report; cite Kansas Division of the Budget and Moody's Economy.com.",
        citation="Kansas Division of the Budget. The Governor's Economic and Demographic Report 2009-2010, January 2010. Appendix L, pp. 139-178; November 2006 projections commissioned from Moody's Economy.com.",
        method_notes=("This is an old November 2006 forecast whose entire 2010-2021 horizon is in the past; it supplies no forecast for 2022 or later. "
            "The report's p. 56 explicitly records the Kansas Division of the Budget commissioning Moody's Economy.com to produce the November 2006 population projections. "
            "January 2010 is the publication date of the selected report, not the model vintage. "
            "The report is no longer produced: the current official catalog states that demographic appendices from FY2012 onward contain Census population estimates. "
            "No successor official projection was established. Newer CEDBR 2024 population dashboards are separate university forecasts: official state demographic authority or adoption was not established, "
            "so no CEDBR population or employment values are substituted. "
            "The last underlying estimate year and detailed forecasting method for the commissioned product are unstated; base_year is null. "
            "References to the 2000 Census and current historical estimates elsewhere in the report do not identify the forecast base. "
            "Appendix L's Total Population rows for all 105 counties are loaded at each exact annual year 2010-2021. "
            "Every value remains a projection, including past years and 2010; no Census or base-year estimate is generated. "
            "Although the narrative mentions projections for Kansas and all counties, Appendix L contains no statewide Total Population row; county values are never summed into an unpublished state forecast. "
            "All 40 appendix pages have explicit county and age-row continuation checks. Displayed totals are independently checked with Poppler text extraction and rendered original fixtures. "
            "The publisher omits commas in some numeric cells, including Bourbon County's 2016 total 14846; values are preserved as integers. "
            "Age-cohort detail is published but not loaded; household, components, subcounty and eligible SDO jobs publication coverage remains unverified."))
    insert_observations(conn, rows)
    conn.commit()
    print(f"KS load: {len(rows)} observations")


# Independently read from rendered original Appendix L pages, not parser output.
FIXTURES = (("20001", 2010, 13448), ("20001", 2021, 12519), ("20011", 2016, 14846),
            ("20071", 2010, 1218), ("20071", 2021, 873),
            ("20091", 2010, 552605), ("20091", 2021, 614875),
            ("20173", 2010, 480866), ("20173", 2021, 503158),
            ("20209", 2021, 141796))


def verify(conn) -> None:
    rows = conn.execute("SELECT * FROM observations WHERE state='KS'").fetchall()
    ids = set(_counties().values())
    assert len(rows) == 1260 and {(row["geo_id"], row["year"]) for row in rows} == {(gid, year) for gid in ids for year in YEARS}
    assert all(row["geo_level"] == "county" and row["datatype"] == "projection" and row["variable"] == "population"
               and row["source_id"] == SOURCE_ID and row["scenario"] == ""
               and row["age_group"] == row["sex"] == row["race"] == "all" for row in rows)
    values = {(row["geo_id"], row["year"]): row["value"] for row in rows}
    for gid, year, value in FIXTURES:
        assert values[gid, year] == value
    source = conn.execute("SELECT vintage,base_year,horizon_year FROM sources WHERE source_id=?", (SOURCE_ID,)).fetchone()
    assert tuple(source) == (VINTAGE, None, 2021)
    print("KS verify: all 105 county grids, unknown base, expired horizon and rendered fixtures ok")


if __name__ == "__main__":
    if "--acquire" in sys.argv:
        acquire()
    else:
        print("usage: python -m sdo_mcp.ingest.ks --acquire")
