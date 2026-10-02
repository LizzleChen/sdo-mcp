"""Vermont: adopted 2025 state forecast and archived 2013 county scenarios."""
from __future__ import annotations

import io
import re
import sys
from datetime import date

from ..common import fetch
from ..store import REPO_ROOT, insert_observations, upsert_source
from .seed import COUNTY_FILE

RAW_DIR = REPO_ROOT / "data" / "raw" / "vt"
CATALOG_URL = "https://accd.vermont.gov/community-development/town-future/data"
URL = "https://outside.vermont.gov/agency/ACCD/ACCD_Web_Docs/CD/CPR/Planning-Your-Towns-Future/ACCD-DED-VTPopulationProjections-2010-2030.pdf"
FILE = "population_2010-2030_aug2013.pdf"
CATALOG_FILE = "planning_data_catalog_2026-10-02.html"
HOUSING_FILE = "housing_targets_appendix_2025-2029.pdf"
HOUSING_URL = "https://outside.vermont.gov/agency/ACCD/ACCD_Web_Docs/Housing/Housing-Needs-Assessment/2025-2029/Housing-Targets-Appendix.pdf"
HOUSING_CATALOG_FILE = "housing_catalog_2026-10-02.html"
HOUSING_CATALOG_URL = "https://accd.vermont.gov/housing/plans-data-rules/needs-assessment"
EXTRACT_FILE = "state_age_chart_2030-2050_march2025.json"
RECIPE_FILE = "state_age_chart_extraction_recipe.txt"
DOWNLOADS = {FILE: URL, CATALOG_FILE: CATALOG_URL, HOUSING_FILE: HOUSING_URL,
             HOUSING_CATALOG_FILE: HOUSING_CATALOG_URL}
FILES = DOWNLOADS | {EXTRACT_FILE: HOUSING_URL + "#page=16", RECIPE_FILE: HOUSING_URL + "#page=16"}
STATE_SOURCE_ID = "vt-state-pop-housing-march2025"
STATE_VINTAGE = "March 10, 2025 revision (prepared August-October 2024)"
STATE_YEARS = (2030, 2040, 2050)
STATE_TOTALS = (666640, 667903, 644731)
CHART_SHA256 = "d773b9e7fca354c413dfe784f6c789805ce2be369fb27f671a583a0b77d1c469"
# All 54 labels independently read from rendered original and checked by local
# Apple Vision OCR; both ACCD and VHFA PDFs contain identical chart pixels.
STATE_AGE_VALUES = (
    (29443, 29208, 29882, 34269, 36911, 42840, 43333, 38554, 41279, 40387, 37213, 37954, 41813, 47775, 46638, 39987, 27913, 21241),
    (29330, 31026, 30812, 30566, 31272, 35862, 38395, 44295, 44725, 39722, 42193, 40955, 36962, 36923, 38937, 42585, 36378, 36965),
    (26030, 28343, 30693, 32468, 32244, 31987, 32529, 37080, 39628, 45637, 45715, 40281, 41908, 39844, 34420, 32912, 30371, 42641),
)
STATE_AGENCY = "Vermont ACCD Department of Housing and Community Development; Vermont Housing Finance Agency (contracted producer)"
SOURCE_ID = "vt-pop-aug2013"
AGENCY = "Vermont Agency of Commerce and Community Development"
VINTAGE = "August 2013"
YEARS = (2010, 2020, 2030)
SCENARIOS = ("a", "b")
AGES = ("<5",) + tuple(f"{age}-{age + 4}" for age in range(5, 85, 5)) + ("85+",)
STATE_VALUES = {"a": (625741, 653575, 670073), "b": (625741, 628688, 620480)}
# Values independently read from original rendered PDF pp6/11/21/25.
FIXTURES = (("50", "a", 2020, 653575), ("50", "a", 2030, 670073),
            ("50", "b", 2020, 628688), ("50", "b", 2030, 620480),
            ("50009", "a", 2010, 6306), ("50009", "a", 2020, 5949), ("50009", "a", 2030, 5489),
            ("50007", "b", 2010, 156545), ("50007", "b", 2020, 161812), ("50007", "b", 2030, 162967))


def _geographies() -> dict[str, str]:
    counties = {p[4]: p[1] + p[2] for line in COUNTY_FILE.read_text().splitlines()[1:]
                if (p := line.split("|"))[0] == "VT"}
    if len(counties) != 14 or list(counties) != sorted(counties):
        raise ValueError("VT: expected complete alphabetical 14-county roster")
    # Published report order places Orleans before Rutland/Washington/Windham.
    order = ("Addison", "Bennington", "Caledonia", "Chittenden", "Essex", "Franklin", "Grand Isle",
             "Lamoille", "Orange", "Orleans", "Rutland", "Washington", "Windham", "Windsor")
    if set(counties) != {name + " County" for name in order}:
        raise ValueError("VT: changed county roster")
    return {"Vermont Total": "50"} | {name + " County": counties[name + " County"] for name in order}


def _integer(token: str) -> int:
    if not re.fullmatch(r"(?:0|[1-9]\d{0,2}(?:,\d{3})*|[1-9]\d*)", token):
        raise ValueError("VT: invalid or suppressed integer population")
    return int(token.replace(",", ""))


def _parse_table(text: str, name: str, scenario: str) -> tuple[int, ...]:
    lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
    expected = (f"Vermont Population Projections by Age and County, 2020, 2030 - Scenario {scenario.upper()} "
                "Ages 2010 Census 2020 %change from 2010 2030 %change from 2010")
    try:
        start = lines.index(name)
    except ValueError as exc:
        raise ValueError("VT: missing or changed geography label") from exc
    if " ".join(lines[:start]) != expected or lines.count(name) != 1:
        raise ValueError("VT: unexpected geography, scenario or year header")
    data = lines[start + 1:]
    if len(data) != 19:
        raise ValueError("VT: duplicate or missing population age rows")
    cells = []
    for line, label in zip(data, (*AGES, "Total"), strict=True):
        parts = line.split()
        if len(parts) != 6 or parts[0] != label:
            raise ValueError("VT: changed age/year grid")
        counts = tuple(_integer(parts[index]) for index in (1, 2, 4))
        for token, value in zip((parts[3], parts[5]), counts[1:], strict=True):
            if not re.fullmatch(r"-?\d+\.\d%", token) or counts[0] <= 0:
                raise ValueError("VT: invalid percentage or Census denominator")
            if abs(float(token[:-1]) - (value / counts[0] - 1) * 100) > 0.051:
                raise ValueError("VT: changed population/percentage column order")
        cells.append(counts)
    if any(sum(row[index] for row in cells[:-1]) != cells[-1][index] for index in range(3)):
        raise ValueError("VT: exhaustive age cells disagree with published Total")
    return cells[-1]


def _validate_edition(reader) -> None:
    if len(reader.pages) != 61:
        raise ValueError("VT: unexpected report page count")
    title = " ".join((reader.pages[0].extract_text() or "").split())
    method = " ".join((reader.pages[1].extract_text() or "").split())
    if any(marker not in title for marker in ("August, 2013", "Ken Jones", "Agency of Commerce and Community Development", "Committee reviewed the methodology and results")):
        raise ValueError("VT: unexpected producer, adoption or report edition")
    if any(marker not in method for marker in ("1990-2010", "1990s (Scenario A)", "2000s (Scenario B)", "1990s migration rates")):
        raise ValueError("VT: changed scenario definitions or Census base")


def parse(body: bytes) -> list[dict]:
    from pypdf import PdfReader
    fetch.validate_pdf(body, "VT population report")
    reader = PdfReader(io.BytesIO(body))
    _validate_edition(reader)
    rows = []
    for scenario_index, scenario in enumerate(SCENARIOS):
        for index, (name, gid) in enumerate(_geographies().items()):
            values = _parse_table(reader.pages[5 + scenario_index * 15 + index].extract_text() or "", name, scenario)
            rows.extend(dict(state="VT", geo_level="state" if gid == "50" else "county", geo_id=gid,
                             year=year, variable="population", value=value,
                             datatype="estimate" if year == 2010 else "projection", scenario=scenario,
                             source_id=SOURCE_ID) for year, value in zip(YEARS, values, strict=True))
    _check_values(rows)
    return [row for row in rows if row["geo_level"] == "county"]


def _check_values(rows: list[dict]) -> None:
    values = {(r["geo_id"], r["scenario"], r["year"]): r["value"] for r in rows}
    for scenario in SCENARIOS:
        if tuple(values["50", scenario, year] for year in YEARS) != STATE_VALUES[scenario]:
            raise ValueError("VT: state totals disagree with rendered original")
        for year in YEARS:
            if sum(r["value"] for r in rows if r["geo_level"] == "county" and r["scenario"] == scenario and r["year"] == year) != values["50", scenario, year]:
                raise ValueError("VT: normalized counties disagree with published state total")
    for gid, scenario, year, value in FIXTURES:
        if values[gid, scenario, year] != value:
            raise ValueError("VT: independent rendered fixture disagrees")
    for gid in _geographies().values():
        if values[gid, "a", 2010] != values[gid, "b", 2010]:
            raise ValueError("VT: scenarios have inconsistent Census history")


def _parse_state(body: bytes, extract: bytes) -> list[dict]:
    from pypdf import PdfReader
    import json
    fetch.validate_pdf(body, "VT adopted housing-assessment population")
    reader = PdfReader(io.BytesIO(body))
    if len(reader.pages) != 18:
        raise ValueError("VT: unexpected adopted state report page count")
    title = " ".join((reader.pages[0].extract_text() or "").split())
    methods = " ".join((reader.pages[10].extract_text() or "").split())
    caption = " ".join((reader.pages[15].extract_text() or "").split())
    if any(marker not in title for marker in ("Housing Targets", "prepared for the Vermont Department of Housing", "August - October 2024", "Vermont Housing Finance Agency")):
        raise ValueError("VT: changed contracted producer or state adoption")
    if any(marker not in methods for marker in ("cohort-component population projection", "0.49%", "2020-2023", "2019 used for model")) or "projected population if current trends continue, 2030-2050" not in caption:
        raise ValueError("VT: changed state population methods or chart caption")
    image = reader.pages[15]["/Resources"]["/XObject"]["/Im1"].get_object()
    if (image["/Width"], image["/Height"], image["/BitsPerComponent"]) != (1126, 394, 8) or fetch.sha256(image.get_data()) != CHART_SHA256:
        raise ValueError("VT: original labeled state-age chart changed; re-review extraction")
    try:
        data = json.loads(extract)
    except Exception as exc:
        raise ValueError("VT: invalid derived state-age extraction") from exc
    if (data.get("source_sha256") != fetch.sha256(body) or data.get("chart_decoded_sha256") != CHART_SHA256
            or data.get("page") != 16 or data.get("age_groups") != list(AGES)
            or data.get("years") != list(STATE_YEARS)
            or data.get("values_by_year") != [list(values) for values in STATE_AGE_VALUES]):
        raise ValueError("VT: incomplete or altered verified age/year extraction")
    totals = tuple(sum(cells) for cells in data["values_by_year"])
    if totals != STATE_TOTALS:
        raise ValueError("VT: exhaustive state-age sums changed")
    return [dict(state="VT", geo_level="state", geo_id="50", year=year,
                 variable="population", value=value, datatype="projection", scenario="current_trends",
                 source_id=STATE_SOURCE_ID) for year, value in zip(STATE_YEARS, totals, strict=True)]


def _make_extract(body: bytes) -> bytes:
    import json
    return (json.dumps(dict(source_url=HOUSING_URL, source_sha256=fetch.sha256(body),
        chart_decoded_sha256=CHART_SHA256, page=16, extraction="54 published chart labels, visually checked and independently matched by local Apple Vision OCR; no chart-position approximation",
        age_groups=list(AGES), years=list(STATE_YEARS), values_by_year=STATE_AGE_VALUES), indent=2) + "\n").encode()


def _recipe() -> bytes:
    return ("Source: " + HOUSING_URL + "\n"
        "Extract PDF page16 /Resources /XObject /Im1 with pypdf (no Pillow needed).\n"
        "The indexed image is1126x394,8bits,FlateDecode; decodedpixelSHA256=" + CHART_SHA256 + ".\n"
        "Render original using: pdftoppm -f 16 -l 16 -scale-to 1700 -png -singlefile SOURCE.pdf page16\n"
        "Read all18exhaustive agebar labels in each2030/2040/2050column, top to bottom; exact labels only, never widths.\n"
        "Independently run local Apple Vision VNRecognizeTextRequest accurate with languagecorrectionfalse on renderedpage.\n"
        "For numericNN,NNN labels use boundingboxybetween0.71and0.89; xbetween0.25and0.30(2030),0.50and0.56(2040),0.78and0.83(2050).\n"
        "Sort descendingy within eachcolumn. Require18labels percolumn and exact agreement with all54visuallyread values.\n"
        "Labels Under5,5to9,...,80to84,85yearsandover exhaust allages. Sum eachcolumn:666640,667903,644731.\n"
        "These sums normalize exhaustive agecells inside the published state; no counties/regions are combined.\n"
        "VHFA producer version Housing-Targets-Appendix-MAcorrected.pdf contains identicaldecodedchartpixels; independently checked.\n"
        "Rebuild uses archivedPDF, exactdecodedimagefingerprint and checkedstructuredextract; OCR is acquisitionQA only.\n").encode()


def _validate(bodies: dict[str, bytes]) -> list[dict]:
    catalog = " ".join(bodies[CATALOG_FILE].decode("utf-8", "replace").split())
    if any(marker not in catalog for marker in ("<html", "2010-2030 Population Projections", "ACCD has published", "ACCD-DED-VTPopulationProjections-2010-2030.pdf", "Archive Notice")):
        raise ValueError("VT: invalid archived publisher catalog")
    catalog = " ".join(bodies[HOUSING_CATALOG_FILE].decode("utf-8", "replace").split())
    if any(marker not in catalog for marker in ("<html", "VHFA was contracted", "Updated March 10, 2025", "Housing-Targets-Appendix.pdf", "HOME Act of 2023")):
        raise ValueError("VT: invalid adopted state product catalog or edition")
    if bodies[RECIPE_FILE] != _recipe():
        raise ValueError("VT: altered raster extraction recipe")
    return parse(bodies[FILE]) + _parse_state(bodies[HOUSING_FILE], bodies[EXTRACT_FILE])


def acquire() -> None:
    if (RAW_DIR / "manifest.json").exists():
        entries = fetch.read_manifest(RAW_DIR)
        if {e["file"] for e in entries} != set(FILES):
            raise ValueError("VT: incomplete saved manifest")
        _validate({name: (RAW_DIR / name).read_bytes() for name in FILES})
        print("VT acquire: reused validated August 2013 snapshots")
        return
    bodies = {name: fetch.get_bytes(url) for name, url in DOWNLOADS.items()}
    bodies[EXTRACT_FILE] = _make_extract(bodies[HOUSING_FILE])
    bodies[RECIPE_FILE] = _recipe()
    rows = _validate(bodies)
    entries = []
    for name, body in bodies.items():
        fetch.write_snapshot(RAW_DIR / name, body)
        entries.append(dict(file=name, source=FILES[name], retrieved_at=date.today().isoformat(), sha256=fetch.sha256(body),
                            records=84 if name == FILE else 3 if name == HOUSING_FILE else 54 if name == EXTRACT_FILE else None,
                            note="Original publisher bytes. August 2013 ACCD state/all14county Total rows with A/B labels and 2010Census base, checked against rendered original and independent Poppler. Adopted March2025 housing-assessment state-age chart supplies3state totals by checked exhaustiveage summation; housingtargets are not householdcounts."))
    fetch.write_manifest(RAW_DIR, entries)


def load(conn) -> None:
    entries = {e["file"]: e for e in fetch.read_manifest(RAW_DIR)}
    if set(entries) != set(FILES):
        raise ValueError("VT: incomplete saved manifest")
    rows = _validate({name: (RAW_DIR / name).read_bytes() for name in FILES})
    if {(r["geo_level"], r["geo_id"]) for r in conn.execute("SELECT * FROM geographies WHERE state='VT'")} != {(r["geo_level"], r["geo_id"]) for r in rows}:
        raise ValueError("VT: seeded geographies differ from publication")
    upsert_source(conn, source_id=SOURCE_ID, state="VT", agency=AGENCY,
        product_name="Vermont Population Projections 2010-2030: county Total rows, Scenarios A/B",
        vintage=VINTAGE, base_year=2010, horizon_year=2030, source_url=URL, retrieved_at=entries[FILE]["retrieved_at"],
        license="No explicit data license or restrictive terms identified in the report/catalog; cite Vermont ACCD and report authors.",
        citation="Ken Jones and Lilly Schwarz. Vermont Population Projections 2010-2030. Vermont Agency of Commerce and Community Development, August 2013. PDF pp6-35, Total rows, Scenarios A and B.",
        method_notes=("The current ACCD planning-data page labels this August 2013 report as an archived historical reference and explicitly credits ACCD publication. "
            "The cover credits ACCD's Economic Research Analyst and a state agency review committee. Select all 14 county Total rows; this edition's state totals are archived and independently check the county controls, but a separately adopted March 2025 state product supersedes them for serving. "
            "2010 Census history uses this schema's estimate label. 2020 and 2030 remain projections of the 2013 edition, including past 2020. Base year is 2010; units are integer persons, all ages and both sexes. "
            "Scenario A uses 1990-2000 migration patterns; Scenario B uses 2000-2010. B is the server's county default for the later migration period, not a publisher-preferred series. Source A/B labels remain unchanged, and no average is manufactured. "
            "An age-cohort model uses county-specific birth rates and declining mortality. County figures are controlled to independent state projections, and all published age cells and county totals exactly reconcile with their respective Totals. "
            "The report discusses Census residence rather than seasonal or de facto population. The historical reference date is April 1; the exact future reference day is unstated. "
            "Town, city, grant and gore projections on PDF pages 36-61 use weighted historical growth controlled to counties. They remain published but not loaded pending geography crosswalks; these areas are not all Census places. "
            "Age detail is archived but not served. Household counts, complete future components and eligible ACCD jobs coverage remain unverified."))

    upsert_source(conn, source_id=STATE_SOURCE_ID, state="VT", agency=STATE_AGENCY,
        product_name="2025-2029 Housing Needs Assessment, Appendix 1: adopted current-trends state population, 2030/2040/2050",
        vintage=STATE_VINTAGE, base_year=None, horizon_year=2050, source_url=HOUSING_URL,
        retrieved_at=entries[HOUSING_FILE]["retrieved_at"],
        license="No explicit data license or restrictive terms identified in the official report/catalog; cite Vermont DHCD and VHFA.",
        citation="Vermont Housing Finance Agency for Vermont ACCD Department of Housing and Community Development and VAPDA. Vermont Housing Needs Assessment 2025-2029, Appendix 1: Statewide and Regional Housing Targets. Updated March 10, 2025; prepared August-October 2024. Published page 16, current-trends population age chart.",
        method_notes=("The official ACCD catalog establishes DHCD/VAPDA's legal housing-target mandate and VHFA's contracted production. The selected appendix was prepared August-October 2024 and updated March 10, 2025. "
            "Select the state's cohort-component population illustration. Housing stock targets and regional household allocations are separate quantities. The chart explicitly publishes population for 2030, 2040 and 2050 by 18 exhaustive age groups, from under 5 through 85 years and over. "
            "Normalize each state age column by summing its 18 published integer labels: 666640, 667903 and 644731 persons. All 54 labels were visually checked on the rendered original and embedded image, and independently matched by local Apple Vision OCR. VHFA's producer PDF contains identical decoded chart pixels. "
            "The original PDF, structured 54-cell extract, exact source and chart fingerprints, and extraction recipe are archived. Rebuilding validates those without an OCR dependency. No county or housing-target region is combined into population. "
            "The model assumes 0.49% annual net migration based on 2020-2023 experience and 2019 vital statistics, using age-specific Vermont births and deaths and Census migration estimates. The last underlying population estimate and launch date are unstated; base_year is null and no launch row is fabricated. "
            "The server scenario key current_trends describes the chart's if-current-trends-continue caption. It is the sole selected state population series; upper and lower housing-target labels are not population scenarios. "
            "Every served point is a projection. The exact future reference day is unstated, and years between 2030, 2040 and 2050 are not interpolated. "
            "The newer appendix has no complete 14-county population grid. County A/B series retain their separate August 2013 edition, base 2010 and horizon 2030. They do not form a consistent statewide/county vintage with this product. "
            "Housing targets include vacancy normalization, replacement and seasonal homes, and homelessness. They are not household-count forecasts and are not served as households. Other variables remain unverified."))

    insert_observations(conn, rows)
    conn.commit()
    print(f"VT load: {len(rows)} observations")


def verify(conn) -> None:
    rows = [dict(r) for r in conn.execute("SELECT * FROM observations WHERE state='VT'")]
    county_rows = [r for r in rows if r["geo_level"] == "county"]
    state_rows = [r for r in rows if r["geo_level"] == "state"]
    ids = set(_geographies().values()) - {"50"}
    assert len(rows) == 87 and {(r["geo_id"], r["scenario"], r["year"]) for r in county_rows} == {(gid, scenario, year) for gid in ids for scenario in SCENARIOS for year in YEARS}
    assert all(r["datatype"] == ("estimate" if r["year"] == 2010 else "projection") and r["source_id"] == SOURCE_ID
               and r["variable"] == "population" and r["age_group"] == r["sex"] == r["race"] == "all"
               and r["value"] >= 0 and float(r["value"]).is_integer() for r in county_rows)
    original = parse((RAW_DIR / FILE).read_bytes())
    assert {(r["geo_id"], r["scenario"], r["year"]): r["value"] for r in county_rows} == {(r["geo_id"], r["scenario"], r["year"]): r["value"] for r in original}
    assert len(state_rows) == 3 and {(r["geo_id"], r["scenario"], r["year"]): r["value"] for r in state_rows} == {("50", "current_trends", year): value for year, value in zip(STATE_YEARS, STATE_TOTALS, strict=True)}
    assert all(r["datatype"] == "projection" and r["source_id"] == STATE_SOURCE_ID for r in state_rows)
    for source_id, base, horizon, vintage in ((SOURCE_ID, 2010, 2030, VINTAGE), (STATE_SOURCE_ID, None, 2050, STATE_VINTAGE)):
        source = conn.execute("SELECT * FROM sources WHERE source_id=?", (source_id,)).fetchone()
        assert source["base_year"] == base and source["horizon_year"] == horizon and source["vintage"] == vintage
    print("VT verify: adopted2025state/archived2013all14counties, separate grids/scenarios, checked rasterage sums ok")


if __name__ == "__main__":
    if "--acquire" in sys.argv:
        acquire()
    else:
        print("usage: python -m sdo_mcp.ingest.vt --acquire")
