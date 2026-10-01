"""Offline review reminders and inventory of the database actually being served."""

from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

from . import notes, store

# Maintenance choices, not promises about agency release dates.
POLICIES = {
    "AL": (90, "Review CBER's county workbook and Box filename/metadata, 2025 estimate base, rounded display values, and any household or eligible jobs products."),
    "DE": (90, "Review the DPC 2024 edition and its 2025 readoption separately; check population, households, jobs by place of work, municipal and seasonal products."),
    "NM": (90, "Review UNM-GPS state and county projection editions, the 2022 model launch, age/sex and annual exports, and any household, components or eligible jobs products."),
    "SC": (90, "Review RFA publication vintage independently of its storage URL; compare total and age-group workbooks and audit components, households and eligible jobs products."),
    "WY": (90, "Review EAD's February 2025 workbook and PDF, 2023 estimate base, municipal ratio-based forecasts, and any household or eligible jobs product."),
    "MD": (90, "Review population/household workbook dates against the catalog, Census base and auxiliary inputs; check preliminary jobs separately, Baltimore City/county codes, regional and municipal products, and projected components."),
    "IL": (90, "Review IDPH edition, release date, April/July 2020 columns and Table 1/Table 3 differences; check Chicago, five-year components, households and eligible SDO jobs separately."),
    "AZ": (90, "Check all three scenarios and component workbooks."),
    "CA": (30, "Check population, households, and employment separately; files may be replaced in place."),
    "CO": (30, "Check population, households, and jobs separately, especially around the autumn update."),
    "FL": (90, "Check BEBR population tables and the separate household/jobs PDF products."),
    "GA": (90, "Check OPB's projection edition and county workbook."),
    "IN": (90, "Review IBRC's population edition, POST query, state/county bases and horizons; check separate regional, labor-force, household, and economic products."),
    "KY": (90, "Review KSDC population and household editions, Census anchor and estimate inputs, age/sex codebook and county codes; check regional products, place, components and eligible SDO employment coverage."),
    "MI": (90, "Review MCDA state/county population editions, workbook codes, base years and scenarios; separately check regions, places, households, components and eligible SDO employment products."),
    "MN": (90, "Check the state and county files, including the projected launch year."),
    "NC": (90, "Check OSBM's edition and base year, including component files."),
    "OR": (30, "Check every regional release and county edition; preserve the Multnomah exclusion."),
    "PA": (90, "Review PaSDC population edition, estimate labels and methodology; check the state components PDF and separate place, household and eligible employment coverage."),
    "TN": (90, "Check Boyd Center releases and its hosted county detail service."),
    "TX": (90, "Check TDC's edition, all scenarios, and regional products; archive replaced files."),
    "WA": (90, "Review the state forecast, GMA county population, county components, and economic PDF separately."),
    "VA": (90, "Review the Cooper Center population workbook, methodology, and the separate age/sex and large-town products."),
    "WI": (90, "Review DOA state/county population and household workbooks and monitor the un-ingested subcounty products."),
    "UT": (90, "Review Gardner baseline population, household, employment, and components workbook; check the separate scenario release."),
    "AK": (90, "Review September 2026 state scenarios and county workbook, 2025 estimate boundary, current borough/census-area FIPS, components and eligible jobs/households."),
    "HI": (90, "Review DBEDT population/economic 2050 Series, 2020 population/2022 jobs bases, resident/de facto definitions, combined Maui/Kalawao geography and workbook/PDF 2030 discrepancy; check households/subcounty products."),
    "ME": (90, "Review the OSE April 2025 population edition, 2022 estimate base, unusual five-year grid, long-horizon caution, municipal suppression and identifier support; confirm household, future component and eligible jobs products."),
    "NE": (90, "Review CPAR's August 2022 legislature-requested adopted Hauer/SEDAC regional-rivalry product, 2020 history and published state total, current SharePoint download and possible successor; confirm household, component, subcounty and eligible jobs products."),
    "NH": (90, "Review OPD publication and Census-based boundary, Table 1/Appendix A/Appendix B discrepancies, municipal forecasts, five-year components, households and eligible OPD jobs separately."),
    "NV": (90, "Review long-range and March near-term editions separately, certified base estimates, Carson City, rounded PDF totals, demographic detail, and household/eligible jobs/components coverage."),
    "OH": (90, "Review the Research Office catalog and Report 2023 workbook, 2020 estimate base, county/state controls, Ottawa overview discrepancy, conditional revisions and any household, subcounty, components or eligible jobs product."),
    'MA': (90,
     'Review UMDI V2024 edition and any separate revision, adjusted 2020 launch and fractional base '
     'precision, totals versus age/sex workbook, MCD municipal identifiers and RPA products; establish '
     'household, complete future components and eligible current SDO employment coverage independently.'),
    'NJ': (90,
     'Review NJDOL demographic catalog for a successor to the 2014–2034 series, 2014 estimate base, '
     'preferred versus illustrative state models, county rounding and 2029 state/county discrepancy; check '
     'households, future components, subcounty and eligible demographic-program jobs separately from labor '
     'force, occupational and MPO products.'),
    'NY': (90,
     'Review Cornell PAD state and county editions independently: provisional October 2024 state '
     'scenarios/base 2022/horizon 2050 versus September 2018 counties/base 2015/horizon 2040; check all '
     'three state scenarios, county update release, components, economic regions, households, smaller '
     'geography and eligible SDO jobs.'),
    'CT': (90,
     'Review old 2017/2018 edition for a successor, Census anchor and original method recovery, eight '
     'historical counties versus nine COGs and modern planning regions, town identifiers, '
     'households/components/eligible jobs.'),
    'RI': (90,
     'Review revised municipal table, released methods and estimate boundary, city/town county-subdivision '
     'identifiers, state/municipal rounding, earlier county products and released '
     'household/component/eligible jobs products.'),
}
REVIEWS_PATH = Path(__file__).with_name("source_reviews.json")


def review_status(state: str, *, today: date | None = None, reviews=None) -> dict:
    today = today or date.today()
    reviews = json.loads(REVIEWS_PATH.read_text()) if reviews is None else reviews
    days, focus = POLICIES[state]
    record = reviews.get(state)
    reviewed = None
    if record is not None:
        reviewed = date.fromisoformat(record["reviewed_on"])
        if not record.get("evidence") or not record.get("findings"):
            raise ValueError(f"{state}: review needs evidence links and product findings")
        if reviewed > today:
            raise ValueError(f"{state}: review date is after report date")
    due = reviewed + timedelta(days=days) if reviewed else None
    return {
        "interval_days": days,
        "focus": focus,
        "last_reviewed_on": reviewed.isoformat() if reviewed else None,
        "next_review_due": due.isoformat() if due else None,
        "status": "never_reviewed" if due is None else ("due" if today >= due else "not_due"),
        "as_of": today.isoformat(),
        "findings": record["findings"] if record else None,
        "evidence": record["evidence"] if record else [],
        "review_links": notes.STATES[state]["links"],
    }


def coverage_inventory(conn, state: str) -> dict:
    """Count queryable totals, not demographic detail inaccessible to tools.

    'loaded' means rows exist, not that every geography/scenario is complete.
    Keep publication status independent from loading status.
    """
    rows = conn.execute(
        "SELECT variable, geo_level, source_id, COUNT(*) AS row_count,"
        " MIN(year) AS start_year, MAX(year) AS end_year FROM observations"
        " WHERE state=? AND age_group='all' AND sex='all' AND race='all'"
        " GROUP BY variable, geo_level, source_id", (state,),
    ).fetchall()
    result = {}
    for cov in conn.execute("SELECT * FROM coverage WHERE state=? ORDER BY variable, geo_level", (state,)):
        variables = {"births", "deaths", "net_migration"} if cov["variable"] == "components" else {cov["variable"]}
        matches = [dict(r) for r in rows if r["variable"] in variables and r["geo_level"] == cov["geo_level"]]
        present = {r["variable"] for r in matches}
        result.setdefault(cov["variable"], {})[cov["geo_level"]] = {
            "status": cov["status"], "detail": cov["detail"],
            "load_status": ("loaded" if present == variables else "partially_loaded") if matches else "not_loaded",
            "loaded_series": matches,
        }
    return result


def report(conn, *, today: date | None = None) -> dict:
    return {state: {
        "name": notes.STATES[state]["name"],
        "review": review_status(state, today=today),
        "variables": coverage_inventory(conn, state),
        "sources_loaded": [dict(row) for row in store.sources_for_state(conn, state)],
    } for state in sorted(POLICIES)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, help="Defaults to SDO_DB or the installed database")
    args = parser.parse_args()
    conn = store.connect(args.database)
    try:
        print(json.dumps(report(conn), indent=2))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
