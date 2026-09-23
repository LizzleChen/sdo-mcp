"""Offline review reminders and inventory of the database actually being served."""

from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

from . import notes, store

# Maintenance choices, not promises about agency release dates.
POLICIES = {
    "AZ": (90, "Check all three scenarios and component workbooks."),
    "CA": (30, "Check population, households, and employment separately; files may be replaced in place."),
    "CO": (30, "Check population, households, and jobs separately, especially around the autumn update."),
    "FL": (90, "Check BEBR population tables and the separate household/jobs PDF products."),
    "GA": (90, "Check OPB's projection edition and county workbook."),
    "MN": (90, "Check the state and county files, including the projected launch year."),
    "NC": (90, "Check OSBM's edition and base year, including component files."),
    "OR": (30, "Check every regional release and county edition; preserve the Multnomah exclusion."),
    "TN": (90, "Check Boyd Center releases and its hosted county detail service."),
    "TX": (90, "Check TDC's edition, all scenarios, and regional products; archive replaced files."),
    "WA": (90, "Review the state forecast, GMA county population, county components, and economic PDF separately."),
    "VA": (90, "Review the Cooper Center population workbook, methodology, and the separate age/sex and large-town products."),
    "WI": (90, "Review DOA state/county population and household workbooks and monitor the un-ingested subcounty products."),
    "UT": (90, "Review Gardner baseline population, household, employment, and components workbook; check the separate scenario release."),
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
