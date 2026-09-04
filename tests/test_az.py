"""Arizona population and components round-trip by published scenario."""

from sdo_mcp import server


def _point(res, year):
    return next(p for p in res["series"] if p["year"] == year)


def test_state_defaults_to_medium_and_carries_estimate_launch():
    res = server.get_forecast("AZ", "state", "Arizona", "population")
    assert res["status"] == "ok"
    assert res["scenario"] == "medium"
    assert _point(res, 2025) == {"year": 2025, "value": 7718747, "datatype": "estimate"}
    assert _point(res, 2060) == {"year": 2060, "value": 9750566, "datatype": "projection"}
    assert res["source"]["base_year"] == 2025


def test_state_low_and_high_scenarios():
    low = server.get_forecast("AZ", "state", "04", "population", scenario="low")
    high = server.get_forecast("AZ", "state", "AZ", "population", scenario="high")
    assert _point(low, 2060)["value"] == 8854828
    assert _point(high, 2060)["value"] == 12294500
    assert _point(low, 2025) == _point(high, 2025)


def test_pima_county_round_trip():
    res = server.get_forecast("AZ", "county", "Pima", "population")
    assert res["geo"]["id"] == "04019"
    assert _point(res, 2025)["value"] == 1093761
    assert _point(res, 2060)["value"] == 1143575


def test_components_follow_the_selected_scenario():
    medium = server.get_components("AZ", "Arizona", 2025, 2025)
    assert medium["status"] == "ok"
    assert medium["scenario"] == "medium"
    assert medium["series"] == [{
        "year": 2025,
        "datatype": "estimate",
        "births": 78764,
        "deaths": 71016,
        "net_migration": 87805,
    }]
    high = server.get_components("AZ", "Pima", 2060, 2060, scenario="high")
    assert high["status"] == "ok" and high["scenario"] == "high"
    assert high["series"][0]["datatype"] == "projection"


def test_place_and_households_are_structural_refusals():
    place = server.get_forecast("AZ", "place", "Phoenix", "population")
    assert place["status"] == "not_published"
    assert "stale" in place["reason"]
    households = server.get_forecast("AZ", "county", "Maricopa", "households")
    assert households["status"] == "not_published"
