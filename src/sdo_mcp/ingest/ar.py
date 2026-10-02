"""Archived UALR/Arkansas SDC February 2015 time-series population product.

The catalog calls its Census anchor Vintage 2010; methods explicitly use
estimates through 2013. Confidence bounds and fitted values are not scenarios
or historical population estimates and are not served.
"""
from __future__ import annotations

import csv
import io
import json
import math
import sys
from datetime import date

from ..common import fetch
from ..store import REPO_ROOT, insert_observations, upsert_source

RAW_DIR = REPO_ROOT / "data" / "raw" / "ar"
CATALOG_URL = "https://youraedi.com/arkansas-state-data-center/"
ORIGINAL_URL = "https://arstatedatacenter.youraedi.com/population-projections-county/"
URL = "https://web.archive.org/web/20230507205934id_/https://arstatedatacenter.youraedi.com/content/Arkansas_Data/Population_Estimates/Population_Projections/LN(Trans_HIST_not_Adj)_Population_Projection_Charts_to_2065_And_STATE_Revised.xlsx"
FILE = "population_timeseries_1980-2065_feb2015.xlsx"
METHOD_FILE = "timeseries_methods_feb2015.pdf"
FILES = {
    FILE: URL,
    METHOD_FILE: "https://web.archive.org/web/20230507205853id_/https://arstatedatacenter.youraedi.com/content/Arkansas_Data/Population_Estimates/Population_Projections/Overview.pdf",
    "projection_catalog_archived2023.html": "https://web.archive.org/web/20221210000000id_/https://arstatedatacenter.youraedi.com/population-projections-county/",
    "state_data_center_catalog_2026-10-02.json": "https://youraedi.com/wp-json/wp/v2/pages?slug=arkansas-state-data-center",
}
SOURCE_ID = "ar-pop-timeseries-feb2015"
AGENCY = "Institute for Economic Advancement, University of Arkansas at Little Rock; Arkansas State Data Center (now AEDI)"
VINTAGE = "February 20, 2015 (catalog: Vintage 2010 Census anchor)"
YEARS = tuple(range(1980, 2066))
LABELS = (" History", " Fitted values", " Lower confidence limits", " Point forecasts", " Upper confidence limits")
# Original OOXML values independently read at AK/CJ rows 381/20/300/35.
FIXTURES = {
    ("05", 2013): 2959373, ("05", 2014): 2975048.321292217, ("05", 2065): 4437622.27424427,
    ("05007", 2014): 242074.30416131904, ("05007", 2065): 673336.1743284131,
    ("05119", 2014): 393958.1640389359, ("05119", 2065): 551832.5898480512,
    ("05013", 2014): 5218.681172451978, ("05013", 2065): 4158.875482473251,
}


def roster() -> dict[str, str]:
    with (REPO_ROOT / "data" / "raw" / "census_national_county2020.txt").open() as source:
        rows = {r["STATEFP"] + r["COUNTYFP"]: r["COUNTYNAME"]
                for r in csv.DictReader(source, delimiter="|") if r["STATE"] == "AR"}
    if set(rows) != {f"05{code:03d}" for code in range(1, 150, 2)}:
        raise ValueError("AR: incomplete county FIPS reference")
    return rows


def _key(name: str) -> str:
    return name.replace(" ", "").replace(".", "")


def _number(value, *, integer: bool = False) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0 or (integer and value != int(value)):
        raise ValueError("AR: invalid finite positive population cell")
    return value


def parse(body: bytes) -> list[dict]:
    from openpyxl import load_workbook
    try:
        workbook = load_workbook(io.BytesIO(body), data_only=True, read_only=True)
    except Exception as exc:
        raise ValueError("AR: response is not a readable XLSX") from exc
    try:
        if workbook.sheetnames != ["LN_Trans_Hist_not_Adj"]:
            raise ValueError("AR: changed worksheet roster")
        sheet = workbook.active
        if sheet.max_row != 382 or sheet.max_column != 88:
            raise ValueError("AR: changed workbook dimensions")
        try:
            values = list(sheet.values)
        except (ValueError, TypeError) as exc:
            raise ValueError("AR: workbook contains an unreadable numeric cell") from exc
        if values[0] != (None, "YEAR", *YEARS):
            raise ValueError("AR: changed annual year header")
        names = roster()
        rows = []
        totals = {}
        for index, (geo_id, name) in enumerate([*names.items(), ("05", "Arkansas State Total")]):
            start = 1 + index * 5 if geo_id != "05" else 377
            block = values[start:start + 5]
            prefix = _key(name) if geo_id != "05" else name
            ids = (prefix + "_H", prefix + "_F", prefix + "_L", prefix, prefix + "_U") if geo_id != "05" else (name,) * 5
            if tuple(r[0] for r in block) != ids or tuple(r[1] for r in block) != LABELS:
                raise ValueError("AR: changed county/state roster or row semantics")
            for offset, row in enumerate(block):
                for position, year in enumerate(YEARS, 2):
                    value = row[position]
                    historical = offset in (0, 1)
                    if historical != (year <= 2013):
                        if value is not None:
                            raise ValueError("AR: unexpected value outside historical/forecast span")
                    else:
                        _number(value, integer=offset == 0)
            for position, year in enumerate(YEARS, 2):
                if year <= 2013:
                    value = block[0][position]
                else:
                    lower, value, upper = (block[offset][position] for offset in (2, 3, 4))
                    if not lower <= value <= upper:
                        raise ValueError("AR: confidence bounds do not contain point forecast")
                totals[(geo_id, year)] = value
                rows.append(dict(state="AR", geo_level="state" if geo_id == "05" else "county", geo_id=geo_id,
                    year=year, variable="population", value=value, datatype="estimate" if year <= 2013 else "projection", source_id=SOURCE_ID))
        if any(value is not None for value in values[376]):
            raise ValueError("AR: unexpected extra geography row")
        for key, value in FIXTURES.items():
            if totals[key] != value:
                raise ValueError("AR: changed independently checked source value")
        for year in YEARS:
            county_total = sum(totals[(geo_id, year)] for geo_id in names)
            if not math.isclose(county_total, totals[("05", year)], rel_tol=0, abs_tol=1e-8):
                raise ValueError("AR: published county totals disagree with state beyond floating precision")
        return rows
    finally:
        workbook.close()


def _validate_all(bodies: dict[str, bytes]) -> list[dict]:
    from pypdf import PdfReader
    rows = parse(bodies[FILE])
    methods = bodies[METHOD_FILE]
    fetch.validate_pdf(methods, "AR time-series methods")
    reader = PdfReader(io.BytesIO(methods))
    text = " ".join(" ".join((p.extract_text() or "").split()) for p in reader.pages)
    if len(reader.pages) != 4 or any(marker not in text for marker in (
        "Gregory L. Hamilton", "February 20, 2015", "1980-2013 population estimates", "2011-2013",
        "2014-2065", "Holt", "natural logarithmic", "Institute for Economic Advancement")):
        raise ValueError("AR: changed edition, producer, base year or methods")
    catalog = bodies["projection_catalog_archived2023.html"].decode("utf-8", "replace")
    if "<html" not in catalog.lower() or any(marker not in catalog for marker in (
        "Time Series Extrapolations", "2014-2065", "Vintage 2010", "And_STATE_Revised.xlsx", "Overview.pdf", "Total_POP_summary.xls")):
        raise ValueError("AR: invalid original projection catalog")
    try:
        current = json.loads(bodies["state_data_center_catalog_2026-10-02.json"])
        if len(current) != 1 or current[0]["slug"] != "arkansas-state-data-center" or \
                "Population Estimates" not in current[0]["content"]["rendered"]:
            raise ValueError("wrong state data center page")
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError("AR: invalid current publisher page API") from exc
    return rows


def acquire() -> None:
    if (RAW_DIR / "manifest.json").exists():
        entries = fetch.read_manifest(RAW_DIR)
        if {e["file"] for e in entries} != set(FILES):
            raise ValueError("AR: incomplete saved manifest")
        _validate_all({name: (RAW_DIR / name).read_bytes() for name in FILES})
        print("AR acquire: reused validated archived February 2015 originals")
        return
    bodies = {name: fetch.get_bytes(url) for name, url in FILES.items()}
    rows = _validate_all(bodies)
    entries = []
    for name, url in FILES.items():
        fetch.write_snapshot(RAW_DIR / name, bodies[name])
        entries.append(dict(file=name, source=url, retrieved_at=date.today().isoformat(), sha256=fetch.sha256(bodies[name]),
            records=len(rows) if name == FILE else None,
            note="Archived original Arkansas State Data Center / UALR IEA February 20, 2015 time-series product, cataloged as Vintage 2010 Census anchor. History through 2013; annual point forecasts 2014-2065, preserving fractional persons. Current live forecast routes return 404; no successor established."))
    fetch.write_manifest(RAW_DIR, entries)


def load(conn) -> None:
    entries = {e["file"]: e for e in fetch.read_manifest(RAW_DIR)}
    if set(entries) != set(FILES):
        raise ValueError("AR: incomplete saved manifest")
    rows = _validate_all({name: (RAW_DIR / name).read_bytes() for name in FILES})
    names = {r["geo_id"]: r["name"] for r in conn.execute("SELECT geo_id,name FROM geographies WHERE state='AR' AND geo_level='county'")}
    if names != roster() or not conn.execute("SELECT 1 FROM geographies WHERE state='AR' AND geo_level='state' AND geo_id='05'").fetchone():
        raise ValueError("AR: county/state geography is not seeded correctly")
    upsert_source(conn, source_id=SOURCE_ID, state="AR", agency=AGENCY,
        product_name="County Population Projections 2014-2065 for Arkansas: Time Series Extrapolations (published state/county History and Point forecasts)",
        vintage=VINTAGE, base_year=2013, horizon_year=2065, source_url=URL,
        retrieved_at=entries[FILE]["retrieved_at"],
        license="No explicit data license identified in workbook/methods; archived catalog has a general All Rights Reserved footer. Preserve author, UALR IEA and Arkansas SDC/AEDI attribution.",
        citation="Gregory L. Hamilton, Institute for Economic Advancement, University of Arkansas at Little Rock. County Population Projections 2014-2065 for Arkansas: Time Series Extrapolations (February 20, 2015). Original Arkansas SDC XLSX sheet LN_Trans_Hist_not_Adj, History/Point forecasts rows; publisher originals recovered via Internet Archive.",
        method_notes=(
            "Older February 20, 2015 edition recovered from archived original Arkansas State Data Center catalog and downloads. The catalog's Vintage 2010 describes the Census anchor, not release date; methods use annual Census estimates through 2013. No newer eligible statewide edition was established; current catalog routes were removed. "
            "History rows are July 1 midyear/intercensal population estimates, 1980-2013. Point forecasts are annual projections 2014-2065, including now-past years. The model uses Holt exponential smoothing of natural-log population and converts results back to persons. "
            "Source forecast cells contain fractional persons; their original floating precision is preserved without rounding. Historical counts are whole persons. The 75 counties map to Census 2020 FIPS/name references; StFrancisCounty maps to St. Francis County. State total is explicitly published and retained. County History and Point sums agree with state within floating precision (absolute tolerance 1e-8 persons). "
            "Fitted historical values and 95% confidence limits are distinct source rows, not estimates or alternate scenarios; they are checked but not served. County confidence bounds are not added or served as statewide uncertainty. The long-horizon model assumes continuation of past dynamics and publishes no demographic component series. "
            "A separate cataloged 2011-2020 single-age race/Hispanic county and planning-district product (Census 2010) is published but deferred. AEDI's separate two-county NWA cohort-component product is documented in a regional planning appendix but no complete newer statewide original grid was recovered. Municipal, household and eligible SDO jobs products remain unverified."))
    insert_observations(conn, rows)
    conn.commit()
    print(f"AR load: {len(rows)} observations")


def verify(conn) -> None:
    rows = conn.execute("SELECT * FROM observations WHERE state='AR'").fetchall()
    expected = {(g, y) for g in ("05", *roster()) for y in YEARS}
    assert len(rows) == 6536 and {(r["geo_id"], r["year"]) for r in rows} == expected
    assert all(r["variable"] == "population" and r["scenario"] == "" and r["age_group"] == r["sex"] == r["race"] == "all"
        and r["geo_level"] == ("state" if r["geo_id"] == "05" else "county")
        and r["datatype"] == ("estimate" if r["year"] <= 2013 else "projection")
        and r["source_id"] == SOURCE_ID and math.isfinite(r["value"]) and r["value"] > 0 for r in rows)
    actual = {(r["geo_id"], r["year"]): r["value"] for r in rows}
    assert all(actual[k] == v for k, v in FIXTURES.items())
    source = conn.execute("SELECT * FROM sources WHERE source_id=?", (SOURCE_ID,)).fetchone()
    assert source["base_year"] == 2013 and source["horizon_year"] == 2065 and source["vintage"] == VINTAGE
    print("AR verify: all 75 counties/state, 1980-2065 annual grid, 2013 boundary and original fractional forecasts ok")


if __name__ == "__main__":
    if "--acquire" in sys.argv:
        acquire()
    else:
        print("usage: python -m sdo_mcp.ingest.ar --acquire")
