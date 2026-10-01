"""Rhode Island's February 2026 state and city/town population table."""

from __future__ import annotations

import csv
import io
import re
import sys
from datetime import date

from ..common import fetch
from ..store import REPO_ROOT, insert_observations, upsert_source

RAW_DIR = REPO_ROOT / "data" / "raw" / "ri"
URL = "https://planning.ri.gov/sites/g/files/xkgbur826/files/2026-02/Municipal%20Projections%20%2002272026.pdf"
GEO_URL = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer/2025_gaz_cousubs_44.txt"
FILES = {
    "municipal_population_revised2026-02-27.pdf": URL,
    "projection_catalog_2026-10-01.html": "https://planning.ri.gov/",
    "census_cousubs_2025.txt": GEO_URL,
    "planning_work_program_fy2026.pdf": "https://planning.ri.gov/sites/g/files/xkgbur826/files/2025-09/FY26_UPWP_FINAL_06.12.2025%20%285%29.pdf",
}
FILE = next(iter(FILES))
SOURCE_ID = "ri-pop-2026"
AGENCY = "Rhode Island Division of Statewide Planning, Department of Administration"
YEARS = (2025, 2030, 2035, 2040, 2045, 2050)
NAMES = ("Barrington", "Bristol", "Burrillville", "Central Falls", "Charlestown", "Coventry", "Cranston", "Cumberland",
         "East Greenwich", "East Providence", "Exeter", "Foster", "Glocester", "Hopkinton", "Jamestown", "Johnston",
         "Lincoln", "Little Compton", "Middletown", "Narragansett", "New Shoreham", "Newport", "North Kingstown",
         "North Providence", "North Smithfield", "Pawtucket", "Portsmouth", "Providence", "Richmond", "Scituate",
         "Smithfield", "South Kingstown", "Tiverton", "Warren", "Warwick", "West Greenwich", "West Warwick",
         "Westerly", "Woonsocket")
ALIASES = {"E. Greenwich": "East Greenwich", "E. Providence": "East Providence", "No. Kingstown": "North Kingstown",
           "No. Providence": "North Providence", "No. Smithfield": "North Smithfield", "So. Kingstown": "South Kingstown"}
STATE_VALUES = (1104675, 1104638, 1111770, 1119181, 1127525, 1134854)
MUNICIPAL_DIFFERENCES = (-2, -3, -2, 1, 1, -3)


def parse_geographies(body: bytes) -> dict[str, tuple[str, str]]:
    try:
        reader = csv.DictReader(io.StringIO(body.decode("utf-8-sig")), delimiter="|")
        if reader.fieldnames is None or not {"USPS", "GEOID", "GEOIDFQ", "NAME", "FUNCSTAT"} <= set(reader.fieldnames):
            raise ValueError("RI: invalid geography header")
        result = {}
        ids = set()
        undefined_seen = False
        for row in reader:
            gid, name = row["GEOID"], row["NAME"]
            # The reference also includes Newport County's unassigned water
            # area. It is not a municipality and has no population forecast.
            if name == "County subdivisions not defined":
                if (undefined_seen or gid != "4400500000" or row["USPS"] != "RI"
                        or row["GEOIDFQ"] != "0600000US4400500000" or row["ALAND"] != "0"):
                    raise ValueError("RI: unexpected undefined subdivision")
                undefined_seen = True
                continue
            short = re.sub(r" (town|city)$", "", name)
            if (row["USPS"] != "RI" or not re.fullmatch(r"44(?:001|003|005|007|009)[0-9]{5}", gid)
                    or row["GEOIDFQ"] != "0600000US" + gid
                    or row["FUNCSTAT"] != ("F" if name.endswith(" city") else "A")
                    or short not in NAMES or name == short or short in result or gid in ids):
                raise ValueError("RI: invalid or duplicate county subdivision")
            result[short] = (gid, name)
            ids.add(gid)
        if set(result) != set(NAMES) or not undefined_seen:
            raise ValueError("RI: incomplete municipality geography roster")
        return result
    except (UnicodeError, csv.Error, TypeError, KeyError) as exc:
        raise ValueError("RI: unreadable geography reference") from exc


def parse_table(text: str, geographies: dict[str, tuple[str, str]]) -> list[dict]:
    if ("City/Town 2025 2030 2035 2040 2045 2050" not in " ".join(text.split())
            or "Population Projections" not in text or "Revised 2/27/26" not in text
            or "Projections are subject to future revision" not in text):
        raise ValueError("RI: unexpected table header, edition or caveat")
    totals = {}
    for line in text.splitlines():
        line = line.strip()
        if (not line or line.startswith(("City/Town", "Population Projections", "Revised", "Projections are"))):
            continue
        fields = re.fullmatch(r"(.+?)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)", line)
        if not fields:
            raise ValueError("RI: malformed table row")
        name = ALIASES.get(fields[1], fields[1])
        if name not in geographies and name != "Total":
            raise ValueError(f"RI: unknown municipality {name!r}")
        if name in totals:
            raise ValueError("RI: duplicate municipality")
        values = []
        for token in fields.groups()[1:]:
            if not re.fullmatch(r"(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)", token):
                raise ValueError("RI: invalid population integer")
            values.append(int(token.replace(",", "")))
        totals[name] = tuple(values)
    if set(totals) != set(NAMES) | {"Total"}:
        raise ValueError("RI: incomplete municipality/year grid")
    if totals["Total"] != STATE_VALUES:
        raise ValueError("RI: published state totals changed")
    for index, difference in enumerate(MUNICIPAL_DIFFERENCES):
        if sum(values[index] for name, values in totals.items() if name != "Total") - totals["Total"][index] != difference:
            raise ValueError("RI: municipality/state rounding difference changed")
    rows = []
    for name, values in totals.items():
        level, gid = ("state", "44") if name == "Total" else ("county_subdivision", geographies[name][0])
        rows.extend(dict(state="RI", geo_level=level, geo_id=gid, year=year, variable="population",
                         value=value, datatype="projection", source_id=SOURCE_ID)
                    for year, value in zip(YEARS, values, strict=True))
    return rows


def parse(body: bytes, geographies: dict[str, tuple[str, str]]) -> list[dict]:
    from pypdf import PdfReader
    try:
        reader = PdfReader(io.BytesIO(body))
        if len(reader.pages) != 1:
            raise ValueError("unexpected page count")
        text = reader.pages[0].extract_text() or ""
    except Exception as exc:
        raise ValueError("RI: response is not the readable one-page population PDF") from exc
    return parse_table(text, geographies)


def _validate(bodies: dict[str, bytes]) -> tuple[list[dict], dict]:
    geographies = parse_geographies(bodies["census_cousubs_2025.txt"])
    rows = parse(bodies[FILE], geographies)
    page = bodies["projection_catalog_2026-10-01.html"].decode("utf-8", "replace")
    if "<html" not in page or "Municipal%20Projections%20%2002272026.pdf" not in page or "Population Projections 2025-2050" not in page:
        raise ValueError("RI: invalid current publisher catalog")
    program = bodies["planning_work_program_fy2026.pdf"]
    fetch.validate_pdf(program, "RI planning work program")
    from pypdf import PdfReader
    text = " ".join((PdfReader(io.BytesIO(program)).pages[22].extract_text() or "").split())
    if "Project Agency Lead: RIDSP" not in text or "all 39 cities and towns" not in text or "cohort" not in text:
        raise ValueError("RI: invalid producer/method evidence")
    return rows, geographies


def acquire() -> None:
    if (RAW_DIR / "manifest.json").exists():
        entries = fetch.read_manifest(RAW_DIR)
        if {e["file"] for e in entries} != set(FILES):
            raise ValueError("RI: incomplete snapshot manifest")
        _validate({name: (RAW_DIR / name).read_bytes() for name in FILES})
        print("RI acquire: reused validated snapshots")
        return
    bodies = {name: fetch.get_bytes(url) for name, url in FILES.items()}
    _validate(bodies)
    entries = []
    for name, body in bodies.items():
        fetch.write_snapshot(RAW_DIR / name, body)
        entries.append(dict(file=name, source=FILES[name], retrieved_at=date.today().isoformat(),
                            sha256=fetch.sha256(body), records=240 if name == FILE else 40 if name.endswith(".txt") else None))
    fetch.write_manifest(RAW_DIR, entries)


def load(conn) -> None:
    entries = {e["file"]: e for e in fetch.read_manifest(RAW_DIR)}
    rows, geographies = _validate({name: (RAW_DIR / name).read_bytes() for name in FILES})
    conn.executemany("INSERT INTO geographies (geo_id,geo_level,state,name) VALUES (?,'county_subdivision','RI',?)",
                     list(geographies.values()))
    upsert_source(conn, source_id=SOURCE_ID, state="RI", agency=AGENCY,
        product_name="Population Projections 2025-2050: state and 39 cities/towns",
        vintage="February 27, 2026 (revised)", base_year=None, horizon_year=2050, source_url=URL,
        retrieved_at=entries[FILE]["retrieved_at"],
        license="No explicit data license identified; cite the Rhode Island Division of Statewide Planning.",
        citation="Rhode Island Division of Statewide Planning. Population Projections 2025-2050. Revised February 27, 2026. One-page city/town table and Total row.",
        method_notes=("The current agency homepage links this revised table, subject to future revision and correction based on available data and municipal input. "
            "All 2025-2050 points are explicitly published projections; no past projection is relabeled as an estimate. "
            "The FY2026 work program identifies RIDSP as producer and describes a statewide cohort-component model guiding municipal projections. "
            "It proposes a 2020 base, but no completed methodology confirming the last estimate year was located for this revision; base_year is therefore null. "
            "The table's Total row is the independently published statewide product. Municipal sums differ by -3 to +1 persons; no values are adjusted. "
            "All 39 municipalities use ten-digit Census 2025 county-subdivision GEOIDs (state+county+subdivision), including cities. "
            "The Gazetteer includes one undefined Newport County water subdivision; it is excluded. Cities use the Gazetteer's coextensive subdivision records. "
            "Town and Census-place geographies are not interchangeable. Table abbreviations E./No./So. expand to East/North/South. "
            "No county totals are published in this selected table and none are derived. Earlier county products are not mixed into this edition. "
            "Household, component, and eligible SDO jobs publication coverage remains unverified; planned employment work is not evidence of a released jobs forecast."))
    insert_observations(conn, rows)
    conn.commit()
    print(f"RI load: {len(rows)} observations")


# Independently read from the rendered table, rather than from parser output.
FIXTURES = (("44", 2025, 1104675), ("44", 2050, 1134854), ("Barrington", 2050, 17299),
            ("East Providence", 2050, 44994), ("North Kingstown", 2025, 27916),
            ("Providence", 2050, 201447), ("Woonsocket", 2050, 42240))


def verify(conn) -> None:
    rows = conn.execute("SELECT * FROM observations WHERE state='RI'").fetchall()
    geographies = parse_geographies((RAW_DIR / "census_cousubs_2025.txt").read_bytes())
    ids = {gid for gid, name in geographies.values()} | {"44"}
    assert len(rows) == 240 and {(r["geo_id"], r["year"]) for r in rows} == {(gid, y) for gid in ids for y in YEARS}
    assert all(r["geo_level"] == ("state" if r["geo_id"] == "44" else "county_subdivision")
               and r["datatype"] == "projection" and r["source_id"] == SOURCE_ID and r["variable"] == "population"
               and r["scenario"] == "" and r["age_group"] == r["sex"] == r["race"] == "all" for r in rows)
    values = {(r["geo_id"], r["year"]): r["value"] for r in rows}
    for geo, year, value in FIXTURES:
        gid = "44" if geo == "44" else geographies[geo][0]
        assert values[gid, year] == value
    print("RI verify: all 39 municipality grids and rendered fixtures ok")


if __name__ == "__main__":
    if "--acquire" in sys.argv:
        acquire()
    else:
        print("usage: python -m sdo_mcp.ingest.ri --acquire")
