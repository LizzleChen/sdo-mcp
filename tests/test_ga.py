"""Georgia round-trips through the tools: known published values (recorded in
plan/RESEARCH.md from the 2026-vintage OPB files) must come back out of
get_forecast exactly. Offline — runs against the committed snapshots."""

from sdo_mcp import server


def _point(res, year):
    return next(p for p in res["series"] if p["year"] == year)


def test_state_population_round_trip():
    res = server.get_forecast("GA", "state", "Georgia", "population")
    assert res["status"] == "ok"
    assert _point(res, 2026) == {"year": 2026, "value": 11422803, "datatype": "projection"}
    years = [p["year"] for p in res["series"]]
    assert (years[0], years[-1]) == (2026, 2065)
    src = res["source"]
    assert src["vintage"] == "2026" and src["base_year"] == 2025
    assert "OPB" in src["agency"] and "Georgia" in src["agency"]


def test_county_population_by_name_no_fips_in_source():
    # The source file carries names only; the FIPS comes from the Census join.
    res = server.get_forecast("GA", "county", "Appling", "population", 2026, 2026)
    assert res["status"] == "ok"
    assert res["geo"]["id"] == "13001"
    assert res["series"] == [{"year": 2026, "value": 19287, "datatype": "projection"}]


def test_everything_is_projection():
    res = server.get_forecast("GA", "county", "Fulton", "population")
    assert res["status"] == "ok"
    assert all(p["datatype"] == "projection" for p in res["series"])


def test_households_refusal_is_structural():
    res = server.get_forecast("GA", "state", "GA", "households")
    assert res["status"] == "not_published"
