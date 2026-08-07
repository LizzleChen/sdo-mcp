"""Texas round-trips through the tools: known published values (confirmed
against TDC's Projections/Totals API at acquire time) must come back out of
get_forecast exactly, per scenario. Offline — runs against the committed
scenario zips."""

from sdo_mcp import server


def _point(res, year):
    return next(p for p in res["series"] if p["year"] == year)


def test_state_defaults_to_mid_scenario():
    res = server.get_forecast("TX", "state", "Texas", "population")
    assert res["status"] == "ok"
    assert res["scenario"] == "mid"
    assert "recommended" in res["scenario_note"]
    assert _point(res, 2020) == {"year": 2020, "value": 29145505, "datatype": "estimate"}
    assert _point(res, 2024) == {"year": 2024, "value": 31290831, "datatype": "estimate"}
    assert _point(res, 2025) == {"year": 2025, "value": 31669507, "datatype": "projection"}
    years = [p["year"] for p in res["series"]]
    assert (years[0], years[-1]) == (2020, 2060)
    assert len(years) == len(set(years))  # the 2020 duplicate row is gone


def test_county_scenarios_differ():
    mid = server.get_forecast("TX", "county", "Harris", "population", scenario="mid")
    high = server.get_forecast("TX", "county", "Harris", "population", scenario="high")
    low = server.get_forecast("TX", "county", "Harris", "population", scenario="low")
    assert mid["geo"]["id"] == "48201"
    assert _point(mid, 2060)["value"] == 6865248
    assert _point(low, 2060)["value"] < _point(mid, 2060)["value"] < _point(high, 2060)["value"]
    # All three scenarios share the same estimate history.
    assert _point(low, 2020) == _point(mid, 2020) == _point(high, 2020)


def test_anderson_county_matches_totals_api():
    res = server.get_forecast("TX", "county", "Anderson", "population", 2030, 2060)
    assert res["status"] == "ok"
    assert _point(res, 2030)["value"] == 60080
    assert _point(res, 2060)["value"] == 59622


def test_source_records_vintage_and_2020_convention():
    res = server.get_forecast("TX", "state", "48", "population", 2020, 2020)
    src = res["source"]
    assert src["vintage"] == "2024" and src["base_year"] == 2024
    assert "April 1 Census" in src["method_notes"]
    assert src["retrieved_at"]


def test_msa_is_published_but_not_ingested():
    res = server.get_forecast("TX", "msa", "Austin", "population")
    # Honest split: not a refusal ("TDC doesn't publish this") but an error
    # naming the missing geography list — the coverage row says available.
    assert res["status"] == "error"
    assert "no msa geography list loaded" in res["error"]
