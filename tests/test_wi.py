"""Wisconsin state/county population and household projections."""

import pytest

from sdo_mcp import server, store
from sdo_mcp.ingest import wi


def _point(result, year):
    return next(point for point in result["series"] if point["year"] == year)


def test_population_round_trip_has_census_boundary_and_vintage():
    result = server.get_forecast("WI", "state", "Wisconsin", "population")

    assert result["status"] == "ok"
    assert result["geo"] == {"level": "state", "id": "55", "name": "Wisconsin"}
    assert [point["year"] for point in result["series"]] == [2020, 2030, 2040, 2050]
    assert _point(result, 2020) == {"year": 2020, "value": 5893718, "datatype": "estimate"}
    assert _point(result, 2050) == {"year": 2050, "value": 5710120, "datatype": "projection"}
    assert result["source"]["vintage"] == "Vintage 2024 (December 2024)"
    assert result["source"]["base_year"] == 2020
    assert result["source"]["horizon_year"] == 2050


def test_household_round_trip_keeps_unknown_workbook_edition():
    result = server.get_forecast("WI", "county", "Dane", "households")
    state = server.get_forecast("WI", "state", "WI", "households")

    assert result["status"] == state["status"] == "ok"
    assert result["geo"]["id"] == "55025"
    assert _point(result, 2050) == {"year": 2050, "value": 335030, "datatype": "projection"}
    assert _point(state, 2020) == {"year": 2020, "value": 2428361, "datatype": "estimate"}
    assert _point(state, 2050) == {"year": 2050, "value": 2468672, "datatype": "projection"}
    source = state["source"]
    assert source["vintage"] == "2020-2050 series (edition date not stated in workbook)"
    assert source["base_year"] == 2020
    assert "does not state a publication edition date" in source["method_notes"]
    assert "December 2024" not in source["vintage"]


def test_population_control_and_household_rounding_rules_are_preserved():
    conn = store.connect()
    try:
        for variable, maximum_difference in (("population", 0), ("households", 2)):
            rows = conn.execute(
                "SELECT s.year, s.value - SUM(c.value) AS difference "
                "FROM observations AS s JOIN observations AS c "
                "ON c.state='WI' AND c.geo_level='county' AND c.variable=? "
                "AND c.year=s.year WHERE s.state='WI' AND s.geo_level='state' "
                "AND s.variable=? GROUP BY s.year ORDER BY s.year",
                (variable, variable),
            ).fetchall()
            assert rows
            assert all(abs(row["difference"]) <= maximum_difference for row in rows)
        shapes = conn.execute(
            "SELECT variable, COUNT(*) AS n, COUNT(DISTINCT geo_id) AS geos, "
            "COUNT(DISTINCT year) AS years FROM observations "
            "WHERE state='WI' GROUP BY variable ORDER BY variable"
        ).fetchall()
    finally:
        conn.close()

    assert [tuple(row) for row in shapes] == [
        ("households", 292, 73, 4),
        ("population", 292, 73, 4),
    ]


def test_published_subcounty_products_are_not_loaded_and_jobs_are_unresolved():
    place = server.get_forecast("WI", "place", "Madison", "population")
    jobs = server.get_forecast("WI", "state", "WI", "employment")

    assert place["status"] == "not_loaded"
    assert "subcounty" in place["reason"]
    assert jobs["status"] == "coverage_unknown"


def test_acquire_rejects_html_instead_of_workbook(monkeypatch):
    monkeypatch.setattr(wi.fetch, "get_bytes", lambda _url: b"<html>soft 200 error</html>")

    with pytest.raises(RuntimeError, match="not an xlsx"):
        wi.acquire()


def test_acquire_rejects_fake_pdf_payload(monkeypatch, tmp_path):
    responses = iter([
        (wi.RAW_DIR / wi.POP_FILE).read_bytes(),
        (wi.RAW_DIR / wi.HH_FILE).read_bytes(),
        b"%PDF fake but not parseable",
    ])
    monkeypatch.setattr(wi.fetch, "get_bytes", lambda _url: next(responses))
    monkeypatch.setattr(wi, "RAW_DIR", tmp_path / "wi")

    with pytest.raises(ValueError, match="readable PDF"):
        wi.acquire()
