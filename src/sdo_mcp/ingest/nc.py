"""North Carolina adapter.

Source: NC Office of State Budget and Management (OSBM), State Demographer's
Office. County/State Population Projections, Vintage 2025B (2025 released
2026-01-15; the 2025B errata updated Brunswick, Columbus, Jackson, Orange and
the state row): estimates 2010-2024 + projections 2025-2060, annual, July 1.
Verified 2026-08-10 (plan/EXPANSION.md).

North Carolina quirks handled here:
  - the state row carries a pseudo-FIPS 37000 (not 37)
  - files are overwritten in place with no vintage in the filename — the
    committed snapshot is the reproducibility backbone; acquire() re-downloads,
    and a silent vintage swap is exactly what the verify fixtures catch
  - the CSV carries sex x single-age detail; v1 loads the sex='Total' rows
    only (the schema's detail columns leave room for a later pass)
  - datatype is not a column in the CSV: years <= 2024 are estimates (the
    Vintage 2024 estimates the projections are derived from), 2025+
    projections — matching the per-row flags on the ODS API
  - NC runs the only live queryable channel among the expansion states (a
    keyless Opendatasoft API) — used by probe_vintage() below
"""

from __future__ import annotations

import csv
import io
import sys
from datetime import date

from ..common import fetch
from ..store import REPO_ROOT, upsert_source, insert_observations

RAW_DIR = REPO_ROOT / "data" / "raw" / "nc"
STATE_FIPS = "37"
PSEUDO_STATE_FIPS = "37000"  # the CSV's state-row code is not a real FIPS

CSV_URL = "https://www.osbm.nc.gov/population-projections-age-data/download?attachment"
CSV_FILE = "NCprojectionsbyage2025B.csv"
ODS = "https://demography.osbm.nc.gov/api/explore/v2.1/catalog/datasets"

VINTAGE = "2025B"
BASE_YEAR = 2024   # last estimate year; 2025+ are projections
YEARS = (2010, 2060)
SOURCE_ID = "nc-pop-2025B"

AGENCY = (
    "North Carolina Office of State Budget and Management (OSBM), "
    "State Demographer's Office (Demographic and Economic Analysis Section)"
)
CITATION = (
    "NC OSBM State Demographer's Office. County/State Population Projections, "
    "Vintage 2025B (2010-2060). Retrieved from osbm.nc.gov."
)
LICENSE = "Public Domain (per the OSBM data catalog); nc.gov terms apply."


def acquire() -> None:
    """Re-download the sex x single-age CSV into data/raw/nc/.

    WARNING: OSBM overwrites this URL in place on every vintage/errata — a
    re-acquire REPLACES the 2025B snapshot with whatever is current. Run only
    when deliberately moving to a new vintage; the verify fixtures then need
    updating too.
    """
    body = fetch.get_bytes(CSV_URL)
    text = body.decode("utf-8", "replace")
    reader = csv.reader(io.StringIO(text))
    header = next(reader, [])
    if not header[:3] == ["fips", "county", "region"] or "total" not in header:
        raise RuntimeError(
            f"{CSV_URL}: unexpected header {header[:8]!r} — not the projections "
            "CSV (soft-200 trap or a new file layout)"
        )
    n_rows = sum(1 for _ in reader)
    if n_rows < 15_000:
        raise RuntimeError(f"{CSV_URL}: only {n_rows} data rows — truncated download?")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    fetch.write_snapshot(RAW_DIR / CSV_FILE, body)
    fetch.write_manifest(RAW_DIR, [{
        "file": CSV_FILE, "source": CSV_URL,
        "retrieved_at": date.today().isoformat(),
        "sha256": fetch.sha256(body), "records": n_rows,
        "note": "sex x single-age file; v1 loads the sex='Total' rows. Files "
                "are overwritten in place with no vintage in the name.",
    }])
    print(f"NC acquire: {CSV_FILE} ({n_rows:,} rows)")


def _retrieved() -> str:
    entry = next(e for e in fetch.read_manifest(RAW_DIR) if e["file"] == CSV_FILE)
    return entry["retrieved_at"]


def load(conn) -> None:
    """Snapshot -> observations + sources. No network."""
    name_by_fips = {
        row["geo_id"]: row["name"]
        for row in conn.execute(
            "SELECT geo_id, name FROM geographies WHERE state='NC' AND geo_level='county'"
        )
    }

    rows: list[dict] = []
    with open(RAW_DIR / CSV_FILE, newline="") as f:
        reader = csv.DictReader(f)
        age_cols = [c for c in reader.fieldnames if c.startswith("age")]
        assert len(age_cols) == 101, f"NC load: {len(age_cols)} age columns, expected 101"
        n_checked = 0
        for rec in reader:
            if rec["sex"] != "Total":
                continue  # v1 totals only; female/male rows stay in the snapshot
            total = int(rec["total"])
            # The published total must equal its own age detail — checked on
            # every loaded row, so a shifted column can never slip through.
            assert sum(int(rec[a]) for a in age_cols) == total, (
                f"NC load: age columns do not sum to total for "
                f"{rec['county']} {rec['year']}"
            )
            n_checked += 1
            year = int(rec["year"])
            datatype = "estimate" if year <= BASE_YEAR else "projection"
            if rec["fips"] == PSEUDO_STATE_FIPS:
                level, gid = "state", STATE_FIPS
            else:
                level, gid = "county", rec["fips"]
                census_name = name_by_fips.get(gid)
                assert census_name is not None, f"NC load: unknown county FIPS {gid}"
                assert census_name.removesuffix(" County") == rec["county"], (
                    f"NC load: {gid} is {rec['county']!r} in the file but "
                    f"{census_name!r} in the Census list"
                )
            rows.append(dict(state="NC", geo_level=level, geo_id=gid, year=year,
                             variable="population", value=total,
                             datatype=datatype, source_id=SOURCE_ID))
    print(f"NC load: {n_checked} Total rows, age sums all consistent")

    upsert_source(
        conn, source_id=SOURCE_ID, state="NC", agency=AGENCY,
        product_name="County/State Population Projections (Vintage 2025B)",
        vintage=VINTAGE, base_year=BASE_YEAR, horizon_year=YEARS[1],
        source_url=CSV_URL, retrieved_at=_retrieved(),
        license=LICENSE, citation=CITATION,
        method_notes=(
            "Cohort-component, July 1 reference, derived from Vintage 2024 "
            "estimates (2020-rebased). Totals come from the sex x single-age "
            "CSV (sex='Total' rows; detail not loaded in v1). The CSV carries "
            "no estimate/projection flag: years <= 2024 are estimates per the "
            "technical documentation, matching the per-row flags on OSBM's "
            "Opendatasoft API. Files are overwritten in place with no vintage "
            "in the filename — retrieved_at is the vintage anchor; the ODS "
            "API serves as the live vintage-change probe."
        ),
    )
    n = insert_observations(conn, rows)
    conn.commit()
    print(f"NC load: {n} observations")


# Known published values recorded in plan/EXPANSION.md at verification time
# (reconciled CSV <-> summary page <-> ODS API).
FIXTURES = [
    # (geo_level, geo_id, year, value, datatype)
    ("state",  "37",    2024, 11052495, "estimate"),
    ("state",  "37",    2060, 14511374, "projection"),
    ("county", "37183", 2024, 1235748,  "estimate"),     # Wake
    ("county", "37183", 2050, 1762983,  "projection"),   # Wake
    ("county", "37063", 2025, 344640,   "projection"),   # Durham
    ("county", "37119", 2060, 1672969,  "projection"),   # Mecklenburg
]


def verify(conn) -> None:
    for level, gid, year, value, datatype in FIXTURES:
        row = conn.execute(
            "SELECT value, datatype FROM observations WHERE state='NC' AND"
            " geo_level=? AND geo_id=? AND variable='population' AND year=?"
            " AND scenario='' AND age_group='all' AND sex='all' AND race='all'",
            (level, gid, year),
        ).fetchone()
        assert row is not None, f"NC verify: missing {level} {gid} {year}"
        assert int(row["value"]) == value and row["datatype"] == datatype, (
            f"NC verify: {level} {gid} {year} -> {row['value']}/{row['datatype']},"
            f" expected {value}/{datatype}"
        )

    # The strong check: counties partition the state — sums must equal the
    # state row exactly in every one of the 51 years.
    bad = conn.execute(
        "SELECT s.year, s.value AS state_total, c.sumy AS county_sum"
        " FROM observations s JOIN ("
        "  SELECT year, SUM(value) AS sumy FROM observations"
        "  WHERE state='NC' AND geo_level='county' AND variable='population'"
        "  GROUP BY year) c ON c.year = s.year"
        " WHERE s.state='NC' AND s.geo_level='state' AND s.variable='population'"
        "  AND s.value != c.sumy"
    ).fetchall()
    assert not bad, f"NC verify: county sums != state at {[tuple(r) for r in bad[:5]]}"

    span = conn.execute(
        "SELECT MIN(year) lo, MAX(year) hi, COUNT(DISTINCT year) ny,"
        " COUNT(DISTINCT geo_id) n"
        " FROM observations WHERE state='NC' AND geo_level='county'"
    ).fetchone()
    assert (span["lo"], span["hi"], span["ny"]) == (YEARS[0], YEARS[1], 51), (
        f"NC verify: county span {span['lo']}-{span['hi']} ({span['ny']} years)"
    )
    assert span["n"] == 100, f"NC verify: {span['n']} counties, expected 100"

    # The estimate/projection boundary must be exactly 2024/2025 everywhere.
    edge = conn.execute(
        "SELECT datatype, MIN(year) lo, MAX(year) hi FROM observations"
        " WHERE state='NC' GROUP BY datatype"
    ).fetchall()
    spans = {r["datatype"]: (r["lo"], r["hi"]) for r in edge}
    assert spans == {"estimate": (2010, 2024), "projection": (2025, 2060)}, spans

    print(f"NC verify: {len(FIXTURES)} round-trip values + 51-year county partition"
          " + datatype boundary ok")


def probe_vintage() -> dict:
    """Live vintage-change probe against OSBM's keyless Opendatasoft API: the
    current Wake County 2050 value and the record's own vintage label vs the
    stored snapshot's. A new vintage (or another errata like 2025B) changes
    one of them — then re-acquire and re-verify."""
    import urllib.parse

    url = (
        f"{ODS}/county-population-totals/records?"
        + urllib.parse.urlencode({"refine": ["county:Wake", "year:2050"], "limit": 5},
                                 doseq=True)
    )
    payload = fetch.get_json(url)
    results = payload.get("results", [])
    if len(results) != 1:
        raise RuntimeError(f"NC probe: expected 1 ODS record, got {len(results)}")
    live = results[0]
    snapshot_value = next(
        v for (_l, _g, y, v, _d) in FIXTURES
        if _g == "37183" and y == 2050
    )
    return {
        "live_wake_2050": live.get("value"),
        "snapshot_wake_2050": snapshot_value,
        "live_vintage_label": live.get("vintage"),
        "snapshot_vintage": VINTAGE,
        "live_flag": live.get("estimateprojection"),
        "changed": live.get("value") != snapshot_value,
    }


if __name__ == "__main__":
    if "--probe" in sys.argv:
        print(probe_vintage())
    elif "--acquire" in sys.argv:
        acquire()
    else:
        print("usage: python -m sdo_mcp.ingest.nc [--acquire | --probe]")
