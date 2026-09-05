"""Tennessee adapter.

Source: Boyd Center for Business and Economic Research (UT Knoxville),
disseminated via the Tennessee State Data Center. 2022-vintage projections
(released Aug 2024): base July 1 2022 estimate, projections 2023-2070 annual,
state + 95 counties. License CC0. Verified 2026-08-07 (plan/RESEARCH.md).

Snapshots (committed 2026-08-07, byte-identical to the source downloads):
  data/raw/TN_CoPopProj_2022.xlsx  — county: total / age / race / sex tabs
  data/raw/TN_PopProj_2022.xlsx    — state: same four tabs
  data/raw/tn/TN_CoPopProj_2022_alldata.csv.gz — county crossed
    age×sex×race detail, from the Boyd Center's own ArcGIS feature service
    (myUTK org on Esri cloud — the layer feeding the official projections
    dashboard; scoped 2026-08-07, plan/RESEARCH.md GIS section). The flat-file
    host for this dataset (tndata.utk.edu) was down at ingest time; the
    service is the only live route to the crossed detail.

Tennessee quirks handled here:
  - the summary files never cross dimensions: age OR race OR sex, one at a
    time. Detail rows are stored exactly that shape (age_group=X, sex='all',
    race='all') — absent combinations stay absent. The ArcGIS detail is the
    opposite: fully crossed cells only, no totals and no state rows. The
    crossed cells sum exactly to the published county totals (verified for
    every county-year at build time); the one-dimension summary tabs were
    rounded independently, so those margins reconcile only within ±5 persons.
  - 2022 column = estimate, 2023+ = projection (explicit in the layout PDF)
  - every Excel value arrives as a string; every ArcGIS value as a float
  - the service publishes 2022 twice: SOURCE='v2022' (raw vintage estimates)
    and SOURCE='Projection' (the projection base). They differ in 6 counties
    (statewide 7,051,339 vs 7,051,572); the summary files publish the
    projection-base values, so acquire keeps the Projection copy for all
    years and drops v2022. 2022 stays datatype=estimate (layout PDF).
  - no state rows in the service — state figures come from the state
    summary product
  - the ArcGIS /query endpoint stalls on GET; POST form data works
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
DETAIL_SOURCE_ID = "tn-pop-2022-detail"

URLS = {
    COUNTY_XLSX.name: "https://tnsdc.utk.edu/wp-content/uploads/sites/94/2024/06/TN_CoPopProj_2022.xlsx",
    STATE_XLSX.name: "https://tnsdc.utk.edu/wp-content/uploads/sites/94/2024/06/TN_PopProj_2022.xlsx",
}

# Boyd Center's own hosted feature service (owner tkuhn_myUTK; public, CC0).
DETAIL_LAYER = (
    "https://services1.arcgis.com/HLC8bAygObK4fhPW/arcgis/rest/services/"
    "TN_CoPopProj_2022_alldata/FeatureServer/0"
)
DETAIL_DIR = RAW_DIR / "tn"
DETAIL_CSV = DETAIL_DIR / "TN_CoPopProj_2022_alldata.csv.gz"
DETAIL_PAGE = 32000  # standardMaxRecordCount (resultType=standard)

# Service codes -> the labels the summary tabs publish (mapping verified
# 2026-08-07 by matching crossed sums against every summary margin).
AGE_GROUPS = {i + 1: label for i, label in enumerate((
    "0 to 4", "5 to 9", "10 to 14", "15 to 19", "20 to 24", "25 to 29",
    "30 to 34", "35 to 39", "40 to 44", "45 to 49", "50 to 54", "55 to 59",
    "60 to 64", "65 to 69", "70 to 74", "75 to 79", "80 to 84", "85 and over",
))}
RACES = {
    "NHWA": "Non-Hispanic White alone",
    "NHBA": "Non-Hispanic Black alone",
    "H": "Hispanic",
    "NHOTH": "Non-Hispanic other and two or more races",
}
SEXES = {"MALE": "Male", "FEMALE": "Female"}

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
        fetch.write_snapshot(RAW_DIR / name, body)
        print(f"TN acquire: {name} ({len(body):,} bytes, sha256 {fetch.sha256(body)[:12]}…)")


def _arcgis_query(form: dict) -> dict:
    """POST /query (GET stalls on this layer) and reject ArcGIS's in-band
    errors, which arrive as HTTP 200 with a JSON {"error": ...} body."""
    resp = fetch.post_json(DETAIL_LAYER + "/query", {"f": "json", **form})
    if "error" in resp:
        raise RuntimeError(f"ArcGIS error: {resp['error']}")
    return resp


def _detail_pull(where: str) -> list[dict]:
    """All rows matching `where`, paged by OBJECTID order."""
    records, offset = [], 0
    while True:
        resp = _arcgis_query({
            "where": where,
            "outFields": "GEOID,SOURCE,SEX,RACE,AGEGRP,YEAR,POPULATION",
            "orderByFields": "OBJECTID",
            "returnGeometry": "false",
            "resultType": "standard",
            "resultOffset": str(offset),
            "resultRecordCount": str(DETAIL_PAGE),
        })
        page = [f["attributes"] for f in resp["features"]]
        records.extend(page)
        offset += len(page)
        print(f"  {where!r}: {offset} rows", flush=True)
        if not resp.get("exceededTransferLimit") and len(page) < DETAIL_PAGE:
            return records


def acquire_detail() -> None:
    """Snapshot the crossed age×sex×race county detail from the Boyd Center's
    ArcGIS service into data/raw/tn/ (network)."""
    import csv
    import gzip
    import io
    from datetime import date

    # The service publishes 2022 twice: SOURCE='v2022' (raw vintage
    # estimates) and SOURCE='Projection' (the projection base; differs in 6
    # counties). The summary files publish the projection-base values —
    # checked here by requiring the Projection 2022 statewide sum to equal
    # the published state total, then only the Projection copy is kept.
    sums = _arcgis_query({
        "where": "YEAR=2022",
        "groupByFieldsForStatistics": "SOURCE",
        "outStatistics": '[{"statisticType":"sum","onStatisticField":'
                         '"POPULATION","outStatisticFieldName":"pop"}]',
    })
    by_source = {f["attributes"]["SOURCE"]: int(f["attributes"]["pop"])
                 for f in sums["features"]}
    assert by_source["Projection"] == 7051572, (
        f"Projection 2022 no longer sums to the published state total: {by_source}"
    )
    print(f"TN detail: 2022 base check ok {by_source}")

    rows_raw = _detail_pull(
        f"SOURCE='Projection' AND YEAR>={BASE_YEAR} AND YEAR<={HORIZON}"
    )
    cells = 95 * len(AGE_GROUPS) * len(SEXES) * len(RACES)
    expected = cells * (HORIZON - BASE_YEAR + 1)
    assert len(rows_raw) == expected, (
        f"detail rows {len(rows_raw)}, expected {expected}"
    )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["geoid", "year", "agegrp", "sex", "race", "population"])
    for rec in rows_raw:
        gid, agegrp = str(rec["GEOID"]), int(rec["AGEGRP"])
        pop = rec["POPULATION"]
        assert gid.startswith("47") and len(gid) == 5, f"bad GEOID {gid!r}"
        assert agegrp in AGE_GROUPS and rec["SEX"] in SEXES and rec["RACE"] in RACES
        assert float(pop) == int(pop), f"non-integer population {pop!r}"
        writer.writerow([gid, int(rec["YEAR"]), agegrp, rec["SEX"], rec["RACE"], int(pop)])

    DETAIL_DIR.mkdir(parents=True, exist_ok=True)
    out = io.BytesIO()
    # mtime=0 keeps the gzip byte-stable, so the committed snapshot only
    # changes when the data does.
    with gzip.GzipFile(fileobj=out, mode="wb", filename="", mtime=0) as gz:
        gz.write(buf.getvalue().encode())
    body = out.getvalue()
    fetch.write_snapshot(DETAIL_CSV, body)
    fetch.write_manifest(DETAIL_DIR, [{
        "file": DETAIL_CSV.name,
        "source": f"{DETAIL_LAYER}/query (POST; SOURCE='Projection' "
                  f"YEAR {BASE_YEAR}-{HORIZON})",
        "retrieved_at": date.today().isoformat(),
        "sha256": fetch.sha256(body),
        "records": len(rows_raw),
        "note": f"2022 statewide sums at snapshot time: {by_source} — the "
                f"summary files publish the Projection-base values, so only "
                f"that copy is kept (2022 stays datatype=estimate). "
                f"County-only; the service has no state rows.",
    }])
    print(f"TN detail acquire: {len(rows_raw)} rows, "
          f"{len(body):,} bytes gzip -> {DETAIL_CSV}")


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
            "sex one dimension at a time, never crossed; the crossed detail "
            "is loaded separately (tn-pop-2022-detail)."
        ),
    )
    n = insert_observations(conn, rows)
    n_detail = _load_detail(conn)
    conn.commit()
    print(f"TN load: {n} summary + {n_detail} crossed-detail observations")


def _load_detail(conn) -> int:
    """The crossed age×sex×race county snapshot -> observations. Crossed cells
    only, exactly as published: no totals, no state rows."""
    import csv
    import gzip

    manifest = next(e for e in fetch.read_manifest(DETAIL_DIR)
                    if e["file"] == DETAIL_CSV.name)
    rows = []
    with gzip.open(DETAIL_CSV, "rt", newline="") as f:
        for rec in csv.DictReader(f):
            year = int(rec["year"])
            rows.append(dict(
                state="TN", geo_level="county", geo_id=rec["geoid"], year=year,
                variable="population", value=int(rec["population"]),
                datatype="estimate" if year <= BASE_YEAR else "projection",
                age_group=AGE_GROUPS[int(rec["agegrp"])],
                sex=SEXES[rec["sex"]], race=RACES[rec["race"]],
                source_id=DETAIL_SOURCE_ID,
            ))

    upsert_source(
        conn, source_id=DETAIL_SOURCE_ID, state="TN", agency=AGENCY,
        product_name=("Population projections, 2022 vintage "
                      "(crossed age × sex × race county detail)"),
        vintage="2022", base_year=BASE_YEAR, horizon_year=HORIZON,
        source_url=DETAIL_LAYER,
        retrieved_at=manifest["retrieved_at"], license=LICENSE,
        citation=CITATION + " Crossed detail retrieved from the Boyd Center's "
                 "ArcGIS feature service (TN_CoPopProj_2022_alldata).",
        method_notes=(
            "Same cohort-component product as tn-pop-2022, via the Boyd "
            "Center's own ArcGIS service (the layer behind the official "
            "projections dashboard). SOURCE='Projection' rows only, "
            "2022-2070; the service's alternate 2022 copy (SOURCE='v2022', "
            "raw vintage estimates) differs in 6 counties and is not the "
            "series the summary files publish, so it is not loaded. County "
            "only — no state rows in the service; state figures come from "
            "the state summary product. Crossed cells sum exactly to the "
            "published county totals (checked for every county-year at build "
            "time); the one-dimension summary tabs were rounded "
            "independently and reconcile within +/-5 persons."
        ),
    )
    return insert_observations(conn, rows)


# Known published values recorded in plan/RESEARCH.md at verification time
# (2026-08-07), read straight off the source downloads.
FIXTURES = [
    ("state",  "47",    2022, 7051572, "estimate"),
    ("state",  "47",    2023, 7117168, "projection"),
    ("county", "47001", 2022, 78913,   "estimate"),
    ("county", "47003", 2025, 54010,   "projection"),
]

# Crossed-detail cells captured from the ArcGIS service at snapshot time
# (2026-08-07): (geo_id, year, agegrp code, SEX, RACE, value, datatype).
DETAIL_FIXTURES = [
    ("47001", 2022, 1,  "MALE",   "NHWA",  1723, "estimate"),
    ("47003", 2025, 5,  "MALE",   "NHOTH", 91,   "projection"),
    ("47037", 2040, 7,  "FEMALE", "H",     3770, "projection"),
    ("47157", 2070, 18, "FEMALE", "NHBA",  7656, "projection"),
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
            f" AND source_id='{SOURCE_ID}'"
        ).fetchone()
        assert int(row["s"]) == 7051572, f"TN {column} detail sums to {row['s']}"

    _verify_detail(conn)
    print(f"TN verify: {len(FIXTURES)} round-trip values + spans + detail sums"
          " + crossed margins ok")


def _verify_detail(conn) -> None:
    for gid, year, agegrp, sex, race, value, datatype in DETAIL_FIXTURES:
        row = conn.execute(
            "SELECT value, datatype FROM observations WHERE state='TN' AND"
            " geo_level='county' AND geo_id=? AND year=? AND age_group=? AND"
            " sex=? AND race=? AND variable='population' AND scenario=''",
            (gid, year, AGE_GROUPS[agegrp], SEXES[sex], RACES[race]),
        ).fetchone()
        assert row is not None, f"TN detail verify: missing {gid} {year} cell"
        assert int(row["value"]) == value and row["datatype"] == datatype, (
            f"TN detail verify: {gid} {year} {agegrp}/{sex}/{race} -> "
            f"{row['value']}/{row['datatype']}, expected {value}/{datatype}"
        )

    shape = conn.execute(
        "SELECT COUNT(*) n, COUNT(DISTINCT geo_id) c, MIN(year) lo, MAX(year) hi,"
        " MAX(CASE WHEN datatype='estimate' THEN year END) base"
        " FROM observations WHERE source_id=?", (DETAIL_SOURCE_ID,),
    ).fetchone()
    cells = 95 * len(AGE_GROUPS) * len(SEXES) * len(RACES)
    expected = cells * (HORIZON - BASE_YEAR + 1)
    assert shape["n"] == expected, f"TN detail rows {shape['n']}, expected {expected}"
    assert shape["c"] == 95, f"TN detail has {shape['c']} counties"
    assert (shape["lo"], shape["hi"]) == (BASE_YEAR, HORIZON), (
        f"TN detail span {shape['lo']}-{shape['hi']}"
    )
    assert shape["base"] == BASE_YEAR, f"TN detail estimate boundary {shape['base']}"

    # The crossed cells sum EXACTLY to the published county totals — every
    # county, every year. `IS NOT` (not `!=`) so a missing summary total
    # fails instead of vanishing as NULL.
    bad = conn.execute(
        "SELECT COUNT(*) bad FROM ("
        " SELECT d.geo_id, d.year FROM observations d WHERE d.source_id=?"
        " GROUP BY d.geo_id, d.year"
        " HAVING SUM(d.value) IS NOT ("
        "  SELECT m.value FROM observations m"
        "  WHERE m.state='TN' AND m.geo_level='county' AND m.geo_id=d.geo_id"
        "   AND m.year=d.year AND m.variable='population' AND m.scenario=''"
        "   AND m.age_group='all' AND m.sex='all' AND m.race='all'))",
        (DETAIL_SOURCE_ID,),
    ).fetchone()
    assert bad["bad"] == 0, (
        f"TN detail verify: {bad['bad']} county totals disagree with the "
        "summary files"
    )

    # The one-dimension summary tabs were rounded independently of the
    # crossed cells, so those margins reconcile only within a few persons
    # (observed max 5 across all counties × years × dimensions, 2026-08-07).
    # A wrong code->label mapping or a wrong SOURCE series would blow far
    # past this; a missing summary cell arrives as a NULL delta.
    for dim in ("age_group", "race", "sex"):
        others = [c for c in ("age_group", "race", "sex") if c != dim]
        row = conn.execute(
            f"SELECT COUNT(*) - COUNT(delta) missing, MAX(ABS(delta)) worst"
            f" FROM ("
            f" SELECT SUM(d.value) - ("
            f"  SELECT m.value FROM observations m"
            f"  WHERE m.state='TN' AND m.geo_level='county' AND m.geo_id=d.geo_id"
            f"   AND m.year=d.year AND m.variable='population' AND m.scenario=''"
            f"   AND m.{dim}=d.{dim}"
            f"   AND m.{others[0]}='all' AND m.{others[1]}='all') delta"
            f" FROM observations d WHERE d.source_id=?"
            f" GROUP BY d.geo_id, d.year, d.{dim})",
            (DETAIL_SOURCE_ID,),
        ).fetchone()
        assert row["missing"] == 0, (
            f"TN detail verify: {row['missing']} {dim} margins have no "
            "summary counterpart"
        )
        assert row["worst"] <= 5, (
            f"TN detail verify: {dim} margins drift up to {row['worst']} from "
            "the summary files (rounding tolerance is 5)"
        )


if __name__ == "__main__":
    if "--acquire" in sys.argv:
        acquire()
    elif "--acquire-detail" in sys.argv:
        acquire_detail()
    else:
        print("usage: python -m sdo_mcp.ingest.tn [--acquire | --acquire-detail]")
