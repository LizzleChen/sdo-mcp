"""Oregon adapter.

Source: Portland State University Population Research Center (PSU PRC),
Oregon Population Forecast Program combined county workbook. It contains 35
counties (Multnomah is handled by Metro), estimates for 1990/2000/2010/2020,
and forecasts for 2025-2045. Verified 2026-08-10
(plan/EXPANSION.md).

The combined workbook is the common v1 product. Newer rolling regional files
are separate vintages with different horizons and are deliberately not mixed
into it. Oregon publishes no official statewide OPFP forecast.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from datetime import date

from ..common import fetch
from ..store import REPO_ROOT, insert_observations, upsert_source

RAW_DIR = REPO_ROOT / "data" / "raw" / "or"
FILE = "age_specific_combined_results_2025.xlsx"
URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1qBDbPJBMz7bRiUksBF7BgIpDnVcmSEEJEYTg23JSUN0/export?format=xlsx"
)

SOURCE_ID = "or-pop-combined-2020"
BASE_YEAR = 2020
HORIZON_YEAR = 2045
ESTIMATE_YEARS = (1990, 2000, 2010, 2020)
FORECAST_YEARS = tuple(range(2025, 2046))
ALL_YEARS = (*ESTIMATE_YEARS, *FORECAST_YEARS)
MULTNOMAH_FIPS = "41051"

AGENCY = "Portland State University Population Research Center (PSU PRC)"
CITATION = (
    "Portland State University Population Research Center. Oregon Population "
    "Forecast Program, combined county age-sex results, 2020-based series "
    "through 2045."
)
LICENSE = "No separate license statement; official public forecast under Oregon law."


def acquire() -> None:
    """Download and validate the combined workbook without touching regional files."""
    import io
    import openpyxl

    body = fetch.get_bytes(URL)
    if not body.startswith(b"PK"):
        raise RuntimeError(f"{URL}: body is not an xlsx (Google error page?)")
    wb = openpyxl.load_workbook(io.BytesIO(body), read_only=True, data_only=True)
    try:
        ws = wb[wb.sheetnames[0]]
        header = tuple(next(ws.iter_rows(values_only=True)))
        if header[:6] != ("YEAR", "COUNTY", "SEX", "AGE5", "POPULATION", "SOURCE"):
            raise RuntimeError(f"{URL}: unexpected workbook header {header[:6]!r}")
    finally:
        wb.close()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_DIR / FILE).write_bytes(body)
    old_entries = []
    if (RAW_DIR / "manifest.json").exists():
        old_entries = [e for e in fetch.read_manifest(RAW_DIR) if e["file"] != FILE]
    old_entries.append({
        "file": FILE,
        "source": URL,
        "retrieved_at": date.today().isoformat(),
        "sha256": fetch.sha256(body),
        "records": None,
        "note": (
            "Official combined 35-county workbook: sparse estimates through "
            "2020 and annual forecasts 2025-2045. Rolling regional workbooks "
            "are separate products and are not mixed into this source."
        ),
    })
    fetch.write_manifest(RAW_DIR, old_entries)
    print(f"OR acquire: {FILE} ({len(body):,} bytes)")


def _retrieved() -> str:
    return next(
        e["retrieved_at"] for e in fetch.read_manifest(RAW_DIR) if e["file"] == FILE
    )


def load(conn) -> None:
    """Combined age-sex workbook -> 35 county population totals."""
    import openpyxl

    fips_by_name = {
        row["name"].removesuffix(" County"): row["geo_id"]
        for row in conn.execute(
            "SELECT geo_id, name FROM geographies WHERE state='OR' AND geo_level='county'"
        )
    }
    wb = openpyxl.load_workbook(RAW_DIR / FILE, read_only=True, data_only=True)
    try:
        ws = wb[wb.sheetnames[0]]
        header = tuple(next(ws.iter_rows(values_only=True)))
        assert header[:6] == ("YEAR", "COUNTY", "SEX", "AGE5", "POPULATION", "SOURCE")

        totals: defaultdict[tuple[str, int], int] = defaultdict(int)
        cells: defaultdict[tuple[str, int], int] = defaultdict(int)
        labels: defaultdict[tuple[str, int], set[str]] = defaultdict(set)
        source_names: set[str] = set()
        for rec in ws.iter_rows(min_row=2, values_only=True):
            if rec[0] is None:
                continue
            year = int(rec[0])
            name = str(rec[1]).strip()
            key = (name, year)
            totals[key] += int(round(float(rec[4])))
            cells[key] += 1
            labels[key].add(str(rec[5]).strip())
            source_names.add(name)
    finally:
        wb.close()

    expected_names = set(fips_by_name) - {"Multnomah"}
    if source_names != expected_names:
        raise RuntimeError(
            f"OR load: county mismatch; missing {sorted(expected_names - source_names)}, "
            f"extra {sorted(source_names - expected_names)}"
        )

    rows: list[dict] = []
    for (name, year), value in totals.items():
        assert cells[(name, year)] == 36, (
            f"OR load: {name} {year} has {cells[(name, year)]} age/sex cells, expected 36"
        )
        assert len(labels[(name, year)]) == 1, (
            f"OR load: {name} {year} has mixed source labels {labels[(name, year)]}"
        )
        label = next(iter(labels[(name, year)]))
        if label == "PSUPRC Estimate":
            datatype = "estimate"
        elif label == "PSUPRC Forecast":
            datatype = "projection"
        else:
            raise RuntimeError(f"OR load: unknown SOURCE label {label!r}")
        rows.append(dict(
            state="OR", geo_level="county", geo_id=fips_by_name[name], year=year,
            variable="population", value=value, datatype=datatype,
            source_id=SOURCE_ID,
        ))

    upsert_source(
        conn,
        source_id=SOURCE_ID,
        state="OR",
        agency=AGENCY,
        product_name="Oregon Population Forecast Program combined county series",
        vintage="2020-based combined workbook (retrieved 2026-08-10)",
        base_year=BASE_YEAR,
        horizon_year=HORIZON_YEAR,
        source_url=URL,
        retrieved_at=_retrieved(),
        license=LICENSE,
        citation=CITATION,
        method_notes=(
            "County totals are exact sums of 18 age groups by two sexes. The "
            "SOURCE field explicitly labels 1990, 2000, 2010, and 2020 as "
            "PSUPRC Estimate and 2025-2045 as PSUPRC Forecast. No 2021-2024 "
            "points are published, and none are interpolated. The combined "
            "workbook covers 35 counties; Multnomah County is handled by Metro. "
            "Rolling regional releases use different vintages and horizons and "
            "are not mixed into this common series. No official statewide OPFP "
            "forecast is published."
        ),
    )
    n = insert_observations(conn, rows)
    conn.commit()
    print(f"OR load: {n} observations")


FIXTURES = [
    ("41003", 2020, 95319, "estimate"),    # Benton
    ("41003", 2045, 112545, "projection"),
    ("41017", 2020, 199264, "estimate"),  # Deschutes
    ("41017", 2045, 292440, "projection"),
]


def verify(conn) -> None:
    for gid, year, value, datatype in FIXTURES:
        row = conn.execute(
            "SELECT value, datatype FROM observations WHERE state='OR' AND "
            "geo_level='county' AND geo_id=? AND variable='population' AND year=?",
            (gid, year),
        ).fetchone()
        assert row is not None, f"OR verify: missing county {gid} {year}"
        assert (int(row["value"]), row["datatype"]) == (value, datatype)

    shape = conn.execute(
        "SELECT COUNT(*) n, COUNT(DISTINCT geo_id) ng, COUNT(DISTINCT year) ny "
        "FROM observations WHERE state='OR' AND variable='population'"
    ).fetchone()
    assert tuple(shape) == (875, 35, 25)

    years = [
        r["year"] for r in conn.execute(
            "SELECT DISTINCT year FROM observations WHERE state='OR' ORDER BY year"
        )
    ]
    assert years == list(ALL_YEARS), f"OR verify: unexpected year set {years}"

    labels = conn.execute(
        "SELECT datatype, GROUP_CONCAT(DISTINCT year) years FROM observations "
        "WHERE state='OR' GROUP BY datatype ORDER BY datatype"
    ).fetchall()
    by_type = {
        r["datatype"]: {int(y) for y in r["years"].split(",")} for r in labels
    }
    assert by_type == {
        "estimate": set(ESTIMATE_YEARS),
        "projection": set(FORECAST_YEARS),
    }

    state_rows = conn.execute(
        "SELECT COUNT(*) n FROM observations WHERE state='OR' AND geo_level='state'"
    ).fetchone()["n"]
    multnomah_rows = conn.execute(
        "SELECT COUNT(*) n FROM observations WHERE state='OR' AND geo_id=?",
        (MULTNOMAH_FIPS,),
    ).fetchone()["n"]
    assert state_rows == 0 and multnomah_rows == 0
    print(f"OR verify: {len(FIXTURES)} fixtures + exact counties + sparse years + labels ok")


if __name__ == "__main__":
    if "--acquire" in sys.argv:
        acquire()
    else:
        print("usage: python -m sdo_mcp.ingest.or --acquire")
