"""Connecticut State Data Center's revised 2017/2018 resident projections."""

from __future__ import annotations

import csv
import io
import json
import re
import sys
from datetime import date

from ..common import fetch
from ..store import REPO_ROOT, insert_observations, upsert_source

RAW_DIR = REPO_ROOT / "data" / "raw" / "ct"
URL = "https://data.ct.gov/api/views/pv2w-k7qu/rows.csv?accessType=DOWNLOAD"
META_URL = "https://data.ct.gov/api/views/pv2w-k7qu.json"
METHOD_URL = "https://portal.ct.gov/-/media/Departments-and-Agencies/DSS/Health-and-Home-Care/Medicaid-Long-Term-Care-Demand-Projections/Main-report--CT-LTC-Demand-Report-Narrative.pdf"
FILES = {
    "population_2015-2040_revised2017-2018.csv": URL,
    "dataset_metadata_2026-10-01.json": META_URL,
    "revised_release_2017.html": "https://blogs.lib.uconn.edu/outsidetheneatline/2017/07/30/connecticuts-population-is-expected-to-grow-slowly-connecticut-state-data-center-reports/",
    "adopted_population_methods_2019.pdf": METHOD_URL,
    "geography_guidance_2026-10-01.html": "https://portal.ct.gov/dph/resources-and-records/data-research/vital-statistics-and-population-data/population-statistics",
}
DATA_FILE = next(iter(FILES))
AGENCY = "Connecticut State Data Center, University of Connecticut"
YEARS = (2015, 2020, 2025, 2030, 2035, 2040)
AGES = tuple(f"{a}_{a + 4}" for a in range(0, 85, 5)) + ("85+", "Total")
COUNTIES = dict(zip(("Fairfield", "Hartford", "Litchfield", "Middlesex", "New Haven", "New London", "Tolland", "Windham"),
                    (f"09{n:03d}" for n in range(1, 16, 2)), strict=True))
COGS = {
    "Capitol Region": ("ct-cog-capitol-region", "Capitol Region"),
    "Metropolitian": ("ct-cog-metropolitan", "Metropolitan"),
    "Lower CT River Valley": ("ct-cog-lower-ct-river-valley", "Lower CT River Valley"),
    "Naugatuck Valley": ("ct-cog-naugatuck-valley", "Naugatuck Valley"),
    "Northeastern CT": ("ct-cog-northeastern-ct", "Northeastern CT"),
    "Northwest Hills": ("ct-cog-northwest-hills", "Northwest Hills"),
    "South Central": ("ct-cog-south-central", "South Central"),
    "Southeastern CT": ("ct-cog-southeastern-ct", "Southeastern CT"),
    "Western CT": ("ct-cog-western-ct", "Western CT"),
}
ROSTER = {("State", "Connecticut"): ("state", "09")}
ROSTER.update({("County", name): ("county", gid) for name, gid in COUNTIES.items()})
ROSTER.update({("Regional Council of Government", name): ("cog", gid) for name, (gid, _) in COGS.items()})
SOURCE_IDS = {"state": "ct-pop-state-2017", "county": "ct-pop-county-2018", "cog": "ct-pop-cog-2018"}
COUNTY_DIFFERENCES = (0, -4, 2, -1, -11, 6)
COG_DIFFERENCES = (-1, 2, 2, 7, -5, -8)


def parse(body: bytes) -> list[dict]:
    try:
        reader = csv.DictReader(io.StringIO(body.decode("utf-8-sig")))
        if reader.fieldnames != ["Year", "Geography_Type", "Geography", "Age_Group", "Male", "Female", "Total"]:
            raise ValueError("unexpected CSV header")
        cells = {}
        for row in reader:
            if None in row or any(v is None for v in row.values()):
                raise ValueError("malformed CSV row")
            geo = (row["Geography_Type"], row["Geography"])
            if geo not in ROSTER:
                raise ValueError(f"unknown geography {geo}")
            if row["Year"] not in {str(y) for y in YEARS} or row["Age_Group"] not in AGES:
                raise ValueError("unexpected year or age group")
            key = (geo, int(row["Year"]), row["Age_Group"])
            if key in cells:
                raise ValueError("duplicate geography/year/age")
            values = []
            for field in ("Male", "Female", "Total"):
                if not re.fullmatch(r"[0-9]+", row[field]):
                    raise ValueError(f"invalid integer {field}")
                values.append(int(row[field]))
            if abs(values[2] - values[0] - values[1]) > 1:
                raise ValueError("sex totals differ beyond rounding")
            cells[key] = values
    except (UnicodeError, csv.Error) as exc:
        raise ValueError("CT: response is not readable CSV") from exc
    expected = {(geo, y, age) for geo in ROSTER for y in YEARS for age in AGES}
    if cells.keys() != expected:
        raise ValueError("CT: incomplete geography/year/age grid")
    rows = []
    for geo, (level, gid) in ROSTER.items():
        for year in YEARS:
            values = cells[geo, year, "Total"]
            for index in range(3):
                summed = sum(cells[geo, year, age][index] for age in AGES[:-1])
                # County/COG totals sum the integer cells exactly. The state
                # publishes independently rounded totals, up to three apart.
                tolerance = 3 if level == "state" else 0
                if abs(summed - values[index]) > tolerance:
                    raise ValueError("CT: age totals differ beyond rounding")
            rows.append(dict(state="CT", geo_level=level, geo_id=gid, year=year,
                             variable="population", value=values[2], datatype="projection",
                             source_id=SOURCE_IDS[level]))
    values = {(r["geo_id"], r["year"]): r["value"] for r in rows}
    for level, differences in (("county", COUNTY_DIFFERENCES), ("cog", COG_DIFFERENCES)):
        for year, difference in zip(YEARS, differences, strict=True):
            if sum(r["value"] for r in rows if r["geo_level"] == level and r["year"] == year) - values["09", year] != difference:
                raise ValueError(f"CT: {level}/state difference changed")
    return rows


def _validate_evidence(name: str, body: bytes) -> None:
    if name.endswith(".json"):
        try:
            meta = json.loads(body)
            description = meta["description"]
            if (meta["id"] != "pv2w-k7qu" or meta["attribution"] != "Connecticut State Data Center"
                    or meta["licenseId"] != "CC_30_BY_SA"
                    or "September 19, 2017" not in description or "June 29, 2018" not in description):
                raise ValueError("edition or producer changed")
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError("CT: invalid dataset metadata") from exc
    elif name.endswith(".pdf"):
        from pypdf import PdfReader
        fetch.validate_pdf(body, "CT methods")
        text = " ".join((PdfReader(io.BytesIO(body)).pages[10].extract_text() or "").split())
        if "Data from the 2010 Census is the starting point" not in text or "2015, 2020, 2025, 2030" not in text:
            raise ValueError("CT: methods base or projection boundary missing")
    else:
        page = " ".join(body.decode("utf-8", "replace").lower().split())
        markers = (("<html", "revised september 19, 2017", "3.65 million") if name.startswith("revised")
                   else ("<html", "nine planning regions", "eight historical counties"))
        if not all(m in page for m in markers):
            raise ValueError("CT: invalid publisher evidence")


def _validate(bodies: dict[str, bytes]) -> list[dict]:
    rows = parse(bodies[DATA_FILE])
    for name in FILES:
        if name != DATA_FILE:
            _validate_evidence(name, bodies[name])
    return rows


def acquire() -> None:
    if (RAW_DIR / "manifest.json").exists():
        entries = fetch.read_manifest(RAW_DIR)
        if {e["file"] for e in entries} != set(FILES):
            raise ValueError("CT: incomplete snapshot manifest")
        _validate({name: (RAW_DIR / name).read_bytes() for name in FILES})
        print("CT acquire: reused validated snapshots")
        return
    bodies = {name: fetch.get_bytes(url) for name, url in FILES.items()}
    _validate(bodies)
    entries = []
    for name, body in bodies.items():
        fetch.write_snapshot(RAW_DIR / name, body)
        entries.append(dict(file=name, source=FILES[name], retrieved_at=date.today().isoformat(),
                            sha256=fetch.sha256(body), records=2052 if name == DATA_FILE else None))
    fetch.write_manifest(RAW_DIR, entries)


def load(conn) -> None:
    entries = {e["file"]: e for e in fetch.read_manifest(RAW_DIR)}
    rows = _validate({name: (RAW_DIR / name).read_bytes() for name in FILES})
    expected = set(COUNTIES.values())
    seeded = {r[0] for r in conn.execute("SELECT geo_id FROM geographies WHERE state='CT' AND geo_level='county'")}
    if seeded != expected:
        raise ValueError("CT: seed must preserve the eight historical counties")
    conn.executemany("INSERT INTO geographies (geo_id,geo_level,state,name) VALUES (?,'cog','CT',?)",
                     [(gid, name) for gid, name in COGS.values()])
    for level, sid in SOURCE_IDS.items():
        vintage = "September 19, 2017 (revised)" if level == "state" else "June 29, 2018 (2017 model)"
        upsert_source(conn, source_id=sid, state="CT", agency=AGENCY,
            product_name=f"Resident population projections 2015-2040: {level} totals",
            vintage=vintage, base_year=2010, horizon_year=2040, source_url=URL,
            retrieved_at=entries[DATA_FILE]["retrieved_at"], license="CC BY-SA 3.0",
            citation=f"Connecticut State Data Center. Population Projections 2015-2040. {vintage}. Connecticut open-data dataset pv2w-k7qu.",
            method_notes=("Annual-average resident population at exact five-year points; all 2015-2040 rows are projections, including years now in the past. "
                "Connecticut DSS's 2019 adopted report, printed page 9, reproduces the State Data Center methods and identifies the 2010 Census starting point. "
                "base_year=2010 records that historical anchor; no estimate rows are served. The old UConn methods URL now redirects to the CTData homepage. "
                "The dataset's 2023 metadata change is not a new model vintage. Eight historical counties retain their Census 2020 FIPS. "
                "The nine 2018 regional councils of government use separate prefixed IDs and geo_level=cog; they are not mapped to modern county-equivalent planning regions. "
                "Publisher typo Metropolitian is displayed as Metropolitan. Independently rounded state, county and COG totals can differ by up to 11 persons; values are preserved. "
                "Age/sex detail is archived but not served. Town products are deferred. Household and eligible SDO jobs publication coverage remains unverified."))
    insert_observations(conn, rows)
    conn.commit()
    print(f"CT load: {len(rows)} observations")


FIXTURES = (("09", 2015, 3593301), ("09", 2040, 3654015), ("09001", 2040, 905219),
            ("09013", 2040, 154560), ("09015", 2040, 134876), ("ct-cog-southeastern-ct", 2040, 303785))


def verify(conn) -> None:
    rows = conn.execute("SELECT * FROM observations WHERE state='CT'").fetchall()
    expected = {(level, gid, y) for level, gid in ROSTER.values() for y in YEARS}
    assert len(rows) == 108 and {(r["geo_level"], r["geo_id"], r["year"]) for r in rows} == expected
    assert all(r["datatype"] == "projection" and r["source_id"] == SOURCE_IDS[r["geo_level"]]
               and r["variable"] == "population" and r["scenario"] == ""
               and r["age_group"] == r["sex"] == r["race"] == "all" for r in rows)
    values = {(r["geo_id"], r["year"]): r["value"] for r in rows}
    for gid, year, value in FIXTURES:
        assert values[gid, year] == value
    print("CT verify: historical county/COG grids and fixtures ok")


if __name__ == "__main__":
    if "--acquire" in sys.argv:
        acquire()
    else:
        print("usage: python -m sdo_mcp.ingest.ct --acquire")
