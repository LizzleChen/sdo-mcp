"""Florida round-trips through the tools: known published values read off the
BEBR 2026-edition snapshot must come back out of get_forecast exactly, per
scenario. Offline — runs against the committed snapshot."""

from sdo_mcp import server


def _point(res, year):
    return next(p for p in res["series"] if p["year"] == year)


def test_state_defaults_to_medium_and_carries_base_estimate():
    res = server.get_forecast("FL", "state", "Florida", "population")
    assert res["status"] == "ok"
    assert res["scenario"] == "medium"
    assert _point(res, 2025) == {"year": 2025, "value": 23379261, "datatype": "estimate"}
    assert _point(res, 2050) == {"year": 2050, "value": 28250100, "datatype": "projection"}
    years = [p["year"] for p in res["series"]]
    assert years == [2025, 2030, 2035, 2040, 2045, 2050]  # 5-year steps, no annual
    src = res["source"]
    assert src["base_year"] == 2025 and src["horizon_year"] == 2050
    assert "rounded to the nearest 100" in src["method_notes"]
    assert "December 2025" in src["method_notes"]  # vintage-skew traceability


def test_county_scenarios_by_name_no_fips_in_source():
    low = server.get_forecast("FL", "county", "Alachua", "population", scenario="low")
    high = server.get_forecast("FL", "county", "Alachua", "population", scenario="high")
    assert low["geo"]["id"] == "12001"
    assert _point(low, 2030)["value"] == 295400
    assert _point(high, 2050)["value"] == 410700
    # Shared base estimate across scenarios.
    assert _point(low, 2025) == _point(high, 2025)


def test_county_households_points_to_state_pdf_only():
    res = server.get_forecast("FL", "county", "Miami-Dade", "households")
    assert res["status"] == "state_level_only"
    assert res["closest_published"][0]["status"] == "pdf_only"


def test_all_six_pilot_states_loaded():
    res = server.list_states()
    assert all(s["data_loaded"] for s in res["states"].values()), {
        k: v["data_loaded"] for k, v in res["states"].items()
    }
