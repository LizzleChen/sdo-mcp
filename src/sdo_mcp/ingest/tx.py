"""Texas adapter.

Source: Texas Demographic Center (TDC), University of Texas at San Antonio —
Population Projections Vintage 2024 (released 2025-09-30). Annual 2020-2060,
state + 254 counties, three migration scenarios (Mid / High / Low; TDC
recommends Mid). Verified 2026-08-07 (plan/RESEARCH.md).

Acquired via the registration-cookie dance (POST /api/Tpepp/AddUser with
Mode=skip -> uid -> Cookie: projections-uid=<uid>), then the full-detail bulk
zips. Snapshots are committed because TDC deletes old vintages when a new one
is published — the committed zips are the only reproducible record.

Texas quirks handled here:
  - dead/ungated URLs return HTTP 200 with the current HTML page; zip bodies
    are validated by magic bytes
  - the CSV carries two year-2020 rows: year_month 202004 (April 1 Census
    count) and 202007 (July 1). TDC's own totals API serves the 202004 value,
    so 202004 is kept and 202007 dropped
  - no estimate/projection flag in the file. Boundary 2024/2025: the vintage
    is aligned to Census Bureau Vintage 2024 estimates (through July 2024);
    2025-2060 are model years
  - the CSV is not valid UTF-8 (decoded latin-1; only numeric fields and
    FIPS are consumed)
  - acquire cross-checks the Mid CSV against TDC's Projections/Totals API
    (the second publication channel) at every decade year, all 254 counties
"""

from __future__ import annotations

import csv
import io
import sys
import zipfile
from datetime import date

from ..common import fetch
from ..store import REPO_ROOT, upsert_source, insert_observations

BASE = "https://demographics.texas.gov"
RAW_DIR = REPO_ROOT / "data" / "raw" / "tx"
STATE_FIPS = "48"

SCENARIOS = ("Mid", "High", "Low")
YEARS = (2020, 2060)
BOUNDARY = 2024   # aligned to Census Vintage 2024 estimates; 2025+ model years
SOURCE_ID = "tx-pop-2024"

# Single-dimension detail published on the All-Ages row (never crossed here;
# the full age x sex x race detail stays in the committed zips for later).
SEX_COLS = {"total_male": "male", "total_female": "female"}
RACE_COLS = {
    "nh_white_total": "nh_white",
    "nh_black_total": "nh_black",
    "hispanic_total": "hispanic",
    "nh_asian_total": "nh_asian",
    "nh_other_total": "nh_other",
}

AGENCY = "Texas Demographic Center (TDC), University of Texas at San Antonio"
CITATION = (
    "Texas Demographic Center. Texas Population Projections, Vintage 2024 "
    "(released September 2025). Retrieved from demographics.texas.gov."
)
LICENSE = (
    "No stated terms; public data. Downloads sit behind a skippable "
    "registration survey; non-commercial use per project decision 2026-08-07."
)


def _zip_name(scenario: str) -> str:
    return f"Full_Pop_Projections_{scenario}.zip"


def _registration_uid() -> str:
    import json
    import urllib.request

    req = urllib.request.Request(
        f"{BASE}/api/Tpepp/AddUser",
        data=b"Mode=skip&Program=Projections",
        headers={**fetch.UA, "Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        body = json.loads(r.read().decode())
    return body["uid"]


def _csv_rows(scenario: str):
    """Stream the All-Ages rows of one scenario's committed zip, with the
    202007 duplicate of year 2020 dropped."""
    with zipfile.ZipFile(RAW_DIR / _zip_name(scenario)) as z:
        member = next(n for n in z.namelist() if n.endswith(".csv"))
        with z.open(member) as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="latin-1"))
            for row in reader:
                if row["age_in_yrs_num"] != "-1":
                    continue
                if row["year"] == "2020" and row["year_month"] != "202004":
                    continue
                yield row


def _api_totals_crosscheck() -> dict:
    """TDC's second channel: the Projections/Totals API (decade years). Every
    decade value for all 254 counties must match the Mid CSV exactly."""
    api = fetch.get_json(f"{BASE}/api/Tpepp/Projections/Totals/Mid?AreaVintageID=20202201")
    if len(api) != 254:
        raise RuntimeError(f"totals API returned {len(api)} counties, expected 254")
    def key(name: str) -> str:
        # The two channels spell a few counties differently (CSV "De Witt",
        # API "DeWitt") — compare with spaces and suffix removed.
        return name.lower().replace(" ", "").removesuffix("county")

    csv_by_name: dict[tuple[str, int], int] = {}
    for row in _csv_rows("Mid"):
        year = int(row["year"])
        if row["FIPS"] != "000" and year % 10 == 0:
            csv_by_name[(key(row["area_name"]), year)] = int(row["total"])
    mismatches = []
    for rec in api:
        for year in (2020, 2030, 2040, 2050, 2060):
            expected = int(rec[f"Pop{year}"])
            if csv_by_name.get((key(rec["Name"]), year)) != expected:
                mismatches.append((rec["Name"], year, expected,
                                   csv_by_name.get((key(rec["Name"]), year))))
    if mismatches:
        raise RuntimeError(
            f"TX API/CSV cross-check FAILED ({len(mismatches)} mismatches): "
            f"{mismatches[:5]} — the two TDC channels disagree; do not snapshot"
        )
    return {"counties": 254, "decade_points": 254 * 5, "max_abs_diff": 0}


def acquire() -> None:
    """Registration-cookie dance, then snapshot the three scenario zips."""
    uid = _registration_uid()
    print(f"TX acquire: registration uid {uid} (Mode=skip)")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    entries = []
    for scenario in SCENARIOS:
        url = f"{BASE}/Projections.tpepp?yr=2024&fl={_zip_name(scenario)}"
        import urllib.request

        req = urllib.request.Request(
            url, headers={**fetch.UA, "Cookie": f"projections-uid={uid}"}
        )
        with urllib.request.urlopen(req, timeout=600) as r:
            body = r.read()
        if not body.startswith(b"PK"):
            raise RuntimeError(f"{url}: body is not a zip (soft-200/redirect trap)")
        (RAW_DIR / _zip_name(scenario)).write_bytes(body)
        entries.append({
            "file": _zip_name(scenario), "source": url,
            "retrieved_at": date.today().isoformat(),
            "sha256": fetch.sha256(body), "records": None, "note": "",
        })
        print(f"TX acquire: {_zip_name(scenario)} ({len(body):,} bytes)")
    xchk = _api_totals_crosscheck()
    entries[0]["note"] = f"Projections/Totals API cross-check: {xchk}"
    print(f"TX acquire: API cross-check ok: {xchk}")
    fetch.write_manifest(RAW_DIR, entries)


def _geo(fips: str) -> tuple[str, str]:
    if fips == "000":
        return "state", STATE_FIPS
    return "county", STATE_FIPS + fips


def load(conn) -> None:
    """Committed zips -> observations + sources. No network."""
    rows: list[dict] = []
    for scenario in SCENARIOS:
        scen = scenario.lower()
        for rec in _csv_rows(scenario):
            level, gid = _geo(rec["FIPS"])
            year = int(rec["year"])
            datatype = "estimate" if year <= BOUNDARY else "projection"
            common = dict(state="TX", geo_level=level, geo_id=gid, year=year,
                          variable="population", datatype=datatype,
                          scenario=scen, source_id=SOURCE_ID)
            rows.append(dict(common, value=int(rec["total"])))
            for col, label in SEX_COLS.items():
                rows.append(dict(common, value=int(rec[col]), sex=label))
            for col, label in RACE_COLS.items():
                rows.append(dict(common, value=int(rec[col]), race=label))

    retrieved = fetch.read_manifest(RAW_DIR)[0]["retrieved_at"]
    upsert_source(
        conn, source_id=SOURCE_ID, state="TX", agency=AGENCY,
        product_name="Population Projections, Vintage 2024 (Mid/High/Low migration scenarios)",
        vintage="2024", base_year=BOUNDARY, horizon_year=YEARS[1],
        source_url=f"{BASE}/data/population-projections",
        retrieved_at=retrieved, license=LICENSE, citation=CITATION,
        method_notes=(
            "Cohort-component, aligned to Census Bureau Vintage 2024 estimates; "
            "2025-2060 are model years. TDC recommends the Mid scenario. Year "
            "2020 is the April 1 Census count (the file's July 2020 duplicate "
            "row is dropped to match TDC's own totals API). Snapshots are "
            "committed because TDC deletes old vintages on release; the Mid "
            "zip was cross-checked against the Projections/Totals API at "
            "acquire time (all 254 counties, every decade year, exact)."
        ),
    )
    n = insert_observations(conn, rows)
    conn.commit()
    print(f"TX load: {n} observations")


# Known published values: state and Anderson County (48001) read off the CSVs
# and confirmed against the Projections/Totals API at acquire time.
FIXTURES = [
    # (geo_level, geo_id, scenario, year, value, datatype)
    ("state",  "48",    "mid",  2020, 29145505, "estimate"),
    ("state",  "48",    "mid",  2024, 31290831, "estimate"),
    ("state",  "48",    "mid",  2025, 31669507, "projection"),
    ("county", "48001", "mid",  2030, 60080,    "projection"),
    ("county", "48001", "mid",  2060, 59622,    "projection"),
    ("county", "48201", "mid",  2060, 6865248,  "projection"),
]


def verify(conn) -> None:
    for level, gid, scen, year, value, datatype in FIXTURES:
        row = conn.execute(
            "SELECT value, datatype FROM observations WHERE state='TX' AND"
            " geo_level=? AND geo_id=? AND variable='population' AND year=?"
            " AND scenario=? AND age_group='all' AND sex='all' AND race='all'",
            (level, gid, year, scen),
        ).fetchone()
        assert row is not None, f"TX verify: missing {level} {gid} {scen} {year}"
        assert int(row["value"]) == value and row["datatype"] == datatype, (
            f"TX verify: {level} {gid} {scen} {year} -> "
            f"{row['value']}/{row['datatype']}, expected {value}/{datatype}"
        )

    for scen in ("mid", "high", "low"):
        span = conn.execute(
            "SELECT MIN(year) lo, MAX(year) hi, COUNT(DISTINCT geo_id) n"
            " FROM observations WHERE state='TX' AND geo_level='county'"
            " AND scenario=? AND age_group='all' AND sex='all' AND race='all'",
            (scen,),
        ).fetchone()
        assert (span["lo"], span["hi"]) == YEARS, f"TX {scen} span {span['lo']}-{span['hi']}"
        assert span["n"] == 254, f"TX {scen} has {span['n']} counties, expected 254"

    # Internal consistency of the published detail: sexes and race groups must
    # each sum to the published total (state, mid, horizon year).
    total = conn.execute(
        "SELECT value FROM observations WHERE state='TX' AND geo_id='48' AND"
        " year=2060 AND scenario='mid' AND sex='all' AND race='all'"
    ).fetchone()["value"]
    for column in ("sex", "race"):
        s = conn.execute(
            f"SELECT SUM(value) s FROM observations WHERE state='TX' AND"
            f" geo_id='48' AND year=2060 AND scenario='mid' AND {column} != 'all'"
        ).fetchone()["s"]
        assert int(s) == int(total), f"TX {column} detail sums to {s}, total {total}"

    print(f"TX verify: {len(FIXTURES)} round-trip values + spans + detail sums ok")


if __name__ == "__main__":
    if "--acquire" in sys.argv:
        acquire()
    else:
        print("usage: python -m sdo_mcp.ingest.tx --acquire")
