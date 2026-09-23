"""Virginia population projections round-trip through the public tools.

The Cooper Center workbook uses county-equivalent FIPS rows, including
independent cities, and retains fractional model outputs.  These checks run
against the committed snapshot through the session database fixture.
"""

import io
import zipfile
from math import isclose

import pytest

from sdo_mcp import server, store
from sdo_mcp.ingest import va


def _point(result, year):
    return next(point for point in result["series"] if point["year"] == year)


def test_state_round_trip_preserves_fractional_values_and_metadata():
    result = server.get_forecast("VA", "state", "Virginia", "population")

    assert result["status"] == "ok"
    assert result["geo"] == {"level": "state", "id": "51", "name": "Virginia"}
    assert result["scenario"] is None
    assert [point["year"] for point in result["series"]] == [2030, 2035, 2040, 2045, 2050, 2055]
    assert _point(result, 2030) == {
        "year": 2030,
        "value": 9060432.76370604,
        "datatype": "projection",
    }
    assert _point(result, 2055) == {
        "year": 2055,
        "value": 10700734.641079888,
        "datatype": "projection",
    }
    assert result["source"]["vintage"] == "July 2025"
    assert result["source"]["base_year"] == 2024
    assert result["source"]["horizon_year"] == 2055
    assert "interpolated" in result["source"]["method_notes"]


def test_independent_city_county_equivalents_remain_distinct():
    fairfax_county = server.get_forecast("VA", "county", "Fairfax", "population")
    fairfax_city = server.get_forecast("VA", "county", "Fairfax city", "population")
    roanoke_city = server.get_forecast("VA", "county", "Roanoke city", "population")

    assert fairfax_county["status"] == fairfax_city["status"] == roanoke_city["status"] == "ok"
    assert fairfax_county["geo"]["id"] == "51059"
    assert fairfax_city["geo"]["id"] == "51600"
    assert roanoke_city["geo"]["id"] == "51770"
    assert fairfax_county["geo"]["id"] != fairfax_city["geo"]["id"]
    assert isclose(_point(fairfax_county, 2040)["value"], 1222111.5391638146, rel_tol=0, abs_tol=1e-12)
    assert isclose(_point(fairfax_city, 2050)["value"], 26893.56200471817, rel_tol=0, abs_tol=1e-12)
    assert isclose(_point(roanoke_city, 2050)["value"], 103345.24624644822, rel_tol=0, abs_tol=1e-12)
    assert all(point["datatype"] == "projection" for point in fairfax_city["series"])


def test_locality_shape_and_unloaded_large_town_product():
    conn = store.connect()
    try:
        shape = conn.execute(
            "SELECT COUNT(*) AS n, COUNT(DISTINCT geo_id) AS geos, "
            "COUNT(DISTINCT year) AS years FROM observations "
            "WHERE state='VA' AND variable='population'"
        ).fetchone()
    finally:
        conn.close()

    assert tuple(shape) == (804, 134, 6)
    place = server.get_forecast("VA", "place", "Leesburg", "population")
    assert place["status"] == "not_loaded"
    assert "large-town" in place["reason"]


def test_unreviewed_va_products_have_unknown_coverage():
    households = server.get_forecast("VA", "state", "VA", "households")
    employment = server.get_forecast("VA", "state", "VA", "employment")

    assert households["status"] == employment["status"] == "coverage_unknown"
    assert households["closest_published"] is None
    assert employment["closest_published"] is None


def test_acquire_rejects_html_instead_of_workbook(monkeypatch):
    monkeypatch.setattr(va.fetch, "get_bytes", lambda _url: b"<html>soft 200 error</html>")

    with pytest.raises(RuntimeError, match="not an xlsx"):
        va.acquire()


def test_acquire_rejects_unrelated_zip_instead_of_methodology_docx(monkeypatch, tmp_path):
    workbook = (va.RAW_DIR / va.FILE).read_bytes()
    unrelated = io.BytesIO()
    with zipfile.ZipFile(unrelated, "w") as archive:
        archive.writestr("unrelated.txt", "not a Word document")
    responses = iter([workbook, unrelated.getvalue()])
    monkeypatch.setattr(va.fetch, "get_bytes", lambda _url: next(responses))
    monkeypatch.setattr(va, "RAW_DIR", tmp_path / "va")

    with pytest.raises(KeyError, match="word/document.xml"):
        va.acquire()
