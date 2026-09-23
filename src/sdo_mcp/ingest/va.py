"""Virginia population projection adapter.

The University of Virginia Weldon Cooper Center's July 2025 workbook publishes
total population for Virginia and its 133 localities (95 counties plus 38
independent cities) at 2030, 2035, 2040, 2045, 2050, and 2055.  The second
sheet's mid-decade values are explicitly described as interpolated from the
direct projections; they are publisher-provided outputs and are loaded as
such, while this adapter never creates additional years.
"""

from __future__ import annotations

import io
import sys
import zipfile
from datetime import date
from xml.etree import ElementTree

from ..common import fetch
from ..store import REPO_ROOT, insert_observations, upsert_source

RAW_DIR = REPO_ROOT / "data" / "raw" / "va"
FILE = "VAPopProjections_Total_2030-2050_1July2025.xlsx"
METHOD_FILE = "VAPopProjMethodology_2025_FINAL_accessible_protected.docx"
URL = "https://www.coopercenter.org/sites/default/files/2025-07/VAPopProjections_Total_2030-2050_1July2025.xlsx"
METHOD_URL = "https://www.coopercenter.org/sites/default/files/2025-07/VAPopProjMethodology_2025_FINAL_accessible_protected.docx"
STATE_FIPS = "51"
SOURCE_ID = "va-pop-2025"
BASE_YEAR = 2024
HORIZON_YEAR = 2055
AGENCY = "University of Virginia Weldon Cooper Center for Public Service, Demographics Research Group"
LICENSE = "Public University of Virginia data; cite the Weldon Cooper Center."


def acquire() -> None:
    """Download and validate the official workbook and current methodology."""
    import openpyxl

    body = fetch.get_bytes(URL)
    if not body.startswith(b"PK"):
        raise RuntimeError(f"{URL}: body is not an xlsx (HTML or soft-200 error)")
    wb = openpyxl.load_workbook(io.BytesIO(body), read_only=True, data_only=True)
    try:
        expected = {"Total_2030,2040,2050", "Total_2035,2045,2055"}
        if set(wb.sheetnames) != expected:
            raise RuntimeError(f"{URL}: unexpected workbook sheets {wb.sheetnames!r}")
        for sheet, years in (("Total_2030,2040,2050", (2030, 2040, 2050)),
                             ("Total_2035,2045,2055", (2035, 2045, 2055))):
            ws = wb[sheet]
            rows = list(ws.iter_rows(values_only=True))
            if not rows or not str(rows[0][0]).startswith("Population Projections for Virginia"):
                raise RuntimeError(f"{URL}: unexpected {sheet} title")
            if tuple(rows[3][2:5]) != years:
                raise RuntimeError(f"{URL}: unexpected {sheet} year header")
            actual = [r for r in rows[4:] if any(v is not None for v in r[:5])]
            if len(actual) != 134 or actual[0][0] != 51000:
                raise RuntimeError(f"{URL}: {sheet} has {len(actual)} locality rows, expected 134")
    finally:
        wb.close()

    method = fetch.get_bytes(METHOD_URL)
    if not method.startswith(b"PK"):
        raise RuntimeError(f"{METHOD_URL}: body is not a docx (HTML or soft-200 error)")
    with zipfile.ZipFile(io.BytesIO(method)) as archive:
        document = ElementTree.fromstring(archive.read("word/document.xml"))
        if document.tag != "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}document":
            raise ValueError(f"{METHOD_URL}: response is not a Word document")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    fetch.write_snapshot(RAW_DIR / FILE, body)
    fetch.write_snapshot(RAW_DIR / METHOD_FILE, method)
    today = date.today().isoformat()
    fetch.write_manifest(RAW_DIR, [
        dict(file=FILE, source=URL, retrieved_at=today, sha256=fetch.sha256(body), records=134 * 6,
             note="July 2025 Cooper Center total population workbook; six publisher-provided 2030-2055 values (2035/2045/2055 are explicitly interpolated in the source workbook) for 133 Virginia localities."),
        dict(file=METHOD_FILE, source=METHOD_URL, retrieved_at=today, sha256=fetch.sha256(method), records=None,
             note="Official July 2025 Virginia population projection methodology document."),
    ])
    print(f"VA acquire: {FILE} ({len(body):,} bytes)")


def _retrieved(filename: str = FILE) -> str:
    return next(e["retrieved_at"] for e in fetch.read_manifest(RAW_DIR) if e["file"] == filename)


def load(conn) -> None:
    """Load the six publisher-provided locality totals, preserving decimals."""
    import math
    import openpyxl

    geographies = {
        row["geo_id"]: (row["geo_level"], row["name"])
        for row in conn.execute("SELECT geo_id, geo_level, name FROM geographies WHERE state='VA'")
    }
    if len(geographies) != 134:  # state + 133 county-equivalent localities
        raise RuntimeError(f"VA load: expected 134 geographies, found {len(geographies)}")

    wb = openpyxl.load_workbook(RAW_DIR / FILE, read_only=True, data_only=True)
    try:
        observations = []
        for sheet, years in (("Total_2030,2040,2050", (2030, 2040, 2050)),
                             ("Total_2035,2045,2055", (2035, 2045, 2055))):
            rows = list(wb[sheet].iter_rows(values_only=True))
            if tuple(rows[3][2:5]) != years:
                raise ValueError(f"VA load: unexpected {sheet} year header")
            seen: set[str] = set()
            for rec in rows[4:]:
                if not any(v is not None for v in rec[:5]):
                    continue
                fips, name, *values = rec[:5]
                if not isinstance(fips, (int, float)) or isinstance(fips, bool) or int(fips) != fips:
                    raise ValueError(f"VA load: invalid FIPS {fips!r}")
                gid = STATE_FIPS if int(fips) == 51000 else f"{int(fips):05d}"
                if gid not in geographies:
                    raise RuntimeError(f"VA load: source locality {name!r}/{gid} is not in Census geography seed")
                if gid in seen:
                    raise ValueError(f"VA load: duplicate locality {gid}")
                seen.add(gid)
                if not isinstance(name, str) or not name.strip():
                    raise ValueError(f"VA load: missing locality name for {gid}")
                expected_name = geographies[gid][1]
                if gid == STATE_FIPS:
                    if "Virginia" not in name:
                        raise ValueError(f"VA load: state label mismatch {name!r}")
                elif name != expected_name:
                    raise ValueError(f"VA load: FIPS/name mismatch {gid}: {name!r} != {expected_name!r}")
                if len(values) != 3 or any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(float(v)) or float(v) < 0 for v in values):
                    raise ValueError(f"VA load: invalid values for {gid}")
                level = geographies[gid][0]
                for year, value in zip(years, values):
                    observations.append(dict(state="VA", geo_level=level, geo_id=gid, year=year,
                                              variable="population", value=float(value),
                                              datatype="projection", source_id=SOURCE_ID))
            if seen != set(geographies):
                raise RuntimeError(f"VA load: {sheet} locality set differs; missing {sorted(set(geographies) - seen)}")
    finally:
        wb.close()

    upsert_source(
        conn, source_id=SOURCE_ID, state="VA", agency=AGENCY,
        product_name="Virginia Population Projections, 2030-2050",
        vintage="July 2025", base_year=BASE_YEAR, horizon_year=HORIZON_YEAR,
        source_url=URL, retrieved_at=_retrieved(), license=LICENSE,
        citation="University of Virginia Weldon Cooper Center for Public Service. Virginia Population Projections (2025).",
        method_notes=(
            "Total-population projections for 2030, 2035, 2040, 2045, 2050, and 2055 are served for Virginia and all 133 county-equivalent localities. "
            "The 2035/2045/2055 values are on a separate workbook sheet explicitly labelled interpolated from the direct projections; they are retained because they are publisher-provided outputs, not years generated by this adapter. "
            "The projection method uses 2024 population estimates as the launch/base series, so all served observations are projections and base_year=2024. "
            "Workbook values are fractional model outputs; the raw numeric precision is retained in SQLite and the totals API. Virginia independent cities (including Fairfax, Roanoke, and Virginia Beach) remain separate county-equivalent FIPS geographies."
        ),
    )
    n = insert_observations(conn, observations)
    conn.commit()
    print(f"VA load: {n} observations")


FIXTURES = [
    ("state", "51", 2030, 9060432.76370604),
    ("state", "51", 2055, 10700734.641079888),
    ("county", "51059", 2040, 1222111.5391638146),  # Fairfax County
    ("county", "51600", 2050, 26893.56200471817),    # Fairfax city (independent city)
    ("county", "51770", 2050, 103345.24624644822),   # Roanoke city (independent city)
]


def verify(conn) -> None:
    for level, gid, year, value in FIXTURES:
        row = conn.execute(
            "SELECT value, datatype FROM observations WHERE state='VA' AND geo_level=? AND geo_id=? "
            "AND variable='population' AND year=?", (level, gid, year)
        ).fetchone()
        assert row is not None, f"VA verify: missing {level} {gid} {year}"
        assert abs(float(row["value"]) - value) < 1e-9 and row["datatype"] == "projection"
    shape = conn.execute(
        "SELECT COUNT(*) n, COUNT(DISTINCT geo_id) ng, COUNT(DISTINCT year) ny, MIN(year) lo, MAX(year) hi "
        "FROM observations WHERE state='VA' AND variable='population'"
    ).fetchone()
    assert tuple(shape) == (804, 134, 6, 2030, 2055)
    assert conn.execute("SELECT COUNT(*) FROM observations WHERE state='VA' AND datatype='estimate'").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM observations WHERE state='VA' AND year IN (2035,2045,2055)").fetchone()[0] == 402
    print(f"VA verify: {len(FIXTURES)} fixtures + 133-locality six-year shape ok")


if __name__ == "__main__":
    if "--acquire" in sys.argv:
        acquire()
    else:
        print("usage: python -m sdo_mcp.ingest.va --acquire")
