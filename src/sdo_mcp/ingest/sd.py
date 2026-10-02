"""SDSU's preliminary 2012 medium population projections, source-era counties.

The original workbook survives at its migrated university URL. Census 2010
counts independently check every base total; DLR repeats rounded state totals.
"""
from __future__ import annotations

import csv
import io
import math
import re
import sys
import zipfile
from datetime import date

from ..common import fetch
from ..store import REPO_ROOT, insert_observations, upsert_source

RAW_DIR = REPO_ROOT / "data" / "raw" / "sd"
URL = "https://www.sdstate.edu/sites/default/files/soc/rlcdc/generaldemographicdata/upload/Projections-with-Pyramids2.xlsx"
CATALOG_URL = "https://dlr.sd.gov/lmic/menu_population.aspx"
FILE = "population_2010-2035_preliminary2012.xlsx"
GEO_FILE = "census_counties_2010.zip"
FILES = {
    FILE: URL,
    GEO_FILE: "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/Gaz_counties_national.zip",
    "projection_catalog_archived2015.html": "https://web.archive.org/web/20150501000000id_/http://www.sdstate.edu/soc/rlcdc/generaldemographicdata/age-and-sex-structure.cfm",
    "projection_referral_2026-10-02.html": CATALOG_URL,
    "projection_referral_archived2018.html": "https://web.archive.org/web/20180101000000id_/https://dlr.sd.gov/lmic/menu_population.aspx",
    "projection_methods_2013.pdf": "https://web.archive.org/web/20210101000000id_/https://openprairie.sdstate.edu/cgi/viewcontent.cgi?article=1000&context=sd_demography_conference",
    "projection_methods_catalog_2026-10-02.html": "https://openprairie.sdstate.edu/sd_demography_conference/2013/presentations/1/",
    "county_name_change_2015.pdf": "https://www.weather.gov/media/notification/pdfs/scn15-31shannon_oglalacty_cca.pdf",
    "workforce_report_2020.pdf": "https://dlr.sd.gov/lmic/publications/labor_market_reports/workforce_report_2020.pdf",
}
SOURCE_ID = "sd-pop-preliminary2012-medium"
AGENCY = "South Dakota State Data Center / State Demographer, South Dakota State University"
VINTAGE = "2012 (preliminary)"
YEARS = (2010, 2015, 2020, 2025, 2030, 2035)
AGES = tuple(f"{age}-{age + 4}" for age in range(0, 85, 5)) + ("85+",)
STATE_ROUNDED = (814180, 852624, 889447, 922748, 951885, 977574)
COUNTY_STATE_DIFFERENCES = (0, -3354.8833976779133, -6613.721976290573,
                           -8547.856665975647, -9002.786699847784, -8185.921664994676)


def parse_geographies(body: bytes) -> dict[str, tuple[str, str, int]]:
    """Read the unchanged national Census 2010 Gazetteer, including Shannon."""
    try:
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            if archive.namelist() != ["Gaz_counties_national.txt"]:
                raise ValueError("SD: unexpected Census geography archive")
            text = archive.read(archive.namelist()[0]).decode("latin-1")
        reader = csv.DictReader(io.StringIO(text), delimiter="\t")
        if reader.fieldnames is None or not {"USPS", "GEOID", "NAME", "POP10"} <= set(reader.fieldnames):
            raise ValueError("SD: invalid Census geography header")
        result = {}
        ids = set()
        for row in reader:
            if row["USPS"] != "SD":
                continue
            gid, name, count = row["GEOID"].strip(), row["NAME"].strip(), row["POP10"].strip()
            short = name.removesuffix(" County")
            if (not re.fullmatch(r"46\d{3}", gid) or name == short or short in result
                    or gid in ids or not re.fullmatch(r"[1-9]\d*", count)):
                raise ValueError("SD: invalid or duplicate Census county")
            result[short] = (gid, name, int(count))
            ids.add(gid)
        if (len(result) != 66 or result.get("Shannon") != ("46113", "Shannon County", 13586)
                or "46102" in ids or sum(row[2] for row in result.values()) != STATE_ROUNDED[0]):
            raise ValueError("SD: incomplete or changed source-era county roster")
        return result
    except (zipfile.BadZipFile, UnicodeError, csv.Error, KeyError, TypeError) as exc:
        raise ValueError("SD: unreadable Census geography archive") from exc


def _number(value) -> float | int:
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value < 0):
        raise ValueError("SD: population must be a finite nonnegative number")
    return value


def parse(body: bytes, geographies: dict[str, tuple[str, str, int]]) -> list[dict]:
    from openpyxl import load_workbook
    try:
        workbook = load_workbook(io.BytesIO(body), read_only=True, data_only=True)
    except Exception as exc:
        raise ValueError("SD: response is not a readable population workbook") from exc
    try:
        if len(workbook.sheetnames) != 67 or set(workbook.sheetnames) != set(geographies) | {"So Dak Proj"}:
            raise ValueError("SD: incomplete or unknown workbook geography grid")
        rows = []
        for name in workbook.sheetnames:
            sheet = workbook[name]
            # Cache only the actual A:G source table; chart/ratio cells are not
            # additional forecast years or scenarios.
            cells = list(sheet.iter_rows(min_row=1, max_row=66, max_col=7, values_only=True))
            label = "South Dakota" if name == "So Dak Proj" else name + " County"
            gid = "46" if name == "So Dak Proj" else geographies[name][0]
            groups = []
            for title_row, header_row, start_row, total_row, sex in (
                    (1, 2, 3, 21, "Male"), (23, 24, 25, 43, "Female"), (46, 47, 48, 66, "Total")):
                title = f"{sex} Population Projections -- Medium Series -- {label}"
                if name == "Tripp" and sex == "Total":
                    title = "Total Population Projections -- Medium Series --Tripp County"
                if (cells[title_row - 1][0] != title
                        or cells[header_row - 1] != ("Age", *YEARS)
                        or cells[total_row - 1][0] != "Total"):
                    raise ValueError("SD: unexpected title, scenario, year grid or total row")
                data = cells[start_row - 1:total_row - 1]
                if tuple(row[0] for row in data) != AGES:
                    raise ValueError("SD: incomplete or changed age grid")
                values = [tuple(_number(value) for value in row[1:]) for row in data]
                totals = tuple(_number(value) for value in cells[total_row - 1][1:])
                for col, total in enumerate(totals):
                    if not math.isclose(sum(row[col] for row in values), total, rel_tol=0, abs_tol=1e-7):
                        raise ValueError("SD: age values and published total disagree")
                groups.append((values, totals))
            for col in range(6):
                if not math.isclose(groups[0][1][col] + groups[1][1][col], groups[2][1][col], rel_tol=0, abs_tol=1e-7):
                    raise ValueError("SD: sex totals disagree")
                if any(not math.isclose(groups[0][0][i][col] + groups[1][0][i][col], groups[2][0][i][col],
                                        rel_tol=0, abs_tol=1e-7) for i in range(18)):
                    raise ValueError("SD: age/sex cells disagree")
            total = groups[2][1]
            base = STATE_ROUNDED[0] if gid == "46" else geographies[name][2]
            if total[0] != base:
                raise ValueError("SD: 2010 base differs from independent Census count")
            rows.extend(dict(state="SD", geo_level="state" if gid == "46" else "county", geo_id=gid,
                             year=year, variable="population", value=value, scenario="medium",
                             datatype="estimate" if year == 2010 else "projection", source_id=SOURCE_ID)
                        for year, value in zip(YEARS, total, strict=True))
        state_values = [r["value"] for r in rows if r["geo_id"] == "46"]
        if tuple(round(value) for value in state_values) != STATE_ROUNDED:
            raise ValueError("SD: state totals differ from independent DLR reprint")
        for year, state, difference in zip(YEARS, state_values, COUNTY_STATE_DIFFERENCES, strict=True):
            county = sum(r["value"] for r in rows if r["geo_level"] == "county" and r["year"] == year)
            if not math.isclose(county - state, difference, rel_tol=0, abs_tol=1e-7):
                raise ValueError("SD: county/state difference changed")
        return rows
    finally:
        workbook.close()


def _pdf_text(body: bytes, label: str) -> list[str]:
    from pypdf import PdfReader
    fetch.validate_pdf(body, label)
    return [" ".join((page.extract_text() or "").split()) for page in PdfReader(io.BytesIO(body)).pages]


def _html(body: bytes, markers: tuple[str, ...], label: str) -> None:
    text = " ".join(body.decode("utf-8", "replace").split())
    if "<html" not in text.lower() or any(marker not in text for marker in markers):
        raise ValueError(f"SD: invalid {label} evidence")


def _validate_all(bodies: dict[str, bytes]) -> tuple[list[dict], dict]:
    geographies = parse_geographies(bodies[GEO_FILE])
    rows = parse(bodies[FILE], geographies)
    _html(bodies["projection_catalog_archived2015.html"],
          ("Preliminary Populations Projections 2010-2035", "Projections-with-Pyramids2.xlsx", "all of its counties"), "archived catalog")
    _html(bodies["projection_referral_2026-10-02.html"], ("population projections", "all of its counties", "contracts", "Census Data Center"), "current referral")
    _html(bodies["projection_referral_archived2018.html"], ("Preliminary population projections", "jointly funded", "South Dakota State University"), "archived referral")
    _html(bodies["projection_methods_catalog_2026-10-02.html"], ("Our Largest Project in 2012", "McCurry", "2013"), "methods catalog")
    methods = _pdf_text(bodies["projection_methods_2013.pdf"], "SD methods")
    if (len(methods) != 33 or "South Dakota State Demographer" not in methods[0]
            or "Our Largest Project in 2012" not in methods[0]
            or "trends and population that existed on April 1, 2010" not in methods[2]
            or "can be downloaded" not in methods[32]):
        raise ValueError("SD: unexpected producer, edition or 2010 model base")
    change = " ".join(_pdf_text(bodies["county_name_change_2015.pdf"], "SD county change"))
    if any(marker not in change for marker in ("Shannon", "Oglala Lakota", "46113", "46102", "boundaries will not change")):
        raise ValueError("SD: unexpected county name/code change evidence")
    report = _pdf_text(bodies["workforce_report_2020.pdf"], "SD independent state totals")
    if len(report) <= 54 or "Total 814,180 852,624 889,447 922,748 951,885 977,574" not in report[54]:
        raise ValueError("SD: unexpected independent rounded state totals")
    return rows, geographies


def acquire() -> None:
    if (RAW_DIR / "manifest.json").exists():
        entries = fetch.read_manifest(RAW_DIR)
        if {e["file"] for e in entries} != set(FILES):
            raise ValueError("SD: incomplete saved manifest")
        _validate_all({name: (RAW_DIR / name).read_bytes() for name in FILES})
        print("SD acquire: reused validated preliminary 2012 snapshots")
        return
    bodies = {name: fetch.get_bytes(url) for name, url in FILES.items()}
    rows, _ = _validate_all(bodies)
    entries = []
    for name, url in FILES.items():
        fetch.write_snapshot(RAW_DIR / name, bodies[name])
        entries.append(dict(file=name, source=url, retrieved_at=date.today().isoformat(), sha256=fetch.sha256(bodies[name]),
                            records=len(rows) if name == FILE else None,
                            note="Unchanged original source or essential producer/base/geography/independent-value evidence. Archived URLs retain original publisher bytes; archive request dates are selectors, not publication vintages."))
    fetch.write_manifest(RAW_DIR, entries)


def load(conn) -> None:
    entries = {e["file"]: e for e in fetch.read_manifest(RAW_DIR)}
    if set(entries) != set(FILES):
        raise ValueError("SD: incomplete saved manifest")
    rows, geographies = _validate_all({name: (RAW_DIR / name).read_bytes() for name in FILES})
    expected = {gid: name for gid, name, _ in geographies.values()}
    seeded = {r["geo_id"]: r["name"] for r in conn.execute("SELECT * FROM geographies WHERE state='SD' AND geo_level='county'")}
    current = {**expected}
    current.pop("46113")
    current["46102"] = "Oglala Lakota County"
    if seeded not in (expected, current):
        raise ValueError("SD: seeded counties differ from exact source or current roster")
    if seeded == current:
        if conn.execute("SELECT 1 FROM observations WHERE state='SD' AND geo_id='46102'").fetchone():
            raise ValueError("SD: cannot replace an already loaded modern county geography")
        conn.execute("DELETE FROM geographies WHERE state='SD' AND geo_level='county' AND geo_id='46102'")
        conn.execute("INSERT INTO geographies VALUES ('46113','county','SD','Shannon County')")
    if not conn.execute("SELECT 1 FROM geographies WHERE state='SD' AND geo_level='state' AND geo_id='46'").fetchone():
        raise ValueError("SD: state geography is not seeded")
    upsert_source(conn, source_id=SOURCE_ID, state="SD", agency=AGENCY,
        product_name="Preliminary Population Projections 2010-2035: state and all 66 source-era counties, Medium Series",
        vintage=VINTAGE, base_year=2010, horizon_year=2035, source_url=URL,
        retrieved_at=entries[FILE]["retrieved_at"],
        license="No explicit data license identified; cite the South Dakota State Data Center, South Dakota State University.",
        citation="South Dakota State Data Center / State Demographer, SDSU. Preliminary Population Projections 2010-2035 (2012), Projections-with-Pyramids2.xlsx, Total Population / Total row 66, Medium Series.",
        method_notes=("This original 2012 preliminary workbook publishes the state and all 66 counties at six five-year points in persons. "
            "The State Demographer's May 2013 presentation explicitly identifies April 1, 2010 trends/population as the model base, with no later estimate calibration established. "
            "Every county 2010 total matches the independent Census 2010 Gazetteer; 2010 Census counts use this schema's estimate label and 2015-2035 remain projections. "
            "The source labels the selected scenario Medium Series. Original cached Excel numeric precision is preserved, including fractional persons displayed rounded in Excel. "
            "The DLR 2020 workforce report independently repeats all rounded statewide totals; its age 16-64 workforce discussion is not an employment forecast. "
            "County forecasts are not constrained to the separately published state forecast; sums differ by up to about 9,003 persons, and no balancing is applied. "
            "Shannon County uses source-era FIPS 46113. Its 2015 rename to Oglala Lakota / 46102 did not change boundaries, but no values or aliases are substituted under the modern code. "
            "The current national Census 2020 snapshot remains unchanged. DLR's archived page describes joint SDSU/LMIC funding, and the methods author is the South Dakota State Demographer. "
            "No newer statewide/all-county eligible projection release was established; household counts, complete components, subcounty forecasts and eligible SDO jobs coverage remain unverified."))
    insert_observations(conn, rows)
    conn.commit()
    print(f"SD load: {len(rows)} observations")


# Decimal anchors checked directly in original worksheet XML, with independent
# Census base counts and the DLR rounded-state table, not generated by parse().
FIXTURES = (("46", 2010, 814180), ("46", 2025, 922747.8576791115), ("46", 2035, 977573.6733717498),
            ("46099", 2010, 169468), ("46099", 2035, 212353.3156841234),
            ("46075", 2010, 1006), ("46075", 2035, 651.1085612215595),
            ("46113", 2010, 13586), ("46113", 2035, 19755.46602925523))


def verify(conn) -> None:
    geographies = parse_geographies((RAW_DIR / GEO_FILE).read_bytes())
    gids = {row[0] for row in geographies.values()} | {"46"}
    rows = conn.execute("SELECT * FROM observations WHERE state='SD'").fetchall()
    assert len(rows) == 402 and {(r["geo_id"], r["year"], r["scenario"]) for r in rows} == {(gid, year, "medium") for gid in gids for year in YEARS}
    assert all(r["datatype"] == ("estimate" if r["year"] == 2010 else "projection")
               and r["source_id"] == SOURCE_ID and r["variable"] == "population"
               and r["geo_level"] == ("state" if r["geo_id"] == "46" else "county")
               and r["age_group"] == r["sex"] == r["race"] == "all"
               and math.isfinite(r["value"]) and r["value"] >= 0 for r in rows)
    actual_geo = {r["geo_id"]: r["name"] for r in conn.execute("SELECT * FROM geographies WHERE state='SD' AND geo_level='county'")}
    assert actual_geo == {gid: name for gid, name, _ in geographies.values()}
    source = conn.execute("SELECT * FROM sources WHERE source_id=?", (SOURCE_ID,)).fetchone()
    assert source["base_year"] == 2010 and source["horizon_year"] == 2035 and source["vintage"] == VINTAGE
    values = {(r["geo_id"], r["year"]): r["value"] for r in rows}
    for gid, year, value in FIXTURES:
        assert values[gid, year] == value
    for gid, _, base in geographies.values():
        assert values[gid, 2010] == base
    for year, difference in zip(YEARS, COUNTY_STATE_DIFFERENCES, strict=True):
        assert math.isclose(sum(values[gid, year] for gid in gids if gid != "46") - values["46", year], difference, rel_tol=0, abs_tol=1e-7)
    print("SD verify: 402 complete medium totals, Census base, source-era counties and independent values ok")


if __name__ == "__main__":
    if "--acquire" in sys.argv:
        acquire()
    else:
        print("usage: python -m sdo_mcp.ingest.sd --acquire")
