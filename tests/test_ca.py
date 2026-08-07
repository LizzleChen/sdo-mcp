"""California round-trips through the tools: known published values read off
the DOF snapshot files must come back out of get_forecast / get_components
exactly. Offline — runs against the committed snapshots. The heavier
reproducibility gate (P3 microdata sums == served totals) runs in the
adapter's verify() during the session rebuild."""

import pytest

from sdo_mcp import server


def _point(res, year):
    return next(p for p in res["series"] if p["year"] == year)


def test_state_population_boundary_2025_2026():
    res = server.get_forecast("CA", "state", "California", "population")
    assert res["status"] == "ok"
    assert _point(res, 2025) == {"year": 2025, "value": 39528899, "datatype": "estimate"}
    assert _point(res, 2026) == {"year": 2026, "value": 39567317, "datatype": "projection"}
    years = [p["year"] for p in res["series"]]
    assert (years[0], years[-1]) == (2020, 2070)
    assert "Vintage 2026" in res["source"]["vintage"]
    assert res["source"]["base_year"] == 2025


def test_county_population_by_name():
    res = server.get_forecast("CA", "county", "Los Angeles", "population", 2025, 2026)
    assert res["status"] == "ok"
    assert res["geo"]["id"] == "06037"
    assert _point(res, 2025) == {"year": 2025, "value": 9853435, "datatype": "estimate"}
    assert _point(res, 2026) == {"year": 2026, "value": 9811358, "datatype": "projection"}


def test_households_are_p4_with_2040_horizon():
    res = server.get_forecast("CA", "state", "CA", "households")
    assert res["status"] == "ok"
    assert _point(res, 2025) == {"year": 2025, "value": 13993318, "datatype": "estimate"}
    assert _point(res, 2026) == {"year": 2026, "value": 14089261, "datatype": "projection"}
    assert res["series"][-1]["year"] == 2040  # P-4 horizon, not LRCF's 2055
    assert "P-4" in res["source"]["product"]
    assert "never merged" in res["source"]["method_notes"]


def test_employment_is_lrcf_farm_plus_nonfarm():
    res = server.get_forecast("CA", "county", "Alameda", "employment")
    assert res["status"] == "ok"
    assert _point(res, 2055)["value"] == pytest.approx(730.964983064773 + 864885.192079286)
    assert _point(res, 2024)["datatype"] == "estimate"
    assert _point(res, 2025)["datatype"] == "projection"
    assert res["series"][-1]["year"] == 2055
    src = res["source"]
    assert "Economic Research Unit" in src["agency"]
    assert "Farm + Total Nonfarm" in src["method_notes"]


def test_components_recorded_under_period_end_year():
    res = server.get_components("CA", "Alameda", 2021, 2021)
    assert res["status"] == "ok"
    assert res["series"] == [
        {"year": 2021, "datatype": "estimate",
         "births": 16738, "deaths": 11595, "net_migration": -27689}
    ]


def test_place_refusal_points_to_county():
    res = server.get_forecast("CA", "place", "Sacramento", "population")
    assert res["status"] == "not_published"
    assert "county" in {p["geo_level"] for p in res["closest_published"]}
