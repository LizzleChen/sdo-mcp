"""Oregon adapter.

Source: Portland State University Population Research Center (PSU PRC),
Oregon Population Forecast Program county workbooks. PSU refreshes one region
per year, so Oregon's latest county data is a rolling set of 2023-2026 releases
rather than one statewide vintage. Multnomah County is handled by Metro, and
PSU publishes no official statewide OPFP forecast.
"""

from __future__ import annotations

import csv
import io
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from ..common import fetch
from ..store import REPO_ROOT, insert_observations, upsert_source

RAW_DIR = REPO_ROOT / "data" / "raw" / "or"
COMPACT_FILE = "county_population_2023-2026.csv"
MULTNOMAH_FIPS = "41051"

AGENCY = "Portland State University Population Research Center (PSU PRC)"
LICENSE = "CC BY 4.0 for archived reports; no separate statement on live workbooks."


@dataclass(frozen=True)
class CountyRelease:
    county: str
    release_year: int
    file_id: str
    base_year: int
    horizon_year: int

    @property
    def filename(self) -> str:
        return f"county/{self.release_year}_{self.county.replace(' ', '_')}.xlsx"

    @property
    def url(self) -> str:
        return (
            "https://docs.google.com/spreadsheets/d/"
            f"{self.file_id}/export?format=xlsx"
        )

    @property
    def source_id(self) -> str:
        return f"or-pop-{self.county.lower().replace(' ', '-')}-{self.release_year}"


# Latest published workbook for every county covered by PSU PRC as of 2026-09-04.
# PSU updates regions on a four-year rotation; these are deliberately separate
# source records because their base years and horizons differ.
COUNTY_RELEASES = (
    # Current cycle, Region 1, final June 2026. Baseline: 2025.
    CountyRelease("Curry", 2026, "14v4zD2RiVUnBYA04CzXYnvrHnuIon1c_", 2025, 2076),
    CountyRelease("Coos", 2026, "1sQ91lxfZpCYvHmCK72FsnFKlway5olyO", 2025, 2076),
    CountyRelease("Douglas", 2026, "1MzqA948JBoYaBSFaE43VjppxILACSw_A", 2025, 2076),
    CountyRelease("Josephine", 2026, "1uTALQjWeQw5O3pqQJWROB1IMlv42WHzi", 2025, 2076),
    CountyRelease("Jackson", 2026, "1o1yFfeqsU2kbXNU7r1YN76GoNK2RXfOQ", 2025, 2076),
    CountyRelease("Klamath", 2026, "1TQzqDAVBMA1-SfvHEGttIk4FLJM9NrvK", 2025, 2076),
    CountyRelease("Deschutes", 2026, "1ksQvrCBDagrTXwhlOO2eGZFboHgkP8yi", 2025, 2076),
    CountyRelease("Jefferson", 2026, "1r9JfJyxCpFCd1DdowN2fLnyVU8tMhPFX", 2025, 2076),
    CountyRelease("Lake", 2026, "1gixAFphjjIQvL_NiiFttm8ieltWC0Dtf", 2025, 2076),
    CountyRelease("Crook", 2026, "1SZ8Xm5IIb78eNCJpsSU7B8MFY1UPhLm4", 2025, 2076),
    CountyRelease("Harney", 2026, "1G_XePh8N2j0vVcZcqtVGgrwqF8qKUmKD", 2025, 2076),
    # Prior cycle, Regions 1/4, final 2025. Baseline: 2024.
    CountyRelease("Benton", 2025, "1pfc5SFppHml4LM1YPNkvi5DiZ3TTTffv", 2024, 2075),
    CountyRelease("Lane", 2025, "1v40QrcU_8O8fPWwe-i0lkZv9psW90y8n", 2024, 2075),
    CountyRelease("Lincoln", 2025, "1aemEtkYW2RtuclSDyYHlr--ZJ6aSoyOW", 2024, 2075),
    CountyRelease("Linn", 2025, "1arP2OP2WVL3IPBCXf3oObUADEZo7ELro", 2024, 2075),
    CountyRelease("Marion", 2025, "15YaSD72SYvIlF6jNW94X8og91sKuNX93", 2024, 2075),
    CountyRelease("Polk", 2025, "1Y7FwYcWyZLE2nX8od_ayuy1vRC9SA3wu", 2024, 2075),
    # Prior cycle, Region 3, final 2024. Baseline: 2022.
    CountyRelease("Clackamas", 2024, "1Q26ze9h_srupolHX74LM2n5DuNz5-6NQ", 2022, 2074),
    CountyRelease("Clatsop", 2024, "1ML4zdOV5nQEw_pT4_Uz3mORfwvljtiLe", 2022, 2074),
    CountyRelease("Columbia", 2024, "1_3HjqE6fteajSntRKUIZ4dybc7EhTpPF", 2022, 2074),
    CountyRelease("Hood River", 2024, "1ppbFimgVyVmu1lga6QRwu2_W2zmwrgOv", 2022, 2074),
    CountyRelease("Tillamook", 2024, "1o3qxmnR9rJpifa8AkSQZMjKJN4gh-7d_", 2022, 2074),
    CountyRelease("Wasco", 2024, "1ciqjtOrqqr5USwgVqhOZOMiW31JMlCyW", 2022, 2074),
    CountyRelease("Washington", 2024, "1zec3qdUpI7FmX3rcVBcijefPUStQAzji", 2022, 2074),
    CountyRelease("Yamhill", 2024, "1xBc-cyMabzSrynFBH2_jGUNDghYtNp03", 2022, 2074),
    # Prior cycle, Region 2, final June 2023. Baseline: 2020.
    CountyRelease("Baker", 2023, "17TWMR-bfGgFo6tJ-CPbUO9gkP8y044Mn", 2020, 2073),
    CountyRelease("Gilliam", 2023, "1Tm1l0ZKojFqnnSP_e--DXE2QTC5EpNwZ", 2020, 2073),
    CountyRelease("Grant", 2023, "1TCbM2cxJ-2heqKTlfwyaoWCR0bqKvvy8", 2020, 2073),
    CountyRelease("Malheur", 2023, "1kRvoZ9d26bxvq-p_P9xHm24CzIIKb7ib", 2020, 2073),
    CountyRelease("Morrow", 2023, "1Z1cCD36hwP-M4cURRuBbmPljbQqTk3GY", 2020, 2073),
    CountyRelease("Sherman", 2023, "1AkxCv00Sb1QOMkP7gEa_ZJTblAdnqvZ8", 2020, 2073),
    CountyRelease("Umatilla", 2023, "1OSQAZra1ynY4pEzuGFbisdXOODEX3Z2l", 2020, 2073),
    CountyRelease("Union", 2023, "135K4ShuyHshv5je79zBO4g5QH3Jbp4n-", 2020, 2073),
    CountyRelease("Wallowa", 2023, "1qsmJQaT7D-SQEapCb3GlWQK35tIUP_cD", 2020, 2073),
    CountyRelease("Wheeler", 2023, "1VUKrZlTXaaOW0d3ptxhh4rWZDFHlGsSV", 2020, 2073),
)

METHOD_RELEASES = (
    (2023, "1svaV1LDStsSG5r4N827ZCW_inJaVZgRI"),
    (2024, "1rJ7mLo43BnfI9IyUrQuyo1S36QYuDPxD"),
    (2025, "1NHBZxTlpW0Uh5WuKBrbOelDkt15qpFh_"),
    (2026, "18nKAL5lKsK9DBi53Vc95GDUNSTfeG_qf"),
)


def _find_total_table(workbook, source: str):
    """Return the sheet and columns for a county-total table."""
    for ws in workbook.worksheets:
        for row_number, row in enumerate(
            ws.iter_rows(min_row=1, max_row=12, values_only=True), start=1
        ):
            values = [str(v).strip().upper() if v is not None else "" for v in row]
            if "YEAR" not in values or "POPULATION" not in values:
                continue
            year_col = values.index("YEAR") + 1
            pop_col = values.index("POPULATION") + 1
            type_col = values.index("TYPE") + 1 if "TYPE" in values else None
            return ws, row_number, year_col, pop_col, type_col
    raise RuntimeError(f"{source}: no YEAR/POPULATION county-total table found")


def _read_series(source: Path | io.BytesIO, release: CountyRelease) -> list[dict]:
    import openpyxl

    wb = openpyxl.load_workbook(source, read_only=True, data_only=True)
    try:
        ws, header_row, year_col, pop_col, type_col = _find_total_table(
            wb, release.filename
        )
        rows = []
        for rec in ws.iter_rows(min_row=header_row + 1, values_only=True):
            year_value = rec[year_col - 1] if len(rec) >= year_col else None
            pop_value = rec[pop_col - 1] if len(rec) >= pop_col else None
            if year_value is None or pop_value is None:
                continue
            try:
                year = int(year_value)
                value = int(round(float(pop_value)))
            except (TypeError, ValueError):
                continue
            if type_col is None:
                datatype = "projection"
            else:
                label = str(rec[type_col - 1]).strip().lower()
                if label == "estimate":
                    datatype = "estimate"
                elif label == "forecast":
                    datatype = "projection"
                else:
                    raise RuntimeError(
                        f"{release.filename}: unknown TYPE label {label!r} for {year}"
                    )
            rows.append({"year": year, "value": value, "datatype": datatype})
    finally:
        wb.close()

    years = [row["year"] for row in rows]
    if not rows or len(years) != len(set(years)) or years != sorted(years):
        raise RuntimeError(f"{release.filename}: empty, duplicate, or unordered years")
    if years[-1] != release.horizon_year:
        raise RuntimeError(
            f"{release.filename}: horizon {years[-1]} != {release.horizon_year}"
        )
    if any(row["year"] <= release.base_year and row["datatype"] == "projection" for row in rows):
        raise RuntimeError(f"{release.filename}: projection at or before the base year")
    if any(row["year"] > release.base_year and row["datatype"] == "estimate" for row in rows):
        raise RuntimeError(f"{release.filename}: estimate after the base year")
    if any(row["value"] < 0 for row in rows):
        raise RuntimeError(f"{release.filename}: negative population")
    return rows


def acquire() -> None:
    """Download official files and create the compact committed totals snapshot."""
    old_entries = fetch.read_manifest(RAW_DIR) if (RAW_DIR / "manifest.json").exists() else []
    entries_by_file = {
        entry["file"]: entry
        for entry in old_entries
        if not entry["file"].lower().endswith((".xlsx", ".pdf"))
    }
    today = date.today().isoformat()
    added = 0
    compact_rows = []

    for release in COUNTY_RELEASES:
        path = RAW_DIR / release.filename
        body = path.read_bytes() if path.exists() else fetch.get_bytes(release.url)
        if not body.startswith(b"PK"):
            raise RuntimeError(f"{release.url}: body is not an xlsx (Google error page?)")
        series = _read_series(io.BytesIO(body), release)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
            added += 1
        compact_rows.extend(
            {
                "county": release.county,
                "release_year": release.release_year,
                "base_year": release.base_year,
                "horizon_year": release.horizon_year,
                "year": point["year"],
                "value": point["value"],
                "datatype": point["datatype"],
                "source_url": release.url,
            }
            for point in series
        )

    for release_year, file_id in METHOD_RELEASES:
        filename = f"methodology/PSUPRC_Forecast_Methodology_{release_year}.pdf"
        url = f"https://drive.google.com/uc?export=download&id={file_id}"
        path = RAW_DIR / filename
        body = path.read_bytes() if path.exists() else fetch.get_bytes(url)
        if not body.startswith(b"%PDF"):
            raise RuntimeError(f"{url}: body is not a PDF (Google error page?)")
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
            added += 1

    fields = (
        "county", "release_year", "base_year", "horizon_year", "year", "value",
        "datatype", "source_url",
    )
    text = io.StringIO(newline="")
    writer = csv.DictWriter(text, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(compact_rows)
    compact_body = text.getvalue().encode("utf-8")
    compact_path = RAW_DIR / COMPACT_FILE
    if compact_path.exists() and compact_path.read_bytes() != compact_body:
        raise RuntimeError(
            f"{compact_path}: existing compact snapshot differs; use a new vintage filename"
        )
    if not compact_path.exists():
        compact_path.write_bytes(compact_body)
    entries_by_file[COMPACT_FILE] = {
        "file": COMPACT_FILE,
        "source": "https://www.pdx.edu/population-research/population-forecasts",
        "retrieved_at": today,
        "sha256": fetch.sha256(compact_body),
        "records": len(compact_rows),
        "note": (
            "County totals extracted from the latest official 2023-2026 regional "
            "workbooks. Each row retains its county release, base year, horizon, "
            "estimate/projection label, and exact workbook URL."
        ),
    }

    fetch.write_manifest(RAW_DIR, list(entries_by_file.values()))
    print(
        f"OR acquire: {added} downloaded files; {len(COUNTY_RELEASES)} county workbooks "
        f"and {len(METHOD_RELEASES)} methods documents validated; "
        f"{len(compact_rows)} compact rows ready"
    )


def _manifest_entry(filename: str) -> dict:
    return next(e for e in fetch.read_manifest(RAW_DIR) if e["file"] == filename)


def _read_compact() -> dict[str, list[dict]]:
    releases_by_county = {release.county: release for release in COUNTY_RELEASES}
    series_by_county: dict[str, list[dict]] = {}
    with (RAW_DIR / COMPACT_FILE).open(newline="") as source:
        for rec in csv.DictReader(source):
            county = rec["county"]
            release = releases_by_county.get(county)
            if release is None:
                raise RuntimeError(f"{COMPACT_FILE}: unexpected county {county!r}")
            metadata = (
                int(rec["release_year"]), int(rec["base_year"]),
                int(rec["horizon_year"]), rec["source_url"],
            )
            expected = (
                release.release_year, release.base_year,
                release.horizon_year, release.url,
            )
            if metadata != expected:
                raise RuntimeError(
                    f"{COMPACT_FILE}: source metadata mismatch for {county}: "
                    f"{metadata!r} != {expected!r}"
                )
            series_by_county.setdefault(county, []).append({
                "year": int(rec["year"]),
                "value": int(rec["value"]),
                "datatype": rec["datatype"],
            })

    for release in COUNTY_RELEASES:
        rows = series_by_county.get(release.county, [])
        years = [row["year"] for row in rows]
        if not rows or len(years) != len(set(years)) or years != sorted(years):
            raise RuntimeError(
                f"{COMPACT_FILE}: empty, duplicate, or unordered {release.county} years"
            )
        if years[-1] != release.horizon_year:
            raise RuntimeError(
                f"{COMPACT_FILE}: {release.county} horizon {years[-1]} "
                f"!= {release.horizon_year}"
            )
        if any(
            row["year"] <= release.base_year and row["datatype"] == "projection"
            for row in rows
        ):
            raise RuntimeError(f"{COMPACT_FILE}: projection at or before a base year")
        if any(
            row["year"] > release.base_year and row["datatype"] == "estimate"
            for row in rows
        ):
            raise RuntimeError(f"{COMPACT_FILE}: estimate after a base year")
    return series_by_county


def load(conn) -> None:
    """Compact extract of latest rolling releases -> 35 county population series."""
    fips_by_name = {
        row["name"].removesuffix(" County"): row["geo_id"]
        for row in conn.execute(
            "SELECT geo_id, name FROM geographies WHERE state='OR' AND geo_level='county'"
        )
    }
    expected_names = set(fips_by_name) - {"Multnomah"}
    release_names = {release.county for release in COUNTY_RELEASES}
    if release_names != expected_names:
        raise RuntimeError(
            f"OR load: county mismatch; missing {sorted(expected_names - release_names)}, "
            f"extra {sorted(release_names - expected_names)}"
        )

    series_by_county = _read_compact()
    manifest = _manifest_entry(COMPACT_FILE)
    rows: list[dict] = []
    for release in COUNTY_RELEASES:
        series = series_by_county[release.county]
        upsert_source(
            conn,
            source_id=release.source_id,
            state="OR",
            agency=AGENCY,
            product_name=f"Oregon Population Forecast Program: {release.county} County",
            vintage=f"{release.release_year} regional release",
            base_year=release.base_year,
            horizon_year=release.horizon_year,
            source_url=release.url,
            retrieved_at=manifest["retrieved_at"],
            license=LICENSE,
            citation=(
                f"Portland State University Population Research Center. "
                f"{release.county} County coordinated population forecast, "
                f"{release.release_year} regional release."
            ),
            method_notes=(
                f"This is the latest PSU PRC workbook for {release.county} County as of "
                f"2026-09-04. Its base year is {release.base_year} and its horizon is "
                f"{release.horizon_year}. The 2025 and 2026 workbooks label their rows "
                "Estimate or Forecast directly. The 2023 and 2024 total tables omit that "
                "column; their methods documents name the base year, and every published "
                "table year is later than it, so those rows are projections. No years are "
                "filled or combined across vintages. Model results stored with decimals "
                "are rounded to the whole-person values displayed by PSU. Oregon has no "
                "official statewide OPFP forecast, and Multnomah County is handled "
                "separately by Metro."
            ),
        )
        rows.extend(
            {
                "state": "OR",
                "geo_level": "county",
                "geo_id": fips_by_name[release.county],
                "year": point["year"],
                "variable": "population",
                "value": point["value"],
                "datatype": point["datatype"],
                "source_id": release.source_id,
            }
            for point in series
        )

    n = insert_observations(conn, rows)
    conn.commit()
    print(f"OR load: {n} observations from {len(COUNTY_RELEASES)} county vintages")


FIXTURES = [
    ("41003", 2020, 95184, "estimate"),     # Benton, 2025 release
    ("41003", 2045, 112546, "projection"),
    ("41017", 2025, 213886, "estimate"),   # Deschutes, 2026 release
    ("41017", 2045, 278432, "projection"),
    ("41001", 2023, 16977, "projection"),  # Baker, 2023 release
    ("41005", 2023, 434554, "projection"), # Clackamas, 2024 release
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
        "SELECT COUNT(*) n, COUNT(DISTINCT geo_id) ng, COUNT(DISTINCT source_id) ns "
        "FROM observations WHERE state='OR' AND variable='population'"
    ).fetchone()
    assert tuple(shape) == (1916, 35, 35)

    releases = conn.execute(
        "SELECT CAST(SUBSTR(s.vintage, 1, 4) AS INTEGER) release_year, "
        "COUNT(DISTINCT o.geo_id) counties "
        "FROM observations o JOIN sources s USING (source_id) "
        "WHERE o.state='OR' GROUP BY release_year ORDER BY release_year"
    ).fetchall()
    assert [(r["release_year"], r["counties"]) for r in releases] == [
        (2023, 10), (2024, 8), (2025, 6), (2026, 11)
    ]

    bad_boundaries = conn.execute(
        "SELECT COUNT(*) n FROM observations o JOIN sources s USING (source_id) "
        "WHERE o.state='OR' AND ((o.year <= s.base_year AND o.datatype='projection') "
        "OR (o.year > s.base_year AND o.datatype='estimate'))"
    ).fetchone()["n"]
    assert bad_boundaries == 0

    state_rows = conn.execute(
        "SELECT COUNT(*) n FROM observations WHERE state='OR' AND geo_level='state'"
    ).fetchone()["n"]
    multnomah_rows = conn.execute(
        "SELECT COUNT(*) n FROM observations WHERE state='OR' AND geo_id=?",
        (MULTNOMAH_FIPS,),
    ).fetchone()["n"]
    assert state_rows == 0 and multnomah_rows == 0
    print(
        f"OR verify: {len(FIXTURES)} fixtures + 35 county vintages + "
        "estimate/projection boundaries ok"
    )


if __name__ == "__main__":
    if "--acquire" in sys.argv:
        acquire()
    else:
        print("usage: python -m sdo_mcp.ingest.or --acquire")
