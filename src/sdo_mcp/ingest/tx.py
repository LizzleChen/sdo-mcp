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
  - MSA/COG/TxDOT-district totals come from the same no-auth Totals API at
    decade resolution (2020/2030/2040/2050/2060). Ids come from the
    Geography lists and are joined on whitespace-normalized names (TxDOT
    names carry non-breaking spaces in *both* channels). COG and TxDOT
    districts each partition Texas exactly (checked at acquire); MSAs
    exclude non-metro counties and never sum to the state.
"""

from __future__ import annotations

import csv
import io
import json
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

# Non-county levels are served through TDC's second channel: the no-auth
# Projections/Totals API at decade resolution (the zips' annual detail is
# county/state only). AreaVintageID encodes geography type + delineation
# vintage (verified 2026-08-07, plan/RESEARCH.md).
DECADE_YEARS = (2020, 2030, 2040, 2050, 2060)
AREA_IDS = {
    "msa": "80202307",             # 2023-July CBSA delineation, 26 MSAs
    "cog": "90202104",             # 2021-April delineation, 24 COGs
    "txdot_district": "92000000",  # TDC's own ids 1-25
    "state": "10000000",           # single "Texas" record (partition anchor)
}
GEO_LEVELS = ("msa", "cog", "txdot_district")

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


def _norm_name(name: str) -> str:
    """Case + whitespace normalization for joining the two API channels.
    TxDOT names carry non-breaking spaces in both; collapse any run of
    whitespace (incl. \xa0) to single ASCII spaces, then lowercase."""
    return " ".join(str(name).split()).lower()


def _geo_id(level: str, raw_id: str) -> str:
    """Schema geo_id for a non-county level: MSAs keep the 5-digit CBSA
    FIPS; COG/TxDOT ids are TDC's own integers, prefixed per the schema's
    non-FIPS convention ('tx-cog-18', 'tx-txdot-1')."""
    if level == "msa":
        return raw_id
    return {"cog": "tx-cog-", "txdot_district": "tx-txdot-"}[level] + raw_id


def _snapshot_raw(name: str, body: bytes, source: str, records: int) -> dict:
    """Manifest entry for a snapshot written byte-identical to the API body
    (fetch.snapshot_json re-serializes; these files are the raw response)."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_DIR / name).write_bytes(body)
    return {
        "file": name,
        "source": source,
        "retrieved_at": date.today().isoformat(),
        "sha256": fetch.sha256(body),
        "records": records,
        "note": "",
    }


def _read_json(name: str) -> list:
    return json.loads((RAW_DIR / name).read_text())


def _registration_uid() -> str:
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
    decade value for all 254 counties must match the Mid CSV exactly, and the
    state totals API record must match the CSV's "State of Texas" row (the
    anchor the non-county partition checks compare against)."""
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
        if year % 10 == 0:
            name_key = "texas" if row["FIPS"] == "000" else key(row["area_name"])
            csv_by_name[(name_key, year)] = int(row["total"])
    mismatches = []
    for rec in api:
        for year in DECADE_YEARS:
            expected = int(rec[f"Pop{year}"])
            if csv_by_name.get((key(rec["Name"]), year)) != expected:
                mismatches.append((rec["Name"], year, expected,
                                   csv_by_name.get((key(rec["Name"]), year))))
    state_api = fetch.get_json(
        f"{BASE}/api/Tpepp/Projections/Totals/Mid?AreaVintageID={AREA_IDS['state']}"
    )
    if len(state_api) != 1:
        raise RuntimeError(f"state totals API returned {len(state_api)} records, expected 1")
    for year in DECADE_YEARS:
        expected = int(state_api[0][f"Pop{year}"])
        if csv_by_name.get(("texas", year)) != expected:
            mismatches.append(("Texas (state)", year, expected,
                               csv_by_name.get(("texas", year))))
    if mismatches:
        raise RuntimeError(
            f"TX API/CSV cross-check FAILED ({len(mismatches)} mismatches): "
            f"{mismatches[:5]} — the two TDC channels disagree; do not snapshot"
        )
    return {
        "counties": 254, "state": 1,
        "decade_points": 254 * 5 + 5, "max_abs_diff": 0,
    }


def _partition_crosscheck(snap: dict[str, list]) -> dict:
    """Structural guard for the non-county channel: COGs and TxDOT districts
    each partition Texas, so their decade sums must equal the state totals
    API record exactly (per scenario, all five decades). MSAs exclude
    non-metro counties and are never asserted."""
    state = {}
    for scenario in SCENARIOS:
        recs = snap[f"totals_state_{scenario}.json"]
        if len(recs) != 1:
            raise RuntimeError(
                f"TX state totals {scenario}: {len(recs)} records, expected 1"
            )
        state[scenario] = recs[0]
    checked = 0
    for level in ("cog", "txdot_district"):
        for scenario in SCENARIOS:
            recs = snap[f"totals_{level}_{scenario}.json"]
            for year in DECADE_YEARS:
                total = sum(int(r[f"Pop{year}"]) for r in recs)
                expected = int(state[scenario][f"Pop{year}"])
                checked += 1
                if total != expected:
                    raise RuntimeError(
                        f"TX partition check FAILED: {level} {scenario} {year} "
                        f"sums to {total}, state totals API says {expected} — "
                        "do not snapshot"
                    )
    return {
        "levels": 2, "scenarios": len(SCENARIOS),
        "decade_points": checked, "max_abs_diff": 0,
    }


def _api_snapshots() -> list[dict]:
    """Fetch + snapshot the non-county channel: the three Geography lists,
    the totals for all three levels x three scenarios, and the state anchor.
    Bodies are written byte-identical to the API response; the partition
    check runs before anything hits disk."""
    fetched: list[tuple[str, str, bytes, list]] = []
    for level in GEO_LEVELS:
        area_id = AREA_IDS[level]
        url = f"{BASE}/api/Geography/tpepp/{area_id}"
        body = fetch.get_bytes(url)
        data = json.loads(body.decode())
        if not isinstance(data, list) or not data:
            raise RuntimeError(f"TX geography {url}: body not a list {str(data)[:120]!r}")
        fetched.append((f"geography_{level}_{area_id}.json", url, body, data))
    for level, area_id in AREA_IDS.items():
        for scenario in SCENARIOS:
            url = f"{BASE}/api/Tpepp/Projections/Totals/{scenario}?AreaVintageID={area_id}"
            body = fetch.get_bytes(url)
            data = json.loads(body.decode())
            if not isinstance(data, list) or not data:
                raise RuntimeError(f"TX totals {url}: body not a list {str(data)[:120]!r}")
            fetched.append((f"totals_{level}_{scenario}.json", url, body, data))

    by_file = {name: data for name, _, _, data in fetched}
    xchk = _partition_crosscheck(by_file)
    entries = [_snapshot_raw(name, body, url, len(data))
               for name, url, body, data in fetched]
    for e in entries:
        if e["file"] == "totals_state_Mid.json":
            e["note"] = f"partition cross-check: {xchk}"
    print(f"TX acquire: {len(fetched)} API snapshots ok: {xchk}")
    return entries


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
    entries.extend(_api_snapshots())
    fetch.write_manifest(RAW_DIR, entries)
    print(f"TX acquire: manifest has {len(entries)} entries")


def _geo(fips: str) -> tuple[str, str]:
    if fips == "000":
        return "state", STATE_FIPS
    return "county", STATE_FIPS + fips


def _geo_names() -> list[tuple[str, str, str, str]]:
    """Geography rows for the three non-county levels, from the committed
    Geography-list snapshots (names single-spaced, ids per _geo_id)."""
    geos = []
    for level in GEO_LEVELS:
        for rec in _read_json(f"geography_{level}_{AREA_IDS[level]}.json"):
            geos.append((_geo_id(level, str(rec["Value"])), level, "TX",
                         " ".join(str(rec["Text"]).split())))
    return geos


def _geo_rows() -> list[dict]:
    """Decade population totals for MSAs/COGs/TxDOT districts from the
    committed Totals-API snapshots: 75 geos x 5 years x 3 scenarios. Totals
    responses carry names only — ids come from the Geography lists, joined
    on normalized names (fail loudly on any drift)."""
    rows: list[dict] = []
    for level in GEO_LEVELS:
        id_by_name = {
            _norm_name(rec["Text"]): _geo_id(level, str(rec["Value"]))
            for rec in _read_json(f"geography_{level}_{AREA_IDS[level]}.json")
        }
        for scenario in SCENARIOS:
            scen = scenario.lower()
            for rec in _read_json(f"totals_{level}_{scenario}.json"):
                gid = id_by_name.get(_norm_name(rec["Name"]))
                if gid is None:
                    raise RuntimeError(
                        f"TX {level}: totals name {rec['Name']!r} not in the "
                        "committed geography list — name normalization drifted"
                    )
                for year in DECADE_YEARS:
                    rows.append(dict(
                        state="TX", geo_level=level, geo_id=gid, year=year,
                        variable="population",
                        datatype="estimate" if year <= BOUNDARY else "projection",
                        scenario=scen, source_id=SOURCE_ID,
                        value=int(rec[f"Pop{year}"]),
                    ))
    return rows


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

    geos = _geo_names()
    conn.executemany(
        "INSERT OR REPLACE INTO geographies (geo_id, geo_level, state, name)"
        " VALUES (?,?,?,?)",
        geos,
    )
    rows.extend(_geo_rows())

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
            "acquire time (all 254 counties + the state row, every decade "
            "year, exact). MSA/COG/TxDOT-district totals are served at "
            "decade resolution from the same Totals API channel "
            "(2020/2030/2040/2050/2060); COG and TxDOT district sums each "
            "equal the state total exactly (partition check at acquire). "
            "Annual detail stays county-only."
        ),
    )
    n = insert_observations(conn, rows)
    conn.commit()
    print(f"TX load: {n} observations ({len(geos)} msa/cog/txdot geography rows)")


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

# Known published values for the non-county levels, live-verified from the
# Totals API 2026-08-07 (plan/RESEARCH.md). Mid scenario.
GEO_FIXTURES = [
    # (geo_level, geo_id, scenario, year, value, datatype)
    ("msa", "10180",           "mid", 2020, 176579,  "estimate"),
    ("msa", "10180",           "mid", 2060, 218016,  "projection"),
    ("cog", "tx-cog-18",       "mid", 2020, 2671161, "estimate"),
    ("cog", "tx-cog-18",       "mid", 2060, 4074166, "projection"),
    ("txdot_district", "tx-txdot-1", "mid", 2020, 266921, "estimate"),
    ("txdot_district", "tx-txdot-1", "mid", 2060, 301271, "projection"),
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

    for level, gid, scen, year, value, datatype in GEO_FIXTURES:
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

    # Scenario ordering across the non-county levels: low <= mid <= high at
    # every point (2020 shares the same estimate in all three scenarios).
    geo_rows = conn.execute(
        "SELECT geo_level, geo_id, year, scenario, value FROM observations"
        " WHERE state='TX' AND geo_level IN ('msa','cog','txdot_district')"
        " AND scenario IN ('low','mid','high') AND variable='population'"
        " AND age_group='all' AND sex='all' AND race='all'",
    ).fetchall()
    by_point: dict[tuple, dict] = {}
    for r in geo_rows:
        by_point.setdefault((r["geo_level"], r["geo_id"], r["year"]), {})[
            r["scenario"]
        ] = r["value"]
    assert len(by_point) == 75 * 5, f"TX geo points: {len(by_point)}, expected 375"
    for (level, gid, year), vals in by_point.items():
        assert vals["low"] <= vals["mid"] <= vals["high"], (
            f"TX {level} {gid} {year}: low/mid/high ordering broken {vals}"
        )

    # Partition structure: COGs and TxDOT districts each sum to the served
    # state total (geo_id '48', CSV/API-agreed at acquire) per scenario per
    # decade. MSAs do not partition — never asserted.
    for scen in ("low", "mid", "high"):
        state_by_year = {}
        for year in DECADE_YEARS:
            state_by_year[year] = conn.execute(
                "SELECT value FROM observations WHERE state='TX' AND"
                " geo_level='state' AND geo_id='48' AND variable='population'"
                " AND year=? AND scenario=? AND age_group='all' AND sex='all'"
                " AND race='all'",
                (year, scen),
            ).fetchone()["value"]
        for level in ("cog", "txdot_district"):
            for year in DECADE_YEARS:
                s = sum(
                    int(r["value"]) for r in geo_rows
                    if r["geo_level"] == level and r["year"] == year
                    and r["scenario"] == scen
                )
                assert s == int(state_by_year[year]), (
                    f"TX {level} {scen} {year}: sum {s} != state {state_by_year[year]}"
                )

    print(
        f"TX verify: {len(FIXTURES) + len(GEO_FIXTURES)} round-trip values + "
        "spans + detail sums + geo scenario ordering + COG/TxDOT partitions ok"
    )


if __name__ == "__main__":
    if "--acquire" in sys.argv:
        acquire()
    else:
        print("usage: python -m sdo_mcp.ingest.tx --acquire")
