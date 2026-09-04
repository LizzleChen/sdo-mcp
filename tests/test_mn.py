"""Minnesota's published values and projection-only boundary round-trip."""

from sdo_mcp import server


def _point(res, year):
    return next(p for p in res["series"] if p["year"] == year)


def test_state_population_is_projection_from_launch_year():
    res = server.get_forecast("MN", "state", "Minnesota", "population")
    assert res["status"] == "ok"
    assert _point(res, 2024) == {"year": 2024, "value": 5777995, "datatype": "projection"}
    assert _point(res, 2075) == {"year": 2075, "value": 6112793, "datatype": "projection"}
    assert all(p["datatype"] == "projection" for p in res["series"])
    assert res["source"]["base_year"] == 2022
    assert "2024 launch value is itself a projection" in res["source"]["method_notes"]


def test_county_totals_are_summed_from_age_and_sex():
    res = server.get_forecast("MN", "county", "Hennepin", "population")
    assert res["status"] == "ok"
    assert res["geo"]["id"] == "27053"
    assert _point(res, 2024)["value"] == 1270261
    assert _point(res, 2050)["value"] == 1227870
    assert res["series"][-1]["year"] == 2055


def test_statewide_components_round_trip():
    res = server.get_components("MN", "MN", 2024, 2024)
    assert res["status"] == "ok"
    assert res["series"] == [{
        "year": 2024,
        "datatype": "projection",
        "births": 63284,
        "deaths": 46611,
        "net_migration": 10595,
    }]


def test_county_components_and_households_are_structural_refusals():
    components = server.get_components("MN", "Hennepin")
    assert components["status"] == "not_published"
    households = server.get_forecast("MN", "county", "Hennepin", "households")
    assert households["status"] == "not_published"
