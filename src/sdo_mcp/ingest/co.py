"""Colorado adapter — the reference state.

Source: DOLA State Demography Office live JSON API
(gis.dola.colorado.gov/lookups — undocumented backend of the SDO lookup apps;
endpoints re-verified 2026-08-07, see plan/RESEARCH.md).

Adapter contract (plan/DESIGN.md §4):
  acquire()  -> snapshot the API into data/raw/co/ with checksums + retrieval
                dates, cross-checked against the Socrata mirror
  load(conn) -> melt the snapshots into observations + sources rows
  verify(conn) -> round-trip known published values out of the store exactly

Colorado quirks handled here:
  - errors arrive as HTTP 200 with a plain-text body (fetch.get_json guards)
  - nearly all numeric values arrive as strings
  - datatype casing varies by endpoint (Estimate/Projection vs
    ESTIMATE/PROJECTION); the household endpoint has no flag at all — its
    estimate/projection boundary is borrowed from the population series
  - county codes are bare 3-digit FIPS (35, not 08035); 0 = statewide
"""

from __future__ import annotations

import sys
import time

from ..common import fetch
from ..common.normalize import county_geo_id, norm_datatype
from ..store import REPO_ROOT, upsert_source, insert_observations
from .seed import COUNTY_FILE

API = "https://gis.dola.colorado.gov/lookups"
SOCRATA = "https://data.colorado.gov/resource/q5vp-adf3.json"
RAW_DIR = REPO_ROOT / "data" / "raw" / "co"
STATE_FIPS = "08"

POP_YEARS = (1970, 2060)
HH_YEARS = (2010, 2050)   # hard endpoint range
JOBS_YEARS = (2000, 2050)  # 1990-99 accepted but return []

AGENCY = "Colorado State Demography Office, Department of Local Affairs (DOLA)"
CITATION = (
    "Colorado State Demography Office, Department of Local Affairs. "
    "Retrieved from the SDO lookup API (gis.dola.colorado.gov/lookups)."
)
LICENSE = "Public data; API openly served. Cite the State Demography Office."


def _county_codes() -> list[int]:
    """Bare county codes from the committed Census county list: 0 (statewide)
    + the 64 Colorado counties."""
    codes = [0]
    for line in COUNTY_FILE.read_text().splitlines()[1:]:
        parts = line.split("|")
        if len(parts) >= 5 and parts[0] == "CO":
            codes.append(int(parts[2]))
    return codes


def _chunks(items: list[int], size: int = 13):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _pull(endpoint: str, years: tuple[int, int], extra: str = "") -> list[dict]:
    yrs = ",".join(str(y) for y in range(years[0], years[1] + 1))
    records: list[dict] = []
    for chunk in _chunks(_county_codes()):
        counties = ",".join(str(c) for c in chunk)
        url = f"{API}/{endpoint}?county={counties}&year={yrs}{extra}"
        records.extend(fetch.get_json(url))
        time.sleep(0.4)
    return records


def _socrata_crosscheck(components: list[dict]) -> dict:
    """The same forecast published through DOLA's second channel (Socrata,
    single year of age). Summed to county totals it must reproduce the
    components series to within rounding — one extra call that turns an
    undocumented endpoint into a reproducible figure.

    Compared from 1991 forward only: the two channels genuinely disagree on
    1990 (Socrata's 1990 sits on a different reference point — Douglas -52,
    El Paso ~600 persons), and match within 9 persons on every later year,
    forecast years included (re-confirmed 2026-08-07)."""
    import urllib.parse

    ours = {
        (int(r["countyfips"]), int(r["year"])): int(r["estimate"])
        for r in components
        if int(r["year"]) >= 1991
    }
    worst, compared = 0, 0
    for fips in (35, 41):  # Douglas, El Paso — the skill's reference counties
        q = SOCRATA + "?" + urllib.parse.urlencode(
            {
                "$select": "year,sum(totalpopulation) as pop",
                "$where": f"fipscode='{fips}'",
                "$group": "year",
                "$limit": "500",
            }
        )
        for rec in fetch.get_json(q):
            key = (fips, int(rec["year"]))
            if key in ours:
                worst = max(worst, abs(int(float(rec["pop"])) - ours[key]))
                compared += 1
        time.sleep(0.4)
    if compared < 100:
        raise RuntimeError(f"socrata cross-check too thin: {compared} year-points")
    if worst > 10:
        raise RuntimeError(
            f"socrata cross-check FAILED: max |diff| {worst} persons (>10) — "
            "the two DOLA channels disagree; do not snapshot"
        )
    return {"points_compared": compared, "max_abs_diff_persons": worst}


def acquire() -> None:
    """Refresh the data/raw/co/ snapshots from the live API (network)."""
    print("CO acquire: components (population + births/deaths/net migration)")
    components = _pull("components", POP_YEARS)
    xchk = _socrata_crosscheck(components)
    print(f"  socrata cross-check ok: {xchk}")

    print("CO acquire: households (totals, age=0, household=0)")
    households = _pull("household", HH_YEARS, "&age=0&household=0")

    print("CO acquire: jobs forecast")
    jobs = _pull("jobs-forecast", JOBS_YEARS)

    entries = [
        fetch.snapshot_json(
            RAW_DIR, "components.json", components,
            f"{API}/components (chunked; counties 0+64; years {POP_YEARS[0]}-{POP_YEARS[1]})",
            note=f"socrata q5vp-adf3 cross-check: {xchk}",
        ),
        fetch.snapshot_json(
            RAW_DIR, "households.json", households,
            f"{API}/household (age=0, household=0; years {HH_YEARS[0]}-{HH_YEARS[1]})",
            note="no estimate/projection flag in source; boundary borrowed from components",
        ),
        fetch.snapshot_json(
            RAW_DIR, "jobs.json", jobs,
            f"{API}/jobs-forecast (years {JOBS_YEARS[0]}-{JOBS_YEARS[1]})",
        ),
    ]
    fetch.write_manifest(RAW_DIR, entries)
    print(f"CO acquire: wrote {len(entries)} snapshots + manifest to {RAW_DIR}")


def _read_snapshot(name: str) -> tuple[list[dict], str]:
    import json

    entry = next(e for e in fetch.read_manifest(RAW_DIR) if e["file"] == name)
    return json.loads((RAW_DIR / name).read_text()), entry["retrieved_at"]


def _geo(countyfips: int | str) -> tuple[str, str]:
    c = int(countyfips)
    if c == 0:
        return "state", STATE_FIPS
    return "county", county_geo_id(STATE_FIPS, c)


def load(conn) -> None:
    """Snapshots -> observations + sources. No network."""
    components, comp_date = _read_snapshot("components.json")
    households, hh_date = _read_snapshot("households.json")
    jobs, jobs_date = _read_snapshot("jobs.json")

    # Population + components of change. The estimate/projection boundary is
    # read from the data itself, not assumed.
    rows = []
    boundary = 0
    for rec in components:
        level, gid = _geo(rec["countyfips"])
        year = int(rec["year"])
        datatype = norm_datatype(rec["datatype"])
        if datatype == "estimate":
            boundary = max(boundary, year)
        rows.append(dict(state="CO", geo_level=level, geo_id=gid, year=year,
                         variable="population", value=int(rec["estimate"]),
                         datatype=datatype, source_id="co-pop-2024"))
        for var, field in (("births", "births"), ("deaths", "deaths"),
                           ("net_migration", "netmig")):
            rows.append(dict(state="CO", geo_level=level, geo_id=gid, year=year,
                             variable=var, value=int(rec[field]),
                             datatype=datatype, source_id="co-pop-2024"))

    for rec in households:
        level, gid = _geo(rec["area_code"])
        year = int(rec["year"])
        rows.append(dict(state="CO", geo_level=level, geo_id=gid, year=year,
                         variable="households", value=int(rec["total_households"]),
                         datatype="estimate" if year <= boundary else "projection",
                         source_id="co-hh-2024"))

    for rec in jobs:
        level, gid = _geo(rec["countyfips"])
        rows.append(dict(state="CO", geo_level=level, geo_id=gid,
                         year=int(rec["population_year"]),
                         variable="employment", value=int(rec["totaljobs"]),
                         datatype=norm_datatype(rec["datatype"]),
                         source_id="co-jobs-2024"))

    vintage = str(boundary)
    common = dict(state="CO", agency=AGENCY, license=LICENSE, citation=CITATION)
    upsert_source(conn, source_id="co-pop-2024", vintage=vintage,
                  product_name="Population estimates & forecasts with components of change",
                  base_year=boundary, horizon_year=POP_YEARS[1],
                  source_url=f"{API}/components", retrieved_at=comp_date,
                  method_notes="Cohort-component model; annual series 1970-2060. "
                               "Cross-checked against the Socrata mirror (q5vp-adf3) "
                               "at snapshot time.", **common)
    upsert_source(conn, source_id="co-hh-2024", vintage=vintage,
                  product_name="Household forecasts (all household types)",
                  base_year=boundary, horizon_year=HH_YEARS[1],
                  source_url=f"{API}/household", retrieved_at=hh_date,
                  method_notes="Source carries no estimate/projection flag; the "
                               f"boundary ({boundary}/{boundary + 1}) is borrowed "
                               "from the population series.", **common)
    upsert_source(conn, source_id="co-jobs-2024", vintage=vintage,
                  product_name="Total jobs estimates & forecast (SDO series)",
                  base_year=boundary, horizon_year=JOBS_YEARS[1],
                  source_url=f"{API}/jobs-forecast", retrieved_at=jobs_date,
                  method_notes="DOLA's own total-jobs series — not the CDLE "
                               "occupational projections. Horizon 2050.", **common)

    n = insert_observations(conn, rows)
    conn.commit()
    print(f"CO load: {n} observations, boundary year {boundary}")


# Known published values, captured from the live API at snapshot time
# (2026-08-07). A state without a passing round-trip does not ship.
FIXTURES = [
    # (geo_level, geo_id, variable, year, value, datatype)
    ("state",  "08",    "population",    2024, 5956729, "estimate"),
    ("county", "08035", "population",    2024, 394030,  "estimate"),
    ("county", "08035", "population",    2025, 401211,  "projection"),
    ("county", "08035", "births",        2024, 3960,    "estimate"),
    ("county", "08035", "deaths",        2024, 2105,    "estimate"),
    ("county", "08035", "net_migration", 2024, 7034,    "estimate"),
    ("state",  "08",    "households",    2024, 2429420, "estimate"),
    ("county", "08035", "households",    2024, 146660,  "estimate"),
    ("state",  "08",    "employment",    2024, 3506270, "estimate"),
    ("county", "08035", "employment",    2024, 188130,  "estimate"),
    ("county", "08035", "employment",    2025, 191719,  "projection"),
]


def verify(conn) -> None:
    for level, gid, var, year, value, datatype in FIXTURES:
        row = conn.execute(
            "SELECT value, datatype FROM observations WHERE state='CO' AND"
            " geo_level=? AND geo_id=? AND variable=? AND year=? AND scenario=''"
            " AND age_group='all' AND sex='all' AND race='all'",
            (level, gid, var, year),
        ).fetchone()
        assert row is not None, f"CO verify: missing {level} {gid} {var} {year}"
        assert int(row["value"]) == value and row["datatype"] == datatype, (
            f"CO verify: {level} {gid} {var} {year} -> "
            f"{row['value']}/{row['datatype']}, expected {value}/{datatype}"
        )

    spans = {
        ("population", "county"): (1970, 2060),
        ("households", "county"): HH_YEARS,
        ("employment", "county"): JOBS_YEARS,
    }
    for (var, level), (y0, y1) in spans.items():
        row = conn.execute(
            "SELECT MIN(year) lo, MAX(year) hi, COUNT(DISTINCT geo_id) n"
            " FROM observations WHERE state='CO' AND geo_level=? AND variable=?",
            (level, var),
        ).fetchone()
        assert (row["lo"], row["hi"]) == (y0, y1), f"CO verify: {var} span {row['lo']}-{row['hi']}"
        assert row["n"] == 64, f"CO verify: {var} has {row['n']} counties, expected 64"

    print(f"CO verify: {len(FIXTURES)} round-trip values + spans ok")


def probe_vintage() -> dict:
    """Live vintage-change probe: compare the API's current estimate/projection
    boundary against the stored snapshot's. DOLA's next annual cycle is
    expected late Oct 2026 — when it lands, this reports 'changed' and the
    snapshots should be re-acquired."""
    live = fetch.get_json(
        f"{API}/components?county=0&year="
        + ",".join(str(y) for y in range(2020, 2031))
    )
    live_boundary = max(
        int(r["year"]) for r in live if norm_datatype(r["datatype"]) == "estimate"
    )
    _, stored_date = _read_snapshot("components.json")
    stored = max(
        int(r["year"])
        for r in _read_snapshot("components.json")[0]
        if norm_datatype(r["datatype"]) == "estimate"
    )
    return {
        "live_boundary": live_boundary,
        "snapshot_boundary": stored,
        "snapshot_date": stored_date,
        "changed": live_boundary != stored,
    }


if __name__ == "__main__":
    if "--probe" in sys.argv:
        print(probe_vintage())
    elif "--acquire" in sys.argv:
        acquire()
    else:
        print("usage: python -m sdo_mcp.ingest.co [--acquire | --probe]")
