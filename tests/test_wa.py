"""Washington's state and county products remain separate and round-trip."""

from sdo_mcp import server


def _point(res, year):
    return next(p for p in res["series"] if p["year"] == year)


def test_state_uses_newer_single_series_not_gma_comparison():
    res = server.get_forecast("WA", "state", "Washington", "population")
    assert res["status"] == "ok"
    assert res["scenario"] is None
    assert _point(res, 2025) == {"year": 2025, "value": 8115100, "datatype": "estimate"}
    assert _point(res, 2050) == {"year": 2050, "value": 9719108, "datatype": "projection"}
    assert res["source"]["base_year"] == 2025
    assert "State Population" in res["source"]["product"]


def test_state_rejects_county_scenario_choice():
    res = server.get_forecast("WA", "state", "WA", "population", scenario="high")
    assert res["status"] == "error"
    assert "single series" in res["error"]


def test_king_county_defaults_to_gma_medium():
    res = server.get_forecast("WA", "county", "King", "population")
    assert res["status"] == "ok"
    assert res["scenario"] == "medium"
    assert res["geo"]["id"] == "53033"
    assert _point(res, 2020)["value"] == 2269675
    assert _point(res, 2025) == {"year": 2025, "value": 2377737, "datatype": "projection"}
    assert _point(res, 2050)["value"] == 2879176
    assert "Growth Management Act" in res["source"]["product"]


def test_gma_gap_is_not_filled():
    res = server.get_forecast("WA", "county", "King", "population")
    years = [p["year"] for p in res["series"]]
    assert years[:4] == [2020, 2021, 2022, 2025]
    assert 2023 not in years and 2024 not in years


def test_unloaded_components_and_pdf_employment_are_explicit():
    components = server.get_components("WA", "WA")
    assert components["status"] == "not_loaded"
    jobs = server.get_forecast("WA", "state", "WA", "employment")
    assert jobs["status"] == "pdf_only"
