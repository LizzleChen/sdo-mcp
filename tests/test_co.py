"""Colorado round-trips THROUGH THE TOOLS: known published values (captured
from the live DOLA API 2026-08-07, recorded in the adapter's FIXTURES) must
come back out of get_forecast / get_components exactly. Offline — runs
against the committed snapshots."""

from sdo_mcp import server


def _point(res, year):
    return next(p for p in res["series"] if p["year"] == year)


def test_county_population_round_trip():
    res = server.get_forecast("CO", "county", "Douglas", "population")
    assert res["status"] == "ok"
    assert res["geo"] == {"level": "county", "id": "08035", "name": "Douglas County"}
    assert _point(res, 2024) == {"year": 2024, "value": 394030, "datatype": "estimate"}
    assert _point(res, 2025) == {"year": 2025, "value": 401211, "datatype": "projection"}
    years = [p["year"] for p in res["series"]]
    assert (years[0], years[-1]) == (1970, 2060)
    src = res["source"]
    assert src["base_year"] == 2024
    assert src["retrieved_at"] and src["citation"] and src["vintage"] == "2024"


def test_state_population_and_fips_input():
    res = server.get_forecast("CO", "state", "08", "population", 2024, 2024)
    assert res["status"] == "ok"
    assert res["series"] == [{"year": 2024, "value": 5956729, "datatype": "estimate"}]


def test_households_boundary_borrowed_from_population():
    res = server.get_forecast("CO", "county", "35", "households")
    assert _point(res, 2024) == {"year": 2024, "value": 146660, "datatype": "estimate"}
    assert _point(res, 2025)["datatype"] == "projection"
    assert res["series"][-1]["year"] == 2050  # HH horizon, not 2060
    assert "borrowed" in res["source"]["method_notes"]


def test_employment_is_the_sdo_series():
    res = server.get_forecast("CO", "county", "Douglas", "employment")
    assert _point(res, 2024) == {"year": 2024, "value": 188130, "datatype": "estimate"}
    assert _point(res, 2025) == {"year": 2025, "value": 191719, "datatype": "projection"}
    assert res["series"][-1]["year"] == 2050
    assert "CDLE" in res["source"]["method_notes"]  # never the labor dept product


def test_components_round_trip():
    res = server.get_components("CO", "Douglas County", 2024, 2024)
    assert res["status"] == "ok"
    assert res["series"] == [
        {"year": 2024, "datatype": "estimate",
         "births": 3960, "deaths": 2105, "net_migration": 7034}
    ]


def test_year_range_off_the_ends_names_published_range():
    res = server.get_forecast("CO", "county", "Douglas", "population", 2100, 2110)
    assert res["status"] == "error"
    assert "1970-2060" in res["error"]


def test_co_shows_loaded_in_list_states():
    res = server.list_states()
    assert res["states"]["CO"]["data_loaded"] is True
    assert res["states"]["TX"]["data_loaded"] is False


def test_describe_source_lists_three_loaded_products():
    res = server.describe_source("CO")
    assert len(res["sources_loaded"]) == 3
    assert all(s["retrieved_at"] for s in res["sources_loaded"])
