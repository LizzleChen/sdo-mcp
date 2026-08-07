"""Tennessee adapter.

Source: Boyd Center for Business and Economic Research (UT Knoxville),
disseminated via the Tennessee State Data Center. 2022-vintage projections
(released Aug 2024): base July 1 2022 estimate, projections 2023-2070 annual,
state + 95 counties. License CC0. Verified 2026-08-07 (plan/RESEARCH.md).

Snapshots (committed 2026-08-07, byte-identical to the source downloads):
  data/raw/TN_CoPopProj_2022.xlsx  — county: total / age / race / sex tabs
  data/raw/TN_PopProj_2022.xlsx    — state: same four tabs

Tennessee quirks handled here:
  - the summary files never cross dimensions: age OR race OR sex, one at a
    time. Detail rows are stored exactly that shape (age_group=X, sex='all',
    race='all') — absent combinations stay absent.
  - 2022 column = estimate, 2023+ = projection (explicit in the layout PDF)
  - every value arrives as a string
  - the full crossed-detail file server (tndata.utk.edu) was down at ingest
    time; only the summary files are loaded.
"""

from __future__ import annotations

import sys

from ..common import fetch
from ..store import REPO_ROOT, upsert_source, insert_observations

RAW_DIR = REPO_ROOT / "data" / "raw"
COUNTY_XLSX = RAW_DIR / "TN_CoPopProj_2022.xlsx"
STATE_XLSX = RAW_DIR / "TN_PopProj_2022.xlsx"
RETRIEVED_AT = "2026-08-07"  # snapshot date, recorded in plan/PLAN.md

BASE_YEAR = 2022   # the one estimate column; 2023+ are projections
HORIZON = 2070
SOURCE_ID = "tn-pop-2022"

URLS = {
    COUNTY_XLSX.name: "https://tnsdc.utk.edu/wp-content/uploads/sites/94/2024/06/TN_CoPopProj_2022.xlsx",
    STATE_XLSX.name: "https://tnsdc.utk.edu/wp-content/uploads/sites/94/2024/06/TN_PopProj_2022.xlsx",
}

AGENCY = (
    "Boyd Center for Business and Economic Research, University of Tennessee "
    "Knoxville (via the Tennessee State Data Center)"
)
CITATION = (
    "Boyd Center for Business and Economic Research, University of Tennessee. "
    "Tennessee Population Projections, 2022 vintage (released August 2024). "
    "Retrieved from tnsdc.utk.edu."
)
LICENSE = "CC0 public domain."


def acquire() -> None:
    """Re-download the summary files (only needed on a new vintage; the
    committed snapshots are the normal source)."""
    for name, url in URLS.items():
        body = fetch.get_bytes(url)
        if not body.startswith(b"PK"):
            raise RuntimeError(f"{url}: body is not an xlsx (soft-200 trap)")
        (RAW_DIR / name).write_bytes(body)
        print(f"TN acquire: {name} ({len(body):,} bytes, sha256 {fetch.sha256(body)[:12]}…)")


def _sheet_rows(path, sheet: str) -> list[tuple]:
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True)
    try:
        return [tuple(r) for r in wb[sheet].iter_rows(values_only=True)]
    finally:
        wb.close()


def _melt(raw: list[tuple], geo_of, detail_column: str | None) -> list[dict]:
    """Wide year columns -> one row per number. On detail tabs the published
    label (e.g. '0 to 4', 'Non-Hispanic White') sits in the column just before
    the first year and lands in `detail_column` (age_group/race/sex)."""
    header = raw[0]
    first_year_col = len(header) - sum(1 for h in header if str(h).isdigit())
    years = [int(h) for h in header[first_year_col:]]
    assert years[0] == BASE_YEAR and years[-1] == HORIZON, f"TN year span {years[0]}-{years[-1]}"

    rows = []
    for rec in raw[1:]:
        level, gid = geo_of(rec)
        dims = {}
        if detail_column is not None:
            dims = {detail_column: str(rec[first_year_col - 1]).strip()}
        for year, val in zip(years, rec[first_year_col:]):
            rows.append(dict(
                state="TN", geo_level=level, geo_id=gid, year=year,
                variable="population", value=int(val),
                datatype="estimate" if year <= BASE_YEAR else "projection",
                source_id=SOURCE_ID, **dims,
            ))
    return rows


def load(conn) -> None:
    """Committed snapshots -> observations + sources. No network."""
    def county_geo(rec):
        return "county", str(rec[0]).strip()

    def state_geo(_rec):
        return "state", "47"

    rows: list[dict] = []
    # Totals.
    rows += _melt(_sheet_rows(COUNTY_XLSX, "Total by County"), county_geo, None)
    rows += _melt(_sheet_rows(STATE_XLSX, "Total"), state_geo, None)
    # One-dimension detail, exactly as published (never crossed).
    for sheet_c, sheet_s, column in (
        ("Total by County by Age Group", "Total by Age Group", "age_group"),
        ("Total by County by Race", "Total by Race", "race"),
        ("Total by County by Sex", "Total by Sex", "sex"),
    ):
        rows += _melt(_sheet_rows(COUNTY_XLSX, sheet_c), county_geo, column)
        rows += _melt(_sheet_rows(STATE_XLSX, sheet_s), state_geo, column)

    upsert_source(
        conn, source_id=SOURCE_ID, state="TN", agency=AGENCY,
        product_name="Population projections, 2022 vintage (summary files)",
        vintage="2022", base_year=BASE_YEAR, horizon_year=HORIZON,
        source_url="https://tnsdc.utk.edu/data-releases/projections/",
        retrieved_at=RETRIEVED_AT, license=LICENSE, citation=CITATION,
        method_notes=(
            "Cohort-component (Boyd Center). Base July 1 2022 estimate; "
            "2023-2070 are projections. Summary files publish age, race, and "
            "sex one dimension at a time, never crossed; the crossed-detail "
            "server (tndata.utk.edu) was down at ingest time."
        ),
    )
    n = insert_observations(conn, rows)
    conn.commit()
    print(f"TN load: {n} observations")


# Known published values recorded in plan/RESEARCH.md at verification time
# (2026-08-07), read straight off the source downloads.
FIXTURES = [
    ("state",  "47",    2022, 7051572, "estimate"),
    ("state",  "47",    2023, 7117168, "projection"),
    ("county", "47001", 2022, 78913,   "estimate"),
    ("county", "47003", 2025, 54010,   "projection"),
]


def verify(conn) -> None:
    for level, gid, year, value, datatype in FIXTURES:
        row = conn.execute(
            "SELECT value, datatype FROM observations WHERE state='TN' AND"
            " geo_level=? AND geo_id=? AND variable='population' AND year=?"
            " AND scenario='' AND age_group='all' AND sex='all' AND race='all'",
            (level, gid, year),
        ).fetchone()
        assert row is not None, f"TN verify: missing {level} {gid} {year}"
        assert int(row["value"]) == value and row["datatype"] == datatype, (
            f"TN verify: {level} {gid} {year} -> {row['value']}/{row['datatype']},"
            f" expected {value}/{datatype}"
        )

    span = conn.execute(
        "SELECT MIN(year) lo, MAX(year) hi, COUNT(DISTINCT geo_id) n"
        " FROM observations WHERE state='TN' AND geo_level='county'"
        " AND age_group='all' AND sex='all' AND race='all'"
    ).fetchone()
    assert (span["lo"], span["hi"]) == (BASE_YEAR, HORIZON), f"TN span {span['lo']}-{span['hi']}"
    assert span["n"] == 95, f"TN has {span['n']} counties, expected 95"

    # The published one-dimension detail must sum back to the published total
    # (internal consistency of the source, checked per dimension).
    for column in ("age_group", "race", "sex"):
        row = conn.execute(
            f"SELECT SUM(value) s FROM observations WHERE state='TN' AND"
            f" geo_level='state' AND year=2022 AND {column} != 'all'"
        ).fetchone()
        assert int(row["s"]) == 7051572, f"TN {column} detail sums to {row['s']}"

    print(f"TN verify: {len(FIXTURES)} round-trip values + spans + detail sums ok")


if __name__ == "__main__":
    if "--acquire" in sys.argv:
        acquire()
    else:
        print("usage: python -m sdo_mcp.ingest.tn --acquire")
