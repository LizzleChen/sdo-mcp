"""WVU BBER October 2022 state/county population totals, checked against age/sex PDF."""
from __future__ import annotations

import io
import re
import sys
from datetime import date

from ..common import fetch
from ..store import REPO_ROOT, insert_observations, upsert_source
from .seed import COUNTY_FILE

RAW_DIR = REPO_ROOT / "data" / "raw" / "wv"
CATALOG_URL = "https://business.wvu.edu/research-outreach/bureau-of-business-and-economic-research/data"
URL = "https://business.wvu.edu/files/d/73f29801-fb12-40d4-b8d0-5802a29742be/wvsummary_2022.pdf"
FILE = "population_summary_oct2022.pdf"
DETAIL_FILE = "population_age_sex_oct2022.pdf"
FILES = {
    FILE: URL,
    DETAIL_FILE: "https://business.wvu.edu/files/d/a0ae66e0-5d50-4c96-b327-8194e3478890/wvcounties_2022.pdf",
    "projection_catalog_2026-10-02.html": CATALOG_URL,
    "hca_projection_source_2026-10-02.html": "https://hca.wv.gov/certificateofneed/Pages/Applications.aspx",
    "hca_application_mar2017.pdf": "https://hca.wv.gov/certificateofneed/Documents/CON_Application-August_2016.pdf",
}
SOURCE_ID = "wv-pop-oct2022"
AGENCY = "Bureau of Business and Economic Research, West Virginia University"
VINTAGE = "October 2022"
YEARS = (2020, 2025, 2030, 2035, 2040)
SEXES = ("MALE", "FEMALE", "MALE & FEMALE")
AGES = tuple(f"{a}-{a + 4}" for a in range(0, 85, 5)) + ("85+",)
FOOTER = "Bureau of Business and Economic Research, College of Business and Economics, West Virginia University, October 2022"
STATE_VALUES = (1793716, 1768247, 1747217, 1723594, 1705509)


def _geographies() -> dict[str, str]:
    geos = {"West Virginia": "54"}
    for line in COUNTY_FILE.read_text().splitlines()[1:]:
        fields = line.split("|")
        if fields[0] == "WV":
            geos[fields[4].removesuffix(" County")] = fields[1] + fields[2]
    if len(geos) != 56:
        raise ValueError("WV: incomplete reference geography roster")
    return geos


def _integer(token: str) -> int:
    if not re.fullmatch(r"(?:0|[1-9]\d{0,2}(?:,\d{3})*|[1-9]\d*)", token):
        raise ValueError("WV: invalid nonnegative integer population")
    return int(token.replace(",", ""))


def _lines(text: str) -> list[str]:
    return [" ".join(line.split()) for line in text.splitlines() if line.strip()]


def _cells(line: str, label: str) -> tuple[int, ...]:
    fields = line.rsplit(" ", 5)
    if len(fields) != 6 or fields[0] != label:
        raise ValueError("WV: changed or incomplete geography/age grid")
    return tuple(_integer(v) for v in fields[1:])


def _parse_summary_page(text: str, sex: str) -> dict[str, tuple[int, ...]]:
    lines = _lines(text)
    first_date = "4/1/2020" if sex == "MALE" else "7/1/2020"
    header = ("State/County " if sex == "MALE" else "") + first_date + " 7/1/2025 7/1/2030 7/1/2035 7/1/2040"
    if (len(lines) != 60 or lines[:3] != [
            "West Virginia Population Projection by Counties 2020-2040, Summary Table", sex, header]
            or lines[-1] != FOOTER):
        raise ValueError("WV: changed summary header, sex, year or edition")
    return {name: _cells(line, name) for name, line in zip(_geographies(), lines[3:-1], strict=True)}


def _parse_detail_page(text: str, name: str) -> dict[str, tuple[int, ...]]:
    lines = _lines(text)
    # Original detailed pages 10/11 misspell two county titles; summary and
    # Census roster spell them correctly. Explicit aliases change no IDs.
    detail_name = {"Doddridge": "Dodridge", "Fayette": "Feyette"}.get(name, name)
    title = "State of West Virginia" if name == "West Virginia" else detail_name + " County, W.Va"
    if (len(lines) != 67 or lines[:3] != ["Population Projection by Age and Sex, " + title,
            "Census-2020", "4/1/2020 7/1/2025 7/1/2030 7/1/2035 7/1/2040"]
            or lines[63:] != [FOOTER, "Gender &", "Age", "Projections"]):
        raise ValueError("WV: changed detail geography, Census/projection header or edition")
    totals = {}
    for n, sex in enumerate(SEXES):
        start = 3 + n * 20
        if lines[start] != sex:
            raise ValueError("WV: changed detail sex grid")
        for label, line in zip(AGES, lines[start + 1:start + 19], strict=True):
            _cells(line, label)
        totals[sex] = _cells(lines[start + 19], "TOTAL" if n == 2 else "Total")
    return totals


def _reader(body: bytes, pages: int):
    from pypdf import PdfReader
    fetch.validate_pdf(body, "WV population")
    reader = PdfReader(io.BytesIO(body))
    if len(reader.pages) != pages:
        raise ValueError("WV: incomplete PDF page/geography grid")
    return reader


def parse(summary: bytes, detail: bytes) -> list[dict]:
    tables = {sex: _parse_summary_page(page.extract_text() or "", sex)
              for sex, page in zip(SEXES, _reader(summary, 3).pages, strict=True)}
    geos = _geographies()
    for name, page in zip(geos, _reader(detail, 56).pages, strict=True):
        independent = _parse_detail_page(page.extract_text() or "", name)
        if any(independent[sex] != tables[sex][name] for sex in SEXES):
            raise ValueError("WV: summary and independent detail totals disagree")
        # The original Roane 2035 sex totals sum to 12,174 while its combined
        # Total is 12,173 in both documents. Retain that published discrepancy.
        differences = tuple(tables["MALE"][name][i] + tables["FEMALE"][name][i] - tables["MALE & FEMALE"][name][i]
                            for i in range(5))
        if differences != ((0, 0, 0, 1, 0) if name == "Roane" else (0, 0, 0, 0, 0)):
            raise ValueError("WV: published sex-total discrepancy changed")
    totals = tables["MALE & FEMALE"]
    if totals["West Virginia"] != STATE_VALUES:
        raise ValueError("WV: rendered state fixtures changed")
    if any(sum(totals[name][i] for name in geos if name != "West Virginia") != STATE_VALUES[i]
           for i in range(5)):
        raise ValueError("WV: published state/county totals disagree")
    return [dict(state="WV", geo_level="state" if gid == "54" else "county", geo_id=gid,
                 year=y, variable="population", value=v, datatype="estimate" if y == 2020 else "projection",
                 source_id=SOURCE_ID)
            for name, gid in geos.items() for y, v in zip(YEARS, totals[name], strict=True)]


def _validate(bodies: dict[str, bytes]) -> list[dict]:
    for name, markers in (
        ("projection_catalog_2026-10-02.html", ("<html", "West Virginia Population Projections", "released October 2022", "wvsummary_2022.pdf", "wvcounties_2022.pdf")),
        ("hca_projection_source_2026-10-02.html", ("<html", "Link for population projections", "business.wvu.edu/research-outreach/bureau-of-business-and-economic-research/data"))):
        text = bodies[name].decode("utf-8", "replace").replace("&#58;", ":")
        if any(marker not in text for marker in markers):
            raise ValueError("WV: invalid original catalog or state-use evidence")
    application = _reader(bodies["hca_application_mar2017.pdf"], 30)
    text = " ".join((application.pages[14].extract_text() or "").split())
    if "Data provided by the Authority shall be used" not in text or "Estimated population of the service area" not in text:
        raise ValueError("WV: changed state application population requirement")
    return parse(bodies[FILE], bodies[DETAIL_FILE])


def acquire() -> None:
    if (RAW_DIR / "manifest.json").exists():
        entries = fetch.read_manifest(RAW_DIR)
        if {entry["file"] for entry in entries} != set(FILES):
            raise ValueError("WV: incomplete saved snapshot manifest")
        _validate({name: (RAW_DIR / name).read_bytes() for name in FILES})
        print("WV acquire: reused validated October 2022 snapshots")
        return
    bodies = {name: fetch.get_bytes(url) for name, url in FILES.items()}
    rows = _validate(bodies)
    entries = []
    for name, url in FILES.items():
        fetch.write_snapshot(RAW_DIR / name, bodies[name])
        entries.append(dict(file=name, source=url, retrieved_at=date.today().isoformat(),
            sha256=fetch.sha256(bodies[name]), records=len(rows) if name == FILE else None,
            note="Original publisher bytes. Summary totals independently checked against companion age/sex TOTAL rows; detailed Census2020 header resolves conflicting summary2020 dates. HCA directs projection users to WVU catalog."))
    fetch.write_manifest(RAW_DIR, entries)


def load(conn) -> None:
    entries = {e["file"]: e for e in fetch.read_manifest(RAW_DIR)}
    if set(entries) != set(FILES):
        raise ValueError("WV: incomplete saved snapshot manifest")
    rows = _validate({name: (RAW_DIR / name).read_bytes() for name in FILES})
    actual = {(r["geo_level"], r["geo_id"]) for r in conn.execute("SELECT * FROM geographies WHERE state='WV'")}
    if actual != {(r["geo_level"], r["geo_id"]) for r in rows}:
        raise ValueError("WV: seeded geography roster differs from publication")
    upsert_source(conn, source_id=SOURCE_ID, state="WV", agency=AGENCY,
        product_name="West Virginia Population Projection by Counties 2020-2040: summary both-sex totals",
        vintage=VINTAGE, base_year=None, horizon_year=2040, source_url=URL,
        retrieved_at=entries[FILE]["retrieved_at"],
        license="No explicit data license identified in public original files; cite WVU Bureau of Business and Economic Research.",
        citation="WVU Bureau of Business and Economic Research. West Virginia Population Projection by Counties 2020-2040, October 2022, Summary Table page 3, MALE & FEMALE; companion age/sex PDF TOTAL rows.",
        method_notes=("WVU BBER is the Census FSCPP West Virginia contact; the state Health Care Authority explicitly directs Certificate of Need projection users to this same publisher catalog. "
            "This is a state-used demographic product, not a claim of a statewide statutory mandate. "
            "The companion detailed PDF labels 2020 Census-2020 (April 1) and 2025-2040 Projections (July 1). Census history uses the MCP estimate label. "
            "The summary female/combined columns print July 1 2020, conflicting with its male column and the detailed Census April 1 header; their counts exactly match. "
            "Detailed page titles spell Doddridge as Dodridge and Fayette as Feyette; explicit aliases preserve the summary's correct names and Census FIPS. "
            "The 2020 Census anchor is confirmed, but the last underlying estimate input and released technical methodology were not established; base_year is null, not inferred from the 2022 release. "
            "All 280 whole-person state/county totals match the independent age/sex TOTAL rows. All county sums agree exactly with published state totals. "
            "Roane 2035 male 5976 plus female 6198 is 12174, but both documents give combined Total 12173; the published combined Total is preserved. All other sex totals agree exactly. "
            "Single unnamed scenario; no interpolation or post2040 extension. Age/sex detail is archived but not served. Household, component, subcounty and eligible SDO jobs coverage remains unverified; economic outlooks and occupational products are not substituted."))
    insert_observations(conn, rows)
    print(f"WV: {len(rows)} population totals loaded")


def verify(conn) -> None:
    expected = parse((RAW_DIR / FILE).read_bytes(), (RAW_DIR / DETAIL_FILE).read_bytes())
    actual = conn.execute("SELECT * FROM observations WHERE state='WV'").fetchall()
    fields = ("geo_level", "geo_id", "year", "variable", "value", "datatype", "source_id")
    if (len(actual) != 280 or {tuple(r[k] for k in fields) for r in actual} != {tuple(r[k] for k in fields) for r in expected}
            or any(r["scenario"] or any(r[k] != "all" for k in ("age_group", "sex", "race")) for r in actual)):
        raise ValueError("WV: loaded totals differ from checked original grid")


if __name__ == "__main__":
    if sys.argv[1:] == ["acquire"]:
        acquire()
