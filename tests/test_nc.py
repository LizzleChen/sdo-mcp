"""North Carolina round-trips through the tools: known published values
(recorded in plan/EXPANSION.md from the Vintage 2025B files, reconciled
CSV <-> summary page <-> ODS API) must come back out of get_forecast exactly.
Offline — runs against the committed snapshot."""

from sdo_mcp import server


def _point(res, year):
    return next(p for p in res["series"] if p["year"] == year)


def test_state_population_round_trip():
    res = server.get_forecast("NC", "state", "North Carolina", "population")
    assert res["status"] == "ok"
    assert res["geo"]["id"] == "37"  # not the CSV's pseudo-FIPS 37000
    assert _point(res, 2024) == {"year": 2024, "value": 11052495, "datatype": "estimate"}
    assert _point(res, 2025)["datatype"] == "projection"
    assert _point(res, 2060) == {"year": 2060, "value": 14511374, "datatype": "projection"}
    years = [p["year"] for p in res["series"]]
    assert (years[0], years[-1]) == (2010, 2060)
    src = res["source"]
    assert src["vintage"] == "2025B" and src["base_year"] == 2024
    assert "OSBM" in src["agency"]


def test_county_fixtures():
    wake = server.get_forecast("NC", "county", "Wake", "population")
    assert wake["status"] == "ok"
    assert wake["geo"]["id"] == "37183"
    assert _point(wake, 2024) == {"year": 2024, "value": 1235748, "datatype": "estimate"}
    assert _point(wake, 2050) == {"year": 2050, "value": 1762983, "datatype": "projection"}
    meck = server.get_forecast("NC", "county", "37119", "population", 2060, 2060)
    assert meck["series"] == [{"year": 2060, "value": 1672969, "datatype": "projection"}]


def test_estimate_projection_boundary():
    res = server.get_forecast("NC", "county", "Durham", "population")
    assert res["status"] == "ok"
    assert _point(res, 2024)["datatype"] == "estimate"
    assert _point(res, 2025) == {"year": 2025, "value": 344640, "datatype": "projection"}
    assert all(p["datatype"] == "estimate" for p in res["series"] if p["year"] <= 2024)
    assert all(p["datatype"] == "projection" for p in res["series"] if p["year"] >= 2025)


def test_no_scenarios_to_pick():
    res = server.get_forecast("NC", "state", "NC", "population", scenario="high")
    assert res["status"] == "error"
    assert "no scenarios" in res["error"]


def test_households_refusal_is_structural():
    res = server.get_forecast("NC", "state", "NC", "households")
    assert res["status"] == "not_published"
    assert res["closest_published"] is None


def test_place_forecast_refusal_points_to_county():
    res = server.get_forecast("NC", "place", "Charlotte", "population")
    assert res["status"] == "not_published"
    assert "county" in {p["geo_level"] for p in res["closest_published"]}
